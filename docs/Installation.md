# Installation

## Voraussetzungen

- Docker + Docker Compose
- Netzwerkzugang zu den lokalen Diensten (Home Assistant, Bambuddy, etc.)
- `config.yaml` mit den korrekten IPs und Tokens

---

## Option 1: Docker Compose (Standard)

```bash
# Repository klonen
git clone https://github.com/hoktaar/H15-Hub.git
cd H15-Hub

# Konfiguration anpassen
cp config.yaml config.local.yaml
nano config.local.yaml

# Starten
docker-compose up -d

# Logs anzeigen
docker-compose logs -f

# Dashboard öffnen
open http://localhost:8000
```

---

## Option 2: Unraid

### Via Community Applications

1. Unraid → **Apps** → Suchfeld: `H15-Hub`
2. Template auswählen, **Install** klicken
3. Felder ausfüllen:
   - **Home Assistant IP**: z.B. `192.168.1.10`
   - **Bambuddy IP**: z.B. `192.168.1.20`
4. **Apply** klicken – Container startet automatisch

> Der Container legt beim ersten Start eine Beispiel-`config.yaml` unter `/mnt/user/appdata/h15hub/config/config.yaml` an.
> Passe sie dort an deine Umgebung an und starte den Container neu.

### Via Unraid Docker UI (manuell)

| Feld | Wert |
|---|---|
| Image | `ghcr.io/hoktaar/h15-hub:latest` |
| Port | `8031` → `8000` |
| Volume | `/mnt/user/appdata/h15hub/config` → `/app/config` (ro) |
| Volume | `/mnt/user/appdata/h15hub/data` → `/app/data` |

---

## Option 3: Raspberry Pi (ohne Docker)

```bash
# Python 3.11+ vorausgesetzt
git clone https://github.com/hoktaar/H15-Hub.git
cd H15-Hub
pip install -e .

# Config anpassen
nano config.yaml

# Als Service starten (systemd)
sudo nano /etc/systemd/system/h15hub.service
```

```ini
[Unit]
Description=H15-Hub Makerspace Integration Hub
After=network.target

[Service]
User=pi
WorkingDirectory=/home/pi/H15-Hub
ExecStart=uvicorn h15hub.main:app --host 0.0.0.0 --port 8000
Restart=always
Environment=H15HUB_CONFIG=/home/pi/H15-Hub/config.yaml

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable h15hub
sudo systemctl start h15hub
```

---

## Labeldrucker (Brother QL) – USB-Zugriff

Damit Docker auf den USB-Drucker zugreifen kann:

```yaml
# docker-compose.yml
devices:
  - /dev/usb/lp0:/dev/usb/lp0
```

Auf Unraid: Im Docker-Template unter **Devices** eintragen: `/dev/usb/lp0`

Der Pfad kann abweichen – prüfen mit:
```bash
ls /dev/usb/
# oder
lsusb | grep Brother
```
