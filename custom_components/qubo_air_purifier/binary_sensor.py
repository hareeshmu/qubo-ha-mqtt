"""Binary sensor: Air Quality Good (the device's leaf icon, derived from PM2.5)."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SERVICE_AQI_STATUS
from .coordinator import QuboCoordinator
from .entity import QuboEntity

GOOD_PM25_THRESHOLD = 50.0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: QuboCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([QuboAirQualityGood(coordinator)])


class QuboAirQualityGood(QuboEntity, BinarySensorEntity):
    _attr_translation_key = "air_quality_good"
    _attr_name = "Air Quality Good"
    _attr_icon = "mdi:leaf"

    def __init__(self, coordinator: QuboCoordinator) -> None:
        super().__init__(coordinator, SERVICE_AQI_STATUS)
        self._attr_unique_id = f"{coordinator.device_uuid}_air_quality_good"

    @property
    def is_on(self) -> bool | None:
        raw = self.coordinator.current(SERVICE_AQI_STATUS, "PM25")
        if raw is None:
            return None
        try:
            return float(raw) < GOOD_PM25_THRESHOLD
        except (ValueError, TypeError):
            return None
