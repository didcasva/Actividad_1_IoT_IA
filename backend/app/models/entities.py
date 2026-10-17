from datetime import datetime, timezone
from sqlalchemy import String, ForeignKey, UniqueConstraint, CheckConstraint, Index, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


def now():
    return datetime.now(timezone.utc)


class Device(Base):
    __tablename__ = "devices"
    id: Mapped[int] = mapped_column(primary_key=True)
    device_code: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    sensor_type: Mapped[str] = mapped_column(String(10))
    location: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    is_active: Mapped[bool] = mapped_column(default=True)
    __table_args__ = (CheckConstraint("sensor_type IN ('DHT11','DHT22')"),)


class SensorReading(Base):
    __tablename__ = "sensor_readings"
    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"))
    temperature_c: Mapped[float]
    humidity_percent: Mapped[float]
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    boot_id: Mapped[str] = mapped_column(String(80))
    sequence_number: Mapped[int]
    __table_args__ = (
        UniqueConstraint("device_id", "boot_id", "sequence_number"),
        CheckConstraint("humidity_percent BETWEEN 0 AND 100"),
        CheckConstraint("temperature_c BETWEEN -40 AND 80"),
        CheckConstraint("sequence_number >= 0"),
        Index("ix_device_time", "device_id", "measured_at"),
    )
