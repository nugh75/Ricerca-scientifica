import sys

from PyInstaller.utils.hooks import collect_submodules

hiddenimports = collect_submodules("keyring.backends")
# uvicorn loads "litreview.main:app" via a string at runtime, so PyInstaller
# cannot see it statically; bundle the app package explicitly.
hiddenimports += collect_submodules("litreview")

if sys.platform.startswith("win"):
    name = "litreview-backend-windows"
    console = False
elif sys.platform == "darwin":
    name = "litreview-backend-macos"
    console = False
else:
    name = "litreview-backend-linux"
    console = True

a = Analysis(
    ["../packaging/run_litreview.py"],
    pathex=["../src"],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=console,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
