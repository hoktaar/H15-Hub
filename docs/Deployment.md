# Deployment

## Docker Image

Das Docker Image wird automatisch via **GitHub Actions** gebaut und in die **GitHub Container Registry** gepusht.

```bash
# Neuestes Image ziehen
docker pull ghcr.io/hoktaar/h15-hub:latest
```

### Unterstützte Plattformen

| Plattform | Gerät |
|---|---|
| `linux/amd64` | x86 Server, Unraid, normaler PC |
| `linux/arm64` | Raspberry Pi 4/5, Apple M-Chip |

---

## GitHub Actions Workflow

| Event | Tests | Docker Build | Push nach GHCR |
|---|---|---|---|
| Pull Request nach main | Ja | Ja | Nein |
| Merge in main | Ja | Ja | Ja: latest |
| Tag v1.2.3 | Ja | Ja | Ja: 1.2.3 |

### Release erstellen

```bash
git tag v1.0.0
git push origin v1.0.0
```

---

## Raspberry Pi

```bash
docker pull ghcr.io/hoktaar/h15-hub:latest
nano config.yaml
docker-compose up -d
```

### systemd-Service (ohne Docker)

```ini
[Unit]
Description=H15-Hub
After=network.target

[Service]
User=pi
WorkingDirectory=/home/pi/H15-Hub
ExecStart=uvicorn h15hub.main:app --host 0.0.0.0 --port 8032
Restart=always
Environment=H15HUB_CONFIG=/home/pi/H15-Hub/config.yaml

[Install]
WantedBy=multi-user.target
```

---

## Unraid

Image-Tag: ghcr.io/hoktaar/h15-hub:latest

Siehe Installation-Seite fuer den vollstaendigen Unraid-Guide.
Mit dem Docker Auto-Update Plugin wird das Image automatisch aktualisiert.

Das Unraid-Template kann per Shell direkt aus GitHub aktualisiert werden:

```bash
curl -fsSL https://raw.githubusercontent.com/hoktaar/H15-Hub/main/unraid/h15hub.xml -o /boot/config/plugins/dockerMan/templates-user/h15hub.xml
```

---

## Updates

```bash
docker-compose pull
docker-compose up -d
```

---

## Backup

- config.yaml - Konfiguration (in Git verwalten)
- data/h15hub.db - SQLite-Datenbank mit Buchungen

```bash
# Lokales Backup
cp data/h15hub.db data/h15hub.db.backup

# Auf Unraid
cp /mnt/user/appdata/h15hub/data/h15hub.db /mnt/user/backup/h15hub.db
```
