from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from legal_ocr import LegalOcrConfig, LegalOcrEvidenceStore, LegalOcrPipeline  # noqa: E402
from legal_ocr.unlimited.batch import build_jobs_from_target, run_batch  # noqa: E402
from legal_ocr.unlimited.config import UnlimitedOcrSettings  # noqa: E402
from legal_ocr.unlimited.qa import answer_questions_from_text, default_legal_questions  # noqa: E402


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    parser = argparse.ArgumentParser(
        description=(
            "Benchmark IUSENTRA per Unlimited-OCR: lettura PDF/immagini, fallback corrente "
            "e domande Lex fondate sul testo letto."
        )
    )
    parser.add_argument("target", help="PDF, immagine, TXT, ZIP o cartella da processare.")
    parser.add_argument("--tenant", required=True, help="Identificativo tenant/studio.")
    parser.add_argument("--storage-root", default="./data/legal_document_evidence/unlimited_ocr_benchmark", help="Archivio evidenze OCR benchmark.")
    parser.add_argument("--fallback", default="native-text-fallback", help="Motore fallback corrente.")
    parser.add_argument("--questions-file", default="", help="File JSON/lista testo con domande da porre sul contenuto OCR.")
    parser.add_argument("--output-report", default="", help="Percorso JSON report. Se omesso stampa solo stdout/JSON.")
    parser.add_argument("--run-page-batch", action="store_true", help="Esegue anche benchmark concorrente stile repo Baidu su pagine/immagini.")
    parser.add_argument("--batch-output-dir", default="", help="Cartella output Markdown del benchmark concorrente.")
    parser.add_argument("--require-unlimited", action="store_true", help="Fallisce se l'evidenza finale non usa Unlimited-OCR.")
    parser.add_argument("--json", action="store_true", help="Stampa report JSON completo.")
    args = parser.parse_args()

    questions = _load_questions(args.questions_file)
    pipeline_report = _run_pipeline(args, questions)
    batch_report: dict[str, Any] = {}
    if args.run_page_batch:
        batch_report = _run_page_batch(args)
    report = {
        "ok": pipeline_report["ok"] and (not batch_report or bool(batch_report.get("ok"))),
        "created_at": datetime.now().astimezone().isoformat(),
        "target": str(Path(args.target).resolve()),
        "tenant_id": args.tenant,
        "engine": "unlimited-ocr",
        "policy": {
            "mode": "self_hosted_first",
            "fallback": args.fallback,
            "no_silent_success": True,
            "lex_answers_require_document_citation": True,
        },
        "pipeline": pipeline_report,
        "batch": batch_report,
    }
    if args.require_unlimited and not pipeline_report.get("unlimited_selected"):
        report["ok"] = False
        report["blocking_reason"] = "Unlimited-OCR non è stato selezionato: controllare flag, endpoint o qualità risposta."
    if args.output_report:
        target = Path(args.output_report)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_human(report)
    return 0 if report["ok"] else 2


def _run_pipeline(args: argparse.Namespace, questions: list[str]) -> dict[str, Any]:
    store = LegalOcrEvidenceStore(args.storage_root, args.tenant)
    pipeline = LegalOcrPipeline(
        LegalOcrConfig(
            tenant_id=args.tenant,
            primary_engine="unlimited-ocr",
            fallback_engine=args.fallback,
        ),
        store,
    )
    evidences = pipeline.run_path(args.target, tenant_id=args.tenant, source_type="unlimited-ocr-benchmark")
    items: list[dict[str, Any]] = []
    all_text_parts: list[str] = []
    for evidence in evidences:
        text = _read_store_text(args.storage_root, evidence.get("ocr_text_path"))
        all_text_parts.append(text)
        qa = answer_questions_from_text(text, questions or None)
        items.append(
            {
                "run_id": evidence.get("run_id"),
                "selected_engine": evidence.get("selected_engine"),
                "engine_version": evidence.get("engine_version"),
                "metrics": evidence.get("metrics"),
                "qc": evidence.get("qc"),
                "evidence_path": evidence.get("evidence_path"),
                "ocr_text_path": evidence.get("ocr_text_path"),
                "lex_export_path": (evidence.get("lex_export") or {}).get("path"),
                "legal_entities": evidence.get("legal_entities"),
                "qa": qa,
            }
        )
    combined_qa = answer_questions_from_text("\n\n".join(all_text_parts), questions or None)
    unlimited_selected = any(_is_valid_unlimited_selection(item) for item in items)
    return {
        "ok": bool(items) and combined_qa["answered"] > 0,
        "evidence_count": len(items),
        "unlimited_selected": unlimited_selected,
        "questions": questions or default_legal_questions(),
        "combined_qa": combined_qa,
        "items": items,
    }


def _is_valid_unlimited_selection(item: dict[str, Any]) -> bool:
    if str(item.get("selected_engine") or "") != "unlimited-ocr":
        return False
    selected_version = str(((item.get("engine_version") or {}).get("selected")) or "").lower()
    if any(marker in selected_version for marker in ("not-ready", ":error", ":empty", ":no-pages")):
        return False
    attempts = ((item.get("qc") or {}).get("engine_attempts") or [])
    selected_attempts = [
        attempt
        for attempt in attempts
        if str(attempt.get("engine") or "") == "unlimited-ocr"
        and str(attempt.get("version") or "") == str(((item.get("engine_version") or {}).get("selected")) or "")
    ]
    if selected_attempts:
        return int(selected_attempts[0].get("token_count") or 0) > 0
    return bool((item.get("metrics") or {}).get("avg_confidence"))


def _run_page_batch(args: argparse.Namespace) -> dict[str, Any]:
    settings = UnlimitedOcrSettings.from_env()
    readiness = settings.readiness()
    if not readiness["ok"]:
        return {
            "ok": False,
            "skipped": True,
            "reason": readiness.get("reason"),
            "warnings": readiness.get("warnings") or [],
        }
    mode, jobs = build_jobs_from_target(args.target, output_dir=args.batch_output_dir or None)
    result = run_batch(jobs, settings=settings)
    return {
        "ok": result.ok,
        "mode": mode,
        "total_jobs": result.total_jobs,
        "successful_jobs": result.successful_jobs,
        "total_chars": result.total_chars,
        "wall_time_seconds": result.wall_time_seconds,
        "chars_per_second": result.chars_per_second,
        "results": [
            {
                "index": item.get("index"),
                "image_path": item.get("image_path"),
                "output_path": item.get("output_path"),
                "ok": item.get("ok"),
                "chars": item.get("chars"),
                "elapsed_ms": item.get("elapsed_ms"),
                "attempts": item.get("attempts"),
                "error": item.get("error"),
            }
            for item in result.results
        ],
    }


def _load_questions(path: str) -> list[str]:
    if not path:
        return []
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"File domande non trovato: {path}")
    raw = source.read_text(encoding="utf-8")
    if source.suffix.lower() == ".json":
        data = json.loads(raw)
        if isinstance(data, list):
            return [str(item.get("question") if isinstance(item, dict) else item).strip() for item in data if str(item).strip()]
        if isinstance(data, dict) and isinstance(data.get("questions"), list):
            return [str(item.get("question") if isinstance(item, dict) else item).strip() for item in data["questions"] if str(item).strip()]
    return [line.strip() for line in raw.splitlines() if line.strip()]


def _read_store_text(storage_root: str, relative_path: object) -> str:
    if not relative_path:
        return ""
    path = Path(storage_root).resolve() / str(relative_path)
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _print_human(report: dict[str, Any]) -> None:
    pipeline = report.get("pipeline") or {}
    combined = pipeline.get("combined_qa") or {}
    print("Benchmark Unlimited-OCR + Lex")
    print(f"Stato: {'OK' if report.get('ok') else 'DA VERIFICARE'}")
    print(f"Evidenze OCR: {pipeline.get('evidence_count', 0)}")
    print(f"Unlimited-OCR selezionato: {'sì' if pipeline.get('unlimited_selected') else 'no'}")
    print(f"Domande risposte: {combined.get('answered', 0)}/{combined.get('total', 0)} ({combined.get('coverage_pct', 0)}%)")
    for answer in combined.get("answers") or []:
        print(f"- {answer.get('question')}")
        print(f"  {answer.get('status')}: {answer.get('answer')}")
    if report.get("blocking_reason"):
        print(f"Blocco: {report['blocking_reason']}")


if __name__ == "__main__":
    raise SystemExit(main())
