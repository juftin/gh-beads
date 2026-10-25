"""Verify the unified CLI and its installed entrypoint outside the source checkout."""

from __future__ import annotations

import json
import os
import subprocess
import time
from importlib.metadata import distribution
from pathlib import Path

import pytest
from click.testing import CliRunner

from gh_beads import cli, runtime, snapshot, sync, triage


def test_single_console_entrypoint() -> None:
    """The installed distribution exposes only the unified CLI."""
    commands = {
        entry.name: entry.value
        for entry in distribution("gh-beads").entry_points
        if entry.group == "console_scripts"
    }
    assert commands == {"gh-beads": "gh_beads.cli:main"}


def test_sync_status_outside_checkout(tmp_path: Path) -> None:
    """Read polling progress through the installed command without GitHub or source-path setup."""
    result = subprocess.run(
        ["gh-beads", "sync", "--status"],
        cwd=tmp_path,
        env={**os.environ, "BEADS_WORKING_DIR": str(tmp_path), "GH_TOKEN": "", "PYTHONPATH": ""},
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert json.loads(result.stdout) == {"version": 1, "repositories": {}, "retry_at": 0}
    assert not list(tmp_path.iterdir())


def test_current_repository_is_default_workspace(tmp_path: Path) -> None:
    """Local CLI calls share the repository's checkpoints and lock without workspace settings."""
    (tmp_path / ".beads").mkdir()
    (tmp_path / ".beads/metadata.json").write_text("{}")
    state = {"version": 1, "repositories": {}, "retry_at": time.time() + 600}
    (tmp_path / ".github-sync-state.json").write_text(json.dumps(state))
    env = {key: value for key, value in os.environ.items() if key != "BEADS_WORKING_DIR"}
    env.update(GH_TOKEN="", PYTHONPATH="")
    status = subprocess.run(
        ["gh-beads", "sync", "--status"],
        cwd=tmp_path,
        env=env,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert json.loads(status.stdout) == state
    sync = subprocess.run(
        ["gh-beads", "sync"],
        cwd=tmp_path,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert sync.returncode == 1
    assert json.loads(sync.stdout)["retry_at"] == state["retry_at"]
    assert (tmp_path / ".github-sync.lock").exists()


@pytest.mark.parametrize(
    "command",
    [
        [],
        ["sync"],
        ["mcp"],
        ["runtime"],
        ["snapshot"],
        ["triage"],
        ["skill"],
        ["skill", "list"],
        ["skill", "show"],
        ["skill", "install"],
    ],
)
def test_command_help_outside_checkout(tmp_path: Path, command: list[str]) -> None:
    """Resolve console entrypoints without starting services or requiring a hub workspace."""
    result = subprocess.run(
        ["gh-beads", *command, "--help"],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": ""},
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert f"Usage: gh-beads {' '.join(command)}".rstrip() in result.stdout
    assert not list(tmp_path.iterdir())


def test_selected_repository_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    """Repeated repository flags and full repairs reach the sync runner together."""
    calls: list[dict[str, object]] = []

    def run(**kwargs: object) -> dict[str, str]:
        """Capture one requested pass without network or database access."""
        calls.append(kwargs)
        return {"status": "complete"}

    monkeypatch.setattr(sync, "run_sync", run)
    result = CliRunner().invoke(cli.main, ["sync", "--repo", "a/one", "--repo", "b/two", "--full"])
    assert result.exit_code == 0, result.output
    assert calls == [{"repositories": ["a/one", "b/two"], "force_full": True}]
    assert json.loads(result.stdout)["status"] == "complete"


@pytest.mark.parametrize("status,code", [("complete", 0), ("partial", 1), ("busy", 0)])
def test_sync_exit_status(monkeypatch: pytest.MonkeyPatch, status: str, code: int) -> None:
    """One-shot failures remain machine-readable and exit nonzero."""
    monkeypatch.setattr(sync, "run_sync", lambda **kwargs: {"status": status})
    result = CliRunner().invoke(cli.main, ["sync"])
    assert result.exit_code == code
    assert json.loads(result.stdout) == {"status": status}


def test_sync_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    """A periodic partial pass retries with the same selection and interval."""
    calls: list[dict[str, object]] = []
    intervals: list[int] = []

    def run(**kwargs: object) -> dict[str, str]:
        calls.append(kwargs)
        return {"status": "partial" if len(calls) == 1 else "complete"}

    def sleep(interval: int) -> None:
        intervals.append(interval)
        if len(intervals) == 2:
            raise KeyboardInterrupt

    monkeypatch.setattr(sync, "run_sync", run)
    monkeypatch.setattr("gh_beads.cli.time.sleep", sleep)
    result = CliRunner().invoke(
        cli.main, ["sync", "--loop", "--interval", "7", "--repo", "a/one", "--full"]
    )
    assert result.exit_code == 1
    assert calls == [{"repositories": ["a/one"], "force_full": True}] * 2
    assert intervals == [7, 7]
    assert [json.loads(line)["status"] for line in result.stdout.splitlines()] == [
        "partial",
        "complete",
    ]


@pytest.mark.parametrize(
    "args",
    [
        ["sync", "--loop", "--status"],
        ["sync", "--repo", "a/b", "--status"],
        ["sync", "--repo", "repo:a/b"],
        ["sync", "--interval", "0"],
        ["snapshot", "--limit", "0"],
        ["snapshot", "--limit", "1001"],
        ["snapshot", "--repo", "invalid"],
        ["triage", "hub-1", "--rationale", "Reason"],
        ["skill", "install", "--target", "invalid"],
    ],
)
def test_usage_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, args: list[str]) -> None:
    """Invalid input fails before workspace access, writes, or GitHub requests."""
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(cli.main, args)
    assert result.exit_code == 2, result.output
    assert "Error:" in result.stderr
    assert not list(tmp_path.iterdir())


def test_snapshot_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    """Snapshot selection and queue limits reach the read-only service."""
    calls: list[object] = []

    def read(repositories: list[str] | None, limit: int) -> dict[str, object]:
        calls.append((repositories, limit))
        return {"queues": {}}

    monkeypatch.setattr(snapshot, "portfolio_snapshot", read)
    result = CliRunner().invoke(
        cli.main, ["snapshot", "--repo", "a/b", "--repo", "a/c", "--limit", "50", "--json"]
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {"queues": {}}
    assert calls == [(["a/b", "a/c"], 50)]


def test_triage_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    """Triage preserves reviewer and stale-evidence guard arguments."""
    calls: list[object] = []

    def record(*args: object, **kwargs: object) -> dict[str, str]:
        calls.append((args, kwargs))
        return {"id": "hub-1"}

    monkeypatch.setattr(triage, "record_triage", record)
    result = CliRunner().invoke(
        cli.main,
        [
            "triage",
            "hub-1",
            "--rationale",
            "Reason",
            "--next-action",
            "Act",
            "--reviewer",
            "agent",
            "--expected-fingerprint",
            "abc",
        ],
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {"id": "hub-1"}
    assert calls == [
        (("hub-1", "Reason", "Act"), {"reviewer": "agent", "expected_fingerprint": "abc"})
    ]


@pytest.mark.parametrize("args", [[], ["--sql"], ["--configure-remote"]])
def test_runtime_cli(monkeypatch: pytest.MonkeyPatch, args: list[str]) -> None:
    """The runtime subcommand routes readiness and account provisioning separately."""
    calls: list[object] = []
    monkeypatch.setattr(runtime, "wait_for_hub", lambda **kwargs: calls.append(kwargs))
    monkeypatch.setattr(runtime, "configure_remote_access", lambda: calls.append("configure"))
    result = CliRunner().invoke(cli.main, ["runtime", *args])
    assert result.exit_code == 0, result.output
    assert calls == (["configure"] if "--configure-remote" in args else [{"sql_only": bool(args)}])


@pytest.mark.parametrize("command", ["snapshot", "triage", "runtime", "mcp"])
def test_command_errors(monkeypatch: pytest.MonkeyPatch, command: str) -> None:
    """Expected service failures are readable on stderr without corrupting JSON or MCP stdout."""
    from gh_beads import mcp

    def fail(*args: object, **kwargs: object) -> None:
        raise RuntimeError("workspace unavailable")

    monkeypatch.setattr(snapshot, "portfolio_snapshot", fail)
    monkeypatch.setattr(triage, "record_triage", fail)
    monkeypatch.setattr(runtime, "wait_for_hub", fail)
    monkeypatch.setattr(mcp, "serve", fail)
    args = [command]
    if command == "triage":
        args += ["hub-1", "--rationale", "Reason", "--next-action", "Act"]
    result = CliRunner().invoke(cli.main, args)
    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == "Error: workspace unavailable\n"


@pytest.mark.parametrize("names", [[], [""], ["repo:a/b"], ["a"], ["a/"], ["/b"], ["a/b;org:c"]])
def test_invalid_repository_selection(names: list[str]) -> None:
    """Empty selections and scope injection cannot fall back to the full portfolio."""
    with pytest.raises(ValueError, match="OWNER/REPO"):
        sync.repository_scopes(names)


def test_skill_cli_outside_checkout(tmp_path: Path) -> None:
    """The installed gh-beads skill CLI lists, displays, and installs skills outside checkout."""
    env = {**os.environ, "BEADS_WORKING_DIR": str(tmp_path), "PYTHONPATH": ""}

    # 1. List skills
    list_res = subprocess.run(
        ["gh-beads", "skill", "list", "--json"],
        cwd=tmp_path,
        env=env,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    skills = json.loads(list_res.stdout)
    assert any(s["name"] == "oss-steward" for s in skills)

    # 2. Show skill
    show_res = subprocess.run(
        ["gh-beads", "skill", "show", "oss-steward"],
        cwd=tmp_path,
        env=env,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert "Open-Source Maintainer Stewardship" in show_res.stdout

    # 3. Install skill to workspace
    install_res = subprocess.run(
        ["gh-beads", "skill", "install", "oss-steward", "--target", "workspace", "--json"],
        cwd=tmp_path,
        env=env,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    data = json.loads(install_res.stdout)
    assert data["status"] == "success"
    installed_skill = tmp_path / ".agents" / "skills" / "oss-steward" / "SKILL.md"
    assert installed_skill.is_file()
