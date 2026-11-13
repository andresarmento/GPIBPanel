from abc import ABC, abstractmethod

from app.gpib.errors import GpibError

MIN_ADDRESS = 0
MAX_ADDRESS = 30


def check_address(address: int) -> None:
    if not MIN_ADDRESS <= address <= MAX_ADDRESS:
        raise GpibError(f"Endereço GPIB inválido: {address} (use {MIN_ADDRESS} a {MAX_ADDRESS})")


class Transport(ABC):
    """Interface comum a qualquer forma de falar com o barramento GPIB.

    Os métodos são bloqueantes e NÃO são thread-safe: quem garante que só uma
    operação acontece por vez é o GpibBus (fila única).
    """

    kind: str = "?"

    @abstractmethod
    def open(self) -> None: ...

    @abstractmethod
    def close(self) -> None: ...

    @abstractmethod
    def write(self, address: int, command: str) -> None:
        """Envia um comando ao instrumento no endereço dado."""

    @abstractmethod
    def read(self, address: int) -> str:
        """Lê uma resposta do instrumento (sem o terminador)."""

    def query(self, address: int, command: str) -> str:
        self.write(address, command)
        return self.read(address)

    @abstractmethod
    def describe(self) -> dict:
        """Informações para exibir na tela (tipo, porta, versão...)."""
