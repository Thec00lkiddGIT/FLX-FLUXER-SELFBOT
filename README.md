# FLX

Your Fluxer selfbot, with a **dashboard you can actually use** and a **Script Hub** for your own commands (plus community scripts you can grab with one click).

**Version:** 1.1.3

## Get FLX

**Downloads:** [github.com/Thec00lkiddGIT/FLX-FLUXER-SELFBOT/releases](https://github.com/Thec00lkiddGIT/FLX-FLUXER-SELFBOT/releases)

| Where you're on | Grab this |
|-----------------|-----------|
| **Mac (Apple Silicon)** | `FLX-macOS.zip` — unzip, open `FLX.app` |
| **Windows** | `FLX-Windows.zip` — unzip, run `FLX.exe` |
| **Chromebook / Linux** | `FLX-ChromeOS.zip` — run `./run-chromebook.sh` |

**Chromebook:** Turn on Linux (Crostini), unzip, run the script, open the link in Chrome. Step-by-step: [docs/CHROMEBOOK.md](docs/CHROMEBOOK.md)

**Building it yourself:**

| Platform | Command |
|----------|---------|
| **macOS** | `bash scripts/build_mac.sh` |
| **Windows** | `scripts\build_windows.bat` |
| **Linux / Chromebook** | `bash scripts/build_linux.sh` |

On Windows, the app window needs WebView2. If the native window acts up, run `python gui.py --web` and use it in your browser.

On Chromebook, `python gui.py --chromebook` or `./run-chromebook.sh` is usually the smoothest.

## Run from source (Python)

```bash
git clone https://github.com/Thec00lkiddGIT/FLX-FLUXER-SELFBOT.git
cd FLX-FLUXER-SELFBOT
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python gui.py
```

1. Open **Settings** → **Edit config** and paste your `FLUXER_TOKEN`
2. Hit **Start bot** on the dashboard
3. In Fluxer, try `!ping` (or whatever you set as `PREFIX`)

Prefer a browser tab? `python gui.py --web` → http://127.0.0.1:8766/

## Scripts (FlxScript)

Write Python in **Script Hub** with `@flxScript` and `@bot.command`. The **Community** tab has starter scripts (`echo`, `httpcat`, `pokemon`, `check`) — open one and click **Add to Script Hub** to make it yours.

Full guide: [docs/FLXSCRIPT_GUIDE.md](docs/FLXSCRIPT_GUIDE.md)

## Commands that ship with FLX

| Command | What it does |
|---------|----------------|
| `!ping` | See if the bot's alive |
| `!help` | List commands |
| `!status` | Set your presence |
| `!purge [n]` | Delete your recent messages |
| `!poof` | Remove image background (reply with an image; needs `POOF_API_KEY`) |
| `!screenshot <url>` | Screenshot a link (Microlink) |
| `!info user` | Profile, avatar, snowflake decode |
| `!wb <url> send\|delete` | Send or delete via a webhook URL |

FLX waits and retries when Fluxer rate-limits you or a channel is on slowmode.

The spicy abuse / mod / troll stuff stays locked until you turn on **abuse mode** in the app (`!abuse`).

## Config file

| OS | Where it lives |
|----|----------------|
| macOS | `~/Library/Application Support/Flx/config.env` |
| Windows | `%APPDATA%\Flx\config.env` |
| Linux / Chromebook | `~/.config/Flx/config.env` |

| Variable | Default |
|----------|---------|
| `FLUXER_TOKEN` | (you need this) |
| `FLUXER_API_URL` | `https://api.fluxer.app` |
| `PREFIX` | `!` |
| `POOF_API_KEY` | optional, for `!poof` |

## What's in the repo

```
gui.py              # Start the app (native or browser)
flx/                # Bot, dashboard, FlxScript
scripts/hub/        # Empty personal hub template
scripts/community/  # Bundled community scripts
build/flx.spec      # PyInstaller build
docs/FLXSCRIPT_GUIDE.md
```

## Links

- [Fluxer](https://fluxer.app)
- [Fluxer API docs](https://fluxerapp-fluxer.mintlify.app/)
