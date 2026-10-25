# Stewardship implementation handoff

This captures the context of the 2026-10-23 maintainer-workflow assessment for an agent that has not read the conversation. The [roadmap](roadmap.md#open-source-stewardship) owns the proposed phases and completion criteria; [architecture](architecture.md) owns current contracts; [decisions](decisions.md) records established constraints; the [checklist](checklist.md) owns validation evidence. Recheck the checkout before implementing: this is a dated handoff, not a live capability report.

## User intent and authorized work so far

The user maintains multiple open-source GitHub repositories and wants to be a good steward of:

- Renovate/Dependabot upgrades: review release notes and breaking changes, merge acceptable updates, and flag concerns.
- External code contributions: review implemented fixes/features, help contributors move forward, and merge or explain what remains.
- Bug reports, including reports accompanied by PRs: gather missing information, coordinate the fix, and keep reporters informed.
- Feature requests: clarify the need, make and communicate a decision, and track commitments.

The desired workflow includes triage, ownership, proactive information requests and updates, PR decisions, and follow-through across sessions. A useful outcome advances an item and remembers who owes the next action and when to revisit it.

This conversation authorized assessment and documentation updates. It has not implemented roadmap capabilities, submitted GitHub comments/reviews, merged PRs, or authorized commits/pushes. A later user's task determines implementation and external-action scope; this handoff is context, not standing permission to operate on repositories.

## What exists at the handoff

The assessment found a useful portfolio triage foundation, with gaps in detailed investigation, upstream actions, and scheduled follow-up. Existing CLI commands are `gh-beads-sync`, `gh-beads-mcp`, `gh-beads-runtime`, `gh-beads-snapshot`, and `gh-beads-triage`. The wrapper adds `trigger_github_sync`, `portfolio_snapshot`, and `record_triage` to the official Beads MCP server.

There is no packaged stewardship skill, live-investigation command, native GitHub action layer, structured timed follow-up queue, or scheduled reasoning agent. Names such as `gh-beads-doctor`, `gh-beads-inspect`, and `gh-beads-action plan/apply` in the roadmap are proposals; do not write instructions that present them as available.

Important operational details for implementation and skill authors:

- Imports are Beads `task` children of repository epics, distinguished with `type:issue` and `type:pr` labels. A Beads claim is separate from GitHub assignment.
- PR `open`/`in_progress` is deterministic triage state. Pending checks and drafts can appear in progress; approved, passing PRs also wait there. Inspect active work as well as `bd ready`.
- Existing source facts include author association, fork identity, head/base SHAs, PR body, aggregate CI/review state, requested reviewers, and closing references. Reuse these before adding requests. Bot authorship and diff size are factual filters, not risk or priority decisions.
- Conversation bodies, patches, individual check results, and full review histories are absent. A stored review fingerprint cannot detect changes to evidence that has not been fetched/imported. Changed-since-review includes terminal imported changes, but does not imply complete conversation monitoring.
- Reviewer detail is bounded to 100 with explicit coverage; closing references are fully paginated. Snapshot limits are 1–1,000 per queue with no cursor. Full CLI inventory uses Beads `--limit 0`, not snapshot `--limit 0`.
- Repository `last_success_at` establishes stored coverage freshness. An unchanged item retains `observed_at`; it is not a poll heartbeat. Snapshot `coverage.status=complete` is not a live freshness guarantee.
- Bootstrap imports open work, not all historical closed work. Scope selection preserves excluded imports; absence and access failures never establish closure.

## Design direction and boundaries

Use the phase order in the roadmap. Deliver onboarding and a portable skill around existing tools first, followed by selected live investigation, structured follow-up/navigation, actions/scheduling, and end-to-end validation. These are recommendations to implement in scoped increments, not a request to build every phase in one change.

Preserve the separation between source synchronization, local decisions, investigation, and action execution:

- Keep the poller focused on source facts. An agent runner supplies recurring judgment and outreach; installing a skill or connecting MCP alone does not start scheduled maintenance.
- Fetch detailed evidence for selected items on demand rather than mirroring every conversation, patch, or log across the portfolio. Return provenance, observation time, and coverage with the evidence.
- Keep CLI/MCP domain operations backed by shared application logic and retain official Beads tools. Use native `bd` for ordinary local planning changes.
- Use a companion GitHub connector or CLI for upstream work initially. This does not require replacing the hub's GitHubKit adapter or adding GitHub CLI to its runtime image. Native action support remains a decision to justify, not a prerequisite for shipping the skill.
- Preserve local priority, claims, reasoning, categories, and triage history through sync. Do not restore wholesale GitHub-label copies. Read upstream classification on demand if needed, keeping it distinct from local classification.
- Preserve authoritative closure and dependency direction: `bd dep add ISSUE_ID PR_ID` means the issue depends on its proposed fix. Related mentions and duplicates need explicit semantics and provenance before becoming blockers.
- Existing upstream closure wins over local workflow state. A PR closed without merging does not prove that its issue was fixed or closed.
- Keep live merge checks distinct from local triage fingerprints. Revalidate the reviewed head and current merge rules; record confirmed action results and reconcile ambiguous attempts before retrying.

Expanded metadata/custom workflow changes were previously reverted because pinned beads-ui could not fully display/manage them. Read the [UI compatibility decision](decisions.md#gate-workflow-extensions-on-ui-support) before selecting persistence or status changes. Supported labels/descriptions may provide a first increment; browser validation and upstream support remain necessary before restoring the deferred extensions.

## Choices still open

The conversation established product direction, not final schemas, integrations, or automation policies. Resolve choices only as needed for the implementation slice, recording the rationale in the appropriate design documentation.

| Choice | What remains to decide |
| --- | --- |
| Investigation contract | Evidence selection, pagination/cursors, size limits, provenance, freshness, and handling missing access; what is transient versus persisted. |
| Local workflow schema | How category/decision/response ownership/follow-up dates and receipts relate to append-only triage history; versioning, preservation, and UI presentation. Proposed field names are illustrative. |
| Stewardship policy | Repository-specific response cadence, ownership, acceptance/risk criteria, and authorized actions. No universal follow-up deadline or dependency auto-merge rule was selected. |
| GitHub actions | Which companion tools are available to the user and whether native operations add enough reliability to justify their cost. Define result/receipt and retry semantics for the chosen path. |
| Scheduler | Runner, deployment, cadence, overlap coordination, and failure visibility. No scheduler product or automatic-maintenance permission was selected. |
| Skill distribution | Supported clients, discovery/install instructions, required versus optional tool capabilities, and usable behavior when a GitHub connector is absent. The proposed skill path/name is not a published package. |

## Code and documentation entry points

| Area | Existing implementation / evidence |
| --- | --- |
| Source adapter and selected fields | [github.py](../src/gh_beads/github.py), [source tests](../tests/test_github_source.py) |
| Reconciliation, ownership, readiness, dependencies | [sync.py](../src/gh_beads/sync.py), [sync tests](../tests/test_sync.py), [polling tests](../tests/test_polling.py) |
| Coverage, queues, remembered decisions | [snapshot.py](../src/gh_beads/snapshot.py), [triage.py](../src/gh_beads/triage.py), [portfolio tests](../tests/test_portfolio.py) |
| MCP and installed CLI behavior | [mcp.py](../src/gh_beads/mcp.py), [MCP tests](../tests/test_mcp.py), [CLI tests](../tests/test_cli.py), [pyproject.toml](../pyproject.toml) |
| Rendered evidence and UI compatibility | [description.py](../src/gh_beads/description.py), [description tests](../tests/test_description.py), [compatibility watch](roadmap.md#beads-ui-compatibility-watch) |
| First-use workflow and agent guidance | [README](../README.md#quick-start), [local setup](local.md), [usage](usage.md), [AGENTS.md](../AGENTS.md) |

For a first implementation task, use [phase 1](roadmap.md#phase-1-first-success-and-a-stewardship-skill) as the suggested slice: improve the first-repository walkthrough and package the skill using only existing commands, with an explicit companion-tool path for GitHub actions. Document unavailable capabilities honestly. Select later phases when the user's next task calls for them.

## Behavioral cases to retain

These are examples for implementation review and skill evaluation, not a fixed test suite or permission to act on live repositories:

- A grouped bot upgrade contains a concerning release note or an unknown version transition: inspect each affected dependency, explain the concern with sources, and record a concrete next step; bot identity and passing CI do not settle the decision.
- A bug lacks a reproduction, then the reporter replies: ask for the specific missing details when authorized, remember response ownership and a revisit date, and surface the reply without asking the same question again.
- An external contribution is approved, then receives a new commit: review the changed evidence before merging; do not reuse a stale action plan merely because the local review is unchanged.
- A PR references an issue, then closes without merging: preserve the issue's independently verified state and reassess the next action.
- A feature request is deferred: record and, when authorized, communicate why and any revisit trigger. Age alone does not justify closure.
- A comment request times out after GitHub may have accepted it: reconcile the upstream outcome before retrying, and keep the action status uncertain until confirmed.
- Coverage is stale or a queue is truncated: disclose the gap, refresh or traverse within scope, and avoid claiming complete portfolio maintenance.

## Validation baseline and handoff limits

During the assessment, `uv run --locked pytest -q` passed all 151 offline tests. Native `bd` was unavailable and the snapshot command reported no initialized hub workspace. No live portfolio coverage or credentialed GitHub workflow was established; do not initialize a replacement database just because the code checkout lacks one. Current setup/environment availability should be checked again by the next agent.

The roadmap/checklist edits were documentation only. Local Markdown links/anchors, balanced code fences, and `git diff --check` passed after the roadmap update. Historical runtime/smoke evidence and outstanding credentialed, Docker, browser, and restore checks remain in the checklist; none became verified by this conversation.

For implementation, follow [AGENTS.md](../AGENTS.md#if-changing-this-project) and the locked [Task workflows](../Taskfile.yaml). Match validation to the change: meaningful behavior tests for domain operations, smoke checks for runtime/transport changes, packaging checks for distribution changes, and browser checks for UI-dependent workflow claims. Record new evidence without overwriting historical limitations.
