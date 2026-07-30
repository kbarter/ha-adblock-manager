"""Switch platform for AdBlock Manager."""
from __future__ import annotations

import asyncio
from typing import Any

import voluptuous as vol
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_platform
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .aggregate import (
    all_coordinators,
    claim_aggregate_ownership_if_unclaimed,
    compute_overall_status,
)
from .client import AdBlockError
from .const import DOMAIN, SIGNAL_AGGREGATE_UPDATE, STATUS_DISABLED, STATUS_ENABLED
from .coordinator import AdBlockCoordinator
from .device import build_aggregate_device_info, build_device_info

SERVICE_DISABLE_FOR = "disable_for"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: AdBlockCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SwitchEntity] = [AdBlockSwitch(coordinator, entry)]
    if claim_aggregate_ownership_if_unclaimed(hass, entry):
        entities.append(AdBlockOverallSwitch())
    async_add_entities(entities)

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
        await self.coordinator.async_refresh()
        self.coordinator.async_schedule_burst_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        try:
            await self.coordinator.client.async_set_status("disable")
        except AdBlockError as err:
            raise HomeAssistantError(f"Failed to disable blocking: {err}") from err
        await self.coordinator.async_refresh()
        self.coordinator.async_schedule_burst_refresh()

    async def async_disable_for(self, minutes: int) -> None:
        try:
            await self.coordinator.client.async_set_status("disable", minutes=minutes)
        except AdBlockError as err:
            raise HomeAssistantError(
                f"Failed to disable blocking for {minutes} minutes: {err}"
            ) from err
        await self.coordinator.async_refresh()
        self.coordinator.async_schedule_burst_refresh()


class AdBlockOverallSwitch(SwitchEntity):
    """Turns blocking on/off across every configured server at once."""

    _attr_has_entity_name = True
    _attr_name = "Overall"
    _attr_should_poll = False
    _attr_unique_id = f"{DOMAIN}_aggregate_switch"
    _attr_device_info = build_aggregate_device_info()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_AGGREGATE_UPDATE, self._handle_update
            )
        )

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        statuses = [c.data["status"] for c in all_coordinators(self.hass)]
        return compute_overall_status(statuses) == STATUS_ENABLED

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._async_set_all("enable")

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_set_all("disable")

    async def _async_set_all(self, action: str) -> None:
        coordinators = all_coordinators(self.hass)
        results = await asyncio.gather(
            *(c.client.async_set_status(action) for c in coordinators),
            return_exceptions=True,
        )
        failed = [
            c.config_entry.title
            for c, result in zip(coordinators, results, strict=True)
            if isinstance(result, Exception)
        ]
        await asyncio.gather(*(c.async_refresh() for c in coordinators))
        for c in coordinators:
            c.async_schedule_burst_refresh()
        if failed:
            raise HomeAssistantError(
                f"Failed to {action} blocking on: {', '.join(failed)}"
            )
