#!/bin/sh
set -e

CONFIG_FILE="${H15HUB_CONFIG:-/app/config/config.yaml}"
CONFIG_DIR="$(dirname "$CONFIG_FILE")"

# Config-Verzeichnis anlegen falls nicht vorhanden
mkdir -p "$CONFIG_DIR"

# Minimal-Config erstellen wenn keine vorhanden
if [ ! -f "$CONFIG_FILE" ]; then
    echo "INFO: Keine config.yaml gefunden – erstelle Beispiel-Konfiguration in $CONFIG_FILE"
    cat > "$CONFIG_FILE" << 'YAML'
# H15-Hub Konfiguration
# Passe die IPs und Token an deine Umgebung an.
# Dokumentation: https://github.com/hoktaar/H15-Hub/wiki

app:
  title: "H15-Hub"
  description: "Hebewerk e.V. Makerspace Integration Hub"
  poll_interval_seconds: 10

devices: {}

automations: []
YAML
fi

exec "$@"
