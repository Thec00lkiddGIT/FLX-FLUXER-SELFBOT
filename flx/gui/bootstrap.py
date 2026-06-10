"""Load saved GUI settings on launch."""

from __future__ import annotations

import os

from flx.community_hub import ensure_community_hub
from flx.ollama_runtime import ensure_ollama_async
from flx.paths import ensure_env_file, ensure_script_hub
from flx.runtime import get_runtime
from flx.ssl_certs import install as install_ssl_certs
from flx.state import load_gui_settings


def prepare_runtime(*, autostart: bool | None = None) -> None:
    install_ssl_certs()
    ensure_env_file()
    ensure_script_hub()
    ensure_community_hub()
    ensure_ollama_async()
    settings = load_gui_settings()
    rt = get_runtime()
    rt.update_settings(
        delete_commands=bool(settings.get("delete_commands", True)),
        verbose=bool(settings.get("verbose", True)),
    )

    should_start = settings.get("autostart") if autostart is None else autostart
    if os.environ.get("FLX_NO_AUTOSTART") == "1":
        should_start = False

    if should_start:
        rt.start()
