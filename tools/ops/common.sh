#!/usr/bin/env bash

set -Eeuo pipefail

REVIEW_COMPOSE_PROJECT="${REVIEW_COMPOSE_PROJECT:-review-platform-mvp}"
REVIEW_CURRENT_LINK="${REVIEW_CURRENT_LINK:-/opt/ai-review-platform-current}"
REVIEW_PREVIOUS_LINK="${REVIEW_PREVIOUS_LINK:-/opt/ai-review-platform-previous}"
REVIEW_RELEASES_DIR="${REVIEW_RELEASES_DIR:-/opt/ai-review-releases}"
REVIEW_STATE_DIR="${REVIEW_STATE_DIR:-/opt/ai-review-state}"
REVIEW_ENV_FILE="${REVIEW_ENV_FILE:-${REVIEW_STATE_DIR}/review.env}"
REVIEW_LEGACY_ENV_FILE="${REVIEW_LEGACY_ENV_FILE:-${REVIEW_STATE_DIR}/legacy.env}"
REVIEW_MODEL_ENV_FILE="${REVIEW_MODEL_ENV_FILE:-${REVIEW_STATE_DIR}/model.env}"
REVIEW_MODEL_ENABLED_MARKER="${REVIEW_MODEL_ENABLED_MARKER:-${REVIEW_STATE_DIR}/model-enabled}"
REVIEW_BACKUP_DIR="${REVIEW_BACKUP_DIR:-/opt/ai-review-backups}"

die() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "required command is missing: $1"
}

require_root() {
  [[ "${EUID}" -eq 0 ]] || die "run this command as root"
}

require_absolute_path() {
  local path="$1"
  local label="$2"
  [[ "$path" == /* ]] || die "$label must be an absolute path"
}

require_safe_release_dir() {
  local release_dir="$1"
  local resolved_release
  local resolved_root
  require_absolute_path "$release_dir" "release directory"
  resolved_release="$(realpath -e "$release_dir")"
  resolved_root="$(realpath -e "$REVIEW_RELEASES_DIR")"
  [[ "$resolved_release" == "$resolved_root"/* ]] || die "release is outside $resolved_root"
  [[ -f "$resolved_release/deploy/compose/compose.yaml" ]] || die "release has no base Compose file"
}

require_production_release() {
  local release_dir="$1"
  require_safe_release_dir "$release_dir"
  [[ -f "$release_dir/deploy/compose/compose.production.yaml" ]] || die "release has no production Compose file"
}

release_commit() {
  local release_dir="$1"
  local commit_file="$release_dir/RELEASE_COMMIT"
  [[ -r "$commit_file" ]] || die "release has no readable RELEASE_COMMIT"
  local commit
  commit="$(tr -d '\r\n' < "$commit_file")"
  [[ "$commit" =~ ^[0-9a-f]{40}$ ]] || die "RELEASE_COMMIT is not a full Git SHA"
  printf '%s\n' "$commit"
}

env_value() {
  local key="$1"
  local file="${2:-$REVIEW_ENV_FILE}"
  [[ -r "$file" ]] || die "environment file is not readable: $file"
  awk -F= -v wanted="$key" '$1 == wanted {sub(/^[^=]*=/, ""); print; found=1} END {if (!found) exit 1}' "$file"
}

compose_base_args() {
  local release_dir="$1"
  require_production_release "$release_dir"
  COMPOSE_ARGS=(
    --project-name "$REVIEW_COMPOSE_PROJECT"
    --env-file "$REVIEW_ENV_FILE"
  )
  if [[ -r "$release_dir/release.env" ]]; then
    COMPOSE_ARGS+=(--env-file "$release_dir/release.env")
  fi
  COMPOSE_ARGS+=(
    -f "$release_dir/deploy/compose/compose.yaml"
    -f "$release_dir/deploy/compose/compose.production.yaml"
  )
}

compose_legacy_args() {
  local release_dir="$1"
  require_safe_release_dir "$release_dir"
  check_private_file "$REVIEW_LEGACY_ENV_FILE"
  COMPOSE_ARGS=(
    --project-name "$REVIEW_COMPOSE_PROJECT"
    --env-file "$REVIEW_ENV_FILE"
    --env-file "$REVIEW_LEGACY_ENV_FILE"
    -f "$release_dir/deploy/compose/compose.yaml"
  )
}

compose_model_args() {
  local release_dir="$1"
  compose_base_args "$release_dir"
  COMPOSE_ARGS+=(
    --env-file "$REVIEW_MODEL_ENV_FILE"
    -f "$release_dir/deploy/compose/compose.external-model.yaml"
  )
}

compose_active_args() {
  local release_dir="$1"
  if [[ -f "$REVIEW_MODEL_ENABLED_MARKER" ]]; then
    check_private_file "$REVIEW_MODEL_ENV_FILE"
    compose_model_args "$release_dir"
  else
    compose_base_args "$release_dir"
  fi
}

check_private_file() {
  local path="$1"
  [[ -f "$path" && -r "$path" ]] || die "required private file is missing: $path"
  local mode
  mode="$(stat -c '%a' "$path")"
  (( (8#$mode & 077) == 0 )) || die "private file must not be accessible by group or others: $path"
}

check_nonpublic_file() {
  local path="$1"
  [[ -f "$path" && -r "$path" ]] || die "required protected file is missing: $path"
  local mode
  mode="$(stat -c '%a' "$path")"
  (( (8#$mode & 007) == 0 )) || die "protected file must not be accessible by others: $path"
}
