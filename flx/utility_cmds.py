"""Extra built-in utility commands (prefix commands)."""

from __future__ import annotations

import base64
import json
import random
import re
import secrets
import string
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from flx.commands import BuiltinResult
from flx.config import api_base_url, set_command_prefix
from flx.fluxerscript import FlxMessage
from flx.parse_util import parse_user_id
from flx.paths import app_support_dir
from flx.rest import FluxerREST
from flx.state import load_gui_settings, save_gui_settings
from flx.targets import resolve_target_user_id
from flx.user_info import _discovery, _static_cdn, avatar_url

if TYPE_CHECKING:
    from flx.rest import FluxerREST

GENERAL_UTILITY_COMMANDS: list[tuple[str, str]] = [
    ("changeprefix", "Change the bot's command prefix"),
    ("shutdown", "Stop the selfbot and quit FLX"),
    ("uptime", "How long the selfbot has been running"),
    ("pingweb", "Ping a URL (HTTP status)"),
    ("geoip", "Look up an IP location"),
    ("tts", "Text to speech (audio file)"),
    ("reverse", "Reverse a message"),
    ("afk", "ON|OFF [message] - auto-reply in DMs"),
    ("fetchmembers", "List server members (saved to Flx notes file)"),
    ("firstmessage", "Link to the first message in this channel"),
    ("guildicon", "Get this server's icon"),
    ("usericon", "Get a user's avatar"),
    ("guildbanner", "Get this server's banner"),
    ("tokeninfo", "Info from a token (do not share tokens)"),
    ("guildinfo", "Info about this server"),
    ("playing", 'Set activity to "Playing …"'),
    ("watching", 'Set activity to "Watching …"'),
    ("stopactivity", "Clear custom activity"),
    ("ascii", "ASCII art from text"),
    ("minesweeper", "Custom minesweeper grid"),
    ("leetpeek", "1337 speak"),
]

MOD_UTILITY_COMMANDS: list[tuple[str, str]] = [
    ("guildrename", "Rename this server"),
]

ABUSE_UTILITY_COMMANDS: list[tuple[str, str]] = [
    ("copycat", "ON|OFF <@user> - mirror their messages"),
    ("quickdelete", "Send a message and delete it after 2s"),
    ("sendall", "Send a message to all text channels"),
    ("gentoken", "Generate a fake token-shaped string"),
    ("airplane", "Plane meme (use responsibly)"),
    ("dick", "Joke size command"),
]

UTILITY_COMMANDS: list[tuple[str, str]] = (
    GENERAL_UTILITY_COMMANDS + MOD_UTILITY_COMMANDS + ABUSE_UTILITY_COMMANDS
)

_STARTED_AT = time.time()
_app_exit_callback: object | None = None

_LEET_MAP = {
    "a": "4",
    "b": "8",
    "c": "(",
    "e": "3",
    "g": "9",
    "h": "#",
    "i": "1",
    "l": "1",
    "m": "m",
    "n": "n",
    "o": "0",
    "s": "5",
    "t": "7",
    "u": "u",
    "z": "2",
}


def _to_leet(text: str) -> str:
    return "".join(_LEET_MAP.get(c, _LEET_MAP.get(c.lower(), c)) for c in text)


def set_app_exit_callback(callback: object | None) -> None:
    global _app_exit_callback
    _app_exit_callback = callback


def _usage(prefix: str, cmd: str, text: str) -> BuiltinResult:
    return BuiltinResult(replies=[f"Usage: `{prefix}{cmd}` {text}"])


def _resolve_guild_id(msg: FlxMessage, rest: FluxerREST) -> str:
    if msg.guild_id:
        return msg.guild_id
    channel = rest.get_channel(msg.channel_id)
    guild_id = channel.get("guild_id")
    if guild_id:
        return str(guild_id)
    raise ValueError("This only works in a server channel, not DMs.")


def _guild_asset_url(rest: FluxerREST, kind: str, guild_id: str, asset_hash: str | None) -> str | None:
    if not asset_hash:
        return None
    cdn = _static_cdn(rest)
    if not cdn:
        return None
    ext = "gif" if str(asset_hash).startswith("a_") else "png"
    return f"{cdn}/{kind}/{guild_id}/{asset_hash}.{ext}"


def _fetch_url_status(url: str) -> tuple[int | None, str]:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    req = urllib.request.Request(
        url,
        method="GET",
        headers={"User-Agent": "Flx/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return int(getattr(resp, "status", 200)), url
    except urllib.error.HTTPError as exc:
        return exc.code, url
    except urllib.error.URLError as exc:
        raise RuntimeError(str(exc.reason)) from exc


def _geoip_lookup(ip: str) -> str:
    url = f"http://ip-api.com/json/{urllib.parse.quote(ip)}?fields=status,message,country,regionName,city,isp,query"
    req = urllib.request.Request(url, headers={"User-Agent": "Flx/1.0"})
    with urllib.request.urlopen(req, timeout=12) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if data.get("status") != "success":
        raise RuntimeError(data.get("message", "Lookup failed"))
    return (
        f"**{data.get('query')}**\n"
        f"{data.get('city')}, {data.get('regionName')}, {data.get('country')}\n"
        f"ISP: {data.get('isp')}"
    )


def _tts_wav(text: str) -> tuple[str, bytes]:
    text = text.strip()[:400]
    if not text:
        raise ValueError("Give some text to speak.")
    tmp = Path(tempfile.mkstemp(suffix=".wav")[1])
    try:
        if sys.platform == "darwin":
            subprocess.run(
                ["say", "-o", str(tmp), "--data-format=LEF32@22050", text],
                check=True,
                capture_output=True,
            )
        elif sys.platform.startswith("linux"):
            subprocess.run(
                ["espeak", "-w", str(tmp), text],
                check=True,
                capture_output=True,
            )
        else:
            raise ValueError("TTS is supported on macOS and Linux only.")
        return "tts.wav", tmp.read_bytes()
    except FileNotFoundError as exc:
        raise ValueError("TTS tool not found (macOS: say, Linux: espeak).") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(exc.stderr.decode(errors="replace") or "TTS failed") from exc
    finally:
        tmp.unlink(missing_ok=True)


def _oldest_message_id(rest: FluxerREST, channel_id: str) -> dict | None:
    oldest: dict | None = None
    before: str | None = None
    for _ in range(20):
        batch = rest.list_channel_messages(channel_id, limit=100, before=before)
        if not batch:
            break
        oldest = batch[-1]
        if len(batch) < 100:
            break
        before = str(batch[-1].get("id"))
    return oldest


def _format_member_lines(members: list[dict]) -> str:
    lines: list[str] = []
    for m in members:
        user = m.get("user") if isinstance(m.get("user"), dict) else m
        if not isinstance(user, dict):
            continue
        uid = str(user.get("id", ""))
        name = user.get("global_name") or user.get("username") or uid
        lines.append(f"{name} (`{uid}`)")
    return "\n".join(lines) if lines else "(no members)"


def handle_incoming_message(msg: FlxMessage, rest: FluxerREST, self_user_id: str | None) -> None:
    """Copycat + AFK auto-replies for messages from other users."""
    if not self_user_id or msg.author_id == self_user_id:
        return
    settings = load_gui_settings()

    if settings.get("copycat_enabled") and str(settings.get("copycat_user_id")) == msg.author_id:
        content = (msg.content or "").strip()
        if content:
            try:
                rest.send_message(
                    msg.channel_id,
                    content,
                    guild_id=msg.guild_id,
                )
            except RuntimeError:
                pass

    if not settings.get("afk_enabled"):
        return
    channel = rest.get_channel(msg.channel_id)
    if int(channel.get("type", 0)) not in (1, 3):
        return
    afk_msg = str(settings.get("afk_message") or "I'm AFK right now.")
    try:
        rest.send_message(
            msg.channel_id,
            afk_msg,
            reply_to=msg.id,
            guild_id=msg.guild_id,
        )
    except RuntimeError:
        pass


def dispatch_utility(
    name: str,
    args: str,
    message: FlxMessage,
    rest: FluxerREST,
    *,
    prefix: str,
) -> BuiltinResult | None:
    if name == "changeprefix":
        if not args.strip():
            return _usage(prefix, "changeprefix", "<new prefix>")
        try:
            new = set_command_prefix(args.strip())
            return BuiltinResult(
                replies=[f"Prefix is now `{new}` — use `{new}help`."],
                delete_invocation=True,
            )
        except ValueError as exc:
            return BuiltinResult(replies=[str(exc)])

    if name == "shutdown":
        from flx.runtime import get_runtime

        get_runtime().stop()

        def _exit_later() -> None:
            time.sleep(0.4)
            cb = _app_exit_callback
            if callable(cb):
                cb()

        threading.Thread(target=_exit_later, name="flx-shutdown", daemon=True).start()
        return BuiltinResult(
            replies=["Shutting down FLX…"],
            delete_invocation=True,
        )

    if name == "uptime":
        secs = int(time.time() - _STARTED_AT)
        h, rem = divmod(secs, 3600)
        m, s = divmod(rem, 60)
        parts = []
        if h:
            parts.append(f"{h}h")
        if m:
            parts.append(f"{m}m")
        parts.append(f"{s}s")
        return BuiltinResult(replies=[f"Uptime: **{' '.join(parts)}**"])

    if name == "copycat":
        parts = args.split()
        if len(parts) < 2:
            return _usage(prefix, "copycat", "ON|OFF <@user>")
        mode, target = parts[0].upper(), " ".join(parts[1:])
        try:
            uid = resolve_target_user_id(
                target,
                message,
                rest,
                empty_hint="Provide @user, user ID, or reply to their message.",
            )
        except ValueError as exc:
            return BuiltinResult(replies=[str(exc)])
        if mode == "ON":
            save_gui_settings(copycat_enabled=True, copycat_user_id=uid)
            return BuiltinResult(replies=[f"Copycat **on** for <@{uid}>."])
        if mode == "OFF":
            save_gui_settings(copycat_enabled=False, copycat_user_id="")
            return BuiltinResult(replies=["Copycat **off**."])
        return BuiltinResult(replies=["Use ON or OFF."])

    if name == "pingweb":
        if not args.strip():
            return _usage(prefix, "pingweb", "<url>")
        try:
            code, url = _fetch_url_status(args.strip())
            return BuiltinResult(replies=[f"`{url}` → **HTTP {code}**"])
        except RuntimeError as exc:
            return BuiltinResult(replies=[f"Ping failed: {exc}"])

    if name == "geoip":
        if not args.strip():
            return _usage(prefix, "geoip", "<ip>")
        try:
            return BuiltinResult(replies=[_geoip_lookup(args.strip().split()[0])])
        except (RuntimeError, urllib.error.URLError, json.JSONDecodeError) as exc:
            return BuiltinResult(replies=[f"GeoIP error: {exc}"])

    if name == "tts":
        if not args.strip():
            return _usage(prefix, "tts", "<text>")
        try:
            fname, data = _tts_wav(args)
            return BuiltinResult(replies=["TTS:"], files=[(fname, data)])
        except (ValueError, RuntimeError) as exc:
            return BuiltinResult(replies=[str(exc)])

    if name == "reverse":
        if not args.strip():
            return _usage(prefix, "reverse", "<message>")
        return BuiltinResult(replies=[args[::-1]])

    if name == "gentoken":
        part = "".join(
            secrets.choice(string.ascii_letters + string.digits + "_-")
            for _ in range(24)
        )
        fake = f"mfa.{part}.{secrets.token_hex(27)}"
        return BuiltinResult(
            replies=[f"Fake token (invalid): `{fake[:20]}…`"],
            delete_invocation=True,
        )

    if name == "quickdelete":
        if not args.strip():
            return _usage(prefix, "quickdelete", "<message>")
        sent = rest.send_message(message.channel_id, args, guild_id=message.guild_id)

        def _del() -> None:
            time.sleep(2)
            try:
                rest.delete_message(message.channel_id, str(sent.get("id", "")))
            except RuntimeError:
                pass

        threading.Thread(target=_del, daemon=True).start()
        return BuiltinResult(replies=[], delete_invocation=True)

    if name == "afk":
        parts = args.split(maxsplit=1)
        if not parts:
            return _usage(prefix, "afk", "ON|OFF [message]")
        mode = parts[0].upper()
        if mode == "ON":
            msg = parts[1].strip() if len(parts) > 1 else "I'm AFK right now."
            save_gui_settings(afk_enabled=True, afk_message=msg)
            return BuiltinResult(replies=[f"AFK **on** — DMs get: {msg}"])
        if mode == "OFF":
            save_gui_settings(afk_enabled=False)
            return BuiltinResult(replies=["AFK **off**."])
        return BuiltinResult(replies=["Use ON or OFF."])

    if name == "fetchmembers":
        try:
            guild_id = _resolve_guild_id(message, rest)
        except ValueError as exc:
            return BuiltinResult(replies=[str(exc)])
        members: list[dict] = []
        after: str | None = None
        for _ in range(10):
            batch = rest.list_guild_members(guild_id, limit=1000, after=after)
            if not batch:
                break
            members.extend(batch)
            if len(batch) < 1000:
                break
            after = str(batch[-1].get("user", {}).get("id", batch[-1].get("id", "")))
        body = _format_member_lines(members)
        notes_path = app_support_dir() / f"members_{guild_id}.txt"
        notes_path.write_text(
            f"# Members ({len(members)})\n# {datetime.now(timezone.utc).isoformat()}\n\n{body}\n",
            encoding="utf-8",
        )
        preview = body[:1500] + ("…" if len(body) > 1500 else "")
        return BuiltinResult(
            replies=[
                f"**{len(members)}** members. Saved to:\n`{notes_path}`\n\n{preview}",
            ]
        )

    if name == "firstmessage":
        first = _oldest_message_id(rest, message.channel_id)
        if not first:
            return BuiltinResult(replies=["No messages found in this channel."])
        cid, mid = message.channel_id, str(first.get("id"))
        link = f"https://fluxer.app/channels/{cid}/{mid}"
        return BuiltinResult(replies=[f"First message: {link}"])

    if name == "sendall":
        from flx.abuse_settings import require_abuse_mode

        blocked = require_abuse_mode()
        if blocked:
            return BuiltinResult(replies=[blocked], delete_invocation=True)
        if not args.strip():
            return _usage(prefix, "sendall", "<message>")
        try:
            guild_id = _resolve_guild_id(message, rest)
        except ValueError as exc:
            return BuiltinResult(replies=[str(exc)])
        channels = rest.list_guild_channels(guild_id)
        sent = 0
        for ch in channels:
            if int(ch.get("type", 0)) not in (0, 5):
                continue
            try:
                rest.send_message(str(ch["id"]), args, guild_id=guild_id)
                sent += 1
                time.sleep(0.35)
            except RuntimeError:
                pass
        return BuiltinResult(replies=[f"Sent to **{sent}** channels."])

    if name == "guildicon":
        try:
            guild_id = _resolve_guild_id(message, rest)
        except ValueError as exc:
            return BuiltinResult(replies=[str(exc)])
        guild = rest.get_guild(guild_id)
        icon = guild.get("icon") or guild.get("icon_hash")
        url = _guild_asset_url(rest, "icons", guild_id, str(icon) if icon else None)
        if not url:
            return BuiltinResult(replies=["This server has no icon."])
        return BuiltinResult(replies=[url])

    if name == "usericon":
        try:
            uid = resolve_target_user_id(
                args,
                message,
                rest,
                empty_hint="Provide @user, user ID, or reply to their message.",
            )
        except ValueError as exc:
            return BuiltinResult(replies=[str(exc)])
        user = rest.get_user(uid)
        url = avatar_url(rest, uid, user.get("avatar") or user.get("avatar_hash"))
        if not url:
            return BuiltinResult(replies=["No avatar for that user."])
        return BuiltinResult(replies=[url])

    if name == "guildbanner":
        try:
            guild_id = _resolve_guild_id(message, rest)
        except ValueError as exc:
            return BuiltinResult(replies=[str(exc)])
        guild = rest.get_guild(guild_id)
        banner = guild.get("banner") or guild.get("banner_hash")
        url = _guild_asset_url(rest, "banners", guild_id, str(banner) if banner else None)
        if not url:
            return BuiltinResult(replies=["This server has no banner."])
        return BuiltinResult(replies=[url])

    if name == "tokeninfo":
        token = args.strip()
        if not token:
            return _usage(prefix, "tokeninfo", "<token>")
        probe = FluxerREST(token, api_base_url())
        lines = []
        try:
            me = probe.get_me()
            lines.append(f"**User:** {me.get('global_name') or me.get('username')}")
            lines.append(f"**ID:** `{me.get('id')}`")
            lines.append(f"**Email:** {me.get('email', '(hidden)')}")
        except RuntimeError as exc:
            lines.append(f"API: {exc}")
        parts = token.split(".")
        if len(parts) >= 2:
            try:
                pad = parts[1] + "=" * (-len(parts[1]) % 4)
                payload = json.loads(base64.urlsafe_b64decode(pad))
                if isinstance(payload, dict):
                    exp = payload.get("exp")
                    if exp:
                        lines.append(f"**JWT exp:** <t:{exp}:F>")
                    lines.append(f"**JWT keys:** {', '.join(payload.keys())}")
            except (json.JSONDecodeError, ValueError):
                pass
        return BuiltinResult(replies=["\n".join(lines)], delete_invocation=True)

    if name == "guildinfo":
        try:
            guild_id = _resolve_guild_id(message, rest)
        except ValueError as exc:
            return BuiltinResult(replies=[str(exc)])
        g = rest.get_guild(guild_id)
        lines = [
            f"**{g.get('name', 'Server')}**",
            f"ID: `{guild_id}`",
            f"Members: **{g.get('member_count', '?')}**",
            f"Owner: `{g.get('owner_id', '?')}`",
        ]
        if g.get("description"):
            lines.append(f"Description: {g.get('description')}")
        return BuiltinResult(replies=["\n".join(lines)])

    if name == "guildrename":
        if not args.strip():
            return _usage(prefix, "guildrename", "<new name>")
        try:
            guild_id = _resolve_guild_id(message, rest)
            rest.patch_guild(guild_id, {"name": args.strip()[:100]})
            return BuiltinResult(replies=[f"Renamed server to **{args.strip()[:100]}**"])
        except ValueError as exc:
            return BuiltinResult(replies=[str(exc)])
        except RuntimeError as exc:
            return BuiltinResult(replies=[f"Rename failed: {exc}"])

    if name == "playing":
        text = args.strip() or "FLX"
        try:
            rest.set_activity(status="online", activity_type=0, activity_name=text)
            return BuiltinResult(replies=[f'Now **Playing** "{text}"'])
        except RuntimeError as exc:
            return BuiltinResult(replies=[f"Activity failed: {exc}"])

    if name == "watching":
        text = args.strip() or "Fluxer"
        try:
            rest.set_activity(status="online", activity_type=3, activity_name=text)
            return BuiltinResult(replies=[f'Now **Watching** "{text}"'])
        except RuntimeError as exc:
            return BuiltinResult(replies=[f"Activity failed: {exc}"])

    if name == "stopactivity":
        try:
            rest.set_activity(clear=True)
            return BuiltinResult(replies=["Activity cleared."])
        except RuntimeError as exc:
            return BuiltinResult(replies=[f"Activity failed: {exc}"])

    if name == "ascii":
        if not args.strip():
            return _usage(prefix, "ascii", "<text>")
        try:
            out = subprocess.run(
                ["figlet", args.strip()[:40]],
                capture_output=True,
                text=True,
                timeout=8,
            )
            art = (out.stdout or "").strip() if out.returncode == 0 else ""
            if not art:
                raise ValueError("figlet not installed or failed")
            return BuiltinResult(replies=[f"```\n{art}\n```"])
        except (FileNotFoundError, ValueError, subprocess.TimeoutExpired):
            return BuiltinResult(replies=[f"```{args.strip().upper()}```"])

    if name == "airplane":
        art = (
            "✈️ __| _\n"
            " _  __|_\n"
            "  _  __\n"
            "   _\n"
            "  Tower: cleared for takeoff 🗽"
        )
        return BuiltinResult(replies=[art])

    if name == "dick":
        try:
            uid = (
                resolve_target_user_id(
                    args,
                    message,
                    rest,
                    empty_hint="Provide @user, user ID, or reply to their message.",
                )
                if args.strip()
                else message.author_id
            )
        except ValueError as exc:
            return BuiltinResult(replies=[str(exc)])
        inches = random.randint(1, 12)
        return BuiltinResult(replies=[f"<@{uid}> is **{inches}** inches."])

    if name == "minesweeper":
        parts = args.split()
        w, h = 5, 5
        if len(parts) >= 2:
            try:
                w, h = int(parts[0]), int(parts[1])
            except ValueError:
                return _usage(prefix, "minesweeper", "[width] [height]")
        w = max(3, min(w, 9))
        h = max(3, min(h, 9))
        bombs = max(1, (w * h) // 5)
        grid = [[False] * w for _ in range(h)]
        placed = 0
        while placed < bombs:
            x, y = random.randrange(w), random.randrange(h)
            if not grid[y][x]:
                grid[y][x] = True
                placed += 1
        emojis = []
        for y in range(h):
            row = []
            for x in range(w):
                if grid[y][x]:
                    row.append("||💣||")
                else:
                    n = 0
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            if dx == dy == 0:
                                continue
                            ny, nx = y + dy, x + dx
                            if 0 <= ny < h and 0 <= nx < w and grid[ny][nx]:
                                n += 1
                    row.append("⬜" if n == 0 else str(n))
            emojis.append("".join(row))
        return BuiltinResult(replies=["\n".join(emojis)])

    if name == "leetpeek":
        if not args.strip():
            return _usage(prefix, "leetpeek", "<message>")
        return BuiltinResult(replies=[_to_leet(args)])

    return None
