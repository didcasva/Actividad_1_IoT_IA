import csv
import io
from pathlib import Path
from sqlalchemy import select
from app.core.config import settings
from app.core.database import Session
from app.models.entities import SensorReading
from app.services.csv_store import write_rows

with Session() as db:
    stream = io.StringIO(newline="")
    write_rows(stream, db.scalars(select(SensorReading).order_by(SensorReading.id)))
expected = list(csv.reader(io.StringIO(stream.getvalue())))
with Path(settings.csv_path).open(encoding="utf-8", newline="") as f:
    actual = list(csv.reader(f))
assert actual == expected, "CSV diferente de la base de datos; ejecute reconciliación"
print(f"Coincidencia exacta: {len(actual)-1} mediciones")
