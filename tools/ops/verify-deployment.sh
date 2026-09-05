#!/usr/bin/env bash

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

require_root
require_command curl
require_command openssl
require_command python3

public_ip="${REVIEW_PUBLIC_IP:-$(env_value REVIEW_PUBLIC_IP)}"
credentials_file="${REVIEW_GATEWAY_CREDENTIALS_FILE:-$(env_value REVIEW_GATEWAY_CREDENTIALS_FILE)}"
tls_dir="${REVIEW_TLS_DIR:-$(env_value REVIEW_TLS_DIR)}"
check_private_file "$credentials_file"

username="$(awk -F= '$1 == "username" {sub(/^[^=]*=/, ""); print}' "$credentials_file")"
password="$(awk -F= '$1 == "password" {sub(/^[^=]*=/, ""); print}' "$credentials_file")"
[[ -n "$username" && -n "$password" ]] || die "gateway credentials file is incomplete"

curl_config="$(mktemp)"
cleanup() { rm -f -- "$curl_config"; }
trap cleanup EXIT INT TERM
chmod 600 "$curl_config"
printf 'user = "%s:%s"\n' "$username" "$password" > "$curl_config"

redirect_status="$(curl --silent --output /dev/null --write-out '%{http_code}' "http://$public_ip/")"
[[ "$redirect_status" == 308 ]] || die "plaintext endpoint did not redirect (status $redirect_status)"

unauthorized_status="$(curl --silent --output /dev/null --write-out '%{http_code}' "https://$public_ip/")"
[[ "$unauthorized_status" == 401 ]] || die "gateway did not reject unauthenticated access (status $unauthorized_status)"

authorized_status="$(curl --silent --output /dev/null --write-out '%{http_code}' --config "$curl_config" "https://$public_ip/")"
[[ "$authorized_status" == 200 ]] || die "gateway did not accept operator credentials (status $authorized_status)"

cross_origin_status="$(curl --silent --output /dev/null --write-out '%{http_code}' --config "$curl_config" \
  --request POST --header 'Origin: https://cross-origin.invalid' "https://$public_ip/api/v1/review-runs")"
[[ "$cross_origin_status" == 403 ]] || die "cross-origin mutation was not rejected (status $cross_origin_status)"

bootstrap_file="$(mktemp)"
profiles_file="$(mktemp)"
trap 'rm -f -- "$curl_config" "$bootstrap_file" "$profiles_file"' EXIT INT TERM
chmod 600 "$bootstrap_file" "$profiles_file"
curl --silent --show-error --fail --config "$curl_config" "https://$public_ip/api/v1/bootstrap" > "$bootstrap_file"
workspace_id="$(python3 - "$bootstrap_file" <<'PY'
import json
import sys
from pathlib import Path

value = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print(value["workspace"]["id"])
PY
)"
curl --silent --show-error --fail --config "$curl_config" \
  "https://$public_ip/api/v1/workspaces/$workspace_id/model-profiles" > "$profiles_file"
if [[ -f "$REVIEW_MODEL_ENABLED_MARKER" ]]; then
  expected_model_id="$(env_value REVIEW_MODEL_PROFILE_ID "$REVIEW_MODEL_ENV_FILE")"
else
  expected_model_id="$(env_value REVIEW_MODEL_PROFILE_ID)"
fi
python3 - "$profiles_file" "$expected_model_id" "$REVIEW_MODEL_ENABLED_MARKER" <<'PY'
import json
import sys
from pathlib import Path

value = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
profiles = value.get("items", [])
expected_id = sys.argv[2]
model_enabled = Path(sys.argv[3]).is_file()
selected = [profile for profile in profiles if profile.get("id") == expected_id]
if len(selected) != 1:
    raise SystemExit(f"expected exactly one model profile {expected_id!r}")
if model_enabled:
    if selected[0].get("availability") != "available":
        raise SystemExit("enabled production model profile is not available")
elif any(profile.get("availability") != "unavailable" for profile in profiles):
    raise SystemExit("unconfigured production model profiles do not report unavailable")
PY

openssl x509 -in "$tls_dir/live/$public_ip/fullchain.pem" -noout -checkend 86400 >/dev/null \
  || die "certificate expires in less than 24 hours"

if ss -lnt | awk 'NR > 1 {print $4}' | grep -Eq '(^|:)(5432|8000)$'; then
  die "database or API listens on a host port"
fi

printf 'gateway, TLS, origin policy, private services, and model mode: PASS\n'
