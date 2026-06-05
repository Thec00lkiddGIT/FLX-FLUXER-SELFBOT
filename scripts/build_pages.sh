#!/usr/bin/env bash
# Build static GitHub Pages site into docs/ from the FLX dashboard UI.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DOCS="${ROOT}/docs"
STATIC_SRC="${ROOT}/flx/gui/static"

rm -rf "${DOCS}/static"
mkdir -p "${DOCS}/static"

cp "${STATIC_SRC}/app.css" "${STATIC_SRC}/app.js" "${STATIC_SRC}/icon.png" "${DOCS}/static/"
cp "${ROOT}/scripts/pages/demo-data.js" "${DOCS}/static/demo-data.js"
touch "${DOCS}/.nojekyll"

python3 - "$ROOT" <<'PY'
import sys
from pathlib import Path

root = Path(sys.argv[1])
src = (root / "flx/gui/static/index.html").read_text(encoding="utf-8")
src = src.replace('href="/static/', 'href="./static/')
src = src.replace('src="/static/', 'src="./static/')

banner = """  <div class="pages-demo-banner glass" role="status">
    <strong>Live preview</strong> — FLX dashboard on GitHub Pages.
    <a href="https://github.com/Thec00lkiddGIT/FLX-FLUXER-SELFBOT">Get FLX</a> to run the real bot.
  </div>
"""
inject = """  <script>window.FLX_DEMO = true;</script>
  <script src="./static/demo-data.js"></script>
"""
src = src.replace("<body>", "<body>\n" + banner, 1)
src = src.replace("</body>", inject + "</body>", 1)
(root / "docs/index.html").write_text(src, encoding="utf-8")
print(f"Wrote {root / 'docs/index.html'}")
PY

echo "GitHub Pages build ready in ${DOCS}"
