from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from legal_ocr import LegalOcrConfig, LegalOcrEvidenceStore, LegalOcrPipeline  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Esegue OCR legal-grade IUSENTRA con evidenze immutabili.")
    parser.add_argument("target", help="File, ZIP o cartella da processare.")
    parser.add_argument("--tenant", required=True, help="Identificativo tenant/studio.")
    parser.add_argument("--storage-root", default="./data/legal_document_evidence/legal_ocr_cli", help="Radice evidenze OCR.")
    parser.add_argument("--primary", default="tesseract", help="Engine OCR primario.")
    parser.add_argument("--fallback", default="native-text-fallback", help="Engine OCR fallback.")
    parser.add_argument("--allow-cloud", action="store_true", help="Consente engine cloud configurati per il tenant.")
    parser.add_argument("--document-id", default="", help="ID documento IUSENTRA.")
    parser.add_argument("--fascicolo-id", default="", help="ID fascicolo IUSENTRA.")
    parser.add_argument("--json", action="store_true", help="Stampa output JSON completo.")
    args = parser.parse_args()

    pipeline = LegalOcrPipeline(
        LegalOcrConfig(
            tenant_id=args.tenant,
            primary_engine=args.primary,
            fallback_engine=args.fallback,
            local_first_only=not args.allow_cloud,
        ),
        LegalOcrEvidenceStore(args.storage_root, args.tenant),
    )
    evidences = pipeline.run_path(args.target, tenant_id=args.tenant, fascicolo_id=args.fascicolo_id, document_id=args.document_id)
    summary = {
        "tenant_id": args.tenant,
        "target": str(Path(args.target).resolve()),
        "count": len(evidences),
        "evidences": [
            {
                "run_id": item.get("run_id"),
                "document_id": item.get("document_id"),
                "parent_run_id": item.get("parent_run_id"),
                "selected_engine": item.get("selected_engine"),
                "engine_version": item.get("engine_version"),
                "metrics": item.get("metrics"),
                "hil_required": (item.get("qc") or {}).get("hil_required"),
                "hil_reasons": (item.get("qc") or {}).get("hil_reasons") or [],
                "regex_summary": item.get("regex_summary"),
                "evidence_path": item.get("evidence_path"),
                "ocr_text_path": item.get("ocr_text_path"),
                "lex_export_path": (item.get("lex_export") or {}).get("path"),
                "notification_proposals": len(item.get("notification_proposals") or []),
            }
            for item in evidences
        ],
    }
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"OCR legal-grade completato: {summary['count']} evidenze")
        for item in summary["evidences"]:
            metrics = item.get("metrics") or {}
            print(
                f"- run_id={item['run_id']} engine={item['selected_engine']} "
                f"conf={metrics.get('avg_confidence')} low={metrics.get('pct_tokens_<0.75')} "
                f"HIL={item['hil_required']}"
            )
            print(f"  evidence={item['evidence_path']}")
            print(f"  text={item['ocr_text_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
