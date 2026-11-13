from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.gpib.ar488 import AR488Transport, list_serial_ports
from app.gpib.bus import GpibBus
from app.gpib.simulated import SimulatedTransport
from app.gpib.transport import MAX_ADDRESS, MIN_ADDRESS

router = APIRouter(prefix="/bus", tags=["barramento"])


def _bus(request: Request) -> GpibBus:
    return request.app.state.bus


class ConnectRequest(BaseModel):
    kind: Literal["ar488", "sim"]
    port: str | None = None
    baudrate: int = 115200


class CommandRequest(BaseModel):
    address: int = Field(ge=MIN_ADDRESS, le=MAX_ADDRESS)
    command: str = Field(min_length=1)


@router.get("")
def status(request: Request) -> dict:
    return _bus(request).status()


@router.get("/ports")
def ports() -> list[dict]:
    return list_serial_ports()


@router.post("/connect")
async def connect(body: ConnectRequest, request: Request) -> dict:
    if body.kind == "ar488":
        if not body.port:
            raise HTTPException(400, "Informe a porta serial do AR488")
        transport = AR488Transport(body.port, body.baudrate)
    else:
        transport = SimulatedTransport()
    bus = _bus(request)
    await bus.connect(transport)
    return bus.status()


@router.post("/disconnect")
async def disconnect(request: Request) -> dict:
    bus = _bus(request)
    await bus.disconnect()
    return bus.status()


@router.post("/write")
async def write(body: CommandRequest, request: Request) -> dict:
    await _bus(request).write(body.address, body.command)
    return {"ok": True}


@router.post("/query")
async def query(body: CommandRequest, request: Request) -> dict:
    response = await _bus(request).query(body.address, body.command)
    return {"response": response}
