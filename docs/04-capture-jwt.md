# 4. Capture Device JWT + UUIDs

The purifier connects to your broker using a **username** (user_uuid) and
**password** (a JWT issued by Qubo cloud). You need to capture both so you
can:

1. Add them to your broker's auth DB (so it authenticates)
2. Use them later for the cloud bridge (doc 5)

You'll also harvest the **device UUIDs** from the first heartbeat message.

---

## Step 4.1 — Accept any credentials temporarily

Simplest approach: **disable authentication** on the TLS listener briefly so
the device connects, publishes its heartbeat, and we capture everything.

### EMQX

```bash
docker exec -e EMQX_LISTENERS__SSL__DEFAULT__ENABLE_AUTHN=false \
  emqx emqx ctl conf reload
```

Or set the env var in `docker-compose.yml`:

```yaml
environment:
  - EMQX_LISTENERS__SSL__DEFAULT__ENABLE_AUTHN=false
```

`docker compose up -d`.

### Mosquitto

Our config in doc 2 already has `allow_anonymous true` on :8883. Done.

## Step 4.2 — Capture heartbeat for UUIDs

Power-cycle the purifier. In another terminal, subscribe to heartbeat:

```bash
mosquitto_sub -h <broker-ip> -p 1883 -u mqtt -P '<ha-password>' \
  -t '/monitor/+/+/heartbeat' -v -C 1
```

You'll see one heartbeat message:

```
/monitor/<unit_uuid>/<device_uuid>/heartbeat  {"devices": {
  "deviceUUID":"<device_uuid>",
  "entityUUID":"<entity_uuid>",
  "unitUUID":"<unit_uuid>",
  "userUUID":"<user_uuid>",
  "srcDeviceId":"HPH_XX:XX:XX:XX:XX:XX",
  ...
}}
```

**Record the 4 UUIDs and the MAC.** You'll put these in `devices.yaml`.

Note: `userUUID` in the heartbeat payload is sometimes the same as
`deviceUUID`. The **MQTT username** (a different value) is what we need for
auth. Get it from the broker's client list:

```bash
# EMQX
curl -s "http://localhost:18083/api/v5/clients?limit=100" \
  -H "Authorization: Bearer $TOKEN" | \
  jq '.data[] | select(.clientid | contains("HPH")) | {clientid, username, ip}'
```

The `username` field is the **true `user_uuid`** (and what the device uses
as MQTT username). Record it.

---

## Step 4.3 — Capture the JWT password

This is trickier. EMQX/Mosquitto don't log the password by default. Use a
small HTTP authenticator that logs and always returns "allow".

### Step 4.3.1 — Start an HTTP auth logger on the broker host

Save to `authlog.py`:

```python
from http.server import BaseHTTPRequestHandler, HTTPServer
import json, datetime

class H(BaseHTTPRequestHandler):
    def log_message(self, *a, **k): pass
    def do_POST(self):
        ln = int(self.headers.get('Content-Length','0') or '0')
        body = self.rfile.read(ln)
        try:
            d = json.loads(body.decode())
        except:
            d = {'raw': body.decode(errors='replace')}
        ts = datetime.datetime.now().isoformat(timespec='seconds')
        entry = {'ts': ts, 'data': d}
        with open('auth.log','a') as f:
            f.write(json.dumps(entry)+'\n')
        print(json.dumps(entry), flush=True)
        self.send_response(200)
        self.send_header('Content-Type','application/json')
        self.end_headers()
        self.wfile.write(b'{"result":"allow"}')

HTTPServer(('0.0.0.0', 8090), H).serve_forever()
```

Run it:

```bash
python3 authlog.py &
```

It listens on port 8090 and logs any auth attempt.

### Step 4.3.2 — Point EMQX at this logger

If EMQX is in Docker, find the gateway IP for the container (so it can reach
your host):

```bash
docker inspect emqx --format '{{range .NetworkSettings.Networks}}{{.Gateway}}{{end}}'
# e.g. 172.21.0.1
```

Via EMQX dashboard → **Authentication** → **Create** → **HTTP / password
based**:

- Method: POST
- URL: `http://172.21.0.1:8090/mqtt/auth`
- Body: `{"username":"${username}","password":"${password}","clientid":"${clientid}"}`
- Headers: `Content-Type: application/json`
- Enable: ✓

Move this authenticator **before** the built-in DB so it runs first.

### Step 4.3.3 — Re-enable authN on :8883

If you disabled it in step 4.1, re-enable:

```bash
# Remove the ENABLE_AUTHN=false env var from docker-compose.yml, then
docker compose up -d
```

### Step 4.3.4 — Power-cycle the device

On reconnect, EMQX calls your HTTP logger with the real creds:

```bash
tail -f auth.log
# Look for username: <user_uuid>, password: eyJhbGciOiJIUzI1NiJ9... (JWT)
```

**Copy the full JWT password.** It starts with `eyJ...` and has two dots
(three base64 parts).

### Step 4.3.5 — Decode JWT (optional, for understanding)

```bash
python3 -c "import base64,sys,json; p=sys.argv[1].split('.')[1]; p+='='*(-len(p)%4); print(json.dumps(json.loads(base64.urlsafe_b64decode(p)),indent=2))" '<your-jwt>'
```

Example:
```json
{
  "sub": "DEVICE",
  "unit": "<unit_uuid>",
  "iss": "<provider-id>",
  "exp": 1778770941,    ← Unix epoch; converts to ~30 days from issue
  "device": "<device-uuid>",
  "iat": 1776178941
}
```

Note the `exp` value — this JWT expires ~30 days from its `iat`. You'll want
the bridge (doc 5) to forward the cloud's refreshed JWTs automatically.

---

## Step 4.4 — Add device to broker's built-in auth DB

So you don't need the HTTP logger running forever.

### EMQX

Dashboard → **Authentication → password_based:built_in_database → Users →
Add**

- User ID type: `username`
- User ID: `<user_uuid>` (from step 4.2)
- Password: `<JWT>` (from step 4.3)

Or via API:
```bash
curl -X POST "http://localhost:18083/api/v5/authentication/password_based:built_in_database/users" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d "{\"user_id\":\"<user_uuid>\",\"password\":\"<JWT>\"}"
```

Then **disable the HTTP authenticator** (or delete it) so only built-in DB
runs. Stop `authlog.py` — `kill %1`.

### Mosquitto

```bash
sudo mosquitto_passwd -b /etc/mosquitto/passwd "<user_uuid>" "<JWT>"
sudo systemctl restart mosquitto
```

---

## Step 4.5 — Verify device still connects

Power-cycle the purifier again. Within 15 s:

```bash
curl -s "http://localhost:18083/api/v5/clients?limit=100" \
  -H "Authorization: Bearer $TOKEN" | jq '.data[] | select(.clientid | contains("HPH"))'
```

Should show the device connected on `ssl:default`.

---

## Step 4.6 — Record everything for `devices.yaml`

You should now have:

```
unit_uuid:   <uuid>
device_uuid: <uuid>
entity_uuid: <uuid>
user_uuid:   <uuid>  (MQTT username — may or may not equal device_uuid)
mac:         XX:XX:XX:XX:XX:XX
jwt:         eyJhbGciOiJIUzI1NiJ9....
```

Keep the JWT **secret** — it authenticates you as the device to Qubo cloud.

## Next step

- If you want the Qubo mobile app to keep working: [→ 05 Cloud bridge](05-cloud-bridge.md)
- If you're fine with HA-only local control: skip to [→ 06 HA integration](06-ha-integration.md)
