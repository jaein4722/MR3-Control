"""Windows BLE bonding only; never pair the classic Bluetooth audio device."""
import asyncio
import logging
import re


async def read_paired_devices():
    """Read Windows' local LE bond inventory; no scan, GATT connection or pairing."""
    from winrt.windows.devices.bluetooth import BluetoothLEDevice
    from winrt.windows.devices.enumeration import DeviceInformation
    selector = BluetoothLEDevice.get_device_selector_from_pairing_state(True)
    async with asyncio.timeout(8):
        devices = await DeviceInformation.find_all_async_aqs_filter(selector)
    paired = {}
    for info in devices:
        # Windows LE AEP identity ends in adapter-MAC / remote-MAC.
        addresses = re.findall(r'(?:[0-9a-f]{2}:){5}[0-9a-f]{2}', info.id, re.I)
        if not addresses:
            raise ValueError('Windows BLE 주소 형식을 확인하지 못했습니다.')
        address = addresses[-1].upper()
        paired[address] = {'address': address, 'name': info.name or '이름 없음'}
    return paired


class PairingError(ConnectionError):
    pass


async def ensure_ble_paired(address, progress, timeout=60):
    """Check the OS bond on each connection; create it once when absent.

    Custom CONFIRM_ONLY avoids a separate confirmation window. Protection-level
    negotiation matches Bleak 3's Windows pairing implementation. Cancellation
    releases the handler/device but never deletes a bond that Windows completed.
    """
    progress('BLE 페어링 기록 확인 중…')
    try:
        async with asyncio.timeout(timeout):
            return await _ensure_paired(address, progress)
    except TimeoutError as error:
        raise PairingError('BLE 페어링 응답 시간이 초과됐습니다. 기기의 검색 가능 상태와 다른 앱의 연결을 확인한 뒤 다시 연결하세요.') from error
    except PairingError:
        raise
    except Exception as error:
        raise PairingError(f'BLE 페어링 확인/등록 실패: {error}') from error


async def _ensure_paired(address, progress):
    from winrt.windows.devices.bluetooth import BluetoothLEDevice
    from winrt.windows.devices.enumeration import (
        DeviceInformation, DevicePairingKinds, DevicePairingProtectionLevel,
        DevicePairingResultStatus,
    )
    device = await BluetoothLEDevice.from_bluetooth_address_async(int(address.replace(':', ''), 16))
    if device is None:
        raise PairingError('Windows가 BLE 기기에 접근하지 못했습니다. Bluetooth 상태를 확인하세요.')
    try:
        device_id = device.device_information.id
        info = await DeviceInformation.create_from_id_async(device_id)
        if info.pairing.is_paired:
            logging.info('MR3 existing Windows BLE bond: %s', address)
            progress('저장된 BLE 페어링 확인됨 · 제어 연결 준비 중…')
            return False
        if not info.pairing.can_pair:
            raise PairingError('이 기기는 현재 BLE 페어링을 허용하지 않습니다. 기기 상태를 확인한 뒤 다시 연결하세요.')
        progress('최초 BLE 페어링 중… · 최대 60초')
        custom = info.pairing.custom
        token = custom.add_pairing_requested(lambda sender, args: args.accept())
        try:
            for level in (DevicePairingProtectionLevel.ENCRYPTION_AND_AUTHENTICATION,
                          DevicePairingProtectionLevel.ENCRYPTION):
                result = await custom.pair_with_protection_level_async(DevicePairingKinds.CONFIRM_ONLY, level)
                if result.status != DevicePairingResultStatus.PROTECTION_LEVEL_COULD_NOT_BE_MET:
                    break
            else:
                result = await custom.pair_async(DevicePairingKinds.CONFIRM_ONLY)
        finally:
            custom.remove_pairing_requested(token)
        logging.info('MR3 BLE pairing result: %s address=%s', result.status.name, address)
        if result.status not in (DevicePairingResultStatus.PAIRED, DevicePairingResultStatus.ALREADY_PAIRED):
            raise PairingError(f'BLE 페어링 실패 ({result.status.name}). 기기의 검색 가능 상태와 다른 앱의 연결을 확인하세요.')
        info = await DeviceInformation.create_from_id_async(device_id)
        if not info.pairing.is_paired:
            raise PairingError('Windows에서 BLE 페어링 기록 저장을 확인하지 못했습니다. 다시 연결하세요.')
        progress('BLE 페어링 완료 · 제어 연결 준비 중…')
        return True
    finally:
        device.close()
