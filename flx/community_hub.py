"""Community Script Hub - read-only bundled scripts (install to personal hub only)."""

COMMUNITY_READONLY = True

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

from flx.script_hub import (
    HubScript,
    _hub_script_from_raw,
    _now_iso,
    read_script_code,
    save_script,
    validate_code,
    validate_command_name,
)
from flx.paths import bundled_community_dir, ensure_script_hub

COMMAND_RE = re.compile(r"^[a-z][a-z0-9_]{1,31}$")


def _copy_bundled_community(bundled: Path, dest: Path) -> None:
    import shutil

    for item in bundled.iterdir():
        target = dest / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target)


def _sync_community_from_bundled(community: Path, bundled: Path) -> None:
    """Replace local community hub with bundled scripts only (no user uploads)."""
    import shutil

    if not bundled.is_dir():
        _save_manifest_to(community / "manifest.json", [])
        return

    bundled_scripts = _load_manifest_from(bundled / "manifest.json")
    allowed_ids = {str(e.get("id") or "").strip() for e in bundled_scripts if e.get("id")}

    for py in community.glob("*.py"):
        if py.stem not in allowed_ids:
            py.unlink(missing_ok=True)

    _copy_bundled_community(bundled, community)
    _save_manifest_to(community / "manifest.json", bundled_scripts)


def _load_manifest_from(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    scripts = data.get("scripts")
    return scripts if isinstance(scripts, list) else []


def _save_manifest_to(path: Path, scripts: list[dict]) -> None:
    path.write_text(json.dumps({"scripts": scripts}, indent=2) + "\n", encoding="utf-8")


def ensure_community_hub() -> Path:
    community = ensure_script_hub() / "community"
    community.mkdir(parents=True, exist_ok=True)
    bundled = bundled_community_dir()
    manifest = community / "manifest.json"
    if bundled:
        _sync_community_from_bundled(community, bundled)
    elif not manifest.is_file():
        _save_manifest_to(manifest, [])
    return community


def community_writes_allowed() -> bool:
    return not COMMUNITY_READONLY


def _community_dir() -> Path:
    return ensure_community_hub()


def _manifest_path() -> Path:
    return _community_dir() / "manifest.json"


def _load_manifest() -> list[dict]:
    path = _manifest_path()
    if not path.is_file():
        path.write_text(json.dumps({"scripts": []}, indent=2) + "\n")
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return []
    scripts = data.get("scripts")
    return scripts if isinstance(scripts, list) else []


def _save_manifest(scripts: list[dict]) -> None:
    _manifest_path().write_text(json.dumps({"scripts": scripts}, indent=2) + "\n")


def _script_path(script_id: str) -> Path:
    safe = re.sub(r"[^a-zA-Z0-9_-]", "", script_id)
    return _community_dir() / f"{safe}.py"


def _validate_community_command(command: str, *, exclude_id: str | None = None) -> str | None:
    name = command.strip().lower()
    if not COMMAND_RE.match(name):
        return "Command must be 2-32 chars: lowercase letters, digits, underscore; start with a letter."
    for entry in _load_manifest():
        if entry.get("id") == exclude_id:
            continue
        cmds = entry.get("commands") or [entry.get("command")]
        if name in {str(c).lower() for c in cmds if c}:
            return f"!{name} is already used by another community script."
    return None


def list_community_scripts() -> list[HubScript]:
    scripts: list[HubScript] = []
    for raw in _load_manifest():
        script = _hub_script_from_raw(raw)
        if script:
            scripts.append(script)
    scripts.sort(key=lambda s: s.name.lower())
    return scripts


def community_script_dict(script: HubScript) -> dict:
    raw = next((e for e in _load_manifest() if e.get("id") == script.id), {})
    data = script.to_dict()
    data["submitted_by"] = str(raw.get("submitted_by") or "")
    data["code"] = read_community_code(script.id)
    return data


def read_community_code(script_id: str) -> str:
    path = _script_path(script_id)
    if path.is_file():
        return path.read_text()
    return ""


def save_community_script(
    *,
    script_id: str | None,
    name: str,
    author: str,
    description: str,
    usage: str,
    command: str,
    help_text: str,
    code: str,
    submitted_by: str = "",
) -> tuple[HubScript | None, str | None]:
    if COMMUNITY_READONLY:
        return None, "Community scripts are read-only. Use Add to Script Hub to install them locally."

    from flx.script_hub import _extract_commands_from_code

    sid = script_id or uuid.uuid4().hex[:12]
    err = validate_code(code, script_id=sid)
    if err:
        return None, err

    commands, load_err = _extract_commands_from_code(code, sid)
    if load_err:
        return None, load_err

    primary = command.strip().lower() or (commands[0] if commands else "")
    if not commands and primary:
        err = _validate_community_command(primary, exclude_id=sid)
        if err:
            return None, err
        commands = [primary]
    elif commands:
        for cmd in commands:
            err = _validate_community_command(cmd, exclude_id=sid)
            if err and cmd != primary:
                return None, err
            if err and not script_id:
                return None, err
    else:
        return None, "No commands found. Add @bot.command or a legacy run(args) function."

    if primary and primary not in commands:
        primary = commands[0]

    manifest = _load_manifest()
    now = _now_iso()
    entry = next((e for e in manifest if e.get("id") == sid), None)
    if entry is None:
        entry = {"id": sid, "created": now, "format": "flxscript"}
        manifest.append(entry)

    entry["name"] = name.strip() or primary
    entry["author"] = author.strip() or "Community"
    entry["description"] = description.strip() or help_text.strip()
    entry["usage"] = usage.strip() or f"!{primary}"
    entry["command"] = primary
    entry["help"] = help_text.strip() or entry["description"]
    entry["commands"] = commands
    entry["enabled"] = True
    entry["updated"] = now
    if submitted_by.strip():
        entry["submitted_by"] = submitted_by.strip()

    _script_path(sid).write_text(code if code.endswith("\n") else code + "\n")
    _save_manifest(manifest)

    return _hub_script_from_raw(entry), None


def delete_community_script(script_id: str) -> bool:
    if COMMUNITY_READONLY:
        return False
    manifest = _load_manifest()
    new_manifest = [s for s in manifest if s.get("id") != script_id]
    if len(new_manifest) == len(manifest):
        return False
    _script_path(script_id).unlink(missing_ok=True)
    _save_manifest(new_manifest)
    return True


def import_community_to_hub(community_id: str) -> tuple[HubScript | None, str | None]:
    raw = next((e for e in _load_manifest() if e.get("id") == community_id), None)
    if raw is None:
        return None, "Community script not found."

    script = _hub_script_from_raw(raw)
    if script is None:
        return None, "Invalid community script entry."

    code = read_community_code(community_id)
    if not code.strip():
        return None, "Community script file is missing."

    primary = script.command
    err = validate_command_name(primary)
    if err:
        return None, f"Cannot add to Script Hub: {err} Pick a different script or edit the command first."

    return save_script(
        script_id=None,
        name=script.name,
        author=script.author,
        description=script.description,
        usage=script.usage,
        command=primary,
        help_text=script.help,
        code=code,
        enabled=True,
    )
