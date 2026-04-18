from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from pct.postgres_runtime_support import PostgresRepositoryBackend
SCHEMA_GIURISPRUDENZA_REPOSITORY = Path(__file__).with_name("sql") / "20260414_giurisprudenza_repository.sql"
POSTGRES_SCHEMA_GIURISPRUDENZA_REPOSITORY = Path(__file__).with_name("sql") / "20260418_giurisprudenza_repository_postgres.sql"

_RECENCY_MARKERS = (
    "oggi",
    "ultima",
    "ultime",
    "ultimo",
    "ultimi",
    "recent",
    "aggiorn",
    "nuov",
)

_PREFER_PDF_MARKERS = (
    "pdf",
    "scarica",
    "scaricare",
    "download",
    "apri",
    "aprila",
)

_PREFER_VERIFIED_MARKERS = (
    "citabile",
    "citare",
    "verificata",
    "verificato",
    "ufficiale",
    "numero",
    "ecli",
    "massima ufficiale",
)

_AREA_SOURCE_DEFAULTS = {
    "Civile": ["cassazione", "merito_civile_bdp"],
    "Penale": ["cassazione"],
    "Amministrativo": ["openga", "giustizia_amministrativa"],
    "Tribunario": ["giustizia_tributaria"],
    "Tributario": ["giustizia_tributaria"],
    "Costituzionale": ["corte_costituzionale"],
    "UE / CEDU": ["curia", "hudoc"],
    "Contabile": ["corte_conti"],
}

_DIRECT_SOURCE_HINTS = {
    "cassazione": ["cassazione"],
    "merito_civile_bdp": ["tribunale", "corte d'appello", "merito"],
    "corte_costituzionale": ["corte costituzionale", "costituzionale"],
    "openga": ["openga", "tar", "consiglio di stato", "cga"],
    "giustizia_amministrativa": ["giustizia amministrativa", "tar", "consiglio di stato", "cga"],
    "giustizia_tributaria": ["tributaria", "corte di giustizia tributaria", "riscossione"],
    "curia": ["curia", "cgue", "corte di giustizia ue", "ue"],
    "hudoc": ["hudoc", "cedu", "equo processo", "corte edu"],
    "corte_conti": ["corte dei conti", "erariale", "contabile"],
    "simpliciter_cliente": ["materiale cliente", "simpliciter", "cliente"],
    "manuale_interno": ["inserimento interno", "manuale interno"],
}


def _clean_spaces(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _normalize_text(value: Any) -> str:
    return _clean_spaces(value).lower()


def _slug(value: Any) -> str:
    text = _normalize_text(value)
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


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


def _route_bias(access_mode: str, sync_mode: str, supports_auto_sync: bool) -> str:
    access = _normalize_text(access_mode)
    sync = _normalize_text(sync_mode)
    if supports_auto_sync:
        return "corpus_e_sync_pubblico"
    if access in {"pubblico", "open_data", "portale_ufficiale"}:
        return "corpus_e_verifica_pubblica"
    if access in {"area_riservata_pst", "materiale_cliente"} or "assistito" in sync:
        return "corpus_e_handoff"
    return "corpus_professionale"


def _usage_rule_rows() -> list[dict[str, Any]]:
    rows = [
        {
            "policy_id": "regola:corpus_first_search",
            "policy_type": "regola_operativa",
            "policy_value": "corpus_first_search",
            "label": "Prima il corpus professionale",
            "operational_text": (
                "Lex deve partire dal corpus professionale verificabile e passare alle fonti esterne solo quando il corpus non basta."
            ),
            "sort_order": 100,
        },
        {
            "policy_id": "regola:cite_only_verified",
            "policy_type": "regola_operativa",
            "policy_value": "cite_only_verified",
            "label": "Cita solo riferimenti verificabili",
            "operational_text": (
                "Lex puo citare una sentenza solo quando il riferimento professionale e verificato dal corpus."
            ),
            "sort_order": 101,
        },
        {
            "policy_id": "regola:offer_pdf_only_real",
            "policy_type": "regola_operativa",
            "policy_value": "offer_pdf_only_real",
            "label": "Prometti PDF solo se esiste davvero",
            "operational_text": (
                "Lex puo offrire un PDF solo quando il corpus segnala un PDF ufficiale realmente disponibile."
            ),
            "sort_order": 102,
        },
        {
            "policy_id": "regola:explain_source_mode",
            "policy_type": "regola_operativa",
            "policy_value": "explain_source_mode",
            "label": "Spiega modalita della fonte",
            "operational_text": (
                "Lex deve distinguere tra fonte automatica pubblica, portale ufficiale con handoff e import assistito da materiale cliente."
            ),
            "sort_order": 103,
        },
    ]
    for row in rows:
        row["search_text"] = _build_search_text(
            row.get("policy_type"),
            row.get("policy_value"),
            row.get("label"),
            row.get("operational_text"),
        )
    return rows


def derive_giurisprudenza_repository_db_path(storage_path: str) -> str:
    target = Path(storage_path).resolve()
    return str(target.with_name("giurisprudenza_repository.db"))


def derive_giurisprudenza_repository_json_path(storage_path: str) -> str:
    target = Path(storage_path).resolve()
    return str(target.with_name("giurisprudenza_repository.json"))


def derive_giurisprudenza_sources_json_path(storage_path: str) -> str:
    target = Path(storage_path).resolve()
    return str(target.with_name("giurisprudenza_sources_repository.json"))


def derive_giurisprudenza_taxonomy_json_path(storage_path: str) -> str:
    target = Path(storage_path).resolve()
    return str(target.with_name("giurisprudenza_taxonomy_repository.json"))


def derive_giurisprudenza_usage_json_path(storage_path: str) -> str:
    target = Path(storage_path).resolve()
    return str(target.with_name("giurisprudenza_usage_policy.json"))


def derive_giurisprudenza_sync_json_path(storage_path: str) -> str:
    target = Path(storage_path).resolve()
    return str(target.with_name("giurisprudenza_sync_registry.json"))


def build_giurisprudenza_sources_rows(
    source_specs: list[Any],
    catalog_rows: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    catalog_index = {str(row.get("id") or ""): dict(row or {}) for row in (catalog_rows or []) if row.get("id")}
    rows: list[dict[str, Any]] = []
    for spec in source_specs or []:
        payload = spec.to_dict() if hasattr(spec, "to_dict") else dict(spec or {})
        source_id = _clean_spaces(payload.get("id"))
        catalog_row = catalog_index.get(source_id, {})
        last_run = dict(catalog_row.get("last_run") or {})
        link_keywords = [item for item in (_clean_spaces(x) for x in _as_list(payload.get("link_keywords"))) if item]
        row = {
            "source_id": source_id,
            "nome": _clean_spaces(payload.get("nome")),
            "giurisdizione": _clean_spaces(payload.get("giurisdizione")),
            "coverage": _clean_spaces(payload.get("coverage")),
            "official_url": _clean_spaces(payload.get("official_url")),
            "search_url": _clean_spaces(payload.get("search_url")),
            "access_mode": _clean_spaces(payload.get("access_mode")),
            "sync_mode": _clean_spaces(payload.get("sync_mode")),
            "badge": _clean_spaces(payload.get("badge")),
            "icon": _clean_spaces(payload.get("icon")),
            "search_label": _clean_spaces(payload.get("search_label")),
            "supports_auto_sync": bool(payload.get("supports_auto_sync")),
            "default_area": _clean_spaces(payload.get("default_area")),
            "default_grade": _clean_spaces(payload.get("default_grade")),
            "license_note": _clean_spaces(payload.get("license_note")),
            "route_bias": _route_bias(
                payload.get("access_mode"),
                payload.get("sync_mode"),
                bool(payload.get("supports_auto_sync")),
            ),
            "link_keywords": link_keywords,
            "judgment_count": int(catalog_row.get("judgment_count") or 0),
            "last_status": _clean_spaces(last_run.get("status")),
            "last_check": _clean_spaces(last_run.get("ended_at") or last_run.get("checked_at") or last_run.get("started_at")),
            "last_message": _clean_spaces(last_run.get("message")),
            "last_imported": int(last_run.get("items_imported") or last_run.get("imported") or 0),
            "last_updated": int(last_run.get("items_updated") or last_run.get("updated") or 0),
        }
        row["search_text"] = _build_search_text(
            row.get("source_id"),
            row.get("nome"),
            row.get("giurisdizione"),
            row.get("coverage"),
            row.get("access_mode"),
            row.get("sync_mode"),
            row.get("badge"),
            row.get("default_area"),
            row.get("default_grade"),
            row.get("license_note"),
            row.get("route_bias"),
            row.get("link_keywords"),
            row.get("last_status"),
            row.get("last_message"),
        )
        rows.append(row)
    rows.sort(key=lambda item: (item.get("giurisdizione") or "", item.get("nome") or ""))
    return rows


def build_giurisprudenza_taxonomy_rows(taxonomy: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    order = 0
    for area in taxonomy or []:
        order += 1
        area_id = _clean_spaces(area.get("id"))
        area_title = _clean_spaces(area.get("title"))
        area_description = _clean_spaces(area.get("description"))
        icon = _clean_spaces(area.get("icon"))
        rows.append(
            {
                "taxon_id": area_id,
                "level_name": "area",
                "area_id": area_id,
                "area_title": area_title,
                "branch_title": "",
                "subbranch_title": "",
                "title": area_title,
                "icon": icon,
                "description": area_description,
                "sort_order": order,
                "search_text": _build_search_text(area_id, area_title, area_description),
            }
        )
        for branch_index, branch in enumerate(area.get("branches") or [], start=1):
            branch_title = _clean_spaces(branch.get("title"))
            branch_id = f"{area_id}:{_slug(branch_title)}"
            rows.append(
                {
                    "taxon_id": branch_id,
                    "level_name": "branch",
                    "area_id": area_id,
                    "area_title": area_title,
                    "branch_title": branch_title,
                    "subbranch_title": "",
                    "title": branch_title,
                    "icon": icon,
                    "description": area_description,
                    "sort_order": order * 100 + branch_index,
                    "search_text": _build_search_text(area_id, area_title, branch_title, area_description),
                }
            )
            for sub_index, subbranch in enumerate(branch.get("subbranches") or [], start=1):
                sub_title = _clean_spaces(subbranch)
                rows.append(
                    {
                        "taxon_id": f"{branch_id}:{_slug(sub_title)}",
                        "level_name": "subbranch",
                        "area_id": area_id,
                        "area_title": area_title,
                        "branch_title": branch_title,
                        "subbranch_title": sub_title,
                        "title": sub_title,
                        "icon": icon,
                        "description": area_description,
                        "sort_order": order * 10000 + branch_index * 100 + sub_index,
                        "search_text": _build_search_text(area_id, area_title, branch_title, sub_title, area_description),
                    }
                )
    return rows


def build_giurisprudenza_usage_rows(
    orientamenti: list[str],
    rilevanze: list[str],
    usi: list[str],
    tipi_provvedimento: list[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, value in enumerate(orientamenti or [], start=1):
        rows.append(
            {
                "policy_id": f"orientamento:{_slug(value)}",
                "policy_type": "orientamento",
                "policy_value": _clean_spaces(value),
                "label": f"Orientamento {value}",
                "operational_text": "Classifica se il precedente e conforme, contrario, superato o ancora in formazione.",
                "sort_order": index,
            }
        )
    for index, value in enumerate(rilevanze or [], start=20):
        rows.append(
            {
                "policy_id": f"rilevanza:{_slug(value)}",
                "policy_type": "rilevanza_pratica",
                "policy_value": _clean_spaces(value),
                "label": f"Rilevanza pratica {value}",
                "operational_text": "Usa la rilevanza pratica per ordinare le pronunce da leggere o citare per prime.",
                "sort_order": index,
            }
        )
    for index, value in enumerate(usi or [], start=40):
        rows.append(
            {
                "policy_id": f"uso:{_slug(value)}",
                "policy_type": "uso_nel_software",
                "policy_value": _clean_spaces(value),
                "label": f"Uso nel software {value}",
                "operational_text": "Indica se la pronuncia e citabile in atto, precedente forte, precedente debole o solo studio.",
                "sort_order": index,
            }
        )
    for index, value in enumerate(tipi_provvedimento or [], start=60):
        rows.append(
            {
                "policy_id": f"provvedimento:{_slug(value)}",
                "policy_type": "tipo_provvedimento",
                "policy_value": _clean_spaces(value),
                "label": f"Tipo provvedimento {value}",
                "operational_text": "Chiarisci sempre se si tratta di sentenza, ordinanza, decreto, decisione, parere o massima.",
                "sort_order": index,
            }
        )
    rows.extend(_usage_rule_rows())
    for row in rows:
        row["search_text"] = _build_search_text(
            row.get("policy_type"),
            row.get("policy_value"),
            row.get("label"),
            row.get("operational_text"),
        )
    rows.sort(key=lambda item: (int(item.get("sort_order") or 0), item.get("label") or ""))
    return rows


def build_giurisprudenza_sync_rows(catalog_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for payload in catalog_rows or []:
        row = dict(payload or {})
        last_run = dict(row.get("last_run") or {})
        supports_auto_sync = bool(row.get("supports_auto_sync"))
        last_status = _clean_spaces(last_run.get("status") or ("mai_eseguito" if supports_auto_sync else "handoff_richiesto"))
        last_check = _clean_spaces(last_run.get("ended_at") or last_run.get("checked_at") or last_run.get("started_at"))
        last_message = _clean_spaces(
            last_run.get("message")
            or (
                "Fonte con recupero assistito o consultazione manuale dal portale ufficiale."
                if not supports_auto_sync
                else "Nessuna esecuzione registrata."
            )
        )
        handoff_required = (not supports_auto_sync) or last_status == "handoff_richiesto"
        item = {
            "source_id": _clean_spaces(row.get("id")),
            "source_name": _clean_spaces(row.get("nome") or row.get("name")),
            "giurisdizione": _clean_spaces(row.get("giurisdizione")),
            "access_mode": _clean_spaces(row.get("access_mode")),
            "sync_mode": _clean_spaces(row.get("sync_mode")),
            "supports_auto_sync": supports_auto_sync,
            "judgment_count": int(row.get("judgment_count") or 0),
            "last_status": last_status,
            "last_check": last_check,
            "last_message": last_message,
            "imported": int(last_run.get("items_imported") or last_run.get("imported") or 0),
            "updated": int(last_run.get("items_updated") or last_run.get("updated") or 0),
            "candidates": int(last_run.get("items_found") or last_run.get("candidates") or 0),
            "handoff_required": handoff_required,
        }
        item["search_text"] = _build_search_text(
            item.get("source_id"),
            item.get("source_name"),
            item.get("giurisdizione"),
            item.get("access_mode"),
            item.get("sync_mode"),
            item.get("last_status"),
            item.get("last_message"),
        )
        rows.append(item)
    rows.sort(key=lambda item: (item.get("last_check") or "", item.get("source_name") or ""), reverse=True)
    return rows


class GestioneRepositoryGiurisprudenza:
    def __init__(
        self,
        db_path: str,
        *,
        json_path: str = "",
        sources_json_path: str = "",
        taxonomy_json_path: str = "",
        usage_json_path: str = "",
        sync_json_path: str = "",
        postgres_dsn: str = "",
        postgres_schema_path: Path | None = None,
    ) -> None:
        self.db_path = str(db_path or "").strip()
        self.json_path = str(json_path or "").strip()
        self.sources_json_path = str(sources_json_path or "").strip()
        self.taxonomy_json_path = str(taxonomy_json_path or "").strip()
        self.usage_json_path = str(usage_json_path or "").strip()
        self.sync_json_path = str(sync_json_path or "").strip()
        self.postgres_dsn = str(postgres_dsn or "").strip()
        self.postgres_schema_path = Path(postgres_schema_path or POSTGRES_SCHEMA_GIURISPRUDENZA_REPOSITORY)
        self.backend_kind = "postgresql" if self.postgres_dsn else "sqlite"
        self._postgres_backend = (
            PostgresRepositoryBackend(self.postgres_dsn, self.postgres_schema_path)
            if self.postgres_dsn
            else None
        )
        self._ensure_schema()

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
            else SCHEMA_GIURISPRUDENZA_REPOSITORY.read_text(encoding="utf-8")
        )
        with self._connect() as conn:
            conn.executescript(schema)
            conn.commit()

    def _get_meta(self, key: str) -> str:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT meta_value FROM giurisprudenza_repository_meta WHERE meta_key = ?",
                (key,),
            ).fetchone()
        return str(row["meta_value"]) if row else ""

    def _set_meta(self, conn: sqlite3.Connection, key: str, value: Any) -> None:
        conn.execute(
            """
            INSERT INTO giurisprudenza_repository_meta (meta_key, meta_value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(meta_key) DO UPDATE SET
                meta_value = excluded.meta_value,
                updated_at = CURRENT_TIMESTAMP
            """,
            (key, _clean_spaces(value)),
        )

    def storage_stats(self) -> dict[str, Any]:
        tables = (
            "giurisprudenza_sources_repository",
            "giurisprudenza_taxonomy_repository",
            "giurisprudenza_usage_policy_repository",
            "giurisprudenza_sync_registry",
        )
        stats: dict[str, Any] = {
            "db_path": self.db_path,
            "json_path": self.json_path,
            "sources_json_path": self.sources_json_path,
            "taxonomy_json_path": self.taxonomy_json_path,
            "usage_json_path": self.usage_json_path,
            "sync_json_path": self.sync_json_path,
            "backend_kind": self.backend_kind,
        }
        with self._connect() as conn:
            for table_name in tables:
                stats[table_name] = int(conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])
            runtime_row = conn.execute("SELECT COUNT(*) FROM giurisprudenza_runtime_state").fetchone()
        stats["giurisprudenza_runtime_state"] = int((runtime_row or [0])[0] or 0)
        stats["source_signature"] = self._get_meta("source_signature")
        return stats

    def load_runtime_state(self) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT state_json FROM giurisprudenza_runtime_state WHERE state_id = ?",
                ("runtime",),
            ).fetchone()
        if not row:
            return {}
        try:
            return dict(json.loads(row["state_json"] or "{}"))
        except Exception:
            return {}

    def save_runtime_state(self, payload: dict[str, Any]) -> None:
        encoded = json.dumps(dict(payload or {}), ensure_ascii=False)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO giurisprudenza_runtime_state (state_id, state_json, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(state_id) DO UPDATE SET
                    state_json = excluded.state_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                ("runtime", encoded),
            )
            conn.commit()

    def synchronize_runtime(
        self,
        *,
        source_rows: list[dict[str, Any]],
        taxonomy_rows: list[dict[str, Any]],
        usage_rows: list[dict[str, Any]],
        sync_rows: list[dict[str, Any]],
        export_json: bool = True,
    ) -> dict[str, Any]:
        payload = {
            "sources": source_rows,
            "taxonomy": taxonomy_rows,
            "usage_policy": usage_rows,
            "sync_registry": sync_rows,
        }
        signature = _payload_signature(payload)
        if signature != self._get_meta("source_signature"):
            self.rebuild_from_payload(payload, source_label="giurisprudenza_runtime")
        if export_json:
            self.export_repository_json()
            self.export_split_jsons()
        return self.storage_stats()

    def rebuild_from_payload(self, payload: dict[str, Any], *, source_label: str = "giurisprudenza_runtime") -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM giurisprudenza_sources_repository")
            conn.execute("DELETE FROM giurisprudenza_taxonomy_repository")
            conn.execute("DELETE FROM giurisprudenza_usage_policy_repository")
            conn.execute("DELETE FROM giurisprudenza_sync_registry")

            for row in payload.get("sources") or []:
                conn.execute(
                    """
                    INSERT INTO giurisprudenza_sources_repository (
                        source_id, nome, giurisdizione, coverage, official_url, search_url,
                        access_mode, sync_mode, badge, icon, search_label, supports_auto_sync,
                        default_area, default_grade, license_note, route_bias, link_keywords_json,
                        judgment_count, last_status, last_check, last_message, last_imported, last_updated, search_text
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row.get("source_id"),
                        row.get("nome"),
                        row.get("giurisdizione") or "",
                        row.get("coverage") or "",
                        row.get("official_url") or "",
                        row.get("search_url") or "",
                        row.get("access_mode") or "",
                        row.get("sync_mode") or "",
                        row.get("badge") or "",
                        row.get("icon") or "",
                        row.get("search_label") or "",
                        1 if row.get("supports_auto_sync") else 0,
                        row.get("default_area") or "",
                        row.get("default_grade") or "",
                        row.get("license_note") or "",
                        row.get("route_bias") or "",
                        _to_json(row.get("link_keywords") or []),
                        int(row.get("judgment_count") or 0),
                        row.get("last_status") or "",
                        row.get("last_check") or "",
                        row.get("last_message") or "",
                        int(row.get("last_imported") or 0),
                        int(row.get("last_updated") or 0),
                        row.get("search_text") or "",
                    ),
                )

            for row in payload.get("taxonomy") or []:
                conn.execute(
                    """
                    INSERT INTO giurisprudenza_taxonomy_repository (
                        taxon_id, level_name, area_id, area_title, branch_title, subbranch_title,
                        title, icon, description, sort_order, search_text
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row.get("taxon_id"),
                        row.get("level_name"),
                        row.get("area_id") or "",
                        row.get("area_title") or "",
                        row.get("branch_title") or "",
                        row.get("subbranch_title") or "",
                        row.get("title") or "",
                        row.get("icon") or "",
                        row.get("description") or "",
                        int(row.get("sort_order") or 0),
                        row.get("search_text") or "",
                    ),
                )

            for row in payload.get("usage_policy") or []:
                conn.execute(
                    """
                    INSERT INTO giurisprudenza_usage_policy_repository (
                        policy_id, policy_type, policy_value, label, operational_text, sort_order, search_text
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row.get("policy_id"),
                        row.get("policy_type"),
                        row.get("policy_value"),
                        row.get("label"),
                        row.get("operational_text") or "",
                        int(row.get("sort_order") or 0),
                        row.get("search_text") or "",
                    ),
                )

            for row in payload.get("sync_registry") or []:
                conn.execute(
                    """
                    INSERT INTO giurisprudenza_sync_registry (
                        source_id, source_name, giurisdizione, access_mode, sync_mode,
                        supports_auto_sync, judgment_count, last_status, last_check, last_message,
                        imported, updated, candidates, handoff_required, search_text
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row.get("source_id"),
                        row.get("source_name"),
                        row.get("giurisdizione") or "",
                        row.get("access_mode") or "",
                        row.get("sync_mode") or "",
                        1 if row.get("supports_auto_sync") else 0,
                        int(row.get("judgment_count") or 0),
                        row.get("last_status") or "",
                        row.get("last_check") or "",
                        row.get("last_message") or "",
                        int(row.get("imported") or 0),
                        int(row.get("updated") or 0),
                        int(row.get("candidates") or 0),
                        1 if row.get("handoff_required") else 0,
                        row.get("search_text") or "",
                    ),
                )

            self._set_meta(conn, "source_label", source_label)
            self._set_meta(conn, "source_signature", _payload_signature(payload))
            conn.commit()

    def load_repository_payload(self) -> dict[str, Any]:
        with self._connect() as conn:
            source_rows = []
            for row in conn.execute(
                "SELECT * FROM giurisprudenza_sources_repository ORDER BY giurisdizione, nome"
            ).fetchall():
                payload = dict(row)
                payload["supports_auto_sync"] = bool(payload.get("supports_auto_sync"))
                payload["link_keywords"] = json.loads(payload.pop("link_keywords_json", "[]") or "[]")
                source_rows.append(payload)

            taxonomy_rows = [dict(row) for row in conn.execute(
                "SELECT * FROM giurisprudenza_taxonomy_repository ORDER BY sort_order, title"
            ).fetchall()]

            usage_rows = [dict(row) for row in conn.execute(
                "SELECT * FROM giurisprudenza_usage_policy_repository ORDER BY sort_order, label"
            ).fetchall()]

            sync_rows = []
            for row in conn.execute(
                "SELECT * FROM giurisprudenza_sync_registry ORDER BY last_check DESC, source_name"
            ).fetchall():
                payload = dict(row)
                payload["supports_auto_sync"] = bool(payload.get("supports_auto_sync"))
                payload["handoff_required"] = bool(payload.get("handoff_required"))
                sync_rows.append(payload)

        return {
            "counts": {
                "sources": len(source_rows),
                "taxonomy": len(taxonomy_rows),
                "usage_policy": len(usage_rows),
                "sync_registry": len(sync_rows),
            },
            "sources": source_rows,
            "taxonomy": taxonomy_rows,
            "usage_policy": usage_rows,
            "sync_registry": sync_rows,
        }

    def export_repository_json(self) -> str:
        if not self.json_path:
            return ""
        payload = self.load_repository_payload()
        target = Path(self.json_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(target)

    def export_split_jsons(self, base_dir: str | None = None) -> dict[str, str]:
        payload = self.load_repository_payload()
        if base_dir:
            base = Path(base_dir)
            paths = {
                "repository": str(base / "giurisprudenza_repository.json"),
                "sources": str(base / "giurisprudenza_sources_repository.json"),
                "taxonomy": str(base / "giurisprudenza_taxonomy_repository.json"),
                "usage_policy": str(base / "giurisprudenza_usage_policy.json"),
                "sync_registry": str(base / "giurisprudenza_sync_registry.json"),
            }
        else:
            paths = {
                "repository": self.json_path,
                "sources": self.sources_json_path,
                "taxonomy": self.taxonomy_json_path,
                "usage_policy": self.usage_json_path,
                "sync_registry": self.sync_json_path,
            }
        for path in paths.values():
            if path:
                Path(path).parent.mkdir(parents=True, exist_ok=True)
        if paths["repository"]:
            Path(paths["repository"]).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        if paths["sources"]:
            Path(paths["sources"]).write_text(
                json.dumps(
                    {"repository": "giurisprudenza_sources_repository", "count": len(payload["sources"]), "rows": payload["sources"]},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        if paths["taxonomy"]:
            Path(paths["taxonomy"]).write_text(
                json.dumps(
                    {"repository": "giurisprudenza_taxonomy_repository", "count": len(payload["taxonomy"]), "rows": payload["taxonomy"]},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        if paths["usage_policy"]:
            Path(paths["usage_policy"]).write_text(
                json.dumps(
                    {"repository": "giurisprudenza_usage_policy", "count": len(payload["usage_policy"]), "rows": payload["usage_policy"]},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        if paths["sync_registry"]:
            Path(paths["sync_registry"]).write_text(
                json.dumps(
                    {"repository": "giurisprudenza_sync_registry", "count": len(payload["sync_registry"]), "rows": payload["sync_registry"]},
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
        limit_sources: int = 4,
        limit_taxonomy: int = 6,
        limit_usage: int = 6,
    ) -> dict[str, Any]:
        payload = self.load_repository_payload()
        normalized_question = _normalize_text(question)
        terms = _query_terms(question)

        scored_sources: list[tuple[int, dict[str, Any]]] = []
        direct_source_hits: list[str] = []
        for row in payload.get("sources") or []:
            score = 0
            search_text = _normalize_text(row.get("search_text"))
            for marker in _DIRECT_SOURCE_HINTS.get(row.get("source_id") or "", []):
                if marker and marker in normalized_question:
                    score += 6
                    direct_source_hits.append(marker)
            for keyword in row.get("link_keywords") or []:
                normalized_keyword = _normalize_text(keyword)
                if normalized_keyword and normalized_keyword in normalized_question:
                    score += 4
            score += sum(1 for term in terms if term in search_text)
            if score > 0:
                scored_sources.append((score, row))
        scored_sources.sort(
            key=lambda item: (item[0], item[1].get("supports_auto_sync"), item[1].get("judgment_count", 0)),
            reverse=True,
        )

        scored_taxonomy: list[tuple[int, dict[str, Any]]] = []
        for row in payload.get("taxonomy") or []:
            search_text = _normalize_text(row.get("search_text"))
            score = sum(1 for term in terms if term in search_text)
            normalized_title = _normalize_text(row.get("title"))
            if normalized_title and normalized_title in normalized_question:
                score += 5
            if score > 0:
                scored_taxonomy.append((score, row))
        scored_taxonomy.sort(key=lambda item: (item[0], -int(item[1].get("sort_order") or 0)), reverse=True)

        selected_taxonomy = [row for _score, row in scored_taxonomy[:limit_taxonomy]]
        area_row = next((row for row in selected_taxonomy if row.get("level_name") == "area"), None)
        branch_row = next((row for row in selected_taxonomy if row.get("level_name") == "branch"), None)
        subbranch_row = next((row for row in selected_taxonomy if row.get("level_name") == "subbranch"), None)
        preferred_area_title = _clean_spaces((subbranch_row or branch_row or area_row or {}).get("area_title") or (area_row or {}).get("title"))
        preferred_branch_title = _clean_spaces((subbranch_row or branch_row or {}).get("branch_title") or (branch_row or {}).get("title"))
        preferred_subbranch_title = _clean_spaces((subbranch_row or {}).get("subbranch_title") or (subbranch_row or {}).get("title"))

        source_index = {row.get("source_id"): row for row in payload.get("sources") or []}
        source_ids: list[str] = []
        for _score, row in scored_sources:
            source_id = row.get("source_id")
            if source_id and source_id not in source_ids:
                source_ids.append(source_id)
            if len(source_ids) >= limit_sources:
                break
        if not source_ids and preferred_area_title:
            for source_id in _AREA_SOURCE_DEFAULTS.get(preferred_area_title, []):
                if source_id in source_index and source_id not in source_ids:
                    source_ids.append(source_id)
        if not source_ids:
            source_ids = ["cassazione", "merito_civile_bdp"]

        selected_sources = [source_index[source_id] for source_id in source_ids if source_id in source_index][:limit_sources]
        sync_index = {row.get("source_id"): row for row in payload.get("sync_registry") or []}
        selected_sync_rows = [sync_index[source_id] for source_id in source_ids if source_id in sync_index][:limit_sources]

        prefer_pdf = any(marker in normalized_question for marker in _PREFER_PDF_MARKERS)
        prefer_verified_only = prefer_pdf or any(marker in normalized_question for marker in _PREFER_VERIFIED_MARKERS)
        needs_live_sync = any(marker in normalized_question for marker in _RECENCY_MARKERS) and any(
            bool(row.get("supports_auto_sync")) for row in selected_sources
        )

        route_mode = "corpus_professionale"
        if needs_live_sync:
            route_mode = "corpus_e_sync_pubblico"
        elif any(bool(row.get("handoff_required")) for row in selected_sync_rows):
            route_mode = "corpus_e_handoff"
        elif any((row.get("route_bias") or "") == "corpus_e_verifica_pubblica" for row in selected_sources):
            route_mode = "corpus_e_verifica_pubblica"

        relevant_usage: list[dict[str, Any]] = []
        for row in payload.get("usage_policy") or []:
            search_text = _normalize_text(row.get("search_text"))
            if row.get("policy_type") == "regola_operativa":
                if row.get("policy_value") in {"corpus_first_search", "cite_only_verified"}:
                    relevant_usage.append(row)
                    continue
                if prefer_pdf and row.get("policy_value") == "offer_pdf_only_real":
                    relevant_usage.append(row)
                    continue
                if route_mode == "corpus_e_handoff" and row.get("policy_value") == "explain_source_mode":
                    relevant_usage.append(row)
                    continue
            elif any(term in search_text for term in terms):
                relevant_usage.append(row)
            if len(relevant_usage) >= limit_usage:
                break

        reason_parts: list[str] = ["corpus professionale come primo livello"]
        if preferred_area_title:
            reason_parts.append(f"area: {preferred_area_title}")
        if preferred_branch_title:
            reason_parts.append(f"branca: {preferred_branch_title}")
        if preferred_subbranch_title:
            reason_parts.append(f"sottobranca: {preferred_subbranch_title}")
        if direct_source_hits:
            reason_parts.append("fonti da keyword: " + ", ".join(dict.fromkeys(direct_source_hits)))
        if route_mode == "corpus_e_handoff":
            reason_parts.append("serve handoff su fonte assistita o area riservata")
        elif route_mode == "corpus_e_sync_pubblico":
            reason_parts.append("richiesta recente con fonte pubblica monitorabile")

        return {
            "question": _clean_spaces(question),
            "normalized_question": normalized_question,
            "preferred_area_title": preferred_area_title,
            "preferred_branch_title": preferred_branch_title,
            "preferred_subbranch_title": preferred_subbranch_title,
            "route_mode": route_mode,
            "needs_live_sync": needs_live_sync,
            "prefer_pdf": prefer_pdf,
            "prefer_verified_only": prefer_verified_only,
            "source_ids": source_ids,
            "source_rows": selected_sources,
            "taxonomy_rows": selected_taxonomy,
            "usage_rows": relevant_usage[:limit_usage],
            "sync_rows": selected_sync_rows,
            "reason": "; ".join(part for part in reason_parts if part),
        }


__all__ = [
    "GestioneRepositoryGiurisprudenza",
    "SCHEMA_GIURISPRUDENZA_REPOSITORY",
    "build_giurisprudenza_sources_rows",
    "build_giurisprudenza_taxonomy_rows",
    "build_giurisprudenza_usage_rows",
    "build_giurisprudenza_sync_rows",
    "derive_giurisprudenza_repository_db_path",
    "derive_giurisprudenza_repository_json_path",
    "derive_giurisprudenza_sources_json_path",
    "derive_giurisprudenza_taxonomy_json_path",
    "derive_giurisprudenza_usage_json_path",
    "derive_giurisprudenza_sync_json_path",
]
