"""Fan entity — power, speed (1-3), preset modes. Auto-powers-on for preset/speed."""
from __future__ import annotations

from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from .const import (
    DOMAIN,
    PRESET_MODES,
    SERVICE_FAN_MODE,
    SERVICE_FAN_SPEED,
    SERVICE_LC_SWITCH,
    SPEED_RANGE,
)
from .coordinator import QuboCoordinator, signal_state
from .entity import QuboEntity
from homeassistant.helpers.dispatcher import async_dispatcher_connect


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: QuboCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([QuboFan(coordinator)])


class QuboFan(QuboEntity, FanEntity):
    _attr_name = None  # use device name
    _attr_translation_key = "fan"
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.PRESET_MODE
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )
    _attr_preset_modes = PRESET_MODES
    _attr_speed_count = SPEED_RANGE[1] - SPEED_RANGE[0] + 1

    def __init__(self, coordinator: QuboCoordinator) -> None:
        super().__init__(coordinator, SERVICE_LC_SWITCH)
        self._attr_unique_id = f"{coordinator.device_uuid}_fan"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        # Also react to speed + preset updates
        for svc in (SERVICE_FAN_SPEED, SERVICE_FAN_MODE):
            self.async_on_remove(
                async_dispatcher_connect(
                    self.hass,
                    signal_state(self.coordinator.entry.entry_id, svc),
                    self.async_write_ha_state,
                )
            )

    @property
    def is_on(self) -> bool | None:
        power = self.coordinator.power_state()
        if power is None:
            return None
        return power.lower() == "on"

    @property
    def percentage(self) -> int | None:
        if not self.is_on:
            return 0
        raw = self.coordinator.current(SERVICE_FAN_SPEED, "speed")
        if raw is None:
            return None
        try:
            step = int(raw)
        except (ValueError, TypeError):
            return None
        return ranged_value_to_percentage(SPEED_RANGE, step)

    @property
    def preset_mode(self) -> str | None:
        if not self.is_on:
            return None
        return self.coordinator.current(SERVICE_FAN_MODE, "state")

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        await self.coordinator.async_set_attribute(SERVICE_LC_SWITCH, "power", "on")
        if preset_mode is not None:
            await self.coordinator.async_set_attribute(
                SERVICE_FAN_MODE, "state", preset_mode
            )
        if percentage is not None:
            step = int(percentage_to_ranged_value(SPEED_RANGE, percentage))
            await self.coordinator.async_set_attribute(
                SERVICE_FAN_SPEED, "speed", str(step)
            )

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_attribute(SERVICE_LC_SWITCH, "power", "off")

    async def async_set_percentage(self, percentage: int) -> None:
        if percentage == 0:
            await self.async_turn_off()
            return
        if not self.is_on:
            await self.coordinator.async_set_attribute(SERVICE_LC_SWITCH, "power", "on")
        step = int(percentage_to_ranged_value(SPEED_RANGE, percentage))
        await self.coordinator.async_set_attribute(
            SERVICE_FAN_SPEED, "speed", str(step)
        )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        if not self.is_on:
            await self.coordinator.async_set_attribute(SERVICE_LC_SWITCH, "power", "on")
        await self.coordinator.async_set_attribute(
            SERVICE_FAN_MODE, "state", preset_mode
        )
