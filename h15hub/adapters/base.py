from abc import ABC, abstractmethod
from h15hub.models.device import Device, ActionResult


class DeviceAdapter(ABC):
    """Einheitliches Interface für alle Geräte-Adapter."""

    @abstractmethod
    async def get_status(self) -> list[Device]:
        """Aktuellen Status aller Geräte dieses Adapters abfragen."""

    @abstractmethod
    async def execute_action(self, device_id: str, action: str, params: dict) -> ActionResult:
        """
        Aktion auf einem Gerät ausführen.
        Mögliche actions: "start", "pause", "resume", "cancel", "print"
        """
