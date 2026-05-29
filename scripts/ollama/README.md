# Ollama twin (bundled with FLX)

macOS builds download `Ollama-darwin.zip` here via `scripts/fetch_ollama_mac.sh`.

- **PyInstaller** embeds only the zip (nested `Ollama.app` breaks codesign).
- **DMG** also includes `Ollama.app` beside `FLX.app` — drag both to Applications.
- **First launch**, FLX extracts the zip to Application Support if needed, starts Ollama, and pulls `llama3.2`.

Dev unpack: `UNZIP=1 bash scripts/fetch_ollama_mac.sh`

Large files are gitignored. CI and `scripts/build_mac.sh` fetch the zip automatically.
