"""User-writable paths (Application Support / AppData) vs bundled app files."""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

APP_NAME = "Flx"
DEFAULT_ENV = """# FLX config — fill in what you need below.
# This file was created on first launch.

FLUXER_TOKEN=
FLUXER_API_URL=https://api.fluxer.app
PREFIX=!

# Optional keys (only for commands that use them)
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


_LEGACY_HUB_IDS = frozenset({"echo", "httpcat", "pokemon", "check"})
_HUB_MIGRATION_MARKER = ".personal_hub_migrated_v2"
_BUNDLED_SEED_MARKER = ".personal_hub_bundled_v1_1_0"


def _prune_orphan_hub_py(hub: Path, scripts: list[dict]) -> None:
    allowed = {str(entry.get("id") or "").strip() for entry in scripts}
    allowed.discard("")
    for py in hub.glob("*.py"):
        if py.stem not in allowed:
            py.unlink(missing_ok=True)


def _migrate_legacy_personal_scripts(hub: Path, manifest: Path) -> None:
    """One-time: remove old built-ins that moved to the community hub."""
    marker = hub / _HUB_MIGRATION_MARKER
    if marker.is_file():
        return
    scripts = _read_hub_manifest(manifest)
    kept = [e for e in scripts if str(e.get("id") or "").strip() not in _LEGACY_HUB_IDS]
    for legacy_id in _LEGACY_HUB_IDS:
        (hub / f"{legacy_id}.py").unlink(missing_ok=True)
    if len(kept) != len(scripts):
        _write_hub_manifest(manifest, kept)
    marker.write_text("1\n", encoding="utf-8")


def _seed_missing_bundled_scripts(hub: Path, bundled: Path | None) -> None:
    """Until Community tab is fixed: ensure bundled hub scripts exist in My Scripts."""
    if not bundled or not bundled.is_dir():
        return
    marker = hub / _BUNDLED_SEED_MARKER
    if marker.is_file():
        return
    manifest = hub / "manifest.json"
    if not manifest.is_file():
        return
    personal = _read_hub_manifest(manifest)
    existing_ids = {str(e.get("id") or "").strip() for e in personal}
    bundled_scripts = _read_hub_manifest(bundled / "manifest.json")
    added = False
    for entry in bundled_scripts:
        sid = str(entry.get("id") or "").strip()
        if not sid or sid in existing_ids:
            continue
        src = bundled / f"{sid}.py"
        if src.is_file():
            shutil.copy2(src, hub / f"{sid}.py")
        personal.append(dict(entry))
        existing_ids.add(sid)
        added = True
    if added:
        _write_hub_manifest(manifest, personal)
    marker.write_text("1\n", encoding="utf-8")


def _sync_personal_hub(hub: Path, bundled: Path | None) -> None:
    """Seed an empty personal hub on first launch; keep user-installed scripts after that."""
    manifest = hub / "manifest.json"
    if manifest.is_file():
        _migrate_legacy_personal_scripts(hub, manifest)
        _seed_missing_bundled_scripts(hub, bundled)
        _prune_orphan_hub_py(hub, _read_hub_manifest(manifest))
        return

    scripts: list[dict] = []
    if bundled and bundled.is_dir():
        scripts = _read_hub_manifest(bundled / "manifest.json")
        for entry in scripts:
            sid = str(entry.get("id") or "").strip()
            if not sid:
                continue
            src = bundled / f"{sid}.py"
            if src.is_file():
                shutil.copy2(src, hub / f"{sid}.py")
    _write_hub_manifest(manifest, scripts)
    (hub / _HUB_MIGRATION_MARKER).write_text("1\n", encoding="utf-8")
    (hub / _BUNDLED_SEED_MARKER).write_text("1\n", encoding="utf-8")


def ensure_script_hub() -> Path:
    hub = hub_dir()
    hub.mkdir(parents=True, exist_ok=True)
    (hub / "json").mkdir(parents=True, exist_ok=True)
    bundled = bundled_hub_dir()
    if bundled and not (hub / "manifest.json").is_file():
        _copy_bundled_tree(bundled, hub)
    _sync_personal_hub(hub, bundled)

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
