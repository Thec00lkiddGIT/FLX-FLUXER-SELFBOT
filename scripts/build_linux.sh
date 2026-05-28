#!/usr/bin/env bash
# Build Linux folder for Chromebook (Crostini) and other Linux desktops.
set -euo pipefail
cd "$(dirname "$0")/.."

PYTHON="${PYTHON:-python3}"
if [[ ! -d .venv-build ]]; then
  "$PYTHON" -m venv .venv-build
fi
# shellcheck disable=SC1091
source .venv-build/bin/activate
pip install -q -U pip
pip install -q -r requirements.txt -r requirements-build.txt
python scripts/prepare_icons.py
pyinstaller build/flx.spec --clean --noconfirm

DIST="dist/FLX-FLUXER-SELFBOT"
chmod +x "$DIST/FLX-FLUXER-SELFBOT"
cp scripts/run_chromebook.sh "$DIST/run-chromebook.sh"
chmod +x "$DIST/run-chromebook.sh"
cp assets/icon.png "$DIST/icon.png" 2>/dev/null || true

cd dist
zip -r FLX-FLUXER-SELFBOT-Chromebook-Linux.zip FLX-FLUXER-SELFBOT
echo ""
echo "Done."
echo "  Folder: dist/FLX-FLUXER-SELFBOT/"
echo "  Zip:    dist/FLX-FLUXER-SELFBOT-Chromebook-Linux.zip"
echo "  Chromebook: unzip, then run ./run-chromebook.sh"
