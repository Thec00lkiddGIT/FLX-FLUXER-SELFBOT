"""Disable TLS certificate verification (embedded iOS/Android Python has no trust store)."""

from __future__ import annotations

import os
import ssl
import sys

_installed = False


def _skip_verify() -> bool:
    if os.environ.get("FLX_IOS") == "1" or os.environ.get("FLX_ANDROID") == "1":
        return True
    return sys.platform in ("ios", "android")


def ssl_context() -> ssl.SSLContext:
    if _skip_verify():
        return ssl._create_unverified_context()
    return ssl.create_default_context()


def install() -> None:
    """Patch stdlib SSL + urllib before any HTTPS/WebSocket traffic."""
    global _installed
    if _installed or not _skip_verify():
        return
    _installed = True

    import urllib.request

    def _unverified_context(*_args, **_kwargs) -> ssl.SSLContext:
        return ssl._create_unverified_context()

    ssl.create_default_context = _unverified_context  # type: ignore[assignment]
    if hasattr(ssl, "_create_default_https_context"):
        ssl._create_default_https_context = _unverified_context  # type: ignore[assignment]

    ctx = ssl._create_unverified_context()
    _orig_urlopen = urllib.request.urlopen

    def _urlopen(*args, **kwargs):
        kwargs["context"] = ctx
        return _orig_urlopen(*args, **kwargs)

    urllib.request.urlopen = _urlopen  # type: ignore[assignment]


if _skip_verify():
    install()
