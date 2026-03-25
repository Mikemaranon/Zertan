import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


APP_NAME = "Zertan Server"
IS_WINDOWS = sys.platform.startswith("win")
IS_MACOS = sys.platform == "darwin"
SERVER_VERSION = os.environ.get("ZERTAN_SERVER_VERSION") or "0.0.0"
BUNDLE_BUILD_VERSION = SERVER_VERSION.split("-", 1)[0]
WINDOWS_ICON = os.environ.get("ZERTAN_SERVER_ICON_ICO") or None
MACOS_ICON = os.environ.get("ZERTAN_SERVER_ICON_ICNS") or None
MACOS_CODESIGN_IDENTITY = os.environ.get("ZERTAN_MACOS_CODESIGN_IDENTITY") or None
MACOS_ENTITLEMENTS_PATH = os.environ.get("ZERTAN_MACOS_ENTITLEMENTS_PATH") or None
project_root = Path(SPECPATH).resolve().parents[2]
datas = [
    (str(project_root / "app" / "web_app"), "app/web_app"),
]
hiddenimports = collect_submodules("api_m.domains") + collect_submodules("webview")


a = Analysis(
    [str(project_root / "deploy" / "src" / "server" / "server_launcher.py")],
    pathex=[str(project_root), str(project_root / "app" / "web_server")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

if IS_WINDOWS:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name=APP_NAME,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=False,
        icon=WINDOWS_ICON,
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name=APP_NAME,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=not IS_MACOS,
        codesign_identity=MACOS_CODESIGN_IDENTITY,
        entitlements_file=MACOS_ENTITLEMENTS_PATH,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=False,
        upx_exclude=[],
        name=APP_NAME,
    )

    if IS_MACOS:
        app = BUNDLE(
            coll,
            name=f"{APP_NAME}.app",
            bundle_identifier="com.zertan.server",
            icon=MACOS_ICON,
            info_plist={
                "CFBundleDisplayName": APP_NAME,
                "CFBundleName": APP_NAME,
                "CFBundleShortVersionString": SERVER_VERSION,
                "CFBundleVersion": BUNDLE_BUILD_VERSION,
                "LSBackgroundOnly": False,
                "NSHighResolutionCapable": True,
            },
        )
