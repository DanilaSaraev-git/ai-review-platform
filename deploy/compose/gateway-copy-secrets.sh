#!/bin/sh

set -eu

# Use the same strict flag as the API. A typo must never open the gateway.
case "${REVIEW_GUEST_ACCESS-false}" in
  true|false) ;;
  *) printf '%s\n' 'REVIEW_GUEST_ACCESS must be true or false' >&2; exit 1 ;;
esac

mkdir -p /etc/nginx/private
cp /run/review-secrets/gateway.htpasswd /etc/nginx/private/gateway.htpasswd
chown root:nginx /etc/nginx/private /etc/nginx/private/gateway.htpasswd
chmod 750 /etc/nginx/private
chmod 640 /etc/nginx/private/gateway.htpasswd
