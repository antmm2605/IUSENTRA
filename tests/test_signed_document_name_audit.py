import json
import sqlite3
from pathlib import Path

from scripts.repair_signed_document_names import main, repair_sqlite_db


def _create_fascicoli_db(path: Path, documents: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE fascicoli (
                id TEXT PRIMARY KEY,
                numero TEXT,
                titolo TEXT,
                documenti_json TEXT
            )
            """
        )
        conn.execute(
            "INSERT INTO fascicoli (id, numero, titolo, documenti_json) VALUES (?,?,?,?)",
            ("FASC1", "2026/1", "Fascicolo prova", json.dumps({"documenti": documents}, ensure_ascii=False)),
        )
        conn.commit()


def test_audit_nomi_firmati_usa_studio_db_e_non_json_mirror(tmp_path: Path, capsys):
    tenant_root = tmp_path / "tenants" / "studio-sql"
    _create_fascicoli_db(
        tenant_root / "studio.db",
        [
            {
                "id": "doc1",
                "nome": "Memoria.pdf",
                "nome_originale": "Memoria.pdf.p7m",
            }
        ],
    )
    mirror = tenant_root / "fascicoli" / "fascicoli.json"
    mirror.parent.mkdir(parents=True, exist_ok=True)
    mirror.write_text(json.dumps({"fascicoli": []}, ensure_ascii=False), encoding="utf-8")

    exit_code = main(["--root", str(tmp_path), "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["authoritative_source"] == "sqlite_core"
    assert payload["json_source_of_truth"] is False
    assert payload["sqlite_databases"] == 1
    assert payload["json_mirrors_skipped"] == 1
    assert payload["checked"] == 1
    assert payload["changed"] == 1
    assert payload["results"][0]["changes"][0]["nome_corretto"] == "Memoria.pdf.p7m"


def test_audit_nomi_firmati_non_usa_flag_storico_come_firma(tmp_path: Path):
    db_path = tmp_path / "studio.db"
    _create_fascicoli_db(
        db_path,
        [
            {
                "id": "doc1",
                "nome": "Ricorso.pdf",
                "firmato_digitalmente": True,
            }
        ],
    )

    report = repair_sqlite_db(db_path, apply=False)

    assert report["source_kind"] == "sqlite_core"
    assert report["changed"] == 0
    assert report["signed_flag_plain_pdf"] == 1
    assert "Flag storico" in report["flag_only_examples"][0]["nota"]


def test_audit_nomi_firmati_apply_aggiorna_documenti_json_sql(tmp_path: Path):
    db_path = tmp_path / "studio.db"
    _create_fascicoli_db(
        db_path,
        [
            {
                "id": "doc1",
                "nome": "Procura.pdf",
                "percorso": "FASC1/Procura.pdf.p7m",
            }
        ],
    )

    report = repair_sqlite_db(db_path, apply=True)

    assert report["changed"] == 1
    with sqlite3.connect(db_path) as conn:
        payload = json.loads(conn.execute("SELECT documenti_json FROM fascicoli").fetchone()[0])
    assert payload["documenti"][0]["nome"] == "Procura.pdf.p7m"
