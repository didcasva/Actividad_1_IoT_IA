import io
import secrets
from typing import Annotated
from pydantic import AwareDatetime
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from sqlalchemy import select, text
from app.core.config import settings
from app.core.database import Session
from app.models.entities import Device
from app.schemas.readings import ReadingIn, ReadingOut, DeviceOut
from app.repositories.readings import query
from app.services.ingestion import ingest
from app.services.csv_store import reconcile, write_rows
from app.services.influx_store import ping

router = APIRouter()


def session():
    with Session() as db:
        yield db


def auth(x_api_key: Annotated[str | None, Header()] = None):
    if not x_api_key or not secrets.compare_digest(x_api_key, settings.api_key):
        raise HTTPException(401, "API Key inválida")


def filters(device_id: int | None = None, start: AwareDatetime | None = None, end: AwareDatetime | None = None):
    if start and end and start > end:
        raise HTTPException(422, "Inicio posterior al fin")
    return query(device_id, start, end)


@router.post("/api/v1/readings", response_model=ReadingOut, dependencies=[Depends(auth)])
def post(data: ReadingIn, db=Depends(session)):
    return ingest(db, data)


@router.get("/api/v1/readings/latest", response_model=ReadingOut | None)
def latest(q=Depends(filters), db=Depends(session)):
    return db.scalar(q.limit(1))


@router.get("/api/v1/readings/export.csv")
def export(q=Depends(filters), db=Depends(session)):
    f = io.StringIO(newline="")
    write_rows(f, db.scalars(q))
    return Response(f.getvalue(), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="readings.csv"'})


@router.get("/api/v1/readings", response_model=list[ReadingOut])
def history(q=Depends(filters), limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0), db=Depends(session)):
    return list(db.scalars(q.limit(limit).offset(offset)))


@router.get("/api/v1/devices", response_model=list[DeviceOut])
def devices(db=Depends(session)):
    return list(db.scalars(select(Device).order_by(Device.id)))


@router.get("/health")
def health(db=Depends(session)):
    try:
        db.execute(text("SELECT 1"))
        reconcile()
    except Exception:
        raise HTTPException(503, "Dependencia no disponible")
    # InfluxDB se informa sin marcar la API como no saludable: el dashboard no depende de ella.
    return {"status": "ok", "database": "ok", "csv": "ok", "influx": ping()}
