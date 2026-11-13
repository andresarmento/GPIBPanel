"""Driver do gerador de funções HP/Agilent 33120A (15 MHz).

Primeira versão: senoidal, quadrada, triangular, rampa, ruído e DC, com
frequência, amplitude (Vpp), offset, ciclo de trabalho e carga.
Modulação (AM/FM/FSK), varredura, burst e formas arbitrárias ficam para depois.

- Uma saída ("OUT") SEM liga/desliga: no 33120A ela está sempre ativa.
- Forma, frequência, amplitude e offset vão juntos num APPLy (evita conflitos
  intermediários entre amplitude e offset). APPLy desliga modulação/varredura.
- A amplitude é sempre em Vpp no GPIBPanel. Se alguém escolher Vrms/dBm no painel
  frontal, a leitura converte para Vpp e o ajuste volta a unidade para Vpp.
- OUTP:LOAD não muda o sinal na saída; muda a escala (com alta impedância, o
  valor programado é o dobro do que seria em 50 Ω) e os limites.
"""

import math

from app.drivers.errors import InstrumentError
from app.drivers.function_generator import FunctionGenerator, Waveform

_TO_SCPI = {"SIN": "SIN", "SQU": "SQU", "TRI": "TRI", "RAMP": "RAMP", "NOISE": "NOIS", "DC": "DC"}
_FROM_SCPI = {"SIN": "SIN", "SQU": "SQU", "TRI": "TRI", "RAMP": "RAMP", "NOIS": "NOISE", "DC": "DC", "USER": "USER"}
# Vpp / Vrms de cada forma (para converter quando o painel frontal está em Vrms/dBm)
_CREST = {"SIN": 2 * math.sqrt(2), "SQU": 2.0, "TRI": 2 * math.sqrt(3), "RAMP": 2 * math.sqrt(3)}
_INFINITE = 9.0e37  # OUTP:LOAD? responde 9.9E37 em alta impedância


class HP33120A(FunctionGenerator):
    name = "HP33120A"
    models = ("33120A",)
    description = "Gerador de funções HP/Agilent 33120A: 15 MHz, 1 saída"
    channels = ("OUT",)
    waveforms = (
        Waveform("SIN", "Senoidal", 15e6, 100e-6),
        Waveform("SQU", "Quadrada", 15e6, 100e-6, duty=True),
        Waveform("TRI", "Triangular", 100e3, 100e-6),
        Waveform("RAMP", "Rampa", 100e3, 100e-6),
        Waveform("NOISE", "Ruído", None),
        Waveform("DC", "DC", None, amplitude=False),
    )
    has_output_switch = False
    duty_min = 20.0
    duty_max = 80.0

    @classmethod
    def limits(cls, load: str) -> dict:
        if load == "50":
            return {"amplitude_min": 0.05, "amplitude_max": 10.0, "offset_max": 5.0}
        return {"amplitude_min": 0.1, "amplitude_max": 20.0, "offset_max": 10.0}

    # --- leitura ---------------------------------------------------------------

    def _read_waveform(self, channel: str) -> str:
        reply = self.io.query("FUNC:SHAP?").strip().upper()
        if reply not in _FROM_SCPI:
            raise InstrumentError(f"Resposta inesperada a FUNC:SHAP?: {reply!r}")
        return _FROM_SCPI[reply]

    def _read_frequency(self, channel: str) -> float:
        return self.io.query_float("FREQ?")

    def _read_amplitude(self, channel: str) -> float | None:
        value = self.io.query_float("VOLT?")
        unit = self.io.query("VOLT:UNIT?").strip().upper()
        if unit == "VPP":
            return value
        crest = _CREST.get(self._read_waveform(channel))
        if crest is None:
            return None  # ruído em Vrms/dBm: sem conversão simples
        vrms = value if unit == "VRMS" else math.sqrt(10 ** (value / 10) / 1000 * 50)  # dBm em 50 Ω
        return vrms * crest

    def _read_offset(self, channel: str) -> float:
        return self.io.query_float("VOLT:OFFS?")

    def _read_duty(self, channel: str) -> float:
        return self.io.query_float("PULS:DCYC?")

    def _read_load(self, channel: str) -> str:
        return "HIGHZ" if self.io.query_float("OUTP:LOAD?") >= _INFINITE else "50"

    # --- ajustes ---------------------------------------------------------------

    def _write_apply(self, channel, waveform, frequency, amplitude, offset) -> None:
        if self.io.query("VOLT:UNIT?").strip().upper() != "VPP":
            self.command("VOLT:UNIT VPP")
        freq = "DEF" if frequency is None else f"{frequency:.10g}"
        amp = "DEF" if amplitude is None else f"{amplitude:.5g}"
        self.command(f"APPL:{_TO_SCPI[waveform]} {freq}, {amp}, {offset:.5g}")

    def _write_duty(self, channel: str, percent: float) -> None:
        self.command(f"PULS:DCYC {percent:.4g}")

    def _write_load(self, channel: str, load: str) -> None:
        self.command("OUTP:LOAD 50" if load == "50" else "OUTP:LOAD INF")
