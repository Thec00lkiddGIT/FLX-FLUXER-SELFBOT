# FLX

Fluxer selfbot for [fluxer.app](https://fluxer.app) / [web.fluxer.app](https://web.fluxer.app), with a **web dashboard** and **FlxScript** hub (personal + community scripts).

**Current version:** 1.0.7

## Downloads

**Releases:** [github.com/Thec00lkiddGIT/FLX-FLUXER-SELFBOT/releases](https://github.com/Thec00lkiddGIT/FLX-FLUXER-SELFBOT/releases)

| Platform | File |
|----------|------|
| **macOS** (Apple Silicon) | `FLX-macOS.zip` -> open `FLX.app` |
| **Windows** | `FLX-Windows.zip` -> run `FLX.exe` |
| **ChromeOS / Chromebook / Linux** | `FLX-ChromeOS.zip` -> run `./run-chromebook.sh` |

**Chromebook:** Turn on Linux (Crostini), unzip, run `./run-chromebook.sh`, open the URL in Chrome. Full guide: [docs/CHROMEBOOK.md](docs/CHROMEBOOK.md)

Build from source:

| Platform | Command |
|----------|---------|
| **macOS** | `bash scripts/build_mac.sh` |
| **Windows** | `scripts\build_windows.bat` |
| **Linux / Chromebook** | `bash scripts/build_linux.sh` |

**Windows note:** WebView2 is required for the native window. Use `python gui.py --web` if the native window fails.

**Chromebook note:** Use `python gui.py --chromebook` or `./run-chromebook.sh` for the browser dashboard (recommended).

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

## FlxScript

Write Python in **Script Hub** using `@flxScript`, `@bot.command`, and `@bot.listen`. The **Community** tab ships starter scripts (`echo`, `httpcat`, `pokemon`, `check`) - open it and click **Add to Script Hub** to install them.

Full guide: [docs/FLXSCRIPT_GUIDE.md](docs/FLXSCRIPT_GUIDE.md)

## Built-in commands

| Command | Description |
|---------|-------------|
| `!ping` | Latency check |
| `!help` | List commands |
| `!status` | Set presence |
| `!purge [n]` | Delete your recent messages |
| `!poof` | Remove image background (reply with image; needs `POOF_API_KEY`) |
| `!screenshot <url>` | Screenshot a URL (Microlink) |
| `!info user` | Profile, avatar, snowflake decode |
| `!wb <url> send\|delete` | Webhook send or delete via URL |

Outgoing messages wait and retry on channel slowmode / rate limits automatically.

Abuse / mod / troll commands require enabling **abuse mode** in the GUI (`!abuse`).

## Config

| OS | Config file |
|----|-------------|
| macOS | `~/Library/Application Support/Flx/config.env` |
| Windows | `%APPDATA%\Flx\config.env` |
| Linux / Chromebook | `~/.config/Flx/config.env` |

| Variable | Default |
|----------|---------|
| `FLUXER_TOKEN` | (required) |
| `FLUXER_API_URL` | `https://api.fluxer.app` |
| `PREFIX` | `!` |
| `POOF_API_KEY` | (optional, for `!poof`) |

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
