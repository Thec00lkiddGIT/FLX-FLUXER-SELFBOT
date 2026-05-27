# FLX FLUXER SELFBOT

Fluxer selfbot for [fluxer.app](https://fluxer.app) / [web.fluxer.app](https://web.fluxer.app), with an **Ibot-style dashboard** and **Nighty-style FlxScript** hub.

## Downloads (macOS and Windows)

Build standalone apps from source:

| Platform | Command | Output |
|----------|---------|--------|
| **macOS** | `bash scripts/build_mac.sh` | `dist/FLX FLUXER SELFBOT.app` |
| **Windows** | `scripts\build_windows.bat` | `dist\FLX-FLUXER-SELFBOT\FLX-FLUXER-SELFBOT.exe` |

**Windows note:** WebView2 runtime is required for the native window (usually already installed on Windows 10/11). Use `python gui.py --web` if the native window fails.

## Quick start (Python)

```bash
git clone https://github.com/Thec00lkiddGIT/FLX-FLUXER-SELFBOT.git
cd FLX-FLUXER-SELFBOT
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python gui.py
```

1. **Settings** -> **Edit config** -> set `FLUXER_TOKEN`
2. **Dashboard** -> **Start bot**
3. In Fluxer, send `!ping` (or your `PREFIX`) from your account

Browser UI: `python gui.py --web` -> http://127.0.0.1:8766/

## FlxScript (like Nighty)

Write Python in **Script Hub** using `@flxScript`, `@bot.command`, and `@bot.listen`.

Full guide: [docs/FLXSCRIPT_GUIDE.md](docs/FLXSCRIPT_GUIDE.md)

## Built-in commands

| Command | Description |
|---------|-------------|
| `!ping` | Latency check |
| `!help` | List commands |
| `!echo` | Repeat text |
| `!status` | Set presence |
| `!purge [n]` | Delete your recent messages |

Abuse / mod / troll commands require enabling **abuse mode** in the GUI (`!abuse`).

## Config

| OS | Config file |
|----|-------------|
| macOS | `~/Library/Application Support/Flx/config.env` |
| Windows | `%APPDATA%\Flx\config.env` |
| Linux | `~/.config/Flx/config.env` |

| Variable | Default |
|----------|---------|
| `FLUXER_TOKEN` | (required) |
| `FLUXER_API_URL` | `https://api.fluxer.app` |
| `PREFIX` | `!` |

## Project layout

```
gui.py              # Launch native / web UI
flx/                # Bot core, GUI, FlxScript
scripts/hub/        # Bundled example scripts
scripts/build_*.sh  # macOS / Windows packagers
build/flx.spec      # PyInstaller spec
docs/FLXSCRIPT_GUIDE.md
```

## Links

- [Fluxer](https://fluxer.app)
- [API docs](https://fluxerapp-fluxer.mintlify.app/)
