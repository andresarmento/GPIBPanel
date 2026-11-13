"""Tipo de equipamento: gerador de funções (FunctionGenerator).

Contrato comum a qualquer gerador, com uma ou várias saídas (canais). Em cada
canal: forma de onda, frequência, amplitude (sempre em Vpp), offset, ciclo de
trabalho (quadrada), carga esperada (50 Ω ou alta impedância) e, se o modelo
tiver, liga/desliga da saída.

O resto do sistema (API, telas, scripts) fala só com este contrato; comandos,
limites e particularidades do modelo ficam no driver. A validação e a ordem
das operações ficam aqui, iguais para todos.
"""

from dataclasses import asdict, dataclass

from app.drivers.base import Instrument
from app.drivers.errors import LimitError

LOADS = ("50", "HIGHZ")  # carga esperada na saída: 50 Ω ou alta impedância


@dataclass(frozen=True)
class Waveform:
    name: str  # nome comum (ex.: "SIN"), igual em todos os drivers
    label: str  # texto para a tela (ex.: "Senoidal")
    max_frequency: float | None  # None = forma sem frequência (ruído, DC)
    min_frequency: float = 0.0
    amplitude: bool = True  # False = sem amplitude (DC: o nível é o offset)
    duty: bool = False  # aceita ciclo de trabalho (quadrada)


@dataclass
class GenChannelState:
    channel: str
    waveform: str
    frequency: float | None  # Hz (None se a forma não tem frequência)
    amplitude: float | None  # Vpp (None se a forma não tem amplitude)
    offset: float  # V (em DC, é o nível de saída)
    duty: float | None  # % (só na quadrada)
    load: str  # "50" | "HIGHZ"
    output: bool | None  # None = o modelo não tem liga/desliga (saída sempre ativa)

    def to_dict(self) -> dict:
        return asdict(self)


class FunctionGenerator(Instrument):
    type = "function_generator"
    channels: tuple[str, ...] = ("OUT",)
    waveforms: tuple[Waveform, ...] = ()
    has_output_switch = False  # o modelo tem liga/desliga da saída?
    duty_min = 20.0
    duty_max = 80.0

    @classmethod
    def describe(cls) -> dict:
        return {
            **super().describe(),
            "channels": [{"name": c} for c in cls.channels],
            "waveforms": [asdict(w) for w in cls.waveforms],
            "loads": list(LOADS),
            "has_output_switch": cls.has_output_switch,
            "duty_min": cls.duty_min,
            "duty_max": cls.duty_max,
            "limits": {load: cls.limits(load) for load in LOADS},
        }

    # --- limites (o driver define conforme a carga) -----------------------------

    @classmethod
    def limits(cls, load: str) -> dict:
        """{"amplitude_min", "amplitude_max" (Vpp), "offset_max" (V, |offset| + Vpp/2)}"""
        raise NotImplementedError

    # --- consultas ------------------------------------------------------------

    def channel(self, name: str) -> str:
        for c in self.channels:
            if c.upper() == name.upper():
                return c
        raise LimitError(f"{self.name} não tem o canal {name!r} (canais: {', '.join(self.channels)})")

    def waveform_info(self, name: str) -> Waveform:
        for w in self.waveforms:
            if w.name.upper() == name.upper():
                return w
        names = ", ".join(w.name for w in self.waveforms)
        raise LimitError(f"{self.name} não tem a forma de onda {name!r} (formas: {names})")

    def read_state(self, channel: str) -> GenChannelState:
        ch = self.channel(channel)
        name = self._read_waveform(ch)
        wf = next((w for w in self.waveforms if w.name == name), None)
        return GenChannelState(
            channel=ch,
            waveform=name,  # pode ser uma forma que o GPIBPanel não ajusta (ex.: arbitrária)
            frequency=self._read_frequency(ch) if wf is None or wf.max_frequency is not None else None,
            amplitude=self._read_amplitude(ch) if wf is None or wf.amplitude else None,
            offset=self._read_offset(ch),
            duty=self._read_duty(ch) if wf is not None and wf.duty else None,
            load=self._read_load(ch),
            output=self._read_output(ch) if self.has_output_switch else None,
        )

    def snapshot(self) -> dict:
        return {"channels": [self.read_state(c).to_dict() for c in self.channels]}

    # --- ajustes --------------------------------------------------------------

    def apply(
        self,
        channel: str,
        *,
        waveform: str | None = None,
        frequency: float | None = None,
        amplitude: float | None = None,
        offset: float | None = None,
        duty: float | None = None,
        load: str | None = None,
        output: bool | None = None,
    ) -> GenChannelState:
        """Aplica vários ajustes de uma vez e devolve o estado final.

        Tudo é validado ANTES de mandar qualquer comando (com os valores atuais
        no lugar do que não foi pedido). Ordem: desligar saída → carga → forma,
        frequência, amplitude e offset juntos → ciclo de trabalho → ligar saída.
        """
        ch = self.channel(channel)
        if output is not None and not self.has_output_switch:
            raise LimitError(f"{self.name} não tem liga/desliga da saída (ela fica sempre ativa)")
        if load is not None and load not in LOADS:
            raise LimitError(f"Carga {load!r} inválida (use {' ou '.join(LOADS)})")

        cur = self.read_state(ch)
        wf = self.waveform_info(waveform if waveform is not None else cur.waveform)
        target_load = load if load is not None else cur.load
        lim = self.limits(target_load)
        # Trocar a carga não muda o sinal na saída, só a escala: em alta impedância os
        # valores programados são o dobro dos de 50 Ω. Valores atuais são convertidos.
        scale = {("50", "HIGHZ"): 2.0, ("HIGHZ", "50"): 0.5}.get((cur.load, target_load), 1.0)

        freq = amp = None
        if wf.max_frequency is not None:
            freq = frequency if frequency is not None else cur.frequency
            if freq is None:
                freq = 1000.0
            if frequency is not None or waveform is not None:
                _check("Frequência", freq, wf.min_frequency, wf.max_frequency, "Hz", f"na forma {wf.name}")
        elif frequency is not None:
            raise LimitError(f"A forma {wf.name} não tem frequência")
        if wf.amplitude:
            amp = amplitude if amplitude is not None else (cur.amplitude * scale if cur.amplitude else None)
            if amp is None:
                amp = lim["amplitude_min"]
            if amplitude is not None or waveform is not None or load is not None:
                _check("Amplitude", amp, lim["amplitude_min"], lim["amplitude_max"], "Vpp", _load_text(target_load))
        elif amplitude is not None:
            raise LimitError(f"A forma {wf.name} não tem amplitude (o nível é o offset)")
        off = offset if offset is not None else cur.offset * scale
        if offset is not None or amplitude is not None or waveform is not None or load is not None:
            peak = abs(off) + (amp or 0) / 2
            if not (peak <= lim["offset_max"] + 1e-9):  # também recusa NaN
                raise LimitError(
                    f"|offset| + amplitude/2 = {peak:g} V passa de {lim['offset_max']:g} V {_load_text(target_load)}"
                )
        if duty is not None:
            if not wf.duty:
                raise LimitError(f"A forma {wf.name} não tem ciclo de trabalho")
            _check("Ciclo de trabalho", duty, self.duty_min, self.duty_max, "%", "")

        if output is False:
            self._write_output(ch, False)
        if load is not None:
            self._write_load(ch, load)
        if any(v is not None for v in (waveform, frequency, amplitude, offset)):
            self._write_apply(ch, wf.name, freq, amp, off)
        if wf.duty and (duty is not None or waveform is not None):
            self._write_duty(ch, duty if duty is not None else (cur.duty or 50.0))
        if output is True:
            self._write_output(ch, True)
        return self.read_state(ch)

    def set_waveform(self, channel: str, waveform: str) -> GenChannelState:
        return self.apply(channel, waveform=waveform)

    def set_frequency(self, channel: str, hz: float) -> GenChannelState:
        return self.apply(channel, frequency=hz)

    def set_amplitude(self, channel: str, vpp: float) -> GenChannelState:
        return self.apply(channel, amplitude=vpp)

    def set_offset(self, channel: str, volts: float) -> GenChannelState:
        return self.apply(channel, offset=volts)

    # --- a implementar em cada driver -----------------------------------------
    # waveform é sempre o nome comum (Waveform.name); amplitude sempre em Vpp.

    def _read_waveform(self, channel: str) -> str:
        raise NotImplementedError

    def _read_frequency(self, channel: str) -> float:
        raise NotImplementedError

    def _read_amplitude(self, channel: str) -> float | None:
        raise NotImplementedError

    def _read_offset(self, channel: str) -> float:
        raise NotImplementedError

    def _read_duty(self, channel: str) -> float:
        raise NotImplementedError

    def _read_load(self, channel: str) -> str:
        raise NotImplementedError

    def _read_output(self, channel: str) -> bool:
        raise NotImplementedError

    def _write_apply(
        self, channel: str, waveform: str, frequency: float | None, amplitude: float | None, offset: float
    ) -> None:
        """Forma, frequência, amplitude e offset de uma vez (None = a forma não usa)."""
        raise NotImplementedError

    def _write_duty(self, channel: str, percent: float) -> None:
        raise NotImplementedError

    def _write_load(self, channel: str, load: str) -> None:
        raise NotImplementedError

    def _write_output(self, channel: str, on: bool) -> None:
        raise NotImplementedError


def _load_text(load: str) -> str:
    return "com carga de 50 Ω" if load == "50" else "em alta impedância"


def _check(what: str, value: float, lo: float, hi: float, unit: str, where: str) -> None:
    if not (lo <= value <= hi):  # também recusa NaN
        where = f" {where}" if where else ""
        raise LimitError(f"{what} {value:g} {unit} fora do limite{where} ({lo:g} a {hi:g} {unit})")
