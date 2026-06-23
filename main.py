"""
steam-games-info - Decky Loader Plugin Backend
Inspect installed Steam game builds, runnable platforms, and default launch.
"""

import json
import os
import sys
import time
from pathlib import Path

import decky

PY_MODULES_DIR = os.path.join(decky.DECKY_PLUGIN_DIR, "backend", "py_modules")
if os.path.isdir(PY_MODULES_DIR) and PY_MODULES_DIR not in sys.path:
    sys.path.insert(0, PY_MODULES_DIR)

BACKEND_DIR = os.path.join(decky.DECKY_PLUGIN_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from steam_games_info import scan_installed_games  # noqa: E402


class Plugin:
    last_error: str = ""
    last_scan: dict | None = None
    last_scan_at: float = 0.0

    def _set_error(self, message: str) -> str:
        self.last_error = message
        decky.logger.error(message)
        return message

    def _read_plugin_version(self) -> str:
        try:
            package_json = Path(decky.DECKY_PLUGIN_DIR) / "package.json"
            if package_json.exists():
                with open(package_json, "r", encoding="utf-8") as file_handle:
                    return json.load(file_handle).get("version", "unknown")
        except Exception as exc:
            decky.logger.error("Failed to read plugin version: %s", exc)
        return "unknown"

    async def _main(self):
        decky.logger.info(
            "steam-games-info initialized (plugin_dir=%s)",
            decky.DECKY_PLUGIN_DIR,
        )

    async def _unload(self):
        decky.logger.info("steam-games-info unloaded")

    async def _migration(self):
        pass

    async def scan_games(self, include_all: bool = False) -> dict:
        self.last_error = ""
        started = time.monotonic()
        result = scan_installed_games(include_all=include_all)
        elapsed_ms = int((time.monotonic() - started) * 1000)

        if not result.get("ok"):
            self._set_error(result.get("error") or "Scan failed")
        else:
            self.last_scan = result
            self.last_scan_at = time.time()

        return {
            **result,
            "scan_ms": elapsed_ms,
            "last_error": self.last_error,
            "plugin_version": self._read_plugin_version(),
        }

    async def get_last_scan(self) -> dict:
        if self.last_scan is None:
            return {
                "has_scan": False,
                "last_scan_at": 0,
                "last_error": self.last_error,
                "plugin_version": self._read_plugin_version(),
            }
        return {
            "has_scan": True,
            "last_scan_at": self.last_scan_at,
            "last_error": self.last_error,
            "plugin_version": self._read_plugin_version(),
            "steam_root": self.last_scan.get("steam_root"),
            "game_count": self.last_scan.get("game_count", 0),
            "library_count": self.last_scan.get("library_count", 0),
        }
