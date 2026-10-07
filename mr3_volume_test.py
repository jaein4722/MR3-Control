"""One-step volume write/read-back/restore test; no periodic polling."""
import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / ".deps"))
from mr3_protocol import QuerySession, SERVICE, RX, TX


def volume_packet(value):
    if type(value) is not int or not 0 <= value <= 30:
        raise ValueError("MR3 volume must be an integer from 0 to 30")
    data = bytes((0xAA, 0xEC, 0x67, 0, 1, value))
    return data + bytes((sum(data) & 255,))


def decode_volume(data):
    if data is None or len(data) != 2 or data[0] != 30 or data[1] > 30:
        raise RuntimeError("Unexpected MR3 volume response")
    return data[1]


async def volume_roundtrip(session, report, save):
    original = decode_volume(await session.query("volume"))
    report["original_volume"] = original
    save()
    if original == 0:
        report["status"] = "skipped_already_muted"
        return
    target = original - 1
    report["temporary_volume"] = target
    report["writes"] = []
    async def write(value, purpose):
        packet = volume_packet(value)
        record = {"purpose": purpose, "value": value, "hex": packet.hex(" "),
                  "status": "attempting"}
        report["writes"].append(record)
        save()  # Retain original value and attempted command even if the process fails.
        await session.client.write_gatt_char(TX, packet, response=True)
        record["status"] = "gatt_write_completed"
        await asyncio.sleep(0.25)  # One settling delay, not a polling loop.
    try:
        print(f"Original {original}/30; testing {target}/30...", flush=True)
        await write(target, "temporary_lower")
        observed = decode_volume(await session.query("volume"))
        report["temporary_readback"] = observed
        report["change_verified"] = observed == target
        print(f"After write: {observed}/30", flush=True)
    finally:
        try:
            await write(original, "restore_original")
            restored = decode_volume(await session.query("volume"))
            report["restored_readback"] = restored
            report["restore_verified"] = restored == original
            print(f"Restored read-back: {restored}/30 (expected {original}/30)", flush=True)
        except BaseException as error:
            report["restore_verified"] = False
            report["restore_error"] = f"{type(error).__name__}: {error}"
            raise
        finally:
            save()
    report["status"] = ("write_and_restore_verified" if report.get("change_verified")
                        and report.get("restore_verified") else "verification_failed")


async def run(address, report, save):
    from bleak import BleakClient, BleakScanner
    print("Finding MR3...", flush=True)
    target = await BleakScanner.find_device_by_address(address, timeout=30)
    if target is None:
        report["status"] = "not_found"
        return
    async with BleakClient(target, timeout=25, pair=False,
                           winrt={"use_cached_services": False}) as client:
        if client.services.get_service(SERVICE) is None:
            raise RuntimeError("MR3 service missing; no settings written")
        session = QuerySession(client, report)
        await client.start_notify(RX, session.on_notification)
        try:
            name = await session.query("name")
            firmware = await session.query("firmware")
            if name != b"EDIFIER MR3" or firmware != bytes((1, 0, 7)):
                raise RuntimeError("Expected MR3 1.0.7 identity not confirmed; no settings written")
            report["device_name"] = name.decode()
            report["firmware"] = "1.0.7"
            await volume_roundtrip(session, report, save)
        finally:
            if client.is_connected:
                await client.stop_notify(RX)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--address", required=True)
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    path = ROOT / "diagnostics" / f"{now:%Y%m%dT%H%M%S%fZ}-volume-write-test.json"
    report = {"started_utc": now.isoformat(), "address": args.address, "status": "started",
              "periodic_polling": False}
    def save():
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        asyncio.run(run(args.address, report, save))
    except (Exception, KeyboardInterrupt) as error:
        report.update(status="error", error=f"{type(error).__name__}: {error}")
        print(report["error"], flush=True)
    finally:
        save()
    print(f"Result: {report['status']}\nReport: {path}", flush=True)
    return 0 if report["status"] == "write_and_restore_verified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
