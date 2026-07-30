"""Constants for the AdBlock Manager integration."""
from __future__ import annotations

from enum import StrEnum

from homeassistant.const import Platform

DOMAIN = "adblock_manager"

PLATFORMS = [Platform.SWITCH, Platform.SENSOR]

CONF_SERVER_TYPE = "server_type"
CONF_API_VERSION = "api_version"

DEFAULT_SCAN_INTERVAL = 30

STATUS_ENABLED = "enabled"
STATUS_DISABLED = "disabled"
STATUS_ERROR = "error"


class ServerType(StrEnum):
    """Supported DNS server types."""

    PIHOLE = "pihole"
    TECHNITIUM = "technitium"
