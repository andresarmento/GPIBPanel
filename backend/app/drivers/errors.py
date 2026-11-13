from app.gpib.errors import GpibError


class DriverError(GpibError):
    """Erro na camada de drivers."""

    status_code = 400


class LimitError(DriverError):
    """Valor pedido fora do que o equipamento aceita (canal, faixa, tensão...)."""

    status_code = 422


class InstrumentError(DriverError):
    """O instrumento acusou erro (fila SYST:ERR?) ou respondeu algo inesperado."""

    status_code = 502

    def __init__(self, message: str, errors: list[str] | None = None):
        super().__init__(message)
        self.errors = errors or []


class UnknownInstrument(DriverError):
    """Nenhum driver reconhece o instrumento (ou o driver pedido não existe)."""

    status_code = 404
