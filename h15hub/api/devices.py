from fastapi import APIRouter, Depends, HTTPException, Request

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

    return router
