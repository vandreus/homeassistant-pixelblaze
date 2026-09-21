"""Dynamic number entities for writable exported pattern variables."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import PixelblazeError
from .const import CONF_DYNAMIC_VARS, DEFAULT_DYNAMIC_VARS, DOMAIN
from .coordinator import PixelblazeCoordinator
from .entity import PixelblazeEntity
from .helpers import classify_vars


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    if not entry.options.get(CONF_DYNAMIC_VARS, DEFAULT_DYNAMIC_VARS):
        return
    coordinator: PixelblazeCoordinator = hass.data[DOMAIN][entry.entry_id]
    known: set[str] = set()

    @callback
    def _sync() -> None:
        numbers, _ = classify_vars(coordinator.client.vars)
        new = numbers - known
        if new:
            known.update(new)
            async_add_entities(
                PixelblazeVarNumber(coordinator, name) for name in sorted(new)
            )

    entry.async_on_unload(coordinator.async_add_listener(_sync))
    _sync()


class PixelblazeVarNumber(PixelblazeEntity, NumberEntity):
    """Writable exported variable of the active pattern (e.g. game speed)."""

    _attr_mode = NumberMode.BOX
    _attr_native_min_value = -100000
    _attr_native_max_value = 100000
    _attr_native_step = 0.01
    _attr_icon = "mdi:tune-variant"

    def __init__(self, coordinator: PixelblazeCoordinator, var: str) -> None:
        super().__init__(coordinator)
        self._var = var
        self._attr_unique_id = f"{coordinator.entry.entry_id}_var_{var}"
        self._attr_name = f"Var {var}"

    @property
    def available(self) -> bool:
        return self._client.connected and self._var in self._client.vars

    @property
    def native_value(self) -> float | None:
        value = self._client.vars.get(self._var)
        return float(value) if isinstance(value, (int, float)) else None

    async def async_set_native_value(self, value: float) -> None:
        try:
            await self._client.set_vars({self._var: value})
        except PixelblazeError as err:
            raise HomeAssistantError(str(err)) from err
