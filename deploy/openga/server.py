"""Un solo motore, nessuna esposizione pubblica: chiamato dal backend autenticato."""
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from pct.openga_search import _reranker, public_inventory, search_openga


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass  # Le domande non vengono conservate nei log HTTP.

    def send(self, status, body):
        data = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/inventory":
            return self.send(200, public_inventory({}))
        if self.path != "/health":
            return self.send(404, {})
        from pct import __version__
        ready = Path(os.environ["IUSENTRA_OPENGA_CATALOGO_DB"]).is_file()
        cache = _reranker.cache_info()
        self.send(200 if ready else 503, {"configured": ready, "version": __version__, "training": False,
                                        "pid": os.getpid(), "reranker_cache": {"caricati": cache.currsize,
                                        "misses": cache.misses, "hits": cache.hits}})

    def do_POST(self):
        if self.path not in {"/search", "/document-identity"}:
            return self.send(404, {})
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 8192:
                raise ValueError()
            body = json.loads(self.rfile.read(size))
            if not isinstance(body, dict):
                raise TypeError()
            if self.path == "/document-identity":
                from pct.openga_identita import identita_catalogo
                result = {"ok": True, "identita": identita_catalogo(
                    os.environ["IUSENTRA_OPENGA_CATALOGO_DB"], body)}
            else:
                result = search_openga(body, {})
            self.send(200, result)
        except (ValueError, TypeError):
            self.send(400, {"ok": False, "message": "Richiesta non valida.", "evidence_scope": "metadata_only"})


if __name__ == "__main__":
    ThreadingHTTPServer((os.getenv("OPENGA_BIND", "0.0.0.0"), 8092), Handler).serve_forever()
