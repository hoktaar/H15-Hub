# Architektur

## Überblick

```
Browser
  │  WebSocket /ws/status (Echtzeit)
  │  HTTP REST /api/...
  ▼
┌─────────────────────────────────────────┐
│              FastAPI App                │
│  ┌──────────┐ ┌──────────┐ ┌────────┐  │
│  │ /devices │ │/bookings │ │  /ws   │  │
│  └────┬─────┘ └────┬─────┘ └───┬────┘  │
│       └─────────────┴───────────┘       │
│              Device Registry            │
│         (pollt alle 5 Sekunden)         │
│  ┌──────────────────────────────────┐   │
│  │       Unified Mapping Layer      │   │
│  │  ┌────────┐ ┌────┐ ┌─────────┐  │   │
│  │  │Bambuddy│ │ HA │ │Lasercutr│  │   │
│  │  └────────┘ └────┘ └─────────┘  │   │
│  └──────────────────────────────────┘   │
│  ┌──────────────────────────────────┐   │
│  │       Automations Engine         │   │
│  │    (Tarjan's SCC Validierung)    │   │
│  └──────────────────────────────────┘   │
└─────────────────────────────────────────┘
         │           │           │
    Bambuddy    Home Assistant  Drucker
    :8080        :8123          IPP
```

## Unified Mapping Layer

Jedes Gerät hat eine andere API. Der Adapter-Layer übersetzt alle Formate in ein einheitliches `Device`-Modell:

```python
class Device(BaseModel):
    id: str              # "bambu-p1s-1", "lasercutter", ...
    name: str            # Anzeigename
    type: str            # "3d_printer" | "lasercutter" | "printer" | "sensor"
    status: DeviceStatus # FREE | IN_USE | OFFLINE | ERROR
    current_user: str | None
    progress: int | None    # 0–100 für Druckfortschritt
    eta_minutes: int | None
    capabilities: list[str] # ["pause", "cancel", "print", ...]
    raw: dict               # Original-API-Antwort (für Debugging)
```

Jeder Adapter implementiert dasselbe Interface:

```python
class DeviceAdapter(ABC):
    async def get_status(self) -> list[Device]: ...
    async def execute_action(self, device_id, action, params) -> ActionResult: ...
```

## Device Registry

Die `DeviceRegistry` ist das Herzstück:
- Registriert alle konfigurierten Adapter beim Start
- Pollt jeden Adapter alle N Sekunden (konfigurierbar, Standard: 5s)
- Hält den aktuellen Status aller Geräte im Speicher
- Ruft registrierte Callbacks auf wenn sich ein Status ändert

```
Registry.start()
  └── _poll_loop()  ← alle 5s
        ├── BambuddyAdapter.get_status()
        ├── HomeAssistantAdapter.get_status()
        ├── LasercutterAdapter.get_status()
        └── on_status_change(old, new)
              ├── notify_status_change()  → WebSocket broadcast
              └── AutomationEngine.on_status_change()
```

## Tarjan's SCC – Zyklus-Erkennung

Automations-Regeln können zirkuläre Abhängigkeiten erzeugen. Beim Start analysiert H15-Hub alle Regeln als gerichteten Graphen mit **Tarjan's Strongly Connected Components Algorithmus**:

```
Regel A: lasercutter:free  → bambu:start
Regel B: bambu:free        → lasercutter:start
→ Zyklus! A→B→A → Server-Start schlägt fehl
```

Jede SCC mit mehr als einem Knoten ist ein Zyklus und wird mit einer klaren Fehlermeldung abgelehnt.

## Datenbankschema

SQLite via SQLAlchemy (async). Tabelle `bookings`:

| Spalte | Typ | Beschreibung |
|---|---|---|
| id | INTEGER | Primary Key |
| device_id | VARCHAR | Geräte-ID |
| member_name | VARCHAR | Name des Mitglieds |
| start_time | DATETIME | Buchungsbeginn |
| end_time | DATETIME | Buchungsende |
| status | ENUM | confirmed / cancelled / done |
| note | VARCHAR | Optionale Notiz |
