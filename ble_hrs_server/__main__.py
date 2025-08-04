import asyncio
import traceback
from typing import TYPE_CHECKING

from bleak import BleakScanner

from .conf import config
from .conn import HRSDeviceConnection
from .data import HRS_UUID, HRMData

if TYPE_CHECKING:
    from cookit import Signal


async def scan_supported_devices(delay: float = 2.0):
    async with BleakScanner(service_uuids=[HRS_UUID]) as scanner:
        await asyncio.sleep(delay)
    return list(scanner.discovered_devices_and_advertisement_data.values())


async def select_device():
    print("Scanning for devices with Heart Rate Service (HRS) supported...")
    devices = await scan_supported_devices(config.device_discover_delay)
    if not devices:
        print("No devices found.")
        return None

    print("Supported devices found:")
    for i, (device, adv) in enumerate(devices, 1):
        print(f"{i}: {adv.local_name or device.name or 'Unknown'} ({device.address})")

    if len(devices) == 1:
        print("Only one device found, automatically selecting it.")
        return devices[0][0].address

    while True:
        choice = input("Select a device by number: ")
        if not choice.isdigit():
            print("Please enter a valid number.")
            continue

        choice = int(choice) - 1
        if 0 <= choice < len(devices):
            return devices[choice][0].address
        print("Invalid choice.")


async def main():
    if config.last_device_address:
        device = config.last_device_address
        print(f"Using last connected device: {device}")
    else:
        device = await select_device()
        if not device:
            return
        config.last_device_address = device
        config.save()

    async def sig_exc_handler(_: "Signal", e: Exception):
        print("Some handler raised an exception")
        traceback.print_exception(e)

    conn = HRSDeviceConnection(
        device,
        retry_interval=config.conn_retry_interval,
        sig_exc_handler=sig_exc_handler,
    )

    @conn.connecting_sig.connect
    async def _(_: HRSDeviceConnection):
        print("Connecting to device...")

    @conn.connect_failed_sig.connect
    async def _(_: HRSDeviceConnection, e: Exception):
        print(f"Connect failed, will retry in {config.conn_retry_interval} seconds")
        print(f"{type(e).__name__}: {e}")

    @conn.connection_lost_sig.connect
    async def _(_: HRSDeviceConnection):
        print(
            f"Connection lost, will reconnect in {config.conn_retry_interval} seconds",
        )

    @conn.connected_sig.connect
    async def _(_: HRSDeviceConnection):
        print("Device connected")

    @conn.started_notify_sig.connect
    async def _(_: HRSDeviceConnection):
        print("Started to receive data")

    @conn.data_received_sig.connect
    async def _(_: HRSDeviceConnection, data: HRMData):
        print(
            f"Received heart rate {data.heart_rate} bpm"
            f", sensor contact status: {data.sensor_contact}",
        )

    await conn.connect()


asyncio.run(main())
