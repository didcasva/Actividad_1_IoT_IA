import csv
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
import paho.mqtt.client as mqtt
from app.core.config import settings
from app.core.database import Session
from app.models.entities import SensorReading
from app.services.mqtt_ingestion import process_message
from app import mqtt_worker

TOPIC = "rutasalud/esp32-01/telemetria"
PAYLOAD = dict(device_code="esp32-01", temperature_c=26.4, humidity_percent=58,
               measured_at=None, boot_id="mqtt-test", sequence_number=0)


def payload(**changes):
    return json.dumps(PAYLOAD | changes).encode()


def count():
    with Session() as db:
        return db.query(SensorReading).count()


def test_mqtt_to_http_and_csv(client):
    topic, ack = process_message(TOPIC, payload())
    assert topic == "rutasalud/esp32-01/ack"
    assert ack["status"] == "stored"
    assert client.get("/api/v1/readings/latest").json()["id"] == ack["id"]
    with Path(settings.csv_path).open(newline="", encoding="utf-8") as stream:
        assert [int(row["id"]) for row in csv.DictReader(stream)] == [ack["id"]]


def test_http_and_mqtt_retries_share_identity(client):
    first = client.post("/api/v1/readings", json=PAYLOAD, headers={"X-API-Key": "test-key"}).json()
    for _ in range(3):
        assert process_message(TOPIC, payload())[1]["id"] == first["id"]
    assert count() == 1


@pytest.mark.parametrize("topic,body", [
    ("rutasalud/OTHER/telemetria", payload()),
    ("rutasalud/esp32-01/estado", payload()),
    ("rutasalud/+/telemetria", payload()),
    (TOPIC, b"{"), (TOPIC, b"x" * 2049),
    (TOPIC, payload(humidity_percent=101)),
    (TOPIC, payload(sequence_number=-1)),
    (TOPIC, payload(temperature_c=float("nan"))),
])
def test_reject_invalid_without_storing(client, topic, body):
    with pytest.raises((ValueError, ValidationError)):
        process_message(topic, body)
    assert count() == 0


def test_no_application_ack_until_csv_recovers(client, monkeypatch):
    import app.services.ingestion as ingestion
    original = ingestion.reconcile
    monkeypatch.setattr(ingestion, "reconcile", Mock(side_effect=OSError("disk unavailable")))
    with pytest.raises(HTTPException) as error:
        process_message(TOPIC, payload())
    assert error.value.status_code == 503
    assert count() == 1  # SQL ya confirmado; el reintento no duplica esa fila.
    monkeypatch.setattr(ingestion, "reconcile", original)
    assert process_message(TOPIC, payload())[1]["status"] == "stored"
    assert count() == 1


def message(retain=False):
    return SimpleNamespace(topic=TOPIC, payload=payload(), qos=1, mid=17, retain=retain)


def test_worker_storage_failure_does_not_ack_transport_or_application(client, monkeypatch):
    fake = Mock()
    monkeypatch.setattr(mqtt_worker, "process_message", Mock(side_effect=HTTPException(503)))
    with pytest.raises(RuntimeError):
        mqtt_worker.on_message(fake, None, message())
    fake.publish.assert_not_called()
    fake.ack.assert_not_called()


def test_worker_publishes_application_ack_then_transport_ack(client):
    fake = Mock()
    fake.publish.return_value.rc = mqtt.MQTT_ERR_SUCCESS
    fake.ack.return_value = mqtt.MQTT_ERR_SUCCESS
    mqtt_worker.on_message(fake, None, message())
    published = json.loads(fake.publish.call_args.args[1])
    assert published["status"] == "stored"
    assert count() == 1
    assert fake.method_calls[0][0] == "publish"
    assert fake.method_calls[1][0] == "ack"
    fake.ack.assert_called_once_with(17, 1)


def test_retained_telemetry_never_stored_or_application_acked(client):
    fake = Mock()
    fake.ack.return_value = mqtt.MQTT_ERR_SUCCESS
    mqtt_worker.on_message(fake, None, message(retain=True))
    fake.publish.assert_not_called()
    fake.ack.assert_called_once_with(17, 1)
    assert count() == 0
