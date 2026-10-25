"""The gh-beads command-line interface."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import click

from gh_beads import runtime, skill, snapshot, sync, triage
from gh_beads.state import SyncState


@click.group()
@click.version_option(package_name="gh-beads")
def main() -> None:
    """Maintain a shared Beads backlog for GitHub issues and pull requests."""


def _repositories(names: tuple[str, ...]) -> list[str] | None:
    """Validate explicit selection before accessing a workspace or GitHub."""
    repositories = list(names) if names else None
    try:
        sync.repository_scopes(repositories)
    except ValueError as exc:
        raise click.BadParameter(str(exc), param_hint="--repo") from exc
    return repositories


@main.command("sync")
@click.option("--loop", is_flag=True, help="Reconcile periodically.")
@click.option("--status", is_flag=True, help="Show durable polling progress.")
@click.option("--full", is_flag=True, help="Force a full open-backlog repair.")
@click.option(
    "--repo",
    multiple=True,
    metavar="OWNER/REPO",
    help="Sync only this repository (repeatable); replaces GH_SYNC_QUERY for this run.",
)
@click.option(
    "--interval",
    type=click.IntRange(min=1),
    default=120,
    show_default=True,
    help="Seconds between sync passes.",
)
def sync_command(
    loop: bool, status: bool, full: bool, repo: tuple[str, ...], interval: int
) -> None:
    """Reconcile GitHub issues and PRs, or inspect polling progress."""
    repositories = _repositories(repo)
    if status and loop:
        raise click.UsageError("--loop cannot be combined with --status")
    if status and repositories:
        raise click.UsageError("--repo cannot be combined with --status")
    if status:
        workspace = Path(os.environ.get("BEADS_WORKING_DIR", "."))
        try:
            state = SyncState(workspace / ".github-sync-state.json")
        except (OSError, ValueError) as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(json.dumps(state.data))
        return
    while True:
        summary = sync.run_sync(force_full=full, repositories=repositories)
        click.echo(json.dumps(summary))
        if not loop:
            if summary["status"] == "partial":
                raise click.exceptions.Exit(1)
            return
        time.sleep(interval)


@main.command("mcp")
def mcp_command() -> None:
    """Serve the official Beads MCP tools over stdio, HTTP, or SSE.

    Configure MCP_TRANSPORT (default: stdio), MCP_HOST, and MCP_PORT in the environment.
    """
    # Import only when serving: help and other commands must not initialize MCP.
    from gh_beads.mcp import serve

    try:
        serve()
    except (OSError, RuntimeError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc


@main.command("runtime")
@click.option("--sql", is_flag=True, help="Wait only for the SQL listener.")
@click.option("--configure-remote", is_flag=True, help="Provision remote SQL access.")
def runtime_command(sql: bool, configure_remote: bool) -> None:
    """Wait for SQL/hub readiness or provision the remote SQL account."""
    try:
        if configure_remote:
            runtime.configure_remote_access()
        else:
            runtime.wait_for_hub(sql_only=sql)
    except (OSError, RuntimeError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc


@main.command("snapshot")
@click.option(
    "--repo", multiple=True, metavar="OWNER/REPO", help="Select a repository (repeatable)."
)
@click.option(
    "--limit",
    type=click.IntRange(1, 1000),
    default=20,
    show_default=True,
    help="Maximum items per queue.",
)
@click.option("--json", "json_output", is_flag=True, help="JSON output (the default).")
def snapshot_command(repo: tuple[str, ...], limit: int, json_output: bool) -> None:
    """Read stored portfolio coverage, queues, and saved review changes as JSON."""
    repositories = _repositories(repo)
    try:
        result = snapshot.portfolio_snapshot(repositories, limit)
    except (RuntimeError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(json.dumps(result))


@main.command("triage")
@click.argument("bead_id")
@click.option("--rationale", required=True, help="Reason for the decision.")
@click.option("--next-action", required=True, help="Concrete next step.")
@click.option("--reviewer", help="Reviewer identity (defaults to BEADS_ACTOR).")
@click.option("--expected-fingerprint", help="Refuse a review if stored source facts changed.")
def triage_command(
    bead_id: str,
    rationale: str,
    next_action: str,
    reviewer: str | None,
    expected_fingerprint: str | None,
) -> None:
    """Record a local review with rationale and a next action."""
    try:
        result = triage.record_triage(
            bead_id,
            rationale,
            next_action,
            reviewer=reviewer,
            expected_fingerprint=expected_fingerprint,
        )
    except (RuntimeError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(json.dumps(result))


@main.group("skill", invoke_without_command=True)
@click.pass_context
def skill_group(ctx: click.Context) -> None:
    """Inspect and install agent skills across agent ecosystems."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(skill_list)


@skill_group.command("list")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON.")
def skill_list(json_output: bool) -> None:
    """List available skills."""
    skills = skill.list_skills()
    if json_output:
        click.echo(json.dumps(skills, indent=2))
    else:
        click.echo("Available skills:")
        for item in skills:
            click.echo(f"  • {item['name']}: {item['description']}")
            if item["references"]:
                click.echo(f"    References: {', '.join(item['references'])}")


@skill_group.command("show")
@click.argument("name", default=skill.DEFAULT_SKILL)
@click.option("--consolidated", is_flag=True, help="Inline all reference files into one document.")
def skill_show(name: str, consolidated: bool) -> None:
    """Show skill instructions."""
    try:
        content = skill.consolidate_skill(name) if consolidated else skill.get_skill_content(name)
    except FileNotFoundError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(content)


@skill_group.command("install")
@click.argument("name", default=skill.DEFAULT_SKILL)
@click.option(
    "--target",
    type=click.Choice(skill.SUPPORTED_TARGETS),
    default="workspace",
    show_default=True,
    help="Agent target platform.",
)
@click.option(
    "--dir",
    "directory",
    type=click.Path(path_type=Path, file_okay=False),
    help="Base directory for project installation (default: working directory).",
)
@click.option(
    "--dest",
    type=click.Path(path_type=Path, file_okay=False),
    help="Explicit destination directory (sets target=custom).",
)
@click.option("--overwrite", is_flag=True, help="Overwrite existing skill files.")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON.")
def skill_install(
    name: str,
    target: str,
    directory: Path | None,
    dest: Path | None,
    overwrite: bool,
    json_output: bool,
) -> None:
    """Install a skill into agent directories."""
    target = "custom" if dest else target
    try:
        result = skill.install_skill(
            skill_name=name,
            target=target,
            base_dir=directory,
            custom_dest=dest,
            overwrite=overwrite,
        )
    except (ValueError, FileNotFoundError) as exc:
        raise click.ClickException(str(exc)) from exc
    if json_output:
        click.echo(json.dumps(result, indent=2))
    else:
        click.echo(f"Successfully installed skill '{name}' (target: {target}):")
        for action in result["actions"]:
            click.echo(f"  ✓ {action}")
