"""Riallinea il catalogo documenti dei fascicoli con OCR/metadati."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pct.fascicolo_document_catalog import (
    classify_fascicolo_document,
    document_ai_texts_for_catalog,
    should_apply_catalog_type,
)
from pct.fascicoli import TipoDocumento
from scripts.backfill_sentenza_lex_economics import TenantBackfillTarget, _build_repositories, _load_tenants


def _text(value: Any) -> str:
    return str(value or "").strip()


def _source_of_truth(tenant: TenantBackfillTarget, fascicoli: Any) -> str:
    studio_db = getattr(fascicoli, "_studio_db", None)
    if studio_db is None:
        return "json_mirror"
    kind = _text(getattr(studio_db, "backend_kind", "")).lower()
    if kind == "postgresql":
        return "postgresql"
    return "sqlite"


def run_reclassification(
    *,
    data_root: Path,
    registry: Path,
    tenants: set[str] | None = None,
    apply: bool = False,
) -> dict[str, Any]:
    selected = tenants or set()
    report: dict[str, Any] = {
        "ok": True,
        "applied": bool(apply),
        "source_of_truth": "sqlite/postgresql when available; JSON only as mirror/bootstrap",
        "tenants": [],
        "totals": {
            "tenants": 0,
            "fascicoli_seen": 0,
            "documents_seen": 0,
            "documents_with_ocr_text": 0,
            "reclassified": 0,
            "wrong_atti_fixed": 0,
            "ricorsi_main_act": 0,
            "skipped_low_confidence": 0,
            "skipped_specific": 0,
            "errors": 0,
        },
    }
    for tenant in _load_tenants(registry, data_root, selected):
        fascicoli, _fatturazione = _build_repositories(tenant)
        tenant_report: dict[str, Any] = {
            "tenant": tenant.tenant,
            "storage_key": tenant.storage_key,
            "root": str(tenant.root),
            "source_of_truth": _source_of_truth(tenant, fascicoli),
            "fascicoli_seen": 0,
            "documents_seen": 0,
            "documents_with_ocr_text": 0,
            "reclassified": 0,
            "wrong_atti_fixed": 0,
            "ricorsi_main_act": 0,
            "skipped_low_confidence": 0,
            "skipped_specific": 0,
            "errors": [],
            "samples": [],
        }
        report["totals"]["tenants"] += 1
        for fascicolo in fascicoli.tutti(archiviati=True):
            fid = _text(getattr(fascicolo, "id", ""))
            documents = list(getattr(fascicolo, "documenti", []) or [])
            tenant_report["fascicoli_seen"] += 1
            report["totals"]["fascicoli_seen"] += 1
            text_map = document_ai_texts_for_catalog(
                tenant_ids=[tenant.storage_key, tenant.tenant],
                fascicolo_id=fid,
                documents=documents,
                fascicoli_db_path=tenant.root / "fascicoli" / "fascicoli.json",
                structured_db=getattr(fascicoli, "_studio_db", None),
                # Questo è uno script nominato di audit/riparazione, non il
                # runtime del fascicolo: può consultare lo storico estratto
                # per correggere il catalogo e ne produce il report.
                allow_extracted_files_fallback=True,
            )
            updates: list[dict[str, Any]] = []
            for doc in documents:
                tenant_report["documents_seen"] += 1
                report["totals"]["documents_seen"] += 1
                did = _text(getattr(doc, "id", ""))
                if did in text_map:
                    tenant_report["documents_with_ocr_text"] += 1
                    report["totals"]["documents_with_ocr_text"] += 1
                classification = classify_fascicolo_document(doc, extracted_text=text_map.get(did, ""))
                current_type = getattr(doc, "tipo", TipoDocumento.ALTRO)
                current_value = _text(getattr(current_type, "value", current_type)).upper()
                if classification.role == "atto_principale" and classification.tipo_documento == TipoDocumento.RICORSO:
                    tenant_report["ricorsi_main_act"] += 1
                    report["totals"]["ricorsi_main_act"] += 1
                if current_value == TipoDocumento.ATTO_GIUDIZIARIO.value and classification.section != "atti" and classification.confidence >= 75:
                    tenant_report["wrong_atti_fixed"] += 1
                    report["totals"]["wrong_atti_fixed"] += 1
                if not should_apply_catalog_type(current_type, classification):
                    if classification.confidence < 75:
                        tenant_report["skipped_low_confidence"] += 1
                        report["totals"]["skipped_low_confidence"] += 1
                    else:
                        tenant_report["skipped_specific"] += 1
                        report["totals"]["skipped_specific"] += 1
                    continue
                updates.append({"id_doc": did, "tipo": classification.tipo_documento})
                tenant_report["reclassified"] += 1
                report["totals"]["reclassified"] += 1
                if len(tenant_report["samples"]) < 40:
                    tenant_report["samples"].append(
                        {
                            "fascicolo_id": fid,
                            "document_id": did,
                            "name": _text(getattr(doc, "nome", "")),
                            "from": current_value,
                            "to": classification.tipo_documento.value,
                            "label": classification.label,
                            "role": classification.role,
                            "section": classification.section,
                            "confidence": classification.confidence,
                            "evidence": classification.evidence,
                        }
                    )
            if apply and updates:
                try:
                    fascicoli.aggiorna_documenti_deposito(fid, updates)
                except Exception as exc:
                    tenant_report["errors"].append({"fascicolo_id": fid, "error": str(exc)})
                    report["totals"]["errors"] += 1
                    report["ok"] = False
        report["tenants"].append(tenant_report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Riallinea la catalogazione documenti fascicolo da OCR/metadati.")
    parser.add_argument("--data-root", default="data", help="Data root IUSENTRA.")
    parser.add_argument("--registry", default="data/tenants.json", help="Registro tenant.")
    parser.add_argument("--tenant", action="append", default=[], help="Tenant/storage_key da processare; ripetibile.")
    parser.add_argument("--apply", action="store_true", help="Applica gli aggiornamenti ai fascicoli.")
    parser.add_argument("--report", default="", help="Percorso report JSON.")
    args = parser.parse_args()
    report = run_reclassification(
        data_root=Path(args.data_root),
        registry=Path(args.registry),
        tenants=set(args.tenant or []),
        apply=bool(args.apply),
    )
    output = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report:
        path = Path(args.report)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(output + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
