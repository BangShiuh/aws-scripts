# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

boto3_d,    boto3_b,    boto3_h    = collect_all('boto3')
botocore_d, botocore_b, botocore_h = collect_all('botocore')
certifi_d,  certifi_b,  certifi_h  = collect_all('certifi')

a = Analysis(
    ['gui/app.py'],
    pathex=['.'],
    binaries=boto3_b + botocore_b + certifi_b,
    datas=boto3_d + botocore_d + certifi_d,
    hiddenimports=boto3_h + botocore_h + certifi_h + [
        'tkinter', 'tkinter.ttk', 'tkinter.messagebox', 'tkinter.simpledialog',
    ],
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
    a.zipfiles,
    a.datas,
    [],
    name='EC2 Manager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,           # no terminal window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
