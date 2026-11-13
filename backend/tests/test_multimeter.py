import math

import pytest
from fastapi.testclient import TestClient

from app.drivers import K2015, find_driver, identify, open_instrument
from app.drivers.base import Idn, InstrumentIO
from app.drivers.errors import InstrumentError, LimitError
from app.drivers.k2015 import parse_reading
from app.gpib.errors import GpibTimeout
from app.gpib.simulated import SimK2015, SimulatedTransport
from app.main import app


class Spy(SimulatedTransport):
    """Simulador que registra os comandos enviados (sem as consultas de erro)."""

    def __init__(self):
        super().__init__({16: SimK2015(noise=0)})
        self.sent = []

    def write(self, address, command):
        if command != "SYST:ERR?":
            self.sent.append(command)
        super().write(address, command)


@pytest.fixture
def sim():
    return SimK2015(noise=0)


@pytest.fixture
def transport(sim):
    t = SimulatedTransport({16: sim})
    t.open()
    return t


@pytest.fixture
def dmm(transport):
    return K2015(InstrumentIO(transport, 16))


# --- identificação ------------------------------------------------------------


def test_find_driver():
    assert find_driver(Idn.parse("KEITHLEY INSTRUMENTS INC.,MODEL 2015,1234567,A01  /A02")) is K2015
    assert find_driver(Idn.parse("KEITHLEY INSTRUMENTS INC.,MODEL 2000,1,A01")) is None


def test_identify_and_open(transport):
    idn, cls = identify(InstrumentIO(transport, 16))
    assert idn.model == "MODEL 2015" and cls is K2015
    assert isinstance(open_instrument(InstrumentIO(transport, 16)), K2015)


def test_describe():
    d = K2015.describe()
    assert d["type"] == "multimeter"
    names = [f["name"] for f in d["functions"]]
    assert names == ["DCV", "ACV", "DCI", "ACI", "OHM2", "OHM4", "FREQ"]
    freq = d["functions"][-1]
    assert list(freq["ranges"]) == [] and freq["nplc"] is False and freq["unit"] == "Hz"


def test_parse_reading():
    assert parse_reading("+1.23456789E+00") == pytest.approx(1.23456789)
    assert parse_reading("-4.5E-03VDC,+0012345RDNG#") == pytest.approx(-4.5e-3)
    assert parse_reading(" 12 ") == 12
    with pytest.raises(InstrumentError):
        parse_reading("OVERFLOW")


# --- leitura ------------------------------------------------------------------


def test_initial_state(dmm):
    s = dmm.read_state()
    assert s.function == "DCV" and s.unit == "V" and s.auto is True
    assert s.range == 10.0  # auto escolheu 10 V para 1,23 V
    assert s.nplc == 1.0 and s.value == pytest.approx(1.234567) and s.overload is False
    assert dmm.measure() == pytest.approx(1.234567)


def test_each_function(dmm, sim):
    expected = {"ACV": 0.5, "DCI": 0.0123, "ACI": 0.25, "OHM2": 4700, "OHM4": 4699.5, "FREQ": 1000}
    for name, value in expected.items():
        s = dmm.set_function(name)
        assert s.function == name and s.value == pytest.approx(value)
    s = dmm.read_state()
    assert s.function == "FREQ" and s.range is None and s.nplc is None and s.auto is True


def test_manual_range_and_overload(dmm):
    s = dmm.set_range(5)  # menor faixa que comporta 5 V
    assert s.range == 10.0 and s.auto is False
    s = dmm.set_range(1)  # 1,23 V passa dos 120% da faixa de 1 V
    assert s.range == 1.0 and s.overload is True and s.value is None
    assert math.isinf(dmm.measure())
    s = dmm.set_range("auto")
    assert s.auto is True and s.range == 10.0 and not s.overload


def test_ranges_are_per_function(dmm):
    dmm.configure(function="OHM2", range=1e3)
    s = dmm.configure(function="DCV")
    assert s.auto is True  # a faixa manual de Ω não afetou a de tensão
    s = dmm.set_function("OHM2")
    assert s.auto is False and s.overload is True  # 4,7 kΩ na faixa de 1 kΩ


def test_nplc(dmm):
    assert dmm.set_nplc(10).nplc == 10
    assert dmm.configure(function="ACV", nplc=0.1).nplc == pytest.approx(0.1)
    assert dmm.set_function("DCV").nplc == 10  # cada função guarda o seu


def test_limits(dmm):
    with pytest.raises(LimitError):
        dmm.set_function("TEMP")
    with pytest.raises(LimitError):
        dmm.set_range(2000)  # acima de 1000 V
    with pytest.raises(LimitError):
        dmm.set_range(0)
    with pytest.raises(LimitError):
        dmm.set_range("MAX")
    with pytest.raises(LimitError):
        dmm.set_nplc(20)
    with pytest.raises(LimitError):
        dmm.set_nplc(float("nan"))
    with pytest.raises(LimitError):
        dmm.configure(function="FREQ", nplc=1)
    with pytest.raises(LimitError):
        dmm.configure(function="FREQ", range=10)
    assert dmm.configure(function="FREQ", range="AUTO").function == "FREQ"  # auto é aceito


def test_limit_error_sends_nothing():
    spy = Spy()
    spy.open()
    dmm = K2015(InstrumentIO(spy, 16))
    with pytest.raises(LimitError):
        dmm.configure(function="ACV", nplc=0.5, range=1000)  # ACV vai só até 750 V
    assert spy.sent == []


def test_configure_order_and_commands():
    spy = Spy()
    spy.open()
    dmm = K2015(InstrumentIO(spy, 16))
    dmm.configure(function="OHM4", nplc=2, range=10e3)
    writes = [c for c in spy.sent if not c.endswith("?")]
    assert writes == [":SENS:FUNC 'FRES'", ":SENS:FRES:NPLC 2", ":SENS:FRES:RANG 10000"]


def test_restarts_continuous_trigger(dmm, sim):
    sim.handle("*RST")
    assert sim.init_cont is False
    assert dmm.measure() == pytest.approx(1.234567)
    assert sim.init_cont is True


def test_instrument_error_is_reported(dmm, sim):
    with pytest.raises(InstrumentError, match="-224"):
        dmm.command(":SENS:FUNC 'XYZ'")


def test_no_reading_is_timeout(transport, sim):
    sim.init_cont = False
    with pytest.raises(GpibTimeout):
        transport.query(16, ":SENS:DATA:FRES?")


# --- API e leitura automática ---------------------------------------------------


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_api_configure_and_live(client):
    client.post("/api/bus/connect", json={"kind": "sim"})  # simulador tem o 2015 no endereço 16
    eq = client.post("/api/equipment", json={"name": "DMM", "address": 16, "driver": "K2015"}).json()
    eq = client.patch(f"/api/equipment/{eq['id']}/poll", json={"poll_ms": 0}).json()
    with client.websocket_connect("/api/ws") as ws:
        ws.send_json({"subscribe": [eq["id"]]})
        msg = ws.receive_json()
        assert msg["ok"] and msg["data"]["function"] == "DCV"

        r = client.post(f"/api/equipment/{eq['id']}/dmm", json={"function": "OHM2", "range": 10000, "nplc": 5})
        assert r.status_code == 200
        assert r.json()["function"] == "OHM2" and r.json()["range"] == 10000 and r.json()["nplc"] == 5

        msg = ws.receive_json()
        assert msg["data"]["function"] == "OHM2" and msg["data"]["unit"] == "Ω"

    assert client.post(f"/api/equipment/{eq['id']}/dmm", json={"range": "AUTO"}).json()["auto"] is True
    assert client.post(f"/api/equipment/{eq['id']}/dmm", json={"function": "XYZ"}).status_code == 422
    assert client.post(f"/api/equipment/{eq['id']}/dmm", json={"range": "MAX"}).status_code == 422


def test_api_wrong_type(client):
    client.post("/api/bus/connect", json={"kind": "sim"})
    psu = client.post("/api/equipment", json={"name": "Fonte", "address": 5, "driver": "E3632A"}).json()
    dmm = client.post("/api/equipment", json={"name": "DMM", "address": 16, "driver": "K2015"}).json()
    assert client.post(f"/api/equipment/{psu['id']}/dmm", json={}).status_code == 400
    assert client.post(f"/api/equipment/{dmm['id']}/psu/OUT", json={}).status_code == 400
