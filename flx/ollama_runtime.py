"""Bundled Ollama (FLX twin) — launch local Llama and pull the default model."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from flx.config import ollama_base_url, ollama_model
from flx.paths import app_support_dir, project_root

_SETUP_MARKER = ".ollama_flx_bundled_v1"
_START_TIMEOUT_SEC = 90
_pull_lock = threading.Lock()
_pull_thread: threading.Thread | None = None


def is_mobile_platform() -> bool:
    if os.environ.get("FLX_IOS") == "1" or os.environ.get("FLX_ANDROID") == "1":
        return True
    return sys.platform in ("ios", "android")


def ollama_is_localhost(url: str | None = None) -> bool:
    from urllib.parse import urlparse

    host = (urlparse(url or ollama_base_url()).hostname or "").lower()
    return host in ("127.0.0.1", "localhost", "::1", "0.0.0.0", "")


MOBILE_OLLAMA_HINT = (
    "On iPhone/iPad, FLX AI talks to Ollama on your Mac. "
    "On the Mac: run Ollama, enable network access, then add "
    "OLLAMA_BASE_URL=http://YOUR_MAC_IP:11434 to config.env "
    "(Files → On My iPhone → FLX → Flx)."
)


def _system_ollama_app() -> Path:
    return Path("/Applications/Ollama.app")


def _flx_installed_ollama_app() -> Path:
    return app_support_dir() / "ollama" / "Ollama.app"


def _sibling_ollama_app() -> Path | None:
    """Ollama.app next to FLX.app (DMG folder before drag-to-Applications)."""
    if not getattr(sys, "frozen", False):
        return None
    try:
        exe = Path(sys.executable).resolve()
        # .../FLX.app/Contents/MacOS/FLX
        flx_app = exe.parent.parent.parent
        sibling = flx_app.parent / "Ollama.app"
        if sibling.is_dir():
            return sibling
    except (OSError, IndexError):
        pass
    return None


def bundled_ollama_zip() -> Path | None:
    root = project_root()
    for rel in ("ollama/Ollama-darwin.zip", "scripts/ollama/Ollama-darwin.zip"):
        path = root / rel
        if path.is_file():
            return path
    return None


def bundled_ollama_app() -> Path | None:
    if _system_ollama_app().is_dir():
        return _system_ollama_app()
    installed = _flx_installed_ollama_app()
    if installed.is_dir():
        return installed
    sibling = _sibling_ollama_app()
    if sibling is not None:
        return sibling
    root = project_root()
    for rel in ("ollama/Ollama.app", "scripts/ollama/Ollama.app"):
        app = root / rel
        if app.is_dir():
            return app
    return None


def _extract_bundled_zip() -> Path | None:
    target = _flx_installed_ollama_app()
    if target.is_dir():
        return target
    zip_path = bundled_ollama_zip()
    if not zip_path:
        return None
    dest_dir = target.parent
    dest_dir.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(dest_dir)
    except (OSError, zipfile.BadZipFile):
        return None
    return target if target.is_dir() else None


def resolve_ollama_app() -> Path | None:
    app = bundled_ollama_app()
    if app is not None:
        return app
    return _extract_bundled_zip()


def ollama_cli_path() -> str | None:
    app = resolve_ollama_app()
    if app:
        cli = app / "Contents/Resources/ollama"
        if cli.is_file():
            return str(cli)
    system_cli = _system_ollama_app() / "Contents/Resources/ollama"
    if system_cli.is_file():
        return str(system_cli)
    return shutil.which("ollama")


def _api_reachable() -> bool:
    try:
        req = urllib.request.Request(f"{ollama_base_url()}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=2) as resp:
            json.loads(resp.read().decode("utf-8"))
        return True
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return False


def _model_installed(model: str) -> bool:
    try:
        req = urllib.request.Request(f"{ollama_base_url()}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        names = [str(m.get("name") or "") for m in data.get("models") or []]
        return any(model in n or n.startswith(model) for n in names)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return False


def _install_bundled_to_applications() -> bool:
    if sys.platform != "darwin":
        return False
    if _system_ollama_app().is_dir():
        return True
    app = resolve_ollama_app()
    if not app or app == _system_ollama_app():
        return _system_ollama_app().is_dir()
    try:
        shutil.copytree(app, _system_ollama_app(), symlinks=True)
        return True
    except OSError:
        return False


def _launch_ollama_mac() -> bool:
    if _api_reachable():
        return True
    app_path = resolve_ollama_app()
    if app_path is None:
        return False
    if app_path != _system_ollama_app() and not _system_ollama_app().is_dir():
        _install_bundled_to_applications()
        if _system_ollama_app().is_dir():
            app_path = _system_ollama_app()
    try:
        subprocess.run(
            ["open", "-a", str(app_path), "--args", "hidden"],
            check=False,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return True


def _launch_ollama_generic() -> bool:
    if _api_reachable():
        return True
    cli = ollama_cli_path()
    if not cli:
        return False
    env = os.environ.copy()
    host = ollama_base_url().replace("http://", "").replace("https://", "")
    env.setdefault("OLLAMA_HOST", host)
    try:
        subprocess.Popen(
            [cli, "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
            start_new_session=True,
        )
    except OSError:
        return False
    return True


def launch_ollama() -> bool:
    if is_mobile_platform():
        return _api_reachable()
    if sys.platform == "darwin":
        return _launch_ollama_mac()
    return _launch_ollama_generic()


def wait_for_ollama(timeout_sec: float = _START_TIMEOUT_SEC) -> bool:
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        if _api_reachable():
            return True
        time.sleep(0.5)
    return False


def pull_model_via_api(model: str | None = None) -> bool:
    """Download a model through Ollama's HTTP API (blocks until done)."""
    name = (model or ollama_model()).strip()
    if not name:
        return False
    if _model_installed(name):
        return True
    payload = json.dumps({"name": name, "stream": False}).encode("utf-8")
    req = urllib.request.Request(
        f"{ollama_base_url()}/api/pull",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=3600) as resp:
            resp.read()
    except (urllib.error.URLError, TimeoutError, OSError):
        return _model_installed(name)
    return _model_installed(name)


def pull_default_model(*, blocking: bool = False) -> None:
    model = ollama_model()
    if _model_installed(model):
        return
    if blocking:
        pull_model_via_api(model)
        return
    _pull_default_model_async()


def _pull_default_model_async() -> None:
    global _pull_thread
    with _pull_lock:
        if _pull_thread is not None and _pull_thread.is_alive():
            return

        def _run() -> None:
            pull_model_via_api(ollama_model())

        _pull_thread = threading.Thread(target=_run, name="flx-ollama-pull", daemon=True)
        _pull_thread.start()


def ensure_model_ready(*, blocking: bool = False, wait_sec: float = 0) -> bool:
    """Ensure configured model exists; optionally wait for background pull."""
    model = ollama_model()
    if _model_installed(model):
        return True
    if blocking:
        return pull_model_via_api(model)
    if not _api_reachable():
        return False
    _pull_default_model_async()
    if wait_sec > 0:
        deadline = time.monotonic() + wait_sec
        while time.monotonic() < deadline:
            if _model_installed(model):
                return True
            time.sleep(1.0)
    return False


def ensure_ollama_setup() -> dict[str, object]:
    if is_mobile_platform():
        return {
            "bundled": False,
            "running": _api_reachable(),
            "model": ollama_model(),
            "model_ready": _model_installed(ollama_model()) if _api_reachable() else False,
        }

    marker = app_support_dir() / _SETUP_MARKER
    has_zip = bundled_ollama_zip() is not None
    out: dict[str, object] = {
        "bundled": has_zip or resolve_ollama_app() is not None,
        "running": False,
        "model": ollama_model(),
        "model_ready": False,
    }

    if not _api_reachable():
        launch_ollama()
        out["running"] = wait_for_ollama()
    else:
        out["running"] = True

    if out["running"] and not _model_installed(ollama_model()):
        pull_default_model(blocking=False)

    if out["running"]:
        out["model_ready"] = _model_installed(ollama_model())
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("1\n", encoding="utf-8")

    return out


def ensure_ollama_async() -> None:
    if os.environ.get("FLX_SKIP_OLLAMA_SETUP") == "1":
        return
    if is_mobile_platform():
        return

    def _run() -> None:
        try:
            ensure_ollama_setup()
        except Exception:
            pass

    threading.Thread(target=_run, name="flx-ollama-setup", daemon=True).start()


def runtime_info() -> dict[str, object]:
    app = resolve_ollama_app()
    return {
        "bundled_app": bundled_ollama_zip() is not None or app is not None,
        "cli": ollama_cli_path() or "",
        "installed_app": _system_ollama_app().is_dir(),
        "api_up": _api_reachable(),
        "model_ready": _model_installed(ollama_model()),
    }
