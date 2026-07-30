"""Async clients for Pi-hole and Technitium DNS servers."""
from __future__ import annotations

import asyncio
import re
from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta
from typing import Any

import aiohttp

from .const import STATUS_DISABLED, STATUS_ENABLED

# Credentials travel as query-string parameters on some server APIs (notably
# Pi-hole v5's `?auth=<token>`), and aiohttp puts the full request URL into
# ClientResponseError.__str__(). Any error text derived from an aiohttp
# exception must be scrubbed before it reaches an HA log or the UI.
_CREDENTIAL_QUERY_RE = re.compile(
    r"([?&])(auth|token|password|sid|api_key)=[^\s&'\"]*", re.IGNORECASE
)


def redact_credentials(message: str) -> str:
    """Replace credential-bearing query-string values with ``***``."""
    return _CREDENTIAL_QUERY_RE.sub(r"\1\2=***", message)


class AdBlockError(Exception):
    """Base error for AdBlock client failures."""


class AdBlockAuthError(AdBlockError):
    """Raised when the server rejects credentials (401/403)."""


class AdBlockConnectionError(AdBlockError):
    """Raised on connection failure, timeout, or unexpected server error."""


class DNSClient(ABC):
    """Base class for an async Pi-hole/Technitium client."""

    def __init__(self, session: aiohttp.ClientSession, host: str) -> None:
        self._session = session
        self.host = host.rstrip("/")

    async def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        try:
            async with asyncio.timeout(10):
                async with self._session.request(
                    method, url, params=params, json=json, headers=headers
                ) as resp:
                    if resp.status in (401, 403):
                        raise AdBlockAuthError(
                            f"Authentication failed ({resp.status})"
                        )
                    resp.raise_for_status()
                    return await resp.json()
        except AdBlockAuthError:
            raise
        except TimeoutError as err:
            raise AdBlockConnectionError("Timed out connecting to server") from err
        except aiohttp.ContentTypeError as err:
            # Raised by resp.json() when the server answers with a 2xx but
            # a non-JSON content type (e.g. an HTML error/login page) - a
            # ClientResponseError subclass, so it must be checked before
            # the generic branch below or it would misleadingly render as
            # "Server returned HTTP 200".
            raise AdBlockConnectionError(
                "Server returned an unexpected content type"
            ) from err
        except aiohttp.ClientResponseError as err:
            # str(err) embeds the real request URL (and therefore any token
            # carried in the query string) — build the message from the
            # status code instead.
            raise AdBlockConnectionError(
                f"Server returned HTTP {err.status}"
            ) from err
        except aiohttp.ClientError as err:
            raise AdBlockConnectionError(redact_credentials(str(err))) from err
        except ValueError as err:
            # json.JSONDecodeError subclasses ValueError: a truncated or
            # non-JSON body is a connection-level problem, not an auth one,
            # so entities must stay available and show "error" instead.
            raise AdBlockConnectionError("Malformed response from server") from err

    @staticmethod
    def _local_disabled_until(minutes: int) -> str:
        """Fallback `disabled_until` for servers that report no remaining time."""
        return (datetime.now(UTC) + timedelta(minutes=minutes)).isoformat()

    @abstractmethod
    async def async_get_status(self) -> dict[str, Any]:
        """Return {"status": "enabled"|"disabled", "disabled_until": str | None}."""

    @abstractmethod
    async def async_set_status(
        self, action: str, minutes: int | None = None
    ) -> dict[str, Any]:
        """Enable or disable blocking. `minutes` only applies to disable."""

    async def async_close(self) -> None:
        """Optional cleanup for session-based APIs."""
        return


class TechnitiumClient(DNSClient):
    """Async client for Technitium DNS."""

    def __init__(self, session: aiohttp.ClientSession, host: str, token: str) -> None:
        super().__init__(session, host)
        self._token = token

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    async def async_get_status(self) -> dict[str, Any]:
        data = await self._request(
            "GET",
            f"{self.host}/api/settings/get",
            params={"token": self._token},
            headers=self._auth_headers(),
        )
        self._raise_for_api_error(data)
        # `or {}` (not a .get() default) so a literal `"response": null`
        # still yields a mapping instead of blowing up on .get() below.
        response = data.get("response") or {}
        is_enabled = response.get("enableBlocking", False)
        disabled_until = None
        if not is_enabled:
            # `temporaryDisableBlockingTill` is only returned by
            # /api/settings/temporaryDisableBlocking, not by settings/get.
            # It's read here defensively in case a future server version
            # surfaces it; async_set_status captures the authoritative value.
            temp_until = response.get("temporaryDisableBlockingTill")
            if temp_until:
                disabled_until = temp_until
        return {
            "status": STATUS_ENABLED if is_enabled else STATUS_DISABLED,
            "disabled_until": disabled_until,
        }

    @staticmethod
    def _raise_for_api_error(data: dict[str, Any]) -> None:
        if data.get("status") != "ok":
            raise AdBlockConnectionError(
                redact_credentials(str(data.get("errorMessage", "Unknown API error")))
            )

    async def async_set_status(
        self, action: str, minutes: int | None = None
    ) -> dict[str, Any]:
        timed_disable = action == "disable" and bool(minutes)
        server_disabled_until: str | None = None

        if timed_disable:
            data = await self._request(
                "POST",
                f"{self.host}/api/settings/temporaryDisableBlocking",
                params={"token": self._token, "minutes": max(1, minutes)},
                headers=self._auth_headers(),
            )
            self._raise_for_api_error(data)
            # The only place Technitium reports the resume time.
            server_disabled_until = (data.get("response") or {}).get(
                "temporaryDisableBlockingTill"
            )
        else:
            data = await self._request(
                "POST",
                f"{self.host}/api/settings/set",
                params={
                    "token": self._token,
                    "enableBlocking": "true" if action == "enable" else "false",
                },
                headers=self._auth_headers(),
            )
            self._raise_for_api_error(data)

        status = await self.async_get_status()
        if timed_disable:
            status["disabled_until"] = (
                server_disabled_until
                or status.get("disabled_until")
                or self._local_disabled_until(minutes)
            )
        return status


class PiHoleClient(DNSClient):
    """Async client for Pi-hole v5 and v6."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        version: int,
        token: str | None = None,
        password: str | None = None,
    ) -> None:
        super().__init__(session, host)
        self.version = version
        self._token = token
        self._password = password
        self._sid: str | None = None
        self._base_url = (
            f"{self.host}/api" if version == 6 else f"{self.host}/admin/api.php"
        )

    def _sid_headers(self) -> dict[str, str]:
        """Pi-hole v6 session header.

        v6 accepts the session id as `?sid=`, a JSON `sid` field, an `sid`
        cookie, or the `X-FTL-SID` header — a bare `sid:` header is NOT
        accepted and always 401s.
        """
        return {"X-FTL-SID": self._sid or ""}

    async def _v6_auth(self) -> None:
        if self._sid:
            return
        data = await self._request(
            "POST", f"{self._base_url}/auth", json={"password": self._password}
        )
        session = data.get("session") or {}
        if not session.get("valid"):
            raise AdBlockAuthError("Invalid Pi-hole password")
        sid = session.get("sid")
        if not sid:
            raise AdBlockConnectionError("Malformed auth response: missing sid")
        self._sid = sid

    async def async_get_status(self) -> dict[str, Any]:
        if self.version == 6:
            await self._v6_auth()
            try:
                data = await self._request(
                    "GET",
                    f"{self._base_url}/dns/blocking",
                    headers=self._sid_headers(),
                )
            except AdBlockAuthError:
                self._sid = None
                await self._v6_auth()
                data = await self._request(
                    "GET",
                    f"{self._base_url}/dns/blocking",
                    headers=self._sid_headers(),
                )
            # NOTE: Pi-hole v6 has returned `blocking` as both a boolean and
            # a string enum ("enabled"/"disabled") across versions — handle
            # both rather than relying on truthiness (a plain `if blocking:`
            # would wrongly treat the string "disabled" as truthy).
            blocking = data.get("blocking")
            is_enabled = blocking is True or blocking == "enabled"
            disabled_until = None
            timer = data.get("timer")
            if not is_enabled and timer:
                disabled_until = (
                    datetime.now(UTC) + timedelta(seconds=timer)
                ).isoformat()
            return {
                "status": STATUS_ENABLED if is_enabled else STATUS_DISABLED,
                "disabled_until": disabled_until,
            }

        data = await self._request(
            "GET", self._base_url, params={"status": 1, "auth": self._token}
        )
        status = data.get("status")
        return {
            "status": STATUS_ENABLED if status == "enabled" else STATUS_DISABLED,
            "disabled_until": None,
        }

    async def async_set_status(
        self, action: str, minutes: int | None = None
    ) -> dict[str, Any]:
        if self.version == 6:
            await self._v6_auth()
            payload: dict[str, Any] = {"blocking": action == "enable"}
            if action == "disable" and minutes:
                payload["timer"] = minutes * 60
            try:
                await self._request(
                    "POST",
                    f"{self._base_url}/dns/blocking",
                    json=payload,
                    headers=self._sid_headers(),
                )
            except AdBlockAuthError:
                self._sid = None
                await self._v6_auth()
                await self._request(
                    "POST",
                    f"{self._base_url}/dns/blocking",
                    json=payload,
                    headers=self._sid_headers(),
                )
        else:
            params = {action: "", "auth": self._token}
            if action == "disable" and minutes:
                params[action] = str(minutes * 60)
            await self._request("GET", self._base_url, params=params)

        status = await self.async_get_status()
        if action == "disable" and minutes and not status.get("disabled_until"):
            # v5 has no remaining-time field at all, and v6 can race the
            # timer field — fall back to call-time + minutes so the switch
            # always exposes a disabled_until right after a timed disable.
            status["disabled_until"] = self._local_disabled_until(minutes)
        return status

    async def async_close(self) -> None:
        if self.version == 6 and self._sid:
            try:
                await self._request(
                    "DELETE", f"{self._base_url}/auth", headers=self._sid_headers()
                )
            except AdBlockError:
                pass
            self._sid = None
