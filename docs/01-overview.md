# 1. Overview & Prerequisites

## What you'll build

```
     Qubo app  ───►  Real Qubo cloud  ◄──bridge──  Your local MQTT broker  ◄──►  Your Home Assistant
                                                            ▲
                                                            │ DNS override
                                                            │
                                                      Qubo Purifier
```

Your purifier will think your local broker IS the real cloud. HA talks to
the local broker directly. Your mobile app keeps talking to the real cloud.
A bridge keeps them in sync so commands work from either side.

## Hardware prerequisites

- **Qubo device** — R700 Smart Air Purifier (HPH07) is tested. Other Qubo
  devices (smart plug, doorbell) use the same protocol and should work after
  capturing their UUIDs.
- **Always-on Linux box** for the MQTT broker — Raspberry Pi, NAS, VPS, or
  any Docker-capable host. Must have:
  - A fixed/reserved IP on your LAN
  - Ports 1883 (plain MQTT for HA) and 8883 (TLS MQTT for Qubo) reachable
- **Home Assistant** 2024.1+ with the MQTT integration configured (any
  install: HAOS, Container, Supervised, Core).
- **A way to override DNS on your network** — one of:
  - A router with per-device DNS or DHCP DNS options (pfSense, OPNsense,
    MikroTik, UniFi, OpenWrt, Asus/Netgear with custom firmware)
  - AdGuard Home, Pi-hole, or similar DNS resolver where you assign specific
    clients to specific upstreams
  - Basic routers without per-device DNS **won't work** — you'd need
    split-horizon DNS at a different layer

## Skill prerequisites

You will:
1. Generate a self-signed TLS certificate with a specific SAN entry
2. Configure an MQTT broker's TLS listener
3. Set up DNS overrides that apply **only to the purifier** (other devices
   must still resolve the real cloud — otherwise the mobile app breaks)
4. One-time capture of the device's MQTT JWT credential using a
   reverse-proxy technique (MITM yourself for 30 seconds)
5. Edit a YAML config and run a small Python script
6. (Optional) Configure an MQTT-to-MQTT bridge inside EMQX

If any of this sounds unfamiliar, read the step docs thoroughly and be
prepared for ~2 hours of focused work.

## What you need to discover yourself

The following are **different for every device / user** — you cannot copy
these from anyone else:

| Item | How you get it |
|------|----------------|
| `unit_uuid` | From device's first MQTT CONNECT + heartbeat (see doc 4) |
| `device_uuid` | Same heartbeat payload |
| `entity_uuid` | Same heartbeat payload |
| `user_uuid` | MQTT username the device sends on connect |
| `mac` | On device label, or ARP scan for `94:51:DC:*` |
| Device JWT password | Captured via one-time MITM (see doc 4) |

The setup guides show exactly how to extract each.

## Time & complexity budget

| Step | Time | Difficulty |
|------|------|------------|
| 02 MQTT broker TLS | 15–30 min | Medium |
| 03 Split DNS | 10–30 min (varies) | Medium |
| 04 Capture JWT | 10–20 min | Hard (one-time) |
| 05 Cloud bridge (optional) | 20–30 min | Medium |
| 06 HA integration | 10 min | Easy |
| 07 Lovelace dashboard | 10 min | Easy |

## What if you skip the cloud bridge?

- ✅ HA fully controls the device locally
- ✅ Works forever (tokens don't matter for local control)
- ❌ **Mobile app cannot reach the device** — cloud can't push commands to
  your locally-redirected purifier
- ❌ Device JWT expires in 30 days — you must re-capture to keep HA
  authenticated (because EMQX's built-in auth DB uses the JWT). Actually if
  you set EMQX listener to `enable_authn=false` on port 8883 you skip this,
  but then your broker accepts any creds on 8883 — acceptable inside LAN.

The bridge is **recommended** but the setup works without it for HA-only use.

## Next step

[→ 02 MQTT broker TLS setup](02-mqtt-broker-setup.md)
