import csv
import os
import tempfile
from pathlib import Path
from filelock import FileLock
from sqlalchemy import select
from app.core.database import Session
from app.core.config import settings
from app.models.entities import SensorReading

FIELDS = ["id", "device_id", "temperature_c", "humidity_percent", "measured_at", "received_at", "boot_id", "sequence_number"]


def write_rows(stream, rows):
    writer = csv.writer(stream)
    writer.writerow(FIELDS)
    for row in rows:
        writer.writerow([getattr(row, k).isoformat() if hasattr(getattr(row, k), "isoformat")
                         else getattr(row, k) for k in FIELDS])


def reconcile():
    path = Path(settings.csv_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Lock before opening a fresh snapshot, so old snapshots cannot overwrite new ones.
    with FileLock(str(path) + ".lock", timeout=30):
        temp = None
        try:
            with Session() as db, tempfile.NamedTemporaryFile(mode="w", newline="", encoding="utf-8", dir=path.parent, delete=False) as f:
                temp = f.name
                write_rows(f, db.scalars(select(SensorReading).order_by(SensorReading.id)))
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp, path)
        finally:
            if temp and os.path.exists(temp):
                os.unlink(temp)
