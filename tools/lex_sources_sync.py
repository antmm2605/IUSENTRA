from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from lex.sources.db import export_chunks_jsonl, init_db
from lex.sources.registry import load_sources
from lex.sources.runner import run_source


def copy_default_config(target: Path) -> None:
    src = PROJECT_ROOT / "config" / "lex_official_sources.example.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, target)
    print(f"Configurazione creata: {target}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Centro Fonti Ufficiali Lex - sincronizzazione fonti ufficiali")
    parser.add_argument("--config", default="config/lex_official_sources.example.json")
    parser.add_argument("--db", default="data/fonti_ufficiali/lex_sources.sqlite")
    parser.add_argument("--raw-dir", default="data/fonti_ufficiali/raw")
    parser.add_argument("--text-dir", default="data/fonti_ufficiali/text")
    parser.add_argument("--jsonl", default="data/fonti_ufficiali/index/lex_sources_chunks.jsonl")
    parser.add_argument("--init-config", action="store_true")
    parser.add_argument("--init-db", action="store_true")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--run")
    parser.add_argument("--run-all", action="store_true")
    parser.add_argument("--include-disabled", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--export-jsonl", action="store_true")
    args = parser.parse_args()

    config_path = Path(args.config)
    if args.init_config:
        copy_default_config(config_path)
        return 0

    if args.init_db:
        init_db(args.db)
        print(f"Database inizializzato: {args.db}")

    sources = load_sources(config_path)

    if args.list:
        print("Fonti configurate:")
        for s in sorted(sources, key=lambda x: (-x.priority, x.id)):
            state = "ON" if s.enabled else "OFF"
            print(f"- [{state}] {s.id:24s} {s.name} | connector={s.connector} | priority={s.priority}")
        return 0

    if args.run:
        selected = [s for s in sources if s.id == args.run]
        if not selected:
            print(f"Fonte non trovata: {args.run}", file=sys.stderr)
            return 2
        found, saved = run_source(selected[0], args.db, args.raw_dir, args.text_dir, dry_run=args.dry_run)
        print(f"Completato {args.run}: trovati={found}, salvati={saved}")

    if args.run_all:
        total_found = 0
        total_saved = 0
        for s in sorted(sources, key=lambda x: -x.priority):
            if not s.enabled and not args.include_disabled:
                continue
            found, saved = run_source(s, args.db, args.raw_dir, args.text_dir, dry_run=args.dry_run)
            total_found += found
            total_saved += saved
        print(f"Run completo: trovati={total_found}, salvati={total_saved}")

    if args.export_jsonl:
        output = export_chunks_jsonl(args.db, args.jsonl)
        print(f"JSONL esportato: {output}")

    if not any([args.init_db, args.run, args.run_all, args.export_jsonl]):
        parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
