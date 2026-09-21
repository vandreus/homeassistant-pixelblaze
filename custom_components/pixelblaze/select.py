"""Pattern selection entity."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import PixelblazeError
from .const import DOMAIN
from .coordinator import PixelblazeCoordinator
from .entity import PixelblazeEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: PixelblazeCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([PixelblazePatternSelect(coordinator)])


class PixelblazePatternSelect(PixelblazeEntity, SelectEntity):
    """Dropdown of saved patterns; reflects outside changes via polling."""

    _attr_translation_key = "pattern"
    _attr_icon = "mdi:led-strip-variant"

    def __init__(self, coordinator: PixelblazeCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_pattern"

    @property
    def options(self) -> list[str]:
        return sorted(set(self._client.patterns.values()), key=str.casefold)

    @property
    def current_option(self) -> str | None:
        name = self._client.active_name
        if name in self.options:
            return name
        return None

    async def async_select_option(self, option: str) -> None:
        pattern_id = self._client.pattern_id_by_name(option)
        if pattern_id is None:
            raise HomeAssistantError(f"Unknown pattern: {option}")
        try:
            await self._client.set_active_pattern(pattern_id)
        except PixelblazeError as err:
            raise HomeAssistantError(str(err)) from err
