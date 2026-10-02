#!/usr/bin/env python3
"""Banco fonti di Lex: recall@5, recall@10 e MRR della ricerca Normattiva attuale (commit 50d9060) e della FTS.

Uso: python scripts/lex_fonti_banco.py [--errori] [--ollama]

Colonne: attuale (50d9060), fts (lessicale), semantica e ibrida (embedding finto deterministico di
default; con --ollama l'embedding reale se Ollama e' raggiungibile, altrimenti salta con un messaggio).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.lex_fonti_banco.valutazione import esegui_banco, tabella  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--errori", action="store_true", help="elenca le domande in cui la ricerca scelta non trova l'articolo atteso nei primi 5")
    parser.add_argument("--ollama", action="store_true", help="usa embeddinggemma reale (LEX_EMBED_MODEL) invece dell'embedding finto")
    parser.add_argument("--classifica", default="fts", help="ricerca per --errori (fts, semantica, ibrida)")
    args = parser.parse_args()
    from lex.ricerca_giuridica.embedding import EmbedderFinto, OllamaEmbedder

    embedder = EmbedderFinto(256)
    if args.ollama:
        reale = OllamaEmbedder(timeout=60.0)
        try:
            reale.embed(["prova"])
            embedder = reale
        except Exception as exc:
            print(f"Ollama non raggiungibile ({reale.url}, {reale.modello}): {exc}\nColonne semantica/ibrida con embedding reale saltate.")
            embedder = None
    esito = esegui_banco(embedder=embedder)
    if embedder is not None:
        print(f"Embedding: {embedder.modello}" + (" (finto: misura la pipeline, non la semantica)" if isinstance(embedder, EmbedderFinto) else ""))
    print(tabella(esito))
    if args.errori:
        classifiche = esito["ricerche"].get(args.classifica, esito["ricerche"]["fts"])["classifiche"]
        for domanda, classifica in zip(esito["domande"], classifiche):
            attesi = [(a["codice"], a["articolo"]) for a in domanda["attesi"]]
            if not all(a in classifica[:5] for a in attesi):
                print(f"\n#{domanda['id']} {domanda['domanda']}\n  attesi: {attesi}\n  primi 5: {classifica[:5]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
