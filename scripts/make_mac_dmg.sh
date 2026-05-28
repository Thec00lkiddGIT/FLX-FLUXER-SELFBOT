#!/usr/bin/env bash
# Build a drag-to-Applications DMG from dist/FLX.app
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

APP_PATH="${1:-dist/FLX.app}"
if [[ ! -d "$APP_PATH" ]]; then
  echo "Missing app bundle: $APP_PATH (run scripts/build_mac.sh first)" >&2
  exit 1
fi

VERSION="$(python3 -c 'from flx.version import APP_VERSION; print(APP_VERSION)')"
DMG_NAME="FLX-${VERSION}-macOS.dmg"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

ditto "$APP_PATH" "$STAGE/FLX.app"
ln -s /Applications "$STAGE/Applications"

rm -f "dist/$DMG_NAME"
hdiutil create \
  -volname "FLX" \
  -srcfolder "$STAGE" \
  -ov \
  -format UDZO \
  -imagekey zlib-level=9 \
  "dist/$DMG_NAME"

echo "DMG: dist/$DMG_NAME"
