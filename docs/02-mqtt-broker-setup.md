# 2. MQTT Broker TLS Setup

Your local MQTT broker needs:

- **Plain MQTT listener on :1883** (so Home Assistant talks without TLS)
- **TLS MQTT listener on :8883** with a **self-signed cert whose SAN contains
  `mqtt.platform.quboworld.com`** (so the Qubo device accepts the connection)
- **No client-cert requirement** (device doesn't present one)

Choose one broker. **EMQX** is recommended (runs headless, has API, bridges
built-in). **Mosquitto** is lighter but requires manual config for bridges.

---

## Option A — EMQX (recommended)

### A.1. Run EMQX via Docker Compose

Create `docker-compose.yml` on your always-on host:

```yaml
services:
  emqx:
    image: emqx:5.8.6
    restart: unless-stopped
    container_name: emqx
    environment:
      - TZ=Asia/Kolkata   # your timezone
      - EMQX_NODE__DATA_DIR=/data/emqx/data
      - EMQX_NODE__ETC_DIR=/data/emqx/etc
      - EMQX_PLUGINS__INSTALL_DIR=/data/emqx/plugins
      - EMQX_LOG_DIR=/config/log
      # Qubo TLS listener config
      - EMQX_LISTENERS__SSL__DEFAULT__SSL_OPTIONS__CERTFILE=/data/emqx/data/certs/quboworld/server.crt
      - EMQX_LISTENERS__SSL__DEFAULT__SSL_OPTIONS__KEYFILE=/data/emqx/data/certs/quboworld/server.key
      - EMQX_LISTENERS__SSL__DEFAULT__SSL_OPTIONS__CACERTFILE=/data/emqx/data/certs/quboworld/ca.crt
      - EMQX_LISTENERS__SSL__DEFAULT__SSL_OPTIONS__VERIFY=verify_none
    ports:
      - 1883:1883    # Plain MQTT (HA)
      - 8883:8883    # TLS MQTT (Qubo device)
      - 18083:18083  # Web dashboard
      - 8083:8083    # Websocket (optional)
    volumes:
      - ./data:/data
      - ./log:/config/log
```

Start it:

```bash
docker compose up -d
docker logs -f emqx   # wait for "EMQX is running now!"
```

### A.2. Generate TLS certificate

The cert's SAN must include `DNS:mqtt.platform.quboworld.com` — that's what
the device checks.

```bash
CERTDIR=./data/emqx/data/certs/quboworld
mkdir -p "$CERTDIR"
cd "$CERTDIR"

# CA
openssl genrsa -out ca.key 2048
openssl req -new -x509 -days 3650 -key ca.key -out ca.crt \
  -subj "/CN=QuboLocalCA"

# Server key + CSR
openssl genrsa -out server.key 2048
openssl req -new -key server.key -out server.csr \
  -subj "/CN=mqtt.platform.quboworld.com"

# Extension file with SAN (critical!)
cat > server.ext <<EOF
authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names
[alt_names]
DNS.1 = mqtt.platform.quboworld.com
DNS.2 = localhost
IP.1  = <your-broker-ip>     # e.g. 10.10.10.10
EOF

openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
  -out server.crt -days 3650 -extfile server.ext

chmod 644 *.crt *.key
```

Verify the SAN is present:

```bash
openssl x509 -in server.crt -noout -ext subjectAltName
# Must output: DNS:mqtt.platform.quboworld.com, DNS:localhost, IP Address:<broker-ip>
```

Or use the bundled script:

```bash
./scripts/gen-certs.sh ./data/emqx/data/certs/quboworld <broker-ip>
```

### A.3. Restart EMQX to load the cert

```bash
docker compose up -d   # recreates container with new env vars
sleep 5

# Verify TLS listener serves the new cert
openssl s_client -connect localhost:8883 -servername mqtt.platform.quboworld.com \
  </dev/null 2>/dev/null | grep -E "subject=|Alt"
# subject=CN = mqtt.platform.quboworld.com
# DNS:mqtt.platform.quboworld.com, DNS:localhost, IP Address:...
```

### A.4. Configure EMQX authentication (for HA connection)

EMQX dashboard → `http://<broker-ip>:18083` (default: `admin` / `public`,
change on first login).

**Authentication → Authentication** → ensure a password-based authenticator
exists. Add your HA connection user:

- **Username**: `mqtt` (or whatever HA uses)
- **Password**: your choice

This user is what **HA uses on :1883**. The Qubo device will add its own user
later (after JWT capture — see doc 4).

### A.5. Connect HA to the broker

Settings → Devices & Services → Add Integration → **MQTT**
- Broker: `<broker-ip>`
- Port: `1883`
- Username: `mqtt`
- Password: (what you set)

Submit. HA should say "Connected".

---

## Option B — Mosquitto (simpler)

### B.1. Install

```bash
sudo apt install mosquitto mosquitto-clients
```

### B.2. Generate cert (same as above)

```bash
sudo mkdir -p /etc/mosquitto/certs
# (run the openssl commands from A.2 into /etc/mosquitto/certs/)
sudo chown mosquitto:mosquitto /etc/mosquitto/certs/*
sudo chmod 600 /etc/mosquitto/certs/*.key
```

### B.3. Configure listeners

Create `/etc/mosquitto/conf.d/qubo.conf`:

```conf
# Plain MQTT for Home Assistant (auth required)
listener 1883
allow_anonymous false
password_file /etc/mosquitto/passwd

# TLS MQTT for Qubo device — NO auth required (device uses its own JWT
# which we'll accept any creds for since it's inside your LAN)
listener 8883
certfile /etc/mosquitto/certs/server.crt
keyfile /etc/mosquitto/certs/server.key
cafile /etc/mosquitto/certs/ca.crt
require_certificate false
allow_anonymous true

# Logging
log_type all
log_dest file /var/log/mosquitto/mosquitto.log
```

Create the password file for HA:

```bash
sudo mosquitto_passwd -c /etc/mosquitto/passwd mqtt
# (prompts for password)
```

Restart:

```bash
sudo systemctl restart mosquitto
sudo tail -f /var/log/mosquitto/mosquitto.log
```

### B.4. Connect HA

Same as A.5, broker IP is your Mosquitto host.

---

## Verify the broker

```bash
# From the broker host itself
mosquitto_sub -h localhost -p 1883 -u mqtt -P <password> -t 'test/#' -v &
mosquitto_pub -h localhost -p 1883 -u mqtt -P <password> -t 'test/hi' -m 'ok'
# Subscriber prints: test/hi ok

# TLS listener
openssl s_client -connect <broker-ip>:8883 \
  -servername mqtt.platform.quboworld.com </dev/null 2>&1 | head -20
# verify return 0 (or "self-signed certificate in chain" — that's expected)
# subject: CN=mqtt.platform.quboworld.com
```

You should now have:
- :1883 working for HA
- :8883 serving a valid cert for `mqtt.platform.quboworld.com`

## Next step

[→ 03 Split DNS configuration](03-dns-split.md)
