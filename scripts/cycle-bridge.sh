#!/usr/bin/env bash
# Force-cycle the EMQX cloud-bridge connector to clear a stuck cloud-side
# session. Use when the Qubo app shows "online" but buttons silently do
# nothing AND a phone-side app restart didn't fix it (both sides are stale —
# this fixes the cloud side; you still need to force-kill + reopen the app).
#
# Env vars (or defaults):
#   EMQX_URL        default: http://127.0.0.1:18083
#   EMQX_USER       default: admin
#   EMQX_PASS       required
#   CONNECTOR_NAME  default: qubo_cloud
#
# Exit codes: 0 = cycled OK, 1 = config / auth error, 2 = reconnect failed.

set -euo pipefail

EMQX_URL="${EMQX_URL:-http://127.0.0.1:18083}"
EMQX_USER="${EMQX_USER:-admin}"
CONNECTOR_NAME="${CONNECTOR_NAME:-qubo_cloud}"

if [[ -z "${EMQX_PASS:-}" ]]; then
  echo "error: EMQX_PASS not set" >&2
  exit 1
fi

if ! command -v jq >/dev/null; then
  echo "error: jq required (brew install jq)" >&2
  exit 1
fi

token=$(curl -fsS -X POST "$EMQX_URL/api/v5/login" \
  -H 'Content-Type: application/json' \
  -d "{\"username\":\"$EMQX_USER\",\"password\":\"$EMQX_PASS\"}" \
  | jq -r .token)

if [[ -z "$token" || "$token" == "null" ]]; then
  echo "error: login failed" >&2
  exit 1
fi

connector_id="mqtt:$CONNECTOR_NAME"
auth=(-H "Authorization: Bearer $token" -H 'Content-Type: application/json')

# Fetch + strip read-only fields
body=$(curl -fsS "${auth[@]}" "$EMQX_URL/api/v5/connectors/$connector_id" \
  | jq 'del(.status,.node_status,.status_reason,.type,.name,.actions,.sources,.bridge_mode)')

echo "stopping connector $connector_id..."
curl -fsS -X PUT "${auth[@]}" "$EMQX_URL/api/v5/connectors/$connector_id" \
  -d "$(jq '.enable=false' <<<"$body")" >/dev/null
sleep 3

echo "starting connector $connector_id..."
curl -fsS -X PUT "${auth[@]}" "$EMQX_URL/api/v5/connectors/$connector_id" \
  -d "$(jq '.enable=true' <<<"$body")" >/dev/null
sleep 5

status=$(curl -fsS "${auth[@]}" "$EMQX_URL/api/v5/connectors/$connector_id" | jq -r .status)
if [[ "$status" != "connected" ]]; then
  echo "error: connector did not reconnect (status=$status)" >&2
  exit 2
fi

echo "ok — bridge reconnected. Now force-kill + reopen the Qubo app on your phone."
