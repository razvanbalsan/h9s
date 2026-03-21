# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for H9S — builds a single self-contained binary.
#
# Usage:
#   pip install pyinstaller
#   pyinstaller h9s.spec
#
# Output: dist/h9s  (macOS / Linux)  or  dist/h9s.exe  (Windows)

from PyInstaller.utils.hooks import collect_all, collect_data_files

# Collect all Textual and Rich assets (CSS, themes, etc.)
textual_datas, textual_binaries, textual_hiddenimports = collect_all("textual")
rich_datas, rich_binaries, rich_hiddenimports = collect_all("rich")
yaml_datas, yaml_binaries, yaml_hiddenimports = collect_all("yaml")

a = Analysis(
    ["helm_dashboard/__main__.py"],
    pathex=["."],
    binaries=textual_binaries + rich_binaries + yaml_binaries,
    datas=textual_datas + rich_datas + yaml_datas,
    hiddenimports=textual_hiddenimports + rich_hiddenimports + yaml_hiddenimports,
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
    name="h9s",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
