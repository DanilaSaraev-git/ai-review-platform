#!/usr/bin/env bash

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

usage() {
  printf 'usage: %s /opt/ai-review-releases/FULL_GIT_SHA\n' "$0" >&2
  exit 2
}

[[ $# -eq 1 ]] || usage
require_root
require_command curl
require_command docker
require_command flock
release_dir="$(realpath -e "$1")"
require_production_release "$release_dir"
commit="$(release_commit "$release_dir")"
check_private_file "$REVIEW_ENV_FILE"

exec 9>"${REVIEW_STATE_DIR}/.release.lock"
flock -n 9 || die "another release operation is already running"

old_release=""
old_commit=""
if [[ -L "$REVIEW_CURRENT_LINK" ]]; then
  old_release="$(realpath -e "$REVIEW_CURRENT_LINK")"
  old_commit="$(release_commit "$old_release")"
fi
if [[ -n "${REVIEW_EXPECTED_CURRENT_COMMIT:-}" ]]; then
  [[ "$REVIEW_EXPECTED_CURRENT_COMMIT" =~ ^[0-9a-f]{40}$ ]] \
    || die "REVIEW_EXPECTED_CURRENT_COMMIT must be a full Git SHA"
  [[ "$old_commit" == "$REVIEW_EXPECTED_CURRENT_COMMIT" ]] \
    || die "current release changed; inspect it before retrying promotion"
fi

umask 077
{
  printf 'REVIEW_APP_IMAGE=review-platform-mvp:%s\n' "$commit"
  printf 'REVIEW_WEB_IMAGE=review-platform-web:%s\n' "$commit"
} > "$release_dir/release.env"
chmod 600 "$release_dir/release.env"

if [[ -n "$old_commit" ]]; then
  REVIEW_RELEASE_LOCK_HELD=1 REVIEW_COMPOSE_RELEASE_DIR="$release_dir" REVIEW_BACKUP_RELEASE_COMMIT="$old_commit" \
    "$release_dir/tools/ops/backup.sh" >/dev/null
fi

compose_active_args "$release_dir"
docker compose "${COMPOSE_ARGS[@]}" config --quiet
docker compose "${COMPOSE_ARGS[@]}" build api
docker compose "${COMPOSE_ARGS[@]}" build proxy

migration_started=0
guest_schema_transition=0
guest_migration=packages/review-runtime/migrations/versions/20260906_0003_guest_sessions.py
if [[ -f "$release_dir/$guest_migration" && ! -f "$old_release/$guest_migration" ]]; then
  guest_schema_transition=1
fi
rollback_on_failure() {
  local status=$?
  if ((status != 0 && migration_started == 1 && guest_schema_transition == 1)); then
    # The migration may already have committed even when the command failed.
    # Older code requires schema 0002 and cannot safely serve the upgraded DB.
    docker compose "${COMPOSE_ARGS[@]}" stop --timeout 30 gateway >/dev/null 2>&1 || true
    printf '%s\n' 'promotion failed after guest migration started; old code was not restarted and gateway is stopped' >&2
    printf 'repair and re-promote %s; for trusted access use that same release with REVIEW_GUEST_ACCESS=false after migration succeeds; do not downgrade the database\n' \
      "$release_dir" >&2
    exit "$status"
  fi
  if ((status != 0)) && [[ -n "$old_release" ]]; then
    if [[ -f "$old_release/deploy/compose/compose.production.yaml" ]]; then
      compose_active_args "$old_release"
      docker compose "${COMPOSE_ARGS[@]}" up --detach --no-build --remove-orphans postgres api proxy gateway >/dev/null 2>&1 || true
    else
      REVIEW_COMPOSE_RELEASE_DIR="$release_dir" REVIEW_LABEL_ENV_FILE="$REVIEW_LEGACY_ENV_FILE" \
        "$release_dir/tools/ops/update-deployment-labels.sh" >/dev/null 2>&1 || true
      compose_legacy_args "$old_release"
      docker compose "${COMPOSE_ARGS[@]}" up --detach --no-build --remove-orphans postgres api proxy >/dev/null 2>&1 || true
    fi
  fi
  exit "$status"
}
trap rollback_on_failure EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

docker compose "${COMPOSE_ARGS[@]}" stop --timeout 30 gateway proxy api >/dev/null 2>&1 || true
migration_started=1
docker compose "${COMPOSE_ARGS[@]}" run --rm migrate
REVIEW_COMPOSE_RELEASE_DIR="$release_dir" "$release_dir/tools/ops/update-deployment-labels.sh" --allow-missing
docker compose "${COMPOSE_ARGS[@]}" up --detach --no-build --wait postgres api
REVIEW_COMPOSE_RELEASE_DIR="$release_dir" "$release_dir/tools/ops/update-deployment-labels.sh"
docker compose "${COMPOSE_ARGS[@]}" up --detach --no-build --wait --remove-orphans postgres api proxy gateway
"$release_dir/tools/ops/verify-deployment.sh"

if [[ -n "$old_release" ]]; then
  previous_tmp="${REVIEW_PREVIOUS_LINK}.new-$$"
  ln -s "$old_release" "$previous_tmp"
  mv -Tf "$previous_tmp" "$REVIEW_PREVIOUS_LINK"
fi
current_tmp="${REVIEW_CURRENT_LINK}.new-$$"
ln -s "$release_dir" "$current_tmp"
mv -Tf "$current_tmp" "$REVIEW_CURRENT_LINK"

trap - EXIT INT TERM
printf 'promoted release %s\n' "$commit"
