import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        c.post("/api/bus/connect", json={"kind": "sim"})
        yield c


def test_drivers(client):
    assert [d["name"] for d in client.get("/api/drivers").json()] == ["E3632A"]


def test_identify(client):
    r = client.post("/api/instruments/5/identify").json()
    assert r["idn"]["model"] == "E3632A"
    assert r["driver"]["name"] == "E3632A"


def test_identify_timeout(client):
    assert client.post("/api/instruments/7/identify").status_code == 504


def test_psu_state_and_apply(client):
    r = client.get("/api/instruments/5/psu/OUT")
    assert r.status_code == 200 and r.json()["output"] is False

    r = client.post("/api/instruments/5/psu/OUT", json={"voltage": 5, "current": 1, "output": True})
    assert r.status_code == 200
    s = r.json()
    assert s["output"] is True and s["voltage"] == pytest.approx(5)


def test_psu_limit_is_422(client):
    r = client.post("/api/instruments/5/psu/OUT", json={"voltage": 99})
    assert r.status_code == 422
    assert "fora do limite" in r.json()["detail"]


def test_psu_bad_channel_is_422(client):
    assert client.get("/api/instruments/5/psu/CH9").status_code == 422


def test_bad_address_is_422(client):
    assert client.post("/api/instruments/31/identify").status_code == 422
