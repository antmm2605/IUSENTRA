"""Runtime applicativo del controllo economico sentenze (avvio manuale).

Separazione netta:
- `run_analysis(...)` è il **core iniettabile** (fascicolo, testo, repo, tiers): puro
  rispetto a Flask, quindi testabile in isolamento;
- i wrapper (`analyze_fascicolo_document`, `build_sentenza_economic_payload`,
  `confirm_economic_action`) risolvono tenant/permessi/OCR dal contesto e delegano
  al core.

Niente `tenant_id` dal client (risolto server-side), nessun path filesystem nelle
risposte, nessun testo sentenza nei log.
"""

from __future__ import annotations

from typing import Any

from pct.sentenza_economic_audit import build_audit
from pct.sentenza_economic_dashboard import build_sentenze_economiche_summary
from pct.sentenza_economic_repository import SentenzaEconomicRepository

# Azioni del motore che diventano eventi economici del fascicolo.
_ACTION_BENEFICIARY_EVENTS = {
    "apri_credito_cliente",
    "apri_credito_avvocato_antistatario",
    "monitora_decreto_gratuito_patrocinio",
    "verifica_contributo_unificato",
    "scadenza_invito_cu",
    "verifica_riconciliazione",
}
_CONFIRM_STATUS = {"confirm": "confirmed", "reject": "rejected", "review": "to_review"}
_SENTENZA_DOC_TYPES = {"SENTENZA", "ORDINANZA", "DECRETO", "VERBALE"}
_SENTENZA_DOC_TOKENS = ("sentenza", "ordinanza", "decreto", "provvedimento", "p.q.m", "definitivamente pronunciando")


def run_analysis(
    *,
    fascicolo: Any,
    testo: str,
    repo: SentenzaEconomicRepository,
    cu_tiers: list[tuple[float, float]] | None = None,
    fonte: str = "FASCICOLO",
    documento_id: str = "",
    document_hash_sha256: str = "",
    message_id: str = "",
    valore_causa: float = 0.0,
    cu_evidence: dict[str, Any] | None = None,
    actor_id: str = "",
    tenant_id: str = "",
) -> dict[str, Any]:
    """Core: costruisce l'audit, persiste audit+eventi+decisione firmata."""

    audit = build_audit(
        fascicolo=fascicolo,
        testo=testo,
        fonte=fonte,
        documento_id=documento_id,
        document_hash_sha256=document_hash_sha256,
        message_id=message_id,
        valore_causa=valore_causa,
        cu_tiers=cu_tiers,
        cu_evidence=cu_evidence,
    )
    audit_dict = audit.to_dict()
    fascicolo_id = str(getattr(fascicolo, "id", "") or "")

    saved = repo.save_sentenza_audit(
        tenant_id,
        fascicolo_id=fascicolo_id,
        documento_id=documento_id,
        message_id=message_id,
        document_hash_sha256=document_hash_sha256,
        fonte=fonte,
        rg_numero_rilevato=audit.match.rg_rilevato,
        rg_anno_rilevato=audit.match.anno_rg_rilevato,
        cliente_rilevato=audit.match.cliente_rilevato,
        tribunale_rilevato=audit.match.tribunale_rilevato,
        match_score=audit.match.overall_score,
        safe_to_attach=audit.safe_to_attach,
        human_review_required=audit.human_review_required,
        status=audit.status,
        audit=audit_dict,
    )

    eventi = []
    for azione in audit.azioni:
        if azione.type not in _ACTION_BENEFICIARY_EVENTS:
            continue
        eventi.append(repo.add_economic_event(
            tenant_id,
            fascicolo_id=fascicolo_id,
            event_type=azione.type,
            source_type="sentenza_economic_audit",
            source_id=saved["id"],
            beneficiary_type=azione.beneficiary_type,
            amount=azione.amount,
            status="to_review",
            priority=azione.priority,
            evidence=[{"label": azione.label, "requires_confirmation": azione.requires_confirmation}],
        ))

    repo.record_decision(
        tenant_id=tenant_id,
        actor_id=actor_id,
        kind="sentenza_economic_analyzed",
        subject_ref=fascicolo_id,
        decision="verificato" if audit.safe_to_attach else "da_revisionare",
        rationale=(
            f"RG match={audit.match.rg_match}, safe_to_attach={audit.safe_to_attach}, "
            f"beneficiario={audit.sentenza.spese_liquidate.beneficiario_credito}, cu={audit.contributo_unificato.status}"
        ),
        evidence={"audit_id": saved["id"], "document_hash_sha256": document_hash_sha256, "eventi": [e["id"] for e in eventi]},
    )

    return {"ok": True, "audit": saved, "eventi": eventi, "detail": audit_dict}


# --------------------------------------------------------------------------- #
# Wrapper con contesto (tenant/OCR/permessi)                                    #
# --------------------------------------------------------------------------- #


def _flag_on() -> bool:
    from flask import current_app
    from web.services.feature_flags import is_feature_enabled

    return bool(is_feature_enabled("features.sentenzaEconomicControl", current_app.config))


def _tenant_id() -> str:
    from flask import g

    utente = g.get("utente_corrente")
    return str(getattr(g, "tenant_context_slug", "") or getattr(utente, "tenant_slug", "") or "")


def _repo() -> SentenzaEconomicRepository:
    from web.services.tenant_paths import tenant_data_path

    db_path = tenant_data_path("SENTENZA_ECONOMIC_DB", require_tenant=True)
    return SentenzaEconomicRepository(db_path)


def _cu_tiers() -> list[tuple[float, float]] | None:
    try:
        from web.helpers import get_normative_tables

        return get_normative_tables().contributo_tiers("civile")
    except Exception:
        return None


def _actor_id() -> str:
    from flask import g

    return str(getattr(g.get("utente_corrente"), "id", "") or "")


def _resolve_fascicolo(fascicolo_id: str):
    from web.helpers import get_fascicoli

    gestione = get_fascicoli()
    getter = getattr(gestione, "get", None)
    if callable(getter):
        return gestione.get(fascicolo_id)
    for fascicolo in getattr(gestione, "tutti", lambda: [])():
        if str(getattr(fascicolo, "id", "")) == fascicolo_id:
            return fascicolo
    return None


def _document_id(documento: Any) -> str:
    return str(getattr(documento, "id", "") or "")


def _document_hash(documento: Any) -> str:
    return str(getattr(documento, "hash_sha256", "") or "")


def _document_name(documento: Any) -> str:
    return str(getattr(documento, "nome", "") or getattr(documento, "nome_file", "") or getattr(documento, "filename", "") or "")


def _document_type_value(documento: Any) -> str:
    value = getattr(documento, "tipo", "")
    return str(getattr(value, "value", value) or "").upper()


def _is_sentenza_candidate(documento: Any) -> bool:
    tipo = _document_type_value(documento)
    haystack = " ".join([
        tipo,
        _document_name(documento),
        str(getattr(documento, "descrizione", "") or ""),
        str(getattr(documento, "note", "") or ""),
    ]).casefold()
    return tipo in _SENTENZA_DOC_TYPES or any(token in haystack for token in _SENTENZA_DOC_TOKENS)


def _already_analyzed(audits: list[dict[str, Any]], documento: Any) -> bool:
    doc_id = _document_id(documento)
    doc_hash = _document_hash(documento)
    for audit in audits:
        if doc_id and str(audit.get("documento_id") or "") == doc_id:
            return True
        if doc_hash and str(audit.get("document_hash_sha256") or "") == doc_hash:
            return True
    return False


def _document_texts_for_fascicolo(fascicolo: Any, tenant_id: str) -> dict[str, str]:
    try:
        from web.services.tenant_paths import tenant_data_path
        from web.services.storage_runtime import get_request_studio_db
        from pct.fascicolo_document_catalog import document_ai_texts_for_catalog

        fascicoli_db_path = tenant_data_path("FASCICOLI_DB", require_tenant=True)
        try:
            structured_db = get_request_studio_db(fascicoli_db_path)
        except Exception:
            structured_db = None
        return document_ai_texts_for_catalog(
            tenant_ids=[tenant_id],
            fascicolo_id=str(getattr(fascicolo, "id", "") or ""),
            documents=getattr(fascicolo, "documenti", []) or [],
            fascicoli_db_path=fascicoli_db_path,
            structured_db=structured_db,
            storage_root=tenant_data_path("DOCUMENTI_AI_DIR", require_tenant=True),
        )
    except Exception:
        return {}


def _document_text(fascicolo: Any, documento_id: str, document_ai_texts: dict[str, str] | None = None) -> tuple[str, str]:
    """Ritorna (testo, hash) dal documento del fascicolo via cache OCR."""

    documento = next(
        (doc for doc in getattr(fascicolo, "documenti", []) if str(getattr(doc, "id", "")) == documento_id),
        None,
    )
    if documento is None:
        return "", ""
    hash_doc = str(getattr(documento, "hash_sha256", "") or "")
    document_ai_text = (document_ai_texts or {}).get(documento_id) or ""
    if document_ai_text.strip():
        return document_ai_text, hash_doc
    try:
        from web.services.tenant_paths import tenant_data_path
        from pct.search_index import IndiceRicerca

        index_path = tenant_data_path("SEARCH_INDEX", require_tenant=True)
        indice = IndiceRicerca(index_path)
        testo = indice.get_ocr_cache(hash_doc) or ""
        if not testo.strip() and documento_id:
            row = indice._conn.execute(
                "SELECT corpo FROM documenti WHERE tipo = ? AND entity_id = ? LIMIT 1",
                ("documento", f"{getattr(fascicolo, 'id', '')}:{documento_id}"),
            ).fetchone()
            testo = row["corpo"] if row else ""
    except Exception:
        testo = ""
    return testo, hash_doc


def ensure_fascicolo_sentenza_economic_analysis(fascicolo_id: str) -> dict[str, Any]:
    if not _flag_on():
        return {"ok": False, "code": "feature_disabled", "analyzed": 0}
    tenant_id = _tenant_id()
    if not tenant_id:
        return {"ok": False, "code": "tenant_context_required", "analyzed": 0}
    fascicolo = _resolve_fascicolo(str(fascicolo_id or "").strip())
    if fascicolo is None:
        return {"ok": False, "code": "not_found", "analyzed": 0}

    repo = _repo()
    audits = repo.list_sentenza_audits(tenant_id, fascicolo_id=str(getattr(fascicolo, "id", "") or ""))
    document_ai_texts = _document_texts_for_fascicolo(fascicolo, tenant_id)
    report = {"ok": True, "analyzed": 0, "skipped": 0, "missing_text": 0, "errors": 0, "candidates": 0}
    for documento in getattr(fascicolo, "documenti", []) or []:
        if not _is_sentenza_candidate(documento):
            continue
        report["candidates"] += 1
        if _already_analyzed(audits, documento):
            report["skipped"] += 1
            continue
        doc_id = _document_id(documento)
        if not doc_id:
            continue
        testo, doc_hash = _document_text(fascicolo, doc_id, document_ai_texts)
        if not testo.strip():
            report["missing_text"] += 1
            continue
        try:
            try:
                actor_id = _actor_id() or "sentenza-auto"
            except Exception:
                actor_id = "sentenza-auto"
            result = run_analysis(
                fascicolo=fascicolo,
                testo=testo,
                repo=repo,
                cu_tiers=_cu_tiers(),
                fonte="FASCICOLO_AUTO",
                documento_id=doc_id,
                document_hash_sha256=doc_hash,
                valore_causa=float(getattr(fascicolo, "valore_causa", 0.0) or 0.0),
                actor_id=actor_id,
                tenant_id=tenant_id,
            )
            if result.get("ok"):
                report["analyzed"] += 1
                audits.append(result.get("audit") or {"documento_id": doc_id, "document_hash_sha256": doc_hash})
        except Exception:
            report["errors"] += 1
    return report


def analyze_fascicolo_document(payload: dict[str, Any]) -> dict[str, Any]:
    if not _flag_on():
        return {"ok": False, "code": "feature_disabled", "message": "Controllo economico sentenze non attivo."}
    tenant_id = _tenant_id()
    if not tenant_id:
        return {"ok": False, "code": "tenant_context_required", "message": "Contesto studio non disponibile."}
    fascicolo_id = str(payload.get("fascicoloId") or "").strip()
    documento_id = str(payload.get("documentoId") or "").strip()
    testo = str(payload.get("testo") or "")
    if not fascicolo_id:
        return {"ok": False, "code": "validation_error", "message": "Fascicolo obbligatorio."}
    fascicolo = _resolve_fascicolo(fascicolo_id)
    if fascicolo is None:
        return {"ok": False, "code": "not_found", "message": "Fascicolo non trovato."}
    document_hash = ""
    if not testo and documento_id:
        testo, document_hash = _document_text(fascicolo, documento_id, _document_texts_for_fascicolo(fascicolo, tenant_id))
    if not testo.strip():
        return {"ok": False, "code": "validation_error", "message": "Testo del provvedimento non disponibile (OCR mancante): incollalo o esegui prima l'OCR."}
    result = run_analysis(
        fascicolo=fascicolo,
        testo=testo,
        repo=_repo(),
        cu_tiers=_cu_tiers(),
        fonte=str(payload.get("fonte") or "FASCICOLO"),
        documento_id=documento_id,
        document_hash_sha256=document_hash,
        valore_causa=float(getattr(fascicolo, "valore_causa", 0.0) or 0.0),
        actor_id=_actor_id(),
        tenant_id=tenant_id,
    )
    return result


def build_sentenza_economic_payload(fascicolo_id: str = "") -> dict[str, Any]:
    if not _flag_on():
        return {"ok": False, "code": "feature_disabled", "message": "Controllo economico sentenze non attivo."}
    tenant_id = _tenant_id()
    if not tenant_id:
        return {"ok": False, "code": "tenant_context_required", "message": "Contesto studio non disponibile."}
    try:
        auto_report = ensure_fascicolo_sentenza_economic_analysis(fascicolo_id) if str(fascicolo_id or "").strip() else {"ok": True, "analyzed": 0}
    except Exception:
        auto_report = {"ok": False, "code": "auto_analysis_error", "analyzed": 0}
    repo = _repo()
    audits = repo.list_sentenza_audits(tenant_id, fascicolo_id=fascicolo_id)
    events = repo.list_economic_events(tenant_id, fascicolo_id=fascicolo_id)
    summary = build_sentenze_economiche_summary(audits, events)
    return {"ok": True, "fascicoloId": fascicolo_id, "audits": audits, "eventi": events, "summary": summary, "autoAnalysis": auto_report}


def confirm_economic_action(payload: dict[str, Any]) -> dict[str, Any]:
    if not _flag_on():
        return {"ok": False, "code": "feature_disabled", "message": "Controllo economico sentenze non attivo."}
    tenant_id = _tenant_id()
    if not tenant_id:
        return {"ok": False, "code": "tenant_context_required", "message": "Contesto studio non disponibile."}
    event_id = str(payload.get("eventId") or "").strip()
    decision = str(payload.get("decision") or "").strip().lower()
    if not event_id or decision not in _CONFIRM_STATUS:
        return {"ok": False, "code": "validation_error", "message": "Evento o decisione non validi."}
    repo = _repo()
    actor_id = _actor_id()
    repo.update_event_status(tenant_id, event_id, status=_CONFIRM_STATUS[decision], reviewed_by=actor_id)
    repo.record_decision(
        tenant_id=tenant_id, actor_id=actor_id, kind="economic_action_review",
        subject_ref=event_id, decision=_CONFIRM_STATUS[decision],
        rationale=f"Revisione avvocato: {decision}", evidence={"event_id": event_id},
    )
    return {"ok": True, "eventId": event_id, "status": _CONFIRM_STATUS[decision]}


def run_pec_economic_trigger(
    *,
    classification: dict[str, Any],
    fascicolo: Any,
    testo: str,
    repo: SentenzaEconomicRepository,
    cu_tiers: list[tuple[float, float]] | None = None,
    tenant_id: str = "",
    message_id: str = "",
    document_hash_sha256: str = "",
    actor_id: str = "pec-presidio",
) -> dict[str, Any]:
    """Auto-trigger dal presidio PEC: SOLO su 'deposito_sentenza', SOLO in anteprima.

    Non scrive nulla di definitivo: l'audit e gli eventi restano `to_review` come
    alert 'documento da verificare economicamente'. La conferma resta manuale.
    """

    from pct.sentenza_economic_workflow import should_trigger_economic_audit

    if not should_trigger_economic_audit(classification):
        return {"ok": False, "code": "not_triggered", "message": "PEC non classificata come deposito di sentenza."}
    if not testo.strip():
        return {"ok": False, "code": "validation_error", "message": "Testo del provvedimento non disponibile: OCR mancante."}
    return run_analysis(
        fascicolo=fascicolo,
        testo=testo,
        repo=repo,
        cu_tiers=cu_tiers,
        fonte="PEC",
        message_id=message_id,
        document_hash_sha256=document_hash_sha256,
        valore_causa=float(getattr(fascicolo, "valore_causa", 0.0) or 0.0),
        actor_id=actor_id,
        tenant_id=tenant_id,
    )


def genera_parcella_from_event(payload: dict[str, Any]) -> dict[str, Any]:
    """Wrapper con contesto: genera la parcella da un credito confermato."""

    if not _flag_on():
        return {"ok": False, "code": "feature_disabled", "message": "Controllo economico sentenze non attivo."}
    tenant_id = _tenant_id()
    if not tenant_id:
        return {"ok": False, "code": "tenant_context_required", "message": "Contesto studio non disponibile."}
    event_id = str(payload.get("eventId") or "").strip()
    fascicolo_id = str(payload.get("fascicoloId") or "").strip()
    if not event_id or not fascicolo_id:
        return {"ok": False, "code": "validation_error", "message": "Evento e fascicolo obbligatori."}
    repo = _repo()
    evento = next(
        (e for e in repo.list_economic_events(tenant_id, fascicolo_id=fascicolo_id) if e.get("id") == event_id),
        None,
    )
    if evento is None:
        return {"ok": False, "code": "not_found", "message": "Evento economico non trovato."}
    fascicolo = _resolve_fascicolo(fascicolo_id)
    if fascicolo is None:
        return {"ok": False, "code": "not_found", "message": "Fascicolo non trovato."}
    try:
        from web.helpers import get_fatturazione
        from pct.sentenza_economic_workflow import genera_parcella_da_credito

        result = genera_parcella_da_credito(
            evento=evento, fascicolo=fascicolo, fatturazione=get_fatturazione(),
            creato_da=_actor_id(), audit_id=str(evento.get("source_id", "") or ""),
        )
    except Exception:
        return {"ok": False, "code": "error", "message": "Generazione parcella non riuscita."}
    if result.get("ok"):
        parcella = result.get("parcella")
        repo.record_decision(
            tenant_id=tenant_id, actor_id=_actor_id(), kind="parcella_generata_da_sentenza",
            subject_ref=fascicolo_id, decision="parcella_creata",
            rationale=f"Parcella origine=sentenza da evento {event_id}",
            evidence={"event_id": event_id, "parcella_id": str(getattr(parcella, "id", "") or "")},
        )
        return {"ok": True, "parcellaId": str(getattr(parcella, "id", "") or ""), "eventId": event_id}
    return result


__all__ = [
    "run_analysis",
    "ensure_fascicolo_sentenza_economic_analysis",
    "analyze_fascicolo_document",
    "build_sentenza_economic_payload",
    "confirm_economic_action",
    "run_pec_economic_trigger",
    "genera_parcella_from_event",
]
