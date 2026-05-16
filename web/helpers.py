"""
web/helpers.py — Factory functions condivise tra app.py e blueprint.

Ogni funzione usa `current_app` e `g` di Flask, quindi deve essere chiamata
dentro un application context (durante una request o with app.app_context()).

Multi-tenant: se g.data_paths è popolato (dal middleware carica_tenant),
i percorsi dei dati vengono sovrascritti con quelli del tenant corrente.
In assenza di tenant (SUPERADMIN o modalità single-tenant), si usano
i percorsi di default da current_app.config.
"""
from __future__ import annotations
from flask import current_app, g

from pct.agenda import Agenda
from pct.clienti import GestioneClienti
from pct.fascicoli import GestioneFascicoli
from pct.scadenziario import GestioneScadenziario
from pct.auth import GestioneUtenti
from pct.search_index import IndiceRicerca
from pct.wizard_pro import GestioneWizardPro
from pct.legal_intelligence import GestioneLegalIntelligence
from pct.giurisprudenza import GestioneGiurisprudenza
from pct.normative_tables import GestioneTabelleNormative
from pct.calendar_sync import GestioneCalendarSync
from pct.soggetti import GestioneSoggetti
from pct.timesheet import GestioneTimesheet
from pct.time_tracking import GestioneTimeTracking
from pct.applicazioni_repository import get_runtime_applicazioni_repository
from pct.fatturazione import GestioneFatturazione
from pct.pagamenti import GestionePagamenti
from pct.preventivi import GestionePreventivi
from pct.practice_engine import PracticeEngineRepository
from pct.legal_update_pipeline import LegalUpdatePipeline, build_legal_update_pipeline
from web.services.storage_runtime import get_request_storage_runtime, get_request_studio_db


# ---------------------------------------------------------------- helper percorsi tenant-aware

def _cfg(key: str) -> str:
    """
    Restituisce il percorso dati per `key`.
    Se il tenant corrente ha sovrascritta la chiave (g.data_paths), usa quella;
    altrimenti cade su current_app.config.
    """
    paths = getattr(g, "data_paths", {})
    if paths and key in paths:
        if current_app.config.get("MULTI_TENANT") or getattr(g, "multi_tenant_enabled", False):
            from web.services.tenant_isolation_runtime import assert_tenant_data_path

            return assert_tenant_data_path(paths[key], key=key)
        return paths[key]
    if getattr(g, "tenant_context_missing", False):
        raise RuntimeError(
            "Contesto studio non disponibile per la richiesta corrente. "
            "Accesso ai dati bloccato per evitare letture cross-studio."
        )
    return current_app.config[key]


def _studio_db():
    anchor = None
    paths = getattr(g, "data_paths", {})
    if paths and "CLIENTI_DB" in paths:
        anchor = paths["CLIENTI_DB"]
    else:
        anchor = current_app.config.get("CLIENTI_DB")
    if not anchor:
        return None
    return get_request_studio_db(anchor)


# ---------------------------------------------------------------- gestori dati

def get_agenda() -> Agenda:
    return Agenda(db_path=_cfg("AGENDA_DB"), studio_db=_studio_db())


def get_clienti() -> GestioneClienti:
    return GestioneClienti(db_path=_cfg("CLIENTI_DB"), studio_db=_studio_db())


def get_fascicoli() -> GestioneFascicoli:
    return GestioneFascicoli(
        db_path=_cfg("FASCICOLI_DB"),
        documents_dir=_cfg("FASCICOLI_DOCS"),
        archive_dir=_cfg("FASCICOLI_ARCH"),
        studio_db=_studio_db(),
    )


def get_practice_engine() -> PracticeEngineRepository:
    return PracticeEngineRepository(_cfg("PRACTICE_ENGINE_DB"))


def get_scadenziario() -> GestioneScadenziario:
    return GestioneScadenziario(db_path=_cfg("SCADENZIARIO_DB"), studio_db=_studio_db())


def get_timesheet() -> GestioneTimesheet:
    return GestioneTimesheet(db_path=_cfg("TIMESHEET_DB"), studio_db=_studio_db())


def get_time_tracking() -> GestioneTimeTracking:
    return GestioneTimeTracking(db_path=_cfg("TIME_TRACKING_DB"), studio_db=_studio_db())


def get_preventivi() -> GestionePreventivi:
    return GestionePreventivi(db_path=_cfg("PREVENTIVI_DB"), studio_db=_studio_db())


def get_preventivi_readonly() -> GestionePreventivi:
    return GestionePreventivi(
        db_path=_cfg("PREVENTIVI_DB"),
        studio_db=_studio_db(),
        sync_repository_on_init=False,
    )


def get_fatturazione() -> GestioneFatturazione:
    return GestioneFatturazione(db_path=_cfg("FATTURAZIONE_DB"), studio_db=_studio_db())


def get_pagamenti() -> GestionePagamenti:
    return GestionePagamenti(db_dir=_cfg("PAGAMENTI_DIR"), studio_db=_studio_db())


def get_utenti() -> GestioneUtenti:
    tenant_slug = str(getattr(g, "tenant_context_slug", "") or "").strip().lower()
    if not tenant_slug:
        tenant = getattr(g, "tenant", None)
        tenant_slug = str(getattr(tenant, "slug", "") or "").strip().lower()
    return GestioneUtenti(
        db_path=_cfg("AUTH_DB"),
        audit_path=_cfg("AUDIT_DB"),
        secret_key=current_app.secret_key,
        studio_db=_studio_db(),
        bootstrap_admin_password=current_app.config.get("BOOTSTRAP_ADMIN_PASSWORD", ""),
        bootstrap_admin_credentials_path=current_app.config.get(
            "BOOTSTRAP_ADMIN_CREDENTIALS_PATH", ""
        ),
        tenant_slug_context=tenant_slug,
    )


def get_indice() -> IndiceRicerca:
    return IndiceRicerca(index_path=_cfg("SEARCH_INDEX"))


def get_wizard_pro() -> GestioneWizardPro:
    return GestioneWizardPro(db_path=_cfg("WIZARD_PRO_DB"))


def get_legal_intelligence() -> GestioneLegalIntelligence:
    return GestioneLegalIntelligence(
        db_path=str(current_app.config.get("LEGAL_INTELLIGENCE_DB") or _cfg("LEGAL_INTELLIGENCE_DB")),
        normative_db_path=str(current_app.config.get("NORMATIVE_TABLES_DB") or _cfg("NORMATIVE_TABLES_DB")),
    )


def get_legal_update_pipeline() -> LegalUpdatePipeline:
    return build_legal_update_pipeline(
        str(current_app.config.get("LEGAL_INTELLIGENCE_DB") or "./intelligence/motori.json"),
        giurisprudenza_db_path=str(current_app.config.get("GIURISPRUDENZA_DB") or ""),
        ai_base_url=str(
            current_app.config.get("LOCAL_AI_BASE_URL")
            or current_app.config.get("PCT_LOCAL_AI_BASE_URL")
            or ""
        ),
        ai_model=str(
            current_app.config.get("LOCAL_AI_CHAT_MODEL")
            or current_app.config.get("OLLAMA_MODEL")
            or "mistral"
        ),
    )


def get_normative_tables() -> GestioneTabelleNormative:
    return GestioneTabelleNormative(
        db_path=str(current_app.config.get("NORMATIVE_TABLES_DB") or _cfg("NORMATIVE_TABLES_DB"))
    )


def get_giurisprudenza() -> GestioneGiurisprudenza:
    return GestioneGiurisprudenza(db_path=_cfg("GIURISPRUDENZA_DB"))


def get_calendar_sync() -> GestioneCalendarSync:
    return GestioneCalendarSync(db_path=_cfg("CALENDAR_SYNC_DB"))


def get_soggetti() -> GestioneSoggetti:
    return GestioneSoggetti(
        soggetti_path=_cfg("SOGGETTI_DB"),
        parti_path=_cfg("SOGGETTI_PARTI_DB"),
    )


def get_applicazioni_repository():
    return get_runtime_applicazioni_repository(anchor_path=_cfg("STUDIO_CONFIG"))


def storage_runtime_corrente() -> dict:
    return get_request_storage_runtime(_cfg("CLIENTI_DB")).to_dict()


# ---------------------------------------------------------------- tenant corrente

def tenant_corrente():
    """Restituisce lo StudioLegale del tenant corrente, o None."""
    return g.get("tenant")


def studio_nome() -> str:
    """Nome studio: dal tenant corrente oppure dalla config globale."""
    t = tenant_corrente()
    if t:
        return t.nome
    return current_app.config.get("STUDIO_NOME", "IUSENTRA")


# ---------------------------------------------------------------- auth API

def utente_corrente():
    """Restituisce l'utente corrente dalla request o None."""
    return g.get("utente_corrente")


# ---------------------------------------------------------------- paginazione

def pagina(lista: list, page: int = 1, per_page: int = 20) -> dict:
    """Restituisce un dict paginato compatibile con il formato API v1."""
    per_page = max(1, min(int(per_page), 100))
    page = max(1, int(page))
    total = len(lista)
    start = (page - 1) * per_page
    return {
        "data": lista[start: start + per_page],
        "meta": {
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": max(1, (total + per_page - 1) // per_page),
        },
    }
