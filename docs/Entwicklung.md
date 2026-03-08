# Entwicklung

## Setup

```bash
git clone https://github.com/hoktaar/H15-Hub.git
cd H15-Hub

# Abhängigkeiten installieren (inkl. dev-Tools)
pip install -e ".[dev]"

# Optional: Drucker-Bibliotheken
pip install -e ".[printers]"
```

## Tests ausführen

```bash
pytest -q
```

Aktuell sind **26 Tests** grün, u. a. für:
- `test_adapters.py` – Bambuddy & HA Adapter (Status-Mapping, Mock-HTTP)
- `test_auth_admin.py` – Setup, Login, Session und Admin-Schutz
- `test_boards.py` – geschützte Board-Endpunkte und Kartenlogik
- `test_bookings.py` – Buchungs-Logik (SQLite in-memory)
- `test_tarjan.py` – Zyklus-Erkennung (inkl. AutomationEngine)

## Server lokal starten

```bash
uvicorn h15hub.main:app --reload --port 8032
# Dashboard: http://localhost:8032
# API Docs:  http://localhost:8032/docs
```

> Mit `--reload` wird der Server bei Code-Änderungen automatisch neu gestartet.

### Relevante Einstiegsrouten

- `/setup` – Ersteinrichtung des ersten Admin-Kontos
- `/login` – Anmeldung
- `/admin` – Adminbereich für Benutzer, Rollen und Gruppen
- `/boards` – geschützter Bereich für Hebewerk-Gruppen / Boards

---

## Neuen Adapter hinzufügen

1. **Datei erstellen:** `h15hub/adapters/meingeraet.py`

```python
from h15hub.adapters.base import DeviceAdapter
from h15hub.models.device import Device, DeviceStatus, ActionResult

class MeinGeraetAdapter(DeviceAdapter):
    def __init__(self, config: dict) -> None:
        self.name = config.get("name", "Mein Gerät")
        self.url = config["url"]

    async def get_status(self) -> list[Device]:
        # API abfragen, Device-Objekt zurückgeben
        return [Device(
            id="mein-geraet",
            name=self.name,
            type="sensor",
            status=DeviceStatus.FREE,
            capabilities=[],
        )]

    async def execute_action(self, device_id: str, action: str, params: dict) -> ActionResult:
        return ActionResult(success=False, message="Keine Aktionen verfügbar")
```

2. **In `device_registry.py` registrieren:**

```python
# h15hub/engine/device_registry.py
from h15hub.adapters.meingeraet import MeinGeraetAdapter

adapter_map = {
    ...
    "meingeraet": MeinGeraetAdapter,
}
```

3. **In `config.yaml` konfigurieren:**

```yaml
devices:
  mein_geraet:
    adapter: meingeraet
    url: http://192.168.1.99:8080
    name: "Mein Gerät"
```

4. **Tests schreiben:** `tests/test_adapters.py` erweitern

---

## Projektstruktur

```
h15hub/
├── main.py                  FastAPI App + Lifespan
├── database.py              SQLAlchemy async Setup
├── models/
│   ├── device.py            Unified Device Model (Pydantic)
│   └── booking.py           Buchungs-Model (SQLAlchemy)
├── adapters/
│   ├── base.py              Abstract DeviceAdapter
│   ├── bambuddy.py
│   ├── homeassistant.py
│   ├── lasercutter.py
│   ├── labelprinter.py
│   └── laserprinter.py
├── engine/
│   ├── device_registry.py   Polling + Callbacks
│   ├── tarjan.py            Tarjan's SCC Algorithmus
│   └── automation.py        Automations-Engine
├── api/
│   ├── devices.py           REST: Geräte
│   ├── bookings.py          REST: Buchungen
│   └── ws.py                WebSocket
└── frontend/
    └── templates/           Jinja2 HTML Templates
```

---

## Code-Stil

- Python 3.11+, `from __future__ import annotations`
- Async/await durchgehend (FastAPI, SQLAlchemy, httpx)
- Pydantic v2 für alle Datenmodelle
- Keine externen Linter-Konfigurationen – einfach sauber halten
