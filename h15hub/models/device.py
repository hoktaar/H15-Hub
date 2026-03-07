from __future__ import annotations
from enum import Enum
from pydantic import BaseModel


class DeviceStatus(str, Enum):
    FREE = "free"
    IN_USE = "in_use"
    OFFLINE = "offline"
    ERROR = "error"


class Device(BaseModel):
    id: str
    name: str
    type: str  # "3d_printer" | "lasercutter" | "printer" | "sensor"
    status: DeviceStatus
    current_user: str | None = None
    progress: int | None = None       # 0-100 für Drucker-Jobs
    eta_minutes: int | None = None
    capabilities: list[str] = []      # ["start", "pause", "cancel", "print"]
    raw: dict = {}                    # Original-Antwort vom Adapter


class ActionResult(BaseModel):
    success: bool
    message: str
    data: dict = {}
