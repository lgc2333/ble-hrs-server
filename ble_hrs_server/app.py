from contextlib import asynccontextmanager

import uvicorn
from fastapi import APIRouter, FastAPI, WebSocket, WebSocketDisconnect, status as c
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .conf import config
from .conn import BLEHRSConnection, HRMData
from .log import LOGGING_CONFIG
from .main import init

_curr_conn: BLEHRSConnection


@asynccontextmanager
async def app_lifespan(_: FastAPI):
    global _curr_conn

    conn = await init()
    if not conn:
        raise RuntimeError("No device found")
    _curr_conn = conn

    async with conn:
        yield


app = FastAPI(
    lifespan=app_lifespan,
    openapi_url=None,
    docs_url=None,
    redoc_url=None,
    swagger_ui_oauth2_redirect_url=None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.server_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_router = APIRouter(prefix="/api/v1")


class WsHRMConnectionState(BaseModel):
    connected: bool


class WsHRMData(BaseModel):
    t: float
    r: int
    s: bool | None


@api_router.websocket("/ws")
async def _(ws: WebSocket):
    if not _curr_conn.started:
        await ws.close(code=c.WS_1011_INTERNAL_ERROR, reason="Connection not started")
        return

    await ws.accept()
    await ws.send_text(
        WsHRMConnectionState(connected=_curr_conn.connected).model_dump_json(),
    )

    @_curr_conn.prepared_sig.connect
    async def _prepared(_: BLEHRSConnection):
        await ws.send_text(WsHRMConnectionState(connected=True).model_dump_json())

    @_curr_conn.connection_lost_sig.connect
    async def _lost(_: BLEHRSConnection):
        await ws.send_text(WsHRMConnectionState(connected=False).model_dump_json())

    @_curr_conn.data_received_sig.connect
    async def _data(_: BLEHRSConnection, data: HRMData, t: float):
        r, s = data
        await ws.send_text(WsHRMData(t=t, r=r, s=s).model_dump_json())

    @_curr_conn.shutting_down_sig.connect
    async def _shutting_down(_: BLEHRSConnection):
        await ws.close(
            code=c.WS_1012_SERVICE_RESTART,
            reason="Device connection shutting down",
        )

    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        _curr_conn.prepared_sig.slots.remove(_prepared)
        _curr_conn.connection_lost_sig.slots.remove(_lost)
        _curr_conn.data_received_sig.slots.remove(_data)
        _curr_conn.shutting_down_sig.slots.remove(_shutting_down)


app.include_router(api_router)


def run():
    uvicorn.run(
        app,
        host=config.server_host,
        port=config.server_port,
        log_config=LOGGING_CONFIG,
    )
