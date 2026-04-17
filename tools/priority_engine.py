from __future__ import annotations

import argparse

from pct.legal_coverage_pipeline import build_gap_queue, run_coverage_audit
from tools.legal_coverage_cli_common import add_db_args, build_repository, dump_payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Calcola priorità e restituisce i gap ordinati.")
    add_db_args(parser)
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    repository = build_repository(args)
    run_coverage_audit(repository)
    build_gap_queue(repository)
    dump_payload(repository.list_open_gaps(limit=args.limit))


if __name__ == "__main__":
    main()
