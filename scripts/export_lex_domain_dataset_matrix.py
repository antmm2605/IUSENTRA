"""Espone in sola lettura la matrice domini software/dataset per Lex AI."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = ROOT / "docs" / "lex_software_domain_dataset_matrix.json"


def load_matrix() -> dict[str, Any]:
    with MATRIX_PATH.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("La matrice Lex deve essere un oggetto JSON.")
    return payload


def select_domain(matrix: dict[str, Any], domain_id: str) -> dict[str, Any]:
    for domain in matrix.get("domains", []):
        if domain.get("id") == domain_id:
            return domain
    raise KeyError(f"Dominio Lex non trovato: {domain_id}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Stampa la matrice read-only dei domini IUSENTRA che Lex deve "
            "conoscere per dataset e RAG. Non avvia training e non legge dati studio."
        )
    )
    parser.add_argument("--domain", default="", help="Restituisce un solo dominio per id.")
    parser.add_argument("--pretty", action="store_true", help="Formatta il JSON con indentazione.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    matrix = load_matrix()
    payload: dict[str, Any] = select_domain(matrix, args.domain) if args.domain else matrix
    print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0


if __name__ == "__main__":  # pragma: no cover
    try:
        raise SystemExit(main())
    except KeyError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)
