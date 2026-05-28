#!/usr/bin/env bash
# Build Linux / Chromebook folder and zip
set -euo pipefail
cd "$(dirname "$0")/.."

python3 -m pip install -q -r requirements.txt -r requirements-build.txt
python3 scripts/prepare_icons.py
pyinstaller build/flx.spec --clean --noconfirm

DIST="dist/FLX"
chmod +x "$DIST/FLX"
cp scripts/run_chromebook.sh "$DIST/run-chromebook.sh"
chmod +x "$DIST/run-chromebook.sh"
cp assets/icon.png "$DIST/icon.png"
(
  cd dist
  zip -r FLX-ChromeOS.zip FLX
)
echo "Done."
echo "  Folder: dist/FLX/"
echo "  Zip:    dist/FLX-ChromeOS.zip"
