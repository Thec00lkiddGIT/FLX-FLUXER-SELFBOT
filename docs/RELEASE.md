# Shipping a new FLX version

## Build on your machine

**macOS**

```bash
bash scripts/build_mac.sh
```

You get `dist/FLX-macOS.zip` with `FLX.app` inside.

**Windows** (on a Windows PC)

```bat
scripts\build_windows.bat
```

You get `dist/FLX-Windows.zip`.

**DMG (Mac only, optional)**

```bash
bash scripts/make_mac_dmg.sh
```

Puts `dist/FLX-<version>-macOS.dmg` in `dist/` — handy for dragging into Applications.

## Let GitHub Actions do it

Tag and push:

```bash
git tag v1.0.8 && git push origin v1.0.8
```

Or: **Actions** → **Release** → **Run workflow** and type the tag (e.g. `v1.0.8`).

CI uploads `FLX-macOS.zip`, `FLX-Windows.zip`, and `FLX-ChromeOS.zip`, creates the GitHub release, and posts to your Fluxer `#releases` webhook (if the secret is set).

## Fluxer `#releases` webhook

When a release goes live, the workflow posts to your **updates** webhook in `#releases`.

**One-time setup:**

```bash
gh secret set FLUXER_RELEASES_WEBHOOK_URL < "$HOME/Library/Application Support/Flx/releases_webhook.url"
```

That URL is saved locally when you set up the channel — don't commit it.

**Add a Windows zip to an existing release:**

```bash
gh release upload v1.0.8 dist/FLX-Windows.zip
```
