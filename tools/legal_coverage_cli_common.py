from __future__ import annotations

import argparse
import json
import sys

from tools.coverage_cli_base import add_db_args, build_base_parser, build_repository, require_positive_int

__all__ = [
    'add_db_args',
    'build_base_parser',
    'build_repository',
    'dump_payload',
    'require_positive_int',
]


def dump_payload(payload) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


def cli_main_guard(main_callable) -> None:
    try:
        main_callable()
    except KeyboardInterrupt:
        print('Operazione interrotta.', file=sys.stderr)
        raise SystemExit(130)
    except Exception as exc:
        print(f'Errore: {exc}', file=sys.stderr)
        raise SystemExit(1)
