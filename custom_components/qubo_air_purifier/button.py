"""Buttons: refresh AQI, refresh filter, refresh usage, reboot."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    SERVICE_AQI_REFRESH,
    SERVICE_DEVICE_REBOOT,
    SERVICE_FILTER_RESET,
    SERVICE_PURIFIER_USAGE,
)
from .coordinator import QuboCoordinator
from .entity import QuboEntity


@dataclass(frozen=True, kw_only=True)
class QuboButtonDescription(ButtonEntityDescription):
    service: str
    command: str


BUTTONS: tuple[QuboButtonDescription, ...] = (
    QuboButtonDescription(
        key="refresh_aqi",
        translation_key="refresh_aqi",
        name="Refresh AQI",
        icon="mdi:refresh",
        entity_category=EntityCategory.DIAGNOSTIC,
        service=SERVICE_AQI_REFRESH,
        command="refresh",
    ),
    QuboButtonDescription(
        key="refresh_filter",
        translation_key="refresh_filter",
        name="Refresh Filter Status",
        icon="mdi:air-filter",
        entity_category=EntityCategory.DIAGNOSTIC,
        service=SERVICE_FILTER_RESET,
        command="getCurrentStatus",
    ),
    QuboButtonDescription(
        key="refresh_usage",
        translation_key="refresh_usage",
        name="Refresh Usage Stats",
        icon="mdi:chart-line",
        entity_category=EntityCategory.DIAGNOSTIC,
        service=SERVICE_PURIFIER_USAGE,
        command="getPurifierUsage",
    ),
    QuboButtonDescription(
        key="reboot",
        translation_key="reboot",
        name="Reboot",
        icon="mdi:restart",
        entity_category=EntityCategory.CONFIG,
        service=SERVICE_DEVICE_REBOOT,
        command="reboot",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: QuboCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(QuboButton(coordinator, d) for d in BUTTONS)


class QuboButton(QuboEntity, ButtonEntity):
    entity_description: QuboButtonDescription

    def __init__(
        self, coordinator: QuboCoordinator, description: QuboButtonDescription
    ) -> None:
        super().__init__(coordinator, description.service)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.device_uuid}_{description.key}"

    async def async_press(self) -> None:
        await self.coordinator.async_send_command(
            self.entity_description.service, self.entity_description.command
        )
