from __future__ import annotations

import argparse
import json
from typing import Sequence

from pct.legal_update_pipeline import build_legal_update_pipeline


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m pct.legal_update_job",
        description="Esegue una singola unita della pipeline aggiornamenti legali.",
    )
    parser.add_argument("--intelligence-db", required=True)
    parser.add_argument("--giurisprudenza-db", default="")
    parser.add_argument("--source-code", default="")
    parser.add_argument("--publish-only", action="store_true")
    parser.add_argument("--publish-limit", type=int, default=1)
    parser.add_argument("--backfill-web-evidence", action="store_true")
    parser.add_argument("--backfill-limit", type=int, default=100)
    parser.add_argument("--backfill-max-seconds", type=int, default=0)
    parser.add_argument("--backfill-status", action="append", default=[])
    parser.add_argument("--backfill-include-closed", action="store_true")
    parser.add_argument("--backfill-include-open-data", action="store_true")
    parser.add_argument("--backfill-full-search", action="store_true")
    parser.add_argument("--backfill-query", default="")
    parser.add_argument("--backfill-review-id", action="append", type=int, default=[])
    parser.add_argument("--no-auto-publish", action="store_true")
    parser.add_argument("--local-ai-url", default="")
    parser.add_argument("--local-ai-model", default="mistral")
    parser.add_argument("--export-json", action="store_true")
    parser.add_argument("--mirror-giurisprudenza-json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    pipeline = build_legal_update_pipeline(
        args.intelligence_db,
        giurisprudenza_db_path=args.giurisprudenza_db,
        ai_base_url=args.local_ai_url,
        ai_model=args.local_ai_model,
        export_json_enabled=bool(args.export_json),
        mirror_giurisprudenza_json_enabled=bool(args.mirror_giurisprudenza_json),
    )

    if args.backfill_web_evidence:
        source_codes = [str(args.source_code or "").strip()] if str(args.source_code or "").strip() else None
        backfill = pipeline.backfill_web_verification_evidence(
            limit=max(1, int(args.backfill_limit or 1)),
            source_codes=source_codes,
            statuses=tuple(args.backfill_status or ()) or None,
            include_closed=bool(args.backfill_include_closed),
            include_open_data=bool(args.backfill_include_open_data),
            direct_only=not bool(args.backfill_full_search),
            max_seconds=max(0, int(args.backfill_max_seconds or 0)),
            query=str(args.backfill_query or "").strip(),
            review_ids=tuple(int(value) for value in args.backfill_review_id or [] if int(value or 0) > 0),
        )
        payload = {
            "ok": True,
            "mode": "backfill_web_evidence",
            "backfill": backfill,
            "dashboard": backfill.get("dashboard") or pipeline.dashboard_snapshot(),
        }
    elif args.publish_only:
        published = pipeline.publish_auto_news(limit=max(1, int(args.publish_limit or 1)))
        payload = {
            "ok": True,
            "mode": "publish",
            "published": published,
            "published_count": int((published or {}).get("count") or 0),
            "dashboard": pipeline.dashboard_snapshot(),
        }
    else:
        source_code = str(args.source_code or "").strip()
        if not source_code:
            raise SystemExit("--source-code e' obbligatorio senza --publish-only")
        report = pipeline.run_cycle(
            source_codes=[source_code],
            auto_publish=not bool(args.no_auto_publish),
        )
        payload = {
            "ok": True,
            "mode": "source",
            "source_code": source_code,
            "report": report,
            "processed": sum(int(row.get("processed") or 0) for row in report.get("reports") or []),
            "documents_found": sum(int(row.get("documents_found") or 0) for row in report.get("reports") or []),
            "dashboard": report.get("dashboard") or pipeline.dashboard_snapshot(),
        }

    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
