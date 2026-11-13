import math

import pytest

from app.drivers import E3632A, find_driver, identify, list_drivers, open_instrument
from app.drivers.base import Idn, InstrumentIO
from app.drivers.errors import InstrumentError, LimitError, UnknownInstrument
from app.gpib.simulated import SimE3632A, SimInstrument, SimulatedTransport


class SimOther(SimInstrument):
    model = "X1"

    def command(self, header, arg):
        return "ACME,X1,123,1.0" if header == "*IDN?" else None


class Spy(SimulatedTransport):
    """Simulador que registra os comandos enviados (sem as consultas de erro)."""

    def __init__(self):
        super().__init__({5: SimE3632A()})
        self.sent = []

    def write(self, address, command):
        if command != "SYST:ERR?":
            self.sent.append(command)
        super().write(address, command)


@pytest.fixture
def transport():
    t = SimulatedTransport({5: SimE3632A(load_ohms=10.0), 6: SimOther()})
    t.open()
    return t


@pytest.fixture
def psu(transport):
    return E3632A(InstrumentIO(transport, 5))


# --- identificação --------------------------------------------------------


def test_idn_parse():
    idn = Idn.parse("HEWLETT-PACKARD,E3632A,0,1.1-5.0-1.0\n")
    assert (idn.manufacturer, idn.model, idn.serial, idn.firmware) == ("HEWLETT-PACKARD", "E3632A", "0", "1.1-5.0-1.0")
    assert Idn.parse("so-um-campo").model == ""


def test_find_driver_by_model_any_brand():
    for maker in ("HEWLETT-PACKARD", "Agilent Technologies", "Keysight Technologies"):
        assert find_driver(Idn.parse(f"{maker},E3632A,0,2.1")) is E3632A
    assert find_driver(Idn.parse("ACME,X1,0,1")) is None


def test_identify_and_open(transport):
    idn, cls = identify(InstrumentIO(transport, 5))
    assert idn.model == "E3632A" and cls is E3632A
    assert isinstance(open_instrument(InstrumentIO(transport, 5)), E3632A)


def test_unknown_instrument(transport):
    with pytest.raises(UnknownInstrument):
        open_instrument(InstrumentIO(transport, 6))
    with pytest.raises(UnknownInstrument):
        open_instrument(InstrumentIO(transport, 5), driver="NAO_EXISTE")


def test_list_drivers():
    d, dmm, fgen, rf = list_drivers()
    assert rf["name"] == "MG3601A" and rf["type"] == "rf_generator"
    assert dmm["name"] == "K2015" and dmm["type"] == "multimeter"
    assert fgen["name"] == "HP33120A" and fgen["type"] == "function_generator"
    assert d["name"] == "E3632A" and d["type"] == "power_supply"
    assert [r["name"] for r in d["channels"][0]["ranges"]] == ["P15V", "P30V"]


# --- fonte ------------------------------------------------------------------


def test_initial_state(psu):
    s = psu.read_state("OUT")
    assert s.range == "P15V" and s.output is False
    assert s.voltage == 0.0 and s.current == 0.0


def test_apply_cv(psu):
    s = psu.apply("out", voltage=5, current=1, output=True)  # nome do canal sem diferenciar maiúsculas
    assert s.channel == "OUT" and s.output is True
    assert s.voltage_set == 5 and s.current_set == 1
    assert math.isclose(s.voltage, 5) and math.isclose(s.current, 0.5)  # 5 V em 10 Ω


def test_apply_cc(psu):
    s = psu.apply("OUT", voltage=10, current=0.2, output=True)
    assert math.isclose(s.current, 0.2) and math.isclose(s.voltage, 2.0)


def test_range_and_limits(psu):
    with pytest.raises(LimitError):
        psu.set_voltage("OUT", 20)  # P15V vai só até 15,45 V
    s = psu.apply("OUT", range="P30V", voltage=20)  # valida contra a faixa nova
    assert s.range == "P30V" and s.voltage_set == 20
    with pytest.raises(LimitError):
        psu.set_current("OUT", 5)  # P30V vai só até 4,12 A
    for bad in (-1, float("nan")):
        with pytest.raises(LimitError):
            psu.set_voltage("OUT", bad)


def test_invalid_channel_and_range(psu):
    with pytest.raises(LimitError):
        psu.read_state("CH2")
    with pytest.raises(LimitError):
        psu.set_range("OUT", "P60V")


def test_limit_error_sends_nothing():
    t = Spy()
    t.open()
    psu = E3632A(InstrumentIO(t, 5))
    with pytest.raises(LimitError):
        psu.apply("OUT", current=1, voltage=99, output=True)
    assert not any(c.startswith(("CURR ", "VOLT ", "OUTP ")) for c in t.sent)


def test_safe_order():
    t = Spy()
    t.open()
    E3632A(InstrumentIO(t, 5)).apply("OUT", output=True, voltage=3, current=1, range="P30V")
    writes = [c for c in t.sent if not c.endswith("?")]
    assert writes == ["VOLT:RANG P30V", "CURR 1.0000", "VOLT 3.0000", "OUTP ON"]

    t.sent.clear()
    E3632A(InstrumentIO(t, 5)).apply("OUT", output=False, voltage=1)
    writes = [c for c in t.sent if not c.endswith("?")]
    assert writes == ["OUTP OFF", "VOLT 1.0000"]  # desliga primeiro


def test_instrument_error_is_reported(psu, transport):
    with pytest.raises(InstrumentError) as e:
        psu.command("BOBAGEM")
    assert e.value.errors and e.value.errors[0].startswith("-113")
    assert psu.read_errors() == []  # a fila foi esvaziada
