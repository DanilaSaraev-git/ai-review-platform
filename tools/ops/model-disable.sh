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

rm -f -- "$REVIEW_MODEL_ENABLED_MARKER"
compose_base_args "$release_dir"
docker compose "${COMPOSE_ARGS[@]}" config --quiet
docker compose "${COMPOSE_ARGS[@]}" up --detach --no-build --wait api proxy gateway
"$release_dir/tools/ops/verify-deployment.sh"
printf 'external model composition disabled; configured model files were preserved\n'
