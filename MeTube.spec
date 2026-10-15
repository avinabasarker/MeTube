# -*- mode: python ; coding: utf-8 -*-
# Every path is resolved from SPECPATH (this file's folder), so the spec builds
# from any clone and on any machine.  scripts/build_ship.py is the authoritative
# builder: it passes these same options on the PyInstaller command line and then
# assembles dist\MeTubeShip.
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

PROJECT = Path(SPECPATH)

datas = [(str(PROJECT / 'assets' / 'icon.ico'), 'assets')]
datas += collect_data_files('customtkinter')


a = Analysis(
    [str(PROJECT / 'app.py')],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='MeTube',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version=str(PROJECT / 'version_info.txt'),
    icon=[str(PROJECT / 'assets' / 'icon.ico')],
)
