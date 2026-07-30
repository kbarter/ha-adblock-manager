"""Tests for integration setup/unload."""
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.adblock_manager.const import DOMAIN, SIGNAL_AGGREGATE_UPDATE


async def test_setup_and_unload_entry(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get(
        "http://dns.example.com/api/settings/get",
        json={"status": "ok", "response": {"enableBlocking": True}},
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
    assert entry.entry_id in hass.data[DOMAIN]

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.entry_id not in hass.data[DOMAIN]


async def test_coordinator_update_sends_aggregate_signal(
    hass: HomeAssistant, aioclient_mock
) -> None:
    aioclient_mock.get(
        "http://dns.example.com/api/settings/get",
        json={"status": "ok", "response": {"enableBlocking": True}},
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

    received = []
    async_dispatcher_connect(
        hass, SIGNAL_AGGREGATE_UPDATE, lambda: received.append(True)
    )

    coordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_request_refresh()

    assert received == [True]


async def test_removing_owner_entry_hands_off_aggregate_to_remaining_entry(
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
    entry_a, entry_b = await setup_two_entries(hass)

    assert hass.states.get("switch.adblock_overall") is not None

    assert (await hass.config_entries.async_remove(entry_a.entry_id))[
        "require_restart"
    ] is False
    await hass.async_block_till_done()

    assert hass.states.get("switch.adblock_overall") is not None
    assert hass.states.get("sensor.adblock_overall_status") is not None


async def test_removing_owner_entry_preserves_renamed_aggregate_entity(
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
    entry_a, entry_b = await setup_two_entries(hass)

    registry = er.async_get(hass)
    registry.async_update_entity(
        "switch.adblock_overall", new_entity_id="switch.my_custom_adblock"
    )

    result = await hass.config_entries.async_remove(entry_a.entry_id)
    assert result["require_restart"] is False
    await hass.async_block_till_done()

    entry = registry.async_get("switch.my_custom_adblock")
    assert entry is not None
    assert entry.config_entry_id == entry_b.entry_id


async def test_adding_second_entry_immediately_updates_aggregate(
    hass: HomeAssistant, aioclient_mock
) -> None:
    aioclient_mock.get(
        "http://a.example.com/api/settings/get",
        json={"status": "ok", "response": {"enableBlocking": True}},
    )
    entry_a = MockConfigEntry(
        domain=DOMAIN,
        title="Server A",
        data={
            "server_type": "technitium",
            "host": "http://a.example.com",
            "token": "tok",
            "verify_ssl": True,
        },
        unique_id="technitium:http://a.example.com",
    )
    entry_a.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry_a.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("switch.adblock_overall").state == "on"

    aioclient_mock.get(
        "http://b.example.com/api/settings/get",
        json={"status": "ok", "response": {"enableBlocking": False}},
    )
    entry_b = MockConfigEntry(
        domain=DOMAIN,
        title="Server B",
        data={
            "server_type": "technitium",
            "host": "http://b.example.com",
            "token": "tok",
            "verify_ssl": True,
        },
        unique_id="technitium:http://b.example.com",
    )
    entry_b.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry_b.entry_id)
    await hass.async_block_till_done()

    # No manual coordinator refresh triggered anywhere above - if this is
    # "on" or the sensor is "enabled", the fix isn't wired up correctly.
    assert hass.states.get("switch.adblock_overall").state == "off"
    assert hass.states.get("sensor.adblock_overall_status").state == "partial"
