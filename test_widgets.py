"""Input/notification separation for the new sliders and switches; no Bluetooth."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent/'.deps'))
from types import SimpleNamespace
import tkinter as tk
import unittest
from mr3_widgets import Slider,VolumeBar,Toggle,CircleButton
from mr3_help import HelpPopover
from mr3_dpi import initialize


class WidgetTests(unittest.TestCase):
    def setUp(self):
        self.root=tk.Tk()
        self.root.attributes('-alpha',0)
        self.root.withdraw()

    def tearDown(self):
        self.root.destroy()

    def test_notification_and_disabled_slider_never_send_command(self):
        changes=[]
        var=tk.DoubleVar(value=13)
        slider=Slider(self.root,var,range(31),command=lambda:changes.append(var.get()))
        var.set(14)
        slider.redraw()
        self.assertEqual(changes,[])
        slider.key(SimpleNamespace(keysym='Right'))
        self.assertEqual(changes,[15])
        slider.configure(state='disabled')
        slider.key(SimpleNamespace(keysym='End'))
        slider.press(SimpleNamespace(x=100,y=20))
        slider.release(None)
        self.assertEqual(changes,[15])

    def test_negative_tuning_steps_and_eq_half_decibels(self):
        var=tk.StringVar(value='-6')
        slope=Slider(self.root,var,[-6,-12,-18,-24])
        slope.key(SimpleNamespace(keysym='Right'))
        self.assertEqual(var.get(),'-12')
        slope.key(SimpleNamespace(keysym='End'))
        self.assertEqual(var.get(),'-24')
        gain=tk.DoubleVar(value=-1.5)
        eq=Slider(self.root,gain,[i/2 for i in range(-6,7)],vertical=True)
        eq.key(SimpleNamespace(keysym='Up'))
        self.assertEqual(gain.get(),-1)
        gain.set(3)
        eq.key(SimpleNamespace(keysym='Up'))
        self.assertEqual(gain.get(),3)

    def test_volume_strip_endpoints_and_notification_only_redraw(self):
        self.root.deiconify()
        value=tk.DoubleVar(value=13)
        display=tk.StringVar(value='13 / 30')
        changes=[]
        bar=VolumeBar(self.root,value,display,lambda:changes.append(value.get()))
        bar.pack(fill='x')
        self.root.update()
        value.set(14)
        display.set('14 / 30')
        self.assertEqual(changes,[])
        bar.press(SimpleNamespace(x=0,y=20))
        self.assertEqual(value.get(),0)
        self.assertEqual(changes,[])
        bar.move(SimpleNamespace(x=bar.winfo_width(),y=20))
        self.assertEqual(value.get(),30)
        bar.release(None)
        self.assertEqual(changes,[30])
        bar.configure(state='disabled')
        bar.press(SimpleNamespace(x=0,y=20))
        bar.release(None)
        self.assertEqual(changes,[30])

    def test_switch_state_sync_does_not_apply_setting(self):
        changes=[]
        var=tk.BooleanVar(value=False)
        toggle=Toggle(self.root,var,lambda:changes.append(var.get()))
        var.set(True)
        self.assertEqual(changes,[])
        toggle.toggle()
        self.assertEqual(changes,[False])
        toggle.configure(state='disabled')
        toggle.toggle()
        self.assertEqual(changes,[False])

    def test_help_stays_in_window_and_dismisses_before_consumed_click(self):
        self.root.deiconify()
        self.root.geometry('600x450')
        initialize(self.root)
        popover=HelpPopover(self.root)
        anchor=CircleButton(self.root,'?',lambda:popover.toggle(anchor,'도움말','설명입니다. '*16),filled=True)
        anchor.place(x=550,y=390)
        clicked=[]
        outside=CircleButton(self.root,'+',lambda:clicked.append(True))
        outside.place(x=10,y=10)
        popover.install()
        self.root.update()
        anchor.event_generate('<Button-1>')
        self.root.update()
        self.assertIs(popover.anchor,anchor)
        self.assertEqual(popover.panel.winfo_toplevel(),self.root)
        self.assertLessEqual(popover.panel.winfo_x()+popover.panel.winfo_width(),600)
        self.assertLessEqual(popover.panel.winfo_y()+popover.panel.winfo_height(),anchor.winfo_y())
        # CircleButton returns 'break'; the early bindtag must still dismiss.
        outside.event_generate('<Button-1>')
        self.root.update()
        self.assertIsNone(popover.anchor)
        self.assertEqual(clicked,[True])
        anchor.invoke()
        anchor.invoke()
        self.assertIsNone(popover.anchor)
        anchor.invoke()
        self.assertEqual(popover.escape(),'break')
        self.assertIsNone(popover.anchor)


if __name__=='__main__': unittest.main()
