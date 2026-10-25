"""Serve the official beads-mcp tools and resources over stdio, HTTP, or SSE."""

from __future__ import annotations

import os
from typing import Any

from beads_mcp.server import mcp as mcp

from gh_beads.runtime import wait_for_hub
from gh_beads.skill import (
    get_reference_content,
    get_skill_content,
    install_skill,
)
from gh_beads.snapshot import portfolio_snapshot
from gh_beads.sync import run_sync
from gh_beads.triage import record_triage


@mcp.tool(
    name="install_stewardship_skill",
    description=(
        "Install the oss-steward maintainer skill into an agent environment "
        "(workspace, global, claude, cursor, copilot, or all)."
    ),
)
def install_stewardship_skill_tool(
    target: str = "workspace",
    directory: str | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Install the oss-steward skill files into the designated agent discovery path."""
    from pathlib import Path

    return install_skill(
        skill_name="oss-steward",
        target=target,
        base_dir=Path(directory) if directory else None,
        overwrite=overwrite,
    )


@mcp.resource("skills://oss-steward/SKILL.md")
def get_stewardship_skill_resource() -> str:
    """The main open-source stewardship skill instructions."""
    return get_skill_content("oss-steward")


@mcp.resource("skills://oss-steward/references/{name}")
def get_stewardship_reference_resource(name: str) -> str:
    """A reference guide for the open-source stewardship skill."""
    return get_reference_content("oss-steward", name)


@mcp.prompt(name="oss_steward")
def oss_steward_prompt() -> str:
    """Procedures for open-source repository triage, investigation, and maintenance."""
    return get_skill_content("oss-steward")


@mcp.tool(name="portfolio_snapshot")
def portfolio_snapshot_tool(
    repositories: list[str] | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """Read stored repository coverage, readiness, attention signals, and saved triage decisions."""
    return portfolio_snapshot(repositories, limit)


@mcp.tool(name="record_triage")
def record_triage_tool(
    bead_id: str,
    rationale: str,
    next_action: str,
    reviewer: str | None = None,
    expected_fingerprint: str | None = None,
) -> dict[str, Any]:
    """Remember a local review; supply reviewer or configure BEADS_ACTOR. No GitHub writes."""
    return record_triage(
        bead_id,
        rationale,
        next_action,
        reviewer=reviewer,
        expected_fingerprint=expected_fingerprint,
    )


@mcp.tool(
    name="trigger_github_sync",
    description="Reconcile GitHub issues and pull requests; returns complete, partial, or busy.",
)
def trigger_github_sync(repositories: list[str] | None = None) -> dict[str, Any]:
    """Sync selected OWNER/REPO names, or configured scopes when repositories is omitted."""
    return run_sync(repositories=repositories)


def serve() -> None:
    """Wait for initialization and serve the official MCP instance on the configured transport."""
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    if transport not in {"stdio", "streamable-http", "sse"}:
        raise ValueError("MCP_TRANSPORT must be stdio, streamable-http, or sse")
    wait_for_hub()
    if transport == "stdio":
        mcp.run(transport="stdio")
        return
    mcp.run(
        transport="sse" if transport == "sse" else "streamable-http",
        host=os.environ.get("MCP_HOST", "0.0.0.0"),
        port=int(os.environ.get("MCP_PORT", "8080")),
    )
