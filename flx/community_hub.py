"""Community Script Hub - read-only bundled scripts (install to personal hub only)."""

from __future__ import annotations

COMMUNITY_READONLY = True

import json
import re
import uuid
from pathlib import Path

from flx.script_hub import (
    HubScript,
    _hub_script_from_raw,
    _load_manifest as _load_personal_manifest,
    _now_iso,
    _save_manifest as _save_personal_manifest,
    _script_path as _personal_script_path,
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


def _ensure_community_py_files(community: Path, bundled: Path, scripts: list[dict]) -> None:
    """Make sure every manifest entry has a .py on disk (fixes empty editor in packaged builds)."""
    import shutil

    for entry in scripts:
        sid = re.sub(r"[^a-zA-Z0-9_-]", "", str(entry.get("id") or ""))
        if not sid:
            continue
        src = bundled / f"{sid}.py"
        dest = community / f"{sid}.py"
        if src.is_file() and (not dest.is_file() or dest.stat().st_size == 0):
            shutil.copy2(src, dest)


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
    _ensure_community_py_files(community, bundled, bundled_scripts)
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
    safe = re.sub(r"[^a-zA-Z0-9_-]", "", script_id)
    if not safe:
        return ""

    candidates: list[Path] = []
    bundled = bundled_community_dir()
    if bundled:
        candidates.append(bundled / f"{safe}.py")
    candidates.append(_community_dir() / f"{safe}.py")

    for path in candidates:
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if text.strip():
            return text
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
        return None, "Community scripts can't be edited here — use Add to my scripts instead."

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


def _command_names(entry: dict) -> set[str]:
    names: set[str] = set()
    for c in entry.get("commands") or [entry.get("command")]:
        if c:
            names.add(str(c).strip().lower())
    return names


def _clear_personal_hub_slots(community_id: str, command_names: set[str]) -> None:
    """Drop old My-scripts copies that block installing a community script (!echo x2, etc.)."""
    if not command_names:
        return
    kept: list[dict] = []
    for entry in _load_personal_manifest():
        eid = str(entry.get("id") or "").strip()
        cmds = _command_names(entry)
        if eid == community_id or cmds & command_names:
            _personal_script_path(eid).unlink(missing_ok=True)
            continue
        kept.append(entry)
    _save_personal_manifest(kept)


def import_community_to_hub(
    community_id: str,
    *,
    code: str | None = None,
) -> tuple[HubScript | None, str | None]:
    raw = next((e for e in _load_manifest() if e.get("id") == community_id), None)
    if raw is None:
        return None, "Couldn't find that community script."

    script = _hub_script_from_raw(raw)
    if script is None:
        return None, "That script entry looks broken — sorry about that."

    body = read_community_code(community_id).strip()
    if not body:
        body = (code or "").strip()
    if not body:
        return None, "The script file is missing on disk."

    from flx.script_hub import _extract_commands_from_code

    commands, load_err = _extract_commands_from_code(body, community_id)
    if load_err:
        return None, load_err

    primary = (script.command or "").strip().lower()
    if not primary and commands:
        primary = commands[0]
    cmd_set = {primary} if primary else set()
    cmd_set.update(commands)

    _clear_personal_hub_slots(community_id, cmd_set)

    if primary:
        err = validate_command_name(primary, exclude_id=community_id)
        if err:
            return None, f"Can't add this one: {err} Try another script or rename the command."

    return save_script(
        script_id=community_id,
        name=script.name,
        author=script.author,
        description=script.description,
        usage=script.usage,
        command=primary or (commands[0] if commands else ""),
        help_text=script.help,
        code=body,
        enabled=True,
    )
