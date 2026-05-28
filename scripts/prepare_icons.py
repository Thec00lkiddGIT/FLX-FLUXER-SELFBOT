#!/usr/bin/env python3
"""Download Fluxer favicon, flip horizontally, write assets/icon.*."""

from __future__ import annotations

import io
import subprocess
import sys
import urllib.request
from pathlib import Path

FAVICON_URL = "https://fluxerstatic.com/web/apple-touch-icon.png"


def main() -> int:
    try:
        from PIL import Image
    except ImportError:
        print("Install Pillow: pip install Pillow", file=sys.stderr)
        return 1

    root = Path(__file__).resolve().parents[1]
    assets = root / "assets"
    assets.mkdir(exist_ok=True)

    raw = urllib.request.urlopen(FAVICON_URL, timeout=30).read()
    img = Image.open(io.BytesIO(raw)).convert("RGBA")
    flipped = img.transpose(Image.FLIP_LEFT_RIGHT)
    flipped.save(assets / "icon.png")

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
