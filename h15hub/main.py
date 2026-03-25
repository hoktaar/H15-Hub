from __future__ import annotations
import os
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
from h15hub.configuration import load_config
from h15hub.database import init_db, get_db
from h15hub.engine.device_registry import build_registry_from_config
from h15hub.engine.automation import AutomationEngine
from h15hub.api.boards import router as board_router
from h15hub.api.devices import make_router as make_device_router
from h15hub.api.bookings import router as booking_router
from h15hub.api.public import router as public_router
from h15hub.api.ws import make_ws_router, notify_status_change
from h15hub.models.user import UserRole

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

SESSION_SECRET = os.getenv("H15HUB_SESSION_SECRET", "h15hub-dev-session-secret")

templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(__file__), "frontend", "templates")
)


def template_context(request: Request, **extra: object) -> dict[str, object]:
    return {"request": request, **extra}


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

    # Öffentlich zugängliche Geräte (kein Login nötig)
    from h15hub.adapters.labelprinter import LabelprinterAdapter
    public: set[str] = set()
    for adapter in registry._adapters.values():
        if isinstance(adapter, LabelprinterAdapter) and adapter.public:
            for d in await adapter.get_status():
                public.add(d.id)
    app.state.public_devices = public

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
app.include_router(public_router)
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

    # HA-Entitäten vorausladen (für Wizard-Autocomplete)
    ha_entities: list[dict] = []
    try:
        import httpx as _httpx
        from h15hub.configuration import load_config as _load_config
        _cfg = _load_config()
        _ha = next(
            (c for c in _cfg.get("devices", {}).values() if c.get("adapter") == "homeassistant"),
            None,
        )
        if _ha:
            async with _httpx.AsyncClient(timeout=5.0) as _c:
                _r = await _c.get(
                    _ha["url"].rstrip("/") + "/api/states",
                    headers={"Authorization": f"Bearer {_ha.get('token', '')}"},
                )
                if _r.status_code == 200:
                    ha_entities = sorted(
                        [
                            {
                                "entity_id": s["entity_id"],
                                "name": (s.get("attributes") or {}).get("friendly_name") or s["entity_id"],
                                "state": s.get("state"),
                                "domain": s["entity_id"].split(".")[0],
                            }
                            for s in _r.json()
                        ],
                        key=lambda x: x["entity_id"],
                    )
    except Exception:
        pass  # Wizard zeigt leere Liste, Nutzer kann manuell eingeben

    return templates.TemplateResponse(
        "admin.html",
        template_context(request, current_user=current_user, ha_entities=ha_entities),
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
    public_devices: set[str] = getattr(request.app.state, "public_devices", set())
    if device_id in public_devices:
        current_user = await get_current_user_from_request(request, db)
    else:
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


@app.get("/labeldesigner", response_class=HTMLResponse)
async def labeldesigner_page(request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    current_user = await ensure_page_user(request, db)
    if isinstance(current_user, RedirectResponse):
        return current_user
    return templates.TemplateResponse(
        "labeldesigner.html",
        template_context(request, current_user=current_user),
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
    project_id: int | None = None,
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    from h15hub.models.board import BoardGroup, BoardProject

    current_user = await ensure_page_user(request, db)
    if isinstance(current_user, RedirectResponse):
        return current_user

    group_result = await db.execute(select(BoardGroup).order_by(BoardGroup.name))
    groups = list(group_result.scalars().all())
    project_result = await db.execute(
        select(BoardProject, BoardGroup)
        .join(BoardGroup, BoardProject.group_id == BoardGroup.id)
        .order_by(BoardGroup.name, BoardProject.name, BoardProject.id)
    )
    projects = [
        {
            "id": project.id,
            "name": project.name,
            "group_id": group.id,
            "group_name": group.name,
        }
        for project, group in project_result.all()
    ]

    selected_project = next((project for project in projects if project["id"] == project_id), None)
    if not selected_project and projects:
        selected_project = projects[0]

    groups_payload = [{"id": group.id, "name": group.name} for group in groups]

    return templates.TemplateResponse(
        "boards.html",
        {
            **template_context(request, current_user=current_user),
            "groups": groups,
            "groups_payload": groups_payload,
            "projects": projects,
            "projects_payload": projects,
            "selected_project": selected_project,
            "selected_project_id": selected_project["id"] if selected_project else None,
        },
    )


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "h15hub"}
