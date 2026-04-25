"""UI e API compatibili con la patch SIGP Sync."""

from __future__ import annotations

from functools import wraps

from flask import Blueprint, current_app, g, jsonify, redirect, render_template, request, url_for

from integrations.sigp.sync_repository import SigpSyncRepository
from integrations.sigp.sync_service import (
    get_sigp_sync_status,
    import_authorized_sigp_payload,
    resolve_sigp_sync_db_path,
)

sigp_sync_bp = Blueprint(
    "sigp_sync",
    __name__,
    url_prefix="/sigp-sync",
    template_folder="templates",
    static_folder="static",
)


def _richiedi_login(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not g.get("utente_corrente"):
            return redirect(url_for("login"))
        return fn(*args, **kwargs)

    return wrapper


def _repo() -> SigpSyncRepository:
    return SigpSyncRepository(resolve_sigp_sync_db_path(current_app.config))


@sigp_sync_bp.get("/")
@_richiedi_login
def index():
    return render_template("sigp_sync.html", status=get_sigp_sync_status())


@sigp_sync_bp.get("/api/health")
@_richiedi_login
def api_health():
    return jsonify(get_sigp_sync_status())


@sigp_sync_bp.post("/api/schema/ensure")
@_richiedi_login
def api_ensure_schema():
    try:
        _repo().ensure_schema()
        return jsonify({"ok": True, "message": "Schema SIGP Sync verificato."})
    except Exception as exc:
        current_app.logger.exception("Errore preparazione schema SIGP Sync: %s", exc)
        return jsonify({"ok": False, "message": str(exc)}), 400


@sigp_sync_bp.post("/api/preflight")
@_richiedi_login
def api_preflight():
    return jsonify(
        {
            "ok": True,
            "authenticated": False,
            "adapter": "payload_autorizzato",
            "message": (
                "Il controllo token avviene sul PC dello studio tramite Local Signer/Connector. "
                "Questa UI non salva PIN e non interroga portali tramite scraping."
            ),
        }
    )


@sigp_sync_bp.post("/api/fascicoli/search")
@_richiedi_login
def api_search():
    return jsonify(
        {
            "ok": True,
            "items": [],
            "message": (
                "Ricerca remota non eseguita dal server cloud. Usare Local Connector/PST/PdA "
                "autorizzato e importare il payload reale."
            ),
        }
    )


@sigp_sync_bp.post("/api/fascicoli/sync")
@_richiedi_login
def api_sync():
    return jsonify(
        {
            "ok": False,
            "message": (
                "Sincronizzazione diretta disponibile solo tramite adapter PST/PdA/Model Office "
                "autorizzato. Importare un payload reale o collegare il Local Connector."
            ),
        }
    ), 400


@sigp_sync_bp.post("/api/fascicoli/importa-payload")
@_richiedi_login
def api_importa_payload():
    try:
        data = request.get_json(silent=True) or {}
        raw_payload = data.get("payload") or data
        result = import_authorized_sigp_payload(
            raw_payload=raw_payload,
            db_path=resolve_sigp_sync_db_path(current_app.config),
            fascicolo_locale_id=data.get("fascicolo_locale_id") or data.get("fascicoloLocaleId"),
        )
        result["message"] = "Payload reale autorizzato importato."
        return jsonify(result)
    except Exception as exc:
        current_app.logger.exception("Errore import payload SIGP Sync: %s", exc)
        return jsonify({"ok": False, "message": str(exc)}), 400


@sigp_sync_bp.get("/api/fascicoli")
@_richiedi_login
def api_fascicoli():
    limit = request.args.get("limit", "100")
    return jsonify({"ok": True, "items": _repo().list_fascicoli(limit=int(limit or 100))})


@sigp_sync_bp.get("/api/fascicoli/<int:sigp_fascicolo_id>")
@_richiedi_login
def api_snapshot(sigp_fascicolo_id: int):
    snapshot = _repo().get_snapshot(sigp_fascicolo_id)
    if not snapshot:
        return jsonify({"ok": False, "message": "Fascicolo SIGP non trovato."}), 404
    return jsonify({"ok": True, "snapshot": snapshot})


@sigp_sync_bp.post("/api/fascicoli/<int:sigp_fascicolo_id>/download")
@_richiedi_login
def api_download(sigp_fascicolo_id: int):
    return jsonify(
        {
            "ok": False,
            "message": (
                f"Download documenti per fascicolo SIGP {sigp_fascicolo_id} non eseguito dal server. "
                "Serve Local Connector autorizzato e selezione utente."
            ),
        }
    ), 400
