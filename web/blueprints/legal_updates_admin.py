from __future__ import annotations

from functools import wraps
from typing import Any

from flask import Blueprint, abort, current_app, g, jsonify, request

from pct.auth import RuoloUtente
from web.services.legal_update_surface import (
    build_legal_update_pipeline_runtime,
    build_legal_update_surface,
)
from web.services.piattaforma_shell_runtime import render_piattaforma_shell
from web.services.security_redaction import redacted_json_response


legal_updates_admin = Blueprint(
    "legal_updates_admin",
    __name__,
    url_prefix="/admin/aggiornamenti-legali",
)

ACTION_LABELS = {
    "NEWS_ONLY": "Notizia informativa",
    "NEW_NORMATIVE": "Nuova normativa",
    "UPDATE_NORMATIVE": "Aggiornamento normativo",
    "NEW_CASE_LAW": "Nuova giurisprudenza",
    "NEW_PRASSI": "Nuova prassi",
    "DUPLICATE": "Già presente in archivio",
    "OUT_OF_SCOPE": "Fuori perimetro",
    "NEEDS_REVIEW": "Controllo richiesto",
}

CLASSIFICATION_LABELS = {
    "NORMATIVA_NUOVA": "Normativa nuova",
    "NORMATIVA_AGGIORNAMENTO": "Aggiornamento normativo",
    "GIURISPRUDENZA": "Giurisprudenza",
    "PRASSI": "Prassi",
    "NEWS": "Notizia",
    "COMMENTO": "Commento",
    "DUPLICATO": "Duplicato",
    "INCERTO": "Da classificare",
}

STATUS_LABELS = {
    "pending": "In verifica",
    "approved": "Pronta alla pubblicazione",
    "published": "Pubblicata",
    "rejected": "Rifiutata",
    "closed": "Chiusa",
}


def utente_ammesso_console(user) -> bool:
    """Chi apre la console Update Intelligence: il superamministratore, oppure
    l'amministratore dello studio o chi ha i permessi `admin.leggi` e `ai.configura`.
    Lo stesso criterio vale per le pagine React del pannello (`api_v1_piattaforma`)."""
    if not user:
        return False
    if getattr(user, "is_superadmin", False):
        return True
    has_permissions = bool(
        getattr(user, "ha_permesso", lambda _perm: False)("admin.leggi")
        and getattr(user, "ha_permesso", lambda _perm: False)("ai.configura")
    )
    return has_permissions or getattr(user, "ruolo", None) == RuoloUtente.AMMINISTRATORE


def superadmin_required(fn):
    """Consente la console Update Intelligence agli amministratori autorizzati."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        if utente_ammesso_console(getattr(g, "utente_corrente", None)):
            return fn(*args, **kwargs)
        abort(403)

    return wrapper


def _json_error(message: str, *, status: int = 200):
    return jsonify({"ok": False, "errore": message}), status


def _json_ok(payload: dict, *, status: int = 200):
    return jsonify(payload), status


def _clean_label(value: Any) -> str:
    return " ".join(str(value or "").replace("_", " ").split()).strip()


@legal_updates_admin.app_template_filter("legal_update_action_label")
def legal_update_action_label(value: Any) -> str:
    key = str(value or "").strip().upper()
    return ACTION_LABELS.get(key, _clean_label(value).capitalize() or "Controllo richiesto")


@legal_updates_admin.app_template_filter("legal_update_classification_label")
def legal_update_classification_label(value: Any) -> str:
    key = str(value or "").strip().upper()
    return CLASSIFICATION_LABELS.get(key, _clean_label(value).capitalize() or "Da classificare")


@legal_updates_admin.app_template_filter("legal_update_status_label")
def legal_update_status_label(value: Any) -> str:
    key = str(value or "").strip().lower()
    return STATUS_LABELS.get(key, _clean_label(value).capitalize() or "In verifica")


@legal_updates_admin.app_template_filter("legal_update_staging_status_label")
def legal_update_staging_status_label(item: Any) -> str:
    row = item if isinstance(item, dict) else {}
    if not row.get("analysis_id"):
        return "Da analizzare"
    status = str(row.get("review_status") or "").strip().lower()
    action = str(row.get("proposed_action") or "").strip().upper()
    if status == "published":
        return "Pubblicato"
    if status == "closed":
        if action == "DUPLICATE":
            return "Gia' presente"
        if action == "OUT_OF_SCOPE":
            return "Archiviato automaticamente"
        return "Chiuso"
    if status == "approved":
        return "Pronto alla pubblicazione"
    if status == "rejected":
        return "Rifiutato"
    if action == "NEEDS_REVIEW":
        return "Classificato con controllo richiesto"
    if status == "pending":
        return "Verifica fonti in corso"
    return "Classificato automaticamente"


@legal_updates_admin.app_template_filter("legal_update_staging_status_class")
def legal_update_staging_status_class(item: Any) -> str:
    row = item if isinstance(item, dict) else {}
    status = str(row.get("review_status") or "").strip().lower()
    action = str(row.get("proposed_action") or "").strip().upper()
    if status == "published":
        return "success"
    if status == "approved":
        return "primary"
    if status == "closed":
        return "secondary" if action != "OUT_OF_SCOPE" else "light"
    if status == "rejected":
        return "danger"
    if row.get("analysis_id"):
        return "info"
    return "warning"


def _reviewer_name() -> str:
    user = getattr(g, "utente_corrente", None)
    return str(getattr(user, "username", "") or "superadmin")


def _selected_tenant_slug() -> str:
    # Presidio condiviso: questa console non seleziona piu' uno studio.
    return ""


def _request_payload() -> dict[str, Any]:
    return request.get_json(silent=True) or request.form.to_dict()


def _bool_from_payload(value: Any, *, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "si", "sì", "yes", "on"}


def _positive_int_payload(value: Any, *, default: int, maximum: int = 500) -> int:
    try:
        parsed = int(str(value or "").strip())
    except (TypeError, ValueError):
        return default
    if parsed <= 0:
        return default
    return min(parsed, maximum)


def _list_payload(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        raw_values = value
    else:
        raw_values = str(value or "").replace(";", ",").split(",")
    return [str(item or "").strip() for item in raw_values if str(item or "").strip()]


def _int_list_payload(value: Any) -> tuple[int, ...]:
    items: list[int] = []
    for item in _list_payload(value):
        try:
            parsed = int(item)
        except (TypeError, ValueError):
            continue
        if parsed > 0:
            items.append(parsed)
    return tuple(items)


def _serialize_surface(pipeline, *, tenant_slug: str = "") -> dict[str, Any]:
    payload = build_legal_update_surface(tenant_slug=tenant_slug)
    payload["raw_documents"] = pipeline.repository.list_raw_documents(limit=20)
    payload["analyses"] = pipeline.repository.list_analyses(limit=20)
    payload["audit"] = pipeline.repository.list_audit(limit=20)
    return payload


def _upsert_source_from_payload(payload: dict[str, Any], *, current_source: dict[str, Any] | None = None) -> dict[str, Any]:
    current_source = current_source or {}
    return {
        "name": payload.get("name") or current_source.get("name"),
        "code": payload.get("code") or current_source.get("code"),
        "category": payload.get("category") or current_source.get("category") or "news",
        "base_url": payload.get("base_url") or current_source.get("base_url"),
        "source_type": payload.get("source_type") or current_source.get("source_type") or "web",
        "trust_class": payload.get("trust_class") or current_source.get("trust_class") or "C",
        "is_official": _bool_from_payload(payload.get("is_official"), default=bool(current_source.get("is_official", False))),
        "enabled": _bool_from_payload(payload.get("enabled"), default=bool(current_source.get("enabled", True))),
        "polling_minutes": int(payload.get("polling_minutes") or current_source.get("polling_minutes") or 240),
        "parser_type": payload.get("parser_type") or current_source.get("parser_type") or "html",
        "notes": payload.get("notes") if payload.get("notes") is not None else current_source.get("notes", ""),
    }


@legal_updates_admin.get("")
@legal_updates_admin.get("/")
@superadmin_required
def dashboard():
    return render_piattaforma_shell("aggiornamenti-legali", "Aggiornamenti legali")


@legal_updates_admin.get("/fonti")
@superadmin_required
def sources_page():
    return render_piattaforma_shell("aggiornamenti-fonti", "Fonti degli aggiornamenti")


@legal_updates_admin.get("/staging")
@superadmin_required
def staging_page():
    return render_piattaforma_shell("aggiornamenti-staging", "Acquisizione dei documenti")


@legal_updates_admin.get("/staging/<int:raw_document_id>")
@superadmin_required
def staging_detail_page(raw_document_id: int):
    return render_piattaforma_shell("aggiornamenti-staging-scheda", "Dettaglio acquisizione", {"id": str(raw_document_id)})


@legal_updates_admin.get("/analisi")
@superadmin_required
def analysis_page():
    return render_piattaforma_shell("aggiornamenti-analisi", "Catalogazione")


@legal_updates_admin.get("/archivio")
@superadmin_required
def archive_page():
    return render_piattaforma_shell("aggiornamenti-archivio", "Archivio degli aggiornamenti")


@legal_updates_admin.get("/review")
@superadmin_required
def review_page():
    return render_piattaforma_shell("aggiornamenti-revisione", "Coda revisioni aggiornamenti")


@legal_updates_admin.get("/api/review-queue")
@superadmin_required
def api_review_queue():
    try:
        pipeline = build_legal_update_pipeline_runtime(tenant_slug=_selected_tenant_slug())
        return jsonify({"ok": True, "items": pipeline.repository.list_review_queue(limit=100)})
    except Exception as exc:
        current_app.logger.exception("Errore api_review_queue: %s", exc)
        return _json_error("Coda aggiornamenti non disponibile.")


@legal_updates_admin.get("/api/review-queue/<int:review_id>")
@superadmin_required
def api_review_detail(review_id: int):
    try:
        pipeline = build_legal_update_pipeline_runtime(tenant_slug=_selected_tenant_slug())
        row = pipeline.repository.get_review_item(review_id)
        if not row:
            return _json_error("Review non trovata.", status=404)
        return jsonify({"ok": True, "item": row})
    except Exception as exc:
        current_app.logger.exception("Errore api_review_detail: %s", exc)
        return _json_error("Dettaglio revisione non disponibile.")


@legal_updates_admin.post("/api/review-queue/<int:review_id>/approve")
@superadmin_required
def api_review_approve(review_id: int):
    try:
        payload = _request_payload()
        row = build_legal_update_pipeline_runtime(
            tenant_slug=str(payload.get("tenant_slug") or _selected_tenant_slug()).strip().lower()
        ).approve_review(
            review_id,
            reviewer=str(payload.get("reviewer") or "superadmin"),
            notes=str(payload.get("review_notes") or ""),
        )
        return jsonify({"ok": True, "item": row})
    except Exception as exc:
        current_app.logger.exception("Errore api_review_approve: %s", exc)
        return _json_error("Approvazione revisione non completata.")


@legal_updates_admin.post("/api/review-queue/<int:review_id>/edit-and-approve")
@superadmin_required
def api_review_edit_and_approve(review_id: int):
    try:
        payload = _request_payload()
        item = build_legal_update_pipeline_runtime(
            tenant_slug=str(payload.get("tenant_slug") or _selected_tenant_slug()).strip().lower()
        ).edit_and_approve_review(
            review_id,
            reviewer=str(payload.get("reviewer") or "superadmin"),
            review_notes=str(payload.get("review_notes") or ""),
            summary_short=str(payload.get("summary_short") or ""),
            what_changes=str(payload.get("what_changes") or ""),
        )
        return jsonify({"ok": True, "item": item})
    except Exception as exc:
        current_app.logger.exception("Errore api_review_edit_and_approve: %s", exc)
        return _json_error("Modifica revisione non completata.")


@legal_updates_admin.post("/api/review-queue/<int:review_id>/reject")
@superadmin_required
def api_review_reject(review_id: int):
    try:
        payload = _request_payload()
        row = build_legal_update_pipeline_runtime(
            tenant_slug=str(payload.get("tenant_slug") or _selected_tenant_slug()).strip().lower()
        ).reject_review(
            review_id,
            reviewer=str(payload.get("reviewer") or "superadmin"),
            notes=str(payload.get("review_notes") or ""),
        )
        return jsonify({"ok": True, "item": row})
    except Exception as exc:
        current_app.logger.exception("Errore api_review_reject: %s", exc)
        return _json_error("Rifiuto revisione non completato.")


@legal_updates_admin.post("/api/review-queue/<int:review_id>/publish")
@superadmin_required
def api_review_publish(review_id: int):
    try:
        payload = _request_payload()
        result = build_legal_update_pipeline_runtime(
            tenant_slug=str(payload.get("tenant_slug") or _selected_tenant_slug()).strip().lower()
        ).publish_review(
            review_id,
            reviewer=str(payload.get("reviewer") or "superadmin"),
        )
        return _json_ok({"ok": True, "result": result})
    except Exception as exc:
        current_app.logger.exception("Errore api_review_publish: %s", exc)
        return _json_error("Pubblicazione revisione non completata.")


@legal_updates_admin.post("/api/backfill-web-evidence")
@superadmin_required
def api_backfill_web_evidence():
    try:
        payload = _request_payload()
        pipeline = build_legal_update_pipeline_runtime(
            tenant_slug=str(payload.get("tenant_slug") or _selected_tenant_slug()).strip().lower()
        )
        statuses = tuple(status.lower() for status in _list_payload(payload.get("statuses") or payload.get("status")))
        result = pipeline.backfill_web_verification_evidence(
            limit=_positive_int_payload(payload.get("limit"), default=20, maximum=200),
            source_codes=_list_payload(payload.get("source_codes") or payload.get("source_code")),
            statuses=statuses or None,
            include_closed=_bool_from_payload(payload.get("include_closed"), default=False),
            include_open_data=_bool_from_payload(payload.get("include_open_data"), default=False),
            direct_only=_bool_from_payload(payload.get("direct_only"), default=True),
            max_seconds=_positive_int_payload(payload.get("max_seconds"), default=0, maximum=900)
            if payload.get("max_seconds")
            else 0,
            query=str(payload.get("query") or "").strip(),
            review_ids=_int_list_payload(payload.get("review_ids") or payload.get("review_id")),
        )
        return _json_ok({"ok": True, "result": result})
    except Exception as exc:
        current_app.logger.exception("Errore api_backfill_web_evidence: %s", exc)
        return _json_error("Backfill evidenze web non completato.")


@legal_updates_admin.get("/api/sources")
@superadmin_required
def api_sources():
    try:
        pipeline = build_legal_update_pipeline_runtime(tenant_slug=_selected_tenant_slug())
        return jsonify({"ok": True, "items": pipeline.list_sources(enabled_only=False)})
    except Exception as exc:
        current_app.logger.exception("Errore api_sources: %s", exc)
        return _json_error("Catalogo fonti non disponibile.")


@legal_updates_admin.post("/api/sources")
@superadmin_required
def api_create_source():
    try:
        payload = _request_payload()
        pipeline = build_legal_update_pipeline_runtime(
            tenant_slug=str(payload.get("tenant_slug") or _selected_tenant_slug()).strip().lower()
        )
        source_row = _upsert_source_from_payload(payload)
        pipeline.repository.upsert_sources([source_row])
        created = pipeline.repository.get_source_by_code(str(source_row["code"]))
        return jsonify({"ok": True, "item": created})
    except Exception as exc:
        current_app.logger.exception("Errore api_create_source: %s", exc)
        return _json_error("Fonte non creata.")


@legal_updates_admin.put("/api/sources/<int:source_id>")
@superadmin_required
def api_update_source(source_id: int):
    try:
        payload = _request_payload()
        pipeline = build_legal_update_pipeline_runtime(
            tenant_slug=str(payload.get("tenant_slug") or _selected_tenant_slug()).strip().lower()
        )
        current_source = pipeline.repository.get_source_by_id(source_id)
        if not current_source:
            return _json_error("Fonte non trovata.", status=404)
        source_row = _upsert_source_from_payload(payload, current_source=current_source)
        pipeline.repository.upsert_sources([source_row])
        return jsonify({"ok": True, "item": pipeline.repository.get_source_by_code(str(source_row["code"]))})
    except Exception as exc:
        current_app.logger.exception("Errore api_update_source: %s", exc)
        return _json_error("Fonte non aggiornata.")


@legal_updates_admin.post("/api/sources/<int:source_id>/fetch")
@superadmin_required
def api_fetch_source(source_id: int):
    try:
        payload = _request_payload()
        auto_publish = _bool_from_payload(payload.get("auto_publish"), default=True)
        result = build_legal_update_pipeline_runtime(
            tenant_slug=str(payload.get("tenant_slug") or _selected_tenant_slug()).strip().lower()
        ).fetch_source_by_id(source_id, auto_publish=auto_publish)
        return redacted_json_response({"ok": True, "result": result})
    except Exception as exc:
        current_app.logger.exception("Errore api_fetch_source: %s", exc)
        return _json_error("Recupero fonte non completato.")


@legal_updates_admin.get("/api/raw-documents")
@superadmin_required
def api_raw_documents():
    try:
        pipeline = build_legal_update_pipeline_runtime(tenant_slug=_selected_tenant_slug())
        return jsonify(
            {
                "ok": True,
                "items": pipeline.repository.list_raw_documents(
                    source_code=request.args.get("source", ""),
                    classification_type=request.args.get("classification", ""),
                    status=request.args.get("status", ""),
                    limit=int(request.args.get("limit") or 100),
                ),
            }
        )
    except Exception as exc:
        current_app.logger.exception("Errore api_raw_documents: %s", exc)
        return _json_error("Documenti acquisiti non disponibili.")


@legal_updates_admin.get("/api/raw-documents/<int:raw_document_id>")
@superadmin_required
def api_raw_document_detail(raw_document_id: int):
    try:
        pipeline = build_legal_update_pipeline_runtime(tenant_slug=_selected_tenant_slug())
        item = pipeline.repository.get_staging_document(raw_document_id)
        if not item:
            return _json_error("Documento non trovato.", status=404)
        return jsonify({"ok": True, "item": item})
    except Exception as exc:
        current_app.logger.exception("Errore api_raw_document_detail: %s", exc)
        return _json_error("Dettaglio documento non disponibile.")


@legal_updates_admin.post("/api/analyze/<int:raw_document_id>")
@superadmin_required
def api_analyze_raw_document(raw_document_id: int):
    try:
        result = build_legal_update_pipeline_runtime(tenant_slug=_selected_tenant_slug()).analyze_raw_document(
            raw_document_id,
            auto_publish=True,
        )
        return redacted_json_response({"ok": True, "result": result})
    except Exception as exc:
        current_app.logger.exception("Errore api_analyze_raw_document: %s", exc)
        return _json_error("Analisi documento non completata.")


@legal_updates_admin.get("/api/analysis/<int:analysis_id>")
@superadmin_required
def api_analysis_detail(analysis_id: int):
    try:
        pipeline = build_legal_update_pipeline_runtime(tenant_slug=_selected_tenant_slug())
        item = pipeline.repository.get_analysis(analysis_id)
        if not item:
            return _json_error("Analisi non trovata.", status=404)
        return jsonify({"ok": True, "item": item})
    except Exception as exc:
        current_app.logger.exception("Errore api_analysis_detail: %s", exc)
        return _json_error("Dettaglio analisi non disponibile.")


@legal_updates_admin.get("/api/normative")
@superadmin_required
def api_normative():
    try:
        pipeline = build_legal_update_pipeline_runtime(tenant_slug=_selected_tenant_slug())
        return jsonify({"ok": True, "items": pipeline.repository.list_published_normative(limit=int(request.args.get("limit") or 100))})
    except Exception as exc:
        current_app.logger.exception("Errore api_normative: %s", exc)
        return _json_error("Normativa non disponibile.")


@legal_updates_admin.get("/api/normative/<int:normative_id>/versions")
@superadmin_required
def api_normative_versions(normative_id: int):
    try:
        pipeline = build_legal_update_pipeline_runtime(tenant_slug=_selected_tenant_slug())
        return jsonify({"ok": True, "items": pipeline.repository.list_normative_versions(normative_id)})
    except Exception as exc:
        current_app.logger.exception("Errore api_normative_versions: %s", exc)
        return _json_error("Versioni normative non disponibili.")


@legal_updates_admin.get("/api/jurisprudence")
@superadmin_required
def api_jurisprudence():
    try:
        pipeline = build_legal_update_pipeline_runtime(tenant_slug=_selected_tenant_slug())
        return jsonify({"ok": True, "items": pipeline.repository.list_published_jurisprudence(limit=int(request.args.get("limit") or 100))})
    except Exception as exc:
        current_app.logger.exception("Errore api_jurisprudence: %s", exc)
        return _json_error("Giurisprudenza non disponibile.")


@legal_updates_admin.get("/api/prassi")
@superadmin_required
def api_prassi():
    try:
        pipeline = build_legal_update_pipeline_runtime(tenant_slug=_selected_tenant_slug())
        return jsonify({"ok": True, "items": pipeline.repository.list_published_prassi(limit=int(request.args.get("limit") or 100))})
    except Exception as exc:
        current_app.logger.exception("Errore api_prassi: %s", exc)
        return _json_error("Prassi non disponibile.")


@legal_updates_admin.get("/api/news")
@superadmin_required
def api_news():
    try:
        pipeline = build_legal_update_pipeline_runtime(tenant_slug=_selected_tenant_slug())
        return jsonify({"ok": True, "items": pipeline.repository.list_news(limit=100, include_drafts=True)})
    except Exception as exc:
        current_app.logger.exception("Errore api_news admin: %s", exc)
        return _json_error("News non disponibili.")


@legal_updates_admin.get("/api/audit")
@superadmin_required
def api_audit():
    try:
        pipeline = build_legal_update_pipeline_runtime(tenant_slug=_selected_tenant_slug())
        return jsonify(
            {
                "ok": True,
                "items": pipeline.repository.list_audit(
                    entity_type=request.args.get("entity_type", ""),
                    limit=int(request.args.get("limit") or 100),
                ),
            }
        )
    except Exception as exc:
        current_app.logger.exception("Errore api_audit: %s", exc)
        return _json_error("Registro attività non disponibile.")
