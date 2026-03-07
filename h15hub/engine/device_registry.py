from __future__ import annotations
import asyncio
import logging
from typing import Callable, Awaitable

from h15hub.adapters.base import DeviceAdapter
from h15hub.models.device import Device, DeviceStatus, ActionResult

logger = logging.getLogger(__name__)

# Typ für Status-Change-Callbacks
StatusChangeCallback = Callable[[Device, Device], Awaitable[None]]


class DeviceRegistry:
    """
    Zentrale Registry aller Geräte-Adapter.
    Pollt regelmäßig den Status aller Geräte und hält den aktuellen Zustand.
    Benachrichtigt registrierte Callbacks bei Status-Änderungen.
    """

    def __init__(self, poll_interval: int = 5) -> None:
        self._adapters: dict[str, DeviceAdapter] = {}
        self._current_state: dict[str, Device] = {}
        self._poll_interval = poll_interval
        self._callbacks: list[StatusChangeCallback] = []
        self._task: asyncio.Task | None = None

    def register(self, name: str, adapter: DeviceAdapter) -> None:
        self._adapters[name] = adapter

    def on_status_change(self, callback: StatusChangeCallback) -> None:
        self._callbacks.append(callback)

    async def start(self) -> None:
        """Startet den Polling-Loop im Hintergrund."""
        self._task = asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _poll_loop(self) -> None:
        while True:
            await self._poll_all()
            await asyncio.sleep(self._poll_interval)

    async def _poll_all(self) -> None:
        for name, adapter in self._adapters.items():
            try:
                devices = await adapter.get_status()
                for device in devices:
                    old = self._current_state.get(device.id)
                    self._current_state[device.id] = device
                    if old and old.status != device.status:
                        await self._notify_change(old, device)
            except Exception as e:
                logger.error("Fehler beim Polling von %s: %s", name, e)

    async def _notify_change(self, old: Device, new: Device) -> None:
        for callback in self._callbacks:
            try:
                await callback(old, new)
            except Exception as e:
                logger.error("Fehler im Status-Change-Callback: %s", e)

    def get_all(self) -> list[Device]:
        return list(self._current_state.values())

    def get(self, device_id: str) -> Device | None:
        return self._current_state.get(device_id)

    async def execute_action(self, device_id: str, action: str, params: dict) -> ActionResult:
        for adapter in self._adapters.values():
            devices = await adapter.get_status()
            if any(d.id == device_id for d in devices):
                return await adapter.execute_action(device_id, action, params)
        return ActionResult(success=False, message=f"Gerät nicht gefunden: {device_id}")


def build_registry_from_config(config: dict) -> DeviceRegistry:
    """Erstellt eine DeviceRegistry aus der config.yaml."""
    from h15hub.adapters.bambuddy import BambuddyAdapter
    from h15hub.adapters.homeassistant import HomeAssistantAdapter
    from h15hub.adapters.labelprinter import LabelprinterAdapter
    from h15hub.adapters.laserprinter import LaserprinterAdapter
    from h15hub.adapters.lasercutter import LasercutterAdapter

    adapter_map = {
        "bambuddy": BambuddyAdapter,
        "homeassistant": HomeAssistantAdapter,
        "labelprinter": LabelprinterAdapter,
        "laserprinter": LaserprinterAdapter,
        "lasercutter": LasercutterAdapter,
    }

    poll_interval = config.get("app", {}).get("poll_interval_seconds", 5)
    registry = DeviceRegistry(poll_interval=poll_interval)

    for name, device_config in config.get("devices", {}).items():
        adapter_type = device_config.get("adapter")
        adapter_cls = adapter_map.get(adapter_type)
        if adapter_cls:
            registry.register(name, adapter_cls(device_config))
        else:
            logger.warning("Unbekannter Adapter-Typ: %s", adapter_type)

    return registry
