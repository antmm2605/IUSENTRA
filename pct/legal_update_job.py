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

    if args.publish_only:
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
