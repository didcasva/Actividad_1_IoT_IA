from datetime import datetime, timezone
from fastapi import HTTPException
from filelock import Timeout
import httpx
from sqlalchemy.exc import IntegrityError
from app.repositories import readings as repo
from app.models.entities import SensorReading
from app.services.csv_store import reconcile
from app.services.influx_store import write_reading


def ingest(db, data):
    device = repo.device(db, data.device_code)
    if not device or not device.is_active:
        raise HTTPException(404, "Dispositivo desconocido o inactivo")
    if device.sensor_type == "DHT11" and not 0 <= data.temperature_c <= 50:
        raise HTTPException(422, "DHT11 admite 0 a 50 °C")
    row = repo.duplicate(db, device.id, data)
    if not row:
        values = data.model_dump(exclude={"device_code"})
        values["measured_at"] = (data.measured_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
        row = SensorReading(device_id=device.id, **values)
        db.add(row)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            row = repo.duplicate(db, device.id, data)
            if row is None:
                raise
        db.refresh(row)
    try:
        reconcile()
    except (OSError, Timeout) as exc:
        raise HTTPException(503, "Medición guardada; CSV pendiente, reintente la misma identidad") from exc
    try:
        write_reading(data.device_code, row)
    except httpx.HTTPError as exc:
        raise HTTPException(503, "Medición guardada; InfluxDB pendiente, reintente la misma identidad") from exc
    return row
