#!/usr/bin/env bash
# Build iOS IPA + Android APK, tag release, upload to GitHub, notify Fluxer webhook.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TAG="${1:-v1.1.4}"
REPO="flxselfbot/FLX-FLUXER-SELFBOT"
DIST="${ROOT}/dist/mobile-release"
WEBHOOK_FILE="${HOME}/Library/Application Support/Flx/releases_webhook.url"

cd "$ROOT"
mkdir -p "$DIST"

echo "=== Building iOS ==="
bash scripts/build_ios.sh
bash scripts/export_ipa.sh
cp "${HOME}/Desktop/FLX.ipa" "${DIST}/FLX-iOS.ipa"

echo "=== Building Android ==="
bash scripts/build_android.sh
APK="$(find "${ROOT}/dist" -name 'FLX-*.apk' | head -1)"
if [[ -z "$APK" || ! -f "$APK" ]]; then
  APK="${HOME}/Desktop/FLX.apk"
fi
cp "$APK" "${DIST}/FLX-Android.apk"

_github_token() {
  printf "protocol=https\nhost=github.com\n\n" | git credential fill 2>/dev/null | awk -F= '/^password=/{print $2}'
}

_wait_release() {
  local token="$1" attempt=0 id=""
  while [[ $attempt -lt 90 ]]; do
    id="$(curl -s -H "Authorization: Bearer $token" -H "Accept: application/vnd.github+json" \
      "https://api.github.com/repos/${REPO}/releases/tags/${TAG}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id') or '')" 2>/dev/null || true)"
    if [[ -n "$id" && "$id" != "None" ]]; then
      echo "$id"
      return 0
    fi
    sleep 20
    attempt=$((attempt + 1))
  done
  return 1
}

_upload_asset() {
  local token="$1" release_id="$2" file="$3"
  local name size ct
  name="$(basename "$file")"
  size="$(wc -c < "$file" | tr -d ' ')"
  case "$name" in
    *.ipa) ct="application/octet-stream" ;;
    *.apk) ct="application/vnd.android.package-archive" ;;
    *) ct="application/octet-stream" ;;
  esac
  curl -s -X POST \
    -H "Authorization: Bearer $token" \
    -H "Accept: application/vnd.github+json" \
    -H "Content-Type: $ct" \
    --data-binary @"$file" \
    "https://uploads.github.com/repos/${REPO}/releases/${release_id}/assets?name=${name}&label=${name}" \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('browser_download_url') or d.get('message','uploaded'))"
}

TOKEN="$(_github_token)"
if [[ -z "$TOKEN" ]]; then
  echo "No GitHub token from git credential."
  exit 1
fi

RELEASE_ID="$(_wait_release "$TOKEN" || true)"
if [[ -z "$RELEASE_ID" ]]; then
  echo "Release ${TAG} not found yet — creating draft release for mobile assets."
  RELEASE_ID="$(curl -s -X POST \
    -H "Authorization: Bearer $TOKEN" \
    -H "Accept: application/vnd.github+json" \
    -d "{\"tag_name\":\"${TAG}\",\"name\":\"FLX ${TAG}\",\"body\":\"iOS and Android builds — sideload FLX-iOS.ipa or install FLX-Android.apk.\",\"draft\":false,\"prerelease\":false}" \
    "https://api.github.com/repos/${REPO}/releases" \
    | python3 -c "import sys,json; print(json.load(sys.stdin).get('id') or '')")"
fi

if [[ -z "$RELEASE_ID" ]]; then
  echo "Could not find or create GitHub release ${TAG}."
  exit 1
fi

echo "=== Uploading mobile assets to release ${TAG} (id ${RELEASE_ID}) ==="
_upload_asset "$TOKEN" "$RELEASE_ID" "${DIST}/FLX-iOS.ipa"
_upload_asset "$TOKEN" "$RELEASE_ID" "${DIST}/FLX-Android.apk"

RELEASE_URL="https://github.com/${REPO}/releases/tag/${TAG}"
echo "Release: ${RELEASE_URL}"

if [[ -f "$WEBHOOK_FILE" ]]; then
  echo "=== Posting to Fluxer webhook ==="
  export FLUXER_RELEASES_WEBHOOK_URL="$(cat "$WEBHOOK_FILE")"
  export RELEASE_TAG="$TAG"
  export RELEASE_NAME="FLX ${TAG}"
  export RELEASE_URL="$RELEASE_URL"
  export RELEASE_BODY="iOS and Android client builds are live. Download FLX-iOS.ipa or FLX-Android.apk from GitHub Releases."
  export RELEASE_CONTENT="NEW CLIENT, we have now support for ios and android devices!"
  export GITHUB_REPOSITORY="$REPO"
  python3 scripts/notify_fluxer_release.py
else
  echo "No webhook file at ${WEBHOOK_FILE} — skip notify."
fi

echo "Done. Mobile builds uploaded to ${RELEASE_URL}"
