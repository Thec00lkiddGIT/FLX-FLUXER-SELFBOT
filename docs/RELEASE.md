# Release builds

## macOS (local or CI)

```bash
bash scripts/build_mac.sh
```

Output: `dist/FLX-macOS.zip` (contains `FLX.app`)

## Windows (local or CI)

On a Windows machine:

```bat
scripts\build_windows.bat
```

Output: `dist\FLX-Windows.zip`

## GitHub Actions (all platforms)

1. Tag a release: `git tag v1.0.4 && git push origin v1.0.4`

Or: **Actions** -> **Release** -> **Run workflow** -> version `v1.0.4`

CI uploads: `FLX-macOS.zip`, `FLX-Windows.zip`, `FLX-ChromeOS.zip`

## Fluxer #releases webhook (automated)

When a GitHub release is **published**, `.github/workflows/fluxer-release-notify.yml` posts to the **updates** webhook in `#releases`.

**One-time GitHub secret** (after creating the webhook in `#releases`):

```bash
gh secret set FLUXER_RELEASES_WEBHOOK_URL < "$HOME/Library/Application Support/Flx/releases_webhook.url"
```

The webhook URL is also saved locally at `~/Library/Application Support/Flx/releases_webhook.url` when you run the setup script (do not commit this file).

Upload a Windows zip to an existing release:

```bash
gh release upload v1.0.4 dist/FLX-Windows.zip
```
