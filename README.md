# H15-Hub

Lokaler Integrations-Hub für den **Hebewerk e.V. Makerspace** (Havellandstraße 15, Eberswalde).

H15-Hub verbindet Geräte, Buchungen und interne Arbeitsabläufe in einem gemeinsamen Web-Interface:

- **Home Assistant** – Gebäudeautomation, Sensoren
- **Bambuddy** – Bambu P1S 3D-Drucker (Docker auf Raspberry Pi)
- **Lasercutter**
- **Labeldrucker** (Brother QL)
- **Laserdrucker** (IPP/CUPS)

## Features

- Echtzeit-Statusübersicht aller Maschinen (frei / belegt / offline)
- Maschinensteuerung direkt im Browser (z. B. Pause, Cancel)
- Buchungssystem mit Konflikt-Prüfung
- Session-basierter **Login / Logout**
- **Ersteinrichtung** über `/setup` zum Anlegen des ersten Admin-Kontos
- Rollenmodell mit **`admin`** und **`member`**
- **Adminbereich** für Benutzer-, Rollen-, Gruppen- und Konfigurationsverwaltung
- Geschützte Member-Bereiche und APIs für Dashboard, Geräte, Buchungen und Boards
- **Boards mit Projekten**, die bestehenden Gruppen zugeordnet werden, inkl. Karten, Spalten und Sortierung
- Browser-Benachrichtigungen, wenn Maschinen frei werden
- Automations-Engine mit Zyklus-Erkennung (Tarjan's SCC)

## Zugriff, Login und Rollen

### Erster Start

- Wenn noch kein Benutzer existiert, führt H15-Hub zur Ersteinrichtung unter **`/setup`**
- Dort wird das erste **Admin-Konto** angelegt

### Danach

- Anmeldung über **`/login`**
- Admins erreichen den Verwaltungsbereich unter **`/admin`**
- Angemeldete Mitglieder nutzen die geschützten Seiten:
  - `/` – Dashboard / Mitgliederbereich
  - `/device/{device_id}` – Geräteansicht
  - `/bookings` – Buchungen
  - `/boards` – Projekt-Boards mit Kartenansicht

### Rollen

- **Admin**
  - Benutzer anlegen und bearbeiten
  - Rollen ändern
  - Konten aktivieren/deaktivieren
  - Gruppen anlegen, umbenennen und löschen
- **Member**
  - geschützte Mitgliederseiten und Member-APIs nutzen

### Boards / Projekte

- **Gruppen** werden im **Adminbereich** angelegt und verwaltet
- Im Bereich **`/boards`** werden daraus **Projekte** erstellt und einer Gruppe zugeordnet
- Karten werden innerhalb eines Projekts verwaltet
- Neue Karten werden über ein **Modal** angelegt
- Projekte können im Boards-Bereich **bearbeitet und gelöscht** werden

## Schnellstart

```bash
# Konfiguration anpassen (IPs und Tokens eintragen)
nano config.yaml

# Mit Docker starten
docker-compose up

# App öffnen
open http://localhost:8032
```

Danach gilt:

- beim ersten Start: **`/setup`**
- sonst: **Login über `/login`**
- API-Dokumentation: **`/docs`**

## Installation auf Unraid

### Option A: Community Applications Template

1. In Unraid → **Apps** → Suchfeld: `H15-Hub`
2. Template installieren
3. Pfade und IPs anpassen
4. Container starten und anschließend `http://UNRAID-IP:8032` öffnen

Falls du das Unraid-Template manuell aus GitHub aktualisieren willst:

```bash
curl -fsSL https://raw.githubusercontent.com/hoktaar/H15-Hub/main/unraid/h15hub.xml -o /boot/config/plugins/dockerMan/templates-user/h15hub.xml
```

### Option B: Manuell via docker-compose

```bash
# AppData-Verzeichnis anlegen
mkdir -p /mnt/user/appdata/h15hub/data

# Verzeichnisse anlegen
mkdir -p /mnt/user/appdata/h15hub/config /mnt/user/appdata/h15hub/data

# Starten
docker-compose -f docker-compose.unraid.yml up -d

# App öffnen
open http://UNRAID-IP:8032
```

Danach wird beim ersten Start automatisch eine Beispiel-Datei unter
`/mnt/user/appdata/h15hub/config/config.yaml` angelegt. Diese kann später auch im Adminbereich bearbeitet werden.

### Option C: Unraid Docker UI (ohne compose)

```
Image:    ghcr.io/hoktaar/h15-hub:latest
Port:     8032 → 8032
Volume:   /mnt/user/appdata/h15hub/config → /app/config (rw)
Volume:   /mnt/user/appdata/h15hub/data        → /app/data
Extra:    --add-host homeassistant:192.168.1.10 --add-host bambuddy:192.168.1.20
```

Template per Shell aktualisieren:

```bash
curl -fsSL https://raw.githubusercontent.com/hoktaar/H15-Hub/main/unraid/h15hub.xml -o /boot/config/plugins/dockerMan/templates-user/h15hub.xml
```

## Entwicklung

```bash
pip install -e ".[dev]"
pytest -q
uvicorn h15hub.main:app --reload --port 8032
```

- Lokale App: `http://localhost:8032`
- API-Doku: `http://localhost:8032/docs`
- Aktueller Stand der Tests: **26 Tests grün**

Weitere Entwicklungsdetails stehen in `docs/Entwicklung.md`.