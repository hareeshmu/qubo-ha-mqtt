"""Constants for the Qubo Air Purifier integration."""
from __future__ import annotations

DOMAIN = "qubo_air_purifier"

CONF_NAME = "name"
CONF_MAC = "mac"
CONF_UNIT_UUID = "unit_uuid"
CONF_DEVICE_UUID = "device_uuid"
CONF_ENTITY_UUID = "entity_uuid"
CONF_USER_UUID = "user_uuid"
CONF_MANUFACTURER = "manufacturer"
CONF_MODEL = "model"

DEFAULT_MANUFACTURER = "KPR"
DEFAULT_MODEL = "Qubo Smart Air Purifier R700"

PLATFORMS: list[str] = [
    "fan",
    "sensor",
    "binary_sensor",
    "switch",
    "select",
    "button",
]

# Adaptive polling: PM2.5 speeds up while air is changing, slows when stable.
PM25_POLL_FAST_SECONDS = 30
PM25_POLL_SLOW_SECONDS = 300
PM25_DELTA_FAST_THRESHOLD = 5.0  # µg/m³: |ΔPM2.5| ≥ this → fast
PM25_STABLE_POLLS_TO_SLOW = 3  # consecutive small-delta polls → slow

# Filter life and usage stats rarely change — poll on a fixed long interval.
FILTER_USAGE_POLL_SECONDS = 900

PRESET_AUTO = "auto"
PRESET_MANUAL = "manual"
PRESET_SLEEP = "sleep"
PRESET_QSENSE = "qsense"
PRESET_MODES = [PRESET_AUTO, PRESET_MANUAL, PRESET_SLEEP, PRESET_QSENSE]

SPEED_RANGE = (1, 3)

SERVICE_LC_SWITCH = "lcSwitchControl"
SERVICE_FAN_SPEED = "fanSpeedControl"
SERVICE_FAN_MODE = "fanControlMode"
SERVICE_AQI_STATUS = "aqiStatus"
SERVICE_FILTER_RESET = "filterReset"
SERVICE_PURIFIER_USAGE = "purifierUsage"
SERVICE_CHILD_LOCK = "childLockControl"
SERVICE_SILENT_MODE = "silentModeAP"
SERVICE_DIMMER = "dimmerControlAP"
SERVICE_TIMER = "timerControlPurifier"
SERVICE_MCU_VERSION = "mcuSWVersion"
SERVICE_DEVICE_REBOOT = "deviceReboot"
SERVICE_AQI_REFRESH = "aqiRefresh"
