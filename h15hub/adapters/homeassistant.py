from __future__ import annotations
import httpx
from h15hub.adapters.base import DeviceAdapter
from h15hub.models.device import Device, DeviceStatus, ActionResult

_TYPE_CAPABILITIES: dict[str, list[str]] = {
    "lasercutter": ["start", "stop"],
    "sensor": [],
    "switch": ["turn_on", "turn_off"],
}


class HomeAssistantAdapter(DeviceAdapter):
    """
    Adapter für Home Assistant.
    Liest Entity-States über die HA REST-API aus und mappt sie auf Device-Objekte.
    """

    def __init__(self, config: dict) -> None:
        self.base_url = config["url"].rstrip("/")
        self.token = config["token"]
        self.entities: list[dict] = config.get("entities", [])

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    async def get_status(self) -> list[Device]:
        devices = []
        async with httpx.AsyncClient(timeout=5.0) as client:
            for entity_cfg in self.entities:
                device = await self._fetch_entity(client, entity_cfg)
                devices.append(device)
        return devices

    async def _fetch_entity(self, client: httpx.AsyncClient, entity_cfg: dict) -> Device:
        entity_id = entity_cfg["entity_id"]
        device_type = entity_cfg.get("type", "sensor")
        name = entity_cfg["name"]

        try:
            resp = await client.get(
                f"{self.base_url}/api/states/{entity_id}",
                headers=self._headers(),
            )
            resp.raise_for_status()
            data = resp.json()
            state = data.get("state", "unavailable")
            status = _map_ha_state(state)

            return Device(
                id=entity_id,
                name=name,
                type=device_type,
                status=status,
                capabilities=_TYPE_CAPABILITIES.get(device_type, []),
                raw=data,
            )
        except (httpx.HTTPError, httpx.ConnectError):
            return Device(
                id=entity_id,
                name=name,
                type=device_type,
                status=DeviceStatus.OFFLINE,
                capabilities=[],
            )

    async def execute_action(self, device_id: str, action: str, params: dict) -> ActionResult:
        # Findet die Entity-Config für die device_id
        entity_cfg = next((e for e in self.entities if e["entity_id"] == device_id), None)
        if not entity_cfg:
            return ActionResult(success=False, message=f"Unbekanntes Gerät: {device_id}")

        # Mappt lokale Actions auf HA-Service-Calls
        service_map = {
            "turn_on": ("homeassistant", "turn_on"),
            "turn_off": ("homeassistant", "turn_off"),
            "start": ("homeassistant", "turn_on"),
            "stop": ("homeassistant", "turn_off"),
        }
        if action not in service_map:
            return ActionResult(success=False, message=f"Unbekannte Aktion: {action}")

        domain, service = service_map[action]
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(
                    f"{self.base_url}/api/services/{domain}/{service}",
                    headers=self._headers(),
                    json={"entity_id": device_id, **params},
                )
                resp.raise_for_status()
                return ActionResult(success=True, message=f"{action} erfolgreich")
        except httpx.HTTPError as e:
            return ActionResult(success=False, message=str(e))


def _map_ha_state(state: str) -> DeviceStatus:
    if state in ("on", "open", "active", "running"):
        return DeviceStatus.IN_USE
    if state in ("off", "closed", "idle"):
        return DeviceStatus.FREE
    if state in ("unavailable", "unknown"):
        return DeviceStatus.OFFLINE
    return DeviceStatus.FREE
