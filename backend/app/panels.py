"""Painéis: telas montadas pelo usuário com widgets numa grade.

Cada widget tem:
    id      texto único dentro do painel (gerado pela tela)
    type    "psu_channel" | "display" | "output_button" | "text" | "chart"
    x, y    posição na grade (coluna, linha), a partir de 0
    w, h    largura e altura em células
    config  configuração do tipo (equipamento, canal, grandeza...): quem
            interpreta é a tela; aqui só se garante que é um objeto JSON.

A grade tem GRID_COLS colunas e quantas linhas forem precisas.
"""

import json
import sqlite3
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.db import Database
from app.errors import Conflict, Invalid, NotFound

GRID_COLS = 12
MAX_ROWS = 200
MAX_WIDGETS = 100
MAX_NAME = 100

WidgetType = Literal["psu_channel", "display", "output_button", "text", "chart"]


class Widget(BaseModel):
    id: str = Field(min_length=1, max_length=40)
    type: WidgetType
    x: int = Field(ge=0, lt=GRID_COLS)
    y: int = Field(ge=0, lt=MAX_ROWS)
    w: int = Field(ge=1, le=GRID_COLS)
    h: int = Field(ge=1, le=MAX_ROWS)
    config: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def _inside_grid(self):
        if self.x + self.w > GRID_COLS:
            raise ValueError(f"widget {self.id!r} passa da borda da grade ({GRID_COLS} colunas)")
        return self


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _check_widgets(widgets: list[Widget]) -> None:
    if len(widgets) > MAX_WIDGETS:
        raise Invalid(f"Painel com widgets demais (máximo {MAX_WIDGETS})")
    ids = [w.id for w in widgets]
    if len(ids) != len(set(ids)):
        raise Invalid("Há widgets com id repetido")
    occupied: dict[tuple[int, int], str] = {}
    for w in widgets:
        for x in range(w.x, w.x + w.w):
            for y in range(w.y, w.y + w.h):
                other = occupied.setdefault((x, y), w.id)
                if other != w.id:
                    raise Invalid(f"Os widgets {other!r} e {w.id!r} estão sobrepostos")


def _clean_name(name: str) -> str:
    name = name.strip()
    if not name:
        raise Invalid("Informe o nome do painel")
    if len(name) > MAX_NAME:
        raise Invalid(f"Nome muito longo (máximo {MAX_NAME} caracteres)")
    return name


def _to_dict(row: sqlite3.Row, with_widgets: bool = True) -> dict:
    d = {k: row[k] for k in ("id", "name", "created_at", "updated_at")}
    widgets = json.loads(row["widgets"])
    if with_widgets:
        d["widgets"] = widgets
    else:
        d["widget_count"] = len(widgets)
    return d


class PanelStore:
    def __init__(self, db: Database):
        self.db = db

    def list(self) -> list[dict]:
        with self.db.connect() as con:
            rows = con.execute("SELECT * FROM panels ORDER BY name").fetchall()
        return [_to_dict(r, with_widgets=False) for r in rows]

    def get(self, panel_id: int) -> dict:
        with self.db.connect() as con:
            row = con.execute("SELECT * FROM panels WHERE id = ?", (panel_id,)).fetchone()
        if row is None:
            raise NotFound(f"Painel {panel_id} não existe")
        return _to_dict(row)

    def create(self, name: str, widgets: list[Widget] | None = None) -> dict:
        name = _clean_name(name)
        widgets = widgets or []
        _check_widgets(widgets)
        now = _now()
        try:
            with self.db.connect() as con:
                cur = con.execute(
                    "INSERT INTO panels (name, widgets, created_at, updated_at) VALUES (?, ?, ?, ?)",
                    (name, _dump(widgets), now, now),
                )
        except sqlite3.IntegrityError:
            raise Conflict(f"Já existe um painel chamado {name!r}") from None
        return self.get(cur.lastrowid)

    def update(self, panel_id: int, name: str, widgets: list[Widget]) -> dict:
        name = _clean_name(name)
        _check_widgets(widgets)
        try:
            with self.db.connect() as con:
                cur = con.execute(
                    "UPDATE panels SET name = ?, widgets = ?, updated_at = ? WHERE id = ?",
                    (name, _dump(widgets), _now(), panel_id),
                )
        except sqlite3.IntegrityError:
            raise Conflict(f"Já existe um painel chamado {name!r}") from None
        if cur.rowcount == 0:
            raise NotFound(f"Painel {panel_id} não existe")
        return self.get(panel_id)

    def delete(self, panel_id: int) -> None:
        with self.db.connect() as con:
            cur = con.execute("DELETE FROM panels WHERE id = ?", (panel_id,))
        if cur.rowcount == 0:
            raise NotFound(f"Painel {panel_id} não existe")


def _dump(widgets: list[Widget]) -> str:
    return json.dumps([w.model_dump() for w in widgets], ensure_ascii=False)
