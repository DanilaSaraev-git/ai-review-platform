#!/usr/bin/env bash

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

require_root
require_command flock
exec 9>"${REVIEW_STATE_DIR}/.release.lock"
flock -n 9 || die "another release, backup, or model operation is already running"
check_private_file "$REVIEW_MODEL_ENV_FILE"
release_dir="$(realpath -e "$REVIEW_CURRENT_LINK")"
require_safe_release_dir "$release_dir"
profile_file="$(env_value REVIEW_MODEL_PROFILE_FILE "$REVIEW_MODEL_ENV_FILE")"
credential_file="$(env_value REVIEW_MODEL_CREDENTIAL_FILE "$REVIEW_MODEL_ENV_FILE")"
check_nonpublic_file "$profile_file"
check_nonpublic_file "$credential_file"

cleanup_marker_on_failure() {
  local status=$?
  if ((status != 0)); then
    rm -f -- "$REVIEW_MODEL_ENABLED_MARKER"
    compose_base_args "$release_dir"
    docker compose "${COMPOSE_ARGS[@]}" up --detach --no-build --wait api proxy gateway >/dev/null 2>&1 || true
  fi
  exit "$status"
}
trap cleanup_marker_on_failure EXIT INT TERM
umask 077
printf 'enabled\n' > "$REVIEW_MODEL_ENABLED_MARKER"
compose_model_args "$release_dir"
docker compose "${COMPOSE_ARGS[@]}" config --quiet
docker compose "${COMPOSE_ARGS[@]}" up --detach --no-build --wait api proxy gateway
docker compose "${COMPOSE_ARGS[@]}" run --rm --no-deps api review-cli model-probe
"$release_dir/tools/ops/verify-deployment.sh"
trap - EXIT INT TERM
printf 'external model composition enabled and its declared availability probe passed\n'
