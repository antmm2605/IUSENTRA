"""Bootstrap e service wiring estratti da web.app."""

from __future__ import annotations

import errno
import os
from pathlib import Path
from typing import Any

from flask import Flask, g, has_request_context, request, session

from pct.agenda import Agenda
from pct.auth import GestioneUtenti, RuoloUtente
from pct.backup import GestioneBackup
from pct.clienti import GestioneClienti
from pct.condivisione import GestioneCondivisioni, RuoloCondivisione
from pct.database import GestioneDatabase, bootstrap_moduli_monitorati
from pct.fascicoli import GestioneFascicoli
from pct.fatturazione import GestioneFatturazione
from pct.messaggi import ConfigEmail, ConfigMessaggistica, ConfigTwilio, GestioneMessaggi
from pct.pagamenti import GestionePagamenti
from pct.pdp_penale_workflow import PDPPenaleWorkflowRepository
from pct.preventivi import GestionePreventivi
from pct.privacy import GestioneTrattamenti
from pct.scadenziario import GestioneScadenziario, regola_patrono_studio
from pct.search_index import IndiceRicerca
from pct.soggetti import GestioneSoggetti
from pct.sync import get_gestore
from pct.telematico_workflow import TelematicoWorkflowRepository
from pct.runtime_env import is_managed_cloud_runtime
from pct.tenant import DbMode, normalize_db_mode
from pct.timesheet import GestioneTimesheet
from pct.workspace_intelligente import WorkspaceIntelligenteService
from web.services.auth_runtime import register_auth_runtime
from web.services.feature_flags import resolve_feature_flags
from web.services.runtime_settings import apply_runtime_settings
from web.services.security_runtime import register_security_runtime
from web.services.storage_runtime import get_request_studio_db


def build_core_runtime(app: Flask, cfg: dict[str, Any]) -> dict[str, Any]:
    configured_storage_raw = cfg.get("STORAGE_MODE_DEFAULT")
    if configured_storage_raw is None:
        configured_storage_raw = os.getenv("PCT_STORAGE_MODE", "")
    if str(configured_storage_raw or "").strip():
        configured_storage_mode = normalize_db_mode(configured_storage_raw)
    else:
        configured_storage_mode = DbMode.SQLITE
    legacy_sqlite_raw = cfg.get("SQLITE_MODE")
    if legacy_sqlite_raw is None:
        legacy_sqlite_raw = os.getenv("PCT_SQLITE_MODE", "")
    legacy_sqlite_text = str(legacy_sqlite_raw or "").strip().lower()
    data_root = str(
        cfg.get("PCT_DATA_ROOT")
        or os.getenv("PCT_DATA_ROOT")
        or cfg.get("DATA_DIR")
        or os.getenv("IUSENTRA_DATA_DIR")
        or ""
    ).strip()

    app.config["STORAGE_MODE_DEFAULT"] = configured_storage_mode
    app.config["SQLITE_MODE"] = (
        configured_storage_mode == DbMode.SQLITE
        if not legacy_sqlite_text
        else legacy_sqlite_text in ("1", "true", "yes")
    )
    app.config["PCT_DATA_ROOT"] = data_root
    app.config["DATA_DIR"] = str(cfg.get("DATA_DIR") or os.getenv("IUSENTRA_DATA_DIR") or data_root).strip()
    app.config["AGENDA_DB"] = cfg.get(
        "AGENDA_DB", os.getenv("PCT_AGENDA_DB", "./agenda/appuntamenti.json")
    )
    app.config["CALENDAR_SYNC_DB"] = cfg.get(
        "CALENDAR_SYNC_DB",
        os.getenv(
            "PCT_CALENDAR_SYNC_DB",
            str(Path(app.config["AGENDA_DB"]).parent / "calendar_sync.json"),
        ),
    )
    app.config["CALENDAR_SYNC_ENGINE_DB"] = cfg.get(
        "CALENDAR_SYNC_ENGINE_DB",
        os.getenv(
            "PCT_CALENDAR_SYNC_ENGINE_DB",
            str(Path(app.config["AGENDA_DB"]).parent / "calendar_sync_engine.json"),
        ),
    )
    app.config["CALENDAR_CONFLICTS_DB"] = cfg.get(
        "CALENDAR_CONFLICTS_DB",
        os.getenv(
            "PCT_CALENDAR_CONFLICTS_DB",
            str(Path(app.config["AGENDA_DB"]).parent / "calendar_conflicts.json"),
        ),
    )
    app.config["CALENDAR_TOKEN_DB"] = cfg.get(
        "CALENDAR_TOKEN_DB",
        os.getenv(
            "PCT_CALENDAR_TOKEN_DB",
            str(Path(app.config["AGENDA_DB"]).parent / "cal_token.json"),
        ),
    )
    app.config["CLIENTI_DB"] = cfg.get(
        "CLIENTI_DB", os.getenv("PCT_CLIENTI_DB", "./clienti/anagrafica.json")
    )

    def _env_or_data_peer_path(env_key: str, folder: str, filename: str) -> str:
        fallback = _data_peer_path(app.config["CLIENTI_DB"], folder, filename)
        if "CLIENTI_DB" in cfg:
            return fallback
        return os.getenv(env_key, fallback)

    def _env_or_explicit_root_default(env_key: str, fallback: str, *root_keys: str) -> str:
        if any(key in cfg for key in ("CLIENTI_DB", *root_keys)):
            return fallback
        return os.getenv(env_key, fallback)

    def _data_peer_path(base_path: str, folder: str, filename: str) -> str:
        base = Path(base_path)
        if base.parent.name.lower() == "clienti" and base.name.lower() == "anagrafica.json":
            root = base.parent.parent
        else:
            root = base.parent
        return str(root / folder / filename)

    def _runtime_data_default(*parts: str, fallback: str) -> str:
        if data_root:
            return str(Path(data_root).joinpath(*parts))
        return fallback

    app.config["STORAGE_CONFIG"] = cfg.get(
        "STORAGE_CONFIG",
        os.getenv(
            "PCT_STORAGE_CONFIG",
            _data_peer_path(app.config["CLIENTI_DB"], "config", "storage.json"),
        ),
    )
    app.config["STUDIO_LOCAL_PACK_DB"] = cfg.get(
        "STUDIO_LOCAL_PACK_DB",
        os.getenv(
            "PCT_STUDIO_LOCAL_PACK_DB",
            _data_peer_path(app.config["CLIENTI_DB"], "config", "studio_local_pack.json"),
        ),
    )

    app.config["CONDIVISIONI_DB"] = cfg.get(
        "CONDIVISIONI_DB", os.getenv("PCT_CONDIVISIONI_DB", "./clienti/condivisioni.json")
    )
    app.config["NOTE_FALDONE_DB"] = cfg.get(
        "NOTE_FALDONE_DB", os.getenv("PCT_NOTE_FALDONE_DB", "./clienti/note_faldone.json")
    )
    app.config["FASCICOLI_DB"] = cfg.get(
        "FASCICOLI_DB", os.getenv("PCT_FASCICOLI_DB", "./fascicoli/fascicoli.json")
    )
    app.config["FASCICOLI_DOCS"] = cfg.get(
        "FASCICOLI_DOCS", os.getenv("PCT_FASCICOLI_DOCS", "./fascicoli/documenti")
    )
    app.config["FASCICOLI_ARCH"] = cfg.get(
        "FASCICOLI_ARCH", os.getenv("PCT_FASCICOLI_ARCH", "./fascicoli/archivio")
    )
    default_practice_engine_db = os.getenv("PCT_PRACTICE_ENGINE_DB") or str(
        Path(app.config["FASCICOLI_DB"]).parent / "practice_engine" / "practice_engine.json"
    )
    app.config["PRACTICE_ENGINE_DB"] = cfg.get(
        "PRACTICE_ENGINE_DB",
        default_practice_engine_db,
    )
    fascicoli_root = Path(app.config["FASCICOLI_DB"]).parent
    app.config["DOCUMENTI_AI_DIR"] = cfg.get(
        "DOCUMENTI_AI_DIR",
        os.getenv("PCT_DOCUMENTI_AI_DIR", str(fascicoli_root / "documenti_ai")),
    )
    app.config["DOCUMENTI_AI_DB"] = cfg.get(
        "DOCUMENTI_AI_DB",
        os.getenv("PCT_DOCUMENTI_AI_DB", str(Path(app.config["DOCUMENTI_AI_DIR"]) / "documenti_ai.json")),
    )
    app.config["EDITOR_AI_DB"] = cfg.get(
        "EDITOR_AI_DB",
        os.getenv("PCT_EDITOR_AI_DB", str(fascicoli_root / "editor_ai" / "editor_ai.json")),
    )
    app.config["FASCICOLI_IMPORTAZIONI_DIR"] = cfg.get(
        "FASCICOLI_IMPORTAZIONI_DIR",
        os.getenv("PCT_FASCICOLI_IMPORTAZIONI_DIR", str(fascicoli_root / "importazioni")),
    )
    app.config["PEC_CANCELLERIA_STATE_DB"] = cfg.get(
        "PEC_CANCELLERIA_STATE_DB",
        os.getenv("PCT_PEC_CANCELLERIA_STATE_DB", str(fascicoli_root / "pec_cancelleria_state.json")),
    )
    app.config["PST_IMPORT_DIR"] = cfg.get(
        "PST_IMPORT_DIR",
        os.getenv(
            "PCT_PST_IMPORT_DIR",
            str(Path(app.config["FASCICOLI_DOCS"]).parent / "import_pst"),
        ),
    )
    app.config["MESSAGGI_DB"] = cfg.get(
        "MESSAGGI_DB", os.getenv("PCT_MESSAGGI_DB", "./messaggi/storico.json")
    )
    app.config["EMAIL_CASELLA_DB"] = cfg.get(
        "EMAIL_CASELLA_DB",
        os.getenv(
            "PCT_EMAIL_DB",
            _runtime_data_default("email", "casella.json", fallback="./email/casella.json"),
        ),
    )
    app.config["EMAIL_ORDINARIA_DB"] = cfg.get(
        "EMAIL_ORDINARIA_DB",
        os.getenv(
            "PCT_EMAIL_ORDINARIA_DB",
            _runtime_data_default(
                "email",
                "ordinaria.json",
                fallback=str(Path(app.config["EMAIL_CASELLA_DB"]).with_name("ordinaria.json")),
            ),
        ),
    )
    app.config["BACKUP_DIR"] = cfg.get(
        "BACKUP_DIR", os.getenv("PCT_BACKUP_DIR", "./backup")
    )
    app.config["BACKUP_LOCAL_MIRROR_DIR"] = cfg.get(
        "BACKUP_LOCAL_MIRROR_DIR",
        os.getenv("PCT_BACKUP_LOCAL_MIRROR_DIR", ""),
    )
    app.config["BACKUP_SECONDARY_MIRROR_DIR"] = cfg.get(
        "BACKUP_SECONDARY_MIRROR_DIR",
        os.getenv("PCT_BACKUP_SECONDARY_MIRROR_DIR", ""),
    )
    app.config["BACKUP_SECONDARY_LABEL"] = cfg.get(
        "BACKUP_SECONDARY_LABEL",
        os.getenv("PCT_BACKUP_SECONDARY_LABEL", "Destinazione esterna da configurare"),
    )
    app.config["AUTH_DB"] = cfg.get(
        "AUTH_DB", os.getenv("PCT_AUTH_DB", "./auth/utenti.json")
    )
    app.config["AUDIT_DB"] = cfg.get(
        "AUDIT_DB", os.getenv("PCT_AUDIT_DB", "./auth/audit.json")
    )
    bootstrap_admin_password = cfg.get(
        "BOOTSTRAP_ADMIN_PASSWORD",
        os.getenv("PCT_BOOTSTRAP_ADMIN_PASSWORD", ""),
    )
    if not str(bootstrap_admin_password or "").strip() and cfg.get("TESTING"):
        bootstrap_admin_password = "admin"
    app.config["BOOTSTRAP_ADMIN_PASSWORD"] = bootstrap_admin_password
    app.config["BOOTSTRAP_ADMIN_CREDENTIALS_PATH"] = cfg.get(
        "BOOTSTRAP_ADMIN_CREDENTIALS_PATH",
        os.getenv(
            "PCT_BOOTSTRAP_ADMIN_CREDENTIALS_PATH",
            str(Path(app.config["AUTH_DB"]).parent / "bootstrap_admin.json"),
        ),
    )
    app.config["SCADENZIARIO_DB"] = cfg.get(
        "SCADENZIARIO_DB", os.getenv("PCT_SCADENZIARIO_DB", "./scadenziario/scadenze.json")
    )
    app.config["TERMINI_PROCESSUALI_DB"] = cfg.get(
        "TERMINI_PROCESSUALI_DB",
        os.getenv(
            "PCT_TERMINI_PROCESSUALI_DB",
            str(Path(app.config["SCADENZIARIO_DB"]).with_name("termini_processuali.json")),
        ),
    )
    app.config["TIMESHEET_DB"] = cfg.get(
        "TIMESHEET_DB",
        os.getenv("PCT_TIMESHEET_DB", "./timesheet/entries.json"),
    )
    app.config["TIME_TRACKING_DB"] = cfg.get(
        "TIME_TRACKING_DB",
        os.getenv("PCT_TIME_TRACKING_DB", "./timesheet/time_tracking.json"),
    )
    app.config["CRM_DB"] = cfg.get(
        "CRM_DB",
        os.getenv("PCT_CRM_DB", "./crm/leads.json"),
    )
    app.config["CTU_DB"] = cfg.get(
        "CTU_DB",
        os.getenv("PCT_CTU_DB", "./ctu/incarichi.json"),
    )
    app.config["PRIMA_NOTA_DB"] = cfg.get(
        "PRIMA_NOTA_DB",
        os.getenv("PCT_PRIMA_NOTA_DB", "./contabilita/prima_nota.json"),
    )
    app.config["SEARCH_INDEX"] = cfg.get(
        "SEARCH_INDEX", os.getenv("PCT_SEARCH_INDEX", "./search/index.db")
    )
    app.config["OCR_QUEUE_DB"] = cfg.get(
        "OCR_QUEUE_DB",
        os.getenv(
            "PCT_OCR_QUEUE_DB",
            str(Path(app.config["SEARCH_INDEX"]).parent / "ocr_jobs.db"),
        ),
    )
    app.config["PRIVACY_DB"] = cfg.get(
        "PRIVACY_DB", os.getenv("PCT_PRIVACY_DB", "./privacy/registro.json")
    )
    app.config["API_KEY"] = os.getenv("PCT_API_KEY", "")
    app.config["API_V1_ALLOWED_ORIGINS"] = cfg.get(
        "API_V1_ALLOWED_ORIGINS",
        os.getenv("PCT_API_V1_ALLOWED_ORIGINS", ""),
    )
    app.config["FEATURE_FLAGS"] = resolve_feature_flags(cfg)
    app.config["STUDIO_NOME"] = os.getenv("PCT_STUDIO_NOME", "IUSENTRA")
    default_portale_db = _env_or_data_peer_path("PCT_PORTALE_DB", "portale", "portali.json")
    app.config["PORTALE_DB"] = cfg.get("PORTALE_DB", default_portale_db)
    portale_root = Path(app.config["PORTALE_DB"]).parent
    app.config["PORTALE_UPLOADS"] = cfg.get(
        "PORTALE_UPLOADS",
        _env_or_explicit_root_default("PCT_PORTALE_UPLOADS", str(portale_root / "uploads"), "PORTALE_DB"),
    )
    app.config["PORTALE_IMPORT_LOG_DB"] = cfg.get(
        "PORTALE_IMPORT_LOG_DB",
        _env_or_explicit_root_default("PCT_PORTALE_IMPORT_LOG_DB", str(portale_root / "import_log.json"), "PORTALE_DB"),
    )
    app.config["FATTURAZIONE_DB"] = cfg.get(
        "FATTURAZIONE_DB", os.getenv("PCT_FATTURAZIONE_DB", "./fatturazione/parcelle.json")
    )
    app.config["PREVENTIVI_DB"] = cfg.get(
        "PREVENTIVI_DB", os.getenv("PCT_PREVENTIVI_DB", "./preventivi/preventivi.json")
    )
    preventivi_root = Path(app.config["PREVENTIVI_DB"]).parent
    app.config["PREVENTIVI_REPOSITORY_DB"] = cfg.get(
        "PREVENTIVI_REPOSITORY_DB",
        os.getenv("PCT_PREVENTIVI_REPOSITORY_DB", str(preventivi_root / "preventivi_repository.json")),
    )
    app.config["PREVENTIVI_WORKFLOW_STATES_DB"] = cfg.get(
        "PREVENTIVI_WORKFLOW_STATES_DB",
        os.getenv("PCT_PREVENTIVI_WORKFLOW_STATES_DB", str(preventivi_root / "preventivi_workflow_states.json")),
    )
    app.config["PREVENTIVI_FIELD_MAP_DB"] = cfg.get(
        "PREVENTIVI_FIELD_MAP_DB",
        os.getenv("PCT_PREVENTIVI_FIELD_MAP_DB", str(preventivi_root / "preventivi_field_map.json")),
    )
    app.config["PREVENTIVI_RULES_DB"] = cfg.get(
        "PREVENTIVI_RULES_DB",
        os.getenv("PCT_PREVENTIVI_RULES_DB", str(preventivi_root / "preventivi_rules.json")),
    )
    app.config["NOTIFICHE_LOG"] = cfg.get(
        "NOTIFICHE_LOG",
        os.getenv(
            "PCT_NOTIFICHE_LOG",
            _data_peer_path(app.config["CLIENTI_DB"], "notifiche", "log.json"),
        ),
    )
    app.config["NOTIFICATIONS_DB"] = cfg.get(
        "NOTIFICATIONS_DB",
        os.getenv(
            "PCT_NOTIFICATIONS_DB",
            os.getenv(
                "NOTIFICATIONS_DB",
                _data_peer_path(app.config["CLIENTI_DB"], "notifications", "notifications.db"),
            ),
        ),
    )
    app.config["IUSENTRA_WEB_PUSH_ENABLED"] = cfg.get(
        "IUSENTRA_WEB_PUSH_ENABLED",
        os.getenv("IUSENTRA_WEB_PUSH_ENABLED", "0"),
    )
    app.config["IUSENTRA_VAPID_PUBLIC_KEY"] = cfg.get(
        "IUSENTRA_VAPID_PUBLIC_KEY",
        os.getenv("IUSENTRA_VAPID_PUBLIC_KEY", ""),
    )
    app.config["IUSENTRA_VAPID_PRIVATE_KEY"] = cfg.get(
        "IUSENTRA_VAPID_PRIVATE_KEY",
        os.getenv("IUSENTRA_VAPID_PRIVATE_KEY", ""),
    )
    app.config["IUSENTRA_VAPID_SUBJECT"] = cfg.get(
        "IUSENTRA_VAPID_SUBJECT",
        os.getenv("IUSENTRA_VAPID_SUBJECT", "mailto:admin@example.com"),
    )
    app.config["SOGGETTI_DB"] = cfg.get(
        "SOGGETTI_DB",
        _env_or_data_peer_path("PCT_SOGGETTI_DB", "soggetti", "anagrafica.json"),
    )
    app.config["SOGGETTI_PARTI_DB"] = cfg.get(
        "SOGGETTI_PARTI_DB",
        _env_or_data_peer_path("PCT_SOGGETTI_PARTI_DB", "soggetti", "parti.json"),
    )
    app.config["WIZARD_PRO_DB"] = cfg.get(
        "WIZARD_PRO_DB", os.getenv(
            "PCT_WIZARD_PRO_DB",
            _data_peer_path(app.config["CLIENTI_DB"], "wizard_pro", "sessioni.json"),
        )
    )
    app.config["LEGAL_INTELLIGENCE_DB"] = cfg.get(
        "LEGAL_INTELLIGENCE_DB",
        os.getenv(
            "PCT_LEGAL_INTELLIGENCE_DB",
            _data_peer_path(app.config["CLIENTI_DB"], "intelligence", "motori.json"),
        ),
    )
    app.config["LEGAL_COVERAGE_SQLITE_DB"] = cfg.get(
        "LEGAL_COVERAGE_SQLITE_DB",
        os.getenv(
            "LEGAL_COVERAGE_SQLITE_DB",
            os.getenv(
                "PCT_LEGAL_COVERAGE_SQLITE_DB",
                _data_peer_path(app.config["CLIENTI_DB"], "intelligence", "legal_coverage.db"),
            ),
        ),
    )
    app.config["LEGAL_SKILLS_PROFILE_DB"] = cfg.get(
        "LEGAL_SKILLS_PROFILE_DB",
        os.getenv(
            "PCT_LEGAL_SKILLS_PROFILE_DB",
            _data_peer_path(app.config["CLIENTI_DB"], "intelligence/legal_skills", "profile.json"),
        ),
    )
    app.config["LEGAL_SKILLS_RUNS_DB"] = cfg.get(
        "LEGAL_SKILLS_RUNS_DB",
        os.getenv(
            "PCT_LEGAL_SKILLS_RUNS_DB",
            _data_peer_path(app.config["CLIENTI_DB"], "intelligence/legal_skills", "runs.json"),
        ),
    )
    app.config["LEGAL_SKILLS_SCHEDULED_DB"] = cfg.get(
        "LEGAL_SKILLS_SCHEDULED_DB",
        os.getenv(
            "PCT_LEGAL_SKILLS_SCHEDULED_DB",
            _data_peer_path(app.config["CLIENTI_DB"], "intelligence/legal_skills", "scheduled.json"),
        ),
    )
    app.config["WORKFLOW_AGENTS_RUNS_DB"] = cfg.get(
        "WORKFLOW_AGENTS_RUNS_DB",
        os.getenv(
            "PCT_WORKFLOW_AGENTS_RUNS_DB",
            _data_peer_path(app.config["CLIENTI_DB"], "intelligence/workflow_agents", "runs.json"),
        ),
    )
    app.config["WORKFLOW_AGENTS_METRICS_DB"] = cfg.get(
        "WORKFLOW_AGENTS_METRICS_DB",
        os.getenv(
            "PCT_WORKFLOW_AGENTS_METRICS_DB",
            _data_peer_path(app.config["CLIENTI_DB"], "intelligence/workflow_agents", "metrics.json"),
        ),
    )
    app.config["WORKFLOW_AGENTS_ACTIONS_DB"] = cfg.get(
        "WORKFLOW_AGENTS_ACTIONS_DB",
        os.getenv(
            "PCT_WORKFLOW_AGENTS_ACTIONS_DB",
            _data_peer_path(app.config["CLIENTI_DB"], "intelligence/workflow_agents", "actions.json"),
        ),
    )
    app.config["NORMATIVE_TABLES_DB"] = cfg.get(
        "NORMATIVE_TABLES_DB",
        os.getenv(
            "PCT_NORMATIVE_TABLES_DB",
            _data_peer_path(app.config["CLIENTI_DB"], "intelligence", "tabelle_normative.json"),
        ),
    )
    app.config["GIURISPRUDENZA_DB"] = cfg.get(
        "GIURISPRUDENZA_DB",
        os.getenv(
            "PCT_GIURISPRUDENZA_DB",
            _data_peer_path(app.config["CLIENTI_DB"], "intelligence", "giurisprudenza.json"),
        ),
    )
    intelligence_root = Path(app.config["LEGAL_INTELLIGENCE_DB"]).parent
    for key, filename in {
        "GIURISPRUDENZA_REPOSITORY_DB": "giurisprudenza_repository.json",
        "GIURISPRUDENZA_SOURCES_REPOSITORY_DB": "giurisprudenza_sources_repository.json",
        "GIURISPRUDENZA_SYNC_REGISTRY_DB": "giurisprudenza_sync_registry.json",
        "GIURISPRUDENZA_TAXONOMY_REPOSITORY_DB": "giurisprudenza_taxonomy_repository.json",
        "GIURISPRUDENZA_USAGE_POLICY_DB": "giurisprudenza_usage_policy.json",
        "LEGAL_ENGINE_SOURCE_EDGES_DB": "legal_engine_source_edges.json",
        "LEGAL_ENGINES_REPOSITORY_DB": "legal_engines_repository.json",
        "LEGAL_INTELLIGENCE_REPOSITORY_DB": "legal_intelligence_repository.json",
        "LEGAL_KEYWORD_TO_ENGINE_DB": "legal_keyword_to_engine.json",
        "LEGAL_KEYWORD_TO_SOURCE_DB": "legal_keyword_to_source.json",
        "LEGAL_OPERATIONAL_REPOSITORY_DB": "legal_operational_repository.json",
        "LEGAL_SOURCES_REPOSITORY_DB": "legal_sources_repository.json",
        "TELEMATICO_ACTIONS_REPOSITORY_DB": "telematico_actions_repository.json",
        "TELEMATICO_CAPABILITIES_REPOSITORY_DB": "telematico_capabilities_repository.json",
        "TELEMATICO_CATALOG_SNAPSHOT_DB": "telematico_catalog_snapshot.json",
        "TELEMATICO_CATALOG_SOURCES_REPOSITORY_DB": "telematico_catalog_sources_repository.json",
        "TELEMATICO_METHODS_REPOSITORY_DB": "telematico_methods_repository.json",
        "TELEMATICO_MONITORING_REPOSITORY_DB": "telematico_monitoring_repository.json",
        "TELEMATICO_REPOSITORY_JSON": "telematico_repository.json",
        "TELEMATICO_RULES_REPOSITORY_DB": "telematico_rules_repository.json",
        "TELEMATICO_SOURCES_REPOSITORY_DB": "telematico_sources_repository.json",
        "TELEMATICO_WIZARD_SECTIONS_REPOSITORY_DB": "telematico_wizard_sections_repository.json",
        "TELEMATICO_WSDL_MODULES_REPOSITORY_DB": "telematico_wsdl_modules_repository.json",
        "TELEMATICO_XSD_CHANNELS_REPOSITORY_DB": "telematico_xsd_channels_repository.json",
    }.items():
        app.config[key] = cfg.get(
            key,
            os.getenv(f"PCT_{key}", str(intelligence_root / filename)),
        )
    app.config["LEX_DATASET_DIR"] = cfg.get(
        "LEX_DATASET_DIR",
        os.getenv("PCT_LEX_DATASET_DIR", str(intelligence_root / "lex_dataset")),
    )
    app.config["LEX_OFFICIAL_DB"] = cfg.get(
        "LEX_OFFICIAL_DB",
        os.getenv(
            "PCT_LEX_OFFICIAL_DB",
            os.getenv(
                "PCT_OFFICIAL_SOURCES_DB",
                os.getenv(
                    "PCT_LEX_SOURCES_DB",
                    _runtime_data_default(
                        "fonti_ufficiali",
                        "lex_sources.sqlite",
                        fallback="./data/fonti_ufficiali/lex_sources.sqlite",
                    ),
                ),
            ),
        ),
    )
    app.config["NORMATTIVA_DB"] = cfg.get(
        "NORMATTIVA_DB",
        os.getenv(
            "PCT_NORMATTIVA_DB",
            os.getenv(
                "PCT_LEX_NORMATTIVA_DB",
                _runtime_data_default(
                    "normativa",
                    "normattiva.sqlite",
                    fallback="./data/normativa/normattiva.sqlite",
                ),
            ),
        ),
    )
    app.config["NORMATTIVA_JSONL"] = cfg.get(
        "NORMATTIVA_JSONL",
        os.getenv(
            "PCT_NORMATTIVA_JSONL",
            os.getenv(
                "PCT_LEX_NORMATTIVA_JSONL",
                _runtime_data_default(
                    "normativa",
                    "index",
                    "normattiva_chunks.jsonl",
                    fallback="./data/normativa/index/normattiva_chunks.jsonl",
                ),
            ),
        ),
    )
    app.config["WORKSPACE_INTELLIGENCE_DB"] = cfg.get(
        "WORKSPACE_INTELLIGENCE_DB",
        os.getenv(
            "PCT_WORKSPACE_INTELLIGENCE_DB",
            _data_peer_path(app.config["CLIENTI_DB"], "intelligence", "workspace_intelligence.json"),
        ),
    )
    app.config["VALIDATION_RUNS_DB"] = cfg.get(
        "VALIDATION_RUNS_DB",
        os.getenv(
            "PCT_VALIDATION_RUNS_DB",
            _data_peer_path(app.config["CLIENTI_DB"], "intelligence", "validation_runs.json"),
        ),
    )
    app.config["PDP_PENALE_DB"] = cfg.get(
        "PDP_PENALE_DB",
        os.getenv(
            "PCT_PDP_PENALE_DB",
            _data_peer_path(app.config["CLIENTI_DB"], "penale", "pdp_penale.db"),
        ),
    )
    app.config["TELEMATICO_DB"] = cfg.get(
        "TELEMATICO_DB",
        os.getenv(
            "PCT_TELEMATICO_DB",
            _data_peer_path(app.config["CLIENTI_DB"], "telematico", "workflow.db"),
        ),
    )
    # WhatsApp / notifiche
    app.config["TWILIO_SID"]     = os.getenv("PCT_TWILIO_SID", "")
    app.config["TWILIO_TOKEN"]   = os.getenv("PCT_TWILIO_TOKEN", "")
    app.config["TWILIO_NUMERO"]  = os.getenv("PCT_TWILIO_NUMERO", "")
    app.config["CALLMEBOT_KEY"]  = os.getenv("PCT_CALLMEBOT_KEY", "")
    # Dati studio per PDF parcelle e template atti
    app.config["STUDIO_PIVA"]      = os.getenv("PCT_STUDIO_PIVA", "")
    app.config["STUDIO_CF"]        = os.getenv("PCT_STUDIO_CF", "")
    app.config["STUDIO_INDIRIZZO_VIA"] = os.getenv("PCT_STUDIO_INDIRIZZO", "")
    app.config["STUDIO_INDIRIZZO"] = os.getenv("PCT_STUDIO_INDIRIZZO", "")
    app.config["STUDIO_CAP"]       = os.getenv("PCT_STUDIO_CAP", "")
    app.config["STUDIO_CITY"]      = os.getenv("PCT_STUDIO_CITY", "")
    app.config["STUDIO_PROVINCE"]  = os.getenv("PCT_STUDIO_PROVINCE", "")
    app.config["STUDIO_IBAN"]      = os.getenv("PCT_STUDIO_IBAN", "")
    app.config["STUDIO_BANCA"]     = os.getenv("PCT_STUDIO_BANCA", "")
    app.config["STUDIO_BIC_SWIFT"] = (
        os.getenv("PCT_STUDIO_BIC_SWIFT", "")
        or os.getenv("PCT_FATTURAZIONE_BIC_SWIFT", "")
    )
    app.config["STUDIO_AVVOCATO"]  = os.getenv("PCT_STUDIO_AVVOCATO", "")
    app.config["STUDIO_NUMERO_ISCRIZIONE_ALBO"] = os.getenv(
        "PCT_STUDIO_NUMERO_ISCRIZIONE_ALBO", ""
    )
    app.config["STUDIO_ORDINE_AVVOCATI"] = os.getenv("PCT_STUDIO_ORDINE_AVVOCATI", "")
    app.config["TEMPLATE_ATTI_DB"] = cfg.get(
        "TEMPLATE_ATTI_DB", os.getenv("PCT_TEMPLATE_ATTI_DB", "./template_atti/templates.json")
    )
    app.config["TEMPLATE_REPOSITORY_DB"] = cfg.get(
        "TEMPLATE_REPOSITORY_DB",
        os.getenv(
            "PCT_TEMPLATE_REPOSITORY_DB",
            str(Path(app.config["TEMPLATE_ATTI_DB"]).with_name("template_repository.json")),
        ),
    )
    app.config["PROCEDURE_COMPLETION_DB"] = cfg.get(
        "PROCEDURE_COMPLETION_DB",
        os.getenv("PROCEDURE_COMPLETION_DB", "./intelligence/procedure_completion.sqlite"),
    )
    app.config["TEMPLATE_ATTI_PREFS_DB"] = cfg.get(
        "TEMPLATE_ATTI_PREFS_DB",
        os.getenv(
            "PCT_TEMPLATE_ATTI_PREFS_DB",
            _data_peer_path(app.config["TEMPLATE_ATTI_DB"], "template_atti", "editor_layout.json"),
        ),
    )
    app.config["STUDIO_TIMBRO_DB"] = cfg.get(
        "STUDIO_TIMBRO_DB",
        os.getenv(
            "PCT_STUDIO_TIMBRO_DB",
            _data_peer_path(
                cfg.get(
                    "CONFIG_STUDIO_DB",
                    os.getenv("PCT_CONFIG_STUDIO_DB", cfg.get("STUDIO_CONFIG", os.getenv("PCT_STUDIO_CONFIG", "./config/studio.json"))),
                ),
                "config",
                "studio_timbro.db",
            ),
        ),
    )
    app.config["REDACTION_ASSISTANT_DB"] = cfg.get(
        "REDACTION_ASSISTANT_DB",
        os.getenv(
            "PCT_REDACTION_ASSISTANT_DB",
            _data_peer_path(app.config["CLIENTI_DB"], "intelligence", "assistente_redazionale.json"),
        ),
    )
    app.config["UFFICI_GIUDIZIARI_DB"] = cfg.get(
        "UFFICI_GIUDIZIARI_DB",
        os.getenv("PCT_UFFICI_DB", "/data/uffici/uffici_giudiziari.json"),
    )
    app.config["PST_WSDL_CATALOG_ZIP"] = cfg.get(
        "PST_WSDL_CATALOG_ZIP",
        os.getenv(
            "PCT_PST_WSDL_CATALOG_ZIP",
            _data_peer_path(app.config["CLIENTI_DB"], "intelligence", "A1_WSDL_CATALOG_v1.52b.zip"),
        ),
    )
    app.config["PST_OFFICIAL_CACHE"] = cfg.get(
        "PST_OFFICIAL_CACHE",
        os.getenv(
            "PCT_PST_OFFICIAL_CACHE",
            _data_peer_path(app.config["CLIENTI_DB"], "intelligence", "pst_catalogo_ufficiale.json"),
        ),
    )
    app.config["PST_SOAP_CATALOGO_UG_ENDPOINT"] = cfg.get(
        "PST_SOAP_CATALOGO_UG_ENDPOINT",
        os.getenv("PCT_PST_SOAP_CATALOGO_UG_ENDPOINT", ""),
    )
    app.config["PST_SOAP_TIMEOUT"] = float(
        cfg.get("PST_SOAP_TIMEOUT", os.getenv("PCT_PST_SOAP_TIMEOUT", "8")) or 8
    )
    apply_runtime_settings(app, cfg, data_peer_path=_data_peer_path)

    def _tenant_config_studio_path_from_session() -> str:
        if not (
            has_request_context()
            and (app.config.get("MULTI_TENANT") or getattr(g, "multi_tenant_enabled", False))
        ):
            return ""
        tenant_slug = str(
            getattr(g, "tenant_context_slug", "")
            or session.get("tenant_slug")
            or session.get("auth_tenant_slug")
            or ""
        ).strip().lower()
        if not tenant_slug:
            return ""
        from pct.tenant import GestioneTenant
        from web.services.tenant_isolation_runtime import assert_tenant_data_path

        paths = GestioneTenant(registry_path=app.config["TENANTS_REGISTRY"]).percorsi_dati(
            tenant_slug,
            reconcile_aliases=False,
            ensure_baseline=False,
        )
        config_path = str(paths.get("CONFIG_STUDIO_DB") or "")
        if not config_path:
            return ""
        return assert_tenant_data_path(config_path, key="CONFIG_STUDIO_DB")

    def _cfg_data_path(key: str) -> str:
        if has_request_context():
            paths = getattr(g, "data_paths", {}) or {}
            if not paths and getattr(g, "tenant_context_missing", False):
                raise RuntimeError(
                    "Contesto studio non disponibile per la richiesta corrente. "
                    "Accesso ai dati bloccato per evitare letture cross-studio."
                )
            if paths and key in paths:
                if app.config.get("MULTI_TENANT") or getattr(g, "multi_tenant_enabled", False):
                    from web.services.tenant_isolation_runtime import assert_tenant_data_path

                    return assert_tenant_data_path(paths[key], key=key)
                return paths[key]
            if key == "CONFIG_STUDIO_DB":
                tenant_config_path = _tenant_config_studio_path_from_session()
                if tenant_config_path:
                    return tenant_config_path
            return app.config[key]
        return app.config[key]

    def _database_paths() -> dict[str, str]:
        return {
            "calendar_sync": _cfg_data_path("CALENDAR_SYNC_DB"),
            "calendar_sync_engine": _cfg_data_path("CALENDAR_SYNC_ENGINE_DB"),
            "calendar_conflicts": _cfg_data_path("CALENDAR_CONFLICTS_DB"),
            "calendar_token": _cfg_data_path("CALENDAR_TOKEN_DB"),
            "storage_config": _cfg_data_path("STORAGE_CONFIG"),
            "studio_local_pack": _cfg_data_path("STUDIO_LOCAL_PACK_DB"),
            "clienti": _cfg_data_path("CLIENTI_DB"),
            "condivisioni": _cfg_data_path("CONDIVISIONI_DB"),
            "note_faldone": _cfg_data_path("NOTE_FALDONE_DB"),
            "fascicoli": _cfg_data_path("FASCICOLI_DB"),
            "documenti_ai": _cfg_data_path("DOCUMENTI_AI_DB"),
            "editor_ai": _cfg_data_path("EDITOR_AI_DB"),
            "pec_cancelleria_state": _cfg_data_path("PEC_CANCELLERIA_STATE_DB"),
            "practice_engine": _cfg_data_path("PRACTICE_ENGINE_DB"),
            "appuntamenti": _cfg_data_path("AGENDA_DB"),
            "scadenze": _cfg_data_path("SCADENZIARIO_DB"),
            "timesheet": _cfg_data_path("TIMESHEET_DB"),
            "time_tracking": _cfg_data_path("TIME_TRACKING_DB"),
            "crm": _cfg_data_path("CRM_DB"),
            "ctu": _cfg_data_path("CTU_DB"),
            "prima_nota": _cfg_data_path("PRIMA_NOTA_DB"),
            "messaggi": _cfg_data_path("MESSAGGI_DB"),
            "notifiche": _cfg_data_path("NOTIFICHE_LOG"),
            "notifications": _cfg_data_path("NOTIFICATIONS_DB"),
            "email_casella": _cfg_data_path("EMAIL_CASELLA_DB"),
            "email_ordinaria": _cfg_data_path("EMAIL_ORDINARIA_DB"),
            "utenti": _cfg_data_path("AUTH_DB"),
            "audit": _cfg_data_path("AUDIT_DB"),
            "privacy": _cfg_data_path("PRIVACY_DB"),
            "backup": str(Path(_cfg_data_path("BACKUP_DIR")) / "registro.json"),
            "portale": _cfg_data_path("PORTALE_DB"),
            "fatturazione": _cfg_data_path("FATTURAZIONE_DB"),
            "preventivi": _cfg_data_path("PREVENTIVI_DB"),
            "preventivi_repository": _cfg_data_path("PREVENTIVI_REPOSITORY_DB"),
            "preventivi_workflow_states": _cfg_data_path("PREVENTIVI_WORKFLOW_STATES_DB"),
            "preventivi_field_map": _cfg_data_path("PREVENTIVI_FIELD_MAP_DB"),
            "preventivi_rules": _cfg_data_path("PREVENTIVI_RULES_DB"),
            "soggetti": _cfg_data_path("SOGGETTI_DB"),
            "soggetti_parti": _cfg_data_path("SOGGETTI_PARTI_DB"),
            "wizard_pro": _cfg_data_path("WIZARD_PRO_DB"),
            "legal_intelligence": _cfg_data_path("LEGAL_INTELLIGENCE_DB"),
            "giurisprudenza_repository": _cfg_data_path("GIURISPRUDENZA_REPOSITORY_DB"),
            "giurisprudenza_sources_repository": _cfg_data_path("GIURISPRUDENZA_SOURCES_REPOSITORY_DB"),
            "giurisprudenza_sync_registry": _cfg_data_path("GIURISPRUDENZA_SYNC_REGISTRY_DB"),
            "giurisprudenza_taxonomy_repository": _cfg_data_path("GIURISPRUDENZA_TAXONOMY_REPOSITORY_DB"),
            "giurisprudenza_usage_policy": _cfg_data_path("GIURISPRUDENZA_USAGE_POLICY_DB"),
            "legal_engine_source_edges": _cfg_data_path("LEGAL_ENGINE_SOURCE_EDGES_DB"),
            "legal_engines_repository": _cfg_data_path("LEGAL_ENGINES_REPOSITORY_DB"),
            "legal_intelligence_repository": _cfg_data_path("LEGAL_INTELLIGENCE_REPOSITORY_DB"),
            "legal_keyword_to_engine": _cfg_data_path("LEGAL_KEYWORD_TO_ENGINE_DB"),
            "legal_keyword_to_source": _cfg_data_path("LEGAL_KEYWORD_TO_SOURCE_DB"),
            "legal_operational_repository": _cfg_data_path("LEGAL_OPERATIONAL_REPOSITORY_DB"),
            "legal_sources_repository": _cfg_data_path("LEGAL_SOURCES_REPOSITORY_DB"),
            "telematico_actions_repository": _cfg_data_path("TELEMATICO_ACTIONS_REPOSITORY_DB"),
            "telematico_capabilities_repository": _cfg_data_path("TELEMATICO_CAPABILITIES_REPOSITORY_DB"),
            "telematico_catalog_snapshot": _cfg_data_path("TELEMATICO_CATALOG_SNAPSHOT_DB"),
            "telematico_catalog_sources_repository": _cfg_data_path("TELEMATICO_CATALOG_SOURCES_REPOSITORY_DB"),
            "telematico_methods_repository": _cfg_data_path("TELEMATICO_METHODS_REPOSITORY_DB"),
            "telematico_monitoring_repository": _cfg_data_path("TELEMATICO_MONITORING_REPOSITORY_DB"),
            "telematico_repository": _cfg_data_path("TELEMATICO_REPOSITORY_JSON"),
            "telematico_rules_repository": _cfg_data_path("TELEMATICO_RULES_REPOSITORY_DB"),
            "telematico_sources_repository": _cfg_data_path("TELEMATICO_SOURCES_REPOSITORY_DB"),
            "telematico_wizard_sections_repository": _cfg_data_path("TELEMATICO_WIZARD_SECTIONS_REPOSITORY_DB"),
            "telematico_wsdl_modules_repository": _cfg_data_path("TELEMATICO_WSDL_MODULES_REPOSITORY_DB"),
            "telematico_xsd_channels_repository": _cfg_data_path("TELEMATICO_XSD_CHANNELS_REPOSITORY_DB"),
            "legal_coverage": _cfg_data_path("LEGAL_COVERAGE_SQLITE_DB"),
            "normative_tables": _cfg_data_path("NORMATIVE_TABLES_DB"),
            "giurisprudenza": _cfg_data_path("GIURISPRUDENZA_DB"),
            "workspace_intelligence": _cfg_data_path("WORKSPACE_INTELLIGENCE_DB"),
            "workflow_agents_runs": _cfg_data_path("WORKFLOW_AGENTS_RUNS_DB"),
            "workflow_agents_metrics": _cfg_data_path("WORKFLOW_AGENTS_METRICS_DB"),
            "workflow_agents_actions": _cfg_data_path("WORKFLOW_AGENTS_ACTIONS_DB"),
            "local_ai": _cfg_data_path("LOCAL_AI_DB"),
            "validation_runs": _cfg_data_path("VALIDATION_RUNS_DB"),
            "template_atti": _cfg_data_path("TEMPLATE_ATTI_DB"),
            "template_repository": _cfg_data_path("TEMPLATE_REPOSITORY_DB"),
            "template_atti_prefs": _cfg_data_path("TEMPLATE_ATTI_PREFS_DB"),
            "studio_timbro": _cfg_data_path("STUDIO_TIMBRO_DB"),
            "redaction_assistant": _cfg_data_path("REDACTION_ASSISTANT_DB"),
            "termini_processuali": _cfg_data_path("TERMINI_PROCESSUALI_DB"),
            "search_index": _cfg_data_path("SEARCH_INDEX"),
            "telematico": _cfg_data_path("TELEMATICO_DB"),
        }

    def _bootstrap_runtime_data_modules() -> dict[str, str]:
        created = bootstrap_moduli_monitorati(_database_paths())
        if created:
            app.logger.info(
                "Bootstrap automatico moduli dati: %s",
                ", ".join(f"{nome}={path}" for nome, path in sorted(created.items())),
            )
        return created

    def get_studio_db(anchor_key: str = "CLIENTI_DB"):
        """
        Restituisce l'istanza StudioDB per il tenant corrente,
        oppure None se PCT_SQLITE_MODE non è attivo.

        Il percorso di studio.db è derivato dalla root dei dati del tenant:
        es. /data/clienti/anagrafica.json -> /data/studio.db
        """
        return get_request_studio_db(_cfg_data_path(anchor_key))

    def get_agenda() -> Agenda:
        if not hasattr(g, "_agenda"):
            g._agenda = Agenda(
                db_path=_cfg_data_path("AGENDA_DB"),
                studio_db=get_studio_db("AGENDA_DB"),
            )
        return g._agenda

    def get_calendar_sync():
        if not hasattr(g, "_calendar_sync"):
            from pct.calendar_sync import GestioneCalendarSync
            g._calendar_sync = GestioneCalendarSync(db_path=_cfg_data_path("CALENDAR_SYNC_DB"))
        return g._calendar_sync

    def get_giurisprudenza():
        if not hasattr(g, "_giurisprudenza"):
            from pct.giurisprudenza import GestioneGiurisprudenza

            g._giurisprudenza = GestioneGiurisprudenza(db_path=_cfg_data_path("GIURISPRUDENZA_DB"))
        return g._giurisprudenza

    def get_clienti() -> GestioneClienti:
        if not hasattr(g, "_clienti"):
            g._clienti = GestioneClienti(
                db_path=_cfg_data_path("CLIENTI_DB"),
                studio_db=get_studio_db("CLIENTI_DB"),
            )
        return g._clienti

    def get_fascicoli() -> GestioneFascicoli:
        if not hasattr(g, "_fascicoli"):
            g._fascicoli = GestioneFascicoli(
                db_path=_cfg_data_path("FASCICOLI_DB"),
                documents_dir=_cfg_data_path("FASCICOLI_DOCS"),
                archive_dir=_cfg_data_path("FASCICOLI_ARCH"),
                studio_db=get_studio_db("FASCICOLI_DB"),
            )
        return g._fascicoli

    def get_practice_engine():
        if not hasattr(g, "_practice_engine"):
            from pct.practice_engine import PracticeEngineRepository

            g._practice_engine = PracticeEngineRepository(
                _cfg_data_path("PRACTICE_ENGINE_DB"),
                # PRACTICE_ENGINE_DB è soltanto il mirror tenant-aware: la
                # fonte di verità SQL è sempre lo studio.db del fascicolo.
                studio_db=get_studio_db("FASCICOLI_DB"),
            )
        return g._practice_engine

    def get_pdp_penale() -> PDPPenaleWorkflowRepository:
        if not hasattr(g, "_pdp_penale_repo"):
            g._pdp_penale_repo = PDPPenaleWorkflowRepository(_cfg_data_path("PDP_PENALE_DB"))
        return g._pdp_penale_repo

    def get_telematico() -> TelematicoWorkflowRepository:
        if not hasattr(g, "_telematico_repo"):
            g._telematico_repo = TelematicoWorkflowRepository(_cfg_data_path("TELEMATICO_DB"))
        return g._telematico_repo

    def get_deposito_guidato():
        if not hasattr(g, "_deposito_guidato"):
            from pct.deposito_guidato import OrchestratoreDepositoGuidato

            g._deposito_guidato = OrchestratoreDepositoGuidato(
                validation_db_path=_cfg_data_path("VALIDATION_RUNS_DB"),
                office_cache_path=app.config.get("UFFICI_GIUDIZIARI_DB", ""),
                pst_wsdl_catalog_zip_path=app.config.get("PST_WSDL_CATALOG_ZIP", ""),
                pst_official_cache_path=app.config.get("PST_OFFICIAL_CACHE", ""),
                pst_catalog_endpoint=app.config.get("PST_SOAP_CATALOGO_UG_ENDPOINT", ""),
                pst_timeout=float(app.config.get("PST_SOAP_TIMEOUT", 8.0) or 8.0),
            )
        return g._deposito_guidato

    def get_workspace_intelligente() -> WorkspaceIntelligenteService:
        if not hasattr(g, "_workspace_intelligente"):
            g._workspace_intelligente = WorkspaceIntelligenteService(
                agenda=get_agenda(),
                scadenziario=get_scadenziario(),
                fascicoli=get_fascicoli(),
                calendar_sync=get_calendar_sync(),
                giurisprudenza=get_giurisprudenza(),
                studio_patron_rule=_studio_patron_rule_from_config(),
                snapshot_path=_cfg_data_path("WORKSPACE_INTELLIGENCE_DB"),
            )
        return g._workspace_intelligente

    def get_config_studio():
        from pct.config_studio import GestioneConfigStudio

        config_path = _cfg_data_path("CONFIG_STUDIO_DB")
        cached_path = getattr(g, "_config_studio_path", "")
        if not hasattr(g, "_config_studio") or cached_path != config_path:
            g._config_studio = GestioneConfigStudio(config_path=config_path)
            g._config_studio_path = config_path
        gs = g._config_studio
        cfg = gs.config
        gs.nome = (
            cfg.studio.nome
            if cfg and hasattr(cfg, "studio") and cfg.studio.nome
            else app.config.get("STUDIO_NOME", "Studio Legale")
        )
        return gs

    def get_messaggi() -> GestioneMessaggi:
        cfg_studio = get_config_studio().config
        smtp_cfg = getattr(cfg_studio, "smtp", None)
        whatsapp_cfg = getattr(cfg_studio, "whatsapp", None)
        studio_cfg = getattr(cfg_studio, "studio", None)
        cfg = ConfigMessaggistica(
            email=ConfigEmail(
                smtp_host=getattr(smtp_cfg, "host", "") or app.config.get("SMTP_HOST", ""),
                smtp_port=getattr(smtp_cfg, "port", 0) or app.config.get("SMTP_PORT", 587),
                username=getattr(smtp_cfg, "username", "") or app.config.get("SMTP_USER", ""),
                password=getattr(smtp_cfg, "password", "") or app.config.get("SMTP_PASS", ""),
                mittente_email=getattr(smtp_cfg, "from_address", "") or app.config.get("SMTP_FROM", ""),
                mittente_nome=getattr(smtp_cfg, "from_name", "")
                or getattr(studio_cfg, "nome", "")
                or app.config.get("SMTP_FROM_NAME", app.config.get("STUDIO_NOME", "Studio Legale")),
            ),
            twilio=ConfigTwilio(
                account_sid=getattr(whatsapp_cfg, "twilio_sid", "") or app.config.get("TWILIO_SID", ""),
                auth_token=getattr(whatsapp_cfg, "twilio_token", "") or app.config.get("TWILIO_TOKEN", ""),
                numero_sms=getattr(whatsapp_cfg, "twilio_numero", "") or app.config.get("TWILIO_NUMERO", ""),
                numero_whatsapp=getattr(whatsapp_cfg, "twilio_numero", "") or app.config.get("TWILIO_NUMERO", ""),
            ),
            studio_nome=getattr(studio_cfg, "nome", "") or app.config.get("STUDIO_NOME", "Studio Legale"),
        )
        return GestioneMessaggi(
            config=cfg,
            db_path=_cfg_data_path("MESSAGGI_DB"),
            studio_db=get_studio_db("MESSAGGI_DB"),
        )

    def get_backup() -> GestioneBackup:
        data_paths = {
            "agenda": _cfg_data_path("AGENDA_DB"),
            "clienti": _cfg_data_path("CLIENTI_DB"),
            "fascicoli": _cfg_data_path("FASCICOLI_DB"),
            "messaggi": _cfg_data_path("MESSAGGI_DB"),
            "documenti": _cfg_data_path("FASCICOLI_DOCS"),
        }
        return GestioneBackup(
            directory_backup=_cfg_data_path("BACKUP_DIR"),
            percorsi_dati=data_paths,
        )

    def get_utenti() -> GestioneUtenti:
        if not hasattr(g, "_utenti"):
            # In modalità multi-tenant, il primo utente globale deve essere SUPERADMIN
            # per poter accedere al pannello /admin/ e creare studi.
            ruolo_default = (
                RuoloUtente.SUPERADMIN
                if app.config.get("MULTI_TENANT")
                else RuoloUtente.AMMINISTRATORE
            )
            auth_db_path = _cfg_data_path("AUTH_DB")
            audit_db_path = _cfg_data_path("AUDIT_DB")
            bootstrap_admin_credentials_path = str(
                Path(auth_db_path).parent / "bootstrap_admin.json"
            )
            platform_studio_db = None if app.config.get("MULTI_TENANT") else get_studio_db("AUTH_DB")
            tenant_slug = str(getattr(g, "tenant_context_slug", "") or "").strip().lower()
            if not tenant_slug:
                tenant = getattr(g, "tenant", None)
                tenant_slug = str(getattr(tenant, "slug", "") or "").strip().lower()
            g._utenti = GestioneUtenti(
                db_path=auth_db_path,
                audit_path=audit_db_path,
                secret_key=app.secret_key,
                ruolo_default=ruolo_default,
                studio_db=platform_studio_db,
                bootstrap_admin_password=app.config.get("BOOTSTRAP_ADMIN_PASSWORD", ""),
                bootstrap_admin_credentials_path=bootstrap_admin_credentials_path,
                tenant_slug_context=tenant_slug,
            )
        return g._utenti

    def get_scadenziario() -> GestioneScadenziario:
        if not hasattr(g, "_scadenziario"):
            scadenziario_path = _cfg_data_path("SCADENZIARIO_DB")
            use_studio_db = not (
                app.testing and Path(scadenziario_path).suffix.lower() == ".json"
            )
            g._scadenziario = GestioneScadenziario(
                db_path=scadenziario_path,
                studio_db=get_studio_db("SCADENZIARIO_DB") if use_studio_db else None,
            )
        return g._scadenziario

    def get_timesheet() -> GestioneTimesheet:
        if not hasattr(g, "_timesheet"):
            g._timesheet = GestioneTimesheet(
                db_path=_cfg_data_path("TIMESHEET_DB"),
                studio_db=get_studio_db("TIMESHEET_DB"),
            )
        return g._timesheet

    def get_crm():
        if not hasattr(g, "_crm_intake"):
            from pct.crm_intake import GestioneCrmIntake

            g._crm_intake = GestioneCrmIntake(db_path=_cfg_data_path("CRM_DB"))
        return g._crm_intake

    def get_ctu():
        if not hasattr(g, "_ctu"):
            from pct.ctu import GestioneCtu

            g._ctu = GestioneCtu(db_path=_cfg_data_path("CTU_DB"))
        return g._ctu

    def get_prima_nota():
        if not hasattr(g, "_prima_nota"):
            from pct.prima_nota import GestionePrimaNota

            g._prima_nota = GestionePrimaNota(db_path=_cfg_data_path("PRIMA_NOTA_DB"))
        return g._prima_nota

    def get_preventivi() -> GestionePreventivi:
        if not hasattr(g, "_preventivi"):
            g._preventivi = GestionePreventivi(
                db_path=_cfg_data_path("PREVENTIVI_DB"),
                studio_db=get_studio_db("PREVENTIVI_DB"),
            )
        return g._preventivi

    def get_fatturazione() -> GestioneFatturazione:
        if not hasattr(g, "_fatturazione"):
            g._fatturazione = GestioneFatturazione(
                db_path=_cfg_data_path("FATTURAZIONE_DB"),
                studio_db=get_studio_db("FATTURAZIONE_DB"),
            )
        return g._fatturazione

    def get_pagamenti() -> GestionePagamenti:
        if not hasattr(g, "_pagamenti"):
            g._pagamenti = GestionePagamenti(
                db_dir=_cfg_data_path("PAGAMENTI_DIR"),
                studio_db=get_studio_db("PAGAMENTI_DIR"),
            )
        return g._pagamenti

    def _resolve_judicial_office_by_code(codice: str) -> dict:
        if not codice:
            return {}
        try:
            from pct.uffici_giudiziari import get_gestore as _get_uffici

            cache_path = app.config.get("UFFICI_GIUDIZIARI_DB") or os.getenv("PCT_UFFICI_DB", "/data/uffici/uffici_giudiziari.json")
            return next((u for u in _get_uffici(cache_path).carica() if u.get("codice") == codice), {}) or {}
        except Exception:
            return {}

    def _studio_patron_rule_from_config():
        cfg = get_config_studio().config.studio
        return regola_patrono_studio(
            "default-studio",
            str(getattr(cfg, "patron_name", "") or "").strip(),
            int(getattr(cfg, "patron_day", 0) or 0),
            int(getattr(cfg, "patron_month", 0) or 0),
        )

    def get_soggetti() -> GestioneSoggetti:
        if not hasattr(g, "_soggetti"):
            g._soggetti = GestioneSoggetti(
                soggetti_path=_cfg_data_path("SOGGETTI_DB"),
                parti_path=_cfg_data_path("SOGGETTI_PARTI_DB"),
                studio_db=get_studio_db("SOGGETTI_DB"),
            )
        return g._soggetti

    def get_indice() -> IndiceRicerca:
        if not hasattr(g, "_indice"):
            g._indice = IndiceRicerca(index_path=_cfg_data_path("SEARCH_INDEX"))
        return g._indice

    def get_trattamenti() -> GestioneTrattamenti:
        if not hasattr(g, "_trattamenti"):
            g._trattamenti = GestioneTrattamenti(
                db_path=_cfg_data_path("PRIVACY_DB"),
                studio_db=get_studio_db("PRIVACY_DB"),
            )
        return g._trattamenti

    def get_condivisioni() -> GestioneCondivisioni:
        if not hasattr(g, "_condivisioni"):
            g._condivisioni = GestioneCondivisioni(
                db_path=_cfg_data_path("CONDIVISIONI_DB"),
                secret_key=app.config["SECRET_KEY"],
            )
        return g._condivisioni

    def cliente_accessibile(id_cliente: str, richiesto: RuoloCondivisione = RuoloCondivisione.LETTURA) -> bool:
        """
        Verifica se l'utente corrente può accedere alla cartella di un cliente.
        - Utenti con permesso globale 'clienti.leggi' -> sempre True
        - Altri -> solo se la cartella è stata condivisa con loro al livello richiesto
        """
        u = g.utente_corrente
        if not u:
            return False
        if u.ha_permesso("clienti.leggi"):
            return True
        return get_condivisioni().ha_accesso(u.id, id_cliente, richiesto)

    def get_database() -> GestioneDatabase:
        _bootstrap_runtime_data_modules()
        return GestioneDatabase(_database_paths())

    def _latest_sqlite_snapshot_path(backup_dir: str) -> str:
        backup_path = Path(backup_dir or "./backup")
        preferred = backup_path / "studio_legale.db"
        if preferred.exists():
            return str(preferred)
        candidates = sorted(
            backup_path.glob("studio_legale*.db"),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
        return str(candidates[0]) if candidates else str(preferred)

    if not is_managed_cloud_runtime():
        _bootstrap_runtime_data_modules()
    else:
        app.logger.info(
            "Runtime cloud gestito: rinvio il bootstrap iniziale dei registri dati al primo uso effettivo."
        )

    # Singleton di sincronizzazione (uno per processo Flask)
    def _resolve_sync_runtime():
        try:
            from web import app as web_app_module

            compat_getter = getattr(web_app_module, "get_gestore", None)
            if callable(compat_getter):
                return compat_getter()
        except Exception:
            pass
        return get_gestore()

    _sync = _resolve_sync_runtime()

    # ---------------------------------------------------------------- hardening browser/session security
    register_security_runtime(app)

    # ---------------------------------------------------------------- auth middleware
    register_auth_runtime(
        app,
        get_utenti=get_utenti,
        bootstrap_runtime_data_modules=_bootstrap_runtime_data_modules,
    )

    def audit(azione: str, risorsa_tipo: str = "", risorsa_id: str = "", dettagli: str = ""):
        """Helper per registrare un evento audit."""
        u = g.utente_corrente
        get_utenti().registra_evento(
            azione=azione,
            id_utente=u.id if u else "",
            username=u.username if u else "anonimo",
            risorsa_tipo=risorsa_tipo,
            risorsa_id=risorsa_id,
            dettagli=dettagli,
            ip=request.remote_addr or "",
        )

    def track_recente(tipo: str, id_: str, titolo: str, url_: str, icona: str = "bi-file"):
        """Aggiorna la cronologia Recenti nella sessione utente (ultimi 5 elementi)."""
        recenti = session.get("recenti", [])
        recenti = [r for r in recenti if not (r["tipo"] == tipo and r["id"] == id_)]
        recenti.insert(0, {"tipo": tipo, "id": id_, "titolo": titolo[:48], "url": url_, "icona": icona})
        session["recenti"] = recenti[:5]

    def sync_pubblica(tipo: str, modulo: str, id_risorsa: str = "", utente: str = ""):
        """Pubblica un evento di sincronizzazione a tutti gli operatori connessi."""
        u = g.utente_corrente
        _sync.pubblica(
            tipo=tipo,
            modulo=modulo,
            id_risorsa=id_risorsa,
            utente=utente or (u.username if u else "sistema"),
        )

    def _audit_and_sync_best_effort(
        *,
        audit_azione: str = "",
        audit_risorsa_tipo: str = "",
        audit_risorsa_id: str = "",
        audit_dettagli: str = "",
        sync_tipo: str = "",
        sync_modulo: str = "",
        sync_id_risorsa: str = "",
    ) -> list[str]:
        """
        Registra audit e sincronizzazione senza bloccare le azioni utente.

        Firma, upload documenti e depositi non devono fallire se il canale
        realtime o il log audit hanno un problema operativo.
        """
        avvisi: list[str] = []
        if audit_azione:
            try:
                audit(
                    audit_azione,
                    audit_risorsa_tipo,
                    audit_risorsa_id,
                    audit_dettagli,
                )
            except Exception as exc:
                app.logger.exception("Errore audit best-effort %s: %s", audit_azione, exc)
                avvisi.append("audit")

        if sync_tipo and sync_modulo:
            try:
                sync_pubblica(sync_tipo, sync_modulo, sync_id_risorsa)
            except Exception as exc:
                app.logger.exception(
                    "Errore sincronizzazione best-effort %s/%s/%s: %s",
                    sync_tipo,
                    sync_modulo,
                    sync_id_risorsa,
                    exc,
                )
                avvisi.append("sync")

        return avvisi

    def _is_no_space_error(error: Exception) -> bool:
        return isinstance(error, OSError) and getattr(error, "errno", None) == errno.ENOSPC

    def _cleanup_partial_signed_variant(gf: GestioneFascicoli, id_fasc: str, id_doc: str, nome_file: str) -> None:
        try:
            fasc = gf.get(id_fasc)
            doc = next((item for item in (getattr(fasc, "documenti", []) or []) if item.id == id_doc), None)
            if not doc:
                return
            current_path = str(doc.percorso or "").strip()
            target_path = str((Path(id_fasc) / Path(nome_file).name).as_posix())
            if not target_path or target_path == current_path:
                return
            orphan = gf.documents_dir / target_path
            if orphan.exists():
                orphan.unlink()
        except Exception:
            app.logger.debug("Pulizia file firmato parziale non riuscita per %s/%s", id_fasc, id_doc)

    def _signature_storage_error_message(error: Exception) -> str:
        if _is_no_space_error(error):
            return (
                "Spazio di archiviazione insufficiente sul server IUSENTRA. "
                "La firma e' stata prodotta ma il server non riesce a salvare una nuova copia del documento."
            )
        return f"Errore tecnico durante il salvataggio del documento firmato: {error}"

    def _salva_documento_firmato_resiliente(
        *,
        gf: GestioneFascicoli,
        id_fasc: str,
        id_doc: str,
        nome_file: str,
        contenuto: bytes,
        hash_contenuto_sha256: str,
        caricato_da: str,
        note: str,
    ) -> list[str]:
        try:
            gf.sostituisci_documento(
                id_fasc=id_fasc,
                id_doc=id_doc,
                nome_file=nome_file,
                contenuto=contenuto,
                hash_contenuto_sha256=hash_contenuto_sha256,
                caricato_da=caricato_da,
                note=note,
            )
            return []
        except OSError as exc:
            if not _is_no_space_error(exc):
                raise
            app.logger.warning(
                "Spazio insufficiente durante il salvataggio firmato %s/%s; attivo fallback compatto.",
                id_fasc,
                id_doc,
            )
            _cleanup_partial_signed_variant(gf, id_fasc, id_doc, nome_file)
            gf.sostituisci_documento(
                id_fasc=id_fasc,
                id_doc=id_doc,
                nome_file=nome_file,
                contenuto=contenuto,
                hash_contenuto_sha256=hash_contenuto_sha256,
                caricato_da=caricato_da,
                note=note,
                preserve_version_snapshot=False,
                reuse_existing_path=True,
            )
            return ["storage_compact"]

    def get_base_url() -> str:
        configured = os.getenv("PCT_BASE_URL", "").rstrip("/")
        if configured:
            return configured
        base = request.host_url.rstrip("/")
        if base.startswith("http://"):
            base = "https://" + base[len("http://") :]
        return base

    return {
        "cfg_data_path": _cfg_data_path,
        "database_paths": _database_paths,
        "bootstrap_runtime_data_modules": _bootstrap_runtime_data_modules,
        "get_studio_db": get_studio_db,
        "get_agenda": get_agenda,
        "get_calendar_sync": get_calendar_sync,
        "get_giurisprudenza": get_giurisprudenza,
        "get_clienti": get_clienti,
        "get_fascicoli": get_fascicoli,
        "get_practice_engine": get_practice_engine,
        "get_pdp_penale": get_pdp_penale,
        "get_telematico": get_telematico,
        "get_deposito_guidato": get_deposito_guidato,
        "get_workspace_intelligente": get_workspace_intelligente,
        "get_config_studio": get_config_studio,
        "get_messaggi": get_messaggi,
        "get_backup": get_backup,
        "get_utenti": get_utenti,
        "get_scadenziario": get_scadenziario,
        "get_timesheet": get_timesheet,
        "get_crm": get_crm,
        "get_ctu": get_ctu,
        "get_prima_nota": get_prima_nota,
        "get_preventivi": get_preventivi,
        "get_fatturazione": get_fatturazione,
        "get_pagamenti": get_pagamenti,
        "resolve_judicial_office_by_code": _resolve_judicial_office_by_code,
        "studio_patron_rule_from_config": _studio_patron_rule_from_config,
        "get_soggetti": get_soggetti,
        "get_indice": get_indice,
        "get_trattamenti": get_trattamenti,
        "get_condivisioni": get_condivisioni,
        "cliente_accessibile": cliente_accessibile,
        "get_database": get_database,
        "latest_sqlite_snapshot_path": _latest_sqlite_snapshot_path,
        "audit": audit,
        "track_recente": track_recente,
        "sync_pubblica": sync_pubblica,
        "sync_manager": _sync,
        "audit_and_sync_best_effort": _audit_and_sync_best_effort,
        "is_no_space_error": _is_no_space_error,
        "cleanup_partial_signed_variant": _cleanup_partial_signed_variant,
        "signature_storage_error_message": _signature_storage_error_message,
        "salva_documento_firmato_resiliente": _salva_documento_firmato_resiliente,
        "get_base_url": get_base_url,
    }
