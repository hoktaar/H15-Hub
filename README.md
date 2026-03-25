# H15-Hub

Lokaler Integrations-Hub für den **Hebewerk e.V. Makerspace** (Havellandstraße 15, Eberswalde).

H15-Hub verbindet Maschinen, Buchungen und interne Arbeitsabläufe in einem gemeinsamen Web-Interface – erreichbar im lokalen Netzwerk über Port **8032**.

---

## Inhalt

- [Features](#features)
- [Seiten & Navigation](#seiten--navigation)
- [Schnellstart](#schnellstart)
- [Konfiguration](#konfiguration)
- [Adapter & Geräte](#adapter--geräte)
- [Label Designer](#label-designer)
- [Buchungen](#buchungen)
- [Projekt-Boards](#projekt-boards)
- [Admin-Bereich](#admin-bereich)
- [API-Übersicht](#api-übersicht)
- [Echtzeit via WebSocket](#echtzeit-via-websocket)
- [Rollen & Rechte](#rollen--rechte)
- [Installation auf Unraid](#installation-auf-unraid)
- [Lokale Entwicklung](#lokale-entwicklung)
- [Umgebungsvariablen](#umgebungsvariablen)

---

## Features

- **Echtzeit-Statusübersicht** aller Maschinen (frei / belegt / offline / Fehler)
- **Maschinensteuerung** direkt im Browser (Pause, Fortsetzen, Abbrechen)
- **Buchungssystem** mit Konflikt-Prüfung
- **Label Designer** – Labels gestalten und direkt auf dem Brother QL-Drucker ausgeben
- **Projekt-Boards** (Kanban) – Gruppen → Projekte → Karten mit Spalten
- **Browser-Benachrichtigungen**, wenn Maschinen frei werden
- **Administrationsoberfläche** für Benutzer, Gruppen und Konfiguration
- **Automations-Engine** mit Zykluserkennung (Tarjan's SCC-Algorithmus)
- **WebSocket** für Live-Updates ohne Seiten-Reload
- **Swagger UI** unter `/docs` für API-Erkundung

---

## Seiten & Navigation

| Route | Zugang | Beschreibung |
|---|---|---|
| `/` | Member | Dashboard – Statusübersicht aller Geräte |
| `/setup` | Offen (nur erster Start) | Ersten Admin-Account anlegen |
| `/login` | Offen | Anmeldung |
| `/device/{id}` | Member (oder öffentlich) | Gerätedetail – Status, Kamera, Steuerung |
| `/labeldesigner` | Member | Interaktiver Label Designer |
| `/bookings` | Member | Buchungskalender und -liste |
| `/boards` | Member | Projekt-Boards mit Karten |
| `/admin` | Admin | Benutzerverwaltung, Konfiguration, Gruppen |
| `/docs` | Offen | Automatische Swagger-API-Dokumentation |
| `/health` | Offen | Healthcheck-Endpunkt |

---

## Schnellstart

```bash
# 1. Konfiguration anpassen
nano config.yaml

# 2. Container starten
docker-compose up -d

# 3. Im Browser öffnen
http://localhost:8032
```

Beim **ersten Start** wird automatisch auf `/setup` weitergeleitet, wo der erste Admin-Account angelegt wird. Danach läuft die Anmeldung über `/login`.

**API-Dokumentation:** `http://localhost:8032/docs`

---

## Konfiguration

Die Konfiguration liegt in `config.yaml` (Produktion) bzw. `config.local.yaml` (lokale Entwicklung, nicht im Git).

```yaml
app:
  title: H15-Hub
  description: Hebewerk e.V. Makerspace Integration Hub
  poll_interval_seconds: 5      # Wie oft Geräte abgefragt werden (Sekunden)

devices:
  bambu:
    adapter: bambuddy
    url: http://makerspace:8000
    api_key: bb_xxxx
    printers:
      - id: bambu-p1s-ams
        name: P1S AMS

  homeassistant:
    adapter: homeassistant
    url: http://192.168.1.10:8123
    token: eyJhbGci...
    entities:
      - entity_id: switch.lasercutter_power
        name: Lasercutter
        type: lasercutter
      - entity_id: binary_sensor.werkstatt_besetzt
        name: Offene Werkstatt
        type: sensor

  labelprinter:
    adapter: labelprinter
    model: QL-500
    device: /dev/usb/lp0
    name: Labeldrucker
    public: true           # Kein Login nötig für dieses Gerät

  laserprinter_color:
    adapter: laserprinter
    id: laserprinter-color
    url: ipp://192.168.1.172/ipp/print
    web_url: http://192.168.1.172
    name: Farb-Laserdrucker

automations:
  - name: "Beispiel-Automation"
    trigger: "device:bambu-p1s-ams:status = FREE"
    action: "device:labelprinter:print"
```

Die Konfiguration kann auch direkt im **Admin-Bereich** bearbeitet werden. Änderungen am Device-Setup werden über `POST /api/admin/reload` ohne Neustart aktiviert.

---

## Adapter & Geräte

H15-Hub verbindet sich mit folgenden Gerätetypen über spezialisierte Adapter:

### BambuddyAdapter – Bambu P1S 3D-Drucker

- **Protokoll:** HTTP REST via [Bambuddy](https://github.com/aksdb/bambuddy) Docker-Container
- **Status:** idle → frei · printing/pause → belegt · error → Fehler
- **Aktionen:** pause, resume, cancel
- **Config-Key:** `adapter: bambuddy`

### HomeAssistantAdapter – HA-Entitäten

- **Protokoll:** Home Assistant REST API mit Long-Lived Token
- **Unterstützte Typen:** `lasercutter`, `sensor`, `switch`
- **Status:** on/active → belegt · off/idle → frei · unavailable → offline
- **Config-Key:** `adapter: homeassistant`

### LabelprinterAdapter – Brother QL

- **Protokoll:** USB via `brother_ql`-Bibliothek
- **Unterstützte Modelle:** QL-500, QL-550, QL-570, QL-580NX, QL-700, QL-800, QL-810W, QL-820NWB
- **Label-Format:** 62mm (Standard)
- **Aktionen:** preview (Vorschaubild), print (drucken)
- **Kann öffentlich geschaltet werden** (`public: true`) – kein Login nötig
- **Config-Key:** `adapter: labelprinter`

### LaserprinterAdapter – Netzwerk-Laserdrucker

- **Protokoll:** IPP (Internet Printing Protocol) via `pyipp`
- **Zeigt:** Tonerfüllstände, Seitenzähler, Modell, Standort
- **Status:** idle → frei · processing → belegt · stopped → Fehler
- **Config-Key:** `adapter: laserprinter`

### LasercutterAdapter – CNC-Lasercutter

- **Kann optional einen lokalen HTTP-Controller ansprechen**
- **Ohne Controller:** Status kommt aus Home Assistant
- **Aktionen (nur mit Controller):** start, stop, emergency_stop
- **Config-Key:** `adapter: lasercutter`

---

## Label Designer

Unter `/labeldesigner` gibt es einen interaktiven Editor für Brother QL Labels:

- **Text** mit Schriftart, Größe und Ausrichtung
- **QR-Code** – beliebiger Inhalt
- **Icons** aus der [Tabler Icons](https://tabler-icons.io/) Bibliothek
- **Rotation** (0°, 90°)
- **Live-Vorschau** direkt im Browser
- **Drucken** mit einem Klick auf dem angeschlossenen Brother QL-Drucker

**Verfügbare Schriften:** DejaVu Sans, DejaVu Mono, DejaVu Serif (jeweils normal und fett)

---

## Buchungen

Unter `/bookings` können Maschinenzeiten reserviert werden:

- **Kalenderansicht** und Listenansicht
- **Konflikt-Prüfung:** Überschneidungen werden automatisch erkannt
- **Felder:** Gerät, Mitgliedsname, Startzeit, Endzeit, optionale Notiz
- **Status-Verlauf:** pending → confirmed → cancelled / done

---

## Projekt-Boards

Unter `/boards` gibt es ein Kanban-System für interne Projekte:

**Hierarchie:** Gruppen → Projekte → Karten

- **Gruppen** werden im Admin-Bereich angelegt
- **Projekte** werden einer Gruppe zugeordnet
- **Karten** haben Titel, Beschreibung, Verantwortliche/n und eine Spalte:
  - `backlog` · `in_progress` · `blocked` · `done`
- Karten können per Drag & Drop sortiert werden

---

## Admin-Bereich

Erreichbar unter `/admin` (nur für Admins):

### Benutzerverwaltung
- Benutzer anlegen (Username, Anzeigename, Passwort, Rolle)
- Benutzer bearbeiten und aktivieren/deaktivieren
- Rollen: `admin` oder `member`

### Gruppenverwaltung
- Gruppen anlegen, umbenennen, löschen
- Löschen einer Gruppe entfernt automatisch alle zugehörigen Projekte und Karten

### Konfiguration
- `config.yaml` direkt im Browser bearbeiten
- Home Assistant Entities abrufen und in die Konfiguration übernehmen

### System
- `POST /api/admin/reload` – Device-Registry neu laden ohne Neustart
- Aktuelle HA-Entities abrufen über `GET /api/admin/ha-entities`

---

## API-Übersicht

Alle Endpunkte sind unter `/docs` mit Swagger UI erkundbar.

### Geräte (`/api/devices`) – Login erforderlich

| Methode | Pfad | Beschreibung |
|---|---|---|
| GET | `/api/devices` | Alle Geräte mit aktuellem Status |
| GET | `/api/devices/{id}` | Einzelnes Gerät |
| POST | `/api/devices/{id}/action` | Aktion ausführen (pause, cancel, …) |
| GET | `/api/devices/{id}/preview` | Label-Vorschau generieren |
| GET | `/api/devices/{id}/camera` | Kamera-Snapshot |

### Öffentliche Geräte (`/api/public/devices`) – kein Login

Nur für Geräte mit `public: true` in der Konfiguration.

| Methode | Pfad | Beschreibung |
|---|---|---|
| GET | `/api/public/devices/{id}/preview` | Label-Vorschau |
| POST | `/api/public/devices/{id}/action` | Aktion ausführen |
| GET | `/api/public/devices/{id}/settings` | Geräte-Einstellungen lesen |
| PUT | `/api/public/devices/{id}/settings` | Geräte-Einstellungen speichern |

### Buchungen (`/api/bookings`) – Login erforderlich

| Methode | Pfad | Beschreibung |
|---|---|---|
| GET | `/api/bookings` | Buchungen auflisten (Filter: device_id, date) |
| POST | `/api/bookings` | Neue Buchung anlegen |
| DELETE | `/api/bookings/{id}` | Buchung stornieren |

### Boards (`/api/boards`) – Login erforderlich

| Methode | Pfad | Beschreibung |
|---|---|---|
| GET | `/api/boards/groups` | Alle Gruppen |
| GET/POST | `/api/boards/projects` | Projekte auflisten / anlegen |
| PATCH/DELETE | `/api/boards/projects/{id}` | Projekt bearbeiten / löschen |
| GET/POST | `/api/boards/projects/{id}/cards` | Karten auflisten / anlegen |
| PATCH/DELETE | `/api/boards/cards/{id}` | Karte bearbeiten / löschen |

### Auth (`/api/auth`)

| Methode | Pfad | Beschreibung |
|---|---|---|
| POST | `/api/auth/setup` | Ersten Admin anlegen |
| POST | `/api/auth/login` | Anmelden |
| POST | `/api/auth/logout` | Abmelden |
| GET | `/api/auth/me` | Aktuellen Benutzer abrufen |

### Admin (`/api/admin`) – Admin erforderlich

| Methode | Pfad | Beschreibung |
|---|---|---|
| GET/POST | `/api/admin/users` | Benutzer auflisten / anlegen |
| PATCH | `/api/admin/users/{id}` | Benutzer bearbeiten |
| GET/POST | `/api/admin/groups` | Gruppen auflisten / anlegen |
| PATCH/DELETE | `/api/admin/groups/{id}` | Gruppe bearbeiten / löschen |
| GET/PATCH | `/api/admin/config` | Konfiguration lesen / schreiben |
| GET | `/api/admin/ha-entities` | Home Assistant Entities abrufen |
| POST | `/api/admin/reload` | Device-Registry neu laden |

---

## Echtzeit via WebSocket

Verbindung: `ws://localhost:8032/ws/status`

Beim Verbinden wird sofort ein `full_update` gesendet, danach alle 5 Sekunden oder bei Statusänderungen:

```json
// Vollständiges Update (Verbindungsaufbau + alle 5s)
{
  "type": "full_update",
  "devices": [ { "id": "bambu-p1s-ams", "status": "FREE", ... } ]
}

// Statusänderung
{
  "type": "status_change",
  "device_id": "bambu-p1s-ams",
  "old_status": "IN_USE",
  "new_status": "FREE",
  "device": { ... }
}
```

---

## Rollen & Rechte

| Funktion | Member | Admin |
|---|---|---|
| Dashboard, Geräte, Buchungen, Boards | ✓ | ✓ |
| Geräte steuern (pause, cancel, …) | ✓ | ✓ |
| Labels designen und drucken | ✓ | ✓ |
| Benutzer verwalten | – | ✓ |
| Gruppen verwalten | – | ✓ |
| Konfiguration bearbeiten | – | ✓ |
| System neu laden | – | ✓ |

Geräte mit `public: true` in der Konfiguration sind ohne Login erreichbar.

---

## Installation auf Unraid

### Option A: Community Applications Template

1. Unraid → **Apps** → Suchfeld: `H15-Hub`
2. Template installieren, Pfade und IPs anpassen
3. Container starten → `http://UNRAID-IP:8032`

Template manuell aktualisieren:

```bash
curl -fsSL https://raw.githubusercontent.com/hoktaar/H15-Hub/main/unraid/h15hub.xml \
  -o /boot/config/plugins/dockerMan/templates-user/h15hub.xml
```

### Option B: Docker UI (ohne compose)

```
Image:   ghcr.io/hoktaar/h15-hub:latest
Port:    8032 → 8032
Volume:  /mnt/user/appdata/h15hub/config → /app/config  (rw)
Volume:  /mnt/user/appdata/h15hub/data   → /app/data
Extra:   --add-host homeassistant:192.168.1.10 --add-host bambuddy:192.168.1.20
```

### Option C: docker-compose auf Unraid

```bash
mkdir -p /mnt/user/appdata/h15hub/config /mnt/user/appdata/h15hub/data
docker-compose -f docker-compose.unraid.yml up -d
```

Beim ersten Start wird eine Beispiel-`config.yaml` angelegt, die danach im Adminbereich bearbeitet werden kann.

---

## Lokale Entwicklung

```bash
# Abhängigkeiten installieren
pip install -e ".[dev]"

# Server starten
uvicorn h15hub.main:app --reload --port 8032

# Tests ausführen
pytest -q
```

- App: `http://localhost:8032`
- API-Doku: `http://localhost:8032/docs`

Lokale Konfiguration in `config.local.yaml` ablegen (wird nicht committed).

---

## Umgebungsvariablen

| Variable | Standard | Beschreibung |
|---|---|---|
| `H15HUB_CONFIG` | `./config.yaml` | Pfad zur Konfigurationsdatei |
| `H15HUB_DB_URL` | `sqlite+aiosqlite:///./data/h15hub.db` | Datenbank-URL |
| `H15HUB_SESSION_SECRET` | `h15hub-dev-session-secret` | Session-Signierung (in Produktion ändern!) |

---

## Technischer Stack

| Schicht | Technologie |
|---|---|
| Web-Framework | FastAPI 0.111+ |
| Server | Uvicorn 0.29+ |
| Datenbank | SQLite + SQLAlchemy (async via aiosqlite) |
| Sessions | Starlette SessionMiddleware (itsdangerous) |
| Echtzeit | WebSocket (Starlette) |
| Templates | Jinja2 3.1+ |
| HTTP-Client | httpx 0.27+ (async) |
| Label-Druck | brother_ql + PIL + cairosvg |
| Drucker-Protokoll | pyipp 0.14+ (IPP) |
| QR-Codes | qrcode[pil] 7.0+ |
| Python | 3.13+ |
