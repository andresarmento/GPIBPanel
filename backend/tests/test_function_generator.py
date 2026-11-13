import math

import pytest
from fastapi.testclient import TestClient

from app.drivers import HP33120A, find_driver, identify
from app.drivers.base import Idn, InstrumentIO
from app.drivers.errors import InstrumentError, LimitError
from app.gpib.simulated import SimHP33120A, SimulatedTransport
from app.main import app


class Spy(SimulatedTransport):
    """Simulador que registra os comandos enviados (sem as consultas)."""

    def __init__(self):
        super().__init__({10: SimHP33120A()})
        self.sent = []

    def write(self, address, command):
        if not command.endswith("?"):
            self.sent.append(command)
        super().write(address, command)


@pytest.fixture
def sim():
    return SimHP33120A()


@pytest.fixture
def gen(sim):
    t = SimulatedTransport({10: sim})
    t.open()
    return HP33120A(InstrumentIO(t, 10))


def spy_gen():
    spy = Spy()
    spy.open()
    return spy, HP33120A(InstrumentIO(spy, 10))


# --- identificação e descrição ----------------------------------------------------


def test_identify(gen):
    idn, cls = identify(gen.io)
    assert idn.model == "33120A" and cls is HP33120A
    assert find_driver(Idn.parse("Agilent Technologies,33120A,0,8.0-5.0-1.0")) is HP33120A


def test_describe():
    d = HP33120A.describe()
    assert d["type"] == "function_generator" and d["has_output_switch"] is False
    assert [w["name"] for w in d["waveforms"]] == ["SIN", "SQU", "TRI", "RAMP", "NOISE", "DC"]
    assert d["channels"] == [{"name": "OUT"}] and d["loads"] == ["50", "HIGHZ"]
    assert d["limits"]["50"]["amplitude_max"] == 10 and d["limits"]["HIGHZ"]["amplitude_max"] == 20


# --- leitura ----------------------------------------------------------------------


def test_initial_state(gen):
    s = gen.read_state("OUT")
    assert (s.waveform, s.frequency, s.amplitude, s.offset, s.load) == ("SIN", 1000, 0.1, 0, "50")
    assert s.duty is None and s.output is None
    (ch,) = gen.snapshot()["channels"]
    assert ch["channel"] == "OUT"


def test_amplitude_always_in_vpp(gen, sim):
    sim.unit, sim.ampl = "VRMS", 1.0  # alguém mudou para Vrms no painel frontal
    assert gen.read_state("OUT").amplitude == pytest.approx(2 * math.sqrt(2))
    sim.unit, sim.ampl = "DBM", 10.0  # 10 dBm em 50 Ω = 0,707 Vrms
    assert gen.read_state("OUT").amplitude == pytest.approx(2.0, rel=1e-3)
    gen.set_amplitude("OUT", 1)
    assert sim.unit == "VPP" and sim.ampl == 1


def test_user_waveform_is_reported(gen, sim):
    sim.func = "USER"  # forma arbitrária escolhida no painel frontal
    assert gen.read_state("OUT").waveform == "USER"
    with pytest.raises(LimitError):
        gen.set_frequency("OUT", 100)  # não sabemos os limites da forma arbitrária
    assert gen.set_waveform("OUT", "SIN").waveform == "SIN"


# --- ajustes ----------------------------------------------------------------------


def test_apply_all(gen):
    s = gen.apply("OUT", waveform="SQU", frequency=2500, amplitude=2, offset=0.5, duty=30)
    assert (s.waveform, s.frequency, s.amplitude, s.offset, s.duty) == ("SQU", 2500, 2, 0.5, 30)


def test_one_apply_command():
    spy, gen = spy_gen()
    gen.apply("OUT", waveform="SQU", frequency=1234.5, amplitude=1, offset=-0.25, duty=40)
    assert spy.sent == ["APPL:SQU 1234.5, 1, -0.25", "PULS:DCYC 40"]


def test_partial_keeps_other_values(gen):
    gen.apply("OUT", waveform="TRI", frequency=5000, amplitude=3, offset=1)
    s = gen.set_frequency("OUT", 7000)
    assert (s.waveform, s.frequency, s.amplitude, s.offset) == ("TRI", 7000, 3, 1)


def test_noise_and_dc(gen):
    s = gen.apply("OUT", waveform="NOISE", amplitude=1)
    assert s.waveform == "NOISE" and s.frequency is None and s.amplitude == 1
    s = gen.apply("OUT", waveform="DC", offset=-2.5)
    assert s.waveform == "DC" and s.amplitude is None and s.offset == -2.5
    with pytest.raises(LimitError):
        gen.set_frequency("OUT", 1000)
    with pytest.raises(LimitError):
        gen.set_amplitude("OUT", 1)


def test_load_keeps_signal(gen, sim):
    gen.apply("OUT", amplitude=2, offset=1)
    s = gen.apply("OUT", load="HIGHZ")  # mesmo sinal, valores em alta impedância = dobro
    assert (s.load, s.amplitude, s.offset) == ("HIGHZ", 4, 2)
    s = gen.apply("OUT", load="50", frequency=300)  # troca a carga e ajusta outra coisa junto
    assert (s.load, s.amplitude, s.offset, s.frequency) == ("50", 2, 1, 300)


def test_limits(gen):
    for kw in (
        {"frequency": 20e6},  # seno até 15 MHz
        {"waveform": "TRI", "frequency": 200e3},  # triangular até 100 kHz
        {"amplitude": 0.01},
        {"amplitude": 12},  # 10 Vpp em 50 Ω
        {"amplitude": 8, "offset": 2},  # 2 + 4 > 5 V
        {"offset": float("nan")},
        {"duty": 50},  # seno não tem ciclo de trabalho
        {"waveform": "SQU", "duty": 90},
        {"waveform": "XYZ"},
        {"load": "75"},
        {"output": False},  # 33120A não tem liga/desliga
    ):
        with pytest.raises(LimitError):
            gen.apply("OUT", **kw)
    with pytest.raises(LimitError):
        gen.apply("CH2", amplitude=1)
    # em alta impedância os limites dobram
    assert gen.apply("OUT", load="HIGHZ", amplitude=16, offset=1).amplitude == 16


def test_limit_error_sends_nothing():
    spy, gen = spy_gen()
    with pytest.raises(LimitError):
        gen.apply("OUT", load="HIGHZ", amplitude=30)
    assert spy.sent == []


def test_instrument_error_is_reported(gen):
    with pytest.raises(InstrumentError, match="-113"):
        gen.command("FUNC:SQU:DCYC 50")  # comando que o 33120A não conhece


# --- API ----------------------------------------------------------------------------


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_api(client):
    client.post("/api/bus/connect", json={"kind": "sim"})  # simulador tem o 33120A no endereço 10
    eq = client.post("/api/equipment", json={"name": "Gerador", "address": 10, "driver": "HP33120A"}).json()
    r = client.post(f"/api/equipment/{eq['id']}/fgen/OUT", json={"waveform": "SQU", "frequency": 1e4, "duty": 25})
    assert r.status_code == 200 and r.json()["duty"] == 25 and r.json()["frequency"] == 1e4
    assert client.post(f"/api/equipment/{eq['id']}/fgen/OUT", json={"amplitude": 50}).status_code == 422
    assert client.post(f"/api/equipment/{eq['id']}/fgen/OUT", json={"output": True}).status_code == 422
    psu = client.post("/api/equipment", json={"name": "Fonte", "address": 5, "driver": "E3632A"}).json()
    assert client.post(f"/api/equipment/{psu['id']}/fgen/OUT", json={}).status_code == 400
