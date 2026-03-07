from __future__ import annotations
from h15hub.adapters.base import DeviceAdapter
from h15hub.models.device import Device, DeviceStatus, ActionResult


class LabelprinterAdapter(DeviceAdapter):
    """
    Adapter für Brother QL Labeldrucker.
    Nutzt die brother_ql Python-Library für Druckjobs.
    """

    def __init__(self, config: dict) -> None:
        self.model = config.get("model", "QL-800")
        self.device_path = config.get("device", "/dev/usb/lp0")
        self.name = config.get("name", "Labeldrucker")

    async def get_status(self) -> list[Device]:
        import os
        available = os.path.exists(self.device_path)
        return [
            Device(
                id="labelprinter",
                name=self.name,
                type="printer",
                status=DeviceStatus.FREE if available else DeviceStatus.OFFLINE,
                capabilities=["print"] if available else [],
            )
        ]

    async def execute_action(self, device_id: str, action: str, params: dict) -> ActionResult:
        if action != "print":
            return ActionResult(success=False, message=f"Unbekannte Aktion: {action}")

        text = params.get("text")
        if not text:
            return ActionResult(success=False, message="Parameter 'text' fehlt")

        try:
            from brother_ql.conversion import convert
            from brother_ql.backends.helpers import send
            from brother_ql.raster import BrotherQLRaster
            from PIL import Image, ImageDraw, ImageFont

            # Einfaches Text-Label erstellen
            img = Image.new("RGB", (400, 100), color="white")
            draw = ImageDraw.Draw(img)
            draw.text((10, 10), text, fill="black")

            qlr = BrotherQLRaster(self.model)
            qlr.exception_on_warning = True
            instructions = convert(qlr=qlr, images=[img], label="62")

            send(
                instructions=instructions,
                printer_identifier=self.device_path,
                backend_identifier="pyusb",
            )
            return ActionResult(success=True, message="Label gedruckt")
        except Exception as e:
            return ActionResult(success=False, message=str(e))
