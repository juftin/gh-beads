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
| Detailed checks and review threads | Pending | Bounded check names/details URLs and unresolved review-thread evidence |
| Explicit issue blockers | Pending | Source-owned issue-to-issue dependencies beyond PR closing references |
| Portfolio snapshot | Implemented as CLI, MCP, and Compose Task with repository rollups and bounded work/review queues | Stored read-only view; explicit discovery/selection gaps and freshness ages; separate source/local counts |
| Remembered triage decisions | Implemented with local review history, reviewer/rationale/next action, and source fingerprints | Sync-preserved; changed-since-review includes terminal updates; no automatic classification or GitHub writes |
| Source and local triage separation | Implemented | Classification is supplied by humans/agents |
| Omit GitHub label copies | Implemented | Source labels are excluded from Beads labels/metadata; successful selected passes prune legacy copies even with empty deltas while retaining local decisions and hub signals |
| PR signal triage and closing dependencies | Implemented | Latest signals, indexed closing targets, GitHub's recognized references |
| Shared CLI, UI, official MCP | Implemented | Trusted clients; one database |
| Agent triage workflow | Implemented in a concise [AGENTS.md](../AGENTS.md), with Beads 1.3.1's minimal `bd onboard` reference | Starts with portfolio-wide inventory, source freshness, ranked actions, and durable local decisions; setup/development detail stays in linked documentation |
| Local embedded Dolt and stdio MCP | Implemented as the local default with repository-local storage and no SQL listener | Current-directory or explicit workspace; native ARM64 initialization, concurrent poller/MCP access, shared locking, and persistence verified with `task smoke-local` |
| Python source package and uv workflows | Implemented in `src/gh_beads` with the uv build backend and installed sync/MCP/runtime commands | Locked editable development install, non-editable Docker install, source distribution and wheel via `task package` |
| Unified image and Docker Compose deployment | Implemented | Four services, one persistent volume, localhost ports; operator supplies runtime credentials |
| Runtime and regression validation | 151 offline tests, installed CLI and stdio default checks, source/wheel builds, operation-count and repair-coverage regressions, native ARM64 macOS and AMD64 Linux embedded Dolt validation, linked table renderer checks, and prior Compose smoke coverage | Latest embedded CLI/MCP review/snapshot and offline restore checks pass on AMD64 Linux; Docker epic/link/triage/restore assertions await execution; credentialed pilot, AMD64 image build, and full browser interactions remain unverified; see checklist |
| Live multi-repository pilot | Pending | Needs an authorized GitHub credential and Docker host |
| Backup/restore exercise | Native embedded offline copy/independent restore passes; Compose smoke and operator runbook implemented | Preserves full workspace, graph, local decisions, and checkpoints; SQL/Compose restore execution requires a Docker host |

Before adopting this as a daily backlog, run a credentialed pilot across issue-only, PR-only, private, and organization repositories. Confirm visibility, merge policy signals, graph cleanup, and operational freshness. Record request volume, `writes`, pass duration, and throttling before deciding whether GraphQL batching, conditional HTTP caching, different worker counts, or per-repository cadence are needed.

HA, webhooks, automatic GitHub writes, model-driven categorization, full conversation/code ingestion, built-in authentication, and migration from the earlier application are outside this milestone. Add them only when a workflow demonstrates the need and defines completion criteria.

## beads-ui compatibility watch

On 2026-10-23, we reverted the expanded metadata and native workflow changes from `a6b39d6` because pinned beads-ui 0.12.6 cannot fully visualize or manage them. The candidate types were `github_issue` and `pull_request`; the manual statuses were `in_review:wip`, `backlog:active`, and `icebox:frozen`. Existing selected GitHub metadata and rendered descriptions remain supported by the hub.

Check [beads-ui releases](https://github.com/mantoni/beads-ui/releases) when reviewing dependency updates. Reconsider these features after upstream provides:

- Discovery of configured custom statuses/types, correct labels, and editing/filter options rather than fixed built-in lists.
- Category-aware board placement and a way to browse frozen work such as icebox items.
- A useful view of namespaced issue metadata, including `metadata.hub.github`.

Verify the released UI against the pinned Beads version in a browser before reintroducing these changes. Exercise create/edit/filter/board/detail flows and refresh after external sync writes; passing CLI/MCP tests alone is insufficient. This is a dependency-review watch item, not an automated monitor.
