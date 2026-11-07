#!/usr/bin/env python3
"""GitHub webhook listener: on a valid package-published POST, run autoupdate.py.

Validates X-Hub-Signature-256 (GitHub's standard HMAC-SHA256 of the raw body)
against WEBHOOK_SECRET, then runs scripts/autoupdate.py under a lock so
concurrent pushes don't race. Runs in a container on caddy-net with the repo
mounted at /repo, the docker socket, and the host's docker credentials —
autoupdate.py resolves stack compose files via container labels, not paths.

Usage: WEBHOOK_SECRET=... python3 webhook.py
"""

import fcntl
import hashlib
import hmac
import json
import os
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

AUTOUPDATE = "/repo/scripts/autoupdate.py"  # fixed container path, independent of host location
LOCK = "/tmp/webhook-autoupdate.lock"
SECRET = os.environ.get("WEBHOOK_SECRET", "")
BIND = os.environ.get("WEBHOOK_BIND", "0.0.0.0")
PORT = int(os.environ.get("WEBHOOK_PORT", "8082"))
BEERRUN_IMAGE = "ghcr.io/matei9721/beer-run-jpn"


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # health check for uptime-kuma (GET never triggers a run)
        self._send(200, "ok")

    def do_POST(self):
        if self.path not in ("/update", "/update/beer-run"):
            return self._send(404, "not found")
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        sig = self.headers.get("X-Hub-Signature-256", "")
        expected = "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
        if not SECRET or not hmac.compare_digest(sig, expected):
            self._send(401, "bad signature")
            return
        event = self.headers.get("X-GitHub-Event", "?")
        try:
            action = json.loads(body).get("action", "?")
        except json.JSONDecodeError:
            action = "?"
        if action != "published":
            self._send(200, f"ignored ({event}/{action})")
            return
        with open(LOCK, "a+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            command = ["python3", AUTOUPDATE]
            if self.path == "/update/beer-run":
                command += ["--image-repository", BEERRUN_IMAGE]
            out = subprocess.run(command, capture_output=True, text=True, timeout=600).stdout
        self._send(200, out[-4000:])

    def _send(self, code, text):
        body = text.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # quiet; autoupdate.py already logs
        pass


if __name__ == "__main__":
    print(f"listening on {BIND}:{PORT}", flush=True)
    ThreadingHTTPServer((BIND, PORT), Handler).serve_forever()
