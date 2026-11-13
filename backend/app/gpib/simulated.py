"""Transporte simulado: instrumentos virtuais que respondem SCPI.

Serve para desenvolver e testar sem o AR488 conectado.
"""

import random

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
    normalize = staticmethod(normalize_header)

    def handle(self, line: str) -> str | None:
        """Processa uma linha (pode ter vários comandos separados por ';')."""
        replies = []
        for cmd in line.split(";"):
            cmd = cmd.strip()
            if not cmd:
                continue
            header, _, arg = cmd.partition(" ")
            reply = self.command(self.normalize(header), arg.strip())
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


def _norm_keithley(header: str) -> str:
    """':SENSe:VOLTage:DC:RANGe?' -> 'VOLT:DC:RANG?' (mantém DC/AC, tira SENS)."""
    query = header.endswith("?")
    parts = [p.upper() for p in header.rstrip("?").strip(":").split(":") if p]
    if parts and parts[0] in ("SENS", "SENSE"):
        parts = parts[1:]
    parts = [_norm_keyword(p) for p in parts]
    return ":".join(parts) + ("?" if query else "")


class SimK2015(SimInstrument):
    """Multímetro Keithley 2015 virtual, medindo entradas fixas (com um pouco de ruído).

    Faixa manual menor que a entrada responde 9.9E37 (sobrecarga), como o real.
    Com o disparo contínuo desligado (*RST), :DATA:FRES? não responde (timeout).
    """

    model = "MODEL 2015"
    normalize = staticmethod(_norm_keithley)
    FUNCS = {
        "VOLT:DC": (0.1, 1.0, 10.0, 100.0, 1000.0),
        "VOLT:AC": (0.1, 1.0, 10.0, 100.0, 750.0),
        "CURR:DC": (0.01, 0.1, 1.0, 3.0),
        "CURR:AC": (1.0, 3.0),
        "RES": (100.0, 1e3, 10e3, 100e3, 1e6, 10e6, 100e6),
        "FRES": (100.0, 1e3, 10e3, 100e3, 1e6, 10e6, 100e6),
        "FREQ": (),
    }
    ALIASES = {"VOLT": "VOLT:DC", "CURR": "CURR:DC", "RESISTANCE": "RES", "FRESISTANCE": "FRES", "FREQUENCY": "FREQ"}

    def __init__(self, noise: float = 1e-6):
        self.noise = noise
        self.inputs = {
            "VOLT:DC": 1.234567,
            "VOLT:AC": 0.5,
            "CURR:DC": 0.0123,
            "CURR:AC": 0.25,
            "RES": 4700.0,
            "FRES": 4699.5,
            "FREQ": 1000.0,
        }
        self.errors: list[str] = []
        self.init_cont = True  # ligado como no painel frontal
        self.reset()

    def reset(self) -> None:
        self.func = "VOLT:DC"
        self.auto = {f: True for f in self.FUNCS}
        self.range = {f: (r[-1] if r else 0.0) for f, r in self.FUNCS.items()}
        self.nplc = {f: 1.0 for f in self.FUNCS}

    def _err(self, code: int, msg: str) -> None:
        self.errors.append(f'{code},"{msg}"')

    def _effective_range(self, func: str) -> float:
        ranges = self.FUNCS[func]
        if not ranges:
            return 0.0
        if not self.auto[func]:
            return self.range[func]
        x = abs(self.inputs[func])
        return next((r for r in ranges if x <= r), ranges[-1])

    def reading(self) -> float:
        x = self.inputs[self.func]
        rng = self._effective_range(self.func)
        if rng and abs(x) > rng * 1.2:
            return 9.9e37
        return x * (1 + random.uniform(-self.noise, self.noise))

    def _split(self, header: str) -> tuple[str | None, str]:
        """'VOLT:DC:RANG:AUTO' -> ('VOLT:DC', 'RANG:AUTO')"""
        for f in sorted(self.FUNCS, key=len, reverse=True):
            if header == f or header.startswith(f + ":"):
                return f, header[len(f) + 1 :]
        return None, header

    def command(self, header: str, arg: str) -> str | None:
        query = header.endswith("?")
        bare = header.rstrip("?")
        match header:
            case "*IDN?":
                return "KEITHLEY INSTRUMENTS INC.,MODEL 2015,1234567,A01  /A02"
            case "*RST":
                self.reset()
                self.init_cont = False  # no GPIB, *RST desliga o disparo contínuo
                return None
            case "*CLS":
                self.errors.clear()
                return None
            case "SYST:ERR?":
                return self.errors.pop(0) if self.errors else '0,"No error"'
            case "INIT:CONT?":
                return "1" if self.init_cont else "0"
            case "INIT:CONT":
                self.init_cont = arg.upper() in ("ON", "1")
                return None
            case "DATA:FRES?" | "FETC?":
                return fmt(self.reading()) if self.init_cont else None
            case "FUNC?":
                return f'"{self.func}"'
            case "FUNC":
                name = arg.strip("'\"").upper()
                name = self.ALIASES.get(name, name)
                if name in self.FUNCS:
                    self.func = name
                else:
                    self._err(-224, "Illegal parameter value")
                return None

        func, rest = self._split(bare)
        if func is None:
            self._err(-113, "Undefined header")
            return None
        ranges = self.FUNCS[func]
        match rest, query:
            case "RANG", True if ranges:
                return fmt(self._effective_range(func))
            case "RANG", False if ranges:
                try:
                    value = float(arg)
                except ValueError:
                    self._err(-104, "Data type error")
                    return None
                chosen = next((r for r in ranges if value <= r * (1 + 1e-9)), None)
                if chosen is None or value < 0:
                    self._err(-222, "Parameter data out of range")
                else:
                    self.range[func] = chosen
                    self.auto[func] = False
            case "RANG:AUTO", True if ranges:
                return "1" if self.auto[func] else "0"
            case "RANG:AUTO", False if ranges:
                if arg.upper() in ("ON", "1"):
                    self.range[func] = self._effective_range(func)
                    self.auto[func] = True
                elif arg.upper() in ("OFF", "0"):
                    self.range[func] = self._effective_range(func)
                    self.auto[func] = False
                else:
                    self._err(-224, "Illegal parameter value")
            case "NPLC", True if func != "FREQ":
                return fmt(self.nplc[func])
            case "NPLC", False if func != "FREQ":
                try:
                    value = float(arg)
                except ValueError:
                    self._err(-104, "Data type error")
                    return None
                if 0.01 <= value <= 10:
                    self.nplc[func] = value
                else:
                    self._err(-222, "Parameter data out of range")
            case _:
                self._err(-113, "Undefined header")
        return None


class SimHP33120A(SimInstrument):
    """Gerador de funções HP 33120A virtual (1 saída, sempre ativa)."""

    model = "33120A"
    normalize = staticmethod(_norm_keithley)  # mantém "DC" (APPL:DC)
    FUNCS = {"SIN": 15e6, "SQU": 15e6, "TRI": 100e3, "RAMP": 100e3, "NOIS": None, "DC": None}

    def __init__(self):
        self.errors: list[str] = []
        self.reset()

    def reset(self) -> None:
        self.func = "SIN"
        self.freq = 1000.0
        self.ampl = 0.1  # Vpp
        self.offs = 0.0
        self.dcyc = 50.0
        self.load_50 = True
        self.unit = "VPP"

    def _err(self, code: int, msg: str) -> None:
        self.errors.append(f'{code},"{msg}"')

    def _limits(self) -> tuple[float, float, float]:
        return (0.05, 10.0, 5.0) if self.load_50 else (0.1, 20.0, 10.0)

    def _num(self, arg: str, current: float) -> float | None:
        a = arg.strip().upper()
        if a in ("DEF", "DEFAULT", ""):
            return current
        try:
            return float(a)
        except ValueError:
            self._err(-104, "Data type error")
            return None

    def command(self, header: str, arg: str) -> str | None:
        amin, amax, omax = self._limits()
        match header:
            case "*IDN?":
                return "HEWLETT-PACKARD,33120A,0,7.0-5.0-1.0"
            case "*RST":
                self.reset()
            case "*CLS":
                self.errors.clear()
            case "SYST:ERR?":
                return self.errors.pop(0) if self.errors else '+0,"No error"'
            case "FUNC:SHAP?":
                return self.func
            case "FREQ?":
                return f"{self.freq:+.11E}"
            case "VOLT?":
                return f"{self.ampl:+.5E}"
            case "VOLT:UNIT?":
                return self.unit
            case "VOLT:UNIT":
                u = arg.upper()
                if u in ("VPP", "VRMS", "DBM"):
                    self.unit = u
                else:
                    self._err(-224, "Illegal parameter value")
            case "VOLT:OFFS?":
                return f"{self.offs:+.5E}"
            case "PULS:DCYC?":
                return f"{self.dcyc:+.5E}"
            case "PULS:DCYC":
                v = self._num(arg, self.dcyc)
                if v is not None and 20 <= v <= 80:
                    self.dcyc = v
                elif v is not None:
                    self._err(-222, "Data out of range")
            case "OUTP:LOAD?":
                return "+5.00000E+01" if self.load_50 else "+9.90000E+37"
            case "OUTP:LOAD":
                new_50 = {"50": True, "INF": False}.get(arg.upper())
                if new_50 is None:
                    self._err(-224, "Illegal parameter value")
                elif new_50 != self.load_50:
                    k = 0.5 if new_50 else 2.0  # mesmo sinal na saída, outra escala
                    self.ampl *= k
                    self.offs *= k
                    self.load_50 = new_50
            case _ if header.startswith("APPL:"):
                func = header[5:]
                if func not in self.FUNCS:
                    self._err(-113, "Undefined header")
                    return None
                args = [a for a in arg.split(",")] + ["", "", ""]
                freq = self._num(args[0], self.freq)
                ampl = self._num(args[1], self.ampl)
                offs = self._num(args[2], self.offs)
                if None in (freq, ampl, offs):
                    return None
                fmax = self.FUNCS[func]
                if fmax is not None and not 100e-6 <= freq <= fmax:
                    self._err(-222, "Data out of range")
                    return None
                if func != "DC" and not amin <= ampl <= amax:
                    self._err(-222, "Data out of range")
                    return None
                if abs(offs) + (0 if func == "DC" else ampl / 2) > omax:
                    self._err(-221, "Settings conflict")
                    return None
                self.func, self.offs = func, offs
                if fmax is not None:
                    self.freq = freq
                if func != "DC":
                    self.ampl = ampl
            case _:
                self._err(-113, "Undefined header")
        return None


class SimMG3601A(SimInstrument):
    """Gerador de RF Anritsu MG3601A virtual (códigos Anritsu, sem SCPI nem *IDN?).

    Os códigos xxRD escolhem o dado que o aparelho manda nas leituras seguintes.
    """

    model = "MG3601A"
    normalize = staticmethod(lambda h: h.strip().upper())
    _UNITS = {"GHZ": 1e9, "MHZ": 1e6, "KHZ": 1e3, "HZ": 1.0}

    def __init__(self):
        self.reset()

    def reset(self) -> None:
        self.freq = 100e6
        self.level = -10.0  # dBm
        self.rf_on = True
        self.error = 0
        self.talk = "FRRD"  # dado escolhido para as leituras

    @staticmethod
    def _fmt(value: float, exp: int) -> str:
        n = round(abs(value) / 10.0**exp)
        return f"{'-' if value < 0 else '+'}{n:09d}E{exp:+03d}"

    def _reply(self) -> str:
        match self.talk:
            case "FRRD" | "CFRD":
                return self._fmt(self.freq, 0)
            case "APRD" | "OLRD":
                return self._fmt(0, 0) if not self.rf_on else self._fmt(self.level, -1)
            case "SURD":
                return self._fmt(self.error, 0)
            case _:
                return self._fmt(0, 0)

    def handle(self, line: str) -> str | None:
        line = line.strip().upper()
        if line.endswith("RD"):  # pedido de dado: vale para as próximas leituras
            self.talk = line
            return self._reply()
        if line in ("RO", "RF"):
            self.rf_on = line == "RO"
            return None
        if line.startswith(("FR ", "CF ")):
            arg = line[3:].strip()
            unit = next((u for u in self._UNITS if arg.endswith(u)), None)
            try:
                hz = float(arg[: -len(unit)] if unit else arg) * self._UNITS.get(unit, 1.0)
            except ValueError:
                self.error = 1
                return None
            if 0.1e6 <= hz <= 1040e6:
                self.freq = round(hz / 10) * 10
            else:
                self.error = 1
            return None
        if line.startswith(("AP ", "OL ")):
            arg = line[3:].strip()
            try:
                dbm = float(arg[:-3] if arg.endswith("DBM") else arg)
            except ValueError:
                self.error = 1
                return None
            if -133 <= dbm <= 13:
                self.level = round(dbm, 1)
            else:
                self.error = 1
            return None
        if line.endswith("?"):  # ex.: *IDN?: ignorado, mas a leitura traz o último dado pedido
            return self._reply()
        return None  # código desconhecido: ignorado


class SimulatedTransport(Transport):
    kind = "sim"

    def __init__(self, instruments: dict[int, SimInstrument] | None = None):
        self.instruments = instruments if instruments is not None else {5: SimE3632A(), 10: SimHP33120A(), 13: SimMG3601A(), 16: SimK2015()}
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
