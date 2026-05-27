#!/usr/bin/env bash
# Build macOS app bundle: dist/FLX FLUXER SELFBOT.app
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
pyinstaller build/flx.spec --clean --noconfirm
cd dist
ditto -c -k --sequesterRsrc --keepParent "FLX FLUXER SELFBOT.app" FLX-FLUXER-SELFBOT-macOS.zip
echo ""
echo "Done."
echo "  App:  dist/FLX FLUXER SELFBOT.app"
echo "  Zip:  dist/FLX-FLUXER-SELFBOT-macOS.zip"
