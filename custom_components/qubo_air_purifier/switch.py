"""Switches: child lock, silent mode."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SERVICE_CHILD_LOCK, SERVICE_SILENT_MODE
from .coordinator import QuboCoordinator
from .entity import QuboEntity


@dataclass(frozen=True, kw_only=True)
class QuboSwitchDescription(SwitchEntityDescription):
    service: str
    attr_key: str
    value_on: str
    value_off: str


SWITCHES: tuple[QuboSwitchDescription, ...] = (
    QuboSwitchDescription(
        key="child_lock",
        translation_key="child_lock",
        name="Child Lock",
        icon="mdi:lock",
        service=SERVICE_CHILD_LOCK,
        attr_key="state",
        value_on="enable",
        value_off="disable",
    ),
    QuboSwitchDescription(
        key="silent_mode",
        translation_key="silent_mode",
        name="Silent Mode",
        icon="mdi:volume-off",
        service=SERVICE_SILENT_MODE,
        attr_key="state",
        value_on="enable",
        value_off="disable",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: QuboCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(QuboSwitch(coordinator, d) for d in SWITCHES)


class QuboSwitch(QuboEntity, SwitchEntity):
    entity_description: QuboSwitchDescription

    def __init__(
        self, coordinator: QuboCoordinator, description: QuboSwitchDescription
    ) -> None:
        super().__init__(coordinator, description.service)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.device_uuid}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        raw = self.coordinator.current(
            self.entity_description.service, self.entity_description.attr_key
        )
        if raw is None:
            return None
        return str(raw).lower() == self.entity_description.value_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_attribute(
            self.entity_description.service,
            self.entity_description.attr_key,
            self.entity_description.value_on,
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_attribute(
            self.entity_description.service,
            self.entity_description.attr_key,
            self.entity_description.value_off,
        )
