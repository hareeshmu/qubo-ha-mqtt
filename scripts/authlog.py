#!/usr/bin/env python3
"""HTTP authentication logger for Qubo device JWT capture.

Run this on your MQTT broker host. Point EMQX's HTTP authenticator at
http://<broker>:8090/mqtt/auth. It returns 'allow' for every request and
appends each {username, password, clientid} triple to ./auth.log.

Once you've captured the Qubo device's creds, stop this script and
permanently store the creds in your broker's built-in DB.

Usage: python3 scripts/authlog.py [port]
"""
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import sys
import datetime
import os


LOG_PATH = os.environ.get("AUTHLOG_FILE", "auth.log")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args, **kwargs):
        return  # suppress default noise

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(length)
        try:
            data = json.loads(body.decode())
        except Exception:
            data = {"raw": body.decode(errors="replace")}

        ts = datetime.datetime.now().isoformat(timespec="seconds")
        entry = {"ts": ts, "path": self.path, "data": data}

        with open(LOG_PATH, "a") as f:
            f.write(json.dumps(entry) + "\n")

        print(json.dumps(entry), flush=True)

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"result":"allow"}')


def main() -> int:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8090
    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"Auth-logger listening on 0.0.0.0:{port}")
    print(f"Writing to {LOG_PATH}")
    print("Point EMQX HTTP authenticator at http://<host>:{port}/mqtt/auth")
    print("Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
