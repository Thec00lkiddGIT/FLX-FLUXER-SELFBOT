# PyInstaller spec for FLX FLUXER SELFBOT
# macOS:   pyinstaller build/flx.spec --clean --noconfirm
# Windows: pyinstaller build\flx.spec --clean --noconfirm

import sys
from pathlib import Path

ROOT = Path(SPECPATH)
if not (ROOT / "gui.py").is_file():
    ROOT = ROOT.parent

block_cipher = None

datas = [
    (str(ROOT / "flx" / "gui" / "static"), "flx/gui/static"),
    (str(ROOT / "scripts" / "hub"), "scripts/hub"),
    (str(ROOT / ".env.example"), "."),
]

hiddenimports = [
    "flx",
    "flx.config",
    "flx.paths",
    "flx.runtime",
    "flx.gateway",
    "flx.rest",
    "flx.commands",
    "flx.danger_cmds",
    "flx.troll",
    "flx.abuse_settings",
    "flx.parse_util",
    "flx.textutil",
    "flx.script_hub",
    "flx.fluxerscript",
    "flx.gui.server",
    "flx.gui.bootstrap",
    "flx.gui.native_window",
    "flx.gui.commands_list",
    "flx.weather",
    "flx.dadjoke",
    "flx.randomword",
    "flx.youtube",
    "flx.glcheck",
    "flx.osint",
    "flx.qr",
    "webview",
    "websockets",
]

a = Analysis(
    [str(ROOT / "gui.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FLX-FLUXER-SELFBOT",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="FLX-FLUXER-SELFBOT",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="FLX FLUXER SELFBOT.app",
        icon=None,
        bundle_identifier="app.fluxer.flx.selfbot",
    )
