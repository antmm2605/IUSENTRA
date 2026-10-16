"""Cataloghi pubblici Normattiva: consultazione degli indici già disponibili.

Non costruisce indici, non importa fonti e non attesta copertura o vigenza.
Le ispezioni con db_path esplicito restano nella procedura nativa esistente.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path


class NormativaIndexUnavailable(RuntimeError):
    """Nessun indice consultabile: non avviare una scansione nella richiesta."""


DIAGNOSTICS = {
    "normativa_index_unavailable": "Indice Normattiva non disponibile: la ricerca locale non è stata eseguita.",
    "normativa_library_scope": "Consultata la biblioteca di codici e leggi acquisiti; l'archivio generale non è ancora indicizzato.",
    "normativa_library_supplement": "Consultata anche la biblioteca di codici e leggi acquisiti per il riferimento non reperito nell'archivio generale.",
}


def diagnostic_messages(codes) -> list[str]:
    return list(dict.fromkeys(DIAGNOSTICS[code] for code in codes if code in DIAGNOSTICS))


def _indexed(path: Path) -> bool:
    from lex.ricerca_giuridica.indice_fts import indice_fts_presente

    try:
        if not path.is_file():
            return False
        with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=0.25)) as conn:
            return indice_fts_presente(conn)
    except (sqlite3.Error, OSError) as exc:
        raise NormativaIndexUnavailable(
            "L'indice Normattiva non è consultabile: ricerca locale non completata."
        ) from exc


def select_runtime_catalog(general: Path) -> tuple[Path, str]:
    if _indexed(general):
        return general, "archivio_generale"
    library = general.with_name("codici_leggi.sqlite")
    if library != general and _indexed(library):
        return library, "biblioteca_codici_leggi"
    raise NormativaIndexUnavailable(
        "Gli archivi Normattiva non hanno un indice disponibile: ricerca locale non eseguita."
    )


def runtime_general_path() -> Path:
    from .official_sources_retriever import (
        CONTAINER_NORMATTIVA_DB,
        DEFAULT_NORMATTIVA_DB,
        _resolve_runtime_path,
    )
    return _resolve_runtime_path(
        None, env_names=("PCT_NORMATTIVA_DB", "PCT_LEX_NORMATTIVA_DB"),
        container_path=CONTAINER_NORMATTIVA_DB, repo_path=DEFAULT_NORMATTIVA_DB,
    )


def query_indexed_catalogs(general: Path, query: str, *, materia=None, vigenza=None, limit=10, diagnostics=None):
    """Lotti pigri: primario, poi biblioteca solo se il chiamante deve proseguire."""
    from .official_sources_retriever import _search_normattiva_indexed

    primary, catalog = select_runtime_catalog(general)

    def read(path, label):
        rows = _search_normattiva_indexed(path, query, materia=materia, vigenza=vigenza, limit=limit)
        if rows is None:
            raise NormativaIndexUnavailable("L'indice Normattiva non è consultabile: ricerca locale non completata.")
        return path, label, annotate_rows(rows, label)

    if catalog == "biblioteca_codici_leggi" and diagnostics is not None:
        diagnostics.append("normativa_library_scope")
    yield read(primary, catalog)
    library = general.with_name("codici_leggi.sqlite")
    if catalog == "archivio_generale" and library != primary and _indexed(library):
        if diagnostics is not None:
            diagnostics.append("normativa_library_supplement")
        yield read(library, "biblioteca_codici_leggi")


def catalog_revision() -> list:
    """Solo stat dei due archivi e WAL: nessuna lettura o enumerazione SQL."""
    general = runtime_general_path()
    revisions = []
    for path in (general, general.with_name("codici_leggi.sqlite")):
        for item in (path, Path(str(path) + "-wal")):
            try:
                stat = item.stat()
                revisions.append((str(item), stat.st_ino, stat.st_size, stat.st_mtime_ns))
            except OSError as exc:
                revisions.append((str(item), type(exc).__name__))
    return revisions


def annotate_rows(rows: list[dict], catalog: str) -> list[dict]:
    for row in rows:
        row["archive_catalog"] = catalog
        row["index_status"] = "available"
        # La presenza dell'indice non prova che ogni fonte sia indicizzata.
        row["index_coverage"] = "not_attested"
    return rows
