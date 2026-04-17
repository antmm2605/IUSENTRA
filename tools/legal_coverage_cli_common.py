from __future__ import annotations

import argparse
import json

from pct.legal_coverage_repository import CoverageDbConfig, PostgresCoverageRepository


def add_db_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--dsn", default="")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=5432)
    parser.add_argument("--dbname", default="iusentra")
    parser.add_argument("--user", default="postgres")
    parser.add_argument("--password", default="postgres")


def build_repository(args: argparse.Namespace) -> PostgresCoverageRepository:
    return PostgresCoverageRepository(
        CoverageDbConfig(
            dsn=str(getattr(args, "dsn", "") or ""),
            host=str(getattr(args, "host", "localhost") or "localhost"),
            port=int(getattr(args, "port", 5432) or 5432),
            dbname=str(getattr(args, "dbname", "iusentra") or "iusentra"),
            user=str(getattr(args, "user", "postgres") or "postgres"),
            password=str(getattr(args, "password", "postgres") or "postgres"),
            explicit=True,
        )
    )


def dump_payload(payload) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
