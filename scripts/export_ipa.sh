#!/usr/bin/env bash
# Build a device FLX.app and export ~/Desktop/FLX.ipa.
# Does NOT push to GitHub or post release webhooks.
#
# Signing is optional. Set FLX_IOS_TEAM_ID only if you want Xcode to sign with
# your team; otherwise exports an unsigned IPA (re-sign with Sideloadly / Xcode).

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
XCODE_DIR="${ROOT}/build/app/ios/xcode"
if [[ ! -d "$XCODE_DIR" ]]; then
  XCODE_DIR="${ROOT}/build/flx/ios/xcode"
fi
PLIST="${XCODE_DIR}/FLX/FLX-Info.plist"
DESKTOP_IPA="${HOME}/Desktop/FLX.ipa"
BUNDLE_ID="com.flx.app"

if [[ ! -d "$XCODE_DIR" ]]; then
  echo "No iOS Xcode project found. Run: bash scripts/build_ios.sh"
  exit 1
fi

PLIST_BACKUP="$(mktemp)"
cp "$PLIST" "$PLIST_BACKUP"
restore_plist() { mv "$PLIST_BACKUP" "$PLIST"; }
trap restore_plist EXIT

/usr/libexec/PlistBuddy -c "Set :CFBundleIdentifier ${BUNDLE_ID}" "$PLIST"
cd "$XCODE_DIR"

if [[ -n "${FLX_IOS_TEAM_ID:-}" ]]; then
  echo "Building signed Release (bundle ${BUNDLE_ID}, team ${FLX_IOS_TEAM_ID})..."
  xcodebuild -project FLX.xcodeproj -scheme FLX -configuration Release \
    -sdk iphoneos -destination 'generic/platform=iOS' \
    DEVELOPMENT_TEAM="${FLX_IOS_TEAM_ID}" \
    CODE_SIGN_STYLE=Automatic \
    PRODUCT_BUNDLE_IDENTIFIER="$BUNDLE_ID" \
    -allowProvisioningUpdates \
    build
else
  echo "Building unsigned Release (bundle ${BUNDLE_ID})..."
  echo "Tip: set FLX_IOS_TEAM_ID to sign with your Apple team, or re-sign the IPA later."
  /usr/libexec/PlistBuddy -c "Delete :UIBackgroundModes" "$PLIST" 2>/dev/null || true
  if ! xcodebuild -project FLX.xcodeproj -scheme FLX -configuration Release \
    -sdk iphoneos -destination 'generic/platform=iOS' \
    CODE_SIGN_IDENTITY='-' \
    CODE_SIGNING_REQUIRED=NO \
    CODE_SIGNING_ALLOWED=YES \
    CODE_SIGN_STYLE=Manual \
    EXPANDED_CODE_SIGN_IDENTITY='-' \
    PRODUCT_BUNDLE_IDENTIFIER="$BUNDLE_ID" \
    build 2>/dev/null; then
    echo "Xcode unsigned build blocked — repackaging device FLX.app with fresh Python sources..."
    SRC_APP="$(find ~/Library/Developer/Xcode/DerivedData/FLX-*/Build/Products/Release-iphoneos -name 'FLX.app' -type d 2>/dev/null | head -1)"
    if [[ -z "$SRC_APP" || ! -d "$SRC_APP" ]]; then
      echo "No Release-iphoneos FLX.app found. Run: bash scripts/build_ios.sh"
      exit 1
    fi
    REPACK="$(mktemp -d)"
    cp -R "$SRC_APP" "$REPACK/FLX.app"
    APP_SRC="${XCODE_DIR}/FLX/app"
    PKG_SRC="${XCODE_DIR}/FLX/app_packages.iphoneos"
    if [[ -d "$APP_SRC" ]]; then
      echo "Syncing app/ from ${APP_SRC}..."
      rsync -a --delete "$APP_SRC/" "$REPACK/FLX.app/app/"
      find "$REPACK/FLX.app/app" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    fi
    if [[ -d "$PKG_SRC" ]]; then
      echo "Syncing app_packages.iphoneos from ${PKG_SRC}..."
      rsync -a --delete "$PKG_SRC/" "$REPACK/FLX.app/app_packages/"
      find "$REPACK/FLX.app/app_packages" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    fi
    /usr/libexec/PlistBuddy -c "Set :CFBundleIdentifier ${BUNDLE_ID}" "$REPACK/FLX.app/Info.plist"
    rm -f "$REPACK/FLX.app/embedded.mobileprovision" 2>/dev/null || true
    /usr/bin/codesign --force --sign - --deep "$REPACK/FLX.app"
    APP="$REPACK/FLX.app"
  fi
fi

if [[ -z "${APP:-}" ]]; then
  APP="$(find ~/Library/Developer/Xcode/DerivedData/FLX-*/Build/Products/Release-iphoneos -name 'FLX.app' -type d 2>/dev/null | head -1)"
fi
if [[ -z "$APP" || ! -d "$APP" ]]; then
  echo "Build finished but FLX.app not found."
  exit 1
fi

if [[ -z "${FLX_IOS_TEAM_ID:-}" ]]; then
  /usr/bin/codesign --force --sign - --deep "$APP" 2>/dev/null || true
fi

STAGE="$(mktemp -d)"
mkdir -p "${STAGE}/Payload"
cp -R "$APP" "${STAGE}/Payload/"
( cd "$STAGE" && zip -qr "$DESKTOP_IPA" Payload )
rm -rf "$STAGE"

BUNDLE="$(/usr/libexec/PlistBuddy -c 'Print CFBundleIdentifier' "$APP/Info.plist")"
echo ""
echo "IPA ready: ${DESKTOP_IPA} ($(du -h "$DESKTOP_IPA" | cut -f1), bundle ${BUNDLE})"
if [[ -z "${FLX_IOS_TEAM_ID:-}" ]]; then
  echo "Unsigned build — install via Sideloadly/AltStore or open the Xcode project and sign there."
else
  echo "Install: Xcode → Devices, Sideloadly, or AltStore."
fi
