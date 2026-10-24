"""Validate topic/payload binding and reuse the same durable ingestion as HTTP."""
import re
from app.core.database import Session
from app.schemas.readings import ReadingIn
from app.services.ingestion import ingest


def process_message(topic: str, payload: bytes) -> tuple[str, dict]:
    match = re.fullmatch(r"rutasalud/([A-Za-z0-9_-]{1,80})/telemetria", topic)
    if not match or len(payload) > 2048:
        raise ValueError("Topic o longitud de mensaje no admitidos")
    data = ReadingIn.model_validate_json(payload)
    if data.device_code != match[1]:
        raise ValueError("device_code no coincide con la unidad autorizada por el topic")
    with Session() as db:
        row = ingest(db, data)  # Retorna solamente tras transaccion SQL y reconciliacion CSV.
        ack = {"status": "stored", "device_code": data.device_code,
               "boot_id": data.boot_id, "sequence_number": data.sequence_number, "id": row.id}
    return f"rutasalud/{data.device_code}/ack", ack
