"""Cataloghi pubblici Normattiva: consultazione degli indici già disponibili.

Non costruisce indici, non importa fonti e non attesta copertura o vigenza.
Le ispezioni con db_path esplicito restano nella procedura nativa esistente.
"""

from __future__ import annotations

import json
import os
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



def library_path(general: Path) -> Path:
    configured = str(os.getenv("PCT_CODICI_LEGGI_DB", "") or "").strip()
    return Path(configured) if configured else general.with_name("codici_leggi.sqlite")


def select_runtime_catalog(general: Path) -> tuple[Path, str]:
    if _indexed(general):
        return general, "archivio_generale"
    library = library_path(general)
    if library != general and _indexed(library):
        return library, "biblioteca_codici_leggi"
    raise NormativaIndexUnavailable(
        "Gli archivi Normattiva non hanno un indice disponibile: ricerca locale non eseguita."
    )


def runtime_general_path() -> Path:
    from flask import current_app, has_app_context

    from .official_sources_retriever import (
        CONTAINER_NORMATTIVA_DB,
        DEFAULT_NORMATTIVA_DB,
        _resolve_runtime_path,
    )

    configured=current_app.config.get("NORMATTIVA_DB") if has_app_context() else None
    return _resolve_runtime_path(
        Path(configured) if configured else None, env_names=("PCT_NORMATTIVA_DB", "PCT_LEX_NORMATTIVA_DB"),
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
    library = library_path(general)
    if catalog == "archivio_generale" and library != primary and _indexed(library):
        if diagnostics is not None:
            diagnostics.append("normativa_library_supplement")
        yield read(library, "biblioteca_codici_leggi")


def catalog_revision() -> list:
    """Solo stat dei due archivi e WAL: nessuna lettura o enumerazione SQL."""
    general = runtime_general_path()
    revisions = []
    for path in (general, library_path(general)):
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


def leggi_testo_articolo(row: dict, general: Path) -> dict:
    """Rilegge l'articolo del chunk selezionato nel solo archivio proprietario.

    Non cerca per titolo o numero: ID SQL e impronta documento devono coincidere.
    """
    import hashlib

    catalog = row.get("archive_catalog")
    path = library_path(general) if catalog == "biblioteca_codici_leggi" else general
    chunk_id = row.get("chunk_rowid")
    if type(chunk_id) is not int:
        return row
    with closing(sqlite3.connect(path.resolve().as_uri()+"?mode=ro", uri=True, timeout=2)) as conn:
        conn.row_factory = sqlite3.Row
        found = conn.execute("SELECT c.document_id,c.metadata_json,a.id AS article_id,a.article_text,d.xml_sha256,d.text_content "
                             "FROM normative_chunks c LEFT JOIN normative_articles a ON a.id=c.article_id "
                             "JOIN normative_documents d ON d.id=c.document_id WHERE c.id=?", (chunk_id,)).fetchone()
        component = None
        if found and found["article_id"] is None:
            metadata = json.loads(found["metadata_json"] or "{}")
            component_id = metadata.get("component_id")
            if type(component_id) is int:
                component = conn.execute("SELECT testo,sha256_testo,localizzatore_xml FROM normative_components WHERE id=? AND document_id=?",
                                         (component_id,found["document_id"])).fetchone()
                if component is None or hashlib.sha256(component["testo"].encode()).hexdigest() != component["sha256_testo"]:
                    raise NormativaIndexUnavailable("Componente XML non riscontrato o alterato")
    if not found or found["document_id"] != row.get("document_id") or found["xml_sha256"] != row.get("hash_sha256"):
        raise NormativaIndexUnavailable("La fonte e cambiata durante la lettura: ripetere la ricerca puntuale.")
    text = component["testo"] if component is not None else (found["article_text"] if found["article_id"] is not None else found["text_content"])
    text = text or ""
    if not text.strip():
        raise NormativaIndexUnavailable("Articolo senza testo nell'archivio proprietario.")
    from .abrogazione import tagga_abrogazione

    return tagga_abrogazione(dict(row, testo=text, normative_full_text=text,
                articolo_o_chunk=row.get("articolo_o_chunk") if found["article_id"] is not None else "",
                normative_scope="articolo" if found["article_id"] is not None else ("allegato_non_articolato" if component is not None else "atto_non_articolato"),
                normative_component_locator=component["localizzatore_xml"] if component is not None else None,
                normative_full_text_sha256=hashlib.sha256(text.encode()).hexdigest(),
                normative_article_id=found["article_id"]))


def fondi_cataloghi(batches, *, limit: int) -> list[dict]:
    """Fusione RRF dei cataloghi; deduplica solo testo e identita coincidenti.

    Partizioni e versioni con testi diversi restano distinte anche se condividono
    numero e URN. La preferenza non dipende dal banco di valutazione.
    """
    import hashlib

    scored = {}
    ranked = {}
    for _, _label, rows in batches:
        for rank, row in enumerate(rows, 1):
            key = (row.get("url_origine"), row.get("articolo_o_chunk"),
                   hashlib.sha256(str(row.get("testo") or "").encode()).hexdigest())
            if key not in ranked:
                ranked[key] = row
            scored[key] = scored.get(key,0.0)+1/(60+rank)
    ordered = sorted(ranked, key=lambda k: (not bool(ranked[k].get("riferimento_esatto")), -scored[k]))
    return [ranked[k] for k in ordered[:limit]]
