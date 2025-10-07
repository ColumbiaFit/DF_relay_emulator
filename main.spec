# -*- mode: python ; coding: utf-8 -*-
import sys
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# Collect additional files
datas = [
    ('unlock_click.mp3', '.'),  # Include sound file for unlocking
    ('lock_click.mp3', '.'),  # Include sound file for locking
    ('emulator_settings.conf', '.'),  # Include settings file if it exists
]

# Collect data files for dependencies if needed
datas += collect_data_files('serial')  # Include serial library data if needed
datas += collect_data_files('pygame')  # Include pygame resources if needed

a = Analysis(
    ['relay_emulator.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'serial.tools.list_ports',  # Ensure serial.tools is included
        'pygame.mixer',  # Ensure pygame.mixer is included
        'tkinter',  # Include tkinter for GUI
    ],
    hookspath=[],
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
    name='RelayEmulator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Set to False to avoid a console window
    icon=None,  # You can specify an icon file here if needed
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='RelayEmulator',
)
