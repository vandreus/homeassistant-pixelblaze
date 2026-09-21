"""Config flow for the Pixelblaze integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, OptionsFlow

try:  # HA >= 2024.4
    from homeassistant.config_entries import ConfigFlowResult
except ImportError:  # pragma: no cover - older cores
    from homeassistant.data_entry_flow import FlowResult as ConfigFlowResult
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import PixelblazeClient, PixelblazeError
from .const import (
    CONF_DYNAMIC_VARS,
    CONF_POLL_INTERVAL,
    DEFAULT_DYNAMIC_VARS,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
)

USER_SCHEMA = vol.Schema(
    {
        vol.Required("host"): str,
        vol.Optional("name", default="Pixelblaze"): str,
    }
)


class PixelblazeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the UI configuration of a Pixelblaze."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input["host"].strip()
            await self.async_set_unique_id(host)
            self._abort_if_unique_id_configured()

            client = PixelblazeClient(host, async_get_clientsession(self.hass))
            try:
                await client.start()
                await client.wait_connected(timeout=8)
                await client.poll()
            except PixelblazeError:
                errors["base"] = "cannot_connect"
            finally:
                await client.stop()

            if not errors:
                title = user_input.get("name") or client.config.get(
                    "name", "Pixelblaze"
                )
                return self.async_create_entry(
                    title=title, data={"host": host, "name": title}
                )

        return self.async_show_form(
            step_id="user", data_schema=USER_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> PixelblazeOptionsFlow:
        return PixelblazeOptionsFlow()


class PixelblazeOptionsFlow(OptionsFlow):
    """Options: poll interval, dynamic variable entities."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_POLL_INTERVAL,
                    default=options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
                ): vol.All(vol.Coerce(int), vol.Range(min=2, max=300)),
                vol.Optional(
                    CONF_DYNAMIC_VARS,
                    default=options.get(CONF_DYNAMIC_VARS, DEFAULT_DYNAMIC_VARS),
                ): bool,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
