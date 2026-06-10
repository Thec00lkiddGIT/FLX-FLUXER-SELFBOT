"""Entry point for packaged FLX (iOS / Android Briefcase builds)."""

from __future__ import annotations

import os
import sys

if sys.platform == "ios":
    os.environ.setdefault("FLX_IOS", "1")
elif sys.platform == "android":
    os.environ.setdefault("FLX_ANDROID", "1")

if sys.platform in ("ios", "android"):
    from flx.ssl_certs import install as _install_ssl

    _install_ssl()


def main() -> None:
    if sys.platform in ("ios", "android"):
        from flx.ios_app import run_toga_app

        run_toga_app().main_loop()
        return
    import gui

    raise SystemExit(gui.main())


if __name__ == "__main__":
    main()
