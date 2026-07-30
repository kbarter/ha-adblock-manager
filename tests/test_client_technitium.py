"""Tests for the async Technitium client."""
import aiohttp
import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.adblock_manager.client import (
    AdBlockAuthError,
    AdBlockConnectionError,
    TechnitiumClient,
)


async def test_get_status_enabled(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get(
        "http://dns.example.com/api/settings/get",
        json={"status": "ok", "response": {"enableBlocking": True}},
    )
    client = TechnitiumClient(
        async_get_clientsession(hass), "http://dns.example.com", "tok"
    )
    result = await client.async_get_status()
    assert result == {"status": "enabled", "disabled_until": None}


async def test_get_status_disabled(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get(
        "http://dns.example.com/api/settings/get",
        json={"status": "ok", "response": {"enableBlocking": False}},
    )
    client = TechnitiumClient(
        async_get_clientsession(hass), "http://dns.example.com", "tok"
    )
    result = await client.async_get_status()
    assert result["status"] == "disabled"


async def test_set_status_disable_with_timer(
    hass: HomeAssistant, aioclient_mock
) -> None:
    aioclient_mock.post(
        "http://dns.example.com/api/settings/temporaryDisableBlocking",
        json={"status": "ok"},
    )
    aioclient_mock.get(
        "http://dns.example.com/api/settings/get",
        json={"status": "ok", "response": {"enableBlocking": False}},
    )
    client = TechnitiumClient(
        async_get_clientsession(hass), "http://dns.example.com", "tok"
    )
    result = await client.async_set_status("disable", minutes=5)
    assert result["status"] == "disabled"


async def test_auth_error(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get("http://dns.example.com/api/settings/get", status=401)
    client = TechnitiumClient(
        async_get_clientsession(hass), "http://dns.example.com", "bad-tok"
    )
    with pytest.raises(AdBlockAuthError):
        await client.async_get_status()


async def test_connection_error(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get(
        "http://dns.example.com/api/settings/get",
        exc=aiohttp.ClientConnectionError(),
    )
    client = TechnitiumClient(
        async_get_clientsession(hass), "http://dns.example.com", "tok"
    )
    with pytest.raises(AdBlockConnectionError):
        await client.async_get_status()
