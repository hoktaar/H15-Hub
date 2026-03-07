from __future__ import annotations
import httpx
from h15hub.adapters.base import DeviceAdapter
from h15hub.models.device import Device, DeviceStatus, ActionResult


class LaserprinterAdapter(DeviceAdapter):
    """
    Adapter für Netzwerk-Laserdrucker via IPP (Internet Printing Protocol).
    """

    def __init__(self, config: dict) -> None:
        self.ipp_url = config["url"]
        self.name = config.get("name", "Laserdrucker")

    async def get_status(self) -> list[Device]:
        try:
            import pyipp
            async with pyipp.IPP(self.ipp_url) as ipp:
                printer_info = await ipp.printer()
                state = printer_info.info.state.value if printer_info.info else "unknown"
                status = _map_ipp_state(state)
                return [
                    Device(
                        id="laserprinter",
                        name=self.name,
                        type="printer",
                        status=status,
                        capabilities=["print"],
                        raw={"state": state},
                    )
                ]
        except Exception:
            return [
                Device(
                    id="laserprinter",
                    name=self.name,
                    type="printer",
                    status=DeviceStatus.OFFLINE,
                    capabilities=[],
                )
            ]

    async def execute_action(self, device_id: str, action: str, params: dict) -> ActionResult:
        return ActionResult(
            success=False,
            message="Druckjobs werden direkt über das Betriebssystem gesendet",
        )


def _map_ipp_state(state: str) -> DeviceStatus:
    if "idle" in state:
        return DeviceStatus.FREE
    if "processing" in state:
        return DeviceStatus.IN_USE
    if "stopped" in state or "error" in state:
        return DeviceStatus.ERROR
    return DeviceStatus.OFFLINE
