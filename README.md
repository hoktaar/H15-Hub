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

## Entwicklung

```bash
pip install -e ".[dev]"
pytest tests/ -v
uvicorn h15hub.main:app --reload
```