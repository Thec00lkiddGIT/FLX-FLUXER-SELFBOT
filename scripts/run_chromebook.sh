#!/usr/bin/env bash
# Run FLX in Chromebook / Linux browser mode (from extracted zip).
set -euo pipefail
cd "$(dirname "$0")"
exec ./FLX --chromebook "$@"
