"""Banco SQLite local.

O arquivo fica em backend/data/gpibpanel.db (ou na pasta da variável de
ambiente GPIBPANEL_DATA). A estrutura é criada/atualizada por MIGRATIONS:
cada item é aplicado uma vez, na ordem; o número da última aplicada fica
em PRAGMA user_version. Para mudar o banco, ACRESCENTE um item no fim
(nunca altere um que já existe).
"""

import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

MIGRATIONS = [
    """
    CREATE TABLE equipment (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT NOT NULL UNIQUE COLLATE NOCASE,
        address     INTEGER NOT NULL CHECK (address BETWEEN 0 AND 30),
        driver      TEXT NOT NULL,
        notes       TEXT NOT NULL DEFAULT '',
        image       BLOB,
        image_type  TEXT,
        created_at  TEXT NOT NULL,
        updated_at  TEXT NOT NULL
    )
    """,
    # 2 (Fase 4): intervalo de leitura automática, em ms; 0 = pausado
    "ALTER TABLE equipment ADD COLUMN poll_ms INTEGER NOT NULL DEFAULT 1000",
    # 3 (Fase 5): painéis; widgets = lista JSON com tipo, posição na grade e configuração
    """
    CREATE TABLE panels (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT NOT NULL UNIQUE COLLATE NOCASE,
        widgets     TEXT NOT NULL DEFAULT '[]',
        created_at  TEXT NOT NULL,
        updated_at  TEXT NOT NULL
    )
    """,
    # 4 (Fase 6): grade com o dobro de resolução (12 -> 24 colunas, linhas de 56 -> 24 px);
    # dobra posição e tamanho dos widgets salvos, para os painéis ficarem iguais
    """
    UPDATE panels SET widgets = (
        SELECT COALESCE(json_group_array(json_set(value,
            '$.x', json_extract(value, '$.x') * 2, '$.y', json_extract(value, '$.y') * 2,
            '$.w', json_extract(value, '$.w') * 2, '$.h', json_extract(value, '$.h') * 2)), '[]')
        FROM json_each(panels.widgets)
    )
    """,
]


def data_dir() -> Path:
    return Path(os.environ.get("GPIBPANEL_DATA") or DEFAULT_DATA_DIR)


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.migrate()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """Conexão curta; confirma (commit) no fim do bloco ou desfaz se der erro."""
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        try:
            with con:
                yield con
        finally:
            con.close()

    def migrate(self) -> None:
        with self.connect() as con:
            version = con.execute("PRAGMA user_version").fetchone()[0]
            for number, sql in enumerate(MIGRATIONS[version:], start=version + 1):
                con.execute(sql)
                con.execute(f"PRAGMA user_version = {number}")
