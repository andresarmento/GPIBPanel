"""Drivers de instrumentos e o registro que escolhe o driver pelo *IDN?.

Para adicionar um modelo: crie o driver (subclasse de um tipo, ex. PowerSupply)
e coloque a classe em DRIVERS abaixo.
"""

from app.drivers.base import Idn, Instrument, InstrumentIO
from app.drivers.e3632a import E3632A
from app.drivers.errors import UnknownInstrument

DRIVERS: dict[str, type[Instrument]] = {cls.name: cls for cls in (E3632A,)}


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
    """Pergunta *IDN? e devolve a identificação e o driver que a reconhece (ou None)."""
    idn = Idn.parse(io.query("*IDN?"))
    return idn, find_driver(idn)


def open_instrument(io: InstrumentIO, driver: str | None = None) -> Instrument:
    """Cria o driver: o indicado pelo nome, ou o identificado pelo *IDN?."""
    if driver is not None:
        return get_driver(driver)(io)
    idn, cls = identify(io)
    if cls is None:
        raise UnknownInstrument(f"Nenhum driver para {idn.raw!r} (endereço {io.address})")
    return cls(io)
