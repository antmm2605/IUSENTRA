from __future__ import annotations

import argparse
import csv
import io
import json
import sqlite3
import sys
import tempfile
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pct.territorio_italia import DEFAULT_TERRITORIO_DB, normalize_comune_key


ISTAT_COMUNI_URL = "https://www.istat.it/storage/codici-unita-amministrative/Elenco-comuni-italiani.xlsx"
GARDA_COMUNI_ZIP_URL = "https://www.gardainformatica.it/gi_db_comuni/gi_db_comuni-2026-05-22-c82f3.zip"
EXPECTED_COMUNI_MIN = 7800


def _download(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "IUSENTRA territorio audit/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:  # nosec B310 - fonti dati esplicite.
        return response.read()


def _xlsx_first_sheet_rows(content: bytes) -> list[list[str]]:
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in root.findall("m:si", ns):
                shared_strings.append("".join(node.text or "" for node in item.findall(".//m:t", ns)))
        sheet_name = "xl/worksheets/sheet1.xml"
        root = ElementTree.fromstring(archive.read(sheet_name))
        rows: list[list[str]] = []
        for row in root.findall(".//m:sheetData/m:row", ns):
            cells: dict[int, str] = {}
            for cell in row.findall("m:c", ns):
                ref = cell.attrib.get("r", "")
                column = 0
                for char in ref:
                    if not char.isalpha():
                        break
                    column = column * 26 + (ord(char.upper()) - 64)
                value_node = cell.find("m:v", ns)
                raw = value_node.text if value_node is not None else ""
                if cell.attrib.get("t") == "s" and raw:
                    value = shared_strings[int(raw)]
                else:
                    value = raw or ""
                cells[column] = str(value)
            if cells:
                max_column = max(cells)
                rows.append([cells.get(index, "") for index in range(1, max_column + 1)])
    return rows


def _read_istat_codes(content: bytes) -> set[str]:
    rows = _xlsx_first_sheet_rows(content)
    if not rows:
        return set()
    header = rows[0]
    try:
        code_index = header.index("Codice Comune formato alfanumerico")
    except ValueError:
        code_index = 4
    codes = {str(row[code_index]).strip().zfill(6) for row in rows[1:] if len(row) > code_index and str(row[code_index]).strip()}
    return codes


def _read_garda_rows(zip_content: bytes) -> dict[str, dict[str, str]]:
    with zipfile.ZipFile(io.BytesIO(zip_content)) as archive:
        raw = archive.read("csv/gi_comuni_cap.csv").decode("utf-8-sig")
    rows: dict[str, dict[str, str]] = {}
    for row in csv.DictReader(io.StringIO(raw), delimiter=";"):
        code = str(row.get("codice_istat") or "").strip().zfill(6)
        if not code:
            continue
        current = rows.setdefault(
            code,
            {
                "codice_istat": code,
                "nome": str(row.get("denominazione_ita") or "").strip(),
                "nome_altro": str(row.get("denominazione_altra") or "").strip(),
                "sigla_provincia": str(row.get("sigla_provincia") or "").strip().upper(),
                "provincia": str(row.get("denominazione_provincia") or "").strip(),
                "codice_regione": str(row.get("codice_regione") or "").strip().zfill(2),
                "regione": str(row.get("denominazione_regione") or "").strip(),
                "codice_belfiore": str(row.get("codice_belfiore") or "").strip().upper(),
                "lat": str(row.get("lat") or "").strip(),
                "lon": str(row.get("lon") or "").strip(),
                "cap_set": set(),
            },
        )
        cap = str(row.get("cap") or "").strip().zfill(5)
        if cap:
            current["cap_set"].add(cap)
    return rows


def build_db(db_path: Path, *, work_dir: Path | None = None) -> dict[str, object]:
    work_dir = work_dir or Path(tempfile.gettempdir())
    work_dir.mkdir(parents=True, exist_ok=True)
    istat_content = _download(ISTAT_COMUNI_URL)
    garda_content = _download(GARDA_COMUNI_ZIP_URL)
    istat_codes = _read_istat_codes(istat_content)
    garda_rows = _read_garda_rows(garda_content)
    missing_in_garda = sorted(istat_codes - set(garda_rows))
    extra_in_garda = sorted(set(garda_rows) - istat_codes)
    if len(istat_codes) < EXPECTED_COMUNI_MIN:
        raise RuntimeError(f"Fonte ISTAT incompleta: {len(istat_codes)} comuni.")
    if missing_in_garda:
        raise RuntimeError(f"CAP mancanti per {len(missing_in_garda)} comuni ISTAT: {missing_in_garda[:5]}")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA journal_mode=DELETE")
        conn.executescript(
            """
            DROP TABLE IF EXISTS comuni;
            DROP TABLE IF EXISTS territorio_sources;
            CREATE TABLE comuni (
              codice_istat TEXT PRIMARY KEY,
              nome TEXT NOT NULL,
              nome_altro TEXT NOT NULL DEFAULT '',
              cap TEXT NOT NULL DEFAULT '',
              sigla_provincia TEXT NOT NULL,
              provincia TEXT NOT NULL,
              codice_regione TEXT NOT NULL,
              regione TEXT NOT NULL,
              codice_belfiore TEXT NOT NULL DEFAULT '',
              lat TEXT NOT NULL DEFAULT '',
              lon TEXT NOT NULL DEFAULT '',
              search_key TEXT NOT NULL
            );
            CREATE INDEX idx_comuni_search_key ON comuni(search_key);
            CREATE INDEX idx_comuni_cap ON comuni(cap);
            CREATE TABLE territorio_sources (
              id TEXT PRIMARY KEY,
              url TEXT NOT NULL,
              downloaded_at TEXT NOT NULL,
              records INTEGER NOT NULL,
              note TEXT NOT NULL DEFAULT ''
            );
            """
        )
        now = datetime.now(timezone.utc).isoformat()
        for code in sorted(istat_codes):
            row = garda_rows[code]
            cap = ",".join(sorted(row["cap_set"]))
            conn.execute(
                """
                INSERT INTO comuni (
                  codice_istat, nome, nome_altro, cap, sigla_provincia, provincia,
                  codice_regione, regione, codice_belfiore, lat, lon, search_key
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    code,
                    row["nome"],
                    row["nome_altro"],
                    cap,
                    row["sigla_provincia"],
                    row["provincia"],
                    row["codice_regione"],
                    row["regione"],
                    row["codice_belfiore"],
                    row["lat"],
                    row["lon"],
                    normalize_comune_key(row["nome"]),
                ),
            )
        conn.execute(
            "INSERT INTO territorio_sources VALUES (?, ?, ?, ?, ?)",
            ("istat-comuni", ISTAT_COMUNI_URL, now, len(istat_codes), "Elenco ufficiale Comuni italiani"),
        )
        conn.execute(
            "INSERT INTO territorio_sources VALUES (?, ?, ?, ?, ?)",
            ("garda-cap", GARDA_COMUNI_ZIP_URL, now, len(garda_rows), "CAP, province e coordinate in licenza MIT"),
        )
        conn.commit()
    finally:
        conn.close()
    return {
        "ok": True,
        "db": str(db_path),
        "istat_comuni": len(istat_codes),
        "garda_comuni": len(garda_rows),
        "extra_in_garda": len(extra_in_garda),
        "missing_in_garda": len(missing_in_garda),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Crea la banca dati SQLite dei Comuni italiani.")
    parser.add_argument("--db", default=str(DEFAULT_TERRITORIO_DB), help="Percorso SQLite da generare.")
    args = parser.parse_args()
    result = build_db(Path(args.db))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
