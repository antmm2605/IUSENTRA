from __future__ import annotations

import argparse
import os
from typing import Iterable, Sequence

from pct.legal_coverage_repository import CoverageDbConfig, PostgresCoverageRepository


def add_db_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument('--dsn', default=os.getenv('IUSENTRA_COVERAGE_DSN', ''))
    parser.add_argument('--host', default=os.getenv('IUSENTRA_DB_HOST', 'localhost'))
    parser.add_argument('--port', type=int, default=int(os.getenv('IUSENTRA_DB_PORT', '5432')))
    parser.add_argument('--dbname', default=os.getenv('IUSENTRA_DB_NAME', 'iusentra'))
    parser.add_argument('--user', default=os.getenv('IUSENTRA_DB_USER', 'postgres'))
    parser.add_argument('--password', default=os.getenv('IUSENTRA_DB_PASSWORD', ''))


def build_base_parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    add_db_args(parser)
    return parser


def build_repository(args: argparse.Namespace) -> PostgresCoverageRepository:
    password = str(getattr(args, 'password', '') or os.getenv('IUSENTRA_DB_PASSWORD', '')).strip()
    dsn = str(getattr(args, 'dsn', '') or os.getenv('IUSENTRA_COVERAGE_DSN', '')).strip()
    if not dsn and not password:
        raise ValueError(
            'Password database non configurata. Usa --password oppure imposta IUSENTRA_DB_PASSWORD.'
        )
    return PostgresCoverageRepository(
        CoverageDbConfig(
            dsn=dsn,
            host=str(getattr(args, 'host', 'localhost') or 'localhost'),
            port=int(getattr(args, 'port', 5432) or 5432),
            dbname=str(getattr(args, 'dbname', 'iusentra') or 'iusentra'),
            user=str(getattr(args, 'user', 'postgres') or 'postgres'),
            password=password,
            explicit=True,
        )
    )


def require_positive_int(value: int | None, name: str) -> int:
    normalized = int(value or 0)
    if normalized <= 0:
        raise ValueError(f'{name} deve essere maggiore di zero.')
    return normalized
