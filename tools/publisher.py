from __future__ import annotations

import argparse

from pct.legal_coverage_pipeline import publish_approved_drafts
from tools.legal_coverage_cli_common import add_db_args, build_repository, dump_payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Pubblica in SQL i draft approvati.")
    add_db_args(parser)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--auto-only", action="store_true")
    args = parser.parse_args()
    dump_payload(
        publish_approved_drafts(
            build_repository(args),
            limit=args.limit,
            auto_only=args.auto_only,
            apply_to_db=True,
        )
    )


if __name__ == "__main__":
    main()
