"""Tests for diagnostics."""
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.adblock_manager.const import DOMAIN
from custom_components.adblock_manager.diagnostics import (
    async_get_config_entry_diagnostics,
)


async def test_diagnostics_redacts_secrets(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "server_type": "technitium",
            "host": "http://dns.example.com",
            "token": "super-secret",
            "verify_ssl": True,
        },
        unique_id="technitium:http://dns.example.com",
    )
    entry.add_to_hass(hass)

    result = await async_get_config_entry_diagnostics(hass, entry)
    assert result["entry_data"]["token"] == "**REDACTED**"
    assert result["entry_data"]["host"] == "http://dns.example.com"
