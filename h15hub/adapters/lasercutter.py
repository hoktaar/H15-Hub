from __future__ import annotations
import httpx
from h15hub.adapters.base import DeviceAdapter
from h15hub.models.device import Device, DeviceStatus, ActionResult


class LasercutterAdapter(DeviceAdapter):
    """
    Adapter für den Lasercutter.
    Liest den Status über Home Assistant (switch/sensor) aus.
    Direkte Steuerung über optionalen lokalen HTTP-Controller möglich.
    """

    def __init__(self, config: dict) -> None:
        self.name = config.get("name", "Lasercutter")
        self.controller_url: str | None = config.get("controller_url")

    async def get_status(self) -> list[Device]:
        # Status kommt primär über Home Assistant (siehe homeassistant.py).
        # Falls ein lokaler Controller vorhanden ist, diesen abfragen.
        if self.controller_url:
            return await self._fetch_controller_status()

        # Fallback: immer als FREE anzeigen (HA-Adapter liefert den echten Status)
        return [
            Device(
                id="lasercutter",
                name=self.name,
                type="lasercutter",
                status=DeviceStatus.FREE,
                capabilities=["start", "stop", "emergency_stop"],
            )
        ]

    async def _fetch_controller_status(self) -> list[Device]:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.controller_url}/status")
                resp.raise_for_status()
                data = resp.json()
                state = data.get("state", "idle")
                return [
                    Device(
                        id="lasercutter",
                        name=self.name,
                        type="lasercutter",
                        status=DeviceStatus.IN_USE if state == "running" else DeviceStatus.FREE,
                        progress=data.get("progress"),
                        capabilities=["start", "stop", "emergency_stop"],
                        raw=data,
                    )
                ]
        except (httpx.HTTPError, httpx.ConnectError):
            return [
                Device(
                    id="lasercutter",
                    name=self.name,
                    type="lasercutter",
                    status=DeviceStatus.OFFLINE,
                    capabilities=[],
                )
            ]

    async def execute_action(self, device_id: str, action: str, params: dict) -> ActionResult:
        if not self.controller_url:
            return ActionResult(
                success=False,
                message="Kein lokaler Controller konfiguriert. Steuerung über Home Assistant.",
            )
        valid = {"start", "stop", "emergency_stop"}
        if action not in valid:
            return ActionResult(success=False, message=f"Unbekannte Aktion: {action}")
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(
                    f"{self.controller_url}/{action}", json=params
                )
                resp.raise_for_status()
                return ActionResult(success=True, message=f"{action} ausgeführt", data=resp.json())
        except httpx.HTTPError as e:
            return ActionResult(success=False, message=str(e))
