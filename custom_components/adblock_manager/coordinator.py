"""DataUpdateCoordinator for AdBlock Manager."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .client import AdBlockAuthError, AdBlockConnectionError, DNSClient
from .const import DOMAIN, STATUS_ERROR

_LOGGER = logging.getLogger(__name__)


class AdBlockCoordinator(DataUpdateCoordinator[dict]):
    """Polls a single Pi-hole/Technitium server."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: DNSClient,
        scan_interval: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            # Required for ConfigEntryAuthFailed to actually start the reauth
            # flow — without it the base class falls back to a contextvar
            # that is only set during real entry setup.
            config_entry=entry,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(seconds=scan_interval),
        )
        self.client = client

    async def _async_update_data(self) -> dict:
        try:
            return await self.client.async_get_status()
        except AdBlockAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except AdBlockConnectionError as err:
            return {
                "status": STATUS_ERROR,
                "error_message": str(err),
                "disabled_until": None,
            }
