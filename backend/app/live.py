"""Leitura automática dos equipamentos e distribuição para as telas (WebSocket).

- Cada tela conectada em /api/ws diz quais equipamentos está mostrando
  ({"subscribe": [1, 2]}). Só esses são lidos: equipamento que ninguém está
  olhando não ocupa o barramento.
- Cada equipamento observado tem um "leitor" (tarefa asyncio) que chama
  driver.snapshot() pela fila única do barramento e espera o intervalo
  cadastrado (poll_ms; 0 = pausado). Leituras convivem com o console, os
  comandos e os scripts, porque tudo passa pela mesma fila.
- O leitor pode ser "cutucado" (poke) para ler na hora: depois de um comando,
  de mudar o intervalo ou de conectar o barramento.

Mensagem enviada a cada leitura:
    {"type": "state", "id": 1, "ok": true, "status": "ok", "data": {...},
     "error": null, "poll_ms": 1000, "cycle_ms": 180, "time": 1731470000.0}
status: "ok" | "timeout" (instrumento não respondeu) | "error" | "disconnected".
Se o equipamento for excluído: {"type": "removed", "id": 1}.
"""

import asyncio
import logging
import time

from fastapi import WebSocket

from app.drivers import open_instrument
from app.drivers.base import Instrument, InstrumentIO
from app.equipment import EquipmentStore
from app.errors import AppError, NotFound
from app.gpib.bus import GpibBus
from app.gpib.errors import GpibTimeout, NotConnected
from app.gpib.transport import Transport

log = logging.getLogger(__name__)

# Depois de um erro, espera pelo menos isto antes de tentar de novo
ERROR_RETRY_S = 1.0


def open_equipment(eq: dict, transport: Transport) -> Instrument:
    """Driver do equipamento cadastrado (usa o driver salvo, sem perguntar *IDN?)."""
    return open_instrument(InstrumentIO(transport, eq["address"]), driver=eq["driver"])


class _Poller:
    def __init__(self):
        self.wake = asyncio.Event()
        self.task: asyncio.Task | None = None


class LiveHub:
    def __init__(self, bus: GpibBus, store: EquipmentStore):
        self.bus = bus
        self.store = store
        self._clients: dict[WebSocket, set[int]] = {}
        self._pollers: dict[int, _Poller] = {}
        self._last: dict[int, dict] = {}  # última mensagem de cada equipamento

    # --- telas ---------------------------------------------------------------

    def add_client(self, ws: WebSocket) -> None:
        self._clients[ws] = set()

    def remove_client(self, ws: WebSocket) -> None:
        self._clients.pop(ws, None)
        self._update_pollers()

    async def subscribe(self, ws: WebSocket, ids: set[int]) -> None:
        old = self._clients.get(ws, set())
        self._clients[ws] = ids
        self._update_pollers()
        # Quem acabou de assinar recebe logo a última leitura conhecida
        for eq_id in ids - old:
            if eq_id in self._last:
                await self._send(ws, self._last[eq_id])

    async def publish(self, msg: dict) -> None:
        eq_id = msg["id"]
        if msg["type"] == "state":
            self._last[eq_id] = msg
        for ws, ids in list(self._clients.items()):
            if eq_id in ids:
                await self._send(ws, msg)

    async def _send(self, ws: WebSocket, msg: dict) -> None:
        try:
            await ws.send_json(msg)
        except Exception:
            pass  # tela fechou; ela sai da lista quando o WebSocket terminar

    # --- leitores ------------------------------------------------------------

    def watched(self) -> set[int]:
        return set().union(*self._clients.values()) if self._clients else set()

    def _update_pollers(self) -> None:
        wanted = self.watched()
        for eq_id in list(self._pollers):
            if eq_id not in wanted:
                self._pollers.pop(eq_id).task.cancel()
                self._last.pop(eq_id, None)
        for eq_id in wanted - self._pollers.keys():
            poller = _Poller()
            self._pollers[eq_id] = poller
            poller.task = asyncio.create_task(self._run(eq_id, poller), name=f"poll-{eq_id}")

    def poke(self, eq_id: int) -> None:
        """Faz o leitor do equipamento ler agora (se alguém estiver olhando)."""
        poller = self._pollers.get(eq_id)
        if poller:
            poller.wake.set()

    def poke_all(self) -> None:
        for poller in self._pollers.values():
            poller.wake.set()

    async def shutdown(self) -> None:
        tasks = [p.task for p in self._pollers.values() if p.task]
        self._pollers.clear()
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _run(self, eq_id: int, poller: _Poller) -> None:
        try:
            while True:
                poller.wake.clear()
                try:
                    eq = self.store.get(eq_id)
                except NotFound:
                    await self.publish({"type": "removed", "id": eq_id})
                    return
                msg = await self.read(eq)
                await self.publish(msg)
                await self._wait(poller, msg)
        finally:
            if self._pollers.get(eq_id) is poller:
                del self._pollers[eq_id]

    async def _wait(self, poller: _Poller, msg: dict) -> None:
        """Espera o próximo ciclo, ou até ser cutucado."""
        if msg["poll_ms"] == 0 or msg["status"] == "disconnected":
            timeout = None  # pausado / sem barramento: só lê de novo se cutucado
        else:
            # O intervalo conta do início de um ciclo ao início do próximo
            timeout = max(msg["poll_ms"] - msg["cycle_ms"], 0) / 1000
            if not msg["ok"]:
                timeout = max(timeout, ERROR_RETRY_S)
        try:
            await asyncio.wait_for(poller.wake.wait(), timeout)
        except asyncio.TimeoutError:
            pass

    async def read(self, eq: dict) -> dict:
        """Uma leitura completa do equipamento, já no formato da mensagem."""
        start = time.perf_counter()
        status, data, error = "ok", None, None
        if not self.bus.status()["connected"]:
            status, error = "disconnected", "Barramento desconectado"
        else:
            try:
                data = await asyncio.wrap_future(
                    self.bus.transaction(lambda t: open_equipment(eq, t).snapshot())
                )
            except NotConnected as e:
                status, error = "disconnected", str(e)
            except GpibTimeout as e:
                status, error = "timeout", str(e)
            except AppError as e:
                status, error = "error", str(e)
            except Exception as e:
                log.exception("Erro lendo o equipamento %s", eq["id"])
                status, error = "error", f"Erro inesperado: {e}"
        return {
            "type": "state",
            "id": eq["id"],
            "ok": status == "ok",
            "status": status,
            "data": data,
            "error": error,
            "poll_ms": eq["poll_ms"],
            "cycle_ms": round((time.perf_counter() - start) * 1000),
            "time": time.time(),
        }
