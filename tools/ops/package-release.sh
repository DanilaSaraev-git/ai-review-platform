#!/usr/bin/env bash

set -Eeuo pipefail

usage() {
  printf 'usage: %s /absolute/path/to/release.tar.gz\n' "$0" >&2
  exit 2
}

[[ $# -eq 1 ]] || usage
output="$1"
[[ "$output" == /* ]] || { printf 'output must be an absolute path\n' >&2; exit 1; }

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"
[[ -z "$(git status --porcelain)" ]] || { printf 'refusing to package a dirty worktree\n' >&2; exit 1; }
commit="$(git rev-parse HEAD)"
[[ "$commit" =~ ^[0-9a-f]{40}$ ]] || { printf 'HEAD is not a full Git SHA\n' >&2; exit 1; }

umask 077
git archive --format=tar --prefix="$commit/" HEAD | gzip -9 > "$output"
printf '%s\n' "$commit"
