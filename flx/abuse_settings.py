"""Abuse mode flags (GUI-confirmed)."""

from __future__ import annotations

from flx.state import load_gui_settings, save_gui_settings

ABUSE_WARNING = (
    "Do you want to turn on abuse mode? This is unsafe due to abusing the Fluxer API "
    "and may lead to account bans. Use at your own risk."
)


def abuse_mode_enabled() -> bool:
    return bool(load_gui_settings().get("abuse_mode", False))


def abuse_pending_confirm() -> bool:
    return bool(load_gui_settings().get("abuse_pending_confirm", False))


def request_abuse_confirm() -> None:
    save_gui_settings(abuse_pending_confirm=True)


def confirm_abuse_mode() -> None:
    save_gui_settings(abuse_mode=True, abuse_pending_confirm=False)


def cancel_abuse_confirm() -> None:
    save_gui_settings(abuse_pending_confirm=False)


def disable_abuse_mode() -> None:
    save_gui_settings(abuse_mode=False, abuse_pending_confirm=False)


def require_abuse_mode() -> str | None:
    if abuse_mode_enabled():
        return None
    if abuse_pending_confirm():
        return "Abuse mode is waiting for confirmation in the Flx dashboard."
    return f"Abuse mode is off. Type `{_prefix()}abuse` and confirm in the GUI first."


def _prefix() -> str:
    from flx.config import command_prefix

    return command_prefix()
