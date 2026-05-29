"""Fluxer WebSocket gateway (Discord-compatible protocol)."""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from typing import Callable

from flx.rest import FluxerREST

log = logging.getLogger("flx.gateway")

OP_DISPATCH = 0
OP_HEARTBEAT = 1
OP_IDENTIFY = 2
OP_HELLO = 10
OP_HEARTBEAT_ACK = 11

EventHandler = Callable[[str, dict], None]

# User selfbots: /v1/gateway often 404; connect directly (same as fluxer-selfbot).
DEFAULT_GATEWAY_URL = "wss://gateway.fluxer.app"


class GatewayWorker:
    """Runs asyncio gateway loop in a background thread."""

    def __init__(
        self,
        token: str,
        api_base: str,
        on_event: EventHandler,
        *,
        on_ready: Callable[[dict], None] | None = None,
        on_error: Callable[[str], None] | None = None,
    ) -> None:
        self.token = token
        self.rest = FluxerREST(token, api_base)
        self.on_event = on_event
        self.on_ready_cb = on_ready
        self.on_error = on_error
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self.user: dict | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run_thread, name="flx-gateway", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _gateway_url(self) -> str:
        try:
            gw = self.rest.get_gateway()
            url = str(gw.get("url") or "").strip()
            if url:
                return url
        except RuntimeError as exc:
            if "404" not in str(exc) and "NOT_FOUND" not in str(exc):
                raise
            log.info("GET /gateway unavailable; using %s", DEFAULT_GATEWAY_URL)
        return DEFAULT_GATEWAY_URL

    def _run_thread(self) -> None:
        try:
            asyncio.run(self._main())
        except Exception as exc:  # noqa: BLE001
            log.exception("Gateway crashed")
            if self.on_error:
                self.on_error(str(exc))

    async def _main(self) -> None:
        try:
            import websockets
        except ImportError as exc:
            raise RuntimeError("Install websockets: pip install websockets") from exc

        url = self._gateway_url()
        if "?" not in url:
            url = f"{url}?v=1&encoding=json"

        heartbeat_interval = 41250
        seq: int | None = None

        while not self._stop.is_set():
            try:
                async with websockets.connect(url, max_size=2**20) as ws:
                    identified = False
                    while not self._stop.is_set():
                        raw = await asyncio.wait_for(ws.recv(), timeout=60)
                        payload = json.loads(raw)
                        op = payload.get("op")

                        if op == OP_HELLO:
                            heartbeat_interval = payload["d"]["heartbeat_interval"]
                            await ws.send(
                                json.dumps(
                                    {
                                        "op": OP_IDENTIFY,
                                        "d": {
                                            "token": self.token,
                                            "properties": {
                                                "os": "Windows",
                                                "browser": "Chrome",
                                                "device": "Chrome",
                                            },
                                            "compress": False,
                                            "large_threshold": 250,
                                        },
                                    }
                                )
                            )
                            identified = True

                            async def heartbeat() -> None:
                                while not self._stop.is_set():
                                    await asyncio.sleep(heartbeat_interval / 1000)
                                    await ws.send(json.dumps({"op": OP_HEARTBEAT, "d": seq}))

                            asyncio.create_task(heartbeat())
                            continue

                        if op == OP_HEARTBEAT:
                            await ws.send(json.dumps({"op": OP_HEARTBEAT, "d": seq}))
                            continue

                        if op == OP_HEARTBEAT_ACK:
                            continue

                        if op == OP_DISPATCH:
                            if payload.get("s") is not None:
                                seq = payload["s"]
                            event = payload.get("t")
                            data = payload.get("d")
                            if event == "READY" and isinstance(data, dict):
                                self.user = data.get("user")
                                if self.on_ready_cb and self.user:
                                    self.on_ready_cb(self.user)
                            if isinstance(data, dict) and event in (
                                "MESSAGE_CREATE",
                                "MESSAGE_REACTION_ADD",
                            ):
                                await asyncio.to_thread(self.on_event, event, data)
            except asyncio.CancelledError:
                break
            except Exception as exc:  # noqa: BLE001
                if self._stop.is_set():
                    break
                log.warning("Gateway reconnecting: %s", exc)
                if self.on_error:
                    self.on_error(str(exc))
                await asyncio.sleep(3)
