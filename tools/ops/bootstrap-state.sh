#!/usr/bin/env bash

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

usage() {
  printf 'usage: %s PUBLIC_IPV4\n' "$0" >&2
  exit 2
}

[[ $# -eq 1 ]] || usage
require_root
require_command docker
require_command openssl
public_ip="$1"
[[ "$public_ip" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]] || die "PUBLIC_IPV4 is invalid"
IFS=. read -r octet1 octet2 octet3 octet4 <<< "$public_ip"
for octet in "$octet1" "$octet2" "$octet3" "$octet4"; do
  ((10#$octet >= 0 && 10#$octet <= 255)) || die "PUBLIC_IPV4 is invalid"
done

template="$(realpath -e "$SCRIPT_DIR/../../deploy/compose/production.env.example")"
install -d -m 700 "$REVIEW_STATE_DIR" "${REVIEW_STATE_DIR}/secrets"

capture_legacy_environment() {
  local key
  local -a required_keys=(
    REVIEW_COMPOSITION
    REVIEW_MODEL_PROFILE_ID
    REVIEW_DIALOGUE_POLICY_ID
    REVIEW_ORGANIZATION_ID
    REVIEW_ORGANIZATION_NAME
    REVIEW_WORKSPACE_ID
    REVIEW_WORKSPACE_NAME
    REVIEW_ACTOR_ID
    REVIEW_ACTOR_DISPLAY_NAME
  )
  if [[ -e "$REVIEW_LEGACY_ENV_FILE" ]]; then
    check_private_file "$REVIEW_LEGACY_ENV_FILE"
    local legacy_complete=1
    for key in "${required_keys[@]}"; do
      if [[ -z "$(env_value "$key" "$REVIEW_LEGACY_ENV_FILE" 2>/dev/null || true)" ]]; then
        legacy_complete=0
        break
      fi
    done
    if [[ "$legacy_complete" == 1 ]]; then
      return 0
    fi
  fi
  local api_container
  local -a api_containers
  mapfile -t api_containers < <(docker ps \
    --filter "label=com.docker.compose.project=$REVIEW_COMPOSE_PROJECT" \
    --filter 'label=com.docker.compose.service=api' \
    --format '{{.ID}}')
  if ((${#api_containers[@]} > 1)); then
    die "multiple running API containers match the deployment project"
  fi
  if ((${#api_containers[@]} == 0)); then
    [[ ! -e "$REVIEW_LEGACY_ENV_FILE" ]] \
      || die "legacy environment is incomplete and no running API can refresh it"
    return 0
  fi
  api_container="${api_containers[0]}"
  umask 077
  local legacy_tmp
  legacy_tmp="$(mktemp "${REVIEW_STATE_DIR}/.legacy.env.XXXXXX")"
  if ! docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' "$api_container" \
    | awk -F= '$1 ~ /^REVIEW_[A-Z0-9_]+$/ {print}' > "$legacy_tmp"; then
    rm -f -- "$legacy_tmp"
    die "failed to inspect the running API environment"
  fi
  chmod 600 "$legacy_tmp"
  for key in "${required_keys[@]}"; do
    if [[ -z "$(env_value "$key" "$legacy_tmp" 2>/dev/null || true)" ]]; then
      rm -f -- "$legacy_tmp"
      die "running API environment has no required legacy setting: $key"
    fi
  done
  mv -f -- "$legacy_tmp" "$REVIEW_LEGACY_ENV_FILE"
}

capture_legacy_environment
if [[ -e "$REVIEW_ENV_FILE" ]]; then
  check_private_file "$REVIEW_ENV_FILE"
  [[ "$(env_value REVIEW_PUBLIC_IP)" == "$public_ip" ]] \
    || die "existing environment belongs to another public IP"
  printf 'state already initialized: %s\n' "$REVIEW_ENV_FILE"
  exit 0
fi

postgres_password=""
mapfile -t postgres_containers < <(docker ps \
  --filter "label=com.docker.compose.project=$REVIEW_COMPOSE_PROJECT" \
  --filter 'label=com.docker.compose.service=postgres' \
  --format '{{.ID}}')
if ((${#postgres_containers[@]} > 1)); then
  die "multiple running PostgreSQL containers match the deployment project"
fi
if ((${#postgres_containers[@]} == 1)); then
  postgres_password="$(docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' \
    "${postgres_containers[0]}" | awk -F= '$1 == "POSTGRES_PASSWORD" {sub(/^[^=]*=/, ""); print; exit}')"
  [[ -n "$postgres_password" ]] || die "running PostgreSQL container has no configured password"
fi
postgres_password="${postgres_password:-$(openssl rand -hex 32)}"
[[ "$postgres_password" =~ ^[A-Za-z0-9._~-]{8,128}$ ]] \
  || die "existing PostgreSQL password cannot be represented safely in the deployment env file"
umask 077
awk -v password="$postgres_password" -v ip="$public_ip" '
  /^POSTGRES_PASSWORD=/ {$0 = "POSTGRES_PASSWORD=" password}
  /^REVIEW_PUBLIC_IP=/ {$0 = "REVIEW_PUBLIC_IP=" ip}
  {print}
' "$template" > "$REVIEW_ENV_FILE"
unset postgres_password
chmod 600 "$REVIEW_ENV_FILE"

[[ "$(env_value REVIEW_PUBLIC_IP)" == "$public_ip" ]] || die "failed to initialize public IP"
[[ "$(env_value POSTGRES_PASSWORD)" != replace-with-a-long-random-value ]] \
  || die "failed to initialize database password"
printf 'private deployment state initialized: %s\n' "$REVIEW_ENV_FILE"
if [[ -f "$REVIEW_LEGACY_ENV_FILE" ]]; then
  printf 'private legacy rollback environment captured: %s\n' "$REVIEW_LEGACY_ENV_FILE"
fi
