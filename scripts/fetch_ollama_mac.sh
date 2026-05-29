#!/usr/bin/env bash
# Download Ollama zip for FLX twin (DMG sidecar + in-app zip; do NOT pack .app into PyInstaller).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/scripts/ollama"
ZIP="$DEST/Ollama-darwin.zip"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "fetch_ollama_mac.sh is for macOS builds only." >&2
  exit 1
fi

mkdir -p "$DEST"
if [[ -f "$ZIP" ]]; then
  echo "Already have $ZIP"
else
  echo "Downloading Ollama for macOS…"
  curl -fsSL --progress-bar -o "$ZIP" "https://ollama.com/download/Ollama-darwin.zip"
  echo "Saved: $ZIP"
fi

# Optional dev unpack: UNZIP=1 bash scripts/fetch_ollama_mac.sh
if [[ "${UNZIP:-}" == "1" ]] && [[ ! -d "$DEST/Ollama.app" ]]; then
  unzip -q -o "$ZIP" -d "$DEST"
  echo "Unpacked: $DEST/Ollama.app"
fi
