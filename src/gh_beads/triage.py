"""Remember local reviews independently of sync-owned source observations."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

from gh_beads.sync import MANAGED_PREFIXES, Beads, Json


def source_fingerprint(bead: Json) -> str:
    """Hash imported facts, ignoring polling time, graph bookkeeping, and local workflow."""
    hub = (bead.get("metadata") or {}).get("hub") or {}
    github = {
        key: value for key, value in (hub.get("github") or {}).items() if key != "observed_at"
    }
    facts = {
        key: hub.get(key)
        for key in ("node_id", "repo_id", "repo", "kind", "number", "source_state")
    }
    facts.update(
        github=github,
        title=bead.get("title"),
        description=bead.get("description"),
        external_ref=bead.get("external_ref"),
        labels=sorted(
            label for label in bead.get("labels", []) if label.startswith(MANAGED_PREFIXES)
        ),
    )
    return hashlib.sha256(json.dumps(facts, sort_keys=True).encode()).hexdigest()


def review_history(bead: Json) -> list[Json]:
    """Fail visibly rather than discarding incompatible local review history."""
    triage = (bead.get("metadata") or {}).get("triage")
    if triage is None:
        return []
    if (
        not isinstance(triage, dict)
        or triage.get("version") != 1
        or not isinstance(triage.get("reviews"), list)
        or any(not isinstance(review, dict) for review in triage["reviews"])
    ):
        raise ValueError(
            "Invalid metadata.triage; inspect existing metadata before recording a review"
        )
    return list(triage["reviews"])


def triage_status(bead: Json) -> Json:
    """Return the latest decision and whether the imported evidence has changed since review."""
    fingerprint = source_fingerprint(bead)
    reviews = review_history(bead)
    latest = reviews[-1] if reviews else None
    return {
        "status": "unreviewed"
        if latest is None
        else ("unchanged" if latest.get("source_fingerprint") == fingerprint else "changed"),
        "source_fingerprint": fingerprint,
        "review_count": len(reviews),
        "latest": latest,
    }


def record_triage(
    bead_id: str,
    rationale: str,
    next_action: str,
    *,
    reviewer: str | None = None,
    expected_fingerprint: str | None = None,
    beads: Beads | None = None,
) -> Json:
    """Append one review, with an optional guard against reviewing newer unseen source facts."""
    actor = reviewer or os.environ.get("BEADS_ACTOR")
    if not all(
        isinstance(value, str) and value.strip() for value in (rationale, next_action, actor)
    ):
        raise ValueError("rationale, next_action, and reviewer (or BEADS_ACTOR) must be nonempty")
    if not bead_id or bead_id.startswith("-"):
        raise ValueError("A Beads issue ID is required")
    workspace = Path(os.environ.get("BEADS_WORKING_DIR", "."))
    if not (workspace / ".beads/metadata.json").is_file():
        raise RuntimeError(
            "Select an initialized hub workspace; do not initialize an unrelated checkout"
        )
    beads = beads or Beads()
    with (workspace / ".github-sync.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError(
                "Hub is busy syncing or recording a review; retry after it finishes"
            ) from exc
        shown: Any = beads.call("show", bead_id, "--readonly")
        bead = shown[0] if isinstance(shown, list) and len(shown) == 1 else shown
        if not isinstance(bead, dict) or not bead.get("id"):
            raise ValueError("Expected exactly one Beads item")
        hub = (bead.get("metadata") or {}).get("hub") or {}
        if hub.get("kind") not in {"issue", "pr"} or not hub.get("node_id"):
            raise ValueError("Triage reviews require a GitHub-backed issue or PR")
        fingerprint = source_fingerprint(bead)
        if expected_fingerprint is not None and expected_fingerprint != fingerprint:
            raise ValueError(
                "Source changed since inspection; read the item again before reviewing"
            )
        reviews = review_history(bead)
        review = {
            "reviewed_at": time.time(),
            "reviewer": actor,
            "rationale": rationale,
            "next_action": next_action,
            "source_fingerprint": fingerprint,
        }
        beads.call(
            "update",
            bead["id"],
            "--metadata",
            json.dumps({"triage": {"version": 1, "reviews": [*reviews, review]}}),
        )
    return {"id": bead["id"], "review": review, "review_count": len(reviews) + 1}
