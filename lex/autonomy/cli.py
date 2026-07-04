"""CLI del ciclo di apprendimento autonomo di Lex.

Uso tipico (offline, deterministico, zero rete):

    python scripts/lex_autonomous_cycle.py \
        --config examples/lex_autonomous_config.json \
        --samples examples/legal_samples.json \
        --memory-dir data/lex_memory --report text

Exit code: 0 successo · 1 errore di configurazione/input · 2 errore fonti ·
3 errore del ciclo. La modalità web parte SOLO con `mode=web`, `allow_web=true`
e allowlist non vuota nel config (o `--allow-web` che pretende comunque un
config coerente): default OFF.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from lex.autonomy.autonomous_cycle import run_autonomous_cycle
from lex.autonomy.discovery import ConfigurableWebSearchProvider, SearchProvider, StaticSearchProvider
from lex.autonomy.report import render_json, render_text
from lex.autonomy.safety import CycleConfigError, CycleError, SourceAccessError, validate_cycle_config
from lex.learning.models import LegalSourceSample
from lex.sources.polite_fetcher import PoliteFetcher


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="lex_autonomous_cycle",
        description="Esegue il ciclo di apprendimento autonomo governato di Lex (deterministico, fail-closed).",
    )
    parser.add_argument("--config", required=True, help="Percorso del file di configurazione JSON del ciclo.")
    parser.add_argument("--samples", default="", help="Percorso del file JSON con i campioni legali di partenza.")
    parser.add_argument("--memory-dir", default="", help="Directory della memoria JSONL (override del config).")
    parser.add_argument("--report", choices=("text", "json"), default="text", help="Formato del report finale.")
    parser.add_argument("--dry-run", action="store_true", help="Esegue senza scrivere nulla su disco.")
    parser.add_argument(
        "--allow-web",
        action="store_true",
        help="Consente la modalità web SOLO se il config è già coerente (mode=web, allowlist non vuota).",
    )
    args = parser.parse_args(argv)

    try:
        raw_config = _load_json(Path(args.config), label="configurazione")
        if args.allow_web:
            raw_config = dict(raw_config)
            raw_config["allow_web"] = True
        config = validate_cycle_config(raw_config)
        if args.memory_dir:
            config.memory_dir = args.memory_dir
        if args.dry_run:
            config.dry_run = True
        samples = _load_samples(Path(args.samples)) if args.samples else []
    except CycleConfigError as exc:
        print(f"Errore di configurazione: {exc}", file=sys.stderr)
        return 1
    except (OSError, ValueError) as exc:
        print(f"Errore di input: {exc}", file=sys.stderr)
        return 1

    provider: SearchProvider
    fetcher: PoliteFetcher | None = None
    if config.mode == "web":
        provider = ConfigurableWebSearchProvider(limit_results=config.max_sources)
        fetcher = PoliteFetcher(
            min_interval_seconds=config.min_interval_seconds,
            timeout_seconds=config.timeout_seconds,
            max_bytes=config.max_bytes,
            respect_robots=config.respect_robots,
        )
    else:
        provider = StaticSearchProvider(config.offline_results)

    try:
        result = run_autonomous_cycle(config=config, samples=samples, search_provider=provider, fetcher=fetcher)
    except SourceAccessError as exc:
        print(f"Errore fonti: {exc}", file=sys.stderr)
        return 2
    except CycleError as exc:
        print(f"Errore del ciclo: {exc}", file=sys.stderr)
        return 3
    except Exception as exc:  # difesa finale: mai traceback grezzo all'utente
        print(f"Errore del ciclo: {exc}", file=sys.stderr)
        return 3

    print(render_json(result) if args.report == "json" else render_text(result))
    return 0


def _load_json(path: Path, *, label: str) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise OSError(f"file di {label} non trovato: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"file di {label} non è JSON valido: {path} ({exc})") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"file di {label} deve contenere un oggetto JSON: {path}")
    return payload


def _load_samples(path: Path) -> list[LegalSourceSample]:
    payload = _load_json(path, label="campioni")
    rows = payload.get("samples")
    if not isinstance(rows, list):
        raise ValueError(f"file campioni senza lista 'samples': {path}")
    samples = [LegalSourceSample.from_dict(row) for row in rows if isinstance(row, dict)]
    if not samples:
        raise ValueError(f"file campioni vuoto: {path}")
    return samples


__all__ = ["main"]


if __name__ == "__main__":  # pragma: no cover - eseguibile anche come modulo
    raise SystemExit(main())
