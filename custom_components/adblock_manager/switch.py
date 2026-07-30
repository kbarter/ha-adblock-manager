"""Switch platform for AdBlock Manager."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .client import AdBlockError
from .const import DOMAIN, STATUS_DISABLED, STATUS_ENABLED
from .coordinator import AdBlockCoordinator
from .device import build_device_info

SERVICE_DISABLE_FOR = "disable_for"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: AdBlockCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([AdBlockSwitch(coordinator, entry)])

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_DISABLE_FOR,
        {vol.Required("minutes"): vol.All(int, vol.Range(min=1))},
        "async_disable_for",
    )


class AdBlockSwitch(CoordinatorEntity[AdBlockCoordinator], SwitchEntity):
    """Represents blocking on/off for one server."""

    _attr_has_entity_name = True
    _attr_name = "Blocking"

    def __init__(self, coordinator: AdBlockCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_blocking"
        self._attr_device_info = build_device_info(entry)

    @property
    def is_on(self) -> bool | None:
        status = self.coordinator.data.get("status")
        if status == STATUS_ENABLED:
            return True
        if status == STATUS_DISABLED:
            return False
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"disabled_until": self.coordinator.data.get("disabled_until")}

    async def async_turn_on(self, **kwargs: Any) -> None:
        try:
            await self.coordinator.client.async_set_status("enable")
        except AdBlockError as err:
            raise HomeAssistantError(f"Failed to enable blocking: {err}") from err
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        try:
            await self.coordinator.client.async_set_status("disable")
        except AdBlockError as err:
            raise HomeAssistantError(f"Failed to disable blocking: {err}") from err
        await self.coordinator.async_request_refresh()

    async def async_disable_for(self, minutes: int) -> None:
        try:
            await self.coordinator.client.async_set_status("disable", minutes=minutes)
        except AdBlockError as err:
            raise HomeAssistantError(
                f"Failed to disable blocking for {minutes} minutes: {err}"
            ) from err
        await self.coordinator.async_request_refresh()
