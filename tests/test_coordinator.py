"""Tests for AdBlockCoordinator."""
from homeassistant.core import HomeAssistant

from custom_components.adblock_manager.client import (
    AdBlockAuthError,
    AdBlockConnectionError,
)
from custom_components.adblock_manager.coordinator import AdBlockCoordinator


class FakeClient:
    """Stand-in DNSClient that returns/raises a fixed result."""

    def __init__(self, result=None, error=None):
        self._result = result
        self._error = error

    async def async_get_status(self):
        if self._error:
            raise self._error
        return self._result


async def test_coordinator_success(hass: HomeAssistant, mock_config_entry) -> None:
    mock_config_entry.add_to_hass(hass)
    client = FakeClient(result={"status": "enabled", "disabled_until": None})
    coordinator = AdBlockCoordinator(hass, mock_config_entry, client, 30)
    await coordinator.async_refresh()
    assert coordinator.data == {"status": "enabled", "disabled_until": None}
    assert coordinator.last_update_success is True


async def test_coordinator_connection_error_returns_error_status(
    hass: HomeAssistant, mock_config_entry
) -> None:
    mock_config_entry.add_to_hass(hass)
    client = FakeClient(error=AdBlockConnectionError("down"))
    coordinator = AdBlockCoordinator(hass, mock_config_entry, client, 30)
    await coordinator.async_refresh()
    assert coordinator.data["status"] == "error"
    assert coordinator.last_update_success is True


async def test_coordinator_auth_error_marks_update_failed(
    hass: HomeAssistant, mock_config_entry
) -> None:
    mock_config_entry.add_to_hass(hass)
    client = FakeClient(error=AdBlockAuthError("bad creds"))
    coordinator = AdBlockCoordinator(hass, mock_config_entry, client, 30)
    await coordinator.async_refresh()
    assert coordinator.last_update_success is False

    # last_update_success is False for UpdateFailed too - it can't by
    # itself distinguish "raised ConfigEntryAuthFailed" (what's required)
    # from "raised the more generic UpdateFailed" (what's forbidden). The
    # thing that's actually load-bearing is that a reauth flow started.
    await hass.async_block_till_done()
    flows = hass.config_entries.flow.async_progress()
    assert any(f["context"]["source"] == "reauth" for f in flows)
