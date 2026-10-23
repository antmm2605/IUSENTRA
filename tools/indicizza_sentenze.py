"""Costruzione locale esplicita dell'indice candidato, senza attivazione."""

import argparse
import json

from lex.ricerca_giuridica.embedding import OllamaEmbedder
from pct.giurisprudenza_semantica import costruisci


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", required=True)
    p.add_argument("--folder")
    p.add_argument("--massimo", type=int)
    p.add_argument("--cache-pubblica")
    p.add_argument("--batch", type=int, default=16)
    args = p.parse_args()
    print(
        json.dumps(
            costruisci(
                args.db,
                folder=args.folder,
                massimo=args.massimo,
                batch=args.batch,
                cache_pubblica=args.cache_pubblica,
                embedder=OllamaEmbedder(),
            ),
            indent=2,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
