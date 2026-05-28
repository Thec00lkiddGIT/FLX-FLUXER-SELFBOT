# Release builds

## macOS (local or CI)

```bash
bash scripts/build_mac.sh
```

Output: `dist/FLX-FLUXER-SELFBOT-macOS.zip`

## Windows (local or CI)

On a Windows machine:

```bat
scripts\build_windows.bat
```

Output: `dist\FLX-FLUXER-SELFBOT-Windows.zip`

## GitHub Actions (both platforms)

1. Copy `docs/github-release-workflow.yml` to `.github/workflows/release.yml` on GitHub (web UI), **or** run `gh auth refresh -h github.com -s workflow` then `git push origin main`
2. Tag a release: `git tag v1.0.3 && git push origin v1.0.3`

Or: **Actions** -> **Release** -> **Run workflow** -> version `v1.0.3`

CI uploads all three zips: macOS, Windows, and ChromeOS.

Upload a Windows zip to an existing release:

```bash
gh release upload v1.0.0 dist/FLX-FLUXER-SELFBOT-Windows.zip
```
