"""Small, non-activating Windows volume flyout. Timers animate UI only."""
import ctypes as C
from ctypes import wintypes as W
from functools import lru_cache
import logging
import time
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from mr3_paths import RESOURCE_DIR
from mr3_dpi import dp

WIDTH, HEIGHT = 356, 88  # Includes transparent shadow margin.
ACCENT = '#dfbf7c'


@lru_cache(maxsize=12)
def _font(size, scale, weight='Medium'):
    return ImageFont.truetype(str(RESOURCE_DIR / 'assets/fonts' / f'Pretendard-{weight}.ttf'), round(size*scale))


@lru_cache(maxsize=4)
def _background(scale):
    image = Image.new('RGBA', (round(WIDTH*scale), round(HEIGHT*scale)))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(tuple(round(n*scale) for n in (12, 15, 344, 81)), radius=13*scale, fill=(0,0,0,85))
    image = image.filter(ImageFilter.GaussianBlur(5*scale))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(tuple(round(n*scale) for n in (10, 8, 346, 72)), radius=12*scale,
                           fill=(35,35,38,250), outline=(91,91,95,190), width=max(1,round(.75*scale)))
    return image


def render_overlay(value, level=None, scale=1.0):
    """Pure RGBA renderer, also used for previews; never touches the desktop."""
    value = max(0, min(30, int(value)))
    level = value if level is None else max(0, min(30, float(level)))
    size = (round(WIDTH*scale), round(HEIGHT*scale))
    s = scale*3
    image = _background(s).copy()
    draw = ImageDraw.Draw(image)
    def box(values): return tuple(round(x*s) for x in values)
    def line(values, fill='#f4f4f5', width=1.6):
        draw.line(box(values), fill=fill, width=max(1,round(width*s)), joint='curve')
    # Speaker glyph has no dependency on system icon fonts.
    line((29,35,34,35,41,29,41,51,34,45,29,45,29,35))
    if value == 0:
        line((46,36,53,44)); line((53,36,46,44))
    else:
        draw.arc(box((38,34,50,46)), -65, 65, fill='#f4f4f5', width=round(1.6*s))
        if value >= 15:
            draw.arc(box((36,29,56,51)), -60, 60, fill='#f4f4f5', width=round(1.6*s))
    draw.text(box((72,26)), 'MR3', font=_font(11,s), fill='#bbbbc1', anchor='lm')
    x0, x1, y = 72, 268, 48
    draw.rounded_rectangle(box((x0,y-2,x1,y+2)), radius=2*s, fill='#626267')
    end = x0+(x1-x0)*level/30
    if level > 0:
        draw.rounded_rectangle(box((x0,y-2,end,y+2)), radius=2*s, fill=ACCENT)
    draw.ellipse(box((end-5,y-5,end+5,y+5)), fill=ACCENT)
    draw.text(box((306,35)), str(value), font=_font(21,s), fill='#fafafa', anchor='mm')
    draw.text(box((306,54)), '/ 30', font=_font(10,s), fill='#a4a4ad', anchor='mm')
    return image.resize(size, Image.Resampling.LANCZOS)


def overlay_position(work, size, scale):
    left, top, right, bottom = work
    width, height = size
    return max(left, left+(right-left-width)//2), max(top, bottom-height-round(18*scale))


class NativeSurface:
    """Per-pixel alpha window; never calls a focus/activation API."""
    def __init__(self):
        self.u = C.WinDLL('user32', use_last_error=True)
        self.g = C.WinDLL('gdi32', use_last_error=True)
        k = C.WinDLL('kernel32', use_last_error=True)
        self.proc_type = C.WINFUNCTYPE(C.c_ssize_t, W.HWND, W.UINT, W.WPARAM, W.LPARAM)
        class WindowClass(C.Structure):
            _fields_ = [('style',W.UINT),('proc',self.proc_type),('cls_extra',C.c_int),('win_extra',C.c_int),
                        ('instance',W.HINSTANCE),('icon',W.HICON),('cursor',W.HANDLE),('brush',W.HBRUSH),
                        ('menu',W.LPCWSTR),('name',W.LPCWSTR)]
        self.u.DefWindowProcW.argtypes = [W.HWND,W.UINT,W.WPARAM,W.LPARAM]
        self.u.DefWindowProcW.restype = C.c_ssize_t
        self.u.RegisterClassW.argtypes = [C.POINTER(WindowClass)]
        self.u.RegisterClassW.restype = W.ATOM
        self.u.CreateWindowExW.argtypes = [W.DWORD,W.LPCWSTR,W.LPCWSTR,W.DWORD,C.c_int,C.c_int,C.c_int,C.c_int,W.HWND,W.HMENU,W.HINSTANCE,W.LPVOID]
        self.u.CreateWindowExW.restype = W.HWND
        self.u.DestroyWindow.argtypes = [W.HWND]
        self.u.UnregisterClassW.argtypes = [W.LPCWSTR,W.HINSTANCE]
        self.u.ShowWindow.argtypes = [W.HWND,C.c_int]
        self.u.SetWindowPos.argtypes = [W.HWND,W.HWND,C.c_int,C.c_int,C.c_int,C.c_int,W.UINT]
        self.u.GetForegroundWindow.restype = W.HWND
        self.u.MonitorFromWindow.argtypes = [W.HWND,W.DWORD]
        self.u.MonitorFromWindow.restype = W.HANDLE
        k.GetModuleHandleW.argtypes = [W.LPCWSTR]
        k.GetModuleHandleW.restype = W.HMODULE
        self.instance = k.GetModuleHandleW(None)
        self.class_name = f'MR3VolumeFlyout_{id(self)}'
        def window_proc(hwnd, message, wp, lp):
            if message == 0x21: return 3  # WM_MOUSEACTIVATE -> MA_NOACTIVATE
            if message == 0x84: return -1  # WM_NCHITTEST -> HTTRANSPARENT
            return self.u.DefWindowProcW(hwnd,message,wp,lp)
        self.callback = self.proc_type(window_proc)
        wc = WindowClass(proc=self.callback,instance=self.instance,name=self.class_name)
        if not self.u.RegisterClassW(C.byref(wc)): raise C.WinError(C.get_last_error())
        # WS_EX_LAYERED | TOOLWINDOW | NOACTIVATE | TRANSPARENT; WS_POPUP.
        self.hwnd = self.u.CreateWindowExW(0x080800A0,self.class_name,'MR3 Volume',0x80000000,
                                           0,0,0,0,None,None,self.instance,None)
        if not self.hwnd:
            self.u.UnregisterClassW(self.class_name,self.instance)
            raise C.WinError(C.get_last_error())
        self.visible = False

    def work_area(self):
        class MonitorInfo(C.Structure):
            _fields_ = [('size',W.DWORD),('monitor',W.RECT),('work',W.RECT),('flags',W.DWORD)]
        monitor = self.u.MonitorFromWindow(self.u.GetForegroundWindow(),2)
        info = MonitorInfo(size=C.sizeof(MonitorInfo))
        self.u.GetMonitorInfoW.argtypes = [W.HANDLE,C.POINTER(MonitorInfo)]
        if not self.u.GetMonitorInfoW(monitor,C.byref(info)): raise C.WinError(C.get_last_error())
        r = info.work
        return r.left,r.top,r.right,r.bottom

    def paint(self, image, position, opacity):
        class Header(C.Structure):
            _fields_ = [('size',W.DWORD),('width',W.LONG),('height',W.LONG),('planes',W.WORD),
                        ('bits',W.WORD),('compression',W.DWORD),('image_size',W.DWORD),
                        ('xppm',W.LONG),('yppm',W.LONG),('used',W.DWORD),('important',W.DWORD)]
        class BitmapInfo(C.Structure):
            _fields_ = [('header',Header),('colors',W.DWORD*3)]
        class Blend(C.Structure):
            _fields_ = [('op',C.c_ubyte),('flags',C.c_ubyte),('alpha',C.c_ubyte),('format',C.c_ubyte)]
        self.g.CreateCompatibleDC.argtypes = [W.HDC]
        self.g.CreateCompatibleDC.restype = W.HDC
        self.g.CreateDIBSection.argtypes = [W.HDC,C.POINTER(BitmapInfo),W.UINT,C.POINTER(C.c_void_p),W.HANDLE,W.DWORD]
        self.g.CreateDIBSection.restype = W.HBITMAP
        self.g.SelectObject.argtypes = [W.HDC,W.HANDLE]
        self.g.SelectObject.restype = W.HANDLE
        self.g.DeleteObject.argtypes = [W.HANDLE]
        self.g.DeleteDC.argtypes = [W.HDC]
        self.u.UpdateLayeredWindow.argtypes = [W.HWND,W.HDC,C.POINTER(W.POINT),C.POINTER(W.SIZE),W.HDC,C.POINTER(W.POINT),W.DWORD,C.POINTER(Blend),W.DWORD]
        width,height = image.size
        info = BitmapInfo(header=Header(size=C.sizeof(Header),width=width,height=-height,planes=1,bits=32))
        bits = C.c_void_p()
        dc = self.g.CreateCompatibleDC(None)
        if not dc: raise C.WinError(C.get_last_error())
        bitmap, previous = None,None
        try:
            bitmap = self.g.CreateDIBSection(dc,C.byref(info),0,C.byref(bits),None,0)
            if not bitmap: raise C.WinError(C.get_last_error())
            previous = self.g.SelectObject(dc,bitmap)
            pixels = image.convert('RGBa').tobytes('raw','BGRa')  # Premultiplied alpha.
            C.memmove(bits,pixels,len(pixels))
            pos, size, origin = W.POINT(*position),W.SIZE(width,height),W.POINT(0,0)
            blend = Blend(0,0,round(max(0,min(1,opacity))*255),1)
            if not self.u.UpdateLayeredWindow(self.hwnd,None,C.byref(pos),C.byref(size),dc,C.byref(origin),0,C.byref(blend),2):
                raise C.WinError(C.get_last_error())
            if not self.visible:
                if not self.u.SetWindowPos(self.hwnd,W.HWND(-1),0,0,0,0,0x53):  # SHOWWINDOW | NOACTIVATE | NOMOVE | NOSIZE
                    raise C.WinError(C.get_last_error())
                self.visible = True
        finally:
            if previous: self.g.SelectObject(dc,previous)
            if bitmap: self.g.DeleteObject(bitmap)
            self.g.DeleteDC(dc)

    def hide(self):
        self.u.ShowWindow(self.hwnd,0)
        self.visible = False

    def close(self):
        if self.hwnd:
            self.u.DestroyWindow(self.hwnd)
            self.hwnd = None
            self.u.UnregisterClassW(self.class_name,self.instance)


class VolumeOverlay:
    def __init__(self, root, surface_factory=NativeSurface, clock=time.perf_counter):
        self.root, self.factory, self.clock = root,surface_factory,clock
        self.surface = None
        self.visible = self.closed = False
        self.value = 0
        self.level = self.opacity = 0.0
        self.frame_timer = self.hide_timer = None
        self.scale = dp(100)/100
        self.position = (0,0)
        root.bind('<Destroy>',self._destroyed,add='+')

    def _destroyed(self,event):
        if event.widget is self.root: self.close()

    def _cancel(self, name):
        timer = getattr(self,name)
        if timer is not None:
            self.root.after_cancel(timer)
            setattr(self,name,None)

    def show(self,value):
        if self.closed: return
        self._cancel('hide_timer')
        self._cancel('frame_timer')
        self.value = max(0,min(30,int(value)))
        try:
            if self.surface is None: self.surface = self.factory()
            self.position = overlay_position(self.surface.work_area(),
                (round(WIDTH*self.scale),round(HEIGHT*self.scale)),self.scale)
            if not self.visible:
                self.level,self.opacity = float(self.value),0.0
            self.visible = True
            self._transition(1.0,self.value,.12)
            if self.visible:
                self.hide_timer = self.root.after(2000,self._fade_out)
        except OSError:
            logging.exception('Volume overlay could not be shown')
            self.hide()

    def _transition(self, alpha, level, duration):
        self._cancel('frame_timer')
        start = self.clock()
        from_alpha,from_level = self.opacity,self.level
        def step():
            self.frame_timer = None
            if self.closed: return
            progress = min(1,max(0,(self.clock()-start)/duration))
            ease = 1-(1-progress)**3
            self.opacity = from_alpha+(alpha-from_alpha)*ease
            self.level = from_level+(level-from_level)*ease
            try:
                self.surface.paint(render_overlay(self.value,self.level,self.scale),self.position,self.opacity)
            except OSError:
                logging.exception('Volume overlay rendering failed')
                self.hide()
                return
            if progress < 1:
                self.frame_timer = self.root.after(16,step)
            elif alpha == 0:
                self.hide()
        step()

    def _fade_out(self):
        self.hide_timer = None
        self._transition(0.0,self.value,.16)

    def hide(self):
        self._cancel('frame_timer')
        self._cancel('hide_timer')
        self.visible = False
        self.opacity = 0.0
        if self.surface: self.surface.hide()

    def close(self):
        if self.closed: return
        self.hide()
        self.closed = True
        if self.surface: self.surface.close()
