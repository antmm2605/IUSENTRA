"""
Flask web application - Studio Legale PCT.

Avvio:
    python -m web
    oppure: flask --app web.app run --debug
"""

from __future__ import annotations

import os

from flask import Flask

from lex.providers.local_ai_service import get_local_ai_service
from pct import __version__ as APP_VERSION
from web.bootstrap.app_wiring import register_app_wiring
from web.services.core_runtime import build_core_runtime
from web.services.document_crypto import decrypt_doc, encrypt_doc
from web.services.fascicoli_runtime import build_fascicoli_runtime
from web.services.ocr_runtime import build_ocr_runtime
from web.services.pdp_penale_runtime import build_pdp_penale_runtime
from web.services.security_runtime import apply_security_defaults
from web.services.telematico_runtime import build_telematico_runtime


def create_app(config: dict | None = None) -> Flask:
    """Crea l'app Flask e delega bootstrap, runtime e wiring ai moduli dedicati."""

    app = Flask(__name__, template_folder="templates", static_folder="static")
    cfg = config or {}
    app.config["TESTING"] = bool(cfg.get("TESTING", False))
    scheduler_only = bool(cfg.get("SCHEDULER_ONLY"))
    app.config["PCT_SCHEDULER_WORKER"] = scheduler_only

    from werkzeug.middleware.proxy_fix import ProxyFix

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    apply_security_defaults(
        app,
        {
            **cfg,
            "PCT_SECRET_KEY": os.getenv("PCT_SECRET_KEY", ""),
            "PCT_HTTPS": cfg.get("PCT_HTTPS", os.getenv("PCT_HTTPS", "")),
        },
    )
    if app.config.get("SECRET_KEY_EPHEMERAL"):
        app.logger.warning(
            "PCT_SECRET_KEY non configurata o insicura: uso una chiave effimera valida solo per questo avvio."
        )

    core = build_core_runtime(app, cfg)
    if scheduler_only:
        return app
    ocr_runtime = build_ocr_runtime(decrypt_doc=decrypt_doc)
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
    telematico: dict[str, object] = {}
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

    register_app_wiring(
        app,
        app_version=APP_VERSION,
        core=core,
        fascicoli=fascicoli,
        telematico=telematico,
        pdp_penale=pdp_penale,
        ocr_runtime=ocr_runtime,
        get_local_ai_service=get_local_ai_service,
    )
    return app
