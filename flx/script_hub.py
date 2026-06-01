"""Load, save, and run Script Hub scripts (FlxScript / legacy run())."""

from __future__ import annotations

import importlib.util
import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from flx.command_catalog import all_builtin_command_names
from flx.fluxerscript import (
    CommandContext,
    FlxMessage,
    ScriptBot,
    ScriptMeta,
    forwardEmbedMethod,
    getConfigData,
    getScriptsPath,
    flxScript,
    log,
    set_script_context,
    updateConfigData,
)

from flx.paths import ensure_script_hub

COMMAND_RE = re.compile(r"^[a-z][a-z0-9_]{1,31}$")
_BOT_COMMAND_NAME_RE = re.compile(
    r"@bot\.command\s*\([^)]*name\s*=\s*[\"']([a-z][a-z0-9_]*)[\"']",
    re.IGNORECASE,
)
_SCRIPT_NO_COMMANDS_MSG = (
    "No commands registered. Use @flxScript + @bot.command inside a setup function, "
    "then call that function at the bottom (e.g. my_script()). "
    "Check for typos in @bot.command(name=\"...\")."
)
_BUILTIN_NAMES_CACHE: frozenset[str] | None = None
_REGISTRY_LOADING = False
_INJECT_ACTIVE = False


def _builtin_names() -> frozenset[str]:
    global _BUILTIN_NAMES_CACHE
    if _BUILTIN_NAMES_CACHE is None:
        _BUILTIN_NAMES_CACHE = all_builtin_command_names()
    return _BUILTIN_NAMES_CACHE


def _hub() -> Path:
    return ensure_script_hub()


def _manifest() -> Path:
    return _hub() / "manifest.json"

SCRIPT_TEMPLATE = '''"""FlxScript hub script for Fluxer."""

from flx.fluxerscript import (
    forwardEmbedMethod,
    getConfigData,
    getScriptsPath,
    flxScript,
    log,
    updateConfigData,
)


@flxScript(
    name="{name}",
    author="{author}",
    description="{description}",
    usage="{usage}",
)
def {entry_fn}():
    """
    {name}
    ----------

    {description}

    COMMANDS:
    !{command} <args> - {description}

    EXAMPLES:
    !{command} hello - Example usage
    """

    @bot.command(name="{command}", description="{description}")
    def {command}_handler(ctx, *, args: str):
        if not args:
            ctx.send("Usage: !{command} <text>")
            return
        ctx.send(f"You said: {{args}}")
        log("Handled !{command}", type_="INFO")


{entry_fn}()  # IMPORTANT: call to register commands
'''

_registry_mtime: float = 0.0
_registry_bots: dict[str, ScriptBot] = {}
_registry_commands: dict[str, tuple[str, ScriptBot]] = {}  # cmd -> (script_id, bot)
_registry_meta: dict[str, ScriptMeta] = {}


@dataclass
class HubScript:
    id: str
    name: str
    author: str
    description: str
    usage: str
    command: str
    help: str
    commands: list[str] = field(default_factory=list)
    enabled: bool = True
    created: str = ""
    updated: str = ""
    format: str = "flxscript"

    def to_dict(self) -> dict:
        return asdict(self)


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _ensure_hub() -> None:
    hub = _hub()
    (hub / "json").mkdir(parents=True, exist_ok=True)
    manifest = _manifest()
    if not manifest.exists():
        manifest.write_text(json.dumps({"scripts": []}, indent=2) + "\n")


def _load_manifest() -> list[dict]:
    _ensure_hub()
    manifest = _manifest()
    try:
        data = json.loads(manifest.read_text())
    except (json.JSONDecodeError, OSError):
        return []
    scripts = data.get("scripts")
    return scripts if isinstance(scripts, list) else []


def _save_manifest(scripts: list[dict]) -> None:
    _ensure_hub()
    _manifest().write_text(json.dumps({"scripts": scripts}, indent=2) + "\n")


def _script_path(script_id: str) -> Path:
    safe = re.sub(r"[^a-zA-Z0-9_-]", "", script_id)
    return _hub() / f"{safe}.py"


def _manifest_mtime() -> float:
    manifest = _manifest()
    if not manifest.exists():
        return 0.0
    mt = manifest.stat().st_mtime
    for entry in _load_manifest():
        sid = str(entry.get("id", ""))
        p = _script_path(sid)
        if p.is_file():
            mt = max(mt, p.stat().st_mtime)
    return mt


def _entry_fn_name(name: str) -> str:
    base = re.sub(r"[^a-zA-Z0-9_]", "_", name.strip().lower()) or "script"
    if base[0].isdigit():
        base = f"script_{base}"
    return base


def _hub_script_from_raw(raw: dict) -> HubScript | None:
    try:
        commands = raw.get("commands")
        if not isinstance(commands, list):
            commands = [str(raw.get("command", ""))]
        cmd = str(raw.get("command") or (commands[0] if commands else ""))
        desc = str(raw.get("description") or raw.get("help") or "")
        return HubScript(
            id=str(raw["id"]),
            name=str(raw.get("name") or cmd),
            author=str(raw.get("author") or "Flx"),
            description=desc,
            usage=str(raw.get("usage") or f"!{cmd}"),
            command=cmd,
            help=desc or str(raw.get("help", "")),
            commands=[str(c) for c in commands if c],
            enabled=bool(raw.get("enabled", True)),
            created=str(raw.get("created", "")),
            updated=str(raw.get("updated", "")),
            format=str(raw.get("format") or "flxscript"),
        )
    except (KeyError, TypeError):
        return None


def _commands_from_source_regex(code: str) -> list[str]:
    return sorted({m.lower() for m in _BOT_COMMAND_NAME_RE.findall(code)})


def _run_flxscript_setups(module: Any, bot: ScriptBot) -> None:
    """Register @bot.command handlers defined inside @flxScript setup functions."""
    if bot.commands:
        return
    seen: set[int] = set()
    for attr in dir(module):
        if attr.startswith("_"):
            continue
        obj = getattr(module, attr, None)
        meta = getattr(obj, "__flx_script_meta__", None)
        if not meta or not callable(obj):
            continue
        key = id(obj)
        if key in seen:
            continue
        seen.add(key)
        obj()


def _inject_module(script_id: str, path: Path) -> tuple[Any, ScriptBot]:
    global _INJECT_ACTIVE
    if _INJECT_ACTIVE:
        raise RuntimeError(
            "Script tried to load the hub while it was already loading. "
            "Remove top-level save_script / ensure_registry / import cycles."
        )
    _INJECT_ACTIVE = True
    try:
        bot = ScriptBot(script_id)
        module_name = f"flx_hub_{script_id}_{path.stat().st_mtime_ns}"
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise RuntimeError("Could not load script module")

        module = importlib.util.module_from_spec(spec)
        module.__dict__.update(
            {
                "bot": bot,
                "flxScript": flxScript,
                "getConfigData": getConfigData,
                "updateConfigData": updateConfigData,
                "getScriptsPath": getScriptsPath,
                "forwardEmbedMethod": forwardEmbedMethod,
                "log": log,
            }
        )
        set_script_context(script_id)
        try:
            spec.loader.exec_module(module)
            _run_flxscript_setups(module, bot)
        finally:
            set_script_context(None)

        if bot.meta is None:
            for attr in dir(module):
                obj = getattr(module, attr)
                meta = getattr(obj, "__flx_script_meta__", None)
                if meta and callable(obj):
                    bot.meta = ScriptMeta(
                        script_id=script_id,
                        name=str(meta.get("name", script_id)),
                        author=str(meta.get("author", "Flx")),
                        description=str(meta.get("description", "")),
                        usage=str(meta.get("usage", "")),
                    )
                    break

        return module, bot
    finally:
        _INJECT_ACTIVE = False


def reload_registry() -> None:
    global _registry_mtime, _registry_bots, _registry_commands, _registry_meta, _REGISTRY_LOADING
    if _REGISTRY_LOADING:
        return
    _REGISTRY_LOADING = True
    try:
        _registry_bots = {}
        _registry_commands = {}
        _registry_meta = {}

        for raw in _load_manifest():
            script = _hub_script_from_raw(raw)
            if script is None or not script.enabled:
                continue
            path = _script_path(script.id)
            if not path.is_file():
                continue
            try:
                _, bot = _inject_module(script.id, path)
            except Exception:
                continue
            _registry_bots[script.id] = bot
            if bot.meta:
                _registry_meta[script.id] = bot.meta
            for spec in bot.commands.values():
                if spec.script_id != script.id:
                    continue
                _registry_commands[spec.name] = (script.id, bot)
                for alias in spec.aliases:
                    _registry_commands[alias] = (script.id, bot)

        _registry_mtime = _manifest_mtime()
    finally:
        _REGISTRY_LOADING = False


def ensure_registry() -> None:
    if _manifest_mtime() != _registry_mtime:
        reload_registry()


def hub_command_specs() -> list[dict]:
    ensure_registry()
    seen: set[tuple[str, str]] = set()
    out: list[dict] = []
    for bot in _registry_bots.values():
        for spec in bot.commands.values():
            key = (spec.script_id, spec.name)
            if key in seen:
                continue
            seen.add(key)
            out.append(
                {
                    "name": spec.name,
                    "help": spec.description or spec.usage,
                    "script_id": spec.script_id,
                    "aliases": list(spec.aliases),
                }
            )
    out.sort(key=lambda x: x["name"])
    return out


def validate_command_name(command: str, *, exclude_id: str | None = None) -> str | None:
    name = command.strip().lower()
    if not COMMAND_RE.match(name):
        return "Commands need to be 2–32 characters: lowercase letters, numbers, underscore, and they have to start with a letter."
    if name in _builtin_names():
        return f"!{name} is already a built-in command."
    for entry in _load_manifest():
        if entry.get("id") == exclude_id:
            continue
        cmds = entry.get("commands") or [entry.get("command")]
        if name in {str(c).lower() for c in cmds if c}:
            return f"!{name} is already used by another hub script."
    return None


def _extract_commands_from_code(code: str, script_id: str | None) -> tuple[list[str], str | None]:
    import tempfile

    sid = script_id or "_validate"
    if _INJECT_ACTIVE or _REGISTRY_LOADING:
        names = _commands_from_source_regex(code)
        if names:
            return names, None
        if "def run(" in code:
            return [], None
        return [], _SCRIPT_NO_COMMANDS_MSG
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
            tmp.write(code)
            tmp_path = Path(tmp.name)
        _, bot = _inject_module(sid, tmp_path)
    except Exception as exc:
        names = _commands_from_source_regex(code)
        if names:
            return names, None
        return [], str(exc)
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
    names = sorted({s.name for s in bot.commands.values() if s.script_id == sid})
    if names:
        return names, None
    names = _commands_from_source_regex(code)
    if names:
        return names, None
    if "def run(" in code:
        return [], None
    return [], _SCRIPT_NO_COMMANDS_MSG


def validate_code(code: str, *, script_id: str | None = None) -> str | None:
    if not code.strip():
        return "Paste some code first — the file can't be empty."
    try:
        compile(code, "<script>", "exec")
    except SyntaxError as exc:
        return f"Syntax error: {exc.msg} (line {exc.lineno})"
    _, err = _extract_commands_from_code(code, script_id)
    return err


def list_scripts(*, include_disabled: bool = True) -> list[HubScript]:
    scripts: list[HubScript] = []
    for raw in _load_manifest():
        script = _hub_script_from_raw(raw)
        if script is None:
            continue
        if include_disabled or script.enabled:
            scripts.append(script)
    scripts.sort(key=lambda s: s.name.lower())
    return scripts


def get_script_by_command(command: str) -> HubScript | None:
    ensure_registry()
    name = command.strip().lower()
    hit = _registry_commands.get(name)
    if not hit:
        return None
    script_id, _ = hit
    for script in list_scripts():
        if script.id == script_id and script.enabled:
            return script
    return None


def read_script_code(script_id: str) -> str:
    path = _script_path(script_id)
    if path.is_file():
        return path.read_text()
    return ""


def _manifest_ids() -> set[str]:
    return {str(e.get("id") or "").strip() for e in _load_manifest() if e.get("id")}


def _allocate_script_id(preferred: str = "") -> str:
    base = re.sub(r"[^a-z0-9_]", "", preferred.strip().lower())[:32]
    if base and COMMAND_RE.match(base) and base not in _manifest_ids():
        path = _hub() / f"{base}.py"
        if not path.is_file():
            return base
    while True:
        sid = uuid.uuid4().hex[:12]
        if sid not in _manifest_ids():
            return sid


def create_script(
    *,
    name: str = "My Script",
    author: str = "Flx",
    command: str = "mycommand",
    description: str = "My custom command",
    code: str | None = None,
) -> tuple[HubScript | None, str | None]:
    """Create manifest entry and `{id}.py` on disk immediately (New script / import)."""
    tpl = new_script_template(
        name=name,
        author=author,
        command=command,
        description=description,
    )
    sid = _allocate_script_id(str(tpl.get("command") or command))
    body = (code if code is not None else tpl["code"]).strip()
    if not body:
        body = tpl["code"]
    if not body.endswith("\n"):
        body += "\n"

    script, err = save_script(
        script_id=sid,
        name=str(tpl["name"]),
        author=str(tpl["author"]),
        description=str(tpl["description"]),
        usage=str(tpl["usage"]),
        command=str(tpl["command"]),
        help_text=str(tpl["description"]),
        code=body,
        enabled=True,
    )
    if err:
        return None, err
    return script, None


def new_script_template(
    *,
    name: str = "My Script",
    author: str = "Flx",
    command: str = "mycommand",
    description: str = "My custom command",
) -> dict:
    cmd = command.strip().lower() or "mycommand"
    entry = _entry_fn_name(name)
    usage = f"!{cmd} <args>"
    return {
        "id": "",
        "name": name,
        "author": author,
        "description": description,
        "usage": usage,
        "command": cmd,
        "help": description,
        "commands": [cmd],
        "enabled": True,
        "format": "flxscript",
        "code": SCRIPT_TEMPLATE.format(
            name=name,
            author=author,
            description=description.replace('"', '\\"'),
            usage=usage,
            command=cmd,
            entry_fn=entry,
        ),
    }


def save_script(
    *,
    script_id: str | None,
    name: str,
    author: str,
    description: str,
    usage: str,
    command: str,
    help_text: str,
    code: str,
    enabled: bool = True,
) -> tuple[HubScript | None, str | None]:
    sid = script_id or uuid.uuid4().hex[:12]
    err = validate_code(code, script_id=sid)
    if err:
        return None, err

    commands, load_err = _extract_commands_from_code(code, sid)
    if load_err:
        return None, load_err

    primary = command.strip().lower() or (commands[0] if commands else "")
    if not commands and primary:
        err = validate_command_name(primary, exclude_id=sid)
        if err:
            return None, err
        commands = [primary]
    elif commands:
        for cmd in commands:
            err = validate_command_name(cmd, exclude_id=sid)
            if err:
                return None, err
    else:
        return None, "No commands found — add a @bot.command or a run(args) function."

    if primary and primary not in commands:
        primary = commands[0]

    manifest = _load_manifest()
    now = _now_iso()
    entry = next((e for e in manifest if e.get("id") == sid), None)
    if entry is None:
        entry = {"id": sid, "created": now, "format": "flxscript"}
        manifest.append(entry)

    entry["name"] = name.strip() or primary
    entry["author"] = author.strip() or "Flx"
    entry["description"] = description.strip() or help_text.strip()
    entry["usage"] = usage.strip() or f"!{primary}"
    entry["command"] = primary
    entry["help"] = help_text.strip() or entry["description"]
    entry["commands"] = commands
    entry["enabled"] = bool(enabled)
    entry["updated"] = now

    _save_manifest(manifest)
    _script_path(sid).write_text(
        code if code.endswith("\n") else code + "\n",
        encoding="utf-8",
    )
    reload_registry()

    script = _hub_script_from_raw(entry)
    return script, None


def delete_script(script_id: str) -> bool:
    manifest = _load_manifest()
    new_manifest = [s for s in manifest if s.get("id") != script_id]
    if len(new_manifest) == len(manifest):
        return False
    _script_path(script_id).unlink(missing_ok=True)
    _save_manifest(new_manifest)
    reload_registry()
    return True


def set_script_enabled(script_id: str, enabled: bool) -> HubScript | None:
    manifest = _load_manifest()
    for entry in manifest:
        if entry.get("id") == script_id:
            entry["enabled"] = bool(enabled)
            entry["updated"] = _now_iso()
            _save_manifest(manifest)
            reload_registry()
            return _hub_script_from_raw(entry)
    return None


def _run_legacy(script_id: str, args: str) -> str | list[str]:
    path = _script_path(script_id)
    module, _ = _inject_module(script_id, path)
    run_fn = getattr(module, "run", None)
    if not callable(run_fn):
        raise RuntimeError("Legacy script must define run(args)")
    set_script_context(script_id)
    try:
        result = run_fn(args)
    finally:
        set_script_context(None)
    if isinstance(result, str):
        return result
    if isinstance(result, list) and all(isinstance(x, str) for x in result):
        return result
    raise RuntimeError("run(args) must return str or list[str]")


_ASYNC_HANDLER_POOL: object | None = None


def _async_handler_pool():
    global _ASYNC_HANDLER_POOL
    if _ASYNC_HANDLER_POOL is None:
        from concurrent.futures import ThreadPoolExecutor

        _ASYNC_HANDLER_POOL = ThreadPoolExecutor(
            max_workers=4,
            thread_name_prefix="flx-async-cmd",
        )
    return _ASYNC_HANDLER_POOL


def _run_async_handler(handler: Callable[..., Any], ctx: CommandContext, args: str) -> None:
    import asyncio

    coro = handler(ctx, args=args)

    def _thread_main() -> None:
        asyncio.run(coro)

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(coro)
        return

    pool = _async_handler_pool()
    pool.submit(_thread_main).result()


def _resolve_awaitable(value: Any) -> Any:
    import asyncio
    import inspect

    if not inspect.iscoroutine(value):
        return value

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(value)

    def _thread_main() -> Any:
        return asyncio.run(value)

    return _async_handler_pool().submit(_thread_main).result()


def _invoke_listener(handler: Callable[..., Any], message: FlxMessage) -> Any:
    import inspect

    if inspect.iscoroutinefunction(handler):
        return _resolve_awaitable(handler(message))
    result = handler(message)
    return _resolve_awaitable(result)


def _call_handler(handler: Callable[..., Any], ctx: CommandContext, args: str) -> None:
    import inspect

    if inspect.iscoroutinefunction(handler):
        _run_async_handler(handler, ctx, args)
    else:
        handler(ctx, args=args)


def dispatch_hub_command(
    command: str,
    args: str,
    message: FlxMessage,
) -> tuple[str | list[str] | None, bool, list[tuple[str, bytes]]]:
    """Returns (reply payload, delete_invocation, file attachments)."""
    ensure_registry()
    name = command.strip().lower()
    hit = _registry_commands.get(name)
    if hit:
        script_id, bot = hit
        spec = bot.commands.get(name)
        if spec is None:
            return None, False, []
        ctx = CommandContext(
            message=message,
            script_id=script_id,
            command=spec.name,
            args=args,
        )
        set_script_context(script_id)
        try:
            _call_handler(spec.handler, ctx, args)
        finally:
            set_script_context(None)
        delete = ctx._delete_invocation
        if ctx.replies or ctx.files:
            payload = None
            if ctx.replies:
                payload = ctx.replies if len(ctx.replies) > 1 else ctx.replies[0]
            return payload, delete, ctx.files
        return None, delete, []

    script = get_script_by_command(name)
    if script is None:
        for s in list_scripts():
            if s.command.lower() == name and s.enabled:
                script = s
                break
    if script is None:
        return None, False, []

    path = _script_path(script.id)
    if not path.is_file():
        return None, False, []
    try:
        _, bot = _inject_module(script.id, path)
    except Exception:
        return None, False, []

    spec = bot.commands.get(name)
    if spec is None:
        for candidate in bot.commands.values():
            if candidate.name == name or name in candidate.aliases:
                spec = candidate
                break
    if spec is None:
        legacy = _run_legacy(script.id, args)
        return legacy, False, []

    ctx = CommandContext(
        message=message,
        script_id=script.id,
        command=spec.name,
        args=args,
    )
    set_script_context(script.id)
    try:
        _call_handler(spec.handler, ctx, args)
    finally:
        set_script_context(None)
    delete = ctx._delete_invocation
    if ctx.replies or ctx.files:
        payload = ctx.replies if len(ctx.replies) > 1 else (ctx.replies[0] if ctx.replies else None)
        return payload, delete, ctx.files
    return None, delete, []


def _test_message(cmd: str, args: str) -> FlxMessage:
    from flx.config import command_prefix

    prefix = command_prefix()
    body = f"{prefix}{cmd} {args}".strip()
    return FlxMessage.from_gateway(
        {
            "id": "0",
            "channel_id": "0",
            "content": body,
            "author": {"id": "0", "username": "test"},
        }
    )


def dispatch_message_listeners(message: FlxMessage) -> list[str]:
    ensure_registry()
    outgoing: list[str] = []

    for script_id, bot in _registry_bots.items():
        handler = bot.listeners.get("on_message")
        if not handler:
            continue
        set_script_context(script_id)
        try:
            result = _invoke_listener(handler, message)
            if isinstance(result, str) and result:
                outgoing.append(result)
            elif isinstance(result, list):
                outgoing.extend(str(x) for x in result if x)
        except Exception as exc:
            log(f"Listener error: {exc}", type_="ERROR")
        finally:
            set_script_context(None)

    return outgoing


def test_script_code(code: str, command: str, args: str) -> str | list[str]:
    import tempfile

    err = validate_code(code, script_id="_test")
    if err:
        raise ValueError(err)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
        tmp.write(code)
        tmp_path = Path(tmp.name)
    try:
        module, bot = _inject_module("_test", tmp_path)
        cmd = command.strip().lower()
        if not cmd and bot.commands:
            cmd = next(iter({s.name for s in bot.commands.values()}))
        if cmd and cmd in bot.commands:
            spec = bot.commands[cmd]
            ctx = CommandContext(
                message=_test_message(cmd, args),
                script_id="_test",
                command=spec.name,
                args=args,
            )
            set_script_context("_test")
            try:
                _call_handler(spec.handler, ctx, args)
            finally:
                set_script_context(None)
            if ctx.replies:
                return ctx.replies if len(ctx.replies) > 1 else ctx.replies[0]
            raise RuntimeError("Command produced no output")
        run_fn = getattr(module, "run", None)
        if callable(run_fn):
            set_script_context("_test")
            try:
                result = run_fn(args)
            finally:
                set_script_context(None)
            if isinstance(result, str):
                return result
            if isinstance(result, list):
                return result
        raise RuntimeError("No command handler matched")
    finally:
        tmp_path.unlink(missing_ok=True)


def run_script(script_id: str, args: str) -> str | list[str]:
    ensure_registry()
    path = _script_path(script_id)
    if not path.is_file():
        raise FileNotFoundError("Script file missing")

    script = next((s for s in list_scripts() if s.id == script_id), None)
    cmd = script.command if script else ""
    if cmd:
        fake = _test_message(cmd, args)
        result, _, _files = dispatch_hub_command(cmd, args, fake)
        if result is not None:
            return result
    return _run_legacy(script_id, args)
