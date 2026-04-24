"""Sensors: PM2.5, filter life, usage stats, MCU version."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONCENTRATION_MICROGRAMS_PER_CUBIC_METER, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    SERVICE_AQI_STATUS,
    SERVICE_FILTER_RESET,
    SERVICE_MCU_VERSION,
    SERVICE_PURIFIER_USAGE,
)
from .coordinator import QuboCoordinator
from .entity import QuboEntity


@dataclass(frozen=True, kw_only=True)
class QuboSensorDescription(SensorEntityDescription):
    service: str
    extractor: Callable[[dict[str, Any]], Any]


def _get(key: str) -> Callable[[dict[str, Any]], Any]:
    return lambda changed: changed.get(key)


SENSORS: tuple[QuboSensorDescription, ...] = (
    QuboSensorDescription(
        key="pm25",
        translation_key="pm25",
        name="PM2.5",
        service=SERVICE_AQI_STATUS,
        extractor=_get("PM25"),
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
    QuboSensorDescription(
        key="filter_life",
        translation_key="filter_life",
        name="Filter Life Remaining",
        service=SERVICE_FILTER_RESET,
        extractor=_get("value"),
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    QuboSensorDescription(
        key="mcu_version",
        translation_key="mcu_version",
        name="MCU Version",
        service=SERVICE_MCU_VERSION,
        extractor=_get("value"),
    ),
    QuboSensorDescription(
        key="usage_min_pm25",
        translation_key="usage_min_pm25",
        name="Today Min PM2.5",
        service=SERVICE_PURIFIER_USAGE,
        extractor=_get("minPm25"),
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
    QuboSensorDescription(
        key="usage_max_pm25",
        translation_key="usage_max_pm25",
        name="Today Max PM2.5",
        service=SERVICE_PURIFIER_USAGE,
        extractor=_get("maxPm25"),
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
    QuboSensorDescription(
        key="usage_avg_pm25",
        translation_key="usage_avg_pm25",
        name="Today Avg PM2.5",
        service=SERVICE_PURIFIER_USAGE,
        extractor=_get("avgPm25"),
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
    QuboSensorDescription(
        key="usage_total_minutes",
        translation_key="usage_total_minutes",
        name="Total Usage Minutes",
        service=SERVICE_PURIFIER_USAGE,
        extractor=_get("totalUsages"),
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: QuboCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(QuboSensor(coordinator, desc) for desc in SENSORS)


class QuboSensor(QuboEntity, SensorEntity):
    entity_description: QuboSensorDescription

    def __init__(
        self, coordinator: QuboCoordinator, description: QuboSensorDescription
    ) -> None:
        super().__init__(coordinator, description.service)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.device_uuid}_{description.key}"

    @property
    def native_value(self) -> Any | None:
        changed = self.coordinator.state.get(self.entity_description.service)
        if not changed:
            return None
        value = self.entity_description.extractor(changed)
        if value is None:
            return None
        if self.entity_description.device_class == SensorDeviceClass.PM25:
            try:
                return float(value)
            except (ValueError, TypeError):
                return None
        if self.entity_description.state_class in (
            SensorStateClass.MEASUREMENT,
            SensorStateClass.TOTAL_INCREASING,
        ):
            try:
                return float(value)
            except (ValueError, TypeError):
                return value
        return value
