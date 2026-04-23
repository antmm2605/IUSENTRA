from __future__ import annotations

from pct.legal_coverage_pipeline import build_gap_queue, run_coverage_audit
from tools.legal_coverage_cli_common import build_base_parser, build_repository, cli_main_guard, dump_payload


def main() -> None:
    parser = build_base_parser('Rigenera la gap queue della coverage pipeline.')
    parser.add_argument('--skip-audit', action='store_true')
    args = parser.parse_args()
    repository = build_repository(args)
    if not args.skip_audit:
        run_coverage_audit(repository)
    dump_payload(build_gap_queue(repository))


if __name__ == '__main__':
    cli_main_guard(main)
