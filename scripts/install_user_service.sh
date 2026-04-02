#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SYSTEMD_USER_DIR="${HOME}/.config/systemd/user"
ENV_PATH="${HOME}/.config/memoryos.env"

mkdir -p "$SYSTEMD_USER_DIR"
mkdir -p "$(dirname "$ENV_PATH")"

install -m 0644 "$ROOT_DIR/deploy/systemd/user/memoryos-api.service" \
  "$SYSTEMD_USER_DIR/memoryos-api.service"
install -m 0644 "$ROOT_DIR/deploy/systemd/user/memoryos-worker.service" \
  "$SYSTEMD_USER_DIR/memoryos-worker.service"
install -m 0644 "$ROOT_DIR/deploy/systemd/user/memoryos-worker.timer" \
  "$SYSTEMD_USER_DIR/memoryos-worker.timer"

if [ ! -f "$ENV_PATH" ]; then
  cat > "$ENV_PATH" <<EOF
MEMORYOS_APP_ENV=production
MEMORYOS_HOST=0.0.0.0
MEMORYOS_PORT=8765
MEMORYOS_METRICS_PORT=8766
MEMORYOS_DATA_ROOT=${HOME}/VaultMind/var/data
MEMORYOS_API_KEYS_JSON={"nexus":"dev-nexus-key","morgan":"dev-morgan-key","anya":"dev-anya-key"}
EOF
  echo "Created $ENV_PATH from template."
else
  echo "Keeping existing $ENV_PATH"
fi

systemctl --user daemon-reload

cat <<EOF
Installed user units:
  - memoryos-api.service
  - memoryos-worker.service
  - memoryos-worker.timer

Next steps:
  systemctl --user enable --now memoryos-api.service
  systemctl --user enable --now memoryos-worker.timer
  systemctl --user status memoryos-api.service
EOF
