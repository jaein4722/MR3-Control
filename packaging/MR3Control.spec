# Build from the isolated environment, never include development data or APKs.
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules
import winrt

project = Path(SPECPATH).parent
hidden = collect_submodules('winrt') + [
    'bleak.backends.winrt.client', 'bleak.backends.winrt.scanner', 'pystray._win32',
]
winrt_root = Path(next(iter(winrt.__path__)))
binaries = [(str(path), 'winrt') for path in winrt_root.glob('*.pyd')]
datas = [(str(project / 'assets'), 'assets'),
         (str(project / 'build/third-party'), 'licenses')]
a = Analysis([str(project / 'src/mr3_launcher.py')], pathex=[str(project / 'src')],
             binaries=binaries, datas=datas, hiddenimports=hidden,
             excludes=['pytest', 'unittest', 'IPython', 'matplotlib', 'numpy'])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='MR3 Control',
          debug=False, strip=False, upx=False, console=False,
          icon=str(project / 'assets/mr3.ico'),
          version=str(project / 'build/version-info.txt'),
          manifest=str(project / 'build/app.manifest'))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='MR3 Control')
