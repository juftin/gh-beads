#!/usr/bin/env bash
set -euo pipefail

image="${1:-gh-beads:test}"
stack="gh-beads-smoke-$$"
restore_stack="${stack}-restore"
backup_volume="${stack}-backup"
root="$(cd "$(dirname "$0")/.." && pwd)"
export IMAGE="$image" GH_TOKEN= GH_SYNC_QUERY=user:@me MCP_TRANSPORT=streamable-http
export BEADS_REMOTE_PASSWORD=synthetic-smoke-password
export GH_BEADS_DATABASE=gh_beads
export BEADS_UI_PORT=0 BEADS_MCP_PORT=0 BEADS_SQL_PORT=0
compose() {
  docker compose --project-name "$stack" --file "$root/compose.yaml" "$@"
}
restore_compose() {
  docker compose --project-name "$restore_stack" --file "$root/compose.yaml" "$@"
}
cleanup() {
  restore_compose down --volumes >/dev/null 2>&1 || true
  compose down --volumes >/dev/null 2>&1 || true
  docker volume rm "$backup_volume" >/dev/null 2>&1 || true
}
trap cleanup EXIT
if ! compose up -d --build --wait --wait-timeout 180; then
  compose logs
  exit 1
fi
dolt_id="$(compose ps -q dolt)"
ui_address="$(compose port dolt 3000)"
case "$ui_address" in
  127.0.0.1:*) curl -fsS "http://$ui_address/healthz" ;;
  *) echo 'UI port must be bound to localhost' >&2; exit 1 ;;
esac
if ! docker run --rm --network "container:$dolt_id" \
  -v "${stack}_data:/var/lib/beads" -v "$root/tests:/tmp/hub-tests:ro" \
  "$image" python3 /tmp/hub-tests/smoke_runtime.py; then
  compose logs
  exit 1
fi

# A separate container verifies the documented remote pointer over the Compose network.
docker run --rm --network "${stack}_default" -e BEADS_DOLT_SERVER_HOST=dolt \
  -e BEADS_DOLT_SERVER_USER=beads -e BEADS_DOLT_PASSWORD=synthetic-smoke-password \
  -e BEADS_DIR=/tmp/pointer/.beads -e BEADS_WORKING_DIR=/tmp/pointer "$image" bash -c '
    set -euo pipefail
    mkdir -p /tmp/pointer
    cd /tmp/pointer
    bd init --server --external --server-host dolt --server-port 3307 --server-user beads \
      --database gh_beads --prefix hub --non-interactive --skip-agents --skip-hooks
    bd list --all --limit 0 --json
  '

compose down
compose up -d --wait --wait-timeout 180
compose exec -T hub gh-beads-runtime
compose exec -T hub python3 -c \
  'import json, subprocess; assert len(json.loads(subprocess.check_output(["bd", "list", "--all", "--limit", "0", "--json"], text=True))) == 3'
compose exec -T github-reconciler python3 -c \
  'from pathlib import Path; from gh_beads.state import SyncState; state = SyncState(Path("/var/lib/beads/.github-sync-state.json")); assert state.data["repositories"]["R_1"]["name"] == "example/renamed"; assert state.data["repositories"]["R_1"]["checkpoint"] > 0'

# Capture a baseline with application writers stopped, then stop SQL before copying.
compose stop github-reconciler beads-mcp hub
dolt_id="$(compose ps -q dolt)"
docker run --rm --network "container:$dolt_id" \
  -v "${stack}_data:/var/lib/beads" -v "$root/tests:/tmp/hub-tests:ro" \
  "$image" python3 /tmp/hub-tests/smoke_restore.py \
  --capture /var/lib/beads/.restore-baseline.json
compose down
docker volume create "$backup_volume" >/dev/null
docker run --rm -v "${stack}_data:/source:ro" -v "$backup_volume:/backup" \
  "$image" bash -c 'cp -a /source/. /backup/'
docker volume create "${restore_stack}_data" >/dev/null
docker run --rm -v "$backup_volume:/backup:ro" -v "${restore_stack}_data:/restore" \
  "$image" bash -c 'cp -a /backup/. /restore/'
if ! restore_compose up -d --wait --wait-timeout 180; then
  restore_compose logs
  exit 1
fi
restored_dolt_id="$(restore_compose ps -q dolt)"
docker run --rm --network "container:$restored_dolt_id" \
  -v "${restore_stack}_data:/var/lib/beads" -v "$root/tests:/tmp/hub-tests:ro" \
  "$image" python3 /tmp/hub-tests/smoke_restore.py \
  --verify /var/lib/beads/.restore-baseline.json
echo 'Smoke checks passed, including remote pointer, restart, and independent volume restore.'
