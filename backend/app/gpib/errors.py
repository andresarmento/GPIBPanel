from app.errors import AppError


class GpibError(AppError):
    """Erro genérico de comunicação GPIB."""

    status_code = 502


class GpibTimeout(GpibError):
    """O instrumento não respondeu a tempo."""

    status_code = 504


class NotConnected(GpibError):
    """Nenhum transporte conectado ao barramento."""

    status_code = 409
