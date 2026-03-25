from __future__ import annotations
import logging
import httpx
from h15hub.adapters.base import DeviceAdapter
from h15hub.models.device import Device, DeviceStatus, ActionResult

logger = logging.getLogger(__name__)

_STATE_MAP = {
    "idle":     DeviceStatus.FREE,
    "finish":   DeviceStatus.FREE,   # Druck fertig, Platte noch nicht geräumt
    "running":  DeviceStatus.IN_USE,
    "printing": DeviceStatus.IN_USE,
    "pause":    DeviceStatus.IN_USE,
    "paused":   DeviceStatus.IN_USE,
    "failed":   DeviceStatus.ERROR,
    "error":    DeviceStatus.ERROR,
    "offline":  DeviceStatus.OFFLINE,
}


class BambuddyAdapter(DeviceAdapter):
    """Adapter für Bambuddy (Brother Bambu Lab 3D-Druckerverwaltung)."""

    def __init__(self, config: dict) -> None:
        self.web_url   = config["url"].rstrip("/")
        self.base_url  = self.web_url + "/api/v1"
        self.api_key   = config.get("api_key", "")
        self.printers  = config.get("printers", [])
        self._id_map: dict[str, int] = {}  # Druckername → Bambuddy-ID

    @property
    def _headers(self) -> dict:
        if self.api_key:
            return {"X-API-Key": self.api_key}
        return {}

    async def _resolve_ids(self, client: httpx.AsyncClient) -> None:
        """Ermittelt die numerischen Bambuddy-IDs anhand der Druckernamen."""
        if self._id_map:
            return
        try:
            r = await client.get(f"{self.base_url}/printers/")
            r.raise_for_status()
            for p in r.json():
                self._id_map[p["name"]] = p["id"]
        except Exception as e:
            logger.warning("Bambuddy ID-Auflösung fehlgeschlagen: %s", e)

    async def get_status(self) -> list[Device]:
        devices = []
        async with httpx.AsyncClient(timeout=5.0, headers=self._headers) as client:
            await self._resolve_ids(client)
            for printer in self.printers:
                devices.append(await self._fetch_status(client, printer))
        return devices

    async def _fetch_status(self, client: httpx.AsyncClient, printer: dict) -> Device:
        printer_id   = printer["id"]
        printer_name = printer.get("name", "")
        bambuddy_id  = printer.get("bambuddy_id") or self._id_map.get(printer_name)

        if not bambuddy_id:
            return Device(
                id=printer_id, name=printer_name, type="3d_printer",
                status=DeviceStatus.OFFLINE, capabilities=[],
                raw={"error": "Bambuddy-ID nicht gefunden"},
            )

        try:
            r = await client.get(f"{self.base_url}/printers/{bambuddy_id}/status")
            r.raise_for_status()
            data = r.json()

            state    = data.get("state", "offline").lower()
            status   = _STATE_MAP.get(state, DeviceStatus.OFFLINE)
            progress = data.get("progress")
            eta      = data.get("remaining_time")  # Sekunden
            subtask  = data.get("subtask_name") or data.get("current_print") or None

            caps = ["refresh_status"]
            if state in ("idle", "finish"):
                caps.append("clear_plate")

            # Smartplug-Status abrufen
            plug_id        = None
            plug_on        = None
            plug_reachable = None
            try:
                rp = await client.get(f"{self.base_url}/smart-plugs/by-printer/{bambuddy_id}")
                if rp.status_code == 200:
                    plug_data = rp.json()
                    plug_id   = plug_data.get("id")
                    if plug_id:
                        rs = await client.get(f"{self.base_url}/smart-plugs/{plug_id}/status")
                        if rs.status_code == 200:
                            ps          = rs.json()
                            plug_on     = ps.get("state", "").upper() == "ON"
                            plug_reachable = ps.get("reachable", False)
            except Exception as pe:
                logger.debug("Smartplug-Abfrage fehlgeschlagen: %s", pe)

            if plug_id:
                caps += ["plug_on", "plug_off"]

            return Device(
                id=printer_id,
                name=printer_name,
                type="3d_printer",
                status=status,
                current_user=subtask,
                progress=int(progress) if progress else None,
                eta_minutes=int(eta / 60) if eta else None,
                capabilities=caps,
                raw={
                    "bambuddy_id":   bambuddy_id,
                    "bambuddy_url":  self.web_url,
                    "state":         data.get("state"),
                    "temperatures":  data.get("temperatures", {}),
                    "ams":           data.get("ams", []),
                    "subtask":       subtask,
                    "layer":         f"{data.get('layer_num', 0)} / {data.get('total_layers', 0)}",
                    "wifi":          data.get("wifi_signal"),
                    "plate_cleared": data.get("plate_cleared"),
                    "hms_errors":    data.get("hms_errors", []),
                    "plug_id":       plug_id,
                    "plug_on":       plug_on,
                    "plug_reachable": plug_reachable,
                },
            )
        except (httpx.HTTPError, httpx.ConnectError) as e:
            return Device(
                id=printer_id, name=printer_name, type="3d_printer",
                status=DeviceStatus.OFFLINE, capabilities=[],
                raw={"error": str(e)},
            )

    async def execute_action(self, device_id: str, action: str, params: dict) -> ActionResult:
        # Bambuddy-ID für diesen Drucker ermitteln
        printer_cfg  = next((p for p in self.printers if p["id"] == device_id), None)
        printer_name = printer_cfg.get("name", "") if printer_cfg else ""

        async with httpx.AsyncClient(timeout=10.0, headers=self._headers) as client:
            await self._resolve_ids(client)
            bambuddy_id = (printer_cfg or {}).get("bambuddy_id") or self._id_map.get(printer_name)

            if not bambuddy_id:
                return ActionResult(success=False, message="Bambuddy-ID nicht gefunden.")

            if action == "clear_plate":
                r = await client.post(f"{self.base_url}/printers/{bambuddy_id}/clear-plate")
                r.raise_for_status()
                return ActionResult(success=True, message="Platte freigegeben.")

            if action == "refresh_status":
                r = await client.post(f"{self.base_url}/printers/{bambuddy_id}/refresh-status")
                r.raise_for_status()
                return ActionResult(success=True, message="Status-Aktualisierung angefordert.")

            if action in ("plug_on", "plug_off"):
                rp = await client.get(f"{self.base_url}/smart-plugs/by-printer/{bambuddy_id}")
                rp.raise_for_status()
                plug_id = rp.json().get("id")
                if not plug_id:
                    return ActionResult(success=False, message="Kein Smartplug gefunden.")
                ctrl_action = "on" if action == "plug_on" else "off"
                rc = await client.post(
                    f"{self.base_url}/smart-plugs/{plug_id}/control",
                    json={"action": ctrl_action},
                )
                rc.raise_for_status()
                return ActionResult(success=True, message=f"Steckdose {ctrl_action}geschaltet.")

            if action == "get_files":
                path = params.get("path", "/model")
                r    = await client.get(
                    f"{self.base_url}/printers/{bambuddy_id}/files",
                    params={"path": path},
                )
                r.raise_for_status()
                files = [
                    f for f in r.json().get("files", [])
                    if not f.get("is_directory")
                ]
                return ActionResult(success=True, message="", data={"files": files})

            if action == "get_snapshot":
                r = await client.get(
                    f"{self.base_url}/printers/{bambuddy_id}/camera/snapshot",
                    timeout=8.0,
                )
                r.raise_for_status()
                return ActionResult(
                    success=True, message="",
                    data={"jpeg_b64": __import__("base64").b64encode(r.content).decode()},
                )

        return ActionResult(success=False, message=f"Unbekannte Aktion: {action}")
