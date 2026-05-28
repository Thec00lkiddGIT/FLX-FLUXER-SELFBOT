"""Native app window (macOS WebKit / Windows Edge WebView2)."""

from __future__ import annotations

import sys
import threading
import time

from flx.version import APP_NAME

APP_TITLE = APP_NAME


def _webview_gui_backend() -> str | None:
    if sys.platform == "darwin":
        return "cocoa"
    if sys.platform == "win32":
        return "edgechromium"
    if sys.platform.startswith("linux"):
        return "gtk"
    return None


def run_native_app(host: str = "127.0.0.1", port: int = 8766) -> None:
    try:
        import webview
    except ImportError as exc:
        raise SystemExit(
            "Missing pywebview. Install:\n\n  pip install pywebview websockets\n"
        ) from exc

    from flx.gui.bootstrap import prepare_runtime
    from flx.gui.server import run_server
    from flx.runtime import get_runtime

    server = run_server(host, port)
    url = f"http://{host}:{port}/"

    threading.Thread(target=server.serve_forever, name="flx-http", daemon=True).start()
    time.sleep(0.3)
    prepare_runtime()

    webview.create_window(
        APP_TITLE,
        url,
        width=1100,
        height=700,
        min_size=(880, 560),
        background_color="#060a12",
        text_select=True,
    )
    backend = _webview_gui_backend()
    if backend:
        webview.start(gui=backend)
    else:
        webview.start()
    get_runtime().stop()
    server.shutdown()
