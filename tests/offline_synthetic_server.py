"""Browser diagnostic harness: never starts production or opens real archives."""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from types import SimpleNamespace

from flask import Flask, g, redirect, session

from pct.offline.notes import NoteSync
from web.bootstrap.offline_routes import register_offline_routes

app = Flask(__name__, static_folder="../web/static", static_url_path="/static")
app.secret_key = "synthetic-browser-test-only"
app.config.update(OFFLINE_WORKSPACE_ENABLED=True, MULTI_TENANT=False)
raw = sqlite3.connect(":memory:", check_same_thread=False)
db = SimpleNamespace(conn=raw)
NoteSync(db, "single-studio", "synthetic-admin").ensure_schema()
raw.execute("CREATE TABLE fascicoli(id TEXT PRIMARY KEY,numero TEXT,oggetto TEXT)")
raw.execute("INSERT INTO fascicoli VALUES ('synthetic-case','TEST/2026','Fascicolo sintetico')")
raw.commit()
# Inject this isolated SQL backend into the actual production route module.
import web.services.storage_runtime

web.services.storage_runtime.get_request_studio_db = lambda _: db


@app.before_request
def identity():
    if session.get("synthetic_user"):
        g.utente_corrente = SimpleNamespace(
            id="synthetic-admin", attivo=True, ruolo=SimpleNamespace(value="AMMINISTRATORE"), ha_permesso=lambda _: True
        )


@app.get("/synthetic-login")
def login():
    session.update(synthetic_user=True, _csrf_token="synthetic-csrf")
    return redirect("/static/offline-workspace/offline.html")


@app.get("/sw.js")
def worker():
    return app.send_static_file("sw.js"), 200, {"Service-Worker-Allowed": "/"}


@app.get("/offline")
def offline():
    return '<html lang="it"><a href="/static/offline-workspace/offline.html">Apri archivio autorizzato</a></html>'


manager = SimpleNamespace(get=lambda case: SimpleNamespace(id=case) if case == "synthetic-case" else None)
register_offline_routes(app, get_fascicoli=lambda: manager, get_utenti=lambda: None, audit=lambda *args, **kwargs: None)
if __name__ == "__main__":
    from werkzeug.serving import make_server

    server = make_server("127.0.0.1", int(sys.argv[1]), app)
    print("synthetic-ready", flush=True)
    server.serve_forever()
