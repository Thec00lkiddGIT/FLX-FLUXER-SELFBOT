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
echo ""
echo "Done. Run:"
echo "  open \"dist/FLX FLUXER SELFBOT.app\""
