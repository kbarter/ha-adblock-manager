"""Sensor platform for AdBlock Manager."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, STATUS_DISABLED, STATUS_ENABLED, STATUS_ERROR
from .coordinator import AdBlockCoordinator
from .device import build_device_info


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: AdBlockCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([AdBlockStatusSensor(coordinator, entry)])


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
