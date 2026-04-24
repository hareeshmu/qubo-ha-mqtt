#!/usr/bin/env python3
"""Watch /config/{unit_uuid} for refreshed JWT tokens from Qubo cloud.

When the cloud pushes a new token, this script catches it locally and
updates BOTH credential stores that use it:

  1. EMQX built-in auth DB  — so the device can keep connecting locally
  2. EMQX cloud-bridge connector password  — so the bridge can keep
     subscribing to /control and /config on the Qubo cloud

Both stores hold the same JWT but EMQX keeps them independent, so we
update each explicitly. Skipping #2 makes the mobile app silently stop
working ~30 days after the JWT last rotated.

Config via env vars or CLI args:
  BROKER_HOST       (default: 127.0.0.1)
  BROKER_PORT       (default: 1883)
  BROKER_USER       (default: mqtt)
  BROKER_PASS       (required)
  EMQX_URL          (default: http://127.0.0.1:18083)
  EMQX_USER         (default: admin)
  EMQX_PASS         (required)
  UNIT_UUID         (required — from your devices.yaml)
  MQTT_USERNAME     (required — the user_uuid that the device authenticates as)
  BRIDGE_CONNECTOR  (default: qubo_cloud — EMQX connector name for the bridge)

Run under systemd:
  [Service]
  Environment=BROKER_PASS=... EMQX_PASS=... UNIT_UUID=... MQTT_USERNAME=...
  ExecStart=/path/to/.venv/bin/python /path/to/refresh-jwt.py
  Restart=always
"""
import json
import os
import sys
import logging

import paho.mqtt.client as mqtt
import requests


log = logging.getLogger("refresh-jwt")
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")


def env(name: str, default: str | None = None) -> str:
    val = os.environ.get(name, default)
    if val is None:
        log.error(f"Missing required env var: {name}")
        sys.exit(1)
    return val


BROKER_HOST = env("BROKER_HOST", "127.0.0.1")
BROKER_PORT = int(env("BROKER_PORT", "1883"))
BROKER_USER = env("BROKER_USER", "mqtt")
BROKER_PASS = env("BROKER_PASS")
EMQX_URL = env("EMQX_URL", "http://127.0.0.1:18083").rstrip("/")
EMQX_USER = env("EMQX_USER", "admin")
EMQX_PASS = env("EMQX_PASS")
UNIT_UUID = env("UNIT_UUID")
MQTT_USERNAME = env("MQTT_USERNAME")
BRIDGE_CONNECTOR = env("BRIDGE_CONNECTOR", "qubo_cloud")


def emqx_login() -> str:
    r = requests.post(f"{EMQX_URL}/api/v5/login",
                      json={"username": EMQX_USER, "password": EMQX_PASS},
                      timeout=10)
    r.raise_for_status()
    return r.json()["token"]


def emqx_update_password(token: str, user_id: str, password: str) -> None:
    """Update the password for a user in the built-in auth DB.

    EMQX 5.x: PUT /api/v5/authentication/password_based:built_in_database/users/<user_id>
    """
    url = f"{EMQX_URL}/api/v5/authentication/password_based:built_in_database/users/{user_id}"
    r = requests.put(url,
                     headers={"Authorization": f"Bearer {token}"},
                     json={"password": password},
                     timeout=10)
    if r.status_code == 404:
        # user doesn't exist yet — create it
        r = requests.post(f"{EMQX_URL}/api/v5/authentication/password_based:built_in_database/users",
                          headers={"Authorization": f"Bearer {token}"},
                          json={"user_id": user_id, "password": password},
                          timeout=10)
    r.raise_for_status()


def emqx_update_bridge_password(token: str, connector: str, password: str) -> None:
    """Update the Password field on the cloud-bridge MQTT connector.

    GET the connector, preserve every field, replace `password`, PUT it back.
    Read-only fields returned by GET are stripped before PUT.
    """
    url = f"{EMQX_URL}/api/v5/connectors/mqtt:{connector}"
    headers = {"Authorization": f"Bearer {token}"}

    r = requests.get(url, headers=headers, timeout=10)
    r.raise_for_status()
    body = r.json()

    for ro in ("status", "node_status", "status_reason",
               "type", "name", "actions", "sources", "bridge_mode"):
        body.pop(ro, None)
    body["password"] = password

    r = requests.put(url, headers=headers, json=body, timeout=10)
    r.raise_for_status()


def extract_password(payload: dict) -> str | None:
    """Try several plausible paths where the new JWT might live in the payload."""
    candidates = [
        payload.get("password"),
        payload.get("jwt"),
        payload.get("token"),
    ]
    msg = payload.get("message")
    if isinstance(msg, list):
        for m in msg:
            if isinstance(m, dict):
                candidates.append(m.get("password"))
                candidates.append(m.get("jwt"))
                meta = m.get("metadata", {}) or {}
                candidates.append(meta.get("password"))
                candidates.append(meta.get("jwt"))
    for c in candidates:
        if isinstance(c, str) and c.count(".") == 2 and c.startswith("eyJ"):
            return c  # looks like a JWT
    return None


def on_message(client, userdata, msg):
    topic = msg.topic
    try:
        payload = json.loads(msg.payload.decode())
    except Exception:
        log.warning(f"{topic}: not JSON, ignoring")
        return
    log.info(f"{topic}: received ({len(msg.payload)} bytes)")
    new_pw = extract_password(payload)
    if not new_pw:
        log.debug(f"{topic}: no JWT-like password in payload; ignoring")
        return

    log.info(f"Found candidate JWT in {topic}: {new_pw[:20]}...{new_pw[-8:]}")
    try:
        token = emqx_login()
        emqx_update_password(token, MQTT_USERNAME, new_pw)
        log.info(f"Updated EMQX auth DB for user {MQTT_USERNAME}")
        emqx_update_bridge_password(token, BRIDGE_CONNECTOR, new_pw)
        log.info(f"Updated EMQX bridge connector {BRIDGE_CONNECTOR} password")
    except Exception as e:
        log.error(f"Failed to update EMQX: {e}")


def main() -> int:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="qubo-refresh-jwt")
    client.username_pw_set(BROKER_USER, BROKER_PASS)
    client.on_message = on_message
    client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
    topic = f"/config/{UNIT_UUID}"
    log.info(f"Subscribing to {topic}")
    client.subscribe(topic, qos=1)
    client.loop_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
