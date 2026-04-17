# vercel_app.py — Entry point Vercel serverless
# Prepara l'ambiente /tmp prima di importare Flask/app.
import os
import json
import traceback
from pathlib import Path

# ── Cartelle base in /tmp (unico filesystem scrivibile su Vercel) ──────────
BASE_TMP = Path("/tmp/iusentra_data")
BASE_TMP.mkdir(parents=True, exist_ok=True)


def _json_file(path: str, default=None) -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        p.write_text(json.dumps(default or {}, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(p)


def _dir(path: str) -> str:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return str(p)


# ── Segnali ambiente serverless ────────────────────────────────────────────
os.environ["VERCEL"] = "1"
os.environ["SERVERLESS"] = "1"
os.environ["PCT_DISABLE_SCHEDULER"] = "1"
os.environ["PCT_STORAGE_MODE"] = "JSON"
os.environ["PCT_SQLITE_MODE"] = "0"
os.environ["PCT_MULTI_TENANT"] = "0"
os.environ["PCT_HTTPS"] = "true"

DATA = BASE_TMP / "data"

# ── Variabili d'ambiente con prefisso PCT_ (lette da core_runtime.py) ─────
os.environ["PCT_STUDIO_CONFIG"]       = _json_file(str(BASE_TMP / "config" / "studio.json"))
os.environ["PCT_TENANTS_REGISTRY"]    = _json_file(str(DATA / "tenants.json"))
os.environ["PCT_AUTH_DB"]             = _json_file(str(DATA / "auth" / "utenti.json"))
os.environ["PCT_AUDIT_DB"]            = _json_file(str(DATA / "auth" / "audit.json"), [])
os.environ["PCT_AGENDA_DB"]           = _json_file(str(DATA / "agenda" / "appuntamenti.json"))
os.environ["PCT_CALENDAR_SYNC_DB"]    = _json_file(str(DATA / "agenda" / "calendar_sync.json"))
os.environ["PCT_SCADENZIARIO_DB"]     = _json_file(str(DATA / "scadenziario" / "scadenze.json"))
os.environ["PCT_CLIENTI_DB"]          = _json_file(str(DATA / "clienti" / "anagrafica.json"))
os.environ["PCT_CONDIVISIONI_DB"]     = _json_file(str(DATA / "clienti" / "condivisioni.json"))
os.environ["PCT_NOTE_FALDONE_DB"]     = _json_file(str(DATA / "clienti" / "note_faldone.json"))
os.environ["PCT_SOGGETTI_DB"]         = _json_file(str(DATA / "soggetti" / "anagrafica.json"))
os.environ["PCT_SOGGETTI_PARTI_DB"]   = _json_file(str(DATA / "soggetti" / "parti.json"))
os.environ["PCT_FASCICOLI_DB"]        = _json_file(str(DATA / "fascicoli" / "fascicoli.json"))
os.environ["PCT_FASCICOLI_DOCS"]      = _dir(str(DATA / "fascicoli" / "documenti"))
os.environ["PCT_FASCICOLI_ARCH"]      = _dir(str(DATA / "fascicoli" / "archivio"))
os.environ["PCT_MESSAGGI_DB"]         = _json_file(str(DATA / "messaggi" / "storico.json"))
os.environ["PCT_EMAIL_DB"]            = _json_file(str(DATA / "email" / "casella.json"))
os.environ["PCT_FATTURAZIONE_DB"]     = _json_file(str(DATA / "fatturazione" / "parcelle.json"))
os.environ["PCT_PREVENTIVI_DB"]       = _json_file(str(DATA / "preventivi" / "preventivi.json"))
os.environ["PCT_TEMPLATE_ATTI_DB"]    = _json_file(str(DATA / "template_atti" / "templates.json"))
os.environ["PCT_TEMPLATE_ATTI_PREFS_DB"] = _json_file(str(DATA / "template_atti" / "editor_layout.json"))
os.environ["PCT_PORTALE_DB"]          = _json_file(str(DATA / "portale" / "portali.json"))
os.environ["PCT_PORTALE_UPLOADS"]     = _dir(str(DATA / "portale" / "uploads"))
os.environ["PCT_NOTIFICHE_LOG"]       = _json_file(str(DATA / "notifiche" / "log.json"), [])
os.environ["PCT_BACKUP_DIR"]          = _dir(str(DATA / "backup"))
os.environ["PCT_PAGAMENTI_DIR"]       = _dir(str(DATA / "pagamenti"))
os.environ["PCT_SEARCH_INDEX"]        = str(DATA / "search" / "index.db")
os.environ["PCT_PRIVACY_DB"]          = _json_file(str(DATA / "privacy" / "registro.json"))
os.environ["PCT_WIZARD_PRO_DB"]       = _json_file(str(DATA / "wizard_pro" / "sessioni.json"))
os.environ["PCT_TELEMATICO_DB"]       = str(DATA / "telematico" / "workflow.db")
os.environ["PCT_UFFICI_DB"]           = str(DATA / "uffici" / "uffici.json")
os.environ["PCT_LEGAL_INTELLIGENCE_DB"]     = _json_file(str(DATA / "intelligence" / "motori.json"))
os.environ["PCT_GIURISPRUDENZA_DB"]         = _json_file(str(DATA / "intelligence" / "giurisprudenza.json"))
os.environ["PCT_WORKSPACE_INTELLIGENCE_DB"] = _json_file(str(DATA / "intelligence" / "workspace_intelligence.json"))
os.environ["PCT_NORMATIVE_TABLES_DB"]       = _json_file(str(DATA / "intelligence" / "tabelle_normative.json"))
os.environ["PCT_VALIDATION_RUNS_DB"]        = _json_file(str(DATA / "intelligence" / "validation_runs.json"))
os.environ["PCT_REDACTION_ASSISTANT_DB"]    = _json_file(str(DATA / "intelligence" / "assistente_redazionale.json"))
os.environ["PCT_SCADENZIARIO_DB"]           = _json_file(str(DATA / "scadenziario" / "scadenze.json"))

_dir(str(DATA / "search"))
_dir(str(DATA / "telematico"))
_dir(str(DATA / "uffici"))

# ── Import app (solo dopo aver preparato l'ambiente) ───────────────────────
_import_error: Exception | None = None
app = None

try:
    from web.app import create_app as _create_app
    app = _create_app()
except Exception as exc:
    _import_error = exc

# ── Fallback WSGI se create_app() è crashata ──────────────────────────────
if app is None:
    from werkzeug.wrappers import Request, Response

    _err_body = json.dumps({
        "errore": "Avvio applicazione fallito",
        "dettaglio": traceback.format_exception_only(type(_import_error), _import_error)[-1].strip(),
        "traceback": traceback.format_exc(),
    }, ensure_ascii=False, indent=2)

    def app(environ, start_response):  # type: ignore[misc]
        req = Request(environ)
        body = _err_body.encode()
        start_response("500 Internal Server Error", [
            ("Content-Type", "application/json; charset=utf-8"),
            ("Content-Length", str(len(body))),
        ])
        return [body]
