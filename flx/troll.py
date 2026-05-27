"""Background troll handlers (MESSAGE_CREATE / MESSAGE_REACTION_ADD)."""

from __future__ import annotations

import threading
from typing import Any

from flx.state import load_gui_settings, save_gui_settings


class TrollManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()

    def _state(self) -> dict[str, Any]:
        settings = load_gui_settings()
        troll = settings.get("troll")
        if not isinstance(troll, dict):
            troll = {}
        return troll

    def _save(self, troll: dict[str, Any]) -> None:
        save_gui_settings(troll=troll)

    def set_delete_target(self, user_id: str, enabled: bool) -> None:
        with self._lock:
            troll = self._state()
            targets = set(troll.get("delete_targets") or [])
            if enabled:
                targets.add(user_id)
            else:
                targets.discard(user_id)
            troll["delete_targets"] = sorted(targets)
            self._save(troll)

    def set_unreact_target(self, user_id: str, enabled: bool) -> None:
        with self._lock:
            troll = self._state()
            targets = set(troll.get("unreact_targets") or [])
            if enabled:
                targets.add(user_id)
            else:
                targets.discard(user_id)
            troll["unreact_targets"] = sorted(targets)
            self._save(troll)

    def set_react_annoy(self, user_id: str | None, emoji: str | None) -> None:
        with self._lock:
            troll = self._state()
            if user_id and emoji:
                troll["react_annoy"] = {"user_id": user_id, "emoji": emoji}
            else:
                troll.pop("react_annoy", None)
            self._save(troll)

    def delete_targets(self) -> set[str]:
        return set(self._state().get("delete_targets") or [])

    def unreact_targets(self) -> set[str]:
        return set(self._state().get("unreact_targets") or [])

    def react_annoy(self) -> tuple[str, str] | None:
        raw = self._state().get("react_annoy")
        if isinstance(raw, dict) and raw.get("user_id") and raw.get("emoji"):
            return str(raw["user_id"]), str(raw["emoji"])
        return None

    def on_message_create(self, rest: Any, data: dict) -> None:
        author = (data.get("author") or {}).get("id")
        if not author:
            return
        author_id = str(author)
        channel_id = str(data.get("channel_id", ""))
        message_id = str(data.get("id", ""))
        if not channel_id or not message_id:
            return

        if author_id in self.delete_targets():
            try:
                rest.delete_message(channel_id, message_id)
            except RuntimeError:
                pass
            return

        annoy = self.react_annoy()
        if annoy and author_id == annoy[0]:
            user_id, emoji = annoy
            try:
                rest.add_reaction(channel_id, message_id, emoji)
            except RuntimeError:
                pass

    def on_reaction_add(self, rest: Any, data: dict) -> None:
        user_id = str((data.get("user_id") or data.get("member", {}).get("user", {}).get("id") or ""))
        if not user_id or user_id not in self.unreact_targets():
            return
        channel_id = str(data.get("channel_id", ""))
        message_id = str(data.get("message_id", ""))
        emoji = data.get("emoji") or {}
        emoji_key = _emoji_key(emoji)
        if not channel_id or not message_id or not emoji_key:
            return
        try:
            rest.remove_user_reaction(channel_id, message_id, emoji_key, user_id)
        except RuntimeError:
            pass


def _emoji_key(emoji: dict) -> str:
    if emoji.get("id"):
        name = emoji.get("name") or "emoji"
        return f"{name}:{emoji['id']}"
    return str(emoji.get("name") or "")


_manager: TrollManager | None = None


def get_troll_manager() -> TrollManager:
    global _manager
    if _manager is None:
        _manager = TrollManager()
    return _manager
