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

PLATFORMS: list[str] = ["fan", "sensor", "switch", "select", "button"]

REFRESH_INTERVAL_SECONDS = 300

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
SERVICE_SILENT_MODE = "silentModeControl"
SERVICE_DIMMER = "dimmerControlAPControl"
SERVICE_TIMER = "timerControlPurifier"
SERVICE_MCU_VERSION = "mcuSWVersionCurrent"
SERVICE_DEVICE_REBOOT = "deviceReboot"
SERVICE_AQI_REFRESH = "aqiRefresh"
