"""Transporte simulado: instrumentos virtuais que respondem SCPI.

Serve para desenvolver e testar sem o AR488 conectado.
"""

from app.gpib.errors import GpibError, GpibTimeout
from app.gpib.transport import Transport, check_address

# Formas longas das palavras-chave SCPI -> forma curta
_KEYWORDS = {
    "VOLTAGE": "VOLT",
    "CURRENT": "CURR",
    "OUTPUT": "OUTP",
    "MEASURE": "MEAS",
    "RANGE": "RANG",
    "SOURCE": "SOUR",
    "SYSTEM": "SYST",
    "ERROR": "ERR",
    "STATE": "STAT",
    "LEVEL": "LEV",
    "IMMEDIATE": "IMM",
    "AMPLITUDE": "AMPL",
    "SCALAR": "SCAL",
}
# Palavras opcionais que podem ser omitidas
_OPTIONAL = {"SOUR", "LEV", "IMM", "AMPL", "DC", "SCAL", "STAT"}


def _norm_keyword(kw: str) -> str:
    kw = kw.upper()
    for long, short in _KEYWORDS.items():
        if kw.startswith(short) and long.startswith(kw):
            return short
    return kw


def normalize_header(header: str) -> str:
    """'SOURce:VOLTage:LEVel?' -> 'VOLT?'"""
    query = header.endswith("?")
    parts = [_norm_keyword(p) for p in header.rstrip("?").strip(":").split(":") if p]
    parts = [p for p in parts if p not in _OPTIONAL] or parts
    return ":".join(parts) + ("?" if query else "")


def fmt(value: float) -> str:
    return f"{value:+.8E}"


class SimInstrument:
    model = "?"

    def handle(self, line: str) -> str | None:
        """Processa uma linha (pode ter vários comandos separados por ';')."""
        replies = []
        for cmd in line.split(";"):
            cmd = cmd.strip()
            if not cmd:
                continue
            header, _, arg = cmd.partition(" ")
            reply = self.command(normalize_header(header), arg.strip())
            if reply is not None:
                replies.append(reply)
        return ";".join(replies) if replies else None

    def command(self, header: str, arg: str) -> str | None:
        raise NotImplementedError


class SimE3632A(SimInstrument):
    """Fonte HP/Agilent E3632A virtual: 1 saída, faixas P15V (15 V/7 A) e P30V (30 V/4 A).

    A saída alimenta uma carga resistiva fixa, para que as medições façam sentido
    (modo CV ou CC conforme o limite de corrente).
    """

    model = "E3632A"
    RANGES = {"P15V": (15.45, 7.21), "P30V": (30.9, 4.12)}

    def __init__(self, load_ohms: float = 10.0):
        self.load_ohms = load_ohms
        self.errors: list[str] = []
        self.reset()

    def reset(self) -> None:
        self.range = "P15V"
        self.volt = 0.0
        self.curr = 7.0
        self.output = False

    def _err(self, code: int, msg: str) -> None:
        self.errors.append(f'{code},"{msg}"')

    def _number(self, arg: str, maximum: float) -> float | None:
        a = arg.upper()
        if a in ("MAX", "MAXIMUM"):
            return maximum
        if a in ("MIN", "MINIMUM"):
            return 0.0
        try:
            value = float(arg)
        except ValueError:
            self._err(-104, "Data type error")
            return None
        if not 0.0 <= value <= maximum:
            self._err(-222, "Data out of range")
            return None
        return value

    def measure(self) -> tuple[float, float]:
        if not self.output:
            return 0.0, 0.0
        i = self.volt / self.load_ohms
        if i <= self.curr:
            return self.volt, i  # tensão constante (CV)
        return self.curr * self.load_ohms, self.curr  # corrente constante (CC)

    def command(self, header: str, arg: str) -> str | None:
        vmax, imax = self.RANGES[self.range]
        match header:
            case "*IDN?":
                return "HEWLETT-PACKARD,E3632A,0,1.1-5.0-1.0"
            case "*RST":
                self.reset()
            case "*CLS":
                self.errors.clear()
            case "*OPC?":
                return "1"
            case "SYST:ERR?":
                return self.errors.pop(0) if self.errors else '+0,"No error"'
            case "VOLT":
                v = self._number(arg, vmax)
                if v is not None:
                    self.volt = v
            case "VOLT?":
                return fmt(self.volt)
            case "CURR":
                i = self._number(arg, imax)
                if i is not None:
                    self.curr = i
            case "CURR?":
                return fmt(self.curr)
            case "VOLT:RANG":
                r = {"P15V": "P15V", "LOW": "P15V", "P30V": "P30V", "HIGH": "P30V"}.get(arg.upper())
                if r is None:
                    self._err(-224, "Illegal parameter value")
                else:
                    self.range = r
                    vmax, imax = self.RANGES[r]
                    self.volt = min(self.volt, vmax)
                    self.curr = min(self.curr, imax)
            case "VOLT:RANG?":
                return self.range
            case "OUTP":
                state = {"ON": True, "1": True, "OFF": False, "0": False}.get(arg.upper())
                if state is None:
                    self._err(-224, "Illegal parameter value")
                else:
                    self.output = state
            case "OUTP?":
                return "1" if self.output else "0"
            case "MEAS:VOLT?":
                return fmt(self.measure()[0])
            case "MEAS:CURR?":
                return fmt(self.measure()[1])
            case _:
                self._err(-113, "Undefined header")
        return None


class SimulatedTransport(Transport):
    kind = "sim"

    def __init__(self, instruments: dict[int, SimInstrument] | None = None):
        self.instruments = instruments if instruments is not None else {5: SimE3632A()}
        self._output: dict[int, str] = {}
        self._open = False

    def open(self) -> None:
        self._open = True

    def close(self) -> None:
        self._open = False
        self._output.clear()

    def _instrument(self, address: int) -> SimInstrument:
        check_address(address)
        if not self._open:
            raise GpibError("Simulador fechado")
        inst = self.instruments.get(address)
        if inst is None:
            raise GpibTimeout(f"Nenhum instrumento simulado no endereço {address}")
        return inst

    def write(self, address: int, command: str) -> None:
        reply = self._instrument(address).handle(command)
        if reply is not None:
            self._output[address] = reply

    def read(self, address: int) -> str:
        self._instrument(address)
        reply = self._output.pop(address, None)
        if reply is None:
            raise GpibTimeout("Sem resposta do instrumento (timeout)")
        return reply

    def describe(self) -> dict:
        return {
            "kind": self.kind,
            "port": None,
            "version": "Simulador GPIBPanel",
            "instruments": {addr: inst.model for addr, inst in self.instruments.items()},
        }
