# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[os.path.abspath('.')],
    binaries=[],
    datas=[],
    hiddenimports=[
        'git2base.database.connection',
        'git2base.database.model',
        'git2base.database.operation',
        'git2base.git.utils',
        'git2base.git.wrapper',
        'git2base.analyzers.base_analyzer',
        'git2base.analyzers.file_char_count_analyzer',
        'git2base.analyzers.file_line_count_analyzer',
        'git2base.analyzers.regex_match_count_analyzer',
        'git2base.analyzers.xml_elm_count_analyzer'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='git2base',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
