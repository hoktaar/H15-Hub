# Automations

Automations erlauben es, auf Geräte-Status-Änderungen automatisch zu reagieren – z.B. eine Benachrichtigung senden wenn der 3D-Drucker fertig ist.

## Konfiguration

Automations werden in `config.yaml` unter dem Schlüssel `automations` definiert:

```yaml
automations:
  - name: "Drucker fertig → Benachrichtigung"
    trigger: "device:bambu-p1s-1:progress = 100"
    action: "notify:member:all"

  - name: "Lasercutter frei → Label drucken"
    trigger: "device:lasercutter:status = free"
    action: "device:labelprinter:print"
```

---

## Trigger-Format

```
device:{device_id}:{feld} = {wert}
```

| Feld | Mögliche Werte | Beispiel |
|---|---|---|
| `status` | `free`, `in_use`, `offline`, `error` | `device:bambu-p1s-1:status = free` |
| `progress` | `0`–`100` | `device:bambu-p1s-1:progress = 100` |

---

## Action-Format

### Benachrichtigung

```
notify:member:{name}
notify:member:all
```

Sendet eine WebSocket-Nachricht an alle verbundenen Browser. Browser-Notifications werden angezeigt wenn die Berechtigung erteilt wurde.

### Geräte-Aktion

```
device:{device_id}:{action}
```

Führt eine Aktion auf einem Gerät aus:

```yaml
action: "device:labelprinter:print"
action: "device:bambu-p1s-2:pause"
```

---

## Zyklus-Erkennung (Tarjan's SCC)

H15-Hub erkennt zirkuläre Automations beim Start automatisch.

**Beispiel eines Zyklus:**
```yaml
automations:
  - trigger: "device:lasercutter:status = free"
    action: "device:bambu-p1s-1:start"       # Lasercutter → Bambu

  - trigger: "device:bambu-p1s-1:status = free"
    action: "device:lasercutter:start"        # Bambu → Lasercutter ← ZYKLUS!
```

**Fehlermeldung beim Start:**
```
ERROR: Zirkuläre Automations-Abhängigkeiten gefunden: [['lasercutter', 'bambu-p1s-1']]
       Bitte die config.yaml korrigieren.
```

H15-Hub startet in diesem Fall **nicht** – der Fehler muss zuerst behoben werden.

### Wie Tarjan's SCC funktioniert

1. Alle Automations werden als gerichteter Graph modelliert:
   - **Knoten**: Geräte-IDs
   - **Kanten**: `trigger-device → action-device`
2. Tarjan's Algorithmus findet alle **Strongly Connected Components**
3. Jede SCC mit mehr als einem Knoten (oder einem Self-Loop) ist ein Zyklus

---

## Beispiele

### Fertigmeldung für 3D-Drucker

```yaml
automations:
  - name: "P1S #1 fertig"
    trigger: "device:bambu-p1s-1:progress = 100"
    action: "notify:member:all"

  - name: "P1S #2 fertig"
    trigger: "device:bambu-p1s-2:progress = 100"
    action: "notify:member:all"
```

### Lasercutter-Freimeldung

```yaml
automations:
  - name: "Lasercutter frei"
    trigger: "device:switch.lasercutter_power:status = free"
    action: "notify:member:all"
```

### Keine Automations (Standard)

```yaml
automations: []
```
