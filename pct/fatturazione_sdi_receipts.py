"""Ricevute SdI dai canali già acquisiti, senza trasporto e senza inferire incassi.

Riferimento: documentazione ufficiale SDICoop Trasmissione v1.1, cap. 4;
copia governata docs/specs/ministero/fonti_ufficiali/2026-06-02/.
"""
from __future__ import annotations
import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any
from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException

_NAMESPACES = {"http://www.fatturapa.gov.it/sdi/messaggi/v1.0", "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fattura/messaggi/v1.0"}
_STATUSES = {"RicevutaConsegna": "CONSEGNATA", "NotificaScarto": "SCARTATA", "RicevutaScarto": "SCARTATA",
    "NotificaMancataConsegna": "MANCATA_CONSEGNA", "RicevutaImpossibilitaRecapito": "MANCATA_CONSEGNA",
    "NotificaDecorrenzaTermini": "DECORRENZA_TERMINI", "AttestazioneTrasmissioneFattura": "MANCATA_CONSEGNA"}


def parse_sdi_receipt(xml_bytes: bytes) -> dict[str, Any] | None:
    if not xml_bytes or len(xml_bytes) > 2 * 1024 * 1024:
        return None
    try:
        root = ElementTree.fromstring(xml_bytes)
    except (ElementTree.ParseError, ValueError, DefusedXmlException):
        return None
    namespace, _, kind = root.tag.lstrip("{").partition("}")
    if namespace not in _NAMESPACES or kind not in _STATUSES:
        return None
    def field(name: str) -> str:
        return next((str(node.text or "").strip() for node in root.iter() if node.tag.rsplit("}", 1)[-1] == name), "")
    identifier, filename = field("IdentificativoSdI"), field("NomeFile")
    if not identifier or not filename:
        return None
    return {"kind": kind, "status": _STATUSES[kind], "sdi_id": identifier, "filename": filename,
        "sha256": hashlib.sha256(xml_bytes).hexdigest(),
        "errors": [str(node.text or "").strip()[:500] for node in root.iter() if node.tag.rsplit("}", 1)[-1] == "Descrizione"][:25]}


def ingest_sdi_receipt(manager: Any, xml_bytes: bytes, *, tenant_id: str, source: dict[str, Any]) -> dict[str, Any]:
    """Chiamare solo dall'acquisizione PEC/email autenticata, dopo verifica del mittente SdI.

    source richiede prova prodotta dal verificatore PEC, message_id, attachment_id, received_at,
    href interno. Nessun parametro del client può attestare la provenienza.
    I file non correlati restano nella coda documentale del canale di provenienza.
    """
    receipt = parse_sdi_receipt(xml_bytes)
    if receipt is None:
        return {"ok": True, "applied": False, "code": "not_sdi_receipt"}
    if not all(source.get(key) for key in ("message_id", "attachment_id", "received_at")):
        return {"ok": False, "applied": False, "code": "receipt_provenance_required"}
    proof = dict(source.get("provenance") or {})
    receipt["provenance_verified"] = (proof.get("verified") is True and proof.get("method") == "agid_ca1_native_root_smime_crl_v1"
        and receipt["sha256"] in (proof.get("receipt_hashes") or []) and bool(proof.get("envelope_sha256")))
    if proof.get("verified") is True and not receipt["provenance_verified"]:
        proof = {"verified": False, "code": "attachment_not_certified", "retryable": False,
                 "message": "L'allegato non appartiene al messaggio originale coperto dalla firma PEC."}
    checked_at = datetime.now(timezone.utc)
    verification_state = "verified" if receipt["provenance_verified"] else "retryable" if proof.get("retryable") else "review"
    next_attempt = (checked_at + timedelta(minutes=15)).isoformat() if verification_state == "retryable" else ""
    proof.setdefault("checked_at", checked_at.isoformat())
    candidates = []
    for invoice in manager.tutte():
        data = getattr(invoice, "dati_personalizzati", {}) or {}
        if str((data.get("document") or {}).get("documento_operativo") or "").upper() == "PROFORMA":
            continue
        workflow = data.get("fatturapa_workflow") or {}
        signed, prepared = workflow.get("signed_xml") or {}, workflow.get("xml_prepared") or {}
        filenames = {str(signed.get(key) or "") for key in ("fileName", "originalFileName")}
        filenames.add(str(prepared.get("fileName") or ""))
        current_id = str(getattr(invoice, "sdi_identificativo", "") or "")
        if current_id == receipt["sdi_id"] or (receipt["filename"] in filenames and not current_id):
            candidates.append(invoice)
    from pct.fatturazione_delivery_repository import FatturazioneDeliveryRepository
    repository = FatturazioneDeliveryRepository(getattr(manager, "_studio_db", None), tenant_id)
    evidence = {key: source[key] for key in ("message_id", "attachment_id", "received_at")}
    evidence["provenance"] = {key: proof[key] for key in ("verified", "code", "message", "retryable", "checked_at", "envelope_sha256", "signer_sha256", "revocations", "method", "certification_sha256") if key in proof}
    href = str(source.get("href") or "")
    evidence["href"] = href if href.startswith("/") and not href.startswith("//") else ""
    record_id = hashlib.sha256((tenant_id + ":" + receipt["sha256"]).encode()).hexdigest()
    if len(candidates) != 1:
        # La ricezione è un fatto persistente anche quando la fattura non è
        # ancora nell'archivio. Nessun collegamento per somiglianza e nessun
        # retry periodico della correlazione senza una nuova evidenza.
        evidence["correlation"] = {"code": "receipt_correlation_review", "candidate_count": len(candidates)}
        with repository.transaction():
            repository.conn.execute(
                "INSERT INTO fatturazione_sdi_receipts (id, tenant_id, invoice_id, receipt_hash, status, receipt_json, source_json, received_at, verification_state, next_attempt_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT DO NOTHING",
                (record_id, tenant_id, "", receipt["sha256"], receipt["status"], json.dumps(receipt, ensure_ascii=False), json.dumps(evidence, ensure_ascii=False), source["received_at"], "correlation_required", ""),
            )
        return {"ok": False, "applied": False, "code": "receipt_correlation_review", "candidate_count": len(candidates), "receipt": receipt, "receipt_id": record_id, "persisted": True}
    invoice = candidates[0]
    with repository.transaction():
        repository.conn.execute("INSERT INTO fatturazione_sdi_receipts (id, tenant_id, invoice_id, receipt_hash, status, receipt_json, source_json, received_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT DO NOTHING",
            (record_id, tenant_id, invoice.id, receipt["sha256"], receipt["status"], json.dumps(receipt, ensure_ascii=False), json.dumps(evidence, ensure_ascii=False), source["received_at"]))
        repository.conn.execute(
            "UPDATE fatturazione_sdi_receipts SET invoice_id = ?, receipt_json = ?, source_json = ? WHERE tenant_id = ? AND id = ? AND invoice_id = '' AND verification_state = 'correlation_required'",
            (invoice.id, json.dumps(receipt, ensure_ascii=False), json.dumps(evidence, ensure_ascii=False), tenant_id, record_id),
        )
        assigned = repository.conn.execute(
            "SELECT invoice_id FROM fatturazione_sdi_receipts WHERE tenant_id = ? AND id = ?",
            (tenant_id, record_id),
        ).fetchone()
        if assigned is None or assigned["invoice_id"] != invoice.id:
            return {"ok": False, "applied": False, "code": "receipt_correlation_conflict", "receipt_id": record_id, "persisted": assigned is not None}
        if receipt["provenance_verified"]:
            repository.conn.execute("UPDATE fatturazione_sdi_receipts SET receipt_json = ?, source_json = ? WHERE tenant_id = ? AND id = ? AND invoice_id = ?",
                (json.dumps(receipt, ensure_ascii=False), json.dumps(evidence, ensure_ascii=False), tenant_id, record_id, invoice.id))
        else:
            # Aggiorna il motivo recuperabile senza retrocedere una prova già verificata.
            prior = repository.conn.execute("SELECT receipt_json FROM fatturazione_sdi_receipts WHERE tenant_id = ? AND id = ? AND invoice_id = ?", (tenant_id, record_id, invoice.id)).fetchone()
            if prior and not json.loads(prior["receipt_json"]).get("provenance_verified"):
                repository.conn.execute("UPDATE fatturazione_sdi_receipts SET source_json = ? WHERE tenant_id = ? AND id = ? AND invoice_id = ?",
                    (json.dumps(evidence, ensure_ascii=False), tenant_id, record_id, invoice.id))
        repository.conn.execute("UPDATE fatturazione_sdi_receipts SET verification_state = ?, next_attempt_at = ? WHERE tenant_id = ? AND id = ? AND invoice_id = ? AND (verification_state <> 'verified' OR ? = 'verified')",
            (verification_state, next_attempt, tenant_id, record_id, invoice.id, verification_state))
        rows = repository.conn.execute("SELECT status, receipt_json, source_json FROM fatturazione_sdi_receipts WHERE tenant_id = ? AND invoice_id = ? ORDER BY received_at, id", (tenant_id, invoice.id)).fetchall()
    receipts = [{**json.loads(row["receipt_json"]), "source": json.loads(row["source_json"])} for row in rows]
    verified_receipts = [item for item in receipts if item.get("provenance_verified") is True]
    states = {item["status"] for item in verified_receipts}
    existing_workflow = (getattr(invoice, "dati_personalizzati", {}) or {}).get("fatturapa_workflow") or {}
    manual = existing_workflow.get("sdi_manual_outcome") or {}
    if manual.get("identifier") == receipt["sdi_id"] and manual.get("status") in set(_STATUSES.values()):
        states.add(manual["status"])
    conflict = "SCARTATA" in states and bool(states & {"CONSEGNATA", "DECORRENZA_TERMINI"})
    current = str(getattr(invoice, "sdi_stato", "") or "")
    state = current if conflict else next((value for value in ("SCARTATA", "DECORRENZA_TERMINI", "CONSEGNATA", "MANCATA_CONSEGNA") if value in states), current)
    data = dict(getattr(invoice, "dati_personalizzati", {}) or {})
    workflow = dict(data.get("fatturapa_workflow") or {})
    workflow["sdi_receipts"] = verified_receipts
    reviewed_hashes = {item.get("sha256") for item in workflow.get("sdi_receipts_reviewed") or []}
    workflow["sdi_receipts_pending"] = [item for item in receipts if item.get("provenance_verified") is not True and item.get("sha256") not in reviewed_hashes]
    workflow["sdi_reconciliation_required"] = conflict
    data["fatturapa_workflow"] = workflow
    if not receipt["provenance_verified"]:
        manager.aggiorna(invoice.id, dati_personalizzati=data)
        return {"ok": True, "applied": False, "code": "receipt_provenance_review", "invoice_id": invoice.id, "receipt_id": record_id}
    # Lo stato PAGATA e la conferma dell'incasso non vengono toccati da alcuna ricevuta SdI.
    matching = [entry for entry in verified_receipts if entry.get("status") == state]
    effective_source = (matching[-1].get("source") or {}) if matching else {}
    keep_registered = conflict or (state == current and manual.get("status") == state)
    result_at = str(getattr(invoice, "sdi_data_esito", "") or "") if keep_registered else str(effective_source.get("received_at") or source["received_at"])
    result_ref = str(getattr(invoice, "sdi_ricevuta", "") or "") if keep_registered else str(effective_source.get("href") or evidence["href"] or record_id)
    manager.aggiorna(invoice.id, dati_personalizzati=data, sdi_stato=state, sdi_identificativo=receipt["sdi_id"],
        sdi_data_esito=result_at, sdi_ricevuta=result_ref,
        sdi_note="Ricevuta acquisita dal canale SdI verificato." if not conflict else "Ricevute discordanti: riconciliazione richiesta.")
    return {"ok": True, "applied": True, "invoice_id": invoice.id, "status": state, "review_required": conflict, "receipt_id": record_id}


def build_sdi_validation_report(parsed: dict[str, Any], attachments: list[dict[str, Any]]) -> dict[str, Any]:
    """Profilo fiscale distinto da udienze, notifiche e ricevute di trasporto."""
    receipts = list(parsed.get("sdi_receipts") or [])
    acquisition = parsed.get("sdi_acquisition") or {}
    provenance = acquisition.get("provenance") or {}
    results = acquisition.get("results") or []
    issues = []
    labels = {"CONSEGNATA": "Fattura consegnata", "SCARTATA": "Fattura scartata", "MANCATA_CONSEGNA": "Fattura non recapitata", "DECORRENZA_TERMINI": "Decorrenza termini SdI"}
    for receipt in receipts:
        state = receipt.get("status")
        if state in {"SCARTATA", "MANCATA_CONSEGNA"}:
            issues.append({"code": "sdi_" + str(state).lower(), "severity": "danger" if state == "SCARTATA" else "warning", "blocking": False,
                "title": labels[state], "detail": "; ".join(receipt.get("errors") or []) or labels[state]})
    if provenance.get("verified") is not True:
        issues.append({"code": "sdi_provenance_pending", "severity": "warning", "blocking": False,
            "title": "Provenienza SdI da verificare", "detail": provenance.get("message") or "La lettura dell'XML non prova da sola la provenienza della ricevuta. La fattura non viene aggiornata senza verifica della busta PEC."})
    elif not results or any(not item.get("applied") or item.get("review_required") for item in results):
        issues.append({"code": "sdi_correlation_pending", "severity": "warning", "blocking": False,
            "title": "Associazione alla fattura da completare", "detail": "Busta PEC verificata: resta da provare il collegamento univoco al documento trasmesso o riconciliare gli esiti discordanti."})
    actions = ["Conservare la ricevuta e aggiornare la fatturazione solo dopo verifica di provenienza e collegamento al documento trasmesso."]
    if any(item.get("status") == "SCARTATA" for item in receipts):
        actions.insert(0, "Correggere il motivo di scarto prima di una nuova trasmissione, che resta sotto il controllo dell'avvocato.")
    profile = {"tipo_evento": "Ricevuta SdI", "fase_pratica": "Fatturazione elettronica", "ricevute_sdi": receipts,
        "checklist_avvocato": actions, "domande_lex": ["Quale fattura e quale trasmissione identifica la ricevuta SdI?"]}
    return {"event_type": "ricevuta_sdi", "required": [], "present": sorted({str(item.get("classification") or "") for item in attachments}),
        "issues": issues, "deposit_lifecycle": {}, "deposit_correlation": {}, "semantic_context": parsed.get("semantic_context") or {},
        "legal_workflow": {"event_type": "ricevuta_sdi", "azione_proposta": actions[0]}, "procedural_profile": profile,
        "remote_hearing": {}, "lawyer_checklist": actions, "normative_references": [], "agent_questions": profile["domande_lex"],
        "recommended_actions": actions, "deadline_proposal": {"status": "not_needed", "auto_create": False, "title": "", "due_date": "", "legal_deadline": False, "calendar_scope": "nessuno", "reason": "Ricevuta fiscale SdI: nessuna scadenza processuale."},
        "blocking": False, "severity": "danger" if any(item["severity"] == "danger" for item in issues) else "warning" if issues else "ok",
        "generated_at": datetime.now(timezone.utc).isoformat()}
