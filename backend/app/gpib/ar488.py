"""Transporte via adaptador AR488 (compatível com Prologix GPIB-USB).

O AR488 aparece como uma porta serial. Linhas que começam com "++" são
comandos para o próprio adaptador; o resto é repassado ao instrumento
endereçado com "++addr".
"""

import time

import serial
from serial.tools import list_ports

from app.gpib.errors import GpibError, GpibTimeout
from app.gpib.transport import Transport, check_address

ESC = 0x1B
# Caracteres que precisam de ESC antes para irem como dado ao instrumento
_SPECIAL = {0x0D, 0x0A, ESC, ord("+")}


def escape(data: bytes) -> bytes:
    out = bytearray()
    for b in data:
        if b in _SPECIAL:
            out.append(ESC)
        out.append(b)
    return bytes(out)


def list_serial_ports() -> list[dict]:
    return [{"device": p.device, "description": p.description} for p in list_ports.comports()]


class AR488Transport(Transport):
    kind = "ar488"

    def __init__(
        self,
        port: str,
        baudrate: int = 115200,
        gpib_timeout_ms: int = 2000,
        reset_delay: float = 2.0,
        serial_factory=serial.Serial,
    ):
        self.port = port
        self.baudrate = baudrate
        self.gpib_timeout_ms = gpib_timeout_ms
        # Abrir a serial reinicia o Arduino; esperamos ele dar boot
        self.reset_delay = reset_delay
        self._serial_factory = serial_factory
        self._ser = None
        self._addr: int | None = None
        self.version: str | None = None

    # --- ciclo de vida -------------------------------------------------

    def open(self) -> None:
        serial_timeout = self.gpib_timeout_ms / 1000 + 1.0
        try:
            self._ser = self._serial_factory(
                self.port, self.baudrate, timeout=serial_timeout, write_timeout=serial_timeout
            )
        except (serial.SerialException, OSError) as e:
            raise GpibError(f"Não foi possível abrir {self.port}: {e}") from e

        try:
            if self.reset_delay:
                time.sleep(self.reset_delay)
            self._ser.reset_input_buffer()
            self._send_line(b"++mode 1")  # controlador do barramento
            self._send_line(b"++auto 0")  # não lê automaticamente após escrever
            self._send_line(b"++eoi 1")  # sinaliza EOI no último byte enviado
            self._send_line(b"++eos 2")  # termina comandos com LF
            self._send_line(f"++read_tmo_ms {self.gpib_timeout_ms}".encode())
            self._ser.reset_input_buffer()
            self._send_line(b"++ver")
            try:
                self.version = self._read_line()
            except GpibTimeout:
                raise GpibError(
                    f"O AR488 não respondeu em {self.port}. Confira a porta e o baud rate."
                ) from None
        except Exception:
            self.close()
            raise

    def close(self) -> None:
        if self._ser is not None:
            try:
                self._ser.close()
            except Exception:
                pass
        self._ser = None
        self._addr = None

    # --- operações -------------------------------------------------------

    def write(self, address: int, command: str) -> None:
        self._select(address)
        try:
            data = command.encode("ascii")
        except UnicodeEncodeError:
            raise GpibError("Comando contém caracteres não-ASCII") from None
        self._send_line(escape(data))

    def read(self, address: int) -> str:
        self._select(address)
        self._ser.reset_input_buffer()  # descarta sobras de leituras anteriores
        self._send_line(b"++read eoi")
        return self._read_line()

    def describe(self) -> dict:
        return {
            "kind": self.kind,
            "port": self.port,
            "baudrate": self.baudrate,
            "version": self.version,
        }

    # --- internos --------------------------------------------------------

    def _select(self, address: int) -> None:
        check_address(address)
        if self._ser is None:
            raise GpibError("Porta serial fechada")
        if address != self._addr:
            self._send_line(f"++addr {address}".encode())
            self._addr = address

    def _send_line(self, data: bytes) -> None:
        try:
            self._ser.write(data + b"\n")
        except (serial.SerialException, OSError) as e:
            raise GpibError(f"Erro ao escrever em {self.port}: {e}") from e

    def _read_line(self) -> str:
        try:
            data = self._ser.read_until(b"\n")
        except (serial.SerialException, OSError) as e:
            raise GpibError(f"Erro ao ler de {self.port}: {e}") from e
        if not data.endswith(b"\n"):
            raise GpibTimeout("Sem resposta do instrumento (timeout)")
        return data.decode("ascii", errors="replace").strip()
