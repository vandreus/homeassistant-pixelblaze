"""Base entity for the Pixelblaze integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import PixelblazeCoordinator


class PixelblazeEntity(CoordinatorEntity[PixelblazeCoordinator]):
    """Common device info + availability."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: PixelblazeCoordinator) -> None:
        super().__init__(coordinator)
        entry = coordinator.entry
        self._client = coordinator.client
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data.get("name") or self._client.config.get("name", "Pixelblaze"),
            manufacturer=MANUFACTURER,
            model=MODEL,
            configuration_url=f"http://{entry.data['host']}/",
        )

    @property
    def available(self) -> bool:
        return self._client.connected
