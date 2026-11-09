"""Conteggi del solo corpus dello studio corrente, senza creare o modificare database."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace


def corpus_inventory(manager):
    path = getattr(manager, "corpus_db_path", None)
    if not path:
        return None
    try:
        database = Path(path).resolve(strict=True)
        with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=2) as connection:
            rows = connection.execute(
                "SELECT f.codice, COUNT(*), "
                "SUM(CASE WHEN s.testo_integrale_presente=1 THEN 1 ELSE 0 END) "
                "FROM sentenze s JOIN fonti_giurisprudenza f ON f.id=s.fonte_id "
                "GROUP BY f.codice"
            ).fetchall()
        return {code: {"decisions": count, "fullTexts": texts} for code, count, texts in rows}
    except (OSError, sqlite3.Error, ValueError):
        return None


def attach_corpus_counts(sources, manager, config=None):
    from web.services.sentenzeweb_runtime import inventory as public_inventory

    from web.services.giurisprudenza_public_corpus import PUBLIC_SOURCES, configured_public_corpus

    inventory = corpus_inventory(manager)
    try:
        public_owner = configured_public_corpus(config or {})
        public_counts = corpus_inventory(SimpleNamespace(corpus_db_path=public_owner.db_path)) if public_owner else None
    except (OSError, sqlite3.Error, ValueError):
        public_counts = None
    try:
        shared = public_inventory(config) if any(source["id"] == "cassazione" for source in sources) else {}
    except (OSError, sqlite3.Error, ValueError):
        shared = {}
    for source in sources:
        source["sharedCorpusCount"] = shared.get("caseCount") if source["id"] == "cassazione" else None
        if public_counts is not None and source["id"] in PUBLIC_SOURCES:
            source["sharedCorpusCount"] = public_counts.get(source["id"], {}).get("decisions", 0)
        source["sharedCorpusStatus"] = shared.get("status", "unknown") if source["id"] == "cassazione" else ""
        source["corpusCount"] = None
        source["corpusFullTextCount"] = None
        if inventory is not None:
            counts = inventory.get(source["id"], {"decisions": 0, "fullTexts": 0})
            source["corpusCount"] = counts["decisions"]
            source["corpusFullTextCount"] = counts["fullTexts"]
    return sources
