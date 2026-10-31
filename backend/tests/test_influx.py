from datetime import datetime, timezone
import json
from types import SimpleNamespace
from unittest.mock import Mock
import httpx
import pytest
from fastapi import HTTPException
from app.core.config import settings
from app.core.database import Session
from app.models.entities import Device, SensorReading
from app.services import influx_store
from app.services.mqtt_ingestion import process_message

TOPIC = "rutasalud/esp32-01/telemetria"
PAYLOAD = dict(device_code="esp32-01", temperature_c=26.4, humidity_percent=58,
               measured_at="2026-10-17T15:00:00Z", boot_id="influx-test", sequence_number=0)
HEADERS = {"X-API-Key": "test-key"}


def payload(**changes):
    return json.dumps(PAYLOAD | changes).encode()


def count():
    with Session() as db:
        return db.query(SensorReading).count()


@pytest.fixture
def influx(monkeypatch):
    monkeypatch.setattr(settings, "influx_url", "http://influx.test:8086/")
    monkeypatch.setattr(settings, "influx_token", "token-de-prueba")
    post = Mock(return_value=httpx.Response(204, request=httpx.Request("POST", "http://influx.test")))
    monkeypatch.setattr(influx_store.httpx, "post", post)
    return post


def body(call):
    return call.kwargs["content"].decode()


def test_line_protocol_is_exact_and_escapes_tag():
    row = SimpleNamespace(id=7, temperature_c=26.4, humidity_percent=58,
                          measured_at=datetime(2026, 10, 17, 15, 0, 0, 123456, tzinfo=timezone.utc))
    assert influx_store.line("UM 1,a=b", row) == (
        r"ambiente,device_code=UM\ 1\,a\=b temperature_c=26.4,humidity_percent=58.0,reading_id=7i 1792249200123456")


def test_naive_sqlite_time_is_utc():
    aware = datetime(2026, 10, 17, 15, tzinfo=timezone.utc)
    assert influx_store.microseconds(aware.replace(tzinfo=None)) == influx_store.microseconds(aware)


def test_disabled_without_configuration(client, monkeypatch):
    post = Mock()
    monkeypatch.setattr(influx_store.httpx, "post", post)
    assert client.post("/api/v1/readings", json=PAYLOAD, headers=HEADERS).status_code == 200
    post.assert_not_called()
    assert client.get("/health").json()["influx"] == "disabled"


def test_http_and_mqtt_write_one_authenticated_point(client, influx):
    process_message(TOPIC, payload())
    call = influx.call_args
    assert call.args[0] == "http://influx.test:8086/api/v2/write"
    assert call.kwargs["params"] == {"org": "rutasalud", "bucket": "telemetria", "precision": "us"}
    assert call.kwargs["headers"]["Authorization"] == "Token token-de-prueba"
    assert body(call).startswith("ambiente,device_code=esp32-01 temperature_c=26.4,humidity_percent=58.0,reading_id=")


def test_retry_without_ntp_rewrites_identical_point(client, influx):
    process_message(TOPIC, payload(measured_at=None))
    process_message(TOPIC, payload(measured_at=None))
    assert count() == 1
    assert influx.call_count == 2
    assert body(influx.call_args_list[0]) == body(influx.call_args_list[1])


@pytest.mark.parametrize("failure", [
    httpx.ConnectError("sin ruta"),
    httpx.HTTPStatusError("401", request=httpx.Request("POST", "http://influx.test"), response=httpx.Response(401)),
])
def test_no_application_ack_until_influx_recovers(client, influx, failure):
    working = influx.return_value
    influx.side_effect = failure
    with pytest.raises(HTTPException) as error:
        process_message(TOPIC, payload())
    assert error.value.status_code == 503
    assert count() == 1  # SQL ya confirmado; el reintento no duplica esa fila.
    influx.side_effect = None
    influx.return_value = working
    assert process_message(TOPIC, payload())[1]["status"] == "stored"
    assert count() == 1


def test_health_reports_influx_without_failing(client, influx, monkeypatch):
    request = httpx.Request("GET", "http://influx.test")
    monkeypatch.setattr(influx_store.httpx, "get", Mock(return_value=httpx.Response(200, request=request)))
    assert client.get("/health").json()["influx"] == "ok"
    monkeypatch.setattr(influx_store.httpx, "get", Mock(side_effect=httpx.ConnectError("caido")))
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["influx"] == "error"


def test_backfill_loads_history_in_batches(client, influx, monkeypatch):
    for sequence in range(5):
        process_message(TOPIC, payload(sequence_number=sequence))
    influx.reset_mock()
    monkeypatch.setattr(influx_store, "BATCH", 2)
    assert influx_store.backfill() == 5
    assert [len(body(call).split("\n")) for call in influx.call_args_list] == [2, 2, 1]


def test_stored_parses_flux_csv_and_matches_sql(client, influx):
    _, ack = process_message(TOPIC, payload())
    csv_text = (",result,table,_time,device_code,humidity_percent,reading_id,temperature_c\r\n"
                f",_result,0,2026-10-17T15:00:00Z,esp32-01,58,{ack['id']},26.4\r\n\r\n")
    influx.return_value = httpx.Response(200, text=csv_text, request=httpx.Request("POST", "http://influx.test"))
    assert influx_store.stored() == influx_store.expected()
    assert "application/vnd.flux" == influx.call_args.kwargs["headers"]["Content-Type"]


def test_expected_includes_every_device(client, influx):
    with Session() as db:
        db.add(Device(device_code="UM1", name="UM1", sensor_type="DHT11", location="Atención"))
        db.commit()
    process_message(TOPIC, payload())
    process_message("rutasalud/UM1/telemetria", payload(device_code="UM1"))
    assert sorted(value[0] for value in influx_store.expected().values()) == ["UM1", "esp32-01"]
