# Chromebook guide

Two ways to use FLX on a Chromebook.

## Option A: Browser only (no Linux) — pretty limited

Without Linux turned on, FLX can't run on the Chromebook itself. You can still chat on [web.fluxer.app](https://web.fluxer.app). For the selfbot, you'll need Linux on the Chromebook, or use a Mac, Windows PC, or phone elsewhere.

## Option B: Linux on Chromebook (recommended)

1. Open **Settings** -> **Developers** -> turn on **Linux development environment** (Crostini).
2. In the Linux terminal:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip unzip
cd ~
wget -O flx.zip https://github.com/flxselfbot/FLX-FLUXER-SELFBOT/releases/latest/download/FLX-ChromeOS.zip
unzip flx.zip
cd FLX
./run-chromebook.sh
```

3. When the terminal shows `http://127.0.0.1:8766/`, open **Chrome** and go to that address (or it may open automatically).
4. **Settings** -> **Edit config** -> set `FLUXER_TOKEN` -> **Start bot**.

Config is stored at `~/.config/Flx/config.env`.

### Native window (optional)

If GTK/WebKit is installed:

```bash
sudo apt install -y python3-gi gir1.2-gtk-3.0 gir1.2-webkit2-4.1
./FLX
```

Most Chromebook users should use `./run-chromebook.sh` instead.

## Option C: Run from source

```bash
git clone https://github.com/flxselfbot/FLX-FLUXER-SELFBOT.git
cd FLX-FLUXER-SELFBOT
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python gui.py --chromebook
```

## ARM Chromebooks

The release zip is built for **x86_64** Linux. On ARM Chromebooks, use **Option C** (Python from source) with `--chromebook`.
