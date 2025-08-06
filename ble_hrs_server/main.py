import asyncio
import traceback
from typing import TYPE_CHECKING

from .conf import config
from .conn import BLEHRSConnection, scan_hrs_supported_devices
from .log import logger

if TYPE_CHECKING:
    from cookit import Signal


async def sig_exc_handler(_: "Signal", e: Exception):
    logger.error("Some handler raised an exception")
    traceback.print_exception(e)


async def select_device():
    logger.info("Scanning for devices with Heart Rate Service (HRS) supported")
    devices = await scan_hrs_supported_devices(config.device_discover_delay)
    if not devices:
        logger.error("No devices found")
        return None

    logger.success("Supported devices found:")
    for i, (device, adv) in enumerate(devices, 1):
        logger.success(
            f"{i}: {adv.local_name or device.name or 'Unknown'} ({device.address})",
        )

    if len(devices) == 1:
        logger.info("Only one device found, automatically selecting it")
        return devices[0][0].address

    while True:
        logger.info("Select a device by number: ")
        choice = input("INPUT> ")
        if not choice.isdigit():
            logger.error("Please enter a valid number")
            continue

        choice = int(choice) - 1
        if 0 <= choice < len(devices):
            return devices[choice][0].address
        logger.error("Invalid choice")


async def construct_conn(address: str) -> BLEHRSConnection:
    conn = BLEHRSConnection(
        address,
        retry_interval=config.conn_retry_interval,
        sig_exc_handler=sig_exc_handler,
    )

    @conn.connecting_sig.connect
    async def _(_: BLEHRSConnection):
        logger.info("Connecting to device")

    @conn.connect_failed_sig.connect
    async def _(_: BLEHRSConnection, e: Exception):
        logger.error(f"Connect failed: {type(e).__name__}: {e}")
        logger.opt(exception=e).debug("Stacktrace")

    @conn.connection_lost_sig.connect
    async def _(_: BLEHRSConnection):
        logger.error("Connection lost")

    @conn.connected_sig.connect
    async def _(_: BLEHRSConnection):
        logger.info("Device connected")

    @conn.prepared_sig.connect
    async def _(_: BLEHRSConnection):
        logger.success("Started receiving data")

    # @conn.data_received_sig.connect
    # async def _(_: BLEHRSConnection, data: HRMData):
    #     logger.debug(f"Received: {data}")

    return conn


async def construct_available_conn(address: str) -> BLEHRSConnection | None:
    conn = await construct_conn(address)

    first_conn_ok_fut = asyncio.Future[bool]()

    @conn.prepared_sig.connect
    async def _prepared(_: BLEHRSConnection):
        first_conn_ok_fut.set_result(True)

    @conn.connect_failed_sig.connect
    async def _failed(_: BLEHRSConnection, __: Exception):
        first_conn_ok_fut.set_result(False)

    asyncio.create_task(conn.start())

    if await first_conn_ok_fut:
        conn.prepared_sig.slots.remove(_prepared)
        conn.connect_failed_sig.slots.remove(_failed)
        return conn

    await conn.shutdown()
    return None


async def init():
    conn = None
    if config.last_device_address:
        address = config.last_device_address
        logger.info(f"Using last connected device: {address}")
        conn = await construct_available_conn(address)
        if conn:
            return conn
        logger.error("Cannot connect to last used device, please re-select one")

    while True:
        address = await select_device()
        if not address:
            return None
        conn = await construct_available_conn(address)
        if conn:
            config.last_device_address = address
            config.save()
            break
        logger.error("Cannot connect to this device, please re-select one")

    return conn
