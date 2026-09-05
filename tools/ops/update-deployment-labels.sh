#!/usr/bin/env bash

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

require_root
release_dir="${REVIEW_COMPOSE_RELEASE_DIR:-$(realpath -e "$REVIEW_CURRENT_LINK")}"
require_safe_release_dir "$release_dir"

organization_id="$(env_value REVIEW_ORGANIZATION_ID)"
organization_name="$(env_value REVIEW_ORGANIZATION_NAME)"
workspace_id="$(env_value REVIEW_WORKSPACE_ID)"
workspace_name="$(env_value REVIEW_WORKSPACE_NAME)"
actor_id="$(env_value REVIEW_ACTOR_ID)"
actor_name="$(env_value REVIEW_ACTOR_DISPLAY_NAME)"

compose_base_args "$release_dir"
updated="$(docker compose "${COMPOSE_ARGS[@]}" exec -T postgres sh -ec '
  psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --tuples-only --no-align \
    --set=organization_id="$1" --set=organization_name="$2" \
    --set=workspace_id="$3" --set=workspace_name="$4" \
    --set=actor_id="$5" --set=actor_name="$6" <<"SQL"
BEGIN;
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
  | awk -F'|' '/^[0-9]+\|[0-9]+\|[0-9]+$/ {print; exit}')"
[[ "$updated" == "1|1|1" ]] || die "deployment label update did not match exactly one organization, workspace, and actor"
printf 'deployment display labels updated without changing IDs\n'
