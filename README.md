# Steam Games Info

Decky Loader plugin that scans your installed Steam library and shows, for each game:

- which OS builds are offered and installed
- what can run on Linux (native vs Proton)
- the default launch method
- user-forced compatibility tools and last-run compat mapping from `compat_log.txt`

Based on the standalone `steam_game_versions.py` scanner.

## Usage

Open the plugin in the Decky quick access menu. Use **Rescan library** after installing or removing games. Filter by installed/offered builds, runnable platform, default launch, and forced Proton tool.

## Installation

**One-line terminal install:**

```bash
curl -fsSL -H 'Cache-Control: no-cache' https://raw.githubusercontent.com/lonsdaleite/steam-games-info/main/install.sh | bash
```

Manual install: download the latest `steam-games-info-v*.zip` from [Releases](https://github.com/lonsdaleite/steam-games-info/releases) and install via Decky Loader settings.

## Build

```bash
pnpm install
pnpm run build
./release.sh
```

## Requirements

- Native (non-Flatpak) Steam install

Python dependencies from `backend/requirements.txt` are bundled into `backend/py_modules/` during `./release.sh`. No manual pip install on the Deck is needed.
