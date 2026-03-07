# H15-Hub

Lokaler Integrations-Hub für den **Hebewerk e.V. Makerspace** (Havellandstraße 15, Eberswalde).

Verbindet alle Geräte und Systeme im Makerspace in einem einheitlichen Dashboard:
- **Home Assistant** – Gebäudeautomation, Sensoren
- **Bambuddy** – Bambu P1S 3D-Drucker (Docker auf Raspberry Pi)
- **Lasercutter**
- **Labeldrucker** (Brother QL)
- **Laserdrucker** (IPP/CUPS)

## Features

- Echtzeit-Statusübersicht aller Maschinen (frei / belegt / offline)
- Maschinensteuerung (Pause, Cancel, etc.) direkt im Browser
- Buchungssystem mit Konflikt-Prüfung
- Browser-Benachrichtigungen wenn Maschine frei wird
- Automations-Engine mit Zyklus-Erkennung (Tarjan's SCC)

## Schnellstart

```bash
# Konfiguration anpassen (IPs und Tokens eintragen)
nano config.yaml

# Mit Docker starten
docker-compose up

# Dashboard öffnen
open http://localhost:8000
```

## Installation auf Unraid

### Option A: Community Applications Template

1. In Unraid → **Apps** → Suchfeld: `H15-Hub`
2. Template installieren
3. Pfade und IPs anpassen, Container starten

### Option B: Manuell via docker-compose

```bash
# AppData-Verzeichnis anlegen
mkdir -p /mnt/user/appdata/h15hub/data

# Konfiguration hineinkopieren und anpassen
cp config.yaml /mnt/user/appdata/h15hub/config.yaml
nano /mnt/user/appdata/h15hub/config.yaml

# Starten
docker-compose -f docker-compose.unraid.yml up -d

# Dashboard
open http://UNRAID-IP:8000
```

### Option C: Unraid Docker UI (ohne compose)

```
Image:    ghcr.io/hoktaar/h15-hub:latest
Port:     8000 → 8000
Volume:   /mnt/user/appdata/h15hub/config.yaml → /app/config.yaml (ro)
Volume:   /mnt/user/appdata/h15hub/data        → /app/data
Extra:    --add-host homeassistant:192.168.1.10 --add-host bambuddy:192.168.1.20
```

## Entwicklung

```bash
pip install -e ".[dev]"
pytest tests/ -v
uvicorn h15hub.main:app --reload
```