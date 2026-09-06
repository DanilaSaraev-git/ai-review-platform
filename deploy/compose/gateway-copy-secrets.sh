#!/bin/sh

set -eu

mkdir -p /etc/nginx/private
cp /run/review-secrets/gateway.htpasswd /etc/nginx/private/gateway.htpasswd
chown root:nginx /etc/nginx/private /etc/nginx/private/gateway.htpasswd
chmod 750 /etc/nginx/private
chmod 640 /etc/nginx/private/gateway.htpasswd
