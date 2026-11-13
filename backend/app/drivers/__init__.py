"""Drivers de instrumentos e o registro que escolhe o driver pelo *IDN?.

Para adicionar um modelo: crie o driver (subclasse de um tipo, ex. PowerSupply ou Multimeter)
e coloque a classe em DRIVERS abaixo.
"""

from app.drivers.base import Idn, Instrument, InstrumentIO
from app.drivers.e3632a import E3632A
from app.drivers.errors import UnknownInstrument
from app.drivers.hp33120a import HP33120A
from app.drivers.k2015 import K2015
from app.drivers.mg3601a import MG3601A
from app.gpib.errors import GpibTimeout

DRIVERS: dict[str, type[Instrument]] = {cls.name: cls for cls in (E3632A, K2015, HP33120A, MG3601A)}


def list_drivers() -> list[dict]:
    return [cls.describe() for cls in DRIVERS.values()]


def get_driver(name: str) -> type[Instrument]:
    try:
        return DRIVERS[name]
    except KeyError:
        raise UnknownInstrument(f"Driver {name!r} não existe") from None


def find_driver(idn: Idn) -> type[Instrument] | None:
    for cls in DRIVERS.values():
        if cls.matches(idn):
            return cls
    return None


def identify(io: InstrumentIO) -> tuple[Idn, type[Instrument] | None]:
    """Identifica o instrumento no endereço: devolve a identificação e o driver (ou None).

    Primeiro pergunta *IDN?. Se ninguém responder, ou se a resposta não tiver o
    formato "fabricante,modelo,série,firmware", tenta os drivers de aparelhos sem
    *IDN? (anteriores ao IEEE 488.2), cada um com sua consulta de leitura (probe).
    Ex.: o Anritsu MG3601A ignora o *IDN? e, na leitura, manda o último dado pedido
    (a frequência). Um aparelho SCPI nunca chega aos probes.
    """
    try:
        reply = io.query("*IDN?")
    except GpibTimeout:
        reply = None
    if reply is not None and "," in reply:
        idn = Idn.parse(reply)
        return idn, find_driver(idn)
    for cls in DRIVERS.values():
        probe = getattr(cls, "probe", None)
        if probe is not None:
            found = probe(io)
            if found is not None:
                return found, cls
    if reply is None:
        raise GpibTimeout(f"Nenhum instrumento respondeu no endereço {io.address}")
    return Idn.parse(reply), None


def open_instrument(io: InstrumentIO, driver: str | None = None) -> Instrument:
    """Cria o driver: o indicado pelo nome, ou o identificado pelo *IDN?."""
    if driver is not None:
        return get_driver(driver)(io)
    idn, cls = identify(io)
    if cls is None:
        raise UnknownInstrument(f"Nenhum driver para {idn.raw!r} (endereço {io.address})")
    return cls(io)
