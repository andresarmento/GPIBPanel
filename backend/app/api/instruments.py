"""API dos drivers: lista de drivers e identificação de um endereço (*IDN?).

O controle dos instrumentos é feito pelo equipamento cadastrado (app/api/live.py).
"""

import asyncio
from typing import Annotated

from fastapi import APIRouter, Path, Request

from app.drivers import identify, list_drivers
from app.drivers.base import InstrumentIO
from app.gpib.bus import GpibBus
from app.gpib.transport import MAX_ADDRESS, MIN_ADDRESS

router = APIRouter(tags=["drivers"])

Address = Annotated[int, Path(ge=MIN_ADDRESS, le=MAX_ADDRESS)]


@router.get("/drivers")
def drivers() -> list[dict]:
    return list_drivers()


@router.post("/instruments/{address}/identify")
async def identify_instrument(address: Address, request: Request) -> dict:
    bus: GpibBus = request.app.state.bus
    idn, cls = await asyncio.wrap_future(bus.transaction(lambda t: identify(InstrumentIO(t, address))))
    return {"address": address, "idn": idn.to_dict(), "driver": cls.describe() if cls else None}
