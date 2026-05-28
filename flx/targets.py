"""Resolve command targets (mentions, replies, IDs)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flx.fluxerscript import FlxMessage
from flx.parse_util import parse_user_id

if TYPE_CHECKING:
    from flx.rest import FluxerREST


def resolve_target_user_id(
    target_raw: str,
    msg: FlxMessage,
    rest: FluxerREST,
    *,
    empty_hint: str,
) -> str:
    text = target_raw.strip()
    if text:
        return parse_user_id(text)

    ref = msg.raw.get("message_reference")
    if isinstance(ref, dict) and ref.get("message_id"):
        channel_id = str(ref.get("channel_id") or msg.channel_id)
        message_id = str(ref["message_id"])
        try:
            replied = rest.get_message(channel_id, message_id)
            author = replied.get("author") or {}
            user_id = author.get("id")
            if user_id:
                return str(user_id)
        except RuntimeError:
            pass

    mentions = msg.raw.get("mentions") or []
    if len(mentions) == 1:
        user_id = (mentions[0] or {}).get("id")
        if user_id:
            return str(user_id)

    raise ValueError(empty_hint)
