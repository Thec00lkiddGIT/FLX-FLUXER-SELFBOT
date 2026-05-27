#!/usr/bin/env python3
"""Launch FLX FLUXER SELFBOT (native dashboard or browser UI)."""

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


def _run_web(host: str, port: int) -> int:
    import webbrowser

    from flx.gui.bootstrap import prepare_runtime
    from flx.gui.server import run_server
    from flx.runtime import get_runtime

    server = run_server(host, port)
    url = f"http://{host}:{port}/"
    print(f"FLX FLUXER SELFBOT web UI: {url}", flush=True)
    prepare_runtime()
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        get_runtime().stop()
        server.shutdown()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="FLX FLUXER SELFBOT")
    parser.add_argument("--web", action="store_true", help="Open in browser")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()

    if args.web:
        return _run_web(args.host, args.port)

    from flx.gui.native_window import run_native_app

    run_native_app(args.host, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
