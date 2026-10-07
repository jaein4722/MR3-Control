"""Discover Edifier BLE candidates and inspect GATT structure without control writes."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if (ROOT / ".deps").is_dir():
    sys.path.insert(0, str(ROOT / ".deps"))

CONNEX_SEARCH_UUID = "0000f600-0000-1000-8000-00805f9b34fb"
# Observed on this user's EDIFIER BLE advertisement; MR3 model still unverified.
OBSERVED_EDIFIER_UUID = "0000f300-0000-1000-8000-00805f9b34fb"


def is_candidate(device, advertisement):
    name = " ".join((device.name or "", advertisement.local_name or "")).upper()
    services = [uuid.lower() for uuid in advertisement.service_uuids]
    return ("EDIFIER" in name or "MR3" in name
            or CONNEX_SEARCH_UUID in services or OBSERVED_EDIFIER_UUID in services)


def describe(device, advertisement):
    return {
        "name": advertisement.local_name or device.name,
        "address": device.address,
        "rssi_dbm": advertisement.rssi,
        "advertised_services": advertisement.service_uuids,
        "identification": "candidate only; model not verified",
    }


async def diagnose(args, report):
    from bleak import BleakClient, BleakScanner

    print(f"Scanning for Edifier BLE advertisements ({args.seconds:g}s)...", flush=True)
    found = await BleakScanner.discover(timeout=args.seconds, return_adv=True)
    candidates = [(d, a) for d, a in found.values() if is_candidate(d, a)]
    report["nearby_device_count"] = len(found)
    report["candidates"] = [describe(d, a) for d, a in candidates]
    # Unrelated device names, addresses and payloads are deliberately not saved.
    for item in report["candidates"]:
        print(f"Candidate: {item['name'] or '(unnamed)'} | {item['address']} | {item['rssi_dbm']} dBm")
    if not candidates:
        print("No Edifier candidate found. Wake MR3, close ConneX and enable discovery, then retry.")
    if args.command == "scan":
        report["status"] = "candidates_found" if candidates else "no_candidates"
        return 0 if candidates else 2

    matches = [d for d, a in candidates if d.address.upper() == args.address.upper()]
    if len(matches) != 1:
        report["status"] = "target_not_found"
        print("Target must be an Edifier candidate visible in this scan. No connection attempted.")
        return 2
    target = matches[0]
    report["target"] = target.address
    report["services"] = []
    print("Connecting to selected candidate...", flush=True)
    async with asyncio.timeout(args.timeout):
        async with BleakClient(target, timeout=args.timeout, pair=False,
                               winrt={"use_cached_services": False}) as client:
            for service in client.services:
                record = {"uuid": service.uuid, "description": service.description,
                          "characteristics": []}
                for characteristic in service.characteristics:
                    record["characteristics"].append({
                        "uuid": characteristic.uuid,
                        "handle": characteristic.handle,
                        "properties": list(characteristic.properties),
                        "descriptors": [{"uuid": d.uuid, "handle": d.handle}
                                        for d in characteristic.descriptors],
                    })
                report["services"].append(record)
                print(f"Service: {service.uuid} ({len(record['characteristics'])} characteristics)")
            if args.command in ("identify", "status"):
                from mr3_protocol import read_device
                await read_device(client, report, include_state=args.command == "status")
                return 0 if report["status"] == "queries_complete" else 2
    report["status"] = "services_found" if report["services"] else "no_services"
    return 0 if report["services"] else 2


def positive_duration(value):
    number = float(value)
    if not 0 < number <= 60:
        raise argparse.ArgumentTypeError("Duration must be greater than 0 and at most 60 seconds")
    return number


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("scan", "inspect", "identify", "status"))
    parser.add_argument("--address", help="An Edifier candidate address, required except for scan")
    parser.add_argument("--seconds", type=positive_duration, default=15)
    parser.add_argument("--timeout", type=positive_duration, default=30)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.command != "scan" and not args.address:
        parser.error(f"{args.command} requires --address")
    now = datetime.now(timezone.utc)
    report = {"timestamp_utc": now.isoformat(), "command": args.command,
              "settings_changed": False, "status": "started"}
    output = args.output or ROOT / "diagnostics" / f"{now:%Y%m%dT%H%M%S%fZ}-{args.command}.json"
    try:
        code = asyncio.run(diagnose(args, report))
    except KeyboardInterrupt:
        report["status"] = "cancelled"
        code = 130
    except Exception as error:
        report["status"] = "error"
        report["error"] = f"{type(error).__name__}: {error}"
        print(report["error"], file=sys.stderr)
        code = 1
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Report: {output}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
