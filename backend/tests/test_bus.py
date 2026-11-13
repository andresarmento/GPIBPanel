import asyncio
import threading
import time

import pytest

from app.gpib.bus import GpibBus
from app.gpib.errors import NotConnected
from app.gpib.simulated import SimulatedTransport
from app.gpib.transport import Transport


class SlowTransport(Transport):
    """Registra entradas/saídas para provar que nunca há duas operações ao mesmo tempo."""

    kind = "slow"

    def __init__(self):
        self.active = 0
        self.max_active = 0
        self.lock = threading.Lock()
        self.log = []

    def open(self):
        pass

    def close(self):
        pass

    def write(self, address, command):
        with self.lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        time.sleep(0.01)
        self.log.append(command)
        with self.lock:
            self.active -= 1

    def read(self, address):
        return "ok"

    def describe(self):
        return {"kind": self.kind}


@pytest.fixture
def bus():
    b = GpibBus()
    yield b
    b.shutdown()


def test_not_connected(bus):
    with pytest.raises(NotConnected):
        asyncio.run(bus.query(5, "*IDN?"))


def test_query_through_simulator(bus):
    async def go():
        await bus.connect(SimulatedTransport())
        return await bus.query(5, "*IDN?")

    assert "E3632A" in asyncio.run(go())
    assert bus.status()["connected"] is True


def test_operations_never_overlap(bus):
    t = SlowTransport()

    async def go():
        await bus.connect(t)
        await asyncio.gather(*(bus.write(1, f"C{i}") for i in range(20)))

    asyncio.run(go())
    assert t.max_active == 1
    assert len(t.log) == 20


def test_sync_callers_from_threads(bus):
    """Scripts (Fase 6) vão chamar o barramento a partir de outras threads."""
    t = SlowTransport()
    asyncio.run(bus.connect(t))
    threads = [
        threading.Thread(target=lambda i=i: bus.transaction(lambda tr: tr.write(1, f"T{i}")).result())
        for i in range(10)
    ]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    assert t.max_active == 1
    assert len(t.log) == 10


def test_transaction_is_atomic(bus):
    t = SlowTransport()
    asyncio.run(bus.connect(t))

    def seq(tr):
        tr.write(1, "A")
        tr.write(1, "B")

    f1 = bus.transaction(seq)
    f2 = bus.transaction(lambda tr: tr.write(1, "X"))
    f1.result()
    f2.result()
    assert t.log == ["A", "B", "X"]


def test_disconnect(bus):
    asyncio.run(bus.connect(SimulatedTransport()))
    asyncio.run(bus.disconnect())
    assert bus.status() == {"connected": False}
