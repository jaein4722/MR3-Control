"""GUI event delivery smoke test; does not connect to Bluetooth or change settings."""
import asyncio
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import tkinter as tk
from tkinter import font as tkfont
from mr3_app import App


class AppTests(unittest.TestCase):
    def test_preferences_survive_restart_and_control_window_lifecycle(self):
        with tempfile.TemporaryDirectory() as folder:
            config=Path(folder)/'app-state.json'
            config.write_text(json.dumps({'address':'AA:BB:CC:DD:EE:FF','device_name':'My MR3',
                                          'devices':[{'address':'AA:BB:CC:DD:EE:01','name':'Other MR3'}],
                                          'auto_connect':False}),encoding='utf-8')
            with patch('mr3_app.CONFIG',config),patch.object(App,'setup_tray'),patch.object(App,'connect') as connect:
                for launch in range(2):
                    root=tk.Tk()
                    root.attributes('-alpha',0)  # Still creates a window: run only on an isolated desktop.
                    app=App(root)
                    app.overlay.factory=lambda: Mock(work_area=lambda:(0,0,1920,1040))
                    try:
                        root.update()
                        self.assertEqual(app.address.get(),'AA:BB:CC:DD:EE:FF')
                        if launch==0:
                            app.start_minimized.set(True)
                            app.close_to_tray.set(False)
                            app.save_config()
                        else:
                            self.assertEqual(root.state(),'withdrawn')
                            self.assertFalse(app.close_to_tray.get())
                            self.assertEqual(app.config['device_name'],'My MR3')
                            self.assertEqual({d['name'] for d in app.config['devices']},{'My MR3','Other MR3'})
                            with patch.object(app,'quit') as quit,patch.object(app,'hide') as hide:
                                app.on_close()
                                quit.assert_called_once()
                                hide.assert_not_called()
                                app.close_to_tray.set(True)
                                app.on_close()
                                hide.assert_called_once()
                            app.events.put(('tray_failed',None))
                            app.drain()
                            root.update()
                            self.assertEqual(root.state(),'normal')
                        connect.assert_not_called()
                    finally:
                        app.closed=True
                        app.loop.call_soon_threadsafe(app.loop.stop)
                        app.worker.join(timeout=2)
                        root.destroy()

    def test_worker_event_displays_and_hides_osd_without_polling(self):
        root=tk.Tk()
        root.attributes('-alpha',0)
        root.withdraw()
        errors=[]
        root.report_callback_exception=lambda *args:errors.append(args)
        with patch.object(App,'connect'),patch.object(App,'setup_tray'):
            app=App(root)
        app.overlay.factory=lambda: Mock(work_area=lambda:(0,0,1920,1040))
        app.save_config=lambda:None
        self.assertEqual(tkfont.Font(root=root,family='Pretendard',size=11).actual('family'),'Pretendard')
        self.assertEqual(app.book.current,0)
        app.home_rows[0].invoke()
        self.assertEqual(app.book.current,1)
        self.assertEqual(app.book.pages[0].winfo_manager(),'')
        self.assertEqual(app.book.pages[1].winfo_manager(),'grid')
        app.book.select(5)
        app.book.back()
        self.assertEqual(app.book.current,1)
        app.book.back()
        self.assertEqual(app.book.current,0)
        self.assertEqual(app.cutoff.get(),'')
        self.assertEqual(app.space.get(),'')
        original=[2,1,0,45,3,3,1]
        app.sync({'connected':True,'raw':{'d5':original},'mode_code':2,'room':original[1:]})
        self.assertEqual((app.cutoff.get(),app.slope.get(),app.space.get(),app.desktop.get()),('45','-24','-3',True))
        self.assertEqual(app.home_mode_var.get(),'사용자 설정')
        self.assertIn('45Hz',app.home_tuning_var.get())
        self.assertIn('−3dB',app.home_tuning_var.get())
        with patch.object(app,'submit') as submit:
            app.apply_room()
            submit.assert_called_once_with(app.client.set_room,45,3,3,1)
        app.sync({'connected':False,'raw':{}})
        self.assertEqual(app.space.get(),'')
        app.overlay_enabled.set(True)
        # Real event_generate crosses from the asyncio thread to Tk's main loop.
        async def emit():
            app.post('volume',12)
        def start():
            asyncio.run_coroutine_threadsafe(emit(),app.loop)
        observations=[]
        def visible():
            observations.append((app.overlay.visible,app.overlay.value))
        def finish():
            observations.append(app.overlay.visible)
            app.closed=True
            app.loop.call_soon_threadsafe(app.loop.stop)
            root.destroy()
        root.after(100,start)
        root.after(500,visible)
        root.after(2500,finish)
        root.mainloop()
        app.worker.join(timeout=2)
        self.assertEqual(errors,[])
        self.assertEqual(observations[0][0],1)
        self.assertEqual(observations[0][1],12)
        self.assertEqual(observations[1],0)
        self.assertEqual(app.client.tx_count,0)


if __name__=='__main__': unittest.main()
