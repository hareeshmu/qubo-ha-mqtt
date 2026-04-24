# 5. Cloud Bridge (Optional)

Without a bridge:
- ✅ HA controls the device locally, forever
- ❌ The Qubo mobile app shows "device offline" and can't control it
- ❌ When the device's JWT expires (~30 days), you must re-capture manually

With a bridge:
- ✅ HA controls the device locally
- ✅ Mobile app keeps working (commands from the app route: app → real cloud
  → bridge → local broker → device)
- ✅ Cloud pushes refreshed JWTs to `/config/{unit_uuid}` automatically —
  your bridge forwards these; the device picks up the new token; you don't
  have to re-capture

**Setup: ~30 min.** EMQX required (Mosquitto bridge supports MQTT→MQTT but
lacks HA-friendly rule engine).

---

## Step 5.1 — Let EMQX resolve the real cloud inside the container

Your host's DNS resolves `mqtt.platform.quboworld.com` to your **local
broker** (doc 3). But inside the EMQX container we need it to resolve to the
**real cloud** — otherwise the bridge connects to itself (loop).

Add `extra_hosts` to your `docker-compose.yml`:

```yaml
services:
  emqx:
    # ... existing config ...
    extra_hosts:
      - "mqtt.platform.quboworld.com:65.1.150.122"   # ← real cloud IP
```

Replace `65.1.150.122` with the IP you saw in doc 3 step 3.1.

Recreate:

```bash
docker compose up -d
docker exec emqx getent hosts mqtt.platform.quboworld.com
# 65.1.150.122    mqtt.platform.quboworld.com
```

---

## Step 5.2 — Create MQTT connector to the cloud

Via EMQX API (or dashboard → **Integration → Connector → Create → MQTT**):

```bash
TOKEN=$(curl -s -X POST http://localhost:18083/api/v5/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"<admin-pw>"}' | jq -r .token)

JWT='<your-device-JWT-from-doc-4>'
USER='<your-user_uuid-from-doc-4>'
MAC='<your-device-MAC-uppercase-e.g.-AA:BB:CC:DD:EE:FF>'

curl -s -X POST "http://localhost:18083/api/v5/connectors" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d "{
    \"type\": \"mqtt\",
    \"name\": \"qubo_cloud\",
    \"enable\": true,
    \"server\": \"mqtt.platform.quboworld.com:8883\",
    \"clean_start\": true,
    \"keepalive\": \"60s\",
    \"username\": \"${USER}\",
    \"password\": \"${JWT}\",
    \"proto_ver\": \"v4\",
    \"ssl\": {
      \"enable\": true,
      \"verify\": \"verify_none\",
      \"server_name_indication\": \"mqtt.platform.quboworld.com\"
    },
    \"pool_size\": 1,
    \"static_clientids\": [{\"node\": \"emqx@node1.emqx.local\",
                            \"ids\": [\"HPH_${MAC}\"]}]
  }" | jq .status
# "connected"
```

> ⚠️ **The `static_clientids` value matters — don't randomize it.**
>
> Qubo cloud routes `/control/<unit>/<device>/...` publishes **only to the
> clientId that matches the device** (`HPH_<MAC>`). Any other value — e.g.
> EMQX's default `EMQX_BRIDGE_<ts>` — gets a successful TLS + CONNACK
> (EMQX shows `connected`) but **zero inbound messages** from cloud.
> Outbound `/monitor` still flows, so the symptom is "mobile app sees
> status but its buttons do nothing, and `/config` JWT refreshes never
> arrive." Since the real device now connects to your local broker,
> its cloud clientId slot is free — the bridge impersonates it.

Check status — `connected` = auth succeeded with the cloud.

If it says `disconnected` / `unauthorized`, your JWT is bad or expired.
Re-capture (doc 4).

---

## Step 5.3 — Source: pull commands from cloud into local

The cloud publishes `/control/{unit}/...` and `/config/{unit}` toward the
device (bridge). We subscribe to these on the cloud and push locally.

```bash
UNIT='<your-unit_uuid>'

# /control/+/+/# — commands from the mobile app
curl -s -X POST "http://localhost:18083/api/v5/sources" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d "{
    \"type\": \"mqtt\",
    \"name\": \"qubo_control_in\",
    \"enable\": true,
    \"connector\": \"qubo_cloud\",
    \"parameters\": {\"topic\": \"/control/${UNIT}/+/#\", \"qos\": 0}
  }" | jq .status

# /config/{unit} — includes refreshed JWTs
curl -s -X POST "http://localhost:18083/api/v5/sources" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d "{
    \"type\": \"mqtt\",
    \"name\": \"qubo_config_in\",
    \"enable\": true,
    \"connector\": \"qubo_cloud\",
    \"parameters\": {\"topic\": \"/config/${UNIT}\", \"qos\": 1}
  }" | jq .status
```

Both should return `"connected"`.

---

## Step 5.4 — Action: publish local state to cloud

The device publishes `/monitor/{unit}/...` locally. Forward to cloud so the
app sees state updates.

```bash
curl -s -X POST "http://localhost:18083/api/v5/actions" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d "{
    \"type\": \"mqtt\",
    \"name\": \"qubo_monitor_out\",
    \"enable\": true,
    \"connector\": \"qubo_cloud\",
    \"parameters\": {
      \"topic\": \"\${topic}\",
      \"payload\": \"\${payload}\",
      \"qos\": 0,
      \"retain\": false
    }
  }" | jq .status
```

---

## Step 5.5 — Rules: wire sources & actions to real topics

### Rule A: republish ingress to local topic

Sources deliver messages to virtual `$bridges/mqtt:<name>` topics. A rule
forwards to the real local topic so the device (subscribed to `/control/...`
locally) receives them:

```bash
curl -s -X POST "http://localhost:18083/api/v5/rules" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{
    "id": "qubo_control_republish",
    "enable": true,
    "sql": "SELECT * FROM \"$bridges/mqtt:qubo_control_in\", \"$bridges/mqtt:qubo_config_in\"",
    "actions": [{"function":"republish","args":{"topic":"${topic}","payload":"${payload}","qos":"${qos}","retain":"${retain}"}}]
  }' | jq .enable
```

### Rule B: local monitor → cloud action

```bash
curl -s -X POST "http://localhost:18083/api/v5/rules" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d "{
    \"id\": \"qubo_monitor_fwd\",
    \"enable\": true,
    \"sql\": \"SELECT * FROM '/monitor/${UNIT}/+/+'\",
    \"actions\": [\"mqtt:qubo_monitor_out\"]
  }" | jq .enable
```

---

## Step 5.6 — Verify round-trip

1. Open the **Qubo app** on your phone. Does the device appear online?
   - If yes, the egress path works (local state is reaching the cloud).
2. In the app, **toggle a mode** (Auto → Manual). Does the purifier respond
   physically?
   - If yes, the ingress path works (cloud is reaching device via bridge).

Also watch local broker in a terminal:

```bash
mosquitto_sub -h localhost -p 1883 -u mqtt -P '<pw>' \
  -t "/control/<unit>/#" -t "/monitor/<unit>/#" -v
```

You should see both `/monitor` (from device) and `/control` (republished
from cloud) flowing.

---

## Step 5.7 — JWT auto-refresh

As the device approaches JWT expiry, Qubo cloud pushes a new token via
`/config/{unit_uuid}`. Your bridge forwards that locally → device picks it
up → device reconnects with new JWT.

But your broker's built-in auth DB still has the **old** JWT. Next reconnect
fails.

**Solution: auto-update EMQX's built-in DB when a new JWT comes in.**

Add a rule that listens to `/config/` and calls EMQX's API to update the
user's password. Or use a small helper script:

See [`scripts/refresh-jwt.py`](../scripts/refresh-jwt.py) — runs as an
MQTT client subscribed to `/config/{unit}`, extracts the new `password`
field, and updates EMQX via its API.

Run under systemd or cron.

---

## Loop-safety check

- Bridge subscribes only to `/control/+/+/#` and `/config/+` on cloud → not
  `/monitor`, so our own monitor messages don't loop back.
- Bridge publishes to `/monitor/...` on cloud → cloud doesn't echo those
  back to us since we're only subscribed to `/control` and `/config`.

No loops.

## Next step

[→ 06 HA integration install](06-ha-integration.md)
