"""!info user - profile and snowflake decode."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import TYPE_CHECKING

from flx.fluxerscript import FlxMessage
from flx.snowflake import decode_snowflake, format_snowflake_block
from flx.targets import resolve_target_user_id

if TYPE_CHECKING:
    from flx.rest import FluxerREST

_DISCOVERY_CACHE: dict | None = None


def _discovery(rest: FluxerREST) -> dict:
    global _DISCOVERY_CACHE
    if _DISCOVERY_CACHE is not None:
        return _DISCOVERY_CACHE
    root = rest.base.rsplit("/v1", 1)[0]
    url = f"{root}/.well-known/fluxer"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Flx/1.0", "Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
            data = json.loads(raw.decode("utf-8")) if raw else {}
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
        data = {}
    _DISCOVERY_CACHE = data if isinstance(data, dict) else {}
    return _DISCOVERY_CACHE


def _static_cdn(rest: FluxerREST) -> str:
    endpoints = _discovery(rest).get("endpoints") or {}
    cdn = endpoints.get("static_cdn") or endpoints.get("media") or ""
    return str(cdn).rstrip("/")


def _avatar_hash(user: dict) -> str | None:
    for key in ("avatar_hash", "avatar", "avatarHash"):
        value = user.get(key)
        if value and str(value).strip():
            return str(value).strip()
    return None


def avatar_url(rest: FluxerREST, user_id: str, avatar_hash: str | None) -> str | None:
    if not avatar_hash:
        return None
    cdn = _static_cdn(rest)
    if not cdn:
        return None
    ext = "gif" if str(avatar_hash).startswith("a_") else "png"
    return f"{cdn}/avatars/{user_id}/{avatar_hash}.{ext}"


def _fetch_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Flx/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read()


def _format_tag(username: str, discriminator: str | int | None) -> str:
    user = username or "unknown"
    if discriminator is None or discriminator == "":
        return f"@{user}"
    disc = str(discriminator).zfill(4) if str(discriminator).isdigit() else str(discriminator)
    return f"@{user}#{disc}"


def user_info_lookup(
    msg: FlxMessage,
    rest: FluxerREST,
    target_raw: str,
) -> tuple[str, list[tuple[str, bytes]]]:
    if target_raw.strip():
        hint = (
            "Provide a @user, user ID, or reply to their message. "
            "Example: `!info user @someone`"
        )
        user_id = resolve_target_user_id(target_raw, msg, rest, empty_hint=hint)
    else:
        me = rest.get_me()
        user_id = str(me.get("id") or "")
        if not user_id:
            raise RuntimeError("Could not read your user ID.")

    user: dict = {}
    try:
        user = rest.get_user(user_id)
    except RuntimeError:
        pass
    if not user:
        try:
            profile = rest.get_user_profile(user_id)
            if isinstance(profile, dict):
                user = profile.get("user") if isinstance(profile.get("user"), dict) else profile
        except RuntimeError:
            pass
    if not user:
        raise RuntimeError(f"Could not load user `{user_id}`.")

    username = str(user.get("username") or "?")
    global_name = str(user.get("global_name") or user.get("display_name") or "").strip()
    discriminator = user.get("discriminator")
    display = global_name or username
    tag = _format_tag(username, discriminator)

    parts = decode_snowflake(user_id)

    lines = [
        f"**{display}** ({tag})",
        f"**Username:** `{username}`",
        f"**Tag:** `{tag}`",
        f"**User ID:** `{user_id}`",
    ]
    if global_name and global_name != username:
        lines.append(f"**Display name:** `{global_name}`")
    if discriminator is not None and str(discriminator) != "":
        lines.append(f"**Discriminator:** `{discriminator}`")
    if user.get("bot"):
        lines.append("**Bot:** yes")

    lines.append("")
    lines.append("**Snowflake decode** (Fluxer epoch, [fluxertools](https://fluxertools.com/tools/snowflake))")
    lines.append(format_snowflake_block(parts))

    files: list[tuple[str, bytes]] = []
    ahash = _avatar_hash(user)
    url = avatar_url(rest, user_id, ahash)
    if url:
        lines.append(f"**Avatar:** {url}")
        try:
            data = _fetch_bytes(url)
            ext = "gif" if url.endswith(".gif") else "png"
            files.append((f"avatar_{user_id}.{ext}", data))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
            lines.append("_(Could not download avatar image.)_")

    return "\n".join(lines), files
