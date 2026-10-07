"""Discovery presentation tests with synthetic observations; no radio access."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent/'.deps'))
import tkinter as tk
from types import SimpleNamespace
from unittest.mock import Mock
import unittest
from mr3_devices import DevicePicker,saved_devices
from mr3_dpi import initialize


class DevicePickerTests(unittest.TestCase):
    def setUp(self):
        self.root=tk.Tk()
        self.root.attributes('-alpha',0)
        self.root.withdraw()
        initialize(self.root)
        self.saved='AA:BB:CC:DD:EE:01'
        self.other='AA:BB:CC:DD:EE:02'
        self.app=SimpleNamespace(root=self.root,address=tk.StringVar(value=self.saved),
            config={'device_name':'My MR3','address':self.saved},state={},busy=False,action=None,
            discovery={'status':'idle','rows':[]},pairing={'status':'complete','devices':{self.saved:{'name':'EDIFIER BLE','address':self.saved}}},
            start_discovery=Mock(),cancel_connection=Mock(),connect=Mock())
        self.picker=DevicePicker(self.app)

    def tearDown(self):
        self.root.update_idletasks()
        self.root.destroy()

    def test_saved_device_is_separate_and_scan_results_are_fresh(self):
        p=self.picker
        self.assertEqual(p.tree.get_children('paired'),(self.saved,))
        self.assertEqual(p.tree.get_children('candidates'),())
        rows=[{'address':self.saved,'name':'EDIFIER BLE','rssi':-50,'candidate':True},
              {'address':self.other,'name':'이름 없음','rssi':-70,'candidate':False}]
        p.render({'status':'scanning','rows':rows})
        self.assertEqual(p.tree.get_children('paired'),(self.saved,))
        self.assertEqual(p.tree.get_children('others'),(self.other,))
        p.tree.selection_set(self.saved)
        p.render({'status':'scanning','rows':rows})
        self.assertEqual(p.tree.selection(),(self.saved,))
        p.show_others.set(True)
        p.refresh_rows()
        self.assertEqual(len(p.tree.get_children('others')),1)
        p.tree.selection_set(self.other)
        p.update_controls()
        self.assertEqual(p.connect_button.cget('state'),'disabled')
        p.connect_selected()
        self.app.connect.assert_not_called()
        p.show_others.set(False)
        p.refresh_rows()
        self.assertEqual(p.tree.get_children('others'),())
        p.render({'status':'scanning','rows':[]})
        self.assertEqual(p.tree.get_children('paired'),(self.saved,))
        self.assertEqual(p.tree.get_children('others'),())
        self.assertIn('발견되지 않음',p.saved_detail.cget('text'))
        p.render({'status':'complete','rows':[],'time':'12:34:56'})
        self.assertIn('12:34:56',p.scan_status.cget('text'))
        self.assertIn('이번 검색 0대',p.scan_status.cget('text'))
        self.assertEqual(p.connect_button.cget('state'),'disabled')
        self.app.connect.assert_not_called()

    def test_multiple_saved_devices_and_new_candidates_are_separate(self):
        second='AA:BB:CC:DD:EE:03'
        self.app.config['devices']=[{'address':second,'name':'Bedroom MR3'}]
        self.picker.render({'status':'complete','rows':[
            {'address':self.other,'name':'EDIFIER MR3','candidate':True,'rssi':-45}]})
        self.assertEqual(self.picker.tree.get_children('paired'),(self.saved,))
        self.assertEqual(self.picker.tree.get_children('saved'),(second,))
        self.assertEqual(self.picker.tree.get_children('candidates'),(self.other,))
        self.assertEqual(len(saved_devices(self.app.config)),2)
        self.picker.tree.selection_set(second)
        self.picker.connect_selected()
        self.assertEqual(self.app.address.get(),second)
        self.app.connect.assert_called_once()

    def test_busy_buttons_error_and_close_cancel(self):
        p=self.picker
        self.app.busy=True
        self.app.action='discover'
        p.update_controls()
        self.assertEqual(p.search_button.cget('state'),'disabled')
        self.assertEqual(p.saved_connect.cget('state'),'disabled')
        self.assertEqual(p.cancel_button.cget('state'),'normal')
        p.connect_saved()
        self.app.connect.assert_not_called()
        p.render({'status':'error','rows':[],'error':'Bluetooth off','time':'12:34:56'})
        self.assertIn('Bluetooth off',p.hint.cget('text'))
        p.close()
        self.app.cancel_connection.assert_called_once()


if __name__=='__main__': unittest.main()
