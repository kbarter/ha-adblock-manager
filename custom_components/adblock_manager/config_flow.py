"""Config flow for AdBlock Manager."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_TOKEN, CONF_VERIFY_SSL
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import (
    AdBlockAuthError,
    AdBlockConnectionError,
    PiHoleClient,
    TechnitiumClient,
)
from .const import (
    CONF_API_VERSION,
    CONF_SERVER_TYPE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    ServerType,
)

CONF_SCAN_INTERVAL = "scan_interval"


async def _async_validate(hass, data: dict[str, Any]) -> None:
    """Raise AdBlockAuthError/AdBlockConnectionError if unreachable."""
    session = async_get_clientsession(hass, verify_ssl=data.get(CONF_VERIFY_SSL, True))
    if data[CONF_SERVER_TYPE] == ServerType.TECHNITIUM:
        client = TechnitiumClient(session, data[CONF_HOST], data[CONF_TOKEN])
    else:
        client = PiHoleClient(
            session,
            data[CONF_HOST],
            data[CONF_API_VERSION],
            token=data.get(CONF_TOKEN),
            password=data.get(CONF_PASSWORD),
        )
    await client.async_get_status()


class AdBlockManagerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for AdBlock Manager."""

    VERSION = 1

    def __init__(self) -> None:
        self._server_type: ServerType | None = None
        self._reauth_entry: ConfigEntry | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> Any:
        if user_input is not None:
            self._server_type = ServerType(user_input[CONF_SERVER_TYPE])
            if self._server_type == ServerType.TECHNITIUM:
                return await self.async_step_technitium()
            return await self.async_step_pihole()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SERVER_TYPE, default=ServerType.PIHOLE
                    ): vol.In([ServerType.PIHOLE, ServerType.TECHNITIUM])
                }
            ),
        )

    async def async_step_technitium(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {
                CONF_SERVER_TYPE: ServerType.TECHNITIUM,
                CONF_HOST: user_input[CONF_HOST],
                CONF_TOKEN: user_input[CONF_TOKEN],
                CONF_VERIFY_SSL: user_input[CONF_VERIFY_SSL],
            }
            errors = await self._async_try_create(data)
            if not errors:
                return self.async_create_entry(title=data[CONF_HOST], data=data)

        return self.async_show_form(
            step_id="technitium",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_TOKEN): str,
                    vol.Required(CONF_VERIFY_SSL, default=True): bool,
                }
            ),
            errors=errors,
        )

    async def async_step_pihole(self, user_input: dict[str, Any] | None = None) -> Any:
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {
                CONF_SERVER_TYPE: ServerType.PIHOLE,
                CONF_HOST: user_input[CONF_HOST],
                CONF_API_VERSION: user_input[CONF_API_VERSION],
                CONF_VERIFY_SSL: user_input[CONF_VERIFY_SSL],
            }
            if data[CONF_API_VERSION] == 6:
                data[CONF_PASSWORD] = user_input.get(CONF_PASSWORD, "")
            else:
                data[CONF_TOKEN] = user_input.get(CONF_TOKEN, "")
            errors = await self._async_try_create(data)
            if not errors:
                return self.async_create_entry(title=data[CONF_HOST], data=data)

        return self.async_show_form(
            step_id="pihole",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_API_VERSION, default=6): vol.In([5, 6]),
                    vol.Optional(CONF_PASSWORD): str,
                    vol.Optional(CONF_TOKEN): str,
                    vol.Required(CONF_VERIFY_SSL, default=True): bool,
                }
            ),
            errors=errors,
        )

    async def _async_try_create(self, data: dict[str, Any]) -> dict[str, str]:
        await self.async_set_unique_id(f"{data[CONF_SERVER_TYPE]}:{data[CONF_HOST]}")
        self._abort_if_unique_id_configured()
        try:
            await _async_validate(self.hass, data)
        except AdBlockAuthError:
            return {"base": "invalid_auth"}
        except AdBlockConnectionError:
            return {"base": "cannot_connect"}
        return {}

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> Any:
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        self._server_type = ServerType(entry_data[CONF_SERVER_TYPE])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        errors: dict[str, str] = {}
        assert self._reauth_entry is not None
        if user_input is not None:
            data = {**self._reauth_entry.data}
            if self._server_type == ServerType.TECHNITIUM:
                data[CONF_TOKEN] = user_input[CONF_TOKEN]
            elif data[CONF_API_VERSION] == 6:
                data[CONF_PASSWORD] = user_input[CONF_PASSWORD]
            else:
                data[CONF_TOKEN] = user_input[CONF_TOKEN]

            try:
                await _async_validate(self.hass, data)
            except AdBlockAuthError:
                errors["base"] = "invalid_auth"
            except AdBlockConnectionError:
                errors["base"] = "cannot_connect"

            if not errors:
                # async_update_entry alone is enough: it fires the update
                # listener registered in __init__.py (which reloads this
                # entry) whenever data actually changes. Reauth always
                # changes data, so async_update_reload_and_abort's own
                # unconditional reload would fire a second time on top of
                # the listener's - do not use it here.
                self.hass.config_entries.async_update_entry(
                    self._reauth_entry, data=data
                )
                return self.async_abort(reason="reauth_successful")

        if self._server_type == ServerType.TECHNITIUM:
            schema = vol.Schema({vol.Required(CONF_TOKEN): str})
        elif self._reauth_entry.data[CONF_API_VERSION] == 6:
            schema = vol.Schema({vol.Required(CONF_PASSWORD): str})
        else:
            schema = vol.Schema({vol.Required(CONF_TOKEN): str})

        return self.async_show_form(
            step_id="reauth_confirm", data_schema=schema, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> AdBlockManagerOptionsFlow:
        return AdBlockManagerOptionsFlow()


class AdBlockManagerOptionsFlow(OptionsFlow):
    """Options for scan interval and SSL verification.

    `config_entry` is provided read-only by the OptionsFlow base class;
    assigning it in __init__ is removed in HA 2025.12 and raises there.
    """

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> Any:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=current.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    ): int,
                    vol.Required(
                        CONF_VERIFY_SSL,
                        default=current.get(
                            CONF_VERIFY_SSL,
                            self.config_entry.data.get(CONF_VERIFY_SSL, True),
                        ),
                    ): bool,
                }
            ),
        )
