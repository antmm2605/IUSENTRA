from __future__ import annotations

from pct.legal_coverage_pipeline import run_coverage_audit
from tools.legal_coverage_cli_common import build_base_parser, build_repository, cli_main_guard, dump_payload


def main() -> None:
    parser = build_base_parser("Esegue l'auditor di copertura legale.")
    args = parser.parse_args()
    dump_payload(run_coverage_audit(build_repository(args)))


if __name__ == '__main__':
    cli_main_guard(main)
