# PyInstaller spec for FLX
# macOS:      pyinstaller build/flx.spec --clean --noconfirm
# Windows:    pyinstaller build\flx.spec --clean --noconfirm
# Linux/Cros: pyinstaller build/flx.spec --clean --noconfirm

import sys
from pathlib import Path

ROOT = Path(SPECPATH)
if not (ROOT / "gui.py").is_file():
    ROOT = ROOT.parent

ICON_ICO = ROOT / "assets" / "icon.ico"
ICON_ICNS = ROOT / "assets" / "icon.icns"

block_cipher = None

datas = [
    (str(ROOT / "flx" / "gui" / "static"), "flx/gui/static"),
    (str(ROOT / "scripts" / "hub"), "scripts/hub"),
    (str(ROOT / "scripts" / "community"), "scripts/community"),
    (str(ROOT / ".env.example"), "."),
    (str(ROOT / "docs" / "FLXSCRIPT_GUIDE.md"), "docs"),
]
# Zip only — nesting Ollama.app in PyInstaller breaks codesign.
_ollama_zip = ROOT / "scripts" / "ollama" / "Ollama-darwin.zip"
if _ollama_zip.is_file():
    datas.append((str(_ollama_zip), "ollama"))

hiddenimports = [
    "flx",
    "flx.version",
    "flx.config",
    "flx.paths",
    "flx.runtime",
    "flx.gateway",
    "flx.rest",
    "flx.rate_limit",
    "flx.commands",
    "flx.danger_cmds",
    "flx.troll",
    "flx.abuse_settings",
    "flx.parse_util",
    "flx.targets",
    "flx.textutil",
    "flx.script_hub",
    "flx.community_hub",
    "flx.assistant",
    "flx.ollama_runtime",
    "flx.command_catalog",
    "flx.utility_cmds",
    "flx.fluxerscript",
    "flx.snowflake",
    "flx.user_info",
    "flx.webhook_cmd",
    "flx.httpcat",
    "flx.pokemon",
    "flx.poof",
    "flx.microlink",
    "flx.message_attachments",
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

_exe_icon = str(ICON_ICO) if sys.platform == "win32" and ICON_ICO.is_file() else None

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FLX",
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
    icon=_exe_icon,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="FLX",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="FLX.app",
        icon=str(ICON_ICNS) if ICON_ICNS.is_file() else None,
        bundle_identifier="com.flx.app",
    )
