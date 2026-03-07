# Adapter

Jeder Adapter übersetzt die gerätespezifische API in das einheitliche `Device`-Modell.

---

## BambuddyAdapter

**Für:** Bambu P1S 3D-Drucker  
**Protokoll:** HTTP REST  
**Voraussetzung:** [Bambuddy](https://github.com/bambuddy) läuft als Docker-Container im Netzwerk

### Konfiguration

```yaml
devices:
  bambu:
    adapter: bambuddy
    url: http://192.168.1.20:8080
    printers:
      - id: bambu-p1s-1
        name: "Bambu P1S #1"
```

### Status-Mapping

| Bambuddy State | H15-Hub Status |
|---|---|
| `idle` | FREE |
| `printing` | IN_USE |
| `paused` | IN_USE |
| `error` | ERROR |
| `offline` | OFFLINE |

### Verfügbare Aktionen

- `pause` – Aktuellen Druck pausieren
- `resume` – Pausierten Druck fortsetzen
- `cancel` – Druck abbrechen

---

## HomeAssistantAdapter

**Für:** Beliebige Home Assistant Entitäten (Schalter, Sensoren, etc.)  
**Protokoll:** HA REST API  
**Voraussetzung:** Home Assistant läuft im Netzwerk, Long-Lived Token vorhanden

### Konfiguration

```yaml
devices:
  homeassistant:
    adapter: homeassistant
    url: http://192.168.1.10:8123
    token: "eyJ0eXAiOiJKV1QiLCJhbGci..."
    entities:
      - entity_id: switch.lasercutter_power
        name: Lasercutter
        type: lasercutter
      - entity_id: binary_sensor.werkstatt_besetzt
        name: Offene Werkstatt
        type: sensor
```

### Entity-Typen (`type`)

| type | Beschreibung | Capabilities |
|---|---|---|
| `lasercutter` | Lasercutter-Switch | start, stop |
| `sensor` | Nur lesend | – |
| `switch` | Beliebiger Schalter | turn_on, turn_off |

### Status-Mapping

| HA State | H15-Hub Status |
|---|---|
| `on`, `open`, `active` | IN_USE |
| `off`, `closed`, `idle` | FREE |
| `unavailable`, `unknown` | OFFLINE |

---

## LasercutterAdapter

**Für:** CNC-Lasercutter  
**Protokoll:** Optionaler lokaler HTTP-Controller; ansonsten via Home Assistant

### Konfiguration

```yaml
devices:
  lasercutter:
    adapter: lasercutter
    name: "Lasercutter"
    controller_url: http://192.168.1.30:8080   # optional
```

Ohne `controller_url` liefert der Adapter immer `FREE` als Fallback – der echte Status kommt dann über den HomeAssistantAdapter (z.B. via `switch.lasercutter_power`).

### Verfügbare Aktionen (bei vorhandenem Controller)

- `start`
- `stop`
- `emergency_stop`

---

## LabelprinterAdapter

**Für:** Brother QL Labeldrucker (USB)  
**Protokoll:** `brother_ql` Python-Library  
**Voraussetzung:** Drucker per USB angeschlossen, Gerätepfad `/dev/usb/lp0` im Container verfügbar

### Konfiguration

```yaml
devices:
  labelprinter:
    adapter: labelprinter
    model: QL-800
    device: /dev/usb/lp0
    name: "Labeldrucker"
```

### Unterstützte Modelle

Alle Brother QL Modelle die von `brother_ql` unterstützt werden, z.B.:
`QL-500`, `QL-550`, `QL-570`, `QL-580NX`, `QL-700`, `QL-800`, `QL-810W`, `QL-820NWB`

### Aktion: `print`

```bash
curl -X POST http://localhost:8000/api/devices/labelprinter/action \
  -H "Content-Type: application/json" \
  -d '{"action": "print", "params": {"text": "Hebewerk e.V. – Max Mustermann"}}'
```

> **Optional:** `brother-ql` und `pyipp` sind optionale Abhängigkeiten. Installation: `pip install -e ".[printers]"`

---

## LaserprinterAdapter

**Für:** Netzwerk-Laserdrucker  
**Protokoll:** IPP (Internet Printing Protocol) via `pyipp`  
**Voraussetzung:** Drucker im Netzwerk erreichbar

### Konfiguration

```yaml
devices:
  laserprinter:
    adapter: laserprinter
    url: ipp://192.168.1.50/ipp/print
    name: "Büro Laserdrucker"
```

### Status-Mapping

| IPP State | H15-Hub Status |
|---|---|
| `idle` | FREE |
| `processing` | IN_USE |
| `stopped` / `error` | ERROR |
| Nicht erreichbar | OFFLINE |

> Druckjobs werden direkt über das Betriebssystem / CUPS gesendet, nicht über H15-Hub.
