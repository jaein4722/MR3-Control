"""Test one MR3 EQ band and restore its original response; no periodic polling."""
import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".deps"))
from mr3_protocol import QuerySession, SERVICE, RX, TX


def validate_eq(payload):
    if payload is None or len(payload) < 39 or payload[:3] != bytes((12, 9, 0)):
        raise ValueError("Unexpected MR3 EQ header/length")
    frequencies = (62, 125, 250, 500, 1000, 2000, 4000, 8000, 16000)
    for i, freq in enumerate(frequencies):
        record = payload[3 + 4*i:7 + 4*i]
        if record[0] != i or int.from_bytes(record[1:3], "big") != freq or record[3] > 12:
            raise ValueError("Unexpected MR3 EQ record")
    return payload


def band_packet(record):
    if len(record) != 4 or record[:3] != bytes((0, 0, 62)) or not 0 <= record[3] <= 12:
        raise ValueError("Only 62 Hz band with gain codes 0..12 is permitted")
    # MR3 adds a selector byte before the four-byte band record.
    # Omitting it shifts frequency bytes; observed and recovered in hardware testing.
    data = bytes((0xAA, 0xEC, 0x44, 0, 5, 0)) + record
    return data + bytes((sum(data) & 255,))


async def eq_roundtrip(session, report, save):
    preset = await session.query("preset")
    if not preset or preset[0] != 2:
        raise RuntimeError("Custom mode required; no mode change will be attempted")
    original = validate_eq(await session.query("eq"))
    report["original_preset_hex"] = preset.hex(" ")
    report["original_eq_hex"] = original.hex(" ")
    original_record = original[3:7]
    report["original_gain_db"] = (original_record[3] - 6) * 0.5
    save()
    if original_record[3] == 0:
        report["status"] = "skipped_at_minimum_gain"
        return
    target_record = original_record[:3] + bytes((original_record[3] - 1,))
    expected = original[:3] + target_record + original[7:]
    report["temporary_gain_db"] = (target_record[3] - 6) * 0.5
    report["writes"] = []
    async def write(record, purpose):
        packet = band_packet(record)
        item = {"purpose": purpose, "hex": packet.hex(" "), "status": "attempting"}
        report["writes"].append(item)
        save()
        await session.client.write_gatt_char(TX, packet, response=True)
        item["status"] = "gatt_write_completed"
        await asyncio.sleep(0.3)
    try:
        print(f"62 Hz: {report['original_gain_db']:+g} -> {report['temporary_gain_db']:+g} dB", flush=True)
        await write(target_record, "temporary_lower_band_0")
        observed = await session.query("eq")
        report["temporary_eq_hex"] = observed.hex(" ") if observed is not None else None
        report["change_verified"] = observed == expected
        report["changed_byte_offsets"] = ([i for i, (a, b) in enumerate(zip(original, observed)) if a != b]
                                          if observed is not None else None)
        print(f"Exact expected EQ change: {report['change_verified']}", flush=True)
    finally:
        try:
            await write(original_record, "restore_original_band_0")
            restored = await session.query("eq")
            restored_preset = await session.query("preset")
            report["restored_eq_hex"] = restored.hex(" ") if restored is not None else None
            report["restored_preset_hex"] = restored_preset.hex(" ") if restored_preset is not None else None
            report["restore_verified"] = restored == original and restored_preset == preset
            print(f"Full EQ and mode restored byte-for-byte: {report['restore_verified']}", flush=True)
        except BaseException as error:
            report.update(restore_verified=False, restore_error=f"{type(error).__name__}: {error}")
            raise
        finally:
            save()
    report["status"] = ("write_and_restore_verified" if report.get("change_verified") and report.get("restore_verified")
                        else "verification_failed")


async def run(address, report, save, recovery=None):
    from bleak import BleakClient, BleakScanner
    print("Finding MR3...", flush=True)
    target = await BleakScanner.find_device_by_address(address, timeout=30)
    if target is None:
        report["status"] = "not_found"
        return
    async with BleakClient(target, timeout=25, pair=False,
                           winrt={"use_cached_services": False}) as client:
        if client.services.get_service(SERVICE) is None:
            raise RuntimeError("MR3 service missing")
        session = QuerySession(client, report)
        await client.start_notify(RX, session.on_notification)
        try:
            if await session.query("name") != b"EDIFIER MR3" or await session.query("firmware") != bytes((1, 0, 7)):
                raise RuntimeError("Expected MR3 1.0.7 identity not confirmed")
            if recovery is not None:
                original = validate_eq(bytes.fromhex(recovery['original_eq_hex']))
                preset = bytes.fromhex(recovery['original_preset_hex'])
                report['original_eq_hex'] = original.hex(' ')
                report['original_preset_hex'] = preset.hex(' ')
                before = await session.query('eq')
                report['before_recovery_eq_hex'] = before.hex(' ') if before else None
                packet = band_packet(original[3:7])
                report['recovery_request_hex'] = packet.hex(' ')
                save()
                await client.write_gatt_char(TX, packet, response=True)
                await asyncio.sleep(0.3)
                after = await session.query('eq')
                mode = await session.query('preset')
                report['restored_eq_hex'] = after.hex(' ') if after else None
                report['restored_preset_hex'] = mode.hex(' ') if mode else None
                report['restore_verified'] = after == original and mode == preset
                report['status'] = 'recovery_verified' if report['restore_verified'] else 'recovery_failed'
                print(f"Full original EQ/mode recovery: {report['restore_verified']}", flush=True)
            else:
                await eq_roundtrip(session, report, save)
        finally:
            if client.is_connected:
                await client.stop_notify(RX)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--address", required=True)
    parser.add_argument("--recover-from", type=Path, help="Restore band 0 from an earlier test's saved original")
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    path = ROOT / "diagnostics" / f"{now:%Y%m%dT%H%M%S%fZ}-eq-write-test.json"
    report = {"started_utc": now.isoformat(), "address": args.address,
              "status": "started", "periodic_polling": False}
    def save():
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        recovery = json.loads(args.recover_from.read_text(encoding='utf-8')) if args.recover_from else None
        if recovery is not None and recovery.get('address', '').upper() != args.address.upper():
            raise ValueError('Recovery address does not match the saved original')
        asyncio.run(run(args.address, report, save, recovery))
    except (Exception, KeyboardInterrupt) as error:
        report.update(status="error", error=f"{type(error).__name__}: {error}")
        print(report["error"], flush=True)
    finally:
        save()
    print(f"Result: {report['status']}\nReport: {path}", flush=True)
    return 0 if report["status"] in ("write_and_restore_verified", "recovery_verified") else 1


if __name__ == "__main__":
    raise SystemExit(main())
