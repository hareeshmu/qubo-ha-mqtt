# 99 — Future work: Home Assistant add-on for broker + bridge

Status: **not built**. This is a scoping doc for a future effort to
package the broker + cloud-bridge + JWT-refresh stack as a one-click
HA add-on for HA OS / HA Supervised installs.

The **custom integration** (`custom_components/qubo_air_purifier/`)
is already built and works today on all HA install types. The add-on
described here would replace the *broker-side* setup (docs 02, 05,
and parts of 06), not the integration.

## Why this would be useful

Current setup asks users to install and configure EMQX separately and
walk through ~5 doc steps. A Qubo-branded HA add-on would reduce that
to: install add-on → enter UUIDs + MAC + JWT → done. For HA OS users
(majority of the HA install base) that's a massive UX win.

## What the add-on bundles

| Component | Role |
|-----------|------|
| EMQX (or Mosquitto) base image | Local MQTT broker |
| Auto-generated TLS cert | SAN = `mqtt.platform.quboworld.com`, generated on first boot |
| Bridge provisioner (init script) | POSTs connector + sources + republish rule to EMQX admin API |
| `refresh-jwt.py` sidecar | Watches `/config/{unit}` for rotated JWTs, updates both auth stores |
| Web UI (HA ingress) | Optional: view bridge metrics, trigger re-auth |

## Add-on options schema

```yaml
# config.yaml (HA add-on)
options:
  mac: "AA:BB:CC:DD:EE:FF"
  unit_uuid: "00000000-0000-0000-0000-000000000000"
  device_uuid: "00000000-0000-0000-0000-000000000000"
  entity_uuid: "00000000-0000-0000-0000-000000000000"
  user_uuid: "00000000-0000-0000-0000-000000000000"
  jwt: ""  # captured per docs/04 first time only
  enable_cloud_bridge: true
schema:
  mac: "match(^[0-9A-Fa-f:]{17}$)"
  unit_uuid: "match(^[0-9a-f-]{36}$)"
  device_uuid: "match(^[0-9a-f-]{36}$)"
  entity_uuid: "match(^[0-9a-f-]{36}$)"
  user_uuid: "match(^[0-9a-f-]{36}$)"
  jwt: "str"
  enable_cloud_bridge: "bool"
```

## Split of concerns (after add-on exists)

- **Add-on** — runs broker + bridge + JWT refresh. HA OS / Supervised.
- **Custom Integration** — talks to whichever broker HA's `mqtt`
  integration points at. Works against the add-on or any user-owned
  broker.
- **`publish.py` + docs 02–05** — preserved for Container/Core users
  or anyone who wants the manual path.

## Hard limits no add-on can fix

These stay user-owned infrastructure; docs must still cover them:

1. **DNS override** — device must resolve `mqtt.platform.quboworld.com`
   to the HA host's IP. Only possible at router / Pi-hole / pfSense /
   AdGuard. The add-on can print the IP and instructions but can't
   make the change.
2. **First-time JWT capture** — requires MITM of the device's HTTPS
   auth endpoint per `docs/04`. The add-on *could* ship an
   "authlog capture mode" that binds port 443 temporarily and walks
   the user through re-pointing the device, but the network
   redirection is outside HA's sandbox.
3. **Replacing existing brokers** — users already running
   Mosquitto/EMQX elsewhere would need migration or would skip the
   add-on. The integration doesn't care which broker.

## Critical gotchas the add-on's provisioner MUST encode

All discovered during live debugging on 2026-04-24 — they are
easy to get wrong:

1. **Bridge `static_clientids` MUST be `HPH_<MAC>`.** Any other value
   connects OK but receives zero messages from cloud. (See memory
   note + `docs/05-cloud-bridge.md` warning block.)
2. **Rotated JWTs must update BOTH stores.** The EMQX built-in auth DB
   (for device→local connect) and the bridge connector's Password field
   (for bridge→cloud connect) are separate. `refresh-jwt.py` already
   handles both as of 2026-04-24; the add-on must preserve this.
3. **`lcSwitchControl` payload shape** uses attributes, not commands.
   Already encoded in integration and `publish.py` but worth echoing
   if the add-on ever sends test commands during provisioning.

## Implementation sketch

```
addon-qubo-broker/
├── config.yaml          # HA add-on manifest
├── Dockerfile           # FROM emqx/emqx:5.x
├── rootfs/
│   └── etc/services.d/
│       ├── bridge-provision/run    # runs once on first boot
│       └── refresh-jwt/run          # long-running sidecar
├── provision.py         # POSTs to EMQX admin API
├── refresh-jwt.py       # symlink or copy from scripts/
├── gen-cert.sh          # symlink or copy from scripts/
└── README.md
```

First-boot flow (`provision.py`):

1. Wait for EMQX admin API to be reachable on localhost:18083.
2. Read add-on options from `/data/options.json`.
3. If cert doesn't exist, run `gen-cert.sh`.
4. Create built-in auth DB user (`user_uuid` + `jwt`).
5. Create connector with `static_clientids: HPH_<MAC>`.
6. Create sources (`qubo_control_in`, `qubo_config_in`).
7. Create action (`qubo_monitor_out`).
8. Create republish rule.
9. Write marker file so re-run is idempotent.
10. Exit.

## Effort estimate

- **v1 (functional, CLI options only):** ~1 day
- **v2 (cert gen + options schema + ingress page):** +1–2 days
- **Publishing to HA community add-on store:** extra review cycle
- **Ongoing maintenance:** bump EMQX base image every few months

## Decision criteria for when to build it

Build if any of:

- Project is published publicly and getting install friction reports.
- You're about to rebuild the broker host from scratch anyway — would
  be good dogfooding.
- Qubo adds a new device model and we want a smoother onboarding.

Skip if:

- You're still the only user.
- Current broker host is stable and JWT rotations are being handled
  by `refresh-jwt.py` without drama.
