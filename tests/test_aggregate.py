"""Tests for cross-entry aggregate helpers."""
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.adblock_manager.aggregate import (
    all_coordinators,
    claim_aggregate_ownership_if_unclaimed,
    compute_overall_status,
    is_aggregate_owner,
    release_aggregate_ownership,
)
from custom_components.adblock_manager.const import (
    DOMAIN,
    STATUS_DISABLED,
    STATUS_ENABLED,
    STATUS_ERROR,
    STATUS_PARTIAL,
)
from custom_components.adblock_manager.device import build_aggregate_device_info


def test_all_enabled_is_enabled() -> None:
    assert compute_overall_status([STATUS_ENABLED, STATUS_ENABLED]) == STATUS_ENABLED


def test_all_disabled_is_disabled() -> None:
    assert (
        compute_overall_status([STATUS_DISABLED, STATUS_DISABLED]) == STATUS_DISABLED
    )


def test_mixed_enabled_and_disabled_is_partial() -> None:
    assert (
        compute_overall_status([STATUS_ENABLED, STATUS_DISABLED]) == STATUS_PARTIAL
    )


def test_any_error_takes_priority_over_partial() -> None:
    assert (
        compute_overall_status([STATUS_ENABLED, STATUS_ERROR, STATUS_DISABLED])
        == STATUS_ERROR
    )


def test_empty_statuses_is_error() -> None:
    assert compute_overall_status([]) == STATUS_ERROR


def _entry(entry_id: str) -> MockConfigEntry:
    return MockConfigEntry(domain=DOMAIN, entry_id=entry_id)


async def test_first_entry_claims_ownership(hass: HomeAssistant) -> None:
    hass.data[DOMAIN] = {"entry_a": object()}
    entry_a = _entry("entry_a")

    assert claim_aggregate_ownership_if_unclaimed(hass, entry_a) is True
    assert is_aggregate_owner(hass, entry_a) is True


async def test_second_entry_does_not_claim_ownership(hass: HomeAssistant) -> None:
    hass.data[DOMAIN] = {"entry_a": object(), "entry_b": object()}
    entry_a = _entry("entry_a")
    entry_b = _entry("entry_b")
    claim_aggregate_ownership_if_unclaimed(hass, entry_a)

    assert claim_aggregate_ownership_if_unclaimed(hass, entry_b) is False
    assert is_aggregate_owner(hass, entry_b) is False


async def test_release_by_non_owner_is_a_no_op(hass: HomeAssistant) -> None:
    hass.data[DOMAIN] = {"entry_a": object(), "entry_b": object()}
    entry_a = _entry("entry_a")
    entry_b = _entry("entry_b")
    claim_aggregate_ownership_if_unclaimed(hass, entry_a)

    assert release_aggregate_ownership(hass, entry_b) is None
    assert is_aggregate_owner(hass, entry_a) is True


async def test_release_by_owner_returns_a_remaining_entry_id(
    hass: HomeAssistant,
) -> None:
    hass.data[DOMAIN] = {"entry_a": object(), "entry_b": object()}
    entry_a = _entry("entry_a")
    claim_aggregate_ownership_if_unclaimed(hass, entry_a)
    del hass.data[DOMAIN]["entry_a"]

    assert release_aggregate_ownership(hass, entry_a) == "entry_b"
    assert is_aggregate_owner(hass, entry_a) is False


async def test_release_with_no_remaining_entries_returns_none(
    hass: HomeAssistant,
) -> None:
    hass.data[DOMAIN] = {"entry_a": object()}
    entry_a = _entry("entry_a")
    claim_aggregate_ownership_if_unclaimed(hass, entry_a)
    del hass.data[DOMAIN]["entry_a"]

    assert release_aggregate_ownership(hass, entry_a) is None


def test_all_coordinators_returns_every_configured_coordinator() -> None:
    class FakeHass:
        data = {DOMAIN: {"a": "coordinator_a", "b": "coordinator_b"}}

    assert sorted(all_coordinators(FakeHass())) == ["coordinator_a", "coordinator_b"]


def test_aggregate_device_info_uses_a_fixed_identifier() -> None:
    device_info = build_aggregate_device_info()
    assert device_info["identifiers"] == {(DOMAIN, "aggregate")}
    assert device_info["name"] == "AdBlock"
