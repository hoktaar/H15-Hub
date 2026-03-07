from __future__ import annotations
import os
import yaml
import logging
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.sessions import SessionMiddleware

from h15hub.api.admin import router as admin_router
from h15hub.auth import count_users, ensure_page_admin, ensure_page_user, get_current_user_from_request, resolve_next_path
from h15hub.database import init_db, get_db
from h15hub.engine.device_registry import build_registry_from_config
from h15hub.engine.automation import AutomationEngine
from h15hub.api.boards import router as board_router
from h15hub.api.devices import make_router as make_device_router
from h15hub.api.bookings import router as booking_router
from h15hub.api.ws import make_ws_router, notify_status_change
from h15hub.models.user import UserRole

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

CONFIG_PATH = os.getenv("H15HUB_CONFIG", "config.yaml")
SESSION_SECRET = os.getenv("H15HUB_SESSION_SECRET", "h15hub-dev-session-secret")

templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(__file__), "frontend", "templates")
)


def template_context(request: Request, **extra: object) -> dict[str, object]:
    return {"request": request, **extra}


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = load_config()

    await init_db()

    automations = config.get("automations", [])
    try:
        app.state.automations = AutomationEngine(automations)
    except ValueError as e:
        logger.error("Konfigurationsfehler: %s", e)
        raise

    registry = build_registry_from_config(config)
    registry.on_status_change(notify_status_change)
    registry.on_status_change(app.state.automations.on_status_change)
    await registry.start()
    app.state.registry = registry

    logger.info(
        "H15-Hub gestartet. %d Adapter registriert.",
        len(config.get("devices", {})),
    )
    yield

    await registry.stop()
    logger.info("H15-Hub gestoppt.")


app = FastAPI(
    title="H15-Hub",
    description="Hebewerk e.V. Makerspace Integration Hub",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET, same_site="lax")

app.include_router(admin_router)
app.include_router(make_device_router())
app.include_router(booking_router)
app.include_router(board_router)
app.include_router(make_ws_router())


# Frontend-Routen
@app.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    next_path = resolve_next_path(request.query_params.get("next"), "/admin")
    if await count_users(db) > 0:
        current_user = await get_current_user_from_request(request, db)
        if current_user:
            target = "/admin" if current_user.role == UserRole.ADMIN else "/"
            return RedirectResponse(url=target, status_code=303)
        return RedirectResponse(url="/login", status_code=303)

    return templates.TemplateResponse(
        "setup.html",
        template_context(request, next_path=next_path),
    )


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    next_path = resolve_next_path(request.query_params.get("next"), "/")
    if await count_users(db) == 0:
        return RedirectResponse(url="/setup", status_code=303)

    current_user = await get_current_user_from_request(request, db)
    if current_user:
        target = "/admin" if current_user.role == UserRole.ADMIN else "/"
        return RedirectResponse(url=target, status_code=303)

    return templates.TemplateResponse(
        "login.html",
        template_context(request, next_path=next_path),
    )


@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    current_user = await ensure_page_admin(request, db)
    if isinstance(current_user, RedirectResponse):
        return current_user

    return templates.TemplateResponse(
        "admin.html",
        template_context(request, current_user=current_user),
    )


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    current_user = await ensure_page_user(request, db)
    if isinstance(current_user, RedirectResponse):
        return current_user

    return templates.TemplateResponse(
        "index.html",
        template_context(request, current_user=current_user),
    )


@app.get("/device/{device_id}", response_class=HTMLResponse)
async def device_detail(request: Request, device_id: str, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    current_user = await ensure_page_user(request, db)
    if isinstance(current_user, RedirectResponse):
        return current_user

    registry = request.app.state.registry
    device = registry.get(device_id)
    if not device:
        return HTMLResponse("Gerät nicht gefunden", status_code=404)
    return templates.TemplateResponse(
        "device.html",
        template_context(request, current_user=current_user, device=device),
    )


@app.get("/bookings", response_class=HTMLResponse)
async def bookings_page(request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    from h15hub.models.booking import Booking, BookingStatus

    current_user = await ensure_page_user(request, db)
    if isinstance(current_user, RedirectResponse):
        return current_user

    registry = request.app.state.registry
    devices = registry.get_all()

    result = await db.execute(
        select(Booking)
        .where(Booking.status != BookingStatus.CANCELLED)
        .order_by(Booking.start_time)
    )
    bookings = list(result.scalars().all())

    return templates.TemplateResponse(
        "bookings.html",
        template_context(request, current_user=current_user, devices=devices, bookings=bookings),
    )


@app.get("/boards", response_class=HTMLResponse)
async def boards_page(
    request: Request,
    group_id: int | None = None,
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    from h15hub.models.board import BoardGroup

    current_user = await ensure_page_user(request, db)
    if isinstance(current_user, RedirectResponse):
        return current_user

    result = await db.execute(select(BoardGroup).order_by(BoardGroup.name))
    groups = list(result.scalars().all())

    selected_group = next((group for group in groups if group.id == group_id), None)
    if not selected_group and groups:
        selected_group = groups[0]

    groups_payload = [{"id": group.id, "name": group.name} for group in groups]

    return templates.TemplateResponse(
        "boards.html",
        {
            **template_context(request, current_user=current_user),
            "groups": groups,
            "groups_payload": groups_payload,
            "selected_group": selected_group,
            "selected_group_id": selected_group.id if selected_group else None,
        },
    )


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "h15hub"}
