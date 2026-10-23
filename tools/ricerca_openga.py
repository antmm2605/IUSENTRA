"""Ricerca esplicita OpenGA: solo lettura, canali separati e stato semantico visibile."""

import argparse
import json

from lex.ricerca_giuridica.embedding import OllamaEmbedder
from pct.openga_catalogo import CatalogoOpenGA


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query")
    parser.add_argument("--db", required=True)
    parser.add_argument("--sede", default="")
    parser.add_argument("--dal", type=int, default=1900)
    parser.add_argument("--al", type=int, default=2100)
    parser.add_argument("--limite", type=int, default=10, choices=range(1, 101))
    parser.add_argument("--semantica", action="store_true")
    parser.add_argument("--lista-unica", action="store_true", help="Restituisce una sola lista ordinata")
    parser.add_argument("--reranker-dir", help="Cartella locale del classificatore con manifesto verificato")
    parser.add_argument("--timeout", type=float, default=30)
    args = parser.parse_args(argv)
    if not args.query.strip() or args.dal > args.al or not 0 < args.timeout <= 120:
        parser.error("Domanda, intervallo anni o timeout non validi")
    if args.lista_unica and not args.semantica:
        parser.error("La lista unica richiede --semantica")
    if args.reranker_dir and not args.lista_unica:
        parser.error("Il classificatore richiede --lista-unica e --semantica")
    catalog = CatalogoOpenGA(args.db)
    try:
        kwargs = dict(sede=args.sede, dal=args.dal, al=args.al, limit=args.limite)
        if args.lista_unica:
            reranker = None
            model_error = None
            if args.reranker_dir:
                from pct.openga_reranker import RerankerOpenGALocale
                try:
                    reranker = RerankerOpenGALocale(args.reranker_dir)
                except (OSError, ValueError, RuntimeError, ImportError) as exc:
                    model_error = str(exc)
            if model_error:
                result = {"modalita": "solo_lessicale_fallback_classificatore",
                          "risultati": catalog.cerca(args.query, **kwargs),
                          "errore_semantico": None, "errore_reranker": model_error,
                          "evidence_scope": "metadata_only"}
            else:
                result = catalog.cerca_fusa(args.query, **kwargs,
                            embedder=OllamaEmbedder(timeout=args.timeout, tentativi=1), reranker=reranker)
        elif args.semantica:
            result = catalog.cerca_canali(
                args.query, **kwargs, embedder=OllamaEmbedder(timeout=args.timeout, tentativi=1)
            )
        else:
            result = {
                "modalita": "solo_lessicale",
                "limite_per_canale": args.limite,
                "lessicali": catalog.cerca(args.query, **kwargs, semantica=False),
                "semantici_aggiuntivi": [],
                "errore_semantico": None,
                "evidence_scope": "metadata_only",
            }
    except (OSError, ValueError, RuntimeError, ImportError) as exc:
        print(json.dumps({"errore": str(exc), "evidence_scope": "metadata_only"}, ensure_ascii=False))
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 2 if result.get("errore_semantico") or result.get("errore_reranker") else 0


if __name__ == "__main__":
    raise SystemExit(main())
