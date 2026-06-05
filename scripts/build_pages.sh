#!/usr/bin/env bash
# Build GitHub Pages marketing site into docs/ (Nighty-style landing page).

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DOCS="${ROOT}/docs"
PAGES="${ROOT}/pages"
ASSETS="${ROOT}/assets"

mkdir -p "${DOCS}/static"

cp "${PAGES}/index.html" "${DOCS}/index.html"
cp "${PAGES}/landing.css" "${DOCS}/static/landing.css"
cp "${ASSETS}/icon.png" "${DOCS}/static/icon.png"
touch "${DOCS}/.nojekyll"

# Remove old dashboard demo artifacts if present
rm -f "${DOCS}/static/app.js" "${DOCS}/static/app.css" "${DOCS}/static/demo-data.js"

echo "GitHub Pages landing site ready in ${DOCS}"
