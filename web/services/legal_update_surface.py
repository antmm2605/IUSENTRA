from __future__ import annotations

import json
import os
import shutil
import sqlite3
from pathlib import Path
from typing import Any

from flask import current_app, g, has_app_context, has_request_context, request

from pct.legal_update_batch_runner import (
    LegalUpdateJobConfig,
    run_legal_update_batch_with_timeouts,
    run_legal_update_publish_queue_with_timeouts,
)
from pct.legal_update_pipeline import DEFAULT_SOURCE_ROWS, LegalUpdatePipeline, build_legal_update_pipeline
from pct.legal_update_repository import LegalUpdateDbConfig
from pct.tenant import GestioneTenant, normalize_db_mode

try:
    from lex.retrieval.official_sources_retriever import official_archive_snapshot
except Exception:  # pragma: no cover - archivi ufficiali opzionali in ambienti minimi
    official_archive_snapshot = None


def _runtime_app_and_config(app: Any | None = None) -> tuple[Any | None, dict[str, Any]]:
    runtime_app = app
    if runtime_app is None and has_app_context():
        runtime_app = current_app._get_current_object()
    cfg_source = getattr(runtime_app, "config", {}) if runtime_app is not None else {}
    return runtime_app, dict(cfg_source)


def _resolve_requested_tenant_slug(explicit_tenant_slug: str = "") -> str:
    if str(explicit_tenant_slug or "").strip():
        return str(explicit_tenant_slug).strip().lower()
    if has_request_context():
        for source in (
            request.values.get("tenant_slug"),
            request.args.get("tenant_slug"),
        ):
            slug = str(source or "").strip().lower()
            if slug:
                return slug
        tenant = getattr(g, "tenant", None)
        tenant_slug = str(getattr(tenant, "slug", "") or "").strip().lower()
        if tenant_slug:
            return tenant_slug
    return ""


def _tenant_manager(cfg_source: dict[str, Any]) -> GestioneTenant | None:
    registry_path = str(cfg_source.get("TENANTS_REGISTRY") or "").strip()
    if not registry_path:
        return None
    try:
        return GestioneTenant(registry_path=registry_path)
    except Exception:
        return None


def _active_tenants(cfg_source: dict[str, Any], manager: GestioneTenant | None = None) -> list[Any]:
    tenants = manager or _tenant_manager(cfg_source)
    if tenants is None:
        return []
    active_states = {"ATTIVO", "TRIAL"}
    return [
        studio
        for studio in tenants.lista()
        if str(getattr(studio, "stato", "") or "").upper() in active_states
    ]


def _resolve_runtime_tenant(
    cfg_source: dict[str, Any],
    *,
    explicit_tenant_slug: str = "",
) -> Any | None:
    manager = _tenant_manager(cfg_source)
    active_tenants = _active_tenants(cfg_source, manager=manager)
    requested_slug = _resolve_requested_tenant_slug(explicit_tenant_slug)
    if requested_slug:
        if manager is not None:
            return manager.get(requested_slug)
        return None

    tenant = getattr(g, "tenant", None) if has_request_context() else None
    if tenant is not None:
        return tenant

    if len(active_tenants) == 1:
        return active_tenants[0]
    if active_tenants:
        # In console piattaforma evitiamo il repository globale legacy:
        # se non e' stato scelto uno studio, usiamo comunque il primo tenant attivo.
        return active_tenants[0]
    return None


def _load_tenant_studio_payload(manager: GestioneTenant | None, studio: Any = None) -> dict[str, Any]:
    if manager is None or studio is None:
        return {}
    slug = str(getattr(studio, "slug", "") or "").strip().lower()
    if not slug:
        return {}
    try:
        config_path = Path(manager.percorsi_dati(slug).get("CONFIG_STUDIO_DB") or "")
    except Exception:
        return {}
    if not config_path.is_file():
        return {}
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_single_studio_payload(cfg_source: dict[str, Any]) -> dict[str, Any]:
    config_path = Path(str(cfg_source.get("STUDIO_CONFIG") or "").strip())
    if not config_path.is_file():
        return {}
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _tenant_name_bundle(manager: GestioneTenant | None, studio: Any = None) -> dict[str, Any]:
    payload = _load_tenant_studio_payload(manager, studio)
    registry_name = str(getattr(studio, "nome", "") or "").strip()
    configured_name = str(((payload.get("studio") or {}).get("nome")) or "").strip()
    mismatch = bool(
        registry_name
        and configured_name
        and registry_name.casefold() != configured_name.casefold()
    )
    display_name = registry_name or configured_name
    return {
        "registry_name": registry_name,
        "configured_name": configured_name,
        "display_name": display_name,
        "mismatch": mismatch,
    }


def _display_single_studio_name(cfg_source: dict[str, Any]) -> str:
    payload = _load_single_studio_payload(cfg_source)
    return str(((payload.get("studio") or {}).get("nome")) or "").strip()


def _backend_label(cfg_source: dict[str, Any], studio: Any = None) -> str:
    tenant_database = getattr(studio, "database", None)
    effective_kind = str(getattr(tenant_database, "effective_runtime_kind", "") or "").strip().lower()
    if effective_kind == "postgresql":
        return "PostgreSQL tenant-aware"
    if effective_kind == "sqlite":
        return "SQL locale tenant-aware"
    if effective_kind == "json":
        return "JSON locale tenant-aware"

    normalized_mode = str(
        getattr(tenant_database, "normalized_mode", "")
        or normalize_db_mode(getattr(tenant_database, "mode", ""))
    ).strip().upper()
    if normalized_mode == "POSTGRESQL":
        return "PostgreSQL tenant-aware"
    if normalized_mode == "SQLITE":
        return "SQL locale tenant-aware"
    if normalized_mode == "JSON":
        return "JSON locale tenant-aware"
    if not studio:
        return "Archivio locale applicativo"
    return normalized_mode or "n.d."


def _flag_enabled(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "si"}


def _parse_positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(str(value or "").strip())
        return parsed if parsed > 0 else default
    except (TypeError, ValueError):
        return default


def _legal_update_job_config(cfg_source: dict[str, Any]) -> LegalUpdateJobConfig:
    return LegalUpdateJobConfig(
        intelligence_db=str(cfg_source.get("LEGAL_INTELLIGENCE_DB") or "./intelligence/motori.json"),
        giurisprudenza_db=str(cfg_source.get("GIURISPRUDENZA_DB") or ""),
        ai_base_url=str(
            cfg_source.get("LOCAL_AI_BASE_URL")
            or cfg_source.get("PCT_LOCAL_AI_BASE_URL")
            or ""
        ).strip(),
        ai_model=str(
            cfg_source.get("LOCAL_AI_CHAT_MODEL")
            or cfg_source.get("OLLAMA_MODEL")
            or "mistral"
        ).strip(),
        export_json_enabled=_flag_enabled(cfg_source.get("LEGAL_UPDATES_EXPORT_JSON_ENABLED")),
        mirror_giurisprudenza_json_enabled=_flag_enabled(
            cfg_source.get("LEGAL_UPDATES_MIRROR_GIURISPRUDENZA_JSON_ENABLED")
        ),
    )


def _legal_updates_item_timeout(cfg_source: dict[str, Any]) -> int:
    default = _parse_positive_int(os.getenv("IUSENTRA_LEGAL_UPDATES_ITEM_TIMEOUT_SECONDS"), 180)
    return _parse_positive_int(
        cfg_source.get("LEGAL_UPDATES_ITEM_TIMEOUT_SECONDS")
        or cfg_source.get("IUSENTRA_LEGAL_UPDATES_ITEM_TIMEOUT_SECONDS"),
        default,
    )


def _legal_updates_publish_max_items(cfg_source: dict[str, Any]) -> int:
    default = _parse_positive_int(os.getenv("IUSENTRA_LEGAL_UPDATES_PUBLISH_MAX_ITEMS"), 80)
    return _parse_positive_int(
        cfg_source.get("LEGAL_UPDATES_PUBLISH_MAX_ITEMS")
        or cfg_source.get("IUSENTRA_LEGAL_UPDATES_PUBLISH_MAX_ITEMS"),
        default,
    )


def _tenant_choices_payload(cfg_source: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    manager = _tenant_manager(cfg_source)
    for studio in _active_tenants(cfg_source, manager=manager):
        name_bundle = _tenant_name_bundle(manager, studio)
        rows.append(
            {
                "slug": str(getattr(studio, "slug", "") or ""),
                "nome": name_bundle["registry_name"] or name_bundle["display_name"],
                "configured_name": name_bundle["configured_name"],
                "name_mismatch": name_bundle["mismatch"],
                "db_mode": _backend_label(cfg_source, studio),
            }
        )
    return rows


def _repository_data_count(db_path: str) -> int:
    target = Path(str(db_path or "").strip())
    if not target.exists():
        return 0
    try:
        with sqlite3.connect(str(target)) as conn:
            total = 0
            for table in (
                "source_documents_raw",
                "ai_documents_analysis",
                "review_queue",
                "normative",
                "jurisprudence",
                "prassi",
                "news",
            ):
                try:
                    row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
                except sqlite3.Error:
                    continue
                total += int((row or [0])[0] or 0)
            return total
    except sqlite3.Error:
        return 0


def _official_archives_payload() -> dict[str, Any]:
    if official_archive_snapshot is None:
        return {
            "normattiva": {"available": False, "documents": 0, "articles": 0, "chunks": 0},
            "gazzetta": {"available": False, "documents": 0, "chunks": 0, "sources": 0},
        }
    try:
        return dict(official_archive_snapshot())
    except Exception:
        return {
            "normattiva": {"available": False, "documents": 0, "articles": 0, "chunks": 0},
            "gazzetta": {"available": False, "documents": 0, "chunks": 0, "sources": 0},
        }


SOURCE_FAMILY_ORDER: tuple[tuple[str, str, str], ...] = (
    ("normativa", "Normativa nazionale", "Leggi, decreti, testi vigenti e pubblicazioni ufficiali."),
    ("giurisprudenza", "Giurisprudenza", "Corti nazionali, amministrative, previdenziali e giustizia UE."),
    ("prassi", "Prassi e autorita'", "Circolari, interpelli, provvedimenti e presidi istituzionali."),
    ("telematico", "Processo telematico", "Schemi, specifiche e download ufficiali dei portali giustizia."),
    ("osservazione", "Fonti in osservazione", "Canali utili non ancora inseriti nel ciclo automatico."),
)


SOURCE_FAMILY_HINTS: dict[str, str] = {
    "gazzetta_ufficiale": "normativa",
    "normattiva": "normativa",
    "dati_normattiva": "normativa",
    "corte_costituzionale": "giurisprudenza",
    "cassazione_massimario": "giurisprudenza",
    "giustizia_amministrativa": "giurisprudenza",
    "eur_lex": "normativa",
    "curia_cgue_rss": "giurisprudenza",
    "inps_sentenze": "giurisprudenza",
    "pst_giustizia_download": "telematico",
}


SOURCE_CODES_ADDED_BY_CATALOG: tuple[str, ...] = (
    "inps_circolari",
    "inps_messaggi",
    "inps_sentenze",
    "curia_cgue_rss",
    "istat_prezzi",
    "mimit_incentivi",
    "agcm_bollettino",
    "agcom_provvedimenti",
    "banca_italia_normativa",
    "inail_istruzioni_operative",
)


def _source_family_key(source: dict[str, Any]) -> str:
    code = str(source.get("code") or "").strip().lower()
    if not bool(source.get("enabled", True)):
        return "osservazione"
    if code.startswith("openga_") or code == "giustizia_amministrativa":
        return "giurisprudenza"
    if code in SOURCE_FAMILY_HINTS:
        return SOURCE_FAMILY_HINTS[code]
    category = str(source.get("category") or "").strip().lower()
    if category in {"normativa", "ue"}:
        return "normativa"
    if category == "giurisprudenza":
        return "giurisprudenza"
    if category == "telematico":
        return "telematico"
    return "prassi"


def _source_method_label(source: dict[str, Any]) -> str:
    parser_type = str(source.get("parser_type") or "").strip().lower()
    source_type = str(source.get("source_type") or "").strip().lower()
    code = str(source.get("code") or "").strip().lower()
    if parser_type in {"ckan_json"} or source_type == "open_data" or code.startswith("openga_"):
        return "Catalogo open data"
    if parser_type in {"feed", "rss", "atom"} or source_type == "rss":
        return "Feed ufficiale"
    if code in {"normattiva", "dati_normattiva"}:
        return "Archivio e catalogo"
    return "Pagina ufficiale"


def _source_interval_label(minutes: Any) -> str:
    try:
        value = int(minutes or 0)
    except (TypeError, ValueError):
        value = 0
    if value <= 0:
        return "giornaliera"
    if value < 60:
        return f"ogni {value} min"
    if value % 1440 == 0:
        days = max(1, value // 1440)
        return "giornaliera" if days == 1 else f"ogni {days} giorni"
    if value % 60 == 0:
        hours = max(1, value // 60)
        return f"ogni {hours} ore"
    return f"ogni {value} min"


def _source_status_label(source: dict[str, Any]) -> str:
    if not bool(source.get("enabled", True)):
        return "In osservazione"
    if bool(source.get("is_official")):
        return "Attiva e ufficiale"
    return "Attiva"


def _int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _catalog_source_payload(source: dict[str, Any], activity: dict[str, Any]) -> dict[str, Any]:
    row = dict(source)
    row["family_key"] = _source_family_key(row)
    row["method_label"] = _source_method_label(row)
    row["interval_label"] = _source_interval_label(row.get("polling_minutes"))
    row["status_label"] = _source_status_label(row)
    row["raw_documents"] = _int_value(activity.get("raw_documents"))
    row["normalized_documents"] = _int_value(activity.get("normalized_documents"))
    row["analyses"] = _int_value(activity.get("analyses"))
    row["review_pending"] = _int_value(activity.get("review_pending"))
    row["review_published"] = _int_value(activity.get("review_published"))
    row["last_document_at"] = str(activity.get("last_document_at") or "")
    row["latest_source_date"] = str(activity.get("latest_source_date") or "")
    row["was_added_by_catalog"] = str(row.get("code") or "") in SOURCE_CODES_ADDED_BY_CATALOG
    return row


def build_legal_source_catalog(
    pipeline: LegalUpdatePipeline | None = None,
    app: Any | None = None,
) -> dict[str, Any]:
    runtime_app, cfg_source = _runtime_app_and_config(app)
    runtime_pipeline = pipeline or build_legal_update_pipeline_runtime(runtime_app)
    sources = runtime_pipeline.repository.list_sources(enabled_only=False)
    activity = runtime_pipeline.repository.source_activity_summary()
    default_codes = {str(row.get("code") or "") for row in DEFAULT_SOURCE_ROWS}
    official_archives = _official_archives_payload()
    source_rows = [
        _catalog_source_payload(source, activity.get(str(source.get("code") or ""), {}))
        for source in sources
    ]
    families: list[dict[str, Any]] = []
    for key, label, description in SOURCE_FAMILY_ORDER:
        rows = [row for row in source_rows if row.get("family_key") == key]
        if not rows and key != "osservazione":
            continue
        active = [row for row in rows if row.get("enabled")]
        families.append(
            {
                "key": key,
                "label": label,
                "description": description,
                "sources": rows,
                "active_count": len(active),
                "official_count": sum(1 for row in rows if row.get("is_official")),
                "raw_documents": sum(_int_value(row.get("raw_documents")) for row in rows),
                "review_pending": sum(_int_value(row.get("review_pending")) for row in rows),
            }
        )
    return {
        "families": families,
        "sources": source_rows,
        "totals": {
            "sources": len(source_rows),
            "active": sum(1 for row in source_rows if row.get("enabled")),
            "official": sum(1 for row in source_rows if row.get("is_official")),
            "catalog_defaults": sum(1 for row in source_rows if str(row.get("code") or "") in default_codes),
            "added_by_catalog": sum(1 for row in source_rows if row.get("was_added_by_catalog")),
            "raw_documents": sum(_int_value(row.get("raw_documents")) for row in source_rows),
            "review_pending": sum(_int_value(row.get("review_pending")) for row in source_rows),
        },
        "schedule": [
            {
                "time": "23:00",
                "title": "Archivi ufficiali",
                "body": "Normattiva e Gazzetta vengono riconciliate con i dati locali prima di scaricare.",
            },
            {
                "time": "23:10",
                "title": "Gazzetta Ufficiale",
                "body": "Le nuove uscite vengono lette, deduplicate e inviate alla verifica pubblica.",
            },
            {
                "time": "23:15",
                "title": "Catalogo completo",
                "body": "Tutte le fonti attive lavorano a job separati con limite per elemento e pubblicazione governata.",
            },
        ],
        "policy": [
            "Prima si controllano archivio, catalogo e impronta del contenuto gia' presente.",
            "Si acquisiscono solo elementi nuovi o cambiati; i duplicati restano fuori dalla coda.",
            "La verifica pubblica legge pagina ufficiale e allegati collegati quando disponibili.",
            "Lex usa prima gli archivi locali, poi la ricerca web governata se il contesto non basta.",
        ],
        "runtime": {
            "item_timeout_seconds": _legal_updates_item_timeout(cfg_source),
            "publish_max_items": _legal_updates_publish_max_items(cfg_source),
            "attachment_reading": _flag_enabled(
                os.getenv("IUSENTRA_LEGAL_VERIFICATION_READ_ATTACHMENTS", "1")
            ),
        },
        "official_archives": official_archives,
    }


def _bootstrap_legacy_legal_updates(
    cfg_source: dict[str, Any],
    *,
    manager: GestioneTenant | None,
    studio: Any | None,
    target_paths: dict[str, str],
) -> None:
    if manager is None or studio is None:
        return
    root_anchor = str(cfg_source.get("LEGAL_INTELLIGENCE_DB") or "").strip()
    target_anchor = str(target_paths.get("LEGAL_INTELLIGENCE_DB") or "").strip()
    if not root_anchor or not target_anchor:
        return
    root_anchor_path = Path(root_anchor).resolve()
    target_anchor_path = Path(target_anchor).resolve()
    if root_anchor_path == target_anchor_path:
        return

    target_database = getattr(studio, "database", None)
    if str(getattr(target_database, "effective_runtime_kind", "") or "").strip().lower() == "postgresql":
        return

    root_cfg = LegalUpdateDbConfig.from_anchor(str(root_anchor_path))
    target_cfg = LegalUpdateDbConfig.from_anchor(str(target_anchor_path))
    if _repository_data_count(target_cfg.db_path) > 0:
        return
    if _repository_data_count(root_cfg.db_path) <= 0:
        return

    source_db = Path(root_cfg.db_path)
    target_db = Path(target_cfg.db_path)
    if source_db.is_file():
        target_db.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_db, target_db)

    source_json = Path(root_cfg.json_path)
    target_json = Path(target_cfg.json_path)
    if source_json.is_file():
        target_json.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_json, target_json)


def build_legal_update_pipeline_runtime(
    app: Any | None = None,
    *,
    tenant_slug: str = "",
) -> LegalUpdatePipeline:
    runtime_app, cfg_source = _runtime_app_and_config(app)

    # Gli aggiornamenti legali sono presidio pubblico di piattaforma: fonti,
    # acquisizione, review, archivio e news devono essere unici per tutti gli studi.
    # I dati privati di studio restano tenant-aware negli altri domini.
    intelligence_db = str(
        cfg_source.get("LEGAL_INTELLIGENCE_DB")
        or "./intelligence/motori.json"
    )
    giurisprudenza_db_path = str(
        cfg_source.get("GIURISPRUDENZA_DB")
        or ""
    )
    return build_legal_update_pipeline(
        intelligence_db,
        giurisprudenza_db_path=giurisprudenza_db_path,
        ai_base_url=str(
            cfg_source.get("LOCAL_AI_BASE_URL")
            or cfg_source.get("PCT_LOCAL_AI_BASE_URL")
            or ""
        ).strip(),
        ai_model=str(
            cfg_source.get("LOCAL_AI_CHAT_MODEL")
            or cfg_source.get("OLLAMA_MODEL")
            or "mistral"
        ).strip(),
        export_json_enabled=_flag_enabled(cfg_source.get("LEGAL_UPDATES_EXPORT_JSON_ENABLED")),
        mirror_giurisprudenza_json_enabled=_flag_enabled(
            cfg_source.get("LEGAL_UPDATES_MIRROR_GIURISPRUDENZA_JSON_ENABLED")
        ),
    )


def build_legal_update_surface(
    app: Any | None = None,
    *,
    tenant_slug: str = "",
) -> dict[str, Any]:
    runtime_app, cfg_source = _runtime_app_and_config(app)
    active_tenants = _active_tenants(cfg_source)
    pipeline = build_legal_update_pipeline_runtime(runtime_app)
    snapshot = pipeline.dashboard_snapshot()
    snapshot["official_archives"] = _official_archives_payload()
    snapshot["runtime"] = {
        "db_path": pipeline.repository.db_path,
        "json_path": pipeline.repository.json_path,
        "backend_kind": getattr(pipeline.repository, "backend_kind", "sqlite"),
        "db_backend_label": "Archivio legale condiviso",
        "postgres_enabled": False,
        "lex_reads_sql": True,
        "json_export_enabled": bool(getattr(pipeline, "export_json_enabled", False)),
        "giurisprudenza_json_mirror_enabled": bool(
            getattr(pipeline, "mirror_giurisprudenza_json_enabled", False)
        ),
        "ollama_url": pipeline.ai_base_url,
        "ollama_model": pipeline.ai_model,
        "giurisprudenza_db_path": pipeline.giurisprudenza_db_path,
        "tenant_slug": "",
        "tenant_name": "",
        "tenant_registry_name": "",
        "tenant_configured_name": "",
        "tenant_name_mismatch": False,
        "tenant_choices": [],
        "tenant_count": len(active_tenants),
        "storage_scope": "shared_platform",
    }
    return snapshot


def run_legal_update_action(
    action: str,
    *,
    source_codes: list[str] | None = None,
    tenant_slug: str = "",
) -> dict[str, Any]:
    _, cfg_source = _runtime_app_and_config()
    pipeline = build_legal_update_pipeline_runtime(tenant_slug=tenant_slug)
    if action == "scan":
        pipeline.repository.upsert_sources(list(DEFAULT_SOURCE_ROWS))
        selected_sources = source_codes or [
            str(row.get("code") or "")
            for row in pipeline.repository.list_sources(enabled_only=True)
            if str(row.get("code") or "")
        ]
        return run_legal_update_batch_with_timeouts(
            _legal_update_job_config(cfg_source),
            source_codes=selected_sources,
            auto_publish=True,
            item_timeout_seconds=_legal_updates_item_timeout(cfg_source),
            publish_max_items=_legal_updates_publish_max_items(cfg_source),
        )
    if action == "autopublish":
        return run_legal_update_publish_queue_with_timeouts(
            _legal_update_job_config(cfg_source),
            item_timeout_seconds=_legal_updates_item_timeout(cfg_source),
            max_items=_legal_updates_publish_max_items(cfg_source),
        )
    if action == "cleanup":
        return pipeline.repository.deduplicate_archive(performed_by="superadmin")
    raise ValueError(f"Azione non supportata: {action}")
