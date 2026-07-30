"""Tests for the async PiHoleClient (v5 and v6)."""
import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.adblock_manager.client import AdBlockAuthError, PiHoleClient


async def test_v6_get_status_enabled(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.post(
        "http://pihole.example.com/api/auth",
        json={"session": {"valid": True, "sid": "abc123"}},
    )
    aioclient_mock.get(
        "http://pihole.example.com/api/dns/blocking",
        json={"blocking": "enabled", "timer": None},
    )
    client = PiHoleClient(
        async_get_clientsession(hass), "http://pihole.example.com", 6, password="secret"
    )
    result = await client.async_get_status()
    assert result == {"status": "enabled", "disabled_until": None}


async def test_v6_get_status_disabled_with_timer(
    hass: HomeAssistant, aioclient_mock
) -> None:
    aioclient_mock.post(
        "http://pihole.example.com/api/auth",
        json={"session": {"valid": True, "sid": "abc123"}},
    )
    aioclient_mock.get(
        "http://pihole.example.com/api/dns/blocking",
        json={"blocking": "disabled", "timer": 120},
    )
    client = PiHoleClient(
        async_get_clientsession(hass), "http://pihole.example.com", 6, password="secret"
    )
    result = await client.async_get_status()
    assert result["status"] == "disabled"
    assert result["disabled_until"] is not None


async def test_v6_invalid_password(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.post(
        "http://pihole.example.com/api/auth",
        json={"session": {"valid": False}},
    )
    client = PiHoleClient(
        async_get_clientsession(hass), "http://pihole.example.com", 6, password="wrong"
    )
    with pytest.raises(AdBlockAuthError):
        await client.async_get_status()


async def test_v5_get_status(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get(
        "http://legacy.example.com/admin/api.php",
        json={"status": "enabled"},
    )
    client = PiHoleClient(
        async_get_clientsession(hass), "http://legacy.example.com", 5, token="tok"
    )
    result = await client.async_get_status()
    assert result == {"status": "enabled", "disabled_until": None}


async def test_v6_uses_x_ftl_sid_header(hass: HomeAssistant, aioclient_mock) -> None:
    """Pi-hole v6 only accepts the session id via X-FTL-SID (or a query
    param/JSON field/cookie) - a bare `sid:` header always 401s."""
    aioclient_mock.post(
        "http://pihole.example.com/api/auth",
        json={"session": {"valid": True, "sid": "abc123"}},
    )
    aioclient_mock.get(
        "http://pihole.example.com/api/dns/blocking",
        json={"blocking": "enabled", "timer": None},
    )
    client = PiHoleClient(
        async_get_clientsession(hass), "http://pihole.example.com", 6, password="secret"
    )
    await client.async_get_status()

    blocking_calls = [
        call for call in aioclient_mock.mock_calls if "dns/blocking" in str(call[1])
    ]
    assert blocking_calls, "expected a dns/blocking request"
    headers = blocking_calls[0][3]
    assert headers is not None
    assert headers.get("X-FTL-SID") == "abc123"
    assert "sid" not in {k.lower() for k in headers}


async def test_v5_disable_with_timer_sets_local_disabled_until(
    hass: HomeAssistant, aioclient_mock
) -> None:
    """Pi-hole v5 has no remaining-time field at all, so disabled_until must
    fall back to a locally-computed call-time + minutes value."""
    # aioclient_mock matches on the full URL including query string and
    # never consumes a registration, so the disable action call and the
    # follow-up status check (different params) need distinct registrations.
    aioclient_mock.get(
        "http://legacy.example.com/admin/api.php",
        params={"disable": "300", "auth": "tok"},
        json={"status": "ok"},
    )
    aioclient_mock.get(
        "http://legacy.example.com/admin/api.php",
        params={"status": 1, "auth": "tok"},
        json={"status": "disabled"},
    )
    client = PiHoleClient(
        async_get_clientsession(hass), "http://legacy.example.com", 5, token="tok"
    )
    result = await client.async_set_status("disable", minutes=5)
    assert result["status"] == "disabled"
    assert result["disabled_until"] is not None


async def test_v6_get_status_with_401_retry(
    hass: HomeAssistant, aioclient_mock, monkeypatch
) -> None:
    """Test that 401 on dns/blocking triggers re-auth and retry."""
    # Track GET request count
    call_count = {"get": 0}

    # Create a mock response class
    class MockResponse:
        def __init__(self, status, json_data=None):
            self.status = status
            self._json_data = json_data

        async def json(self):
            return self._json_data

        def raise_for_status(self):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return None

    def mock_request(method, url, **kwargs):
        """Return a context manager for the mock response."""
        if method == "GET" and "dns/blocking" in url:
            call_count["get"] += 1
            if call_count["get"] == 1:
                resp = MockResponse(401)
            else:
                resp = MockResponse(200, {"blocking": "enabled", "timer": None})
        elif method == "POST" and "auth" in url:
            resp = MockResponse(200, {"session": {"valid": True, "sid": "abc123"}})
        else:
            raise ValueError(f"Unexpected request: {method} {url}")

        return resp

    # Patch the session's request method
    session = async_get_clientsession(hass)
    monkeypatch.setattr(session, "request", mock_request)

    client = PiHoleClient(session, "http://pihole.example.com", 6, password="secret")
    result = await client.async_get_status()
    assert result == {"status": "enabled", "disabled_until": None}
    assert call_count["get"] == 2  # Verify retry happened
