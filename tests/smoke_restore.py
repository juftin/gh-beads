"""Validate an offline physical workspace backup against an independent restored database.

No production workspace is selected by the native exercise. Capture/verify modes are
only for the synthetic disposable Compose stack created by scripts/smoke.sh.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

from fixtures import FixtureGitHub, item

from gh_beads.snapshot import portfolio_snapshot
from gh_beads.state import SyncState
from gh_beads.sync import Beads, Json, reconcile
from gh_beads.triage import record_triage


def capture() -> Json:
    """Include source/local fields, IDs, graph, reviews, progress, and effective queues."""
    beads = Beads()
    rows = sorted(beads.items(), key=lambda row: row["id"])
    snapshot = portfolio_snapshot(limit=1000)
    return {
        "rows": rows,
        "dependencies": {
            row["id"]: sorted(
                edge["id"]
                for edge in beads.call("dep", "list", row["id"], "--type", "blocks") or []
            )
            for row in rows
        },
        "comments": {row["id"]: beads.call("comments", row["id"], "--readonly") for row in rows},
        "progress": SyncState(Path(".github-sync-state.json")).data,
        "totals": snapshot["totals"],
        "queues": snapshot["queues"],
    }


def native_restore() -> None:
    """Copy a stopped embedded database and checkpoint file, then query a fresh restore."""
    bd = shutil.which(os.environ.get("BEADS_PATH", "bd"))
    if bd is None:
        raise RuntimeError(
            "Install native bd 1.3.1 with embedded Dolt support to run smoke-restore"
        )
    original = Path.cwd()
    bd = str(Path(bd).resolve())
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("BEADS_", "BD_", "DOLT_"))
        and key not in {"GH_TOKEN", "MCP_TRANSPORT"}
    }
    env.update(
        BEADS_PATH=bd,
        BEADS_DOLT_AUTO_START="0",
        BEADS_ACTOR="synthetic-restore",
        GH_TOKEN="",
        GH_SYNC_QUERY="user:@me",
    )
    with tempfile.TemporaryDirectory(prefix="gh-beads-restore-") as directory:
        root = Path(directory)
        source, backup, restored = (root / name for name in ("source", "backup", "restored"))
        subprocess.run(["git", "init", "--quiet", str(source)], check=True)
        with patch.dict(os.environ, env, clear=True):
            os.chdir(source)
            try:
                subprocess.run(
                    [
                        bd,
                        "init",
                        "--prefix",
                        "hub",
                        "--non-interactive",
                        "--skip-agents",
                        "--skip-hooks",
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                beads = Beads()
                issue, pr = item(), item("pr", 2)
                pr["reviewDecision"] = None
                pr["closingIssuesReferences"]["nodes"] = [{"id": issue["id"]}]
                github = FixtureGitHub([issue, pr])
                state = SyncState(Path(".github-sync-state.json"))
                assert reconcile(github, beads, "user:@me", state)["status"] == "complete"
                rows = {row["metadata"]["hub"]["kind"]: row for row in beads.items()}
                issue_id, pr_id = rows["issue"]["id"], rows["pr"]["id"]
                beads.call(
                    "update",
                    pr_id,
                    "--claim",
                    "--priority",
                    "1",
                    "--notes",
                    "Keep rationale",
                    "--add-label",
                    "category:maintenance",
                    "--metadata",
                    '{"local":{"keep":true}}',
                )
                reviewed = subprocess.run(
                    [
                        "gh-beads",
                        "triage",
                        pr_id,
                        "--rationale",
                        "Reviewed source evidence",
                        "--next-action",
                        "Prepare next commit",
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                assert json.loads(reviewed.stdout)["review_count"] == 1
                record_triage(pr_id, "Retained priority after second look", "Prepare next commit")
                beads.call("comments", "add", pr_id, "Synthetic handoff survives restoration")
                # Include terminal local work while retaining an active source and graph edge.
                beads.call("close", issue_id, "--force")
                assert reconcile(github, beads, "user:@me", state)["status"] == "complete"
                assert reconcile(github, beads, "user:@me", state)["writes"] == 0
                baseline = capture()
                snapshot_cli = subprocess.run(
                    ["gh-beads", "snapshot", "--json", "--limit", "1000"],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                assert json.loads(snapshot_cli.stdout)["queues"] == baseline["queues"]
                assert baseline["queues"]["in_progress"]["items"][0]["triage"]["review_count"] == 2
                # All clients are one-shot processes and have exited: copy the entire offline
                # workspace, not issue JSONL or files from an active Dolt writer.
                backup.mkdir()
                shutil.copytree(source / ".beads", backup / ".beads")
                shutil.copy2(source / ".github-sync-state.json", backup / ".github-sync-state.json")
                beads.call("update", pr_id, "--notes", "Changed after backup")
                assert capture() != baseline
                shutil.copytree(backup, restored)
                subprocess.run(["git", "init", "--quiet", str(restored)], check=True)
                os.chdir(restored)
                assert capture() == baseline, (
                    "Restored source facts, local decisions, graph, or progress differ"
                )
                result = reconcile(
                    github, Beads(), "user:@me", SyncState(Path(".github-sync-state.json"))
                )
                assert result["status"] == "complete" and result["writes"] == 0, result
                assert capture()["rows"] == baseline["rows"]
            finally:
                os.chdir(original)
    print("Embedded backup and independent restore preserve IDs, graph, triage, and checkpoints.")


def main() -> None:
    """Exercise native restore, or compare a disposable SQL stack to its saved baseline."""
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--capture", type=Path)
    mode.add_argument("--verify", type=Path)
    args = parser.parse_args()
    if args.capture:
        args.capture.write_text(json.dumps(capture(), sort_keys=True))
    elif args.verify:
        assert capture() == json.loads(args.verify.read_text()), (
            "Restore differs from the saved baseline"
        )
        print("Restored Compose volume matches fields, graph, reviews, queues, and progress.")
    else:
        native_restore()


if __name__ == "__main__":
    main()
