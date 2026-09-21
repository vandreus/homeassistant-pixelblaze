"""The Pixelblaze integration."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .api import PixelblazeError
from .const import DOMAIN, PLATFORMS, SERVICE_SET_PATTERN, SERVICE_SET_VARS
from .coordinator import PixelblazeCoordinator

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

SET_VARS_SCHEMA = vol.Schema(
    {
        vol.Optional("device_id"): cv.string,
        vol.Required("variables"): dict,
    }
)

SET_PATTERN_SCHEMA = vol.Schema(
    {
        vol.Optional("device_id"): cv.string,
        vol.Exclusive("name", "target"): cv.string,
        vol.Exclusive("id", "target"): cv.string,
    }
)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register domain services."""

    def _coordinator_for(call: ServiceCall) -> PixelblazeCoordinator:
        coordinators: dict[str, PixelblazeCoordinator] = hass.data.get(DOMAIN, {})
        if not coordinators:
            raise HomeAssistantError("No Pixelblaze is configured")
        device_id = call.data.get("device_id")
        if device_id:
            device = dr.async_get(hass).async_get(device_id)
            if device:
                for entry_id in device.config_entries:
                    if entry_id in coordinators:
                        return coordinators[entry_id]
            raise HomeAssistantError(f"Device {device_id} is not a Pixelblaze")
        if len(coordinators) > 1:
            raise HomeAssistantError(
                "Several Pixelblazes are configured; pass device_id"
            )
        return next(iter(coordinators.values()))

    async def handle_set_vars(call: ServiceCall) -> None:
        coordinator = _coordinator_for(call)
        try:
            await coordinator.client.set_vars(call.data["variables"])
        except PixelblazeError as err:
            raise HomeAssistantError(str(err)) from err

    async def handle_set_pattern(call: ServiceCall) -> None:
        coordinator = _coordinator_for(call)
        client = coordinator.client
        pattern_id = call.data.get("id")
        if not pattern_id:
            name = call.data.get("name")
            if not name:
                raise HomeAssistantError("Provide a pattern name or id")
            pattern_id = client.pattern_id_by_name(name)
            if not pattern_id:
                raise HomeAssistantError(f"Unknown pattern: {name}")
        try:
            await client.set_active_pattern(pattern_id)
        except PixelblazeError as err:
            raise HomeAssistantError(str(err)) from err

    hass.services.async_register(
        DOMAIN, SERVICE_SET_VARS, handle_set_vars, schema=SET_VARS_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_PATTERN, handle_set_pattern, schema=SET_PATTERN_SCHEMA
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a Pixelblaze from a config entry."""
    coordinator = PixelblazeCoordinator(hass, entry)
    await coordinator.client.start()
    try:
        await coordinator.client.wait_connected()
    except PixelblazeError as err:
        await coordinator.client.stop()
        raise ConfigEntryNotReady(str(err)) from err

    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        coordinator: PixelblazeCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.client.stop()
    return ok
