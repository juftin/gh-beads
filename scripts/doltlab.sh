#!/usr/bin/env bash
# Optional, independent DoltLab deployment using upstream-generated Compose assets.
set -euo pipefail
umask 077

release=v2.6.3
archive_sha256=e17ccf8904fd676dc7649ec3fd52658be1a5105695d562cd1fdbedb6bca3abdf
project=gh-beads-doltlab
repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
deployment_dir="${DOLTLAB_DIR:-$repo_dir/.doltlab}"
action="${1:-}"
if [ "$#" -gt 0 ]; then shift; fi

die() { echo "$*" >&2; exit 1; }

require_passwords() {
  : "${DOLT_ADMIN_PASSWORD:?Inject the DoltLab application database admin password}"
  : "${DOLT_DOLTHUBAPI_PASSWORD:?Inject the DoltLab application database API password}"
  : "${DEFAULT_USER_PASSWORD:?Inject the DoltLab initial admin login password}"
}

if [ "$action" = setup ]; then
  [ "$(uname -s)" = Linux ] && [ "$(uname -m)" = x86_64 ] || \
    die 'DoltLab setup requires a Linux AMD64 host.'
  : "${DOLTLAB_HOST:?Set a hostname or IP reachable by browsers and Dolt clients}"
  require_passwords
  # Upstream embeds absolute paths in generated scripts; keep paths free of whitespace.
  case "$deployment_dir" in *[[:space:]]*) die 'DOLTLAB_DIR must not contain whitespace.';; esac
  mkdir -p -- "$deployment_dir"
  deployment_dir="$(cd -- "$deployment_dir" && pwd)"
  marker="$deployment_dir/.gh-beads-release"
  if [ -e "$deployment_dir/installer" ]; then
    [ -f "$marker" ] && [ "$(cat "$marker")" = "$release" ] || \
      die 'Existing DoltLab installer is unmanaged or a different release; follow the upgrade guide.'
  else
    for dependency in curl unzip sha256sum; do
      command -v "$dependency" >/dev/null || die "Install $dependency before DoltLab setup."
    done
    download_dir="$(mktemp -d)"
    trap 'rm -rf -- "$download_dir"' EXIT
    curl --fail --silent --show-error --location --retry 3 \
      "https://doltlab-releases.s3.us-east-1.amazonaws.com/linux/amd64/doltlab-$release.zip" \
      --output "$download_dir/release.zip"
    echo "$archive_sha256  $download_dir/release.zip" | sha256sum --check --status || \
      die 'DoltLab archive checksum mismatch; nothing was extracted or executed.'
    unzip -q "$download_dir/release.zip" -d "$download_dir/unpacked"
    # Preserve existing operator configuration on repeated setup.
    install -m 700 "$download_dir/unpacked/installer" "$deployment_dir/installer"
    printf '%s\n' "$release" > "$marker"
  fi
  if [ -f "$deployment_dir/.gh-beads-configured" ]; then
    [ -f "$deployment_dir/docker-compose.yaml" ] || die 'Configured DoltLab assets are missing; restore the deployment directory.'
    echo 'DoltLab is already configured; setup preserves its assets and keys.'
    exit 0
  fi
  if [ ! -f "$deployment_dir/installer_config.yaml" ]; then
    cp -- "$repo_dir/deploy/doltlab/installer_config.yaml" "$deployment_dir/installer_config.yaml"
  fi
  cd -- "$deployment_dir"
  ./installer --config "$deployment_dir/installer_config.yaml" --host "$DOLTLAB_HOST" \
    --network "$project" --runtime docker --use-env --disable-usage-metrics
  touch .gh-beads-configured
  echo 'DoltLab configured. Run task doltlab:deploy with the same injected passwords.'
  exit 0
fi

case "$action" in
  deploy|validate|status|logs|down) ;;
  *) die 'Usage: scripts/doltlab.sh {setup|validate|deploy|status|logs|down}' ;;
esac
[ -f "$deployment_dir/docker-compose.yaml" ] || die 'Run task doltlab:setup first.'
[ -f "$deployment_dir/.gh-beads-configured" ] || die 'DoltLab setup did not complete; run task doltlab:setup again.'
deployment_dir="$(cd -- "$deployment_dir" && pwd)"
cd -- "$deployment_dir"

# Keep hub Compose selection and dotenv files out of this independent stack.
unset COMPOSE_FILE COMPOSE_PROFILES COMPOSE_ENV_FILES
export COMPOSE_PROJECT_NAME="$project" COMPOSE_DISABLE_ENV_FILE=true
compose() {
  docker compose --project-name "$project" --env-file /dev/null \
    --file "$deployment_dir/docker-compose.yaml" "$@"
}

case "$action" in
  deploy|validate)
    require_passwords
    compose config --quiet
    if [ "$action" = deploy ]; then
      docker network inspect "$project" >/dev/null 2>&1 || docker network create "$project"
      compose up -d
    fi
    ;;
  status) compose ps ;;
  logs) compose logs --follow "$@" ;;
  down) compose down ;;
esac
