"""Testa o protocolo do AR488 com uma porta serial falsa."""

import pytest

from app.gpib.ar488 import AR488Transport, escape
from app.gpib.errors import GpibError, GpibTimeout


class FakeSerial:
    def __init__(self, replies=None, version=b"AR488 GPIB controller, ver. test\r\n"):
        self.written: list[bytes] = []
        self.buffer = b""
        self.replies = list(replies or [])
        self.version = version
        self.closed = False

    def write(self, data: bytes) -> None:
        self.written.append(data)
        if data == b"++ver\n" and self.version:
            self.buffer += self.version
        elif data == b"++read eoi\n" and self.replies:
            self.buffer += self.replies.pop(0)

    def read_until(self, terminator: bytes) -> bytes:
        i = self.buffer.find(terminator)
        if i < 0:  # simula timeout: devolve o que tiver
            data, self.buffer = self.buffer, b""
            return data
        data, self.buffer = self.buffer[: i + 1], self.buffer[i + 1 :]
        return data

    def reset_input_buffer(self) -> None:
        self.buffer = b""

    def close(self) -> None:
        self.closed = True


def make(fake: FakeSerial) -> AR488Transport:
    t = AR488Transport("COM9", reset_delay=0, serial_factory=lambda *a, **k: fake)
    t.open()
    return t


def test_open_configures_controller():
    fake = FakeSerial()
    t = make(fake)
    assert fake.written[:4] == [b"++mode 1\n", b"++auto 0\n", b"++eoi 1\n", b"++eos 2\n"]
    assert t.version == "AR488 GPIB controller, ver. test"


def test_open_without_answer_fails_and_closes():
    fake = FakeSerial(version=None)
    with pytest.raises(GpibError):
        make(fake)
    assert fake.closed


def test_query_addresses_and_reads():
    fake = FakeSerial(replies=[b"HEWLETT-PACKARD,E3632A,0,1.1\n"])
    t = make(fake)
    fake.written.clear()
    assert t.query(5, "*IDN?") == "HEWLETT-PACKARD,E3632A,0,1.1"
    assert fake.written == [b"++addr 5\n", b"*IDN?\n", b"++read eoi\n"]


def test_address_only_sent_when_changed():
    fake = FakeSerial()
    t = make(fake)
    fake.written.clear()
    t.write(5, "OUTP ON")
    t.write(5, "OUTP OFF")
    t.write(6, "*RST")
    assert fake.written == [b"++addr 5\n", b"OUTP ON\n", b"OUTP OFF\n", b"++addr 6\n", b"*RST\n"]


def test_special_chars_are_escaped():
    assert escape(b"VOLT +5") == b"VOLT \x1b+5"
    assert escape(b"++ver") == b"\x1b+\x1b+ver"


def test_read_timeout():
    t = make(FakeSerial())
    with pytest.raises(GpibTimeout):
        t.query(5, "*IDN?")


def test_invalid_address():
    t = make(FakeSerial())
    with pytest.raises(GpibError):
        t.write(31, "*RST")
