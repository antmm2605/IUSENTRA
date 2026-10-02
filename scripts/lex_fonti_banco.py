#!/usr/bin/env python3
"""Banco fonti di Lex: recall@5, recall@10 e MRR della ricerca Normattiva attuale (commit 50d9060) e della FTS.

Uso: python scripts/lex_fonti_banco.py [--errori]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.lex_fonti_banco.valutazione import esegui_banco, tabella  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--errori", action="store_true", help="elenca le domande in cui la ricerca FTS non trova l'articolo atteso nei primi 5")
    args = parser.parse_args()
    esito = esegui_banco()
    print(tabella(esito))
    if args.errori:
        classifiche = esito["ricerche"]["fts"]["classifiche"]
        for domanda, classifica in zip(esito["domande"], classifiche):
            attesi = [(a["codice"], a["articolo"]) for a in domanda["attesi"]]
            if not all(a in classifica[:5] for a in attesi):
                print(f"\n#{domanda['id']} {domanda['domanda']}\n  attesi: {attesi}\n  primi 5: {classifica[:5]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
