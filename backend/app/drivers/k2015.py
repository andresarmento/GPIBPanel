"""Driver do multímetro Keithley 2015 (THD multimeter, 6½ dígitos).

Primeira versão: DCV, ACV, DCI, ACI, Ω 2 fios, Ω 4 fios e frequência.
Distorção (THD/THD+N/SINAD) e o gerador interno ficam para depois.

Leitura: o 2015 fica em disparo contínuo (INIT:CONT ON, como no painel frontal)
e pedimos a próxima leitura nova com :SENS:DATA:FRES?. Assim o display do
aparelho continua atualizando entre uma consulta e outra. Se o disparo contínuo
estiver desligado (ex.: depois de *RST), o driver religa antes de ler.

⚠ A confirmar no hardware: o formato da resposta de :SENS:DATA:FRES? e
:SENS:FUNC?, e as faixas de Ω 4 fios.
"""

import re

from app.drivers.errors import InstrumentError
from app.drivers.multimeter import Function, Multimeter

# Nome comum -> nome SCPI da função no 2015
_SCPI = {
    "DCV": "VOLT:DC",
    "ACV": "VOLT:AC",
    "DCI": "CURR:DC",
    "ACI": "CURR:AC",
    "OHM2": "RES",
    "OHM4": "FRES",
    "FREQ": "FREQ",
}
# Resposta de :SENS:FUNC? (palavras cortadas em 4 letras) -> nome comum
_FROM_SCPI = {
    "VOLT:DC": "DCV",
    "VOLT:AC": "ACV",
    "CURR:DC": "DCI",
    "CURR:AC": "ACI",
    "RES": "OHM2",
    "RESI": "OHM2",
    "FRES": "OHM4",
    "FREQ": "FREQ",
}
_NUMBER = re.compile(r"^\s*([+-]?(?:\d+\.?\d*|\.\d+)(?:[Ee][+-]?\d+)?)")

_OHMS = (100.0, 1e3, 10e3, 100e3, 1e6, 10e6, 100e6)


class K2015(Multimeter):
    name = "K2015"
    models = ("MODEL 2015", "MODEL 2015P")
    description = "Multímetro Keithley 2015 (6½ dígitos, THD): V, A, Ω 2/4 fios, frequência"
    functions = (
        Function("DCV", "Tensão DC", "V", (0.1, 1.0, 10.0, 100.0, 1000.0)),
        Function("ACV", "Tensão AC", "V", (0.1, 1.0, 10.0, 100.0, 750.0)),
        Function("DCI", "Corrente DC", "A", (0.01, 0.1, 1.0, 3.0)),
        Function("ACI", "Corrente AC", "A", (1.0, 3.0)),
        Function("OHM2", "Resistência 2 fios", "Ω", _OHMS),
        Function("OHM4", "Resistência 4 fios", "Ω", _OHMS),
        Function("FREQ", "Frequência", "Hz", (), nplc=False),
    )
    nplc_min = 0.01
    nplc_max = 10.0
    read_command = ":SENS:DATA:FRES?"

    def _read_function(self) -> str:
        reply = self.io.query(":SENS:FUNC?")
        key = ":".join(p[:4] for p in reply.strip().strip('"').upper().split(":"))
        try:
            return _FROM_SCPI[key]
        except KeyError:
            raise InstrumentError(f"Função não suportada pelo GPIBPanel: {reply.strip()!r}") from None

    def _write_function(self, function: str) -> None:
        self.command(f":SENS:FUNC '{_SCPI[function]}'")

    def _read_range(self, function: str) -> float:
        return self.io.query_float(f":SENS:{_SCPI[function]}:RANG?")

    def _write_range(self, function: str, range: float) -> None:
        self.command(f":SENS:{_SCPI[function]}:RANG {range:g}")

    def _read_auto(self, function: str) -> bool:
        return self.io.query(f":SENS:{_SCPI[function]}:RANG:AUTO?").strip() == "1"

    def _write_auto(self, function: str, on: bool) -> None:
        self.command(f":SENS:{_SCPI[function]}:RANG:AUTO {'ON' if on else 'OFF'}")

    def _read_nplc(self, function: str) -> float:
        return self.io.query_float(f":SENS:{_SCPI[function]}:NPLC?")

    def _write_nplc(self, function: str, nplc: float) -> None:
        self.command(f":SENS:{_SCPI[function]}:NPLC {nplc:g}")

    def _read_value(self) -> float:
        if self.io.query(":INIT:CONT?").strip() != "1":
            self.command(":INIT:CONT ON")
        return parse_reading(self.io.query(self.read_command))


def parse_reading(reply: str) -> float:
    """'+1.23456789E+00' ou '+1.23456789E+00VDC,...' -> 1.23456789"""
    m = _NUMBER.match(reply.split(",", 1)[0])
    if not m:
        raise InstrumentError(f"Leitura inesperada do multímetro: {reply.strip()!r}")
    return float(m.group(1))
