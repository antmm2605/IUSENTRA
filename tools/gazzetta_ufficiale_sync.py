from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from lex.sources.db import export_chunks_jsonl, init_db
from lex.sources.models import SourceConfig
from lex.sources.runner import run_source


def build_source(max_issues: int, min_date: str = "") -> SourceConfig:
    return SourceConfig(
        id="gazzetta_ufficiale",
        name="Gazzetta Ufficiale",
        enabled=True,
        priority=95,
        connector="gazzetta_ufficiale",
        type="novita_normativa",
        refresh="daily",
        base_url="https://www.gazzettaufficiale.it/",
        topics=["novita_normativa", "gazzetta_ufficiale", "leggi", "decreti", "regolamenti"],
        settings={
            "series_pages": [
                {
                    "id": "serie_generale",
                    "name": "Serie Generale - ultimi 30 giorni",
                    "url": "https://www.gazzettaufficiale.it/30giorni/serie_generale",
                    "tipo_serie": "SG",
                }
            ],
            "max_issues": max_issues,
            "min_date": min_date,
            "only_tipo_serie": ["SG"],
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Sincronizza Gazzetta Ufficiale per il Centro Fonti Ufficiali Lex")
    parser.add_argument("--db", default="data/fonti_ufficiali/lex_sources.sqlite")
    parser.add_argument("--raw-dir", default="data/fonti_ufficiali/raw")
    parser.add_argument("--text-dir", default="data/fonti_ufficiali/text")
    parser.add_argument("--jsonl", default="data/fonti_ufficiali/index/lex_sources_chunks.jsonl")
    parser.add_argument("--max-issues", type=int, default=10)
    parser.add_argument("--min-date", default="", help="Formato YYYYMMDD, es. 20260401")
    parser.add_argument("--init-db", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--export-jsonl", action="store_true")
    args = parser.parse_args()

    if args.init_db:
        init_db(args.db)
        print(f"Database inizializzato: {args.db}")

    source = build_source(args.max_issues, args.min_date)
    found, saved = run_source(source, args.db, args.raw_dir, args.text_dir, dry_run=args.dry_run)
    print(json.dumps({"found": found, "saved": saved}, ensure_ascii=False, indent=2))

    if args.export_jsonl:
        out = export_chunks_jsonl(args.db, args.jsonl)
        print(f"JSONL esportato: {out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
