"""Assemblaggio dei runtime applicativi per i profili web IUSENTRA."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from flask import Flask

from pct import __version__ as APP_VERSION
from pct.installation_packs import bootstrap_pack_governance
from pct.runtime_env import is_managed_cloud_runtime
from pct.tenant import GestioneTenant
from web.services.core_runtime import build_core_runtime
from web.services.document_crypto import decrypt_doc, encrypt_doc
from web.services.fascicoli_runtime import build_fascicoli_runtime
from web.services.ocr_runtime import build_ocr_runtime
from web.services.pdp_penale_runtime import build_pdp_penale_runtime
from web.services.telematico_runtime import build_telematico_runtime
from web.services.tenant_legacy_bootstrap import bootstrap_legacy_tenant_runtime_data


@dataclass(slots=True)
class ApplicationRuntimeBundle:
    """Bundle dei runtime costruiti durante il bootstrap dell'applicazione."""

    scheduler_only: bool
    core: dict[str, Any]
    ocr_runtime: Any | None = None
    fascicoli: dict[str, Any] = field(default_factory=dict)
    telematico: dict[str, Any] = field(default_factory=dict)
    pdp_penale: dict[str, Any] = field(default_factory=dict)


def build_application_runtime_bundle(
    app: Flask,
    cfg: dict[str, Any],
) -> ApplicationRuntimeBundle:
    """Costruisce i runtime del profilo web completo o del worker scheduler."""

    core = build_core_runtime(app, cfg)
    scheduler_only = bool(app.config.get("PCT_SCHEDULER_WORKER"))
    if scheduler_only:
        return ApplicationRuntimeBundle(
            scheduler_only=True,
            core=core,
        )

    startup_governance_enabled = not is_managed_cloud_runtime()

    if app.config.get("MULTI_TENANT") and startup_governance_enabled:
        try:
            GestioneTenant(app.config["TENANTS_REGISTRY"]).sync_user_directory(
                secret_key=app.secret_key,
                reconcile_storage=False,
            )
        except Exception as exc:
            app.logger.exception("Errore sync tenant_user_directory in avvio: %s", exc)

    if startup_governance_enabled:
        try:
            bootstrap_pack_governance(
                app_root=Path(__file__).resolve().parents[2],
                registry_path=str(app.config.get("TENANTS_REGISTRY", "./data/tenants.json")),
                app_version=APP_VERSION,
            )
        except Exception as exc:
            app.logger.exception("Errore bootstrap Product Pack / Studio Local Pack: %s", exc)

        try:
            bootstrap_report = bootstrap_legacy_tenant_runtime_data(app)
            if bootstrap_report.get("copied") or bootstrap_report.get("sqlite_migrated"):
                app.logger.info(
                    "Bootstrap legacy tenant in avvio per %s: copied=%s sqlite=%s",
                    bootstrap_report.get("target_slug", ""),
                    ",".join(sorted(bootstrap_report.get("copied", {}).keys())) or "-",
                    bootstrap_report.get("sqlite_migrated", False),
                )
        except Exception as exc:
            app.logger.exception("Errore bootstrap legacy tenant in avvio: %s", exc)
    else:
        app.logger.info(
            "Runtime cloud gestito: rinvio bootstrap tenant e governance pesante dopo il primo avvio."
        )

    ocr_runtime = build_ocr_runtime(
        queue_db_path=app.config.get("OCR_QUEUE_DB"),
        search_index_path=str(app.config.get("SEARCH_INDEX", "")),
    )
    app.extensions["ocr_runtime"] = ocr_runtime
    fascicoli = build_fascicoli_runtime(
        app,
        get_deposito_guidato=core["get_deposito_guidato"],
        get_config_studio=core["get_config_studio"],
        get_utenti=core["get_utenti"],
        audit=core["audit"],
        sync_pubblica=core["sync_pubblica"],
        accoda_ocr=ocr_runtime.enqueue,
        encrypt_doc=encrypt_doc,
        decrypt_doc=decrypt_doc,
    )

    telematico: dict[str, Any] = {}
    pdp_penale = build_pdp_penale_runtime(
        app,
        get_pdp_penale=core["get_pdp_penale"],
        get_fascicoli=core["get_fascicoli"],
        get_config_studio=core["get_config_studio"],
        get_clienti=core["get_clienti"],
        audit=core["audit"],
        sync_pubblica=core["sync_pubblica"],
        resolve_ufficio_destinatario=fascicoli["resolve_ufficio_destinatario"],
        polis_demo_mode=lambda: telematico.get("polis_demo_mode", lambda: True)(),
        salva_documento_fascicolo=fascicoli["salva_documento_fascicolo"],
        espandi_file_importato_portale=fascicoli["espandi_file_importato_portale"],
        pst_import_dir_for_fascicolo=fascicoli["pst_import_dir_for_fascicolo"],
        leggi_staging_documenti_portale=fascicoli["leggi_staging_documenti_portale"],
        archivia_staging_documenti_portale=fascicoli["archivia_staging_documenti_portale"],
        normalizza_nome_match_portale=fascicoli["normalizza_nome_match_portale"],
        fascicolo_text=fascicoli["fascicolo_text"],
    )
    telematico = build_telematico_runtime(
        app,
        cfg_data_path=core["cfg_data_path"],
        get_config_studio=core["get_config_studio"],
        get_pdp_penale=core["get_pdp_penale"],
        get_telematico=core["get_telematico"],
        get_fascicoli=core["get_fascicoli"],
        get_clienti=core["get_clienti"],
        get_soggetti=core["get_soggetti"],
        get_scadenziario=core["get_scadenziario"],
        audit=core["audit"],
        sync_pubblica=core["sync_pubblica"],
        normalizza_nome_match_portale=fascicoli["normalizza_nome_match_portale"],
        tipo_documento_da_item_portale=fascicoli["tipo_documento_da_item_portale"],
        salva_documento_fascicolo=fascicoli["salva_documento_fascicolo"],
        salva_albero_originale_documenti_portale=fascicoli["salva_albero_originale_documenti_portale"],
        catalogo_documenti_portale_fascicolo=fascicoli["catalogo_documenti_portale_fascicolo"],
        gruppa_catalogo_documenti_portale=fascicoli["gruppa_catalogo_documenti_portale"],
        decode_portale_downloaded_items=fascicoli["decode_portale_downloaded_items"],
        importa_documenti_portale_items=fascicoli["importa_documenti_portale_items"],
        portale_ufficiale_label=fascicoli["portale_ufficiale_label"],
        ensure_pdp_penale_case_after_import=pdp_penale["ensure_pdp_penale_case_after_import"],
    )

    return ApplicationRuntimeBundle(
        scheduler_only=False,
        core=core,
        ocr_runtime=ocr_runtime,
        fascicoli=fascicoli,
        telematico=telematico,
        pdp_penale=pdp_penale,
    )
