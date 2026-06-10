#!/usr/bin/env bash
# Build FLX for iOS locally and copy the Xcode project to ~/Desktop/FLX-iOS.
# Does NOT push to GitHub or post release webhooks.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DESKTOP="${HOME}/Desktop/FLX-iOS"
VENV="${ROOT}/.venv"

cd "$ROOT"

if [[ ! -d "$VENV" ]]; then
  python3 -m venv "$VENV"
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"

pip install -U pip briefcase toga-iOS websockets >/dev/null

echo "Preparing app icons (same as macOS / Windows)..."
python3 scripts/prepare_icons.py

echo "Creating / updating Briefcase iOS project..."
briefcase update iOS -r --update-resources --no-input 2>/dev/null || briefcase create iOS --no-input

echo "Building iOS app (this can take several minutes on first run)..."
briefcase build iOS --no-input

PLIST="${ROOT}/build/app/ios/xcode/FLX/FLX-Info.plist"
if [[ ! -f "$PLIST" ]]; then
  PLIST="${ROOT}/build/flx/ios/xcode/FLX/FLX-Info.plist"
fi
if [[ -f "$PLIST" ]]; then
  /usr/libexec/PlistBuddy -c "Print :UIBackgroundModes" "$PLIST" >/dev/null 2>&1 || \
    /usr/libexec/PlistBuddy -c "Add :UIBackgroundModes array" "$PLIST"
  /usr/libexec/PlistBuddy -c "Print :UIBackgroundModes:0" "$PLIST" >/dev/null 2>&1 || \
    /usr/libexec/PlistBuddy -c "Add :UIBackgroundModes:0 string audio" "$PLIST"
  /usr/libexec/PlistBuddy -c "Print :UIFileSharingEnabled" "$PLIST" >/dev/null 2>&1 || \
    /usr/libexec/PlistBuddy -c "Add :UIFileSharingEnabled bool true" "$PLIST"
  /usr/libexec/PlistBuddy -c "Print :LSSupportsOpeningDocumentsInPlace" "$PLIST" >/dev/null 2>&1 || \
    /usr/libexec/PlistBuddy -c "Add :LSSupportsOpeningDocumentsInPlace bool true" "$PLIST"
  /usr/libexec/PlistBuddy -c "Print :UIStatusBarStyle" "$PLIST" >/dev/null 2>&1 || \
    /usr/libexec/PlistBuddy -c "Add :UIStatusBarStyle string UIStatusBarStyleLightContent" "$PLIST"
  /usr/libexec/PlistBuddy -c "Print :UIViewControllerBasedStatusBarAppearance" "$PLIST" >/dev/null 2>&1 || \
    /usr/libexec/PlistBuddy -c "Add :UIViewControllerBasedStatusBarAppearance bool false" "$PLIST"
fi

echo "Exporting to ${DESKTOP}..."
rm -rf "$DESKTOP"
mkdir -p "$DESKTOP"

XCODE_SRC="${ROOT}/build/app/ios/xcode"
if [[ ! -d "$XCODE_SRC" ]]; then
  XCODE_SRC="${ROOT}/build/flx/ios/xcode"
fi
if [[ -d "$XCODE_SRC" ]]; then
  cp -R "$XCODE_SRC" "${DESKTOP}/XcodeProject"
fi

if [[ -d "${ROOT}/build/app/ios" ]]; then
  cp -R "${ROOT}/build/app/ios" "${DESKTOP}/build-artifacts" 2>/dev/null || true
elif [[ -d "${ROOT}/build/flx/ios" ]]; then
  cp -R "${ROOT}/build/flx/ios" "${DESKTOP}/build-artifacts" 2>/dev/null || true
fi

cat > "${DESKTOP}/README.txt" <<'EOF'
FLX iOS (local build)

Open XcodeProject/FLX.xcodeproj in Xcode on your Mac.

Install on device:
  1. Plug in your iPhone
  2. Select your device as run target
  3. Set your Team under Signing & Capabilities
  4. Product -> Run

Behavior:
  - Background (home button / switch apps): bot keeps running via silent audio
  - Swipe away from app switcher: iOS kills the app and the bot stops

First launch:
  - Settings → Enter token (or Files → On My iPhone → FLX → Flx → config.env)
  - Dashboard → Start bot

Files app:
  Your config and scripts are in Files → On My iPhone → FLX → Flx

Rebuild from repo:
  bash scripts/build_ios.sh
EOF

echo ""
echo "Done. FLX iOS project is on your Desktop: ${DESKTOP}"
echo "Open ${DESKTOP}/XcodeProject/FLX.xcodeproj in Xcode to install on your iPhone."
echo ""
echo "Export .ipa to ~/Desktop/FLX.ipa:"
echo "  bash scripts/export_ipa.sh"
