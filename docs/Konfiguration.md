# Konfiguration

Die gesamte Konfiguration erfolgt über eine einzige Datei: `config.yaml`.

Admins können diese Datei im Adminbereich direkt bearbeiten. Änderungen an Geräten und Automationen werden nach einem Neustart des Containers aktiv.

## Vollständiges Beispiel

```yaml
app:
  title: "H15-Hub"
  description: "Hebewerk e.V. Makerspace Integration Hub"
  poll_interval_seconds: 5   # Wie oft Geräte abgefragt werden

devices:
  bambu:
    adapter: bambuddy
    url: http://bambuddy:8080   # oder http://192.168.1.20:8080
    printers:
      - id: bambu-p1s-1
        name: "Bambu P1S #1"
      - id: bambu-p1s-2
        name: "Bambu P1S #2"

  homeassistant:
    adapter: homeassistant
    url: http://homeassistant:8123   # oder http://192.168.1.10:8123
    token: "eyJ0eXAiOiJKV1QiLCJhbGci..."   # Long-Lived Access Token
    entities:
      - entity_id: switch.lasercutter_power
        name: Lasercutter
        type: lasercutter
      - entity_id: binary_sensor.werkstatt_besetzt
        name: Offene Werkstatt
        type: sensor

  labelprinter:
    adapter: labelprinter
    model: QL-800          # Brother QL Modell
    device: /dev/usb/lp0   # USB-Gerätepfad
    name: "Labeldrucker"

  laserprinter:
    adapter: laserprinter
    url: ipp://192.168.1.50/ipp/print   # IPP-URL des Druckers
    name: "Büro Laserdrucker"

automations:
  - name: "Drucker fertig → Benachrichtigung"
    trigger: "device:bambu-p1s-1:progress = 100"
    action: "notify:member:all"

  - name: "Lasercutter frei → Labeldrucker"
    trigger: "device:lasercutter:status = free"
    action: "device:labelprinter:print"
```

---

## Abschnitt: `app`

| Key | Standard | Beschreibung |
|---|---|---|
| `title` | `H15-Hub` | Anzeigename im Dashboard |
| `poll_interval_seconds` | `5` | Polling-Intervall in Sekunden |

---

## Abschnitt: `devices`

Jeder Eintrag unter `devices` hat einen frei wählbaren Namen (z.B. `bambu`, `homeassistant`) und einen `adapter`-Schlüssel der den Adapter-Typ bestimmt.

### Adapter-Typen

| `adapter` | Klasse | Für |
|---|---|---|
| `bambuddy` | BambuddyAdapter | Bambu P1S Drucker via Bambuddy |
| `homeassistant` | HomeAssistantAdapter | Home Assistant Entitäten |
| `lasercutter` | LasercutterAdapter | Lasercutter (optionaler HTTP-Controller) |
| `labelprinter` | LabelprinterAdapter | Brother QL Labeldrucker (USB) |
| `laserprinter` | LaserprinterAdapter | Netzwerkdrucker (IPP) |

---

## Home Assistant Token erstellen

1. Home Assistant öffnen → Profil (unten links)
2. Ganz unten: **Langfristige Zugriffstoken**
3. **Token erstellen** → Name: `h15hub`
4. Token kopieren und in `config.yaml` unter `token` eintragen

---

## IPs über `extra_hosts` (Docker)

Statt IP-Adressen direkt in URLs zu verwenden, können Hostnamen via `extra_hosts` in `docker-compose.yml` aufgelöst werden:

```yaml
extra_hosts:
  - "homeassistant:192.168.1.10"
  - "bambuddy:192.168.1.20"
```

Dann in `config.yaml` einfach `http://homeassistant:8123` verwenden.

---

## Umgebungsvariablen

| Variable | Standard | Beschreibung |
|---|---|---|
| `H15HUB_CONFIG` | `config.yaml` | Pfad zur Konfigurationsdatei |
| `H15HUB_DB_URL` | `sqlite+aiosqlite:///./data/h15hub.db` | Datenbank-URL |
| `LOG_LEVEL` | `INFO` | Log-Level (DEBUG, INFO, WARNING, ERROR) |
