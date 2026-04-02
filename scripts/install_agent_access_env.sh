#!/usr/bin/env bash
set -euo pipefail

TARGET_PATH="${1:-${HOME}/.config/memoryos-agent.env}"
AGENT_ID="${2:-nexus}"
API_KEY="${3:-dev-nexus-key}"
TAILSCALE_IP="${4:-100.93.59.21}"
TAILNET_HOST="${5:-wisepulse.tail925b8e.ts.net}"

mkdir -p "$(dirname "$TARGET_PATH")"

cat > "$TARGET_PATH" <<EOF
MEMORYOS_BASE_URL=http://127.0.0.1:8765
MEMORYOS_FALLBACK_URL=http://${TAILSCALE_IP}:8765
MEMORYOS_TAILSCALE_IP=${TAILSCALE_IP}
MEMORYOS_TAILNET_HOST=${TAILNET_HOST}
MEMORYOS_AGENT_ID=${AGENT_ID}
MEMORYOS_API_KEY=${API_KEY}
NO_PROXY=127.0.0.1,localhost,${TAILSCALE_IP},${TAILNET_HOST}
no_proxy=127.0.0.1,localhost,${TAILSCALE_IP},${TAILNET_HOST}
EOF

echo "Wrote ${TARGET_PATH}"
