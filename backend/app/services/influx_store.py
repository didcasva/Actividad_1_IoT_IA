"""Time-series projection in InfluxDB 2; PostgreSQL remains the source of truth, as with the CSV."""
import csv
from datetime import datetime, timedelta, timezone
import io
import re
import httpx
from sqlalchemy import select
from app.core.config import settings
from app.core.database import Session
from app.models.entities import Device, SensorReading

MEASUREMENT = "ambiente"
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
BATCH = 5000
TIMEOUT = 5


def enabled():
    return bool(settings.influx_url and settings.influx_token)


def request(path, **kwargs):
    headers = {"Authorization": f"Token {settings.influx_token}"} | kwargs.pop("headers", {})
    response = httpx.post(f"{settings.influx_url.rstrip('/')}{path}", headers=headers,
                          params={"org": settings.influx_org} | kwargs.pop("params", {}),
                          timeout=kwargs.pop("timeout", TIMEOUT), **kwargs)
    response.raise_for_status()
    return response


def microseconds(moment):
    return (moment.replace(tzinfo=moment.tzinfo or timezone.utc) - EPOCH) // timedelta(microseconds=1)


def line(device_code, row):
    # Mismo measurement, tag y tiempo sobrescriben el punto: un reintento no lo duplica.
    tag = re.sub(r"([,= \\])", r"\\\1", device_code)
    return (f"{MEASUREMENT},device_code={tag} temperature_c={float(row.temperature_c)!r},"
            f"humidity_percent={float(row.humidity_percent)!r},reading_id={row.id}i {microseconds(row.measured_at)}")


def write(lines):
    request("/api/v2/write", params={"bucket": settings.influx_bucket, "precision": "us"},
            content="\n".join(lines).encode("utf-8"), headers={"Content-Type": "text/plain; charset=utf-8"})


def write_reading(device_code, row):
    if enabled():
        write([line(device_code, row)])


def ping():
    if not enabled():
        return "disabled"
    try:
        httpx.get(f"{settings.influx_url.rstrip('/')}/health", timeout=3).raise_for_status()
    except httpx.HTTPError:
        return "error"
    return "ok"


def rows(db):
    return db.execute(select(Device.device_code, SensorReading).join(Device).order_by(SensorReading.id))


def backfill():
    """Reescribe todas las filas de PostgreSQL; es idempotente y carga el historico."""
    total = 0
    batch = []
    with Session() as db:
        for device_code, row in rows(db):
            batch.append(line(device_code, row))
            if len(batch) == BATCH:
                write(batch)
                total += len(batch)
                batch = []
    if batch:
        write(batch)
        total += len(batch)
    return total


def expected():
    with Session() as db:
        return {row.id: (device_code, microseconds(row.measured_at), float(row.temperature_c), float(row.humidity_percent))
                for device_code, row in rows(db)}


def stored():
    flux = f'''from(bucket: "{settings.influx_bucket}")
  |> range(start: 0)
  |> filter(fn: (r) => r._measurement == "{MEASUREMENT}")
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> keep(columns: ["_time", "device_code", "reading_id", "temperature_c", "humidity_percent"])
  |> group()'''
    response = request("/api/v2/query", content=flux.encode("utf-8"), timeout=60,
                       headers={"Content-Type": "application/vnd.flux", "Accept": "application/csv"})
    return {int(row["reading_id"]): (row["device_code"], microseconds(datetime.fromisoformat(row["_time"])),
                                     float(row["temperature_c"]), float(row["humidity_percent"]))
            for row in csv.DictReader(io.StringIO(response.text, newline=""))}
