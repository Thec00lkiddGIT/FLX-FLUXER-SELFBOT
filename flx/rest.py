"""Minimal Fluxer REST client (urllib, no extra deps)."""

from __future__ import annotations

import json
import threading
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from flx.rate_limit import urlopen_with_rate_limit
from flx.textutil import MAX_MESSAGE_LENGTH, split_message_content

# Small gap between multi-part messages in the same channel.
CHUNK_SEND_GAP_SECONDS = 0.35


class FluxerREST:
    def __init__(self, token: str, api_base: str) -> None:
        self.token = token.strip()
        if self.token.lower().startswith("bearer "):
            self.token = self.token[7:].strip()
        base = api_base.rstrip("/")
        if base.endswith("/api"):
            base = base[: -len("/api")]
        if not base.endswith("/v1"):
            base = f"{base}/v1"
        self.base = base
        self._channel_locks_guard = threading.Lock()
        self._channel_send_locks: dict[str, threading.Lock] = {}

    def _channel_send_lock(self, channel_id: str) -> threading.Lock:
        with self._channel_locks_guard:
            lock = self._channel_send_locks.get(channel_id)
            if lock is None:
                lock = threading.Lock()
                self._channel_send_locks[channel_id] = lock
            return lock

    def _open(self, req: urllib.request.Request, *, timeout: float = 30) -> object:
        return urlopen_with_rate_limit(req, timeout=timeout)

    def _request(
        self,
        method: str,
        route: str,
        *,
        body: dict | None = None,
        auth: bool = True,
    ) -> Any:
        url = f"{self.base}{route}" if route.startswith("/") else f"{self.base}/{route}"
        data = None
        headers = {
            "User-Agent": "Flx/1.0 (Fluxer selfbot)",
            "Accept": "application/json",
        }
        if auth:
            headers["Authorization"] = self.token
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with self._open(req, timeout=30) as resp:
                status = getattr(resp, "status", 200)
                if status in (204, 205):
                    return None
                raw = resp.read()
                if not raw or not raw.strip():
                    return None
                try:
                    return json.loads(raw.decode("utf-8"))
                except json.JSONDecodeError:
                    return None
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
        except RuntimeError:
            raise

    def get_me(self) -> dict:
        return self._request("GET", "/users/@me")

    def get_channel(self, channel_id: str) -> dict:
        result = self._request("GET", f"/channels/{channel_id}")
        return result if isinstance(result, dict) else {}

    def list_channel_messages(
        self,
        channel_id: str,
        *,
        limit: int = 50,
        before: str | None = None,
    ) -> list[dict]:
        limit = max(1, min(int(limit), 100))
        query = urllib.parse.urlencode(
            {k: v for k, v in (("limit", str(limit)), ("before", before)) if v}
        )
        route = f"/channels/{channel_id}/messages"
        if query:
            route = f"{route}?{query}"
        result = self._request("GET", route)
        return result if isinstance(result, list) else []

    def create_guild_channel(
        self,
        guild_id: str,
        *,
        name: str,
        parent_id: str | None = None,
        type_: int = 0,
    ) -> dict:
        body: dict[str, Any] = {"name": name, "type": type_}
        if parent_id:
            body["parent_id"] = parent_id
        result = self._request("POST", f"/guilds/{guild_id}/channels", body=body)
        return result if isinstance(result, dict) else {}

    def get_message(self, channel_id: str, message_id: str) -> dict:
        result = self._request(
            "GET",
            f"/channels/{channel_id}/messages/{message_id}",
        )
        return result if isinstance(result, dict) else {}

    def get_user(self, user_id: str) -> dict:
        result = self._request("GET", f"/users/{user_id}")
        return result if isinstance(result, dict) else {}

    def get_user_profile(self, user_id: str) -> dict:
        result = self._request("GET", f"/users/{user_id}/profile")
        return result if isinstance(result, dict) else {}

    def get_gateway(self) -> dict:
        """Bot-only on many instances; user selfbots should fall back to wss://gateway.fluxer.app."""
        return self._request("GET", "/gateway")

    def _message_payload(
        self,
        content: str,
        *,
        reply_to: str | None = None,
        channel_id: str | None = None,
        guild_id: str | None = None,
        attachments: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        if len(content) > MAX_MESSAGE_LENGTH:
            content = content[:MAX_MESSAGE_LENGTH]
        payload: dict[str, Any] = {"content": content}
        if attachments:
            payload["attachments"] = attachments
        if reply_to and channel_id:
            ref: dict[str, Any] = {
                "message_id": reply_to,
                "channel_id": channel_id,
            }
            if guild_id:
                ref["guild_id"] = guild_id
            payload["message_reference"] = ref
        return payload

    def _encode_multipart(
        self,
        fields: dict[str, str],
        files: list[tuple[str, bytes, str]],
    ) -> tuple[bytes, str]:
        boundary = f"----Flx{uuid.uuid4().hex}"
        parts: list[bytes] = []
        for name, value in fields.items():
            parts.append(
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                f"{value}\r\n".encode()
            )
        for index, (filename, data, content_type) in enumerate(files):
            parts.append(
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="files[{index}]"; '
                f'filename="{filename}"\r\n'
                f"Content-Type: {content_type}\r\n\r\n".encode()
            )
            parts.append(data)
            parts.append(b"\r\n")
        parts.append(f"--{boundary}--\r\n".encode())
        return b"".join(parts), boundary

    def _send_message_once(
        self,
        channel_id: str,
        content: str,
        *,
        reply_to: str | None = None,
        guild_id: str | None = None,
        files: list[tuple[str, bytes]] | None = None,
    ) -> dict:
        if files:
            attachment_meta = [
                {"id": index, "filename": name}
                for index, (name, _) in enumerate(files)
            ]
            payload = self._message_payload(
                content,
                reply_to=reply_to,
                channel_id=channel_id,
                guild_id=guild_id,
                attachments=attachment_meta,
            )
            multipart_files = [
                (name, data, "application/octet-stream")
                for name, data in files
            ]
            body, boundary = self._encode_multipart(
                {"payload_json": json.dumps(payload)},
                multipart_files,
            )
            url = f"{self.base}/channels/{channel_id}/messages"
            req = urllib.request.Request(
                url,
                data=body,
                headers={
                    "Authorization": self.token,
                    "User-Agent": "Flx/1.0 (Fluxer selfbot)",
                    "Content-Type": f"multipart/form-data; boundary={boundary}",
                },
                method="POST",
            )
            with self._open(req, timeout=60) as resp:
                raw = resp.read()
                return json.loads(raw.decode("utf-8")) if raw else {}

        payload = self._message_payload(
            content,
            reply_to=reply_to,
            channel_id=channel_id,
            guild_id=guild_id,
        )
        return self._request("POST", f"/channels/{channel_id}/messages", body=payload) or {}

    def send_message(
        self,
        channel_id: str,
        content: str,
        *,
        reply_to: str | None = None,
        guild_id: str | None = None,
        files: list[tuple[str, bytes]] | None = None,
    ) -> dict:
        chunks = split_message_content(content)
        if not chunks:
            if files:
                chunks = [""]
            else:
                return {}

        last: dict = {}
        with self._channel_send_lock(channel_id):
            for index, chunk in enumerate(chunks):
                last = self._send_message_once(
                    channel_id,
                    chunk,
                    reply_to=reply_to if index == 0 else None,
                    guild_id=guild_id,
                    files=files if index == 0 else None,
                )
                if index < len(chunks) - 1 and CHUNK_SEND_GAP_SECONDS > 0:
                    time.sleep(CHUNK_SEND_GAP_SECONDS)
        return last

    def edit_message(self, channel_id: str, message_id: str, content: str) -> dict:
        chunks = split_message_content(content)
        if not chunks:
            return {}
        return self._request(
            "PATCH",
            f"/channels/{channel_id}/messages/{message_id}",
            body={"content": chunks[0]},
        )

    def delete_message(self, channel_id: str, message_id: str) -> None:
        self._request("DELETE", f"/channels/{channel_id}/messages/{message_id}")

    def set_presence(self, status: str) -> None:
        self._request("PATCH", "/users/@me/settings", body={"status": status})

    def set_activity(
        self,
        *,
        status: str = "online",
        activity_type: int | None = None,
        activity_name: str | None = None,
        clear: bool = False,
    ) -> None:
        body: dict[str, Any] = {"status": status}
        if clear:
            body["custom_status"] = None
            body["activities"] = []
        elif activity_name and activity_type is not None:
            body["activities"] = [
                {"type": activity_type, "name": activity_name[:128]},
            ]
        self._request("PATCH", "/users/@me/settings", body=body)

    def get_guild(self, guild_id: str) -> dict:
        result = self._request("GET", f"/guilds/{guild_id}")
        return result if isinstance(result, dict) else {}

    def patch_guild(self, guild_id: str, body: dict[str, Any]) -> dict:
        result = self._request("PATCH", f"/guilds/{guild_id}", body=body)
        return result if isinstance(result, dict) else {}

    def list_guild_channels(self, guild_id: str) -> list[dict]:
        result = self._request("GET", f"/guilds/{guild_id}/channels")
        return result if isinstance(result, list) else []

    def list_guild_members(
        self,
        guild_id: str,
        *,
        limit: int = 1000,
        after: str | None = None,
    ) -> list[dict]:
        limit = max(1, min(int(limit), 1000))
        params: dict[str, str] = {"limit": str(limit)}
        if after:
            params["after"] = after
        query = urllib.parse.urlencode(params)
        result = self._request("GET", f"/guilds/{guild_id}/members?{query}")
        return result if isinstance(result, list) else []

    @staticmethod
    def _encode_emoji(emoji: str) -> str:
        return urllib.parse.quote(emoji, safe="")

    def add_reaction(self, channel_id: str, message_id: str, emoji: str) -> None:
        enc = self._encode_emoji(emoji)
        self._request(
            "PUT",
            f"/channels/{channel_id}/messages/{message_id}/reactions/{enc}/@me",
        )

    def remove_user_reaction(
        self,
        channel_id: str,
        message_id: str,
        emoji: str,
        user_id: str,
    ) -> None:
        enc = self._encode_emoji(emoji)
        self._request(
            "DELETE",
            f"/channels/{channel_id}/messages/{message_id}/reactions/{enc}/{user_id}",
        )

    def ban_member(
        self,
        guild_id: str,
        user_id: str,
        *,
        delete_message_days: int = 0,
        reason: str | None = None,
    ) -> None:
        body: dict[str, Any] = {"delete_message_days": delete_message_days}
        if reason:
            body["reason"] = reason
        self._request("PUT", f"/guilds/{guild_id}/bans/{user_id}", body=body)

    def kick_member(
        self,
        guild_id: str,
        user_id: str,
        *,
        reason: str | None = None,
    ) -> None:
        route = f"/guilds/{guild_id}/members/{user_id}"
        if reason:
            route = f"{route}?{urllib.parse.urlencode({'reason': reason})}"
        self._request("DELETE", route)
