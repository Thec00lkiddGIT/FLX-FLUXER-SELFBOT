"""Abuse / mod / troll commands."""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING

from flx.abuse_settings import (
    ABUSE_WARNING,
    abuse_mode_enabled,
    request_abuse_confirm,
    require_abuse_mode,
)
from flx.commands import BuiltinResult
from flx.fluxerscript import FlxMessage
from flx.parse_util import mention_user, parse_user_id
from flx.targets import resolve_target_user_id
from flx.troll import get_troll_manager

if TYPE_CHECKING:
    from flx.rest import FluxerREST

MOD_COMMANDS: list[tuple[str, str]] = [
    ("mod", "ban|kick <@user|id> (reply works for kick)"),
]

ABUSE_COMMANDS: list[tuple[str, str]] = [
    ("abuse", "Confirm abuse mode in GUI; `spam <text> <n> <seconds>`"),
    ("troll", "ghostping | annoy unreact|delete | reactannoy | stop"),
]

DANGER_COMMANDS: list[tuple[str, str]] = MOD_COMMANDS + ABUSE_COMMANDS

MAX_SPAM_COUNT = 100
MIN_SPAM_DELAY = 0.05


def _usage(prefix: str, cmd: str, text: str) -> BuiltinResult:
    return BuiltinResult(replies=[f"Usage: `{prefix}{cmd}` {text}"])


def _resolve_guild_id(msg: FlxMessage, rest: FluxerREST) -> str:
    if msg.guild_id:
        return msg.guild_id
    try:
        channel = rest.get_channel(msg.channel_id)
        guild_id = channel.get("guild_id")
        if guild_id:
            return str(guild_id)
    except RuntimeError:
        pass
    raise ValueError("This command only works in a server channel, not DMs.")


def dispatch_danger(
    name: str,
    args: str,
    msg: FlxMessage,
    rest: FluxerREST,
    *,
    prefix: str,
) -> BuiltinResult | None:
    if name == "abuse":
        return _cmd_abuse(args, msg, rest, prefix=prefix)
    if name == "mod":
        return _cmd_mod(args, msg, rest, prefix=prefix)
    if name == "troll":
        return _cmd_troll(args, msg, rest, prefix=prefix)
    return None


def _cmd_abuse(args: str, msg: FlxMessage, rest: FluxerREST, *, prefix: str) -> BuiltinResult:
    parts = args.split(None, 1)
    sub = parts[0].lower() if parts else ""
    subargs = parts[1] if len(parts) > 1 else ""

    if not sub:
        request_abuse_confirm()
        return BuiltinResult(
            replies=[
                "**Abuse mode** - confirm in the Flx dashboard.\n\n"
                f"{ABUSE_WARNING}\n\n"
                "After enabling: "
                f"`{prefix}abuse spam <text> <amount> <seconds>`"
            ],
            delete_invocation=True,
        )

    if sub == "status":
        on = abuse_mode_enabled()
        return BuiltinResult(
            replies=[f"Abuse mode is **{'on' if on else 'off'}**."],
            delete_invocation=True,
        )

    if sub != "spam":
        return _usage(
            prefix,
            "abuse",
            "- confirm in GUI, or `spam <text> <amount> <seconds>`",
        )

    blocked = require_abuse_mode()
    if blocked:
        return BuiltinResult(replies=[blocked], delete_invocation=True)

    try:
        guild_id = _resolve_guild_id(msg, rest)
    except ValueError as exc:
        return BuiltinResult(replies=[str(exc)])

    chunks = subargs.rsplit(None, 2)
    if len(chunks) < 3:
        return _usage(
            prefix,
            "abuse spam",
            "<words> <amount> <seconds>\nExample: `!abuse spam hello 10 0.5`",
        )

    text, amount_s, delay_s = chunks[0], chunks[1], chunks[2]
    try:
        amount = int(amount_s)
        delay = float(delay_s)
    except ValueError:
        return BuiltinResult(replies=["Amount must be an integer and time a number (seconds)."])

    if amount < 1:
        return BuiltinResult(replies=["Amount must be at least 1."])
    if amount > MAX_SPAM_COUNT:
        return BuiltinResult(replies=[f"Max {MAX_SPAM_COUNT} messages per spam."])
    if delay < MIN_SPAM_DELAY:
        delay = MIN_SPAM_DELAY

    channel_id = msg.channel_id

    def _run() -> None:
        for _ in range(amount):
            try:
                rest.send_message(channel_id, text, guild_id=guild_id)
            except RuntimeError:
                break
            time.sleep(delay)

    threading.Thread(target=_run, name="flx-spam", daemon=True).start()
    return BuiltinResult(
        replies=[
            f"Spamming **{amount}** message(s) every **{delay}s** in this channel."
        ],
        delete_invocation=True,
    )


def _cmd_mod(args: str, msg: FlxMessage, rest: FluxerREST, *, prefix: str) -> BuiltinResult:
    blocked = require_abuse_mode()
    if blocked:
        return BuiltinResult(replies=[blocked], delete_invocation=True)

    parts = args.split(None, 1)
    if not parts:
        return _usage(prefix, "mod", "ban|kick <@user|id> (kick: reply to user)")
    sub = parts[0].lower()
    target_raw = parts[1].strip() if len(parts) > 1 else ""

    if sub not in ("ban", "kick"):
        return _usage(prefix, "mod", "ban|kick <@user|id> (kick: reply to user)")
    if not target_raw and sub == "ban":
        return _usage(prefix, "mod", "ban|kick <@user|id>")

    try:
        guild_id = _resolve_guild_id(msg, rest)
        user_id = resolve_target_user_id(
            target_raw,
            msg,
            rest,
            empty_hint=(
                "Provide a @user, user ID, or reply to their message with `!mod kick`."
            ),
        )
    except ValueError as exc:
        return BuiltinResult(replies=[str(exc)], delete_invocation=True)

    try:
        if sub == "ban":
            rest.ban_member(guild_id, user_id)
            action = "banned"
        else:
            rest.kick_member(guild_id, user_id)
            action = "kicked"
    except RuntimeError as exc:
        return BuiltinResult(replies=[f"Mod failed: {exc}"], delete_invocation=True)

    return BuiltinResult(
        replies=[f"User `{user_id}` was **{action}**."],
        delete_invocation=True,
    )


def _cmd_troll(args: str, msg: FlxMessage, rest: FluxerREST, *, prefix: str) -> BuiltinResult:
    blocked = require_abuse_mode()
    if blocked:
        return BuiltinResult(replies=[blocked], delete_invocation=True)

    parts = args.split()
    if not parts:
        return _usage(
            prefix,
            "troll",
            "ghostping|annoy|reactannoy … (see help)",
        )

    sub = parts[0].lower()
    mgr = get_troll_manager()

    if sub == "ghostping":
        if len(parts) < 2:
            return _usage(prefix, "troll ghostping", "<@user|id>")
        try:
            user_id = parse_user_id(parts[1])
        except ValueError as exc:
            return BuiltinResult(replies=[str(exc)])
        ping = mention_user(user_id)
        try:
            sent = rest.send_message(msg.channel_id, ping, guild_id=msg.guild_id)
            message_id = str(sent.get("id", ""))
            if message_id:
                rest.delete_message(msg.channel_id, message_id)
        except RuntimeError as exc:
            return BuiltinResult(replies=[f"Ghost ping failed: {exc}"], delete_invocation=True)
        return BuiltinResult(replies=[], delete_invocation=True)

    if sub == "annoy":
        if len(parts) < 3:
            return _usage(prefix, "troll annoy", "unreact|delete <@user|id>")
        mode = parts[1].lower()
        try:
            user_id = parse_user_id(parts[2])
        except ValueError as exc:
            return BuiltinResult(replies=[str(exc)])
        if mode == "delete":
            mgr.set_delete_target(user_id, True)
            mgr.set_unreact_target(user_id, False)
            detail = "deleting their messages"
        elif mode == "unreact":
            mgr.set_unreact_target(user_id, True)
            mgr.set_delete_target(user_id, False)
            detail = "removing their reactions"
        else:
            return _usage(prefix, "troll annoy", "unreact|delete <@user|id>")
        return BuiltinResult(
            replies=[f"Annoy **on** for `{user_id}` - {detail}."],
            delete_invocation=True,
        )

    if sub == "reactannoy":
        if len(parts) < 3:
            return _usage(prefix, "troll reactannoy", "<emoji> <@user|id>")
        emoji = parts[1]
        try:
            user_id = parse_user_id(parts[2])
        except ValueError as exc:
            return BuiltinResult(replies=[str(exc)])
        mgr.set_react_annoy(user_id, emoji)
        return BuiltinResult(
            replies=[f"React annoy **on** - `{emoji}` on every message from `{user_id}`."],
            delete_invocation=True,
        )

    if sub == "stop":
        if len(parts) < 3:
            return _usage(prefix, "troll stop", "annoy|reactannoy <@user|id>")
        which = parts[1].lower()
        try:
            user_id = parse_user_id(parts[2])
        except ValueError as exc:
            return BuiltinResult(replies=[str(exc)])
        if which == "annoy":
            mgr.set_delete_target(user_id, False)
            mgr.set_unreact_target(user_id, False)
        elif which == "reactannoy":
            mgr.set_react_annoy(None, None)
        else:
            return _usage(prefix, "troll stop", "annoy|reactannoy <@user|id>")
        return BuiltinResult(replies=[f"Troll **off** for `{user_id}`."], delete_invocation=True)

    return _usage(prefix, "troll", "ghostping | annoy | reactannoy | stop")
