"""Ricerca esplicita nei metadati pubblici: nessun import o lettura dei fascicoli."""
import logging
import os
import sqlite3
from contextlib import closing
from functools import lru_cache
from pathlib import Path
from threading import Lock


class InvalidSearch(ValueError):
    pass


_SEARCH_LOCK = Lock()


@lru_cache(maxsize=1)
def _reranker(path):
    from pct.openga_reranker import RerankerOpenGALocale
    return RerankerOpenGALocale(path)


def search_openga(payload, config):
    from lex.ricerca_giuridica.embedding import OllamaEmbedder
    from pct.openga_catalogo import CatalogoOpenGA

    query = payload.get("q")
    if not isinstance(query, str) or not query.strip() or len(query) > 1000:
        raise ValueError("Inserisci una ricerca di massimo 1.000 caratteri.")
    query = query.strip()
    try:
        values = [payload.get(key) for key in ("dal", "al")]
        if any(isinstance(v, (bool, float)) for v in values):
            raise ValueError()
        dal, al = int(values[0] or 1900), int(values[1] or 2100)
    except (ValueError, TypeError):
        raise ValueError("Indica anni validi.") from None
    if not 1900 <= dal <= al <= 2100:
        raise ValueError("Controlla l'intervallo degli anni.")
    sede = payload.get("sede", "")
    if not isinstance(sede, str) or len(sede) > 100:
        raise InvalidSearch("Sede non valida.")
    semantic = payload.get("semantica", False)
    if not isinstance(semantic, bool):
        raise InvalidSearch("Modalità di ricerca non valida.")
    data_dir = Path(config.get("DATA_DIR") or os.getenv("PCT_DATA_ROOT") or "/data")
    path = Path(config.get("OPENGA_CATALOGO_DB") or os.getenv("IUSENTRA_OPENGA_CATALOGO_DB") or data_dir / "fonti_ufficiali/openga/catalogo.db")
    empty = {"ok": False, "risultati": [], "evidence_scope": "metadata_only"}
    if not path.is_file():
        return {**empty, "message": "Il catalogo amministrativo non è ancora disponibile su questa installazione."}
    # Una sola inferenza per processo: niente code illimitate o interruzioni di altri lavori.
    if not _SEARCH_LOCK.acquire(blocking=False):
        return {**empty, "message": "Una ricerca è già in corso. Riprova fra poco."}
    try:
        catalog = CatalogoOpenGA(path)
        options = {"sede": sede.strip(), "dal": dal, "al": al, "limit": 10}
        if not sede.strip():
            from pct.openga_query import sede_richiesta
            with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
                offices = dict(connection.execute("SELECT DISTINCT sede,nome_sede FROM attive"))
            # Stesso riconoscimento della sede per tutti i canali, senza dedurre la competenza.
            options["sede"] = tuple(sede_richiesta(query, offices))
        failed = False
        if semantic:
            try:
                model_path = config.get("OPENGA_RERANKER_DIR") or os.getenv("IUSENTRA_OPENGA_RERANKER_DIR")
                if not model_path:
                    raise RuntimeError("Classificatore non configurato")
                ranker = _reranker(str(Path(model_path).resolve()))
                result = catalog.cerca_fusa(query, **options,
                    embedder=OllamaEmbedder(timeout=10, tentativi=1), reranker=ranker)
                failed = bool(result.get("errore_semantico") or result.get("errore_reranker"))
                rows = result["risultati"]
            except (OSError, ValueError, RuntimeError, ImportError):
                failed = True
                rows = catalog.cerca(query, **options)
        else:
            rows = catalog.cerca(query, **options)
        # Nessun trace, percorso locale, query privata o punteggio interno nel payload UI.
        fields = {"relazione_id", "decisione_id", "organo_giudicante", "numero_sentenza",
                  "anno_sentenza", "numero_ricorso", "oggetto", "esito", "resource_id",
                  "resource_sha256", "official_search_url", "evidence_scope", "fonte_codice"}
        return {"ok": True, "risultati": [{k: v for k, v in row.items() if k in fields} for row in rows],
                "evidence_scope": "metadata_only", "semantic_available": semantic and not failed,
                "message": "Ricerca per significato non disponibile; sono mostrati i risultati per parole." if failed else ""}
    except (sqlite3.Error, OSError, RuntimeError, ValueError, ImportError):
        logging.getLogger(__name__).warning("Ricerca pubblica OpenGA non disponibile")
        return {**empty, "message": "Ricerca amministrativa non disponibile. Riprova più tardi."}
    finally:
        _SEARCH_LOCK.release()
