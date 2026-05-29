"""Persisted GUI settings and stats."""

from __future__ import annotations

import json

from flx.paths import gui_settings_file, stats_file


def load_gui_settings() -> dict:
    path = gui_settings_file()
    defaults = {
        "autostart": False,
        "delete_commands": True,
        "verbose": True,
        "copycat_enabled": False,
        "copycat_user_id": "",
        "afk_enabled": False,
        "afk_message": "I'm AFK right now.",
    }
    if not path.is_file():
        return defaults
    try:
        data = json.loads(path.read_text())
        return {**defaults, **(data if isinstance(data, dict) else {})}
    except (json.JSONDecodeError, OSError):
        return defaults


def save_gui_settings(**kwargs: object) -> None:
    current = load_gui_settings()
    current.update(kwargs)
    gui_settings_file().write_text(json.dumps(current, indent=2) + "\n")


def load_stats() -> dict:
    path = stats_file()
    defaults = {"commands_used": 0, "messages_seen": 0}
    if not path.is_file():
        return defaults
    try:
        data = json.loads(path.read_text())
        return {**defaults, **(data if isinstance(data, dict) else {})}
    except (json.JSONDecodeError, OSError):
        return defaults


def save_stats(commands_used: int, messages_seen: int) -> None:
    stats_file().write_text(
        json.dumps(
            {"commands_used": commands_used, "messages_seen": messages_seen},
            indent=2,
        )
        + "\n"
    )
