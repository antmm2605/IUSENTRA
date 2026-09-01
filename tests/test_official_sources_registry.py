from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from lex.sources.db import init_db
from lex.sources.registry import load_sources


def test_official_sources_config_has_required_sources_and_no_tokens():
    path = Path("config/lex_official_sources.example.json")
    text = path.read_text(encoding="utf-8")
    config = json.loads(text)
    ids = {item["id"] for item in config["sources"]}

    required = {
        "normattiva",
        "codici_normattiva",
        "gazzetta_ufficiale",
        "ministero_giustizia",
        "pst_pct",
        "pat_siga",
        "ptt_sigit",
        "pdp_penale",
        "cnf",
        "agenzia_entrate",
        "garante_privacy",
        "eurlex",
        "anac",
        "inps",
        "inail",
        "banca_italia",
        "agcm",
        "agcom",
        "ipa",
        "inipec",
        "inad",
        "fonti_studio_locali",
    }
    assert required.issubset(ids)
    enabled = {item["id"] for item in config["sources"] if item.get("enabled")}
    assert {"normattiva", "gazzetta_ufficiale"}.issubset(enabled)
    assert enabled.issubset(ids)
    assert "cookie" not in text.lower()
    assert "token" not in text.lower()


def test_load_sources_and_init_sqlite_schema(tmp_path: Path):
    sources = load_sources("config/lex_official_sources.example.json")
    assert any(source.id == "gazzetta_ufficiale" and source.enabled for source in sources)

    db_path = tmp_path / "lex_sources.sqlite"
    init_db(db_path)

    con = sqlite3.connect(db_path)
    try:
        tables = {
            row[0]
            for row in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    finally:
        con.close()

    assert {"official_sources", "official_documents", "official_chunks", "official_sync_runs", "official_source_errors"}.issubset(tables)
