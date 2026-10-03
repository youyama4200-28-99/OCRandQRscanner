# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import copy_metadata


project_root = Path(SPEC).resolve().parent.parent
metadata = []
for distribution in (
    "numpy",
    "opencv-contrib-python",
    "openvino",
    "paddleocr",
    "paddlepaddle",
    "paddlex",
    "PySide6",
    "imagesize",
    "pyclipper",
    "pypdfium2",
    "python-bidi",
    "shapely",
):
    metadata += copy_metadata(distribution)

a = Analysis(
    [str(project_root / "packaging" / "entrypoint.py")],
    pathex=[str(project_root / "src")],
    binaries=[],
    datas=metadata,
    hiddenimports=["paddle", "paddleocr", "paddlex", "openvino"],
    hookspath=[str(project_root / "packaging" / "hooks")],
    hooksconfig={},
    runtime_hooks=[str(project_root / "packaging" / "runtime_hook.py")],
    excludes=["tkinter", "matplotlib", "IPython", "notebook"],
    noarchive=False,
    optimize=1,
)

# Qt6Core expects the Windows system ICU shim. A different unversioned ICU DLL
# can be discovered from the build host's PATH (for example Poppler's ICU 78),
# which then shadows System32 and makes QtCore fail with WinError 127.
excluded_host_icu = {"icuuc.dll", "icudt78.dll"}
a.binaries = [entry for entry in a.binaries if Path(entry[0]).name.lower() not in excluded_host_icu]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SmartScan",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="SmartScan",
)
