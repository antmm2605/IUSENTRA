"""Only the local Docker bridge may use the WSL embedding model; no generation API."""
from __future__ import annotations

import http.client
import ipaddress
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MODEL = "embeddinggemma:300m"
BIND = "172.17.0.1"
BIND_PORT = 11435
NETWORKS = tuple(ipaddress.ip_network(n) for n in ("172.17.0.0/16", "172.18.0.0/16"))
MAX_BODY = 1024 * 1024
# Una richiesta alla volta (decisione del 19/11/2026): gli embedding non si alternano ai modelli di chat in ollama
# e il modello resta caricato. Chi arriva mentre un'altra richiesta è in corso aspetta il turno fino a ATTESA_TURNO_S.
IN_FLIGHT = threading.BoundedSemaphore(1)
ATTESA_TURNO_S = 120
KEEP_ALIVE = "24h"


def allowed_peer(address: str) -> bool:
    try:
        peer = ipaddress.ip_address(address)
    except ValueError:
        return False
    return any(peer in network for network in NETWORKS)


def validate(method: str, path: str, payload: object = None) -> dict | None:
    if method == "GET" and path in ("/api/tags", "/api/version"):
        return None
    if method != "POST" or path not in ("/api/embed", "/api/embeddings", "/api/show"):
        raise ValueError("Endpoint non consentito")
    if not isinstance(payload, dict) or payload.get("model") != MODEL:
        raise ValueError("Modello non consentito")
    fields = {"model"} if path == "/api/show" else {"model", "input", "prompt", "truncate", "keep_alive"}
    if set(payload) - fields:
        raise ValueError("Opzioni non consentite")
    if path in ("/api/embed", "/api/embeddings"):
        payload.setdefault("keep_alive", KEEP_ALIVE)
    if path != "/api/show":
        text = payload.get("input") if path == "/api/embed" else payload.get("prompt")
        values = [text] if isinstance(text, str) else text
        if not isinstance(values, list) or not 1 <= len(values) <= 32:
            raise ValueError("Lotto non valido")
        if any(not isinstance(t, str) or len(t) > 20000 for t in values):
            raise ValueError("Testo non valido")
        if "truncate" in payload and not isinstance(payload["truncate"], bool):
            raise ValueError("truncate non valido")
        if "keep_alive" in payload and payload["keep_alive"] != "24h":
            raise ValueError("keep_alive non consentito")
    return payload


def forward(method: str, path: str, payload: dict | None) -> tuple[int, dict]:
    # Fixed loopback destination; HTTPConnection never follows redirects.
    connection = http.client.HTTPConnection("127.0.0.1", 11434, timeout=180)
    try:
        body = json.dumps(payload).encode() if payload is not None else None
        connection.request(method, path, body=body, headers={"Content-Type": "application/json"})
        response = connection.getresponse()
        raw = response.read(16 * 1024 * 1024 + 1)
        if response.status == 400 and len(raw) <= 16 * 1024 * 1024:
            # Motivo del rifiuto di ollama (per esempio testo oltre il contesto): breve, senza testi dello studio.
            try:
                motivo = str(json.loads(raw).get("error") or "")
            except (ValueError, AttributeError):
                motivo = ""
            return 400, {"error": "Richiesta rifiutata dal modello locale", "motivo": motivo[:200]}
        if len(raw) > 16 * 1024 * 1024 or response.status != 200:
            return 502, {"error": "Embedding locale non disponibile"}
        result = json.loads(raw)
        if path == "/api/tags":
            result = {"models": [m for m in result.get("models", []) if m.get("name") == MODEL or m.get("model") == MODEL]}
        elif path == "/api/show":
            result = {key: result[key] for key in ("digest", "modified_at") if key in result}
        return 200, result
    finally:
        connection.close()


class Handler(BaseHTTPRequestHandler):
    def handle_request(self) -> None:
        self.connection.settimeout(15)
        if not allowed_peer(self.client_address[0]):
            self.respond(403, {"error": "Rete non consentita"})
            return
        if self.headers.get("Transfer-Encoding"):
            self.respond(400, {"error": "Richiesta non valida"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 <= length <= MAX_BODY:
                self.respond(413, {"error": "Richiesta troppo grande"})
                return
            payload = json.loads(self.rfile.read(length)) if length else None
            payload = validate(self.command, self.path, payload)
        except (ValueError, UnicodeError):
            self.respond(400, {"error": "Richiesta non consentita"})
            return
        if not IN_FLIGHT.acquire(timeout=ATTESA_TURNO_S):
            self.respond(503, {"error": "Embedding locale occupato"})
            return
        try:
            try:
                status, result = forward(self.command, self.path, payload)
            except (OSError, ValueError, http.client.HTTPException):
                status, result = 502, {"error": "Embedding locale non disponibile"}
        finally:
            IN_FLIGHT.release()
        self.respond(status, result)

    def respond(self, status: int, result: dict) -> None:
        raw = json.dumps(result).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(raw)
        self.close_connection = True

    do_GET = handle_request
    do_POST = handle_request


if __name__ == "__main__":
    ThreadingHTTPServer((BIND, BIND_PORT), Handler).serve_forever()
