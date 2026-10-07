"""MR3 desktop controls and notification-driven volume OSD. No polling timer."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent
if not getattr(sys, 'frozen', False):
    sys.path.insert(0, str(ROOT / '.deps'))
import asyncio
import ctypes
import json
import logging
import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from mr3_client import MR3Client, eq_band_payload, decode_tuning, encode_tuning
from mr3_widgets import BG,CARD,FG,MUTED,ACCENT,FONT,Slider,button as themed_button
from mr3_dpi import dp,initialize,enable_dpi_awareness
from mr3_paths import DATA_DIR

CONFIG = DATA_DIR / 'app-state.json'
MODES = ('모니터', '음악', '사용자 설정')


class App:
    def __init__(self, root):
        initialize(root)
        self.root = root
        self.closed = False
        self.closing = False
        self.busy = False
        self.events = queue.SimpleQueue()
        self.state = {}
        self.seen = {}
        self.buttons = []
        self.editors = []
        self.action = None
        self.action_future = None
        self.operation_task = None
        self.discovery = {'status':'idle','rows':[]}
        self.pairing = {'status':'idle','devices':{}}
        self.tray = None
        self.tray_ready = False
        self.config = {}
        try:
            self.config = json.loads(CONFIG.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            pass
        self.start_minimized = tk.BooleanVar(value=self.config.get('start_minimized',False))
        self.close_to_tray = tk.BooleanVar(value=self.config.get('close_to_tray',True))
        self.auto_connect = tk.BooleanVar(value=self.config.get('auto_connect',True))
        self.startup_enabled = tk.BooleanVar(value=False)
        self.startup_error = None
        if sys.platform == 'win32':
            try:
                import mr3_startup
                self.startup_enabled.set(mr3_startup.is_enabled())
            except OSError as e:
                self.startup_error = str(e)
                logging.exception('Could not read login startup registration')
        if self.start_minimized.get():
            root.withdraw()
        root.title('MR3 Control')
        root.geometry(f'{dp(940)}x{dp(760)}')
        root.minsize(dp(860), dp(640))
        root.configure(bg=BG)
        root.option_add('*Font', (FONT, 11))
        from tkinter import font as tkfont
        for name in ('TkDefaultFont','TkTextFont','TkMenuFont','TkHeadingFont','TkCaptionFont','TkTooltipFont'):
            tkfont.nametofont(name,root=root).configure(family=FONT)
        style = ttk.Style(root)
        style.theme_use('clam')
        style.configure('.', background=BG, foreground=FG, fieldbackground=CARD, borderwidth=0,font=(FONT,11))
        style.configure('TButton', background=CARD, padding=dp((14, 8)))
        style.map('TButton', background=[('active', '#414141'), ('disabled', '#202020')],
                  foreground=[('disabled', '#767676')])
        style.configure('TNotebook', background=BG, borderwidth=0)
        style.configure('TNotebook.Tab', padding=dp((24, 11)), background=BG)
        style.map('TNotebook.Tab', background=[('selected', CARD)], foreground=[('selected', ACCENT)])
        style.configure('TCombobox', arrowcolor=FG, padding=dp(6))
        style.map('TCombobox', fieldbackground=[('readonly', CARD)], foreground=[('readonly', FG)])
        style.configure('TEntry', padding=dp(6))
        style.configure('Treeview',background=CARD,fieldbackground=CARD,foreground=FG,rowheight=dp(27))
        style.configure('Treeview.Heading',background=BG,foreground=FG,padding=dp(6))
        style.map('Treeview',background=[('selected','#454037')],foreground=[('selected',ACCENT)])
        style.configure('Vertical.TScrollbar',background='#333333',troughcolor=BG,
                        bordercolor=BG,lightcolor=BG,darkcolor=BG,arrowcolor=MUTED,width=dp(6),arrowsize=dp(6),
                        borderwidth=0,gripcount=0)
        style.layout('Vertical.TScrollbar',[('Vertical.Scrollbar.trough',{'sticky':'ns','children':[
            ('Vertical.Scrollbar.thumb',{'sticky':'nswe','expand':1})]})])
        style.map('Vertical.TScrollbar',background=[('active','#555555')])
        style.configure('TCheckbutton', background=BG)
        style.configure('Horizontal.TScale', background=ACCENT, troughcolor=CARD,
                        bordercolor=CARD, lightcolor=ACCENT, darkcolor=ACCENT)
        style.map('TCheckbutton', background=[('active', BG)])
        root.bind('<<MR3Event>>', self.drain)
        root.protocol('WM_DELETE_WINDOW', self.on_close)
        self.status = tk.StringVar(value='연결 대기')
        self.volume_text = tk.StringVar(value='— / 30')
        self.volume = tk.DoubleVar(value=0)
        self.mode = tk.StringVar()
        self.base = tk.StringVar()
        self.eq_name = tk.StringVar()
        self.device_name = tk.StringVar()
        self.address = tk.StringVar(value=self.config.get('address',''))
        self.overlay_enabled = tk.BooleanVar(value=self.config.get('overlay',True))
        self.beep = tk.BooleanVar()
        self.desktop = tk.BooleanVar()
        self.cutoff = tk.StringVar()
        self.slope = tk.StringVar()
        self.space = tk.StringVar()
        self.read_status = tk.StringVar(value='연결 후 기기의 설정을 표시합니다.')
        self.gains = [tk.DoubleVar(value=0) for _ in range(9)]
        self.build()
        self.set_window_icon()
        self.build_overlay()
        self.loop = asyncio.new_event_loop()
        self.client = MR3Client(self.post)
        self.worker = threading.Thread(target=self.run_worker, daemon=True)
        self.worker.start()
        self.setup_tray()
        if self.auto_connect.get() and self.address.get().strip():
            root.after(150, self.connect)
        elif not self.address.get().strip():
            self.status.set('기기 선택에서 MR3를 선택해 주세요.')

    def run_worker(self):
        asyncio.set_event_loop(self.loop)
        initialized = False
        if sys.platform == 'win32':
            initialized = ctypes.windll.ole32.CoInitializeEx(None,0) in (0,1)
        try:
            self.loop.run_forever()
        finally:
            self.loop.run_until_complete(self.loop.shutdown_asyncgens())
            self.loop.close()
            if initialized:
                ctypes.windll.ole32.CoUninitialize()

    def editor(self, widget, normal='normal', **pack):
        widget.pack(**pack)
        self.editors.append((widget,normal))
        return widget

    def label(self, parent, text, size=10, color=FG, **pack):
        w = tk.Label(parent, text=text, bg=BG, fg=color, font=(FONT, size), anchor='w')
        w.pack(**pack)
        return w

    def button(self, parent, text, callback, connected=True, **pack):
        b = ttk.Button(parent, text=text, command=callback)
        b.pack(**pack)
        self.buttons.append((b, connected))
        return b

    def row(self, parent, pady=8):
        f = ttk.Frame(parent)
        f.pack(fill='x', pady=dp(pady))
        return f

    def build(self):
        from mr3_ui import build_interface
        build_interface(self)

    def set_window_icon(self):
        try:
            self.root.iconbitmap(default=str(ROOT/'assets'/'mr3.ico'))
            if sys.platform=='win32':
                self.root.update_idletasks()
                user32=ctypes.windll.user32
                user32.GetParent.restype=ctypes.c_void_p
                hwnd=user32.GetParent(self.root.winfo_id())
                dark=ctypes.c_int(1)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(ctypes.c_void_p(hwnd),20,
                                                          ctypes.byref(dark),ctypes.sizeof(dark))
        except (OSError,tk.TclError):
            logging.exception('Window appearance could not be set')

    def build_overlay(self):
        from mr3_overlay import VolumeOverlay
        self.overlay = VolumeOverlay(self.root)
        self.overlay_enabled.trace_add('write',lambda *_: None if self.overlay_enabled.get() else self.overlay.hide())

    def show_overlay(self,value,preview=False):
        if not preview and not self.overlay_enabled.get():
            return
        self.overlay.show(value)

    def post(self,kind,value=None):
        if self.closed:
            return
        self.events.put((kind,value))
        try:
            self.root.event_generate('<<MR3Event>>',when='tail')
        except (tk.TclError,RuntimeError):
            pass

    def drain(self,event=None):
        while not self.events.empty():
            kind,value=self.events.get()
            if kind=='state':
                self.sync(value)
            elif kind=='volume':
                self.show_overlay(value)
            elif kind=='message':
                self.status.set(value)
            elif kind=='done':
                self.busy=False
                self.action=None
                self.update_controls()
            elif kind=='discovery':
                self.discovery=value
                if hasattr(self,'device_dialog') and self.device_dialog.winfo_exists():
                    self.device_dialog.render(value)
            elif kind=='pairing':
                self.pairing=value
                if hasattr(self,'device_dialog') and self.device_dialog.winfo_exists():
                    self.device_dialog.refresh_rows()
                    self.device_dialog.refresh_saved()
            elif kind=='error':
                self.status.set('처리 실패 · '+value)
                if self.action not in ('connect','discover'):
                    messagebox.showerror('MR3 Control',value,parent=self.root)
            elif kind=='show':
                self.root.deiconify(); self.root.lift()
            elif kind=='tray_ready':
                self.tray_ready=True
            elif kind=='tray_failed':
                self.tray_ready=False
                self.tray=None
                self.root.deiconify()
                self.status.set('트레이를 사용할 수 없어 창을 표시했습니다.')
            elif kind=='quit':
                self.quit()
            elif kind=='closed':
                self.closed=True
                self.overlay.close()
                if self.tray:
                    self.tray.stop()
                self.loop.call_soon_threadsafe(self.loop.stop)
                self.root.destroy()

    def submit(self,method,*args):
        if self.busy:
            return
        self.busy=True
        self.action=method.__name__
        self.status.set('처리 중…')
        self.update_controls()
        async def run():
            self.operation_task=asyncio.current_task()
            try:
                await method(*args)
                if method.__name__=='discover':
                    self.post('message','검색 완료 · 기기를 선택하고 연결하세요.')
                else:
                    self.post('message','연결됨' if self.client.state.get('connected') else '연결 해제됨')
            except asyncio.CancelledError:
                self.post('message','검색을 취소했습니다.' if method.__name__=='discover' else '연결 작업을 취소했습니다.')
            except Exception as e:
                logging.exception('MR3 action failed')
                self.post('error',str(e) or type(e).__name__)
            finally:
                self.operation_task=None
                self.post('done')
        self.action_future=asyncio.run_coroutine_threadsafe(run(),self.loop)

    def sync(self,state):
        was_connected=self.state.get('connected',False)
        self.state=state
        raw=state.get('raw',{})
        if state.get('name'): self.home_name_var.set(state['name'])
        mode_code=state.get('mode_code')
        self.home_mode_var.set(MODES[mode_code] if mode_code in (0,1,2) and raw else '연결 후 설정 확인')
        if raw.get('d5'):
            tuning=decode_tuning(raw['d5'])
            self.home_tuning_var.set(f"{tuning['cutoff']}Hz · {tuning['slope_db']}dB/octave · {tuning['space_db']}dB".replace('-','−'))
        else:
            self.home_tuning_var.set('로우 컷오프 · 어쿠스틱 스페이스 · 데스크톱 컨트롤')
        if not raw:
            for var in (self.mode,self.base,self.cutoff,self.slope,self.space,self.eq_name,self.device_name):
                var.set('')
            self.volume_text.set('— / 30')
            self.read_status.set('연결 후 기기의 설정을 표시합니다.')
        if 'volume' in state and raw.get('66')!=self.seen.get('66'):
            self.volume.set(state['volume'])
            self.volume_text.set(f"{state['volume']} / 30")
        if 'mode_code' in state and raw.get('d5')!=self.seen.get('d5'):
            m=state['mode_code']
            if m in range(3): self.mode.set(MODES[m])
            r=state.get('room',[])
            if len(r)==6 and r[0]==1:
                tuning=decode_tuning(raw['d5'])
                self.cutoff.set(str(tuning['cutoff'])); self.slope.set(str(tuning['slope_db']))
                self.space.set(str(tuning['space_db'])); self.desktop.set(tuning['desktop'])
        if 'eq' in state and raw.get('43')!=self.seen.get('43'):
            for v,b in zip(self.gains,state['eq']['bands']): v.set(b['gain_db'])
            base=raw['43'][2]
            if base in (0,1): self.base.set(MODES[base])
            self.eq_name.set(state['eq'].get('profile_name_candidate',''))
        if raw.get('c9')!=self.seen.get('c9'): self.device_name.set(state.get('name',''))
        if raw.get('86')!=self.seen.get('86'): self.beep.set(state.get('beep',False))
        self.seen={k:list(v) for k,v in raw.items()}
        for label,var in zip(self.eq_value_labels,self.gains):
            label.configure(text=f'{var.get():g}dB' if state.get('eq') else '—')
        self.info.configure(text=f"펌웨어 {state.get('firmware','—')}   ·   {state.get('name','MR3')}")
        if was_connected and not state.get('connected'):
            self.status.set('연결 해제됨 · 연결 버튼으로 다시 연결하세요.')
        if state.get('connected'):
            self.read_status.set('기기 설정 동기화됨')
            if not was_connected:
                self.save_config()
        elif raw:
            self.read_status.set('연결 해제됨 · 표시된 값은 마지막으로 읽은 설정입니다.')
        self.update_controls()

    def update_controls(self):
        connected=self.state.get('connected',False)
        for button,needs_connection in self.buttons:
            button.configure(state='normal' if not self.busy and (connected or not needs_connection) else 'disabled')
        self.vol_slider.configure(state='normal' if connected and not self.busy else 'disabled')
        for widget,normal in self.editors:
            widget.configure(state=normal if connected and not self.busy else 'disabled')
            if isinstance(widget,tk.Scale):
                widget.configure(showvalue=bool(self.state.get('eq')))
        if self.busy and self.action in ('connect','discover'):
            self.cancel_button.pack(side='right',padx=dp(8))
            self.cancel_button.configure(state='normal')
        else:
            self.cancel_button.pack_forget()
        if hasattr(self,'device_dialog') and self.device_dialog.winfo_exists():
            self.device_dialog.refresh_saved()
            self.device_dialog.update_controls()

    def save_config(self):
        from mr3_devices import saved_devices
        known=saved_devices(self.config)
        if self.config.get('address')!=self.address.get().strip():
            self.config.pop('device_name',None)
        self.config.update(address=self.address.get().strip(),overlay=self.overlay_enabled.get(),
                           start_minimized=self.start_minimized.get(),close_to_tray=self.close_to_tray.get(),
                           auto_connect=self.auto_connect.get())
        if self.state.get('connected') and self.state.get('address')==self.config['address']:
            self.config['device_name']=self.state.get('name','MR3')
            known[self.config['address']]={'address':self.config['address'],'name':self.config['device_name']}
        self.config['devices']=list(known.values())
        CONFIG.parent.mkdir(parents=True,exist_ok=True)
        temporary=CONFIG.with_suffix('.tmp')
        temporary.write_text(json.dumps(self.config,ensure_ascii=False,indent=2),encoding='utf-8')
        temporary.replace(CONFIG)

    def change_startup(self):
        import mr3_startup
        requested=self.startup_enabled.get()
        try:
            mr3_startup.set_enabled(requested)
            self.startup_enabled.set(mr3_startup.is_enabled())
            self.status.set('Windows 로그인 시 자동 실행 '+('켬' if self.startup_enabled.get() else '끔'))
        except OSError as e:
            self.startup_enabled.set(not requested)
            logging.exception('Could not change login startup registration')
            messagebox.showerror('자동 실행 설정 실패',str(e),parent=self.root)

    def cancel_connection(self):
        if self.action in ('connect','discover') and self.action_future:
            self.action_future.cancel()

    def connect(self):
        if not self.address.get().strip():
            self.open_devices()
            return
        self.save_config()
        self.seen={}
        self.submit(self.client.connect,self.address.get().strip())

    def apply_eq(self):
        if self.state.get('mode_code')!=2:
            messagebox.showinfo('사용자 EQ','음향 모드를 사용자 설정으로 적용한 뒤 EQ를 적용하세요.',parent=self.root)
            return
        self.submit(self.client.set_eq,[v.get() for v in self.gains],MODES.index(self.base.get()))

    def apply_room(self):
        values=encode_tuning(int(self.cutoff.get()),int(self.slope.get()),int(self.space.get()),self.desktop.get())
        self.submit(self.client.set_room,*values)

    def open_devices(self):
        self.help_popover.hide()
        if hasattr(self,'device_dialog') and self.device_dialog.winfo_exists():
            self.device_dialog.lift()
            return
        from mr3_devices import DevicePicker
        self.device_dialog=DevicePicker(self)
        if not self.busy: self.start_discovery()
        else: asyncio.run_coroutine_threadsafe(self.client.read_pairing(),self.loop)

    def start_discovery(self):
        if self.busy: return
        self.discovery={'status':'scanning','rows':[]}
        if hasattr(self,'device_dialog') and self.device_dialog.winfo_exists():
            self.device_dialog.render(self.discovery)
        self.submit(self.client.discover)

    def save_profile(self):
        path=filedialog.asksaveasfilename(parent=self.root,title='EQ 파일 저장',defaultextension='.json',filetypes=[('MR3 EQ','*.json')])
        if path:
            Path(path).write_text(json.dumps({'format':'mr3-eq-v1','name':self.eq_name.get(),
                'base':MODES.index(self.base.get()),'gains':[v.get() for v in self.gains]},ensure_ascii=False,indent=2),encoding='utf-8')

    def load_profile(self):
        path=filedialog.askopenfilename(parent=self.root,title='EQ 파일 불러오기',filetypes=[('MR3 EQ','*.json')])
        if not path: return
        try:
            p=json.loads(Path(path).read_text(encoding='utf-8'))
            if p['format']!='mr3-eq-v1' or len(p['gains'])!=9 or p['base'] not in (0,1): raise ValueError('잘못된 EQ 파일입니다.')
            for i,g in enumerate(p['gains']): eq_band_payload(i,g,p['base'])
            for v,g in zip(self.gains,p['gains']): v.set(g)
            self.base.set(MODES[p['base']]); self.eq_name.set(str(p.get('name','')))
            self.status.set('파일을 편집 화면에 불러왔습니다. EQ 적용 버튼으로 스피커에 저장하세요.')
        except Exception as e:
            messagebox.showerror('파일 오류',str(e),parent=self.root)

    def restore_backup(self):
        path=filedialog.askopenfilename(parent=self.root,title='원본 설정 백업 선택',initialdir=DATA_DIR/'backups',filetypes=[('MR3 백업','*.json')])
        if not path: return
        try:
            p=json.loads(Path(path).read_text(encoding='utf-8'))
            if p.get('address')!=self.state.get('address'): raise ValueError('현재 스피커의 백업이 아닙니다.')
            raw=p['raw']; eq=bytes(raw['43']); mode=bytes(raw['d5']); beep=bytes(raw['86'])
            if (len(eq)<43 or eq[:2]!=b'\x0c\x09' or len(mode)!=7 or mode[0] not in range(3)
                or mode[1:3]!=b'\x01\x00' or mode[3] not in range(20,101,5)
                or mode[4] not in range(4) or mode[5] not in range(5) or mode[6] not in (0,1)
                or len(beep)!=2 or beep[0]!=2 or beep[1] not in (0,1)):
                raise ValueError('지원하지 않는 백업 형식입니다.')
            gains=[(eq[6+4*i]-6)/2 for i in range(9)]
            for i,g in enumerate(gains):
                if eq_band_payload(i,g,eq[2])[1:]!=eq[3+4*i:7+4*i]:
                    raise ValueError('EQ 주파수 배열이 예상과 다릅니다.')
            for name in (eq[43:],bytes(raw['c9'])):
                text=name.decode('utf-8')
                if not 1<=len(name)<=30 or text.strip()!=text or any(ord(ch)<32 for ch in text):
                    raise ValueError('백업의 이름 형식이 올바르지 않습니다.')
            if not messagebox.askyesno('백업 복원','선택한 백업의 EQ, 음향 모드, 공간 보정, 안내음, 이름을 복원합니다. 볼륨은 유지합니다. 계속할까요?',parent=self.root): return
            async def restore():
                await self.client.set_mode(2)
                await self.client.set_eq(gains,eq[2])
                await self.client.rename_eq(eq[43:].decode('utf-8'))
                await self.client.set_mode(mode[0])
                await self.client.set_room(*mode[3:])
                await self.client.set_beep(bool(beep[1]))
                await self.client.rename(bytes(raw['c9']).decode('utf-8'))
                await self.client.refresh()
            self.submit(restore)
        except Exception as e:
            messagebox.showerror('백업 오류',str(e),parent=self.root)

    def setup_tray(self):
        try:
            import pystray
            from PIL import Image
            icon=Image.open(ROOT/'assets'/'mr3.png').convert('RGBA')
            self.tray=pystray.Icon('MR3Control',icon,'MR3 Control',pystray.Menu(
                pystray.MenuItem('설정 열기',lambda:self.post('show'),default=True),
                pystray.MenuItem('종료',lambda:self.post('quit'))))
            def ready(tray):
                tray.visible=True
                self.post('tray_ready')
            def run():
                try:
                    self.tray.run(setup=ready)
                except Exception:
                    logging.exception('Tray failed')
                    self.post('tray_failed')
            threading.Thread(target=run,daemon=True).start()
        except Exception:
            logging.exception('Tray unavailable')
            self.tray=None
            self.root.deiconify()

    def on_close(self):
        if self.close_to_tray.get(): self.hide()
        else: self.quit()

    def hide(self):
        if self.tray_ready: self.root.withdraw()
        else: self.root.iconify()

    def quit(self):
        if self.closing: return
        if self.busy and self.action not in ('connect','discover'):
            self.status.set('설정 적용이 끝난 뒤 종료해 주세요.')
            return
        self.closing=True
        self.save_config()
        self.busy=True
        self.update_controls()
        async def close():
            try:
                task=self.operation_task
                if task:
                    task.cancel()
                    try: await task
                    except asyncio.CancelledError: pass
                await self.client.disconnect()
            finally: self.post('closed')
        asyncio.run_coroutine_threadsafe(close(),self.loop)


def main():
    enable_dpi_awareness()
    DATA_DIR.mkdir(parents=True,exist_ok=True)
    logging.basicConfig(filename=DATA_DIR/'app.log',level=logging.INFO,encoding='utf-8',
                        format='%(asctime)s %(levelname)s %(message)s')
    instance=None
    if sys.platform=='win32':
        from mr3_instance import SingleInstance
        instance=SingleInstance()
        if instance.existing:
            instance.close()
            return
    if sys.platform=='win32':
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('MR3Control.Desktop')
    root=tk.Tk()
    root.report_callback_exception=lambda t,v,tb: (logging.error('UI error',exc_info=(t,v,tb)),messagebox.showerror('MR3 Control',str(v),parent=root))
    app=App(root)
    if instance: instance.listen(lambda:app.post('show'))
    try:
        root.mainloop()
    finally:
        app.worker.join(timeout=5)
        if instance: instance.close()

if __name__=='__main__':
    main()
