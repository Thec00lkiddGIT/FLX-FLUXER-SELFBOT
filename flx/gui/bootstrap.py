"""Load saved GUI settings on launch."""

from __future__ import annotations

import os

from flx.paths import ensure_env_file, ensure_script_hub
from flx.runtime import get_runtime
from flx.state import load_gui_settings


def prepare_runtime(*, autostart: bool | None = None) -> None:
    ensure_env_file()
    ensure_script_hub()
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
