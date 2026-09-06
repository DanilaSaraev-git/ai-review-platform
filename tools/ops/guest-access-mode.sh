#!/usr/bin/env bash

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

[[ $# -eq 1 && ( "$1" == true || "$1" == false ) ]] \
  || die "usage: $0 true|false"
require_root
require_command docker
require_command flock

release_dir="$(realpath -e "${REVIEW_COMPOSE_RELEASE_DIR:-$REVIEW_CURRENT_LINK}")"
require_production_release "$release_dir"
[[ -f "$release_dir/packages/review-runtime/migrations/versions/20260906_0003_guest_sessions.py" ]] \
  || die "guest mode changes require a release that supports schema 20260906_0003"
check_private_file "$REVIEW_ENV_FILE"

exec 9>"${REVIEW_STATE_DIR}/.release.lock"
flock -n 9 || die "another release, backup, or model operation is already running"

export REVIEW_GUEST_ACCESS="$1"
compose_active_args "$release_dir"
docker compose "${COMPOSE_ARGS[@]}" config --quiet

env_tmp=""
gateway_stopped=0
cleanup_mode_change() {
  local status=$?
  set +e
  [[ -z "$env_tmp" ]] || rm -f -- "$env_tmp"
  if ((status != 0 && gateway_stopped == 1)); then
    docker compose "${COMPOSE_ARGS[@]}" stop --timeout 30 gateway >/dev/null
    printf '%s\n' 'guest mode change failed; gateway is stopped, database and artifacts are unchanged' >&2
  fi
  return "$status"
}
trap cleanup_mode_change EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

docker compose "${COMPOSE_ARGS[@]}" stop --timeout 30 gateway >/dev/null
gateway_stopped=1
env_tmp="$(mktemp "${REVIEW_ENV_FILE}.guest-XXXXXX")"
awk -v mode="$REVIEW_GUEST_ACCESS" '
  /^REVIEW_GUEST_ACCESS=/ {
    if (!seen++) print "REVIEW_GUEST_ACCESS=" mode
    next
  }
  {print}
  END {if (!seen) print "REVIEW_GUEST_ACCESS=" mode}
' "$REVIEW_ENV_FILE" > "$env_tmp"
chmod 600 "$env_tmp"
mv -f -- "$env_tmp" "$REVIEW_ENV_FILE"
env_tmp=""

docker compose "${COMPOSE_ARGS[@]}" up --detach --no-build --no-deps --force-recreate --wait api proxy gateway
"$release_dir/tools/ops/verify-deployment.sh"
printf 'guest access set to %s on the same release; database schema and guest sessions are preserved\n' \
  "$REVIEW_GUEST_ACCESS"
