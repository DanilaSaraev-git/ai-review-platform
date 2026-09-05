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

umask 077
{
  printf 'REVIEW_APP_IMAGE=review-platform-mvp:%s\n' "$commit"
  printf 'REVIEW_WEB_IMAGE=review-platform-web:%s\n' "$commit"
} > "$release_dir/release.env"
chmod 600 "$release_dir/release.env"

old_release=""
old_commit=""
if [[ -L "$REVIEW_CURRENT_LINK" ]]; then
  old_release="$(realpath -e "$REVIEW_CURRENT_LINK")"
  old_commit="$(release_commit "$old_release")"
fi

if [[ -n "$old_commit" ]]; then
  REVIEW_RELEASE_LOCK_HELD=1 REVIEW_COMPOSE_RELEASE_DIR="$release_dir" REVIEW_BACKUP_RELEASE_COMMIT="$old_commit" \
    "$release_dir/tools/ops/backup.sh" >/dev/null
fi

compose_active_args "$release_dir"
docker compose "${COMPOSE_ARGS[@]}" config --quiet
docker compose "${COMPOSE_ARGS[@]}" build api
docker compose "${COMPOSE_ARGS[@]}" build proxy

rollback_on_failure() {
  local status=$?
  if ((status != 0)) && [[ -n "$old_release" ]]; then
    if [[ -f "$old_release/deploy/compose/compose.production.yaml" ]]; then
      compose_active_args "$old_release"
      docker compose "${COMPOSE_ARGS[@]}" up --detach --no-build --remove-orphans postgres api proxy gateway >/dev/null 2>&1 || true
    else
      compose_legacy_args "$old_release"
      docker compose "${COMPOSE_ARGS[@]}" up --detach --no-build --remove-orphans postgres api proxy >/dev/null 2>&1 || true
    fi
  fi
  exit "$status"
}
trap rollback_on_failure EXIT INT TERM

docker compose "${COMPOSE_ARGS[@]}" stop --timeout 30 gateway proxy api >/dev/null 2>&1 || true
docker compose "${COMPOSE_ARGS[@]}" run --rm migrate
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
