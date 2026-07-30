"""Tests for the config flow."""
from homeassistant import config_entries
from homeassistant.core import HomeAssistant

from custom_components.adblock_manager.const import DOMAIN


async def test_technitium_flow_success(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get(
        "http://dns.example.com/api/settings/get",
        json={"status": "ok", "response": {"enableBlocking": True}},
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"server_type": "technitium"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"host": "http://dns.example.com", "token": "tok", "verify_ssl": True},
    )
    assert result["type"] == "create_entry"
    assert result["data"]["host"] == "http://dns.example.com"


async def test_technitium_flow_invalid_auth(
    hass: HomeAssistant, aioclient_mock
) -> None:
    aioclient_mock.get("http://dns.example.com/api/settings/get", status=401)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"server_type": "technitium"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"host": "http://dns.example.com", "token": "bad", "verify_ssl": True},
    )
    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_duplicate_server_is_aborted(
    hass: HomeAssistant, aioclient_mock, mock_config_entry
) -> None:
    object.__setattr__(
        mock_config_entry, "unique_id", "technitium:http://dns.example.com"
    )
    mock_config_entry.add_to_hass(hass)
    aioclient_mock.get(
        "http://dns.example.com/api/settings/get",
        json={"status": "ok", "response": {"enableBlocking": True}},
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"server_type": "technitium"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"host": "http://dns.example.com", "token": "tok", "verify_ssl": True},
    )
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
