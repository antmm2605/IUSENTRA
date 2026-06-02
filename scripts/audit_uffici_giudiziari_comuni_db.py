from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pct.territorio_italia import DEFAULT_TERRITORIO_DB
from pct.uffici_competenti import normalizza_codici_ufficio_telematico
from scripts.build_uffici_giudiziari_comuni_db import DEFAULT_UFFICI_DB, REQUESTED_KINDS


def _association_source(conn: sqlite3.Connection) -> tuple[str, str]:
    columns = {str(row["name"]) for row in conn.execute("PRAGMA table_info(office_associations)").fetchall()}
    if "office_json" in columns:
        return "office_associations", "office_associations"
    return "office_associations a JOIN offices o ON o.office_id = a.office_id", "o"


def _office_json_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    tables = {str(row["name"]) for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()}
    if "offices" in tables:
        return conn.execute("SELECT office_json FROM offices ORDER BY office_id").fetchall()
    return conn.execute("SELECT DISTINCT office_json FROM office_associations ORDER BY office_id").fetchall()


def _audit_codici_uffici(conn: sqlite3.Connection) -> dict[str, object]:
    rows = _office_json_rows(conn)
    leak_samples: list[dict[str, str]] = []
    codice_ufficio = 0
    codice_pst = 0
    codice_gl = 0
    solo_istat = 0
    for row in rows:
        try:
            office = normalizza_codici_ufficio_telematico(json.loads(row["office_json"]))
        except Exception:
            continue
        istat = str(office.get("istatCode") or "").strip()
        code_values = {
            "codice": str(office.get("codice") or "").strip(),
            "codiceMinistero": str(office.get("codiceMinistero") or "").strip(),
            "codiceGiustiziaLocale": str(office.get("codiceGiustiziaLocale") or "").strip(),
        }
        if code_values["codice"]:
            codice_ufficio += 1
        if code_values["codiceMinistero"]:
            codice_pst += 1
        if code_values["codiceGiustiziaLocale"]:
            codice_gl += 1
        if istat and not any(code_values.values()):
            solo_istat += 1
        for field, value in code_values.items():
            if istat and value == istat and len(leak_samples) < 25:
                leak_samples.append(
                    {
                        "ufficio": str(office.get("name") or ""),
                        "campo": field,
                        "valore": value,
                        "istat": istat,
                    }
                )
    return {
        "uffici_unici": len(rows),
        "codici_ufficio_presenti": codice_ufficio,
        "codici_pst_presenti": codice_pst,
        "codici_gl_presenti": codice_gl,
        "uffici_solo_istat_sede": solo_istat,
        "codici_istat_promossi_a_codice": leak_samples,
    }


def audit(db_path: Path, territorio_db: Path) -> dict[str, object]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    territory = sqlite3.connect(territorio_db)
    territory.row_factory = sqlite3.Row
    try:
        expected = int(territory.execute("SELECT COUNT(*) FROM comuni").fetchone()[0])
        status = conn.execute(
            """
            SELECT
              COUNT(*) AS comuni_fetched,
              SUM(CASE WHEN ok = 1 THEN 1 ELSE 0 END) AS comuni_ok,
              SUM(CASE WHEN requested_offices > 0 THEN 1 ELSE 0 END) AS comuni_con_associazioni,
              SUM(CASE WHEN requested_with_pec > 0 THEN 1 ELSE 0 END) AS comuni_con_pec
            FROM comuni_status
            """
        ).fetchone()
        association_from, office_alias = _association_source(conn)
        associations = conn.execute(
            f"""
            SELECT
              COUNT(*) AS associazioni,
              SUM(CASE WHEN {office_alias}.pec <> '' THEN 1 ELSE 0 END) AS associazioni_con_pec,
              COUNT(DISTINCT {office_alias}.kind) AS tipologie
            FROM {association_from}
            """
        ).fetchone()
        kind_rows = conn.execute(
            f"""
            SELECT {office_alias}.kind AS kind,
                   COUNT(*) AS count,
                   SUM(CASE WHEN {office_alias}.pec <> '' THEN 1 ELSE 0 END) AS with_pec
            FROM {association_from}
            GROUP BY {office_alias}.kind
            ORDER BY {office_alias}.kind
            """
        ).fetchall()
        errors = conn.execute(
            """
            SELECT codice_istat, nome, sigla_provincia, error
            FROM comuni_status
            WHERE ok = 0 OR requested_offices = 0
            ORDER BY nome
            LIMIT 25
            """
        ).fetchall()
        codici_audit = _audit_codici_uffici(conn)
    finally:
        conn.close()
        territory.close()
    result = {
        "expected_comuni": expected,
        "comuni_fetched": int(status["comuni_fetched"] or 0),
        "comuni_ok": int(status["comuni_ok"] or 0),
        "comuni_con_associazioni": int(status["comuni_con_associazioni"] or 0),
        "comuni_con_pec": int(status["comuni_con_pec"] or 0),
        "associazioni": int(associations["associazioni"] or 0),
        "associazioni_con_pec": int(associations["associazioni_con_pec"] or 0),
        "tipologie": int(associations["tipologie"] or 0),
        "coverage_comuni_pct": 0,
        "coverage_associazioni_pct": 0,
        "tipologie_richieste_presenti": sorted({row["kind"] for row in kind_rows if row["kind"] in REQUESTED_KINDS}),
        "missing_or_error_sample": [dict(row) for row in errors],
        **codici_audit,
    }
    if expected:
        result["coverage_comuni_pct"] = round(result["comuni_ok"] / expected * 100, 4)
        result["coverage_associazioni_pct"] = round(result["comuni_con_associazioni"] / expected * 100, 4)
    result["ok"] = (
        result["comuni_fetched"] == expected
        and result["comuni_ok"] == expected
        and result["comuni_con_associazioni"] == expected
        and result["coverage_comuni_pct"] == 100.0
        and result["coverage_associazioni_pct"] == 100.0
        and set(result["tipologie_richieste_presenti"]) == REQUESTED_KINDS
        and not result["missing_or_error_sample"]
        and not result["codici_istat_promossi_a_codice"]
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit 100% associazioni Comune -> uffici giudiziari.")
    parser.add_argument("--db", default=str(DEFAULT_UFFICI_DB))
    parser.add_argument("--territorio-db", default=str(DEFAULT_TERRITORIO_DB))
    args = parser.parse_args()
    result = audit(Path(args.db), Path(args.territorio_db))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
