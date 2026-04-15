# 6. Home Assistant Integration

Now publish the HA MQTT Discovery configs so HA auto-creates 18 entities for
your purifier.

---

## Step 6.1 — Install dependencies

Anywhere you have Python 3.10+ (the broker host is a good place):

```bash
git clone <this-repo>
cd qubo-ha-mqtt

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## Step 6.2 — Edit `devices.yaml`

Copy the sample and fill in **your device's** values from doc 4:

```yaml
mqtt:
  host: 10.10.10.10           # your broker IP
  port: 1883
  username: mqtt              # HA's MQTT user
  password: 'YourPassword'

ha_discovery_prefix: homeassistant

devices:
  - name: Qubo Air Purifier
    slug: qubo_r700            # used in entity_id prefixes
    manufacturer: Qubo         # displayed in HA device card
    model: Smart Air Purifier R700
    device_type: air_purifier
    mac: 94:51:DC:XX:XX:XX     # your MAC
    unit_uuid:   <your-unit-uuid>
    device_uuid: <your-device-uuid>
    entity_uuid: <your-entity-uuid>
    user_uuid:   <your-user-uuid>
```

Multiple devices: repeat the `- name: ...` block.

---

## Step 6.3 — Publish

```bash
python publish.py --refresh
```

Output:

```
PUBLISH homeassistant/fan/qubo_r700/config (3140 B)
PUBLISH homeassistant/sensor/qubo_r700_current_mode/config ...
...
PUBLISH homeassistant/button/qubo_r700_refresh_usage/config ...
REFRESH /control/<unit>/<device>/aqiRefresh (aqiRefresh/refresh)
REFRESH /control/<unit>/<device>/filterReset (filterReset/getCurrentStatus)
REFRESH /control/<unit>/<device>/purifierUsage (purifierUsage/getPurifierUsage)
Done. 18 discovery configs published, 3 refresh queries sent.
```

Discovery configs are **retained** on the broker — HA keeps them across
restarts.

---

## Step 6.4 — Verify in HA

Settings → Devices & Services → MQTT → **Devices** → you should see the
purifier with its full entity list:

- `fan.<slug>_fan` — main control
- `sensor.<slug>_pm25`
- `sensor.<slug>_filter_life`
- `sensor.<slug>_current_mode`
- `sensor.<slug>_usage_minpm25` / `maxpm25` / `avgpm25` / `totalusages`
- `sensor.<slug>_mcu_version`
- `switch.<slug>_child_lock`
- `switch.<slug>_silent_mode`
- `select.<slug>_mode`
- `select.<slug>_timer`
- `select.<slug>_dimmer`
- `button.<slug>_refresh_aqi` / `refresh_filter` / `refresh_usage` / `reboot`

---

## Step 6.5 — Test controls

- Toggle the fan entity (`fan.<slug>_fan`) off/on — purifier should respond.
- Change speed (`fan.<slug>_fan` → expand → set speed) — purifier should change.
- Change preset (`fan.<slug>_fan` → preset_mode) — purifier should change.

If nothing happens:
- Check broker: is the device connected? (`clients` API in doc 3.4)
- Check HA logs: Settings → System → Logs → search `mqtt`
- Check retained discovery: `mosquitto_sub -h <broker> -t 'homeassistant/fan/<slug>/config' -C 1`

---

## Step 6.6 — Auto-refresh (optional)

Periodic `--refresh-only` keeps HA populated if entities ever go "unknown"
(e.g., after HA restart, if the MQTT broker had no retained /monitor topics).

Cron on the broker host:

```cron
0 * * * * cd /path/to/qubo-ha-mqtt && .venv/bin/python publish.py --refresh-only >/dev/null 2>&1
```

Or add to your HA `configuration.yaml` as a shell_command + automation:

```yaml
shell_command:
  qubo_refresh: "/path/to/qubo-ha-mqtt/.venv/bin/python /path/to/publish.py --refresh-only"

automation:
  - alias: Qubo state refresh hourly
    trigger:
      - platform: time_pattern
        hours: "/1"
    action:
      - service: shell_command.qubo_refresh
```

---

## Step 6.7 — Updating entity config later

Edit `devices.yaml` (or `publish.py` for deeper changes) → re-run
`python publish.py`. HA auto-updates entities.

To remove all entities: `python publish.py --unpublish`.

## Next step

[→ 07 Lovelace dashboard](07-lovelace-dashboard.md)
