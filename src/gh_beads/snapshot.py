"""Build a bounded portfolio view from stored Beads data without contacting GitHub."""

from __future__ import annotations

import argparse
import json
import os
import time
from collections import Counter
from pathlib import Path

from gh_beads.state import SyncState
from gh_beads.sync import Beads, Json, repository_scopes
from gh_beads.triage import triage_status

ATTENTION = {
    "ci:failing",
    "ci:unknown",
    "ci:pending",
    "conflict:true",
    "conflict:unknown",
    "review:changes-requested",
    "review:needed",
    "draft:true",
}


def hub_metadata(bead: Json) -> Json:
    """Read sync-owned identity without requiring source bodies in output."""
    metadata: Json = (bead.get("metadata") or {}).get("hub") or {}
    return metadata


def portfolio_snapshot(
    repositories: list[str] | None = None,
    limit: int = 20,
    *,
    beads: Beads | None = None,
    state: SyncState | None = None,
) -> Json:
    """Read complete counts and bounded queues; coverage describes last successful discovery."""
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
        raise ValueError("limit must be between 1 and 1000")
    scopes = repository_scopes(repositories)
    workspace = Path(os.environ.get("BEADS_WORKING_DIR", ".")).resolve()
    if not (workspace / ".beads/metadata.json").is_file():
        raise RuntimeError(
            "Select an initialized hub workspace; do not initialize an unrelated checkout"
        )
    state = state or SyncState(workspace / ".github-sync-state.json")
    beads = beads or Beads()
    now = time.time()
    info = beads.call("info", "--readonly")
    rows = beads.call("list", "--all", "--limit", "0", "--flat", "--readonly") or []
    ready = {row["id"] for row in beads.call("ready", "--limit", "0", "--readonly") or []}
    blocked = {row["id"] for row in beads.call("blocked", "--readonly") or []}
    imported = [row for row in rows if hub_metadata(row).get("kind") in {"issue", "pr"}]
    inventory = state.data.get("inventories", {}).get(state.scope_key(scopes))
    known = {
        repo_id: entry.get("name")
        for repo_id, entry in state.data["repositories"].items()
        if entry.get("name")
    }
    known.update(
        {
            hub_metadata(row)["repo_id"]: hub_metadata(row)["repo"]
            for row in rows
            if hub_metadata(row).get("repo_id") and hub_metadata(row).get("repo")
        }
    )
    scope_parts = [part.strip().lower() for part in scopes.split(";") if part.strip()]
    explicit_scopes = bool(scope_parts) and all(part.startswith("repo:") for part in scope_parts)
    requested = {name.lower() for name in repositories or []}
    if repositories is None and explicit_scopes:
        requested = {part.removeprefix("repo:") for part in scope_parts}
    if inventory is not None:
        selected = {repo["node_id"]: repo["name"] for repo in inventory["repositories"]}
    else:
        selected = {
            repo_id: name
            for repo_id, name in known.items()
            if not requested or name.lower() in requested
        }
    imported = [row for row in imported if hub_metadata(row).get("repo_id") in selected]
    imported.sort(
        key=lambda row: (int(row.get("priority", 2)), hub_metadata(row)["repo"], row["id"])
    )
    summaries: list[Json] = []
    reasons = (
        []
        if inventory is not None
        else ["No discovery recorded for these scopes; coverage is unknown"]
    )
    for repo_id, name in sorted(selected.items(), key=lambda pair: pair[1].lower()):
        entry = state.data["repositories"].get(repo_id, {})
        items = [row for row in imported if hub_metadata(row)["repo_id"] == repo_id]
        success = entry.get("last_success_at")
        if not success or entry.get("error"):
            reasons.append(f"{name}: {entry.get('error') or 'never successfully synced'}")
        summaries.append(
            {
                "id": repo_id,
                "name": name,
                "url": f"https://github.com/{name}",
                "last_success_at": success,
                "age_seconds": max(0, now - success) if success else None,
                "last_full_at": entry.get("last_full_at"),
                "error": entry.get("error"),
                "source_states": dict(
                    Counter(hub_metadata(row).get("source_state", "unknown") for row in items)
                ),
                "local_statuses": dict(Counter(row.get("status", "unknown") for row in items)),
                "items": len(items),
            }
        )
    unknown = sorted(requested - {name.lower() for name in selected.values()})
    if unknown:
        reasons.append("Repositories not in the resolved inventory: " + ", ".join(unknown))
    compact: list[Json] = []
    for row in imported:
        hub = hub_metadata(row)
        url_kind = "pull" if hub["kind"] == "pr" else "issues"
        compact.append(
            {
                "id": row["id"],
                "repository": hub["repo"],
                "kind": hub["kind"],
                "number": hub["number"],
                "title": row.get("title"),
                "url": f"https://github.com/{hub['repo']}/{url_kind}/{hub['number']}",
                "source_state": hub.get("source_state"),
                "status": row.get("status"),
                "priority": row.get("priority", 2),
                "assignee": row.get("assignee"),
                "labels": row.get("labels", []),
                "triage": triage_status(row),
            }
        )

    def queue(items: list[Json]) -> Json:
        return {
            "total": len(items),
            "returned": min(limit, len(items)),
            "truncated": len(items) > limit,
            "items": items[:limit],
        }

    active = [row for row in compact if row["source_state"] == "OPEN"]
    return {
        "version": 1,
        "generated_at": now,
        "workspace": {
            "path": str(workspace),
            "database_path": info.get("database_path"),
            "mode": info.get("mode"),
        },
        "coverage": {
            "status": "partial" if reasons else "complete",
            "reasons": reasons,
            "scopes": scopes,
            "selection": "resolved inventory"
            if inventory is not None
            else ("explicit repository names" if requested else "historical fallback"),
            "discovered_at": inventory.get("discovered_at") if inventory else None,
            "retry_at": state.data.get("retry_at", 0),
            "unresolved_repositories": unknown,
            "consistency": "best effort across separate stored reads; no live GitHub requests",
        },
        "repositories": summaries,
        "totals": {
            "items": len(compact),
            "source_states": dict(Counter(row["source_state"] for row in compact)),
            "local_statuses": dict(Counter(row["status"] for row in compact)),
        },
        "queues": {
            "ready": queue([row for row in active if row["id"] in ready]),
            "blocked": queue([row for row in active if row["id"] in blocked]),
            "in_progress": queue([row for row in active if row["status"] == "in_progress"]),
            "needs_attention": queue([row for row in active if set(row["labels"]) & ATTENTION]),
            "unreviewed": queue([row for row in active if row["triage"]["status"] == "unreviewed"]),
            "changed_since_review": queue(
                [row for row in compact if row["triage"]["status"] == "changed"]
            ),
        },
    }


def main() -> None:
    """Print the stored portfolio as JSON, including explicit coverage and truncation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", action="append", dest="repositories")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--json", action="store_true", help="JSON output (the default)")
    args = parser.parse_args()
    try:
        result = portfolio_snapshot(args.repositories, args.limit)
    except (RuntimeError, ValueError) as exc:
        parser.exit(1, f"{exc}\n")
    print(json.dumps(result))
