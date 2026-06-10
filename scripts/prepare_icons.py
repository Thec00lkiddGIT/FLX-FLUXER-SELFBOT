#!/usr/bin/env python3
"""Download Fluxer favicon, flip horizontally, write assets/icon.*."""

from __future__ import annotations

import io
import ssl
import subprocess
import sys
import urllib.request
from pathlib import Path

FAVICON_URL = "https://fluxerstatic.com/web/apple-touch-icon.png"

# Briefcase iOS / splash sizes (see briefcase iOS template icon.* paths).
IOS_ICON_SIZES = (20, 29, 40, 58, 60, 76, 80, 87, 120, 152, 167, 180, 640, 1024, 1280, 1920)

# Briefcase Android launcher / splash (see briefcase Android template icon.* paths).
ANDROID_ROUND = (48, 72, 96, 144, 192)
ANDROID_SQUARE = (48, 72, 96, 144, 192, 320, 480, 640, 960, 1280)
ANDROID_ADAPTIVE = (108, 162, 216, 324, 432)


def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def _load_flipped_image(assets: Path):
    from PIL import Image

    local = assets / "icon.png"
    try:
        req = urllib.request.Request(FAVICON_URL, headers={"User-Agent": "FLX/prepare_icons"})
        with urllib.request.urlopen(req, timeout=30, context=_ssl_context()) as resp:
            raw = resp.read()
        img = Image.open(io.BytesIO(raw)).convert("RGBA")
    except Exception as exc:
        if local.is_file():
            print(f"Could not download favicon ({exc}); using {local}", file=sys.stderr)
            img = Image.open(local).convert("RGBA")
        else:
            print(f"Could not download favicon and no local icon.png: {exc}", file=sys.stderr)
            raise
    return img.transpose(Image.FLIP_LEFT_RIGHT)


def main() -> int:
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        print("Install Pillow: pip install Pillow", file=sys.stderr)
        return 1

    root = Path(__file__).resolve().parents[1]
    assets = root / "assets"
    assets.mkdir(exist_ok=True)

    flipped = _load_flipped_image(assets)
    flipped.save(assets / "icon.png")

    for size in IOS_ICON_SIZES:
        flipped.resize((size, size), Image.Resampling.LANCZOS).save(
            assets / f"icon-{size}.png"
        )

    for size in ANDROID_ROUND:
        flipped.resize((size, size), Image.Resampling.LANCZOS).save(
            assets / f"icon-round-{size}.png"
        )
    for size in ANDROID_SQUARE:
        flipped.resize((size, size), Image.Resampling.LANCZOS).save(
            assets / f"icon-square-{size}.png"
        )
    for size in ANDROID_ADAPTIVE:
        flipped.resize((size, size), Image.Resampling.LANCZOS).save(
            assets / f"icon-adaptive-{size}.png"
        )

    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    icons = [flipped.resize(s, Image.Resampling.LANCZOS) for s in sizes]
    icons[0].save(
        assets / "icon.ico",
        format="ICO",
        sizes=[(i.width, i.height) for i in icons],
        append_images=icons[1:],
    )

    static_icon = root / "flx" / "gui" / "static" / "icon.png"
    flipped.save(static_icon)

    if sys.platform == "darwin":
        iconset = assets / "icon.iconset"
        iconset.mkdir(exist_ok=True)
        mapping = {
            "icon_16x16.png": 16,
            "icon_16x16@2x.png": 32,
            "icon_32x32.png": 32,
            "icon_32x32@2x.png": 64,
            "icon_128x128.png": 128,
            "icon_128x128@2x.png": 256,
            "icon_256x256.png": 256,
            "icon_256x256@2x.png": 512,
            "icon_512x512.png": 512,
            "icon_512x512@2x.png": 1024,
        }
        for name, size in mapping.items():
            flipped.resize((size, size), Image.Resampling.LANCZOS).save(iconset / name)
        icns = assets / "icon.icns"
        subprocess.run(
            ["iconutil", "-c", "icns", str(iconset), "-o", str(icns)],
            check=True,
        )
        import shutil

        shutil.rmtree(iconset)

    print(f"Icons written to {assets}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
