"""Placeholder coordinator — replaced in step 3."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


class QuboCoordinator:
    """Stub; real implementation lands in step 3."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry

    async def async_start(self) -> None:
        return None

    async def async_stop(self) -> None:
        return None
