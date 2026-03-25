from __future__ import annotations
import asyncio
import logging
import re
import time
from typing import Any

import httpx
from h15hub.adapters.base import DeviceAdapter
from h15hub.models.device import Device, DeviceStatus, ActionResult

logger = logging.getLogger(__name__)

# Web-Info TTL in Sekunden (Seitenanzahl, Trommel etc. sind nicht zeitkritisch)
_WEB_CACHE_TTL = 60


class LaserprinterAdapter(DeviceAdapter):
    """
    Adapter für Brother Netzwerk-Laserdrucker.
    Nutzt IPP für schnellen Status + Tonerfüllstand.
    Scrapt optional das Web-Interface für Seitenanzahl und Verbrauchsmaterial.
    """

    def __init__(self, config: dict) -> None:
        self.ipp_url   = config["url"]
        self.web_url   = config.get("web_url", "")
        self.name      = config.get("name", "Laserdrucker")
        self.device_id = config.get("id", "laserprinter")
        self._web_cache: dict[str, Any] = {}
        self._web_cache_ts: float = 0.0

    async def get_status(self) -> list[Device]:
        raw: dict[str, Any] = {}

        # ── IPP-Status ───────────────────────────────────────────────────
        try:
            import pyipp
            async with pyipp.IPP(self.ipp_url) as ipp:
                printer_info = await ipp.printer()

            state  = printer_info.state.printer_state if printer_info.state else "unknown"
            status = _map_ipp_state(state)

            info = printer_info.info
            raw["model"]       = info.model       if info else ""
            raw["manufacturer"] = info.manufacturer if info else ""
            raw["location"]    = info.location    if info else ""
            raw["state_msg"]   = (printer_info.state.message or "").strip() if printer_info.state else ""

            # Toner aus markers
            raw["toner"] = []
            for m in (printer_info.markers or []):
                short = _toner_short(m.name, m.color)
                raw["toner"].append({
                    "name":  short,
                    "label": m.name,
                    "color": m.color or "#888888",
                    "level": m.level,
                    "low":   m.low_level,
                })

        except Exception as e:
            logger.debug("IPP-Fehler für %s: %s", self.device_id, e)
            status = DeviceStatus.OFFLINE

        # ── Web-Interface (gecacht) ──────────────────────────────────────
        if self.web_url and status != DeviceStatus.OFFLINE:
            now = time.monotonic()
            if now - self._web_cache_ts > _WEB_CACHE_TTL:
                try:
                    web = await _fetch_web_info(self.web_url)
                    self._web_cache    = web
                    self._web_cache_ts = now
                except Exception as e:
                    logger.debug("Web-Scraping für %s fehlgeschlagen: %s", self.device_id, e)
            if self._web_cache:
                raw.update(self._web_cache)

        return [Device(
            id=self.device_id,
            name=self.name,
            type="printer",
            status=status,
            capabilities=[],
            raw=raw if raw else None,
        )]

    async def execute_action(self, device_id: str, action: str, params: dict) -> ActionResult:
        return ActionResult(
            success=False,
            message="Druckjobs werden direkt über das Betriebssystem gesendet.",
        )


# ── Hilfsfunktionen ──────────────────────────────────────────────────────────

def _map_ipp_state(state: str) -> DeviceStatus:
    s = state.lower()
    if "idle" in s:
        return DeviceStatus.FREE
    if "processing" in s:
        return DeviceStatus.IN_USE
    if "stopped" in s or "error" in s:
        return DeviceStatus.ERROR
    return DeviceStatus.OFFLINE


def _toner_short(name: str, color: str | None) -> str:
    n = name.upper()
    if "BLACK" in n or "BK" in n:
        return "BK"
    if "CYAN" in n:
        return "C"
    if "MAGENTA" in n:
        return "M"
    if "YELLOW" in n:
        return "Y"
    if color == "#000000":
        return "BK"
    if color == "#00FFFF":
        return "C"
    if color == "#FF00FF":
        return "M"
    if color == "#FFFF00":
        return "Y"
    return name[:2].upper()


async def _fetch_web_info(base_url: str) -> dict[str, Any]:
    """Lädt Seitenanzahl und Verbrauchsmaterial vom Brother-Web-Interface."""
    result: dict[str, Any] = {}
    async with httpx.AsyncClient(follow_redirects=True, timeout=8) as client:
        resp = await client.get(f"{base_url}/general/information.html?kind=item")
        if resp.status_code != 200:
            return result
        html = resp.text

    # Geordnete dt/dd Paare parsen (Duplikate beibehalten!)
    raw_pairs: list[tuple[str, str]] = []
    for k, v in re.findall(r'<dt[^>]*>(.*?)</dt>\s*<dd[^>]*>(.*?)</dd>', html, re.DOTALL):
        k = re.sub(r'<[^>]+>', '', k).replace('&#32;', ' ').replace('&nbsp;', ' ').strip()
        v = re.sub(r'<[^>]+>', ' ', v).replace('&#32;', ' ').replace('&nbsp;', ' ')
        v = ' '.join(v.split()).strip()
        if k:
            raw_pairs.append((k, v))

    # Seitenanzahl: "Page Counter" gefolgt von "Color" und "B&W" (Print-Abschnitt = letzter Block)
    pc_idx = next((i for i, (k, _) in reversed(list(enumerate(raw_pairs))) if k == "Page Counter"), None)
    if pc_idx is not None:
        try:
            result["page_count"] = int(raw_pairs[pc_idx][1].split()[0])
        except (ValueError, IndexError):
            pass
        # Suche Color und B&W direkt danach
        for offset in range(1, 5):
            if pc_idx + offset >= len(raw_pairs):
                break
            lk, lv = raw_pairs[pc_idx + offset]
            if lk == "Color":
                try:
                    result["page_count_color"] = int(lv.split()[0])
                except (ValueError, IndexError):
                    pass
            elif lk in ("B&W", "B&amp;W"):
                try:
                    result["page_count_bw"] = int(lv.split()[0])
                except (ValueError, IndexError):
                    pass

    # Verbrauchsmaterial: geordnet durch pairs iterieren
    consumable_map = {
        "Drum Unit Cyan (C)*":    ("Trommel C",    "#00FFFF"),
        "Drum Unit Magenta (M)*": ("Trommel M",    "#FF00FF"),
        "Drum Unit Yellow (Y)*":  ("Trommel Y",    "#FFFF00"),
        "Drum Unit Black (BK)*":  ("Trommel BK",   "#444"),
        "Belt Unit":              ("Transferband",  "#888888"),
        "Fuser Unit":             ("Fixiereinheit", "#888888"),
        "Paper Feeding Kit 1":    ("Einzug Fach 1", "#888888"),
    }
    consumables: list[dict] = []
    i = 0
    while i < len(raw_pairs):
        key, val = raw_pairs[i]
        if key in consumable_map:
            label, color = consumable_map[key]
            pct: float | None = None
            # Suche direkt dahinter nach "% of Life Remaining"
            if i + 1 < len(raw_pairs) and "Life Remaining" in raw_pairs[i + 1][0]:
                m = re.search(r'(\d+(?:\.\d+)?)', raw_pairs[i + 1][1])
                if m:
                    pct = float(m.group(1))
                    i += 1  # überspringe % Remaining Zeile
            # Inline percentage in value
            if pct is None:
                m = re.search(r'\((\d+(?:\.\d+)?)%\)', val)
                if m:
                    pct = float(m.group(1))
            if pct is not None and pct > 0:
                consumables.append({"name": label, "color": color, "level": pct})
        i += 1

    if consumables:
        result["consumables"] = consumables

    return result
