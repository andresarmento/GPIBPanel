from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app import __version__
from app.api import bus, equipment, health, instruments, live, panels
from app.db import Database, data_dir
from app.equipment import EquipmentStore
from app.errors import AppError
from app.gpib.bus import GpibBus
from app.live import LiveHub
from app.panels import PanelStore


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db = Database(data_dir() / "gpibpanel.db")
    app.state.equipment = EquipmentStore(app.state.db)
    app.state.panels = PanelStore(app.state.db)
    app.state.bus = GpibBus()
    app.state.live = LiveHub(app.state.bus, app.state.equipment)
    yield
    try:
        await app.state.live.shutdown()
        await app.state.bus.disconnect()
    finally:
        app.state.bus.shutdown()


app = FastAPI(title="GPIBPanel", version=__version__, lifespan=lifespan)
app.include_router(health.router, prefix="/api")
app.include_router(bus.router, prefix="/api")
app.include_router(instruments.router, prefix="/api")
app.include_router(equipment.router, prefix="/api")
app.include_router(live.router, prefix="/api")
app.include_router(panels.router, prefix="/api")


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})
