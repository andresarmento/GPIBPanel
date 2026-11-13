"""Base de todos os drivers.

Um driver é síncrono e conversa com UM instrumento através de um InstrumentIO.
Ele deve rodar sempre DENTRO da fila do barramento, por exemplo:

    bus.transaction(lambda t: E3632A(InstrumentIO(t, 5)).read_state("OUT"))

Assim uma sequência (comando + checagem de erro, várias leituras...) nunca é
interrompida por outro pedido no meio.
"""

from dataclasses import asdict, dataclass

from app.drivers.errors import InstrumentError
from app.gpib.transport import Transport


@dataclass(frozen=True)
class Idn:
    """Resposta do *IDN? separada em campos: fabricante,modelo,série,firmware."""

    manufacturer: str
    model: str
    serial: str
    firmware: str
    raw: str

    @classmethod
    def parse(cls, raw: str) -> "Idn":
        parts = [p.strip() for p in raw.strip().split(",", 3)]
        parts += [""] * (4 - len(parts))
        return cls(*parts, raw=raw.strip())

    def to_dict(self) -> dict:
        return asdict(self)


class InstrumentIO:
    """Acesso a um instrumento num endereço. NÃO é thread-safe: use dentro da fila."""

    def __init__(self, transport: Transport, address: int):
        self.transport = transport
        self.address = address

    def write(self, command: str) -> None:
        self.transport.write(self.address, command)

    def query(self, command: str) -> str:
        return self.transport.query(self.address, command)

    def query_float(self, command: str) -> float:
        reply = self.query(command)
        try:
            return float(reply)
        except ValueError:
            raise InstrumentError(f"Resposta inesperada a {command!r}: {reply!r}") from None


class Instrument:
    """Base de qualquer driver. Subclasses definem `name`, `models` e o tipo."""

    name: str = "?"  # identificador do driver (ex.: "E3632A")
    type: str = "generic"  # tipo de equipamento (ex.: "power_supply")
    models: tuple[str, ...] = ()  # modelos que aparecem no *IDN? e este driver atende
    description: str = ""
    max_errors = 20  # limite de leituras da fila de erros (evita laço infinito)

    def __init__(self, io: InstrumentIO):
        self.io = io

    @classmethod
    def matches(cls, idn: Idn) -> bool:
        return idn.model.upper() in {m.upper() for m in cls.models}

    @classmethod
    def describe(cls) -> dict:
        return {"name": cls.name, "type": cls.type, "models": list(cls.models), "description": cls.description}

    def snapshot(self) -> dict:
        """Tudo o que a tela precisa mostrar do instrumento, numa leitura só.

        É o que a leitura automática (Fase 4) chama a cada ciclo. Cada tipo de
        equipamento define o formato.
        """
        raise NotImplementedError

    # --- SCPI comum ------------------------------------------------------

    def identify(self) -> Idn:
        return Idn.parse(self.io.query("*IDN?"))

    def read_errors(self) -> list[str]:
        """Esvazia a fila de erros do instrumento (SYST:ERR?) e devolve o que havia."""
        errors = []
        for _ in range(self.max_errors):
            reply = self.io.query("SYST:ERR?")
            code = reply.split(",", 1)[0].strip()
            try:
                if int(code) == 0:
                    break
            except ValueError:
                raise InstrumentError(f"Resposta inesperada a SYST:ERR?: {reply!r}") from None
            errors.append(reply)
        return errors

    def command(self, command: str) -> None:
        """Envia um comando e confere se o instrumento acusou erro."""
        self.io.write(command)
        errors = self.read_errors()
        if errors:
            raise InstrumentError(f"{self.name} recusou {command!r}: {'; '.join(errors)}", errors)
