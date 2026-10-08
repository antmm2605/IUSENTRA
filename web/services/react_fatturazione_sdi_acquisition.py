"""Acquisizione e riverifica SdI sull'EML PEC già presente nello studio."""
from __future__ import annotations
from typing import Any
from urllib.parse import quote


def _tenant_context(pec_tenant: str):
    from flask import g, has_request_context
    tenant = getattr(g, "tenant", None) if has_request_context() else None
    slug, identifier = str(getattr(tenant, "slug", "") or ""), str(getattr(tenant, "id", "") or "")
    paths = getattr(g, "data_paths", None) if has_request_context() else None
    # PEC usa lo slug; fatturazione usa l'identificativo tecnico del tenant.
    if tenant is None and has_request_context() and g.get("multi_tenant_enabled") is False and pec_tenant == "default" and paths:
        return "default", paths
    if not identifier or not slug or slug.lower() != pec_tenant.lower() or not paths:
        raise PermissionError("Contesto dello studio non disponibile per la verifica PEC.")
    return identifier, paths


def _configured_pec_address() -> str:
    from flask import current_app
    factory = (current_app.extensions.get("core_runtime") or {}).get("get_config_studio")
    config = factory().config if callable(factory) else None
    return str(getattr(getattr(config, "pec", None), "indirizzo", "") or "")


def collect_sdi_receipt_candidates(*, tenant_id: str, message_id: str, context: dict[str, Any], attachments: list[Any]) -> dict[str, Any]:
    invoice_tenant, _paths = _tenant_context(tenant_id)
    from pct.fatturazione_sdi_receipts import ingest_sdi_receipt, parse_sdi_receipt
    candidates = [item for item in attachments if item.data.lstrip().startswith(b"<") and parse_sdi_receipt(item.data)]
    if not candidates:
        return {"ok": True, "collected": 0}
    from web.helpers import get_fatturazione
    from pct.sdi_pec_provenance import verify_sdi_pec_provenance
    manager = get_fatturazione()
    row = dict(context.get("row") or {})
    if str(row.get("tenant_id") or "").lower() != tenant_id.lower():
        raise PermissionError("Busta PEC non appartenente allo studio.")
    provenance = verify_sdi_pec_provenance(bytes(row.get("original_mime") or b""), expected_recipient=_configured_pec_address())
    results = []
    for item in candidates:
        results.append(ingest_sdi_receipt(manager, item.data, tenant_id=invoice_tenant, source={
            "provenance": provenance, "message_id": message_id, "attachment_id": str(item.index),
            "received_at": row["received_at"],
            "href": f"/api/v1/ui/email/source/{quote(message_id, safe='')}?name={quote(item.filename, safe='')}",
        }))
    return {"ok": True, "collected": len(results), "results": results,
            "provenance": {k: provenance[k] for k in ("verified", "code", "message", "retryable")},
            "official_status_updated": any(item.get("applied") for item in results)}


def reverify_sdi_receipts_for_invoice(manager: Any, invoice_id: str, *, retry_only: bool = False) -> dict[str, Any]:
    """Ripete la verifica autentica, senza accettare attestazioni del client."""
    from flask import g
    from web.services.pec_pipeline_runtime import repository_from_paths
    tenant = getattr(g, "tenant", None)
    slug = str(getattr(tenant, "slug", "") or ("default" if g.get("multi_tenant_enabled") is False else ""))
    _identifier, paths = _tenant_context(slug)
    invoice = manager.get(invoice_id)
    if invoice is None:
        raise KeyError(invoice_id)
    workflow = (getattr(invoice, "dati_personalizzati", {}) or {}).get("fatturapa_workflow") or {}
    entries = workflow.get("sdi_receipts_pending") or []
    if retry_only:
        entries = [entry for entry in entries if not (entry.get("source") or {}).get("provenance") or ((entry.get("source") or {}).get("provenance") or {}).get("retryable")]
    message_checks = {str((entry.get("source") or {}).get("message_id") or ""): str(((entry.get("source") or {}).get("provenance") or {}).get("checked_at") or "") for entry in entries}
    messages = set(message_checks)
    messages.discard("")
    if not messages:
        return {"ok": True, "message": "Non ci sono ricevute acquisite in attesa di verifica.", "checked": 0}
    repository = repository_from_paths(paths, tenant_label=slug)
    reports = []
    for message_id in sorted(messages, key=lambda key: (message_checks[key], key))[:10]:
        with repository.connect() as conn:
            context, attachments = repository._attachment_payloads_for_message(conn, message_id)
        reports.append(collect_sdi_receipt_candidates(tenant_id=slug, message_id=message_id, context=context, attachments=attachments))
    pending = [report.get("provenance") or {} for report in reports if not (report.get("provenance") or {}).get("verified")]
    unresolved = any(not result.get("applied") or result.get("review_required") for report in reports for result in report.get("results") or [])
    if unresolved and not pending:
        pending.append({"message": "Provenienza controllata: resta da riconciliare il collegamento o la discordanza delle ricevute."})
    return {"ok": True, "message": (pending[0].get("message") if pending else "Ricevute verificate e stato SdI riconciliato."),
            "checked": len(reports), "remaining": max(0, len(messages) - len(reports)),
            "verificationPending": bool(pending), "reports": reports}


def refresh_pending_sdi_receipts_for_current_tenant(*, limit: int = 10) -> dict[str, Any]:
    """Hook per il job PEC esistente; legge soltanto ricevute SQL già acquisite."""
    from flask import g
    from web.helpers import get_fatturazione
    from pct.fatturazione_delivery_repository import FatturazioneDeliveryRepository
    tenant = getattr(g, "tenant", None)
    identifier, _paths = _tenant_context(str(getattr(tenant, "slug", "") or ("default" if g.get("multi_tenant_enabled") is False else "")))
    manager = get_fatturazione()
    repository = FatturazioneDeliveryRepository(getattr(manager, "_studio_db", None), identifier)
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    rows = repository.conn.execute("SELECT invoice_id, MIN(next_attempt_at) AS next_attempt FROM fatturazione_sdi_receipts WHERE tenant_id = ? AND verification_state IN ('pending', 'retryable') AND next_attempt_at <= ? GROUP BY invoice_id ORDER BY next_attempt, invoice_id LIMIT ?", (identifier, now.isoformat(), max(1, min(int(limit), 20)))).fetchall()
    checked = 0
    for row in rows:
        # Prenotazione breve: evita che due worker ripetano lo stesso controllo.
        with repository.transaction():
            changed = repository.conn.execute("UPDATE fatturazione_sdi_receipts SET next_attempt_at = ? WHERE tenant_id = ? AND invoice_id = ? AND verification_state IN ('pending', 'retryable') AND next_attempt_at <= ?", ((now + timedelta(minutes=15)).isoformat(), identifier, row["invoice_id"], now.isoformat()))
        if changed.rowcount == 0:
            continue
        reverify_sdi_receipts_for_invoice(manager, row["invoice_id"], retry_only=True)
        checked += 1
    return {"ok": True, "checked": checked}
