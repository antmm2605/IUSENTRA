"""Tenant-scoped retry hook for acquired SdI receipts; no mail transport."""
from __future__ import annotations
from pathlib import Path
from typing import Any, Mapping
from flask import Flask


def acquire_sdi_receipts_for_repository(app: Flask, repository: Any, message_id: str) -> dict[str, Any]:
    """Consuma un evento della coda PEC; gli errori restano nel retry nativo."""
    if app.config.get("MULTI_TENANT"):
        from pct.tenant import GestioneTenant
        registry = GestioneTenant(registry_path=app.config["TENANTS_REGISTRY"])
        studio = registry.get(repository.tenant_id)
        if studio is None:
            raise ValueError("Studio dell'evento SdI non disponibile.")
        paths = registry.percorsi_dati(studio.slug, reconcile_aliases=False, ensure_baseline=False)
    else:
        paths = dict(app.config)
    paths = dict(paths)
    expected = paths.get("PEC_AUDIT_DB") or str(Path(paths["EMAIL_CASELLA_DB"]).parent / "pec_audit.sqlite")
    if Path(expected).resolve() != repository.db_path.resolve():
        raise PermissionError("Evento SdI non appartenente all'archivio dello studio.")
    result = refresh_sdi_receipts_for_paths(app, paths, tenant_label=repository.tenant_id, limit=1, message_ids=[message_id])
    if not result.get("ok") or result.get("errors"):
        raise RuntimeError(result.get("message") or "Acquisizione ricevuta SdI da riprovare.")
    return result


def refresh_sdi_receipts_for_paths(app: Flask, paths: Mapping[str, Any], *, tenant_label: str, limit: int = 10, message_ids: list[str] | None = None) -> dict[str, Any]:
    try:
        from pct.tenant import GestioneTenant, StatoTenant
        from web.services.fascicoli_presidi_runtime import _attach_tenant_context
        from web.services.react_fatturazione_sdi_acquisition import refresh_pending_sdi_receipts_for_current_tenant, collect_sdi_receipt_candidates
        multi_tenant = bool(app.config.get("MULTI_TENANT"))
        studio = registry = None
        if multi_tenant:
            registry = GestioneTenant(registry_path=app.config["TENANTS_REGISTRY"])
            studio = registry.get(tenant_label)
            if studio is None or studio.stato == StatoTenant.SOSPESO:
                raise ValueError("Identità dello studio non disponibile per le ricevute SdI.")
            expected = registry.percorsi_dati(studio.slug, reconcile_aliases=False, ensure_baseline=False)
        else:
            if tenant_label != "default":
                raise ValueError("Contesto single-tenant non valido.")
            expected = dict(app.config)
        # La pipeline tenant dichiara EMAIL_CASELLA_DB; il registro PEC è
        # adiacente. Risolvere entrambi i lati prima del confronto proprietario.
        paths, expected = dict(paths), dict(expected)
        for resolved in (paths, expected):
            if not resolved.get("PEC_AUDIT_DB") and resolved.get("EMAIL_CASELLA_DB"):
                resolved["PEC_AUDIT_DB"] = str(Path(resolved["EMAIL_CASELLA_DB"]).parent / "pec_audit.sqlite")
        for key in ("CLIENTI_DB", "PEC_AUDIT_DB"):
            if not paths.get(key) or not expected.get(key) or Path(str(paths[key])).resolve() != Path(str(expected[key])).resolve():
                raise ValueError("Archivio ricevute non appartenente allo studio del job.")
        # Same internal tenant context as the established economic presidio.
        with app.app_context(), app.test_request_context("/_internal/sdi-receipts", method="POST"):
            if multi_tenant:
                _attach_tenant_context(registry, studio)
            else:
                from flask import g
                g.multi_tenant_enabled = False
                g.data_paths = dict(paths)
            collected = []
            if message_ids:
                from web.services.pec_pipeline_runtime import repository_from_paths
                from pct.pec_pipeline import build_validation_report
                repository = repository_from_paths(paths, tenant_label=tenant_label)
                for message_id in list(dict.fromkeys(message_ids))[:max(1, min(int(limit), 200))]:
                    with repository.connect() as conn:
                        context, attachments = repository._attachment_payloads_for_message(conn, message_id)
                    acquisition = collect_sdi_receipt_candidates(tenant_id=tenant_label, message_id=message_id, context=context, attachments=attachments)
                    if not acquisition.get("collected"):
                        continue
                    parsed = dict(context["parsed"])
                    # Compatibilità con JSON storici: riconoscimento condiviso
                    # sui soli allegati di questo evento, senza nuova lettura OCR.
                    from pct.fatturazione_sdi_receipts import parse_sdi_receipt
                    parsed["sdi_receipts"] = [{**receipt, "attachment_id": str(item.index), "attachment_name": item.filename}
                        for item in attachments if (receipt := parse_sdi_receipt(item.data)) is not None]
                    parsed["sdi_acquisition"] = acquisition
                    with repository.connect() as conn:
                        rows = repository.attachment_rows(conn, message_id, context["parsed_row"]["id"])
                        report = build_validation_report(parsed, rows)
                        repository._insert_validation_report(conn, message_id=message_id, parsed_version_id=context["parsed_row"]["id"], report=report, actor="sdi-receipt-worker")
                        repository.append_audit(conn, action="pec.sdi.receipts.acquired", resource_type="pec_message", resource_id=message_id,
                            payload={"results": acquisition.get("results") or [], "provenance": acquisition.get("provenance") or {}}, actor="sdi-receipt-worker")
                    collected.append({"message_id": message_id, **acquisition})
            result = refresh_pending_sdi_receipts_for_current_tenant(limit=max(1, min(int(limit), 10)))
        return {**result, "acquired": collected, "errors": 0 if result.get("ok") else 1}
    except Exception:
        app.logger.exception("Verifica automatica ricevute SdI non riuscita")
        return {"ok": False, "checked": 0, "errors": 1, "message": "Verifica ricevute SdI da riprovare: controlla il contesto dello studio e l’archivio."}
