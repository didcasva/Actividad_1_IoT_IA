import csv
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import pytest
from app.core.config import settings
from app.core.database import Session
from app.models.entities import SensorReading, Device
from app.services.csv_store import reconcile

PAYLOAD = dict(device_code="esp32-01", temperature_c=25.5, humidity_percent=61,
               measured_at="2026-10-17T15:00:00Z", boot_id="test-boot", sequence_number=0)
HEADERS = {"X-API-Key": "test-key"}


def send(client, **values):
    return client.post("/api/v1/readings", json=PAYLOAD | values, headers=HEADERS)


def test_connectivity(client):
    assert client.get("/health").status_code == 200
    assert client.get("/").status_code == 200
    assert client.get("/docs").status_code == 200
    assert client.get("/api/v1/devices").json()[0]["name"] == "Unidad móvil 01"


@pytest.mark.parametrize("patch", [{"humidity_percent": -1}, {"humidity_percent": 101}, {"temperature_c": 81}, {"sequence_number": -1}, {"measured_at": "2026-01-01"}, {"boot_id": ""}, {"temperature_c": "abc"}])
def test_validation(client, patch):
    assert send(client, **patch).status_code == 422


def test_malformed(client):
    assert client.post("/api/v1/readings", content="{broken", headers=HEADERS).status_code == 422


def test_auth(client):
    assert client.post("/api/v1/readings", json=PAYLOAD).status_code == 401
    assert client.post("/api/v1/readings", json=PAYLOAD, headers={"X-API-Key": "wrong"}).status_code == 401


def test_persistence_idempotency_and_csv(client):
    first = send(client)
    assert first.status_code == 200
    assert send(client).json()["id"] == first.json()["id"]
    with Session() as db:
        assert db.query(SensorReading).count() == 1
        assert db.query(SensorReading).one().temperature_c == 25.5
    with Path(settings.csv_path).open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1 and rows[0]["humidity_percent"] == "61.0"
    Path(settings.csv_path).write_text("corrupt", encoding="utf-8")
    reconcile()
    with Path(settings.csv_path).open(newline="", encoding="utf-8") as f:
        assert len(list(csv.DictReader(f))) == 1


def test_history(client):
    for seq in range(3):
        assert send(client, sequence_number=seq).status_code == 200
    assert len(client.get("/api/v1/readings?limit=1&offset=1").json()) == 1
    assert client.get("/api/v1/readings/latest").json()["sequence_number"] == 2
    assert client.get("/api/v1/readings?start=2027-01-01T00:00:00Z").json() == []
    assert client.get("/api/v1/readings?device_id=999").json() == []
    assert client.get("/api/v1/readings?start=2027-01-01T00:00:00Z&end=2026-01-01T00:00:00Z").status_code == 422
    assert len(list(csv.DictReader(client.get("/api/v1/readings/export.csv").text.splitlines()))) == 3


def test_no_ntp_and_dht11(client):
    assert send(client, measured_at=None).status_code == 200
    with Session() as db:
        d = db.query(Device).one()
        d.sensor_type = "DHT11"
        db.commit()
    assert send(client, temperature_c=-1, sequence_number=1).status_code == 422


def test_concurrent_retries(client):
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(lambda _: send(client), range(8)))
    assert all(r.status_code == 200 for r in responses)
    assert len({r.json()["id"] for r in responses}) == 1
    with Session() as db:
        assert db.query(SensorReading).count() == 1


def test_csv_failure_then_retry(client, monkeypatch):
    import app.services.ingestion as service
    original = service.reconcile

    def fail():
        raise OSError("simulated disk failure")

    monkeypatch.setattr(service, "reconcile", fail)
    assert send(client).status_code == 503
    with Session() as db:
        assert db.query(SensorReading).count() == 1
    monkeypatch.setattr(service, "reconcile", original)
    assert send(client).status_code == 200
    with Path(settings.csv_path).open(newline="", encoding="utf-8") as f:
        assert len(list(csv.DictReader(f))) == 1
