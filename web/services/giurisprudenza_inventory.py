"""Conteggi del solo corpus dello studio corrente, senza creare o modificare database."""
from __future__ import annotations

import sqlite3
from pathlib import Path


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

    inventory = corpus_inventory(manager)
    try:
        shared = public_inventory(config) if any(source["id"] == "cassazione" for source in sources) else {}
    except (OSError, sqlite3.Error, ValueError):
        shared = {}
    for source in sources:
        source["sharedCorpusCount"] = shared.get("caseCount") if source["id"] == "cassazione" else None
        source["sharedCorpusStatus"] = shared.get("status", "unknown") if source["id"] == "cassazione" else ""
        source["corpusCount"] = None
        source["corpusFullTextCount"] = None
        if inventory is not None:
            counts = inventory.get(source["id"], {"decisions": 0, "fullTexts": 0})
            source["corpusCount"] = counts["decisions"]
            source["corpusFullTextCount"] = counts["fullTexts"]
    return sources
