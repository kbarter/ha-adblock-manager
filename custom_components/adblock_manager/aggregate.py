"""Shared logic for the cross-entry AdBlock aggregate switch/sensor."""
from __future__ import annotations

from collections.abc import Iterable

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    AGGREGATE_OWNER_DATA_KEY,
    DOMAIN,
    STATUS_DISABLED,
    STATUS_ENABLED,
    STATUS_ERROR,
    STATUS_PARTIAL,
)
from .coordinator import AdBlockCoordinator


def compute_overall_status(statuses: Iterable[str]) -> str:
    """Combine each configured server's status into one overall status.

    `error` takes priority over every other case since a server we can't
    reach means we can't vouch for the true combined state.
    """
    statuses = list(statuses)
    if not statuses or any(status == STATUS_ERROR for status in statuses):
        return STATUS_ERROR
    if all(status == STATUS_ENABLED for status in statuses):
        return STATUS_ENABLED
    if all(status == STATUS_DISABLED for status in statuses):
        return STATUS_DISABLED
    return STATUS_PARTIAL


def all_coordinators(hass: HomeAssistant) -> list[AdBlockCoordinator]:
    """Return every configured server's coordinator, across all entries."""
    return list(hass.data.get(DOMAIN, {}).values())


def is_aggregate_owner(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Return whether `entry` currently owns the aggregate entities."""
    return hass.data.get(AGGREGATE_OWNER_DATA_KEY) == entry.entry_id


def claim_aggregate_ownership_if_unclaimed(
    hass: HomeAssistant, entry: ConfigEntry
) -> bool:
    """Claim aggregate ownership for `entry` if nobody currently holds it.

    Returns True if `entry` owns (or now owns) the aggregate entities.
    """
    current_owner = hass.data.get(AGGREGATE_OWNER_DATA_KEY)
    if current_owner is not None and current_owner in hass.data.get(DOMAIN, {}):
        return current_owner == entry.entry_id
    hass.data[AGGREGATE_OWNER_DATA_KEY] = entry.entry_id
    return True


def release_aggregate_ownership(hass: HomeAssistant, entry: ConfigEntry) -> str | None:
    """Release ownership held by `entry`, if any.

    Returns another remaining entry_id that should be reloaded to take
    over ownership, or None if `entry` wasn't the owner or no entries
    remain.
    """
    if hass.data.get(AGGREGATE_OWNER_DATA_KEY) != entry.entry_id:
        return None
    hass.data.pop(AGGREGATE_OWNER_DATA_KEY, None)
    remaining = [
        entry_id for entry_id in hass.data.get(DOMAIN, {}) if entry_id != entry.entry_id
    ]
    return remaining[0] if remaining else None
