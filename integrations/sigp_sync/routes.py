"""UI e API SIGP Sync con catalogo documenti operativo."""
from __future__ import annotations

import tempfile
from functools import wraps
from pathlib import Path

from flask import (
    Blueprint,
    current_app,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from werkzeug.utils import secure_filename

from integrations.sigp.sync_repository import SigpSyncRepository
from integrations.sigp.sync_service import (
    get_sigp_sync_status,
    import_authorized_sigp_payload,
    resolve_sigp_sync_db_path,
)

from .document_repository import SigpDocumentRepository
from .local_connector_client import LocalConnectorError, SigpLocalConnectorClient


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


def _document_repo() -> SigpDocumentRepository:
    return SigpDocumentRepository(resolve_sigp_sync_db_path(current_app.config))


def _storage_root() -> Path:
    configured = current_app.config.get("SIGP_SYNC_STORAGE_DIR")
    if configured:
        return Path(str(configured))
    data_root = Path(str(current_app.config.get("DATA_ROOT") or "data"))
    return data_root / "sigp_documents"


def _connector_client() -> SigpLocalConnectorClient:
    return SigpLocalConnectorClient(
        base_url=str(current_app.config.get("SIGP_LOCAL_CONNECTOR_URL") or ""),
        token=str(current_app.config.get("SIGP_LOCAL_CONNECTOR_TOKEN") or ""),
        timeout=int(current_app.config.get("SIGP_LOCAL_CONNECTOR_TIMEOUT") or 45),
    )


@sigp_sync_bp.get("/")
@_richiedi_login
def index():
    return render_template("sigp_sync.html", status=get_sigp_sync_status())


@sigp_sync_bp.get("/api/health")
@_richiedi_login
def api_health():
    status = get_sigp_sync_status()
    status["document_catalog"] = True
    status["download_modes"] = ["local_connector", "file_locale_collegato", "catalogo_json"]
    return jsonify(status)


@sigp_sync_bp.post("/api/schema/ensure")
@_richiedi_login
def api_ensure_schema():
    try:
        _repo().ensure_schema()
        return jsonify({"ok": True, "message": "Schema SIGP Sync verificato."})
    except Exception as exc:  # pragma: no cover - route guard
        current_app.logger.exception("Errore preparazione schema SIGP Sync: %s", exc)
        return jsonify({"ok": False, "message": str(exc)}), 400


@sigp_sync_bp.post("/api/preflight")
@_richiedi_login
def api_preflight():
    try:
        client = _connector_client()
        health = client.health().payload
        return jsonify(
            {
                "ok": True,
                "authenticated": bool(health.get("authenticated", False)),
                "adapter": "local_connector",
                "message": health.get("message") or "Local Connector raggiungibile. Token/PIN restano sul PC dello studio.",
                "connector": health,
            }
        )
    except Exception as exc:
        return jsonify(
            {
                "ok": True,
                "authenticated": False,
                "adapter": "payload_autorizzato",
                "message": (
                    "Local Connector non verificato. Puoi comunque importare il catalogo documenti JSON "
                    "o collegare file gia' scaricati dal portale ufficiale. Dettaglio: " + str(exc)
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
                "Ricerca remota non eseguita dal server cloud. Usa il Local Connector/PST/PdA autorizzato "
                "oppure importa un payload reale."
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
                "Sincronizzazione diretta disponibile solo tramite adapter PST/PdA/Model Office autorizzato. "
                "Importa un payload reale o collega il Local Connector."
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
    except Exception as exc:  # pragma: no cover - route guard
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


@sigp_sync_bp.get("/api/fascicoli/<int:sigp_fascicolo_id>/documenti")
@_richiedi_login
def api_documenti(sigp_fascicolo_id: int):
    try:
        documents = _document_repo().list_documents(sigp_fascicolo_id)
        return jsonify({"ok": True, "items": documents, "count": len(documents)})
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400


@sigp_sync_bp.post("/api/fascicoli/<int:sigp_fascicolo_id>/documenti/importa-catalogo")
@_richiedi_login
def api_importa_catalogo_documenti(sigp_fascicolo_id: int):
    try:
        data = request.get_json(silent=True) or {}
        raw_catalog = data.get("catalogo") or data.get("documenti") or data.get("payload") or data
        result = _document_repo().import_catalog(sigp_fascicolo_id, raw_catalog, source=data.get("source") or "manuale_json")
        result["message"] = "Catalogo documenti SIGP importato."
        return jsonify(result)
    except Exception as exc:
        current_app.logger.exception("Errore import catalogo documenti SIGP: %s", exc)
        return jsonify({"ok": False, "message": str(exc)}), 400


@sigp_sync_bp.post("/api/fascicoli/<int:sigp_fascicolo_id>/documenti/preview-local-connector")
@_richiedi_login
def api_preview_documenti_local_connector(sigp_fascicolo_id: int):
    """Importa il catalogo documenti restituito dal Local Connector.

    Questa route sostituisce l'errore bloccante "Anteprima documenti PST via Local Signer richiesta":
    se il connector risponde, il catalogo viene salvato; se non risponde, la UI resta utilizzabile.
    """
    try:
        snapshot = _repo().get_snapshot(sigp_fascicolo_id)
        if not snapshot:
            return jsonify({"ok": False, "message": "Fascicolo SIGP non trovato."}), 404
        client = _connector_client()
        payload = request.get_json(silent=True) or {}
        case_payload = payload.get("fascicolo") or snapshot.get("fascicolo") or {}
        catalog = client.preview_documents(case_payload)
        result = _document_repo().import_catalog(sigp_fascicolo_id, catalog, source="local_connector_preview")
        result["message"] = "Catalogo documenti acquisito dal Local Connector."
        return jsonify(result)
    except Exception as exc:
        current_app.logger.exception("Preview documenti Local Connector fallita: %s", exc)
        return jsonify(
            {
                "ok": False,
                "message": (
                    "Anteprima documenti non disponibile dal Local Connector. "
                    "Puoi importare il catalogo JSON o collegare manualmente i file scaricati. "
                    f"Dettaglio: {exc}"
                ),
            }
        ), 400


def _download_document_ids(sigp_fascicolo_id: int, document_ids: list[int]):
    if not document_ids:
        return {"ok": False, "message": "Nessun documento selezionato."}, 400

    repo = _document_repo()
    snapshot = _repo().get_snapshot(sigp_fascicolo_id)
    if not snapshot:
        return {"ok": False, "message": "Fascicolo SIGP non trovato."}, 404
    fascicolo_payload = snapshot.get("fascicolo") or {}
    try:
        client = _connector_client()
    except Exception as exc:
        return {
            "ok": False,
            "message": (
                "Local Connector non configurato o non raggiungibile. "
                "Puoi visualizzare il catalogo e collegare file scaricati manualmente. "
                f"Dettaglio: {exc}"
            ),
        }, 400

    downloaded = []
    errors = []
    storage_root = _storage_root()
    for document_id in document_ids:
        document = repo.get_document(sigp_fascicolo_id, document_id)
        if not document:
            errors.append({"document_id": document_id, "message": "Documento non trovato."})
            continue
        try:
            content, filename, mime_type = client.download_document(
                {
                    "fascicolo_id": sigp_fascicolo_id,
                    "documento_id": document_id,
                    "fascicolo": fascicolo_payload,
                    "documento": document,
                    "original": False,
                }
            )
            saved = repo.set_downloaded_file(sigp_fascicolo_id, document_id, storage_root, filename, content, mime_type)
            downloaded.append({"document_id": document_id, **saved})
        except LocalConnectorError as exc:
            errors.append({"document_id": document_id, "message": str(exc)})
        except Exception as exc:  # pragma: no cover - route guard
            current_app.logger.exception("Errore download documento SIGP %s: %s", document_id, exc)
            errors.append({"document_id": document_id, "message": str(exc)})

    return {
        "ok": len(errors) == 0 or bool(downloaded),
        "partial": bool(errors and downloaded),
        "downloaded": downloaded,
        "errors": errors,
        "documents": repo.list_documents(sigp_fascicolo_id),
        "message": f"Scaricati {len(downloaded)} documenti. Errori: {len(errors)}.",
    }, 200 if not errors else 207


@sigp_sync_bp.post("/api/fascicoli/<int:sigp_fascicolo_id>/documenti/download-local-connector")
@_richiedi_login
def api_download_documenti_local_connector(sigp_fascicolo_id: int):
    data = request.get_json(silent=True) or {}
    document_ids = [int(value) for value in data.get("document_ids", []) if str(value).isdigit()]
    payload, status_code = _download_document_ids(sigp_fascicolo_id, document_ids)
    return jsonify(payload), status_code


@sigp_sync_bp.post("/api/fascicoli/<int:sigp_fascicolo_id>/documenti/<int:documento_id>/allega-file")
@_richiedi_login
def api_allega_file(sigp_fascicolo_id: int, documento_id: int):
    upload = request.files.get("file")
    if not upload:
        return jsonify({"ok": False, "message": "File mancante."}), 400

    filename = secure_filename(upload.filename or f"documento-{documento_id}.pdf")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir) / filename
        upload.save(tmp_path)
        result = _document_repo().attach_local_file(sigp_fascicolo_id, documento_id, tmp_path, _storage_root(), filename)

    result["message"] = "File collegato al documento SIGP."
    result["documents"] = _document_repo().list_documents(sigp_fascicolo_id)
    return jsonify(result)


@sigp_sync_bp.get("/api/fascicoli/<int:sigp_fascicolo_id>/documenti/<int:documento_id>/file")
@_richiedi_login
def api_file_locale(sigp_fascicolo_id: int, documento_id: int):
    try:
        path = _document_repo().resolve_local_file(sigp_fascicolo_id, documento_id, _storage_root())
        return send_file(path, as_attachment=False)
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 404


@sigp_sync_bp.post("/api/fascicoli/<int:sigp_fascicolo_id>/download")
@_richiedi_login
def api_download(sigp_fascicolo_id: int):
    data = request.get_json(silent=True) or {}
    document_ids = [int(value) for value in (data.get("document_ids") or []) if str(value).isdigit()]
    if not document_ids and data.get("mode") == "new_only":
        docs = _document_repo().list_documents(sigp_fascicolo_id)
        document_ids = [int(doc["id"]) for doc in docs if doc.get("scaricabile") and not doc.get("path_locale")]
    payload, status_code = _download_document_ids(sigp_fascicolo_id, document_ids)
    return jsonify(payload), status_code
