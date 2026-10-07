"""Constrained Edifier query transport. No setting/firmware opcodes are exposed."""
import asyncio

SERVICE = "4809f301-1a48-11e9-ab14-d663bd873d93"
RX = "48090001-1a48-11e9-ab14-d663bd873d93"
TX = "48090002-1a48-11e9-ab14-d663bd873d93"
QUERIES = {"name": 0xC9, "firmware": 0xC6, "capabilities": 0xD8,
           "volume": 0x66, "preset": 0xD5, "eq": 0x43}


def interpret_state(raw):
    """Separate plausible structure from unverified MR3 units/labels."""
    result = {}
    volume = raw.get("volume", [])
    if len(volume) == 2 and 0 <= volume[1] <= volume[0] and volume[0] > 0:
        result["volume"] = {"current": volume[1], "maximum": volume[0],
                            "interpretation": "shared Edifier layout; MR3 app comparison pending"}
    preset = raw.get("preset", [])
    if preset:
        result["preset"] = {"first_byte": preset[0], "remaining_bytes": preset[1:],
                            "label": None, "interpretation": "MR3 mapping not yet verified"}
        if preset[0] == 2:
            result["preset"].update(label="Custom", interpretation=
                                    "MR3 1.0.7 observation matched to user's white LED")
    eq = bytes(raw.get("eq", []))
    # Only decode the exact structural variant observed on this MR3, not all models.
    if len(eq) >= 39 and eq[:2] == b"\x0c\x09":
        bands = []
        for index in range(9):
            offset = 3 + 4 * index
            record = eq[offset:offset + 4]
            if record[0] != index:
                break
            bands.append({"index": index,
                          "frequency_hz": int.from_bytes(record[1:3], "big"),
                          "gain_code": record[3], "gain_db": (record[3] - 6) * 0.5})
        if len(bands) == 9:
            result["eq"] = {"header_hex": eq[:3].hex(" "), "bands": bands,
                            "interpretation": "record structure inferred; gain scale matched to MR3 app at codes 0, 3, 12",
                            "suffix_hex": eq[39:].hex(" ")}
            if len(eq) >= 43:
                try:
                    result["eq"]["profile_name_candidate"] = eq[43:].decode("utf-8")
                except UnicodeDecodeError:
                    pass
    return result


def query_packet(name):
    # No payload argument and no raw-opcode argument, intentionally.
    packet = bytes((0xAA, 0xEC, QUERIES[name], 0, 0))
    return packet + bytes((sum(packet) & 255,))


class FrameParser:
    def __init__(self):
        self.buffer = bytearray()
        self.invalid_frames = 0

    def feed(self, data):
        self.buffer.extend(data)
        frames = []
        while len(self.buffer) >= 2:
            if self.buffer[0] not in (0xBB, 0xCC) or self.buffer[1] != 0xEC:
                del self.buffer[0]
                continue
            if len(self.buffer) < 5:
                break
            size = int.from_bytes(self.buffer[3:5], "big")
            if size > 4096:
                self.invalid_frames += 1
                del self.buffer[0]
                continue
            total = size + 6
            if len(self.buffer) < total:
                break
            packet = bytes(self.buffer[:total])
            if sum(packet[:-1]) & 255 != packet[-1]:
                self.invalid_frames += 1
                del self.buffer[0]
                continue
            del self.buffer[:total]
            frames.append(packet)
        return frames


class QuerySession:
    def __init__(self, client, report):
        self.client = client
        self.report = report
        self.parser = FrameParser()
        self.pending = None
        self.expected = None
        self.report["queries"] = []
        self.report["notifications_hex"] = []

    def on_notification(self, characteristic, data):
        self.report["notifications_hex"].append(bytes(data).hex(" "))
        for packet in self.parser.feed(data):
            if (packet[0] == 0xBB and packet[2] == self.expected
                    and self.pending is not None and not self.pending.done()):
                self.pending.set_result(packet)

    async def query(self, name):
        packet = query_packet(name)
        record = {"name": name, "request_hex": packet.hex(" ")}
        self.report["queries"].append(record)
        self.expected = QUERIES[name]
        self.pending = asyncio.get_running_loop().create_future()
        try:
            # Write transports a documented getter, never a setting command.
            await self.client.write_gatt_char(TX, packet, response=True)
            response = await asyncio.wait_for(self.pending, timeout=5)
            record.update(status="ok", response_hex=response.hex(" "),
                          payload_hex=response[5:-1].hex(" "))
            return response[5:-1]
        except TimeoutError:
            record["status"] = "timeout"
            return None
        finally:
            if not self.pending.done():
                self.pending.cancel()
            self.pending = None
            self.expected = None
            self.report["invalid_frames"] = self.parser.invalid_frames


async def read_device(client, report, include_state=False):
    if client.services.get_service(SERVICE) is None:
        raise RuntimeError("Observed MR3-candidate service is absent; queries refused")
    session = QuerySession(client, report)
    await client.start_notify(RX, session.on_notification)
    try:
        name = await session.query("name")
        if name is None:
            report["status"] = "identity_query_unanswered"
            return
        report["device_name"] = name.decode("utf-8", errors="replace")
        print(f"Device name: {report['device_name']}", flush=True)
        # The device name is user-changeable. Do not call it immutable model proof.
        report["mr3_name_matches"] = report["device_name"].strip().upper() == "EDIFIER MR3"
        if not report["mr3_name_matches"]:
            report["status"] = "unexpected_device_name"
            return
        firmware = await session.query("firmware")
        if firmware is not None:
            report["firmware_raw"] = list(firmware)
            if len(firmware) == 3:
                report["firmware"] = ".".join(map(str, firmware))
                print(f"Firmware: {report['firmware']}", flush=True)
        capabilities = await session.query("capabilities")
        if capabilities is not None:
            report["capabilities_raw"] = list(capabilities)
        if include_state:
            report["state_raw"] = {}
            for name in ("volume", "preset", "eq"):
                payload = await session.query(name)
                if payload is not None:
                    report["state_raw"][name] = list(payload)
                    print(f"{name}: {payload.hex(' ')}", flush=True)
            report["state_interpretation"] = interpret_state(report["state_raw"])
            summary = report["state_interpretation"]
            if "volume" in summary:
                print(f"Volume (shared-format interpretation): {summary['volume']['current']}/{summary['volume']['maximum']}")
            if "preset" in summary:
                print(f"Mode: {summary['preset']['label'] or 'unmapped'}")
            if "eq" in summary:
                print("EQ: " + ", ".join(f"{b['frequency_hz']} Hz {b['gain_db']:+g} dB"
                                          for b in summary["eq"]["bands"]))
        report["status"] = ("queries_complete" if all(q["status"] == "ok" for q in report["queries"])
                            else "queries_partial")
    finally:
        await client.stop_notify(RX)
