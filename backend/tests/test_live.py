import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.db import MIGRATIONS, Database
from app.equipment import EquipmentStore
from app.errors import Invalid
from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def make(client, name="Fonte", address=5, poll_ms=None):
    eq = client.post("/api/equipment", json={"name": name, "address": address, "driver": "E3632A"}).json()
    if poll_ms is not None:
        eq = client.patch(f"/api/equipment/{eq['id']}/poll", json={"poll_ms": poll_ms}).json()
    return eq


def next_state(ws, eq_id, status=None, max_msgs=50):
    """Lê mensagens até chegar uma do equipamento (e com o status pedido)."""
    for _ in range(max_msgs):
        msg = ws.receive_json()
        if msg["id"] == eq_id and (status is None or msg.get("status") == status):
            return msg
    raise AssertionError("mensagem esperada não chegou")


# --- banco ------------------------------------------------------------------


def test_migration_from_v1_keeps_data(tmp_path):
    path = tmp_path / "old.db"
    con = sqlite3.connect(path)
    con.execute(MIGRATIONS[0])
    con.execute(
        "INSERT INTO equipment (name, address, driver, created_at, updated_at) VALUES ('Velha', 5, 'E3632A', 'x', 'x')"
    )
    con.execute("PRAGMA user_version = 1")
    con.commit()
    con.close()

    (eq,) = EquipmentStore(Database(path)).list()
    assert eq["name"] == "Velha" and eq["poll_ms"] == 1000


def test_set_poll_validation(tmp_path):
    store = EquipmentStore(Database(tmp_path / "t.db"))
    eq = store.create("A", 5, "E3632A")
    updated_at = eq["updated_at"]
    assert store.set_poll(eq["id"], 0)["poll_ms"] == 0
    assert store.set_poll(eq["id"], 250)["updated_at"] == updated_at  # não troca a foto em cache
    for bad in (50, 60_001, -1):
        with pytest.raises(Invalid):
            store.set_poll(eq["id"], bad)


# --- leitura automática -------------------------------------------------------


def test_live_reading(client):
    client.post("/api/bus/connect", json={"kind": "sim"})
    eq = make(client, poll_ms=100)
    with client.websocket_connect("/api/ws") as ws:
        ws.send_json({"subscribe": [eq["id"]]})
        msg = next_state(ws, eq["id"])
        assert msg["ok"] and msg["status"] == "ok" and msg["poll_ms"] == 100
        (ch,) = msg["data"]["channels"]
        assert ch["channel"] == "OUT" and ch["output"] is False
        assert msg["cycle_ms"] >= 0


def test_command_updates_screen_immediately(client):
    client.post("/api/bus/connect", json={"kind": "sim"})
    eq = make(client, poll_ms=0)  # pausado: só lê ao abrir e depois de comandos
    with client.websocket_connect("/api/ws") as ws:
        ws.send_json({"subscribe": [eq["id"]]})
        assert next_state(ws, eq["id"])["data"]["channels"][0]["output"] is False

        r = client.post(f"/api/equipment/{eq['id']}/psu/OUT", json={"voltage": 5, "current": 1, "output": True})
        assert r.status_code == 200 and r.json()["voltage"] == pytest.approx(5)

        ch = next_state(ws, eq["id"])["data"]["channels"][0]
        assert ch["output"] is True and ch["current"] == pytest.approx(0.5)


def test_command_errors(client):
    client.post("/api/bus/connect", json={"kind": "sim"})
    eq = make(client)
    assert client.post(f"/api/equipment/{eq['id']}/psu/OUT", json={"voltage": 99}).status_code == 422
    assert client.post(f"/api/equipment/{eq['id']}/psu/CH9", json={}).status_code == 422
    assert client.post("/api/equipment/999/psu/OUT", json={}).status_code == 404
    client.post("/api/bus/disconnect")
    assert client.post(f"/api/equipment/{eq['id']}/psu/OUT", json={"output": True}).status_code == 409


def test_timeout_and_disconnected(client):
    lost = make(client, "Sumida", address=9, poll_ms=100)
    with client.websocket_connect("/api/ws") as ws:
        ws.send_json({"subscribe": [lost["id"]]})
        msg = next_state(ws, lost["id"])
        assert msg["status"] == "disconnected" and not msg["ok"]

        client.post("/api/bus/connect", json={"kind": "sim"})  # cutuca o leitor
        msg = next_state(ws, lost["id"], status="timeout")
        assert msg["error"]


def test_removed(client):
    eq = make(client, poll_ms=0)
    with client.websocket_connect("/api/ws") as ws:
        ws.send_json({"subscribe": [eq["id"]]})
        next_state(ws, eq["id"])
        client.delete(f"/api/equipment/{eq['id']}")
        assert next_state(ws, eq["id"]) == {"type": "removed", "id": eq["id"]}


def test_only_watched_equipment_is_read(client):
    client.post("/api/bus/connect", json={"kind": "sim"})
    a = make(client, "A", poll_ms=100)
    b = make(client, "B", poll_ms=100)
    hub = app.state.live
    assert hub.watched() == set()
    with client.websocket_connect("/api/ws") as ws:
        ws.send_json({"subscribe": [a["id"]]})
        next_state(ws, a["id"])
        assert hub.watched() == {a["id"]}
        ws.send_json({"subscribe": [b["id"]]})
        next_state(ws, b["id"])
        assert hub.watched() == {b["id"]}
        ws.send_json("lixo")  # mensagem inválida é ignorada
        ws.send_json({"subscribe": []})
        ws.send_json({"subscribe": [a["id"]]})
        next_state(ws, a["id"])
    # tela fechou: ninguém mais é lido
    assert hub.watched() == set()


def test_retry_backoff_for_unresponsive_equipment(client):
    from app.live import RETRY_BACKOFF_S, LiveHub, _Poller

    poller = _Poller()
    base = {"poll_ms": 250, "cycle_ms": 10, "status": "timeout", "ok": False}
    delays = []
    for _ in range(6):
        poller.timeouts += 1
        delays.append(LiveHub._delay(poller, base))
    assert delays == [2.0, 5.0, 10.0, 30.0, 30.0, 30.0]
    assert delays[-1] == RETRY_BACKOFF_S[-1]
    # respondeu de novo: volta ao intervalo normal
    poller.timeouts = 0
    assert LiveHub._delay(poller, {**base, "status": "ok", "ok": True}) == pytest.approx(0.24)
    # erro comum (não timeout): 1 s; pausado: só quando cutucado
    assert LiveHub._delay(poller, {**base, "status": "error"}) == 1.0
    assert LiveHub._delay(poller, {**base, "poll_ms": 0}) is None

    # na mensagem: quanto falta para a próxima tentativa
    client.post("/api/bus/connect", json={"kind": "sim"})
    lost = make(client, "Desligada", address=9, poll_ms=100)
    with client.websocket_connect("/api/ws") as ws:
        ws.send_json({"subscribe": [lost["id"]]})
        msg = next_state(ws, lost["id"], status="timeout")
        assert msg["retry_s"] == 2.0
