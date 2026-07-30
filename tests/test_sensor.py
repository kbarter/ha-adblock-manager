"""Tests for the sensor platform."""
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.adblock_manager.const import DOMAIN


async def test_sensor_reports_status(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get(
        "http://dns.example.com/api/settings/get",
        json={"status": "ok", "response": {"enableBlocking": False}},
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "server_type": "technitium",
            "host": "http://dns.example.com",
            "token": "tok",
            "verify_ssl": True,
        },
        unique_id="technitium:http://dns.example.com",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    sensor_states = hass.states.async_all("sensor")
    assert len(sensor_states) == 1
    assert sensor_states[0].state == "disabled"
