#!/usr/bin/env bash

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

BACKUP_RETENTION="${REVIEW_BACKUP_RETENTION:-14}"
ALPINE_IMAGE="${REVIEW_BACKUP_ALPINE_IMAGE:-alpine:3.22.2}"

require_root
require_command docker
require_command flock
require_command sha256sum
require_command tar
[[ "$BACKUP_RETENTION" =~ ^[1-9][0-9]*$ ]] || die "REVIEW_BACKUP_RETENTION must be a positive integer"

release_dir="$(realpath -e "${REVIEW_COMPOSE_RELEASE_DIR:-$REVIEW_CURRENT_LINK}")"
require_safe_release_dir "$release_dir"
commit="${REVIEW_BACKUP_RELEASE_COMMIT:-$(release_commit "$release_dir")}"
[[ "$commit" =~ ^[0-9a-f]{40}$ ]] || die "backup release commit is not a full Git SHA"
install -d -m 700 "$REVIEW_BACKUP_DIR"

if [[ "${REVIEW_RELEASE_LOCK_HELD:-0}" != 1 ]]; then
  exec 8>"${REVIEW_STATE_DIR}/.release.lock"
  flock -n 8 || die "another release or model operation is already running"
fi

exec 9>"$REVIEW_BACKUP_DIR/.backup.lock"
flock -n 9 || die "another backup is already running"

if [[ -f "$release_dir/deploy/compose/compose.production.yaml" ]]; then
  compose_active_args "$release_dir"
else
  compose_legacy_args "$release_dir"
fi
docker compose "${COMPOSE_ARGS[@]}" config --quiet

mapfile -t running_services < <(docker compose "${COMPOSE_ARGS[@]}" ps --services --filter status=running)
was_running() {
  local wanted="$1"
  local service
  for service in "${running_services[@]}"; do
    [[ "$service" == "$wanted" ]] && return 0
  done
  return 1
}

stopped_services=()
tmp_dir=""
resume_services() {
  if ((${#stopped_services[@]})); then
    docker compose "${COMPOSE_ARGS[@]}" start "${stopped_services[@]}" >/dev/null
  fi
}
cleanup_backup() {
  local status=$?
  set +e
  resume_services
  if [[ -n "$tmp_dir" ]]; then
    rm -rf -- "$tmp_dir"
  fi
  return "$status"
}
trap cleanup_backup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

for service in gateway proxy api; do
  if was_running "$service"; then
    stopped_services+=("$service")
    docker compose "${COMPOSE_ARGS[@]}" stop --timeout 30 "$service" >/dev/null
  fi
done

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
final_dir="$REVIEW_BACKUP_DIR/$timestamp"
tmp_dir="$(mktemp -d "$REVIEW_BACKUP_DIR/.${timestamp}.XXXXXX")"
chmod 700 "$tmp_dir"

docker compose "${COMPOSE_ARGS[@]}" exec -T postgres sh -ec \
  'pg_dump --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --format=custom' \
  > "$tmp_dir/database.dump"
docker compose "${COMPOSE_ARGS[@]}" exec -T postgres pg_restore --list \
  < "$tmp_dir/database.dump" >/dev/null

artifact_volume="${REVIEW_COMPOSE_PROJECT}_artifacts"
docker volume inspect "$artifact_volume" >/dev/null
docker run --rm --volume "$artifact_volume:/source:ro" "$ALPINE_IMAGE" \
  tar -C /source -czf - . > "$tmp_dir/artifacts.tar.gz"
tar -tzf "$tmp_dir/artifacts.tar.gz" >/dev/null

counts="$(docker compose "${COMPOSE_ARGS[@]}" exec -T postgres sh -ec \
  'psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --tuples-only --no-align --field-separator="|" --command="SELECT (SELECT count(*) FROM document_versions), (SELECT count(*) FROM review_reports), (SELECT count(*) FROM dialogue_turns), (SELECT count(*) FROM human_decisions);"' \
  | tr -d '[:space:]')"
IFS='|' read -r document_count report_count dialogue_count decision_count <<< "$counts"
for count in "$document_count" "$report_count" "$dialogue_count" "$decision_count"; do
  [[ "$count" =~ ^[0-9]+$ ]] || die "database count verification failed"
done
artifact_count="$(tar -tzf "$tmp_dir/artifacts.tar.gz" | awk '!/\/$/ {count++} END {print count+0}')"
artifact_record_count="$(docker compose "${COMPOSE_ARGS[@]}" exec -T postgres sh -ec \
  'psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --tuples-only --no-align --command="SELECT count(*) FROM artifacts;"' \
  | tr -d '[:space:]')"
[[ "$artifact_record_count" =~ ^[0-9]+$ ]] || die "artifact record count verification failed"

logical_sql="$(printf '%s\n' \
  "COPY (" \
  "SELECT 'document' AS kind, id AS object_id, concat_ws('|', artifact_id, sha256, size_bytes::text, extraction_state) AS payload FROM document_versions" \
  "UNION ALL SELECT 'report', id, concat_ws('|', artifact_id, canonical_sha256, etag, graph::text) FROM review_reports" \
  "UNION ALL SELECT 'dialogue', id, concat_ws('|', revision::text, value::text) FROM finding_dialogues" \
  "UNION ALL SELECT 'turn', id, concat_ws('|', dialogue_id, ordinal::text, state, value::text) FROM dialogue_turns" \
  "UNION ALL SELECT 'decision', finding_id || ':' || revision::text, value::text FROM human_decisions" \
  "ORDER BY kind, object_id" \
  ") TO STDOUT;")"
logical_sha="$(printf '%s' "$logical_sql" \
  | docker compose "${COMPOSE_ARGS[@]}" exec -T postgres sh -ec \
    'psql --quiet --username "$POSTGRES_USER" --dbname "$POSTGRES_DB"' \
  | sha256sum | awk '{print $1}')"

database_sha="$(sha256sum "$tmp_dir/database.dump" | awk '{print $1}')"
artifacts_sha="$(sha256sum "$tmp_dir/artifacts.tar.gz" | awk '{print $1}')"
{
  printf 'schema=review-backup.v1\n'
  printf 'created_at=%s\n' "$timestamp"
  printf 'release_commit=%s\n' "$commit"
  printf 'database_sha256=%s\n' "$database_sha"
  printf 'artifacts_sha256=%s\n' "$artifacts_sha"
  printf 'document_versions=%s\n' "$document_count"
  printf 'review_reports=%s\n' "$report_count"
  printf 'dialogue_turns=%s\n' "$dialogue_count"
  printf 'human_decisions=%s\n' "$decision_count"
  printf 'artifact_files=%s\n' "$artifact_count"
  printf 'artifact_records=%s\n' "$artifact_record_count"
  printf 'logical_sha256=%s\n' "$logical_sha"
} > "$tmp_dir/manifest.env"
chmod 600 "$tmp_dir"/*

[[ ! -e "$final_dir" ]] || die "backup already exists: $final_dir"
mv "$tmp_dir" "$final_dir"
tmp_dir=""
resume_services
stopped_services=()

mapfile -t backup_sets < <(find "$REVIEW_BACKUP_DIR" -mindepth 1 -maxdepth 1 -type d -name '20??????T??????Z' -print | sort)
while ((${#backup_sets[@]} > BACKUP_RETENTION)); do
  old="${backup_sets[0]}"
  [[ "$old" == "$REVIEW_BACKUP_DIR"/20??????T??????Z ]] || die "refusing to prune unexpected path: $old"
  rm -rf -- "$old"
  backup_sets=("${backup_sets[@]:1}")
done

printf '%s\n' "$final_dir"
