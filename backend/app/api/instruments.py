"""API dos drivers.

Na Fase 2 o instrumento é acessado direto pelo endereço GPIB e o driver é
identificado pelo *IDN? a cada pedido. Na Fase 3 o equipamento cadastrado
vai guardar o driver escolhido.
"""

import asyncio
from collections.abc import Callable
from typing import Annotated, TypeVar

from fastapi import APIRouter, Path, Request
from pydantic import BaseModel

from app.drivers import identify, list_drivers, open_instrument
from app.drivers.base import InstrumentIO
from app.drivers.errors import DriverError
from app.drivers.power_supply import PowerSupply
from app.gpib.bus import GpibBus
from app.gpib.transport import MAX_ADDRESS, MIN_ADDRESS, Transport

router = APIRouter(tags=["drivers"])

T = TypeVar("T")
Address = Annotated[int, Path(ge=MIN_ADDRESS, le=MAX_ADDRESS)]


class PsuSettings(BaseModel):
    range: str | None = None
    voltage: float | None = None
    current: float | None = None
    output: bool | None = None


async def _on_bus(request: Request, fn: Callable[[Transport], T]) -> T:
    bus: GpibBus = request.app.state.bus
    return await asyncio.wrap_future(bus.transaction(fn))


async def _with_psu(request: Request, address: int, fn: Callable[[PowerSupply], T]) -> T:
    def run(t: Transport) -> T:
        inst = open_instrument(InstrumentIO(t, address))
        if not isinstance(inst, PowerSupply):
            raise DriverError(f"{inst.name} (endereço {address}) não é uma fonte")
        return fn(inst)

    return await _on_bus(request, run)


@router.get("/drivers")
def drivers() -> list[dict]:
    return list_drivers()


@router.post("/instruments/{address}/identify")
async def identify_instrument(address: Address, request: Request) -> dict:
    idn, cls = await _on_bus(request, lambda t: identify(InstrumentIO(t, address)))
    return {"address": address, "idn": idn.to_dict(), "driver": cls.describe() if cls else None}


@router.get("/instruments/{address}/psu/{channel}")
async def psu_state(address: Address, channel: str, request: Request) -> dict:
    state = await _with_psu(request, address, lambda psu: psu.read_state(channel))
    return state.to_dict()


@router.post("/instruments/{address}/psu/{channel}")
async def psu_apply(address: Address, channel: str, body: PsuSettings, request: Request) -> dict:
    state = await _with_psu(request, address, lambda psu: psu.apply(channel, **body.model_dump()))
    return state.to_dict()
