#!/usr/bin/env bash
# Install or remove the weekday daily pipeline launchd agent.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LABEL="com.usquant.daily"
TEMPLATE="${ROOT}/deploy/launchd/com.usquant.daily.plist"
TARGET="${HOME}/Library/LaunchAgents/${LABEL}.plist"

usage() {
  cat <<EOF
Usage:
  $(basename "$0") install
  $(basename "$0") uninstall
EOF
}

install_agent() {
  mkdir -p "${HOME}/Library/LaunchAgents" "${ROOT}/logs"
  sed "s|__PROJECT_ROOT__|${ROOT}|g" "$TEMPLATE" > "$TARGET"
  chmod +x "${ROOT}/scripts/daily_pipeline.sh"
  launchctl bootout "gui/${UID}/${LABEL}" >/dev/null 2>&1 || true
  launchctl bootstrap "gui/${UID}" "$TARGET"
  launchctl enable "gui/${UID}/${LABEL}"
  echo "Installed ${TARGET}"
}

uninstall_agent() {
  launchctl bootout "gui/${UID}/${LABEL}" >/dev/null 2>&1 || true
  rm -f "$TARGET"
  echo "Removed ${TARGET}"
}

case "${1:-}" in
  install) install_agent ;;
  uninstall) uninstall_agent ;;
  *) usage; exit 1 ;;
esac