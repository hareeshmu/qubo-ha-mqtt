"""MQTT coordinator — single subscriber per device, topic routing, command publishing."""
from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later, async_track_time_interval

from .const import (
    CONF_DEVICE_UUID,
    CONF_ENTITY_UUID,
    CONF_UNIT_UUID,
    CONF_USER_UUID,
    DOMAIN,
    FILTER_USAGE_POLL_SECONDS,
    PM25_DELTA_FAST_THRESHOLD,
    PM25_POLL_FAST_SECONDS,
    PM25_POLL_SLOW_SECONDS,
    PM25_STABLE_POLLS_TO_SLOW,
    SERVICE_AQI_REFRESH,
    SERVICE_AQI_STATUS,
    SERVICE_FILTER_RESET,
    SERVICE_PURIFIER_USAGE,
)

_LOGGER = logging.getLogger(__name__)


def signal_state(entry_id: str, service: str) -> str:
    """Dispatcher signal: entity-specific, fires when `service` state changes."""
    return f"{DOMAIN}_{entry_id}_{service}"


def signal_availability(entry_id: str) -> str:
    return f"{DOMAIN}_{entry_id}_availability"


class QuboCoordinator:
    """Owns the MQTT subscription for one device and exposes publish helpers."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.unit = entry.data[CONF_UNIT_UUID]
        self.device_uuid = entry.data[CONF_DEVICE_UUID]
        self.entity_uuid = entry.data[CONF_ENTITY_UUID]
        self.user_uuid = entry.data[CONF_USER_UUID]
        self.mon_prefix = f"/monitor/{self.unit}/{self.device_uuid}"
        self.ctrl_prefix = f"/control/{self.unit}/{self.device_uuid}"
        self.state: dict[str, dict[str, Any]] = {}
        self.available = False
        self._unsub: Callable[[], None] | None = None
        self._unsub_pm25: Callable[[], None] | None = None
        self._unsub_slow: Callable[[], None] | None = None
        self._last_pm25: float | None = None
        self._stable_polls = 0
        self._pm25_interval = PM25_POLL_SLOW_SECONDS

    async def async_start(self) -> None:
        self._unsub = await mqtt.async_subscribe(
            self.hass, f"{self.mon_prefix}/#", self._on_message, qos=0
        )
        _LOGGER.debug("Subscribed to %s/#", self.mon_prefix)
        await self._poll_pm25()
        await self._poll_slow()
        self._schedule_pm25()
        self._unsub_slow = async_track_time_interval(
            self.hass,
            self._slow_tick,
            timedelta(seconds=FILTER_USAGE_POLL_SECONDS),
        )

    async def async_stop(self) -> None:
        if self._unsub is not None:
            self._unsub()
            self._unsub = None
        if self._unsub_pm25 is not None:
            self._unsub_pm25()
            self._unsub_pm25= None
        if self._unsub_slow is not None:
            self._unsub_slow()
            self._unsub_slow = None

    def _schedule_pm25(self) -> None:
        if self._unsub_pm25 is not None:
            self._unsub_pm25()
        self._unsub_pm25 = async_call_later(
            self.hass, self._pm25_interval, self._pm25_tick
        )

    async def _pm25_tick(self, _now: Any) -> None:
        self._unsub_pm25 = None
        await self._poll_pm25()
        self._schedule_pm25()

    async def _slow_tick(self, _now: Any) -> None:
        await self._poll_slow()

    async def _poll_pm25(self) -> None:
        await self.async_send_command(SERVICE_AQI_REFRESH, "refresh")

    async def _poll_slow(self) -> None:
        await self.async_send_command(SERVICE_FILTER_RESET, "getCurrentStatus")
        await self.async_send_command(SERVICE_PURIFIER_USAGE, "getPurifierUsage")

    @callback
    def _adjust_pm25_cadence(self, new_value: float) -> None:
        prev = self._last_pm25
        self._last_pm25 = new_value
        if prev is None:
            return
        delta = abs(new_value - prev)
        previous_interval = self._pm25_interval
        if delta >= PM25_DELTA_FAST_THRESHOLD:
            self._pm25_interval = PM25_POLL_FAST_SECONDS
            self._stable_polls = 0
        else:
            self._stable_polls += 1
            if self._stable_polls >= PM25_STABLE_POLLS_TO_SLOW:
                self._pm25_interval = PM25_POLL_SLOW_SECONDS
        if self._pm25_interval != previous_interval:
            _LOGGER.debug(
                "PM2.5 poll interval %ss → %ss (Δ=%.1f)",
                previous_interval,
                self._pm25_interval,
                delta,
            )
            # Reschedule immediately so the new cadence takes effect on the next tick.
            self._schedule_pm25()

    @callback
    def _on_message(self, msg: mqtt.ReceiveMessage) -> None:
        service = msg.topic.rsplit("/", 1)[-1]
        try:
            payload = json.loads(msg.payload)
        except (ValueError, TypeError):
            _LOGGER.debug("Non-JSON payload on %s", msg.topic)
            return

        changed = (
            payload.get("devices", {})
            .get("services", {})
            .get(service, {})
            .get("events", {})
            .get("stateChanged")
        )
        if changed is None:
            if service == "heartbeat":
                self._mark_available(True)
            return

        self.state[service] = changed
        self._mark_available(True)
        if service == SERVICE_AQI_STATUS:
            raw = changed.get("PM25")
            try:
                self._adjust_pm25_cadence(float(raw))
            except (TypeError, ValueError):
                pass
        async_dispatcher_send(self.hass, signal_state(self.entry.entry_id, service))

    @callback
    def _mark_available(self, available: bool) -> None:
        if available != self.available:
            self.available = available
            async_dispatcher_send(
                self.hass, signal_availability(self.entry.entry_id)
            )

    def _attr_payload(self, service: str, key: str, value: str) -> str:
        ts = int(time.time() * 1000)
        return json.dumps({
            "command": {
                "devices": {
                    "deviceUUID": self.device_uuid,
                    "handleName": self.user_uuid,
                    "services": {
                        service: {
                            "attributes": {key: value},
                            "instanceId": 0,
                        }
                    },
                }
            },
            "deviceUUID": self.device_uuid,
            "msgSequenceId": ts,
            "srcDeviceId": "home-assistant",
            "timestamp": ts,
        })

    def _cmd_payload(self, service: str, cmd: str) -> str:
        ts = int(time.time() * 1000)
        return json.dumps({
            "command": {
                "devices": {
                    "deviceUUID": self.device_uuid,
                    "handleName": self.user_uuid,
                    "services": {
                        service: {
                            "commands": {cmd: {"instanceId": 0, "parameters": {}}}
                        }
                    },
                }
            },
            "deviceUUID": self.device_uuid,
            "msgSequenceId": ts,
            "srcDeviceId": "home-assistant",
            "timestamp": ts,
        })

    async def async_set_attribute(
        self, service: str, key: str, value: str
    ) -> None:
        topic = f"{self.ctrl_prefix}/{service}"
        await mqtt.async_publish(
            self.hass, topic, self._attr_payload(service, key, value), qos=0
        )

    async def async_send_command(self, service: str, cmd: str) -> None:
        topic = f"{self.ctrl_prefix}/{service}"
        await mqtt.async_publish(
            self.hass, topic, self._cmd_payload(service, cmd), qos=0
        )

    def power_state(self) -> str | None:
        return self.state.get("lcSwitchControl", {}).get("power")

    def current(self, service: str, key: str) -> Any | None:
        return self.state.get(service, {}).get(key)
