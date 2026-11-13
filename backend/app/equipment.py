"""Cadastro de equipamentos (nome, endereço GPIB, driver, observações, foto)."""

import sqlite3
from datetime import datetime, timezone

from app.db import Database
from app.drivers import DRIVERS
from app.errors import Conflict, Invalid, NotFound
from app.gpib.transport import MAX_ADDRESS, MIN_ADDRESS

MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_NAME = 100

# Assinatura dos primeiros bytes -> tipo da imagem
_IMAGE_SIGNATURES = [
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
]

_COLUMNS = "id, name, address, driver, notes, image_type, created_at, updated_at"


def detect_image_type(data: bytes) -> str | None:
    for sig, mime in _IMAGE_SIGNATURES:
        if data.startswith(sig):
            return mime
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    cls = DRIVERS.get(d["driver"])
    has_image = d.pop("image_type") is not None
    d["type"] = cls.type if cls else None
    # ?v= muda quando o registro muda, para o navegador não usar a foto velha do cache
    d["image_url"] = f"/api/equipment/{d['id']}/image?v={d['updated_at']}" if has_image else None
    return d


def _clean(name: str, address: int, driver: str, notes: str) -> tuple[str, int, str, str]:
    name = name.strip()
    if not name:
        raise Invalid("Informe o nome do equipamento")
    if len(name) > MAX_NAME:
        raise Invalid(f"Nome muito longo (máximo {MAX_NAME} caracteres)")
    if not MIN_ADDRESS <= address <= MAX_ADDRESS:
        raise Invalid(f"Endereço GPIB inválido: {address} (use {MIN_ADDRESS} a {MAX_ADDRESS})")
    if driver not in DRIVERS:
        raise Invalid(f"Driver {driver!r} não existe (disponíveis: {', '.join(DRIVERS)})")
    return name, address, driver, notes.strip()


class EquipmentStore:
    def __init__(self, db: Database):
        self.db = db

    def list(self) -> list[dict]:
        with self.db.connect() as con:
            rows = con.execute(f"SELECT {_COLUMNS} FROM equipment ORDER BY name").fetchall()
        return [_to_dict(r) for r in rows]

    def get(self, equipment_id: int) -> dict:
        with self.db.connect() as con:
            row = con.execute(f"SELECT {_COLUMNS} FROM equipment WHERE id = ?", (equipment_id,)).fetchone()
        if row is None:
            raise NotFound(f"Equipamento {equipment_id} não existe")
        return _to_dict(row)

    def create(self, name: str, address: int, driver: str, notes: str = "") -> dict:
        values = _clean(name, address, driver, notes)
        now = _now()
        try:
            with self.db.connect() as con:
                cur = con.execute(
                    "INSERT INTO equipment (name, address, driver, notes, created_at, updated_at)"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    (*values, now, now),
                )
        except sqlite3.IntegrityError:
            raise Conflict(f"Já existe um equipamento chamado {values[0]!r}") from None
        return self.get(cur.lastrowid)

    def update(self, equipment_id: int, name: str, address: int, driver: str, notes: str = "") -> dict:
        values = _clean(name, address, driver, notes)
        try:
            with self.db.connect() as con:
                cur = con.execute(
                    "UPDATE equipment SET name = ?, address = ?, driver = ?, notes = ?, updated_at = ? WHERE id = ?",
                    (*values, _now(), equipment_id),
                )
        except sqlite3.IntegrityError:
            raise Conflict(f"Já existe um equipamento chamado {values[0]!r}") from None
        if cur.rowcount == 0:
            raise NotFound(f"Equipamento {equipment_id} não existe")
        return self.get(equipment_id)

    def delete(self, equipment_id: int) -> None:
        with self.db.connect() as con:
            cur = con.execute("DELETE FROM equipment WHERE id = ?", (equipment_id,))
        if cur.rowcount == 0:
            raise NotFound(f"Equipamento {equipment_id} não existe")

    # --- foto --------------------------------------------------------------

    def get_image(self, equipment_id: int) -> tuple[bytes, str]:
        with self.db.connect() as con:
            row = con.execute("SELECT image, image_type FROM equipment WHERE id = ?", (equipment_id,)).fetchone()
        if row is None:
            raise NotFound(f"Equipamento {equipment_id} não existe")
        if row["image"] is None:
            raise NotFound("Equipamento sem foto")
        return row["image"], row["image_type"]

    def set_image(self, equipment_id: int, data: bytes) -> dict:
        if len(data) > MAX_IMAGE_BYTES:
            raise Invalid(f"Imagem muito grande (máximo {MAX_IMAGE_BYTES // (1024 * 1024)} MB)")
        mime = detect_image_type(data)
        if mime is None:
            raise Invalid("Formato de imagem não suportado (use PNG, JPEG, GIF ou WEBP)")
        return self._write_image(equipment_id, data, mime)

    def clear_image(self, equipment_id: int) -> dict:
        return self._write_image(equipment_id, None, None)

    def _write_image(self, equipment_id: int, data: bytes | None, mime: str | None) -> dict:
        with self.db.connect() as con:
            cur = con.execute(
                "UPDATE equipment SET image = ?, image_type = ?, updated_at = ? WHERE id = ?",
                (data, mime, _now(), equipment_id),
            )
        if cur.rowcount == 0:
            raise NotFound(f"Equipamento {equipment_id} não existe")
        return self.get(equipment_id)
