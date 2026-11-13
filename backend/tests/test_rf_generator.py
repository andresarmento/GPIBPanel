import pytest
from fastapi.testclient import TestClient

from app.drivers import MG3601A, identify, open_instrument
from app.drivers.base import InstrumentIO
from app.drivers.errors import InstrumentError, LimitError
from app.drivers.mg3601a import parse_reply
from app.gpib.errors import GpibTimeout
from app.gpib.simulated import SimE3632A, SimMG3601A, SimulatedTransport
from app.main import app


class Spy(SimulatedTransport):
    """Simulador que registra os ajustes enviados (sem os pedidos de dado xxRD)."""

    def __init__(self):
        super().__init__({13: SimMG3601A()})
        self.sent = []

    def write(self, address, command):
        if not command.endswith("RD"):
            self.sent.append(command)
        super().write(address, command)


@pytest.fixture
def sim():
    return SimMG3601A()


@pytest.fixture
def transport(sim):
    t = SimulatedTransport({13: sim, 5: SimE3632A()})
    t.open()
    return t


@pytest.fixture
def gen(transport):
    return MG3601A(InstrumentIO(transport, 13))


# --- formato das respostas (como o aparelho real respondeu) -------------------------


def test_parse_reply():
    assert parse_reply("+100000000E+00") == (100e6, 0)
    assert parse_reply("-000000100E-01") == (-10.0, -1)
    assert parse_reply("+000000000E+00") == (0.0, 0)
    for bad in ("100 MHz", "+1E+00", "+100000000E0"):
        with pytest.raises(InstrumentError):
            parse_reply(bad)


# --- identificação sem *IDN? ---------------------------------------------------------


def test_sim_answers_idn_like_the_real_one(transport):
    # o MG3601A real ignora o *IDN? e manda o último dado pedido (a frequência)
    assert transport.query(13, "*IDN?") == "+100000000E+00"


def test_identify_without_idn(transport):
    idn, cls = identify(InstrumentIO(transport, 13))
    assert cls is MG3601A and idn.model == "MG3601A" and "FRRD" in idn.raw
    assert isinstance(open_instrument(InstrumentIO(transport, 13)), MG3601A)
    # aparelho SCPI continua identificado pelo *IDN? (o probe nem é tentado)
    assert identify(InstrumentIO(transport, 5))[0].model == "E3632A"


def test_identify_empty_address(transport):
    with pytest.raises(GpibTimeout):
        identify(InstrumentIO(transport, 20))  # ninguém respondeu nem ao *IDN? nem ao probe


def test_describe():
    d = MG3601A.describe()
    assert d["type"] == "rf_generator" and d["channels"] == [{"name": "RF"}]
    assert (d["frequency_min"], d["frequency_max"], d["level_min"], d["level_max"]) == (0.1e6, 1040e6, -133, 13)


# --- leitura ----------------------------------------------------------------------------


def test_read_state(gen):
    s = gen.read_state()
    assert (s.channel, s.frequency, s.level, s.output) == ("RF", 100e6, -10.0, True)
    (ch,) = gen.snapshot()["channels"]
    assert ch["frequency"] == 100e6


def test_rf_off_is_detected(gen, sim):
    sim.rf_on = False  # desligado pelo painel frontal
    s = gen.read_state()
    assert s.output is False and s.level is None
    sim.rf_on, sim.level = True, 0.0  # 0 dBm com RF ligado: "+000000000E-01"
    s = gen.read_state()
    assert s.output is True and s.level == 0.0


# --- ajustes ----------------------------------------------------------------------------


def test_apply(gen):
    s = gen.apply(frequency=433.92e6, level=-30.5)
    assert (s.frequency, s.level, s.output) == (433.92e6, -30.5, True)
    s = gen.set_output(False)
    assert s.output is False and s.level is None
    s = gen.set_output(True)
    assert s.output is True and s.level == -30.5  # o nível volta ao religar


def test_commands_and_order():
    spy = Spy()
    spy.open()
    gen = MG3601A(InstrumentIO(spy, 13))
    gen.apply(frequency=123456789, level=-20, output=True)
    assert spy.sent == ["FR 123456790HZ", "AP -20.0DBM", "RO"]  # resolução de 10 Hz
    spy.sent.clear()
    gen.apply(frequency=1e6, output=False)
    assert spy.sent == ["RF", "FR 1000000HZ"]  # desliga antes de mexer


def test_limits(gen):
    for kw in ({"frequency": 50e3}, {"frequency": 1.1e9}, {"level": 20}, {"level": -140}, {"level": float("nan")}):
        with pytest.raises(LimitError):
            gen.apply(**kw)
    with pytest.raises(LimitError):
        gen.apply("CH2", level=0)


def test_limit_error_sends_nothing():
    spy = Spy()
    spy.open()
    with pytest.raises(LimitError):
        MG3601A(InstrumentIO(spy, 13)).apply(frequency=1e6, level=99, output=True)
    assert spy.sent == []


def test_instrument_error_is_reported(gen, sim):
    with pytest.raises(InstrumentError, match="SURD"):
        gen.command("FR 5000MHZ")  # fora da faixa: o aparelho acusa no status de erro


# --- API ----------------------------------------------------------------------------------


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_api(client):
    client.post("/api/bus/connect", json={"kind": "sim"})  # simulador tem o MG3601A no endereço 13
    r = client.post("/api/instruments/13/identify").json()
    assert r["driver"]["name"] == "MG3601A"
    eq = client.post("/api/equipment", json={"name": "RF", "address": 13, "driver": "MG3601A"}).json()
    assert client.post(f"/api/equipment/{eq['id']}/check").json()["matches"] is True
    r = client.post(f"/api/equipment/{eq['id']}/rf/RF", json={"frequency": 145e6, "level": -50})
    assert r.status_code == 200 and r.json() == {"channel": "RF", "frequency": 145e6, "level": -50.0, "output": True}
    assert client.post(f"/api/equipment/{eq['id']}/rf/RF", json={"level": 30}).status_code == 422
    psu = client.post("/api/equipment", json={"name": "Fonte", "address": 5, "driver": "E3632A"}).json()
    assert client.post(f"/api/equipment/{psu['id']}/rf/RF", json={}).status_code == 400
