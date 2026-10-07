import asyncio
import unittest
from mr3_protocol import FrameParser, QuerySession, query_packet, interpret_state


class ProtocolTests(unittest.TestCase):
    def test_documented_name_request(self):
        self.assertEqual(query_packet("name").hex(), "aaecc900005f")

    def test_no_setter_or_raw_opcode(self):
        for name in ("set_volume", "reset", "firmware_update", 0xCA):
            with self.assertRaises(KeyError):
                query_packet(name)

    def test_fragmented_and_concatenated_replies(self):
        # Published M60 name response; framing only, not a model assumption.
        packet = bytes.fromhex("bb ec c9 00 0b 45 44 49 46 49 45 52 20 4d 36 30 46")
        parser = FrameParser()
        self.assertEqual(parser.feed(packet[:4]), [])
        self.assertEqual(parser.feed(packet[4:9]), [])
        self.assertEqual(parser.feed(packet[9:] + packet), [packet, packet])

    def test_corrupt_response_is_rejected_and_resynchronizes(self):
        valid = bytes.fromhex("bb ec c6 00 03 02 04 01 77")
        parser = FrameParser()
        self.assertEqual(parser.feed(b"noise" + valid[:-1] + b"\x00" + valid), [valid])
        self.assertEqual(parser.invalid_frames, 1)

    def test_oversized_length_is_rejected(self):
        parser = FrameParser()
        self.assertEqual(parser.feed(bytes.fromhex("bb ec c9 ff ff")), [])
        self.assertEqual(parser.invalid_frames, 1)

    def test_actual_mr3_identity_reply(self):
        packet = bytes.fromhex("bb ec c9 00 0b 45 44 49 46 49 45 52 20 4d 52 33 65")
        self.assertEqual(FrameParser().feed(packet)[0][5:-1].decode(), "EDIFIER MR3")

    def test_mr3_eq_structure_and_app_verified_gain_scale(self):
        payload = bytes.fromhex("0c 09 00 00 00 3e 0c 01 00 7d 00 02 00 fa 03 03 01 f4 06 04 03 e8 06 05 07 d0 06 06 0f a0 06 07 1f 40 06 08 3e 80 06")
        result = interpret_state({"volume": [30, 13], "preset": [2, 1, 0, 45, 3, 3, 1], "eq": payload})
        self.assertEqual(result["volume"]["current"], 13)
        self.assertEqual(result["volume"]["maximum"], 30)
        self.assertEqual(result["preset"]["label"], "Custom")
        self.assertIsNone(interpret_state({"preset": [1]})["preset"]["label"])
        self.assertEqual([b["frequency_hz"] for b in result["eq"]["bands"]],
                         [62, 125, 250, 500, 1000, 2000, 4000, 8000, 16000])
        self.assertEqual([b["gain_db"] for b in result["eq"]["bands"]],
                         [3, -3, -1.5, 0, 0, 0, 0, 0, 0])
        self.assertNotIn("eq", interpret_state({"eq": payload[:-1]}))
        wrong_index = bytearray(payload)
        wrong_index[3] = 5
        self.assertNotIn("eq", interpret_state({"eq": wrong_index}))


class QueryTests(unittest.IsolatedAsyncioTestCase):
    async def test_ack_and_unrelated_reply_cannot_satisfy_query(self):
        report = {}
        class Client:
            async def write_gatt_char(client_self, uuid, packet, response):
                def frame(header, opcode, payload):
                    data = bytes([header, 0xEC, opcode, 0, len(payload)]) + payload
                    return data + bytes([sum(data) & 255])
                session.on_notification(None, frame(0xCC, 0xC9, b"\x01"))
                session.on_notification(None, frame(0xBB, 0xC6, b"\x01\x00\x07"))
                self.assertFalse(session.pending.done())
                valid = frame(0xBB, 0xC9, b"EDIFIER MR3")
                session.on_notification(None, valid[:8])
                self.assertFalse(session.pending.done())
                session.on_notification(None, valid[8:])
        session = QuerySession(Client(), report)
        self.assertEqual(await session.query("name"), b"EDIFIER MR3")
        self.assertEqual(report["queries"][0]["status"], "ok")
        self.assertIsNone(session.pending)


if __name__ == "__main__":
    unittest.main()
