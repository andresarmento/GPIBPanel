"""Fila única do barramento GPIB.

Existe um só AR488, então todo acesso ao barramento passa por uma única
thread de trabalho, em ordem de chegada. Isso evita que dois pedidos
(tela, script, leitura periódica...) se misturem no meio de uma conversa
com o instrumento.

- Código async (FastAPI) usa os métodos async: `await bus.query(...)`.
- Código síncrono (scripts, na Fase 6) usa `bus.submit(fn).result()`.
- Para uma sequência de comandos que não pode ser interrompida, use
  `bus.transaction(lambda t: ...)`: a função inteira roda de uma vez na fila.
"""

import asyncio
import queue
import threading
from collections.abc import Callable
from concurrent.futures import Future
from typing import TypeVar

from app.gpib.errors import NotConnected
from app.gpib.transport import Transport

T = TypeVar("T")


class GpibBus:
    def __init__(self):
        self._queue: queue.Queue = queue.Queue()
        self._thread: threading.Thread | None = None
        self._start_lock = threading.Lock()
        self._transport: Transport | None = None

    # --- fila --------------------------------------------------------------

    def _ensure_worker(self) -> None:
        with self._start_lock:
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._worker, name="gpib-bus", daemon=True)
                self._thread.start()

    def _worker(self) -> None:
        while True:
            item = self._queue.get()
            if item is None:
                break
            fn, fut = item
            if not fut.set_running_or_notify_cancel():
                continue
            try:
                fut.set_result(fn())
            except BaseException as e:
                fut.set_exception(e)

    def submit(self, fn: Callable[[], T]) -> "Future[T]":
        """Coloca `fn` na fila; devolve um Future com o resultado."""
        fut: Future = Future()
        if threading.current_thread() is self._thread:
            # Já estamos dentro da fila (ex.: transação chamando outra operação)
            try:
                fut.set_result(fn())
            except BaseException as e:
                fut.set_exception(e)
            return fut
        self._ensure_worker()
        self._queue.put((fn, fut))
        return fut

    async def run(self, fn: Callable[[], T]) -> T:
        return await asyncio.wrap_future(self.submit(fn))

    def shutdown(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            self._queue.put(None)
            self._thread.join(timeout=5)
        self._thread = None

    # --- conexão -----------------------------------------------------------

    def _require(self) -> Transport:
        if self._transport is None:
            raise NotConnected("Barramento desconectado")
        return self._transport

    def _connect(self, transport: Transport) -> dict:
        self._disconnect()
        transport.open()
        self._transport = transport
        return transport.describe()

    def _disconnect(self) -> None:
        if self._transport is not None:
            try:
                self._transport.close()
            finally:
                self._transport = None

    async def connect(self, transport: Transport) -> dict:
        return await self.run(lambda: self._connect(transport))

    async def disconnect(self) -> None:
        await self.run(self._disconnect)

    def status(self) -> dict:
        t = self._transport
        if t is None:
            return {"connected": False}
        return {"connected": True, **t.describe()}

    # --- operações ---------------------------------------------------------

    def transaction(self, fn: Callable[[Transport], T]) -> "Future[T]":
        return self.submit(lambda: fn(self._require()))

    async def write(self, address: int, command: str) -> None:
        await asyncio.wrap_future(self.transaction(lambda t: t.write(address, command)))

    async def query(self, address: int, command: str) -> str:
        return await asyncio.wrap_future(self.transaction(lambda t: t.query(address, command)))

    async def read(self, address: int) -> str:
        """Só lê a resposta pendente (ex.: depois de um pedido de dado sem "?")."""
        return await asyncio.wrap_future(self.transaction(lambda t: t.read(address)))
