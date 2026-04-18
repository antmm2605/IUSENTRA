"""Registrazione delle superfici core dell'applicazione web."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from flask import Flask

from pct.agenda import StatoAppuntamento, TipoAppuntamento
from pct.auth import DESCRIZIONI_RUOLI, RuoloUtente
from pct.clienti import StatoCliente, TipoCliente
from pct.condivisione import RuoloCondivisione
from pct.fascicoli import EsitoAttivita, StatoFascicolo, TipoAttivita, TipoFascicolo
from pct.ocr import estensione_supportata as ocr_supportato
from web.bootstrap.admin_database_routes import register_admin_database_routes
from web.bootstrap.auth_management_routes import register_auth_management_routes
from web.bootstrap.backup_routes import register_backup_routes
from web.bootstrap.calendar_routes import register_calendar_routes
from web.bootstrap.checklist_routes import register_checklist_routes
from web.bootstrap.clienti_routes import register_clienti_routes
from web.bootstrap.clienti_workspace_routes import register_clienti_workspace_routes
from web.bootstrap.condivisioni_routes import register_condivisioni_routes
from web.bootstrap.dashboard_routes import register_dashboard_routes
from web.bootstrap.error_handlers import register_error_handlers
from web.bootstrap.export_routes import register_export_routes
from web.bootstrap.fascicoli_ai_routes import register_fascicoli_ai_routes
from web.bootstrap.health_routes import register_health_routes
from web.bootstrap.lex_operational_routes import register_lex_operational_routes
from web.bootstrap.messages_routes import register_messages_routes
from web.bootstrap.privacy_routes import register_privacy_routes
from web.bootstrap.pwa_routes import register_pwa_routes
from web.bootstrap.scadenziario_routes import register_scadenziario_routes
from web.bootstrap.search_routes import register_search_routes
from web.bootstrap.soggetti_routes import register_soggetti_routes
from web.bootstrap.sync_runtime_routes import register_sync_runtime_routes
from web.bootstrap.template_runtime import register_template_runtime
from web.bootstrap.timesheet_routes import register_timesheet_routes
from web.bootstrap.workspace_routes import register_workspace_routes


def register_core_surfaces(
    app: Flask,
    *,
    app_version: str,
    core: dict[str, Any],
    fascicoli: dict[str, Any],
    ocr_runtime: Any,
    get_local_ai_service: Callable[[], Any],
) -> None:
    register_template_runtime(
        app,
        template_symbols={
            "TipoAppuntamento": TipoAppuntamento,
            "StatoAppuntamento": StatoAppuntamento,
            "TipoCliente": TipoCliente,
            "StatoCliente": StatoCliente,
            "TipoFascicolo": TipoFascicolo,
            "StatoFascicolo": StatoFascicolo,
            "TipoAttivita": TipoAttivita,
            "EsitoAttivita": EsitoAttivita,
            "RuoloUtente": RuoloUtente,
            "DESCRIZIONI_RUOLI": DESCRIZIONI_RUOLI,
            "RuoloCondivisione": RuoloCondivisione,
        },
        app_version=app_version,
        connected_operators=lambda: core["sync_manager"].n_connessi,
    )
    register_pwa_routes(app)
    register_error_handlers(app)
    register_auth_management_routes(app, get_utenti=core["get_utenti"], audit=core["audit"])
    register_scadenziario_routes(
        app,
        get_agenda=core["get_agenda"],
        get_scadenziario=core["get_scadenziario"],
        get_fascicoli=core["get_fascicoli"],
        get_utenti=core["get_utenti"],
        get_config_studio=core["get_config_studio"],
        _studio_patron_rule_from_config=core["studio_patron_rule_from_config"],
        _resolve_judicial_office_by_code=core["resolve_judicial_office_by_code"],
        audit=core["audit"],
        sync_pubblica=core["sync_pubblica"],
    )
    register_workspace_routes(
        app,
        get_workspace_intelligente=core["get_workspace_intelligente"],
        get_local_ai_service=get_local_ai_service,
    )
    register_lex_operational_routes(
        app,
        get_workspace_intelligente=core["get_workspace_intelligente"],
        get_fascicoli=core["get_fascicoli"],
        get_telematico=core["get_telematico"],
    )
    register_dashboard_routes(
        app,
        get_agenda=core["get_agenda"],
        get_scadenziario=core["get_scadenziario"],
        get_fascicoli=core["get_fascicoli"],
        get_clienti=core["get_clienti"],
        get_timesheet=core["get_timesheet"],
        get_condivisioni=core["get_condivisioni"],
        get_workspace_intelligente=core["get_workspace_intelligente"],
        get_calendar_sync=core["get_calendar_sync"],
        audit=core["audit"],
        sync_pubblica=core["sync_pubblica"],
        track_recente=core["track_recente"],
    )
    register_fascicoli_ai_routes(
        app,
        get_fascicoli=core["get_fascicoli"],
        get_agenda=core["get_agenda"],
        get_scadenziario=core["get_scadenziario"],
        get_workspace_intelligente=core["get_workspace_intelligente"],
        get_local_ai_service=get_local_ai_service,
        cfg_data_path=core["cfg_data_path"],
        build_fascicolo_workspace=fascicoli["build_fascicolo_workspace"],
    )
    register_admin_database_routes(
        app,
        get_database=core["get_database"],
        audit=core["audit"],
        latest_sqlite_snapshot_path=core["latest_sqlite_snapshot_path"],
        cfg_data_path=core["cfg_data_path"],
    )
    register_privacy_routes(
        app,
        get_trattamenti=core["get_trattamenti"],
        get_clienti=core["get_clienti"],
        get_fascicoli=core["get_fascicoli"],
        get_utenti=core["get_utenti"],
        audit=core["audit"],
    )
    register_calendar_routes(
        app,
        cfg_data_path=core["cfg_data_path"],
        get_agenda=core["get_agenda"],
        get_scadenziario=core["get_scadenziario"],
        get_calendar_sync=core["get_calendar_sync"],
    )
    register_checklist_routes(
        app,
        get_fascicoli=core["get_fascicoli"],
        get_config_studio=core["get_config_studio"],
        encrypt_doc=fascicoli["encrypt_doc"],
        audit=core["audit"],
    )
    register_soggetti_routes(
        app,
        get_soggetti=core["get_soggetti"],
        get_clienti=core["get_clienti"],
        get_fascicoli=core["get_fascicoli"],
        audit=core["audit"],
    )
    register_messages_routes(
        app,
        get_messaggi=core["get_messaggi"],
        get_clienti=core["get_clienti"],
    )
    register_clienti_routes(
        app,
        get_clienti=core["get_clienti"],
        get_condivisioni=core["get_condivisioni"],
        get_fascicoli=core["get_fascicoli"],
        get_agenda=core["get_agenda"],
        cliente_accessibile=core["cliente_accessibile"],
        track_recente=core["track_recente"],
        sync_pubblica=core["sync_pubblica"],
        audit=core["audit"],
    )
    register_clienti_workspace_routes(
        app,
        get_clienti=core["get_clienti"],
        get_fascicoli=core["get_fascicoli"],
        get_agenda=core["get_agenda"],
        get_messaggi=core["get_messaggi"],
        get_scadenziario=core["get_scadenziario"],
        get_timesheet=core["get_timesheet"],
        get_config_studio=core["get_config_studio"],
        cliente_accessibile=core["cliente_accessibile"],
        track_recente=core["track_recente"],
        audit=core["audit"],
    )
    register_timesheet_routes(
        app,
        get_timesheet=core["get_timesheet"],
        get_clienti=core["get_clienti"],
        get_fascicoli=core["get_fascicoli"],
        audit=core["audit"],
    )
    register_condivisioni_routes(
        app,
        get_condivisioni=core["get_condivisioni"],
        get_clienti=core["get_clienti"],
        get_fascicoli=core["get_fascicoli"],
        get_utenti=core["get_utenti"],
        get_messaggi=core["get_messaggi"],
        cliente_accessibile=core["cliente_accessibile"],
        audit=core["audit"],
        sync_manager=core["sync_manager"],
    )
    register_backup_routes(app, get_backup=core["get_backup"])
    register_health_routes(
        app,
        get_clienti=core["get_clienti"],
        get_fascicoli=core["get_fascicoli"],
        get_agenda=core["get_agenda"],
        get_scadenziario=core["get_scadenziario"],
    )
    register_export_routes(
        app,
        get_clienti=core["get_clienti"],
        get_fascicoli=core["get_fascicoli"],
        get_scadenziario=core["get_scadenziario"],
        audit=core["audit"],
    )
    register_search_routes(
        app,
        get_indice=core["get_indice"],
        get_clienti=core["get_clienti"],
        get_fascicoli=core["get_fascicoli"],
        get_agenda=core["get_agenda"],
        get_scadenziario=core["get_scadenziario"],
        audit=core["audit"],
        ocr_supportato=ocr_supportato,
        ocr_runtime=ocr_runtime,
    )
    register_sync_runtime_routes(
        app,
        sync_manager=core["sync_manager"],
        get_fascicoli=core["get_fascicoli"],
        get_utenti=core["get_utenti"],
        audit=core["audit"],
    )
