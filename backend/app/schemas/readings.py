from datetime import datetime
from pydantic import BaseModel, Field, AwareDatetime, ConfigDict


class ReadingIn(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    device_code: str = Field(min_length=1, max_length=80)
    temperature_c: float = Field(ge=-40, le=80)
    humidity_percent: float = Field(ge=0, le=100)
    measured_at: AwareDatetime | None = None
    boot_id: str = Field(min_length=1, max_length=80)
    sequence_number: int = Field(ge=0, strict=True)


class ReadingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    device_id: int
    temperature_c: float
    humidity_percent: float
    measured_at: datetime
    received_at: datetime
    boot_id: str
    sequence_number: int


class DeviceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    device_code: str
    name: str
    sensor_type: str
    location: str
    created_at: datetime
    is_active: bool
