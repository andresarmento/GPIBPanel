import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:  # "with" roda o lifespan (cria o barramento)
        yield c


def test_starts_disconnected(client):
    assert client.get("/api/bus").json() == {"connected": False}


def test_query_when_disconnected_is_409(client):
    r = client.post("/api/bus/query", json={"address": 5, "command": "*IDN?"})
    assert r.status_code == 409


def test_sim_round_trip(client):
    r = client.post("/api/bus/connect", json={"kind": "sim"})
    assert r.status_code == 200
    assert r.json()["connected"] is True

    assert client.post("/api/bus/write", json={"address": 5, "command": "VOLT 3.3"}).status_code == 200
    r = client.post("/api/bus/query", json={"address": 5, "command": "VOLT?"})
    assert float(r.json()["response"]) == 3.3

    assert client.post("/api/bus/disconnect").json() == {"connected": False}


def test_timeout_is_504(client):
    client.post("/api/bus/connect", json={"kind": "sim"})
    r = client.post("/api/bus/query", json={"address": 7, "command": "*IDN?"})
    assert r.status_code == 504


def test_invalid_address_is_422(client):
    r = client.post("/api/bus/query", json={"address": 40, "command": "*IDN?"})
    assert r.status_code == 422


def test_ar488_requires_port(client):
    r = client.post("/api/bus/connect", json={"kind": "ar488"})
    assert r.status_code == 400


def test_ar488_bad_port_is_502(client):
    r = client.post("/api/bus/connect", json={"kind": "ar488", "port": "COM_INEXISTENTE"})
    assert r.status_code == 502
    assert client.get("/api/bus").json() == {"connected": False}


def test_ports_lists(client):
    assert isinstance(client.get("/api/bus/ports").json(), list)
