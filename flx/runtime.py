"""Background Fluxer gateway loop with events for the GUI."""

from __future__ import annotations

import re
import threading
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from flx.commands import run_builtin
from flx.config import api_base_url, command_prefix, fluxer_token, load_dotenv
from flx.fluxerscript import CommandContext, FlxMessage
from flx.gateway import GatewayWorker
from flx.rest import FluxerREST
from flx.script_hub import dispatch_hub_command, dispatch_message_listeners, ensure_registry
from flx.state import load_gui_settings, save_gui_settings, save_stats
from flx.troll import get_troll_manager
from flx.version import APP_VERSION

_runtime: "BotRuntime | None" = None


def get_runtime() -> "BotRuntime":
    global _runtime
    if _runtime is None:
        _runtime = BotRuntime()
    return _runtime


@dataclass
class BotEvent:
    id: int
    kind: str
    title: str
    body: str
    source: str
    ts: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BotSettings:
    delete_commands: bool = True
    verbose: bool = True
    running: bool = False


class BotRuntime:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._settings = BotSettings()
        self._gateway: GatewayWorker | None = None
        self._rest: FluxerREST | None = None
        self._user_id: str | None = None
        self._user_name: str = "Flx"
        self._events: deque[BotEvent] = deque(maxlen=200)
        self._event_id = 0
        self._error: str | None = None
        self._commands_used = 0
        self._messages_seen = 0
        load_dotenv()
        gui = load_gui_settings()
        self._settings.delete_commands = bool(gui.get("delete_commands", True))
        self._settings.verbose = bool(gui.get("verbose", True))

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

    def _push_event(self, kind: str, title: str, body: str, source: str = "Flx") -> None:
        with self._lock:
            self._event_id += 1
            self._events.append(
                BotEvent(
                    id=self._event_id,
                    kind=kind,
                    title=title,
                    body=body,
                    source=source,
                    ts=self._now_iso(),
                )
            )

    def rest_client(self) -> FluxerREST | None:
        """Shared Fluxer REST client while the bot is running."""
        return self._rest

    def settings(self) -> BotSettings:
        with self._lock:
            return BotSettings(**asdict(self._settings))

    def update_settings(self, **kwargs: object) -> BotSettings:
        persist: dict[str, object] = {}
        with self._lock:
            for key, value in kwargs.items():
                if hasattr(self._settings, key):
                    setattr(self._settings, key, value)
                    if key in ("delete_commands", "verbose"):
                        persist[key] = value
            result = BotSettings(**asdict(self._settings))
        if persist:
            save_gui_settings(**persist)
        return result

    def start(self) -> tuple[bool, str]:
        with self._lock:
            if self._settings.running:
                return True, "Already connected"
            self._error = None
            self._settings.running = True

        try:
            load_dotenv()
            token = fluxer_token()
            api = api_base_url()
            self._rest = FluxerREST(token, api)
            me = self._rest.get_me()
            self._user_id = str(me.get("id", ""))
            self._user_name = str(me.get("global_name") or me.get("username") or "Flx")
        except Exception as exc:  # noqa: BLE001
            with self._lock:
                self._settings.running = False
                self._error = str(exc)
            self._push_event("error", "Couldn't connect", str(exc))
            return False, str(exc)

        ensure_registry()

        def on_ready(user: dict) -> None:
            self._user_id = str(user.get("id", self._user_id or ""))
            self._user_name = str(user.get("global_name") or user.get("username") or "Flx")
            self._push_event("success", "Connected", f"Logged in as {self._user_name}")

        def on_error(msg: str) -> None:
            with self._lock:
                self._error = msg
            self._push_event("error", "Connection trouble", msg)

        def on_disconnect() -> None:
            with self._lock:
                self._settings.running = False
            self._push_event("info", "Disconnected", "Gateway thread stopped.")

        self._gateway = GatewayWorker(
            token,
            api,
            self._on_gateway_event,
            on_ready=on_ready,
            on_error=on_error,
            on_disconnect=on_disconnect,
        )
        self._gateway.start()
        self._push_event("success", "Bot started", "Watching Fluxer for commands.")
        return True, "Started"

    def stop(self) -> None:
        if self._gateway:
            self._gateway.stop()
            self._gateway = None
        with self._lock:
            self._settings.running = False
        self._push_event("info", "Bot stopped", "Gateway disconnected.")

    def events_since(self, after_id: int) -> dict:
        with self._lock:
            return {
                "latest_id": self._event_id,
                "events": [e.to_dict() for e in self._events if e.id > after_id],
            }

    def status(self) -> dict:
        import os

        from flx.abuse_settings import (
            ABUSE_WARNING,
            abuse_mode_enabled,
            abuse_pending_confirm,
        )

        import sys

        from flx.config import has_fluxer_token

        load_dotenv()
        has_token = has_fluxer_token()
        is_ios = sys.platform == "ios" or os.environ.get("FLX_IOS") == "1"
        is_android = sys.platform == "android" or os.environ.get("FLX_ANDROID") == "1"
        with self._lock:
            gw = self._gateway
            gw_alive = (
                gw is not None
                and gw._thread is not None
                and gw._thread.is_alive()
                and self._settings.running
            )
            return {
                "running": gw_alive,
                "delete_commands": self._settings.delete_commands,
                "verbose": self._settings.verbose,
                "display_name": self._user_name,
                "handle": self._user_name.lower().replace(" ", ""),
                "user_id": self._user_id or ("…" if has_token else None),
                "version": APP_VERSION,
                "commands_used": self._commands_used,
                "messages_seen": self._messages_seen,
                "error": self._error,
                "token_ok": has_token,
                "api_url": api_base_url(),
                "prefix": command_prefix(),
                "latest_event_id": self._event_id,
                "abuse_mode": abuse_mode_enabled(),
                "abuse_pending_confirm": abuse_pending_confirm(),
                "abuse_warning": ABUSE_WARNING,
                "platform": "ios" if is_ios else ("android" if is_android else "desktop"),
            }

    def _command_name(self, body: str) -> str | None:
        prefix = command_prefix()
        if not body.startswith(prefix):
            return None
        rest = body[len(prefix) :].strip()
        m = re.match(r"^(\w+)", rest)
        return m.group(1).lower() if m else None

    def _command_args(self, body: str) -> str:
        prefix = command_prefix()
        rest = body[len(prefix) :].strip()
        parts = rest.split(maxsplit=1)
        return parts[1] if len(parts) > 1 else ""

    def _on_gateway_event(self, event: str, data: dict) -> None:
        if event == "MESSAGE_REACTION_ADD":
            if self._rest:
                get_troll_manager().on_reaction_add(self._rest, data)
            return
        if event == "MESSAGE_CREATE":
            self._on_message(data)

    def _on_message(self, data: dict) -> None:
        msg = FlxMessage.from_gateway(data)
        with self._lock:
            self._messages_seen += 1

        if self._rest and msg.author_id != self._user_id:
            get_troll_manager().on_message_create(self._rest, data)

        if not self._user_id or msg.author_id != self._user_id:
            from flx.utility_cmds import handle_incoming_message

            handle_incoming_message(msg, self._rest, self._user_id)
            for reply in dispatch_message_listeners(msg):
                self._send_text(msg.channel_id, reply)
            return

        settings = self.settings()
        if settings.verbose:
            self._push_event("info", "Message", msg.content[:120] or "(empty)", source="you")

        cmd = self._command_name(msg.content)
        if not cmd:
            return

        args = self._command_args(msg.content)
        rest = self._rest
        if rest is None:
            return

        delete_cmd = settings.delete_commands
        replies: list[str] = []
        script_delete = False

        ctx = CommandContext(
            message=msg,
            script_id="builtin",
            command=cmd,
            args=args,
        )
        builtin = run_builtin(ctx, rest)
        files: list[tuple[str, bytes]] = []
        if builtin is not None:
            replies = ctx.replies
            files = list(builtin.files)
            script_delete = ctx._delete_invocation
        else:
            hub_result, script_delete, hub_files = dispatch_hub_command(cmd, args, msg)
            if hub_result is None and not hub_files:
                return
            if hub_result is None:
                replies = []
            elif isinstance(hub_result, list):
                replies = hub_result
            else:
                replies = [hub_result]
            if hub_files:
                files = list(hub_files)

        with self._lock:
            self._commands_used += 1
        save_stats(self._commands_used, self._messages_seen)

        # Send before delete - replying to a message id that was already deleted causes UNKNOWN_MESSAGE.
        will_delete = delete_cmd or script_delete
        sent_any = False
        for i, text in enumerate(replies):
            try:
                reply_to = msg.id if i == 0 and not will_delete and not sent_any else None
                attach = files if i == 0 and files else None
                rest.send_message(
                    msg.channel_id,
                    text,
                    reply_to=reply_to,
                    guild_id=msg.guild_id,
                    files=attach,
                )
                sent_any = True
            except RuntimeError as exc:
                self._push_event("error", "Message didn't send", str(exc))
                break
        if files and not replies:
            try:
                rest.send_message(
                    msg.channel_id,
                    "",
                    guild_id=msg.guild_id,
                    files=files,
                )
            except RuntimeError as exc:
                self._push_event("error", "Message didn't send", str(exc))

        if will_delete:
            try:
                rest.delete_message(msg.channel_id, msg.id)
            except RuntimeError as exc:
                if "UNKNOWN_MESSAGE" not in str(exc):
                    self._push_event("error", "Couldn't delete that message", str(exc))

        self._push_event("success", f"!{cmd}", args[:80] or "(no args)")

    def _send_text(self, channel_id: str, text: str) -> None:
        if self._rest:
            try:
                self._rest.send_message(channel_id, text)
            except RuntimeError:
                pass
