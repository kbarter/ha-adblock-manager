"""Shared test fixtures."""
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.adblock_manager.const import DOMAIN

pytest_plugins = "pytest_homeassistant_custom_component"


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
