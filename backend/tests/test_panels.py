import pytest
from fastapi.testclient import TestClient

from app.db import MIGRATIONS, Database
from app.errors import Conflict, Invalid, NotFound
from app.main import app
from app.panels import GRID_COLS, PanelStore, Widget


def w(id, x=0, y=0, ww=2, h=2, type="text", **config):
    return Widget(id=id, type=type, x=x, y=y, w=ww, h=h, config=config)


@pytest.fixture
def store(tmp_path):
    return PanelStore(Database(tmp_path / "t.db"))


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_migration_version(tmp_path):
    db = Database(tmp_path / "t.db")
    with db.connect() as con:
        assert con.execute("PRAGMA user_version").fetchone()[0] == len(MIGRATIONS) == 4


def test_migration_doubles_grid(tmp_path):
    """Painéis salvos na grade de 12 colunas continuam iguais na de 24."""
    import json
    import sqlite3

    path = tmp_path / "old.db"
    con = sqlite3.connect(path)
    for sql in MIGRATIONS[:3]:
        con.execute(sql)
    old = [
        {"id": "a", "type": "text", "x": 1, "y": 2, "w": 3, "h": 4, "config": {"text": "oi"}},
        {"id": "b", "type": "chart", "x": 6, "y": 0, "w": 6, "h": 4, "config": {"window_s": 60}},
    ]
    con.execute(
        "INSERT INTO panels (name, widgets, created_at, updated_at) VALUES ('P', ?, 'x', 'x'), ('Vazio', '[]', 'x', 'x')",
        (json.dumps(old),),
    )
    con.execute("PRAGMA user_version = 3")
    con.commit()
    con.close()

    store = PanelStore(Database(path))
    p, empty = sorted(store.list(), key=lambda x: x["name"])
    a, b = store.get(p["id"])["widgets"]
    assert (a["x"], a["y"], a["w"], a["h"]) == (2, 4, 6, 8) and a["config"] == {"text": "oi"}
    assert (b["x"], b["w"]) == (12, 12) and b["x"] + b["w"] == GRID_COLS
    assert store.get(empty["id"])["widgets"] == []


def test_crud(store):
    p = store.create(" Bancada ")
    assert p["name"] == "Bancada" and p["widgets"] == []

    widgets = [w("a", text="Título"), w("b", x=2, type="display", equipment_id=1, channel="OUT", quantity="voltage")]
    p = store.update(p["id"], "Bancada 1", widgets)
    assert [x["id"] for x in p["widgets"]] == ["a", "b"]
    assert p["widgets"][0]["config"] == {"text": "Título"}

    (item,) = store.list()
    assert item["widget_count"] == 2 and "widgets" not in item

    store.delete(p["id"])
    with pytest.raises(NotFound):
        store.get(p["id"])


def test_unique_name(store):
    store.create("Bancada")
    with pytest.raises(Conflict):
        store.create("BANCADA")


def test_overlap_rejected(store):
    p = store.create("P")
    with pytest.raises(Invalid):
        store.update(p["id"], "P", [w("a"), w("b", x=1, y=1)])
    store.update(p["id"], "P", [w("a"), w("b", x=2)])  # encostados, sem sobrepor: ok


def test_duplicate_ids_rejected(store):
    p = store.create("P")
    with pytest.raises(Invalid):
        store.update(p["id"], "P", [w("a"), w("a", x=4)])


def test_widget_must_fit_grid():
    with pytest.raises(ValueError):
        w("a", x=GRID_COLS - 1, ww=2)


def test_api(client):
    r = client.post("/api/panels", json={"name": "Bancada"})
    assert r.status_code == 201
    pid = r.json()["id"]

    body = {
        "name": "Bancada",
        "widgets": [{"id": "a", "type": "chart", "x": 0, "y": 0, "w": 6, "h": 4, "config": {"quantity": "current"}}],
    }
    assert client.put(f"/api/panels/{pid}", json=body).status_code == 200
    assert client.get(f"/api/panels/{pid}").json()["widgets"][0]["type"] == "chart"

    listing = client.get("/api/panels").json()
    assert listing["grid_cols"] == GRID_COLS and listing["panels"][0]["widget_count"] == 1

    bad = {**body, "widgets": [{**body["widgets"][0], "type": "foguete"}]}
    assert client.put(f"/api/panels/{pid}", json=bad).status_code == 422
    assert client.post("/api/panels", json={"name": "bancada"}).status_code == 409

    assert client.delete(f"/api/panels/{pid}").status_code == 204
    assert client.get(f"/api/panels/{pid}").status_code == 404


def test_widget_types_match_frontend():
    """Todo tipo de widget do frontend (catalogo.js) precisa ser aceito pelo backend."""
    import re
    import typing
    from pathlib import Path

    from app.panels import WidgetType

    catalog = Path(__file__).parents[2] / "frontend" / "src" / "lib" / "painel" / "catalogo.js"
    text = catalog.read_text(encoding="utf-8")
    block = text[text.index("export const WIDGET_TYPES") :]
    block = block[: block.index("\n};")]
    frontend = set(re.findall(r"^  (\w+): \{", block, re.M))
    assert frontend == set(typing.get_args(WidgetType))
