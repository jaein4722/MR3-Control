"""Load bundled Pretendard privately for this process, without installing fonts."""
import atexit
import ctypes
from pathlib import Path
import sys

FONT='Pretendard'
_loaded=[]


def load_fonts():
    if sys.platform!='win32' or _loaded: return
    gdi=ctypes.windll.gdi32
    gdi.AddFontResourceExW.argtypes=[ctypes.c_wchar_p,ctypes.c_uint,ctypes.c_void_p]
    gdi.RemoveFontResourceExW.argtypes=[ctypes.c_wchar_p,ctypes.c_uint,ctypes.c_void_p]
    for path in sorted((Path(__file__).resolve().parent/'assets'/'fonts').glob('*.ttf')):
        if not gdi.AddFontResourceExW(str(path),0x10,None):
            raise OSError('Pretendard 폰트를 불러오지 못했습니다: '+str(path))
        _loaded.append(str(path))
    if not _loaded: raise FileNotFoundError('assets/fonts의 Pretendard 폰트가 없습니다.')
    def release():
        for path in _loaded: gdi.RemoveFontResourceExW(path,0x10,None)
    atexit.register(release)


load_fonts()
