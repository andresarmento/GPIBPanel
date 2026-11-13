"""Tipo de equipamento: gerador de RF (RFGenerator).

Contrato comum a geradores de sinal de RF: frequência da portadora, nível de
saída (sempre em dBm) e liga/desliga da saída de RF. Uma saída ("RF"), no
mesmo formato de canais da fonte e do gerador de funções, para as telas
tratarem todos do mesmo jeito.

O resto do sistema (API, telas, scripts) fala só com este contrato; comandos e
limites do modelo ficam no driver. A validação e a ordem das operações ficam aqui.
"""

from dataclasses import asdict, dataclass

from app.drivers.base import Instrument
from app.drivers.errors import LimitError


@dataclass
class RfState:
    channel: str
    frequency: float  # Hz
    level: float | None  # dBm (None se o modelo não informa com o RF desligado)
    output: bool  # saída de RF ligada

    def to_dict(self) -> dict:
        return asdict(self)


class RFGenerator(Instrument):
    type = "rf_generator"
    channels: tuple[str, ...] = ("RF",)
    frequency_min: float = 0.0  # Hz
    frequency_max: float = 0.0
    frequency_resolution: float = 1.0  # Hz
    level_min: float = 0.0  # dBm
    level_max: float = 0.0
    level_resolution: float = 0.1  # dB

    @classmethod
    def describe(cls) -> dict:
        return {
            **super().describe(),
            "channels": [{"name": c} for c in cls.channels],
            "frequency_min": cls.frequency_min,
            "frequency_max": cls.frequency_max,
            "frequency_resolution": cls.frequency_resolution,
            "level_min": cls.level_min,
            "level_max": cls.level_max,
            "level_resolution": cls.level_resolution,
        }

    # --- consultas ------------------------------------------------------------

    def channel(self, name: str) -> str:
        for c in self.channels:
            if c.upper() == name.upper():
                return c
        raise LimitError(f"{self.name} não tem a saída {name!r} (saídas: {', '.join(self.channels)})")

    def read_state(self, channel: str = "RF") -> RfState:
        ch = self.channel(channel)
        level, output = self._read_level_output(ch)
        return RfState(channel=ch, frequency=self._read_frequency(ch), level=level, output=output)

    def snapshot(self) -> dict:
        return {"channels": [self.read_state(c).to_dict() for c in self.channels]}

    # --- ajustes --------------------------------------------------------------

    def apply(
        self,
        channel: str = "RF",
        *,
        frequency: float | None = None,
        level: float | None = None,
        output: bool | None = None,
    ) -> RfState:
        """Aplica vários ajustes de uma vez e devolve o estado final.

        Tudo é validado ANTES de mandar qualquer comando. Ordem:
        desligar RF (se pedido) → frequência → nível → ligar RF (se pedido).
        """
        ch = self.channel(channel)
        if frequency is not None and not (self.frequency_min <= frequency <= self.frequency_max):
            raise LimitError(
                f"Frequência {frequency:g} Hz fora do limite do {self.name} "
                f"({self.frequency_min:g} a {self.frequency_max:g} Hz)"
            )
        if level is not None and not (self.level_min <= level <= self.level_max):
            raise LimitError(
                f"Nível {level:g} dBm fora do limite do {self.name} ({self.level_min:g} a {self.level_max:g} dBm)"
            )

        if output is False:
            self._write_output(ch, False)
        if frequency is not None:
            self._write_frequency(ch, frequency)
        if level is not None:
            self._write_level(ch, level)
        if output is True:
            self._write_output(ch, True)
        return self.read_state(ch)

    def set_frequency(self, hz: float, channel: str = "RF") -> RfState:
        return self.apply(channel, frequency=hz)

    def set_level(self, dbm: float, channel: str = "RF") -> RfState:
        return self.apply(channel, level=dbm)

    def set_output(self, on: bool, channel: str = "RF") -> RfState:
        return self.apply(channel, output=on)

    # --- a implementar em cada driver -----------------------------------------

    def _read_frequency(self, channel: str) -> float:
        raise NotImplementedError

    def _read_level_output(self, channel: str) -> tuple[float | None, bool]:
        """(nível em dBm ou None, saída ligada)"""
        raise NotImplementedError

    def _write_frequency(self, channel: str, hz: float) -> None:
        raise NotImplementedError

    def _write_level(self, channel: str, dbm: float) -> None:
        raise NotImplementedError

    def _write_output(self, channel: str, on: bool) -> None:
        raise NotImplementedError
