import asyncio
import unittest
from unittest.mock import Mock,AsyncMock,patch
from types import SimpleNamespace
from mr3_client import MR3Client, eq_band_payload, frame,decode_tuning,encode_tuning


def incoming(op,payload,prefix=0xBB):
    p=bytearray(frame(op,payload)); p[0]=prefix; p[-1]=sum(p[:-1])&255
    return p


class ClientTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.inventory_patch=patch('mr3_client.read_paired_devices',new_callable=AsyncMock,return_value={})
        self.inventory=self.inventory_patch.start()
        self.addCleanup(self.inventory_patch.stop)

    async def test_pairing_inventory_error_is_unknown_not_empty_success(self):
        self.inventory.side_effect=OSError('denied')
        events=[]
        c=MR3Client(lambda k,v:events.append((k,v)))
        await c.read_pairing()
        self.assertEqual(events[-1][1]['status'],'error')
        self.assertEqual(events[-1][1]['devices'],{})
        self.assertIn('denied',events[-1][1]['error'])
        self.assertEqual(c.tx_count,0)

    async def test_discovery_streams_deduplicates_and_clears_previous_scan(self):
        events=[]
        live=asyncio.Event()
        def receive(kind,value):
            events.append((kind,value))
            if kind=='discovery' and value['status']=='scanning' and value['rows']: live.set()
        c=MR3Client(receive)
        device=SimpleNamespace(address='AA:BB:CC:DD:EE:01',name=None)
        other=SimpleNamespace(address='AA:BB:CC:DD:EE:02',name=None)
        class Scanner:
            def __init__(self,detection_callback): self.callback=detection_callback
            async def __aenter__(self):
                self.callback(device,SimpleNamespace(local_name='EDIFIER BLE',rssi=-60,service_uuids=[]))
                self.callback(device,SimpleNamespace(local_name=None,rssi=-50,service_uuids=[]))
                self.callback(other,SimpleNamespace(local_name=None,rssi=-75,service_uuids=[]))
            async def __aexit__(self,*args): stopped.append(True)
        stopped=[]
        async def wait_scan(seconds):
            self.assertEqual(seconds,12)
            await asyncio.wait_for(live.wait(),1)
        with patch.dict('sys.modules',{'bleak':SimpleNamespace(BleakScanner=Scanner)}),patch('mr3_client.asyncio.sleep',wait_scan):
            await c.discover()
            live.clear()
            await c.discover()
        snapshots=[v for k,v in events if k=='discovery']
        self.assertEqual([v['rows'] for v in snapshots if v['status']=='scanning' and not v['rows']],[[],[]])
        self.assertEqual(len(snapshots[-1]['rows']),2)
        self.assertEqual(snapshots[-1]['rows'][0]['name'],'EDIFIER BLE')
        self.assertEqual(snapshots[-1]['rows'][0]['rssi'],-50)
        self.assertEqual(snapshots[-1]['status'],'complete')
        self.assertEqual(stopped,[True,True])
        self.assertEqual(c.tx_count,0)

    async def test_cancelled_discovery_stops_scanner_and_reports_partial_results(self):
        events=[]
        entered=asyncio.Event()
        stopped=[]
        class Scanner:
            def __init__(self,**kwargs): pass
            async def __aenter__(self): entered.set()
            async def __aexit__(self,*args): stopped.append(True)
        c=MR3Client(lambda k,v:events.append((k,v)))
        with patch.dict('sys.modules',{'bleak':SimpleNamespace(BleakScanner=Scanner)}):
            task=asyncio.create_task(c.discover())
            await entered.wait()
            task.cancel()
            with self.assertRaises(asyncio.CancelledError): await task
        self.assertEqual(stopped,[True])
        self.assertEqual(events[-1][1]['status'],'cancelled')

    async def test_discovery_error_is_visible(self):
        events=[]
        c=MR3Client(lambda k,v:events.append((k,v)))
        with patch.dict('sys.modules',{'bleak':SimpleNamespace(BleakScanner=Mock(side_effect=OSError('Bluetooth off')))}):
            with self.assertRaises(OSError): await c.discover()
        self.assertEqual(events[-1][1]['status'],'error')
        self.assertIn('Bluetooth off',events[-1][1]['error'])

    async def test_saved_address_connect_skips_scan_and_retries_once(self):
        scanner=SimpleNamespace(find_device_by_address=AsyncMock())
        fake_bleak=SimpleNamespace(BleakClient=Mock(),BleakScanner=scanner)
        fake_device=SimpleNamespace(BLEDevice=Mock(return_value=object()))
        c=MR3Client(lambda *args:None)
        c._connect_device=AsyncMock(side_effect=[TimeoutError(),None])
        with patch.dict('sys.modules',{'bleak':fake_bleak,'bleak.backends.device':fake_device}),patch('mr3_client.asyncio.sleep',new_callable=AsyncMock),patch('mr3_client.ensure_ble_paired',new_callable=AsyncMock) as paired:
            await c.connect('AA:BB:CC:DD:EE:03')
        paired.assert_awaited_once()
        scanner.find_device_by_address.assert_not_awaited()
        self.assertEqual(c._connect_device.await_count,2)
        self.assertEqual([call.args[-1] for call in c._connect_device.await_args_list],[False,True])

    async def test_failed_connection_is_fully_disposed(self):
        c=MR3Client(lambda *args:None)
        partial=Mock(is_connected=False,connect=AsyncMock(side_effect=TimeoutError()),disconnect=AsyncMock())
        with self.assertRaises(TimeoutError):
            await c._connect_device(Mock(return_value=partial),object(),'AA:BB:CC:DD:EE:03',True)
        partial.disconnect.assert_awaited_once()
        self.assertIsNone(c.client)
        self.assertFalse(c.state['connected'])

    def test_tuning_matches_iphone_screenshot(self):
        raw=bytes.fromhex('02 01 00 2d 03 03 01')
        values=decode_tuning(raw)
        self.assertEqual(values,{'cutoff':45,'slope_db':-24,'space_db':-3,'desktop':True})
        self.assertEqual(bytes(encode_tuning(**values)),raw[3:])

    def test_space_all_positions_match_official_labels(self):
        for code in range(5):
            raw=bytes((2,1,0,45,3,code,1))
            self.assertEqual(decode_tuning(raw)['space_db'],-code)
            self.assertEqual(encode_tuning(45,-24,-code,True)[2],code)

    async def test_dispose_inactive_client(self):
        from unittest.mock import AsyncMock
        c=MR3Client(lambda *args:None)
        inactive=Mock(is_connected=False,disconnect=AsyncMock())
        c.client=inactive
        await c.disconnect()
        inactive.disconnect.assert_awaited_once()
        self.assertIsNone(c.client)

    async def test_old_disconnect_callback_does_not_clear_new_client(self):
        c=MR3Client(lambda *args:None)
        c.client=Mock()
        c.state['connected']=True
        c.disconnected(Mock())
        self.assertTrue(c.state['connected'])

    async def test_notification_only_volume(self):
        events=[]
        c=MR3Client(lambda k,v:events.append((k,v)))
        c.notification(None,incoming(0x66,b'\x1e\x0d'))
        c.notification(None,incoming(0x66,b'\x1e\x0c'))
        c.notification(None,incoming(0x66,b'\x1e\x0c'))
        self.assertEqual([v for k,v in events if k=='volume'],[12])
        self.assertEqual(c.tx_count,0)

    async def test_getter_ignores_transport_ack(self):
        c=MR3Client(lambda *args:None)
        c.expected=0x66
        c.pending=asyncio.get_running_loop().create_future()
        c.notification(None,incoming(0x66,b'\x01',0xCC))
        self.assertFalse(c.pending.done())
        c.notification(None,incoming(0x66,b'\x1e\x0d'))
        self.assertEqual(c.pending.result(),b'\x1e\x0d')

    async def test_rename_accepts_transport_ack(self):
        c=MR3Client(lambda *args:None)
        c.expected=0xCA
        c.pending=asyncio.get_running_loop().create_future()
        c.notification(None,incoming(0xCA,b'\x01',0xCC))
        self.assertEqual(c.pending.result(),b'\x01')
        self.assertNotIn('name',c.state)

    async def test_verified_change_restores_mismatch(self):
        c=MR3Client(lambda *args:None)
        c.backup=Mock()
        calls=[]
        responses=iter([b'old',b'\x01',b'wrong',b'\x01',b'old'])
        async def request(op,payload=b''):
            calls.append((op,payload))
            return next(responses)
        c.request=request
        with self.assertRaisesRegex(RuntimeError,'요청과 다릅니다'):
            await c.verified_change(0xCA,b'new',0xC9,lambda p:p==b'new',lambda old:old)
        self.assertEqual(calls[-2],(0xCA,b'old'))
        self.assertEqual(calls[-1],(0xC9,b''))

    async def test_eq_preserves_base_frequency_and_metadata(self):
        c=MR3Client(lambda *args:None)
        c.backup=Mock()
        eq=bytearray(b'\x0c\x09\x01'+b''.join(eq_band_payload(i,0)[1:] for i in range(9))+b'1234profile')
        original=bytes(eq)
        writes=[]
        async def request(op,payload=b''):
            if op==0xD5: return b'\x02\x01\x00\x2d\x03\x03\x01'
            if op==0x43: return bytes(eq)
            if op==0x44:
                writes.append(payload)
                i=payload[1];eq[2]=payload[0];eq[3+4*i:7+4*i]=payload[1:]
                return b'\x01'
        c.request=request
        await c.set_eq([0.5]+[0]*8)
        self.assertEqual(writes,[b'\x01\x00\x00\x3e\x07'])
        self.assertEqual(eq[39:],original[39:])

    async def test_eq_rollback_after_interrupted_write(self):
        c=MR3Client(lambda *args:None)
        c.backup=Mock()
        eq=bytearray(b'\x0c\x09\x00'+b''.join(eq_band_payload(i,0)[1:] for i in range(9))+b'1234profile')
        original=bytes(eq); failed=False
        async def request(op,payload=b''):
            nonlocal failed
            if op==0xD5: return b'\x02\x01\x00\x2d\x03\x03\x01'
            if op==0x43: return bytes(eq)
            if op==0x44:
                i=payload[1];eq[2]=payload[0];eq[3+4*i:7+4*i]=payload[1:]
                if i==1 and not failed:
                    failed=True
                    raise TimeoutError('simulated failure after write')
                return b'\x01'
        c.request=request
        with self.assertRaises(TimeoutError):
            await c.set_eq([0.5]*9,1)
        self.assertEqual(bytes(eq),original)

    def test_invalid_values_rejected(self):
        for bad in (-3.5,3.5,0.25,float('nan'),float('inf')):
            with self.assertRaises(ValueError): eq_band_payload(0,bad)


if __name__=='__main__': unittest.main()
