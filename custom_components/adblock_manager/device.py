"""Shared device metadata for AdBlock Manager entities."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo

from .const import CONF_API_VERSION, CONF_SERVER_TYPE, DOMAIN, ServerType


def build_device_info(entry: ConfigEntry) -> DeviceInfo:
    """Return the single HA device shared by this entry's entities.

    Both platforms call this so the switch and the sensor land on one
    device, and so manufacturer/model stay defined in exactly one place.
    """
    # entry.data is plain JSON, so this is a stored string, not a
    # ServerType member - compare with == (StrEnum compares equal to its
    # string value) rather than using it as a dict key.
    server_type = entry.data.get(CONF_SERVER_TYPE)

    if server_type == ServerType.TECHNITIUM:
        manufacturer = "Technitium"
        model = "Technitium DNS"
    else:
        manufacturer = "Pi-hole"
        api_version = entry.data.get(CONF_API_VERSION)
        model = f"v{api_version}" if api_version else "Pi-hole"

    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
        manufacturer=manufacturer,
        model=model,
    )
