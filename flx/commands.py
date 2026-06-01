"""Built-in Fluxer selfbot commands."""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field

from flx.config import command_prefix
from flx.dadjoke import dadjoke_reply
from flx.fluxerscript import CommandContext, FlxMessage
from flx.glcheck import bulk_reply
from flx.microlink import screenshot_lookup
from flx.poof import poof_from_message
from flx.osint import credits_reply, search_reply
from flx.qr import fetch_qr_png, format_qr_caption
from flx.randomword import word_reply
from flx.rest import FluxerREST
from flx.weather import weather_reply
from flx.user_info import user_info_lookup
from flx.webhook_cmd import run_webhook_command
from flx.youtube import youtube_reply


COMMANDS: list[tuple[str, str]] = [
    ("ping", "Returns bot latency (ms)"),
    ("gay", "Random percentage joke"),
    ("word", "Random word (API Ninjas)"),
    ("dadjoke", "Random dad joke"),
    ("qr", "QR code image + caption"),
    ("youtube", "search | video | trans (SerpAPI)"),
    ("weather", "City weather (C99.nl)"),
    ("bulk", "Bulk URL check (up to 3)"),
    ("osint", "OSINT Industries lookup"),
    ("help", "List built-in and hub commands"),
    ("status", "Set presence: online | idle | dnd | invisible"),
    ("purge", "Delete your recent messages in this channel"),
    ("poof", "Remove image background (attach image, Poof.bg)"),
    ("screenshot", "Screenshot a URL (Microlink)"),
    ("info", "user - profile, avatar, snowflake decode"),
    ("wb", "Webhook send/delete via URL"),
]


@dataclass
class BuiltinResult:
    replies: list[str] = field(default_factory=list)
    files: list[tuple[str, bytes]] = field(default_factory=list)
    delete_invocation: bool = True


def _usage(cmd: str, text: str) -> str:
    return f"Usage: `{command_prefix()}{cmd}` {text}"


def _err(prefix: str, exc: Exception) -> BuiltinResult:
    return BuiltinResult(replies=[f"{prefix} error: {exc}"])


def dispatch_builtin(
    name: str,
    args: str,
    message: FlxMessage,
    rest: FluxerREST,
) -> BuiltinResult | None:
    from flx.danger_cmds import dispatch_danger
    from flx.utility_cmds import dispatch_utility

    prefix = command_prefix()
    util = dispatch_utility(name, args, message, rest, prefix=prefix)
    if util is not None:
        return util

    danger = dispatch_danger(name, args, message, rest, prefix=prefix)
    if danger is not None:
        return danger

    if name == "ping":
        start = time.perf_counter()
        try:
            rest.get_me()
            ms = int((time.perf_counter() - start) * 1000)
            return BuiltinResult(replies=[f"pong — **{ms}ms**"])
        except RuntimeError as exc:
            return BuiltinResult(replies=[f"pong (API error: {exc})"])

    if name == "gay":
        pct = random.randint(0, 100)
        return BuiltinResult(replies=[f"YOU are {pct}% gay"])

    if name == "word":
        try:
            return BuiltinResult(replies=[word_reply()])
        except ValueError as exc:
            return BuiltinResult(replies=[str(exc)])
        except RuntimeError as exc:
            return _err("Word", exc)

    if name == "dadjoke":
        try:
            return BuiltinResult(replies=[dadjoke_reply()])
        except ValueError as exc:
            return BuiltinResult(replies=[str(exc)])
        except RuntimeError as exc:
            return _err("Dad joke", exc)

    if name == "qr":
        if not args:
            return BuiltinResult(
                replies=[_usage("qr", "<text or link>\nExample: `!qr https://example.com`")]
            )
        try:
            png = fetch_qr_png(args)
            return BuiltinResult(
                replies=[format_qr_caption(args)],
                files=[("qrcode.png", png)],
            )
        except ValueError as exc:
            return BuiltinResult(replies=[str(exc)])
        except RuntimeError as exc:
            return _err("QR", exc)

    if name == "poof":
        try:
            text, files = poof_from_message(message, args, fluxer_token=rest.token)
            return BuiltinResult(replies=[text], files=files)
        except ValueError as exc:
            return BuiltinResult(
                replies=[
                    str(exc),
                    _usage(
                        "poof",
                        "(attach image) [format=png] [channels=rgba] [bg_color=#fff] [size=full] [crop=true]",
                    ),
                ]
            )
        except RuntimeError as exc:
            return _err("Poof", exc)

    if name == "screenshot":
        if not args.strip():
            return BuiltinResult(
                replies=[
                    _usage("screenshot", "<url>\nExample: `!screenshot https://fluxer.app`")
                ]
            )
        try:
            text, files = screenshot_lookup(args.strip())
            return BuiltinResult(replies=[text], files=files)
        except ValueError as exc:
            return BuiltinResult(replies=[str(exc)])
        except RuntimeError as exc:
            return _err("Screenshot", exc)

    if name == "youtube":
        parts = args.split(None, 1)
        if len(parts) < 2:
            return BuiltinResult(
                replies=[
                    "Usage:\n"
                    f"`{prefix}youtube search <query>`\n"
                    f"`{prefix}youtube video <id or url>`\n"
                    f"`{prefix}youtube trans <id or url>`"
                ]
            )
        sub, arg = parts[0].lower(), parts[1].strip()
        try:
            result = youtube_reply(sub, arg)
        except ValueError as exc:
            return BuiltinResult(replies=[str(exc)])
        except RuntimeError as exc:
            return _err("YouTube", exc)
        if isinstance(result, list):
            return BuiltinResult(replies=result)
        return BuiltinResult(replies=[result])

    if name == "weather":
        if not args:
            return BuiltinResult(
                replies=[_usage("weather", "<city>\nExample: `!weather London`")]
            )
        try:
            return BuiltinResult(replies=[weather_reply(args)])
        except ValueError as exc:
            return BuiltinResult(replies=[str(exc)])
        except RuntimeError as exc:
            return _err("Weather", exc)

    if name == "bulk":
        urls = args.split()
        if not urls:
            return BuiltinResult(
                replies=[_usage("bulk", "<url1> <url2> [url3]")]
            )
        try:
            return BuiltinResult(replies=bulk_reply(urls))
        except ValueError as exc:
            return BuiltinResult(replies=[str(exc)])
        except RuntimeError as exc:
            return _err("Bulk", exc)

    if name == "osint":
        parts = args.split(None, 1)
        if not parts:
            return BuiltinResult(
                replies=[
                    "Usage:\n"
                    f"`{prefix}osint email <address>`\n"
                    f"`{prefix}osint phone <number>`\n"
                    f"`{prefix}osint username <handle>`\n"
                    f"`{prefix}osint name <full name>`\n"
                    f"`{prefix}osint wallet <address>`\n"
                    f"`{prefix}osint credits`"
                ]
            )
        sub = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""
        try:
            if sub in ("credits", "credit", "balance"):
                return BuiltinResult(replies=[credits_reply()])
            premium = False
            if sub == "premium" and arg:
                inner = arg.split(None, 1)
                if len(inner) < 2:
                    return BuiltinResult(
                        replies=[
                            _usage(
                                "osint premium",
                                "<email|phone|username|name|wallet> <query>",
                            )
                        ]
                    )
                sub, arg = inner[0].lower(), inner[1].strip()
                premium = True
            return BuiltinResult(replies=search_reply(sub, arg, premium=premium))
        except ValueError as exc:
            return BuiltinResult(replies=[str(exc)])
        except RuntimeError as exc:
            return _err("OSINT", exc)

    if name == "info":
        parts = args.split(None, 1)
        sub = parts[0].lower() if parts else ""
        subargs = parts[1] if len(parts) > 1 else ""
        if sub != "user":
            return BuiltinResult(
                replies=[
                    _usage(
                        "info",
                        "user [@user|id]\n"
                        "Examples: `!info user` `!info user @someone` (reply also works)",
                    )
                ]
            )
        try:
            text, files = user_info_lookup(message, rest, subargs)
            return BuiltinResult(replies=[text], files=files)
        except ValueError as exc:
            return BuiltinResult(replies=[str(exc)])
        except RuntimeError as exc:
            return _err("Info", exc)

    if name == "wb":
        if not args.strip():
            return BuiltinResult(
                replies=[
                    _usage(
                        "wb",
                        "<webhook url> send <text>\n"
                        "`!wb <url> delete` - delete webhook (token URL, no admin)",
                    )
                ]
            )
        try:
            return BuiltinResult(replies=[run_webhook_command(args)])
        except ValueError as exc:
            return BuiltinResult(replies=[str(exc)])
        except RuntimeError as exc:
            return _err("Webhook", exc)

    if name == "help":
        from flx.command_catalog import format_help

        return BuiltinResult(replies=[format_help(prefix)])

    if name == "status":
        status = (args.strip().lower() or "online")
        if status not in ("online", "idle", "dnd", "invisible"):
            return BuiltinResult(
                replies=[_usage("status", "online|idle|dnd|invisible")]
            )
        try:
            rest.set_presence(status)
            return BuiltinResult(replies=[f"Status set to **{status}**"])
        except RuntimeError as exc:
            return _err("Status", exc)

    if name == "purge":
        try:
            limit = min(max(int(args.strip() or "10"), 1), 50)
        except ValueError:
            limit = 10
        me = rest.get_me()["id"]
        batch = rest._request("GET", f"/channels/{message.channel_id}/messages?limit=100")
        deleted = 0
        if isinstance(batch, list):
            for msg in batch:
                if deleted >= limit:
                    break
                if str((msg.get("author") or {}).get("id")) != str(me):
                    continue
                try:
                    rest.delete_message(message.channel_id, str(msg["id"]))
                    deleted += 1
                except RuntimeError:
                    pass
        return BuiltinResult(replies=[f"Deleted **{deleted}** of your messages."])

    return None


def run_builtin(
    ctx: CommandContext,
    rest: FluxerREST,
) -> BuiltinResult | None:
    result = dispatch_builtin(ctx.command, ctx.args, ctx.message, rest)
    if result is None:
        return None
    for text in result.replies:
        ctx.send(text)
    if result.delete_invocation:
        ctx.request_delete_invocation()
    return result
