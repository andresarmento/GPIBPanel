class AppError(Exception):
    """Erro com mensagem para o usuário; vira JSON {"detail": ...} com status_code."""

    status_code = 500


class NotFound(AppError):
    status_code = 404


class Conflict(AppError):
    status_code = 409


class Invalid(AppError):
    status_code = 422
