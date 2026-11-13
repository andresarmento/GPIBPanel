import pytest

from app.gpib.errors import GpibTimeout
from app.gpib.simulated import SimE3632A, SimulatedTransport, normalize_header


@pytest.fixture
def sim():
    t = SimulatedTransport()
    t.open()
    return t


def test_normalize_header():
    assert normalize_header("SOURce:VOLTage:LEVel?") == "VOLT?"
    assert normalize_header("voltage:range") == "VOLT:RANG"
    assert normalize_header("MEASure:CURRent:DC?") == "MEAS:CURR?"
    assert normalize_header("OUTPut:STATe") == "OUTP"
    assert normalize_header("*IDN?") == "*IDN?"


def test_idn(sim):
    assert "E3632A" in sim.query(5, "*IDN?")


def test_set_and_read_back(sim):
    sim.write(5, "VOLT 12.5")
    sim.write(5, "CURR 1")
    assert float(sim.query(5, "VOLT?")) == 12.5
    assert float(sim.query(5, "CURR?")) == 1.0


def test_measure_cv_and_cc(sim):
    # carga de 10 ohms
    sim.write(5, "VOLT 5; CURR 1; OUTP ON")
    assert float(sim.query(5, "MEAS:VOLT?")) == pytest.approx(5.0)
    assert float(sim.query(5, "MEAS:CURR?")) == pytest.approx(0.5)
    sim.write(5, "CURR 0.2")  # limita a corrente -> modo CC
    assert float(sim.query(5, "MEAS:CURR?")) == pytest.approx(0.2)
    assert float(sim.query(5, "MEAS:VOLT?")) == pytest.approx(2.0)


def test_output_off_measures_zero(sim):
    sim.write(5, "VOLT 5")
    assert float(sim.query(5, "MEAS:VOLT?")) == 0.0


def test_range_limits(sim):
    sim.write(5, "VOLT 20")  # fora da faixa P15V
    assert sim.query(5, "SYST:ERR?").startswith("-222")
    sim.write(5, "VOLT:RANG P30V")
    sim.write(5, "VOLT 20")
    assert sim.query(5, "VOLT:RANG?") == "P30V"
    assert float(sim.query(5, "VOLT?")) == 20.0
    assert sim.query(5, "SYST:ERR?") == '+0,"No error"'


def test_unknown_command_logs_error(sim):
    sim.write(5, "FOO 1")
    assert sim.query(5, "SYST:ERR?").startswith("-113")


def test_rst(sim):
    sim.write(5, "VOLT 3; OUTP ON")
    sim.write(5, "*RST")
    assert sim.query(5, "OUTP?") == "0"
    assert float(sim.query(5, "VOLT?")) == 0.0


def test_missing_instrument_times_out(sim):
    with pytest.raises(GpibTimeout):
        sim.query(7, "*IDN?")


def test_read_without_query_times_out(sim):
    with pytest.raises(GpibTimeout):
        sim.read(5)


def test_custom_instruments():
    t = SimulatedTransport({3: SimE3632A()})
    t.open()
    assert "E3632A" in t.query(3, "*IDN?")
