"""Tipo de equipamento: multímetro (Multimeter).

Contrato comum a qualquer multímetro de bancada: UMA função ativa por vez
(tensão DC, resistência...), cada uma com sua unidade, suas faixas (ou auto)
e o tempo de integração em NPLC (ciclos da rede: mais = mais lento e mais preciso).

O resto do sistema (API, telas, scripts) fala só com este contrato; os comandos
de cada modelo e a lista de funções/faixas ficam dentro do driver. A validação
dos valores e a ordem das operações ficam aqui, iguais para todos.
"""

import math
from dataclasses import asdict, dataclass

from app.drivers.base import Instrument
from app.drivers.errors import LimitError

# Multímetros SCPI respondem 9.9E37 quando a entrada passa da faixa ("OVERFLOW")
OVERLOAD = 9.0e37
# Folga para comparar faixas (o instrumento devolve 1.000000E+01 para "10")
_TOL = 1e-6


@dataclass(frozen=True)
class Function:
    name: str  # identificador comum (ex.: "DCV"), igual em todos os drivers
    label: str  # texto para a tela (ex.: "Tensão DC")
    unit: str  # unidade da leitura (ex.: "V", "A", "Ω", "Hz")
    ranges: tuple[float, ...] = ()  # faixas manuais (fundo de escala); vazio = só automático
    nplc: bool = True  # aceita ajuste de NPLC


@dataclass
class DmmState:
    function: str
    unit: str
    auto: bool  # faixa automática
    range: float | None  # faixa atual (None se a função não tem faixas)
    nplc: float | None  # None se a função não usa NPLC
    value: float | None  # leitura; None quando em sobrecarga
    overload: bool  # entrada acima da faixa

    def to_dict(self) -> dict:
        return asdict(self)


class Multimeter(Instrument):
    type = "multimeter"
    functions: tuple[Function, ...] = ()
    nplc_min: float = 0.01
    nplc_max: float = 10.0

    @classmethod
    def describe(cls) -> dict:
        return {
            **super().describe(),
            "functions": [asdict(f) for f in cls.functions],
            "nplc_min": cls.nplc_min,
            "nplc_max": cls.nplc_max,
        }

    # --- consultas ------------------------------------------------------------

    def function_info(self, name: str) -> Function:
        for f in self.functions:
            if f.name.upper() == name.upper():
                return f
        names = ", ".join(f.name for f in self.functions)
        raise LimitError(f"{self.name} não tem a função {name!r} (funções: {names})")

    def get_function(self) -> Function:
        return self.function_info(self._read_function())

    def measure(self) -> float:
        """Uma leitura na função atual. Sobrecarga devolve infinito (com o sinal)."""
        return _value(self._read_value())

    def read_state(self) -> DmmState:
        fn = self.get_function()
        auto = self._read_auto(fn.name) if fn.ranges else True
        rng = _nearest(fn, self._read_range(fn.name)) if fn.ranges else None
        nplc = self._read_nplc(fn.name) if fn.nplc else None
        value = _value(self._read_value())
        overload = math.isinf(value)
        return DmmState(
            function=fn.name,
            unit=fn.unit,
            auto=auto,
            range=rng,
            nplc=nplc,
            value=None if overload else value,
            overload=overload,
        )

    def snapshot(self) -> dict:
        return self.read_state().to_dict()

    # --- ajustes --------------------------------------------------------------

    def configure(
        self,
        *,
        function: str | None = None,
        range: float | str | None = None,
        nplc: float | None = None,
    ) -> DmmState:
        """Aplica vários ajustes de uma vez e devolve o estado final.

        - function: "DCV", "ACV", "OHM2"... (ver `functions` do driver)
        - range: "AUTO" ou o maior valor esperado; escolhe a menor faixa que o
          comporta (ex.: 5 em DCV → faixa de 10 V)
        - nplc: tempo de integração, entre nplc_min e nplc_max

        Tudo é validado ANTES de mandar qualquer comando. Ordem: função → NPLC → faixa.
        """
        fn = self.function_info(function) if function is not None else self.get_function()

        auto, target = None, None
        if range is not None:
            if isinstance(range, str):
                if range.strip().upper() != "AUTO":
                    raise LimitError(f"Faixa {range!r} inválida: use \"AUTO\" ou um número")
                auto = True
            else:
                target = _pick_range(fn, range)
            if not fn.ranges:
                if target is not None:
                    raise LimitError(f"A função {fn.name} só tem faixa automática")
                auto = None  # já é automática: nada a fazer
        if nplc is not None:
            if not fn.nplc:
                raise LimitError(f"A função {fn.name} não usa NPLC")
            if not (self.nplc_min <= nplc <= self.nplc_max):  # também recusa NaN
                raise LimitError(f"NPLC {nplc:g} fora do limite ({self.nplc_min:g} a {self.nplc_max:g})")

        if function is not None:
            self._write_function(fn.name)
        if nplc is not None:
            self._write_nplc(fn.name, nplc)
        if auto:
            self._write_auto(fn.name, True)
        if target is not None:
            self._write_range(fn.name, target)  # faixa manual desliga o automático
        return self.read_state()

    def set_function(self, function: str) -> DmmState:
        return self.configure(function=function)

    def set_range(self, range: float | str) -> DmmState:
        return self.configure(range=range)

    def set_nplc(self, nplc: float) -> DmmState:
        return self.configure(nplc=nplc)

    # --- a implementar em cada driver -----------------------------------------
    # `function` é sempre o nome comum (Function.name); o driver traduz.

    def _read_function(self) -> str:
        raise NotImplementedError

    def _write_function(self, function: str) -> None:
        raise NotImplementedError

    def _read_range(self, function: str) -> float:
        raise NotImplementedError

    def _write_range(self, function: str, range: float) -> None:
        """Escolhe a faixa manual (e desliga a automática)."""
        raise NotImplementedError

    def _read_auto(self, function: str) -> bool:
        raise NotImplementedError

    def _write_auto(self, function: str, on: bool) -> None:
        raise NotImplementedError

    def _read_nplc(self, function: str) -> float:
        raise NotImplementedError

    def _write_nplc(self, function: str, nplc: float) -> None:
        raise NotImplementedError

    def _read_value(self) -> float:
        """Uma leitura na função atual (sobrecarga = 9.9E37, como no SCPI)."""
        raise NotImplementedError


def _value(raw: float) -> float:
    if abs(raw) >= OVERLOAD:
        return math.copysign(math.inf, raw)
    return raw


def _pick_range(fn: Function, value: float) -> float:
    if not fn.ranges:
        return value  # tratado por quem chamou
    if not (value > 0):  # também recusa NaN
        raise LimitError(f"Faixa {value:g} inválida para {fn.name}")
    for r in sorted(fn.ranges):
        if value <= r * (1 + _TOL):
            return r
    raise LimitError(f"Faixa {value:g} {fn.unit} acima da maior faixa de {fn.name} ({max(fn.ranges):g} {fn.unit})")


def _nearest(fn: Function, value: float) -> float:
    """Faixa declarada mais próxima do valor que o instrumento devolveu."""
    return min(fn.ranges, key=lambda r: abs(r - value))
