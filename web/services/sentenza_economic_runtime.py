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
    return _save_audit(audit, fascicolo=fascicolo, repo=repo, fonte=fonte,
        documento_id=documento_id, document_hash_sha256=document_hash_sha256,
        message_id=message_id, actor_id=actor_id, tenant_id=tenant_id)


def _save_audit(audit: Any, *, fascicolo: Any, repo: Any, fonte: str,
                documento_id: str, document_hash_sha256: str,
                message_id: str = "", actor_id: str = "", tenant_id: str = "") -> dict[str, Any]:
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


def _fascicoli_repository_mirato():
    """Riuso il repository mirato della richiesta prima del helper legacy.

    Il dettaglio React ha gia' aperto `get_fascicoli_mirato()` e lo conserva
    in `flask.g`; riusarlo evita che il controllo economico ricarichi tutti i
    fascicoli. Il fallback mantiene compatibilita' per chiamate fuori Flask.
    """
    try:
        from flask import current_app, g

        repository = getattr(g, "_fascicoli_mirato", None)
        if repository is not None:
            return repository
        extensions = getattr(current_app, "extensions", {}) or {}
        core_runtime = extensions.get("core_runtime", {}) or {}
        loader = core_runtime.get("get_fascicoli_mirato")
        if callable(loader):
            return loader()
    except (ImportError, RuntimeError, AttributeError):
        pass
    from web.helpers import get_fascicoli

    try:
        return get_fascicoli()
    except RuntimeError:
        # Il payload di sola lettura puo' essere usato anche da test/CLI senza
        # contesto Flask: gli audit gia' persistiti restano consultabili.
        return None


def _resolve_fascicolo(fascicolo_id: str, *, fascicolo: Any | None = None):
    if fascicolo is not None and str(getattr(fascicolo, "id", "") or "") == str(fascicolo_id or ""):
        return fascicolo
    gestione = _fascicoli_repository_mirato()
    if gestione is None:
        return None
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
    """Gia' analizzato se un audit porta la stessa impronta; a parita' di id conta il contenuto.

    Un documento sostituito sotto lo stesso id (nuova versione della sentenza)
    ha un'impronta diversa e va rianalizzato: l'id da solo non basta.
    """
    doc_id = _document_id(documento)
    doc_hash = _document_hash(documento)
    for audit in audits:
        audit_hash = str(audit.get("document_hash_sha256") or "").strip().lower()
        if doc_hash and audit_hash == doc_hash.lower():
            return True
        if doc_id and str(audit.get("documento_id") or "") == doc_id and (not doc_hash or not audit_hash):
            return True
    return False


def _document_texts_for_fascicolo(fascicolo: Any, tenant_id: str) -> dict[str, str]:
    from web.services.archivio_letture_runtime import testi_indice_archivio
    return testi_indice_archivio(fascicolo)


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
    return "", hash_doc


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
    report = {"ok": True, "analyzed": 0, "skipped": 0, "missing_text": 0, "errors": 0, "candidates": 0}
    from web.services.archivio_letture_runtime import fatti_fascicolo
    esclusi = {f.oggetto_id for f in fatti_fascicolo(fascicolo, canonico=False) if f.campo == "natura_documentale" and f.valore == "precedente_giurisprudenziale"}
    da_analizzare: list[Any] = []
    for documento in getattr(fascicolo, "documenti", []) or []:
        if _document_id(documento) in esclusi or not _is_sentenza_candidate(documento):
            continue
        report["candidates"] += 1
        if _already_analyzed([a for a in audits if a.get("fonte") == "ARCHIVIO_LETTURE"], documento):
            report["skipped"] += 1
            continue
        da_analizzare.append(documento)
    if not da_analizzare:
        # Tutte le sentenze candidate sono gia' state analizzate con questa impronta:
        # i testi del catalogo non si caricano nemmeno.
        return report
    import json
    from pct.sentenza_economic_audit import (
        SentenzaEconomicAudit, SentenzaIdentityMatch, SentenzaEconomicExtraction,
        SpeseLiquidate, ContributoUnificatoAudit, EconomicAction,
    )
    fatti = fatti_fascicolo(fascicolo, canonico=False, verifiche=("verificata", "corretta", "plausibile"))
    correnti = {f.oggetto_id: f for f in fatti if f.campo == "controllo_economico"}
    for documento in da_analizzare:
        doc_id = _document_id(documento)
        fatto = correnti.get(doc_id)
        prova = next((p for p in fatto.prove if p.get("codice") == "audit_economico"), None) if fatto else None
        if not prova:
            report["missing_text"] += 1
            continue
        try:
            data = json.loads(prova["dettaglio"])
            data["match"] = SentenzaIdentityMatch(**data["match"])
            sentenza = data["sentenza"]
            sentenza["spese_liquidate"] = SpeseLiquidate(**sentenza["spese_liquidate"])
            data["sentenza"] = SentenzaEconomicExtraction(**sentenza)
            data["contributo_unificato"] = ContributoUnificatoAudit(**data["contributo_unificato"])
            data["azioni"] = [EconomicAction(**a) for a in data["azioni"]]
            result = _save_audit(SentenzaEconomicAudit(**data),
                fascicolo=fascicolo, repo=repo, fonte="ARCHIVIO_LETTURE",
                documento_id=doc_id, document_hash_sha256=_document_hash(documento),
                actor_id=_actor_id() or "archivio-letture", tenant_id=tenant_id)
            if result.get("ok"):
                report["analyzed"] += 1
                audits.append(result["audit"])
        except Exception:
            from flask import current_app
            current_app.logger.exception("Consegna economica dall’archivio non riuscita")
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
    # Reading is performed by the motors' job, never by this GET projection.
    auto_report = {"ok":True, "source":"archivio_letture", "analyzed":0}
    repo = _repo()
    audits = repo.list_sentenza_audits(tenant_id, fascicolo_id=fascicolo_id)
    events = repo.list_economic_events(tenant_id, fascicolo_id=fascicolo_id)
    from web.services.archivio_letture_runtime import fatti_fascicolo
    fascicolo = _resolve_fascicolo(fascicolo_id) if fascicolo_id else None
    if fascicolo is not None:
        fatti = fatti_fascicolo(fascicolo, canonico=False)
        esclusi = {f.oggetto_id for f in fatti if f.campo == "natura_documentale" and f.valore == "precedente_giurisprudenziale"}
        impronte = {_document_id(d): _document_hash(d) for d in getattr(fascicolo, "documenti", [])}
        audits = [a for a in audits if str(a.get("documento_id") or "") not in esclusi
                  and (a.get("fonte") not in {"FASCICOLO_AUTO", "ARCHIVIO_LETTURE"}
                       or (a.get("fonte") == "ARCHIVIO_LETTURE"
                           and a.get("document_hash_sha256") == impronte.get(str(a.get("documento_id") or ""))))]

        validi = {a["id"] for a in audits}
        events = [e for e in events if e.get("source_type") != "sentenza_economic_audit" or e.get("source_id") in validi]
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
