#!/usr/bin/env bash

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

usage() {
  printf 'usage: %s /absolute/path/to/release.tar.gz FULL_GIT_SHA\n' "$0" >&2
  exit 2
}

[[ $# -eq 2 ]] || usage
require_root
require_command tar
archive="$(realpath -e "$1")"
commit="$2"
[[ "$commit" =~ ^[0-9a-f]{40}$ ]] || die "commit is not a full Git SHA"

install -d -m 755 "$REVIEW_RELEASES_DIR"
target="$REVIEW_RELEASES_DIR/$commit"
[[ ! -e "$target" ]] || die "release already exists: $target"
tmp_target="$REVIEW_RELEASES_DIR/.install-$commit-$$"
install -d -m 755 "$tmp_target"
cleanup() { rm -rf -- "$tmp_target"; }
trap cleanup EXIT INT TERM

tar -xzf "$archive" -C "$tmp_target" --strip-components=1
[[ -f "$tmp_target/AGENTS.md" && -f "$tmp_target/deploy/compose/compose.production.yaml" ]] \
  || die "archive is not an AI Review production release"
printf '%s\n' "$commit" > "$tmp_target/RELEASE_COMMIT"
chmod 644 "$tmp_target/RELEASE_COMMIT"
mv "$tmp_target" "$target"
trap - EXIT INT TERM
printf '%s\n' "$target"
