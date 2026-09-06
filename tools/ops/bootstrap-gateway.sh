#!/usr/bin/env bash

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

CERTBOT_IMAGE="${CERTBOT_IMAGE:-certbot/certbot:v5.8.0}"
BOOTSTRAP_NGINX_IMAGE="${BOOTSTRAP_NGINX_IMAGE:-nginx:1.29.4-alpine}"
GATEWAY_USERNAME="${REVIEW_GATEWAY_USERNAME:-review}"

require_root
require_command docker
require_command curl
require_command openssl
require_command install

public_ip="${REVIEW_PUBLIC_IP:-$(env_value REVIEW_PUBLIC_IP)}"
[[ "$public_ip" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]] || die "set REVIEW_PUBLIC_IP to the public IPv4 address"
[[ "$GATEWAY_USERNAME" =~ ^[A-Za-z0-9._-]{1,64}$ ]] || die "gateway username contains unsupported characters"

tls_dir="${REVIEW_TLS_DIR:-${REVIEW_STATE_DIR}/letsencrypt}"
certbot_lib="${REVIEW_CERTBOT_LIB_DIR:-${REVIEW_STATE_DIR}/certbot-lib}"
acme_webroot="${REVIEW_ACME_WEBROOT:-${REVIEW_STATE_DIR}/acme-webroot}"
secrets_dir="${REVIEW_SECRETS_DIR:-${REVIEW_STATE_DIR}/secrets}"
htpasswd_file="${REVIEW_GATEWAY_HTPASSWD_FILE:-${secrets_dir}/gateway.htpasswd}"
credentials_file="${REVIEW_GATEWAY_CREDENTIALS_FILE:-${secrets_dir}/gateway.credentials}"

for path in "$tls_dir" "$certbot_lib" "$secrets_dir"; do
  require_absolute_path "$path" "state path"
  install -d -m 700 "$path"
done
require_absolute_path "$acme_webroot" "ACME webroot"
install -d -m 755 "$acme_webroot"

if [[ ! -s "$htpasswd_file" ]]; then
  password="$(openssl rand -base64 32 | tr -d '/+=' | head -c 28)"
  password_hash="$(printf '%s\n' "$password" | openssl passwd -apr1 -stdin)"
  umask 077
  printf '%s:%s\n' "$GATEWAY_USERNAME" "$password_hash" > "$htpasswd_file"
  printf 'url=https://%s\nusername=%s\npassword=%s\n' "$public_ip" "$GATEWAY_USERNAME" "$password" > "$credentials_file"
  unset password password_hash
fi
chmod 600 "$htpasswd_file" "$credentials_file"

certificate="$tls_dir/live/$public_ip/fullchain.pem"
if [[ ! -s "$certificate" ]]; then
  bootstrap_name="review-acme-bootstrap-$$"
  cleanup() {
    docker rm --force "$bootstrap_name" >/dev/null 2>&1 || true
  }
  trap cleanup EXIT INT TERM
  docker run --detach --rm \
    --name "$bootstrap_name" \
    --publish 0.0.0.0:80:80 \
    --volume "$acme_webroot:/usr/share/nginx/html:ro" \
    "$BOOTSTRAP_NGINX_IMAGE" >/dev/null

  challenge_name="review-preflight-$(openssl rand -hex 12)"
  challenge_dir="$acme_webroot/.well-known/acme-challenge"
  install -d -m 755 "$challenge_dir"
  printf '%s\n' "$challenge_name" > "$challenge_dir/$challenge_name"
  chmod 644 "$challenge_dir/$challenge_name"
  challenge_url="http://$public_ip/.well-known/acme-challenge/$challenge_name"
  challenge_body=""
  for _ in $(seq 1 10); do
    if challenge_body="$(curl --silent --show-error --fail --max-time 5 "$challenge_url" 2>/dev/null)"; then
      break
    fi
    sleep 1
  done
  [[ "$challenge_body" == "$challenge_name" ]] \
    || die "ACME HTTP challenge preflight failed at $challenge_url"
  rm -f -- "$challenge_dir/$challenge_name"

  certbot_account=(--register-unsafely-without-email)
  if [[ -n "${REVIEW_ACME_EMAIL_FILE:-}" ]]; then
    check_private_file "$REVIEW_ACME_EMAIL_FILE"
    acme_email="$(tr -d '\r\n' < "$REVIEW_ACME_EMAIL_FILE")"
    [[ "$acme_email" == *@* ]] || die "ACME email file does not contain an email address"
    certbot_account=(--email "$acme_email")
  fi

  docker run --rm \
    --volume "$tls_dir:/etc/letsencrypt" \
    --volume "$certbot_lib:/var/lib/letsencrypt" \
    --volume "$acme_webroot:/var/www/certbot" \
    "$CERTBOT_IMAGE" certonly \
    --non-interactive \
    --agree-tos \
    "${certbot_account[@]}" \
    --preferred-profile shortlived \
    --webroot \
    --webroot-path /var/www/certbot \
    --ip-address "$public_ip" \
    --cert-name "$public_ip"
  cleanup
  trap - EXIT INT TERM
fi

openssl x509 -in "$certificate" -noout -checkend 86400 >/dev/null || die "certificate expires in less than 24 hours"
printf 'gateway credentials: %s\n' "$credentials_file"
printf 'certificate: %s\n' "$certificate"
