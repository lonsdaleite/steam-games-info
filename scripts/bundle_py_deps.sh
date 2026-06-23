#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
REQUIREMENTS="${SCRIPT_DIR}/backend/requirements.txt"
TARGET="${SCRIPT_DIR}/backend/py_modules"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required to bundle Python dependencies." >&2
  exit 1
fi

if ! python3 -m pip --version >/dev/null 2>&1; then
  echo "python3 -m pip is required to bundle Python dependencies." >&2
  exit 1
fi

echo "Bundling Python dependencies into backend/py_modules..."
rm -rf "$TARGET"
mkdir -p "$TARGET"
python3 -m pip install -r "$REQUIREMENTS" -t "$TARGET" --no-deps --upgrade
find "$TARGET" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
