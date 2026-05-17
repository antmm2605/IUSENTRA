"""CLI governata per preparare dataset Lex da Documenti AI Fascicolo."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from lex.dataset import (
    ChunkingOptions,
    QAGenerationPolicy,
    StudioDatasetBatchOptions,
    build_studio_dataset_batch,
    load_document_ai_json_documents,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Prepara manifest, chunk e Q&A candidate Lex da testi gia' estratti "
            "e autorizzati di Documenti AI Fascicolo. Non avvia training."
        )
    )
    parser.add_argument("--tenant-id", required=True, help="Tenant/studio da elaborare.")
    parser.add_argument(
        "--document-ai-json",
        required=True,
        help="Percorso tenant-aware di documenti_ai.json.",
    )
    parser.add_argument("--fascicolo-id", action="append", default=[], help="Limita il batch a uno o piu' fascicoli.")
    parser.add_argument("--max-documents", type=int, default=None, help="Limite massimo di documenti da leggere.")
    parser.add_argument("--output-dir", default="", help="Cartella artefatti. Richiesta con --write.")
    parser.add_argument("--write", action="store_true", help="Scrive gli artefatti. Senza questo flag esegue dry-run.")
    parser.add_argument(
        "--allow-sensitive-export",
        action="store_true",
        help="Consente la scrittura di chunk/Q&A/export se il batch contiene dati sensibili.",
    )
    parser.add_argument(
        "--export-pending-review",
        action="store_true",
        help="Esporta anche Q&A non approvate in file dataset candidate. Richiede revisione umana prima del training.",
    )
    parser.add_argument(
        "--format",
        dest="formats",
        action="append",
        choices=["alpaca", "sharegpt", "multilingual"],
        default=[],
        help="Formato dataset da generare. Ripetibile; default: tutti.",
    )
    parser.add_argument("--file-type", choices=["jsonl", "json", "csv"], default="jsonl")
    parser.add_argument("--max-chars", type=int, default=1200)
    parser.add_argument("--overlap-chars", type=int, default=120)
    parser.add_argument("--min-chars", type=int, default=40)
    parser.add_argument("--min-qa-chars", type=int, default=80)
    parser.add_argument("--max-pairs-per-chunk", type=int, default=1)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    output_dir = Path(args.output_dir) if args.output_dir else None
    if args.write and output_dir is None:
        print("--output-dir e' richiesto quando si usa --write.", file=sys.stderr)
        return 2

    documents = load_document_ai_json_documents(
        args.document_ai_json,
        tenant_id=args.tenant_id,
        fascicolo_ids=args.fascicolo_id,
        max_documents=args.max_documents,
    )
    options = StudioDatasetBatchOptions(
        tenant_id=args.tenant_id,
        fascicolo_ids=tuple(args.fascicolo_id or ()),
        max_documents=args.max_documents,
        dry_run=not args.write,
        allow_sensitive_export=bool(args.allow_sensitive_export),
        include_pending_review_export=bool(args.export_pending_review),
        dataset_formats=tuple(args.formats or ("alpaca", "sharegpt", "multilingual")),
        file_type=args.file_type,
        chunking_options=ChunkingOptions(
            max_chars=args.max_chars,
            overlap_chars=args.overlap_chars,
            min_chars=args.min_chars,
        ),
        qa_policy=QAGenerationPolicy(
            max_pairs_per_chunk=args.max_pairs_per_chunk,
            min_chunk_chars=args.min_qa_chars,
        ),
    )
    result = build_studio_dataset_batch(documents, options, output_dir=output_dir)
    print(json.dumps(result.summary(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
