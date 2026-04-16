# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

Home Assistant integration for **Qubo (Hero Electronix) air purifier R700**
implemented as an **MQTT Discovery publisher** — not a traditional HA custom
component. It works around Qubo's cloud-only design by exploiting the device's
permissive TLS hostname validation: a self-signed cert with SAN
`mqtt.platform.quboworld.com` is accepted by the purifier when DNS is
overridden to point at a local broker.

Users get local HA control while the Qubo mobile app keeps working via an
optional MQTT bridge that replays traffic between the local broker and
Qubo's real cloud (AWS ap-south-1).

## How it works (big picture, not obvious from any single file)

Three topic spaces on the local broker:

- `/monitor/{unit_uuid}/{device_uuid}/*` — state published by the purifier
  (heartbeat, aqiStatus, fanSpeedControl state, filterReset, etc.)
- `/control/{unit_uuid}/{device_uuid}/*` — commands sent TO the purifier
  (lcSwitchControl, fanControlMode, aqiRefresh, deviceReboot, etc.)
- `/config/{unit_uuid}` — Qubo cloud pushes JWT refresh tokens here

All payloads are nested JSON with a fixed shape — see the `cmd_payload_jinja`
and `cmd_payload_command` helpers in `publish.py` for the exact structure.
HA Discovery value_templates extract state from
`value_json.devices.services.<service>.events.stateChanged.<key>`.

The JWT the device uses as its MQTT password is captured once via the
HTTP-auth logger in `scripts/authlog.py`, then stored in the broker's
auth DB. That JWT expires every ~30 days — if the cloud bridge is running,
it forwards refreshed tokens via `/config/{unit_uuid}` and
`scripts/refresh-jwt.py` auto-updates the broker's auth record.

## Critical: MQTT fan speed_range semantics

HA's MQTT fan platform with `speed_range_min: 1, speed_range_max: 3` expects
`percentage_value_template` to return the **raw step value (1/2/3)**, NOT a
percentage. HA then converts step→percentage internally using its own
(slightly unusual) formula that produces 33, 66, 100. If the template returns
a percentage directly, HA stores `percentage: null` and the whole control
stops working. This cost hours to debug. See `publish.py` line ~152 and
`docs/08-troubleshooting.md` "HA's fan percentage shows null".

## Common commands

```bash
# Setup
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Publish HA Discovery configs + refresh device state
python publish.py --refresh

# Just re-query device state (e.g. daily cron)
python publish.py --refresh-only

# Preview without publishing
python publish.py --dry-run

# Remove all entities from HA
python publish.py --unpublish

# Generate TLS cert with correct SAN for a new broker host
./scripts/gen-certs.sh /path/to/cert-dir <broker-ip>

# Capture a fresh JWT (runs until killed; point EMQX HTTP authenticator at it)
python3 scripts/authlog.py
```

There is **no test suite**. Verification is manual:

1. `python publish.py --dry-run` — ensures YAML loads and discovery shape is
   valid
2. After publish, check HA Settings → Devices & Services → MQTT → device
   appears with ~18 entities
3. Toggle fan/preset/speed in HA → purifier should respond physically

## Adding a new Qubo device type (smart plug, doorbell, etc.)

Currently only `device_type: air_purifier` is implemented in
`build_entities()`. To add another type:

1. Capture the new device's `/control` and `/monitor` topic suffixes by
   subscribing to `/#` on the broker and clicking through every button in
   the Qubo app — record the JSON payload shape for each
2. Extend `build_entities()` with a branch on `dev["device_type"]`
3. Each entity type in HA MQTT Discovery requires matching command/state
   topic + templates — mirror the air purifier's patterns

## Secrets and what's gitignored

`devices.yaml` contains the device's real UUIDs (privacy-sensitive) and is
gitignored. `devices.yaml.example` is the template. The device's JWT is
NEVER in any file — it lives only in the MQTT broker's auth DB.

When editing files, never hardcode a real UUID, JWT, MAC, or password. Use
`CHANGE_ME` / `<your-...>` / `00000000-...` placeholders.

## Editing Lovelace cards in `lovelace/`

`lovelace/cards/main-unified-dashboard.yaml` is the flagship unified card
(halo + mode buttons + conditional speed pills). It depends on **5 HACS
frontend cards**: `button-card`, `mushroom`, `mini-graph-card`,
`stack-in-card`, `card-mod`. Changes must be pasted into HA's dashboard
raw YAML editor to test — there's no live-reload from the filesystem.

The halo's ring color responds to PM2.5 thresholds (`< 50` Good → `≤ 100`
Moderate → `< 200` Poor → `≥ 200` Very Poor). Adjusting these means
synchronized edits to both the `ringRgb` ladder AND the `label` /
`labelColor` ladder in the `button-card custom_fields.ring` JS template.

## User's documented preferences (global CLAUDE.md context)

- Uses `pnpm` in other projects (not relevant here, but mentioned for
  broader context)
- Strict on typesafety and linting — fix at dev time, not after
- Next.js 16 projects use `proxy.ts` (not relevant here)
- Always run `pnpm build` after core functionality changes (not applicable
  to this Python-only repo)
- Responses should be **extremely concise, sacrificing grammar for
  concision** when reporting back
