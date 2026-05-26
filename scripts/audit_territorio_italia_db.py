from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pct.territorio_italia import DEFAULT_TERRITORIO_DB


EXPECTED_COMUNI = 7894


def audit(db_path: Path) -> dict[str, object]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        stats = conn.execute(
            """
            SELECT
              COUNT(*) AS comuni,
              SUM(CASE WHEN cap <> '' THEN 1 ELSE 0 END) AS comuni_con_cap,
              SUM(CASE WHEN sigla_provincia <> '' THEN 1 ELSE 0 END) AS comuni_con_provincia,
              SUM(CASE WHEN codice_regione <> '' THEN 1 ELSE 0 END) AS comuni_con_regione,
              SUM(CASE WHEN codice_belfiore <> '' THEN 1 ELSE 0 END) AS comuni_con_belfiore,
              COUNT(DISTINCT sigla_provincia) AS province,
              COUNT(DISTINCT codice_regione) AS regioni
            FROM comuni
            """
        ).fetchone()
        duplicates = conn.execute(
            """
            SELECT search_key, COUNT(*) AS count
            FROM comuni
            GROUP BY search_key
            HAVING COUNT(*) > 1
            ORDER BY count DESC, search_key
            """
        ).fetchall()
        missing = conn.execute(
            """
            SELECT codice_istat, nome, sigla_provincia, cap
            FROM comuni
            WHERE cap = '' OR sigla_provincia = '' OR codice_regione = ''
            ORDER BY nome
            LIMIT 20
            """
        ).fetchall()
    finally:
        conn.close()
    result = {key: int(stats[key] or 0) for key in stats.keys()}
    result["expected_comuni"] = EXPECTED_COMUNI
    result["coverage_comuni_pct"] = round(result["comuni"] / EXPECTED_COMUNI * 100, 4)
    result["coverage_cap_pct"] = round(result["comuni_con_cap"] / result["comuni"] * 100, 4) if result["comuni"] else 0
    result["duplicate_name_keys"] = len(duplicates)
    result["missing_required_sample"] = [dict(row) for row in missing]
    result["ok"] = (
        result["comuni"] == EXPECTED_COMUNI
        and result["comuni_con_cap"] == EXPECTED_COMUNI
        and result["comuni_con_provincia"] == EXPECTED_COMUNI
        and result["comuni_con_regione"] == EXPECTED_COMUNI
        and not result["missing_required_sample"]
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit 100% copertura Comuni/CAP/province.")
    parser.add_argument("--db", default=str(DEFAULT_TERRITORIO_DB), help="Percorso SQLite territorio.")
    args = parser.parse_args()
    result = audit(Path(args.db))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
