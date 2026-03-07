from __future__ import annotations
import httpx
from h15hub.adapters.base import DeviceAdapter
from h15hub.models.device import Device, DeviceStatus, ActionResult


class BambuddyAdapter(DeviceAdapter):
    """
    Adapter für Bambuddy – einen Docker-Dienst der Bambu P1S 3D-Drucker verwaltet.
    Erwartet eine REST-API unter der konfigurierten URL.
    """

    def __init__(self, config: dict) -> None:
        self.base_url = config["url"].rstrip("/")
        self.printers: list[dict] = config.get("printers", [])

    async def get_status(self) -> list[Device]:
        devices = []
        async with httpx.AsyncClient(timeout=5.0) as client:
            for printer in self.printers:
                device = await self._fetch_printer_status(client, printer)
                devices.append(device)
        return devices

    async def _fetch_printer_status(self, client: httpx.AsyncClient, printer: dict) -> Device:
        printer_id = printer["id"]
        try:
            resp = await client.get(f"{self.base_url}/printers/{printer_id}")
            resp.raise_for_status()
            data = resp.json()

            state = data.get("state", "idle")
            status = _map_bambu_state(state)
            progress = data.get("print_progress")  # 0-100 oder None
            eta = data.get("eta_minutes")
            current_user = data.get("started_by")

            return Device(
                id=printer_id,
                name=printer["name"],
                type="3d_printer",
                status=status,
                current_user=current_user,
                progress=int(progress) if progress is not None else None,
                eta_minutes=int(eta) if eta is not None else None,
                capabilities=["pause", "resume", "cancel"],
                raw=data,
            )
        except (httpx.HTTPError, httpx.ConnectError):
            return Device(
                id=printer_id,
                name=printer["name"],
                type="3d_printer",
                status=DeviceStatus.OFFLINE,
                capabilities=[],
            )

    async def execute_action(self, device_id: str, action: str, params: dict) -> ActionResult:
        valid_actions = {"pause", "resume", "cancel"}
        if action not in valid_actions:
            return ActionResult(success=False, message=f"Unbekannte Aktion: {action}")
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(
                    f"{self.base_url}/printers/{device_id}/{action}",
                    json=params,
                )
                resp.raise_for_status()
                return ActionResult(success=True, message=f"{action} erfolgreich", data=resp.json())
        except httpx.HTTPError as e:
            return ActionResult(success=False, message=str(e))


def _map_bambu_state(state: str) -> DeviceStatus:
    mapping = {
        "idle": DeviceStatus.FREE,
        "printing": DeviceStatus.IN_USE,
        "paused": DeviceStatus.IN_USE,
        "error": DeviceStatus.ERROR,
        "offline": DeviceStatus.OFFLINE,
    }
    return mapping.get(state, DeviceStatus.OFFLINE)
