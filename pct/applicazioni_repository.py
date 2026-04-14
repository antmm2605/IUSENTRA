from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

from pct.applicazioni_catalogo import (
    ACCESS_META,
    FEATURED_DEFAULT_SLUGS,
    SECTION_KIND_META,
    SECTION_SPECS,
    STATUS_META,
    applicazioni_correlate,
    applicazioni_primo_piano,
    catalogo_applicazioni,
    get_sezioni_catalogo,
    statistiche_catalogo,
)


SCHEMA_APPLICAZIONI_REPOSITORY = Path(__file__).with_name("sql") / "20260414_applicazioni_repository.sql"

_TELEMATIC_MARKERS = ("telematic", "pst", "pdp", "pat", "ptt", "pec", "reginde", "fascicolo telematico")
_CLIENT_MARKERS = ("cliente", "clienti", "fattura", "fatturazione", "preventivo", "parcella", "notula")
_FASCICOLO_MARKERS = ("fascicolo", "fascicoli", "deposito", "atto", "atti", "udienza", "scadenza", "termine")

_RUNTIME_REPOSITORIES: dict[str, "GestioneApplicazioniRepository"] = {}


def _clean_spaces(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _normalize_text(value: Any) -> str:
    return _clean_spaces(value).lower()


def _from_json(value: Any, fallback: Any) -> Any:
    text = _clean_spaces(value)
    if not text:
        return fallback
    try:
        return json.loads(text)
    except Exception:
        return fallback


def _to_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


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


def _payload_signature(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _score_row(terms: list[str], row: dict[str, Any]) -> int:
    if not terms:
        return 0
    title = _normalize_text(row.get("title"))
    summary = _normalize_text(row.get("summary"))
    section = _normalize_text(row.get("section_title"))
    keywords = " ".join(_normalize_text(item) for item in row.get("keywords") or [])
    endpoint = _normalize_text(row.get("endpoint"))
    search_text = _normalize_text(row.get("search_text"))
    score = 0
    for term in terms:
        if term in title:
            score += 8
        if term in keywords:
            score += 6
        if term in summary:
            score += 4
        if term in section:
            score += 3
        if term in endpoint:
            score += 2
        if term in search_text:
            score += 1
    if row.get("featured"):
        score += 2
    if row.get("access_mode") == "diretta":
        score += 2
    if row.get("available"):
        score += 1
    return score


def _select_ranked(rows: list[dict[str, Any]], terms: list[str], limit: int = 5) -> list[dict[str, Any]]:
    scored: list[tuple[int, int, dict[str, Any]]] = []
    for index, row in enumerate(rows):
        scored.append((_score_row(terms, row), -index, row))
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    selected = [row for score, _index, row in scored if score > 0][:limit]
    return selected if selected else rows[:limit]


def _derive_runtime_root(anchor_path: str | None = None) -> Path:
    if not _clean_spaces(anchor_path):
        return Path("./data/applicazioni").resolve()
    target = Path(str(anchor_path)).resolve()
    if target.suffix:
        parent = target.parent
        if parent.name.lower() == "config":
            return parent.parent / "applicazioni"
        return parent / "applicazioni"
    return target


def default_applicazioni_repository_db_path(anchor_path: str | None = None) -> str:
    return str(_derive_runtime_root(anchor_path) / "applicazioni_repository.db")


def derive_applicazioni_repository_json_path(db_path: str) -> str:
    return str(Path(db_path).resolve().with_name("applicazioni_repository.json"))


def derive_applicazioni_sections_json_path(db_path: str) -> str:
    return str(Path(db_path).resolve().with_name("applicazioni_sections_repository.json"))


def derive_applicazioni_catalog_json_path(db_path: str) -> str:
    return str(Path(db_path).resolve().with_name("applicazioni_catalog_repository.json"))


def derive_applicazioni_status_json_path(db_path: str) -> str:
    return str(Path(db_path).resolve().with_name("applicazioni_status_repository.json"))


def derive_applicazioni_access_json_path(db_path: str) -> str:
    return str(Path(db_path).resolve().with_name("applicazioni_access_repository.json"))


def derive_applicazioni_section_kinds_json_path(db_path: str) -> str:
    return str(Path(db_path).resolve().with_name("applicazioni_section_kinds_repository.json"))


def derive_applicazioni_featured_json_path(db_path: str) -> str:
    return str(Path(db_path).resolve().with_name("applicazioni_featured_repository.json"))


def derive_applicazioni_statistics_json_path(db_path: str) -> str:
    return str(Path(db_path).resolve().with_name("applicazioni_statistics_repository.json"))


def _infer_requires_cliente(entry: dict[str, Any]) -> bool:
    bag = _normalize_text(
        _build_search_text(
            entry.get("title"),
            entry.get("summary"),
            entry.get("section_title"),
            entry.get("keywords") or [],
        )
    )
    return any(marker in bag for marker in _CLIENT_MARKERS)


def _infer_requires_fascicolo(entry: dict[str, Any]) -> bool:
    bag = _normalize_text(
        _build_search_text(
            entry.get("title"),
            entry.get("summary"),
            entry.get("section_title"),
            entry.get("keywords") or [],
        )
    )
    return any(marker in bag for marker in _FASCICOLO_MARKERS)


def _infer_requires_telematic_context(entry: dict[str, Any]) -> bool:
    bag = _normalize_text(
        _build_search_text(
            entry.get("title"),
            entry.get("summary"),
            entry.get("section_title"),
            entry.get("section_description"),
            entry.get("keywords") or [],
        )
    )
    return any(marker in bag for marker in _TELEMATIC_MARKERS)


def _build_capabilities(entry: dict[str, Any]) -> list[str]:
    capabilities = ["workspace_registry"]
    if entry.get("access_mode") == "diretta":
        capabilities.append("apertura_diretta_modulo")
    elif entry.get("access_mode") == "guidata":
        capabilities.append("percorso_guidato")
    else:
        capabilities.append("scheda_workspace")
    if entry.get("featured"):
        capabilities.append("primo_piano")
    if _infer_requires_cliente(entry):
        capabilities.append("richiede_contesto_cliente")
    if _infer_requires_fascicolo(entry):
        capabilities.append("richiede_contesto_fascicolo")
    if _infer_requires_telematic_context(entry):
        capabilities.append("contesto_telematico")
    return capabilities


def _build_blocked_if(entry: dict[str, Any]) -> list[str]:
    blocked_if: list[str] = []
    if _infer_requires_cliente(entry):
        blocked_if.append("manca_cliente")
    if _infer_requires_fascicolo(entry):
        blocked_if.append("manca_fascicolo")
    if _infer_requires_telematic_context(entry):
        blocked_if.append("manca_contesto_telematico")
    return blocked_if


def build_applicazioni_sections_rows() -> list[dict[str, Any]]:
    counts = {row["id"]: row["items_count"] for row in get_sezioni_catalogo()}
    rows: list[dict[str, Any]] = []
    for section in SECTION_SPECS:
        kind_meta = SECTION_KIND_META.get(section["id"], {})
        row = {
            "section_id": _clean_spaces(section.get("id")),
            "title": _clean_spaces(section.get("title")),
            "icon": _clean_spaces(section.get("icon")),
            "accent": _clean_spaces(section.get("accent")),
            "description": _clean_spaces(section.get("description")),
            "default_status": _clean_spaces(section.get("default_status")),
            "default_endpoint": _clean_spaces(section.get("default_endpoint")),
            "default_cta_label": _clean_spaces(section.get("default_cta_label")),
            "default_params": dict(section.get("default_params") or {}),
            "items": [_clean_spaces(item) for item in section.get("items") or [] if _clean_spaces(item)],
            "items_count": int(counts.get(section["id"], len(section.get("items") or []))),
            "workspace_kind": _clean_spaces(kind_meta.get("id")),
            "workspace_kind_label": _clean_spaces(kind_meta.get("label")),
            "workspace_kind_badge_class": _clean_spaces(kind_meta.get("badge_class")),
        }
        row["search_text"] = _build_search_text(
            row.get("section_id"),
            row.get("title"),
            row.get("description"),
            row.get("default_status"),
            row.get("default_endpoint"),
            row.get("default_cta_label"),
            row.get("workspace_kind"),
            row.get("workspace_kind_label"),
            row.get("items") or [],
        )
        rows.append(row)
    return rows


def build_applicazioni_catalog_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entry in catalogo_applicazioni():
        keywords = [_clean_spaces(item) for item in entry.get("keywords") or [] if _clean_spaces(item)]
        requires_cliente = _infer_requires_cliente(entry)
        requires_fascicolo = _infer_requires_fascicolo(entry)
        requires_telematic_context = _infer_requires_telematic_context(entry)
        row = {
            "app_id": _clean_spaces(entry.get("id")),
            "title": _clean_spaces(entry.get("title")),
            "section_id": _clean_spaces(entry.get("section_id")),
            "section_title": _clean_spaces(entry.get("section_title")),
            "section_icon": _clean_spaces(entry.get("section_icon")),
            "section_accent": _clean_spaces(entry.get("section_accent")),
            "section_description": _clean_spaces(entry.get("section_description")),
            "summary": _clean_spaces(entry.get("summary")),
            "status": _clean_spaces(entry.get("status")),
            "status_label": _clean_spaces(entry.get("status_label")),
            "status_description": _clean_spaces(entry.get("status_description")),
            "access_mode": _clean_spaces(entry.get("access_mode")),
            "access_mode_label": _clean_spaces(entry.get("access_mode_label")),
            "access_mode_description": _clean_spaces(entry.get("access_mode_description")),
            "endpoint": _clean_spaces(entry.get("endpoint")),
            "params": dict(entry.get("params") or {}),
            "cta_label": _clean_spaces(entry.get("cta_label")),
            "keywords": keywords,
            "workspace_kind": _clean_spaces(entry.get("workspace_kind")),
            "workspace_kind_label": _clean_spaces(entry.get("workspace_kind_label")),
            "featured": bool(entry.get("featured")),
            "available": bool(entry.get("available", True)),
            "sort_order": int(entry.get("order") or 0),
            "requires_guided_flow": _clean_spaces(entry.get("access_mode")) != "diretta",
            "requires_login": True,
            "requires_cliente": requires_cliente,
            "requires_fascicolo": requires_fascicolo,
            "requires_telematic_context": requires_telematic_context,
            "domain_area": _clean_spaces(entry.get("section_title")),
            "detail_path": f"/applicazioni/{_clean_spaces(entry.get('id'))}",
        }
        row["capabilities"] = _build_capabilities({**entry, "keywords": keywords})
        row["suggested_when"] = keywords[:]
        row["blocked_if"] = _build_blocked_if({**entry, "keywords": keywords})
        row["health_state"] = "ok" if row["available"] else "non_disponibile"
        row["search_text"] = _build_search_text(
            row.get("title"),
            row.get("summary"),
            row.get("section_title"),
            row.get("section_description"),
            row.get("status_label"),
            row.get("workspace_kind_label"),
            row.get("access_mode_label"),
            row.get("endpoint"),
            row.get("keywords") or [],
            row.get("capabilities") or [],
        )
        rows.append(row)
    rows.sort(key=lambda item: (item.get("sort_order") or 0, item.get("title") or ""))
    return rows


def build_applicazioni_status_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key, meta in STATUS_META.items():
        row = {
            "status_id": _clean_spaces(key),
            "label": _clean_spaces(meta.get("label")),
            "badge_class": _clean_spaces(meta.get("badge_class")),
            "description": _clean_spaces(meta.get("description")),
        }
        row["search_text"] = _build_search_text(row.get("status_id"), row.get("label"), row.get("description"))
        rows.append(row)
    rows.sort(key=lambda item: item["status_id"])
    return rows


def build_applicazioni_access_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key, meta in ACCESS_META.items():
        row = {
            "access_id": _clean_spaces(key),
            "label": _clean_spaces(meta.get("label")),
            "badge_class": _clean_spaces(meta.get("badge_class")),
            "description": _clean_spaces(meta.get("description")),
        }
        row["search_text"] = _build_search_text(row.get("access_id"), row.get("label"), row.get("description"))
        rows.append(row)
    rows.sort(key=lambda item: item["access_id"])
    return rows


def build_applicazioni_section_kind_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key, meta in SECTION_KIND_META.items():
        row = {
            "section_id": _clean_spaces(key),
            "workspace_kind": _clean_spaces(meta.get("id")),
            "workspace_kind_label": _clean_spaces(meta.get("label")),
            "workspace_kind_badge_class": _clean_spaces(meta.get("badge_class")),
        }
        row["search_text"] = _build_search_text(
            row.get("section_id"),
            row.get("workspace_kind"),
            row.get("workspace_kind_label"),
        )
        rows.append(row)
    rows.sort(key=lambda item: item["section_id"])
    return rows


def build_applicazioni_featured_rows(catalog_rows: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    catalog_index = {row["app_id"]: row for row in catalog_rows or build_applicazioni_catalog_rows()}
    rows: list[dict[str, Any]] = []
    for entry in applicazioni_primo_piano(catalogo_applicazioni(), limit=200):
        app_id = _clean_spaces(entry.get("id"))
        catalog_row = dict(catalog_index.get(app_id) or {})
        row = {
            "app_id": app_id,
            "title": _clean_spaces(entry.get("title") or catalog_row.get("title")),
            "section_id": _clean_spaces(entry.get("section_id") or catalog_row.get("section_id")),
            "section_title": _clean_spaces(entry.get("section_title") or catalog_row.get("section_title")),
            "summary": _clean_spaces(entry.get("summary") or catalog_row.get("summary")),
            "status": _clean_spaces(entry.get("status") or catalog_row.get("status")),
            "status_label": _clean_spaces(entry.get("status_label") or catalog_row.get("status_label")),
            "access_mode": _clean_spaces(entry.get("access_mode") or catalog_row.get("access_mode")),
            "access_mode_label": _clean_spaces(entry.get("access_mode_label") or catalog_row.get("access_mode_label")),
            "endpoint": _clean_spaces(entry.get("endpoint") or catalog_row.get("endpoint")),
            "params": dict(entry.get("params") or catalog_row.get("params") or {}),
            "cta_label": _clean_spaces(entry.get("cta_label") or catalog_row.get("cta_label")),
            "keywords": list(entry.get("keywords") or catalog_row.get("keywords") or []),
            "workspace_kind": _clean_spaces(entry.get("workspace_kind") or catalog_row.get("workspace_kind")),
            "workspace_kind_label": _clean_spaces(entry.get("workspace_kind_label") or catalog_row.get("workspace_kind_label")),
            "featured_default_slug": app_id in FEATURED_DEFAULT_SLUGS,
            "sort_order": int(entry.get("order") or catalog_row.get("sort_order") or 0),
        }
        row["search_text"] = _build_search_text(
            row.get("title"),
            row.get("section_title"),
            row.get("summary"),
            row.get("status_label"),
            row.get("access_mode_label"),
            row.get("endpoint"),
            row.get("keywords") or [],
        )
        rows.append(row)
    rows.sort(key=lambda item: (item.get("access_mode") or "", item.get("sort_order") or 0, item.get("title") or ""))
    return rows


def build_applicazioni_statistics_row() -> dict[str, Any]:
    stats = statistiche_catalogo(catalogo_applicazioni())
    row = {
        "stats_id": "catalog_stats",
        "totale": int(stats.get("totale") or 0),
        "per_stato": dict(stats.get("per_stato") or {}),
        "per_sezione": dict(stats.get("per_sezione") or {}),
        "per_tipo": dict(stats.get("per_tipo") or {}),
        "per_modalita": dict(stats.get("per_modalita") or {}),
        "sezioni_attive": int(stats.get("sezioni_attive") or 0),
        "primo_piano": int(stats.get("primo_piano") or 0),
        "accessi_diretti": int(stats.get("accessi_diretti") or 0),
    }
    row["search_text"] = _build_search_text(
        row.get("totale"),
        row.get("sezioni_attive"),
        row.get("primo_piano"),
        row.get("accessi_diretti"),
    )
    return row


class GestioneApplicazioniRepository:
    def __init__(
        self,
        db_path: str,
        *,
        json_path: str,
        sections_json_path: str,
        catalog_json_path: str,
        statuses_json_path: str,
        access_json_path: str,
        section_kinds_json_path: str,
        featured_json_path: str,
        statistics_json_path: str,
    ) -> None:
        self.db_path = str(Path(db_path))
        self.json_path = str(Path(json_path))
        self.sections_json_path = str(Path(sections_json_path))
        self.catalog_json_path = str(Path(catalog_json_path))
        self.statuses_json_path = str(Path(statuses_json_path))
        self.access_json_path = str(Path(access_json_path))
        self.section_kinds_json_path = str(Path(section_kinds_json_path))
        self.featured_json_path = str(Path(featured_json_path))
        self.statistics_json_path = str(Path(statistics_json_path))
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA_APPLICAZIONI_REPOSITORY.read_text(encoding="utf-8"))

    def _set_meta(self, key: str, value: Any) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO applicazioni_repository_meta (meta_key, meta_value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(meta_key) DO UPDATE SET
                    meta_value=excluded.meta_value,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (key, _clean_spaces(value)),
            )

    def _write_json(self, path: str, payload: dict[str, Any]) -> str:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(target)

    def rebuild_from_payload(self, payload: dict[str, Any]) -> None:
        sections = list(payload.get("sections") or [])
        catalog = list(payload.get("catalog") or [])
        statuses = list(payload.get("statuses") or [])
        access_modes = list(payload.get("access_modes") or [])
        section_kinds = list(payload.get("section_kinds") or [])
        featured = list(payload.get("featured") or [])
        statistics = dict(payload.get("statistics") or {})
        with self._connect() as conn:
            conn.execute("DELETE FROM applicazioni_sections_repository")
            conn.execute("DELETE FROM applicazioni_catalog_repository")
            conn.execute("DELETE FROM applicazioni_status_repository")
            conn.execute("DELETE FROM applicazioni_access_repository")
            conn.execute("DELETE FROM applicazioni_section_kinds_repository")
            conn.execute("DELETE FROM applicazioni_featured_repository")
            conn.execute("DELETE FROM applicazioni_statistics_repository")
            conn.executemany(
                """
                INSERT INTO applicazioni_sections_repository (
                    section_id, title, icon, accent, description, default_status,
                    default_endpoint, default_cta_label, default_params_json, items_json,
                    items_count, workspace_kind, workspace_kind_label, workspace_kind_badge_class,
                    search_text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        row.get("section_id"),
                        row.get("title"),
                        row.get("icon"),
                        row.get("accent"),
                        row.get("description"),
                        row.get("default_status"),
                        row.get("default_endpoint"),
                        row.get("default_cta_label"),
                        _to_json(row.get("default_params") or {}),
                        _to_json(row.get("items") or []),
                        int(row.get("items_count") or 0),
                        row.get("workspace_kind"),
                        row.get("workspace_kind_label"),
                        row.get("workspace_kind_badge_class"),
                        row.get("search_text"),
                    )
                    for row in sections
                ],
            )
            conn.executemany(
                """
                INSERT INTO applicazioni_catalog_repository (
                    app_id, title, section_id, section_title, section_icon, section_accent,
                    section_description, summary, status, status_label, status_description,
                    access_mode, access_mode_label, access_mode_description, endpoint, params_json,
                    cta_label, keywords_json, workspace_kind, workspace_kind_label, featured,
                    available, sort_order, requires_guided_flow, requires_login, requires_cliente,
                    requires_fascicolo, requires_telematic_context, domain_area, capabilities_json,
                    suggested_when_json, blocked_if_json, health_state, detail_path, search_text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        row.get("app_id"),
                        row.get("title"),
                        row.get("section_id"),
                        row.get("section_title"),
                        row.get("section_icon"),
                        row.get("section_accent"),
                        row.get("section_description"),
                        row.get("summary"),
                        row.get("status"),
                        row.get("status_label"),
                        row.get("status_description"),
                        row.get("access_mode"),
                        row.get("access_mode_label"),
                        row.get("access_mode_description"),
                        row.get("endpoint"),
                        _to_json(row.get("params") or {}),
                        row.get("cta_label"),
                        _to_json(row.get("keywords") or []),
                        row.get("workspace_kind"),
                        row.get("workspace_kind_label"),
                        1 if row.get("featured") else 0,
                        1 if row.get("available", True) else 0,
                        int(row.get("sort_order") or 0),
                        1 if row.get("requires_guided_flow") else 0,
                        1 if row.get("requires_login", True) else 0,
                        1 if row.get("requires_cliente") else 0,
                        1 if row.get("requires_fascicolo") else 0,
                        1 if row.get("requires_telematic_context") else 0,
                        row.get("domain_area"),
                        _to_json(row.get("capabilities") or []),
                        _to_json(row.get("suggested_when") or []),
                        _to_json(row.get("blocked_if") or []),
                        row.get("health_state"),
                        row.get("detail_path"),
                        row.get("search_text"),
                    )
                    for row in catalog
                ],
            )
            conn.executemany(
                """
                INSERT INTO applicazioni_status_repository (
                    status_id, label, badge_class, description, search_text
                ) VALUES (?, ?, ?, ?, ?)
                """,
                [(row.get("status_id"), row.get("label"), row.get("badge_class"), row.get("description"), row.get("search_text")) for row in statuses],
            )
            conn.executemany(
                """
                INSERT INTO applicazioni_access_repository (
                    access_id, label, badge_class, description, search_text
                ) VALUES (?, ?, ?, ?, ?)
                """,
                [(row.get("access_id"), row.get("label"), row.get("badge_class"), row.get("description"), row.get("search_text")) for row in access_modes],
            )
            conn.executemany(
                """
                INSERT INTO applicazioni_section_kinds_repository (
                    section_id, workspace_kind, workspace_kind_label, workspace_kind_badge_class, search_text
                ) VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        row.get("section_id"),
                        row.get("workspace_kind"),
                        row.get("workspace_kind_label"),
                        row.get("workspace_kind_badge_class"),
                        row.get("search_text"),
                    )
                    for row in section_kinds
                ],
            )
            conn.executemany(
                """
                INSERT INTO applicazioni_featured_repository (
                    app_id, title, section_id, section_title, summary, status, status_label,
                    access_mode, access_mode_label, endpoint, params_json, cta_label,
                    keywords_json, workspace_kind, workspace_kind_label, featured_default_slug,
                    sort_order, search_text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        row.get("app_id"),
                        row.get("title"),
                        row.get("section_id"),
                        row.get("section_title"),
                        row.get("summary"),
                        row.get("status"),
                        row.get("status_label"),
                        row.get("access_mode"),
                        row.get("access_mode_label"),
                        row.get("endpoint"),
                        _to_json(row.get("params") or {}),
                        row.get("cta_label"),
                        _to_json(row.get("keywords") or []),
                        row.get("workspace_kind"),
                        row.get("workspace_kind_label"),
                        1 if row.get("featured_default_slug") else 0,
                        int(row.get("sort_order") or 0),
                        row.get("search_text"),
                    )
                    for row in featured
                ],
            )
            if statistics:
                conn.execute(
                    """
                    INSERT INTO applicazioni_statistics_repository (
                        stats_id, totale, per_stato_json, per_sezione_json, per_tipo_json,
                        per_modalita_json, sezioni_attive, primo_piano, accessi_diretti, search_text
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        statistics.get("stats_id"),
                        int(statistics.get("totale") or 0),
                        _to_json(statistics.get("per_stato") or {}),
                        _to_json(statistics.get("per_sezione") or {}),
                        _to_json(statistics.get("per_tipo") or {}),
                        _to_json(statistics.get("per_modalita") or {}),
                        int(statistics.get("sezioni_attive") or 0),
                        int(statistics.get("primo_piano") or 0),
                        int(statistics.get("accessi_diretti") or 0),
                        statistics.get("search_text") or "",
                    ),
                )
        self._set_meta("signature", _payload_signature(payload))

    def synchronize_runtime(self, *, export_json: bool = True) -> None:
        catalog_rows = build_applicazioni_catalog_rows()
        payload = {
            "sections": build_applicazioni_sections_rows(),
            "catalog": catalog_rows,
            "statuses": build_applicazioni_status_rows(),
            "access_modes": build_applicazioni_access_rows(),
            "section_kinds": build_applicazioni_section_kind_rows(),
            "featured": build_applicazioni_featured_rows(catalog_rows),
            "statistics": build_applicazioni_statistics_row(),
        }
        self.rebuild_from_payload(payload)
        if export_json:
            self.export_repository_json()
            self.export_split_jsons()

    def storage_stats(self) -> dict[str, Any]:
        table_names = {
            "applicazioni_sections_repository": "applicazioni_sections_repository",
            "applicazioni_catalog_repository": "applicazioni_catalog_repository",
            "applicazioni_status_repository": "applicazioni_status_repository",
            "applicazioni_access_repository": "applicazioni_access_repository",
            "applicazioni_section_kinds_repository": "applicazioni_section_kinds_repository",
            "applicazioni_featured_repository": "applicazioni_featured_repository",
            "applicazioni_statistics_repository": "applicazioni_statistics_repository",
        }
        stats: dict[str, Any] = {}
        with self._connect() as conn:
            for key, table in table_names.items():
                stats[key] = int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        return stats

    def load_repository_payload(self) -> dict[str, Any]:
        with self._connect() as conn:
            section_rows = [dict(row) for row in conn.execute("SELECT * FROM applicazioni_sections_repository ORDER BY title")]
            catalog_rows = [dict(row) for row in conn.execute("SELECT * FROM applicazioni_catalog_repository ORDER BY sort_order, title")]
            status_rows = [dict(row) for row in conn.execute("SELECT * FROM applicazioni_status_repository ORDER BY status_id")]
            access_rows = [dict(row) for row in conn.execute("SELECT * FROM applicazioni_access_repository ORDER BY access_id")]
            section_kind_rows = [dict(row) for row in conn.execute("SELECT * FROM applicazioni_section_kinds_repository ORDER BY section_id")]
            featured_rows = [dict(row) for row in conn.execute("SELECT * FROM applicazioni_featured_repository ORDER BY sort_order, title")]
            statistics_row = conn.execute("SELECT * FROM applicazioni_statistics_repository LIMIT 1").fetchone()
        for row in section_rows:
            row["default_params"] = _from_json(row.pop("default_params_json", "{}"), {})
            row["items"] = _from_json(row.pop("items_json", "[]"), [])
        for row in catalog_rows:
            row["params"] = _from_json(row.pop("params_json", "{}"), {})
            row["keywords"] = _from_json(row.pop("keywords_json", "[]"), [])
            row["capabilities"] = _from_json(row.pop("capabilities_json", "[]"), [])
            row["suggested_when"] = _from_json(row.pop("suggested_when_json", "[]"), [])
            row["blocked_if"] = _from_json(row.pop("blocked_if_json", "[]"), [])
            row["featured"] = bool(row.get("featured"))
            row["available"] = bool(row.get("available"))
            row["requires_guided_flow"] = bool(row.get("requires_guided_flow"))
            row["requires_login"] = bool(row.get("requires_login"))
            row["requires_cliente"] = bool(row.get("requires_cliente"))
            row["requires_fascicolo"] = bool(row.get("requires_fascicolo"))
            row["requires_telematic_context"] = bool(row.get("requires_telematic_context"))
        for row in featured_rows:
            row["params"] = _from_json(row.pop("params_json", "{}"), {})
            row["keywords"] = _from_json(row.pop("keywords_json", "[]"), [])
            row["featured_default_slug"] = bool(row.get("featured_default_slug"))
        statistics = dict(statistics_row) if statistics_row else {}
        if statistics:
            statistics["per_stato"] = _from_json(statistics.pop("per_stato_json", "{}"), {})
            statistics["per_sezione"] = _from_json(statistics.pop("per_sezione_json", "{}"), {})
            statistics["per_tipo"] = _from_json(statistics.pop("per_tipo_json", "{}"), {})
            statistics["per_modalita"] = _from_json(statistics.pop("per_modalita_json", "{}"), {})
        return {
            "counts": {
                "sections": len(section_rows),
                "catalog": len(catalog_rows),
                "statuses": len(status_rows),
                "access_modes": len(access_rows),
                "section_kinds": len(section_kind_rows),
                "featured": len(featured_rows),
                "statistics": 1 if statistics else 0,
            },
            "sections": section_rows,
            "catalog": catalog_rows,
            "statuses": status_rows,
            "access_modes": access_rows,
            "section_kinds": section_kind_rows,
            "featured": featured_rows,
            "statistics": statistics,
        }

    def export_repository_json(self, path: str | None = None) -> str:
        payload = self.load_repository_payload()
        output = {"repository": "applicazioni_repository", **payload}
        return self._write_json(path or self.json_path, output)

    def export_split_jsons(self, base_dir: str | None = None) -> dict[str, str]:
        payload = self.load_repository_payload()
        if base_dir:
            root = Path(base_dir)
            paths = {
                "repository": root / "applicazioni_repository.json",
                "sections": root / "applicazioni_sections_repository.json",
                "catalog": root / "applicazioni_catalog_repository.json",
                "statuses": root / "applicazioni_status_repository.json",
                "access_modes": root / "applicazioni_access_repository.json",
                "section_kinds": root / "applicazioni_section_kinds_repository.json",
                "featured": root / "applicazioni_featured_repository.json",
                "statistics": root / "applicazioni_statistics_repository.json",
            }
        else:
            paths = {
                "repository": Path(self.json_path),
                "sections": Path(self.sections_json_path),
                "catalog": Path(self.catalog_json_path),
                "statuses": Path(self.statuses_json_path),
                "access_modes": Path(self.access_json_path),
                "section_kinds": Path(self.section_kinds_json_path),
                "featured": Path(self.featured_json_path),
                "statistics": Path(self.statistics_json_path),
            }
        datasets = {
            "repository": payload,
            "sections": payload.get("sections") or [],
            "catalog": payload.get("catalog") or [],
            "statuses": payload.get("statuses") or [],
            "access_modes": payload.get("access_modes") or [],
            "section_kinds": payload.get("section_kinds") or [],
            "featured": payload.get("featured") or [],
            "statistics": payload.get("statistics") or {},
        }
        exported: dict[str, str] = {}
        for key, path in paths.items():
            value = datasets.get(key)
            row_count = len(value) if isinstance(value, list) else (1 if value else 0)
            rows = value if isinstance(value, list) else [value] if value else []
            exported[key] = self._write_json(str(path), {"repository": f"applicazioni_{key}", "count": row_count, "rows": rows})
        return exported

    def resolve_workspace_for_request(
        self,
        question: str,
        *,
        current_app_id: str = "",
        limit: int = 5,
    ) -> dict[str, Any]:
        payload = self.load_repository_payload()
        catalog_rows = list(payload.get("catalog") or [])
        featured_rows = list(payload.get("featured") or [])
        statistics = dict(payload.get("statistics") or {})
        terms = _query_terms(question)
        best_matches = _select_ranked(catalog_rows if catalog_rows else featured_rows, terms, limit=max(limit, 3))
        if not terms and featured_rows:
            featured_ids = {row.get("app_id") for row in featured_rows}
            best_matches = [row for row in catalog_rows if row.get("app_id") in featured_ids][: max(limit, 3)] or featured_rows[: max(limit, 3)]
        best_app = dict(best_matches[0]) if best_matches else {}
        if current_app_id:
            current = next((row for row in catalog_rows if row.get("app_id") == current_app_id), None)
            if current:
                best_app = dict(current)
        related_apps = []
        if best_app.get("app_id"):
            related_ids = {row.get("id") for row in applicazioni_correlate(best_app["app_id"], limit=max(limit, 6))}
            related_apps = [row for row in catalog_rows if row.get("app_id") in related_ids][:limit]
        if not related_apps and best_app.get("section_id"):
            related_apps = [
                row
                for row in catalog_rows
                if row.get("app_id") != best_app.get("app_id") and row.get("section_id") == best_app.get("section_id")
            ][:limit]
        section_rows = [
            row
            for row in (payload.get("sections") or [])
            if row.get("section_id") in {item.get("section_id") for item in best_matches[:limit] if item.get("section_id")}
        ]
        if best_app:
            if best_app.get("access_mode") == "diretta":
                access_reason = "accesso diretto disponibile"
            elif best_app.get("access_mode") == "guidata":
                access_reason = "richiede percorso guidato"
            else:
                access_reason = "si apre dalla scheda workspace"
            reason = (
                f"Lex instrada su {best_app.get('title')} per sezione {best_app.get('section_title') or 'modulo'}; "
                f"{access_reason}; stato {best_app.get('status_label') or best_app.get('status') or 'n.d.'}."
            )
        else:
            reason = "Lex usa il registro workspace per suggerire il modulo piu' coerente con la richiesta."
        if best_app.get("access_mode") == "diretta":
            next_action = f"{best_app.get('cta_label') or 'Apri modulo'} tramite endpoint {best_app.get('endpoint') or 'n.d.'}."
        elif best_app.get("access_mode") == "guidata":
            next_action = f"Apri il percorso guidato di {best_app.get('section_title') or 'questa area'} e poi scegli {best_app.get('title') or 'il modulo adatto'}."
        elif best_app:
            next_action = f"Apri la scheda workspace di {best_app.get('title') or 'questo modulo'} e valuta i moduli correlati."
        else:
            next_action = "Apri il catalogo applicazioni e usa il primo piano operativo."
        return {
            "route_scope": "workspace_registry",
            "question": _clean_spaces(question),
            "reason": reason,
            "next_action": next_action,
            "best_app": best_app or None,
            "candidate_apps": best_matches[:limit],
            "related_apps": related_apps[:limit],
            "featured_apps": featured_rows[:limit],
            "section_rows": section_rows,
            "statistics": statistics,
            "direct_endpoint": best_app.get("endpoint") if best_app else "",
            "direct_params": dict(best_app.get("params") or {}) if best_app else {},
            "requires_guided_flow": bool(best_app.get("requires_guided_flow")) if best_app else False,
        }


def get_runtime_applicazioni_repository(
    anchor_path: str | None = None,
    *,
    refresh: bool = False,
) -> GestioneApplicazioniRepository:
    db_path = default_applicazioni_repository_db_path(anchor_path)
    repository = _RUNTIME_REPOSITORIES.get(db_path)
    if repository is None:
        repository = GestioneApplicazioniRepository(
            db_path,
            json_path=derive_applicazioni_repository_json_path(db_path),
            sections_json_path=derive_applicazioni_sections_json_path(db_path),
            catalog_json_path=derive_applicazioni_catalog_json_path(db_path),
            statuses_json_path=derive_applicazioni_status_json_path(db_path),
            access_json_path=derive_applicazioni_access_json_path(db_path),
            section_kinds_json_path=derive_applicazioni_section_kinds_json_path(db_path),
            featured_json_path=derive_applicazioni_featured_json_path(db_path),
            statistics_json_path=derive_applicazioni_statistics_json_path(db_path),
        )
        _RUNTIME_REPOSITORIES[db_path] = repository
        refresh = True
    if refresh:
        repository.synchronize_runtime(export_json=True)
    return repository
