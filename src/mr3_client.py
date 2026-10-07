"""Event-driven MR3 BLE transport. Reads occur on connect or explicit actions only."""
import asyncio
import copy
import json
import logging
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from mr3_protocol import FrameParser, SERVICE, RX, TX, interpret_state
from mr3_pairing import ensure_ble_paired, read_paired_devices
from mr3_paths import DATA_DIR

DISCOVERY_UUIDS = {'0000f300-0000-1000-8000-00805f9b34fb',
                   '0000f600-0000-1000-8000-00805f9b34fb'}


def decode_tuning(payload):
    p = bytes(payload)
    if (len(p) != 7 or p[0] not in range(3) or p[1:3] != b'\x01\x00'
            or p[3] not in range(20,101,5) or p[4] not in range(4)
            or p[5] not in range(5) or p[6] not in (0,1)):
        raise ValueError('지원하지 않는 어쿠스틱 튜닝 형식입니다.')
    return {'cutoff': p[3], 'slope_db': -6*(p[4]+1),
            'space_db': -p[5], 'desktop': bool(p[6])}


def encode_tuning(cutoff, slope_db, space_db, desktop):
    if (cutoff not in range(20,101,5) or slope_db not in (-6,-12,-18,-24)
            or space_db not in (0,-1,-2,-3,-4) or desktop not in (0,1)):
        raise ValueError('어쿠스틱 튜닝 값이 범위를 벗어났습니다.')
    return cutoff, -slope_db//6-1, -space_db, int(desktop)


def frame(opcode, payload=b""):
    data = bytes((0xAA, 0xEC, opcode)) + len(payload).to_bytes(2, "big") + bytes(payload)
    return data + bytes((sum(data) & 255,))


def eq_band_payload(index, gain_db, base=0):
    frequencies = (62, 125, 250, 500, 1000, 2000, 4000, 8000, 16000)
    if type(index) is not int or index not in range(9):
        raise ValueError("Invalid EQ band")
    code = gain_db * 2 + 6
    if not 0 <= code <= 12 or code != int(code):
        raise ValueError("EQ gain must be -3..+3 dB in 0.5 dB steps")
    if base not in (0, 1):
        raise ValueError("Invalid EQ base")
    return bytes((base, index)) + frequencies[index].to_bytes(2, "big") + bytes((int(code),))


class MR3Client:
    def __init__(self, on_event):
        self.on_event = on_event
        self.client = None
        self.parser = FrameParser()
        self.lock = asyncio.Lock()
        self.pending = None
        self.expected = None
        self.state = {"connected": False, "raw": {}}
        self.tx_count = 0
        self.devices = {}

    def emit(self, kind, value):
        self.on_event(kind, copy.deepcopy(value))

    def notification(self, characteristic, data):
        for packet in self.parser.feed(data):
            # CC is a transport acknowledgement, not the getter's state payload.
            if packet[0] != 0xBB:
                if (packet[2] in (0x44, 0x47, 0x67, 0x87, 0xC4, 0xCA)
                        and packet[2] == self.expected and self.pending is not None
                        and not self.pending.done()):
                    self.pending.set_result(packet[5:-1])
                continue
            opcode, payload = packet[2], packet[5:-1]
            self.state["raw"][f"{opcode:02x}"] = list(payload)
            if opcode == 0x66 and len(payload) == 2 and payload[0] == 30 and payload[1] <= 30:
                old = self.state.get("volume")
                self.state["volume"] = payload[1]
                if old is not None and old != payload[1]:
                    self.emit("volume", payload[1])
            elif opcode == 0xC9:
                self.state["name"] = payload.decode("utf-8", errors="replace")
            elif opcode == 0xC6:
                self.state["firmware"] = ".".join(map(str, payload))
            elif opcode == 0xD5 and len(payload) >= 1:
                self.state["mode_code"] = payload[0]
                self.state["room"] = list(payload[1:])
            elif opcode == 0x86 and len(payload) == 2 and payload[0] == 2:
                self.state["beep"] = bool(payload[1])
            elif opcode == 0x43:
                decoded = interpret_state({"eq": list(payload)}).get("eq")
                if decoded:
                    self.state["eq"] = decoded
            if self.pending is not None and not self.pending.done() and opcode == self.expected:
                self.pending.set_result(payload)
            self.emit("state", self.state)

    def disconnected(self, client):
        if client is not self.client:
            return  # A retired Windows session must not clear the new session.
        logging.warning('MR3 active BLE link disconnected by Windows/device')
        self.state["connected"] = False
        if self.pending is not None and not self.pending.done():
            self.pending.set_exception(ConnectionError("MR3 연결이 끊겼습니다."))
        self.emit("state", self.state)

    async def request(self, opcode, payload=b"", expected=None):
        async with self.lock:
            if self.client is None or not self.client.is_connected:
                raise ConnectionError("먼저 MR3에 연결하세요.")
            self.expected = opcode if expected is None else expected
            self.pending = asyncio.get_running_loop().create_future()
            try:
                await self.client.write_gatt_char(TX, frame(opcode, payload), response=True)
                self.tx_count += 1
                return await asyncio.wait_for(self.pending, 5)
            finally:
                if self.pending is not None and not self.pending.done():
                    self.pending.cancel()
                self.pending = None
                self.expected = None

    async def read_pairing(self):
        self.emit('pairing', {'status': 'loading', 'devices': {}})
        try:
            devices = await read_paired_devices()
        except asyncio.CancelledError:
            self.emit('pairing', {'status': 'error', 'devices': {}, 'error': '페어링 확인 취소됨'})
            raise
        except Exception as error:
            logging.warning('Windows BLE pairing inventory failed: %r', error)
            self.emit('pairing', {'status': 'error', 'devices': {}, 'error': str(error) or type(error).__name__})
        else:
            self.emit('pairing', {'status': 'complete', 'devices': devices})

    async def discover(self):
        from bleak import BleakScanner
        rows = {}
        loop = asyncio.get_running_loop()
        pending_update = None

        def publish(status, error=None):
            nonlocal pending_update
            if pending_update:
                pending_update.cancel()
                pending_update = None
            ordered = sorted(rows.values(), key=lambda r: (not r['candidate'], -r['rssi'], r['name']))
            self.emit('discovery', {'status': status, 'rows': ordered, 'error': error,
                                    'time': datetime.now().strftime('%H:%M:%S')})

        def detected(device, adv):
            nonlocal pending_update
            name = adv.local_name or device.name or '이름 없음'
            candidate = ('EDIFIER' in name.upper() or 'MR3' in name.upper()
                         or bool(DISCOVERY_UUIDS.intersection(u.lower() for u in adv.service_uuids)))
            address = device.address.upper()
            previous = rows.get(address)
            # A later advertisement may omit its name/services; retain what this
            # scan already learned, but never carry results from a previous scan.
            if previous:
                if name == '이름 없음': name = previous['name']
                candidate = candidate or previous['candidate']
            self.devices[address] = device
            row = {'address': address, 'name': name, 'rssi': adv.rssi, 'candidate': candidate}
            rows[address] = row
            if row != previous and pending_update is None:
                # Coalesce advertisement bursts; no repeated device queries.
                pending_update = loop.call_later(0.15, publish, 'scanning')

        publish('scanning')
        pairing_task = asyncio.create_task(self.read_pairing())
        try:
            async with BleakScanner(detection_callback=detected):
                await asyncio.sleep(12)
        except asyncio.CancelledError:
            publish('cancelled')
            raise
        except Exception as error:
            publish('error', str(error) or type(error).__name__)
            raise
        else:
            publish('complete')
        finally:
            if pending_update: pending_update.cancel()
            if not pairing_task.done(): pairing_task.cancel()
            await asyncio.gather(pairing_task, return_exceptions=True)
        return list(rows.values())

    async def connect(self, address):
        from bleak import BleakClient, BleakScanner
        from bleak.backends.device import BLEDevice
        address = address.strip().upper()
        if not re.fullmatch(r'(?:[0-9A-F]{2}:){5}[0-9A-F]{2}', address):
            raise ValueError('목록에서 MR3를 선택하거나 올바른 BLE 주소를 입력하세요.')
        await self.disconnect()
        self.state = {"connected": False, "raw": {}}
        self.emit('state', self.state)
        device = self.devices.get(address)
        # Windows accepts a previously known public address without a fresh advertisement.
        # Bleak 3 WinRT extracts only address from BLEDevice; no fabricated advertisement.
        if device is None and sys.platform == 'win32':
            device = BLEDevice(address, '저장된 MR3', None)
        if device is None:
            device = await BleakScanner.find_device_by_address(address, timeout=12)
        if device is None:
            raise ConnectionError('선택한 기기를 찾지 못했습니다. 기기 검색을 다시 실행하세요.')
        if sys.platform == 'win32':
            # Windows keeps the bond; app-state.json only remembers device selection.
            # Pair the selected LE identity, never the classic audio identity.
            await ensure_ble_paired(address, lambda message: self.emit('message', message))
        for attempt, cached in enumerate((False, True), 1):
            logging.info('MR3 connect attempt=%s address=%s cached_services=%s',attempt,address,cached)
            self.emit('message', f'MR3 연결 및 서비스 확인 중… ({attempt}/2)')
            try:
                await self._connect_device(BleakClient, device, address, cached)
                self.devices[address] = device
                return
            except (TimeoutError, OSError) as error:
                logging.warning('Connection attempt %s failed: %r', attempt, error)
                if attempt == 2:
                    raise ConnectionError('Windows에서 MR3의 BLE 서비스에 접근하지 못했습니다. '
                                          '기기 검색 결과와 다른 기기의 연결 상태를 확인하세요. '
                                          '기기가 검색되지 않는 경우에는 숨김 모드일 가능성도 있습니다.') from error
                await asyncio.sleep(1)  # Bounded connection recovery, never volume polling.

    async def _connect_device(self, client_factory, device, address, cached):
        started=time.monotonic()
        stage='Windows GATT connect/service enumeration'
        self.parser = FrameParser()
        self.client = client_factory(device, timeout=15, pair=False, services=[SERVICE],
                                  disconnected_callback=self.disconnected,
                                  winrt={"use_cached_services": cached})
        try:
            await self.client.connect()
            logging.info('MR3 GATT connected/services enumerated in %.3fs',time.monotonic()-started)
            if self.client.services.get_service(SERVICE) is None:
                raise ConnectionError("Windows가 MR3 제어 서비스 목록을 반환하지 않았습니다.")
            stage='notification subscription'
            await self.client.start_notify(RX, self.notification)
            stage='device identity/capabilities'
            await self.request(0xC9)
            await self.request(0xC6)
            caps = await self.request(0xD8)
            if len(caps) < 14 or caps[13] != 30:
                raise ValueError("이 장치의 MR3 설정 형식을 확인하지 못했습니다.")
            self.state["address"] = address
            stage='initial settings read'
            await self.refresh()
            decode_tuning(self.state['raw']['d5'])
            self.state["connected"] = True
            logging.info('MR3 connected and settings read: %s firmware=%s',address,self.state.get('firmware'))
            self.emit('state', self.state)
            self.emit("message", "연결됨 · 변경 알림 수신 중")
        except BaseException as error:
            logging.warning('MR3 connect ended at %s after %.3fs: %r',stage,time.monotonic()-started,error)
            await self.disconnect()
            raise

    async def disconnect(self):
        if self.client is not None:
            client, self.client = self.client, None
            try:
                if client.is_connected:
                    try:
                        await asyncio.wait_for(client.stop_notify(RX), 3)
                    except Exception:
                        logging.debug('Notification cleanup failed', exc_info=True)
                # Even inactive/partially-connected WinRT clients can own GATT handles.
                await client.disconnect()
                logging.info('MR3 GATT connection disposed')
            finally:
                self.state["connected"] = False
                self.emit('state', self.state)
        self.state["connected"] = False
        self.emit("state", self.state)

    async def refresh(self):
        for opcode in (0x66, 0xD5, 0x43, 0x86):
            await self.request(opcode)
        self.emit("state", self.state)

    def backup(self):
        directory = DATA_DIR / "backups"
        directory.mkdir(parents=True,exist_ok=True)
        path = directory / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".json")
        path.write_text(json.dumps(self.state, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    async def set_volume(self, value):
        if type(value) is not int or not 0 <= value <= 30:
            raise ValueError("볼륨 범위는 0~30입니다.")
        await self.request(0x67, bytes((value,)))
        # Setter emits 66 unsolicited; one explicit read verifies the action if needed.
        if self.state.get("volume") != value:
            await self.request(0x66)
        if self.state.get("volume") != value:
            raise RuntimeError("볼륨 변경을 확인하지 못했습니다.")

    async def set_eq(self, gains, base=None):
        if len(gains) != 9:
            raise ValueError("9개 EQ 값이 필요합니다.")
        mode = await self.request(0xD5)
        if mode[0] != 2:
            raise ValueError("사용자 설정 모드를 선택한 뒤 EQ를 적용하세요.")
        original = await self.request(0x43)
        if len(original) < 43 or original[:2] != b"\x0c\x09" or original[2] not in (0, 1):
            raise ValueError("지원하지 않는 EQ 형식입니다.")
        if base is None:
            base = original[2]
        packets = [eq_band_payload(i, g, base) for i, g in enumerate(gains)]
        for i, packet in enumerate(packets):
            if original[3+4*i:6+4*i] != packet[1:4]:
                raise ValueError("EQ 주파수 배열이 예상과 다릅니다.")
        self.backup()
        touched = []
        try:
            for i, packet in enumerate(packets):
                if original[6 + 4*i] != packet[-1] or (i == 0 and base != original[2]):
                    touched.append(i)
                    await self.request(0x44, packet)
            observed = await self.request(0x43)
            expected = bytearray(original)
            expected[2] = base
            for i, packet in enumerate(packets):
                expected[6 + 4*i] = packet[-1]
            if observed != bytes(expected):
                raise RuntimeError("EQ 적용 후 읽은 값이 요청과 다릅니다.")
        except BaseException as error:
            try:
                for i in touched:
                    await self.request(0x44, original[2:3] + original[3 + 4*i:7 + 4*i])
                restored = await self.request(0x43)
                if restored != original:
                    raise RuntimeError("복원 후 값 불일치")
            except BaseException as restore_error:
                raise RuntimeError(f"EQ 자동 복원 확인 실패: {restore_error}. backups 폴더에 원본이 있습니다.") from error
            raise

    async def verified_change(self, setter, payload, getter, expected, restore_payload):
        original = await self.request(getter)
        self.backup()
        try:
            await self.request(setter, payload)
            observed = await self.request(getter)
            if not expected(observed):
                raise RuntimeError("기기에서 읽은 설정이 요청과 다릅니다.")
        except BaseException as error:
            try:
                await self.request(setter, restore_payload(original))
                if await self.request(getter) != original:
                    raise RuntimeError("복원 후 값 불일치")
            except BaseException as restore_error:
                raise RuntimeError(f"변경 실패 및 자동 복원 확인 실패: {restore_error}. backups에 원본이 있습니다.") from error
            raise

    async def set_mode(self, mode):
        if type(mode) is not int or mode not in (0, 1, 2):
            raise ValueError("잘못된 음향 모드입니다.")
        await self.verified_change(0xC4, bytes((mode,)), 0xD5,
                                   lambda p: len(p) == 7 and p[0] == mode,
                                   lambda old: old[:1])

    async def set_room(self, cutoff, slope, space, desktop):
        if cutoff not in range(20, 101, 5) or slope not in range(4) or space not in range(5) or desktop not in (0, 1):
            raise ValueError("음향 보정 값이 범위를 벗어났습니다.")
        original = await self.request(0xD5)
        if len(original) != 7 or original[1:3] != b"\x01\x00":
            raise ValueError("지원하지 않는 음향 보정 형식입니다.")
        target = original[:3] + bytes((cutoff, slope, space, desktop))
        await self.verified_change(0xC4, target, 0xD5, lambda p: p == target, lambda old: old)

    async def set_beep(self, enabled):
        original = await self.request(0x86)
        if len(original) != 2 or original[0] != 2:
            raise ValueError("지원하지 않는 안내음 형식입니다.")
        target = bytes((2, int(bool(enabled))))
        await self.verified_change(0x87, bytes((2, 1, target[1])), 0x86,
                                   lambda p: p == target, lambda old: bytes((2, 1, old[1])))

    async def rename(self, name):
        encoded = name.strip().encode('utf-8')
        # MR3 capability B3=5: official ConneX limit is 30 UTF-8 bytes.
        if not 1 <= len(encoded) <= 30 or any(ord(ch) < 32 for ch in name):
            raise ValueError("기기 이름은 UTF-8 기준 1~30바이트여야 합니다.")
        await self.verified_change(0xCA, encoded, 0xC9, lambda p: p == encoded, lambda old: old)

    async def rename_eq(self, name):
        encoded = name.strip().encode('utf-8')
        if not 1 <= len(encoded) <= 30 or any(ord(ch) < 32 for ch in name):
            raise ValueError("EQ 이름은 UTF-8 기준 1~30바이트여야 합니다.")
        original = await self.request(0x43)
        if len(original) < 43:
            raise ValueError("EQ 이름 형식을 확인하지 못했습니다.")
        target = original[:43] + encoded
        await self.verified_change(0x47, target[39:], 0x43,
                                   lambda p: p == target, lambda old: old[39:])
