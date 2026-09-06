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
guest_access="${REVIEW_GUEST_ACCESS:-$(env_value REVIEW_GUEST_ACCESS 2>/dev/null || printf false)}"
[[ "$guest_access" == true || "$guest_access" == false ]] \
  || die "REVIEW_GUEST_ACCESS must be true or false"
check_private_file "$credentials_file"

username="$(awk -F= '$1 == "username" {sub(/^[^=]*=/, ""); print}' "$credentials_file")"
password="$(awk -F= '$1 == "password" {sub(/^[^=]*=/, ""); print}' "$credentials_file")"
[[ -n "$username" && -n "$password" ]] || die "gateway credentials file is incomplete"

curl_config="$(mktemp)"
probe_dir="$(mktemp -d)"
cleanup() { rm -f -- "$curl_config"; rm -rf -- "$probe_dir"; }
trap cleanup EXIT INT TERM
chmod 600 "$curl_config"
printf 'user = "%s:%s"\n' "$username" "$password" > "$curl_config"

redirect_status="$(curl --silent --output /dev/null --write-out '%{http_code}' "http://$public_ip/")"
[[ "$redirect_status" == 308 ]] || die "plaintext endpoint did not redirect (status $redirect_status)"

protected_paths=(/demo /demo/ /demo/new /demo/data/demo.json /demo/data/document.pdf /demo/api/v1/bootstrap)
if [[ "$guest_access" == false ]]; then
  protected_paths+=(/ /api/v1/bootstrap /v1/bootstrap /docs /docs/ /openapi.json /api/openapi.json /health/ready)
fi
for protected_path in "${protected_paths[@]}"; do
  unauthorized_status="$(curl --silent --output /dev/null --write-out '%{http_code}' \
    "https://$public_ip$protected_path")"
  [[ "$unauthorized_status" == 401 ]] \
    || die "gateway did not reject unauthenticated access to $protected_path (status $unauthorized_status)"
done

authorized_status="$(curl --silent --output /dev/null --write-out '%{http_code}' --config "$curl_config" "https://$public_ip/")"
[[ "$authorized_status" == 200 ]] || die "gateway did not accept operator credentials (status $authorized_status)"

cross_origin_status="$(curl --silent --output /dev/null --write-out '%{http_code}' \
  --request POST --header 'Origin: https://cross-origin.invalid' "https://$public_ip/api/v1/review-runs")"
[[ "$cross_origin_status" == 403 ]] || die "cross-origin mutation was not rejected (status $cross_origin_status)"

bootstrap_file="$probe_dir/bootstrap.json"
profiles_file="$probe_dir/profiles.json"
documents_file="$probe_dir/documents.json"
openapi_file="$probe_dir/openapi.json"
docs_file="$probe_dir/docs.html"
docs_headers="$probe_dir/docs.headers"
cookie_jar="$probe_dir/guest.cookies"
request_auth=(--config "$curl_config")
if [[ "$guest_access" == true ]]; then
  request_auth=(--cookie "$cookie_jar" --cookie-jar "$cookie_jar")
  public_status="$(curl --silent --output /dev/null --write-out '%{http_code}' "https://$public_ip/")"
  [[ "$public_status" == 200 ]] || die "guest UI did not open without credentials (status $public_status)"
fi
curl --silent --show-error --fail "${request_auth[@]}" --dump-header "$probe_dir/bootstrap.headers" \
  "https://$public_ip/api/v1/bootstrap" > "$bootstrap_file"
workspace_id="$(python3 - "$bootstrap_file" <<'PY'
import json
import sys
from pathlib import Path

value = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print(value["workspace"]["id"])
PY
)"
if [[ "$guest_access" == true ]]; then
  python3 - "$probe_dir/bootstrap.headers" <<'PY'
import sys
from http.cookies import SimpleCookie
from pathlib import Path

cookies = SimpleCookie()
for line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    if line.lower().startswith("set-cookie:"):
        cookies.load(line.partition(":")[2].strip())
session = cookies.get("review_guest")
if not session or not session["secure"] or not session["httponly"]:
    raise SystemExit("guest bootstrap did not set a Secure HttpOnly cookie")
if session["samesite"].lower() != "lax" or session["path"] != "/" or session["max-age"] != "2592000":
    raise SystemExit("guest cookie must use SameSite=Lax, Path=/, and a 30-day lifetime")
PY
  curl --silent --show-error --fail "${request_auth[@]}" \
    "https://$public_ip/v1/bootstrap" > "$probe_dir/returning.json"
  curl --silent --show-error --fail --cookie-jar "$probe_dir/other.cookies" \
    "https://$public_ip/v1/bootstrap" > "$probe_dir/other.json"
  python3 - "$bootstrap_file" "$probe_dir/returning.json" "$probe_dir/other.json" <<'PY'
import json
import sys
from pathlib import Path

first, returning, other = [json.loads(Path(path).read_text(encoding="utf-8")) for path in sys.argv[1:]]
if first["workspace"]["id"] != returning["workspace"]["id"] or first["actor"]["id"] != returning["actor"]["id"]:
    raise SystemExit("guest cookie did not preserve browser identity")
if first["workspace"]["id"] == other["workspace"]["id"] or first["actor"]["id"] == other["actor"]["id"]:
    raise SystemExit("independent guests share an identity")
PY
  for api_prefix in /api/v1 /v1; do
    guest_path="$api_prefix/workspaces/$workspace_id/documents"
    no_cookie_status="$(curl --silent --output /dev/null --write-out '%{http_code}' "https://$public_ip$guest_path")"
    [[ "$no_cookie_status" == 401 ]] || die "guest API accepted a request without a cookie ($no_cookie_status)"
    other_status="$(curl --silent --output /dev/null --write-out '%{http_code}' \
      --cookie "$probe_dir/other.cookies" "https://$public_ip$guest_path")"
    [[ "$other_status" == 404 ]] || die "another guest workspace was exposed ($other_status)"
    trusted_status="$(curl --silent --output /dev/null --write-out '%{http_code}' \
      "${request_auth[@]}" "https://$public_ip$api_prefix/workspaces/$(env_value REVIEW_WORKSPACE_ID)/documents")"
    [[ "$trusted_status" == 404 ]] || die "guest cookie exposed the trusted workspace ($trusted_status)"
  done
  demo_status="$(curl --silent --output /dev/null --write-out '%{http_code}' \
    "${request_auth[@]}" "https://$public_ip/demo/data/demo.json")"
  [[ "$demo_status" == 401 ]] || die "guest cookie bypassed demo Basic auth ($demo_status)"
fi
curl --silent --show-error --fail "${request_auth[@]}" \
  "https://$public_ip/api/v1/workspaces/$workspace_id/documents?limit=1" > "$documents_file"
document_id="$(python3 - "$documents_file" <<'PY'
import json
import sys
from pathlib import Path

items = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")).get("items", [])
print(items[0]["id"] if items else "")
PY
)"
if [[ -n "$document_id" ]]; then
  document_status="$(curl --silent --output /dev/null --write-out '%{http_code}' \
    "https://$public_ip/v1/workspaces/$workspace_id/documents/$document_id/content")"
  [[ "$document_status" == 401 ]] \
    || die "gateway exposed document content without credentials (status $document_status)"
fi

curl --silent --show-error --fail "${request_auth[@]}" "https://$public_ip/openapi.json" > "$openapi_file"
docs_redirect_status="$(curl --silent --output /dev/null --dump-header "$docs_headers" --write-out '%{http_code}' \
  "${request_auth[@]}" "https://$public_ip/docs")"
[[ "$docs_redirect_status" == 307 ]] || die "canonical docs URL did not redirect to its directory"
docs_location="$(awk 'BEGIN {IGNORECASE=1} /^location:/ {sub(/\r$/, ""); sub(/^[^:]*:[[:space:]]*/, ""); print; exit}' "$docs_headers")"
[[ "$docs_location" == "https://$public_ip/docs/" ]] \
  || die "canonical docs redirect exposed an internal or plaintext address"
curl --silent --show-error --fail "${request_auth[@]}" "https://$public_ip/docs/" > "$docs_file"
python3 - "$openapi_file" "$docs_file" <<'PY'
import json
import sys
from pathlib import Path

schema = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if not str(schema.get("openapi", "")).startswith("3.") or "/v1/bootstrap" not in schema.get("paths", {}):
    raise SystemExit("gateway OpenAPI document is not the canonical v1 schema")
docs = Path(sys.argv[2]).read_text(encoding="utf-8")
if "<!doctype html" not in docs.lower():
    raise SystemExit("gateway docs route did not return the offline HTML application")
PY

curl --silent --show-error --fail "${request_auth[@]}" \
  "https://$public_ip/api/v1/workspaces/$workspace_id/model-profiles" > "$profiles_file"
model_mode="${REVIEW_VERIFY_MODEL_MODE:-}"
if [[ -z "$model_mode" ]]; then
  if [[ -f "$REVIEW_MODEL_ENABLED_MARKER" ]]; then
    model_mode=enabled
  else
    model_mode=unconfigured
  fi
fi
[[ "$model_mode" == enabled || "$model_mode" == unconfigured ]] \
  || die "REVIEW_VERIFY_MODEL_MODE must be enabled or unconfigured"
if [[ "$model_mode" == enabled ]]; then
  expected_model_id="$(env_value REVIEW_MODEL_PROFILE_ID "$REVIEW_MODEL_ENV_FILE")"
else
  expected_model_id="$(env_value REVIEW_MODEL_PROFILE_ID)"
fi
python3 - "$profiles_file" "$expected_model_id" "$model_mode" <<'PY'
import json
import sys
from pathlib import Path

value = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
profiles = value.get("items", [])
expected_id = sys.argv[2]
model_enabled = sys.argv[3] == "enabled"
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

printf 'gateway, TLS, origin policy, private services, and model mode (guest=%s): PASS\n' "$guest_access"
