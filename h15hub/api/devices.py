import base64
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import Response

from h15hub.auth import require_authenticated_user
from h15hub.models.device import Device, ActionResult

router = APIRouter(
    prefix="/api/devices",
    tags=["devices"],
    dependencies=[Depends(require_authenticated_user)],
)


def make_router(_registry=None) -> APIRouter:
    @router.get("", response_model=list[Device])
    async def list_devices(request: Request) -> list[Device]:
        return request.app.state.registry.get_all()

    @router.get("/{device_id}", response_model=Device)
    async def get_device(request: Request, device_id: str) -> Device:
        device = request.app.state.registry.get(device_id)
        if not device:
            raise HTTPException(status_code=404, detail=f"Gerät nicht gefunden: {device_id}")
        return device

    @router.post("/{device_id}/action", response_model=ActionResult)
    async def device_action(request: Request, device_id: str, body: dict) -> ActionResult:
        action = body.get("action")
        params = body.get("params", {})
        if not action:
            raise HTTPException(status_code=400, detail="'action' fehlt im Request-Body")
        return await request.app.state.registry.execute_action(device_id, action, params)

    @router.get("/{device_id}/preview")
    async def device_preview(
        request: Request,
        device_id: str,
        text:        str = Query(default=""),
        qr_text:     str = Query(default=""),
        qr_type:     str = Query(default="text"),
        label:       str = Query(default="62"),
        font_size:   int = Query(default=72),
        font_family: str = Query(default="dejavu_sans"),
        align:       str = Query(default="left"),
        bold:        int = Query(default=1),
        rotate:      int = Query(default=0),
        text_rotate: int = Query(default=0),
        qr_size:     int = Query(default=80),
        qr_pos:      str = Query(default="left"),
        icon:        str = Query(default=""),
        icon_size:   int = Query(default=80),
        icon_pos:    str = Query(default="right"),
    ) -> Response:
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
        return Response(content=png, media_type="image/png",
                        headers={"Cache-Control": "no-store"})

    @router.get("/{device_id}/camera")
    async def device_camera(request: Request, device_id: str) -> Response:
        result = await request.app.state.registry.execute_action(
            device_id, "get_snapshot", {}
        )
        if not result.success or not result.data:
            raise HTTPException(status_code=503, detail="Kamera nicht verfügbar")
        jpeg = base64.b64decode(result.data["jpeg_b64"])
        return Response(content=jpeg, media_type="image/jpeg")

    return router
