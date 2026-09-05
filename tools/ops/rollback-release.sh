#!/usr/bin/env bash

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

usage() {
  printf 'usage: %s FULL_GIT_SHA\n' "$0" >&2
  exit 2
}

[[ $# -eq 1 ]] || usage
require_root
require_command curl
require_command docker
require_command flock
commit="$1"
[[ "$commit" =~ ^[0-9a-f]{40}$ ]] || die "commit is not a full Git SHA"
target="$(realpath -e "$REVIEW_RELEASES_DIR/$commit")"
require_safe_release_dir "$target"
current="$(realpath -e "$REVIEW_CURRENT_LINK")"
[[ "$target" != "$current" ]] || die "target release is already current"
require_production_release "$current"
check_private_file "$REVIEW_ENV_FILE"
if [[ ! -f "$target/deploy/compose/compose.production.yaml" && -f "$REVIEW_MODEL_ENABLED_MARKER" ]]; then
  die "disable the external model before rolling back to a legacy release"
fi

exec 9>"${REVIEW_STATE_DIR}/.release.lock"
flock -n 9 || die "another release operation is already running"

REVIEW_RELEASE_LOCK_HELD=1 REVIEW_COMPOSE_RELEASE_DIR="$current" "$current/tools/ops/backup.sh" >/dev/null
restore_current_on_failure() {
  local status=$?
  if ((status != 0)); then
    compose_active_args "$current"
    docker compose "${COMPOSE_ARGS[@]}" up --detach --no-build --wait --remove-orphans \
      postgres api proxy gateway >/dev/null 2>&1 || true
  fi
  exit "$status"
}
trap restore_current_on_failure EXIT INT TERM
if [[ -f "$target/deploy/compose/compose.production.yaml" ]]; then
  compose_active_args "$target"
  docker compose "${COMPOSE_ARGS[@]}" config --quiet
  docker compose "${COMPOSE_ARGS[@]}" up --detach --no-build --wait --remove-orphans postgres api proxy gateway
  "$target/tools/ops/verify-deployment.sh"
else
  require_command systemctl
  compose_legacy_args "$target"
  docker compose "${COMPOSE_ARGS[@]}" config --quiet
  docker compose "${COMPOSE_ARGS[@]}" up --detach --no-build --wait --remove-orphans postgres api proxy
  proxy_port="$(env_value REVIEW_PROXY_PORT)"
  curl --silent --show-error --fail --max-time 10 "http://127.0.0.1:${proxy_port}/health/ready" >/dev/null
  curl --silent --show-error --fail --max-time 10 "http://127.0.0.1:${proxy_port}/v1/bootstrap" >/dev/null
  if ss -lnt | awk 'NR > 1 {print $4}' | grep -Eq '(^|:)(80|443)$'; then
    die "legacy rollback left a public gateway listener active"
  fi
  systemctl stop review-backup.timer review-cert-renew.timer review-model-probe.timer || true
fi

previous_tmp="${REVIEW_PREVIOUS_LINK}.new-$$"
current_tmp="${REVIEW_CURRENT_LINK}.new-$$"
ln -s "$current" "$previous_tmp"
ln -s "$target" "$current_tmp"
mv -Tf "$previous_tmp" "$REVIEW_PREVIOUS_LINK"
mv -Tf "$current_tmp" "$REVIEW_CURRENT_LINK"
trap - EXIT INT TERM
printf 'rolled back application to %s; database schema was not downgraded\n' "$commit"
