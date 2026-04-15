"""Wiring centrale dei moduli Flask estratto da web.app."""

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
from web.bootstrap.deposito_routes import register_deposito_routes
from web.bootstrap.error_handlers import register_error_handlers
from web.bootstrap.export_routes import register_export_routes
from web.bootstrap.fascicoli_ai_routes import register_fascicoli_ai_routes
from web.bootstrap.fascicoli_core_routes import register_fascicoli_core_routes
from web.bootstrap.fascicoli_document_routes import register_fascicoli_document_routes
from web.bootstrap.fascicoli_editor_routes import register_fascicoli_editor_routes
from web.bootstrap.fascicoli_management_routes import register_fascicoli_management_routes
from web.bootstrap.fascicoli_pdp_routes import register_fascicoli_pdp_routes
from web.bootstrap.fascicoli_signature_routes import register_fascicoli_signature_routes
from web.bootstrap.health_routes import register_health_routes
from web.bootstrap.messages_routes import register_messages_routes
from web.bootstrap.polisweb_routes import register_polisweb_routes
from web.bootstrap.portali_acquisizione_routes import register_portali_acquisizione_routes
from web.bootstrap.privacy_routes import register_privacy_routes
from web.bootstrap.pwa_routes import register_pwa_routes
from web.bootstrap.reference_lookup_routes import register_reference_lookup_routes
from web.bootstrap.register_blueprints import register_blueprints
from web.bootstrap.scadenziario_routes import register_scadenziario_routes
from web.bootstrap.search_routes import register_search_routes
from web.bootstrap.soggetti_routes import register_soggetti_routes
from web.bootstrap.sync_runtime_routes import register_sync_runtime_routes
from web.bootstrap.tariffario_routes import register_tariffario_routes
from web.bootstrap.telematico_dashboard_routes import register_telematico_dashboard_routes
from web.bootstrap.telematico_local_signer_routes import register_telematico_local_signer_routes
from web.bootstrap.telematico_portali_routes import register_telematico_portali_routes
from web.bootstrap.template_runtime import register_template_runtime
from web.bootstrap.workspace_routes import register_workspace_routes


def register_app_wiring(
    app: Flask,
    *,
    app_version: str,
    core: dict[str, Any],
    fascicoli: dict[str, Any],
    telematico: dict[str, Any],
    pdp_penale: dict[str, Any],
    ocr_runtime: Any,
    get_local_ai_service: Callable[[], Any],
) -> None:
    """Registra template context, route verticali e blueprint applicativi."""

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
    register_dashboard_routes(
        app,
        get_agenda=core["get_agenda"],
        get_scadenziario=core["get_scadenziario"],
        get_fascicoli=core["get_fascicoli"],
        get_clienti=core["get_clienti"],
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
        get_config_studio=core["get_config_studio"],
        cliente_accessibile=core["cliente_accessibile"],
        track_recente=core["track_recente"],
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
        accoda_ocr=ocr_runtime.enqueue,
        ocr_queue=ocr_runtime.queue,
        ocr_stats=ocr_runtime.stats,
        ocr_stats_lock=ocr_runtime.stats_lock,
    )
    register_sync_runtime_routes(
        app,
        sync_manager=core["sync_manager"],
        get_fascicoli=core["get_fascicoli"],
        get_utenti=core["get_utenti"],
        audit=core["audit"],
    )
    register_fascicoli_management_routes(
        app,
        get_fascicoli=core["get_fascicoli"],
        get_clienti=core["get_clienti"],
        get_scadenziario=core["get_scadenziario"],
        get_agenda=core["get_agenda"],
        get_soggetti=core["get_soggetti"],
        get_config_studio=core["get_config_studio"],
        cliente_accessibile=core["cliente_accessibile"],
        audit=core["audit"],
        sync_pubblica=core["sync_pubblica"],
        build_responsabile_conformita_fascicolo=fascicoli["build_responsabile_conformita_fascicolo"],
        fascicolo_form_correction_context=fascicoli["fascicolo_form_correction_context"],
    )
    register_fascicoli_document_routes(
        app,
        get_fascicoli=core["get_fascicoli"],
        audit=core["audit"],
        salva_documento_fascicolo=fascicoli["salva_documento_fascicolo"],
        portale_ufficiale_label=fascicoli["portale_ufficiale_label"],
        espandi_file_importato_portale=fascicoli["espandi_file_importato_portale"],
        pst_import_dir_for_fascicolo=fascicoli["pst_import_dir_for_fascicolo"],
        leggi_staging_documenti_portale=fascicoli["leggi_staging_documenti_portale"],
        salva_albero_originale_documenti_portale=fascicoli["salva_albero_originale_documenti_portale"],
        importa_documenti_portale_items=fascicoli["importa_documenti_portale_items"],
        decode_portale_downloaded_items=fascicoli["decode_portale_downloaded_items"],
        decrypt_doc=fascicoli["decrypt_doc"],
        firma_payload_corrente_o_sibling=fascicoli["firma_payload_corrente_o_sibling"],
        estrai_contenuto_p7m_per_preview=fascicoli["estrai_contenuto_p7m_per_preview"],
        nome_preview_documento=fascicoli["nome_preview_documento"],
        mime_preview_documento=fascicoli["mime_preview_documento"],
        payload_preview_da_versioni_documento=fascicoli["payload_preview_da_versioni_documento"],
        applica_timbro_firma_visibile=fascicoli["applica_timbro_firma_visibile"],
    )
    register_fascicoli_editor_routes(
        app,
        get_fascicoli=core["get_fascicoli"],
        audit=core["audit"],
        decrypt_doc=fascicoli["decrypt_doc"],
        encrypt_doc=fascicoli["encrypt_doc"],
        accoda_ocr=ocr_runtime.enqueue,
    )
    register_fascicoli_signature_routes(
        app,
        get_fascicoli=core["get_fascicoli"],
        get_config_studio=core["get_config_studio"],
        decrypt_doc=fascicoli["decrypt_doc"],
        encrypt_doc=fascicoli["encrypt_doc"],
        salva_documento_firmato_resiliente=core["salva_documento_firmato_resiliente"],
        audit_and_sync_best_effort=core["audit_and_sync_best_effort"],
        signature_storage_error_message=core["signature_storage_error_message"],
        normalizza_modalita_firma_visibile=fascicoli["normalizza_modalita_firma_visibile"],
        luogo_timbro_firma_visibile=fascicoli["luogo_timbro_firma_visibile"],
        audit=core["audit"],
    )
    register_tariffario_routes(app)
    register_deposito_routes(
        app,
        get_fascicoli=core["get_fascicoli"],
        get_config_studio=core["get_config_studio"],
        audit=core["audit"],
        sync_pubblica=core["sync_pubblica"],
        run_deposito_validation=fascicoli["run_deposito_validation"],
        infer_canale_deposito=fascicoli["infer_canale_deposito"],
        resolve_ufficio_destinatario=fascicoli["resolve_ufficio_destinatario"],
        deposito_correction_context=fascicoli["deposito_correction_context"],
        luogo_timbro_firma_visibile=fascicoli["luogo_timbro_firma_visibile"],
        polis_demo_mode=telematico["polis_demo_mode"],
    )
    register_portali_acquisizione_routes(
        app,
        get_fascicoli=core["get_fascicoli"],
        _spec_portale_acquisizione=telematico["spec_portale_acquisizione"],
        _pdp_penale_workspace_url_for_fascicolo=telematico["pdp_penale_workspace_url_for_fascicolo_early"],
        _build_access_status_payload=telematico["build_access_status_payload"],
        _search_fascicoli_portale_server=telematico["search_fascicoli_portale_server"],
        _preview_documenti_portale_server=telematico["preview_documenti_portale_server"],
        _build_portale_preview=telematico["build_portale_preview"],
        _coerce_import_options=telematico["coerce_import_options"],
        _coerce_mapping=telematico["coerce_mapping"],
        _analyze_portale_import=telematico["analyze_portale_import"],
        _importa_o_collega_fascicolo_portale=telematico["importa_o_collega_fascicolo_portale"],
    )
    register_telematico_dashboard_routes(
        app,
        get_fascicoli=core["get_fascicoli"],
        get_telematico=core["get_telematico"],
        _backfill_telematico_from_existing_fascicoli=telematico["backfill_telematico_from_existing_fascicoli"],
        _build_access_status_payload=telematico["build_access_status_payload"],
        _telematico_dashboard_warning_message=telematico["telematico_dashboard_warning_message"],
    )
    register_telematico_local_signer_routes(
        app,
        local_signer_python_name=telematico["local_signer_python_name"],
        local_ai_bridge_source_path=telematico["local_ai_bridge_source_path"],
        local_ai_bridge_python_name=telematico["local_ai_bridge_python_name"],
        local_ai_lex_context_source_path=telematico["local_ai_lex_context_source_path"],
        local_ai_lex_context_python_name=telematico["local_ai_lex_context_python_name"],
        local_signer_visible_signature_source_path=telematico["local_signer_visible_signature_source_path"],
        local_signer_visible_signature_python_name=telematico["local_signer_visible_signature_python_name"],
        local_signer_uffici_path=telematico["local_signer_uffici_path"],
        local_signer_windows_cmd_path=telematico["local_signer_windows_cmd_path"],
        local_signer_windows_cmd_name=telematico["local_signer_windows_cmd_name"],
        local_signer_windows_exe_path=telematico["local_signer_windows_exe_path"],
        local_signer_windows_exe_name=telematico["local_signer_windows_exe_name"],
        local_signer_windows_offline_ps1_path=telematico["local_signer_windows_offline_ps1_path"],
        local_signer_windows_offline_ps1_name=telematico["local_signer_windows_offline_ps1_name"],
        render_local_signer_windows_ps1=telematico["render_local_signer_windows_ps1"],
        local_signer_windows_ps1_name=telematico["local_signer_windows_ps1_name"],
        local_signer_macos_installer_path=telematico["local_signer_macos_installer_path"],
        local_signer_macos_name=telematico["local_signer_macos_name"],
        render_local_signer_macos_command=telematico["render_local_signer_macos_command"],
        local_signer_linux_installer_path=telematico["local_signer_linux_installer_path"],
        local_signer_linux_name=telematico["local_signer_linux_name"],
        render_local_signer_linux_sh=telematico["render_local_signer_linux_sh"],
        get_base_url=core["get_base_url"],
    )
    register_polisweb_routes(
        app,
        get_fascicoli=core["get_fascicoli"],
        get_clienti=core["get_clienti"],
        get_soggetti=core["get_soggetti"],
        audit=core["audit"],
        polis_auth_mode=telematico["polis_auth_mode"],
        polis_demo_mode=telematico["polis_demo_mode"],
        polis_cert_preferences=telematico["polis_cert_preferences"],
    )
    register_telematico_portali_routes(
        app,
        get_fascicoli=core["get_fascicoli"],
        get_clienti=core["get_clienti"],
        polis_demo_mode=telematico["polis_demo_mode"],
        portale_local_channel_enabled=telematico["portale_local_channel_enabled"],
        portale_browser_guided_message=telematico["portale_browser_guided_message"],
        is_portale_dns_error=telematico["is_portale_dns_error"],
        codice_fiscale_avvocato_portale=telematico["codice_fiscale_avvocato_portale"],
        serialize_portale_search_item=telematico["serialize_portale_search_item"],
        build_portale_preview=telematico["build_portale_preview"],
        find_exact_fascicolo_locale_portale=telematico["find_exact_fascicolo_locale_portale"],
        sync_existing_fascicolo_from_portale=telematico["sync_existing_fascicolo_from_portale"],
        register_direct_portale_import_sync=telematico["register_direct_portale_import_sync"],
    )
    register_reference_lookup_routes(app, audit=core["audit"])
    register_fascicoli_core_routes(
        app,
        get_fascicoli=core["get_fascicoli"],
        get_clienti=core["get_clienti"],
        get_agenda=core["get_agenda"],
        get_scadenziario=core["get_scadenziario"],
        get_soggetti=core["get_soggetti"],
        get_workspace_intelligente=core["get_workspace_intelligente"],
        get_config_studio=core["get_config_studio"],
        sync_pubblica=core["sync_pubblica"],
        track_recente=core["track_recente"],
        build_responsabile_conformita_fascicolo=fascicoli["build_responsabile_conformita_fascicolo"],
        build_fascicolo_workspace=fascicoli["build_fascicolo_workspace"],
        fascicolo_form_correction_context=fascicoli["fascicolo_form_correction_context"],
        pst_import_dir_for_fascicolo=fascicoli["pst_import_dir_for_fascicolo"],
        pst_import_pending_count=fascicoli["pst_import_pending_count"],
        catalogo_documenti_portale_fascicolo=fascicoli["catalogo_documenti_portale_fascicolo"],
        gruppa_catalogo_documenti_portale=fascicoli["gruppa_catalogo_documenti_portale"],
        portale_ufficiale_label=fascicoli["portale_ufficiale_label"],
        pdp_penale_summary_for_fascicolo=pdp_penale["pdp_penale_summary_for_fascicolo"],
        luogo_timbro_firma_visibile=fascicoli["luogo_timbro_firma_visibile"],
    )
    register_fascicoli_pdp_routes(
        app,
        get_fascicoli=core["get_fascicoli"],
        get_clienti=core["get_clienti"],
        get_pdp_penale=core["get_pdp_penale"],
        get_config_studio=core["get_config_studio"],
        audit=core["audit"],
        sync_pubblica=core["sync_pubblica"],
        require_pdp_penale_fascicolo=pdp_penale["require_pdp_penale_fascicolo"],
        require_pdp_penale_case=pdp_penale["require_pdp_penale_case"],
        pdp_penale_build_workspace=pdp_penale["pdp_penale_build_workspace"],
        pdp_penale_case_defaults=pdp_penale["pdp_penale_case_defaults"],
        pdp_penale_int=pdp_penale["pdp_penale_int"],
        pdp_penale_float=pdp_penale["pdp_penale_float"],
        pdp_penale_bool=pdp_penale["pdp_penale_bool"],
        pdp_penale_request_reference=pdp_penale["pdp_penale_request_reference"],
        pdp_penale_primary_access_request=pdp_penale["pdp_penale_primary_access_request"],
        pdp_penale_access_status_from_request_status=pdp_penale["pdp_penale_access_status_from_request_status"],
        pdp_penale_local_documents=pdp_penale["pdp_penale_local_documents"],
        pdp_penale_module_documents_enriched=pdp_penale["pdp_penale_module_documents_enriched"],
        pdp_penale_generate_request_pdf=pdp_penale["pdp_penale_generate_request_pdf"],
        pdp_penale_find_case_local_document=pdp_penale["pdp_penale_find_case_local_document"],
        pdp_penale_sync_case_mailbox=pdp_penale["pdp_penale_sync_case_mailbox"],
        pdp_penale_import_download_items=pdp_penale["pdp_penale_import_download_items"],
        pdp_penale_status_label=pdp_penale["pdp_penale_status_label"],
        decrypt_doc=fascicoli["decrypt_doc"],
        resolve_ufficio_destinatario=fascicoli["resolve_ufficio_destinatario"],
        polis_demo_mode=telematico["polis_demo_mode"],
        salva_documento_fascicolo=fascicoli["salva_documento_fascicolo"],
        espandi_file_importato_portale=fascicoli["espandi_file_importato_portale"],
        pst_import_dir_for_fascicolo=fascicoli["pst_import_dir_for_fascicolo"],
        leggi_staging_documenti_portale=fascicoli["leggi_staging_documenti_portale"],
        archivia_staging_documenti_portale=fascicoli["archivia_staging_documenti_portale"],
    )
    register_blueprints(app)
