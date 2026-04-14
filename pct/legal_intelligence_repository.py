from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any


SCHEMA_LEGAL_INTELLIGENCE_REPOSITORY = Path(__file__).with_name("sql") / "20260414_legal_intelligence_repository.sql"

_DEFAULT_ENGINE_IDS = ["fonti_ufficiali", "audit_affidabilita"]
_DEFAULT_SOURCE_IDS = ["normattiva", "pst_giustizia"]
_LIVE_WEB_MARKERS = (
    "ultima",
    "ultime",
    "ultimo",
    "ultimi",
    "oggi",
    "aggiorn",
    "recent",
    "corrente",
    "vigente",
)
_ENGINE_SCOPE_MAP = {
    "fonti_ufficiali": "fonti_ufficiali",
    "vigenza_versionamento": "normativa",
    "procedurale_telematico": "telematico",
    "giurisprudenza_orientamenti": "giurisprudenza",
    "tassi_finanziari": "tassi",
    "professione_forense": "professione_forense",
    "previdenza_forense": "previdenza_forense",
    "monitoraggio_alert": "monitoraggio",
    "audit_affidabilita": "audit",
}


def _clean_spaces(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _normalize_text(value: Any) -> str:
    return _clean_spaces(value).lower()


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def _to_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _query_terms(question: str) -> list[str]:
    seen: set[str] = set()
    terms: list[str] = []
    for raw in _normalize_text(question).replace("/", " ").replace("-", " ").split():
        token = "".join(ch for ch in raw if ch.isalnum())
        if len(token) < 3 or token in seen:
            continue
        seen.add(token)
        terms.append(token)
    return terms


def _build_search_text(*parts: Any) -> str:
    rows: list[str] = []
    for part in parts:
        if isinstance(part, list):
            for item in part:
                text = _clean_spaces(item)
                if text:
                    rows.append(text)
            continue
        text = _clean_spaces(part)
        if text:
            rows.append(text)
    return "\n".join(rows).strip()


def _drop_keys(row: sqlite3.Row, *keys: str) -> dict[str, Any]:
    payload = dict(row)
    for key in keys:
        payload.pop(key, None)
    return payload


def _payload_signature(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def derive_legal_intelligence_repository_db_path(intelligence_db_path: str) -> str:
    target = Path(intelligence_db_path).resolve()
    return str(target.with_name("legal_intelligence_repository.db"))


def derive_legal_intelligence_repository_json_path(intelligence_db_path: str) -> str:
    target = Path(intelligence_db_path).resolve()
    return str(target.with_name("legal_intelligence_repository.json"))


def derive_legal_sources_json_path(intelligence_db_path: str) -> str:
    target = Path(intelligence_db_path).resolve()
    return str(target.with_name("legal_sources_repository.json"))


def derive_legal_engines_json_path(intelligence_db_path: str) -> str:
    target = Path(intelligence_db_path).resolve()
    return str(target.with_name("legal_engines_repository.json"))


def derive_legal_keyword_engine_json_path(intelligence_db_path: str) -> str:
    target = Path(intelligence_db_path).resolve()
    return str(target.with_name("legal_keyword_to_engine.json"))


def derive_legal_keyword_source_json_path(intelligence_db_path: str) -> str:
    target = Path(intelligence_db_path).resolve()
    return str(target.with_name("legal_keyword_to_source.json"))


def derive_legal_engine_edges_json_path(intelligence_db_path: str) -> str:
    target = Path(intelligence_db_path).resolve()
    return str(target.with_name("legal_engine_source_edges.json"))


def derive_legal_operational_json_path(intelligence_db_path: str) -> str:
    target = Path(intelligence_db_path).resolve()
    return str(target.with_name("legal_operational_repository.json"))


def build_legal_sources_rows(sources: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source in (sources or {}).values():
        payload = source.to_dict() if hasattr(source, "to_dict") else dict(source or {})
        rows.append(
            {
                "source_id": _clean_spaces(payload.get("id")),
                "nome": _clean_spaces(payload.get("nome")),
                "motore": _clean_spaces(payload.get("motore")),
                "area": _clean_spaces(payload.get("area")),
                "official_url": _clean_spaces(payload.get("official_url")),
                "monitor_url": _clean_spaces(payload.get("monitor_url")),
                "connector_kind": _clean_spaces(payload.get("connector_kind")),
                "cadence": _clean_spaces(payload.get("cadence")),
                "formats": [item for item in (_clean_spaces(x) for x in _as_list(payload.get("formats"))) if item],
                "capability": _clean_spaces(payload.get("capability")),
                "notes": _clean_spaces(payload.get("notes")),
                "search_text": _build_search_text(
                    payload.get("id"),
                    payload.get("nome"),
                    payload.get("motore"),
                    payload.get("area"),
                    payload.get("official_url"),
                    payload.get("monitor_url"),
                    payload.get("connector_kind"),
                    payload.get("cadence"),
                    payload.get("formats"),
                    payload.get("capability"),
                    payload.get("notes"),
                ),
            }
        )
    rows.sort(key=lambda row: (row["motore"], row["nome"]))
    return rows


def build_legal_engines_rows(engines: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for engine in (engines or {}).values():
        payload = engine.to_dict() if hasattr(engine, "to_dict") else dict(engine or {})
        rows.append(
            {
                "engine_id": _clean_spaces(payload.get("id")),
                "nome": _clean_spaces(payload.get("nome")),
                "short_name": _clean_spaces(payload.get("short_name")),
                "descrizione": _clean_spaces(payload.get("descrizione")),
                "output": _clean_spaces(payload.get("output")),
                "value": _clean_spaces(payload.get("value")),
                "source_ids": [item for item in (_clean_spaces(x) for x in _as_list(payload.get("source_ids"))) if item],
                "search_text": _build_search_text(
                    payload.get("id"),
                    payload.get("nome"),
                    payload.get("short_name"),
                    payload.get("descrizione"),
                    payload.get("output"),
                    payload.get("value"),
                    payload.get("source_ids"),
                ),
            }
        )
    rows.sort(key=lambda row: row["nome"])
    return rows


def build_legal_keyword_engine_rows(mapping: dict[str, list[str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for keyword, engine_ids in (mapping or {}).items():
        clean_ids = [item for item in (_clean_spaces(x) for x in _as_list(engine_ids)) if item]
        rows.append(
            {
                "keyword": _clean_spaces(keyword),
                "engine_ids": clean_ids,
                "search_text": _build_search_text(keyword, clean_ids),
            }
        )
    rows.sort(key=lambda row: row["keyword"])
    return rows


def build_legal_keyword_source_rows(mapping: dict[str, list[str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for keyword, source_ids in (mapping or {}).items():
        clean_ids = [item for item in (_clean_spaces(x) for x in _as_list(source_ids)) if item]
        rows.append(
            {
                "keyword": _clean_spaces(keyword),
                "source_ids": clean_ids,
                "search_text": _build_search_text(keyword, clean_ids),
            }
        )
    rows.sort(key=lambda row: row["keyword"])
    return rows


def build_legal_engine_edges_rows(
    engine_rows: list[dict[str, Any]],
    source_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    source_index = {row["source_id"]: row for row in source_rows}
    rows: list[dict[str, Any]] = []
    for engine in engine_rows:
        for source_id in engine.get("source_ids") or []:
            source = source_index.get(source_id, {})
            rows.append(
                {
                    "engine_id": engine.get("engine_id") or "",
                    "engine_name": engine.get("nome") or "",
                    "source_id": source_id,
                    "source_name": source.get("nome") or source_id,
                    "area": source.get("area") or "",
                    "search_text": _build_search_text(
                        engine.get("engine_id"),
                        engine.get("nome"),
                        source_id,
                        source.get("nome"),
                        source.get("area"),
                    ),
                }
            )
    rows.sort(key=lambda row: (row["engine_id"], row["source_id"]))
    return rows


def build_legal_monitoring_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in rows or []:
        payload = dict(row or {})
        output.append(
            {
                "source_id": _clean_spaces(payload.get("id") or payload.get("source_id")),
                "nome": _clean_spaces(payload.get("nome")),
                "area": _clean_spaces(payload.get("area")),
                "freshness": _clean_spaces(payload.get("freshness")),
                "last_check": _clean_spaces(payload.get("last_check")),
                "status": _clean_spaces(payload.get("status")),
                "status_code": int(payload.get("status_code") or 0),
                "changed": bool(payload.get("changed")),
                "detected_version": _clean_spaces(payload.get("detected_version")),
                "detected_reference": _clean_spaces(payload.get("detected_reference")),
                "detected_document_url": _clean_spaces(payload.get("detected_document_url")),
                "detected_package": _clean_spaces(payload.get("detected_package")),
                "detected_package_date": _clean_spaces(payload.get("detected_package_date")),
                "detected_status": _clean_spaces(payload.get("detected_status")),
                "detected_news_date": _clean_spaces(payload.get("detected_news_date")),
                "detected_news_url": _clean_spaces(payload.get("detected_news_url")),
                "summary": _clean_spaces(payload.get("summary")),
                "warning": _clean_spaces(payload.get("warning")),
                "official_url": _clean_spaces(payload.get("official_url")),
                "monitor_url": _clean_spaces(payload.get("monitor_url")),
                "connector_kind": _clean_spaces(payload.get("connector_kind")),
                "cadence": _clean_spaces(payload.get("cadence")),
                "formats": [item for item in (_clean_spaces(x) for x in _as_list(payload.get("formats"))) if item],
                "search_text": _build_search_text(
                    payload.get("id"),
                    payload.get("nome"),
                    payload.get("area"),
                    payload.get("freshness"),
                    payload.get("status"),
                    payload.get("detected_version"),
                    payload.get("detected_reference"),
                    payload.get("warning"),
                    payload.get("summary"),
                ),
            }
        )
    return output


def build_legal_alert_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in rows or []:
        payload = dict(row or {})
        output.append(
            {
                "alert_id": _clean_spaces(payload.get("id") or payload.get("alert_id")),
                "created_at": _clean_spaces(payload.get("created_at")),
                "source_id": _clean_spaces(payload.get("source_id")),
                "motore_id": _clean_spaces(payload.get("motore_id")),
                "alert_type": _clean_spaces(payload.get("alert_type")),
                "severity": _clean_spaces(payload.get("severity")),
                "title": _clean_spaces(payload.get("title")),
                "details": _clean_spaces(payload.get("details")),
                "official_url": _clean_spaces(payload.get("official_url")),
                "related_entity_type": _clean_spaces(payload.get("related_entity_type")),
                "related_entity_id": _clean_spaces(payload.get("related_entity_id")),
                "acknowledged": bool(payload.get("acknowledged")),
                "search_text": _build_search_text(
                    payload.get("source_id"),
                    payload.get("motore_id"),
                    payload.get("alert_type"),
                    payload.get("severity"),
                    payload.get("title"),
                    payload.get("details"),
                ),
            }
        )
    output.sort(key=lambda row: row["created_at"], reverse=True)
    return output


def build_legal_audit_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in rows or []:
        payload = dict(row or {})
        engine_ids = [item for item in (_clean_spaces(x) for x in _as_list(payload.get("engine_ids"))) if item]
        source_ids = [item for item in (_clean_spaces(x) for x in _as_list(payload.get("source_ids"))) if item]
        output.append(
            {
                "trace_id": _clean_spaces(payload.get("id") or payload.get("trace_id")),
                "created_at": _clean_spaces(payload.get("created_at")),
                "query": _clean_spaces(payload.get("query")),
                "user_name": _clean_spaces(payload.get("user")),
                "engine_ids": engine_ids,
                "source_ids": source_ids,
                "source_snapshots": list(payload.get("source_snapshots") or []),
                "ai_model": _clean_spaces(payload.get("ai_model")),
                "result_summary": _clean_spaces(payload.get("result_summary")),
                "warning": _clean_spaces(payload.get("warning")),
                "search_text": _build_search_text(
                    payload.get("query"),
                    payload.get("user"),
                    engine_ids,
                    source_ids,
                    payload.get("ai_model"),
                    payload.get("result_summary"),
                    payload.get("warning"),
                ),
            }
        )
    output.sort(key=lambda row: row["created_at"], reverse=True)
    return output


def build_legal_operational_rules() -> list[dict[str, Any]]:
    rows = [
        {
            "rule_code": "deterministic_keyword_routing",
            "title": "Routing deterministico per keyword",
            "scope": "routing",
            "operational_text": (
                "Lex deve partire da keyword, motori legali e fonti ufficiali gia mappate prima di lasciare spazio al modello linguistico."
            ),
            "deterministic": True,
            "sort_order": 1,
        },
        {
            "rule_code": "prefer_official_sources",
            "title": "Priorita alle fonti ufficiali",
            "scope": "fonti",
            "operational_text": (
                "Su normativa, telematico, giurisprudenza e professione forense Lex deve preferire sempre fonti istituzionali o ufficiali."
            ),
            "deterministic": True,
            "sort_order": 2,
        },
        {
            "rule_code": "monitoring_before_claim",
            "title": "Usa il monitoraggio prima di affermare aggiornamenti",
            "scope": "monitoraggio",
            "operational_text": (
                "Se una fonte e in errore, da verificare o cambiata, Lex deve dirlo apertamente prima di trattarla come aggiornata."
            ),
            "deterministic": True,
            "sort_order": 3,
        },
        {
            "rule_code": "audit_trace_explainability",
            "title": "Risposta spiegabile con audit e snapshot",
            "scope": "audit",
            "operational_text": (
                "Lex deve poter spiegare quali motori e quali fonti ufficiali ha usato, richiamando audit, hash e snapshot quando disponibili."
            ),
            "deterministic": True,
            "sort_order": 4,
        },
        {
            "rule_code": "live_web_only_when_needed",
            "title": "Web live solo quando serve",
            "scope": "routing",
            "operational_text": (
                "Il web live entra solo quando l'utente chiede l'ultimo aggiornamento o quando il contesto interno non basta a confermare il dato."
            ),
            "deterministic": True,
            "sort_order": 5,
        },
        {
            "rule_code": "llm_explains_not_decides",
            "title": "Il modello spiega, non decide i fatti",
            "scope": "guardrail",
            "operational_text": (
                "Il modello linguistico scrive, sintetizza e confronta; la verita dei fatti resta vincolata a fonti ufficiali, monitoraggio e audit."
            ),
            "deterministic": True,
            "sort_order": 6,
        },
    ]
    for row in rows:
        row["search_text"] = _build_search_text(
            row.get("rule_code"),
            row.get("title"),
            row.get("scope"),
            row.get("operational_text"),
        )
    return rows


class GestioneLegalIntelligenceRepository:
    def __init__(
        self,
        db_path: str,
        *,
        json_path: str = "",
        sources_json_path: str = "",
        engines_json_path: str = "",
        keyword_engine_json_path: str = "",
        keyword_source_json_path: str = "",
        engine_edges_json_path: str = "",
        operational_json_path: str = "",
    ) -> None:
        self.db_path = str(db_path or "").strip()
        self.json_path = str(json_path or "").strip()
        self.sources_json_path = str(sources_json_path or "").strip()
        self.engines_json_path = str(engines_json_path or "").strip()
        self.keyword_engine_json_path = str(keyword_engine_json_path or "").strip()
        self.keyword_source_json_path = str(keyword_source_json_path or "").strip()
        self.engine_edges_json_path = str(engine_edges_json_path or "").strip()
        self.operational_json_path = str(operational_json_path or "").strip()
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        target = Path(self.db_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(target))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _ensure_schema(self) -> None:
        schema = SCHEMA_LEGAL_INTELLIGENCE_REPOSITORY.read_text(encoding="utf-8")
        with self._connect() as conn:
            conn.executescript(schema)
            conn.commit()

    def _get_meta(self, key: str) -> str:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT meta_value FROM legal_repository_meta WHERE meta_key = ?",
                (key,),
            ).fetchone()
        return str(row["meta_value"]) if row else ""

    def _set_meta(self, conn: sqlite3.Connection, key: str, value: Any) -> None:
        conn.execute(
            """
            INSERT INTO legal_repository_meta (meta_key, meta_value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(meta_key) DO UPDATE SET
                meta_value = excluded.meta_value,
                updated_at = CURRENT_TIMESTAMP
            """,
            (key, _clean_spaces(value)),
        )

    def storage_stats(self) -> dict[str, Any]:
        tables = (
            "legal_sources_repository",
            "legal_engines_repository",
            "legal_keyword_to_engine",
            "legal_keyword_to_source",
            "legal_engine_source_edges",
            "legal_monitoring_repository",
            "legal_alert_repository",
            "legal_audit_repository",
            "legal_operational_repository",
        )
        stats: dict[str, Any] = {
            "db_path": self.db_path,
            "json_path": self.json_path,
            "sources_json_path": self.sources_json_path,
            "engines_json_path": self.engines_json_path,
            "keyword_engine_json_path": self.keyword_engine_json_path,
            "keyword_source_json_path": self.keyword_source_json_path,
            "engine_edges_json_path": self.engine_edges_json_path,
            "operational_json_path": self.operational_json_path,
        }
        with self._connect() as conn:
            for table_name in tables:
                stats[table_name] = int(conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])
        stats["source_signature"] = self._get_meta("source_signature")
        return stats

    def synchronize_runtime(
        self,
        *,
        source_rows: list[dict[str, Any]],
        engine_rows: list[dict[str, Any]],
        keyword_engine_rows: list[dict[str, Any]],
        keyword_source_rows: list[dict[str, Any]],
        edge_rows: list[dict[str, Any]],
        monitoring_rows: list[dict[str, Any]],
        alert_rows: list[dict[str, Any]],
        audit_rows: list[dict[str, Any]],
        operational_rows: list[dict[str, Any]],
        export_json: bool = True,
    ) -> dict[str, Any]:
        payload = {
            "sources": source_rows,
            "engines": engine_rows,
            "keyword_to_engine": keyword_engine_rows,
            "keyword_to_source": keyword_source_rows,
            "engine_source_edges": edge_rows,
            "monitoring": monitoring_rows,
            "alerts": alert_rows,
            "audit_traces": audit_rows,
            "operational_rules": operational_rows,
        }
        signature = _payload_signature(payload)
        current_signature = self._get_meta("source_signature")
        if signature != current_signature:
            self.rebuild_from_payload(payload, source_label="legal_intelligence_runtime")
        if export_json:
            self.export_repository_json()
            self.export_split_jsons()
        return self.storage_stats()

    def rebuild_from_payload(self, payload: dict[str, Any], *, source_label: str = "legal_intelligence_runtime") -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM legal_sources_repository")
            conn.execute("DELETE FROM legal_engines_repository")
            conn.execute("DELETE FROM legal_keyword_to_engine")
            conn.execute("DELETE FROM legal_keyword_to_source")
            conn.execute("DELETE FROM legal_engine_source_edges")
            conn.execute("DELETE FROM legal_monitoring_repository")
            conn.execute("DELETE FROM legal_alert_repository")
            conn.execute("DELETE FROM legal_audit_repository")
            conn.execute("DELETE FROM legal_operational_repository")

            for row in payload.get("sources") or []:
                conn.execute(
                    """
                    INSERT INTO legal_sources_repository (
                        source_id, nome, motore, area, official_url, monitor_url,
                        connector_kind, cadence, formats_json, capability, notes, search_text
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row.get("source_id"),
                        row.get("nome"),
                        row.get("motore"),
                        row.get("area"),
                        row.get("official_url"),
                        row.get("monitor_url"),
                        row.get("connector_kind"),
                        row.get("cadence"),
                        _to_json(row.get("formats") or []),
                        row.get("capability") or "",
                        row.get("notes") or "",
                        row.get("search_text") or "",
                    ),
                )

            for row in payload.get("engines") or []:
                conn.execute(
                    """
                    INSERT INTO legal_engines_repository (
                        engine_id, nome, short_name, descrizione, output, value,
                        source_ids_json, search_text
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row.get("engine_id"),
                        row.get("nome"),
                        row.get("short_name"),
                        row.get("descrizione"),
                        row.get("output"),
                        row.get("value"),
                        _to_json(row.get("source_ids") or []),
                        row.get("search_text") or "",
                    ),
                )

            for row in payload.get("keyword_to_engine") or []:
                conn.execute(
                    "INSERT INTO legal_keyword_to_engine (keyword, engine_ids_json, search_text) VALUES (?, ?, ?)",
                    (row.get("keyword"), _to_json(row.get("engine_ids") or []), row.get("search_text") or ""),
                )

            for row in payload.get("keyword_to_source") or []:
                conn.execute(
                    "INSERT INTO legal_keyword_to_source (keyword, source_ids_json, search_text) VALUES (?, ?, ?)",
                    (row.get("keyword"), _to_json(row.get("source_ids") or []), row.get("search_text") or ""),
                )

            for row in payload.get("engine_source_edges") or []:
                conn.execute(
                    """
                    INSERT INTO legal_engine_source_edges (
                        engine_id, source_id, engine_name, source_name, area, search_text
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row.get("engine_id"),
                        row.get("source_id"),
                        row.get("engine_name") or "",
                        row.get("source_name") or "",
                        row.get("area") or "",
                        row.get("search_text") or "",
                    ),
                )

            for row in payload.get("monitoring") or []:
                conn.execute(
                    """
                    INSERT INTO legal_monitoring_repository (
                        source_id, nome, area, freshness, last_check, status, status_code,
                        changed, detected_version, detected_reference, detected_document_url,
                        detected_package, detected_package_date, detected_status,
                        detected_news_date, detected_news_url, summary, warning,
                        official_url, monitor_url, connector_kind, cadence, formats_json, search_text
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row.get("source_id"),
                        row.get("nome") or "",
                        row.get("area") or "",
                        row.get("freshness") or "",
                        row.get("last_check") or "",
                        row.get("status") or "",
                        int(row.get("status_code") or 0),
                        1 if row.get("changed") else 0,
                        row.get("detected_version") or "",
                        row.get("detected_reference") or "",
                        row.get("detected_document_url") or "",
                        row.get("detected_package") or "",
                        row.get("detected_package_date") or "",
                        row.get("detected_status") or "",
                        row.get("detected_news_date") or "",
                        row.get("detected_news_url") or "",
                        row.get("summary") or "",
                        row.get("warning") or "",
                        row.get("official_url") or "",
                        row.get("monitor_url") or "",
                        row.get("connector_kind") or "",
                        row.get("cadence") or "",
                        _to_json(row.get("formats") or []),
                        row.get("search_text") or "",
                    ),
                )

            for row in payload.get("alerts") or []:
                conn.execute(
                    """
                    INSERT INTO legal_alert_repository (
                        alert_id, created_at, source_id, motore_id, alert_type, severity,
                        title, details, official_url, related_entity_type, related_entity_id,
                        acknowledged, search_text
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row.get("alert_id"),
                        row.get("created_at"),
                        row.get("source_id") or "",
                        row.get("motore_id") or "",
                        row.get("alert_type") or "",
                        row.get("severity") or "",
                        row.get("title") or "",
                        row.get("details") or "",
                        row.get("official_url") or "",
                        row.get("related_entity_type") or "",
                        row.get("related_entity_id") or "",
                        1 if row.get("acknowledged") else 0,
                        row.get("search_text") or "",
                    ),
                )

            for row in payload.get("audit_traces") or []:
                conn.execute(
                    """
                    INSERT INTO legal_audit_repository (
                        trace_id, created_at, query, user_name, engine_ids_json, source_ids_json,
                        source_snapshots_json, ai_model, result_summary, warning, search_text
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row.get("trace_id"),
                        row.get("created_at"),
                        row.get("query") or "",
                        row.get("user_name") or "",
                        _to_json(row.get("engine_ids") or []),
                        _to_json(row.get("source_ids") or []),
                        _to_json(row.get("source_snapshots") or []),
                        row.get("ai_model") or "",
                        row.get("result_summary") or "",
                        row.get("warning") or "",
                        row.get("search_text") or "",
                    ),
                )

            for row in payload.get("operational_rules") or []:
                conn.execute(
                    """
                    INSERT INTO legal_operational_repository (
                        rule_code, title, scope, operational_text, deterministic, sort_order, search_text
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row.get("rule_code"),
                        row.get("title"),
                        row.get("scope"),
                        row.get("operational_text"),
                        1 if row.get("deterministic", True) else 0,
                        int(row.get("sort_order") or 0),
                        row.get("search_text") or "",
                    ),
                )

            self._set_meta(conn, "source_signature", _payload_signature(payload))
            self._set_meta(conn, "source_label", source_label)
            conn.commit()

    def load_repository_payload(self) -> dict[str, Any]:
        with self._connect() as conn:
            sources = [
                {
                    **_drop_keys(row, "formats_json"),
                    "formats": json.loads(row["formats_json"] or "[]"),
                }
                for row in conn.execute("SELECT * FROM legal_sources_repository ORDER BY motore, nome").fetchall()
            ]
            engines = [
                {
                    **_drop_keys(row, "source_ids_json"),
                    "source_ids": json.loads(row["source_ids_json"] or "[]"),
                }
                for row in conn.execute("SELECT * FROM legal_engines_repository ORDER BY nome").fetchall()
            ]
            keyword_to_engine = [
                {
                    **_drop_keys(row, "engine_ids_json"),
                    "engine_ids": json.loads(row["engine_ids_json"] or "[]"),
                }
                for row in conn.execute("SELECT * FROM legal_keyword_to_engine ORDER BY keyword").fetchall()
            ]
            keyword_to_source = [
                {
                    **_drop_keys(row, "source_ids_json"),
                    "source_ids": json.loads(row["source_ids_json"] or "[]"),
                }
                for row in conn.execute("SELECT * FROM legal_keyword_to_source ORDER BY keyword").fetchall()
            ]
            engine_source_edges = [
                dict(row)
                for row in conn.execute("SELECT * FROM legal_engine_source_edges ORDER BY engine_id, source_id").fetchall()
            ]
            monitoring = [
                {
                    **_drop_keys(row, "formats_json"),
                    "formats": json.loads(row["formats_json"] or "[]"),
                }
                for row in conn.execute("SELECT * FROM legal_monitoring_repository ORDER BY source_id").fetchall()
            ]
            alerts = [dict(row) for row in conn.execute("SELECT * FROM legal_alert_repository ORDER BY created_at DESC").fetchall()]
            audit_traces = [
                {
                    **_drop_keys(row, "engine_ids_json", "source_ids_json", "source_snapshots_json"),
                    "engine_ids": json.loads(row["engine_ids_json"] or "[]"),
                    "source_ids": json.loads(row["source_ids_json"] or "[]"),
                    "source_snapshots": json.loads(row["source_snapshots_json"] or "[]"),
                }
                for row in conn.execute("SELECT * FROM legal_audit_repository ORDER BY created_at DESC").fetchall()
            ]
            operational_rules = [
                dict(row)
                for row in conn.execute("SELECT * FROM legal_operational_repository ORDER BY sort_order, rule_code").fetchall()
            ]
        return {
            "source": self._get_meta("source_label") or "legal_intelligence_runtime",
            "counts": {
                "sources": len(sources),
                "engines": len(engines),
                "keyword_to_engine": len(keyword_to_engine),
                "keyword_to_source": len(keyword_to_source),
                "engine_source_edges": len(engine_source_edges),
                "monitoring": len(monitoring),
                "alerts": len(alerts),
                "audit_traces": len(audit_traces),
                "operational_rules": len(operational_rules),
            },
            "sources": sources,
            "engines": engines,
            "keyword_to_engine": keyword_to_engine,
            "keyword_to_source": keyword_to_source,
            "engine_source_edges": engine_source_edges,
            "monitoring": monitoring,
            "alerts": alerts,
            "audit_traces": audit_traces,
            "operational_rules": operational_rules,
        }

    def export_repository_json(self, path: str | None = None) -> str:
        target = Path(path or self.json_path)
        if not str(target):
            raise ValueError("Percorso JSON repository legal intelligence non configurato.")
        payload = self.load_repository_payload()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(target)

    def export_split_jsons(self, base_dir: str | None = None) -> dict[str, str]:
        payload = self.load_repository_payload()
        if base_dir:
            base = Path(base_dir)
            paths = {
                "repository": str(base / "legal_intelligence_repository.json"),
                "sources": str(base / "legal_sources_repository.json"),
                "engines": str(base / "legal_engines_repository.json"),
                "keyword_to_engine": str(base / "legal_keyword_to_engine.json"),
                "keyword_to_source": str(base / "legal_keyword_to_source.json"),
                "engine_source_edges": str(base / "legal_engine_source_edges.json"),
                "operational": str(base / "legal_operational_repository.json"),
            }
        else:
            paths = {
                "repository": self.json_path,
                "sources": self.sources_json_path,
                "engines": self.engines_json_path,
                "keyword_to_engine": self.keyword_engine_json_path,
                "keyword_to_source": self.keyword_source_json_path,
                "engine_source_edges": self.engine_edges_json_path,
                "operational": self.operational_json_path,
            }
        for path in paths.values():
            if path:
                Path(path).parent.mkdir(parents=True, exist_ok=True)
        if paths["repository"]:
            Path(paths["repository"]).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        if paths["sources"]:
            Path(paths["sources"]).write_text(
                json.dumps(
                    {"repository": "legal_sources_repository", "count": len(payload["sources"]), "rows": payload["sources"]},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        if paths["engines"]:
            Path(paths["engines"]).write_text(
                json.dumps(
                    {"repository": "legal_engines_repository", "count": len(payload["engines"]), "rows": payload["engines"]},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        if paths["keyword_to_engine"]:
            Path(paths["keyword_to_engine"]).write_text(
                json.dumps(
                    {
                        "repository": "legal_keyword_to_engine",
                        "count": len(payload["keyword_to_engine"]),
                        "rows": payload["keyword_to_engine"],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        if paths["keyword_to_source"]:
            Path(paths["keyword_to_source"]).write_text(
                json.dumps(
                    {
                        "repository": "legal_keyword_to_source",
                        "count": len(payload["keyword_to_source"]),
                        "rows": payload["keyword_to_source"],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        if paths["engine_source_edges"]:
            Path(paths["engine_source_edges"]).write_text(
                json.dumps(
                    {
                        "repository": "legal_engine_source_edges",
                        "count": len(payload["engine_source_edges"]),
                        "rows": payload["engine_source_edges"],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        if paths["operational"]:
            Path(paths["operational"]).write_text(
                json.dumps(
                    {
                        "repository": "legal_operational_repository",
                        "count": len(payload["operational_rules"]),
                        "rows": payload["operational_rules"],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        return paths

    def resolve_route(
        self,
        question: str,
        *,
        limit_sources: int = 5,
        limit_engines: int = 4,
        limit_alerts: int = 4,
        limit_audits: int = 4,
    ) -> dict[str, Any]:
        payload = self.load_repository_payload()
        normalized_question = _normalize_text(question)
        terms = _query_terms(question)

        matched_engine_keywords: list[dict[str, Any]] = []
        engine_ids: list[str] = []
        for row in payload.get("keyword_to_engine") or []:
            keyword = _normalize_text(row.get("keyword"))
            if keyword and keyword in normalized_question:
                matched_engine_keywords.append(row)
                for engine_id in row.get("engine_ids") or []:
                    if engine_id not in engine_ids:
                        engine_ids.append(engine_id)

        matched_source_keywords: list[dict[str, Any]] = []
        source_ids: list[str] = []
        for row in payload.get("keyword_to_source") or []:
            keyword = _normalize_text(row.get("keyword"))
            if keyword and keyword in normalized_question:
                matched_source_keywords.append(row)
                for source_id in row.get("source_ids") or []:
                    if source_id not in source_ids:
                        source_ids.append(source_id)

        engine_index = {row["engine_id"]: row for row in payload.get("engines") or []}
        source_index = {row["source_id"]: row for row in payload.get("sources") or []}
        monitoring_index = {row["source_id"]: row for row in payload.get("monitoring") or []}

        if not engine_ids:
            scored_engines: list[tuple[int, dict[str, Any]]] = []
            for row in payload.get("engines") or []:
                haystack = _normalize_text(row.get("search_text"))
                score = sum(1 for term in terms if term in haystack)
                scored_engines.append((score, row))
            scored_engines.sort(key=lambda item: item[0], reverse=True)
            engine_ids = [row["engine_id"] for score, row in scored_engines if score > 0][:limit_engines]
        if not engine_ids:
            engine_ids = list(_DEFAULT_ENGINE_IDS)

        if not source_ids:
            for edge in payload.get("engine_source_edges") or []:
                if edge.get("engine_id") in engine_ids and edge.get("source_id") not in source_ids:
                    source_ids.append(edge.get("source_id"))
                    if len(source_ids) >= limit_sources:
                        break
        if not source_ids:
            scored_sources: list[tuple[int, dict[str, Any]]] = []
            for row in payload.get("sources") or []:
                haystack = _normalize_text(row.get("search_text"))
                score = sum(1 for term in terms if term in haystack)
                scored_sources.append((score, row))
            scored_sources.sort(key=lambda item: item[0], reverse=True)
            source_ids = [row["source_id"] for score, row in scored_sources if score > 0][:limit_sources]
        if not source_ids:
            source_ids = list(_DEFAULT_SOURCE_IDS)

        engine_rows = [engine_index[engine_id] for engine_id in engine_ids if engine_id in engine_index][:limit_engines]
        source_rows = [source_index[source_id] for source_id in source_ids if source_id in source_index][:limit_sources]
        monitoring_rows = [monitoring_index[source_id] for source_id in source_ids if source_id in monitoring_index][:limit_sources]

        relevant_alerts = [
            row
            for row in (payload.get("alerts") or [])
            if row.get("source_id") in source_ids or row.get("motore_id") in engine_ids
        ][:limit_alerts]
        relevant_audits = [
            row
            for row in (payload.get("audit_traces") or [])
            if set(row.get("engine_ids") or []).intersection(engine_ids)
            or set(row.get("source_ids") or []).intersection(source_ids)
            or any(term in _normalize_text(row.get("search_text")) for term in terms)
        ][:limit_audits]

        dominant_engine = engine_ids[0] if engine_ids else _DEFAULT_ENGINE_IDS[0]
        route_scope = _ENGINE_SCOPE_MAP.get(dominant_engine, "fonti_ufficiali")
        needs_live_web = any(marker in normalized_question for marker in _LIVE_WEB_MARKERS)
        reason_parts: list[str] = []
        if matched_engine_keywords:
            reason_parts.append(
                "motori da keyword: " + ", ".join(row.get("keyword") or "" for row in matched_engine_keywords[:3])
            )
        if matched_source_keywords:
            reason_parts.append(
                "fonti da keyword: " + ", ".join(row.get("keyword") or "" for row in matched_source_keywords[:3])
            )
        if not reason_parts:
            reason_parts.append("routing semantico sul repository legale")

        return {
            "question": _clean_spaces(question),
            "normalized_question": normalized_question,
            "route_scope": route_scope,
            "engine_ids": engine_ids,
            "source_ids": source_ids,
            "engine_rows": engine_rows,
            "source_rows": source_rows,
            "monitoring_rows": monitoring_rows,
            "alert_rows": relevant_alerts,
            "audit_rows": relevant_audits,
            "matched_engine_keywords": [row.get("keyword") for row in matched_engine_keywords],
            "matched_source_keywords": [row.get("keyword") for row in matched_source_keywords],
            "reason": "; ".join(part for part in reason_parts if part),
            "needs_live_web": needs_live_web,
        }
