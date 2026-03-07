from fastapi import APIRouter, HTTPException
from h15hub.models.device import Device, ActionResult
from h15hub.engine.device_registry import DeviceRegistry

router = APIRouter(prefix="/api/devices", tags=["devices"])


def make_router(registry: DeviceRegistry) -> APIRouter:
    @router.get("", response_model=list[Device])
    async def list_devices() -> list[Device]:
        return registry.get_all()

    @router.get("/{device_id}", response_model=Device)
    async def get_device(device_id: str) -> Device:
        device = registry.get(device_id)
        if not device:
            raise HTTPException(status_code=404, detail=f"Gerät nicht gefunden: {device_id}")
        return device

    @router.post("/{device_id}/action", response_model=ActionResult)
    async def device_action(device_id: str, body: dict) -> ActionResult:
        action = body.get("action")
        params = body.get("params", {})
        if not action:
            raise HTTPException(status_code=400, detail="'action' fehlt im Request-Body")
        return await registry.execute_action(device_id, action, params)

    return router
