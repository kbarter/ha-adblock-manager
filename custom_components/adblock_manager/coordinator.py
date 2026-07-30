"""DataUpdateCoordinator for AdBlock Manager."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .client import AdBlockAuthError, AdBlockConnectionError, DNSClient
from .const import DOMAIN, STATUS_ERROR

_LOGGER = logging.getLogger(__name__)

# Enabling blocking can involve the server reloading its blocklist
# before its own status reflects it, while disabling is usually
# immediate - poll again shortly after any action instead of waiting
# for the next full scan_interval tick.
BURST_REFRESH_DELAYS = (5, 15)


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

    def async_schedule_burst_refresh(self) -> asyncio.Task[None]:
        """Poll again a few times shortly after an action, without blocking it."""
        return self.config_entry.async_create_background_task(
            self.hass, self._async_burst_refresh(), f"{self.name}_burst_refresh"
        )

    async def _async_burst_refresh(self) -> None:
        # async_refresh(), not async_request_refresh() - the latter goes
        # through a 10s-cooldown debouncer, which would silently coalesce
        # these deliberately-spaced polls into one delayed call instead of
        # running them at the times below.
        for delay in BURST_REFRESH_DELAYS:
            await asyncio.sleep(delay)
            await self.async_refresh()
