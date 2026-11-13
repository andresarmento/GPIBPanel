"""Controle em tempo real: WebSocket das leituras e comandos por equipamento cadastrado."""

import asyncio
import json

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from app.drivers.errors import DriverError
from app.drivers.function_generator import FunctionGenerator
from app.drivers.multimeter import Multimeter
from app.drivers.rf_generator import RFGenerator
from app.drivers.power_supply import PowerSupply
from app.live import LiveHub, open_equipment

router = APIRouter(tags=["tempo real"])


def _hub(request: Request) -> LiveHub:
    return request.app.state.live


class PsuSettings(BaseModel):
    range: str | None = None
    voltage: float | None = None
    current: float | None = None
    output: bool | None = None


class DmmSettings(BaseModel):
    function: str | None = None
    range: float | str | None = None  # "AUTO" ou o maior valor esperado
    nplc: float | None = None


class FgenSettings(BaseModel):
    waveform: str | None = None
    frequency: float | None = None
    amplitude: float | None = None  # Vpp
    offset: float | None = None
    duty: float | None = None
    load: str | None = None  # "50" | "HIGHZ"
    output: bool | None = None


class RfSettings(BaseModel):
    frequency: float | None = None  # Hz
    level: float | None = None  # dBm
    output: bool | None = None


class PollSettings(BaseModel):
    poll_ms: int


@router.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    """A tela manda {"subscribe": [ids]} com os equipamentos que está mostrando."""
    hub: LiveHub = ws.app.state.live
    await ws.accept()
    hub.add_client(ws)
    try:
        while True:
            text = await ws.receive_text()
            try:
                ids = {int(i) for i in json.loads(text)["subscribe"]}
            except (ValueError, TypeError, KeyError):
                continue  # mensagem mal formada: ignora
            await hub.subscribe(ws, ids)
    except WebSocketDisconnect:
        pass
    finally:
        hub.remove_client(ws)


@router.post("/equipment/{equipment_id}/psu/{channel}")
async def psu_apply(equipment_id: int, channel: str, body: PsuSettings, request: Request) -> dict:
    """Ajusta um canal de fonte; devolve o estado do canal e atualiza as telas na hora."""
    eq = request.app.state.equipment.get(equipment_id)
    hub = _hub(request)

    def run(t):
        inst = open_equipment(eq, t)
        if not isinstance(inst, PowerSupply):
            raise DriverError(f"{eq['name']} não é uma fonte")
        return inst.apply(channel, **body.model_dump())

    try:
        state = await asyncio.wrap_future(hub.bus.transaction(run))
    finally:
        hub.poke(equipment_id)  # mesmo se der erro, a tela mostra o estado real
    return state.to_dict()


@router.post("/equipment/{equipment_id}/dmm")
async def dmm_configure(equipment_id: int, body: DmmSettings, request: Request) -> dict:
    """Ajusta um multímetro (função, faixa, NPLC); devolve o estado e atualiza as telas na hora."""
    eq = request.app.state.equipment.get(equipment_id)
    hub = _hub(request)

    def run(t):
        inst = open_equipment(eq, t)
        if not isinstance(inst, Multimeter):
            raise DriverError(f"{eq['name']} não é um multímetro")
        return inst.configure(**body.model_dump())

    try:
        state = await asyncio.wrap_future(hub.bus.transaction(run))
    finally:
        hub.poke(equipment_id)
    return state.to_dict()


@router.post("/equipment/{equipment_id}/fgen/{channel}")
async def fgen_apply(equipment_id: int, channel: str, body: FgenSettings, request: Request) -> dict:
    """Ajusta um canal de gerador de funções; devolve o estado e atualiza as telas na hora."""
    eq = request.app.state.equipment.get(equipment_id)
    hub = _hub(request)

    def run(t):
        inst = open_equipment(eq, t)
        if not isinstance(inst, FunctionGenerator):
            raise DriverError(f"{eq['name']} não é um gerador de funções")
        return inst.apply(channel, **body.model_dump())

    try:
        state = await asyncio.wrap_future(hub.bus.transaction(run))
    finally:
        hub.poke(equipment_id)
    return state.to_dict()


@router.post("/equipment/{equipment_id}/rf/{channel}")
async def rf_apply(equipment_id: int, channel: str, body: RfSettings, request: Request) -> dict:
    """Ajusta um gerador de RF; devolve o estado e atualiza as telas na hora."""
    eq = request.app.state.equipment.get(equipment_id)
    hub = _hub(request)

    def run(t):
        inst = open_equipment(eq, t)
        if not isinstance(inst, RFGenerator):
            raise DriverError(f"{eq['name']} não é um gerador de RF")
        return inst.apply(channel, **body.model_dump())

    try:
        state = await asyncio.wrap_future(hub.bus.transaction(run))
    finally:
        hub.poke(equipment_id)
    return state.to_dict()


@router.patch("/equipment/{equipment_id}/poll")
async def set_poll(equipment_id: int, body: PollSettings, request: Request) -> dict:
    eq = request.app.state.equipment.set_poll(equipment_id, body.poll_ms)
    _hub(request).poke(equipment_id)
    return eq
