"""Tipo de equipamento: fonte de alimentação (PowerSupply).

Contrato comum a qualquer fonte, com um ou vários canais. O resto do sistema
(API, telas, scripts) fala só com este contrato; o que é específico de um
modelo (comandos, nomes de faixa, limites) fica dentro do driver.

O driver implementa os métodos `_read_*`, `_write_*` e `_measure`. A validação
de limites e a ordem segura das operações ficam aqui, iguais para todas as fontes.
"""

from dataclasses import asdict, dataclass

from app.drivers.base import Instrument
from app.drivers.errors import LimitError


@dataclass(frozen=True)
class Range:
    name: str  # nome que o driver entende (ex.: "P15V")
    max_voltage: float
    max_current: float
    label: str = ""  # texto para a tela (ex.: "15 V / 7 A")


@dataclass(frozen=True)
class Channel:
    name: str
    ranges: tuple[Range, ...]


@dataclass
class ChannelState:
    channel: str
    range: str
    output: bool
    voltage_set: float  # tensão programada
    current_set: float  # limite de corrente programado
    voltage: float  # tensão medida na saída
    current: float  # corrente medida na saída

    def to_dict(self) -> dict:
        return asdict(self)


class PowerSupply(Instrument):
    type = "power_supply"
    channels: tuple[Channel, ...] = ()

    @classmethod
    def describe(cls) -> dict:
        return {**super().describe(), "channels": [asdict(c) for c in cls.channels]}

    # --- consultas ------------------------------------------------------------

    def channel(self, name: str) -> Channel:
        for c in self.channels:
            if c.name.upper() == name.upper():
                return c
        names = ", ".join(c.name for c in self.channels)
        raise LimitError(f"{self.name} não tem o canal {name!r} (canais: {names})")

    def range_info(self, channel: str, range_name: str) -> Range:
        ch = self.channel(channel)
        for r in ch.ranges:
            if r.name.upper() == range_name.upper():
                return r
        names = ", ".join(r.name for r in ch.ranges)
        raise LimitError(f"Faixa {range_name!r} inválida para {ch.name} (faixas: {names})")

    def get_range(self, channel: str) -> Range:
        ch = self.channel(channel)
        if len(ch.ranges) == 1:
            return ch.ranges[0]
        return self.range_info(ch.name, self._read_range(ch.name))

    def measure(self, channel: str) -> tuple[float, float]:
        """(tensão, corrente) medidas na saída."""
        return self._measure(self.channel(channel).name)

    def read_state(self, channel: str) -> ChannelState:
        ch = self.channel(channel).name
        rng = self.get_range(ch)
        voltage, current = self._measure(ch)
        return ChannelState(
            channel=ch,
            range=rng.name,
            output=self._read_output(ch),
            voltage_set=self._read_voltage(ch),
            current_set=self._read_current(ch),
            voltage=voltage,
            current=current,
        )

    def snapshot(self) -> dict:
        return {"channels": [self.read_state(c.name).to_dict() for c in self.channels]}

    # --- ajustes --------------------------------------------------------------

    def apply(
        self,
        channel: str,
        *,
        range: str | None = None,
        voltage: float | None = None,
        current: float | None = None,
        output: bool | None = None,
    ) -> ChannelState:
        """Aplica vários ajustes de uma vez, numa ordem segura, e devolve o estado final.

        Tudo é validado ANTES de mandar qualquer comando. Ordem:
        desligar saída (se pedido) → faixa → corrente → tensão → ligar saída (se pedido).
        """
        ch = self.channel(channel)
        target = self.range_info(ch.name, range) if range is not None else self.get_range(ch.name)
        if voltage is not None:
            _check("Tensão", voltage, target.max_voltage, "V", target)
        if current is not None:
            _check("Corrente", current, target.max_current, "A", target)

        if output is False:
            self._write_output(ch.name, False)
        if range is not None:
            self._write_range(ch.name, target.name)
        if current is not None:
            self._write_current(ch.name, current)
        if voltage is not None:
            self._write_voltage(ch.name, voltage)
        if output is True:
            self._write_output(ch.name, True)
        return self.read_state(ch.name)

    def set_voltage(self, channel: str, volts: float) -> ChannelState:
        return self.apply(channel, voltage=volts)

    def set_current(self, channel: str, amps: float) -> ChannelState:
        return self.apply(channel, current=amps)

    def set_output(self, channel: str, on: bool) -> ChannelState:
        return self.apply(channel, output=on)

    def set_range(self, channel: str, range_name: str) -> ChannelState:
        return self.apply(channel, range=range_name)

    # --- a implementar em cada driver -----------------------------------------

    def _read_range(self, channel: str) -> str:
        raise NotImplementedError

    def _write_range(self, channel: str, range_name: str) -> None:
        raise NotImplementedError

    def _read_voltage(self, channel: str) -> float:
        raise NotImplementedError

    def _write_voltage(self, channel: str, volts: float) -> None:
        raise NotImplementedError

    def _read_current(self, channel: str) -> float:
        raise NotImplementedError

    def _write_current(self, channel: str, amps: float) -> None:
        raise NotImplementedError

    def _read_output(self, channel: str) -> bool:
        raise NotImplementedError

    def _write_output(self, channel: str, on: bool) -> None:
        raise NotImplementedError

    def _measure(self, channel: str) -> tuple[float, float]:
        raise NotImplementedError


def _check(what: str, value: float, maximum: float, unit: str, rng: Range) -> None:
    # "not (a <= x <= b)" também recusa NaN
    if not (0.0 <= value <= maximum):
        raise LimitError(f"{what} {value:g} {unit} fora do limite da faixa {rng.name} (0 a {maximum:g} {unit})")
