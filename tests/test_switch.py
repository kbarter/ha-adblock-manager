"""Tests for the switch platform."""
import aiohttp
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.adblock_manager.const import DOMAIN


async def _setup_entry(hass: HomeAssistant) -> MockConfigEntry:
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
    return entry


async def test_switch_reflects_enabled_state(
    hass: HomeAssistant, aioclient_mock
) -> None:
    aioclient_mock.get(
        "http://dns.example.com/api/settings/get",
        json={"status": "ok", "response": {"enableBlocking": True}},
    )
    await _setup_entry(hass)
    assert any(s.state == "on" for s in hass.states.async_all("switch"))


async def test_switch_turn_off_calls_client(
    hass: HomeAssistant, aioclient_mock
) -> None:
    aioclient_mock.get(
        "http://dns.example.com/api/settings/get",
        json={"status": "ok", "response": {"enableBlocking": True}},
    )
    await _setup_entry(hass)
    aioclient_mock.clear_requests()
    aioclient_mock.post(
        "http://dns.example.com/api/settings/set",
        json={"status": "ok"},
    )
    aioclient_mock.get(
        "http://dns.example.com/api/settings/get",
        json={"status": "ok", "response": {"enableBlocking": False}},
    )
    entity_id = hass.states.async_entity_ids("switch")[0]
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": entity_id}, blocking=True
    )
    state = hass.states.get(entity_id)
    assert state.state == "off"


async def test_switch_is_unknown_when_status_is_error(
    hass: HomeAssistant, aioclient_mock
) -> None:
    aioclient_mock.get(
        "http://dns.example.com/api/settings/get",
        exc=aiohttp.ClientConnectionError(),
    )
    await _setup_entry(hass)
    entity_id = hass.states.async_entity_ids("switch")[0]
    state = hass.states.get(entity_id)
    assert state.state == "unknown"


async def test_disable_for_service_calls_timed_disable(
    hass: HomeAssistant, aioclient_mock
) -> None:
    aioclient_mock.get(
        "http://dns.example.com/api/settings/get",
        json={"status": "ok", "response": {"enableBlocking": True}},
    )
    await _setup_entry(hass)
    aioclient_mock.clear_requests()
    aioclient_mock.post(
        "http://dns.example.com/api/settings/temporaryDisableBlocking",
        json={"status": "ok"},
    )
    aioclient_mock.get(
        "http://dns.example.com/api/settings/get",
        json={"status": "ok", "response": {"enableBlocking": False}},
    )
    entity_id = hass.states.async_entity_ids("switch")[0]
    await hass.services.async_call(
        DOMAIN,
        "disable_for",
        {"entity_id": entity_id, "minutes": 5},
        blocking=True,
    )
    state = hass.states.get(entity_id)
    assert state.state == "off"

    # The state landing on "off" would pass identically whether the service
    # sent minutes=5, minutes=1, or dropped the timer entirely - assert on
    # the actual outbound request so the parameter is really verified.
    timed_disable_calls = [
        call
        for call in aioclient_mock.mock_calls
        if "temporaryDisableBlocking" in str(call[1])
    ]
    assert len(timed_disable_calls) == 1
    assert "minutes=5" in str(timed_disable_calls[0][1])
