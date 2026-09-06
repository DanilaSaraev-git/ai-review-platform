#!/usr/bin/env bash

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

require_root
if [[ ! -f "$REVIEW_MODEL_ENABLED_MARKER" ]]; then
  printf 'external model disabled; availability probe skipped\n'
  exit 0
fi

require_command flock
exec 9>"${REVIEW_STATE_DIR}/.release.lock"
if ! flock -n 9; then
  printf 'release, backup, or model operation active; availability probe skipped\n'
  exit 0
fi

check_private_file "$REVIEW_MODEL_ENV_FILE"
release_dir="$(realpath -e "$REVIEW_CURRENT_LINK")"
require_production_release "$release_dir"
profile_file="$(env_value REVIEW_MODEL_PROFILE_FILE "$REVIEW_MODEL_ENV_FILE")"
credential_file="$(env_value REVIEW_MODEL_CREDENTIAL_FILE "$REVIEW_MODEL_ENV_FILE")"
check_nonpublic_file "$profile_file"
check_nonpublic_file "$credential_file"

compose_model_args "$release_dir"
docker compose "${COMPOSE_ARGS[@]}" run --rm --no-deps api review-cli model-probe
