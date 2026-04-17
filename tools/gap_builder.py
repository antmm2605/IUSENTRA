from __future__ import annotations

import argparse

from pct.legal_coverage_pipeline import build_gap_queue, run_coverage_audit
from tools.legal_coverage_cli_common import add_db_args, build_repository, dump_payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Rigenera la gap queue della coverage pipeline.")
    add_db_args(parser)
    parser.add_argument("--skip-audit", action="store_true")
    args = parser.parse_args()
    repository = build_repository(args)
    if not args.skip_audit:
        run_coverage_audit(repository)
    dump_payload(build_gap_queue(repository))


if __name__ == "__main__":
    main()
