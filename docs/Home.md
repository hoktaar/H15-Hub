# H15-Hub Wiki

Willkommen im Wiki des **H15-Hub** – dem lokalen Integrations-Hub für den [Hebewerk e.V. Makerspace](https://hebewerk-eberswalde.de) in Eberswalde.

## Was ist H15-Hub?

H15-Hub verbindet alle Geräte und Maschinen im Makerspace in einem einheitlichen Web-Dashboard. Mitglieder sehen auf einen Blick welche Maschine frei ist, können Zeiten reservieren und Geräte direkt im Browser steuern.

## Wiki-Seiten

| Seite | Inhalt |
|---|---|
| [Architektur](Architektur) | Unified Mapping Layer, Device Model, Tarjan's SCC |
| [Installation](Installation) | Docker, Raspberry Pi, Unraid |
| [Konfiguration](Konfiguration) | config.yaml Referenz, Geräte einrichten |
| [Adapter](Adapter) | Home Assistant, Bambuddy, Lasercutter, Drucker |
| [API Referenz](API-Referenz) | REST-Endpunkte, WebSocket |
| [Automations](Automations) | Regeln definieren, Zyklus-Erkennung |
| [Entwicklung](Entwicklung) | Setup, Tests, neuen Adapter hinzufügen |
| [Deployment](Deployment) | Docker Compose, GitHub Actions, Unraid |

## Schnellstart

```bash
# Konfiguration anpassen
cp config.yaml config.local.yaml
nano config.local.yaml   # IPs und Tokens eintragen

# Starten
docker-compose up -d

# Dashboard öffnen
open http://localhost:8032
```

## Geräte-Übersicht

| Gerät | Adapter | Protokoll |
|---|---|---|
| Bambu P1S 3D-Drucker | BambuddyAdapter | HTTP REST (Bambuddy Docker) |
| Home Assistant | HomeAssistantAdapter | REST API + Long-Lived Token |
| Lasercutter | LasercutterAdapter | HTTP Controller (optional) |
| Labeldrucker (Brother QL) | LabelprinterAdapter | USB / brother_ql Library |
| Netzwerkdrucker | LaserprinterAdapter | IPP (Internet Printing Protocol) |
