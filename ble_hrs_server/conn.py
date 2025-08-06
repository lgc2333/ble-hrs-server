import asyncio
import time
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Callable, Coroutine
from typing import Any, NamedTuple, Self, override

from bleak import BleakClient, BleakScanner
from cookit import Signal, safe_exc_handler

type Co[T] = Coroutine[Any, Any, T]


class BaseBLEConnection(ABC):
    def __init__(
        self,
        address: str,
        retry_interval: float = 1.0,
        sig_exc_handler: Callable[[Signal, Exception], Co[Any]] = safe_exc_handler,
        **client_kw,
    ) -> None:
        self.address = address
        self.retry_interval = retry_interval
        self.client_kw = client_kw

        self.client: BleakClient | None = None

        self._disconnected_event = asyncio.Event()
        self._reconnect_task: asyncio.Task | None = None

        self.connect_failed_sig = Signal[[Self, Exception], Any, Any](sig_exc_handler)
        self.connection_lost_sig = Signal[[Self], Any, Any](sig_exc_handler)
        self.connecting_sig = Signal[[Self], Any, Any](sig_exc_handler)
        self.connected_sig = Signal[[Self], Any, Any](sig_exc_handler)
        self.prepared_sig = Signal[[Self], Any, Any](sig_exc_handler)
        self.starting_sig = Signal[[Self], Any, Any](sig_exc_handler)
        self.shutting_down_sig = Signal[[Self], Any, Any](sig_exc_handler)

    @property
    def started(self) -> bool:
        return bool(self._reconnect_task)

    @property
    def connected(self) -> bool:
        return (self.client is not None) and self.client.is_connected

    def _disconnected_callback(self, _client: BleakClient):
        self._disconnected_event.set()
        self._disconnected_event.clear()

    def new_client(self) -> BleakClient:
        return BleakClient(
            self.address,
            disconnected_callback=self._disconnected_callback,
            **self.client_kw,
        )

    @abstractmethod
    async def _prepare(self, client: BleakClient): ...

    async def _reconnect_task_func(self):
        while True:
            if self.client and self.client.is_connected:
                await self.client.disconnect()
            self.client = self.new_client()

            if not self.client.is_connected:
                self.connecting_sig.task_gather(self)
                try:
                    await self.client.connect()
                except Exception as e:
                    self.connect_failed_sig.task_gather(self, e)
                    await asyncio.sleep(self.retry_interval)
                    continue
            self.connected_sig.task_gather(self)

            await self._prepare(self.client)
            self.prepared_sig.task_gather(self)

            await self._disconnected_event.wait()
            self.client = None
            self.connection_lost_sig.task_gather(self)

            await asyncio.sleep(self.retry_interval)

    async def start(self):
        if self.started:
            raise RuntimeError("Connection is already started")

        self.starting_sig.task_gather(self)

        self._reconnect_task = asyncio.create_task(self._reconnect_task_func())
        try:
            await self._reconnect_task
        finally:
            await self.shutdown()

    async def shutdown(self):
        self.shutting_down_sig.task_gather(self)

        if self._reconnect_task:
            self._reconnect_task.cancel()
        self._reconnect_task = None

        client = self.client
        self.client = None
        if client and client.is_connected:
            await client.disconnect()

    async def __aenter__(self):
        if not self.started:
            await self.start()

    async def __aexit__(self, _a, _b, _c):  # noqa: ANN001
        await self.shutdown()
        return False


HRS_UUID = "0000180d-0000-1000-8000-00805f9b34fb"
HRM_UUID = "00002a37-0000-1000-8000-00805f9b34fb"


async def scan_hrs_supported_devices(delay: float = 2.0):
    async with BleakScanner(service_uuids=[HRS_UUID]) as scanner:
        await asyncio.sleep(delay)
    return list(scanner.discovered_devices_and_advertisement_data.values())


class HRMData(NamedTuple):
    heart_rate: int
    sensor_contact: bool | None


def parse_hrm_pkg(pkg: bytearray) -> HRMData:
    flag = pkg[0]
    rate_is_u16 = flag & 0b00001 != 0
    sensor_contact_supported = flag & 0b00100 != 0
    sensor_contact = (flag & 0b00010 != 0) if sensor_contact_supported else None

    heart_rate = pkg[1]
    if rate_is_u16:
        heart_rate |= pkg[2] << 8

    return HRMData(heart_rate, sensor_contact)


class BLEHRSConnection(BaseBLEConnection):
    def __init__(
        self,
        address: str,
        retry_interval: float = 1.0,
        sig_exc_handler: Callable[[Signal, Exception], Co[Any]] = safe_exc_handler,
        **client_kw,
    ) -> None:
        super().__init__(address, retry_interval, sig_exc_handler, **client_kw)
        self.data_received_sig = Signal[[Self, HRMData, float], Any, Any](
            sig_exc_handler,
        )

    def _notify_callback_func(self, _, val: bytearray):  # noqa: ANN001
        if not self.data_received_sig.slots:
            return
        t = time.time()
        data = parse_hrm_pkg(val)
        self.data_received_sig.task_gather(self, data, t)

    @override
    async def _prepare(self, client: BleakClient):
        hrm_char = client.services.get_characteristic(HRM_UUID)
        if not hrm_char:
            raise RuntimeError("Device does not support HRM")
        await client.start_notify(hrm_char, self._notify_callback_func)

    async def iter(self) -> AsyncIterator[tuple[HRMData, float]]:
        if not self.connected:
            return

        queue = asyncio.Queue[tuple[HRMData, float] | None]()

        @self.data_received_sig.connect
        async def _recv(_: Self, data: HRMData, t: float):
            await queue.put((data, t))

        @self.connection_lost_sig.connect
        async def _lost(_: Self):
            await queue.put(None)

        try:
            while True:
                x = await queue.get()
                if x is None:
                    return
                yield x
        finally:
            self.data_received_sig.slots.remove(_recv)
            self.connection_lost_sig.slots.remove(_lost)

    def __aiter__(self):
        return self.iter()
