"""Driver do gerador de sinais de RF Anritsu MG3601A (0,1 a 1040 MHz).

Aparelho anterior ao IEEE 488.2: NÃO usa SCPI. Os comandos são códigos curtos
da Anritsu (manual de operação, Tabelas 8-2 e 8-4 e Apêndice J):

    FR <valor>HZ    frequência          AP <valor>DBM   nível de saída
    RO / RF         liga / desliga RF   FRRD / APRD     pede frequência / nível
    SURD            pede o status de erro (0 = sem erro)

- Leitura: o código xxRD escolhe QUAL dado o aparelho manda nas próximas leituras;
  a resposta é sempre "+100000000E+00" (sinal, 9 dígitos, expoente).
- Nível: o GPIBPanel trabalha sempre em dBm (APRD responde na unidade em uso e não
  diz qual é; todo ajuste daqui manda DBM). Valores em dB vêm com expoente E-01
  (resolução 0,1 dB).
- RF desligado: APRD responde exatamente "+000000000E+00" (expoente E+00). Assim
  dá para ver o liga/desliga feito pelo painel frontal; o nível programado não é
  informado enquanto o RF está desligado.
- Sem *IDN?: a identificação é pelo formato da resposta ao FRRD (só leitura).
  O manual é comum ao MG3602A (até 2080 MHz).
- Sem SYST:ERR?: depois de cada ajuste o driver lê SURD.

Primeira versão: frequência, nível e liga/desliga do RF. Modulação (AM/FM/ΦM),
offsets, memórias e funções especiais ficam para depois (TODO.md).
"""

import re

from app.drivers.base import Idn, InstrumentIO
from app.drivers.errors import InstrumentError
from app.drivers.rf_generator import RFGenerator
from app.gpib.errors import GpibTimeout

_REPLY = re.compile(r"^\s*([+-])(\d{9})E([+-]\d{2})\s*$")


def parse_reply(reply: str) -> tuple[float, int]:
    """'+100000000E+00' -> (100000000.0, 0); '-000000100E-01' -> (-10.0, -1)"""
    m = _REPLY.match(reply)
    if not m:
        raise InstrumentError(f"Resposta inesperada do MG3601A: {reply.strip()!r}")
    sign = -1 if m.group(1) == "-" else 1
    exp = int(m.group(3))
    return sign * int(m.group(2)) * 10.0**exp, exp


class MG3601A(RFGenerator):
    name = "MG3601A"
    models = ()  # não responde ao *IDN?: ver probe()
    description = "Gerador de sinais de RF Anritsu MG3601A: 0,1 a 1040 MHz, −133 a +13 dBm (sem SCPI)"
    channels = ("RF",)
    frequency_min = 0.1e6
    frequency_max = 1040e6
    frequency_resolution = 10.0
    level_min = -133.0
    level_max = 13.0
    level_resolution = 0.1

    # --- identificação sem *IDN? ----------------------------------------------

    @classmethod
    def probe(cls, io: InstrumentIO) -> Idn | None:
        """Pede a frequência (FRRD, só leitura) e reconhece o formato da Anritsu."""
        try:
            reply = io.query("FRRD")
        except GpibTimeout:
            return None
        if not _REPLY.match(reply):
            return None
        hz, _ = parse_reply(reply)
        raw = f"(sem *IDN?) FRRD → {reply.strip()} = {hz / 1e6:g} MHz: Anritsu MG3601A/MG3602A"
        return Idn("ANRITSU", "MG3601A", "", "", raw)

    def identify(self) -> Idn:
        idn = self.probe(self.io)
        if idn is None:
            raise InstrumentError(f"Nenhuma resposta de Anritsu MG3601A no endereço {self.io.address}")
        return idn

    # --- erros (SURD em vez de SYST:ERR?) ----------------------------------------

    def read_errors(self) -> list[str]:
        code, _ = parse_reply(self.io.query("SURD"))
        return [] if code == 0 else [f"status de erro {code:g} (SURD)"]

    # --- leitura -----------------------------------------------------------------

    def _read_frequency(self, channel: str) -> float:
        hz, _ = parse_reply(self.io.query("FRRD"))
        return hz

    def _read_level_output(self, channel: str) -> tuple[float | None, bool]:
        value, exp = parse_reply(self.io.query("APRD"))
        if value == 0 and exp == 0:
            return None, False  # RF desligado: o aparelho responde 0 sem casa decimal
        return round(value, 1), True

    # --- ajustes -------------------------------------------------------------------

    def _write_frequency(self, channel: str, hz: float) -> None:
        hz = round(hz / self.frequency_resolution) * self.frequency_resolution
        self.command(f"FR {hz:.0f}HZ")

    def _write_level(self, channel: str, dbm: float) -> None:
        self.command(f"AP {dbm:.1f}DBM")

    def _write_output(self, channel: str, on: bool) -> None:
        self.command("RO" if on else "RF")
