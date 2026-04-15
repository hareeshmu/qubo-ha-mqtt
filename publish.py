#!/usr/bin/env python3
"""Publish Home Assistant MQTT Discovery configs for Qubo devices.

Reads devices.yaml, publishes retained HA Discovery messages so HA auto-creates
entities wired directly to the device's /control/... and /monitor/... topics.
"""
import argparse
import json
import sys
from pathlib import Path

import paho.mqtt.client as mqtt
import yaml

CONFIG_PATH = Path(__file__).parent / "devices.yaml"


def cmd_payload_jinja(service: str, attrs_key: str, attrs_value_expr: str, device_uuid: str, user_uuid: str) -> str:
    """Build a Jinja command_template that produces a Qubo control payload.

    attrs_value_expr is Jinja (e.g. "{{ value }}" or literal "on").
    """
    return (
        "{"
        f'"command":{{'
        f'"devices":{{'
        f'"deviceUUID":"{device_uuid}",'
        f'"handleName":"{user_uuid}",'
        f'"services":{{"{service}":{{'
        f'"attributes":{{"{attrs_key}":"{attrs_value_expr}"}},'
        f'"instanceId":0'
        "}}"
        "}},"
        f'"deviceUUID":"{device_uuid}",'
        '"msgSequenceId":{{ (now().timestamp() * 1000) | int }},'
        '"srcDeviceId":"home-assistant",'
        '"timestamp":{{ (now().timestamp() * 1000) | int }}'
        "}"
    )


def cmd_payload_command(service: str, cmd: str, device_uuid: str, user_uuid: str) -> str:
    """Qubo 'commands' style payload (e.g. aqiRefresh/refresh, filterReset/getCurrentStatus, deviceReboot/reboot)."""
    return (
        "{"
        f'"command":{{"devices":{{'
        f'"deviceUUID":"{device_uuid}",'
        f'"handleName":"{user_uuid}",'
        f'"services":{{"{service}":{{'
        f'"commands":{{"{cmd}":{{"instanceId":0,"parameters":{{}}}}}}'
        "}}"
        "}},"
        f'"deviceUUID":"{device_uuid}",'
        '"msgSequenceId":{{ (now().timestamp() * 1000) | int }},'
        '"srcDeviceId":"home-assistant",'
        '"timestamp":{{ (now().timestamp() * 1000) | int }}'
        "}"
    )


def build_entities(dev: dict) -> list[tuple[str, str, dict]]:
    """Return list of (component, object_id, config_dict) for HA Discovery.

    Topic: <discovery_prefix>/<component>/<object_id>/config
    """
    slug = dev["slug"]
    unit = dev["unit_uuid"]
    device_uuid = dev["device_uuid"]
    user_uuid = dev["user_uuid"]
    mac = dev["mac"]
    ctrl = f"/control/{unit}/{device_uuid}"
    mon = f"/monitor/{unit}/{device_uuid}"

    device_block = {
        "identifiers": [f"qubo_{mac.replace(':', '').lower()}"],
        "name": dev["name"],
        "manufacturer": dev.get("manufacturer", "Qubo"),
        "model": dev.get("model", "Air Purifier"),
        "connections": [["mac", mac.lower()]],
    }

    # Availability: left empty so entities stay always-available. The heartbeat topic
    # is not retained, and adding a strict availability block caused entities to show
    # as offline immediately after HA restart until the next heartbeat arrived.
    avail: list = []

    entities: list[tuple[str, str, dict]] = []

    # --- Sensor: Current Mode (readable mirror of fanControlMode) ---
    entities.append((
        "sensor",
        f"{slug}_current_mode",
        {
            "name": "Current Mode",
            "unique_id": f"{slug}_current_mode",
            "object_id": f"{slug}_current_mode",
            "state_topic": f"{mon}/fanControlMode",
            "value_template": (
                "{% set s = value_json.devices.services.fanControlMode.events.stateChanged.state %}"
                "{% set labels = {'auto':'Auto','manual':'Manual','sleep':'Sleep','qsense':'QSensAI'} %}"
                "{{ labels[s] | default(s) }}"
            ),
            "icon": "mdi:fan",
            "device": device_block,
        },
    ))

    # --- Select: Mode dropdown (mirrors fan preset_mode) ---
    entities.append((
        "select",
        f"{slug}_mode",
        {
            "name": "Mode",
            "unique_id": f"{slug}_mode",
            "object_id": f"{slug}_mode",
            "state_topic": f"{mon}/fanControlMode",
            "value_template": (
                "{% set s = value_json.devices.services.fanControlMode.events.stateChanged.state %}"
                "{% set labels = {'auto':'Auto','manual':'Manual','sleep':'Sleep','qsense':'QSensAI'} %}"
                "{{ labels[s] | default(s) }}"
            ),
            "command_topic": f"{ctrl}/fanControlMode",
            "command_template": cmd_payload_jinja(
                "fanControlMode",
                "state",
                "{% set m = {'Auto':'auto','Manual':'manual','Sleep':'sleep','QSensAI':'qsense'} %}{{ m[value] | default(value | lower) }}",
                device_uuid,
                user_uuid,
            ),
            "options": ["Auto", "Manual", "Sleep", "QSensAI"],
            "icon": "mdi:fan",
            "device": device_block,
        },
    ))

    # --- Fan: combines power / speed / preset ---
    fan_cfg = {
        "name": None,  # use device name
        "unique_id": f"{slug}_fan",
        "object_id": f"{slug}_fan",
        "icon": "mdi:power",
        "state_topic": f"{mon}/lcSwitchControl",
        "state_value_template": "{{ value_json.devices.services.lcSwitchControl.events.stateChanged.power | upper }}",
        "payload_on": "ON",
        "payload_off": "OFF",
        "command_topic": f"{ctrl}/lcSwitchControl",
        "command_template": cmd_payload_jinja(
            "lcSwitchControl", "power", "{{ value | lower }}", device_uuid, user_uuid
        ),
        # Speed 1-3 -> percentage
        "percentage_state_topic": f"{mon}/fanSpeedControl",
        "percentage_value_template": "{{ value_json.devices.services.fanSpeedControl.events.stateChanged.speed | int }}",
        "percentage_command_topic": f"{ctrl}/fanSpeedControl",
        "percentage_command_template": cmd_payload_jinja(
            "fanSpeedControl", "speed", "{{ value }}", device_uuid, user_uuid
        ),
        "speed_range_min": 1,
        "speed_range_max": 3,
        # Preset modes
        "preset_mode_state_topic": f"{mon}/fanControlMode",
        "preset_mode_value_template": "{{ value_json.devices.services.fanControlMode.events.stateChanged.state }}",
        "preset_mode_command_topic": f"{ctrl}/fanControlMode",
        "preset_mode_command_template": cmd_payload_jinja(
            "fanControlMode", "state", "{{ value }}", device_uuid, user_uuid
        ),
        "preset_modes": ["auto", "manual", "sleep", "qsense"],
        "availability": avail,
        "device": device_block,
    }
    entities.append(("fan", slug, fan_cfg))

    # --- Sensor: PM2.5 ---
    entities.append((
        "sensor",
        f"{slug}_pm25",
        {
            "name": "PM2.5",
            "unique_id": f"{slug}_pm25",
            "object_id": f"{slug}_pm25",
            "state_topic": f"{mon}/aqiStatus",
            "value_template": "{{ value_json.devices.services.aqiStatus.events.stateChanged.PM25 }}",
            "device_class": "pm25",
            "state_class": "measurement",
            "unit_of_measurement": "µg/m³",
            "availability": avail,
            "device": device_block,
        },
    ))

    # --- Sensor: Filter life hours remaining ---
    entities.append((
        "sensor",
        f"{slug}_filter_life",
        {
            "name": "Filter Life Remaining",
            "unique_id": f"{slug}_filter_life",
            "object_id": f"{slug}_filter_life",
            "state_topic": f"{mon}/filterReset",
            "value_template": "{{ value_json.devices.services.filterReset.events.stateChanged.timeRemaining }}",
            "state_class": "measurement",
            "unit_of_measurement": "h",
            "icon": "mdi:air-filter",
            "availability": avail,
            "device": device_block,
        },
    ))

    # --- Switch: Child Lock ---
    entities.append((
        "switch",
        f"{slug}_child_lock",
        {
            "name": "Child Lock",
            "unique_id": f"{slug}_child_lock",
            "object_id": f"{slug}_child_lock",
            "state_topic": f"{mon}/childLockControl",
            "value_template": "{{ value_json.devices.services.childLockControl.events.stateChanged.state }}",
            "state_on": "enable",
            "state_off": "disable",
            "command_topic": f"{ctrl}/childLockControl",
            "payload_on": "ON",
            "payload_off": "OFF",
            "command_template": cmd_payload_jinja(
                "childLockControl",
                "state",
                "{{ 'enable' if value == 'ON' else 'disable' }}",
                device_uuid,
                user_uuid,
            ),
            "icon": "mdi:lock",
            "availability": avail,
            "device": device_block,
        },
    ))

    # --- Switch: Silent Mode ---
    entities.append((
        "switch",
        f"{slug}_silent_mode",
        {
            "name": "Silent Mode",
            "unique_id": f"{slug}_silent_mode",
            "object_id": f"{slug}_silent_mode",
            "state_topic": f"{mon}/silentModeAP",
            "value_template": "{{ value_json.devices.services.silentModeAP.events.stateChanged.state }}",
            "state_on": "enable",
            "state_off": "disable",
            "command_topic": f"{ctrl}/silentModeAP",
            "payload_on": "ON",
            "payload_off": "OFF",
            "command_template": cmd_payload_jinja(
                "silentModeAP",
                "state",
                "{{ 'enable' if value == 'ON' else 'disable' }}",
                device_uuid,
                user_uuid,
            ),
            "icon": "mdi:volume-off",
            "availability": avail,
            "device": device_block,
        },
    ))

    # --- Select: Dimmer (LED brightness) ---
    entities.append((
        "select",
        f"{slug}_dimmer",
        {
            "name": "Display Dimmer",
            "unique_id": f"{slug}_dimmer",
            "object_id": f"{slug}_dimmer",
            "state_topic": f"{mon}/dimmerControlAP",
            "value_template": "{{ value_json.devices.services.dimmerControlAP.events.stateChanged.state }}",
            "command_topic": f"{ctrl}/dimmerControlAP",
            "command_template": cmd_payload_jinja(
                "dimmerControlAP", "state", "{{ value }}", device_uuid, user_uuid
            ),
            "options": ["off", "low", "mid", "high"],
            "icon": "mdi:brightness-6",
            "availability": avail,
            "device": device_block,
        },
    ))

    # --- Select: Auto-off Timer ---
    entities.append((
        "select",
        f"{slug}_timer",
        {
            "name": "Auto-off Timer",
            "unique_id": f"{slug}_timer",
            "object_id": f"{slug}_timer",
            "state_topic": f"{mon}/timerControlPurifier",
            "value_template": (
                "{% set v = value_json.devices.services.timerControlPurifier.events.stateChanged.value %}"
                "{% if v is defined %}{{ v }}{% else %}skip{% endif %}"
            ),
            "command_topic": f"{ctrl}/timerControlPurifier",
            "command_template": cmd_payload_jinja(
                "timerControlPurifier", "value", "{{ value }}", device_uuid, user_uuid
            ),
            "options": ["0", "1", "2", "4", "8"],
            "icon": "mdi:timer",
            "availability": avail,
            "device": device_block,
        },
    ))

    # --- Button: Refresh AQI ---
    entities.append((
        "button",
        f"{slug}_refresh_aqi",
        {
            "name": "Refresh AQI",
            "unique_id": f"{slug}_refresh_aqi",
            "object_id": f"{slug}_refresh_aqi",
            "command_topic": f"{ctrl}/aqiRefresh",
            "payload_press": cmd_payload_command("aqiRefresh", "refresh", device_uuid, user_uuid),
            "icon": "mdi:refresh",
            "availability": avail,
            "device": device_block,
        },
    ))

    # --- Button: Refresh Filter Status ---
    entities.append((
        "button",
        f"{slug}_refresh_filter",
        {
            "name": "Refresh Filter Status",
            "unique_id": f"{slug}_refresh_filter",
            "object_id": f"{slug}_refresh_filter",
            "command_topic": f"{ctrl}/filterReset",
            "payload_press": cmd_payload_command(
                "filterReset", "getCurrentStatus", device_uuid, user_uuid
            ),
            "icon": "mdi:air-filter",
            "entity_category": "diagnostic",
            "availability": avail,
            "device": device_block,
        },
    ))

    # --- Button: Reboot ---
    entities.append((
        "button",
        f"{slug}_reboot",
        {
            "name": "Reboot",
            "unique_id": f"{slug}_reboot",
            "object_id": f"{slug}_reboot",
            "command_topic": f"{ctrl}/deviceReboot",
            "payload_press": cmd_payload_command("deviceReboot", "reboot", device_uuid, user_uuid),
            "icon": "mdi:restart",
            "entity_category": "diagnostic",
            "availability": avail,
            "device": device_block,
        },
    ))

    # --- Sensor: MCU SW Version (diagnostic) ---
    entities.append((
        "sensor",
        f"{slug}_mcu_version",
        {
            "name": "MCU Version",
            "unique_id": f"{slug}_mcu_version",
            "object_id": f"{slug}_mcu_version",
            "state_topic": f"{mon}/mcuSWVersion",
            "value_template": "{{ value_json.devices.services.mcuSWVersion.events.stateChanged.version | default('unknown') }}",
            "entity_category": "diagnostic",
            "icon": "mdi:chip",
            "device": device_block,
        },
    ))

    # --- purifierUsage daily stats (min/max/avg PM2.5, total usages) ---
    for key, label, dc, unit in [
        ("minPM25", "Today Min PM2.5", "pm25", "µg/m³"),
        ("maxPM25", "Today Max PM2.5", "pm25", "µg/m³"),
        ("avgPM25", "Today Avg PM2.5", "pm25", "µg/m³"),
        ("totalUsages", "Total Usage Minutes", None, "min"),
    ]:
        cfg = {
            "name": label,
            "unique_id": f"{slug}_usage_{key.lower()}",
            "object_id": f"{slug}_usage_{key.lower()}",
            "state_topic": f"{mon}/purifierUsage",
            "value_template": (
                "{{ value_json.devices.services.purifierUsage.events.stateChanged." + key + " }}"
            ),
            "state_class": "measurement",
            "unit_of_measurement": unit,
            "device": device_block,
        }
        if dc:
            cfg["device_class"] = dc
        entities.append(("sensor", f"{slug}_usage_{key.lower()}", cfg))

    # --- Button: Refresh Usage Stats ---
    entities.append((
        "button",
        f"{slug}_refresh_usage",
        {
            "name": "Refresh Usage Stats",
            "unique_id": f"{slug}_refresh_usage",
            "object_id": f"{slug}_refresh_usage",
            "command_topic": f"{ctrl}/purifierUsage",
            "payload_press": cmd_payload_command(
                "purifierUsage", "getPurifierUsage", device_uuid, user_uuid
            ),
            "icon": "mdi:chart-line",
            "entity_category": "diagnostic",
            "availability": avail,
            "device": device_block,
        },
    ))

    return entities


def send_refresh_queries(client: mqtt.Client, dev: dict) -> int:
    """Ask the device to publish current state on topics where a getter exists.

    The device answers each request by publishing the current state on the
    matching /monitor topic, which HA then picks up. Without this, HA can show
    'Unknown' until the user interacts with each control.
    """
    unit = dev["unit_uuid"]
    device_uuid = dev["device_uuid"]
    user_uuid = dev["user_uuid"]
    ctrl = f"/control/{unit}/{device_uuid}"
    ts = int(__import__("time").time() * 1000)

    def refresh(service: str, command: str) -> dict:
        return {
            "command": {
                "devices": {
                    "deviceUUID": device_uuid,
                    "handleName": user_uuid,
                    "services": {service: {"commands": {command: {"instanceId": 0, "parameters": {}}}}},
                }
            },
            "deviceUUID": device_uuid,
            "msgSequenceId": ts,
            "srcDeviceId": "home-assistant",
            "timestamp": ts,
        }

    queries = [
        ("aqiRefresh", "refresh"),
        ("filterReset", "getCurrentStatus"),
        ("purifierUsage", "getPurifierUsage"),
    ]
    count = 0
    for service, command in queries:
        topic = f"{ctrl}/{service}"
        payload = json.dumps(refresh(service, command), separators=(",", ":"))
        print(f"REFRESH {topic} ({service}/{command})")
        client.publish(topic, payload=payload, qos=0).wait_for_publish(3)
        count += 1
    return count


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(CONFIG_PATH))
    parser.add_argument("--dry-run", action="store_true", help="Print configs, don't publish")
    parser.add_argument("--unpublish", action="store_true", help="Publish empty retained payloads to remove entities")
    parser.add_argument("--refresh", action="store_true", help="After publishing, ping the device to emit current state on all refreshable topics")
    parser.add_argument("--refresh-only", action="store_true", help="Skip discovery publish; only send refresh queries")
    args = parser.parse_args()

    with open(args.config) as f:
        cfg = yaml.safe_load(f)

    prefix = cfg.get("ha_discovery_prefix", "homeassistant")
    broker = cfg["mqtt"]

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="qubo-ha-publisher")
    client.username_pw_set(broker["username"], broker["password"])

    if not args.dry_run:
        client.connect(broker["host"], broker.get("port", 1883), keepalive=30)
        client.loop_start()

    total = 0
    if not args.refresh_only:
        for dev in cfg["devices"]:
            for component, obj_id, conf in build_entities(dev):
                topic = f"{prefix}/{component}/{obj_id}/config"
                payload = "" if args.unpublish else json.dumps(conf, separators=(",", ":"))
                print(f"{'REMOVE' if args.unpublish else 'PUBLISH'} {topic} ({len(payload)} B)")
                if args.dry_run:
                    if not args.unpublish:
                        print(payload[:200] + ("..." if len(payload) > 200 else ""))
                else:
                    client.publish(topic, payload=payload, qos=1, retain=True).wait_for_publish(5)
                total += 1

    refreshed = 0
    if (args.refresh or args.refresh_only) and not args.dry_run and not args.unpublish:
        for dev in cfg["devices"]:
            refreshed += send_refresh_queries(client, dev)

    if not args.dry_run:
        client.loop_stop()
        client.disconnect()
    print(f"Done. {total} discovery configs {'would be' if args.dry_run else ''} published, {refreshed} refresh queries sent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
