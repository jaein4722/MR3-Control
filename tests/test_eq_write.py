import unittest
from tools.mr3_eq_test import validate_eq, band_packet, eq_roundtrip

ORIGINAL = bytes.fromhex("0c 09 00 00 00 3e 0c 01 00 7d 00 02 00 fa 03 03 01 f4 06 04 03 e8 06 05 07 d0 06 06 0f a0 06 07 1f 40 06 08 3e 80 06 56 28 6b 69") + "사운드 효과".encode()


class FakeSession:
    def __init__(self, fail=False):
        self.client = self
        self.eq = ORIGINAL
        self.eq_reads = 0
        self.fail = fail
        self.writes = []

    async def query(self, name):
        if name == "preset":
            return bytes.fromhex("02 01 00 2d 03 03 01")
        self.eq_reads += 1
        if self.fail and self.eq_reads == 2:
            raise RuntimeError("read-back failed")
        return self.eq

    async def write_gatt_char(self, uuid, packet, response):
        self.writes.append(packet)
        self.eq = self.eq[:3] + packet[6:10] + self.eq[7:]


class EqTests(unittest.IsolatedAsyncioTestCase):
    def test_bounds(self):
        self.assertEqual(validate_eq(ORIGINAL), ORIGINAL)
        self.assertEqual(band_packet(bytes.fromhex("00 00 3e 07")).hex(), "aaec4400050000003e0724")
        for value in (b"", bytes.fromhex("01 00 3e 07"), bytes.fromhex("00 00 3e ff")):
            with self.assertRaises(ValueError):
                band_packet(value)
        with self.assertRaises(ValueError):
            validate_eq(ORIGINAL[:10])

    async def test_one_band_change_and_exact_restoration(self):
        session, report = FakeSession(), {}
        await eq_roundtrip(session, report, lambda: None)
        self.assertEqual(report["changed_byte_offsets"], [6])
        self.assertEqual(session.eq, ORIGINAL)
        self.assertEqual(report["status"], "write_and_restore_verified")

    async def test_restore_after_read_failure(self):
        session, report = FakeSession(True), {}
        with self.assertRaisesRegex(RuntimeError, "read-back"):
            await eq_roundtrip(session, report, lambda: None)
        self.assertEqual(session.eq, ORIGINAL)
        self.assertTrue(report["restore_verified"])


if __name__ == "__main__":
    unittest.main()
