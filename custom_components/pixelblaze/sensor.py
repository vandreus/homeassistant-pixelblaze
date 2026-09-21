"""Sensors: FPS, storage, and read-only game variables (score, lives...)."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_DYNAMIC_VARS, DEFAULT_DYNAMIC_VARS, DOMAIN
from .coordinator import PixelblazeCoordinator
from .entity import PixelblazeEntity
from .helpers import classify_vars


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: PixelblazeCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [PixelblazeFpsSensor(coordinator), PixelblazeStorageSensor(coordinator)]
    )

    if not entry.options.get(CONF_DYNAMIC_VARS, DEFAULT_DYNAMIC_VARS):
        return
    known: set[str] = set()

    @callback
    def _sync() -> None:
        _, sensors = classify_vars(coordinator.client.vars)
        new = sensors - known
        if new:
            known.update(new)
            async_add_entities(
                PixelblazeVarSensor(coordinator, name) for name in sorted(new)
            )

    entry.async_on_unload(coordinator.async_add_listener(_sync))
    _sync()


class PixelblazeFpsSensor(PixelblazeEntity, SensorEntity):
    _attr_translation_key = "fps"
    _attr_native_unit_of_measurement = "FPS"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_suggested_display_precision = 0
    _attr_icon = "mdi:speedometer"

    def __init__(self, coordinator: PixelblazeCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_fps"

    @property
    def native_value(self) -> float | None:
        return self._client.fps


class PixelblazeStorageSensor(PixelblazeEntity, SensorEntity):
    _attr_translation_key = "storage"
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_suggested_display_precision = 0
    _attr_icon = "mdi:sd"

    def __init__(self, coordinator: PixelblazeCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_storage"

    @property
    def native_value(self) -> float | None:
        used = self._client.config.get("storageUsed")
        size = self._client.config.get("storageSize")
        if not used or not size:
            return None
        return 100 * used / size


class PixelblazeVarSensor(PixelblazeEntity, SensorEntity):
    """Read-only exported variable of the active pattern (score, lives...)."""

    _attr_icon = "mdi:gamepad-variant"

    def __init__(self, coordinator: PixelblazeCoordinator, var: str) -> None:
        super().__init__(coordinator)
        self._var = var
        self._attr_unique_id = f"{coordinator.entry.entry_id}_var_{var}"
        self._attr_name = var.capitalize()

    @property
    def available(self) -> bool:
        return self._client.connected and self._var in self._client.vars

    @property
    def native_value(self) -> float | None:
        value = self._client.vars.get(self._var)
        return value if isinstance(value, (int, float)) else None
