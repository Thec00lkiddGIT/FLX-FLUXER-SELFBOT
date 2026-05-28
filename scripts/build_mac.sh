#!/usr/bin/env bash
# Build macOS app bundle: dist/FLX.app
set -euo pipefail
cd "$(dirname "$0")/.."

python3 -m pip install -q -r requirements.txt -r requirements-build.txt
python3 scripts/prepare_icons.py
pyinstaller build/flx.spec --clean --noconfirm

cd dist
ditto -c -k --sequesterRsrc --keepParent "FLX.app" FLX-macOS.zip
cd ..
echo "Done."
echo "  App:  dist/FLX.app"
echo "  Zip:  dist/FLX-macOS.zip"
