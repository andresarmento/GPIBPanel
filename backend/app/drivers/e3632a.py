"""Driver da fonte HP/Agilent/Keysight E3632A.

- 1 saída ("OUT"), duas faixas escolhidas com VOLT:RANG:
  P15V = 0 a 15 V / 7 A e P30V = 0 a 30 V / 4 A
  (o instrumento aceita programar um pouco acima: 15,45 V/7,21 A e 30,9 V/4,12 A).
- Todo comando de ajuste é seguido de SYST:ERR? para pegar recusas do instrumento.
"""

from app.drivers.errors import InstrumentError
from app.drivers.power_supply import Channel, PowerSupply, Range


class E3632A(PowerSupply):
    name = "E3632A"
    models = ("E3632A",)
    description = "Fonte DC E3632A (HP/Agilent/Keysight): 1 saída, 15 V/7 A ou 30 V/4 A"
    channels = (
        Channel(
            "OUT",
            (
                Range("P15V", 15.45, 7.21, "15 V / 7 A"),
                Range("P30V", 30.9, 4.12, "30 V / 4 A"),
            ),
        ),
    )

    def _read_range(self, channel: str) -> str:
        reply = self.io.query("VOLT:RANG?").strip().upper()
        if reply not in ("P15V", "P30V"):
            raise InstrumentError(f"Resposta inesperada a VOLT:RANG?: {reply!r}")
        return reply

    def _write_range(self, channel: str, range_name: str) -> None:
        self.command(f"VOLT:RANG {range_name}")

    def _read_voltage(self, channel: str) -> float:
        return self.io.query_float("VOLT?")

    def _write_voltage(self, channel: str, volts: float) -> None:
        self.command(f"VOLT {volts:.4f}")

    def _read_current(self, channel: str) -> float:
        return self.io.query_float("CURR?")

    def _write_current(self, channel: str, amps: float) -> None:
        self.command(f"CURR {amps:.4f}")

    def _read_output(self, channel: str) -> bool:
        return self.io.query("OUTP?").strip() == "1"

    def _write_output(self, channel: str, on: bool) -> None:
        self.command("OUTP ON" if on else "OUTP OFF")

    def _measure(self, channel: str) -> tuple[float, float]:
        return self.io.query_float("MEAS:VOLT?"), self.io.query_float("MEAS:CURR?")
