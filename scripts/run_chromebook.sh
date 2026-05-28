#!/usr/bin/env bash
# Chromebook / Linux: open the dashboard in Chrome (recommended on ChromeOS).
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"
exec ./FLX-FLUXER-SELFBOT --chromebook "$@"
