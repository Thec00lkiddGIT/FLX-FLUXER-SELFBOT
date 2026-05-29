#!/usr/bin/env python3
"""Launch FLX (native dashboard or browser UI)."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def _venv_python(root: Path) -> Path | None:
    if sys.platform == "win32":
        candidate = root / ".venv" / "Scripts" / "python.exe"
    else:
        candidate = root / ".venv" / "bin" / "python3"
    return candidate if candidate.is_file() else None


def _reexec_with_project_venv() -> None:
    if os.environ.get("FLX_GUI_REEXEC") == "1":
        return
    root = Path(__file__).resolve().parent
    venv_py = _venv_python(root)
    if venv_py is None:
        return
    try:
        if Path(sys.executable).resolve() == venv_py.resolve():
            return
    except OSError:
        pass
    os.environ["FLX_GUI_REEXEC"] = "1"
    os.execv(str(venv_py), [str(venv_py), *sys.argv])


_reexec_with_project_venv()


def _is_chromeos_linux() -> bool:
    """True when running in ChromeOS Crostini (Linux on Chromebook)."""
    if sys.platform != "linux":
        return False
    if os.environ.get("CROS_USER_ID_DIR"):
        return True
    try:
        return "chromebook" in Path("/etc/os-release").read_text().lower()
    except OSError:
        return False


def _run_web(host: str, port: int, *, chromebook: bool = False) -> int:
    import webbrowser

    import os

    from flx.gui.bootstrap import prepare_runtime
    from flx.gui.server import run_server
    from flx.runtime import get_runtime
    from flx.utility_cmds import set_app_exit_callback

    set_app_exit_callback(lambda: os._exit(0))

    server = run_server(host, port)
    url = f"http://{host}:{port}/"
    if chromebook or _is_chromeos_linux():
        print("Chromebook mode: open this URL in Chrome:", url, flush=True)
    else:
        print(f"FLX web UI: {url}", flush=True)
    prepare_runtime()
    try:
        webbrowser.open(url)
    except OSError:
        print("Open the URL above in your browser.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        get_runtime().stop()
        server.shutdown()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="FLX")
    parser.add_argument("--web", action="store_true", help="Open dashboard in browser")
    parser.add_argument(
        "--chromebook",
        action="store_true",
        help="Chromebook mode: browser UI (best on ChromeOS Linux)",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()

    if args.web or args.chromebook:
        return _run_web(args.host, args.port, chromebook=args.chromebook)

    from flx.gui.native_window import run_native_app

    run_native_app(args.host, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
