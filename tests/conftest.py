"""Shared test fixtures."""
import pycares
import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.adblock_manager.const import DOMAIN

pytest_plugins = "pytest_homeassistant_custom_component"

# pycares starts a permanent daemon thread on first use and never joins
# it (by design). Whichever test triggers that first gets falsely
# blamed by the per-test "no new threads" check. Pre-warm it here so
# it's already running before any test's thread snapshot.
pycares.Channel()


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Test Pi-hole",
        data={
            "server_type": "pihole",
            "host": "http://pihole.example.com",
            "api_version": 6,
            "password": "secret",
            "verify_ssl": True,
        },
        unique_id="pihole:http://pihole.example.com",
    )


@pytest.fixture
def setup_two_entries():
    """Register and set up two AdBlock Manager config entries together.

    Configure `aioclient_mock` for both hosts first, then await with
    just `hass`. Only entry_a is explicitly set up - HA's domain
    bootstrap loads both since they're already registered; a second
    `async_setup` call on entry_b would raise `OperationNotAllowed`.
    """

    async def _setup_two_entries(
        hass: HomeAssistant,
    ) -> tuple[MockConfigEntry, MockConfigEntry]:
        entry_a = MockConfigEntry(
            domain=DOMAIN,
            title="Server A",
            data={
                "server_type": "technitium",
                "host": "http://a.example.com",
                "token": "tok",
                "verify_ssl": True,
            },
            unique_id="technitium:http://a.example.com",
        )
        entry_b = MockConfigEntry(
            domain=DOMAIN,
            title="Server B",
            data={
                "server_type": "technitium",
                "host": "http://b.example.com",
                "token": "tok",
                "verify_ssl": True,
            },
            unique_id="technitium:http://b.example.com",
        )
        entry_a.add_to_hass(hass)
        entry_b.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry_a.entry_id)
        await hass.async_block_till_done()
        assert entry_b.state is ConfigEntryState.LOADED
        return entry_a, entry_b

    return _setup_two_entries
