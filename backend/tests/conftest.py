import os
import tempfile
from pathlib import Path

test_dir = Path(tempfile.mkdtemp(prefix="iot-tests-"))
os.environ["API_KEY"] = "test-key"
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", "sqlite:///" + (test_dir / "test.db").as_posix())
os.environ["CSV_PATH"] = str(test_dir / "readings.csv")

import pytest
from fastapi.testclient import TestClient
from app.core.database import Base, engine, Session
from app.models.entities import Device, SensorReading
from app.main import app


@pytest.fixture
def client():
    # TEST_DATABASE_URL must point to a dedicated, disposable test database.
    Base.metadata.create_all(engine)
    with Session() as db:
        db.query(SensorReading).delete()
        db.query(Device).delete()
        db.add(Device(device_code="esp32-01", name="Unidad móvil 01", sensor_type="DHT22", location="Atención"))
        db.commit()
    with TestClient(app) as c:
        yield c
