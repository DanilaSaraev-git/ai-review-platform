#!/usr/bin/env bash

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

POSTGRES_IMAGE="${REVIEW_RESTORE_POSTGRES_IMAGE:-postgres:18.6}"
ALPINE_IMAGE="${REVIEW_BACKUP_ALPINE_IMAGE:-alpine:3.22.2}"

usage() {
  printf 'usage: %s /absolute/path/to/backup-set\n' "$0" >&2
  exit 2
}

[[ $# -eq 1 ]] || usage
require_root
require_command docker
require_command sha256sum
require_command tar

backup_dir="$(realpath -e "$1")"
backup_root="$(realpath -e "$REVIEW_BACKUP_DIR")"
[[ "$backup_dir" == "$backup_root"/* ]] || die "backup set is outside $backup_root"
for file in manifest.env database.dump artifacts.tar.gz; do
  [[ -f "$backup_dir/$file" ]] || die "backup set misses $file"
done

manifest_value() {
  env_value "$1" "$backup_dir/manifest.env"
}
[[ "$(manifest_value schema)" == review-backup.v1 ]] || die "unsupported backup manifest"
[[ "$(sha256sum "$backup_dir/database.dump" | awk '{print $1}')" == "$(manifest_value database_sha256)" ]] \
  || die "database checksum mismatch"
[[ "$(sha256sum "$backup_dir/artifacts.tar.gz" | awk '{print $1}')" == "$(manifest_value artifacts_sha256)" ]] \
  || die "artifact checksum mismatch"

suffix="$$-$(date +%s)"
container="review-restore-drill-$suffix"
volume="review-restore-drill-$suffix"
cleanup() {
  docker rm --force "$container" >/dev/null 2>&1 || true
  docker volume rm "$volume" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

docker volume create "$volume" >/dev/null
docker run --detach --rm --name "$container" \
  --env POSTGRES_HOST_AUTH_METHOD=trust "$POSTGRES_IMAGE" >/dev/null
for _ in $(seq 1 60); do
  if docker exec "$container" pg_isready --username postgres >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
docker exec "$container" pg_isready --username postgres >/dev/null 2>&1 || die "restore database did not become ready"
docker exec "$container" createdb --username postgres review_restore
docker exec -i "$container" pg_restore --username postgres --dbname review_restore \
  --no-owner --no-privileges < "$backup_dir/database.dump"

restored_counts="$(docker exec "$container" psql --username postgres --dbname review_restore \
  --tuples-only --no-align --field-separator='|' \
  --command='SELECT (SELECT count(*) FROM document_versions), (SELECT count(*) FROM review_reports), (SELECT count(*) FROM dialogue_turns), (SELECT count(*) FROM human_decisions);' \
  | tr -d '[:space:]')"
expected_counts="$(printf '%s|%s|%s|%s' \
  "$(manifest_value document_versions)" \
  "$(manifest_value review_reports)" \
  "$(manifest_value dialogue_turns)" \
  "$(manifest_value human_decisions)")"
[[ "$restored_counts" == "$expected_counts" ]] || die "restored database counts differ from the manifest"

logical_sql="$(printf '%s\n' \
  "COPY (" \
  "SELECT 'document' AS kind, id AS object_id, concat_ws('|', artifact_id, sha256, size_bytes::text, extraction_state) AS payload FROM document_versions" \
  "UNION ALL SELECT 'report', id, concat_ws('|', artifact_id, canonical_sha256, etag, graph::text) FROM review_reports" \
  "UNION ALL SELECT 'dialogue', id, concat_ws('|', revision::text, value::text) FROM finding_dialogues" \
  "UNION ALL SELECT 'turn', id, concat_ws('|', dialogue_id, ordinal::text, state, value::text) FROM dialogue_turns" \
  "UNION ALL SELECT 'decision', finding_id || ':' || revision::text, value::text FROM human_decisions" \
  "ORDER BY kind, object_id" \
  ") TO STDOUT;")"
restored_logical_sha="$(printf '%s' "$logical_sql" \
  | docker exec -i "$container" psql --quiet --username postgres --dbname review_restore \
  | sha256sum | awk '{print $1}')"
[[ "$restored_logical_sha" == "$(manifest_value logical_sha256)" ]] \
  || die "restored document/report/dialogue fingerprint differs from the manifest"

docker run --rm -i --volume "$volume:/restore" "$ALPINE_IMAGE" \
  tar -xzf - -C /restore < "$backup_dir/artifacts.tar.gz"
restored_artifacts="$(docker run --rm --volume "$volume:/restore:ro" "$ALPINE_IMAGE" \
  find /restore -type f | awk 'END {print NR+0}')"
[[ "$restored_artifacts" == "$(manifest_value artifact_files)" ]] || die "restored artifact count differs from the manifest"

artifact_rows="$(mktemp)"
trap 'rm -f -- "$artifact_rows"; cleanup' EXIT INT TERM
printf '%s' 'COPY (SELECT store_key, sha256, size_bytes FROM artifacts ORDER BY store_key) TO STDOUT;' \
  | docker exec -i "$container" psql --quiet --username postgres --dbname review_restore \
  > "$artifact_rows"
chmod 600 "$artifact_rows"
restored_artifact_records="$(wc -l < "$artifact_rows" | tr -d '[:space:]')"
[[ "$restored_artifact_records" == "$(manifest_value artifact_records)" ]] \
  || die "restored artifact record count differs from the manifest"
docker run --rm --volume "$volume:/restore:ro" --volume "$artifact_rows:/metadata:ro" "$ALPINE_IMAGE" \
  sh -ec '
    tab="$(printf "\t")"
    while IFS="$tab" read -r store_key expected_sha expected_size; do
      case "$store_key" in
        *..*|/*|*//*|*\\*) exit 20 ;;
      esac
      artifact="/restore/artifacts/objects/$store_key"
      test -f "$artifact"
      actual_sha="$(sha256sum "$artifact")"
      actual_sha="${actual_sha%% *}"
      actual_size="$(wc -c < "$artifact" | tr -d "[:space:]")"
      test "$actual_sha" = "$expected_sha"
      test "$actual_size" = "$expected_size"
    done < /metadata
  '

printf 'isolated restore drill: PASS\n'
printf 'database counts: %s\n' "$restored_counts"
printf 'artifact files: %s\n' "$restored_artifacts"
