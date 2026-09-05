#!/usr/bin/env bash

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

require_root
require_command install
require_command systemctl

release_dir="$(realpath -e "$REVIEW_CURRENT_LINK")"
require_safe_release_dir "$release_dir"
for unit in \
  review-backup.service review-backup.timer \
  review-cert-renew.service review-cert-renew.timer \
  review-model-probe.service review-model-probe.timer; do
  install -m 644 "$release_dir/deploy/systemd/$unit" "/etc/systemd/system/$unit"
done
systemctl daemon-reload
systemctl enable --now review-backup.timer review-cert-renew.timer review-model-probe.timer
systemctl list-timers --all \
  review-backup.timer review-cert-renew.timer review-model-probe.timer --no-pager
