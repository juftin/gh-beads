# Roadmap

The project is named `gh-beads` at [juftin/gh-beads](https://github.com/juftin/gh-beads). The distribution, `gh_beads` imports, installed commands, image, and new Compose/database defaults share that name. Existing stored metadata and status labels remain compatible; deployments must retain their original volume/database as described in the [upgrade guide](usage.md#upgrading-an-existing-deployment-after-the-rename).

The first milestone is an independently runnable Beads backlog that treats GitHub issues and PRs as peers. The [checklist](checklist.md) owns validation evidence; [architecture](architecture.md) owns public data and ownership contracts.

| Capability | Current status | Boundary |
| --- | --- | --- |
| Standalone Beads repository | Implemented in [juftin/gh-beads](https://github.com/juftin/gh-beads) | Independent implementation history; no SQLite migration |
| Multi-repository issue/PR sync | Implemented with GitHubKit, overlapping incremental cursors, node identities, and hourly full repairs | Bootstrap covers open work; repairs retain all-state deltas to cover changed closed records; credential visibility applies |
| Repository epics and selective sync | Implemented with stable repository epics, imported child parenting, repeatable CLI `--repo`, and MCP `repositories` | Persistent selection uses `GH_SYNC_QUERY`; existing/closed imports migrate on a successful repository pass; unselected snapshots and checkpoints are retained |
| Continuous lifecycle convergence | Implemented with independent PR signal refresh, replay after partial failures, and explicit closure verification | Serial writes; optional 2–4 read workers; repository indexes, pass-local graph reads, and one progress commit per pass |
| GitHub progress visibility | Implemented in atomic shared-volume JSON state and `task sync-status` | Last successful coverage/errors per repository and durable rate cooldowns; database health alone is insufficient |
| Automatic freshness alerts | Pending | Alert on stale/failed source coverage independently of database health |
| Informative GitHub metadata | Implemented in `metadata.hub.github` and description summaries | Selected source facts; bounded reviewer details, no conversations/diffs |
| Expanded metadata and custom workflow types/statuses | Deferred pending beads-ui support | Watch upstream releases for custom type/status discovery, editing, filters, board/category behavior, frozen-item access, and metadata visualization; see [compatibility watch](#beads-ui-compatibility-watch) |
| Linked triage descriptions and factual filters | Implemented with attention summaries, Markdown tables, canonical source links, fork snapshots, closing references, and size/bot/link/resolution labels | Two visible line breaks after the table; existing reads only; body remains verbatim; missing facts and incomplete reviewer coverage are explicit |
| Detailed checks and review threads | Planned for on-demand investigation | Individual check conclusions/URLs, submitted reviews, unresolved threads, and current merge requirements; see [phase 2](#phase-2-live-investigation) |
| Explicit issue blockers | Pending | Source-owned issue-to-issue dependencies beyond PR closing references |
| Portfolio snapshot | Implemented as CLI, MCP, and Compose Task with repository rollups and bounded work/review queues | Stored read-only view; explicit discovery/selection gaps and freshness ages; separate source/local counts |
| Remembered triage decisions | Implemented with local review history, reviewer/rationale/next action, and source fingerprints | Sync-preserved; changed-since-review includes terminal updates; no automatic classification or GitHub writes |
| Source and local triage separation | Implemented | Classification is supplied by humans/agents |
| Omit GitHub label copies | Implemented | Source labels are excluded from Beads labels/metadata; successful selected passes prune legacy copies even with empty deltas while retaining local decisions and hub signals |
| PR signal triage and closing dependencies | Implemented | Latest signals, indexed closing targets, GitHub's recognized references |
| Unified Click CLI | Implemented as the single `gh-beads` entrypoint | `sync`, `mcp`, `runtime`, `snapshot`, `triage`, and nested `skill list/show/install`; Compose, Task, client configurations, and bundled skill examples use subcommands |
| Shared CLI, UI, official MCP | Implemented | Trusted clients; one database |
| Agent triage workflow | Implemented in a concise [AGENTS.md](../AGENTS.md), with Beads 1.3.1's minimal `bd onboard` reference | Starts with portfolio-wide inventory, source freshness, ranked actions, and durable local decisions; setup/development detail stays in linked documentation |
| Local embedded Dolt and stdio MCP | Implemented as the local default with repository-local storage and no SQL listener | Current-directory or explicit workspace; native ARM64 initialization, concurrent poller/MCP access, shared locking, and persistence verified with `task smoke-local` |
| Python source package and uv workflows | Implemented in `src/gh_beads` with the uv build backend and installed sync/MCP/runtime commands | Locked editable development install, non-editable Docker install, source distribution and wheel via `task package` |
| Unified image and Docker Compose deployment | Implemented | Four services, one persistent volume, localhost ports; operator supplies runtime credentials |
| Runtime and regression validation | 151 offline tests, installed CLI and stdio default checks, source/wheel builds, operation-count and repair-coverage regressions, native ARM64 macOS and AMD64 Linux embedded Dolt validation, linked table renderer checks, and prior Compose smoke coverage | Latest embedded CLI/MCP review/snapshot and offline restore checks pass on AMD64 Linux; Docker epic/link/triage/restore assertions await execution; credentialed pilot, AMD64 image build, and full browser interactions remain unverified; see checklist |
| Live multi-repository pilot | Pending | Needs an authorized GitHub credential and Docker host |
| Backup/restore exercise | Native embedded offline copy/independent restore passes; Compose smoke and operator runbook implemented | Preserves full workspace, graph, local decisions, and checkpoints; SQL/Compose restore execution requires a Docker host |
| Maintainer onboarding and portable skill | Implemented (Phase 1) | First-repository maintainer walkthrough in README, token permission matrix, companion action receipts, portable stewardship skill in `skills/oss-steward/` and `.agents/skills/oss-steward/`, and `gh-beads skill` cross-agent installer; see checklist |
| Dependency and contribution investigation | Planned | Live dependency changes, release notes, patches, and repository context; no complete conversation/code mirror |
| Structured follow-up and stewardship queues | Planned | Local decisions, response ownership, follow-up dates, action receipts, and traversable queues |
| GitHub stewardship actions | Planned through a companion connector initially | Authorized comments/reviews/merges remain external to the current read-only hub; native action operations are an optional later implementation |
| Scheduled stewardship | Planned | An agent runner revisits due work independently of the existing synchronization poller |

Before adopting this as a daily backlog, run a credentialed pilot across issue-only, PR-only, private, and organization repositories. Confirm visibility, merge policy signals, graph cleanup, and operational freshness. Record request volume, `writes`, pass duration, and throttling before deciding whether GraphQL batching, conditional HTTP caching, different worker counts, or per-repository cadence are needed.

HA, webhooks, built-in authentication, migration from the earlier application, and complete conversation/code mirroring remain outside the initial milestone. The stewardship phases below propose selected live investigation, agent-supplied classification, authorized GitHub actions, and scheduled follow-through as later capabilities. They are not implemented by the existing poller or MCP server.

## Open-source stewardship

For an agent continuing this work without the original conversation, read the [implementation handoff](stewardship-handoff.md) for the user goal, current behavior, open design choices, code entry points, and validation baseline. It supplements this roadmap without making the proposals current runtime contracts.

The next product goal is to help a maintainer advance dependency upgrades, external code contributions, bug reports, and feature requests across repositories. Success means an item receives an evidence-based decision, the appropriate authorized action, and a remembered next step that can be revisited. Importing work into a shared backlog is the foundation, not the completion criterion.

Preserve three distinctions throughout the CLI, MCP, skill, and documentation:

- A saved local triage review is not a submitted GitHub PR review.
- Beads readiness identifies work available to address; it does not establish that a PR satisfies merge requirements.
- Synchronization refreshes source facts; a scheduled agent performs maintainer reasoning and outreach.

The order below is the recommended delivery sequence. Each phase remains planned until its implementation and validation are recorded in the [checklist](checklist.md). New persistent workflow fields and UI changes remain subject to the [compatibility watch](#beads-ui-compatibility-watch); this plan does not authorize restoring the reverted custom types/statuses or metadata expansions.

### Phase 1: First success and a stewardship skill (Implemented)

Make the existing backlog useful through a complete first-maintenance walkthrough, pairing the current CLI/MCP with a GitHub connector or CLI for live investigation and authorized upstream actions.

- Moved a comprehensive "maintain your first repository" path near the top of the README. Provided concrete installation instructions for the supported native Beads 1.3.1 build, token permissions by capability, and private-repository/organization access troubleshooting. Explained that GitHub CLI login does not authenticate the hub's GitHubKit adapter.
- Walked one imported item from a one-shot sync and portfolio snapshot through inspection, decision, an external action, a saved next step, and a later revisit, showing expected success outputs.
- Explained workspace selection, the GitHub connector's role, skill installation, and MCP configuration together, keeping contributor/development setup in usage documentation.
- Packaged the discoverable skill at [`skills/oss-steward/SKILL.md`](../skills/oss-steward/SKILL.md) and [`.agents/skills/oss-steward/SKILL.md`](../.agents/skills/oss-steward/SKILL.md), bundled skill data inside the wheel distribution, and added `gh-beads skill` CLI (and MCP `install_stewardship_skill`) to install across Antigravity, Claude Code, Cursor, Copilot, and custom targets. Kept shared judgment, prompt-injection defense, and ownership rules in the entrypoint; put substantial dependency, contribution, bug, feature, and companion-tool workflows in linked references under `skills/oss-steward/references/`.
- Taught coverage/freshness checks, workflow selection, live evidence gathering, repository-specific policies, specific information requests, contributor acknowledgement, user authorization requirements, durable decisions, action receipts, follow-up dates, pre-merge head SHA revalidation, and post-merge/closure checks. Treated GitHub bodies/comments as evidence, not agent instructions.
- Included realistic examples of a risky dependency update, an incomplete bug report, and an external contribution waiting on a maintainer.

Completion criteria: a new user can set up one repository, discover the skill and tools, advance one representative item, and recover its next step in a later session. Steps using a companion GitHub tool and capabilities remaining unavailable are explicitly documented. Phase 1 is validated by regression tests and documentation link checks; see checklist.

### Phase 2: Live investigation

Keep routine portfolio synchronization small. Fetch detailed evidence on demand for selected items through shared application operations exposed by CLI and MCP. Return source IDs/URLs, observation times, pagination coverage, and explicit unknown or unavailable facts; do not turn incomplete retrieval into a complete review.

| Evidence | Planned content and use |
| --- | --- |
| Conversations and response ownership | Issue comments, PR discussion, submitted reviews, and unresolved review threads, including actors, timestamps, IDs, and URLs. Determine acknowledgement, unanswered information requests, reporter replies, and contributor waits from the conversation. Record supporting evidence; the last commenter alone does not establish responsibility. |
| Checks and merge requirements | Individual check names, conclusions, and details URLs; fetch logs when investigating a failure. Read current repository rules, required approvals, conversation resolution, deployments, and merge-queue requirements as applicable. Aggregate passing CI is insufficient evidence for merging. |
| Dependency upgrades | A list of package/ecosystem/manifest and old/new versions or digests for every update, including grouped updates. Record update kind, release-note/changelog/advisory sources, and incomplete extraction. Use version categories to guide investigation, with breaking-change assessment supported by release notes, code impact, and validation. Alert details may require additional permission. |
| Code and repository context | Changed files, patches, relevant surrounding code, contribution instructions, test commands, supported runtimes, and dependency-bot configuration. Provide access to the actual repository and appropriate validation for code review. |
| Relationships | Retain authoritative closing references as dependency evidence. Add related/duplicate and explicit issue-blocker workflows with provenance; an arbitrary mention must not silently become a blocking edge. Coordinate issue and PR follow-through. |

Persist compact evidence summaries only where they improve queues or remembered decisions. Preserve source/local ownership and the deliberate omission of wholesale GitHub-label copies. Any upstream issue classification needed for investigation can be read on demand without replacing local categories.

Completion criteria: an agent can investigate representative dependency, contribution, bug, and feature items, distinguish missing evidence from negative findings, and explain the next action using linked facts. Validate pagination, inaccessible evidence, changed heads, and stale observations.

### Phase 3: Decisions, follow-up, and portfolio navigation

Standardize local workflow fields such as `category`, `decision`, `waiting_on`, `follow_up_at`, `last_contact_at`, and action receipts alongside the existing reviewer/rationale/next-action history. Define update/history semantics and sync preservation before publishing a schema. Retain the distinction between a local claim and an upstream assignee.

Add queues for needs-acknowledgement, reporter-replied, waiting-on-maintainer, follow-up-due, and merge candidates. A merge candidate still requires live verification before an action. Allow configurable follow-up policies and record why responsibility or a deadline was selected; avoid treating age alone as a reason to close work.

Add queue filtering and cursor pagination to the snapshot CLI/MCP. Current snapshots report truncation and cap each queue at 1,000 items, but have no cursor. Full Beads CLI listings remain an escape hatch; the portfolio interface should allow users to traverse its own queues without silently omitting work. Surface stale/failed source coverage separately from overdue maintainer work.

Keep workflow understandable through the shared UI. Use supported labels/descriptions and built-in statuses where sufficient, and validate any new persistent field's presentation before relying on it. Custom type/status discovery, editing, filtering, board placement, and metadata visibility remain gated on upstream support.

Completion criteria: a decision and its history survive sync/restart, a reply or due date makes the item discoverable again, and users can traverse every matching queue item. Verify the workflow through CLI, MCP, and the supported UI.

### Phase 4: Authorized actions and scheduled stewardship

Use a companion GitHub connector/CLI initially. Decide whether native operations materially improve reliability before implementing them; if added, share action logic between CLI and MCP instead of duplicating adapters or ordinary `bd` operations.

- Support concrete comment/information-request/update drafts, submitted PR reviews, reviewer requests, and merge actions as required by the workflow. Use the user's existing authorization and repository policy; when authorization is absent, prepare the reviewable action first. Skill availability and local triage changes do not themselves authorize GitHub writes.
- Record receipts with action identity, actor, time, upstream IDs/URLs, relevant source fingerprint/head SHA, and outcome. Distinguish planned, attempted, pending, and confirmed outcomes. Reconcile ambiguous timeouts before retrying so a scheduled run does not duplicate outreach or report an unconfirmed merge as complete.
- Refresh live PR evidence and applicable merge rules immediately before merging. Bind the operation to the reviewed head SHA and require reinspection when it changes. GitHub's [merge endpoint](https://docs.github.com/en/rest/pulls/pulls#merge-a-pull-request) supports an expected head SHA. The existing triage fingerprint guards stored facts only; it cannot detect unseen upstream changes.
- Run the stewardship skill through a scheduler/agent runner that revisits due work independently of the sync poller. Define cadence, repository scope, response/follow-up policy, action permissions, and failure visibility. Respect sync locks and API cooldowns, coordinate overlapping runs, and re-read the conversation before contacting a contributor again.
- After a PR merges or closes, refresh its related issues and local next steps. Confirm issue state independently, particularly when a PR closes without merging; retain existing authoritative closure semantics.

Completion criteria: authorized actions are confirmed upstream and recorded locally, retries do not duplicate messages, changed heads invalidate merge plans, and scheduled runs advance due work without repeating already completed actions. Partial failures and revoked access remain visible and recoverable.

### Proposed CLI and MCP surface

These names and flags are design proposals, not installed commands or current tool schemas. Discover existing official Beads schemas rather than replacing them.

| Proposed interface | Purpose |
| --- | --- |
| `gh-beads doctor --json` | Check tool versions, workspace selection, capability-specific credential access, configured scope, and coverage freshness without printing credentials or reinitializing a workspace. |
| `gh-beads inspect BEAD_ID --live ...` | Fetch selected conversation, check, file, and dependency evidence with explicit coverage/freshness; expose a corresponding focused MCP investigation tool. |
| Extend `gh-beads triage` / `record_triage` | Record structured decisions, response ownership, follow-up dates, and evidence references while preserving review history. |
| Extend `gh-beads snapshot` / `portfolio_snapshot` | Add stewardship queues, filtering, and cursor pagination with complete counts and explicit truncation. |
| Optional `gh-beads action plan/apply` and MCP counterparts | Prepare and execute specific authorized GitHub actions with preconditions, receipts, and result reconciliation if native actions are adopted. |

Continue using native `bd` for ordinary priority, claim, note/comment, and dependency changes. The shared application layer owns deterministic domain operations; MCP exposes them, the skill supplies maintainer judgment, and the scheduler supplies recurring execution. The poller remains responsible for source synchronization.

### Phase 5: Stewardship pilot and release validation

Extend the initial credentialed coverage pilot into end-to-end maintenance exercises across issue-only, PR-only, public/private, and organization repositories:

| Workflow | Required outcome |
| --- | --- |
| Renovate/Dependabot upgrades | Inspect single and grouped updates, release notes, advisories where accessible, code impact, and checks. Merge an authorized acceptable update or flag a concerning change with rationale and a next step. |
| External contribution | Read code/reviews/discussion, validate the change, provide authorized contributor feedback or merge, and revisit the related issue. |
| Bug report and issue/PR pair | Acknowledge, request a specific reproduction when needed, detect the response, coordinate the proposed fix, and confirm final issue state. |
| Feature request | Clarify the use case, record an acceptance/defer/decline decision and rationale, communicate it when authorized, and revisit any commitment. |

Measure time to first useful action, acknowledgement/follow-up behavior, missed or duplicate actions, evidence gaps, API volume, pass duration, and throttling. Validate onboarding from a fresh supported environment, skill behavior with realistic tasks, CLI/MCP parity, UI flows, pagination, authorization boundaries, stale evidence, restart/retry recovery, and action receipts. Run the outstanding Docker/browser/restore checks separately; offline tests do not establish live GitHub behavior.

Completion criteria: record reproducible outcomes and remaining gaps in the checklist before describing the product as supporting proactive stewardship. Preserve the current validation evidence and distinguish synthetic checks from live exercises.

## beads-ui compatibility watch

On 2026-10-23, we reverted the expanded metadata and native workflow changes from `a6b39d6` because pinned beads-ui 0.12.6 cannot fully visualize or manage them. The candidate types were `github_issue` and `pull_request`; the manual statuses were `in_review:wip`, `backlog:active`, and `icebox:frozen`. Existing selected GitHub metadata and rendered descriptions remain supported by the hub.

Check [beads-ui releases](https://github.com/mantoni/beads-ui/releases) when reviewing dependency updates. Reconsider these features after upstream provides:

- Discovery of configured custom statuses/types, correct labels, and editing/filter options rather than fixed built-in lists.
- Category-aware board placement and a way to browse frozen work such as icebox items.
- A useful view of namespaced issue metadata, including `metadata.hub.github`.

Verify the released UI against the pinned Beads version in a browser before reintroducing these changes. Exercise create/edit/filter/board/detail flows and refresh after external sync writes; passing CLI/MCP tests alone is insufficient. This is a dependency-review watch item, not an automated monitor.
