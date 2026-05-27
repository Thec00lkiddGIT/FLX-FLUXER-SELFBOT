"""Built-in Fluxer selfbot commands (ported from Ibot)."""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from flx.config import command_prefix
from flx.dadjoke import dadjoke_reply
from flx.fluxerscript import CommandContext, FlxMessage
from flx.glcheck import bulk_reply, check_reply
from flx.osint import credits_reply, search_reply
from flx.qr import fetch_qr_png, format_qr_caption
from flx.randomword import word_reply
from flx.rest import FluxerREST
from flx.weather import weather_reply
from flx.youtube import youtube_reply

PREFIX = command_prefix()

FILTER_KEYS = frozenset(
    {
        "fortiguard",
        "lightspeed",
        "paloalto",
        "blocksiweb",
        "blocksiai",
        "blocksiguardian",
        "linewize",
        "cisco",
        "securly",
        "goguardian",
        "goguardianv2",
        "goguardianai",
        "lanschool",
        "lanschoolair",
        "contentkeeper",
        "aristotle",
        "senso",
        "deledao",
        "iboss",
        "barracuda",
        "dnsfilter",
        "qustodio",
        "sophos",
        "zscaler",
        "gaggle",
        "smoothwall",
        "safedns",
        "ruckus",
        "unifi",
        "webroot",
        "nextdns",
        "netsweeper",
        "hapara",
        "forcepoint",
        "cleanbrowsing",
        "adguard",
        "googlesafebrowsing",
        "opendns",
        "watchguard",
        "cloudflareintel",
        "cloudflarefamily",
        "quad9",
        "trellix",
        "controld",
        "dragonflyai",
        "norton",
        "ciracs",
        "safesurfer",
    }
)

COMMANDS: list[tuple[str, str]] = [
    ("ping", "Returns pong"),
    ("gay", "Random percentage joke"),
    ("word", "Random word (API Ninjas)"),
    ("dadjoke", "Random dad joke"),
    ("qr", "QR code image + caption"),
    ("youtube", "search | video | trans (SerpAPI)"),
    ("weather", "City weather (C99.nl)"),
    ("check", "URL filter check (GLSeries)"),
    ("bulk", "Bulk URL check (up to 3)"),
    ("osint", "OSINT Industries lookup"),
    ("help", "List built-in and hub commands"),
    ("echo", "Repeat your text"),
    ("status", "Set presence: online | idle | dnd | invisible"),
    ("purge", "Delete your recent messages in this channel"),
]


@dataclass
class BuiltinResult:
    replies: list[str] = field(default_factory=list)
    files: list[tuple[str, bytes]] = field(default_factory=list)
    delete_invocation: bool = True


def _parse_check_args(args: str) -> tuple[str | None, str]:
    parts = args.split()
    if not parts:
        raise ValueError("missing url")
    if parts[0].lower() in FILTER_KEYS:
        if len(parts) < 2:
            raise ValueError("missing url after filter name")
        return parts[0].lower(), parts[1]
    return None, args


def _usage(cmd: str, text: str) -> str:
    return f"Usage: `{PREFIX}{cmd}` {text}"


def _err(prefix: str, exc: Exception) -> BuiltinResult:
    return BuiltinResult(replies=[f"{prefix} error: {exc}"])


def dispatch_builtin(
    name: str,
    args: str,
    message: FlxMessage,
    rest: FluxerREST,
) -> BuiltinResult | None:
    from flx.danger_cmds import dispatch_danger

    danger = dispatch_danger(name, args, message, rest, prefix=PREFIX)
    if danger is not None:
        return danger

    if name == "ping":
        return BuiltinResult(replies=["pong"])

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

    if name == "youtube":
        parts = args.split(None, 1)
        if len(parts) < 2:
            return BuiltinResult(
                replies=[
                    "Usage:\n"
                    f"`{PREFIX}youtube search <query>`\n"
                    f"`{PREFIX}youtube video <id or url>`\n"
                    f"`{PREFIX}youtube trans <id or url>`"
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

    if name == "check":
        if not args:
            return BuiltinResult(
                replies=[
                    _usage("check", "<url>\nOptional: `!check linewize example.com`")
                ]
            )
        try:
            filter_key, url = _parse_check_args(args)
            return BuiltinResult(replies=check_reply(url, filter_key=filter_key))
        except ValueError as exc:
            return BuiltinResult(replies=[str(exc)])
        except RuntimeError as exc:
            return _err("Check", exc)

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
                    f"`{PREFIX}osint email <address>`\n"
                    f"`{PREFIX}osint phone <number>`\n"
                    f"`{PREFIX}osint username <handle>`\n"
                    f"`{PREFIX}osint name <full name>`\n"
                    f"`{PREFIX}osint wallet <address>`\n"
                    f"`{PREFIX}osint credits`"
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

    if name == "help":
        from flx.script_hub import hub_command_specs

        lines = [f"**Commands** (prefix `{PREFIX}`)", ""]
        rows = list(COMMANDS)
        for spec in hub_command_specs():
            rows.append((spec["name"], spec.get("help", "")))
        seen: set[str] = set()
        for cmd, help_text in rows:
            if cmd in seen:
                continue
            seen.add(cmd)
            lines.append(f"`{PREFIX}{cmd}` - {help_text}")
        lines.extend(["", "**Abuse / mod / troll** (enable with `!abuse` in GUI first)", ""])
        from flx.danger_cmds import DANGER_COMMANDS

        for cmd, help_text in DANGER_COMMANDS:
            lines.append(f"`{PREFIX}{cmd}` - {help_text}")
        return BuiltinResult(replies=["\n".join(lines)])

    if name == "echo":
        if not args.strip():
            return BuiltinResult(replies=[_usage("echo", "<text>")])
        return BuiltinResult(replies=[args.strip()])

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
