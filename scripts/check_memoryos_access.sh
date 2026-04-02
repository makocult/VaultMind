#!/usr/bin/env bash
set -euo pipefail

if [ -f "${1:-}" ]; then
  # shellcheck disable=SC1090
  source "$1"
elif [ -f "${HOME}/.config/memoryos-agent.env" ]; then
  # shellcheck disable=SC1090
  source "${HOME}/.config/memoryos-agent.env"
fi

BASE_URL="${MEMORYOS_BASE_URL:-http://127.0.0.1:8765}"
FALLBACK_URL="${MEMORYOS_FALLBACK_URL:-}"
NO_PROXY_VALUE="${NO_PROXY:-127.0.0.1,localhost}"

export NO_PROXY="$NO_PROXY_VALUE"
export no_proxy="${no_proxy:-$NO_PROXY_VALUE}"

check_url() {
  local url="$1"
  if [ -z "$url" ]; then
    return 1
  fi
  echo "Checking ${url}/readyz"
  curl -sS -m 5 "${url}/readyz"
}

if check_url "$BASE_URL"; then
  exit 0
fi

if check_url "$FALLBACK_URL"; then
  exit 0
fi

echo "MemoryOS access failed via both BASE_URL and FALLBACK_URL" >&2
exit 1
