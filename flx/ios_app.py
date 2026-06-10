"""FLX on mobile (iOS / Android): local dashboard server + Toga WebView shell."""

from __future__ import annotations

import os
import sys
import threading

_IOS_NAV_BG = (12 / 255.0, 18 / 255.0, 32 / 255.0, 1.0)  # #0c1220 — matches dashboard

_IOS_SERVER: object | None = None
_IOS_STARTED = False


def start_dashboard_server(host: str = "127.0.0.1", port: int = 8766) -> str:
    """Start the FLX HTTP server in a background thread (idempotent)."""
    global _IOS_SERVER, _IOS_STARTED
    if _IOS_STARTED:
        return f"http://{host}:{port}/"

    os.environ.setdefault("FLX_NO_AUTOSTART", "1")
    if sys.platform == "android":
        os.environ.setdefault("FLX_ANDROID", "1")
    else:
        os.environ.setdefault("FLX_IOS", "1")

    from flx.gui.bootstrap import prepare_runtime
    from flx.gui.server import run_server

    prepare_runtime(autostart=False)
    server = run_server(host, port)

    def _serve() -> None:
        try:
            server.serve_forever()
        except Exception:
            pass

    threading.Thread(target=_serve, name="flx-ios-http", daemon=True).start()
    _IOS_SERVER = server
    _IOS_STARTED = True
    return f"http://{host}:{port}/"


def stop_flx() -> None:
    """Stop gateway and HTTP server when the app is killed (swipe away)."""
    global _IOS_SERVER, _IOS_STARTED
    try:
        from flx.runtime import get_runtime

        get_runtime().stop()
    except Exception:
        pass
    server = _IOS_SERVER
    if server is not None:
        try:
            server.shutdown()
        except Exception:
            pass
    _IOS_SERVER = None
    _IOS_STARTED = False


def run_toga_app() -> None:
    """Toga shell used by Briefcase iOS / Android builds."""
    import toga
    from toga.style import Pack

    class FLXApp(toga.App):
        def startup(self) -> None:
            if sys.platform == "ios":
                _enable_ios_background_keepalive()
            url = start_dashboard_server()
            self.main_window = toga.MainWindow(title="FLX")
            web = toga.WebView(url=url, style=Pack(flex=1))
            _configure_mobile_webview(web)
            self.main_window.content = web
            self.main_window.show()
            if sys.platform == "ios":
                _style_ios_chrome(self.main_window, web)

        def on_exit(self) -> bool:
            if sys.platform == "ios":
                _disable_ios_background_keepalive()
            stop_flx()
            return True

    return FLXApp("FLX", "com.flx.app")


def _configure_mobile_webview(web: object) -> None:
    """Enable WebView features needed by the FLX dashboard on mobile."""
    try:
        import toga.platform

        if toga.platform.current_platform == "android" and getattr(web, "_impl", None) is not None:
            web._impl.settings.setDomStorageEnabled(True)
            web._impl.settings.setJavaScriptEnabled(True)
    except Exception:
        pass


def _style_ios_chrome(main_window: object, web: object | None = None) -> None:
    """Match Toga's native title bar to the FLX dark-blue dashboard theme."""
    import sys

    if sys.platform != "ios":
        return
    try:
        from rubicon.objc import ObjCClass

        from toga_iOS.libs import UIColor

        impl = main_window._impl  # type: ignore[attr-defined]
        bg = UIColor.colorWithRed_green_blue_alpha_(*_IOS_NAV_BG)
        white = UIColor.whiteColor()

        impl.native.backgroundColor = bg

        nav = impl.container.controller.navigationBar
        nav.prefersLargeTitles = False
        nav.isTranslucent = False
        nav.barTintColor = bg
        nav.tintColor = white

        title_attrs = ObjCClass("NSDictionary").dictionaryWithObject_forKey_(
            white,
            "NSForegroundColorAttributeName",
        )
        NavAppearance = ObjCClass("UINavigationBarAppearance")
        appearance = NavAppearance.alloc().init()
        appearance.configureWithOpaqueBackground()
        appearance.backgroundColor = bg
        appearance.titleTextAttributes = title_attrs
        nav.setStandardAppearance_(appearance)
        nav.setScrollEdgeAppearance_(appearance)
        nav.setCompactAppearance_(appearance)

        if web is not None and getattr(web, "_impl", None) is not None:
            wk = web._impl.native
            wk.opaque = False
            wk.backgroundColor = bg
            wk.scrollView.backgroundColor = bg
    except Exception:
        pass


_SILENT_PLAYER: object | None = None


def _enable_ios_background_keepalive() -> None:
    """Keep gateway alive in background; swipe-away still kills the app."""
    import sys

    if sys.platform != "ios":
        return
    global _SILENT_PLAYER
    try:
        from rubicon.objc import ObjCClass
        from rubicon.objc.runtime import load_library

        load_library("AVFoundation")

        AVAudioSession = ObjCClass("AVAudioSession")
        session = AVAudioSession.sharedInstance()
        session.setCategory_error_("AVAudioSessionCategoryPlayback", None)
        session.setActive_error_(True, None)

        # iOS suspends the process unless audio is actively playing.
        NSData = ObjCClass("NSData")
        AVAudioPlayer = ObjCClass("AVAudioPlayer")
        wav = _minimal_silent_wav()
        data = NSData.dataWithBytes_length_(wav, len(wav))
        player = AVAudioPlayer.alloc().initWithData_error_(data, None)
        player.setNumberOfLoops_(-1)  # loop forever
        player.setVolume_(0.0)
        player.play()
        _SILENT_PLAYER = player
    except Exception:
        pass


def _disable_ios_background_keepalive() -> None:
    import sys

    if sys.platform != "ios":
        return
    global _SILENT_PLAYER
    try:
        from rubicon.objc import ObjCClass

        player = _SILENT_PLAYER
        if player is not None:
            player.stop()
        _SILENT_PLAYER = None
        AVAudioSession = ObjCClass("AVAudioSession")
        AVAudioSession.sharedInstance().setActive_error_(False, None)
    except Exception:
        pass


def _minimal_silent_wav() -> bytes:
    """Tiny mono 8 kHz silent WAV (~0.1 s) for background audio entitlement."""
    import struct

    sample_rate = 8000
    duration_s = 0.1
    num_samples = int(sample_rate * duration_s)
    data_size = num_samples  # 8-bit mono
    byte_rate = sample_rate
    block_align = 1
    bits_per_sample = 8
    riff_size = 36 + data_size
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        riff_size,
        b"WAVE",
        b"fmt ",
        16,
        1,
        1,
        sample_rate,
        byte_rate,
        block_align,
        bits_per_sample,
        b"data",
        data_size,
    )
    return header + (b"\x80" * num_samples)
