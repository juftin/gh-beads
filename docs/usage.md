# Usage

## Development

Python 3.11+, uv, Task, and Docker with the Compose plugin are required for the full validation workflow. `task install` runs `uv sync --locked`, installing the `src/gh_beads` package editable and its development dependencies. `task fix`, `task lint`, `task check`, and `task test` cover formatting, lint, shell syntax, types, and token-free behavior tests. `task run -- <command>` runs inside the locked environment. `task package` uses `uv build --no-sources` to build the source distribution and wheel in `dist/`; `task build` still builds the Docker image.

The package installs one Click command, `gh-beads`, with subcommands: `gh-beads sync` for one-shot/periodic sync and progress inspection, `gh-beads mcp` for the official MCP stdio/HTTP/SSE server, `gh-beads runtime` for readiness and SQL account setup, `gh-beads snapshot` for portfolio coverage and queues, `gh-beads triage` for saved decisions, and `gh-beads skill` for listing, displaying, and installing agent skills. Use `gh-beads --help` to discover subcommands and `gh-beads SUBCOMMAND --help` for options. From the checkout, run them through uv or the Task wrapper:

```sh
task run -- gh-beads sync --help
uv run --locked gh-beads sync --status
```

These commands default to the current repository; `BEADS_WORKING_DIR` can select another initialized workspace. Local sync/MCP requires the matching native `bd` CLI with embedded Dolt support. Docker sets an explicit workspace and SQL connection, installs the package non-editable with runtime dependencies only, then starts the same commands directly. No `PYTHONPATH` configuration is required.

`task smoke` builds `gh-beads:test`, starts the checked-in Compose stack under a disposable project name with its own volume, and removes its test resources on exit. It uses synthetic GitHub data with real Beads, Dolt, UI, and MCP processes. It verifies readiness, dependencies, claims, local fields, closure, reopening, renames, HTTP and stdio MCP access, a separate remote SQL pointer, and restart persistence. It requires no GitHub token and publishes temporary localhost ports instead of the normal fixed ports. Its cleanup removes only the disposable source/restore projects and their data/backup volumes. Do not run `tests/smoke_runtime.py` against a real hub: it intentionally writes its synthetic backlog.

## Local embedded deployment

The [local guide](local.md) covers plain `bd init`, repository-local `.beads/embeddeddolt/` storage, uv polling, and a copyable client configuration. `gh-beads mcp` defaults to stdio. Native `bd` opens the database directly, with no SQL listener or separate Dolt executable. All local processes share one repository workspace, sync lock, and progress file. `task smoke-local` validates embedded behavior, concurrent poller/MCP access, and persistence in a disposable repository using native `bd` and synthetic source records. Compose continues to select HTTP/SSE and its SQL server explicitly. Existing server-mode workspaces retain their configured connection and are not converted by these defaults.

## Select repositories

Set `GH_SYNC_QUERY` in the environment used by Compose to semicolon-separated scopes:

```sh
export GH_SYNC_QUERY='user:@me;org:example-team;repo:another-owner/project'
```

Supported scopes:

| Scope | Coverage |
| --- | --- |
| `user:@me` | Repositories owned by the authenticated user, including accessible private ones |
| `user:NAME` | Repositories returned by GitHub's public user-repositories listing |
| `org:NAME` | Organization repositories visible to the credential |
| `repo:OWNER/REPO` | One explicitly named accessible repository |

Archived and disabled repositories are excluded. Overlapping scopes deduplicate by repository node ID. Search qualifiers such as `is:open`, `label:`, or free text are rejected. These are inventory scopes, not arbitrary GitHub search queries. Both issues and PRs are always included. Visibility is limited to the credential; inaccessible or filtered-out items are never considered closed merely because they disappear.

To sync a specific set on demand, repeat `--repo OWNER/REPO`. These names replace `GH_SYNC_QUERY` for that command, including when combined with `--full` or `--loop`:

```sh
# Local workspace
uv run --locked gh-beads sync --repo example/api --repo example/web
# Compose: repair only this repository
task sync-now -- --repo example/api --full
```

The MCP tool accepts the same selection as `trigger_github_sync` arguments:

```json
{"repositories": ["example/api", "example/web"]}
```

Omit `repositories` to use configured scopes. Empty lists and malformed names are rejected. Unselected repositories keep their existing imports, epics, and checkpoints. A manual selection does not change the running periodic worker; set `GH_SYNC_QUERY='repo:example/api;repo:example/web'` in its environment to persist that selection.

Each selected repository gets an epic titled `OWNER/REPO`, labeled `type:repository`, with its issues and PRs as children. Existing imports, including closed items, gain the parent during the next successful pass for their repository, even with an empty delta. Repository renames preserve the epic and child identities. Empty repositories also have epics. Epic status and local planning fields remain yours; closing children or removing a scope does not automatically close the epic. Sync maintains epic type and child parenting.

```sh
bd list --type epic --json
bd list --parent <epic-id> --all --limit 0 --json
```

The hub starts with a full open-item inventory, then polls changed issues/PRs in all states using a durable per-repository checkpoint and five-minute overlap. Every pass independently refreshes known open PR signals and all closing references. An hourly full open-backlog reconciliation repairs missed changes. It starts immediately after startup readiness; a new pass starts 120 seconds after the preceding pass ends. Set `GH_SYNC_INTERVAL` to another positive number of seconds before `task deploy` to change the pause. This is polling, not a fixed freshness SLA: source/API availability and pass duration affect lag. Manual and MCP triggers share the same lock.

| GitHub change | Next successful poll |
| --- | --- |
| New or reopened open issue/PR | Import or refresh the same stable bead |
| Edited title, assignments, milestone | Refresh source-owned text and metadata |
| New commits, CI results, or review decisions on an open PR | Refresh PR evidence, signal labels, and automatic readiness |
| Imported issue closed or PR closed/merged | Verify state directly, then close the bead and save closure evidence |
| Closed/referenced PR no longer blocks an issue | Closed blockers cease blocking through Beads; removed references prune hub-owned edges |
| Temporary API failure or downtime | Retain the previous snapshot; retry on later polls or after restart |

After bootstrap, all-state deltas can discover an item created and closed entirely between polls. Hourly, rename, and `--full` repairs retain that delta read alongside the full open inventory, so a repair does not skip terminal updates while advancing the checkpoint. Both reads must succeed before writes. Repairs after a long outage may therefore read a larger range of changed closed work. Old closed history predating bootstrap is not imported, and this is not a complete event history. Local Beads closes do not prevent upstream closure verification. A missing or inaccessible source is never proof of closure.

## Deploy with Docker Compose

Docker Engine and the Docker Compose plugin run the four services in `compose.yaml`: Dolt, UI/initialization, official MCP, and the reconciler. The named `data` volume stores the database and workspace. Keep one instance of each service.

Inject these variables through your shell or password manager before starting:

| Variable | Use |
| --- | --- |
| `BEADS_REMOTE_PASSWORD` | Required, nonempty password for the database-scoped remote SQL user `beads`; passed only to hub initialization |
| `GH_BEADS_DATABASE` | SQL database name, default `gh_beads`; use the existing database name when upgrading |
| `GH_TOKEN` | Read credential for selected repositories; passed only to MCP and the reconciler. Optional for offline UI/MCP use; sync reports an authentication failure when absent |
| `GH_SYNC_QUERY` | Inventory scopes, defaults to `user:@me` |
| `GH_SYNC_INTERVAL` | Positive pause in seconds between automatic passes, defaults to `120` |
| `GH_SYNC_WORKERS` | Independent GitHub node-read threads: `1` by default, optionally `2`–`4`; writes stay serial |

The GitHub credential needs metadata, issues, pull-request, checks, and commit-status read access to the selected repositories, including any private-repository and organization authorization. The Python source adapter authenticates directly through GitHubKit; GitHub CLI installation and `gh auth login` are not used by sync. Keep credentials out of source files, printed Compose configuration, and command history. `task validate` checks configuration with `docker compose config --quiet`, without printing environment values. Keep the same runtime environment available for operational tasks; Compose requires the SQL password when loading its configuration.

```sh
task validate
task deploy
```

`task deploy` builds the image locally, then runs `docker compose up -d --wait --wait-timeout 180`. The direct equivalent is `docker compose up -d --build --wait --wait-timeout 180`. Startup waits for SQL, then initializes the workspace and remote account before starting MCP and sync. All services have health checks and `restart: unless-stopped`. An unhealthy running container is reported unhealthy; the restart policy applies when its process exits.

The default image is `gh-beads:test`. To choose another tag consistently across build and startup, use `task deploy IMAGE=ghcr.io/example/gh-beads:0.1.0`. A registry is optional for a local deployment; `task push IMAGE=...` publishes an image only when explicitly invoked.

| Endpoint | Default host address |
| --- | --- |
| Web UI | `http://127.0.0.1:3000` |
| Streamable HTTP MCP | `http://127.0.0.1:8080/mcp` |
| Dolt SQL | `127.0.0.1:3307` |

Compose binds all three published ports to localhost. `BEADS_UI_PORT`, `BEADS_MCP_PORT`, and `BEADS_SQL_PORT` can select different host ports while container ports remain fixed. UI, MCP, and sync share Dolt's network namespace, so their port mappings belong to the `dolt` service. A separate container on the Compose network can reach SQL as `dolt:3307`. Initialize a matching `bd` CLI with the [pointer bootstrap](#compose-sql-clients).

Dolt's root account stays local to the shared container network namespace; external clients use the password-protected `beads` account restricted to `gh_beads`. To rotate its password, update the injected `BEADS_REMOTE_PASSWORD` and run `task deploy` so Compose recreates initialization with the new environment. Use a private tunnel or your own authenticated proxy for access from another host. SQL has no TLS configured, and UI/MCP have no built-in authentication. For legacy SSE, set `MCP_TRANSPORT=sse` and connect to `http://127.0.0.1:8080/sse`.

```sh
task down       # Stops services and removes containers/network; retains the data volume
task deploy     # Reuses the existing database
```

The default Compose project name is `gh-beads`, with data in `gh-beads_data`. `COMPOSE_PROJECT_NAME` or `docker compose -p` selects a different stack and volume. Bring the complete stack up together when replacing the Dolt container because the other services reference its network namespace. `task down` deliberately omits `--volumes`; deleting that volume would erase the backlog.

### Upgrading an existing deployment after the rename

The distribution is now `gh-beads`, Python imports use `gh_beads`, and the only installed command is `gh-beads`. Replace former `gh-beads-SUBCOMMAND` invocations with `gh-beads SUBCOMMAND` (for example, `gh-beads sync --status` and `gh-beads skill install`). In MCP clients, set the program to `gh-beads` and add `mcp` as its first argument, or append `"gh-beads", "mcp"` to the uv argument list. Update scripts and MCP launch configurations, then run `task install` to refresh the locked environment. The old console entrypoints are removed. Native embedded workspaces retain their existing data and polling state; no database initialization is needed.

An existing Compose deployment must keep its original project/volume and SQL database. For the previous defaults, export `COMPOSE_PROJECT_NAME=beads-hub` and `GH_BEADS_DATABASE=beads_hub` before running Compose or Task commands. Stop the old services with their original project name before replacing them, and follow the [backup procedure](#backup-and-restore) with the actual existing volume and image names. Use the existing database name for SQL pointers too. Changing the default project name alone selects a new empty volume; it does not move data. Never reinitialize the existing workspace. New deployments use `gh-beads_data` and `gh_beads`.

Stored `metadata.hub`, `hub:manual-status`, existing bead ID prefixes, and `.github-sync-*` files retain their contracts so existing imports, local status overrides, and saved reviews survive the project rename.

### Compose SQL clients

Create a fresh, dedicated host pointer once, after `task deploy`. This pointer stores connection metadata, not another embedded copy of the backlog:

```sh
export BEADS_WORKING_DIR="$HOME/.config/beads-remote"
export BEADS_DIR="$BEADS_WORKING_DIR/.beads"
export BEADS_DOLT_SERVER_MODE=1
export BEADS_DOLT_SERVER_HOST=127.0.0.1
export BEADS_DOLT_SERVER_PORT=3307
export BEADS_DOLT_SERVER_USER=beads
export BEADS_DOLT_AUTO_START=0
export BEADS_ACTOR=maintainer
: "${BEADS_DOLT_PASSWORD:?Inject the remote SQL password securely at runtime}"

mkdir -p "$BEADS_WORKING_DIR"
(
  cd "$BEADS_WORKING_DIR"
  bd init --server --external --server-host "$BEADS_DOLT_SERVER_HOST" \
    --server-port "$BEADS_DOLT_SERVER_PORT" --server-user beads --database gh_beads --prefix hub \
    --non-interactive --skip-agents --skip-hooks
)
```

The explicit database is `gh_beads`. The `beads` account is restricted to that database; `BEADS_DOLT_PASSWORD` must equal the value injected as `BEADS_REMOTE_PASSWORD` at deployment. If the host SQL port was changed, set the matching client port. A separate container on the Compose network can use `dolt:3307`. For another host, use a private TCP tunnel to the published localhost port. Do not reinitialize an existing unrelated workspace.

Host pointers have separate filesystem locks/progress, even when addressing the same SQL database. Keep GitHub reconciliation inside Compose through `task sync-now` or its HTTP MCP trigger; do not start an independent host poller against the pointer.


## Operate and triage

### Portfolio snapshot and saved decisions

Start portfolio triage with one stored view:

```sh
# Local initialized workspace; no token or network needed
uv run --locked gh-beads snapshot --json
uv run --locked gh-beads snapshot --repo example/api --repo example/web --limit 50
# Compose uses the poller workspace and its checkpoints
task snapshot -- --limit 50
```

The JSON includes workspace/database identity, selection/coverage, repository links and last-success ages, source-state/local-status totals, and ready, blocked, in-progress, needs-attention, unreviewed, and changed-since-review queues. Counts cover the selected stored imports; lists default to 20 items per queue. Inspect `total`, `returned`, and `truncated`. Use `bd show ID --json` for the complete body/evidence. Needs-attention includes claimed/deferred PRs; readiness comes from Beads' dependency evaluation. Review changes include upstream closure. This is a best-effort view across separate stored reads.

`coverage.status=complete` means the last matching repository discovery exists and each discovered repository has a successful checkpoint without a recorded error. Check `discovered_at`, repository `age_seconds`, errors, and `retry_at` separately for freshness. After an upgrade, sync once to populate discovery history. Missing discovery or changed configured scopes means partial coverage: broad scopes return a labeled historical fallback; explicit repo scopes filter by known names. Selected syncs retain configured-portfolio discovery. Closed history before bootstrap remains outside coverage. Host SQL pointers lack Compose's progress file; run snapshots in Compose for source coverage.

Record local decisions after applying desired priority/category changes with `bd`:

```sh
uv run --locked gh-beads triage BEAD_ID --reviewer agent \
  --rationale 'Failing checks block the release' --next-action 'Inspect failing test output'
# Compose: same command against its workspace
docker compose exec -T github-reconciler gh-beads triage BEAD_ID --reviewer agent \
  --rationale 'Failing checks block the release' --next-action 'Inspect failing test output'
```

Each call appends a review without replacing notes/comments or setting priority, status, or assignee. Supply `--reviewer` or configure `BEADS_ACTOR`. Add `--expected-fingerprint VALUE` using the snapshot item's `triage.source_fingerprint` to refuse a review if imported evidence changed after inspection. Re-read after refusal or a busy lock. The guard applies to stored facts, not unseen upstream changes. Keep reviews concise and avoid secrets. Inspect full history under `metadata.triage.reviews` with `bd show`; sync preserves it. Later imported changes set triage status to `changed`; identical polls and local planning edits do not. Reviews do not expire or trigger automatic actions.

MCP exposes `portfolio_snapshot` with `repositories` and `limit`, plus `record_triage` with `bead_id`, `rationale`, `next_action`, optional `reviewer`, and optional `expected_fingerprint`. These additions retain all official Beads tools.

### Sync status and manual triage

```sh
task sync-now
task sync-now -- --full  # Force an open-backlog repair without deleting progress
task sync-status        # Repository checkpoints, last success/error, and rate cooldown
docker compose logs --tail=20 github-reconciler
docker compose logs --tail=20 beads-mcp
docker compose ps
```

One-shot sync emits JSON and exits nonzero on `partial`; a periodic worker logs the same result and retries after its interval. `modes` reports full/delta per repository; `writes` counts successful mutating Beads commands. Item counts describe processed records, not total backlog size. A `busy` result means another pass holds the lock. Discovery failures stop the pass before writes. Repository read failures preserve that repository's prior snapshots; write/graph failures may leave partial changes but do not advance its checkpoint. Successful repository results are saved together once at the end of a pass, while failed ones keep their prior checkpoints. A crash before saving safely replays that pass. There is no transactional snapshot of GitHub or the entire portfolio.

Progress lives in `/var/lib/beads/.github-sync-state.json` on the shared volume. `task sync-status` reads it without contacting GitHub. Each repository has its last committed pass start (`checkpoint`), successful completion (`last_success_at`), full scan (`last_full_at`), and last error. Times are UTC Unix seconds. Check their age and reconciler logs; inventory errors appear in pass logs, and repositories outside the current scopes retain historical progress. The global `retry_at` records API cooldowns. Removing only this progress file requests a new open-inventory bootstrap, but normally use `--full` for repairs; malformed state fails visibly and needs operator attention. Never delete the data volume to reset polling.

A healthy container/database alone does not prove GitHub freshness: the health check verifies database access. An unchanged bead's `metadata.hub.github.observed_at` intentionally stays unchanged to avoid repeat writes; use repository `last_success_at` for polling freshness. No automatic freshness alert or webhook receiver is implemented.

Keep the default one read worker initially. For high-latency portfolios, `export GH_SYNC_WORKERS=2` before `task deploy` enables bounded parallel node reads; 4 is the maximum. GitHub recommends serial API requests to avoid secondary limits, so measure pass duration and API errors before increasing it. Only GitHub reads use threads. Beads writes, graph changes, and checkpoint commits remain ordered, including when sync is triggered through MCP.

Use local labels for classification and standard Beads priority for ranking:

```sh
bd list --label type:issue --json
bd ready --label 'type:pr,review:needed' --json
bd update <id> --add-label category:dependency-upgrade --priority 3
bd update <id> --claim
bd blocked --json
```

GitHub label names are not imported into Beads labels or metadata. Legacy `github:` labels and `metadata.hub.github.labels` are removed from existing imported issues/PRs during the next successful pass for their repository, including closed work and items absent from a delta. Selected syncs leave excluded repositories untouched; a failed source read performs no cleanup. This does not require a full source refresh or modify labels in GitHub. Other local labels, local metadata, and triage history are preserved. The reconciler owns source title/description; put durable reasoning in Beads notes and comments. Beads priority and issue/PR type are local choices (imports start as `task`, priority 2); repository containers stay `epic`.

Every imported issue/PR also carries source facts under `metadata.hub.github`: author, upstream assignees, milestone, dates, comment count, repository details, and PR branch SHAs, size, reviewer requests, merge/review/CI state. Inspect these with `bd show <id> --json`. Descriptions show an attention summary and a linked two-column table, followed by the unchanged GitHub body. Links open the source item/repository, author and assignees, milestone, requested reviewers/teams, source branch snapshots (including forks), PR checks/review pages, and closing issues. Missing forks retain plain branch text; incomplete reviewer lists are marked. GitHub assignees do not claim the bead. Repository grouping remains the `repo:OWNER/REPO` label, with stable repository identity in `metadata.hub.repo_id`.

New source filters are sync-owned:

| Filter | Meaning |
| --- | --- |
| `size:s`, `size:m`, `size:l` | PR added+deleted lines: under 100, 100–499, or 500+; describes diff size, not effort |
| `author:bot` | GitHub identifies the source author as a bot |
| `links:closing-issue` | A PR has authoritative closing references, including targets outside selected scopes |
| `resolution:merged` | Verified upstream PR merge |
| `resolution:not-planned` | Explicit upstream not-planned closure reason |

```sh
bd ready --label 'type:pr,size:s' --json
bd list --label 'author:bot' --json
bd list --all --label 'resolution:merged' --json
```

Canonical author/assignee/milestone URLs are stored under `metadata.hub.github.links`; requested-reviewer URLs, `head_repository`, and fully paginated `closing_issues` live under `pull_request`. No extra API requests are needed for these fields. Existing descriptions and labels refresh when their source items are observed; `task sync-now -- --full` refreshes the current open inventory. Already-closed unchanged history is not reread merely to reformat it. The summary's source dates do not represent polling freshness.

These are selected source observations, with the stored snapshot's `observed_at` timestamp. Reviewer details are bounded to 100 with explicit total/coverage fields; comment bodies, diffs, and history are not imported. See [source metadata](architecture.md#source-metadata) for fields and freshness limits. API throttling/exhaustion persists a cooldown from Retry-After/reset evidence; passes skip network requests until it expires, including after restarts. The SDK does not sleep through resets. Other network failures retry on subsequent polls.

Only authoritative `closingIssuesReferences` create blockers. GitHub resolves supported closing keywords, including recognized cross-repository references; arbitrary mentions and text in non-closing contexts do not create dependencies. Linked issues must already be indexed by the selected scopes. Removing a reference removes only edges managed by the hub. Existing manual edges are retained. Closing a PR releases its blocking effect through Beads' normal readiness rules.

### Open-source stewardship and companion tools

The hub pairs with the portable stewardship skill ([`skills/oss-steward/SKILL.md`](../skills/oss-steward/SKILL.md)) and companion GitHub action tools (such as the `gh` CLI or an agent GitHub connector).

- **Read-only boundary:** `gh-beads` synchronizes GitHub facts into Beads and records local triage decisions. It never writes to GitHub.
- **Companion tools for upstream actions:** Posting comments, submitting PR reviews, merging PRs, or closing issues must be executed through authorized companion tools (e.g., `gh issue comment`, `gh pr review`, `gh pr merge --match-head-commit <sha>`).
- **Action receipts:** Whenever an upstream action is executed, record an action receipt in Beads (`bd note BEAD_ID "receipt: action=... actor=... target=... result=confirmed"`).
- **Stewardship skill:** The [`oss-steward`](../skills/oss-steward/SKILL.md) skill guides agents through prompt injection defense (treating GitHub content as passive evidence), evaluating dependency upgrades, engaging external contributors, triaging bug reports, and managing feature requests.
- **Installing for all agents:** The `gh-beads skill` subcommand (and helper `scripts/install-skill.sh`) installs the skill across agent environments:
  ```sh
  gh-beads skill list --json
  gh-beads skill show oss-steward --consolidated
  gh-beads skill install oss-steward --target workspace   # .agents/skills/oss-steward/
  gh-beads skill install oss-steward --target global      # ~/.agents/skills/ and ~/.gemini/antigravity-cli/skills/
  gh-beads skill install oss-steward --target claude      # .claude/skills/oss-steward/
  gh-beads skill install oss-steward --target cursor      # .cursor/rules/oss-steward.mdc
  gh-beads skill install oss-steward --target copilot     # .github/copilot-instructions.md
  gh-beads skill install oss-steward --target all         # Installs to all supported workspace formats
  ```
- **MCP agent access:** FastMCP serves the skill as tool `install_stewardship_skill`, resources `skills://oss-steward/SKILL.md` and `skills://oss-steward/references/{name}`, and prompt `oss_steward`.

For backups, follow the [offline volume procedure](#backup-and-restore). Preserve workspace metadata, sync progress, and the full database together; test restoration before relying on a backup. Do not delete or reinitialize the data volume to work around startup errors. Initialization errors fail the container without a fallback destructive init.

## Backup and restore

The supported exercise uses an offline physical copy: stop every writer and Dolt before copying the complete workspace/volume. Issue JSONL alone omits database history and sync checkpoints. Never copy active database files. Preserve image/tool versions and non-secret deployment settings with backup records; inject credentials again when restoring. Protect backup storage as you would the backlog.

For the default Compose project, this archives its stopped volume. Substitute the actual volume and matching runtime image if different:

```sh
backup_dir="$HOME/gh-beads-backups/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$backup_dir"
chmod 700 "$backup_dir"
task down
# Stop external SQL clients too. Mount the source read-only.
docker run --rm --network none --entrypoint tar \
  --mount type=volume,src=gh-beads_data,dst=/data,readonly \
  --mount "type=bind,src=$backup_dir,dst=/backup" \
  gh-beads:test -C /data -czf /backup/workspace.tar.gz .
task deploy
```

Restore to a new disposable project/volume first. Use an empty target with no clients. Do not restore over the live volume or reinitialize the backup:

```sh
docker volume create gh-beads-restore_data
docker run --rm --network none --entrypoint tar \
  --mount type=volume,src=gh-beads-restore_data,dst=/data \
  --mount "type=bind,src=$backup_dir,dst=/backup,readonly" \
  gh-beads:test -C /data -xzf /backup/workspace.tar.gz
# Inject BEADS_REMOTE_PASSWORD; leave GitHub polling offline during inspection.
GH_TOKEN= BEADS_UI_PORT=0 BEADS_MCP_PORT=0 BEADS_SQL_PORT=0 \
  docker compose -p gh-beads-restore up -d --wait --wait-timeout 180
docker compose -p gh-beads-restore exec -T github-reconciler gh-beads snapshot --json
```

Compare source/local fields, stable IDs/epic parents, dependency edges, claims, priorities, labels, notes, full triage history, and `.github-sync-state.json` to pre-backup records. Confirm the volume is the restore target. Promote only after verification and reconnecting intended clients. The sample leaves the restore available for inspection; stop it when finished without touching the source project.

`task smoke-restore` automates a fresh synthetic native embedded exercise: copy the stopped `.beads` workspace and progress, modify the original to prove independence, restore elsewhere, compare full records/graph/queues/progress, and replay sync with zero writes. It requires native Beads 1.3.1, no Docker or GitHub credential. `task smoke` adds SQL/Compose validation: restart the synthetic stack, stop application writers and capture a baseline, stop SQL, copy the entire volume to backup and then a separate restore project, start it, and compare full records/graph/reviews/queues/checkpoints. Both workflows clean up their own disposable data. Docker smoke execution requires a Docker host.

## Current limits

This branch stores selected source snapshots in Beads, not complete GitHub conversations, diffs, or source event history. Categorization and triage are human/agent actions; there is no model invocation or automatic taxonomy. Bootstrap imports open work; subsequent deltas include changed closed records. No GitHub write-back, webhooks, adaptive scheduling, GraphQL batching, automatic freshness alerts, HA, built-in authentication, or migration from gh-maintainer is implemented. Repository inventories and Beads lookups still run every pass. PRs absent from the REST delta retain last-known REST facts while GraphQL signals refresh. API changes, long clock skew, and moving paginated collections may require the periodic full repair; a pass is not a point-in-time snapshot. A failed or unavailable source never proves deletion.

The pinned UI watches local workspace files rather than polling SQL for every external mutation. Refresh the browser after remote CLI changes if they have not appeared. Its live-refresh behavior across remote clients is an upstream limitation; the smoke test verifies actual issue/PR delivery over its WebSocket API, not a full browser interaction suite.
