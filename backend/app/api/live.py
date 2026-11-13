"""Controle em tempo real: WebSocket das leituras e comandos por equipamento cadastrado."""

import asyncio
import json

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from app.drivers.errors import DriverError
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


@router.patch("/equipment/{equipment_id}/poll")
async def set_poll(equipment_id: int, body: PollSettings, request: Request) -> dict:
    eq = request.app.state.equipment.set_poll(equipment_id, body.poll_ms)
    _hub(request).poke(equipment_id)
    return eq
