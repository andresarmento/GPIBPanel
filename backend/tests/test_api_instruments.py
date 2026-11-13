import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        c.post("/api/bus/connect", json={"kind": "sim"})
        yield c


def test_drivers(client):
    assert [d["name"] for d in client.get("/api/drivers").json()] == ["E3632A", "K2015", "HP33120A", "MG3601A"]


def test_identify(client):
    r = client.post("/api/instruments/5/identify").json()
    assert r["idn"]["model"] == "E3632A"
    assert r["driver"]["name"] == "E3632A"


def test_identify_timeout(client):
    assert client.post("/api/instruments/7/identify").status_code == 504


def test_bad_address_is_422(client):
    assert client.post("/api/instruments/31/identify").status_code == 422
