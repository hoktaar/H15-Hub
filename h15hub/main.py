from __future__ import annotations
import os
import yaml
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from h15hub.database import init_db, get_db
from h15hub.engine.device_registry import build_registry_from_config
from h15hub.engine.automation import AutomationEngine
from h15hub.api.devices import make_router as make_device_router
from h15hub.api.bookings import router as booking_router
from h15hub.api.ws import make_ws_router, notify_status_change

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

CONFIG_PATH = os.getenv("H15HUB_CONFIG", "config.yaml")

# Templates
templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(__file__), "frontend", "templates")
)


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = load_config()

    # DB initialisieren
    await init_db()

    # Automations validieren (Tarjan's SCC)
    automations = config.get("automations", [])
    try:
        app.state.automations = AutomationEngine(automations)
    except ValueError as e:
        logger.error("Konfigurationsfehler: %s", e)
        raise

    # Device Registry aufbauen und starten
    registry = build_registry_from_config(config)
    registry.on_status_change(notify_status_change)
    registry.on_status_change(app.state.automations.on_status_change)
    await registry.start()
    app.state.registry = registry

    logger.info("H15-Hub gestartet. Geräte: %d Adapter registriert.", len(config.get("devices", {})))
    yield

    await registry.stop()
    logger.info("H15-Hub gestoppt.")


app = FastAPI(
    title="H15-Hub",
    description="Hebewerk e.V. Makerspace Integration Hub",
    version="0.1.0",
    lifespan=lifespan,
)

# API-Router
app.include_router(make_device_router(None))  # registry wird via app.state injiziert
app.include_router(booking_router)
app.include_router(make_ws_router(None))


# Registry via app.state in die Device-Routes einfügen
@app.middleware("http")
async def inject_registry(request: Request, call_next):
    # Macht registry für API-Router zugänglich
    request.state.registry = getattr(request.app.state, "registry", None)
    return await call_next(request)


# Frontend-Routen
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/device/{device_id}", response_class=HTMLResponse)
async def device_detail(request: Request, device_id: str) -> HTMLResponse:
    registry = request.app.state.registry
    device = registry.get(device_id)
    if not device:
        return HTMLResponse("Gerät nicht gefunden", status_code=404)
    return templates.TemplateResponse("device.html", {"request": request, "device": device})


@app.get("/bookings", response_class=HTMLResponse)
async def bookings_page(request: Request) -> HTMLResponse:
    from sqlalchemy import select
    from h15hub.models.booking import Booking, BookingStatus
    registry = request.app.state.registry
    devices = registry.get_all()

    async for db in get_db():
        result = await db.execute(
            select(Booking).where(Booking.status != BookingStatus.CANCELLED)
            .order_by(Booking.start_time)
        )
        bookings = list(result.scalars().all())

    return templates.TemplateResponse(
        "bookings.html",
        {"request": request, "devices": devices, "bookings": bookings},
    )


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "h15hub"}
