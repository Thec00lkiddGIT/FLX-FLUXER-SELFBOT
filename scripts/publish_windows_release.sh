#!/usr/bin/env bash
# Push Windows CI workflow, run build, upload exe zip to GitHub release v1.0.0
set -euo pipefail
cd "$(dirname "$0")/.."

echo "Checking GitHub workflow scope..."
if ! gh auth status 2>&1 | grep -q workflow; then
  echo "Grant workflow scope (required once):"
  echo "  gh auth refresh -h github.com -s workflow"
  gh auth refresh -h github.com -s workflow
fi

mkdir -p .github/workflows
cp docs/github-release-workflow.yml .github/workflows/release.yml
cp .github/workflows/windows-release.yml .github/workflows/windows-release.yml 2>/dev/null || true

if [ ! -f .github/workflows/windows-release.yml ]; then
  echo "Missing .github/workflows/windows-release.yml"
  exit 1
fi

git add .github/workflows/
git commit -m "Add Windows release CI workflow." || true
git push origin main

echo "Starting Windows build on GitHub Actions..."
gh workflow run windows-release.yml

RUN_ID=$(gh run list --workflow=windows-release.yml --limit 1 --json databaseId --jq '.[0].databaseId')
echo "Run: https://github.com/$(gh repo view --json nameWithOwner -q .nameWithOwner)/actions/runs/$RUN_ID"
gh run watch "$RUN_ID" --exit-status

TMP=$(mktemp -d)
gh run download "$RUN_ID" -D "$TMP" || true
ZIP=$(find "$TMP" -name '*.zip' | head -1)
if [ -n "$ZIP" ]; then
  gh release upload v1.0.0 "$ZIP" --clobber
  echo "Uploaded to https://github.com/$(gh repo view --json nameWithOwner -q .nameWithOwner)/releases/tag/v1.0.0"
else
  echo "Download artifact manually from the Actions run."
fi
