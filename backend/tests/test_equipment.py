import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.db import MIGRATIONS, Database
from app.equipment import MAX_IMAGE_BYTES, EquipmentStore, detect_image_type
from app.errors import Conflict, Invalid, NotFound
from app.main import app

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 32
WEBP = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 16


@pytest.fixture
def store(tmp_path):
    return EquipmentStore(Database(tmp_path / "t.db"))


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def new(client, **kw):
    body = {"name": "Fonte bancada", "address": 5, "driver": "E3632A", "notes": "", **kw}
    return client.post("/api/equipment", json=body)


# --- banco / store ----------------------------------------------------------


def test_migration_sets_version(tmp_path):
    db = Database(tmp_path / "t.db")
    Database(tmp_path / "t.db")  # abrir de novo não reaplica
    with db.connect() as con:
        assert con.execute("PRAGMA user_version").fetchone()[0] == len(MIGRATIONS)


def test_crud(store):
    eq = store.create("  Fonte 1 ", 5, "E3632A", "bancada")
    assert eq["name"] == "Fonte 1" and eq["type"] == "power_supply" and eq["image_url"] is None
    assert store.list() == [eq]

    eq2 = store.update(eq["id"], "Fonte A", 6, "E3632A", "")
    assert (eq2["name"], eq2["address"]) == ("Fonte A", 6)

    store.delete(eq["id"])
    assert store.list() == []
    with pytest.raises(NotFound):
        store.get(eq["id"])
    with pytest.raises(NotFound):
        store.delete(eq["id"])


def test_name_unique_ignoring_case(store):
    store.create("Fonte", 5, "E3632A")
    with pytest.raises(Conflict):
        store.create("FONTE", 6, "E3632A")
    other = store.create("Outra", 6, "E3632A")
    with pytest.raises(Conflict):
        store.update(other["id"], "fonte", 6, "E3632A")


def test_same_address_allowed(store):
    # Equipamentos guardados na prateleira podem ter o mesmo endereço padrão
    store.create("A", 5, "E3632A")
    store.create("B", 5, "E3632A")
    assert len(store.list()) == 2


@pytest.mark.parametrize(
    "args",
    [("", 5, "E3632A"), ("x" * 101, 5, "E3632A"), ("A", 31, "E3632A"), ("A", 5, "NAO_EXISTE")],
)
def test_invalid(store, args):
    with pytest.raises(Invalid):
        store.create(*args)


def test_image(store):
    eq = store.create("A", 5, "E3632A")
    eq = store.set_image(eq["id"], PNG)
    assert eq["image_url"].startswith(f"/api/equipment/{eq['id']}/image?v=")
    assert store.get_image(eq["id"]) == (PNG, "image/png")

    eq = store.clear_image(eq["id"])
    assert eq["image_url"] is None
    with pytest.raises(NotFound):
        store.get_image(eq["id"])


def test_image_rejects_bad_files(store):
    eq = store.create("A", 5, "E3632A")
    with pytest.raises(Invalid):
        store.set_image(eq["id"], b"<svg></svg>")
    with pytest.raises(Invalid):
        store.set_image(eq["id"], PNG + b"\x00" * MAX_IMAGE_BYTES)


def test_detect_image_type():
    assert detect_image_type(PNG) == "image/png"
    assert detect_image_type(JPEG) == "image/jpeg"
    assert detect_image_type(WEBP) == "image/webp"
    assert detect_image_type(b"GIF89a...") == "image/gif"
    assert detect_image_type(b"hello") is None


# --- API ----------------------------------------------------------------------


def test_api_crud(client):
    assert client.get("/api/equipment").json() == []

    r = new(client)
    assert r.status_code == 201
    eq = r.json()

    r = client.put(f"/api/equipment/{eq['id']}", json={"name": "Fonte 2", "address": 7, "driver": "E3632A"})
    assert r.status_code == 200 and r.json()["address"] == 7

    assert client.delete(f"/api/equipment/{eq['id']}").status_code == 204
    assert client.get(f"/api/equipment/{eq['id']}").status_code == 404


def test_api_errors(client):
    assert new(client).status_code == 201
    assert new(client).status_code == 409  # nome repetido
    assert new(client, name="X", driver="NAO_EXISTE").status_code == 422
    assert new(client, name="Y", address=40).status_code == 422


def test_api_image(client):
    eq = new(client).json()
    url = f"/api/equipment/{eq['id']}/image"

    r = client.put(url, files={"file": ("foto.jpg", JPEG, "image/jpeg")})
    assert r.status_code == 200
    img = client.get(r.json()["image_url"])
    assert img.content == JPEG and img.headers["content-type"] == "image/jpeg"

    r = client.put(url, files={"file": ("x.txt", b"texto", "text/plain")})
    assert r.status_code == 422

    assert client.delete(url).json()["image_url"] is None
    assert client.get(url).status_code == 404


def test_api_check(client):
    online = new(client, name="Online", address=5).json()
    offline = new(client, name="Offline", address=9).json()

    assert client.post(f"/api/equipment/{online['id']}/check").status_code == 409  # barramento desconectado

    client.post("/api/bus/connect", json={"kind": "sim"})
    r = client.post(f"/api/equipment/{online['id']}/check").json()
    assert r["online"] and r["matches"] and r["idn"]["model"] == "E3632A"

    r = client.post(f"/api/equipment/{offline['id']}/check").json()
    assert r == {"online": False, "idn": None, "detected_driver": None, "matches": False}


def test_data_persists_between_runs(temp_data_dir):
    with TestClient(app) as c:
        new(c)
    with TestClient(app) as c:
        assert [e["name"] for e in c.get("/api/equipment").json()] == ["Fonte bancada"]
    assert sqlite3.connect(temp_data_dir / "gpibpanel.db").execute("SELECT COUNT(*) FROM equipment").fetchone()[0] == 1
