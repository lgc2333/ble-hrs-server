import asyncio
from collections.abc import Callable, Coroutine
from typing import Any, Self

from bleak import BleakClient
from cookit import Signal, safe_exc_handler

from .data import HRM_UUID, HRMData, parse_val

type Co[T] = Coroutine[Any, Any, T]


class HRSDeviceConnection:
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
        self.started_notify_sig = Signal[[Self], Any, Any](sig_exc_handler)
        self.data_received_sig = Signal[[Self, HRMData], Any, Any](sig_exc_handler)

    def new_client(self) -> BleakClient:
        return BleakClient(
            self.address,
            disconnected_callback=self._disconnected_callback,
            **self.client_kw,
        )

    async def __aenter__(self):
        await self.connect()

    async def __aexit__(self, _a, _b, _c):  # noqa: ANN001
        await self.disconnect()
        return False

    async def wait_next_val(self) -> HRMData:
        fut = asyncio.Future[HRMData]()

        @self.data_received_sig.connect
        async def slot(_: Self, data: HRMData):
            fut.set_result(data)

        ret = await fut
        self.data_received_sig.slots.remove(slot)
        return ret

    async def __iter__(self):
        while True:
            yield await self.wait_next_val()

    def _disconnected_callback(self, _client: BleakClient):
        self._disconnected_event.set()
        self._disconnected_event.clear()

    def _notify_callback_func(self, _, val: bytearray):  # noqa: ANN001
        if not self.data_received_sig.slots:
            return
        data = parse_val(val)
        self.data_received_sig.task_gather(self, data)

    async def _reconnect_task_func(self):
        while True:
            if not self.client:
                self.client = self.new_client()

            if not self.client.is_connected:
                self.connecting_sig.task_gather(self)
                try:
                    await self.client.connect()
                except Exception as e:
                    self.connect_failed_sig.task_gather(self, e)
                    continue
            self.connected_sig.task_gather(self)

            hrm_char = self.client.services.get_characteristic(HRM_UUID)
            if not hrm_char:
                raise RuntimeError("Device does not support HRM")
            await self.client.start_notify(hrm_char, self._notify_callback_func)
            self.started_notify_sig.task_gather(self)

            await self._disconnected_event.wait()
            self.client = None
            self.connection_lost_sig.task_gather(self)

            await asyncio.sleep(self.retry_interval)

    async def connect(self):
        self._reconnect_task = asyncio.create_task(self._reconnect_task_func())
        try:
            await self._reconnect_task
        finally:
            await self.disconnect()

    async def disconnect(self):
        if self.client:
            await self.client.disconnect()
        self.client = None
        if self._reconnect_task:
            self._reconnect_task.cancel()
        self._reconnect_task = None
