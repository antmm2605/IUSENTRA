"""Authenticated private-network bridge to an existing loopback llama-server.
No prompt, response or credential is written to logs.
"""
import hmac
import ipaddress
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

MAX_BODY = 2 * 1024 * 1024
MAX_RESPONSE = 16 * 1024 * 1024
SLOTS = threading.BoundedSemaphore(2)


def configuration():
    host = os.environ["LEX_BRIDGE_BIND"]
    address = ipaddress.ip_address(host)
    if address not in ipaddress.ip_network("100.64.0.0/10"):
        raise ValueError("Bind must be a Tailscale IPv4 address")
    allowed = {str(ipaddress.ip_address(value.strip())) for value in os.environ["LEX_BRIDGE_PEERS"].split(",")}
    secret = Path(os.environ["LEX_BRIDGE_KEY_FILE"]).read_text().strip()
    if len(secret) < 32:
        raise ValueError("Private API key is missing or too short")
    return host, allowed, secret


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_args):
        pass

    def answer(self, status, body):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)
        self.close_connection = True

    def do_GET(self):
        self.proxy()

    def do_POST(self):
        self.proxy()

    def proxy(self):
        if self.client_address[0] not in self.server.allowed:
            self.answer(403, b'{"error":"peer denied"}')
            return
        supplied = self.headers.get("Authorization", "")
        if not hmac.compare_digest(supplied, "Bearer " + self.server.secret):
            self.answer(401, b'{"error":"authentication required"}')
            return
        if (self.command, self.path) not in {("GET", "/v1/models"), ("POST", "/v1/chat/completions")}:
            self.answer(404, b'{"error":"unsupported endpoint"}')
            return
        if self.headers.get("Transfer-Encoding"):
            self.answer(400, b'{"error":"transfer encoding unsupported"}')
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            size = -1
        if size < 0 or size > MAX_BODY:
            self.answer(413, b'{"error":"invalid body size"}')
            return
        self.connection.settimeout(15)
        body = self.rfile.read(size) if size else None
        if self.command == "POST":
            try:
                payload = json.loads(body or b"")
                if not isinstance(payload, dict) or payload.get("stream"):
                    raise ValueError()
            except (ValueError, TypeError):
                self.answer(400, b'{"error":"non-streaming JSON object required"}')
                return
        if not SLOTS.acquire(blocking=False):
            self.answer(429, b'{"error":"local model busy"}')
            return
        try:
            request = Request("http://127.0.0.1:8090" + self.path, data=body,
                              headers={"Content-Type": "application/json"}, method=self.command)
            with urlopen(request, timeout=600) as upstream:
                result = upstream.read(MAX_RESPONSE + 1)
                if len(result) > MAX_RESPONSE:
                    self.answer(502, b'{"error":"response limit exceeded"}')
                else:
                    self.answer(upstream.status, result)
        except HTTPError:
            self.answer(502, b'{"error":"local model rejected request"}')
        except (URLError, TimeoutError, OSError):
            self.answer(503, b'{"error":"local model unavailable"}')
        finally:
            SLOTS.release()


def main():
    host, allowed, secret = configuration()
    server = ThreadingHTTPServer((host, 8091), Handler)
    server.daemon_threads = True
    server.allowed, server.secret = allowed, secret
    server.serve_forever()


if __name__ == "__main__":
    main()
