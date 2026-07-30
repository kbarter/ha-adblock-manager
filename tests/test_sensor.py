"""Tests for the sensor platform."""
import aiohttp
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
    assert len(sensor_states) == 2
    assert any(s.state == "disabled" for s in sensor_states)


async def test_aggregate_sensor_enabled_when_all_enabled(
    hass: HomeAssistant, aioclient_mock, setup_two_entries
) -> None:
    aioclient_mock.get(
        "http://a.example.com/api/settings/get",
        json={"status": "ok", "response": {"enableBlocking": True}},
    )
    aioclient_mock.get(
        "http://b.example.com/api/settings/get",
        json={"status": "ok", "response": {"enableBlocking": True}},
    )
    await setup_two_entries(hass)

    state = hass.states.get("sensor.adblock_overall_status")
    assert state.state == "enabled"
    assert state.attributes["Server A"] == "enabled"
    assert state.attributes["Server B"] == "enabled"


async def test_aggregate_sensor_partial_when_mixed(
    hass: HomeAssistant, aioclient_mock, setup_two_entries
) -> None:
    aioclient_mock.get(
        "http://a.example.com/api/settings/get",
        json={"status": "ok", "response": {"enableBlocking": True}},
    )
    aioclient_mock.get(
        "http://b.example.com/api/settings/get",
        json={"status": "ok", "response": {"enableBlocking": False}},
    )
    await setup_two_entries(hass)

    state = hass.states.get("sensor.adblock_overall_status")
    assert state.state == "partial"


async def test_aggregate_sensor_error_when_one_server_unreachable(
    hass: HomeAssistant, aioclient_mock, setup_two_entries
) -> None:
    aioclient_mock.get(
        "http://a.example.com/api/settings/get",
        json={"status": "ok", "response": {"enableBlocking": True}},
    )
    aioclient_mock.get(
        "http://b.example.com/api/settings/get",
        exc=aiohttp.ClientConnectionError(),
    )
    await setup_two_entries(hass)

    state = hass.states.get("sensor.adblock_overall_status")
    assert state.state == "error"
    assert state.attributes["Server B"] == "error"
