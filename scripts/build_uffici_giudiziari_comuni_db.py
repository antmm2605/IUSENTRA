from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import unicodedata
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pct.territorio_italia import DEFAULT_TERRITORIO_DB, ComuneItalia, get_comune, normalize_comune_key
from pct.uffici_competenti import (
    GIUSTIZIA_MAP_VIEW_URL,
    _extract_xml,
    _find_comune_option,
    _office_actions,
    _parse_offices,
    _post_giustizia_map,
)


DEFAULT_UFFICI_DB = Path(__file__).resolve().parents[1] / "pct" / "data" / "uffici_giudiziari_comuni.sqlite"
WIKIPEDIA_FUSIONI_URL = "https://it.wikipedia.org/wiki/Fusione_di_comuni_italiani"
SCORPORI_PREDECESSORI = {
    "mappano": ["Borgaro Torinese", "Caselle Torinese", "Leinì", "Settimo Torinese"],
    "misiliscemi": ["Trapani"],
}
REQUESTED_KINDS = {
    "giudice_pace",
    "tribunale",
    "procura",
    "unep",
    "corte_appello",
    "procura_generale",
    "assise_appello",
    "assise",
    "procura_minorenni",
    "tribunale_minorenni",
}


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(row["name"]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _create_normalized_schema(conn: sqlite3.Connection, *, suffix: str = "") -> None:
    offices_table = f"offices{suffix}"
    associations_table = f"office_associations{suffix}"
    conn.executescript(
        f"""
        CREATE TABLE IF NOT EXISTS {offices_table} (
          office_id TEXT PRIMARY KEY,
          kind TEXT NOT NULL,
          name TEXT NOT NULL,
          pec TEXT NOT NULL DEFAULT '',
          city TEXT NOT NULL DEFAULT '',
          cap TEXT NOT NULL DEFAULT '',
          source_url TEXT NOT NULL,
          office_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_{offices_table}_kind ON {offices_table}(kind);
        CREATE INDEX IF NOT EXISTS idx_{offices_table}_pec ON {offices_table}(pec);
        CREATE TABLE IF NOT EXISTS {associations_table} (
          comune_istat TEXT NOT NULL,
          office_id TEXT NOT NULL,
          kind TEXT NOT NULL,
          derived_from TEXT NOT NULL DEFAULT '',
          association_source TEXT NOT NULL DEFAULT '',
          PRIMARY KEY (comune_istat, office_id)
        );
        CREATE INDEX IF NOT EXISTS idx_{associations_table}_kind ON {associations_table}(kind);
        """
    )


def _office_for_catalog(office: dict[str, Any]) -> dict[str, Any]:
    catalog = dict(office)
    for key in ("associationComuneIstat", "associationComune", "derivedFromComuni", "associationSource"):
        catalog.pop(key, None)
    return catalog


def _migrate_legacy_associations(conn: sqlite3.Connection) -> None:
    columns = _table_columns(conn, "office_associations")
    if "office_json" not in columns:
        _create_normalized_schema(conn)
        return
    conn.executescript(
        """
        DROP TABLE IF EXISTS offices_new;
        DROP TABLE IF EXISTS office_associations_new;
        """
    )
    _create_normalized_schema(conn, suffix="_new")
    rows = conn.execute(
        """
        SELECT comune_istat, office_id, kind, name, pec, city, cap, source_url, office_json
        FROM office_associations
        """
    ).fetchall()
    for row in rows:
        office = json.loads(row["office_json"])
        catalog = _office_for_catalog(office)
        derived_from = json.dumps(list(office.get("derivedFromComuni") or []), ensure_ascii=False)
        association_source = str(office.get("associationSource") or "")
        conn.execute(
            """
            INSERT OR REPLACE INTO offices_new (
              office_id, kind, name, pec, city, cap, source_url, office_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["office_id"],
                row["kind"],
                row["name"],
                row["pec"],
                row["city"],
                row["cap"],
                row["source_url"],
                json.dumps(catalog, ensure_ascii=False, sort_keys=True),
            ),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO office_associations_new (
              comune_istat, office_id, kind, derived_from, association_source
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (row["comune_istat"], row["office_id"], row["kind"], derived_from, association_source),
        )
    conn.executescript(
        """
        DROP TABLE office_associations;
        ALTER TABLE offices_new RENAME TO offices;
        ALTER TABLE office_associations_new RENAME TO office_associations;
        """
    )


def _init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS comuni_status (
              codice_istat TEXT PRIMARY KEY,
              nome TEXT NOT NULL,
              sigla_provincia TEXT NOT NULL,
              cap TEXT NOT NULL DEFAULT '',
              fetched_at TEXT NOT NULL DEFAULT '',
              ok INTEGER NOT NULL DEFAULT 0,
              total_official INTEGER NOT NULL DEFAULT 0,
              requested_offices INTEGER NOT NULL DEFAULT 0,
              requested_with_pec INTEGER NOT NULL DEFAULT 0,
              error TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS uffici_sources (
              id TEXT PRIMARY KEY,
              url TEXT NOT NULL,
              fetched_at TEXT NOT NULL,
              note TEXT NOT NULL DEFAULT ''
            );
            """
        )
        _migrate_legacy_associations(conn)
        conn.execute(
            "INSERT OR REPLACE INTO uffici_sources VALUES (?, ?, ?, ?)",
            (
                "giustizia-map",
                GIUSTIZIA_MAP_VIEW_URL,
                datetime.now(timezone.utc).isoformat(),
                "Associazioni Comune -> uffici giudiziari competenti interrogate da Giustizia Map.",
            ),
        )
        conn.execute(
            "INSERT OR REPLACE INTO uffici_sources VALUES (?, ?, ?, ?)",
            (
                "fusioni-comuni",
                WIKIPEDIA_FUSIONI_URL,
                datetime.now(timezone.utc).isoformat(),
                "Elenco di raccordo dei Comuni istituiti per fusione; ogni predecessore viene poi interrogato su Giustizia Map.",
            ),
        )
        conn.commit()


def _load_comuni(territorio_db: Path, limit: int = 0) -> list[ComuneItalia]:
    with _connect(territorio_db) as conn:
        rows = conn.execute(
            """
            SELECT codice_istat
            FROM comuni
            ORDER BY nome COLLATE NOCASE, sigla_provincia
            """
        ).fetchall()
    comuni = [get_comune(codice_istat=row["codice_istat"], db_path=territorio_db) for row in rows]
    result = [comune for comune in comuni if comune is not None]
    return result[:limit] if limit else result


def _already_done(db_path: Path) -> set[str]:
    if not db_path.exists():
        return set()
    with _connect(db_path) as conn:
        rows = conn.execute("SELECT codice_istat FROM comuni_status WHERE ok = 1").fetchall()
    return {str(row["codice_istat"]) for row in rows}


def _download_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "IUSENTRA uffici giudiziari audit/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:  # nosec B310 - fonte pubblica esplicita.
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def _strip_accents(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(char for char in text if not unicodedata.combining(char))


def _query_variants(value: str) -> list[str]:
    variants: list[str] = []
    for candidate in (value, _strip_accents(value)):
        clean = candidate.strip()
        if clean and clean not in variants:
            variants.append(clean)
    return variants


def _cell_links(cell: Any) -> list[str]:
    links: list[str] = []
    for anchor in cell.find_all("a"):
        text = anchor.get_text(" ", strip=True)
        href = str(anchor.get("href") or "")
        if text and not href.startswith("#cite") and not text.isdigit():
            links.append(text)
    return links or [cell.get_text(" ", strip=True)]


def _expanded_rows(table: Any) -> list[list[Any]]:
    grid: list[list[Any]] = []
    spans: dict[tuple[int, int], tuple[Any, int]] = {}
    for row_index, tr in enumerate(table.find_all("tr")):
        row: list[Any] = []
        column_index = 0

        def flush_spans() -> None:
            nonlocal column_index
            while (row_index, column_index) in spans:
                value, remaining = spans.pop((row_index, column_index))
                row.append(value)
                if remaining > 1:
                    spans[(row_index + 1, column_index)] = (value, remaining - 1)
                column_index += 1

        flush_spans()
        for cell in tr.find_all(["th", "td"], recursive=False):
            flush_spans()
            row_span = int(cell.get("rowspan", "1") or 1)
            col_span = int(cell.get("colspan", "1") or 1)
            for _ in range(col_span):
                row.append(cell)
                if row_span > 1:
                    spans[(row_index + 1, column_index)] = (cell, row_span - 1)
                column_index += 1
        grid.append(row)
    return grid


@lru_cache(maxsize=1)
def _load_fusion_predecessori() -> dict[str, list[str]]:
    try:
        from bs4 import BeautifulSoup
    except Exception as exc:  # pragma: no cover - dipendenza dichiarata in requirements.
        raise RuntimeError("BeautifulSoup non è disponibile per leggere l'elenco delle fusioni comunali.") from exc
    soup = BeautifulSoup(_download_text(WIKIPEDIA_FUSIONI_URL), "html.parser")
    predecessors: dict[str, list[str]] = {}
    for table in soup.find_all("table", class_="wikitable")[:2]:
        for row in _expanded_rows(table)[1:]:
            if len(row) < 5:
                continue
            nuovo = _cell_links(row[3])[0]
            soppressi = [item for item in _cell_links(row[4]) if item]
            if nuovo and soppressi:
                predecessors[normalize_comune_key(nuovo)] = soppressi
    for nome, soppressi in SCORPORI_PREDECESSORI.items():
        predecessors[normalize_comune_key(nome)] = soppressi
    return predecessors


def _select_comune_payload(comune: str, sigla_provincia: str, timeout: float) -> str:
    first = _post_giustizia_map(
        {
            "uid": "G_MAP",
            "_pagina_": "2",
            "cerca_comune": comune,
            "tipo_ufficio": "",
            "lista_regioni": "",
            "lista_prov": "",
            "ricerca_libera": "",
            "_xml_": "xml",
            "Submit": "cerca",
        },
        timeout,
    )
    try:
        _extract_xml(first)
        return first
    except ValueError:
        selected = _find_comune_option(first, comune, sigla_provincia)
        if not selected:
            return first
    return _post_giustizia_map(
        {
            "uid": "G_MAP",
            "_pagina_": "3",
            "comune": selected,
            "_xml_": "xml",
            "Submit": "cerca",
        },
        timeout,
    )


def _fetch_offices(query: str, comune: ComuneItalia, timeout: float) -> list[dict[str, Any]]:
    if "#" in query:
        payload = _post_giustizia_map(
            {
                "uid": "G_MAP",
                "_pagina_": "3",
                "comune": query,
                "_xml_": "xml",
                "Submit": "cerca",
            },
            timeout,
        )
    else:
        payload = _select_comune_payload(query, comune.sigla_provincia, timeout)
    offices = _parse_offices(_extract_xml(payload), comune.label)
    for office in offices:
        office["actions"] = _office_actions(office, comune.label)
    return offices


def _requested(offices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [office for office in offices if str(office.get("kind") or "") in REQUESTED_KINDS]


def _merge_offices(offices: list[dict[str, Any]], source_name: str, comune: ComuneItalia, target: dict[str, dict[str, Any]]) -> None:
    for office in offices:
        if str(office.get("kind") or "") not in REQUESTED_KINDS:
            continue
        office_id = str(office.get("id") or "")
        current = target.get(office_id)
        if current is None:
            current = dict(office)
            current["associationComuneIstat"] = comune.codice_istat
            current["associationComune"] = comune.label
            current["derivedFromComuni"] = []
            current["associationSource"] = (
                "Comune di nuova istituzione non riconosciuto direttamente da Giustizia Map; "
                "ufficio derivato interrogando il Comune predecessore su Giustizia Map."
            )
            target[office_id] = current
        derived = list(current.get("derivedFromComuni") or [])
        if source_name not in derived:
            derived.append(source_name)
        current["derivedFromComuni"] = sorted(derived)
        if not current.get("pec") and office.get("pec"):
            current["pec"] = office.get("pec")


def _fetch_one(comune: ComuneItalia, timeout: float) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    errors: list[str] = []
    try:
        offices = _fetch_offices(comune.giustizia_map_value, comune, timeout)
        requested = _requested(offices)
        return {
            "ok": True,
            "codice_istat": comune.codice_istat,
            "nome": comune.nome,
            "sigla_provincia": comune.sigla_provincia,
            "cap": ",".join(comune.cap),
            "fetched_at": now,
            "total_official": len(offices),
            "requested_offices": len(requested),
            "requested_with_pec": sum(1 for office in requested if str(office.get("pec") or "").strip()),
            "offices": requested,
            "error": "",
        }
    except Exception as exc:
        errors.append(f"{comune.nome}: {exc}")

    try:
        offices = _fetch_offices(comune.nome, comune, timeout)
        requested = _requested(offices)
        return {
            "ok": True,
            "codice_istat": comune.codice_istat,
            "nome": comune.nome,
            "sigla_provincia": comune.sigla_provincia,
            "cap": ",".join(comune.cap),
            "fetched_at": now,
            "total_official": len(offices),
            "requested_offices": len(requested),
            "requested_with_pec": sum(1 for office in requested if str(office.get("pec") or "").strip()),
            "offices": requested,
            "error": "",
        }
    except Exception as exc:
        errors.append(f"{comune.nome} senza codice: {exc}")

    predecessors = _load_fusion_predecessori().get(normalize_comune_key(comune.nome), [])
    if predecessors:
        merged: dict[str, dict[str, Any]] = {}
        official_total = 0
        missing_predecessors: list[str] = []
        for predecessor in predecessors:
            predecessor_errors: list[str] = []
            predecessor_offices: list[dict[str, Any]] = []
            for query in _query_variants(predecessor):
                try:
                    predecessor_offices = _fetch_offices(query, comune, timeout)
                    break
                except Exception as exc:
                    predecessor_errors.append(f"{query}: {exc}")
            if predecessor_offices:
                official_total += len(predecessor_offices)
                _merge_offices(predecessor_offices, predecessor, comune, merged)
            else:
                missing_predecessors.append(predecessor)
                errors.extend(predecessor_errors)
        requested = sorted(merged.values(), key=lambda office: (int(office.get("priority") or 99), str(office.get("name") or "")))
        if requested and not missing_predecessors:
            return {
                "ok": True,
                "codice_istat": comune.codice_istat,
                "nome": comune.nome,
                "sigla_provincia": comune.sigla_provincia,
                "cap": ",".join(comune.cap),
                "fetched_at": now,
                "total_official": official_total,
                "requested_offices": len(requested),
                "requested_with_pec": sum(1 for office in requested if str(office.get("pec") or "").strip()),
                "offices": requested,
                "error": "",
            }

    return {
        "ok": False,
        "codice_istat": comune.codice_istat,
        "nome": comune.nome,
        "sigla_provincia": comune.sigla_provincia,
        "cap": ",".join(comune.cap),
        "fetched_at": now,
        "total_official": 0,
        "requested_offices": 0,
        "requested_with_pec": 0,
        "offices": [],
        "error": "; ".join(errors)[:500],
    }


def _store_result(conn: sqlite3.Connection, result: dict[str, Any]) -> None:
    conn.execute("DELETE FROM office_associations WHERE comune_istat = ?", (result["codice_istat"],))
    conn.execute(
        """
        INSERT OR REPLACE INTO comuni_status (
          codice_istat, nome, sigla_provincia, cap, fetched_at, ok,
          total_official, requested_offices, requested_with_pec, error
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            result["codice_istat"],
            result["nome"],
            result["sigla_provincia"],
            result["cap"],
            result["fetched_at"],
            1 if result["ok"] else 0,
            int(result["total_official"]),
            int(result["requested_offices"]),
            int(result["requested_with_pec"]),
            result["error"],
        ),
    )
    for office in result["offices"]:
        catalog = _office_for_catalog(office)
        derived_from = json.dumps(list(office.get("derivedFromComuni") or []), ensure_ascii=False)
        conn.execute(
            """
            INSERT OR REPLACE INTO offices (
              office_id, kind, name, pec, city, cap, source_url, office_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(office.get("id") or ""),
                str(office.get("kind") or ""),
                str(office.get("name") or ""),
                str(office.get("pec") or ""),
                str(office.get("city") or ""),
                str(office.get("cap") or ""),
                GIUSTIZIA_MAP_VIEW_URL,
                json.dumps(catalog, ensure_ascii=False, sort_keys=True),
            ),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO office_associations (
              comune_istat, office_id, kind, derived_from, association_source
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                result["codice_istat"],
                str(office.get("id") or ""),
                str(office.get("kind") or ""),
                derived_from,
                str(office.get("associationSource") or ""),
            ),
        )


def build(db_path: Path, territorio_db: Path, *, workers: int, timeout: float, limit: int, resume: bool) -> dict[str, Any]:
    _init_db(db_path)
    _load_fusion_predecessori()
    comuni = _load_comuni(territorio_db, limit=limit)
    done = _already_done(db_path) if resume else set()
    queue = [comune for comune in comuni if comune.codice_istat not in done]
    processed = 0
    errors = 0
    with _connect(db_path) as conn:
        with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
            futures = {executor.submit(_fetch_one, comune, timeout): comune for comune in queue}
            for future in as_completed(futures):
                result = future.result()
                processed += 1
                if not result["ok"]:
                    errors += 1
                _store_result(conn, result)
                if processed % 25 == 0:
                    conn.commit()
                    print(json.dumps({"processed": processed, "remaining": len(queue) - processed, "errors": errors}, ensure_ascii=False))
        conn.commit()
    return {
        "ok": errors == 0,
        "db": str(db_path),
        "territorio_db": str(territorio_db),
        "queued": len(queue),
        "skipped_resume": len(done),
        "processed": processed,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Costruisce la DB Comune -> uffici giudiziari da Giustizia Map.")
    parser.add_argument("--db", default=str(DEFAULT_UFFICI_DB))
    parser.add_argument("--territorio-db", default=str(DEFAULT_TERRITORIO_DB))
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--timeout", type=float, default=14)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args()
    result = build(
        Path(args.db),
        Path(args.territorio_db),
        workers=args.workers,
        timeout=args.timeout,
        limit=args.limit,
        resume=not args.no_resume,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
