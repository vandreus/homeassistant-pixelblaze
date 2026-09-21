"""DataUpdateCoordinator glue between the Pixelblaze client and HA."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import PixelblazeClient, PixelblazeError
from .const import CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class PixelblazeCoordinator(DataUpdateCoordinator[None]):
    """Polls the Pixelblaze and relays push updates to entities."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        poll = entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.data['host']}",
            update_interval=timedelta(seconds=poll),
        )
        self.entry = entry
        self.client = PixelblazeClient(
            entry.data["host"],
            async_get_clientsession(hass),
            on_update=self._handle_push,
        )
        self._push_scheduled = False

    @callback
    def _handle_push(self) -> None:
        """Client state changed (push or command echo): refresh entities."""
        if self.hass.loop.is_closed():
            return
        # Debounce: coalesce bursts of frames into one entity update per loop tick.
        if self._push_scheduled:
            return
        self._push_scheduled = True

        def _fire() -> None:
            self._push_scheduled = False
            self.async_set_updated_data(None)

        self.hass.loop.call_soon(_fire)

    async def _async_update_data(self) -> None:
        if not self.client.connected:
            raise UpdateFailed(f"Not connected to {self.client.url}")
        try:
            await self.client.poll()
        except PixelblazeError as err:
            raise UpdateFailed(str(err)) from err
