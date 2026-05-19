"""Blueprint Ricerca Studio."""

from __future__ import annotations

from functools import wraps
from pathlib import Path
from typing import Any

from flask import Blueprint, current_app, g, jsonify, redirect, render_template, request, url_for

from pct.global_search.repository import GlobalSearchRepository
from pct.global_search.service import GlobalSearchService, default_global_search_db_path
from web.helpers import (
    get_agenda,
    get_clienti,
    get_email_ordinaria,
    get_email_pec,
    get_fascicoli,
    get_fatturazione,
    get_legal_intelligence,
    get_messaggi,
    get_pagamenti,
    get_preventivi,
    get_scadenziario,
    get_soggetti,
    tenant_corrente,
)
from web.blueprints.react_shell import render_react_shell_response

global_search = Blueprint("global_search", __name__)


def _richiede_vista_classica() -> bool:
    return (request.args.get("_legacy") or "").strip().lower() in {"1", "true", "si", "yes", "on"}


def _richiedi_login(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not g.get("utente_corrente"):
            return redirect(url_for("login"))
        return fn(*args, **kwargs)

    return wrapper


def _tenant_id() -> str:
    tenant = tenant_corrente()
    return str(getattr(tenant, "id", "") or getattr(tenant, "slug", "") or "default")


def _db_path() -> Path:
    configured = current_app.config.get("GLOBAL_SEARCH_INDEX")
    if configured:
        return Path(str(configured))
    return default_global_search_db_path(current_app.config.get("SEARCH_INDEX", "./data/search/index.db"))


def _service() -> GlobalSearchService:
    return GlobalSearchService(GlobalSearchRepository(_db_path()))


def _context() -> dict[str, Any]:
    ctx: dict[str, Any] = {
        "tenant_id": _tenant_id(),
        "search_index_path": str(current_app.config.get("SEARCH_INDEX", "")),
        "fascicoli": None,
        "clienti": None,
        "soggetti": None,
        "scadenziario": None,
        "agenda": None,
        "preventivi": None,
        "fatturazione": None,
        "pagamenti": None,
        "legal_intelligence": None,
        "messaggi": None,
        "comunicazioni": None,
        "email_pec": None,
        "email_ordinaria": None,
    }
    factories = {
        "fascicoli": get_fascicoli,
        "clienti": get_clienti,
        "soggetti": get_soggetti,
        "scadenziario": get_scadenziario,
        "agenda": get_agenda,
        "preventivi": get_preventivi,
        "fatturazione": get_fatturazione,
        "pagamenti": get_pagamenti,
        "legal_intelligence": get_legal_intelligence,
        "messaggi": get_messaggi,
        "email_pec": get_email_pec,
        "email_ordinaria": get_email_ordinaria,
    }
    for key, factory in factories.items():
        try:
            ctx[key] = factory()
        except Exception as exc:
            current_app.logger.info("Ricerca Studio: modulo %s non disponibile: %s", key, exc)
    ctx["comunicazioni"] = ctx.get("messaggi")
    return ctx


def _types_from_request() -> list[str] | None:
    raw = request.args.get("type") or request.args.get("tipo") or ""
    values = [item.strip() for item in raw.replace(",", " ").split() if item.strip()]
    if not values or "tutto" in values:
        return None
    mapping = {
        "fascicoli": "fascicolo",
        "clienti": "cliente",
        "scadenze": "scadenza",
        "documenti": "documento",
        "comunicazioni": "comunicazione",
        "economia": "fattura",
        "telematico": "deposito",
    }
    expanded: list[str] = []
    for value in values:
        if value == "economia":
            expanded.extend(["preventivo", "conferimento", "fattura", "pagamento"])
        elif value == "telematico":
            expanded.extend(["deposito", "documento"])
        else:
            expanded.append(mapping.get(value, value))
    return expanded


@global_search.get("/global-search")
@_richiedi_login
def index():
    if not _richiede_vista_classica():
        return render_react_shell_response("ricerca-studio")

    q = request.args.get("q", "").strip()
    active_type = request.args.get("type", "tutto").strip() or "tutto"
    service = _service()
    try:
        ctx = _context()
        stats = service.stats(ctx)
        results = service.search(
            ctx,
            q,
            entity_types=_types_from_request(),
            limit=int(request.args.get("limit", 25)),
            user=g.get("utente_corrente"),
        ) if q else {"results": [], "total": 0, "took_ms": 0}
    finally:
        service.repository.close()
    return render_template(
        "global_search/index.html",
        q=q,
        active_type=active_type,
        stats=stats,
        payload=results,
    )


@global_search.get("/api/global-search")
@_richiedi_login
def api_search():
    q = request.args.get("q", "").strip()
    limit = min(max(int(request.args.get("limit", 20)), 1), 100)
    service = _service()
    try:
        ctx = {"tenant_id": _tenant_id()}
        stats = service.stats(ctx)
        if q and stats.get("total", 0) == 0:
            return jsonify({
                "ok": True,
                "query": q,
                "tenant_id": ctx["tenant_id"],
                "took_ms": 0,
                "total": 0,
                "results": [],
                "stats": stats,
                "indexing_required": True,
            })
        payload = service.search(
            ctx,
            q,
            entity_types=_types_from_request(),
            limit=limit,
            user=g.get("utente_corrente"),
        )
        payload["stats"] = service.stats(ctx)
        return jsonify(payload)
    except Exception as exc:
        current_app.logger.exception("Errore Ricerca Studio API: %s", exc)
        return jsonify({"ok": False, "error": str(exc), "results": []}), 200
    finally:
        service.repository.close()


@global_search.get("/api/global-search/stats")
@_richiedi_login
def api_stats():
    service = _service()
    try:
        return jsonify({"ok": True, "stats": service.stats({"tenant_id": _tenant_id()})})
    finally:
        service.repository.close()


@global_search.get("/api/global-search/suggest")
@_richiedi_login
def api_suggest():
    q = request.args.get("q", "").strip()
    service = _service()
    try:
        return jsonify(service.suggest(_context(), q, limit=int(request.args.get("limit", 8))))
    finally:
        service.repository.close()


@global_search.post("/api/global-search/reindex")
@_richiedi_login
def api_reindex():
    service = _service()
    try:
        payload = service.reindex(_context())
        response_payload = dict(payload or {})
        response_payload["ok"] = True
        response_payload["stats"] = payload
        return jsonify(response_payload)
    finally:
        service.repository.close()


@global_search.post("/api/global-search/reindex/entity")
@_richiedi_login
def api_reindex_entity():
    data = request.get_json(silent=True) or request.form
    entity_type = str(data.get("entity_type") or "").strip()
    entity_id = str(data.get("entity_id") or "").strip()
    if not entity_type or not entity_id:
        return jsonify({"ok": False, "error": "entity_type e entity_id sono obbligatori"}), 400
    service = _service()
    try:
        return jsonify(service.reindex_entity(_context(), entity_type, entity_id))
    finally:
        service.repository.close()
