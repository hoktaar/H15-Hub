import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from h15hub.models.device import DeviceStatus
from h15hub.adapters.bambuddy import BambuddyAdapter, _map_bambu_state
from h15hub.adapters.homeassistant import HomeAssistantAdapter, _map_ha_state


# --- Bambuddy Adapter ---

def test_map_bambu_state():
    assert _map_bambu_state("idle") == DeviceStatus.FREE
    assert _map_bambu_state("printing") == DeviceStatus.IN_USE
    assert _map_bambu_state("paused") == DeviceStatus.IN_USE
    assert _map_bambu_state("error") == DeviceStatus.ERROR
    assert _map_bambu_state("offline") == DeviceStatus.OFFLINE
    assert _map_bambu_state("unknown_state") == DeviceStatus.OFFLINE


@pytest.mark.asyncio
async def test_bambuddy_get_status_success():
    config = {
        "url": "http://bambuddy:8080",
        "printers": [{"id": "bambu-p1s-1", "name": "Bambu P1S #1"}],
    }
    adapter = BambuddyAdapter(config)

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "state": "printing",
        "print_progress": 42,
        "eta_minutes": 30,
        "started_by": "Alice",
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
        devices = await adapter.get_status()

    assert len(devices) == 1
    d = devices[0]
    assert d.id == "bambu-p1s-1"
    assert d.status == DeviceStatus.IN_USE
    assert d.progress == 42
    assert d.eta_minutes == 30
    assert d.current_user == "Alice"


@pytest.mark.asyncio
async def test_bambuddy_get_status_offline():
    import httpx
    config = {
        "url": "http://bambuddy:8080",
        "printers": [{"id": "bambu-p1s-1", "name": "Bambu P1S #1"}],
    }
    adapter = BambuddyAdapter(config)

    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        devices = await adapter.get_status()

    assert devices[0].status == DeviceStatus.OFFLINE


@pytest.mark.asyncio
async def test_bambuddy_action_invalid():
    config = {"url": "http://bambuddy:8080", "printers": []}
    adapter = BambuddyAdapter(config)
    result = await adapter.execute_action("bambu-p1s-1", "fly", {})
    assert not result.success
    assert "Unbekannte Aktion" in result.message


# --- Home Assistant Adapter ---

def test_map_ha_state():
    assert _map_ha_state("on") == DeviceStatus.IN_USE
    assert _map_ha_state("off") == DeviceStatus.FREE
    assert _map_ha_state("unavailable") == DeviceStatus.OFFLINE
    assert _map_ha_state("idle") == DeviceStatus.FREE


@pytest.mark.asyncio
async def test_ha_get_status_success():
    config = {
        "url": "http://homeassistant:8123",
        "token": "test-token",
        "entities": [{"entity_id": "switch.lasercutter_power", "name": "Lasercutter", "type": "lasercutter"}],
    }
    adapter = HomeAssistantAdapter(config)

    mock_response = MagicMock()
    mock_response.json.return_value = {"state": "off", "attributes": {}}
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
        devices = await adapter.get_status()

    assert len(devices) == 1
    assert devices[0].name == "Lasercutter"
    assert devices[0].status == DeviceStatus.FREE
