# 3. Split DNS Configuration

The crux of this integration: the **purifier must resolve
`mqtt.platform.quboworld.com` to your local broker**, while **everything else
on your network (including your phone) must resolve it to the real cloud**.

If you don't split — the mobile app breaks.

## Goal

| Client | Resolves to | Purpose |
|--------|-------------|---------|
| Purifier only | Your local broker IP | Device connects locally |
| Every other client (phones, laptops, HA itself) | Real cloud IP (e.g. `65.1.150.122` at time of writing) | Mobile app works |

The real cloud IP can change — you only need to avoid overriding it for
non-purifier clients.

---

## Step 3.1 — Find the real cloud IP (for sanity)

From any client **not** using your override:

```bash
dig @1.1.1.1 mqtt.platform.quboworld.com +short
# 65.1.150.122    (example; may differ for you)
```

Note this IP. You'll need it inside the broker container (see doc 5).

---

## Step 3.2 — Configure split DNS per platform

Follow the section that matches your network.

### Option A — pfSense / OPNsense

1. **Services → DNS Resolver** (Unbound) → **Host Overrides** → **Add**
   - Host: `mqtt`
   - Domain: `platform.quboworld.com`
   - IP: `<your-broker-ip>` (e.g. `10.10.10.10`)
   - Description: `Qubo device local intercept`
   - Save → Apply
2. **Services → DHCP Server** (LAN) → scroll to static mappings → **Add**
   - MAC: `94:51:DC:xx:xx:xx` (your purifier)
   - IP: pick one **outside your DHCP pool** (e.g. `10.10.10.70`)
   - **DNS servers**: `<pfSense LAN IP>` (e.g. `10.10.10.1`)
   - Description: `Qubo purifier`
   - Save → Apply
3. **Ensure other clients don't use pfSense DNS directly** (or if they do,
   they'll also hit the override — in that case use tagged client views
   instead; pfBlockerNG has per-alias DNS).
4. Power-cycle the purifier. It picks up new DHCP lease → uses pfSense DNS →
   gets override.

**Verify** from the broker host (`dig` or `getent hosts`):
```bash
dig @10.10.10.1 mqtt.platform.quboworld.com +short
# 10.10.10.10      ← good
```

### Option B — AdGuard Home (with per-client rewrites)

AdGuard doesn't support per-client DNS rewrites directly, but you can:

1. Run **two AdGuard instances** (or one AdGuard + fallback resolver):
   - AdGuard A: with rewrite `mqtt.platform.quboworld.com → broker-ip`
     → used only by the purifier
   - AdGuard B: normal resolution → used by everyone else
2. On your DHCP server, hand out AdGuard B to all clients. Set a **DHCP
   static reservation** for the purifier MAC with AdGuard A as its DNS.

Alternative: use AdGuard's `$client` filter syntax:

**Filters → Custom filtering rules** (AdGuard 0.107+):
```
||mqtt.platform.quboworld.com^$client=10.10.10.70,dnsrewrite=NOERROR;A;10.10.10.10
```

Reserve `10.10.10.70` (any fixed IP) for the purifier in DHCP.

### Option C — Pi-hole (with per-client rewrites)

Pi-hole's **Local DNS → DNS Records** applies to everyone. For per-client
behaviour:

1. Add entry: `mqtt.platform.quboworld.com → <broker-ip>`
2. Make the purifier use Pi-hole as DNS (DHCP reservation with Pi-hole IP as
   DNS server)
3. Make **other clients** NOT use Pi-hole for this query:
   - Option i: use Pi-hole's `--localise-queries` plus `hosts` file
     conditional forwarding
   - Option ii: run a second Pi-hole for "clean" clients

Simpler: if you only care about the purifier working locally and the Qubo
app on a phone connecting to cloud, set phone DNS manually to `1.1.1.1`.

### Option D — MikroTik / RouterOS

```
/ip dhcp-server lease add
  address=10.10.10.70
  mac-address=94:51:DC:xx:xx:xx
  server=default
  comment="Qubo purifier"
  dhcp-option=<option-name-for-dns-1010101>
```

Create a DHCP option handing out only the MikroTik IP as DNS for this lease,
then in `/ip dns static` add:

```
/ip dns static add name=mqtt.platform.quboworld.com address=10.10.10.10
```

Other clients get public DNS via the default DHCP option set.

### Option E — UniFi

UniFi Controller → Settings → Networks → LAN → **DHCP DNS Server** (set to
your DNS). **New Clients → fingerprint**: find purifier by MAC → **Device
Fixed IP**. No per-client DNS override in UniFi stock — need a UDM + a
separate DNS layer (AdGuard on the UDM is common).

### Option F — OpenWrt

`/etc/config/dhcp`:

```
config host
  option mac '94:51:DC:xx:xx:xx'
  option ip '10.10.10.70'
  option name 'qubo'
  option dns '1'

config domain
  option name 'mqtt.platform.quboworld.com'
  option ip '10.10.10.10'

# For this host only, override DNS:
config host
  option mac '94:51:DC:xx:xx:xx'
  list dhcp_option 'option:dns-server,10.10.10.1'
```

Set the purifier to use the router itself (`10.10.10.1`) which resolves via
the `/etc/config/dhcp` entry. Other clients get a different DNS.

### Option G — Consumer router without per-client DNS

No clean solution. Options:

- Put the purifier on an **IoT VLAN** with its own DNS pointing at your broker
- Run a tiny **dnsmasq** container on the broker host, DHCP-reserve the
  purifier to use that dnsmasq IP
- Buy a pfSense/OPNsense box (best long-term)

---

## Step 3.3 — Verify split DNS

From the broker host:

```bash
# Simulate the purifier's DNS query
dig @<purifier's assigned DNS> mqtt.platform.quboworld.com +short
# → should return <broker-ip>

# Simulate a phone
dig @<phone's DNS> mqtt.platform.quboworld.com +short
# → should return the real cloud IP (e.g. 65.1.150.122)
```

If both return the broker IP → the mobile app will fail to connect to Qubo
cloud. **Fix DNS before proceeding.**

---

## Step 3.4 — Power-cycle the purifier

Unplug → wait 15 seconds → plug back in. It re-DHCPs, picks up the new DNS,
resolves the override, connects to your broker.

**Verify** it connected — on the broker host:

```bash
# EMQX API (replace creds)
curl -s -X POST http://localhost:18083/api/v5/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"<your-admin-pw>"}' | jq -r .token > /tmp/emqx-token

TOKEN=$(cat /tmp/emqx-token)
curl -s "http://localhost:18083/api/v5/clients?limit=100" \
  -H "Authorization: Bearer $TOKEN" | jq '.data[] | select(.clientid | contains("HPH"))'

# Should print a client with:
#   "clientid": "CLIENT_HPH_<MAC>_MainMqttClient_<unit-uuid>"
#   "username": "<some-uuid>"
#   "listener": "ssl:default"
#   "ip_address": "<purifier-IP>"
```

If you see it — DNS override works and the device is talking to your broker.

If the device is **authentication-failing** on your broker, don't worry yet —
doc 4 shows how to accept its credentials.

## Next step

[→ 04 Capture device JWT](04-capture-jwt.md)
