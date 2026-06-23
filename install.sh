#!/usr/bin/env bash
set -euo pipefail

INSTALL_SCRIPT_REV=2

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_NAME="Steam Games Info"
PLUGINS_DIR="${HOME}/homebrew/plugins"
PLUGIN_DIR="${PLUGINS_DIR}/${PLUGIN_NAME}"

if ! command -v sudo >/dev/null 2>&1; then
  echo "sudo is required to install into ${PLUGINS_DIR} on Decky/Bazzite." >&2
  exit 1
fi

if [[ ! -f "${SCRIPT_DIR}/dist/index.js" ]]; then
  echo "dist/index.js is missing. Build first:" >&2
  echo "  cd ${SCRIPT_DIR} && pnpm install && pnpm run build" >&2
  exit 1
fi

echo "install.sh rev ${INSTALL_SCRIPT_REV}"
echo "Installing ${PLUGIN_NAME} from ${SCRIPT_DIR}"

sudo mkdir -p "$PLUGINS_DIR"
sudo rm -rf "$PLUGIN_DIR"
sudo mkdir -p "$PLUGIN_DIR"

sudo cp -r \
  "${SCRIPT_DIR}/dist" \
  "${SCRIPT_DIR}/main.py" \
  "${SCRIPT_DIR}/plugin.json" \
  "${SCRIPT_DIR}/package.json" \
  "${SCRIPT_DIR}/LICENSE" \
  "${SCRIPT_DIR}/README.md" \
  "${SCRIPT_DIR}/backend" \
  "$PLUGIN_DIR/"

if ! sudo test -f "${PLUGIN_DIR}/dist/index.js"; then
  echo "Install failed: dist/index.js is missing." >&2
  exit 1
fi

echo "Restarting plugin_loader..."
if sudo systemctl restart plugin_loader; then
  echo "Installed ${PLUGIN_NAME}."
  echo "Open Decky quick access menu and look for '${PLUGIN_NAME}'."
else
  echo "Plugin files are installed, but plugin_loader restart failed." >&2
  echo "Run: sudo systemctl restart plugin_loader" >&2
  exit 1
fi
