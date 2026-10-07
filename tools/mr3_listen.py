"""Observe unsolicited MR3 notifications. Sends no application query or setter."""
import argparse
import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".deps"))
from mr3_protocol import FrameParser, SERVICE, RX


async def listen(address, duration, report):
    from bleak import BleakClient, BleakScanner
    print("Finding the previously identified MR3...", flush=True)
    target = await BleakScanner.find_device_by_address(address, timeout=30)
    if target is None:
        report["status"] = "not_found"
        return 2
    disconnected = asyncio.Event()
    parser = FrameParser()
    start = time.perf_counter()
    def receive(characteristic, data):
        elapsed = time.perf_counter() - start
        report["notifications"].append({"elapsed_seconds": round(elapsed, 6),
                                         "utc": datetime.now(timezone.utc).isoformat(),
                                         "hex": bytes(data).hex(" ")})
        for frame in parser.feed(data):
            payload = frame[5:-1]
            item = {"elapsed_seconds": round(elapsed, 6),
                    "opcode": f"{frame[2]:02x}", "hex": frame.hex(" "),
                    "payload": list(payload)}
            if frame[2] == 0x66 and len(payload) == 2 and payload[1] <= payload[0]:
                item["volume"] = {"maximum": payload[0], "current": payload[1]}
            report["frames"].append(item)
            print(f"{elapsed:7.3f}s opcode={item['opcode']} payload={payload.hex(' ')}"
                  + (f" volume={payload[1]}/{payload[0]}" if "volume" in item else ""), flush=True)
    async with BleakClient(target, pair=False, timeout=25,
                           disconnected_callback=lambda _: disconnected.set(),
                           winrt={"use_cached_services": False}) as client:
        if client.services.get_service(SERVICE) is None:
            raise RuntimeError("Expected MR3 service missing; not subscribing")
        start = time.perf_counter()
        await client.start_notify(RX, receive)
        report["subscribed_utc"] = datetime.now(timezone.utc).isoformat()
        print(f"LISTENING for {duration}s. Turn the volume knob. No queries are sent.", flush=True)
        try:
            try:
                await asyncio.wait_for(disconnected.wait(), timeout=duration)
                report["status"] = "disconnected_early"
            except TimeoutError:
                report["status"] = "capture_complete"
        finally:
            report["listening_seconds"] = round(time.perf_counter() - start, 3)
            report["invalid_frames"] = parser.invalid_frames
            if client.is_connected:
                await client.stop_notify(RX)
    return 0 if report["status"] == "capture_complete" else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--address", required=True)
    parser.add_argument("--duration", type=int, choices=range(1, 61), default=30, metavar="1..60")
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    output = ROOT / "diagnostics" / f"{now:%Y%m%dT%H%M%S%fZ}-listen.json"
    report = {"started_utc": now.isoformat(), "address": args.address,
              "application_queries_sent": 0, "setting_commands_sent": 0,
              "notifications": [], "frames": [], "status": "started"}
    try:
        code = asyncio.run(listen(args.address, args.duration, report))
    except KeyboardInterrupt:
        report["status"] = "cancelled"
        code = 130
    except Exception as error:
        report.update(status="error", error=f"{type(error).__name__}: {error}")
        print(report["error"], flush=True)
        code = 1
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Captured {len(report['notifications'])} notifications, {len(report['frames'])} valid frames.")
    print(f"Report: {output}", flush=True)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
