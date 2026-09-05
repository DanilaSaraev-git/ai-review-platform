#!/usr/bin/env bash

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

usage() {
  printf 'usage: %s PROFILE_FILE CREDENTIAL_FILE\n' "$0" >&2
  exit 2
}

[[ $# -eq 2 ]] || usage
profile_source="$(realpath -e "$1")"
credential_source="$(realpath -e "$2")"

require_root
require_command docker
require_command flock
require_command install
install -d -m 700 "$REVIEW_STATE_DIR"
exec 9>"${REVIEW_STATE_DIR}/.release.lock"
flock -n 9 || die "another release, backup, or model operation is already running"
[[ ! -f "$REVIEW_MODEL_ENABLED_MARKER" ]] \
  || die "disable the external model before replacing its profile or credential"
check_private_file "$credential_source"
[[ -s "$credential_source" ]] || die "credential file is empty"
[[ "$(stat -c '%s' "$credential_source")" -le 16384 ]] || die "credential file is unexpectedly large"

app_image="${REVIEW_APP_IMAGE:-}"
if [[ -z "$app_image" && -L "$REVIEW_CURRENT_LINK" ]]; then
  current_release="$(realpath -e "$REVIEW_CURRENT_LINK")"
  if [[ -r "$current_release/release.env" ]]; then
    app_image="$(env_value REVIEW_APP_IMAGE "$current_release/release.env")"
  fi
fi
app_image="${app_image:-review-platform-mvp:local}"
profile_id="$(docker run --rm --user 0:0 \
  --volume "$profile_source:/run/review/model-profile.json:ro" \
  --entrypoint python "$app_image" -c '
import json
from pathlib import Path
from urllib.parse import urlsplit
from review_runtime.config.model_profiles import ModelProfile

value = json.loads(Path("/run/review/model-profile.json").read_text(encoding="utf-8"))
profile = ModelProfile.model_validate(value)
url = urlsplit(str(profile.chat_url)) if profile.chat_url is not None else None
if (
    profile.adapter_kind != "openai_compatible"
    or profile.secret_ref is None
    or url is None
    or url.scheme != "https"
):
    raise SystemExit("production model must use an exact HTTPS OpenAI-compatible endpoint")
if url.hostname is None or url.hostname.endswith(".invalid") or "synthetic" in profile.id.lower():
    raise SystemExit("example or synthetic model profiles cannot be enabled in production")
print(profile.id)
')"
runtime_gid="$(docker run --rm --entrypoint id "$app_image" -g review)"
[[ "$runtime_gid" =~ ^[0-9]+$ ]] || die "could not resolve the runtime review group"

secrets_dir="${REVIEW_SECRETS_DIR:-${REVIEW_STATE_DIR}/secrets}"
install -d -m 700 "$secrets_dir"
profile_target="${REVIEW_STATE_DIR}/model-profile.json"
credential_target="${secrets_dir}/model-api-key"
install -m 640 -o root -g "$runtime_gid" "$profile_source" "$profile_target"
install -m 640 -o root -g "$runtime_gid" "$credential_source" "$credential_target"

docker run --rm --user review \
  --volume "$profile_target:/run/review/model-profile.json:ro" \
  --volume "$credential_target:/run/secrets/model-api-key:ro" \
  --entrypoint sh "$app_image" -ec \
  'test -r /run/review/model-profile.json && test -r /run/secrets/model-api-key'

umask 077
{
  printf 'REVIEW_MODEL_PROFILE_FILE=%s\n' "$profile_target"
  printf 'REVIEW_MODEL_CREDENTIAL_FILE=%s\n' "$credential_target"
  printf 'REVIEW_MODEL_PROFILE_ID=%s\n' "$profile_id"
} > "$REVIEW_MODEL_ENV_FILE"
chmod 600 "$REVIEW_MODEL_ENV_FILE"

printf 'model files installed; no provider request was made\n'
printf 'model environment: %s\n' "$REVIEW_MODEL_ENV_FILE"
