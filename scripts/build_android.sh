#!/usr/bin/env bash
# Build FLX for Android and copy APK/AAB artifacts to ~/Desktop/FLX-Android.
# Does NOT push to GitHub or post release webhooks.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DESKTOP="${HOME}/Desktop/FLX-Android"
VENV="${ROOT}/.venv"

if [[ -z "${ANDROID_HOME:-}" ]]; then
  for candidate in "${HOME}/Library/Android/sdk" "${HOME}/Android/Sdk"; do
    if [[ -d "$candidate" ]]; then
      export ANDROID_HOME="$candidate"
      export ANDROID_SDK_ROOT="$candidate"
      break
    fi
  done
fi

# Briefcase expects cmdline-tools/19.0; Homebrew/Android Studio often only provide "latest".
if [[ -n "${ANDROID_HOME:-}" && -d "${ANDROID_HOME}/cmdline-tools/latest" && ! -e "${ANDROID_HOME}/cmdline-tools/19.0" ]]; then
  ln -sfn latest "${ANDROID_HOME}/cmdline-tools/19.0"
fi

if [[ -z "${ANDROID_HOME:-}" || ! -d "$ANDROID_HOME" ]]; then
  echo "Android SDK not found. Install Android Studio or set ANDROID_HOME."
  exit 1
fi

export PATH="${ANDROID_HOME}/platform-tools:${ANDROID_HOME}/cmdline-tools/latest/bin:${PATH}"

cd "$ROOT"

if [[ ! -d "$VENV" ]]; then
  python3 -m venv "$VENV"
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"

pip install -U pip briefcase toga-android websockets >/dev/null

echo "Preparing app icons..."
python3 scripts/prepare_icons.py

echo "Creating / updating Briefcase Android project..."
briefcase create android --no-input 2>/dev/null || briefcase update android -r --update-resources --no-input

echo "Building Android debug APK (first run can take several minutes)..."
briefcase build android --no-input

echo "Packaging debug APK..."
briefcase package android -p debug-apk --no-input

echo "Exporting to ${DESKTOP}..."
rm -rf "$DESKTOP"
mkdir -p "$DESKTOP"

APK="$(find "${ROOT}/dist" -name 'FLX-*.apk' | head -1)"
if [[ -n "$APK" && -f "$APK" ]]; then
  cp "$APK" "$DESKTOP/"
  cp "$APK" "${HOME}/Desktop/FLX.apk"
fi

cat > "${DESKTOP}/README.txt" <<'EOF'
FLX Android (local build)

Install on device:
  1. Enable "Install unknown apps" / sideload the APK
  2. Copy FLX-*.apk to your phone and open it
     — or: adb install FLX-*.apk

First launch:
  - Settings → Enter token
  - Dashboard → Start bot

Data folder (app private storage):
  config.env, scripts/hub/

Rebuild from repo:
  bash scripts/build_android.sh
EOF

echo ""
echo "Done. Android build output: ${DESKTOP}"
ls -lh "$DESKTOP"/*.apk 2>/dev/null || ls -lh "$DESKTOP"
