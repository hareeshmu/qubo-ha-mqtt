# 8. Troubleshooting

## Device doesn't connect to local broker

1. **Verify DNS override is reaching the purifier**:
   ```bash
   dig @<purifier's DNS> mqtt.platform.quboworld.com +short
   # Should return your broker IP, not the cloud IP
   ```
2. If the DNS is wrong — the purifier is using a different DNS than you set.
   Check DHCP lease; some routers give out their own IP regardless of static
   mapping. Use Wireshark on the broker host to see what destination the
   purifier is reaching:
   ```bash
   sudo tcpdump -i any "host <purifier-ip> and port 8883"
   ```
3. Power-cycle the purifier after any DNS change — devices cache DNS for
   minutes to hours.

## Device connects but auth fails

Broker log shows `authentication_failure`:

- Your broker doesn't have the JWT password for the device's user. Revisit
  [doc 4](04-capture-jwt.md) and ensure the JWT is in the built-in DB (or
  Mosquitto passwd).
- **JWT expired** (30-day lifetime). Re-capture via HTTP auth logger.
- **Temporary workaround**: set
  `EMQX_LISTENERS__SSL__DEFAULT__ENABLE_AUTHN=false` — the :8883 listener
  accepts any creds (only the LAN can reach this port).

## Device connects but disconnects constantly

- TLS cert has wrong SAN — must include `DNS:mqtt.platform.quboworld.com`.
  Recheck with:
  ```bash
  openssl x509 -in server.crt -noout -ext subjectAltName
  ```
- Firewall is closing idle connections. Lower keepalive or check firewall
  logs.

## HA shows entity but state is "unknown"

- The device only publishes to `/monitor` **on state change**. After HA
  restart, it subscribes with no history.
- Run `python publish.py --refresh-only` to force the device to publish
  current state on refreshable topics.
- For topics with no getter (lcSwitchControl, fanControlMode, etc.), toggle
  once in the Qubo app or HA to trigger a state update.

## HA's fan `percentage` shows `null`

This almost always means the MQTT fan `percentage_value_template` has a bug.
With `speed_range_min: 1`, `speed_range_max: 3`, the template **must return
a step value (1/2/3), not a percentage**.

Our `publish.py` is already correct. If you customized it and broke it:

```yaml
"percentage_value_template":
  "{{ value_json.devices.services.fanSpeedControl.events.stateChanged.speed | int }}"
```

Then republish and **restart HA** — HA caches MQTT discovery configs and
won't re-apply unless the config changes OR HA restarts.

## HA doesn't pick up updated discovery config

After editing `publish.py` and re-running:

1. `python publish.py --unpublish` (removes configs entirely)
2. `python publish.py --refresh` (re-adds)
3. In HA: Settings → Devices & Services → MQTT → 3-dots → **Reload** (or
   restart HA)

## Mobile app says "device offline"

- You don't have the bridge set up. Either set up [doc 5](05-cloud-bridge.md)
  or accept HA-only control.
- If the bridge IS up, check:
  - Connector status in EMQX dashboard → Integration → Connectors →
    qubo_cloud → should say `connected`
  - JWT hasn't expired (check `exp` claim)
  - Real cloud IP in `extra_hosts` is still valid

## Bridge disconnected / unauthorized

- Cloud pushed a new JWT and your bridge has the old one. Run
  `scripts/refresh-jwt.py` (or re-capture via doc 4 and update EMQX user).

## "Bad Request: client disconnect" in EMQX logs

Usually the device dropping connection during TLS handshake — cert mismatch
or firewall interference. Recheck cert SAN; check if there's a layer-7
firewall (Zscaler, pfSense snort) interfering.

## Speed pills in Lovelace don't activate

- HA `fan.<slug>_fan` entity's `percentage` attribute is empty/wrong.
  Developer Tools → States → check. Should be 33 / 66 / 100 for speed 1/2/3.
- If `percentage` is null, see "HA's fan percentage shows null" above.
- If `percentage` looks right but pills still grey, hard-refresh the HA page
  (Cmd+Shift+R / Ctrl+Shift+R) so the browser reloads card-mod templates.

## HA dashboard card shows "Custom element doesn't exist: X"

- HACS card not loaded. Settings → Dashboards → **Resources** → check each
  `/hacsfiles/...js` resource is listed.
- Hard-refresh browser (browser caches old resources).
- Restart HA if you just installed.

## Halo animation stutters

- Performance: disable animations if running on low-power hardware. Remove
  the `animation:` lines from `.qubo-halo` and `.qubo-particle`.
- Browser: Safari sometimes stutters on conic-gradient + blur; try
  Chrome/Edge.

## Device JWT expired

You'll see in EMQX logs: `authentication_failure: not_authorized` and the
device reconnecting in a loop.

**Fix:**
1. Re-capture JWT via doc 4 steps 4.3–4.4.
2. Update the user's password in EMQX built-in DB (or Mosquitto passwd).
3. Update the **bridge connector's password** in EMQX (Integration →
   Connector → qubo_cloud → Edit → set new password).
4. If you use `scripts/refresh-jwt.py`, this should auto-happen going
   forward.

## Getting help

If stuck, open an issue with:

- Your broker choice (EMQX / Mosquitto) + version
- DNS setup (pfSense / AdGuard / Pi-hole / etc.)
- Output of:
  ```bash
  openssl s_client -connect <broker>:8883 -servername mqtt.platform.quboworld.com </dev/null 2>&1 | head -15
  ```
- Last 50 lines of broker log showing the device connection attempt

Never share your JWT — it authenticates you to Qubo cloud as your device.
