from __future__ import annotations

import argparse

from pct.legal_coverage_pipeline import run_coverage_audit
from tools.legal_coverage_cli_common import add_db_args, build_repository, dump_payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Esegue l'auditor di copertura legale.")
    add_db_args(parser)
    args = parser.parse_args()
    dump_payload(run_coverage_audit(build_repository(args)))


if __name__ == "__main__":
    main()
