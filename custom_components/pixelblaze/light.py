"""Light entity mapping the Pixelblaze global brightness."""

from __future__ import annotations

from typing import Any

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
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
    async_add_entities([PixelblazeLight(coordinator)])


class PixelblazeLight(PixelblazeEntity, LightEntity):
    """On/off + dimming via the device's global brightness (0..1)."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_name = None  # takes the device name

    def __init__(self, coordinator: PixelblazeCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_light"

    @property
    def _device_brightness(self) -> float:
        try:
            return float(self._client.config.get("brightness", 0))
        except (TypeError, ValueError):
            return 0.0

    @property
    def is_on(self) -> bool:
        return self._device_brightness > 0

    @property
    def brightness(self) -> int:
        return round(self._device_brightness * 255)

    async def async_turn_on(self, **kwargs: Any) -> None:
        if ATTR_BRIGHTNESS in kwargs:
            target = kwargs[ATTR_BRIGHTNESS] / 255
        else:
            target = self._client.last_brightness or 1.0
        try:
            await self._client.set_brightness(target)
        except PixelblazeError as err:
            raise HomeAssistantError(str(err)) from err

    async def async_turn_off(self, **kwargs: Any) -> None:
        try:
            await self._client.set_brightness(0)
        except PixelblazeError as err:
            raise HomeAssistantError(str(err)) from err
