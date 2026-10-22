# Reproducible Windows single-file build. Run through build.ps1.
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

root = Path(SPECPATH)
pygame_data, pygame_binaries, pygame_imports = collect_all('pygame')
a = Analysis(
    [str(root / 'main.py')],
    pathex=[str(root)],
    binaries=pygame_binaries,
    datas=pygame_data + [
        (str(root / 'stargate_sg1_adress_glyphs.ttf'), '.'),
        (str(root / 'media'), 'media'),
    ],
    hiddenimports=pygame_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name='StargateDialer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)
