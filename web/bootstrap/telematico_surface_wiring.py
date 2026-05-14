"""Registrazione delle superfici telematiche e portali."""

from __future__ import annotations

from typing import Any

from flask import Flask

from web.bootstrap.polisweb_routes import register_polisweb_routes
from web.bootstrap.portali_acquisizione_routes import register_portali_acquisizione_routes
from web.bootstrap.telematico_dashboard_routes import register_telematico_dashboard_routes
from web.bootstrap.telematico_local_signer_routes import register_telematico_local_signer_routes
from web.bootstrap.telematico_portali_routes import register_telematico_portali_routes


def register_telematico_surfaces(
    app: Flask,
    *,
    core: dict[str, Any],
    fascicoli: dict[str, Any],
    telematico: dict[str, Any],
    pdp_penale: dict[str, Any],
) -> None:
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
        _normalize_authorized_portale_payload=telematico["normalize_authorized_portale_payload"],
        _importa_o_collega_fascicolo_portale=telematico["importa_o_collega_fascicolo_portale"],
        _importa_file_assistiti_portale=telematico["importa_file_assistiti_portale"],
        _portal_assistant_start=telematico["portal_assistant_start"],
        _portal_assistant_open=telematico["portal_assistant_open"],
        _portal_assistant_watch_downloads=telematico["portal_assistant_watch_downloads"],
        _portal_assistant_status=telematico["portal_assistant_status"],
        _portal_assistant_collect=telematico["portal_assistant_collect"],
        _portal_assistant_close=telematico["portal_assistant_close"],
        _deposito_precheck_assistito=telematico["deposito_precheck_assistito"],
        _deposito_prepara_assistito=telematico["deposito_prepara_assistito"],
        _deposito_assistant_start=telematico["deposito_assistant_start"],
        _deposito_importa_ricevute_assistito=telematico["deposito_importa_ricevute_assistito"],
        _deposito_finalizza_assistito=telematico["deposito_finalizza_assistito"],
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
        portale_demo_mode=telematico["portale_demo_mode"],
        portale_browser_channel_required=telematico["portale_browser_channel_required"],
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
