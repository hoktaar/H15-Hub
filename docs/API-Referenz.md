# API Referenz

Alle Endpunkte sind unter `http://HOST:8000` erreichbar.  
Interaktive Dokumentation (Swagger UI): `http://HOST:8000/docs`

---

## Geräte

### `GET /api/devices`

Alle Geräte mit aktuellem Status.

**Response:**
```json
[
  {
    "id": "bambu-p1s-1",
    "name": "Bambu P1S #1",
    "type": "3d_printer",
    "status": "in_use",
    "current_user": "Alice",
    "progress": 42,
    "eta_minutes": 30,
    "capabilities": ["pause", "resume", "cancel"],
    "raw": {}
  }
]
```

---

### `GET /api/devices/{device_id}`

Ein einzelnes Gerät.

```bash
curl http://localhost:8000/api/devices/bambu-p1s-1
```

**404** wenn Gerät nicht bekannt.

---

### `POST /api/devices/{device_id}/action`

Aktion auf einem Gerät ausführen.

**Request:**
```json
{
  "action": "pause",
  "params": {}
}
```

**Response:**
```json
{
  "success": true,
  "message": "pause erfolgreich",
  "data": {}
}
```

**Beispiele:**
```bash
# Drucker pausieren
curl -X POST http://localhost:8000/api/devices/bambu-p1s-1/action \
  -H "Content-Type: application/json" \
  -d '{"action": "pause"}'

# Label drucken
curl -X POST http://localhost:8000/api/devices/labelprinter/action \
  -H "Content-Type: application/json" \
  -d '{"action": "print", "params": {"text": "Hebewerk e.V."}}'

# Lasercutter stoppen (via HA)
curl -X POST http://localhost:8000/api/devices/switch.lasercutter_power/action \
  -H "Content-Type: application/json" \
  -d '{"action": "turn_off"}'
```

---

## Buchungen

### `GET /api/bookings`

Alle aktiven Buchungen.

**Query-Parameter:**
- `device_id` – Filtern nach Gerät
- `date` – Filtern nach Tag (ISO-Format: `2026-03-10`)

```bash
curl "http://localhost:8000/api/bookings?device_id=lasercutter&date=2026-03-10"
```

---

### `POST /api/bookings`

Neue Buchung anlegen.

**Request:**
```json
{
  "device_id": "lasercutter",
  "member_name": "Max Mustermann",
  "start_time": "2026-03-10T14:00:00",
  "end_time": "2026-03-10T16:00:00",
  "note": "PLA-Druck für Vereinsprojekt"
}
```

**201** bei Erfolg, **409** bei Zeitkonflikt, **400** bei ungültigen Zeiten.

---

### `DELETE /api/bookings/{booking_id}`

Buchung stornieren.

```bash
curl -X DELETE http://localhost:8000/api/bookings/42
```

**204** bei Erfolg, **404** wenn nicht gefunden.

---

## WebSocket

### `WS /ws/status`

Echtzeit-Updates aller Geräte.

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/status');

ws.onmessage = (e) => {
  const msg = JSON.parse(e.data);

  if (msg.type === 'full_update') {
    // msg.devices = Array aller Geräte
  }

  if (msg.type === 'status_change') {
    // msg.device_id   = ID des geänderten Geräts
    // msg.old_status  = vorheriger Status
    // msg.new_status  = neuer Status
    // msg.device      = vollständiges Device-Objekt
  }
};
```

**Nachrichten-Typen:**

| type | Wann | Inhalt |
|---|---|---|
| `full_update` | Bei Verbindung + alle 5s | `devices: Device[]` |
| `status_change` | Bei Status-Änderung | `device_id`, `old_status`, `new_status`, `device` |

---

## Health Check

### `GET /health`

```bash
curl http://localhost:8000/health
# {"status": "ok", "service": "h15hub"}
```
