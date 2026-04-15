#!/usr/bin/env bash
# Generate a CA + server cert/key suitable for the Qubo local broker.
# Usage:  ./scripts/gen-certs.sh <output-dir> <broker-ip>
# Example: ./scripts/gen-certs.sh ./certs 10.10.10.10
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <output-dir> <broker-ip>"
  exit 1
fi

DIR="$1"
IP="$2"

mkdir -p "$DIR"
cd "$DIR"

# Clean any prior output
rm -f ca.key ca.crt ca.srl server.key server.csr server.crt server.ext

echo "==> Generating CA..."
openssl genrsa -out ca.key 2048
openssl req -new -x509 -days 3650 -key ca.key -out ca.crt -subj "/CN=QuboLocalCA"

echo "==> Generating server key + CSR..."
openssl genrsa -out server.key 2048
openssl req -new -key server.key -out server.csr \
  -subj "/CN=mqtt.platform.quboworld.com"

echo "==> Building SAN extension..."
cat > server.ext <<EOF
authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
DNS.1 = mqtt.platform.quboworld.com
DNS.2 = localhost
IP.1  = ${IP}
EOF

echo "==> Signing server cert..."
openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
  -out server.crt -days 3650 -extfile server.ext

chmod 644 *.crt *.key

echo
echo "==> Done. Files in: $DIR"
ls -la "$DIR" | awk 'NR>1 {print "   " $NF}'

echo
echo "==> Verifying SAN:"
openssl x509 -in server.crt -noout -ext subjectAltName | tail -1

echo
echo "Point your MQTT broker at:"
echo "  certfile = $DIR/server.crt"
echo "  keyfile  = $DIR/server.key"
echo "  cafile   = $DIR/ca.crt"
