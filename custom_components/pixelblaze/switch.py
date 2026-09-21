"""Sequencer (shuffle) switch."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import PixelblazeError
from .const import DOMAIN
from .coordinator import PixelblazeCoordinator
from .entity import PixelblazeEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: PixelblazeCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([PixelblazeSequencerSwitch(coordinator)])


class PixelblazeSequencerSwitch(PixelblazeEntity, SwitchEntity):
    """Runs the shuffle-all sequencer."""

    _attr_translation_key = "sequencer"
    _attr_icon = "mdi:shuffle-variant"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: PixelblazeCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_sequencer"

    @property
    def is_on(self) -> bool:
        return self._client.sequencer_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        try:
            await self._client.set_sequencer(True, mode=1)
        except PixelblazeError as err:
            raise HomeAssistantError(str(err)) from err

    async def async_turn_off(self, **kwargs: Any) -> None:
        try:
            await self._client.set_sequencer(False)
        except PixelblazeError as err:
            raise HomeAssistantError(str(err)) from err
