"""Check portfolio coverage, source-change reviews, and preservation of local decisions."""

from __future__ import annotations

import copy
import fcntl
import json
from pathlib import Path
from typing import Any

import pytest
from fixtures import FixtureGitHub, item, repository
from test_sync import MemoryBeads

from gh_beads.snapshot import portfolio_snapshot
from gh_beads.state import SyncState
from gh_beads.sync import reconcile
from gh_beads.triage import record_triage, source_fingerprint, triage_status


class PortfolioBeads(MemoryBeads):
    """Supply explicit CLI readiness results without duplicating Beads graph policy."""

    ready_ids: set[str] = set()
    blocked_ids: set[str] = set()

    def call(self, *args: str) -> Any:
        if args[0] == "info":
            self.calls.append(args)
            return {"database_path": "/synthetic/database", "mode": "direct"}
        if args[0] in {"ready", "blocked"}:
            self.calls.append(args)
            ids = self.ready_ids if args[0] == "ready" else self.blocked_ids
            return [{"id": bead_id} for bead_id in sorted(ids)]
        if args[0] == "show":
            self.calls.append(args)
            return [copy.deepcopy(self.rows[args[1]])]
        return super().call(*args)


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / ".beads").mkdir()
    (tmp_path / ".beads/metadata.json").write_text("{}")
    monkeypatch.setenv("BEADS_WORKING_DIR", str(tmp_path))
    monkeypatch.setenv("GH_SYNC_QUERY", "user:@me")
    monkeypatch.setenv("BEADS_ACTOR", "synthetic-reviewer")
    return tmp_path


def test_snapshot_complete_bounded_readonly(workspace: Path) -> None:
    beads, state = PortfolioBeads(), SyncState()
    empty = repository("example/empty", "R_empty")
    issue, pr = item(), item("pr", 2)
    pr["reviewDecision"] = None
    reconcile(FixtureGitHub([issue, pr], repos=[repository(), empty]), beads, "user:@me", state)
    beads.ready_ids, beads.blocked_ids = {"hub-2"}, {"hub-1"}
    beads.rows["hub-2"].update(status="deferred", assignee="owner")
    beads.calls.clear()
    result = portfolio_snapshot(limit=1, beads=beads, state=state)
    assert result["coverage"]["status"] == "complete"
    assert result["workspace"]["path"] == str(workspace)
    assert result["totals"] == {
        "items": 2,
        "source_states": {"OPEN": 2},
        "local_statuses": {"open": 1, "deferred": 1},
    }
    assert result["repositories"][0]["name"] == "example/empty"
    assert result["repositories"][0]["items"] == 0
    assert result["queues"]["blocked"]["items"][0]["id"] == "hub-1"
    assert result["queues"]["needs_attention"]["items"][0]["assignee"] == "owner"
    assert result["queues"]["unreviewed"]["total"] == 2
    assert result["queues"]["unreviewed"]["truncated"] is True
    assert result["queues"]["unreviewed"]["returned"] == 1
    assert "description" not in result["queues"]["ready"]["items"][0]
    assert all("--readonly" in args for args in beads.calls)
    assert not (workspace / ".github-sync.lock").exists()
    assert not (workspace / ".github-sync-state.json").exists()


def test_snapshot_custom_workflow_queues(workspace: Path) -> None:
    """Keep manual review/backlog/icebox work visible with native types and stored links."""
    beads, state = PortfolioBeads(), SyncState()
    reconcile(FixtureGitHub([item(number=n) for n in range(1, 4)]), beads, "user:@me", state)
    for bead_id, status in zip(beads.rows, ["open", "in_review", "backlog", "icebox"], strict=True):
        beads.rows[bead_id]["status"] = status
    beads.rows["hub-1"]["metadata"]["hub"]["github"]["url"] = (
        "https://github.com/example/canonical/issues/1"
    )
    result = portfolio_snapshot(beads=beads, state=state)
    assert result["queues"]["in_progress"]["total"] == 1
    for status in ("in_review", "backlog", "icebox"):
        row = result["queues"][status]["items"][0]
        assert row["status"] == status and row["issue_type"] == "github_issue"
    assert (
        result["queues"]["in_review"]["items"][0]["url"]
        == "https://github.com/example/canonical/issues/1"
    )


def test_scope_inventory_survives_selected_runs_and_restart(workspace: Path) -> None:
    beads, state = PortfolioBeads(), SyncState(workspace / ".github-sync-state.json")
    first, second = repository(), repository("example/other", "R_2")
    reconcile(FixtureGitHub([item()], repos=[first, second]), beads, "user:@me", state)
    reconcile(FixtureGitHub([], repos=[second]), beads, "repo:example/other", state)
    state = SyncState(state.path)
    result = portfolio_snapshot(beads=beads, state=state)
    assert len(result["repositories"]) == 2
    selected = portfolio_snapshot(["EXAMPLE/OTHER"], beads=beads, state=state)
    assert [repo["id"] for repo in selected["repositories"]] == ["R_2"]
    assert selected["totals"]["items"] == 0
    assert selected["coverage"]["status"] == "complete"
    unknown = portfolio_snapshot(["example/missing"], beads=beads, state=state)
    assert unknown["coverage"]["status"] == "partial"
    assert unknown["coverage"]["unresolved_repositories"] == ["example/missing"]
    state.data["repositories"]["R_2"]["error"] = "Synthetic API outage"
    assert portfolio_snapshot(beads=beads, state=state)["coverage"]["status"] == "partial"


def test_old_state_and_changed_configuration_report_unknown(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    beads, state = PortfolioBeads(), SyncState()
    reconcile(FixtureGitHub([item()]), beads, "user:@me", state)
    monkeypatch.setenv("GH_SYNC_QUERY", "org:different")
    assert portfolio_snapshot(beads=beads, state=state)["coverage"]["status"] == "partial"
    del state.data["inventories"]
    state.data["retry_at"] = 9999999999
    result = portfolio_snapshot(beads=beads, state=state)
    assert result["coverage"]["discovered_at"] is None
    assert result["coverage"]["retry_at"] == 9999999999
    assert result["totals"]["items"] == 1
    monkeypatch.setenv("GH_SYNC_QUERY", "repo:example/different")
    narrowed = portfolio_snapshot(beads=beads, state=state)
    assert narrowed["totals"]["items"] == 0
    assert narrowed["coverage"]["unresolved_repositories"] == ["example/different"]


def test_reviews_survive_sync_and_detect_new_source(workspace: Path) -> None:
    beads, state = PortfolioBeads(), SyncState()
    source = FixtureGitHub([item()])
    reconcile(source, beads, "user:@me", state)
    row = beads.rows["hub-1"]
    row.update(priority=1, assignee="owner", notes="Keep these notes")
    row["metadata"]["custom"] = {"team": "example"}
    fingerprint = source_fingerprint(row)
    record_triage(
        "hub-1",
        "Reproduce before patching",
        "Add reproduction",
        beads=beads,
        expected_fingerprint=fingerprint,
    )
    assert triage_status(row)["status"] == "unchanged"
    row["labels"].append("category:bug-fix")
    row["metadata"]["hub"]["github"]["observed_at"] = "different polling time"
    assert source_fingerprint(row) == fingerprint
    reconcile(source, beads, "user:@me", state)
    assert triage_status(row)["status"] == "unchanged"
    source.rows[0]["title"] = "New source evidence"
    reconcile(source, beads, "user:@me", state)
    assert triage_status(row)["status"] == "changed"
    assert (
        portfolio_snapshot(beads=beads, state=state)["queues"]["changed_since_review"]["total"] == 1
    )
    with pytest.raises(ValueError, match="Source changed"):
        record_triage(
            "hub-1", "Old review", "Old action", beads=beads, expected_fingerprint=fingerprint
        )
    record_triage("hub-1", "Evidence accepted", "Implement fix", beads=beads)
    assert triage_status(row)["review_count"] == 2
    assert triage_status(row)["latest"]["reviewer"] == "synthetic-reviewer"
    assert row["metadata"]["custom"] == {"team": "example"}
    assert (row["priority"], row["assignee"], row["notes"]) == (1, "owner", "Keep these notes")
    source.rows[0]["state"] = "CLOSED"
    reconcile(source, beads, "user:@me", state)
    assert (
        portfolio_snapshot(beads=beads, state=state)["queues"]["changed_since_review"]["total"] == 1
    )


def test_review_refuses_busy_and_incompatible_metadata(workspace: Path) -> None:
    beads = PortfolioBeads()
    reconcile(FixtureGitHub([item()]), beads, "user:@me")
    with (workspace / ".github-sync.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(RuntimeError, match="busy"):
            record_triage("hub-1", "Reason", "Act", beads=beads)
    beads.rows["hub-1"]["metadata"]["triage"] = {"version": 99}
    with pytest.raises(ValueError, match="metadata.triage"):
        record_triage("hub-1", "Reason", "Act", beads=beads)


@pytest.mark.parametrize("limit", [0, -1, 1001, True])
def test_snapshot_rejects_invalid_limits(limit: int) -> None:
    with pytest.raises(ValueError, match="limit"):
        portfolio_snapshot(limit=limit)


def test_invalid_inventory_fails_visibly(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "repositories": {},
                "inventories": {
                    "user:@me": {
                        "discovered_at": 123,
                        "repositories": [{"node_id": "R_1"}],
                    }
                },
            }
        )
    )
    with pytest.raises(ValueError, match="inventory"):
        SyncState(path)
