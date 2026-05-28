"""Abuse mode flags (GUI-confirmed)."""

from __future__ import annotations

from flx.state import load_gui_settings, save_gui_settings

ABUSE_WARNING = (
    "Abuse mode unlocks commands that hammer the Fluxer API — spam, mass actions, that kind of thing. "
    "It's risky and can get your account banned. Only turn this on if you really mean it."
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
        return "Abuse mode is waiting — confirm it in the FLX app first."
    return f"Abuse mode is off. Run `{_prefix()}abuse` in Fluxer and confirm in the app."


def _prefix() -> str:
    from flx.config import command_prefix

    return command_prefix()
