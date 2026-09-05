#!/usr/bin/env bash

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

CERTBOT_IMAGE="${CERTBOT_IMAGE:-certbot/certbot:v5.8.0}"

require_root
require_command docker
require_command openssl

public_ip="${REVIEW_PUBLIC_IP:-$(env_value REVIEW_PUBLIC_IP)}"
tls_dir="${REVIEW_TLS_DIR:-$(env_value REVIEW_TLS_DIR)}"
certbot_lib="${REVIEW_CERTBOT_LIB_DIR:-${REVIEW_STATE_DIR}/certbot-lib}"
acme_webroot="${REVIEW_ACME_WEBROOT:-$(env_value REVIEW_ACME_WEBROOT)}"
release_dir="$(realpath -e "$REVIEW_CURRENT_LINK")"
require_safe_release_dir "$release_dir"

docker run --rm \
  --volume "$tls_dir:/etc/letsencrypt" \
  --volume "$certbot_lib:/var/lib/letsencrypt" \
  --volume "$acme_webroot:/var/www/certbot" \
  "$CERTBOT_IMAGE" renew \
  --non-interactive \
  --preferred-profile shortlived \
  --webroot \
  --webroot-path /var/www/certbot

certificate="$tls_dir/live/$public_ip/fullchain.pem"
openssl x509 -in "$certificate" -noout -checkend 86400 >/dev/null || die "renewed certificate expires in less than 24 hours"

compose_base_args "$release_dir"
docker compose "${COMPOSE_ARGS[@]}" exec -T gateway nginx -s reload
printf 'certificate valid and gateway reloaded\n'
