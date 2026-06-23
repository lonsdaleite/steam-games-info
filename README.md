# Steam Games Info

Decky Loader plugin that scans your installed Steam library and shows, for each game:

- which OS builds are offered and installed
- what can run on Linux (native vs Proton)
- the default launch method
- user-forced compatibility tools and last-run compat mapping from `compat_log.txt`

Based on the standalone `steam_game_versions.py` scanner.

## Usage

Open the plugin in the Decky quick access menu. Use **Rescan library** after installing or removing games. Filter by installed/offered builds, runnable platform, default launch, and forced Proton tool.

## Build

```bash
pnpm install
pnpm run build
./release.sh
```

Install the generated zip via Decky Loader settings or copy the plugin folder into `~/homebrew/plugins/Steam Games Info/`.

## Requirements

- Native (non-Flatpak) Steam install
- Python `vdf` module (listed in `backend/requirements.txt`; Decky installs it on plugin load)
