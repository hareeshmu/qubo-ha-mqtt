"""Selects: display dimmer, auto-off timer."""
from __future__ import annotations

from dataclasses import dataclass, field

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SERVICE_DIMMER, SERVICE_TIMER
from .coordinator import QuboCoordinator
from .entity import QuboEntity


@dataclass(frozen=True, kw_only=True)
class QuboSelectDescription(SelectEntityDescription):
    service: str
    attr_key: str
    options_list: list[str] = field(default_factory=list)


SELECTS: tuple[QuboSelectDescription, ...] = (
    QuboSelectDescription(
        key="dimmer",
        translation_key="dimmer",
        name="Display Dimmer",
        icon="mdi:brightness-6",
        service=SERVICE_DIMMER,
        attr_key="state",
        options=["off", "low", "mid", "high"],
        options_list=["off", "low", "mid", "high"],
    ),
    QuboSelectDescription(
        key="timer",
        translation_key="timer",
        name="Auto-off Timer",
        icon="mdi:timer",
        service=SERVICE_TIMER,
        attr_key="value",
        options=["0", "1", "2", "4", "8"],
        options_list=["0", "1", "2", "4", "8"],
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: QuboCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(QuboSelect(coordinator, d) for d in SELECTS)


class QuboSelect(QuboEntity, SelectEntity):
    entity_description: QuboSelectDescription

    def __init__(
        self, coordinator: QuboCoordinator, description: QuboSelectDescription
    ) -> None:
        super().__init__(coordinator, description.service)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.device_uuid}_{description.key}"

    @property
    def current_option(self) -> str | None:
        raw = self.coordinator.current(
            self.entity_description.service, self.entity_description.attr_key
        )
        if raw is None:
            return None
        value = str(raw)
        return value if value in self.entity_description.options_list else None

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_set_attribute(
            self.entity_description.service,
            self.entity_description.attr_key,
            option,
        )
