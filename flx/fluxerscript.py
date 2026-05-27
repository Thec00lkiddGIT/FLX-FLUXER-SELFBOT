"""FlxScript API - Nighty-style custom commands for Fluxer."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from flx.paths import ensure_script_hub

JSON_DIR_NAME = "json"


def getScriptsPath() -> str:
    return str(ensure_script_hub())


def _config_file() -> Path:
    return ensure_script_hub() / "config.json"


_current_script_id: str | None = None


def _load_config_file() -> dict:
    path = _config_file()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _save_config_file(data: dict) -> None:
    ensure_script_hub().mkdir(parents=True, exist_ok=True)
    _config_file().write_text(json.dumps(data, indent=2) + "\n")


def _script_prefix() -> str:
    if not _current_script_id:
        return ""
    return f"{_current_script_id}__"


def getConfigData() -> dict:
    all_cfg = _load_config_file()
    prefix = _script_prefix()
    if not prefix:
        return dict(all_cfg)
    return {k[len(prefix) :]: v for k, v in all_cfg.items() if k.startswith(prefix)}


def updateConfigData(key: str, value: Any) -> None:
    all_cfg = _load_config_file()
    prefix = _script_prefix()
    all_cfg[f"{prefix}{key}"] = value
    _save_config_file(all_cfg)


def forwardEmbedMethod(
    *,
    content: str,
    title: str | None = None,
    image: str | None = None,
    channel_id: str | None = None,
) -> str:
    """Rich embed-style text (Fluxer supports embeds via API; this formats plain content)."""
    lines: list[str] = []
    if title:
        lines.extend(["**" + title + "**", ""])
    lines.append(content)
    if image:
        lines.extend(["", str(image)])
    return "\n".join(lines).strip()


def log(message: str, type_: str = "INFO") -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sid = _current_script_id or "script"
    print(f"[{ts}] [{sid}] [{type_}] {message}", file=sys.stderr)


@dataclass
class FlxMessage:
    """Gateway MESSAGE_CREATE payload wrapper."""

    id: str
    channel_id: str
    guild_id: str | None
    content: str
    author_id: str
    author_name: str
    raw: dict

    @classmethod
    def from_gateway(cls, data: dict) -> FlxMessage:
        author = data.get("author") or {}
        return cls(
            id=str(data.get("id", "")),
            channel_id=str(data.get("channel_id", "")),
            guild_id=str(data["guild_id"]) if data.get("guild_id") else None,
            content=str(data.get("content") or ""),
            author_id=str(author.get("id", "")),
            author_name=str(author.get("username") or author.get("global_name") or "?"),
            raw=data,
        )


@dataclass
class CommandContext:
    """Nighty-style command context (`ctx.send`, `ctx.message`)."""

    message: FlxMessage
    script_id: str
    command: str
    args: str
    _outgoing: list[str] = field(default_factory=list)
    _delete_invocation: bool = False

    @property
    def channel(self) -> FlxMessage:
        return self.message

    def send(self, content: str) -> None:
        if content:
            self._outgoing.append(content)

    def reply_embed(
        self,
        *,
        content: str,
        title: str | None = None,
        image: str | None = None,
    ) -> None:
        self.send(forwardEmbedMethod(content=content, title=title, image=image))

    @property
    def replies(self) -> list[str]:
        return list(self._outgoing)

    def request_delete_invocation(self) -> None:
        self._delete_invocation = True


@dataclass(frozen=True)
class CommandSpec:
    script_id: str
    name: str
    description: str
    usage: str
    handler: Callable[..., Any]
    aliases: tuple[str, ...]


@dataclass
class ScriptMeta:
    script_id: str
    name: str
    author: str
    description: str
    usage: str


class ScriptBot:
    def __init__(self, script_id: str) -> None:
        self.script_id = script_id
        self.commands: dict[str, CommandSpec] = {}
        self.listeners: dict[str, Callable[..., Any]] = {}
        self.meta: ScriptMeta | None = None

    def command(
        self,
        name: str,
        *,
        usage: str = "",
        description: str = "",
        aliases: list[str] | None = None,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            spec = CommandSpec(
                script_id=self.script_id,
                name=name.lower(),
                description=description,
                usage=usage,
                handler=fn,
                aliases=tuple(a.lower() for a in (aliases or [])),
            )
            self.commands[spec.name] = spec
            for alias in spec.aliases:
                self.commands[alias] = spec
            return fn

        return decorator

    def listen(self, event: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            self.listeners[event] = fn
            return fn

        return decorator


def flxScript(
    *,
    name: str,
    author: str = "Flx",
    description: str = "",
    usage: str = "",
) -> Callable[[Callable[[], None]], Callable[[], None]]:
    def decorator(fn: Callable[[], None]) -> Callable[[], None]:
        fn.__flx_script_meta__ = {  # type: ignore[attr-defined]
            "name": name,
            "author": author,
            "description": description,
            "usage": usage,
        }
        return fn

    return decorator


# Nighty-compatible alias
nightyScript = flxScript


def set_script_context(script_id: str | None) -> None:
    global _current_script_id
    _current_script_id = script_id
