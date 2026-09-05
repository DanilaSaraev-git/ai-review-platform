#!/usr/bin/env bash

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

allow_missing=0
if [[ "${1:-}" == --allow-missing ]]; then
  allow_missing=1
  shift
fi
[[ $# -eq 0 ]] || die "usage: $0 [--allow-missing]"

require_root
release_dir="${REVIEW_COMPOSE_RELEASE_DIR:-$(realpath -e "$REVIEW_CURRENT_LINK")}"
require_safe_release_dir "$release_dir"

label_env_file="${REVIEW_LABEL_ENV_FILE:-$REVIEW_ENV_FILE}"
organization_id="$(env_value REVIEW_ORGANIZATION_ID "$label_env_file")"
organization_name="$(env_value REVIEW_ORGANIZATION_NAME "$label_env_file")"
workspace_id="$(env_value REVIEW_WORKSPACE_ID "$label_env_file")"
workspace_name="$(env_value REVIEW_WORKSPACE_NAME "$label_env_file")"
actor_id="$(env_value REVIEW_ACTOR_ID "$label_env_file")"
actor_name="$(env_value REVIEW_ACTOR_DISPLAY_NAME "$label_env_file")"

compose_base_args "$release_dir"
updated="$(docker compose "${COMPOSE_ARGS[@]}" exec -T postgres sh -ec '
  psql --set=ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --tuples-only --no-align \
    --set=organization_id="$1" --set=organization_name="$2" \
    --set=workspace_id="$3" --set=workspace_name="$4" \
    --set=actor_id="$5" --set=actor_name="$6" <<"SQL"
BEGIN;
SELECT concat_ws('"'"'|'"'"',
  (SELECT count(*) FROM organizations WHERE id = :'"'"'organization_id'"'"'),
  (SELECT count(*) FROM workspaces WHERE organization_id = :'"'"'organization_id'"'"' AND id = :'"'"'workspace_id'"'"'),
  (SELECT count(*) FROM actors WHERE organization_id = :'"'"'organization_id'"'"' AND workspace_id = :'"'"'workspace_id'"'"' AND id = :'"'"'actor_id'"'"')
) IN ('"'"'0|0|0'"'"', '"'"'1|1|1'"'"') AS seed_shape_valid \gset
\if :seed_shape_valid
\else
  \echo inconsistent deployment identity shape
  ROLLBACK;
  \quit
\endif
UPDATE organizations
SET name = :'"'"'organization_name'"'"'
WHERE id = :'"'"'organization_id'"'"';
UPDATE workspaces
SET name = :'"'"'workspace_name'"'"'
WHERE organization_id = :'"'"'organization_id'"'"'
  AND id = :'"'"'workspace_id'"'"';
UPDATE actors
SET display_name = :'"'"'actor_name'"'"'
WHERE organization_id = :'"'"'organization_id'"'"'
  AND workspace_id = :'"'"'workspace_id'"'"'
  AND id = :'"'"'actor_id'"'"';
SELECT concat_ws('"'"'|'"'"',
  (SELECT count(*) FROM organizations WHERE id = :'"'"'organization_id'"'"' AND name = :'"'"'organization_name'"'"'),
  (SELECT count(*) FROM workspaces WHERE organization_id = :'"'"'organization_id'"'"' AND id = :'"'"'workspace_id'"'"' AND name = :'"'"'workspace_name'"'"'),
  (SELECT count(*) FROM actors WHERE organization_id = :'"'"'organization_id'"'"' AND workspace_id = :'"'"'workspace_id'"'"' AND id = :'"'"'actor_id'"'"' AND display_name = :'"'"'actor_name'"'"')
);
COMMIT;
SQL
' sh "$organization_id" "$organization_name" "$workspace_id" "$workspace_name" "$actor_id" "$actor_name" \
  | awk -F'|' '/^[0-9]+\|[0-9]+\|[0-9]+$/ {value=$0} END {if (value) print value}')"
if [[ "$allow_missing" == 1 && "$updated" == "0|0|0" ]]; then
  printf 'deployment identity is not seeded yet; label update deferred\n'
  exit 0
fi
[[ "$updated" == "1|1|1" ]] \
  || die "deployment label update did not match exactly one organization, workspace, and actor"
printf 'deployment display labels updated without changing IDs\n'
