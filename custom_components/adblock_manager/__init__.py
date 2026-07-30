"""The AdBlock Manager integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_TOKEN, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import PiHoleClient, TechnitiumClient
from .config_flow import CONF_SCAN_INTERVAL
from .const import (
    CONF_API_VERSION,
    CONF_SERVER_TYPE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    PLATFORMS,
    ServerType,
)
from .coordinator import AdBlockCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up AdBlock Manager from a config entry."""
    data = entry.data
    # Options override data so the options flow's SSL toggle actually takes
    # effect on the reload it triggers.
    verify_ssl = entry.options.get(
        CONF_VERIFY_SSL, data.get(CONF_VERIFY_SSL, True)
    )
    session = async_get_clientsession(hass, verify_ssl=verify_ssl)

    if data[CONF_SERVER_TYPE] == ServerType.TECHNITIUM:
        client = TechnitiumClient(session, data[CONF_HOST], data[CONF_TOKEN])
    else:
        client = PiHoleClient(
            session,
            data[CONF_HOST],
            data[CONF_API_VERSION],
            token=data.get(CONF_TOKEN),
            password=data.get(CONF_PASSWORD),
        )

    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    coordinator = AdBlockCoordinator(hass, entry, client, scan_interval)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: AdBlockCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.client.async_close()
    return unload_ok
