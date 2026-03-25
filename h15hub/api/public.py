"""Public API endpoints — no authentication required, only for public devices."""
from __future__ import annotations
import base64
import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from h15hub.database import get_db

router = APIRouter(prefix="/api/public/devices", tags=["public"])


def _require_public(request: Request, device_id: str) -> None:
    public_devices: set[str] = getattr(request.app.state, "public_devices", set())
    if device_id not in public_devices:
        raise HTTPException(status_code=404, detail="Gerät nicht gefunden")


@router.get("/{device_id}/preview")
async def public_preview(
    request: Request,
    device_id: str,
    text:         str = Query(default=""),
    qr_text:      str = Query(default=""),
    qr_type:      str = Query(default="text"),
    label:        str = Query(default="62"),
    font_size:    int = Query(default=72),
    font_family:  str = Query(default="dejavu_sans"),
    align:        str = Query(default="left"),
    bold:         int = Query(default=1),
    rotate:       int = Query(default=0),
    text_rotate:  int = Query(default=0),
    qr_size:      int = Query(default=80),
    qr_pos:       str = Query(default="left"),
    icon:         str = Query(default=""),
    icon_size:    int = Query(default=80),
    icon_pos:     str = Query(default="right"),
) -> Response:
    _require_public(request, device_id)
    result = await request.app.state.registry.execute_action(
        device_id, "preview", {
            "text": text, "qr_text": qr_text, "qr_type": qr_type,
            "label": label, "font_size": font_size, "font_family": font_family,
            "align": align, "bold": bool(bold),
            "rotate": rotate, "text_rotate": text_rotate,
            "qr_size": qr_size, "qr_pos": qr_pos,
            "icon": icon, "icon_size": icon_size, "icon_pos": icon_pos,
        }
    )
    if not result.success or not result.data:
        raise HTTPException(status_code=422, detail=result.message or "Vorschau nicht verfügbar")
    png = base64.b64decode(result.data["png_b64"])
    return Response(content=png, media_type="image/png", headers={"Cache-Control": "no-store"})


@router.post("/{device_id}/action")
async def public_action(request: Request, device_id: str, body: dict) -> dict:
    _require_public(request, device_id)
    action = body.get("action")
    params = body.get("params", {})
    if not action:
        raise HTTPException(status_code=400, detail="'action' fehlt")
    result = await request.app.state.registry.execute_action(device_id, action, params)
    return {"success": result.success, "message": result.message, "data": result.data}


@router.get("/{device_id}/settings")
async def get_settings(
    request: Request, device_id: str, db: AsyncSession = Depends(get_db)
) -> dict:
    _require_public(request, device_id)
    from h15hub.models.settings import DeviceSettings
    row = await db.get(DeviceSettings, device_id)
    if row:
        return json.loads(row.settings_json)
    return {}


@router.put("/{device_id}/settings")
async def put_settings(
    request: Request, device_id: str, db: AsyncSession = Depends(get_db)
) -> dict:
    _require_public(request, device_id)
    body = await request.json()
    from h15hub.models.settings import DeviceSettings
    row = await db.get(DeviceSettings, device_id)
    if row:
        row.settings_json = json.dumps(body)
    else:
        row = DeviceSettings(device_id=device_id, settings_json=json.dumps(body))
        db.add(row)
    await db.commit()
    return {"ok": True}
