#!/usr/bin/env bash

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

require_root
require_command flock
exec 9>"${REVIEW_STATE_DIR}/.release.lock"
flock -n 9 || die "another release, backup, or model operation is already running"
release_dir="$(realpath -e "$REVIEW_CURRENT_LINK")"
require_production_release "$release_dir"
[[ -f "$REVIEW_MODEL_ENABLED_MARKER" ]] || die "external model is already disabled"
check_private_file "$REVIEW_MODEL_ENV_FILE"

restore_model_on_failure() {
  local status=$?
  if ((status != 0)); then
    compose_model_args "$release_dir"
    docker compose "${COMPOSE_ARGS[@]}" up --detach --no-build --wait api proxy gateway >/dev/null 2>&1 || true
  fi
  exit "$status"
}
trap restore_model_on_failure EXIT INT TERM
compose_base_args "$release_dir"
docker compose "${COMPOSE_ARGS[@]}" config --quiet
docker compose "${COMPOSE_ARGS[@]}" up --detach --no-build --wait api proxy gateway
REVIEW_VERIFY_MODEL_MODE=unconfigured "$release_dir/tools/ops/verify-deployment.sh"
rm -f -- "$REVIEW_MODEL_ENABLED_MARKER"
trap - EXIT INT TERM
printf 'external model composition disabled; configured model files were preserved\n'
