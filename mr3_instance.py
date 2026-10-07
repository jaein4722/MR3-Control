"""Single instance with event-based activation (no socket or polling loop)."""
import ctypes
import threading


class SingleInstance:
    def __init__(self):
        k=self.k=ctypes.windll.kernel32
        k.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_wchar_p]
        k.CreateMutexW.restype=ctypes.c_void_p
        k.CreateEventW.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_int,ctypes.c_wchar_p]
        k.CreateEventW.restype=ctypes.c_void_p
        k.SetEvent.argtypes=[ctypes.c_void_p]
        k.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_ulong]
        k.CloseHandle.argtypes=[ctypes.c_void_p]
        self.mutex=k.CreateMutexW(None,False,'Local\\MR3ControlDesktop')
        self.existing=k.GetLastError()==183
        self.event=k.CreateEventW(None,False,False,'Local\\MR3ControlShow')
        self.stopped=False
        self.thread=None
        if not self.mutex or not self.event:
            raise ctypes.WinError()
        if self.existing:
            k.SetEvent(self.event)

    def listen(self,show):
        def wait():
            while self.k.WaitForSingleObject(self.event,0xFFFFFFFF)==0:
                if self.stopped: break
                show()
        self.thread=threading.Thread(target=wait,daemon=True)
        self.thread.start()

    def close(self):
        self.stopped=True
        if self.thread:
            self.k.SetEvent(self.event)
            self.thread.join(timeout=2)
        self.k.CloseHandle(self.event)
        self.k.CloseHandle(self.mutex)
