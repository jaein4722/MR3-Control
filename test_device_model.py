"""Headless classification tests: never construct Tk or interact with the desktop."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock, patch
from mr3_devices import device_groups, pairing_label
from mr3_pairing import read_paired_devices

SAVED='AA:BB:CC:DD:EE:03'
NEW='AA:BB:CC:DD:EE:01'
OTHER='AA:BB:CC:DD:EE:02'
CONFIG={'address':SAVED,'device_name':'My MR3'}


class GroupTests(unittest.TestCase):
    def test_saved_history_does_not_imply_pairing(self):
        groups=device_groups(CONFIG,[],{'status':'complete','devices':{}},{})
        self.assertFalse(groups['paired'])
        self.assertEqual(groups['saved'][0][0],SAVED)
        self.assertIn('미페어링',groups['saved'][0][2])

    def test_bonded_device_stays_visible_without_advertisement(self):
        groups=device_groups(CONFIG,[],{'status':'complete','devices':{SAVED:{'name':'EDIFIER BLE'}}},{})
        self.assertFalse(groups['saved'])
        self.assertIn('페어링됨 · 검색 미발견',groups['paired'][0][2])
        self.assertEqual(groups['paired'][0][1],'My MR3')

    def test_new_windows_bond_appears_without_app_history(self):
        groups=device_groups({},[],{'status':'complete','devices':{NEW:{'name':'EDIFIER BLE'}}},{})
        self.assertEqual(groups['paired'][0][0],NEW)

    def test_failure_does_not_claim_unpaired_or_trust_stale_bonds(self):
        state={'status':'error','devices':{SAVED:{'name':'EDIFIER BLE'}}}
        groups=device_groups(CONFIG,[],state,{})
        self.assertFalse(groups['paired'])
        self.assertIn('확인 실패',groups['saved'][0][2])
        self.assertEqual(pairing_label(SAVED,state),'페어링 확인 실패')

    def test_candidates_and_unsupported_are_separate_even_when_bonded(self):
        rows=[{'address':NEW,'name':'EDIFIER MR3','candidate':True,'rssi':-40},
              {'address':OTHER,'name':'Mouse','candidate':False,'rssi':-65}]
        pairing={'status':'complete','devices':{OTHER:{'name':'Mouse'}}}
        groups=device_groups(CONFIG,rows,pairing,{})
        self.assertEqual(groups['candidates'][0][0],NEW)
        self.assertEqual(groups['others'][0][0],OTHER)
        self.assertIn('페어링됨',groups['others'][0][2])
        self.assertFalse(groups['paired'])

    def test_connected_is_independent_of_bond_and_discovery(self):
        groups=device_groups(CONFIG,[],{'status':'loading','devices':{}},{'connected':True,'address':SAVED})
        self.assertIn('페어링 확인 중 · 연결됨',groups['saved'][0][2])


class InventoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_windows_inventory_uses_remote_address_and_paired_le_selector(self):
        le=NS(get_device_selector_from_pairing_state=Mock(return_value='paired-le-selector'))
        info=NS(find_all_async_aqs_filter=AsyncMock(return_value=[
            NS(id='BluetoothLE#BluetoothLE11:22:33:44:55:66-aa:bb:cc:dd:ee:03',name='EDIFIER BLE')]))
        with patch.dict('sys.modules',{'winrt.windows.devices.bluetooth':NS(BluetoothLEDevice=le),
                                      'winrt.windows.devices.enumeration':NS(DeviceInformation=info)}):
            result=await read_paired_devices()
        self.assertEqual(list(result),[SAVED])
        le.get_device_selector_from_pairing_state.assert_called_once_with(True)
        info.find_all_async_aqs_filter.assert_awaited_once_with('paired-le-selector')


if __name__=='__main__': unittest.main()
