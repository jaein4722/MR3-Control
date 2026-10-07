"""No hardware or windows: exercise Windows pairing outcomes and cancellation."""
import asyncio
from enum import IntEnum
from types import SimpleNamespace as NS
import unittest
from unittest.mock import AsyncMock, Mock, patch

from mr3_pairing import ensure_ble_paired, PairingError
from mr3_client import MR3Client


class Status(IntEnum):
    PAIRED = 0
    ALREADY_PAIRED = 1
    PROTECTION_LEVEL_COULD_NOT_BE_MET = 2
    REJECTED_BY_HANDLER = 3


class PairingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.custom = Mock(pair_with_protection_level_async=AsyncMock(return_value=NS(status=Status.PAIRED)),
                           pair_async=AsyncMock(return_value=NS(status=Status.PAIRED)))
        self.pairing = NS(is_paired=False, can_pair=True, custom=self.custom)
        self.info = NS(pairing=self.pairing)
        self.saved = NS(pairing=NS(is_paired=True))
        self.device = Mock(device_information=NS(id='BLE-only-id'))
        self.le = NS(from_bluetooth_address_async=AsyncMock(return_value=self.device))
        self.info_api = NS(create_from_id_async=AsyncMock(side_effect=[self.info, self.saved]))
        self.modules = {
            'winrt.windows.devices.bluetooth': NS(BluetoothLEDevice=self.le),
            'winrt.windows.devices.enumeration': NS(DeviceInformation=self.info_api,
                DevicePairingKinds=NS(CONFIRM_ONLY=1),
                DevicePairingProtectionLevel=NS(ENCRYPTION_AND_AUTHENTICATION=2, ENCRYPTION=1),
                DevicePairingResultStatus=Status),
        }
        self.progress = Mock()

    async def run_pair(self, timeout=60):
        with patch.dict('sys.modules', self.modules):
            return await ensure_ble_paired('AA:BB:CC:DD:EE:03', self.progress, timeout)

    async def test_first_pair_verifies_saved_bond_and_cleans_up(self):
        self.assertTrue(await self.run_pair())
        self.info_api.create_from_id_async.assert_any_await('BLE-only-id')
        self.assertEqual(self.info_api.create_from_id_async.await_count, 2)
        self.custom.pair_with_protection_level_async.assert_awaited_once_with(1, 2)
        handler = self.custom.add_pairing_requested.call_args.args[0]
        args = Mock()
        handler(None, args)
        args.accept.assert_called_once_with()
        self.custom.remove_pairing_requested.assert_called_once()
        self.device.close.assert_called_once()

    async def test_existing_bond_skips_pairing(self):
        self.pairing.is_paired = True
        self.assertFalse(await self.run_pair())
        self.custom.add_pairing_requested.assert_not_called()
        self.custom.pair_with_protection_level_async.assert_not_awaited()
        self.device.close.assert_called_once()

    async def test_protection_negotiation_only_falls_back_for_matching_status(self):
        self.custom.pair_with_protection_level_async.side_effect = [
            NS(status=Status.PROTECTION_LEVEL_COULD_NOT_BE_MET),
            NS(status=Status.PROTECTION_LEVEL_COULD_NOT_BE_MET)]
        self.assertTrue(await self.run_pair())
        self.assertEqual(self.custom.pair_with_protection_level_async.await_count, 2)
        self.custom.pair_async.assert_awaited_once_with(1)

    async def test_rejection_preserves_specific_reason_without_retry(self):
        self.custom.pair_with_protection_level_async.return_value = NS(status=Status.REJECTED_BY_HANDLER)
        with self.assertRaisesRegex(PairingError, 'REJECTED_BY_HANDLER'):
            await self.run_pair()
        self.custom.pair_with_protection_level_async.assert_awaited_once()
        self.custom.pair_async.assert_not_awaited()
        self.custom.remove_pairing_requested.assert_called_once()
        self.device.close.assert_called_once()

    async def test_cannot_pair_never_requests_pairing(self):
        self.pairing.can_pair = False
        with self.assertRaisesRegex(PairingError, '허용하지'):
            await self.run_pair()
        self.custom.add_pairing_requested.assert_not_called()
        self.device.close.assert_called_once()

    async def test_success_without_persistent_bond_is_not_reported_as_ready(self):
        self.info_api.create_from_id_async.side_effect = [self.info, self.info]
        with self.assertRaisesRegex(PairingError, '기록 저장'):
            await self.run_pair()

    async def test_timeout_cleans_up_handler_and_device(self):
        async def hang(*args):
            await asyncio.Event().wait()
        self.custom.pair_with_protection_level_async.side_effect = hang
        with self.assertRaisesRegex(PairingError, '시간이 초과'):
            await self.run_pair(timeout=0.02)
        self.custom.remove_pairing_requested.assert_called_once()
        self.device.close.assert_called_once()

    async def test_user_cancel_remains_cancellation_and_cleans_up(self):
        entered = asyncio.Event()
        async def hang(*args):
            entered.set()
            await asyncio.Event().wait()
        self.custom.pair_with_protection_level_async.side_effect = hang
        task = asyncio.create_task(self.run_pair())
        await entered.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.custom.remove_pairing_requested.assert_called_once()
        self.device.close.assert_called_once()

    async def test_client_pairs_before_gatt_and_stops_on_pair_failure(self):
        c = MR3Client(lambda *args: None)
        factory = Mock()
        order = []
        async def pair(*args): order.append('pair')
        async def connect(*args): order.append('gatt')
        c._connect_device = AsyncMock(side_effect=connect)
        with patch.dict('sys.modules', {
            'bleak': NS(BleakClient=factory, BleakScanner=Mock()),
            'bleak.backends.device': NS(BLEDevice=Mock())}), \
                patch('mr3_client.sys.platform', 'win32'), \
                patch('mr3_client.ensure_ble_paired', new_callable=AsyncMock) as ensure:
            ensure.side_effect = pair
            await c.connect('AA:BB:CC:DD:EE:03')
            self.assertEqual(order, ['pair', 'gatt'])
            ensure.side_effect = PairingError('pair rejected')
            with self.assertRaisesRegex(PairingError, 'pair rejected'):
                await c.connect('AA:BB:CC:DD:EE:03')
            c._connect_device.assert_awaited_once()
            self.assertFalse(c.state['connected'])
            self.assertEqual(c.tx_count, 0)


if __name__ == '__main__':
    unittest.main()
