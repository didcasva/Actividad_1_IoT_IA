import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.api.routes import router
from app.services.csv_store import reconcile


async def repair_loop():
    while True:
        try:
            await asyncio.to_thread(reconcile)
        except Exception:
            logging.exception("CSV pendiente de reconciliación")
        await asyncio.sleep(30)


@asynccontextmanager
async def lifespan(app):
    task = asyncio.create_task(repair_loop())
    yield
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task


app = FastAPI(title="Unidades móviles de salud · Monitor ambiental", lifespan=lifespan)
app.include_router(router)
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")


@app.get("/", include_in_schema=False)
def dashboard():
    return FileResponse("frontend/templates/index.html")
