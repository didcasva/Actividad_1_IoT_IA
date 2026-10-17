from sqlalchemy import select
from app.models.entities import Device, SensorReading


def device(db, code):
    return db.scalar(select(Device).where(Device.device_code == code))


def duplicate(db, device_id, data):
    return db.scalar(select(SensorReading).where(
        SensorReading.device_id == device_id,
        SensorReading.boot_id == data.boot_id,
        SensorReading.sequence_number == data.sequence_number,
    ))


def query(device_id=None, start=None, end=None):
    q = select(SensorReading)
    if device_id is not None:
        q = q.where(SensorReading.device_id == device_id)
    if start:
        q = q.where(SensorReading.measured_at >= start)
    if end:
        q = q.where(SensorReading.measured_at <= end)
    return q.order_by(SensorReading.measured_at.desc(), SensorReading.id.desc())
