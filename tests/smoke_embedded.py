"""Exercise repository-local embedded Dolt, polling, and stdio without Docker or a SQL server."""

from __future__ import annotations

import asyncio
import fcntl
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from fixtures import FixtureGitHub, item

from gh_beads.sync import Beads, run_sync


def check_workflow(beads: Beads) -> None:
    """Exercise custom categories, native types, metadata, and repeat sync against real bd."""
    rows = {row["metadata"]["hub"]["kind"]: row for row in beads.items()}
    assert rows["issue"]["issue_type"] == "github_issue"
    assert rows["pr"]["issue_type"] == "pull_request"
    source = rows["pr"]["metadata"]["hub"]["github"]
    assert source["body"] == "Synthetic source body"
    assert source["labels"] == ["bug", "label,with,commas"]
    statuses = {row["name"]: row["category"] for row in beads.call("statuses")["custom_statuses"]}
    assert statuses == {"qa": "wip", "in_review": "wip", "backlog": "active", "icebox": "frozen"}
    assert "incident" in beads.call("types")["custom_types"]
    pr = rows["pr"]
    for status, ready in [("in_review", False), ("backlog", True), ("icebox", False)]:
        beads.call("update", pr["id"], "--status", status)
        assert (pr["id"] in {row["id"] for row in beads.call("ready", "--limit", "0")}) == ready
        visible = {row["id"] for row in beads.call("list", "--limit", "0", "--flat")}
        assert (pr["id"] in visible) == (status != "icebox")
        assert run_sync()["writes"] == 0
        current = next(row for row in beads.items() if row["id"] == pr["id"])
        assert current["status"] == status
    beads.call("update", pr["id"], "--status", pr["status"])


async def check_clients(source: FixtureGitHub, beads: Beads) -> None:
    """Overlap real MCP reads with poller writes, then reopen MCP to verify durable state."""
    issue_id = next(row["id"] for row in beads.items() if row["metadata"]["hub"]["kind"] == "issue")
    beads.call("update", issue_id, "--priority", "1", "--notes", "Synthetic local reasoning")
    for session in range(2):
        transport = StdioTransport(command="gh-beads-mcp", args=[], env=dict(os.environ))
        async with asyncio.timeout(180), Client(transport) as client:
            assert "ready" in {tool.name for tool in await client.list_tools()}
            assert await client.read_resource("beads://quickstart")
            if session == 0:
                for status in ("in_review", "backlog", "icebox"):
                    updated = await client.call_tool(
                        "update", {"issue_id": issue_id, "status": status}
                    )
                    assert not updated.is_error
                    snapshot = await client.call_tool("portfolio_snapshot", {})
                    assert snapshot.data["queues"][status]["items"][0]["id"] == issue_id
                beads.call("update", issue_id, "--status", "open")
                reviewed = await client.call_tool(
                    "record_triage",
                    {
                        "bead_id": issue_id,
                        "rationale": "Synthetic source review",
                        "next_action": "Read next source change",
                        "reviewer": "smoke-agent",
                    },
                )
                assert reviewed.data["review_count"] == 1

                async def poll() -> None:
                    """Write changed snapshots through the normal sync lock and checkpoints."""
                    for number in range(2):
                        source.rows[0]["title"] = f"Synthetic revision {number}"
                        result = await asyncio.to_thread(run_sync)
                        assert result["status"] == "complete", result

                async def read() -> None:
                    """Read the same embedded database through separate MCP bd subprocesses."""
                    for _ in range(3):
                        result = await client.call_tool("stats", {})
                        assert not result.is_error

                await asyncio.gather(poll(), read())
                with Path(".github-sync.lock").open("w") as lock:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    result = await client.call_tool("trigger_github_sync", {})
                    assert result.data["status"] == "busy"
            result = await client.call_tool("show", {"issue_id": issue_id})
            assert not result.is_error
            snapshot = await client.call_tool("portfolio_snapshot", {})
            assert snapshot.data["coverage"]["status"] == "complete"
            assert snapshot.data["queues"]["changed_since_review"]["items"][0]["id"] == issue_id
    rows = beads.items()
    issue = next(row for row in rows if row["id"] == issue_id)
    assert len(rows) == 3 and issue["title"].endswith("Synthetic revision 1")
    epic = next(row for row in rows if row["metadata"]["hub"]["kind"] == "repository")
    assert epic["issue_type"] == "epic" and issue["parent"] == epic["id"]
    assert issue["priority"] == 1 and issue["notes"] == "Synthetic local reasoning"
    assert len(beads.call("dep", "list", issue_id, "--type", "blocks")) == 1
    assert run_sync()["writes"] == 0


def main() -> None:
    """Bootstrap a disposable repository using the installed native bd and embedded defaults."""
    bd = shutil.which(os.environ.get("BEADS_PATH", "bd"))
    if bd is None:
        raise RuntimeError("Install native bd 1.3.1 with embedded Dolt support to run smoke-local")
    bd = str(Path(bd).resolve())
    original = Path.cwd()
    with tempfile.TemporaryDirectory(prefix="gh-beads-embedded-") as directory:
        workspace = Path(directory)
        subprocess.run(["git", "init", "--quiet", str(workspace)], check=True)
        env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith(("BEADS_", "BD_", "DOLT_"))
            and key not in {"GH_TOKEN", "MCP_TRANSPORT"}
        }
        env.update(
            BEADS_PATH=bd,
            BEADS_DOLT_AUTO_START="0",
            BEADS_ACTOR="synthetic-embedded-smoke",
            GH_TOKEN="",
            MCP_PORT="unused",
        )
        with patch.dict(os.environ, env, clear=True):
            os.chdir(workspace)
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
                metadata = json.loads(Path(".beads/metadata.json").read_text())
                assert metadata["dolt_mode"] == "embedded"
                assert Path(".beads/embeddeddolt").is_dir()
                beads = Beads()
                beads.call("config", "set", "status.custom", "qa:wip")
                beads.call("config", "set", "types.custom", "incident")
                subprocess.run(
                    ["gh-beads-runtime", "--configure-workflow"], check=True, timeout=120
                )
                issue, pr = item(), item("pr", number=2)
                pr["closingIssuesReferences"]["nodes"] = [{"id": issue["id"]}]
                source = FixtureGitHub([issue, pr])
                source.client = MagicMock()
                source.retry_at = 0
                with patch("gh_beads.sync.GitHub", return_value=source):
                    result = run_sync()
                    assert result["status"] == "complete", result
                    check_workflow(beads)
                    asyncio.run(check_clients(source, beads))
                status = subprocess.run(
                    ["gh-beads-sync", "--status"],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                progress = json.loads(status.stdout)
                assert progress["repositories"]["R_1"]["checkpoint"] > 0
            finally:
                os.chdir(original)
    print("Embedded Dolt bootstrap, concurrent polling/stdio, locking, and persistence pass.")


if __name__ == "__main__":
    main()
