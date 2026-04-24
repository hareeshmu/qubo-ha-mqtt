"""Config flow for Qubo Air Purifier."""
from __future__ import annotations

import re
from typing import Any
from uuid import UUID

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import TextSelector

from .const import (
    CONF_DEVICE_UUID,
    CONF_ENTITY_UUID,
    CONF_MAC,
    CONF_MANUFACTURER,
    CONF_MODEL,
    CONF_NAME,
    CONF_UNIT_UUID,
    CONF_USER_UUID,
    DEFAULT_MANUFACTURER,
    DEFAULT_MODEL,
    DOMAIN,
)

MAC_RE = re.compile(r"^[0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5}$")


def _is_uuid(value: str) -> bool:
    try:
        UUID(value)
    except (ValueError, AttributeError):
        return False
    return True


class QuboConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Qubo Air Purifier."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            for key in (
                CONF_UNIT_UUID,
                CONF_DEVICE_UUID,
                CONF_ENTITY_UUID,
                CONF_USER_UUID,
            ):
                if not _is_uuid(user_input[key]):
                    errors[key] = "invalid_uuid"
            if not MAC_RE.match(user_input[CONF_MAC]):
                errors[CONF_MAC] = "invalid_mac"

            if not errors:
                await self.async_set_unique_id(user_input[CONF_DEVICE_UUID])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default="Qubo Air Purifier"): TextSelector(),
                vol.Required(CONF_MAC): TextSelector(),
                vol.Required(CONF_UNIT_UUID): TextSelector(),
                vol.Required(CONF_DEVICE_UUID): TextSelector(),
                vol.Required(CONF_ENTITY_UUID): TextSelector(),
                vol.Required(CONF_USER_UUID): TextSelector(),
                vol.Optional(
                    CONF_MANUFACTURER, default=DEFAULT_MANUFACTURER
                ): TextSelector(),
                vol.Optional(CONF_MODEL, default=DEFAULT_MODEL): TextSelector(),
            }
        )
        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )
