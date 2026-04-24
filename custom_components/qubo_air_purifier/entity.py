"""Base entity — wires dispatcher signals to entity state refresh."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import (
    CONF_MAC,
    CONF_MANUFACTURER,
    CONF_MODEL,
    CONF_NAME,
    DEFAULT_MANUFACTURER,
    DEFAULT_MODEL,
    DOMAIN,
)
from .coordinator import QuboCoordinator, signal_availability, signal_state


class QuboEntity(Entity):
    """Base class: subscribes to state & availability signals for one service."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, coordinator: QuboCoordinator, service: str) -> None:
        self.coordinator = coordinator
        self.service = service
        entry = coordinator.entry
        mac = entry.data[CONF_MAC]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"qubo_{mac.replace(':', '').lower()}")},
            name=entry.data[CONF_NAME],
            manufacturer=entry.data.get(CONF_MANUFACTURER, DEFAULT_MANUFACTURER),
            model=entry.data.get(CONF_MODEL, DEFAULT_MODEL),
            connections={("mac", mac.lower())},
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                signal_state(self.coordinator.entry.entry_id, self.service),
                self.async_write_ha_state,
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                signal_availability(self.coordinator.entry.entry_id),
                self.async_write_ha_state,
            )
        )

    @property
    def available(self) -> bool:
        return self.coordinator.available
