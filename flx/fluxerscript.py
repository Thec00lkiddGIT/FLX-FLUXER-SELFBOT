"""FlxScript API - custom commands and listeners for Fluxer."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, TypeVar

T = TypeVar("T")

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


def _embed_color_note(color: int | str | None) -> str:
    if color is None:
        return ""
    if isinstance(color, int):
        return f"#{color & 0xFFFFFF:06X}"
    text = str(color).strip()
    if not text:
        return ""
    if text.isdigit():
        return f"#{int(text) & 0xFFFFFF:06X}"
    return text if text.startswith("#") else f"#{text.lstrip('#')}"


def forwardEmbedMethod(
    *,
    content: str = "",
    title: str | None = None,
    image: str | None = None,
    channel_id: str | None = None,
    color: int | str | None = None,
    description: str | None = None,
    footer: str | None = None,
    thumbnail: str | None = None,
    **_: Any,
) -> str:
    """Rich embed-style text (Fluxer supports embeds via API; this formats plain content)."""
    del channel_id  # reserved for future API embed sends
    body = (content or description or "").strip()
    lines: list[str] = []
    if title:
        lines.extend(["**" + title + "**", ""])
    if body:
        lines.append(body)
    thumb = thumbnail or image
    if thumb:
        lines.extend(["", str(thumb)])
    if image and image != thumb:
        lines.extend(["", str(image)])
    if footer:
        lines.extend(["", f"_{footer}_"])
    color_tag = _embed_color_note(color)
    if color_tag and not footer:
        lines.extend(["", f"_{color_tag}_"])
    elif color_tag and footer:
        lines[-1] = f"_{footer} · {color_tag}_"
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
        guild_id = data.get("guild_id")
        if not guild_id:
            guild = data.get("guild")
            if isinstance(guild, dict) and guild.get("id"):
                guild_id = guild["id"]
        return cls(
            id=str(data.get("id", "")),
            channel_id=str(data.get("channel_id", "")),
            guild_id=str(guild_id) if guild_id else None,
            content=str(data.get("content") or ""),
            author_id=str(author.get("id", "")),
            author_name=str(author.get("username") or author.get("global_name") or "?"),
            raw=data,
        )


@dataclass
class CommandContext:
    """Command context (`ctx.send`, `ctx.attach`, `ctx.message`)."""

    message: FlxMessage
    script_id: str
    command: str
    args: str
    _outgoing: list[str] = field(default_factory=list)
    _files: list[tuple[str, bytes]] = field(default_factory=list)
    _delete_invocation: bool = False

    @property
    def channel(self) -> FlxMessage:
        return self.message

    def send(self, content: str) -> None:
        if content:
            self._outgoing.append(content)

    def attach(self, filename: str, data: bytes) -> None:
        if filename and data:
            self._files.append((filename, data))

    @property
    def files(self) -> list[tuple[str, bytes]]:
        return list(self._files)

    def reply_embed(
        self,
        *,
        content: str = "",
        title: str | None = None,
        image: str | None = None,
        color: int | str | None = None,
        description: str | None = None,
        footer: str | None = None,
        thumbnail: str | None = None,
        **kwargs: Any,
    ) -> None:
        self.send(
            forwardEmbedMethod(
                content=content,
                title=title,
                image=image,
                color=color,
                description=description,
                footer=footer,
                thumbnail=thumbnail,
                **kwargs,
            )
        )

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


def _api_dual(method: Callable[..., T]) -> Callable[..., T | Any]:
    """Sync call returns data; inside async handlers returns an awaitable coroutine."""

    def wrapper(self: ScriptBot, *args: Any, **kwargs: Any) -> T | Any:
        def sync_call() -> T:
            return method(self, *args, **kwargs)

        async def async_call() -> T:
            import asyncio

            return await asyncio.to_thread(sync_call)

        try:
            import asyncio

            asyncio.get_running_loop()
        except RuntimeError:
            return sync_call()
        return async_call()

    return wrapper  # type: ignore[return-value]


class ScriptBot:
    def __init__(self, script_id: str) -> None:
        self.script_id = script_id
        self.commands: dict[str, CommandSpec] = {}
        self.listeners: dict[str, Callable[..., Any]] = {}
        self.meta: ScriptMeta | None = None

    def rest(self) -> Any:
        """Fluxer REST client (requires bot running on the dashboard)."""
        from flx.rest import FluxerREST
        from flx.runtime import get_runtime

        client = get_runtime().rest_client()
        if client is None:
            raise RuntimeError(
                "FLX is not connected — click Start bot on the dashboard, then run your command again."
            )
        return client

    @_api_dual
    def get_guild(self, guild_id: str) -> dict:
        return self.rest().get_guild(str(guild_id))

    @_api_dual
    def get_guild_channels(self, guild_id: str) -> list[dict]:
        return self.rest().list_guild_channels(str(guild_id))

    @_api_dual
    def list_guild_channels(self, guild_id: str) -> list[dict]:
        return self.rest().list_guild_channels(str(guild_id))

    @_api_dual
    def get_guild_members(
        self,
        guild_id: str,
        *,
        limit: int = 1000,
        after: str | None = None,
    ) -> list[dict]:
        return self.rest().list_guild_members(
            str(guild_id),
            limit=limit,
            after=after,
        )

    @_api_dual
    def list_guild_members(
        self,
        guild_id: str,
        *,
        limit: int = 1000,
        after: str | None = None,
    ) -> list[dict]:
        return self.rest().list_guild_members(
            str(guild_id),
            limit=limit,
            after=after,
        )

    @_api_dual
    def send_message(
        self,
        channel_id: str,
        content: str,
        *,
        reply_to: str | None = None,
        guild_id: str | None = None,
    ) -> dict:
        return self.rest().send_message(
            str(channel_id),
            content,
            reply_to=reply_to,
            guild_id=guild_id,
        )

    @_api_dual
    def get_user(self, user_id: str) -> dict:
        return self.rest().get_user(str(user_id))

    @_api_dual
    def get_channel_messages(
        self,
        channel_id: str,
        *,
        limit: int = 50,
        before: str | None = None,
    ) -> list[dict]:
        return self.rest().list_channel_messages(
            str(channel_id),
            limit=limit,
            before=before,
        )

    @_api_dual
    def list_channel_messages(
        self,
        channel_id: str,
        *,
        limit: int = 50,
        before: str | None = None,
    ) -> list[dict]:
        return self.rest().list_channel_messages(
            str(channel_id),
            limit=limit,
            before=before,
        )

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


def set_script_context(script_id: str | None) -> None:
    global _current_script_id
    _current_script_id = script_id
