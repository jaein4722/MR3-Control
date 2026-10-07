import unittest
from mr3_volume_test import volume_packet, volume_roundtrip


class FakeClient:
    def __init__(self):
        self.volume = 13
        self.writes = []

    async def write_gatt_char(self, uuid, packet, response):
        self.volume = packet[5]
        self.writes.append(self.volume)


class FakeSession:
    def __init__(self, fail_readback=False):
        self.client = FakeClient()
        self.count = 0
        self.fail_readback = fail_readback

    async def query(self, name):
        self.count += 1
        if self.fail_readback and self.count == 2:
            raise RuntimeError("simulated read-back failure")
        return bytes((30, self.client.volume))


class VolumeWriteTests(unittest.IsolatedAsyncioTestCase):
    def test_bounds_and_frame(self):
        self.assertEqual(volume_packet(0).hex(), "aaec67000100fe")
        self.assertEqual(volume_packet(12).hex(), "aaec6700010c0a")
        for value in (-1, 31, True, 2.5):
            with self.assertRaises(ValueError):
                volume_packet(value)

    async def test_change_and_restore(self):
        session, report = FakeSession(), {}
        await volume_roundtrip(session, report, lambda: None)
        self.assertEqual(session.client.writes, [12, 13])
        self.assertEqual(report["status"], "write_and_restore_verified")

    async def test_restore_even_after_readback_failure(self):
        session, report = FakeSession(True), {}
        with self.assertRaisesRegex(RuntimeError, "simulated"):
            await volume_roundtrip(session, report, lambda: None)
        self.assertEqual(session.client.volume, 13)
        self.assertTrue(report["restore_verified"])

    async def test_muted_device_is_not_raised(self):
        session, report = FakeSession(), {}
        session.client.volume = 0
        await volume_roundtrip(session, report, lambda: None)
        self.assertEqual(session.client.writes, [])
        self.assertEqual(report["status"], "skipped_already_muted")


if __name__ == "__main__":
    unittest.main()
