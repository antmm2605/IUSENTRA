from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pct.postgres_runtime_support import PostgresRepositoryBackend

SCHEMA_LEGAL_UPDATE_PIPELINE = Path(__file__).with_name("sql") / "20260418_legal_update_pipeline.sql"
POSTGRES_SCHEMA_LEGAL_UPDATE_PIPELINE = (
    Path(__file__).with_name("sql") / "20260419_legal_update_pipeline_postgres.sql"
)

DEFAULT_MATTERS: tuple[dict[str, Any], ...] = (
    {"name": "Diritto civile", "slug": "diritto_civile", "parent_slug": "", "level": 1, "sort_order": 10},
    {"name": "Diritto penale", "slug": "diritto_penale", "parent_slug": "", "level": 1, "sort_order": 20},
    {"name": "Diritto del lavoro", "slug": "diritto_lavoro", "parent_slug": "", "level": 1, "sort_order": 30},
    {"name": "Diritto tributario", "slug": "diritto_tributario", "parent_slug": "", "level": 1, "sort_order": 40},
    {"name": "Diritto amministrativo", "slug": "diritto_amministrativo", "parent_slug": "", "level": 1, "sort_order": 50},
    {"name": "Diritto societario", "slug": "diritto_societario", "parent_slug": "", "level": 1, "sort_order": 60},
    {"name": "Crisi d'impresa", "slug": "diritto_fallimentare_crisi_impresa", "parent_slug": "", "level": 1, "sort_order": 70},
    {"name": "Diritto di famiglia", "slug": "diritto_famiglia", "parent_slug": "", "level": 1, "sort_order": 80},
    {"name": "Diritto immobiliare", "slug": "diritto_immobiliare", "parent_slug": "", "level": 1, "sort_order": 90},
    {"name": "Privacy e protezione dati", "slug": "privacy_protezione_dati", "parent_slug": "", "level": 1, "sort_order": 100},
    {"name": "Appalti e contratti pubblici", "slug": "appalti_contratti_pubblici", "parent_slug": "", "level": 1, "sort_order": 110},
    {"name": "Diritto UE", "slug": "diritto_ue", "parent_slug": "", "level": 1, "sort_order": 120},
    {"name": "Previdenza e assistenza", "slug": "previdenza_assistenza", "parent_slug": "", "level": 1, "sort_order": 130},
    {"name": "Consumatori", "slug": "consumatori", "parent_slug": "", "level": 1, "sort_order": 140},
    {"name": "Ambiente ed energia", "slug": "ambiente_energia", "parent_slug": "", "level": 1, "sort_order": 150},
    {"name": "Sanita", "slug": "sanita", "parent_slug": "", "level": 1, "sort_order": 160},
    {"name": "Edilizia e urbanistica", "slug": "edilizia_urbanistica", "parent_slug": "", "level": 1, "sort_order": 170},
    {"name": "Trasporti", "slug": "trasporti", "parent_slug": "", "level": 1, "sort_order": 180},
    {"name": "Scuola e universita", "slug": "scuola_universita", "parent_slug": "", "level": 1, "sort_order": 190},
    {"name": "Pubblico impiego", "slug": "pubblico_impiego", "parent_slug": "", "level": 1, "sort_order": 200},
    {"name": "Contratti", "slug": "contratti", "parent_slug": "diritto_civile", "level": 2, "sort_order": 210},
    {"name": "Responsabilita civile", "slug": "responsabilita_civile", "parent_slug": "diritto_civile", "level": 2, "sort_order": 220},
    {"name": "Locazioni", "slug": "locazioni", "parent_slug": "diritto_immobiliare", "level": 2, "sort_order": 230},
    {"name": "Licenziamenti", "slug": "licenziamenti", "parent_slug": "diritto_lavoro", "level": 2, "sort_order": 240},
    {"name": "Sicurezza sul lavoro", "slug": "sicurezza_sul_lavoro", "parent_slug": "diritto_lavoro", "level": 2, "sort_order": 250},
    {"name": "IVA", "slug": "iva", "parent_slug": "diritto_tributario", "level": 2, "sort_order": 260},
    {"name": "Accertamento", "slug": "accertamento", "parent_slug": "diritto_tributario", "level": 2, "sort_order": 270},
    {"name": "Riscossione", "slug": "riscossione", "parent_slug": "diritto_tributario", "level": 2, "sort_order": 280},
    {"name": "Processo amministrativo", "slug": "processo_amministrativo", "parent_slug": "diritto_amministrativo", "level": 2, "sort_order": 290},
    {"name": "GDPR", "slug": "gdpr", "parent_slug": "privacy_protezione_dati", "level": 2, "sort_order": 300},
    {"name": "Data breach", "slug": "data_breach", "parent_slug": "privacy_protezione_dati", "level": 2, "sort_order": 310},
    {"name": "Appalti sotto soglia", "slug": "appalti_sotto_soglia", "parent_slug": "appalti_contratti_pubblici", "level": 2, "sort_order": 320},
    {"name": "Appalti sopra soglia", "slug": "appalti_sopra_soglia", "parent_slug": "appalti_contratti_pubblici", "level": 2, "sort_order": 330},
    {"name": "Concordato", "slug": "concordato", "parent_slug": "diritto_fallimentare_crisi_impresa", "level": 2, "sort_order": 340},
    {"name": "Composizione negoziata", "slug": "composizione_negoziata", "parent_slug": "diritto_fallimentare_crisi_impresa", "level": 2, "sort_order": 350},
    {"name": "Esecuzione penale", "slug": "esecuzione_penale", "parent_slug": "diritto_penale", "level": 2, "sort_order": 360},
    {"name": "Procedura civile", "slug": "procedura_civile", "parent_slug": "diritto_civile", "level": 2, "sort_order": 370},
    {"name": "Procedura penale", "slug": "procedura_penale", "parent_slug": "diritto_penale", "level": 2, "sort_order": 380},
    {"name": "Giurisprudenza di merito", "slug": "giurisprudenza_merito", "parent_slug": "diritto_civile", "level": 2, "sort_order": 390},
    {"name": "Avvocati e professione forense", "slug": "avvocati_professione_forense", "parent_slug": "diritto_civile", "level": 2, "sort_order": 400},
    {"name": "Notifiche e PEC", "slug": "notifiche_pec", "parent_slug": "diritto_civile", "level": 2, "sort_order": 410},
    {"name": "Onere della prova", "slug": "onere_della_prova", "parent_slug": "diritto_civile", "level": 2, "sort_order": 420},
    {"name": "Nullita", "slug": "nullita", "parent_slug": "diritto_civile", "level": 2, "sort_order": 430},
    {"name": "Termini processuali", "slug": "termini_processuali", "parent_slug": "procedura_civile", "level": 3, "sort_order": 440},
    {"name": "Separazione e divorzio", "slug": "separazione_divorzio", "parent_slug": "diritto_famiglia", "level": 2, "sort_order": 450},
    {"name": "Figli e mantenimento", "slug": "figli_mantenimento", "parent_slug": "diritto_famiglia", "level": 2, "sort_order": 460},
    {"name": "Decreto ingiuntivo e opposizione", "slug": "decreto_ingiuntivo_opposizione", "parent_slug": "procedura_civile", "level": 3, "sort_order": 470},
    {"name": "Opposizione ISTAT", "slug": "opposizione_istat", "parent_slug": "procedura_civile", "level": 3, "sort_order": 480},
    {"name": "Circolazione stradale", "slug": "circolazione_stradale", "parent_slug": "diritto_civile", "level": 2, "sort_order": 490},
    {"name": "Compensi avvocato", "slug": "compensi_avvocato", "parent_slug": "avvocati_professione_forense", "level": 3, "sort_order": 500},
)


def _clean_spaces(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _normalize_token(value: Any) -> str:
    return _clean_spaces(value).lower()


def _json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _json_load(value: Any, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return default


def _source_agent_payload_errors(payload: dict[str, Any] | None) -> list[str]:
    data = payload if isinstance(payload, dict) else {}
    reports = data.get("reports")
    if not isinstance(reports, list):
        report = data.get("report")
        reports = report.get("reports") if isinstance(report, dict) else []
    errors: list[str] = []
    for item in reports or []:
        if not isinstance(item, dict):
            continue
        message = _clean_spaces(item.get("error") or item.get("error_message"))
        if message:
            errors.append(message)
    direct_error = _clean_spaces(data.get("error") or data.get("error_message"))
    if direct_error:
        errors.append(direct_error)
    return errors


def _source_agent_resolution_hint(source_code: str, message: str) -> str:
    code = _normalize_token(source_code)
    if code == "giustizia_amministrativa" and "openga" not in message.casefold():
        return (
            "Risoluzione automatica: fonte HTML diretta in osservazione; "
            "presidio automatico affidato a OpenGA ufficiale."
        )
    return ""


def _source_agent_error_message(source_code: str, errors: list[str], existing: Any = "") -> str:
    parts = [_clean_spaces(existing)]
    parts.extend(_clean_spaces(error) for error in errors)
    message = "; ".join(dict.fromkeys(part for part in parts if part))
    hint = _source_agent_resolution_hint(source_code, message)
    if hint:
        message = "; ".join(part for part in (message, hint) if part)
    return message


def _slugify(value: str) -> str:
    text = _normalize_token(value)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "record"


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _sha1(value: str) -> str:
    return hashlib.sha1((value or "").encode("utf-8")).hexdigest()


def _ascii_fold(value: Any) -> str:
    return (
        unicodedata.normalize("NFKD", _clean_spaces(value))
        .encode("ascii", "ignore")
        .decode("ascii")
    )


def _canonical_text(value: Any) -> str:
    text = _ascii_fold(value).casefold()
    text = re.sub(r"\b(nr|num|numero)\.?\b", " n ", text)
    text = re.sub(r"\bdel\b", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return _clean_spaces(text)


def _canonical_authority(value: Any) -> str:
    text = _canonical_text(value)
    if "cassazione" in text:
        return "corte cassazione"
    if "costituzionale" in text:
        return "corte costituzionale"
    if "consiglio stato" in text:
        return "consiglio stato"
    if re.search(r"\btar\b", text):
        return "tar"
    if "agenzia entrate" in text:
        return "agenzia entrate"
    if "gazzetta ufficiale" in text:
        return "gazzetta ufficiale"
    return text


def _canonical_url(value: Any) -> str:
    raw = _clean_spaces(value)
    if not raw:
        return ""
    split = urlsplit(raw)
    netloc = split.netloc.casefold()
    path = re.sub(r"/+", "/", split.path or "/").rstrip("/")
    ignored = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "fbclid", "gclid"}
    query_items = [
        (key, val)
        for key, val in parse_qsl(split.query, keep_blank_values=True)
        if key.casefold() not in ignored
    ]
    query = urlencode(sorted(query_items))
    return urlunsplit((split.scheme.casefold(), netloc, path or "/", query, ""))


def _year_from_any(*values: Any) -> str:
    for value in values:
        match = re.search(r"\b(20[0-9]{2}|19[0-9]{2})\b", _clean_spaces(value))
        if match:
            return match.group(1)
    return ""


def _archive_identity_key(entity_type: str, row: dict[str, Any]) -> str:
    entity = _normalize_token(entity_type)
    if entity == "normative":
        norm_type = _canonical_text(row.get("norm_type"))
        number = _canonical_text(row.get("norm_number"))
        year = _canonical_text(row.get("norm_year")) or _year_from_any(row.get("publication_date"), row.get("title"))
        issuer = _canonical_authority(row.get("issuer"))
        if norm_type and number and year:
            return f"normative|{norm_type}|{number}|{year}|{issuer}"
    elif entity == "jurisprudence":
        court = _canonical_authority(row.get("court_name"))
        number = _canonical_text(row.get("decision_number"))
        year = _canonical_text(row.get("decision_year")) or _year_from_any(row.get("decision_date"), row.get("title"))
        if number and year:
            return f"jurisprudence|{court}|{number}|{year}"
    elif entity == "prassi":
        body = _canonical_authority(row.get("issuing_body"))
        act_type = _canonical_text(row.get("act_type"))
        number = _canonical_text(row.get("act_number"))
        year = _canonical_text(row.get("act_year")) or _year_from_any(row.get("act_date"), row.get("title"))
        if body and number and year:
            return f"prassi|{body}|{act_type}|{number}|{year}"
    elif entity == "news":
        related = (
            row.get("related_normative_id"),
            row.get("related_jurisprudence_id"),
            row.get("related_prassi_id"),
        )
        for rel_type, rel_id in zip(("normative", "jurisprudence", "prassi"), related):
            if rel_id:
                return f"news|{rel_type}|{rel_id}|{_canonical_text(row.get('news_type'))}"
        url_key = _canonical_url(row.get("source_url"))
        if url_key:
            return f"news|url|{url_key}|{_canonical_text(row.get('news_type'))}"
    url_key = _canonical_url(row.get("source_url"))
    if url_key:
        return f"{entity}|url|{url_key}"
    date_key = _canonical_text(
        row.get("published_at")
        or row.get("publication_date")
        or row.get("decision_date")
        or row.get("act_date")
        or row.get("effective_date")
    )
    return f"{entity}|title|{_canonical_text(row.get('title'))}|{date_key}"


_LEX_SEARCH_STOPWORDS = {
    "aggiorn",
    "aggiornamento",
    "aggiornamenti",
    "ultime",
    "ultima",
    "ultimo",
    "recenti",
    "recente",
    "news",
    "fonte",
    "fonti",
    "legale",
    "legali",
    "norma",
    "norme",
}


def _lex_search_terms(value: Any) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()
    for raw in re.findall(r"[a-zA-Z0-9_]+", _normalize_token(value)):
        if len(raw) < 3 or raw in _LEX_SEARCH_STOPWORDS or raw in seen:
            continue
        seen.add(raw)
        terms.append(raw)
    return terms


def _limit_value(value: Any, *, default: int = 12, maximum: int = 80) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(1, min(parsed, maximum))


def _first_text(*values: Any) -> str:
    for value in values:
        text = _clean_spaces(value)
        if text:
            return text
    return ""


def _lex_excerpt(*values: Any, limit: int = 520) -> str:
    text = _first_text(*values)
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _lex_candidate_score(row: dict[str, Any], terms: list[str]) -> float:
    base = float(row.get("_base_score") or 0.62)
    if not terms:
        return round(base, 4)
    haystack = _normalize_token(
        " ".join(
            str(row.get(field) or "")
            for field in (
                "title",
                "excerpt",
                "content",
                "authority",
                "matter_name",
                "submatter_name",
                "entity_type",
            )
        )
    )
    matches = sum(1 for term in terms if term in haystack)
    if matches <= 0:
        return round(max(0.2, base - 0.18), 4)
    return round(min(0.98, base + (matches * 0.07)), 4)


def _search_clause(fields: tuple[str, ...], terms: list[str], params: list[Any]) -> str:
    if not terms:
        return ""
    clauses: list[str] = []
    for term in terms:
        like_value = f"%{term}%"
        for field in fields:
            clauses.append(f"LOWER(COALESCE({field}, '')) LIKE ?")
            params.append(like_value)
    return " AND (" + " OR ".join(clauses) + ")"


def derive_legal_updates_db_path(intelligence_db_path: str) -> str:
    target = Path(intelligence_db_path).resolve()
    return str(target.with_name("legal_updates.db"))


def derive_legal_updates_json_path(intelligence_db_path: str) -> str:
    target = Path(intelligence_db_path).resolve()
    return str(target.with_name("legal_updates_repository.json"))


@dataclass(frozen=True)
class LegalUpdateDbConfig:
    db_path: str
    json_path: str

    @classmethod
    def from_anchor(cls, intelligence_db_path: str) -> "LegalUpdateDbConfig":
        return cls(
            db_path=derive_legal_updates_db_path(intelligence_db_path),
            json_path=derive_legal_updates_json_path(intelligence_db_path),
        )


class LegalUpdateRepository:
    def __init__(
        self,
        db_path: str,
        *,
        json_path: str = "",
        postgres_dsn: str = "",
        postgres_schema_path: Path | None = None,
    ) -> None:
        self.db_path = str(db_path or "").strip()
        self.json_path = str(json_path or "").strip()
        self.postgres_dsn = str(postgres_dsn or "").strip()
        self.postgres_schema_path = Path(
            postgres_schema_path or POSTGRES_SCHEMA_LEGAL_UPDATE_PIPELINE
        )
        self.backend_kind = "postgresql" if self.postgres_dsn else "sqlite"
        self.audit_table = "legal_update_audit_log" if self.postgres_dsn else "audit_log"
        self._postgres_backend = (
            PostgresRepositoryBackend(self.postgres_dsn, self.postgres_schema_path)
            if self.postgres_dsn
            else None
        )
        self._ensure_schema()
        self.seed_matters()

    def _connect(self):
        if self._postgres_backend is not None:
            return self._postgres_backend.connection()
        target = Path(self.db_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(target))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _ensure_schema(self) -> None:
        schema = (
            self.postgres_schema_path.read_text(encoding="utf-8")
            if self._postgres_backend is not None
            else SCHEMA_LEGAL_UPDATE_PIPELINE.read_text(encoding="utf-8")
        )
        with self._connect() as conn:
            conn.executescript(schema)
            conn.commit()

    def ping(self) -> bool:
        try:
            with self._connect() as conn:
                conn.execute("SELECT 1").fetchone()
            return True
        except Exception:
            return False

    def _set_meta(self, conn: Any, key: str, value: Any) -> None:
        conn.execute(
            """
            INSERT INTO legal_update_meta (meta_key, meta_value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(meta_key) DO UPDATE SET
                meta_value = excluded.meta_value,
                updated_at = CURRENT_TIMESTAMP
            """,
            (_clean_spaces(key), _clean_spaces(value)),
        )

    def _insert_and_get_id(self, conn: Any, sql: str, params: tuple[Any, ...]) -> int:
        statement = str(sql or "").strip().rstrip(";")
        if self._postgres_backend is not None:
            row = conn.execute(f"{statement} RETURNING id", params).fetchone()
            if row is None:
                raise RuntimeError("Inserimento PostgreSQL senza id restituito.")
            if isinstance(row, dict):
                return int(row.get("id") or next(iter(row.values()), 0) or 0)
            return int((row or [0])[0] or 0)
        cursor = conn.execute(statement, params)
        return int(cursor.lastrowid)

    def _decode_row(self, row: sqlite3.Row | None, *, json_fields: Iterable[str] = ()) -> dict[str, Any] | None:
        if row is None:
            return None
        payload = dict(row)
        for field in json_fields:
            payload[field] = _json_load(payload.get(field), [] if field.endswith("_json") and "entities" not in field and "payload" not in field else {})
        return payload

    def _matter_id(self, conn: Any, slug: str) -> int | None:
        if not slug:
            return None
        row = conn.execute("SELECT id FROM matters WHERE slug = ?", (_normalize_token(slug),)).fetchone()
        return int(row["id"]) if row else None

    def seed_matters(self) -> None:
        with self._connect() as conn:
            for row in DEFAULT_MATTERS:
                parent_id = self._matter_id(conn, str(row.get("parent_slug") or ""))
                conn.execute(
                    """
                    INSERT INTO matters (name, slug, parent_id, level, sort_order, enabled)
                    VALUES (?, ?, ?, ?, ?, 1)
                    ON CONFLICT(slug) DO UPDATE SET
                        name = excluded.name,
                        parent_id = excluded.parent_id,
                        level = excluded.level,
                        sort_order = excluded.sort_order,
                        enabled = 1
                    """,
                    (
                        row["name"],
                        _normalize_token(row["slug"]),
                        parent_id,
                        int(row["level"]),
                        int(row["sort_order"]),
                    ),
                )
            conn.commit()

    def list_matters(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT m.id, m.name, m.slug, m.parent_id, m.level, m.sort_order, m.enabled,
                       p.slug AS parent_slug
                FROM matters m
                LEFT JOIN matters p ON p.id = m.parent_id
                WHERE m.enabled = 1
                ORDER BY m.sort_order, m.name
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def upsert_sources(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        with self._connect() as conn:
            for row in rows:
                conn.execute(
                    """
                    INSERT INTO sources (
                        name, code, category, base_url, source_type, trust_class,
                        is_official, enabled, polling_minutes, parser_type, notes,
                        last_check_at, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ON CONFLICT(code) DO UPDATE SET
                        name = excluded.name,
                        category = excluded.category,
                        base_url = excluded.base_url,
                        source_type = excluded.source_type,
                        trust_class = excluded.trust_class,
                        is_official = excluded.is_official,
                        enabled = excluded.enabled,
                        polling_minutes = excluded.polling_minutes,
                        parser_type = excluded.parser_type,
                        notes = excluded.notes,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (
                        _clean_spaces(row.get("name")),
                        _normalize_token(row.get("code")),
                        _normalize_token(row.get("category")),
                        _clean_spaces(row.get("base_url")),
                        _normalize_token(row.get("source_type") or "web"),
                        _normalize_token(row.get("trust_class") or "a").upper(),
                        1 if row.get("is_official", True) else 0,
                        1 if row.get("enabled", True) else 0,
                        int(row.get("polling_minutes") or 240),
                        _normalize_token(row.get("parser_type") or "html"),
                        _clean_spaces(row.get("notes")),
                        _clean_spaces(row.get("last_check_at")),
                    ),
                )
            conn.commit()
        return self.list_sources(enabled_only=False)

    def list_sources(self, *, enabled_only: bool = True) -> list[dict[str, Any]]:
        query = "SELECT * FROM sources"
        params: tuple[Any, ...] = ()
        if enabled_only:
            query += " WHERE enabled = 1"
        query += " ORDER BY is_official DESC, category, name"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            payload = dict(row)
            payload["is_official"] = bool(payload.get("is_official"))
            payload["enabled"] = bool(payload.get("enabled"))
            result.append(payload)
        return result

    def source_activity_summary(self) -> dict[str, dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    s.code AS source_code,
                    COUNT(DISTINCT r.id) AS raw_documents,
                    COUNT(DISTINCT n.id) AS normalized_documents,
                    COUNT(DISTINCT a.id) AS analyses,
                    COUNT(DISTINCT CASE WHEN q.status = 'pending' THEN q.id END) AS review_pending,
                    COUNT(DISTINCT CASE WHEN q.status = 'approved' THEN q.id END) AS review_approved,
                    COUNT(DISTINCT CASE WHEN q.status = 'published' THEN q.id END) AS review_published,
                    COUNT(DISTINCT CASE WHEN q.status = 'closed' THEN q.id END) AS review_closed,
                    MAX(r.updated_at) AS last_document_at,
                    MAX(CASE WHEN COALESCE(r.published_at, '') <> '' THEN r.published_at ELSE r.created_at END) AS latest_source_date
                FROM sources s
                LEFT JOIN source_documents_raw r ON r.source_id = s.id
                LEFT JOIN source_documents_normalized n ON n.raw_document_id = r.id
                LEFT JOIN ai_documents_analysis a ON a.normalized_document_id = n.id
                LEFT JOIN review_queue q ON q.analysis_id = a.id
                GROUP BY s.code
                """
            ).fetchall()
        summary: dict[str, dict[str, Any]] = {}
        for row in rows:
            payload = dict(row)
            code = _normalize_token(payload.pop("source_code", ""))
            if not code:
                continue
            summary[code] = {
                "raw_documents": int(payload.get("raw_documents") or 0),
                "normalized_documents": int(payload.get("normalized_documents") or 0),
                "analyses": int(payload.get("analyses") or 0),
                "review_pending": int(payload.get("review_pending") or 0),
                "review_approved": int(payload.get("review_approved") or 0),
                "review_published": int(payload.get("review_published") or 0),
                "review_closed": int(payload.get("review_closed") or 0),
                "last_document_at": _clean_spaces(payload.get("last_document_at")),
                "latest_source_date": _clean_spaces(payload.get("latest_source_date")),
            }
        return summary

    def record_source_agent_run(
        self,
        *,
        source_code: str,
        source_name: str = "",
        trigger_label: str = "batch",
        status: str = "completed",
        timeout_seconds: int = 0,
        started_at: str = "",
        finished_at: str = "",
        duration_ms: int = 0,
        documents_found: int = 0,
        processed: int = 0,
        skipped_unchanged: int = 0,
        autopublished_count: int = 0,
        error_message: str = "",
        stderr_tail: str = "",
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        code = _normalize_token(source_code)
        if not code:
            raise ValueError("Codice fonte obbligatorio.")
        payload_data = payload if isinstance(payload, dict) else {}
        payload_errors = _source_agent_payload_errors(payload_data)
        finished = _clean_spaces(finished_at) or _now_iso()
        started = _clean_spaces(started_at) or finished
        clean_status = _normalize_token(status or "completed")
        if clean_status == "completed" and payload_errors:
            clean_status = "failed"
        if clean_status not in {"completed", "failed", "timeout", "running"}:
            clean_status = "failed"
        clean_error_message = _source_agent_error_message(code, payload_errors, error_message)
        with self._connect() as conn:
            run_id = self._insert_and_get_id(
                conn,
                """
                INSERT INTO source_agent_runs (
                    source_code, source_name, trigger_label, status, timeout_seconds,
                    started_at, finished_at, duration_ms, documents_found, processed,
                    skipped_unchanged, autopublished_count, error_message, stderr_tail,
                    payload_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                (
                    code,
                    _clean_spaces(source_name),
                    _clean_spaces(trigger_label or "batch"),
                    clean_status,
                    max(0, int(timeout_seconds or 0)),
                    started,
                    finished,
                    max(0, int(duration_ms or 0)),
                    max(0, int(documents_found or 0)),
                    max(0, int(processed or 0)),
                    max(0, int(skipped_unchanged or 0)),
                    max(0, int(autopublished_count or 0)),
                    clean_error_message[:4000],
                    str(stderr_tail or "")[-4000:],
                    _json_dump(payload_data),
                ),
            )
            conn.commit()
        return self.get_source_agent_run(run_id) or {}

    def _decode_source_agent_run(self, row: sqlite3.Row | None) -> dict[str, Any] | None:
        payload = self._decode_row(row, json_fields=("payload_json",)) if row else None
        if not payload:
            return None
        payload_data = payload.get("payload_json")
        payload_errors = _source_agent_payload_errors(payload_data if isinstance(payload_data, dict) else {})
        if payload_errors:
            status = _normalize_token(payload.get("status"))
            if status == "completed":
                payload["status"] = "failed"
            payload["error_message"] = _source_agent_error_message(
                str(payload.get("source_code") or ""),
                payload_errors,
                payload.get("error_message"),
            )[:4000]
        return payload

    def get_source_agent_run(self, run_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM source_agent_runs WHERE id = ?",
                (int(run_id),),
            ).fetchone()
        return self._decode_source_agent_run(row)

    def latest_source_agent_runs(self) -> dict[str, dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT r.*
                FROM source_agent_runs r
                JOIN (
                    SELECT source_code, MAX(id) AS max_id
                    FROM source_agent_runs
                    GROUP BY source_code
                ) latest ON latest.max_id = r.id
                """
            ).fetchall()
        latest: dict[str, dict[str, Any]] = {}
        for row in rows:
            payload = self._decode_source_agent_run(row) or {}
            code = _normalize_token(payload.get("source_code"))
            if code:
                latest[code] = payload
        return latest

    def record_web_verification_evidence(
        self,
        *,
        review_id: int,
        normalized_document_id: int,
        source: dict[str, Any],
        verification: dict[str, Any],
        verification_status: str = "verified",
    ) -> dict[str, int]:
        """Salva nel database le evidenze web ufficiali usate per completare un riferimento."""

        verification_payload = verification if isinstance(verification, dict) else {}
        confirmations = [
            row
            for row in list(verification_payload.get("confirmations") or [])
            if isinstance(row, dict)
        ]
        if not confirmations and verification_payload:
            searched = verification_payload.get("searched") if isinstance(verification_payload.get("searched"), dict) else {}
            attempted_queries = list(searched.get("queries") or [])
            if not attempted_queries and searched.get("query"):
                attempted_queries = [searched.get("query")]
            attempted_domains = []
            for item in list(searched.get("web_searches") or []):
                if not isinstance(item, dict):
                    continue
                attempted_domains.extend(str(value or "") for value in item.get("source_ids") or [])
            confirmations = [
                {
                    "origin": "ricerca_web_senza_conferma",
                    "title": "Verifica web senza conferme sufficienti",
                    "source_name": _clean_spaces(source.get("name") or source.get("source_name")),
                    "source_url": "",
                    "query": "; ".join(_clean_spaces(item) for item in attempted_queries if _clean_spaces(item))[:520],
                    "excerpt": _clean_spaces(verification_payload.get("reason") or "Nessuna fonte pubblica coerente trovata."),
                    "content": _json_dump(
                        {
                            "reason": verification_payload.get("reason"),
                            "warnings": verification_payload.get("warnings") or [],
                            "searched": searched,
                            "attempted_sources": attempted_domains,
                        }
                    ),
                    "official": False,
                    "context_chars": 0,
                    "matched_terms": [],
                }
            ]
        if not confirmations:
            return {"saved": 0, "attachments": 0}
        source_code = _normalize_token(source.get("code") or source.get("source_code"))
        source_name = _clean_spaces(source.get("name") or source.get("source_name"))
        status = _normalize_token(verification_status or (verification or {}).get("status") or "verified")
        saved = 0
        attachment_rows: list[dict[str, Any]] = []
        with self._connect() as conn:
            for row in confirmations:
                source_url = _first_text(row.get("source_url"), row.get("url"), row.get("official_url"), row.get("url_origine"))
                attachment_url = _clean_spaces(row.get("attachment_url"))
                title = _first_text(row.get("title"), row.get("source_name"), row.get("domain"), "Evidenza fonte ufficiale")
                content_text = _lex_excerpt(
                    row.get("content"),
                    row.get("full_context"),
                    row.get("text_excerpt"),
                    row.get("excerpt"),
                    limit=12000,
                )
                excerpt = _lex_excerpt(row.get("excerpt"), row.get("text_excerpt"), content_text, limit=900)
                if not (source_url or attachment_url or excerpt or content_text):
                    continue
                matched_terms = row.get("matched_terms") if isinstance(row.get("matched_terms"), list) else []
                evidence_key = _sha1(
                    "|".join(
                        (
                            str(review_id or ""),
                            str(normalized_document_id or ""),
                            _normalize_token(row.get("origin")),
                            source_url,
                            attachment_url,
                            _clean_spaces(row.get("sha256")),
                            title,
                            excerpt[:220],
                        )
                    )
                )
                conn.execute(
                    """
                    INSERT INTO web_verification_evidence (
                        evidence_key, review_id, normalized_document_id, source_code, source_name,
                        query, origin, title, source_url, attachment_url, attachment_type, sha256,
                        is_official, context_chars, excerpt, content_text, matched_terms_json,
                        verification_status, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ON CONFLICT(evidence_key) DO UPDATE SET
                        source_code = excluded.source_code,
                        source_name = excluded.source_name,
                        query = excluded.query,
                        origin = excluded.origin,
                        title = excluded.title,
                        source_url = excluded.source_url,
                        attachment_url = excluded.attachment_url,
                        attachment_type = excluded.attachment_type,
                        sha256 = excluded.sha256,
                        is_official = excluded.is_official,
                        context_chars = excluded.context_chars,
                        excerpt = excluded.excerpt,
                        content_text = excluded.content_text,
                        matched_terms_json = excluded.matched_terms_json,
                        verification_status = excluded.verification_status,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (
                        evidence_key,
                        int(review_id or 0) or None,
                        int(normalized_document_id or 0) or None,
                        source_code,
                        source_name or _clean_spaces(row.get("source_name")),
                        _clean_spaces(row.get("query") or (verification or {}).get("query")),
                        _normalize_token(row.get("origin")),
                        title,
                        source_url,
                        attachment_url,
                        _clean_spaces(row.get("attachment_type")),
                        _clean_spaces(row.get("sha256")),
                        1 if bool(row.get("official")) else 0,
                        max(0, int(row.get("context_chars") or 0)),
                        excerpt,
                        content_text,
                        _json_dump(matched_terms),
                        status,
                    ),
                )
                saved += 1
                if attachment_url:
                    attachment_rows.append(
                        {
                            "title": title,
                            "url": attachment_url,
                            "source_url": source_url,
                            "attachment_type": _clean_spaces(row.get("attachment_type")),
                            "sha256": _clean_spaces(row.get("sha256")),
                            "verified": True,
                            "text_excerpt": excerpt,
                            "context_chars": max(0, int(row.get("context_chars") or 0)),
                        }
                    )
            if attachment_rows and int(normalized_document_id or 0):
                current = conn.execute(
                    "SELECT attachments_json FROM source_documents_normalized WHERE id = ?",
                    (int(normalized_document_id),),
                ).fetchone()
                if current:
                    attachments = _json_load(current["attachments_json"], [])
                    if not isinstance(attachments, list):
                        attachments = []
                    by_url = {
                        _clean_spaces(item.get("url") or item.get("attachment_url")): dict(item)
                        for item in attachments
                        if isinstance(item, dict)
                    }
                    changed = False
                    for item in attachment_rows:
                        key = _clean_spaces(item.get("url"))
                        if key and key not in by_url:
                            by_url[key] = item
                            changed = True
                    if changed:
                        conn.execute(
                            """
                            UPDATE source_documents_normalized
                            SET attachments_json = ?, updated_at = CURRENT_TIMESTAMP
                            WHERE id = ?
                            """,
                            (_json_dump(list(by_url.values())), int(normalized_document_id)),
                        )
            conn.commit()
        if saved:
            self.record_audit(
                "web_verification_evidence",
                int(review_id or 0) or None,
                "record",
                {},
                {
                    "saved": saved,
                    "attachments": len(attachment_rows),
                    "source_code": source_code,
                    "verification_status": status,
                },
                "system",
            )
        return {"saved": saved, "attachments": len(attachment_rows)}

    def get_source_by_code(self, code: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM sources WHERE code = ?", (_normalize_token(code),)).fetchone()
        if not row:
            return None
        payload = dict(row)
        payload["is_official"] = bool(payload.get("is_official"))
        payload["enabled"] = bool(payload.get("enabled"))
        return payload

    def get_source_by_id(self, source_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM sources WHERE id = ?", (int(source_id),)).fetchone()
        if not row:
            return None
        payload = dict(row)
        payload["is_official"] = bool(payload.get("is_official"))
        payload["enabled"] = bool(payload.get("enabled"))
        return payload

    def mark_source_checked(self, source_id: int) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE sources SET last_check_at = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (_now_iso(), int(source_id)),
            )
            conn.commit()

    def _published_rows(self, conn: Any, entity_type: str) -> list[dict[str, Any]]:
        table = _normalize_token(entity_type)
        if table not in {"normative", "jurisprudence", "prassi", "news"}:
            return []
        rows = conn.execute(f"SELECT * FROM {table} ORDER BY id ASC").fetchall()
        return [dict(row) for row in rows]

    def _duplicate_groups_for_rows(self, entity_type: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        buckets: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            key = _archive_identity_key(entity_type, row)
            if not key or key.endswith("||"):
                continue
            buckets.setdefault(key, []).append(row)
        return [
            {"entity_type": entity_type, "identity_key": key, "rows": group}
            for key, group in buckets.items()
            if len(group) > 1
        ]

    def archive_duplicate_summary(self) -> dict[str, Any]:
        with self._connect() as conn:
            groups: list[dict[str, Any]] = []
            for entity_type in ("normative", "jurisprudence", "prassi", "news"):
                groups.extend(
                    self._duplicate_groups_for_rows(
                        entity_type,
                        self._published_rows(conn, entity_type),
                    )
                )
        by_type: dict[str, int] = {"normative": 0, "jurisprudence": 0, "prassi": 0, "news": 0}
        duplicate_items = 0
        for group in groups:
            count = max(0, len(group["rows"]) - 1)
            by_type[str(group["entity_type"])] = by_type.get(str(group["entity_type"]), 0) + count
            duplicate_items += count
        return {
            "groups": len(groups),
            "duplicate_items": duplicate_items,
            "by_type": by_type,
        }

    def _best_archive_keeper(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        def score(row: dict[str, Any]) -> tuple[int, int, int]:
            richness = sum(
                1
                for field in (
                    "source_url",
                    "summary",
                    "short_summary",
                    "content",
                    "text_current",
                    "full_text",
                    "source_document_id",
                )
                if _clean_spaces(row.get(field))
            )
            published = 1 if _normalize_token(row.get("publication_status") or "published") == "published" else 0
            return (published, richness, -int(row.get("id") or 0))

        return sorted(rows, key=score, reverse=True)[0]

    def deduplicate_archive(self, *, performed_by: str = "system") -> dict[str, Any]:
        report: dict[str, Any] = {
            "ok": True,
            "removed": 0,
            "groups": 0,
            "by_type": {"normative": 0, "jurisprudence": 0, "prassi": 0, "news": 0},
            "items": [],
        }
        with self._connect() as conn:
            for entity_type in ("normative", "jurisprudence", "prassi", "news"):
                groups = self._duplicate_groups_for_rows(entity_type, self._published_rows(conn, entity_type))
                for group in groups:
                    keeper = self._best_archive_keeper(group["rows"])
                    keeper_id = int(keeper["id"])
                    duplicate_ids = [
                        int(row["id"])
                        for row in group["rows"]
                        if int(row["id"]) != keeper_id
                    ]
                    if not duplicate_ids:
                        continue
                    report["groups"] += 1
                    report["removed"] += len(duplicate_ids)
                    report["by_type"][entity_type] += len(duplicate_ids)
                    report["items"].append(
                        {
                            "entity_type": entity_type,
                            "kept_id": keeper_id,
                            "removed_ids": duplicate_ids,
                            "title": keeper.get("title", ""),
                        }
                    )
                    for duplicate_id in duplicate_ids:
                        if entity_type == "normative":
                            conn.execute("UPDATE news SET related_normative_id = ? WHERE related_normative_id = ?", (keeper_id, duplicate_id))
                            conn.execute("UPDATE jurisprudence SET related_normative_id = ? WHERE related_normative_id = ?", (keeper_id, duplicate_id))
                            conn.execute("UPDATE normative_versions SET normative_id = ? WHERE normative_id = ?", (keeper_id, duplicate_id))
                            conn.execute("UPDATE normative_relations SET normative_id = ? WHERE normative_id = ?", (keeper_id, duplicate_id))
                            conn.execute("UPDATE normative_relations SET related_normative_id = ? WHERE related_normative_id = ?", (keeper_id, duplicate_id))
                            conn.execute("DELETE FROM normative WHERE id = ?", (duplicate_id,))
                        elif entity_type == "jurisprudence":
                            conn.execute("UPDATE news SET related_jurisprudence_id = ? WHERE related_jurisprudence_id = ?", (keeper_id, duplicate_id))
                            conn.execute("DELETE FROM jurisprudence WHERE id = ?", (duplicate_id,))
                        elif entity_type == "prassi":
                            conn.execute("UPDATE news SET related_prassi_id = ? WHERE related_prassi_id = ?", (keeper_id, duplicate_id))
                            conn.execute("DELETE FROM prassi WHERE id = ?", (duplicate_id,))
                        elif entity_type == "news":
                            conn.execute("DELETE FROM news WHERE id = ?", (duplicate_id,))
            conn.commit()
        if report["removed"]:
            self.record_audit("legal_update_archive", None, "deduplicate", {}, report, performed_by)
        return report

    def find_published_duplicate(
        self,
        *,
        source: dict[str, Any],
        normalized: dict[str, Any],
        analysis: dict[str, Any],
    ) -> dict[str, Any] | None:
        classification = _normalize_token(analysis.get("classification_type")).upper()
        candidate_types: tuple[str, ...]
        if classification.startswith("NORMATIVA"):
            candidate_types = ("normative",)
        elif classification == "GIURISPRUDENZA":
            candidate_types = ("jurisprudence",)
        elif classification == "PRASSI":
            candidate_types = ("prassi",)
        else:
            candidate_types = ("news",)

        incoming_common = {
            "title": normalized.get("title"),
            "source_url": normalized.get("source_url"),
            "published_at": normalized.get("published_at") or normalized.get("document_date"),
            "publication_date": normalized.get("document_date") or normalized.get("published_at"),
            "effective_date": analysis.get("effective_date") or normalized.get("document_date"),
            "issuer": analysis.get("issuer") or normalized.get("issuer") or source.get("name"),
            "norm_type": analysis.get("norm_type"),
            "norm_number": analysis.get("norm_number"),
            "norm_year": analysis.get("norm_year"),
            "court_name": analysis.get("court_name"),
            "decision_number": analysis.get("decision_number"),
            "decision_year": analysis.get("decision_year"),
            "decision_date": normalized.get("document_date") or normalized.get("published_at"),
            "issuing_body": analysis.get("issuer") or source.get("name"),
            "act_type": analysis.get("norm_type"),
            "act_number": analysis.get("norm_number"),
            "act_year": analysis.get("norm_year"),
            "act_date": normalized.get("document_date") or normalized.get("published_at"),
            "news_type": _normalize_token(classification or "focus"),
        }
        incoming_keys = {
            _archive_identity_key(candidate_type, incoming_common)
            for candidate_type in candidate_types
        }
        incoming_keys = {key for key in incoming_keys if key}
        if not incoming_keys:
            return None

        with self._connect() as conn:
            for entity_type in candidate_types:
                for row in self._published_rows(conn, entity_type):
                    if _archive_identity_key(entity_type, row) in incoming_keys:
                        return {
                            "entity_type": entity_type,
                            "entity": row,
                            "reason": "already_published",
                        }
        return None

    def save_raw_document(self, payload: dict[str, Any]) -> dict[str, Any]:
        external_id = _clean_spaces(payload.get("external_id")) or _sha1(
            f"{payload.get('source_id')}|{payload.get('source_url')}|{payload.get('title')}"
        )
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT * FROM source_documents_raw WHERE source_id = ? AND external_id = ?",
                (int(payload["source_id"]), external_id),
            ).fetchone()
            if existing:
                conn.execute(
                    """
                    UPDATE source_documents_raw
                    SET source_url = ?, title = ?, published_at = ?, raw_html = ?, raw_text = ?,
                        raw_pdf_path = ?, content_hash = ?, fetch_status = ?, http_status = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (
                        _clean_spaces(payload.get("source_url")),
                        _clean_spaces(payload.get("title")),
                        _clean_spaces(payload.get("published_at")),
                        str(payload.get("raw_html") or ""),
                        str(payload.get("raw_text") or ""),
                        _clean_spaces(payload.get("raw_pdf_path")),
                        _clean_spaces(payload.get("content_hash")),
                        _normalize_token(payload.get("fetch_status") or "fetched"),
                        int(payload.get("http_status") or 0),
                        int(existing["id"]),
                    ),
                )
                raw_id = int(existing["id"])
            else:
                raw_id = self._insert_and_get_id(
                    conn,
                    """
                    INSERT INTO source_documents_raw (
                        source_id, external_id, source_url, title, published_at, raw_html, raw_text,
                        raw_pdf_path, content_hash, fetch_status, http_status, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """,
                    (
                        int(payload["source_id"]),
                        external_id,
                        _clean_spaces(payload.get("source_url")),
                        _clean_spaces(payload.get("title")),
                        _clean_spaces(payload.get("published_at")),
                        str(payload.get("raw_html") or ""),
                        str(payload.get("raw_text") or ""),
                        _clean_spaces(payload.get("raw_pdf_path")),
                        _clean_spaces(payload.get("content_hash")),
                        _normalize_token(payload.get("fetch_status") or "fetched"),
                        int(payload.get("http_status") or 0),
                    ),
                )
            conn.execute(
                "UPDATE sources SET last_check_at = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (_now_iso(), int(payload["source_id"])),
            )
            conn.commit()
        return self.get_raw_document(raw_id) or {}

    def get_raw_document(self, raw_document_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT r.*, s.code AS source_code, s.name AS source_name, s.category AS source_category
                FROM source_documents_raw r
                JOIN sources s ON s.id = r.source_id
                WHERE r.id = ?
                """,
                (int(raw_document_id),),
            ).fetchone()
        return dict(row) if row else None

    def get_raw_document_by_external(self, source_id: int, external_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM source_documents_raw WHERE source_id = ? AND external_id = ?",
                (int(source_id), _clean_spaces(external_id)),
            ).fetchone()
        return dict(row) if row else None

    def list_raw_documents(
        self,
        *,
        source_code: str = "",
        classification_type: str = "",
        status: str = "",
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        clauses = []
        params: list[Any] = []
        if source_code:
            clauses.append("s.code = ?")
            params.append(_normalize_token(source_code))
        if classification_type:
            clauses.append("a.classification_type = ?")
            params.append(_normalize_token(classification_type).upper())
        if status:
            clauses.append("q.status = ?")
            params.append(_normalize_token(status))
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(int(limit))
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT r.id, r.source_id, r.external_id, r.source_url, r.title, r.published_at,
                       r.fetch_status, r.http_status, r.content_hash, r.created_at, r.updated_at,
                       s.code AS source_code, s.name AS source_name, s.category AS source_category,
                       n.id AS normalized_document_id, n.body_short, n.document_date,
                       a.id AS analysis_id, a.classification_type, a.confidence_score, a.proposed_action,
                       q.id AS review_id, q.status AS review_status, q.priority AS review_priority
                FROM source_documents_raw r
                JOIN sources s ON s.id = r.source_id
                LEFT JOIN source_documents_normalized n ON n.raw_document_id = r.id
                LEFT JOIN ai_documents_analysis a ON a.normalized_document_id = n.id
                LEFT JOIN review_queue q ON q.analysis_id = a.id
                {where}
                ORDER BY COALESCE(NULLIF(r.published_at, ''), r.created_at) DESC, r.id DESC
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_staging_document(self, raw_document_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT r.id, r.source_id, r.external_id, r.source_url, r.title, r.published_at,
                       r.raw_html, r.raw_text, r.raw_pdf_path, r.content_hash, r.fetch_status,
                       r.http_status, r.created_at, r.updated_at,
                       s.code AS source_code, s.name AS source_name, s.category AS source_category,
                       s.trust_class, s.is_official,
                       n.id AS normalized_document_id, n.title AS normalized_title, n.body_text, n.body_short,
                       n.language, n.issuer, n.document_date, n.document_type_guess, n.attachments_json,
                       a.id AS analysis_id, a.classification_type, a.confidence_score, a.impact_level,
                       a.norm_type, a.norm_number, a.norm_year, a.decision_number, a.decision_year,
                       a.court_name, a.effective_date, a.summary_short, a.summary_long, a.what_changes,
                       a.extracted_entities_json, a.proposed_action, a.target_entity_type, a.target_entity_id,
                       m.slug AS matter_slug, m.name AS matter_name,
                       sm.slug AS submatter_slug, sm.name AS submatter_name,
                       q.id AS review_id, q.status AS review_status, q.priority AS review_priority,
                       q.review_notes, q.reviewed_by, q.reviewed_at, q.proposal_payload_json
                FROM source_documents_raw r
                JOIN sources s ON s.id = r.source_id
                LEFT JOIN source_documents_normalized n ON n.raw_document_id = r.id
                LEFT JOIN ai_documents_analysis a ON a.normalized_document_id = n.id
                LEFT JOIN matters m ON m.id = a.matter_id
                LEFT JOIN matters sm ON sm.id = a.submatter_id
                LEFT JOIN review_queue q ON q.analysis_id = a.id
                WHERE r.id = ?
                """,
                (int(raw_document_id),),
            ).fetchone()
        return self._decode_row(
            row,
            json_fields=("attachments_json", "extracted_entities_json", "proposal_payload_json"),
        )

    def save_normalized_document(self, raw_document_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT id FROM source_documents_normalized WHERE raw_document_id = ?",
                (int(raw_document_id),),
            ).fetchone()
            params = (
                int(raw_document_id),
                _clean_spaces(payload.get("title")),
                str(payload.get("body_text") or ""),
                _clean_spaces(payload.get("body_short")),
                _normalize_token(payload.get("language") or "it"),
                _clean_spaces(payload.get("issuer")),
                _clean_spaces(payload.get("document_date")),
                _normalize_token(payload.get("document_type_guess")),
                _json_dump(payload.get("attachments_json") or []),
                _clean_spaces(payload.get("normalized_hash")),
            )
            if existing:
                conn.execute(
                    """
                    UPDATE source_documents_normalized
                    SET title = ?, body_text = ?, body_short = ?, language = ?, issuer = ?,
                        document_date = ?, document_type_guess = ?, attachments_json = ?,
                        normalized_hash = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE raw_document_id = ?
                    """,
                    params[1:] + (int(raw_document_id),),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO source_documents_normalized (
                        raw_document_id, title, body_text, body_short, language, issuer,
                        document_date, document_type_guess, attachments_json, normalized_hash,
                        created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """,
                    params,
                )
            conn.commit()
        return self.get_normalized_by_raw(raw_document_id) or {}

    def get_normalized_by_raw(self, raw_document_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT n.*, r.source_id, r.source_url, r.external_id, r.published_at, r.title AS raw_title
                FROM source_documents_normalized n
                JOIN source_documents_raw r ON r.id = n.raw_document_id
                WHERE n.raw_document_id = ?
                """,
                (int(raw_document_id),),
            ).fetchone()
        return self._decode_row(row, json_fields=("attachments_json",))

    def save_analysis(self, normalized_document_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT id FROM ai_documents_analysis WHERE normalized_document_id = ?",
                (int(normalized_document_id),),
            ).fetchone()
            matter_id = self._matter_id(conn, str(payload.get("matter_slug") or ""))
            submatter_id = self._matter_id(conn, str(payload.get("submatter_slug") or ""))
            params = (
                int(normalized_document_id),
                _normalize_token(payload.get("classification_type") or "INCERTO").upper(),
                float(payload.get("confidence_score") or 0),
                _normalize_token(payload.get("impact_level") or "medio"),
                matter_id,
                submatter_id,
                _clean_spaces(payload.get("issuer")),
                _clean_spaces(payload.get("norm_number")),
                _clean_spaces(payload.get("norm_year")),
                _normalize_token(payload.get("norm_type")),
                _clean_spaces(payload.get("decision_number")),
                _clean_spaces(payload.get("decision_year")),
                _clean_spaces(payload.get("court_name")),
                _clean_spaces(payload.get("effective_date")),
                _clean_spaces(payload.get("summary_short")),
                str(payload.get("summary_long") or ""),
                str(payload.get("what_changes") or ""),
                _json_dump(payload.get("extracted_entities_json") or {}),
                _normalize_token(payload.get("proposed_action") or "needs_review").upper(),
                _normalize_token(payload.get("target_entity_type") or ""),
                payload.get("target_entity_id"),
            )
            if existing:
                conn.execute(
                    """
                    UPDATE ai_documents_analysis
                    SET classification_type = ?, confidence_score = ?, impact_level = ?, matter_id = ?,
                        submatter_id = ?, issuer = ?, norm_number = ?, norm_year = ?, norm_type = ?,
                        decision_number = ?, decision_year = ?, court_name = ?, effective_date = ?,
                        summary_short = ?, summary_long = ?, what_changes = ?, extracted_entities_json = ?,
                        proposed_action = ?, target_entity_type = ?, target_entity_id = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE normalized_document_id = ?
                    """,
                    params[1:] + (int(normalized_document_id),),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO ai_documents_analysis (
                        normalized_document_id, classification_type, confidence_score, impact_level,
                        matter_id, submatter_id, issuer, norm_number, norm_year, norm_type,
                        decision_number, decision_year, court_name, effective_date, summary_short,
                        summary_long, what_changes, extracted_entities_json, proposed_action,
                        target_entity_type, target_entity_id, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """,
                    params,
                )
            conn.commit()
        return self.get_analysis_by_normalized(normalized_document_id) or {}

    def get_analysis_by_normalized(self, normalized_document_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT a.*,
                       m.slug AS matter_slug,
                       m.name AS matter_name,
                       sm.slug AS submatter_slug,
                       sm.name AS submatter_name
                FROM ai_documents_analysis a
                LEFT JOIN matters m ON m.id = a.matter_id
                LEFT JOIN matters sm ON sm.id = a.submatter_id
                WHERE a.normalized_document_id = ?
                """,
                (int(normalized_document_id),),
            ).fetchone()
        return self._decode_row(row, json_fields=("extracted_entities_json",))

    def list_analyses(
        self,
        *,
        classification_type: str = "",
        matter_slug: str = "",
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        clauses = []
        params: list[Any] = []
        if classification_type:
            clauses.append("a.classification_type = ?")
            params.append(_normalize_token(classification_type).upper())
        if matter_slug:
            clauses.append("m.slug = ?")
            params.append(_normalize_token(matter_slug))
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(int(limit))
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT a.*,
                       n.title, n.document_date, n.issuer, n.body_short,
                       r.id AS raw_document_id, r.source_url, r.published_at,
                       s.code AS source_code, s.name AS source_name,
                       m.slug AS matter_slug, m.name AS matter_name,
                       sm.slug AS submatter_slug, sm.name AS submatter_name,
                       q.id AS review_id, q.status AS review_status
                FROM ai_documents_analysis a
                JOIN source_documents_normalized n ON n.id = a.normalized_document_id
                JOIN source_documents_raw r ON r.id = n.raw_document_id
                JOIN sources s ON s.id = r.source_id
                LEFT JOIN matters m ON m.id = a.matter_id
                LEFT JOIN matters sm ON sm.id = a.submatter_id
                LEFT JOIN review_queue q ON q.analysis_id = a.id
                {where}
                ORDER BY a.updated_at DESC, a.id DESC
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()
        return [self._decode_row(row, json_fields=("extracted_entities_json",)) or {} for row in rows]

    def get_analysis(self, analysis_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT a.*,
                       n.id AS normalized_document_id, n.title, n.document_date, n.issuer, n.body_text, n.body_short,
                       r.id AS raw_document_id, r.source_url, r.published_at,
                       s.code AS source_code, s.name AS source_name, s.category AS source_category,
                       m.slug AS matter_slug, m.name AS matter_name,
                       sm.slug AS submatter_slug, sm.name AS submatter_name,
                       q.id AS review_id, q.status AS review_status, q.priority AS review_priority
                FROM ai_documents_analysis a
                JOIN source_documents_normalized n ON n.id = a.normalized_document_id
                JOIN source_documents_raw r ON r.id = n.raw_document_id
                JOIN sources s ON s.id = r.source_id
                LEFT JOIN matters m ON m.id = a.matter_id
                LEFT JOIN matters sm ON sm.id = a.submatter_id
                LEFT JOIN review_queue q ON q.analysis_id = a.id
                WHERE a.id = ?
                """,
                (int(analysis_id),),
            ).fetchone()
        return self._decode_row(row, json_fields=("extracted_entities_json",))

    def find_normative_match(self, norm_type: str, norm_number: str, norm_year: str, issuer: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM normative
                WHERE norm_type = ? AND norm_number = ? AND norm_year = ? AND issuer = ?
                """,
                (
                    _normalize_token(norm_type),
                    _clean_spaces(norm_number),
                    _clean_spaces(norm_year),
                    _clean_spaces(issuer),
                ),
            ).fetchone()
        return dict(row) if row else None

    def find_jurisprudence_match(self, court_name: str, decision_number: str, decision_year: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM jurisprudence
                WHERE court_name = ? AND decision_number = ? AND decision_year = ?
                """,
                (
                    _clean_spaces(court_name),
                    _clean_spaces(decision_number),
                    _clean_spaces(decision_year),
                ),
            ).fetchone()
        return dict(row) if row else None

    def find_prassi_match(self, issuing_body: str, act_type: str, act_number: str, act_year: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM prassi
                WHERE issuing_body = ? AND act_type = ? AND act_number = ? AND act_year = ?
                """,
                (
                    _clean_spaces(issuing_body),
                    _normalize_token(act_type),
                    _clean_spaces(act_number),
                    _clean_spaces(act_year),
                ),
            ).fetchone()
        return dict(row) if row else None

    def upsert_review_item(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT id, status FROM review_queue WHERE analysis_id = ?",
                (int(payload["analysis_id"]),),
            ).fetchone()
            params = (
                int(payload["normalized_document_id"]),
                int(payload["analysis_id"]),
                _normalize_token(payload.get("proposal_type") or ""),
                _normalize_token(payload.get("proposed_action") or "").upper(),
                _normalize_token(payload.get("target_entity_type") or ""),
                payload.get("target_entity_id"),
                _json_dump(payload.get("proposal_payload_json") or {}),
                _normalize_token(payload.get("status") or "pending"),
                int(payload.get("priority") or 50),
                _clean_spaces(payload.get("assigned_to")),
                _clean_spaces(payload.get("review_notes")),
                _clean_spaces(payload.get("reviewed_by")),
                _clean_spaces(payload.get("reviewed_at")),
            )
            if existing:
                conn.execute(
                    """
                    UPDATE review_queue
                    SET proposal_type = ?, proposed_action = ?, target_entity_type = ?, target_entity_id = ?,
                        proposal_payload_json = ?, status = ?, priority = ?, assigned_to = ?,
                        review_notes = ?, reviewed_by = ?, reviewed_at = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE analysis_id = ?
                    """,
                    params[2:] + (int(payload["analysis_id"]),),
                )
                review_id = int(existing["id"])
            else:
                review_id = self._insert_and_get_id(
                    conn,
                    """
                    INSERT INTO review_queue (
                        normalized_document_id, analysis_id, proposal_type, proposed_action,
                        target_entity_type, target_entity_id, proposal_payload_json, status,
                        priority, assigned_to, review_notes, reviewed_by, reviewed_at,
                        created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """,
                    params,
                )
            conn.commit()
        return self.get_review_item(review_id) or {}

    def list_review_queue(self, *, statuses: tuple[str, ...] = (), limit: int = 100) -> list[dict[str, Any]]:
        where = ""
        params: list[Any] = []
        if statuses:
            where = "WHERE q.status IN ({})".format(",".join("?" for _ in statuses))
            params.extend(_normalize_token(status) for status in statuses)
        params.append(int(limit))
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT q.*, a.classification_type, a.confidence_score, a.summary_short,
                       a.proposed_action AS analysis_proposed_action,
                       n.title, n.document_date, s.name AS source_name, s.code AS source_code,
                       m.name AS matter_name, sm.name AS submatter_name
                FROM review_queue q
                JOIN ai_documents_analysis a ON a.id = q.analysis_id
                JOIN source_documents_normalized n ON n.id = q.normalized_document_id
                JOIN source_documents_raw r ON r.id = n.raw_document_id
                JOIN sources s ON s.id = r.source_id
                LEFT JOIN matters m ON m.id = a.matter_id
                LEFT JOIN matters sm ON sm.id = a.submatter_id
                {where}
                ORDER BY q.status = 'pending' DESC, q.priority DESC, q.created_at DESC
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()
        return [self._decode_row(row, json_fields=("proposal_payload_json",)) or {} for row in rows]

    def list_reviews_missing_web_evidence(
        self,
        *,
        limit: int = 100,
        source_codes: tuple[str, ...] = (),
        statuses: tuple[str, ...] | None = ("pending", "approved", "published"),
        include_closed: bool = False,
        include_open_data: bool = False,
    ) -> list[dict[str, Any]]:
        clauses = [
            "q.status <> 'rejected'",
            "r.source_url <> ''",
            """
            NOT EXISTS (
                SELECT 1
                FROM web_verification_evidence e
                WHERE e.normalized_document_id = q.normalized_document_id
            )
            """,
        ]
        params: list[Any] = []
        status_values = tuple(_normalize_token(status) for status in (statuses or ()) if _normalize_token(status))
        if status_values:
            clauses.append("q.status IN ({})".format(",".join("?" for _ in status_values)))
            params.extend(status_values)
        elif not include_closed:
            clauses.append("q.status <> 'closed'")
        if source_codes:
            clauses.append("s.code IN ({})".format(",".join("?" for _ in source_codes)))
            params.extend(_normalize_token(code) for code in source_codes)
        if not include_open_data:
            clauses.append("COALESCE(s.source_type, '') <> 'open_data'")
            clauses.append("COALESCE(s.parser_type, '') <> 'ckan_json'")
            clauses.append("s.code NOT LIKE 'openga_%'")
        params.append(int(limit))
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT q.id
                FROM review_queue q
                JOIN ai_documents_analysis a ON a.id = q.analysis_id
                JOIN source_documents_normalized n ON n.id = q.normalized_document_id
                JOIN source_documents_raw r ON r.id = n.raw_document_id
                JOIN sources s ON s.id = r.source_id
                WHERE {' AND '.join(clauses)}
                ORDER BY
                    CASE WHEN q.status IN ('approved', 'pending') THEN 0 ELSE 1 END,
                    q.priority DESC,
                    q.updated_at DESC,
                    q.id DESC
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()
        reviews: list[dict[str, Any]] = []
        for row in rows:
            item = self.get_review_item(int(row["id"]))
            if item:
                reviews.append(item)
        return reviews

    def get_review_item(self, review_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT q.*,
                       a.classification_type, a.confidence_score, a.impact_level, a.summary_short,
                       a.summary_long, a.what_changes, a.proposed_action AS analysis_proposed_action, a.target_entity_type,
                       a.target_entity_id, a.extracted_entities_json, a.issuer AS analysis_issuer,
                       a.norm_type, a.norm_number, a.norm_year, a.decision_number, a.decision_year,
                       a.court_name, a.effective_date,
                       n.title, n.body_short, n.body_text, n.document_date, n.issuer,
                       r.source_url, r.published_at, r.external_id,
                       s.name AS source_name, s.code AS source_code, s.category AS source_category,
                       s.trust_class, s.is_official,
                       m.slug AS matter_slug, m.name AS matter_name,
                       sm.slug AS submatter_slug, sm.name AS submatter_name
                FROM review_queue q
                JOIN ai_documents_analysis a ON a.id = q.analysis_id
                JOIN source_documents_normalized n ON n.id = q.normalized_document_id
                JOIN source_documents_raw r ON r.id = n.raw_document_id
                JOIN sources s ON s.id = r.source_id
                LEFT JOIN matters m ON m.id = a.matter_id
                LEFT JOIN matters sm ON sm.id = a.submatter_id
                WHERE q.id = ?
                """,
                (int(review_id),),
            ).fetchone()
        return self._decode_row(row, json_fields=("proposal_payload_json", "extracted_entities_json"))

    def set_review_status(
        self,
        review_id: int,
        status: str,
        *,
        reviewer: str = "",
        notes: str = "",
        assigned_to: str = "",
        priority: int | None = None,
    ) -> dict[str, Any] | None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE review_queue
                SET status = ?, reviewed_by = ?, reviewed_at = ?, review_notes = ?,
                    priority = CASE WHEN ? IS NOT NULL THEN ? ELSE priority END,
                    assigned_to = CASE WHEN ? <> '' THEN ? ELSE assigned_to END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    _normalize_token(status),
                    _clean_spaces(reviewer),
                    _now_iso(),
                    _clean_spaces(notes),
                    priority,
                    priority,
                    _clean_spaces(assigned_to),
                    _clean_spaces(assigned_to),
                    int(review_id),
                ),
            )
            conn.commit()
        return self.get_review_item(review_id)

    def set_review_proposed_action(
        self,
        review_id: int,
        proposed_action: str,
        *,
        target_entity_type: str = "",
        target_entity_id: int | None = None,
        reviewer: str = "",
        notes: str = "",
    ) -> dict[str, Any] | None:
        action = _normalize_token(proposed_action or "NEWS_ONLY").upper()
        target_type = _normalize_token(target_entity_type or "")
        with self._connect() as conn:
            row = conn.execute(
                "SELECT analysis_id FROM review_queue WHERE id = ?",
                (int(review_id),),
            ).fetchone()
            if not row:
                return None
            analysis_id = int(row["analysis_id"])
            conn.execute(
                """
                UPDATE review_queue
                SET proposed_action = ?, target_entity_type = ?, target_entity_id = ?,
                    reviewed_by = CASE WHEN ? <> '' THEN ? ELSE reviewed_by END,
                    reviewed_at = CASE WHEN ? <> '' THEN ? ELSE reviewed_at END,
                    review_notes = CASE WHEN ? <> '' THEN ? ELSE review_notes END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    action,
                    target_type,
                    target_entity_id,
                    _clean_spaces(reviewer),
                    _clean_spaces(reviewer),
                    _clean_spaces(reviewer),
                    _now_iso(),
                    _clean_spaces(notes),
                    _clean_spaces(notes),
                    int(review_id),
                ),
            )
            conn.execute(
                """
                UPDATE ai_documents_analysis
                SET proposed_action = ?, target_entity_type = ?, target_entity_id = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (action, target_type, target_entity_id, analysis_id),
            )
            conn.commit()
        return self.get_review_item(review_id)

    def assign_review(self, review_id: int, *, assigned_to: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE review_queue
                SET assigned_to = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (_clean_spaces(assigned_to), int(review_id)),
            )
            conn.commit()
        return self.get_review_item(review_id)

    def record_audit(self, entity_type: str, entity_id: int | None, action: str, old_data: Any, new_data: Any, performed_by: str) -> None:
        with self._connect() as conn:
            conn.execute(
                f"""
                INSERT INTO {self.audit_table} (
                    entity_type, entity_id, action, old_data_json, new_data_json, performed_by, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    _normalize_token(entity_type),
                    entity_id,
                    _normalize_token(action),
                    _json_dump(old_data or {}),
                    _json_dump(new_data or {}),
                    _clean_spaces(performed_by),
                ),
            )
            conn.commit()

    def _unique_slug(self, conn: Any, table: str, slug: str, *, existing_id: int | None = None) -> str:
        base = _slugify(slug or "record")
        candidate = base
        suffix = 2
        while True:
            if existing_id:
                row = conn.execute(
                    f"SELECT id FROM {table} WHERE slug = ? AND id <> ? LIMIT 1",
                    (candidate, int(existing_id)),
                ).fetchone()
            else:
                row = conn.execute(
                    f"SELECT id FROM {table} WHERE slug = ? LIMIT 1",
                    (candidate,),
                ).fetchone()
            if not row:
                return candidate
            candidate = f"{base}-{suffix}"
            suffix += 1

    def _find_existing_normative(self, conn: Any, payload: dict[str, Any], slug: str) -> Any:
        norm_type = _normalize_token(payload.get("norm_type"))
        norm_number = _clean_spaces(payload.get("norm_number"))
        norm_year = _clean_spaces(payload.get("norm_year"))
        issuer = _clean_spaces(payload.get("issuer"))
        if norm_type and norm_number and norm_year:
            row = conn.execute(
                """
                SELECT * FROM normative
                WHERE norm_type = ? AND norm_number = ? AND norm_year = ? AND issuer = ?
                LIMIT 1
                """,
                (norm_type, norm_number, norm_year, issuer),
            ).fetchone()
            if row:
                return row
        source_document_id = payload.get("source_document_id")
        if source_document_id:
            row = conn.execute(
                "SELECT * FROM normative WHERE source_document_id = ? LIMIT 1",
                (source_document_id,),
            ).fetchone()
            if row:
                return row
        source_url = _clean_spaces(payload.get("source_url"))
        if source_url:
            row = conn.execute(
                "SELECT * FROM normative WHERE source_url = ? LIMIT 1",
                (source_url,),
            ).fetchone()
            if row:
                return row
        if slug:
            row = conn.execute(
                "SELECT * FROM normative WHERE slug = ? LIMIT 1",
                (slug,),
            ).fetchone()
            if row:
                return row
        return None

    def create_or_update_normative(self, payload: dict[str, Any], *, performed_by: str) -> dict[str, Any]:
        with self._connect() as conn:
            matter_id = self._matter_id(conn, str(payload.get("matter_slug") or ""))
            submatter_id = self._matter_id(conn, str(payload.get("submatter_slug") or ""))
            requested_slug = _slugify(str(payload.get("slug") or payload.get("title")))
            existing = self._find_existing_normative(conn, payload, requested_slug)
            version_group_id = _slugify(
                f"{payload.get('norm_type')}-{payload.get('norm_number')}-{payload.get('norm_year')}-{payload.get('issuer')}"
            )
            source_document_id = payload.get("source_document_id")
            slug = self._unique_slug(
                conn,
                "normative",
                requested_slug,
                existing_id=int(existing["id"]) if existing else None,
            )
            if existing:
                old_payload = dict(existing)
                conn.execute(
                    """
                    UPDATE normative
                    SET title = ?, slug = ?, publication_date = ?, effective_date = ?, status = ?,
                        matter_id = ?, submatter_id = ?, source_url = ?, source_document_id = ?,
                        text_official = ?, text_current = ?, summary = ?, notes = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (
                        _clean_spaces(payload.get("title")),
                        slug,
                        _clean_spaces(payload.get("publication_date")),
                        _clean_spaces(payload.get("effective_date")),
                        _normalize_token(payload.get("status") or "vigente"),
                        matter_id,
                        submatter_id,
                        _clean_spaces(payload.get("source_url")),
                        source_document_id,
                        str(payload.get("text_official") or ""),
                        str(payload.get("text_current") or payload.get("text_official") or ""),
                        str(payload.get("summary") or ""),
                        str(payload.get("notes") or ""),
                        int(existing["id"]),
                    ),
                )
                normative_id = int(existing["id"])
                action = "update"
            else:
                normative_id = self._insert_and_get_id(
                    conn,
                    """
                    INSERT INTO normative (
                        title, slug, norm_type, norm_number, norm_year, issuer, publication_date,
                        effective_date, status, matter_id, submatter_id, source_url, source_document_id,
                        text_official, text_current, summary, notes, version_group_id, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """,
                    (
                        _clean_spaces(payload.get("title")),
                        slug,
                        _normalize_token(payload.get("norm_type")),
                        _clean_spaces(payload.get("norm_number")),
                        _clean_spaces(payload.get("norm_year")),
                        _clean_spaces(payload.get("issuer")),
                        _clean_spaces(payload.get("publication_date")),
                        _clean_spaces(payload.get("effective_date")),
                        _normalize_token(payload.get("status") or "vigente"),
                        matter_id,
                        submatter_id,
                        _clean_spaces(payload.get("source_url")),
                        source_document_id,
                        str(payload.get("text_official") or ""),
                        str(payload.get("text_current") or payload.get("text_official") or ""),
                        str(payload.get("summary") or ""),
                        str(payload.get("notes") or ""),
                        version_group_id,
                    ),
                )
                old_payload = {}
                action = "create"
            existing_version = conn.execute(
                "SELECT id FROM normative_versions WHERE normative_id = ? AND valid_from = ? AND source_url = ? LIMIT 1",
                (
                    normative_id,
                    _clean_spaces(payload.get("effective_date") or payload.get("publication_date")),
                    _clean_spaces(payload.get("source_url")),
                ),
            ).fetchone()
            if not existing_version:
                conn.execute(
                    """
                    INSERT INTO normative_versions (
                        normative_id, version_label, valid_from, valid_to, text_version, source_url, source_document_id, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    (
                        normative_id,
                        _clean_spaces(payload.get("version_label") or payload.get("publication_date") or "versione iniziale"),
                        _clean_spaces(payload.get("effective_date") or payload.get("publication_date")),
                        _clean_spaces(payload.get("valid_to")),
                        str(payload.get("text_current") or payload.get("text_official") or ""),
                        _clean_spaces(payload.get("source_url")),
                        source_document_id,
                    ),
                )
            conn.commit()
        created = self.get_normative(normative_id) or {}
        self.record_audit("normative", normative_id, action, old_payload, created, performed_by)
        return created

    def get_normative(self, normative_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM normative WHERE id = ?", (int(normative_id),)).fetchone()
        return dict(row) if row else None

    def create_or_update_jurisprudence(self, payload: dict[str, Any], *, performed_by: str) -> dict[str, Any]:
        with self._connect() as conn:
            matter_id = self._matter_id(conn, str(payload.get("matter_slug") or ""))
            submatter_id = self._matter_id(conn, str(payload.get("submatter_slug") or ""))
            existing = conn.execute(
                """
                SELECT * FROM jurisprudence
                WHERE court_name = ? AND decision_number = ? AND decision_year = ?
                """,
                (
                    _clean_spaces(payload.get("court_name")),
                    _clean_spaces(payload.get("decision_number")),
                    _clean_spaces(payload.get("decision_year")),
                ),
            ).fetchone()
            params = (
                _clean_spaces(payload.get("title")),
                _slugify(str(payload.get("slug") or payload.get("title"))),
                _clean_spaces(payload.get("court_name")),
                _clean_spaces(payload.get("section_name")),
                _clean_spaces(payload.get("decision_number")),
                _clean_spaces(payload.get("decision_year")),
                _clean_spaces(payload.get("decision_date")),
                _clean_spaces(payload.get("publication_date")),
                matter_id,
                submatter_id,
                str(payload.get("principle_of_law") or ""),
                str(payload.get("summary") or ""),
                str(payload.get("full_text") or ""),
                _clean_spaces(payload.get("source_url")),
                payload.get("source_document_id"),
                payload.get("related_normative_id"),
            )
            if existing:
                old_payload = dict(existing)
                conn.execute(
                    """
                    UPDATE jurisprudence
                    SET title = ?, slug = ?, court_name = ?, section_name = ?, decision_number = ?,
                        decision_year = ?, decision_date = ?, publication_date = ?, matter_id = ?,
                        submatter_id = ?, principle_of_law = ?, summary = ?, full_text = ?, source_url = ?,
                        source_document_id = ?, related_normative_id = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    params + (int(existing["id"]),),
                )
                entity_id = int(existing["id"])
                action = "update"
            else:
                entity_id = self._insert_and_get_id(
                    conn,
                    """
                    INSERT INTO jurisprudence (
                        title, slug, court_name, section_name, decision_number, decision_year,
                        decision_date, publication_date, matter_id, submatter_id, principle_of_law,
                        summary, full_text, source_url, source_document_id, related_normative_id,
                        created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """,
                    params,
                )
                old_payload = {}
                action = "create"
            conn.commit()
        created = self.get_jurisprudence(entity_id) or {}
        self.record_audit("jurisprudence", entity_id, action, old_payload, created, performed_by)
        return created

    def get_jurisprudence(self, entity_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM jurisprudence WHERE id = ?", (int(entity_id),)).fetchone()
        return dict(row) if row else None

    def create_or_update_prassi(self, payload: dict[str, Any], *, performed_by: str) -> dict[str, Any]:
        with self._connect() as conn:
            matter_id = self._matter_id(conn, str(payload.get("matter_slug") or ""))
            submatter_id = self._matter_id(conn, str(payload.get("submatter_slug") or ""))
            existing = conn.execute(
                """
                SELECT * FROM prassi
                WHERE issuing_body = ? AND act_type = ? AND act_number = ? AND act_year = ?
                """,
                (
                    _clean_spaces(payload.get("issuing_body")),
                    _normalize_token(payload.get("act_type")),
                    _clean_spaces(payload.get("act_number")),
                    _clean_spaces(payload.get("act_year")),
                ),
            ).fetchone()
            params = (
                _clean_spaces(payload.get("title")),
                _slugify(str(payload.get("slug") or payload.get("title"))),
                _clean_spaces(payload.get("issuing_body")),
                _normalize_token(payload.get("act_type")),
                _clean_spaces(payload.get("act_number")),
                _clean_spaces(payload.get("act_year")),
                _clean_spaces(payload.get("act_date")),
                matter_id,
                submatter_id,
                str(payload.get("summary") or ""),
                str(payload.get("full_text") or ""),
                _clean_spaces(payload.get("source_url")),
                payload.get("source_document_id"),
            )
            if existing:
                old_payload = dict(existing)
                conn.execute(
                    """
                    UPDATE prassi
                    SET title = ?, slug = ?, issuing_body = ?, act_type = ?, act_number = ?, act_year = ?,
                        act_date = ?, matter_id = ?, submatter_id = ?, summary = ?, full_text = ?,
                        source_url = ?, source_document_id = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    params + (int(existing["id"]),),
                )
                entity_id = int(existing["id"])
                action = "update"
            else:
                entity_id = self._insert_and_get_id(
                    conn,
                    """
                    INSERT INTO prassi (
                        title, slug, issuing_body, act_type, act_number, act_year, act_date,
                        matter_id, submatter_id, summary, full_text, source_url, source_document_id,
                        created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """,
                    params,
                )
                old_payload = {}
                action = "create"
            conn.commit()
        created = self.get_prassi(entity_id) or {}
        self.record_audit("prassi", entity_id, action, old_payload, created, performed_by)
        return created

    def get_prassi(self, entity_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM prassi WHERE id = ?", (int(entity_id),)).fetchone()
        return dict(row) if row else None

    def create_or_update_news(self, payload: dict[str, Any], *, performed_by: str) -> dict[str, Any]:
        slug = _slugify(str(payload.get("slug") or payload.get("title")))
        with self._connect() as conn:
            matter_id = self._matter_id(conn, str(payload.get("matter_slug") or ""))
            submatter_id = self._matter_id(conn, str(payload.get("submatter_slug") or ""))
            existing = conn.execute(
                """
                SELECT * FROM news
                WHERE slug = ? OR (source_document_id = ? AND news_type = ?) OR (source_url = ? AND news_type = ?)
                """,
                (
                    slug,
                    payload.get("source_document_id"),
                    _normalize_token(payload.get("news_type") or "focus"),
                    _clean_spaces(payload.get("source_url")),
                    _normalize_token(payload.get("news_type") or "focus"),
                ),
            ).fetchone()
            params = (
                _clean_spaces(payload.get("title")),
                slug,
                str(payload.get("short_summary") or ""),
                str(payload.get("content") or ""),
                _normalize_token(payload.get("news_type") or "focus"),
                matter_id,
                submatter_id,
                payload.get("related_normative_id"),
                payload.get("related_jurisprudence_id"),
                payload.get("related_prassi_id"),
                _clean_spaces(payload.get("source_url")),
                payload.get("source_document_id"),
                1 if payload.get("is_auto_generated", True) else 0,
                _normalize_token(payload.get("publication_status") or "published"),
                _clean_spaces(payload.get("published_at") or _now_iso()),
            )
            if existing:
                old_payload = dict(existing)
                conn.execute(
                    """
                    UPDATE news
                    SET title = ?, slug = ?, short_summary = ?, content = ?, news_type = ?,
                        matter_id = ?, submatter_id = ?, related_normative_id = ?, related_jurisprudence_id = ?,
                        related_prassi_id = ?, source_url = ?, source_document_id = ?, is_auto_generated = ?,
                        publication_status = ?, published_at = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    params + (int(existing["id"]),),
                )
                entity_id = int(existing["id"])
                action = "update"
            else:
                entity_id = self._insert_and_get_id(
                    conn,
                    """
                    INSERT INTO news (
                        title, slug, short_summary, content, news_type, matter_id, submatter_id,
                        related_normative_id, related_jurisprudence_id, related_prassi_id, source_url,
                        source_document_id, is_auto_generated, publication_status, published_at,
                        created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """,
                    params,
                )
                old_payload = {}
                action = "create"
            conn.commit()
        created = self.get_news(entity_id) or {}
        self.record_audit("news", entity_id, action, old_payload, created, performed_by)
        return created

    def get_news(self, entity_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT n.*, m.slug AS matter_slug, m.name AS matter_name,
                       sm.slug AS submatter_slug, sm.name AS submatter_name
                FROM news n
                LEFT JOIN matters m ON m.id = n.matter_id
                LEFT JOIN matters sm ON sm.id = n.submatter_id
                WHERE n.id = ?
                """,
                (int(entity_id),),
            ).fetchone()
        return dict(row) if row else None

    def get_news_by_slug(self, slug: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT n.*, m.slug AS matter_slug, m.name AS matter_name,
                       sm.slug AS submatter_slug, sm.name AS submatter_name
                FROM news n
                LEFT JOIN matters m ON m.id = n.matter_id
                LEFT JOIN matters sm ON sm.id = n.submatter_id
                WHERE n.slug = ? AND n.publication_status = 'published'
                """,
                (_slugify(slug),),
            ).fetchone()
        return dict(row) if row else None

    def get_news_detail(self, entity_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT n.*, m.slug AS matter_slug, m.name AS matter_name,
                       sm.slug AS submatter_slug, sm.name AS submatter_name
                FROM news n
                LEFT JOIN matters m ON m.id = n.matter_id
                LEFT JOIN matters sm ON sm.id = n.submatter_id
                WHERE n.id = ?
                """,
                (int(entity_id),),
            ).fetchone()
        return dict(row) if row else None

    def list_news(
        self,
        *,
        matter_slug: str = "",
        news_type: str = "",
        limit: int = 50,
        include_drafts: bool = False,
    ) -> list[dict[str, Any]]:
        clauses = []
        params: list[Any] = []
        if not include_drafts:
            clauses.append("n.publication_status = 'published'")
        if matter_slug:
            clauses.append("m.slug = ?")
            params.append(_normalize_token(matter_slug))
        if news_type:
            clauses.append("n.news_type = ?")
            params.append(_normalize_token(news_type))
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(int(limit))
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT n.*, m.slug AS matter_slug, m.name AS matter_name,
                       sm.slug AS submatter_slug, sm.name AS submatter_name
                FROM news n
                LEFT JOIN matters m ON m.id = n.matter_id
                LEFT JOIN matters sm ON sm.id = n.submatter_id
                {where}
                ORDER BY COALESCE(NULLIF(n.published_at, ''), n.created_at) DESC
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_published_normative(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT n.*, m.name AS matter_name, sm.name AS submatter_name
                FROM normative n
                LEFT JOIN matters m ON m.id = n.matter_id
                LEFT JOIN matters sm ON sm.id = n.submatter_id
                ORDER BY COALESCE(NULLIF(n.effective_date, ''), n.publication_date, n.created_at) DESC
                LIMIT ?
                """,
                (int(limit),),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_normative_versions(self, normative_id: int) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM normative_versions
                WHERE normative_id = ?
                ORDER BY COALESCE(NULLIF(valid_from, ''), created_at) DESC, id DESC
                """,
                (int(normative_id),),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_published_jurisprudence(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT j.*, m.name AS matter_name, sm.name AS submatter_name
                FROM jurisprudence j
                LEFT JOIN matters m ON m.id = j.matter_id
                LEFT JOIN matters sm ON sm.id = j.submatter_id
                ORDER BY COALESCE(NULLIF(j.publication_date, ''), j.decision_date, j.created_at) DESC
                LIMIT ?
                """,
                (int(limit),),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_published_prassi(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT p.*, m.name AS matter_name, sm.name AS submatter_name
                FROM prassi p
                LEFT JOIN matters m ON m.id = p.matter_id
                LEFT JOIN matters sm ON sm.id = p.submatter_id
                ORDER BY COALESCE(NULLIF(p.act_date, ''), p.created_at) DESC
                LIMIT ?
                """,
                (int(limit),),
            ).fetchall()
        return [dict(row) for row in rows]

    def _lex_fetch_rows(
        self,
        conn: Any,
        sql: str,
        params: list[Any],
        *,
        terms: list[str],
        fields: tuple[str, ...],
        limit: int,
    ) -> list[dict[str, Any]]:
        search_params = list(params)
        statement = sql.replace("{search_clause}", _search_clause(fields, terms, search_params))
        search_params.append(int(limit))
        rows = conn.execute(statement, tuple(search_params)).fetchall()
        return [dict(row) for row in rows]

    def _lex_sql_candidates(self, conn: Any, *, terms: list[str], limit: int) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        rows.extend(
            self._lex_fetch_rows(
                conn,
                """
                SELECT 'news' AS entity_type, 'legal_updates' AS source_type, n.id AS entity_id,
                       n.title, n.short_summary AS excerpt, n.content, n.news_type AS category,
                       n.publication_status, n.source_url AS official_url, n.published_at,
                       n.created_at, m.slug AS matter_slug, m.name AS matter_name,
                       sm.slug AS submatter_slug, sm.name AS submatter_name,
                       s.name AS authority, s.code AS source_code, s.trust_class, s.is_official,
                       s.base_url AS source_base_url, 0.66 AS _base_score
                FROM news n
                LEFT JOIN source_documents_normalized nd ON nd.id = n.source_document_id
                LEFT JOIN source_documents_raw rd ON rd.id = nd.raw_document_id
                LEFT JOIN sources s ON s.id = rd.source_id
                LEFT JOIN matters m ON m.id = n.matter_id
                LEFT JOIN matters sm ON sm.id = n.submatter_id
                WHERE n.publication_status = 'published'
                {search_clause}
                ORDER BY COALESCE(NULLIF(n.published_at, ''), n.created_at) DESC, n.id DESC
                LIMIT ?
                """,
                [],
                terms=terms,
                fields=("n.title", "n.short_summary", "n.content", "n.news_type", "m.name", "sm.name"),
                limit=limit,
            )
        )
        rows.extend(
            self._lex_fetch_rows(
                conn,
                """
                SELECT 'normative' AS entity_type, 'normativa' AS source_type, n.id AS entity_id,
                       n.title, n.summary AS excerpt, n.text_current AS content, n.norm_type AS category,
                       n.status AS publication_status, n.source_url AS official_url,
                       COALESCE(NULLIF(n.effective_date, ''), n.publication_date) AS published_at,
                       n.created_at, m.slug AS matter_slug, m.name AS matter_name,
                       sm.slug AS submatter_slug, sm.name AS submatter_name,
                       n.issuer AS authority, s.code AS source_code,
                       COALESCE(NULLIF(s.trust_class, ''), 'A') AS trust_class,
                       COALESCE(s.is_official, 1) AS is_official,
                       s.base_url AS source_base_url, 0.78 AS _base_score,
                       n.norm_type, n.norm_number, n.norm_year, n.effective_date
                FROM normative n
                LEFT JOIN source_documents_normalized nd ON nd.id = n.source_document_id
                LEFT JOIN source_documents_raw rd ON rd.id = nd.raw_document_id
                LEFT JOIN sources s ON s.id = rd.source_id
                LEFT JOIN matters m ON m.id = n.matter_id
                LEFT JOIN matters sm ON sm.id = n.submatter_id
                WHERE 1 = 1
                {search_clause}
                ORDER BY COALESCE(NULLIF(n.effective_date, ''), n.publication_date, n.created_at) DESC, n.id DESC
                LIMIT ?
                """,
                [],
                terms=terms,
                fields=("n.title", "n.summary", "n.text_current", "n.notes", "n.issuer", "n.norm_type", "n.norm_number", "m.name", "sm.name"),
                limit=limit,
            )
        )
        rows.extend(
            self._lex_fetch_rows(
                conn,
                """
                SELECT 'jurisprudence' AS entity_type, 'giurisprudenza' AS source_type, j.id AS entity_id,
                       j.title, j.summary AS excerpt, j.full_text AS content, 'giurisprudenza' AS category,
                       'published' AS publication_status, j.source_url AS official_url,
                       COALESCE(NULLIF(j.publication_date, ''), j.decision_date) AS published_at,
                       j.created_at, m.slug AS matter_slug, m.name AS matter_name,
                       sm.slug AS submatter_slug, sm.name AS submatter_name,
                       j.court_name AS authority, s.code AS source_code,
                       COALESCE(NULLIF(s.trust_class, ''), 'A') AS trust_class,
                       COALESCE(s.is_official, 1) AS is_official,
                       s.base_url AS source_base_url, 0.76 AS _base_score,
                       j.court_name, j.section_name, j.decision_number, j.decision_year,
                       j.decision_date, j.principle_of_law
                FROM jurisprudence j
                LEFT JOIN source_documents_normalized nd ON nd.id = j.source_document_id
                LEFT JOIN source_documents_raw rd ON rd.id = nd.raw_document_id
                LEFT JOIN sources s ON s.id = rd.source_id
                LEFT JOIN matters m ON m.id = j.matter_id
                LEFT JOIN matters sm ON sm.id = j.submatter_id
                WHERE 1 = 1
                {search_clause}
                ORDER BY COALESCE(NULLIF(j.publication_date, ''), j.decision_date, j.created_at) DESC, j.id DESC
                LIMIT ?
                """,
                [],
                terms=terms,
                fields=("j.title", "j.summary", "j.full_text", "j.principle_of_law", "j.court_name", "j.decision_number", "j.decision_year", "m.name", "sm.name"),
                limit=limit,
            )
        )
        rows.extend(
            self._lex_fetch_rows(
                conn,
                """
                SELECT 'prassi' AS entity_type, 'prassi' AS source_type, p.id AS entity_id,
                       p.title, p.summary AS excerpt, p.full_text AS content, p.act_type AS category,
                       'published' AS publication_status, p.source_url AS official_url,
                       p.act_date AS published_at, p.created_at,
                       m.slug AS matter_slug, m.name AS matter_name,
                       sm.slug AS submatter_slug, sm.name AS submatter_name,
                       p.issuing_body AS authority, s.code AS source_code,
                       COALESCE(NULLIF(s.trust_class, ''), 'B') AS trust_class,
                       COALESCE(s.is_official, 1) AS is_official,
                       s.base_url AS source_base_url, 0.72 AS _base_score,
                       p.issuing_body, p.act_type, p.act_number, p.act_year
                FROM prassi p
                LEFT JOIN source_documents_normalized nd ON nd.id = p.source_document_id
                LEFT JOIN source_documents_raw rd ON rd.id = nd.raw_document_id
                LEFT JOIN sources s ON s.id = rd.source_id
                LEFT JOIN matters m ON m.id = p.matter_id
                LEFT JOIN matters sm ON sm.id = p.submatter_id
                WHERE 1 = 1
                {search_clause}
                ORDER BY COALESCE(NULLIF(p.act_date, ''), p.created_at) DESC, p.id DESC
                LIMIT ?
                """,
                [],
                terms=terms,
                fields=("p.title", "p.summary", "p.full_text", "p.issuing_body", "p.act_type", "p.act_number", "p.act_year", "m.name", "sm.name"),
                limit=limit,
            )
        )
        rows.extend(
            self._lex_fetch_rows(
                conn,
                """
                SELECT 'web_evidence' AS entity_type, 'legal_web_evidence' AS source_type, e.id AS entity_id,
                       e.title, e.excerpt, e.content_text AS content,
                       COALESCE(NULLIF(e.attachment_type, ''), e.origin) AS category,
                       e.verification_status AS publication_status,
                       COALESCE(NULLIF(e.attachment_url, ''), e.source_url) AS official_url,
                       e.created_at AS published_at, e.created_at,
                       '' AS matter_slug, '' AS matter_name, '' AS submatter_slug, '' AS submatter_name,
                       COALESCE(NULLIF(e.source_name, ''), e.source_code) AS authority,
                       e.source_code, 'A' AS trust_class, e.is_official,
                       e.source_url AS source_base_url, 0.82 AS _base_score,
                       e.origin, e.attachment_url, e.attachment_type, e.sha256,
                       e.context_chars, e.verification_status
                FROM web_verification_evidence e
                WHERE e.verification_status IN ('verified', 'insufficient')
                {search_clause}
                ORDER BY e.is_official DESC, e.context_chars DESC, e.created_at DESC, e.id DESC
                LIMIT ?
                """,
                [],
                terms=terms,
                fields=("e.title", "e.excerpt", "e.content_text", "e.query", "e.source_name", "e.source_url", "e.attachment_url"),
                limit=limit,
            )
        )
        return rows

    def _lex_evidence_payload(self, row: dict[str, Any], terms: list[str]) -> dict[str, Any]:
        entity_type = _normalize_token(row.get("entity_type"))
        entity_id = _clean_spaces(row.get("entity_id"))
        source_type = _normalize_token(row.get("source_type") or "legal_updates")
        trust_class = _clean_spaces(row.get("trust_class")).upper()
        is_official = bool(row.get("is_official", True))
        if not trust_class:
            trust_class = "A" if source_type in {"normativa", "giurisprudenza"} else "B"
        source_level = 1 if trust_class == "A" and is_official else 2 if trust_class in {"A", "B"} else 3
        official_url = _first_text(row.get("official_url"), row.get("source_base_url"))
        authority = _first_text(row.get("authority"), row.get("source_code"), "Update Intelligence SQL")
        excerpt = _lex_excerpt(row.get("excerpt"), row.get("principle_of_law"), row.get("content"))
        content = _lex_excerpt(row.get("content"), row.get("excerpt"), row.get("principle_of_law"), limit=900)
        payload = {
            "type": source_type,
            "id": f"legal-updates-{entity_type}:{entity_id}",
            "title": _first_text(row.get("title"), authority, "Aggiornamento legale"),
            "excerpt": excerpt or content,
            "content": content or excerpt,
            "score": _lex_candidate_score(row, terms),
            "authority": authority,
            "official_url": official_url,
            "published_at": _first_text(row.get("published_at"), row.get("created_at")),
            "trust_class": trust_class,
            "source_level": source_level,
            "verified_reference": bool(official_url and source_level <= 2),
            "source_policy_tier": "tier_1" if source_level == 1 else "tier_2" if source_level == 2 else "tier_3",
            "repository": "legal_updates_sql",
            "db_path": self.db_path,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "publication_status": _clean_spaces(row.get("publication_status")),
            "category": _clean_spaces(row.get("category")),
            "matter_slug": _clean_spaces(row.get("matter_slug")),
            "matter_name": _clean_spaces(row.get("matter_name")),
            "submatter_slug": _clean_spaces(row.get("submatter_slug")),
            "submatter_name": _clean_spaces(row.get("submatter_name")),
            "source_code": _clean_spaces(row.get("source_code")),
        }
        for field in (
            "norm_type",
            "norm_number",
            "norm_year",
            "effective_date",
            "court_name",
            "section_name",
            "decision_number",
            "decision_year",
            "decision_date",
            "principle_of_law",
            "issuing_body",
            "act_type",
            "act_number",
            "act_year",
            "origin",
            "attachment_url",
            "attachment_type",
            "sha256",
            "context_chars",
            "verification_status",
        ):
            if _clean_spaces(row.get(field)):
                payload[field] = _clean_spaces(row.get(field))
        return payload

    def search_lex_sources(self, query: str, *, limit: int = 12) -> list[dict[str, Any]]:
        result_limit = _limit_value(limit, default=12, maximum=80)
        candidate_limit = max(result_limit * 6, 40)
        terms = _lex_search_terms(query)
        with self._connect() as conn:
            candidates = self._lex_sql_candidates(conn, terms=terms, limit=candidate_limit)
            if terms and not candidates:
                candidates = self._lex_sql_candidates(conn, terms=[], limit=candidate_limit)
        payloads = [self._lex_evidence_payload(row, terms) for row in candidates]
        payloads.sort(
            key=lambda row: (
                float(row.get("score") or 0.0),
                _clean_spaces(row.get("published_at")),
            ),
            reverse=True,
        )
        seen: set[tuple[str, str]] = set()
        deduped: list[dict[str, Any]] = []
        for row in payloads:
            key = (_clean_spaces(row.get("type")), _clean_spaces(row.get("id")))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(row)
            if len(deduped) >= result_limit:
                break
        return deduped

    def list_audit(self, *, entity_type: str = "", limit: int = 100) -> list[dict[str, Any]]:
        clauses = []
        params: list[Any] = []
        if entity_type:
            clauses.append("entity_type = ?")
            params.append(_normalize_token(entity_type))
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(int(limit))
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT *
                FROM {self.audit_table}
                {where}
                ORDER BY id DESC
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()
        return [self._decode_row(row, json_fields=("old_data_json", "new_data_json")) or {} for row in rows]

    def dashboard_snapshot(self) -> dict[str, Any]:
        with self._connect() as conn:
            counts = {
                "sources": int(conn.execute("SELECT COUNT(*) FROM sources WHERE enabled = 1").fetchone()[0]),
                "raw_documents": int(conn.execute("SELECT COUNT(*) FROM source_documents_raw").fetchone()[0]),
                "normalized_documents": int(conn.execute("SELECT COUNT(*) FROM source_documents_normalized").fetchone()[0]),
                "analyses": int(conn.execute("SELECT COUNT(*) FROM ai_documents_analysis").fetchone()[0]),
                "review_pending": int(conn.execute("SELECT COUNT(*) FROM review_queue WHERE status = 'pending'").fetchone()[0]),
                "review_approved": int(conn.execute("SELECT COUNT(*) FROM review_queue WHERE status = 'approved'").fetchone()[0]),
                "published_news": int(conn.execute("SELECT COUNT(*) FROM news WHERE publication_status = 'published'").fetchone()[0]),
                "published_normative": int(conn.execute("SELECT COUNT(*) FROM normative").fetchone()[0]),
                "published_jurisprudence": int(conn.execute("SELECT COUNT(*) FROM jurisprudence").fetchone()[0]),
                "published_prassi": int(conn.execute("SELECT COUNT(*) FROM prassi").fetchone()[0]),
                "web_evidence": int(conn.execute("SELECT COUNT(*) FROM web_verification_evidence").fetchone()[0]),
                "web_evidence_verified": int(conn.execute("SELECT COUNT(*) FROM web_verification_evidence WHERE verification_status = 'verified'").fetchone()[0]),
                "web_evidence_attachments": int(conn.execute("SELECT COUNT(*) FROM web_verification_evidence WHERE attachment_url <> ''").fetchone()[0]),
                "documents_with_attachments": int(
                    conn.execute(
                        """
                        SELECT COUNT(*)
                        FROM source_documents_normalized
                        WHERE attachments_json <> '' AND attachments_json <> '[]'
                        """
                    ).fetchone()[0]
                ),
            }
            latest_audit = conn.execute(
                f"SELECT created_at, action, entity_type, entity_id, performed_by FROM {self.audit_table} ORDER BY id DESC LIMIT 12"
            ).fetchall()
        return {
            "headline": counts,
            "quality": {
                "duplicates": self.archive_duplicate_summary(),
                "auto_publish_window": "00:00-05:00",
                "auto_publish_scope": "Fonti ufficiali e contenuti utili allo studio legale",
                "dedupe_policy": "Controllo archivio prima della proposta",
            },
            "sources": self.list_sources(enabled_only=False),
            "review_queue": self.list_review_queue(limit=20),
            "news": self.list_news(limit=8, include_drafts=False),
            "normative": self.list_published_normative(limit=8),
            "jurisprudence": self.list_published_jurisprudence(limit=8),
            "prassi": self.list_published_prassi(limit=8),
            "audit": [dict(row) for row in latest_audit],
        }

    def export_repository_json(self) -> str:
        if not self.json_path:
            return ""
        target = Path(self.json_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.dashboard_snapshot(), ensure_ascii=False, indent=2), encoding="utf-8")
        return str(target)
