"""Sensor platform for AdBlock Manager."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .aggregate import (
    all_coordinators,
    claim_aggregate_ownership_if_unclaimed,
    compute_overall_status,
)
from .const import (
    DOMAIN,
    SIGNAL_AGGREGATE_UPDATE,
    STATUS_DISABLED,
    STATUS_ENABLED,
    STATUS_ERROR,
    STATUS_PARTIAL,
)
from .coordinator import AdBlockCoordinator
from .device import build_aggregate_device_info, build_device_info


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: AdBlockCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = [AdBlockStatusSensor(coordinator, entry)]
    if claim_aggregate_ownership_if_unclaimed(hass, entry):
        entities.append(AdBlockOverallStatusSensor())
    async_add_entities(entities)


class AdBlockStatusSensor(CoordinatorEntity[AdBlockCoordinator], SensorEntity):
    """Reports enabled/disabled/error for one server."""

    _attr_has_entity_name = True
    _attr_name = "Status"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [STATUS_ENABLED, STATUS_DISABLED, STATUS_ERROR]

    def __init__(self, coordinator: AdBlockCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_status"
        self._attr_device_info = build_device_info(entry)

    @property
    def native_value(self) -> str | None:
        return self.coordinator.data.get("status")


class AdBlockOverallStatusSensor(SensorEntity):
    """Reports enabled/disabled/partial/error across every configured server."""

    _attr_has_entity_name = True
    _attr_name = "Overall Status"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [STATUS_ENABLED, STATUS_DISABLED, STATUS_PARTIAL, STATUS_ERROR]
    _attr_should_poll = False
    _attr_unique_id = f"{DOMAIN}_aggregate_status"
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
    def native_value(self) -> str:
        return compute_overall_status(
            c.data["status"] for c in all_coordinators(self.hass)
        )

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        return {
            c.config_entry.title: c.data["status"]
            for c in all_coordinators(self.hass)
        }
