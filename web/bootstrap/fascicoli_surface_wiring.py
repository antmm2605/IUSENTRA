"""Registrazione delle superfici fascicoli/documenti/deposito."""

from __future__ import annotations

from typing import Any

from flask import Flask

from web.bootstrap.deposito_routes import register_deposito_routes
from web.bootstrap.fascicoli_core_routes import register_fascicoli_core_routes
from web.bootstrap.fascicoli_document_routes import register_fascicoli_document_routes
from web.bootstrap.fascicoli_editor_routes import register_fascicoli_editor_routes
from web.bootstrap.fascicoli_management_routes import register_fascicoli_management_routes
from web.bootstrap.fascicoli_pdp_routes import register_fascicoli_pdp_routes
from web.bootstrap.fascicoli_signature_routes import register_fascicoli_signature_routes
from web.bootstrap.reference_lookup_routes import register_reference_lookup_routes
from web.bootstrap.tariffario_routes import register_tariffario_routes


def register_fascicoli_surfaces(
    app: Flask,
    *,
    core: dict[str, Any],
    fascicoli: dict[str, Any],
    telematico: dict[str, Any],
    pdp_penale: dict[str, Any],
    ocr_runtime: Any,
) -> None:
    register_fascicoli_management_routes(
        app,
        get_fascicoli=core["get_fascicoli"],
        get_clienti=core["get_clienti"],
        get_preventivi=core["get_preventivi"],
        get_fatturazione=core["get_fatturazione"],
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
        get_indice=core["get_indice"],
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
    register_reference_lookup_routes(app, audit=core["audit"])
    register_fascicoli_core_routes(
        app,
        get_fascicoli=core["get_fascicoli"],
        get_clienti=core["get_clienti"],
        get_agenda=core["get_agenda"],
        get_scadenziario=core["get_scadenziario"],
        get_soggetti=core["get_soggetti"],
        get_timesheet=core["get_timesheet"],
        get_preventivi=core["get_preventivi"],
        get_fatturazione=core["get_fatturazione"],
        get_indice=core["get_indice"],
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
