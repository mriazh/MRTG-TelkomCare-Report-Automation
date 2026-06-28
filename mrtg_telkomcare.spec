# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT
from PyInstaller.utils.hooks import collect_submodules, collect_data_files, copy_metadata, collect_dynamic_libs

block_cipher = None

hidden_imports = [
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'openpyxl',
    'PIL'
]
hidden_imports += collect_submodules('selenium')
hidden_imports += collect_submodules('webdriver_manager')
hidden_imports += collect_submodules('paddleocr')
hidden_imports += collect_submodules('paddlex')

# Add required OCR runtime submodules
for mod in ['imagesize', 'cv2', 'pyclipper', 'pypdfium2', 'bidi', 'shapely']:
    hidden_imports += collect_submodules(mod)

datas = []
datas += collect_data_files('paddleocr')
datas += collect_data_files('paddlex')
datas.append(('.venv312/Lib/site-packages/paddlex/configs', 'paddlex/configs'))

# Add metadata for Paddlex and its dependencies so runtime version checks pass
for pkg in ['paddlex', 'paddleocr', 'imagesize', 'opencv-contrib-python', 'pyclipper', 'pypdfium2', 'python-bidi', 'shapely']:
    datas += copy_metadata(pkg)

binaries = []
binaries += collect_dynamic_libs('paddle')

a = Analysis(
    ['gui_launcher.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Do not use Tree here because it puts them in _internal.
# We will copy them in the build script instead.

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MRTG-TelkomCare',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/app_icon.ico' if os.path.exists('assets/app_icon.ico') else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MRTG-TelkomCare',
)
