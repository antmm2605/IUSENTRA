"""Read-only lookup helpers for the local ReGIndE certified cache."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import unicodedata
from pathlib import Path
from typing import Any


def default_reginde_cache_db_path(root: Path | None = None) -> Path:
    data_root = os.environ.get("PCT_DATA_ROOT")
    if data_root and root is None:
        return Path(data_root) / "local" / "reginde" / "reginde_cache.sqlite"
    repo_root = root or Path(__file__).resolve().parents[2]
    return repo_root / "data" / "local" / "reginde" / "reginde_cache.sqlite"


def default_registro_ppaa_cache_db_path(root: Path | None = None) -> Path:
    data_root = os.environ.get("PCT_DATA_ROOT")
    if data_root and root is None:
        return Path(data_root) / "local" / "registro_ppaa" / "registro_ppaa_cache.sqlite"
    repo_root = root or Path(__file__).resolve().parents[2]
    return repo_root / "data" / "local" / "registro_ppaa" / "registro_ppaa_cache.sqlite"


def _json_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    try:
        payload = json.loads(str(value or "[]"))
    except Exception:
        return []
    if not isinstance(payload, list):
        return []
    return [str(item).strip() for item in payload if str(item).strip()]


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    try:
        payload = json.loads(str(value or "{}"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _normalise_search_text(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text.lower()).strip()


def _fts_query(value: str) -> str:
    tokens = re.findall(r"[a-z0-9_]{2,}", _normalise_search_text(value))
    return " ".join(f"{token}*" for token in tokens[:8])


def _recipient_role(record: dict[str, Any], *, register_value: str) -> str:
    if register_value == "registro_ppaa":
        return "pa"
    haystack = _normalise_search_text(" ".join(str(record.get(key) or "") for key in ("denominazione", "nome_completo", "ruolo")))
    if "avvocatura" in haystack:
        return "pa"
    if "avvocato" in haystack or "difensore" in haystack:
        return "difensore"
    return "professionista"


def _row_to_recipients(
    row: sqlite3.Row,
    *,
    register_value: str,
    register_badge: str,
    cache_source: str,
) -> list[dict[str, Any]]:
    pecs = _json_list(row["pec_json"])
    if not pecs:
        return []
    codici = _json_list(row["codici_fiscali_json"])
    partite_iva = _json_list(row["partite_iva_json"])
    identity = (codici + partite_iva + [""])[0]
    record = {
        "record_key": row["record_key"],
        "denominazione": row["denominazione"] or "",
        "nome_completo": row["nome_completo"] or "",
        "ruolo": row["ruolo"] or "",
        "stato": row["stato"] or "",
        "last_seen_at": row["last_seen_at"] or "",
    }
    record_payload = _json_object(row["record_json"])
    nome = record["nome_completo"] or record["denominazione"]
    role = _recipient_role(record, register_value=register_value)
    recipients: list[dict[str, Any]] = []
    for pec in pecs[:6]:
        pec_norm = pec.strip().lower()
        if "@" not in pec_norm:
            continue
        key_hash = hashlib.sha256(f"{register_value}|{row['record_key']}|{pec_norm}".encode("utf-8")).hexdigest()[:16]
        recipients.append({
            "id": f"{register_value}-cache-{key_hash}",
            "label": nome or pec_norm,
            "nome": nome,
            "codiceFiscalePiva": identity,
            "pec": pec_norm,
            "ruolo": role,
            "ruoloPratica": register_badge,
            "fontePecSuggerita": register_value,
            "parteRappresentata": "",
            "verificaRichiesta": True,
            "cacheSource": cache_source,
            "aggiornatoIl": record["last_seen_at"],
            "stato": record["stato"],
            "nomeAnagrafico": str(record_payload.get("nome") or "").strip(),
            "cognomeAnagrafico": str(record_payload.get("cognome") or "").strip(),
            "denominazione": record["denominazione"],
            "recordKey": str(row["record_key"] or ""),
        })
    return recipients


def _cache_state(db_path: Path) -> dict[str, Any]:
    manifest_path = db_path.parent / "manifest.json"
    if not manifest_path.exists():
        return {}
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _has_fts(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='records_fts'"
    ).fetchone()
    return bool(row)


def _fallback_rows(conn: sqlite3.Connection, query: str, limit: int) -> list[sqlite3.Row]:
    tokens = re.findall(r"[a-z0-9_]{2,}", _normalise_search_text(query))[:8]
    if not tokens:
        tokens = [_normalise_search_text(query)]
    field_clause = """
        (
            lower(denominazione) LIKE ?
            OR lower(nome_completo) LIKE ?
            OR lower(codici_fiscali_json) LIKE ?
            OR lower(partite_iva_json) LIKE ?
            OR lower(pec_json) LIKE ?
            OR lower(ruolo) LIKE ?
        )
    """
    where_parts = []
    params: list[Any] = []
    for token in tokens:
        like = f"%{token}%"
        where_parts.append(field_clause)
        params.extend([like, like, like, like, like, like])
    params.append(limit)
    return list(conn.execute(
        f"""
        SELECT *
        FROM records
        WHERE visibile = 1
          AND {" AND ".join(where_parts)}
        ORDER BY last_seen_at DESC, denominazione, nome_completo
        LIMIT ?
        """,
        tuple(params),
    ))


def search_public_register_cache(
    db_path: Path,
    query: str,
    *,
    limit: int = 25,
    register_value: str,
    register_label: str,
    register_badge: str,
    cache_source: str,
) -> dict[str, Any]:
    query = (query or "").strip()
    safe_limit = max(1, min(int(limit or 25), 50))
    state = _cache_state(db_path)
    if len(query) < 3:
        return {
            "available": db_path.exists(),
            "complete": bool(state.get("complete")),
            "records": int((state.get("stats") or {}).get("records_distinct") or 0),
            "nextStart": int(state.get("next_start") or 0),
            "updatedAt": str(state.get("updated_at_europe_rome") or ""),
            "results": [],
            "message": f"Digita almeno 3 caratteri per cercare in {register_label} locale.",
        }
    if not db_path.exists():
        return {
            "available": False,
            "complete": False,
            "records": 0,
            "nextStart": 0,
            "updatedAt": "",
            "results": [],
            "message": f"{register_label} locale non ancora sincronizzato.",
        }

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA query_only=ON")
        total_row = conn.execute("SELECT COUNT(*) AS total FROM records").fetchone()
        total = int(total_row["total"] if total_row else 0)
        rows: list[sqlite3.Row]
        fts_query = _fts_query(query)
        if fts_query and _has_fts(conn):
            try:
                rows = list(conn.execute(
                    """
                    SELECT r.*
                    FROM records_fts f
                    JOIN records r ON r.record_key = f.record_key
                    WHERE records_fts MATCH ?
                      AND r.visibile = 1
                    ORDER BY rank
                    LIMIT ?
                    """,
                    (fts_query, safe_limit),
                ))
            except sqlite3.Error:
                rows = _fallback_rows(conn, query, safe_limit)
        else:
            rows = _fallback_rows(conn, query, safe_limit)

        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for row in rows:
            for item in _row_to_recipients(
                row,
                register_value=register_value,
                register_badge=register_badge,
                cache_source=cache_source,
            ):
                key = f"{item['pec']}|{item['codiceFiscalePiva']}|{item['nome']}".lower()
                if key in seen:
                    continue
                seen.add(key)
                results.append(item)
                if len(results) >= safe_limit:
                    break
            if len(results) >= safe_limit:
                break

        return {
            "available": True,
            "complete": bool(state.get("complete")),
            "records": total,
            "nextStart": int(state.get("next_start") or 0),
            "updatedAt": str(state.get("updated_at_europe_rome") or ""),
            "results": results,
            "message": "" if results else f"Nessun soggetto trovato in {register_label} locale.",
        }
    finally:
        conn.close()


def search_reginde_cache(db_path: Path, query: str, *, limit: int = 25) -> dict[str, Any]:
    return search_public_register_cache(
        db_path,
        query,
        limit=limit,
        register_value="reginde",
        register_label="ReGIndE",
        register_badge="ReGIndE",
        cache_source="reginde_cache_locale",
    )


def search_registro_ppaa_cache(db_path: Path, query: str, *, limit: int = 25) -> dict[str, Any]:
    return search_public_register_cache(
        db_path,
        query,
        limit=limit,
        register_value="registro_ppaa",
        register_label="Registro PP.AA.",
        register_badge="Registro PP.AA.",
        cache_source="registro_ppaa_cache_locale",
    )
