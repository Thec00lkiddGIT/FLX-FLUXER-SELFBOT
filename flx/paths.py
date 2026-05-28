"""User-writable paths (Application Support / AppData) vs bundled app files."""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

APP_NAME = "Flx"
DEFAULT_ENV = """# Fluxer selfbot config (edit these values)
# Created automatically on first launch.

FLUXER_TOKEN=
FLUXER_API_URL=https://api.fluxer.app
PREFIX=!

# Optional API keys (only needed for matching commands)
C99_WEATHER_KEY=
GLSERIES_TOKEN=
GLSERIES_BASE_URL=https://live.glseries.net/api/v1
API_NINJAS_KEY=
SERPAPI_KEY=
OSINT_INDUSTRIES_KEY=

# Poof.bg (!poof) - https://docs.poof.bg
POOF_API_KEY=
"""


def project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    return Path(__file__).resolve().parents[1]


def app_support_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base / APP_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    return Path.home() / ".config" / APP_NAME


def ensure_app_support() -> Path:
    support = app_support_dir()
    support.mkdir(parents=True, exist_ok=True)
    return support


def env_file() -> Path:
    return ensure_app_support() / "config.env"


def ensure_env_file() -> Path:
    ensure_app_support()
    path = env_file()
    if path.exists():
        return path

    example = project_root() / ".env.example"
    if example.is_file():
        path.write_text(example.read_text(encoding="utf-8"))
    else:
        path.write_text(DEFAULT_ENV, encoding="utf-8")
    return path


def stats_file() -> Path:
    return ensure_app_support() / ".gui_stats.json"


def gui_settings_file() -> Path:
    return ensure_app_support() / ".gui_settings.json"


def hub_dir() -> Path:
    return ensure_app_support() / "scripts" / "hub"


def bundled_hub_dir() -> Path | None:
    root = project_root() / "scripts" / "hub"
    return root if root.is_dir() else None


def bundled_community_dir() -> Path | None:
    root = project_root() / "scripts" / "community"
    return root if root.is_dir() else None


def _hub_commands(entries: list[dict]) -> set[str]:
    names: set[str] = set()
    for entry in entries:
        cmd = str(entry.get("command") or "").strip().lower()
        if cmd:
            names.add(cmd)
        for c in entry.get("commands") or []:
            if c:
                names.add(str(c).strip().lower())
    return names


def _read_hub_manifest(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    scripts = data.get("scripts")
    return list(scripts) if isinstance(scripts, list) else []


def _write_hub_manifest(path: Path, scripts: list[dict]) -> None:
    path.write_text(json.dumps({"scripts": scripts}, indent=2) + "\n", encoding="utf-8")


def _copy_bundled_tree(bundled: Path, hub: Path) -> None:
    for item in bundled.iterdir():
        dest = hub / item.name
        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dest)


def _merge_bundled_scripts(hub: Path, bundled: Path) -> None:
    manifest = hub / "manifest.json"
    user_scripts = _read_hub_manifest(manifest)
    user_ids = {str(s.get("id")) for s in user_scripts if s.get("id")}
    user_commands = _hub_commands(user_scripts)

    bundled_scripts = _read_hub_manifest(bundled / "manifest.json")
    if not bundled_scripts:
        return

    added = False
    for entry in bundled_scripts:
        sid = str(entry.get("id") or "").strip()
        if not sid or sid in user_ids:
            continue
        cmds = _hub_commands([entry])
        if cmds & user_commands:
            continue
        src = bundled / f"{sid}.py"
        if not src.is_file():
            continue
        shutil.copy2(src, hub / f"{sid}.py")
        user_scripts.append(entry)
        user_ids.add(sid)
        user_commands |= cmds
        added = True

    if added or not manifest.is_file():
        _write_hub_manifest(manifest, user_scripts)


def ensure_script_hub() -> Path:
    hub = hub_dir()
    hub.mkdir(parents=True, exist_ok=True)
    (hub / "json").mkdir(parents=True, exist_ok=True)
    manifest = hub / "manifest.json"
    bundled = bundled_hub_dir()

    if not manifest.is_file():
        if bundled:
            _copy_bundled_tree(bundled, hub)
        else:
            _write_hub_manifest(manifest, [])
    elif bundled:
        _merge_bundled_scripts(hub, bundled)

    return hub


def open_env_in_editor() -> bool:
    import subprocess

    path = ensure_env_file()
    try:
        if sys.platform == "win32":
            os.startfile(str(path))  # noqa: S606
            return True
        if sys.platform == "darwin":
            subprocess.run(["open", "-e", str(path)], check=False)
            return True
        subprocess.run(["xdg-open", str(path)], check=False)
        return True
    except OSError:
        return False
