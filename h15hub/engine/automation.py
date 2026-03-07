from __future__ import annotations
import logging
from h15hub.models.device import Device
from h15hub.engine.tarjan import build_automation_graph, find_cycles

logger = logging.getLogger(__name__)


class AutomationEngine:
    """
    Einfacher regelbasierter Automations-Runner.
    Regeln werden aus config.yaml geladen und gegen Tarjan's SCC validiert.
    """

    def __init__(self, automations: list[dict]) -> None:
        self._validate_no_cycles(automations)
        self.automations = automations

    def _validate_no_cycles(self, automations: list[dict]) -> None:
        graph = build_automation_graph(automations)
        cycles = find_cycles(graph)
        if cycles:
            raise ValueError(
                f"Zirkuläre Automations-Abhängigkeiten gefunden: {cycles}. "
                "Bitte die config.yaml korrigieren."
            )

    async def on_status_change(self, old: Device, new: Device) -> None:
        """Wird vom DeviceRegistry aufgerufen wenn sich ein Gerätestatus ändert."""
        for automation in self.automations:
            if self._matches_trigger(automation["trigger"], old, new):
                logger.info(
                    "Automation '%s' ausgelöst durch %s: %s → %s",
                    automation.get("name", "?"),
                    new.id,
                    old.status,
                    new.status,
                )
                await self._execute_action(automation["action"], new)

    def _matches_trigger(self, trigger: str, old: Device, new: Device) -> bool:
        """
        Prüft ob ein Trigger-String auf die Status-Änderung passt.
        Format: "device:{id}:status = {wert}"
        """
        try:
            parts = trigger.split("=")
            if len(parts) != 2:
                return False
            lhs = parts[0].strip()
            rhs = parts[1].strip()

            lhs_parts = lhs.split(":")
            if lhs_parts[0] != "device" or len(lhs_parts) < 3:
                return False

            device_id = lhs_parts[1]
            field = lhs_parts[2]

            if new.id != device_id:
                return False
            if field == "status":
                return new.status.value == rhs
            if field == "progress":
                return new.progress is not None and str(new.progress) == rhs
        except Exception:
            pass
        return False

    async def _execute_action(self, action: str, trigger_device: Device) -> None:
        """
        Führt eine Automations-Aktion aus.
        Format: "notify:member:{name}" oder "device:{id}:{action}"
        """
        parts = action.split(":")
        if not parts:
            return

        if parts[0] == "notify":
            logger.info("Benachrichtigung: %s", action)
            # WebSocket-Benachrichtigung erfolgt über device_registry callbacks
        elif parts[0] == "device" and len(parts) >= 3:
            target_id = parts[1]
            target_action = parts[2]
            logger.info("Automation: %s → %s(%s)", trigger_device.id, target_id, target_action)
            # Aktion wird über das Registry ausgeführt (Registry-Referenz wird extern injiziert)
