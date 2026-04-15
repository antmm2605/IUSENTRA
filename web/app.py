"""
Flask web application â€” Studio Legale PCT.

Avvio:
    python -m web
    oppure: flask --app web.app run --debug
"""

import base64
import errno
import os
import json
import queue
import re
import shutil
import threading
import unicodedata
import zipfile as _zipfile
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlencode

from flask import (
    Flask,
    request,
    url_for,
    has_request_context,
    session,
    g,
)

from pct.agenda import (
    Agenda,
    TipoAppuntamento,
    StatoAppuntamento,
)
from pct.reginde import ClientReGINde
from pct.clienti import (
    GestioneClienti,
    Cliente,
    TipoCliente,
    StatoCliente,
)
from pct.fascicoli import (
    GestioneFascicoli,
    Fascicolo,
    TipoFascicolo,
    StatoFascicolo,
    stato_fascicolo_da_descrizione_portale,
    TipoDocumento,
    TipoAttivita,
    EsitoAttivita,
    Documento,
)
from pct.messaggi import (
    GestioneMessaggi,
    ConfigEmail,
    ConfigTwilio,
    ConfigMessaggistica,
)
from pct.backup import (
    GestioneBackup,
)
from pct.auth import (
    GestioneUtenti,
    RuoloUtente,
    DESCRIZIONI_RUOLI,
)
from pct.privacy import GestioneTrattamenti
from pct.soggetti import (
    GestioneSoggetti,
)
from pct.scadenziario import (
    GestioneScadenziario,
    TipoTermine,
    regola_patrono_studio,
)
from pct.search_index import IndiceRicerca
from pct.ocr import estrai_testo as ocr_estrai_testo, estensione_supportata as ocr_supportato
from pct.database import GestioneDatabase, bootstrap_moduli_monitorati
from pct.sync import get_gestore
from pct.condivisione import GestioneCondivisioni, RuoloCondivisione
from pct.pst_servizi_catalogo import (
    SEZIONE_COMUNICAZIONI_CANCELLERIA,
    SEZIONE_ISTANZE,
    SEZIONE_UDIENZE_SCADENZE,
    sezione_fascicolo_da_servizio_pst,
)
from pct.pdp_penale_workflow import (
    PDPPenaleWorkflowRepository,
    pdp_penale_classifica_documento,
    pdp_penale_estrai_password,
    pdp_penale_estrai_scadenza_download,
)
from pct.telematico_workflow import TelematicoWorkflowRepository
from pct.workspace_intelligente import WorkspaceIntelligenteService
from pct import __version__ as APP_VERSION
from web.bootstrap.admin_database_routes import register_admin_database_routes
from web.bootstrap.auth_management_routes import register_auth_management_routes
from web.bootstrap.backup_routes import register_backup_routes
from web.bootstrap.calendar_routes import register_calendar_routes
from web.bootstrap.checklist_routes import register_checklist_routes
from web.bootstrap.clienti_routes import register_clienti_routes
from web.bootstrap.clienti_workspace_routes import register_clienti_workspace_routes
from web.bootstrap.condivisioni_routes import register_condivisioni_routes
from web.bootstrap.deposito_routes import register_deposito_routes
from web.bootstrap.dashboard_routes import register_dashboard_routes
from web.bootstrap.error_handlers import register_error_handlers
from web.bootstrap.fascicoli_ai_routes import register_fascicoli_ai_routes
from web.bootstrap.fascicoli_core_routes import register_fascicoli_core_routes
from web.bootstrap.fascicoli_document_routes import register_fascicoli_document_routes
from web.bootstrap.fascicoli_editor_routes import register_fascicoli_editor_routes
from web.bootstrap.fascicoli_management_routes import register_fascicoli_management_routes
from web.bootstrap.fascicoli_pdp_routes import register_fascicoli_pdp_routes
from web.bootstrap.fascicoli_signature_routes import register_fascicoli_signature_routes
from web.bootstrap.export_routes import register_export_routes
from web.bootstrap.health_routes import register_health_routes
from web.bootstrap.messages_routes import register_messages_routes
from web.bootstrap.privacy_routes import register_privacy_routes
from web.bootstrap.pwa_routes import register_pwa_routes
from web.bootstrap.register_blueprints import register_blueprints
from web.bootstrap.polisweb_routes import register_polisweb_routes
from web.bootstrap.portali_acquisizione_routes import register_portali_acquisizione_routes
from web.bootstrap.scadenziario_routes import register_scadenziario_routes
from web.bootstrap.search_routes import register_search_routes
from web.bootstrap.soggetti_routes import register_soggetti_routes
from web.bootstrap.sync_runtime_routes import register_sync_runtime_routes
from web.bootstrap.tariffario_routes import register_tariffario_routes
from web.bootstrap.template_runtime import register_template_runtime
from web.bootstrap.telematico_dashboard_routes import register_telematico_dashboard_routes
from web.bootstrap.telematico_local_signer_routes import register_telematico_local_signer_routes
from web.bootstrap.telematico_portali_routes import register_telematico_portali_routes
from web.bootstrap.reference_lookup_routes import register_reference_lookup_routes
from web.bootstrap.workspace_routes import register_workspace_routes
from web.services.auth_runtime import register_auth_runtime
from web.services.local_ai_runtime import get_local_ai_service
from web.services.runtime_settings import apply_runtime_settings
from web.services.security_runtime import apply_security_defaults, register_security_runtime

# ------------------------------------------------------------------ cifratura documenti (AES-256-GCM)

_ENC_MAGIC = b"PCTENC\x01"


def _doc_key() -> bytes | None:
    """Restituisce la chiave AES-256 da env var PCT_DOC_KEY, o None se non configurata."""
    raw = os.getenv("PCT_DOC_KEY", "")
    if not raw:
        return None
    import hashlib as _hl
    return _hl.sha256(raw.encode()).digest()


def _encrypt_doc(data: bytes) -> bytes:
    """Cifra i byte del documento con AES-256-GCM. No-op se PCT_DOC_KEY non impostata."""
    key = _doc_key()
    if not key:
        return data
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    nonce = os.urandom(12)
    ct = AESGCM(key).encrypt(nonce, data, None)
    return _ENC_MAGIC + nonce + ct


def _decrypt_doc(data: bytes) -> bytes:
    """Decifra i byte del documento. No-op se il file non Ã¨ cifrato (magic header assente)."""
    if not data.startswith(_ENC_MAGIC):
        return data
    key = _doc_key()
    if not key:
        raise ValueError("Documento cifrato ma PCT_DOC_KEY non configurata nel server.")
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    payload = data[len(_ENC_MAGIC):]
    nonce, ct = payload[:12], payload[12:]
    return AESGCM(key).decrypt(nonce, ct, None)


# ------------------------------------------------------------------ OCR worker asincrono

_ocr_queue: queue.Queue = queue.Queue()
_ocr_stats = {"totale": 0, "completati": 0, "errori": 0, "in_coda": 0}
_ocr_stats_lock = threading.Lock()


def _ocr_worker():
    """Thread daemon che processa i job OCR in background."""
    import logging
    log = logging.getLogger("ocr_worker")
    while True:
        job = _ocr_queue.get()
        if job is None:
            break
        percorso, hash_sha256, id_fasc, id_doc, nome_doc, tipo_doc, index_path = job
        with _ocr_stats_lock:
            _ocr_stats["in_coda"] = _ocr_queue.qsize()
        try:
            # Controlla cache prima di rieseguire l'OCR
            idx = IndiceRicerca(index_path=index_path)
            testo = idx.get_ocr_cache(hash_sha256)
            if testo is None:
                raw = Path(percorso).read_bytes()
                decifrato = _decrypt_doc(raw)
                testo = ocr_estrai_testo(decifrato, nome_doc)
                idx.set_ocr_cache(hash_sha256, testo)
            if testo:
                idx.indicizza_documento(id_fasc, id_doc, nome_doc, testo, tipo_doc)
            with _ocr_stats_lock:
                _ocr_stats["completati"] += 1
        except Exception as e:
            log.warning("Errore OCR documento %s/%s: %s", id_fasc, id_doc, e)
            with _ocr_stats_lock:
                _ocr_stats["errori"] += 1
        finally:
            _ocr_queue.task_done()
            with _ocr_stats_lock:
                _ocr_stats["in_coda"] = _ocr_queue.qsize()


# Avvia il worker all'import del modulo (daemon â†’ termina con il processo)
_ocr_thread = threading.Thread(target=_ocr_worker, daemon=True, name="ocr-worker")
_ocr_thread.start()


def _accoda_ocr(percorso: str, hash_sha256: str, id_fasc: str, id_doc: str,
                nome_doc: str, tipo_doc: str, index_path: str):
    """Accoda un job OCR se il file Ã¨ di un tipo supportato."""
    if not ocr_supportato(nome_doc):
        return
    with _ocr_stats_lock:
        _ocr_stats["totale"] += 1
        _ocr_stats["in_coda"] = _ocr_queue.qsize() + 1
    _ocr_queue.put((percorso, hash_sha256, id_fasc, id_doc, nome_doc, tipo_doc, index_path))


# ------------------------------------------------------------------ factory

def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    cfg = config or {}
    app.config["TESTING"] = bool(cfg.get("TESTING", False))

    # ProxyFix: necessario su Railway/Render/Heroku e qualsiasi reverse proxy.
    # Senza questo, request.scheme Ã¨ sempre "http" (schema interno) â†’
    # url_for() e request.host_url generano link http:// invece di https://,
    # rompendo i feed iCal sottoscritti da Google Calendar (che richiede HTTPS).
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
    # SQLite mode: PCT_SQLITE_MODE=1 sostituisce il backend JSON con SQLite per i 7 moduli core
    app.config["SQLITE_MODE"] = os.getenv("PCT_SQLITE_MODE", "").lower() in ("1", "true", "yes")
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
    app.config["CLIENTI_DB"] = cfg.get(
        "CLIENTI_DB", os.getenv("PCT_CLIENTI_DB", "./clienti/anagrafica.json")
    )
    def _data_peer_path(base_path: str, folder: str, filename: str) -> str:
        base = Path(base_path)
        if base.parent.name.lower() == "clienti" and base.name.lower() == "anagrafica.json":
            root = base.parent.parent
        else:
            root = base.parent
        return str(root / folder / filename)
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
        "EMAIL_CASELLA_DB", os.getenv("PCT_EMAIL_DB", "./email/casella.json")
    )
    app.config["BACKUP_DIR"] = cfg.get(
        "BACKUP_DIR", os.getenv("PCT_BACKUP_DIR", "./backup")
    )
    app.config["AUTH_DB"] = cfg.get(
        "AUTH_DB", os.getenv("PCT_AUTH_DB", "./auth/utenti.json")
    )
    app.config["AUDIT_DB"] = cfg.get(
        "AUDIT_DB", os.getenv("PCT_AUDIT_DB", "./auth/audit.json")
    )
    app.config["BOOTSTRAP_ADMIN_PASSWORD"] = cfg.get(
        "BOOTSTRAP_ADMIN_PASSWORD",
        os.getenv("PCT_BOOTSTRAP_ADMIN_PASSWORD", ""),
    )
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
    app.config["SEARCH_INDEX"] = cfg.get(
        "SEARCH_INDEX", os.getenv("PCT_SEARCH_INDEX", "./search/index.db")
    )
    app.config["PRIVACY_DB"] = cfg.get(
        "PRIVACY_DB", os.getenv("PCT_PRIVACY_DB", "./privacy/registro.json")
    )
    app.config["API_KEY"] = os.getenv("PCT_API_KEY", "")
    app.config["API_V1_ALLOWED_ORIGINS"] = cfg.get(
        "API_V1_ALLOWED_ORIGINS",
        os.getenv("PCT_API_V1_ALLOWED_ORIGINS", ""),
    )
    app.config["STUDIO_NOME"] = os.getenv("PCT_STUDIO_NOME", "Studio Legale PCT")
    app.config["PORTALE_DB"] = cfg.get(
        "PORTALE_DB", os.getenv("PCT_PORTALE_DB", "./portale/portali.json")
    )
    app.config["PORTALE_UPLOADS"] = cfg.get(
        "PORTALE_UPLOADS", os.getenv("PCT_PORTALE_UPLOADS", "./portale/uploads")
    )
    app.config["PORTALE_IMPORT_LOG_DB"] = cfg.get(
        "PORTALE_IMPORT_LOG_DB",
        os.getenv("PCT_PORTALE_IMPORT_LOG_DB", "./portale/import_log.json"),
    )
    app.config["FATTURAZIONE_DB"] = cfg.get(
        "FATTURAZIONE_DB", os.getenv("PCT_FATTURAZIONE_DB", "./fatturazione/parcelle.json")
    )
    app.config["PREVENTIVI_DB"] = cfg.get(
        "PREVENTIVI_DB", os.getenv("PCT_PREVENTIVI_DB", "./preventivi/preventivi.json")
    )
    app.config["NOTIFICHE_LOG"] = cfg.get(
        "NOTIFICHE_LOG", os.getenv("PCT_NOTIFICHE_LOG", "./notifiche/log.json")
    )
    app.config["SOGGETTI_DB"] = cfg.get(
        "SOGGETTI_DB",
        os.getenv(
            "PCT_SOGGETTI_DB",
            _data_peer_path(app.config["CLIENTI_DB"], "soggetti", "anagrafica.json"),
        ),
    )
    app.config["SOGGETTI_PARTI_DB"] = cfg.get(
        "SOGGETTI_PARTI_DB",
        os.getenv(
            "PCT_SOGGETTI_PARTI_DB",
            _data_peer_path(app.config["CLIENTI_DB"], "soggetti", "parti.json"),
        ),
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
    app.config["STUDIO_INDIRIZZO"] = os.getenv("PCT_STUDIO_INDIRIZZO", "")
    app.config["STUDIO_IBAN"]      = os.getenv("PCT_STUDIO_IBAN", "")
    app.config["STUDIO_AVVOCATO"]  = os.getenv("PCT_STUDIO_AVVOCATO", "")
    app.config["TEMPLATE_ATTI_DB"] = cfg.get(
        "TEMPLATE_ATTI_DB", os.getenv("PCT_TEMPLATE_ATTI_DB", "./template_atti/templates.json")
    )
    app.config["TEMPLATE_ATTI_PREFS_DB"] = cfg.get(
        "TEMPLATE_ATTI_PREFS_DB",
        os.getenv(
            "PCT_TEMPLATE_ATTI_PREFS_DB",
            _data_peer_path(app.config["TEMPLATE_ATTI_DB"], "template_atti", "editor_layout.json"),
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

    def _cfg_data_path(key: str) -> str:
        if has_request_context():
            paths = getattr(g, "data_paths", {}) or {}
            return paths.get(key, app.config[key])
        return app.config[key]

    def _database_paths() -> dict[str, str]:
        return {
            "calendar_sync": _cfg_data_path("CALENDAR_SYNC_DB"),
            "clienti": _cfg_data_path("CLIENTI_DB"),
            "condivisioni": _cfg_data_path("CONDIVISIONI_DB"),
            "note_faldone": _cfg_data_path("NOTE_FALDONE_DB"),
            "fascicoli": _cfg_data_path("FASCICOLI_DB"),
            "appuntamenti": _cfg_data_path("AGENDA_DB"),
            "scadenze": _cfg_data_path("SCADENZIARIO_DB"),
            "messaggi": _cfg_data_path("MESSAGGI_DB"),
            "notifiche": _cfg_data_path("NOTIFICHE_LOG"),
            "email_casella": _cfg_data_path("EMAIL_CASELLA_DB"),
            "utenti": _cfg_data_path("AUTH_DB"),
            "audit": _cfg_data_path("AUDIT_DB"),
            "privacy": _cfg_data_path("PRIVACY_DB"),
            "backup": str(Path(_cfg_data_path("BACKUP_DIR")) / "registro.json"),
            "portale": _cfg_data_path("PORTALE_DB"),
            "fatturazione": _cfg_data_path("FATTURAZIONE_DB"),
            "preventivi": _cfg_data_path("PREVENTIVI_DB"),
            "soggetti": _cfg_data_path("SOGGETTI_DB"),
            "soggetti_parti": _cfg_data_path("SOGGETTI_PARTI_DB"),
            "wizard_pro": _cfg_data_path("WIZARD_PRO_DB"),
            "legal_intelligence": _cfg_data_path("LEGAL_INTELLIGENCE_DB"),
            "normative_tables": _cfg_data_path("NORMATIVE_TABLES_DB"),
            "giurisprudenza": _cfg_data_path("GIURISPRUDENZA_DB"),
            "workspace_intelligence": _cfg_data_path("WORKSPACE_INTELLIGENCE_DB"),
            "local_ai": _cfg_data_path("LOCAL_AI_DB"),
            "validation_runs": _cfg_data_path("VALIDATION_RUNS_DB"),
            "template_atti": _cfg_data_path("TEMPLATE_ATTI_DB"),
            "template_atti_prefs": _cfg_data_path("TEMPLATE_ATTI_PREFS_DB"),
            "redaction_assistant": _cfg_data_path("REDACTION_ASSISTANT_DB"),
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

    def get_studio_db():
        """
        Restituisce l'istanza StudioDB per il tenant corrente,
        oppure None se PCT_SQLITE_MODE non Ã¨ attivo.

        Il percorso di studio.db Ã¨ derivato dalla root dei dati del tenant:
        es. /data/clienti/anagrafica.json â†’ /data/studio.db
        """
        if not app.config.get("SQLITE_MODE"):
            return None
        if not hasattr(g, "_studio_db"):
            from pct.storage import StudioDB
            db_path = _cfg_data_path("CLIENTI_DB")
            g._studio_db = StudioDB.from_data_path(db_path)
        return g._studio_db

    def get_agenda() -> Agenda:
        if not hasattr(g, "_agenda"):
            g._agenda = Agenda(
                db_path=_cfg_data_path("AGENDA_DB"),
                studio_db=get_studio_db(),
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
                studio_db=get_studio_db(),
            )
        return g._clienti

    def get_fascicoli() -> GestioneFascicoli:
        if not hasattr(g, "_fascicoli"):
            g._fascicoli = GestioneFascicoli(
                db_path=_cfg_data_path("FASCICOLI_DB"),
                documents_dir=_cfg_data_path("FASCICOLI_DOCS"),
                archive_dir=_cfg_data_path("FASCICOLI_ARCH"),
                studio_db=get_studio_db(),
            )
        return g._fascicoli

    def get_pdp_penale() -> PDPPenaleWorkflowRepository:
        if not hasattr(g, "_pdp_penale_repo"):
            backend = get_studio_db() or _cfg_data_path("PDP_PENALE_DB")
            g._pdp_penale_repo = PDPPenaleWorkflowRepository(backend)
        return g._pdp_penale_repo

    def get_telematico() -> TelematicoWorkflowRepository:
        if not hasattr(g, "_telematico_repo"):
            backend = get_studio_db() or _cfg_data_path("TELEMATICO_DB")
            g._telematico_repo = TelematicoWorkflowRepository(backend)
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
            )
        return g._workspace_intelligente

    def _documento_payload_per_validazione(gf: GestioneFascicoli, fasc: Fascicolo, doc_id: str) -> dict | None:
        doc = next((item for item in fasc.documenti if item.id == doc_id), None)
        if not doc:
            return None
        try:
            percorso = str(gf.percorso_documento(fasc.id, doc_id))
        except KeyError:
            return None
        return {
            "id": doc.id,
            "nome": doc.nome,
            "tipo": doc.tipo.value if hasattr(doc.tipo, "value") else str(doc.tipo),
            "percorso": percorso,
            "dimensione_bytes": doc.dimensione_bytes,
            "firmato_digitalmente": bool(doc.firmato_digitalmente),
            "data_documento": doc.data_documento,
        }

    def _build_deposito_validation_context(form_like, fasc: Fascicolo, operatore: str = "") -> dict:
        anno_rg_raw = (form_like.get("anno_rg", "") or "").strip()
        return {
            "tipo_atto": (form_like.get("tipo_atto", "ATTO_GENERICO") or "ATTO_GENERICO").strip(),
            "codice_registro": (form_like.get("codice_registro", "RG") or "RG").strip(),
            "oggetto": (form_like.get("oggetto", "") or fasc.titolo).strip(),
            "numero_rg": (form_like.get("numero_rg", "") or fasc.numero_rg).strip(),
            "anno_rg": int(anno_rg_raw) if anno_rg_raw.isdigit() else fasc.anno_rg,
            "atto_principale_id": (form_like.get("atto_principale_id", "") or "").strip(),
            "allegati_ids": list(form_like.getlist("allegati_ids")) if hasattr(form_like, "getlist") else list(form_like.get("allegati_ids", []) or []),
            "note": (form_like.get("note", "") or "").strip(),
            "operatore": operatore,
        }

    def _run_deposito_validation(
        fasc: Fascicolo,
        gf: GestioneFascicoli,
        form_like,
        operatore: str = "",
    ):
        ctx = _build_deposito_validation_context(form_like, fasc, operatore=operatore)
        selected_ids = []
        if ctx["atto_principale_id"]:
            selected_ids.append(ctx["atto_principale_id"])
        for doc_id in ctx["allegati_ids"]:
            if doc_id and doc_id not in selected_ids:
                selected_ids.append(doc_id)
        selected_docs = [
            payload
            for doc_id in selected_ids
            for payload in [_documento_payload_per_validazione(gf, fasc, doc_id)]
            if payload
        ]
        all_docs = [
            payload
            for doc in fasc.documenti
            for payload in [_documento_payload_per_validazione(gf, fasc, doc.id)]
            if payload
        ]
        return get_deposito_guidato().valida(
            fascicolo=fasc,
            context=ctx,
            selected_documents=selected_docs,
            all_documents=all_docs,
        )

    def _portale_ufficiale_label(fasc: Fascicolo) -> str:
        if fasc.tipo == TipoFascicolo.PENALE:
            return "PDP"
        if fasc.tipo == TipoFascicolo.AMMINISTRATIVO:
            return "PAT"
        if fasc.tipo == TipoFascicolo.TRIBUTARIO:
            return "SIGIT / PTT"
        return "PolisWeb / PST"

    def _tipo_lotto_portale(fasc: Fascicolo) -> str:
        if fasc.tipo == TipoFascicolo.PENALE:
            return "Acquisizione documenti PDP"
        if fasc.tipo == TipoFascicolo.AMMINISTRATIVO:
            return "Acquisizione documenti PAT"
        if fasc.tipo == TipoFascicolo.TRIBUTARIO:
            return "Acquisizione documenti SIGIT"
        return "Acquisizione documenti PolisWeb"

    def _infer_canale_deposito(fasc: Fascicolo, explicit: str = "") -> str:
        canale = (explicit or "").strip().upper()
        if canale:
            return canale
        if fasc.tipo == TipoFascicolo.PENALE:
            return "PDP_PENALE"
        if fasc.tipo == TipoFascicolo.AMMINISTRATIVO:
            return "PAT_AMMINISTRATIVO"
        if fasc.tipo == TipoFascicolo.TRIBUTARIO:
            return "PTT_TRIBUTARIO"
        return "PCT_TELEMATICO"

    def _resolve_ufficio_destinatario(raw_value: str, *, tipo: str | None = None) -> dict | None:
        try:
            from pct.uffici_giudiziari import risolvi_ufficio

            cache_path = os.getenv("PCT_UFFICI_DB", "/data/uffici/uffici_giudiziari.json")
            return risolvi_ufficio(raw_value, tipo=tipo, cache_path=cache_path)
        except Exception:
            return None

    def _pst_import_dir_for_fascicolo(fasc: Fascicolo) -> Path:
        return Path(app.config["PST_IMPORT_DIR"]) / fasc.id

    def _pst_import_pending_count(fasc: Fascicolo) -> int:
        cartella = _pst_import_dir_for_fascicolo(fasc)
        if not cartella.exists():
            return 0
        return sum(1 for path in cartella.rglob("*") if path.is_file())

    _DOC_TIPI_ATTI_PRINCIPALI = {
        TipoDocumento.ATTO_GIUDIZIARIO,
        TipoDocumento.MEMORIA,
        TipoDocumento.RICORSO,
        TipoDocumento.CITAZIONE,
        TipoDocumento.COMPARSA,
    }
    _DOC_TIPI_PROVVEDIMENTI = {
        TipoDocumento.SENTENZA,
        TipoDocumento.ORDINANZA,
        TipoDocumento.DECRETO,
        TipoDocumento.VERBALE,
    }
    _DOC_TIPI_RICEVUTE = {
        TipoDocumento.COMUNICAZIONE,
        TipoDocumento.DEPOSITO_PCT,
        TipoDocumento.NOTIFICA,
    }
    _ATTIVITA_UDIENZE_SCADENZE = {
        TipoAttivita.UDIENZA,
        TipoAttivita.TERMINE_SCADENZA,
        TipoAttivita.RINVIO,
    }

    def _fascicolo_text(*parts: object) -> str:
        return " ".join(str(part or "").strip() for part in parts if str(part or "").strip()).lower()

    def _documento_bucket(doc: Documento) -> str:
        tipo = getattr(doc, "tipo", None)
        if tipo in _DOC_TIPI_PROVVEDIMENTI:
            return "provvedimenti"
        if tipo in _DOC_TIPI_RICEVUTE:
            return "ricevute"
        if tipo in _DOC_TIPI_ATTI_PRINCIPALI:
            return "atti_principali"
        return "allegati"

    def _documento_is_istanza(doc: Documento) -> bool:
        testo = _fascicolo_text(getattr(doc, "nome", ""), getattr(doc, "note", ""), getattr(doc, "tipo", ""))
        return "istanza" in testo

    def _deposito_servizio_portale(dep) -> str:
        return str(getattr(dep, "servizio_portale", "") or "").strip()

    def _deposito_sezione_portale(dep) -> str:
        servizio = _deposito_servizio_portale(dep)
        return sezione_fascicolo_da_servizio_pst(servizio) if servizio else ""

    def _deposito_ha_ricevute(dep) -> bool:
        return any(
            (
                getattr(dep, "ricevuta_accettazione", ""),
                getattr(dep, "ricevuta_consegna", ""),
                getattr(dep, "ricevuta_controlli_automatici", ""),
                getattr(dep, "ricevuta_cancelleria", ""),
            )
        )

    def _deposito_is_istanza(dep) -> bool:
        if _deposito_sezione_portale(dep) == SEZIONE_ISTANZE:
            return True
        testo = _fascicolo_text(
            getattr(dep, "tipo_atto", ""),
            getattr(dep, "messaggio", ""),
            getattr(dep, "note", ""),
            getattr(dep, "nome_atto_principale", ""),
        )
        return "istanza" in testo

    def _deposito_is_udienza_scadenza(dep) -> bool:
        if _deposito_sezione_portale(dep) == SEZIONE_UDIENZE_SCADENZE:
            return True
        testo = _fascicolo_text(
            getattr(dep, "tipo_atto", ""),
            getattr(dep, "note", ""),
            getattr(dep, "nome_atto_principale", ""),
        )
        return any(t in testo for t in ("udienza", "verbale", "scadenz", "rinvio", "termine"))

    def _deposito_is_comunicazione(dep) -> bool:
        sezione_portale = _deposito_sezione_portale(dep)
        if sezione_portale:
            return sezione_portale == SEZIONE_COMUNICAZIONI_CANCELLERIA
        if _deposito_ha_ricevute(dep):
            return True
        return str(getattr(dep, "stato", "") or "").strip().upper() in {
            "INVIATO",
            "ACCETTATO",
            "ACCETTATO_PEC",
            "CONSEGNATO",
            "WARN_CONTROLLI",
            "ERRORE_CONTROLLI",
            "RIFIUTATO",
            "ACCETTATO_CANCELLERIA",
            "RIFIUTATO_CANCELLERIA",
            "ERRORE",
        }

    def _build_fascicolo_workspace(
        fasc: Fascicolo,
        *,
        apps: Optional[list] = None,
        scadenze: Optional[list] = None,
    ) -> dict:
        documenti = list(getattr(fasc, "documenti", []) or [])
        attivita = list(getattr(fasc, "attivita", []) or [])
        depositi = list(getattr(fasc, "depositi_pct", []) or [])
        appuntamenti = list(apps or [])
        termini = list(scadenze or [])

        documenti_buckets = {
            "all": len(documenti),
            "atti_principali": 0,
            "allegati": 0,
            "ricevute": 0,
            "provvedimenti": 0,
            "istanze": 0,
        }
        for doc in documenti:
            documenti_buckets[_documento_bucket(doc)] += 1
            if _documento_is_istanza(doc):
                documenti_buckets["istanze"] += 1

        attivita_processuali = [
            att for att in attivita
            if att.tipo not in _ATTIVITA_UDIENZE_SCADENZE
            and att.tipo != TipoAttivita.COMUNICAZIONE_CANCELLERIA
        ]
        udienze_attivita = [att for att in attivita if att.tipo in _ATTIVITA_UDIENZE_SCADENZE]
        comunicazioni_attivita = [
            att for att in attivita if att.tipo == TipoAttivita.COMUNICAZIONE_CANCELLERIA
        ]
        comunicazioni_depositi = [dep for dep in depositi if _deposito_is_comunicazione(dep)]
        udienze_depositi = [dep for dep in depositi if _deposito_is_udienza_scadenza(dep)]
        istanze_documenti = [doc for doc in documenti if _documento_is_istanza(doc)]
        istanze_depositi = [dep for dep in depositi if _deposito_is_istanza(dep)]

        attivita_processuali.sort(key=lambda att: getattr(att, "data", "") or "", reverse=True)
        udienze_attivita.sort(key=lambda att: getattr(att, "data", "") or "")
        udienze_depositi.sort(key=lambda dep: getattr(dep, "timestamp", "") or "", reverse=True)
        comunicazioni_attivita.sort(key=lambda att: getattr(att, "data", "") or "", reverse=True)
        comunicazioni_depositi.sort(key=lambda dep: getattr(dep, "timestamp", "") or "", reverse=True)
        termini.sort(key=lambda sc: getattr(sc, "data_scadenza", "") or "")
        appuntamenti.sort(key=lambda app_obj: getattr(app_obj, "data_ora", "") or "")

        return {
            "counts": {
                "profilo": 1,
                "documenti": len(documenti),
                "attivita": len(attivita_processuali),
                "udienze_scadenze": len(udienze_attivita) + len(udienze_depositi) + len(termini) + len(appuntamenti),
                "comunicazioni": len(comunicazioni_attivita) + len(comunicazioni_depositi),
                "istanze": len(istanze_documenti) + len(istanze_depositi),
            },
            "documenti_buckets": documenti_buckets,
            "attivita_processuali": attivita_processuali,
            "udienze_attivita": udienze_attivita,
            "udienze_depositi": udienze_depositi,
            "scadenze": termini,
            "appuntamenti": appuntamenti,
            "comunicazioni_attivita": comunicazioni_attivita,
            "comunicazioni_depositi": comunicazioni_depositi,
            "istanze_documenti": istanze_documenti,
            "istanze_depositi": istanze_depositi,
        }

    def _url_with_query(base_url: str, **params) -> str:
        clean = {
            key: value
            for key, value in params.items()
            if value not in (None, "", [], ())
        }
        if not clean:
            return base_url
        joiner = "&" if "?" in base_url else "?"
        return f"{base_url}{joiner}{urlencode(clean, doseq=True)}"

    def _fascicolo_focus_url(id_fasc: str, *, focus: str = "", open_modal: str = "", **extra_params) -> str:
        base = url_for("dettaglio_fascicolo", id_fasc=id_fasc)
        params: dict[str, Any] = dict(extra_params)
        if focus:
            params["focus"] = focus
        if open_modal:
            params["open_modal"] = open_modal
        full = _url_with_query(base, **params)
        return f"{full}#sezione-{focus}" if focus else full

    def _compiler_correction_url(
        id_fasc: str,
        *,
        model_code: str,
        cliente_id: str = "",
        correction_title: str = "",
        correction_help: str = "",
        **query,
    ) -> str:
        if not model_code:
            return ""
        base = url_for(
            "template_atti.compila",
            model_code=model_code,
            id_cliente=cliente_id,
            id_fascicolo=id_fasc,
        )
        return _url_with_query(
            base,
            correction_title=correction_title,
            correction_help=correction_help,
            **query,
        )

    def _deposito_correction_url(id_fasc: str, **query) -> str:
        return _url_with_query(url_for("deposito_prepara", id_fasc=id_fasc), **query)

    def _fascicolo_edit_url(id_fasc: str, **query) -> str:
        return _url_with_query(url_for("modifica_fascicolo", id_fasc=id_fasc), **query)

    def _prefill_tipo_atto_from_summary(summary: Optional[dict]) -> str:
        summary = summary or {}
        practice_id = str(summary.get("practice_id") or "").strip().lower()
        model_code = str(summary.get("model_code") or "").strip().upper()
        haystack = f"{practice_id} {model_code}"
        if "cit" in haystack:
            return "ATTO_DI_CITAZIONE"
        if "comparsa" in haystack or "com_" in haystack:
            return "COMPARSA_RISPOSTA"
        if "cass" in haystack:
            return "RICORSO_CASSAZIONE"
        if "appello" in haystack:
            return "APPELLO"
        if "decreto" in haystack or "ingiunt" in haystack:
            return "DECRETO_INGIUNTIVO"
        if "ricorso" in haystack:
            return "RICORSO"
        return "ATTO_GENERICO"

    def _rc_normalize_status(value: str, *, default: str = "warning") -> str:
        state = str(value or "").strip().lower()
        if state in {"ok", "success", "passed", "pronto", "ready"}:
            return "ok"
        if state in {"warning", "warn", "avviso"}:
            return "warning"
        if state in {"blocco", "block", "blocked", "danger", "errore", "error"}:
            return "block"
        return default

    def _rc_status_rank(value: str) -> int:
        return {"block": 0, "warning": 1, "ok": 2}.get(_rc_normalize_status(value), 3)

    def _rc_section_meta(
        section_key: str,
        *,
        detail_url: str,
        deposit_url: str,
        compile_url: str,
    ) -> dict[str, str]:
        defaults = {
            "processuale": {
                "where": "Profilo fascicolo",
                "url": f"{detail_url}#sezione-profilo",
                "cta": "Apri profilo",
            },
            "documentale": {
                "where": "Documenti fascicolo",
                "url": f"{detail_url}#sezione-documenti-fascicolo",
                "cta": "Apri allegati",
            },
            "tecnico_pst": {
                "where": "Pre-deposito",
                "url": deposit_url,
                "cta": "Apri pre-deposito",
            },
            "redazionale": {
                "where": "Redattore guidato",
                "url": compile_url or f"{detail_url}#sezione-profilo",
                "cta": "Apri redattore",
            },
        }
        return defaults.get(
            section_key,
            {
                "where": "Fascicolo",
                "url": detail_url,
                "cta": "Apri",
            },
        )

    def _rc_first_section_message(section: dict, *, ok_fallback: str) -> str:
        items = list(section.get("items") or [])
        for wanted in ("block", "warning"):
            row = next((item for item in items if str(item.get("state") or "") == wanted), None)
            if row:
                return str(row.get("detail") or row.get("action") or row.get("title") or "").strip()
        row = next((item for item in items if str(item.get("state") or "") == "ok"), None)
        if row:
            return str(row.get("detail") or row.get("title") or ok_fallback).strip()
        return ok_fallback

    def _rc_gate_status(gate: dict, fallback_state: str) -> str:
        if not gate:
            return _rc_normalize_status(fallback_state)
        if not gate.get("applicable", True):
            return "ok"
        if gate.get("allowed"):
            return "ok"
        return _rc_normalize_status(fallback_state, default="block")

    def _rc_issue_family(issue: dict) -> str:
        haystack = " ".join(
            filter(
                None,
                [
                    str(issue.get("code") or "").lower(),
                    str(issue.get("title") or "").lower(),
                    str(issue.get("detail") or "").lower(),
                ],
            )
        )
        if "procura" in haystack:
            return "procura"
        if "notifica" in haystack or "relata" in haystack:
            return "notifica"
        if "contributo" in haystack:
            return "contributo"
        if "sentenza" in haystack and "mancante" in haystack:
            return "sentenza"
        if "oggetto" in haystack and ("mancante" in haystack or "non definito" in haystack):
            return "oggetto"
        if "firma" in haystack and ("mancante" in haystack or "non firmato" in haystack):
            return "firma"
        if "pdf/a" in haystack or "pdfa" in haystack:
            return "pdfa"
        if "sede" in haystack and "mancante" in haystack or "ufficio" in haystack and "mancante" in haystack:
            return "ufficio"
        if "cliente" in haystack and "mancante" in haystack:
            return "cliente"
        return ""

    def _rc_issue_dedupe_rank(issue: dict) -> int:
        family = _rc_issue_family(issue)
        if not family:
            return 100

        code = str(issue.get("code") or "").strip().lower()
        title = str(issue.get("title") or "").strip().lower()
        service = str(issue.get("service") or "").strip().upper()

        # Priorita per famiglia: il controllo piu specifico vince
        specific_codes = {
            "procura": {"citazione_procura_mancante"},
            "notifica": {"citazione_relata_notifica_mancante"},
            "contributo": {"citazione_contributo_non_rilevato"},
            "sentenza": {"citazione_sentenza_mancante"},
            "oggetto": {"redazione_oggetto_mancante"},
            "firma": {"atto_principale_non_firmato"},
            "pdfa": {"atto_principale_non_pdfa"},
            "ufficio": {"sede_mancante"},
            "cliente": {"citazione_cliente_mancante", "campo_mancante_id_cliente"},
        }
        generic_codes = {
            "procura": {"doc_procura_missing"},
            "notifica": {"doc_notifica_missing"},
            "contributo": {"doc_contributo_missing"},
            "sentenza": {"doc_sentenza_missing"},
            "oggetto": set(),
            "firma": set(),
            "pdfa": set(),
            "ufficio": {"ufficio_non_risolto"},
            "cliente": set(),
        }
        selection_codes = {
            "procura": {"procura_mancante"},
            "notifica": {"prova_notifica_non_rilevata"},
            "contributo": {"contributo_non_evidenziato"},
        }

        if code in specific_codes.get(family, set()):
            return 0
        if code in generic_codes.get(family, set()):
            return 1
        if code in selection_codes.get(family, set()):
            return 2
        # Controlli processuali hanno priorita su redazionali per lo stesso concetto
        if service == "GIURIDICO":
            return 3
        if service == "DOCUMENTALE":
            return 4
        if service == "TECNICO":
            return 5
        if "non inclus" in title or "non selezion" in title:
            return 6
        if "non rilevat" in title:
            return 5
        return 50

    def _rc_prune_redundant_corrections(corrections: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], set[str]]:
        best_for_family: dict[str, tuple[int, int]] = {}
        for index, correction in enumerate(corrections):
            family = _rc_issue_family(correction)
            if not family:
                continue
            rank = _rc_issue_dedupe_rank(correction)
            current = best_for_family.get(family)
            if current is None or rank < current[0]:
                best_for_family[family] = (rank, index)

        pruned: list[dict[str, Any]] = []
        suppressed_titles: set[str] = set()
        for index, correction in enumerate(corrections):
            family = _rc_issue_family(correction)
            if family:
                _, best_index = best_for_family.get(family, (999, index))
                if index != best_index:
                    title = str(correction.get("title") or "").strip().lower()
                    if title:
                        suppressed_titles.add(title)
                    continue
            pruned.append(correction)
        return pruned, suppressed_titles

    def _rc_state_from_items(items: list[dict[str, Any]], *, default: str = "ok") -> str:
        if any(str(item.get("state") or item.get("status") or "").strip() == "block" for item in items):
            return "block"
        if any(str(item.get("state") or item.get("status") or "").strip() == "warning" for item in items):
            return "warning"
        return default

    def _responsabile_issue_action_meta(
        id_fasc: str,
        issue: dict,
        *,
        cliente=None,
        summary: Optional[dict] = None,
    ) -> dict[str, str]:
        summary = summary or {}
        model_code = str(summary.get("model_code") or "").strip()
        cliente_id = str(getattr(cliente, "id", "") or "").strip()
        registry_suggestion = str(summary.get("registry_suggestion") or "").strip().upper()

        code = str(issue.get("code") or "").strip().lower()
        field = str(issue.get("field") or "").strip().lower()
        service = str(issue.get("service") or "").upper()
        tokens = " ".join(
            filter(
                None,
                [
                    code,
                    field,
                    str(issue.get("title") or "").lower(),
                    str(issue.get("detail") or "").lower(),
                ],
            )
        )

        if code == "citazione_udienza_mancante" or field == "data_prima_udienza":
            return {
                "action_url": _fascicolo_edit_url(
                    id_fasc,
                    intent="prima_udienza",
                    highlight="data_prima_udienza",
                    correction_title="Imposta prima udienza",
                    correction_help="Per l'atto di citazione serve una data di prima comparizione strutturata nel fascicolo.",
                ),
                "action_label": "Imposta prima udienza",
            }

        if code == "citazione_data_notifica_non_strutturata" or field == "data_notifica_citazione":
            return {
                "action_url": _fascicolo_edit_url(
                    id_fasc,
                    intent="data_notifica_citazione",
                    highlight="data_notifica_citazione",
                    correction_title="Inserisci data notifica",
                    correction_help="La data di notificazione della citazione deve essere salvata in modo strutturato per i controlli successivi.",
                ),
                "action_label": "Inserisci data notifica",
            }

        if code in {"citazione_procura_mancante", "doc_procura_missing"} or "procura" in tokens:
            return {
                "action_url": _fascicolo_focus_url(
                    id_fasc,
                    focus="documenti",
                    open_modal="documento",
                    doc_kind="PROCURA",
                    correction_title="Carica procura alle liti",
                    correction_help="Il controllo ha rilevato l'assenza della procura. Apri il modal giÃ  posizionato sul tipo documento corretto.",
                ),
                "action_label": "Carica procura",
            }

        if code in {"citazione_relata_notifica_mancante", "doc_notifica_missing"} or any(
            token in tokens for token in ("notifica", "relata")
        ):
            return {
                "action_url": _fascicolo_focus_url(
                    id_fasc,
                    focus="documenti",
                    open_modal="documento",
                    doc_kind="NOTIFICA",
                    correction_title="Carica relata o prova di notifica",
                    correction_help="Per superare il blocco documentale serve una relata o prova notificatoria coerente con l'atto introduttivo.",
                ),
                "action_label": "Carica relata / notifica",
            }

        if code in {"citazione_contributo_non_rilevato", "doc_contributo_missing"} or "contributo" in tokens:
            return {
                "action_url": _fascicolo_focus_url(
                    id_fasc,
                    focus="documenti",
                    open_modal="documento",
                    doc_kind="ALLEGATO",
                    doc_hint="contributo",
                    correction_title="Carica ricevuta contributo unificato",
                    correction_help="Il fascicolo non mostra ancora la ricevuta del contributo o dei diritti quando dovuti.",
                ),
                "action_label": "Carica contributo",
            }

        if code in {"citazione_cliente_mancante", "redazione_assistito_non_strutturato"} or any(
            token in tokens for token in ("assistito", "cliente", "attore")
        ):
            return {
                "action_url": _fascicolo_focus_url(
                    id_fasc,
                    focus="parti",
                    open_modal="parte",
                    role_hint="ASSISTITO",
                    correction_title="Aggiungi assistito",
                    correction_help="La conformitÃ  richiede almeno l'assistito strutturato nella sezione Parti del procedimento.",
                ),
                "action_label": "Aggiungi assistito",
            }

        if code in {"citazione_cf_controparte_non_rilevato", "redazione_controparte_non_strutturata"} or "controparte" in tokens:
            return {
                "action_url": _fascicolo_focus_url(
                    id_fasc,
                    focus="parti",
                    open_modal="parte",
                    role_hint="CONTROPARTE",
                    correction_title="Aggiungi controparte",
                    correction_help="La controparte va strutturata nella pratica prima della redazione o del deposito.",
                ),
                "action_label": "Aggiungi controparte",
            }

        if field in {"tribunale", "numero_rg", "anno_rg", "sezione", "giudice", "valore_causa", "oggetto", "avvocato_referente"}:
            return {
                "action_url": _fascicolo_edit_url(
                    id_fasc,
                    intent=field,
                    highlight=field,
                    correction_title="Completa dati fascicolo",
                    correction_help="Apri la scheda del fascicolo direttamente sul campo che il controllo ha segnalato.",
                ),
                "action_label": "Completa dati fascicolo",
            }

        if service == "TECNICO_PST" or any(token in tokens for token in ("schema", "xml", "datiatto", "registro", "rito", "preview")):
            return {
                "action_url": _deposito_correction_url(
                    id_fasc,
                    intent="registro",
                    correction_title="Configura pre-deposito",
                    correction_help="Il wizard pre-deposito si apre giÃ  con i dati tecnici da confermare o correggere.",
                    prefill_tipo_atto=_prefill_tipo_atto_from_summary(summary),
                    prefill_registro=registry_suggestion,
                ),
                "action_label": "Apri pre-deposito",
            }

        if service == "REDAZIONALE" or any(
            token in tokens for token in ("redazione", "fatti", "facts", "requests", "conclusioni", "richieste", "datiatto")
        ):
            focus_field = "facts"
            highlight_fields = ["facts"]
            if any(token in tokens for token in ("conclusioni", "richieste", "requests")):
                focus_field = "requests_or_conclusions"
                highlight_fields = ["requests_or_conclusions"]
            elif any(token in tokens for token in ("datiatto", "xml", "schema")):
                focus_field = "recipient_or_court"
                highlight_fields = ["case_id", "recipient_or_court", "subject"]
            compile_url = _compiler_correction_url(
                id_fasc,
                model_code=model_code,
                cliente_id=cliente_id,
                intent="redazione",
                focus_field=focus_field,
                highlight_fields=",".join(highlight_fields),
                correction_title="Completa il blocco redazionale",
                correction_help="Il redattore guidato si apre sul blocco da completare o correggere.",
            )
            if compile_url:
                return {"action_url": compile_url, "action_label": "Apri redattore guidato"}

        return {
            "action_url": _fascicolo_edit_url(
                id_fasc,
                correction_title="Verifica il fascicolo",
                correction_help="Controlla e completa i dati generali del fascicolo prima di procedere.",
            ),
            "action_label": "Verifica il fascicolo",
        }

    def _build_responsabile_conformita_disattivata(
        *,
        fascicolo: Fascicolo,
    ) -> dict[str, Any]:
        canale_label = _portale_ufficiale_label(fascicolo) or "PCT civile / lavoro / famiglia"
        modello_label = str(
            getattr(fascicolo, "oggetto", "")
            or getattr(fascicolo, "titolo", "")
            or "Atto"
        ).strip()
        summary_text = (
            "I controlli automatici sono disattivati per questo fascicolo. "
            "Riattiva il flag per rigenerare checklist, workflow e controlli rapidi."
        )
        return {
            "available": True,
            "controls_enabled": False,
            "workflow_label": "Controlli automatici disattivati",
            "readiness_label": "Il report di conformita e' momentaneamente sospeso per scelta utente.",
            "summary": summary_text,
            "overall_state": "disabled",
            "badge_class": "secondary",
            "general": {
                "state": "disabled",
                "label": "Disattivati",
                "score": 0,
                "blocking_count": 0,
                "warning_count": 0,
                "info_count": 0,
                "passed_count": 0,
            },
            "practice_id": "",
            "practice_label": modello_label or "Fascicolo",
            "model_code": "",
            "model_name": modello_label,
            "channel": "",
            "channel_label": canale_label,
            "competence_rule": "",
            "registry_suggestion": "",
            "grade_label": "",
            "resolver": {},
            "semaforo": {
                "workflow": "disabled",
                "generale": "disabled",
                "processuale": "disabled",
                "giuridico": "disabled",
                "tecnico_pst": "disabled",
                "tecnico_ministeriale": "disabled",
                "documentale": "disabled",
                "redazionale": "disabled",
            },
            "sections": {},
            "passed_controls": [],
            "corrections": [],
            "action_gates": {},
            "required_documents": [],
            "missing_documents": [],
            "blocking_issues": [],
            "warning_issues": [],
            "info_issues": [],
            "issues": [],
            "next_steps": ["Riattiva i controlli automatici per rieseguire il report."],
            "sources": [],
            "deposit_ready": False,
            "is_blocking": False,
            "score": 0,
            "last_check_at": "",
            "canale_label": canale_label,
            "modello_label": modello_label,
            "summary_text": summary_text,
            "blockers_count": 0,
            "warnings_count": 0,
            "passed_count": 0,
            "missing_docs_count": 0,
            "ready_reason": "Controlli automatici disattivati per questo fascicolo.",
            "next_step": {
                "title": "Riattiva i controlli automatici",
                "reason": summary_text,
                "cta": "Riattiva controlli",
                "url": f"{url_for('dettaglio_fascicolo', id_fasc=fascicolo.id)}#sezione-responsabile-conformita",
            },
            "checklist": [],
            "workflow": [],
            "groups": [],
        }

    def _build_responsabile_conformita_fascicolo(
        *,
        fascicolo: Fascicolo,
        cliente=None,
        preventivo=None,
        conferimento=None,
        parti=None,
    ) -> dict[str, Any]:
        if not bool(getattr(fascicolo, "compliance_controls_enabled", True)):
            return _build_responsabile_conformita_disattivata(fascicolo=fascicolo)

        from pct.responsabile_conformita import build_fascicolo_compliance_summary

        summary = build_fascicolo_compliance_summary(
            fascicolo=fascicolo,
            cliente=cliente,
            preventivo=preventivo,
            conferimento=conferimento,
            config=app.config,
            utente=g.utente_corrente,
            office_cache_path=os.getenv("PCT_UFFICI_DB", "/data/uffici/uffici_giudiziari.json"),
            parti=parti,
        )
        return _arricchisci_responsabile_conformita(
            summary,
            fascicolo=fascicolo,
            cliente=cliente,
        )

    def _arricchisci_responsabile_conformita(
        summary: Optional[dict],
        *,
        fascicolo: Fascicolo,
        cliente=None,
    ) -> Optional[dict]:
        if not summary or not summary.get("available"):
            return summary

        model_code = str(summary.get("model_code") or "").strip()
        cliente_id = str(getattr(cliente, "id", "") or "").strip()
        compile_url = (
            url_for(
                "template_atti.compila",
                model_code=model_code,
                id_cliente=cliente_id,
                id_fascicolo=fascicolo.id,
            )
            if model_code
            else ""
        )
        detail_url = url_for("dettaglio_fascicolo", id_fasc=fascicolo.id)
        deposit_url = url_for("deposito_prepara", id_fasc=fascicolo.id)

        summary["corrections"] = [
            {
                **issue,
                **_responsabile_issue_action_meta(
                    fascicolo.id,
                    issue,
                    cliente=cliente,
                    summary=summary,
                ),
            }
            for issue in summary.get("corrections", [])
        ]
        summary["corrections"], suppressed_titles = _rc_prune_redundant_corrections(
            list(summary.get("corrections") or [])
        )

        gates = dict(summary.get("action_gates") or {})
        if gates.get("generate_final_act") and compile_url:
            gates["generate_final_act"]["url"] = _compiler_correction_url(
                fascicolo.id,
                model_code=model_code,
                cliente_id=cliente_id,
                intent="redazione_finale",
                focus_field="subject",
                highlight_fields="subject,requests_or_conclusions",
                correction_title="Completa la bozza finale",
                correction_help="Risolvi i blocchi redazionali e strutturali prima della generazione definitiva.",
            )
            gates["generate_final_act"]["url_label"] = "Apri redattore guidato"
        if gates.get("generate_xml") and compile_url:
            gates["generate_xml"]["url"] = _compiler_correction_url(
                fascicolo.id,
                model_code=model_code,
                cliente_id=cliente_id,
                intent="datiatto_xml",
                focus_field="recipient_or_court",
                highlight_fields="case_id,recipient_or_court,subject",
                correction_title="Completa DatiAtto.xml",
                correction_help="Il redattore si apre giÃ  sui campi strutturati minimi utili alla generazione XML.",
            )
            gates["generate_xml"]["url_label"] = "Completa DatiAtto.xml"
        if gates.get("prepare_deposit"):
            gates["prepare_deposit"]["url"] = _deposito_correction_url(
                fascicolo.id,
                correction_title="Configura il pre-deposito",
                correction_help="Conferma registro, ufficio, dati atto e documenti prima della preparazione della busta.",
            )
            gates["prepare_deposit"]["url_label"] = "Apri pre-deposito"
        if gates.get("close_review"):
            gates["close_review"]["url"] = f"{detail_url}#sezione-responsabile-conformita"
            gates["close_review"]["url_label"] = "Rivedi controlli"
        summary["action_gates"] = gates

        corrections = list(summary.get("corrections") or [])
        corrections_by_title: dict[str, dict] = {}
        corrections_by_service: dict[str, list[dict]] = {}
        for correction in corrections:
            title_key = str(correction.get("title") or "").strip().lower()
            if title_key and title_key not in corrections_by_title:
                corrections_by_title[title_key] = correction
            service_key = str(correction.get("service") or "").strip().upper()
            if service_key:
                corrections_by_service.setdefault(service_key, []).append(correction)

        section_order = ["processuale", "documentale", "tecnico_pst", "redazionale"]
        checklist: list[dict[str, Any]] = []
        checklist_seen: set[str] = set()
        groups: list[dict[str, Any]] = []
        display_sections: dict[str, dict[str, Any]] = {}
        for section_key in section_order:
            section = dict((summary.get("sections") or {}).get(section_key) or {})
            section_meta = _rc_section_meta(
                section_key,
                detail_url=detail_url,
                deposit_url=deposit_url,
                compile_url=compile_url,
            )
            group_items: list[dict[str, Any]] = []
            section_items: list[dict[str, str]] = []
            raw_items = list(section.get("items") or [])
            for index, item in enumerate(raw_items):
                title = str(item.get("title") or "").strip()
                if not title:
                    continue
                if title.lower() in suppressed_titles:
                    continue
                normalized = _rc_normalize_status(item.get("state"))
                correction = corrections_by_title.get(title.lower(), {})
                item_url = str(correction.get("action_url") or (section_meta["url"] if normalized != "ok" else "")).strip()
                item_cta = str(
                    correction.get("action_label")
                    or correction.get("action")
                    or (section_meta["cta"] if item_url else "")
                ).strip()
                item_payload = {
                    "label": title,
                    "title": title,
                    "status": normalized,
                    "note": str(item.get("detail") or "").strip(),
                    "reason": str(item.get("detail") or "").strip(),
                    "source": str(correction.get("source") or section.get("label") or "").strip(),
                    "where": section_meta["where"],
                    "url": item_url,
                    "cta": item_cta,
                    "_sort": (_rc_status_rank(normalized), index),
                }
                group_items.append(item_payload)
                section_items.append(
                    {
                        "state": normalized,
                        "title": title,
                        "detail": str(item.get("detail") or "").strip(),
                        "action": item_cta,
                    }
                )
                # Checklist: solo controlli azionabili (block/warning),
                # i controlli "ok" restano solo nei gruppi di sezione
                if normalized != "ok":
                    checklist_key = title.lower()
                    if checklist_key not in checklist_seen:
                        checklist_seen.add(checklist_key)
                        checklist.append(item_payload.copy())

            group_items.sort(key=lambda row: row["_sort"])
            for row in group_items:
                row.pop("_sort", None)
            display_sections[section_key] = {
                "label": str(section.get("label") or section_key.replace("_", " ").title()).strip(),
                "state": _rc_state_from_items(
                    section_items,
                    default=_rc_normalize_status(section.get("state")),
                ),
                "items": section_items,
            }
            groups.append(
                {
                    "title": display_sections[section_key]["label"],
                    "status": display_sections[section_key]["state"],
                    "items": group_items,
                }
            )

        checklist.sort(key=lambda row: row["_sort"])
        for row in checklist:
            row.pop("_sort", None)

        def _first_correction_for_service(service_name: str) -> dict:
            return dict((corrections_by_service.get(service_name) or [{}])[0] or {})

        next_step_source = next(
            (
                correction
                for correction in corrections
                if _rc_normalize_status(correction.get("state")) == "block"
            ),
            None,
        ) or next(
            (
                correction
                for correction in corrections
                if _rc_normalize_status(correction.get("state")) == "warning"
            ),
            None,
        )
        if next_step_source:
            next_step = {
                "title": str(
                    next_step_source.get("action")
                    or next_step_source.get("title")
                    or "Apri correzione guidata"
                ).strip(),
                "reason": str(
                    next_step_source.get("detail")
                    or next_step_source.get("source")
                    or summary.get("summary")
                    or ""
                ).strip(),
                "cta": str(
                    next_step_source.get("action_label")
                    or next_step_source.get("action")
                    or "Correggi"
                ).strip(),
                "url": str(next_step_source.get("action_url") or detail_url).strip(),
            }
        else:
            prepare_gate = gates.get("prepare_deposit") or {}
            next_step = {
                "title": "Apri il pre-deposito tecnico",
                "reason": str(
                    prepare_gate.get("reason")
                    or summary.get("summary")
                    or "Rivedi il fascicolo prima del deposito."
                ).strip(),
                "cta": str(prepare_gate.get("url_label") or "Apri pre-deposito").strip(),
                "url": str(prepare_gate.get("url") or deposit_url).strip(),
            }

        sections = display_sections
        process_section = dict(sections.get("processuale") or {})
        document_section = dict(sections.get("documentale") or {})
        tech_section = dict(sections.get("tecnico_pst") or {})
        redaction_section = dict(sections.get("redazionale") or {})

        generate_final_gate = dict(gates.get("generate_final_act") or {})
        generate_xml_gate = dict(gates.get("generate_xml") or {})
        prepare_gate = dict(gates.get("prepare_deposit") or {})
        close_gate = dict(gates.get("close_review") or {})
        document_correction = _first_correction_for_service("DOCUMENTALE")

        workflow = [
            {
                "label": "Redazione atto",
                "status": _rc_gate_status(generate_final_gate, redaction_section.get("state")),
                "note": str(
                    generate_final_gate.get("reason")
                    or _rc_first_section_message(
                        redaction_section,
                        ok_fallback="Il blocco redazionale risulta coerente con il fascicolo.",
                    )
                ).strip(),
                "url": str(generate_final_gate.get("url") or compile_url).strip(),
                "cta": str(generate_final_gate.get("url_label") or "Apri redattore").strip(),
            },
            {
                "label": "Allegati obbligatori",
                "status": _rc_normalize_status(document_section.get("state")),
                "note": _rc_first_section_message(
                    document_section,
                    ok_fallback="Gli allegati oggi richiesti risultano presenti o gia censiti.",
                ),
                "url": str(
                    document_correction.get("action_url")
                    or f"{detail_url}#sezione-documenti-fascicolo"
                ).strip(),
                "cta": str(
                    document_correction.get("action_label")
                    or document_correction.get("action")
                    or "Apri allegati"
                ).strip(),
            },
            {
                "label": "XML ministeriale",
                "status": _rc_gate_status(generate_xml_gate, tech_section.get("state")),
                "note": str(
                    generate_xml_gate.get("reason")
                    or "Verifica i dati strutturati necessari alla generazione XML."
                ).strip(),
                "url": str(generate_xml_gate.get("url") or deposit_url).strip(),
                "cta": str(generate_xml_gate.get("url_label") or "Completa XML").strip(),
            },
            {
                "label": "Verifica tecnica PST",
                "status": _rc_normalize_status(tech_section.get("state")),
                "note": _rc_first_section_message(
                    tech_section,
                    ok_fallback="Nessun errore tecnico bloccante rilevato sui controlli PST.",
                ),
                "url": str(close_gate.get("url") or deposit_url).strip(),
                "cta": str(close_gate.get("url_label") or "Rivedi").strip(),
            },
            {
                "label": "Pre-deposito",
                "status": _rc_gate_status(prepare_gate, summary.get("overall_state")),
                "note": str(
                    prepare_gate.get("reason")
                    or "Riesegui il pre-deposito dopo le correzioni."
                ).strip(),
                "url": str(prepare_gate.get("url") or deposit_url).strip(),
                "cta": str(prepare_gate.get("url_label") or "Apri pre-deposito").strip(),
            },
        ]

        general = dict(summary.get("general") or {})
        visible_items = [item for group in groups for item in group.get("items", [])]
        visible_blockers = sum(1 for item in visible_items if item.get("status") == "block")
        visible_warnings = sum(1 for item in visible_items if item.get("status") == "warning")
        visible_passed = sum(1 for item in visible_items if item.get("status") == "ok")
        deposit_ready = bool(prepare_gate.get("allowed")) if prepare_gate.get("applicable", True) else summary.get("overall_state") == "ok"
        blocking_count = visible_blockers or int(general.get("blocking_count") or 0)
        summary.update(
            {
                "deposit_ready": deposit_ready,
                "is_blocking": blocking_count > 0,
                "score": int(general.get("score") or 0),
                "last_check_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
                "canale_label": str(summary.get("channel_label") or "").strip(),
                "modello_label": str(summary.get("model_name") or "").strip(),
                "summary_text": str(summary.get("summary") or "").strip(),
                "blockers_count": blocking_count,
                "warnings_count": visible_warnings or int(general.get("warning_count") or 0),
                "passed_count": visible_passed or int(general.get("passed_count") or 0),
                "missing_docs_count": len(summary.get("missing_documents") or []),
                "ready_reason": (
                    "Deposito pronto: non risultano blocchi residui sul fascicolo."
                    if deposit_ready
                    else f"Deposito non pronto: {str(summary.get('summary') or '').strip()}"
                ),
                "next_step": next_step,
                "checklist": checklist[:12],
                "workflow": workflow,
                "groups": groups,
            }
        )
        return summary

    def _fascicolo_form_correction_context() -> dict:
        intent = (request.args.get("intent", "") or "").strip()
        highlight = (request.args.get("highlight", "") or "").strip()
        title = (request.args.get("correction_title", "") or "").strip()
        help_text = (request.args.get("correction_help", "") or "").strip()
        if not any([intent, highlight, title, help_text]):
            return {}
        return {
            "active": True,
            "intent": intent,
            "highlight": highlight,
            "title": title or "Correzione guidata del fascicolo",
            "help": help_text or "Completa il campo evidenziato per superare il controllo di conformita'.",
        }

    def _deposito_correction_context(fascicolo: Fascicolo) -> dict:
        correction_title = (request.args.get("correction_title", "") or "").strip()
        correction_help = (request.args.get("correction_help", "") or "").strip()
        prefill_tipo_atto = (request.args.get("prefill_tipo_atto", "") or "").strip()
        prefill_registro = (request.args.get("prefill_registro", "") or "").strip().upper()
        return {
            "active": any([correction_title, correction_help, prefill_tipo_atto, prefill_registro]),
            "title": correction_title or "Pre-deposito guidato",
            "help": correction_help or "Verifica dati atto, registro, ufficio e allegati prima della generazione della busta.",
            "prefill_tipo_atto": prefill_tipo_atto,
            "prefill_registro": prefill_registro,
            "prefill_oggetto": str(getattr(fascicolo, "oggetto", "") or fascicolo.titolo or "").strip(),
        }

    def _tipo_documento_da_nome_portale(nome_file: str) -> TipoDocumento:
        nome = Path(nome_file).name.lower()
        checks = [
            (("sentenza",), TipoDocumento.SENTENZA),
            (("ordinanza",), TipoDocumento.ORDINANZA),
            (("decreto",), TipoDocumento.DECRETO),
            (("verbale", "udienza"), TipoDocumento.VERBALE),
            (("memoria",), TipoDocumento.MEMORIA),
            (("ricorso",), TipoDocumento.RICORSO),
            (("citazione",), TipoDocumento.CITAZIONE),
            (("comparsa",), TipoDocumento.COMPARSA),
            (("procura",), TipoDocumento.PROCURA),
            (("notifica",), TipoDocumento.NOTIFICA),
            (("ricevuta", "accettazione", "consegna", "esito", ".eml", ".msg", ".xml", ".html", ".htm"), TipoDocumento.COMUNICAZIONE),
            (("busta", ".enc", "deposito"), TipoDocumento.DEPOSITO_PCT),
        ]
        for needles, tipo in checks:
            if any(needle in nome for needle in needles):
                return tipo
        if nome.endswith((".pdf", ".p7m")):
            return TipoDocumento.ATTO_GIUDIZIARIO
        return TipoDocumento.ALLEGATO

    def _tipo_documento_da_item_portale(item: dict) -> TipoDocumento:
        nome = str(item.get("nome") or item.get("nome_documento") or "").strip()
        tipo_atto = str(item.get("tipo_atto") or "").strip()
        tipo = str(item.get("tipo") or "").strip()
        testo = _fascicolo_text(nome, tipo_atto, tipo)
        sezione = _sezione_portale_server(item)

        if "procura" in testo:
            return TipoDocumento.PROCURA
        if "sentenza" in testo:
            return TipoDocumento.SENTENZA
        if "ordinanza" in testo:
            return TipoDocumento.ORDINANZA
        if "decreto" in testo:
            return TipoDocumento.DECRETO
        if any(token in testo for token in ("verbale udienza", "verbaleudienza", "verbale", "udienza")):
            return TipoDocumento.VERBALE
        if "memoria" in testo:
            return TipoDocumento.MEMORIA
        if "ricorso" in testo:
            return TipoDocumento.RICORSO
        if "citazione" in testo:
            return TipoDocumento.CITAZIONE
        if "comparsa" in testo:
            return TipoDocumento.COMPARSA
        if "notifica" in testo:
            return TipoDocumento.NOTIFICA
        if any(token in testo for token in ("ricevuta", "accettazione", "consegna", "esito", "comunicazione", "pec")):
            return TipoDocumento.COMUNICAZIONE
        if sezione == "comunicazioni":
            return TipoDocumento.COMUNICAZIONE
        if sezione == "udienze":
            return TipoDocumento.VERBALE
        if sezione == "istanze":
            return TipoDocumento.ALLEGATO

        return _tipo_documento_da_nome_portale(nome)

    def _espandi_file_importato_portale(
        nome_file: str,
        contenuto: bytes,
        data_documento: str = "",
        origine: str = "",
    ) -> list[dict]:
        nome_sicuro = Path(nome_file).name or "documento"
        data_fallback = data_documento or date.today().isoformat()
        if nome_sicuro.lower().endswith(".zip"):
            try:
                with _zipfile.ZipFile(io.BytesIO(contenuto)) as archivio:
                    estratti = []
                    for info in archivio.infolist():
                        if info.is_dir():
                            continue
                        if info.filename.startswith("__MACOSX/"):
                            continue
                        nome_interno = Path(info.filename).name
                        if not nome_interno or nome_interno.lower() in {".ds_store", "thumbs.db"}:
                            continue
                        payload = archivio.read(info)
                        if not payload:
                            continue
                        data_info = data_fallback
                        try:
                            anno, mese, giorno = info.date_time[:3]
                            if anno >= 1980:
                                data_info = date(anno, mese, giorno).isoformat()
                        except Exception:
                            pass
                        estratti.append({
                            "nome": nome_interno,
                            "contenuto": payload,
                            "data_documento": data_info,
                            "origine": f"{origine or nome_sicuro}:{info.filename}",
                        })
                    if estratti:
                        return estratti
            except (_zipfile.BadZipFile, RuntimeError, ValueError):
                pass
        return [{
            "nome": nome_sicuro,
            "contenuto": contenuto,
            "data_documento": data_fallback,
            "origine": origine or nome_sicuro,
        }]

    def _salva_documento_fascicolo(
        gf: GestioneFascicoli,
        id_fasc: str,
        nome_file: str,
        raw: bytes,
        tipo_doc: TipoDocumento,
        note: str = "",
        data_documento: str = "",
        firmato: bool = False,
        caricato_da: str = "",
    ) -> Documento:
        contenuto = _encrypt_doc(raw)
        doc = gf.aggiungi_documento(
            id_fasc,
            nome_file=nome_file,
            tipo=tipo_doc,
            contenuto=contenuto,
            note=note,
            data_documento=data_documento,
            firmato=firmato,
            caricato_da=caricato_da,
        )
        # â”€â”€ Conversione automatica PDF â†’ PDF/A-2B (D.M. 44/2011 art. 12) â”€â”€
        # Se il file Ã¨ un PDF non firmato, lo converte in PDF/A tramite
        # Ghostscript per garantire conformitÃ  al deposito telematico.
        percorso_doc = str(gf.percorso_documento(id_fasc, doc.id))
        if nome_file.lower().endswith(".pdf") and not firmato:
            try:
                from pct.validazione import verifica_pdfa, converti_pdfa
                esito_pdfa = verifica_pdfa(percorso_doc)
                if esito_pdfa.get("conforme") is False:
                    conv = converti_pdfa(percorso_doc)
                    if conv.get("ok"):
                        app.logger.info(
                            "PDF/A auto-conversione: %s â†’ PDF/A-2B (%s)",
                            nome_file, conv.get("messaggio", ""),
                        )
                    else:
                        app.logger.warning(
                            "PDF/A auto-conversione fallita per %s: %s",
                            nome_file, conv.get("messaggio", ""),
                        )
            except Exception as exc:
                app.logger.warning("PDF/A auto-conversione errore per %s: %s", nome_file, exc)
        _accoda_ocr(
            percorso=percorso_doc,
            hash_sha256=doc.hash_sha256,
            id_fasc=id_fasc,
            id_doc=doc.id,
            nome_doc=nome_file,
            tipo_doc=tipo_doc.value,
            index_path=app.config["SEARCH_INDEX"],
        )
        return doc

    def _leggi_staging_documenti_portale(fasc: Fascicolo) -> tuple[list[dict], Path]:
        cartella = _pst_import_dir_for_fascicolo(fasc)
        items: list[dict] = []
        if not cartella.exists():
            return items, cartella
        for path in sorted(cartella.rglob("*")):
            if not path.is_file():
                continue
            if path.name.lower() in {".ds_store", "thumbs.db"}:
                continue
            payload = path.read_bytes()
            if not payload:
                continue
            data_doc = date.fromtimestamp(path.stat().st_mtime).isoformat()
            origine = str(path.relative_to(cartella)).replace("\\", "/")
            items.extend(_espandi_file_importato_portale(
                nome_file=path.name,
                contenuto=payload,
                data_documento=data_doc,
                origine=origine,
            ))
        return items, cartella

    def _archivia_staging_documenti_portale(cartella: Path) -> str:
        if not cartella.exists():
            return ""
        has_files = any(path.is_file() for path in cartella.rglob("*"))
        if not has_files:
            return ""
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        destinazione = cartella.parent / "_importati" / f"{cartella.name}_{stamp}"
        destinazione.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(cartella), str(destinazione))
        cartella.mkdir(parents=True, exist_ok=True)
        return str(destinazione)

    def _slug_portale_chunk(value: str, fallback: str = "n.d.") -> str:
        testo = str(value or "").strip()
        if not testo:
            return fallback
        testo = unicodedata.normalize("NFKD", testo).encode("ascii", "ignore").decode("ascii")
        testo = re.sub(r"[^a-zA-Z0-9._-]+", "-", testo).strip("-._").lower()
        return testo or fallback

    def _sezione_portale_server(item: dict) -> str:
        tipo_atto = str(item.get("tipo_atto") or item.get("tipo") or "").lower()
        nome = str(item.get("nome") or item.get("nome_documento") or "").lower()
        testo = " ".join(part for part in (tipo_atto, nome) if part)
        if "istanza" in testo:
            return "istanze"
        if any(token in testo for token in ("verbaleudienza", "verbale udienza", "udienza", "verbale")):
            return "udienze"
        if any(token in testo for token in ("ordinanza", "decreto", "sentenza", "provvedimento")):
            return "provvedimenti"
        if (
            nome.endswith(".eml")
            or nome.endswith(".msg")
            or nome.endswith(".xml")
            or "ricevuta" in nome
            or "esito" in nome
            or "comunicazione" in testo
            or "pec" in testo
        ):
            return "comunicazioni"
        return "atti"

    def _scrivi_file_univoco(destinazione: Path, payload: bytes) -> Path:
        destinazione.parent.mkdir(parents=True, exist_ok=True)
        candidato = destinazione
        indice = 1
        while candidato.exists():
            candidato = destinazione.with_name(
                f"{destinazione.stem}_{indice}{destinazione.suffix}"
            )
            indice += 1
        candidato.write_bytes(payload)
        return candidato

    def _salva_albero_originale_documenti_portale(fasc: Fascicolo, items: list[dict]) -> str:
        if not items:
            return ""
        base_root = _pst_import_dir_for_fascicolo(fasc).parent / "_alberi_originali" / fasc.id
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        root = base_root / stamp
        scritti = 0
        for idx, item in enumerate(items, start=1):
            nome = Path(str(item.get("nome") or f"documento_{idx}")).name or f"documento_{idx}"
            payload = item.get("contenuto", b"")
            if not payload:
                continue
            sezione = _slug_portale_chunk(_sezione_portale_server(item), "atti")
            deposito_src = (
                str(item.get("id_deposito_pct") or "").strip()
                or str(item.get("id_deposito_esterno") or "").strip()
                or "_".join(
                    part for part in (
                        str(item.get("data_documento") or "").strip(),
                        str(item.get("tipo_atto") or "").strip(),
                    ) if part
                )
            )
            deposito = _slug_portale_chunk(deposito_src, "senza_deposito")
            tipo = _slug_portale_chunk(str(item.get("tipo_atto") or Path(nome).stem), "documento")
            _scrivi_file_univoco(root / sezione / f"{deposito}_{tipo}" / nome, payload)
            scritti += 1
        return str(root) if scritti else ""

    def _decode_portale_downloaded_items(files: list[dict]) -> list[dict]:
        items: list[dict] = []
        for file_item in files or []:
            nome = str((file_item or {}).get("nome") or "").strip()
            contenuto_b64 = str((file_item or {}).get("contenuto_b64") or "").strip()
            if not nome or not contenuto_b64:
                continue
            try:
                payload = base64.b64decode(contenuto_b64)
            except Exception:
                continue
            espansi = _espandi_file_importato_portale(
                nome_file=nome,
                contenuto=payload,
                data_documento=str((file_item or {}).get("data_documento") or date.today().isoformat()),
                origine=str((file_item or {}).get("origine") or f"local-signer:{nome}"),
            )
            for item in espansi:
                item["id_deposito_esterno"] = str((file_item or {}).get("id_deposito_esterno") or "").strip()
                item["id_deposito_pct"] = str((file_item or {}).get("id_deposito_pct") or "").strip()
                item["id_documento_portale"] = str((file_item or {}).get("id_documento_portale") or "").strip()
                item["tipo_atto"] = str((file_item or {}).get("tipo_atto") or "").strip()
                item["tipo"] = str((file_item or {}).get("tipo") or "").strip()
                item["id_cat"] = str((file_item or {}).get("id_cat") or "").strip()
                item["id_repeatto"] = str((file_item or {}).get("id_repeatto") or "").strip()
                item["msg_id"] = str((file_item or {}).get("msg_id") or "").strip()
                item["content_type"] = str((file_item or {}).get("content_type") or "").strip()
                item["nome_file_originale"] = str((file_item or {}).get("nome_file_originale") or "").strip()
                original_documento_portale = bool((file_item or {}).get("original_documento_portale", True))
                item["original_documento_portale"] = original_documento_portale
                item["modalita_documento_portale"] = (
                    str((file_item or {}).get("modalita_documento_portale") or "").strip()
                    or ("originale" if original_documento_portale else "copia")
                )
            items.extend(espansi)
        return items

    def _normalizza_nome_match_portale(nome_file: str) -> str:
        testo = Path(str(nome_file or "")).name.strip().lower()
        if not testo:
            return ""
        testo = re.sub(r"\s+\(\d+\)(?=(\.[^.]+)+$|$)", "", testo)
        while True:
            cambiato = False
            for suffix in (".p7m", ".pdf", ".txt", ".eml", ".msg", ".xml", ".html", ".htm", ".zip"):
                if testo.endswith(suffix):
                    testo = testo[: -len(suffix)]
                    cambiato = True
            if not cambiato:
                break
        testo = unicodedata.normalize("NFKD", testo).encode("ascii", "ignore").decode("ascii")
        return re.sub(r"[^a-z0-9]+", "", testo)

    def _nome_preview_documento(nome_file: str) -> str:
        nome = Path(str(nome_file or "")).name.strip()
        if nome.lower().endswith(".p7m"):
            nome = nome[:-4]
        return nome

    def _mime_preview_documento(nome_file: str, payload: bytes | None = None) -> tuple[str, str] | None:
        nome_preview = _nome_preview_documento(nome_file)
        lower = nome_preview.lower()

        if payload is not None:
            if payload.startswith(b"%PDF"):
                return "application/pdf", nome_preview or "documento.pdf"
            if payload.startswith(b"\xff\xd8\xff"):
                return "image/jpeg", nome_preview or "documento.jpg"
            if payload.startswith(b"\x89PNG\r\n\x1a\n"):
                return "image/png", nome_preview or "documento.png"
            if payload.startswith((b"GIF87a", b"GIF89a")):
                return "image/gif", nome_preview or "documento.gif"
            return None

        if lower.endswith(".pdf"):
            return "application/pdf", nome_preview
        if lower.endswith((".jpg", ".jpeg")):
            return "image/jpeg", nome_preview
        if lower.endswith(".png"):
            return "image/png", nome_preview
        if lower.endswith(".gif"):
            return "image/gif", nome_preview
        return None

    def _estrai_contenuto_p7m_per_preview(data: bytes) -> bytes | None:
        try:
            from asn1crypto import cms
        except Exception:
            return None

        try:
            content_info = cms.ContentInfo.load(data)
            if content_info["content_type"].native != "signed_data":
                return None
            signed_data = content_info["content"]
            encap = signed_data["encap_content_info"]
            contenuto = encap["content"]
            if contenuto is None:
                return None
            native = getattr(contenuto, "native", None)
            if isinstance(native, bytes):
                return native
            if isinstance(contenuto, bytes):
                return contenuto
            if native is not None:
                try:
                    return bytes(native)
                except Exception:
                    return None
        except Exception:
            return None
        return None

    def _payload_preview_da_versioni_documento(gf, doc: Documento) -> bytes | None:
        nome_preview = _nome_preview_documento(doc.nome)
        for versione in reversed(doc.versioni or []):
            try:
                percorso = gf.documents_dir / str(versione.percorso or "")
                if not percorso.exists():
                    continue
                contenuto = _decrypt_doc(percorso.read_bytes())
                if _mime_preview_documento(nome_preview, contenuto):
                    return contenuto
            except Exception:
                continue
        return None

    def _firma_payload_corrente_o_sibling(percorso: Path, nome_file: str, data_corrente: bytes) -> bytes:
        """Restituisce il payload firmato reale (.p7m) anche nei flussi legacy PKCS#11."""
        nome = str(nome_file or "").strip().lower()
        if not nome.endswith(".p7m"):
            return data_corrente
        try:
            from pct.firma import _is_cades as _is_cades_payload
        except Exception:
            _is_cades_payload = None
        try:
            if _is_cades_payload and _is_cades_payload(data_corrente):
                return data_corrente
        except Exception:
            pass
        sibling = Path(str(percorso) + ".p7m")
        if sibling.exists():
            try:
                return _decrypt_doc(sibling.read_bytes())
            except Exception:
                return data_corrente
        return data_corrente

    def _luogo_timbro_firma_visibile() -> str:
        from visible_signature import resolve_visible_signature_place

        try:
            studio_cfg = get_config_studio().config.studio
        except Exception:
            studio_cfg = None
        return resolve_visible_signature_place(
            city=getattr(studio_cfg, "city", "") if studio_cfg else "",
            province=getattr(studio_cfg, "province", "") if studio_cfg else "",
            address=getattr(studio_cfg, "indirizzo", "") if studio_cfg else "",
        )

    def _formatta_data_firma_visibile(valore: str) -> str:
        from visible_signature import format_visible_signature_datetime

        return format_visible_signature_datetime(valore)

    def _normalizza_modalita_firma_visibile(valore: str) -> str:
        from visible_signature import normalize_visible_signature_mode

        return normalize_visible_signature_mode(valore)

    def _testo_timbro_firma_visibile(firme: list[dict]) -> str:
        from visible_signature import build_visible_signature_text

        if not firme:
            return ""
        firma = (firme or [{}])[0] or {}
        return build_visible_signature_text(
            intestatario=str(firma.get("intestatario") or firma.get("cn") or "").strip(),
            data_firma=firma.get("data_firma"),
            luogo=_luogo_timbro_firma_visibile(),
        )

    def _applica_timbro_firma_visibile(pdf_data: bytes, firme: list[dict]) -> bytes:
        from visible_signature import (
            apply_visible_signature_stamp_from_firme,
            has_visible_signature_stamp,
        )

        try:
            studio_cfg = get_config_studio().config.studio
        except Exception:
            studio_cfg = None

        stamped = apply_visible_signature_stamp_from_firme(
            pdf_data,
            firme,
            city=getattr(studio_cfg, "city", "") if studio_cfg else "",
            address=getattr(studio_cfg, "indirizzo", "") if studio_cfg else "",
        )
        if stamped != pdf_data or has_visible_signature_stamp(pdf_data):
            return stamped
        if not pdf_data.startswith(b"%PDF"):
            return pdf_data
        testo = _testo_timbro_firma_visibile(firme)
        if not testo:
            return pdf_data
        app.logger.warning("Impossibile applicare il timbro firma visibile: fallback non disponibile")
        return pdf_data

    def _catalogo_documenti_portale_fascicolo(fasc: Fascicolo) -> list[dict]:
        documenti_locali_per_deposito: dict[str, dict[str, list[Documento]]] = {}
        for doc in fasc.documenti or []:
            dep_id = str(getattr(doc, "id_deposito_pct", "") or "").strip()
            if not dep_id:
                continue
            key = _normalizza_nome_match_portale(str(getattr(doc, "nome", "") or ""))
            if not key:
                continue
            documenti_locali_per_deposito.setdefault(dep_id, {}).setdefault(key, []).append(doc)

        catalogo: list[dict] = []
        for dep in fasc.depositi_pct or []:
            imported_docs = documenti_locali_per_deposito.get(dep.id, {})
            for pdoc in getattr(dep, "documenti_portale", []) or []:
                nome = str((pdoc or {}).get("nome") or "").strip()
                key = _normalizza_nome_match_portale(nome)
                if not nome or not key:
                    continue
                docs_locali = list(imported_docs.get(key, []))
                docs_locali.sort(
                    key=lambda row: (
                        getattr(row, "data_caricamento", "") or "",
                        getattr(row, "nome", "") or "",
                    ),
                    reverse=True,
                )
                doc_locale = docs_locali[0] if docs_locali else None
                preview_info = _mime_preview_documento(getattr(doc_locale, "nome", "") or nome)
                catalogo.append({
                    "id_deposito_pct": dep.id,
                    "id_deposito_esterno": str(getattr(dep, "id_deposito_esterno", "") or "").strip(),
                    "tipo_atto": str((pdoc or {}).get("tipo_atto") or getattr(dep, "tipo_atto", "") or "").strip(),
                    "id_documento_portale": str((pdoc or {}).get("id_documento") or "").strip(),
                    "id_cat": str((pdoc or {}).get("id_cat") or "").strip(),
                    "id_repeatto": str((pdoc or {}).get("id_repeatto") or "").strip(),
                    "msg_id": str((pdoc or {}).get("msg_id") or "").strip(),
                    "data_documento": str((pdoc or {}).get("data_deposito") or "").strip(),
                    "data_deposito": str((pdoc or {}).get("data_deposito") or "").strip(),
                    "nome": nome,
                    "tipo": str((pdoc or {}).get("tipo") or "Documento").strip(),
                    "mittente": str((pdoc or {}).get("mittente") or "").strip(),
                    "dimensione_bytes": int((pdoc or {}).get("dimensione_bytes") or 0),
                    "disponibile": bool((pdoc or {}).get("disponibile", True)),
                    "key": key,
                    "gia_importato": bool(docs_locali),
                    "local_doc_id": getattr(doc_locale, "id", "") if doc_locale else "",
                    "local_doc_nome": getattr(doc_locale, "nome", "") if doc_locale else "",
                    "local_doc_firmato": bool(getattr(doc_locale, "firmato_digitalmente", False)) if doc_locale else False,
                    "local_doc_previewabile": bool(preview_info),
                })
        return catalogo

    def _gruppa_catalogo_documenti_portale(catalogo: list[dict]) -> dict[str, list[dict]]:
        grouped: dict[str, list[dict]] = {}
        for row in catalogo or []:
            dep_id = str(row.get("id_deposito_pct") or "").strip()
            if not dep_id:
                data_key = str(row.get("data_deposito") or "").strip()
                mittente_key = str(row.get("mittente") or "").strip()
                dep_id = f"__{data_key}__{mittente_key}"
            if not dep_id:
                continue
            grouped.setdefault(dep_id, []).append(row)
        for dep_id, items in grouped.items():
            items.sort(
                key=lambda item: (
                    item.get("data_deposito") or "",
                    item.get("nome") or "",
                    item.get("id_documento_portale") or "",
                ),
                reverse=True,
            )
            grouped[dep_id] = items
        return grouped

    def _match_catalogo_documento_portale(
        fasc: Fascicolo,
        item: dict,
        catalogo: list[dict],
    ) -> dict | None:
        dep_ids_validi = {dep.id for dep in (fasc.depositi_pct or [])}
        dep_pct = str(item.get("id_deposito_pct") or "").strip()
        if dep_pct and dep_pct in dep_ids_validi:
            return next((row for row in catalogo if row["id_deposito_pct"] == dep_pct), None)

        doc_portale_id = str(item.get("id_documento_portale") or "").strip()
        if doc_portale_id:
            row = next((entry for entry in catalogo if entry["id_documento_portale"] == doc_portale_id), None)
            if row:
                return row

        dep_esterno = str(item.get("id_deposito_esterno") or item.get("id_deposito") or "").strip()
        if dep_esterno:
            by_dep = [entry for entry in catalogo if entry["id_deposito_esterno"] == dep_esterno]
            if len(by_dep) == 1:
                return by_dep[0]
            item_key = _normalizza_nome_match_portale(str(item.get("nome") or ""))
            if item_key:
                exact = [entry for entry in by_dep if entry["key"] == item_key]
                if len(exact) == 1:
                    return exact[0]

        item_key = _normalizza_nome_match_portale(str(item.get("nome") or ""))
        if len(item_key) < 8:
            return None
        exact = [entry for entry in catalogo if entry["key"] == item_key]
        if len(exact) == 1:
            return exact[0]
        return None

    def _importa_documenti_portale_items(
        *,
        gf: GestioneFascicoli,
        fasc: Fascicolo,
        items: list[dict],
        note_importazione: str = "",
        usa_staging: bool = False,
        staging_dir: Path | None = None,
    ) -> dict:
        fonte = _portale_ufficiale_label(fasc)
        u = g.utente_corrente
        documenti_creati: list[dict] = []

        # Indice dei nomi normalizzati giÃ  presenti nel fascicolo (dedup import ripetuto)
        nomi_esistenti: dict[str, Documento] = {
            _normalizza_nome_match_portale(d.nome): d
            for d in fasc.documenti
            if d.nome
        }

        for item in items:
            nome = item.get("nome", "").strip()
            payload = item.get("contenuto", b"")
            if not nome or not payload:
                continue
            # Deduplicazione: se il file (per nome normalizzato) Ã¨ giÃ  nel fascicolo,
            # riutilizza il documento esistente senza crearne un duplicato.
            nome_norm = _normalizza_nome_match_portale(nome)
            doc_esistente = nomi_esistenti.get(nome_norm)
            if doc_esistente:
                documenti_creati.append({"doc": doc_esistente, "item": item})
                continue
            tipo_doc = _tipo_documento_da_item_portale(item)
            note_doc = [f"Importato da {fonte} il {date.today().isoformat()}"]
            if note_importazione:
                note_doc.append(note_importazione)
            origine = (item.get("origine", "") or "").strip()
            if origine and origine != nome:
                note_doc.append(f"Origine: {origine}")
            tipo_atto = str(item.get("tipo_atto") or item.get("tipo") or "").strip()
            if tipo_atto:
                note_doc.append(f"Tipo atto portale: {tipo_atto}")
            doc = _salva_documento_fascicolo(
                gf=gf,
                id_fasc=fasc.id,
                nome_file=nome,
                raw=payload,
                tipo_doc=tipo_doc,
                note=" | ".join(note_doc),
                data_documento=item.get("data_documento", "") or date.today().isoformat(),
                firmato=nome.lower().endswith(".p7m"),
                caricato_da=u.username if u else "",
            )
            documenti_creati.append({"doc": doc, "item": item})
            nomi_esistenti[nome_norm] = doc

        if not documenti_creati:
            raise ValueError("I file selezionati non contengono documenti importabili.")

        catalogo = _catalogo_documenti_portale_fascicolo(fasc)
        docs_per_deposito: dict[str, list[str]] = {}
        documenti_sfusi: list[str] = []
        for entry in documenti_creati:
            match = _match_catalogo_documento_portale(fasc, entry["item"], catalogo)
            if match and match["id_deposito_pct"]:
                docs_per_deposito.setdefault(match["id_deposito_pct"], []).append(entry["doc"].id)
            else:
                documenti_sfusi.append(entry["doc"].id)

        depositi_agganciati: list[str] = []
        for dep_id, doc_ids in docs_per_deposito.items():
            dep = next((row for row in fasc.depositi_pct if row.id == dep_id), None)
            if not dep:
                documenti_sfusi.extend(doc_ids)
                continue
            descrizione_link = (
                f"{len(doc_ids)} file ufficiali acquisiti localmente da {fonte}."
                + (f" {note_importazione}" if note_importazione else "")
            ).strip()
            gf.collega_documenti_a_deposito_portale(
                fasc.id,
                dep_id,
                doc_ids,
                note=descrizione_link,
                registrato_da=u.username if u else "",
            )
            depositi_agganciati.append(dep_id)

        deposito_generico = None
        if documenti_sfusi:
            pec_tribunale = ""
            if fasc.tribunale:
                try:
                    uff = ClientReGINde().cerca_ufficio_giudiziario(fasc.tribunale)
                    pec_tribunale = uff.pec if uff else ""
                except Exception:
                    pec_tribunale = ""

            docs_creati_index = {entry["doc"].id: entry["doc"] for entry in documenti_creati}
            principali = [
                docs_creati_index[doc_id].nome
                for doc_id in documenti_sfusi
                if docs_creati_index[doc_id].tipo
                in {
                    TipoDocumento.ATTO_GIUDIZIARIO,
                    TipoDocumento.RICORSO,
                    TipoDocumento.CITAZIONE,
                    TipoDocumento.COMPARSA,
                    TipoDocumento.MEMORIA,
                    TipoDocumento.SENTENZA,
                    TipoDocumento.ORDINANZA,
                    TipoDocumento.DECRETO,
                }
            ]
            principale = principali[0] if principali else docs_creati_index[documenti_sfusi[0]].nome
            descrizione_lotto = (
                f"{len(documenti_sfusi)} documenti ufficiali acquisiti da {fonte}."
                + (f" {note_importazione}" if note_importazione else "")
            ).strip()
            deposito_generico = gf.registra_import_documenti_portale(
                id_fasc=fasc.id,
                fonte=fonte,
                documenti_ids=documenti_sfusi,
                tipo_atto=_tipo_lotto_portale(fasc),
                note=descrizione_lotto,
                registrato_da=u.username if u else "",
                pec_destinatario=pec_tribunale,
                nome_atto_principale=principale,
            )

        staging_archived = ""
        if usa_staging and staging_dir is not None:
            staging_archived = _archivia_staging_documenti_portale(staging_dir)

        audit(
            "fascicoli.documento.importa_portale",
            "fascicolo",
            fasc.id,
            dettagli=(
                f"{fonte}: {len(documenti_creati)} file â€” "
                f"{len(depositi_agganciati)} depositi agganciati"
                + (f", lotto {deposito_generico.id}" if deposito_generico else "")
            ),
        )
        _sync.pubblica("modifica", "fascicoli", fasc.id, utente=u.username if u else "")

        return {
            "fonte": fonte,
            "documenti_importati": len(documenti_creati),
            "depositi_agganciati": depositi_agganciati,
            "lotto_generico": deposito_generico.id if deposito_generico else "",
            "staging_archived": staging_archived,
        }

    def get_config_studio():
        from pct.config_studio import GestioneConfigStudio
        gs = GestioneConfigStudio(config_path=app.config.get("STUDIO_CONFIG", "./config/studio.json"))
        cfg = gs.config
        gs.nome = (cfg.studio.nome if cfg and hasattr(cfg, "studio") and cfg.studio.nome
                   else app.config.get("STUDIO_NOME", "Studio Legale"))
        return gs

    def get_messaggi() -> GestioneMessaggi:
        # Usa app.config (popolato da config_studio.json al boot, con fallback su env)
        cfg = ConfigMessaggistica(
            email=ConfigEmail(
                smtp_host=app.config.get("SMTP_HOST", ""),
                smtp_port=app.config.get("SMTP_PORT", 587),
                username=app.config.get("SMTP_USER", ""),
                password=app.config.get("SMTP_PASS", ""),
                mittente_email=app.config.get("SMTP_FROM", ""),
                mittente_nome=app.config.get("SMTP_FROM_NAME",
                              app.config.get("STUDIO_NOME", "Studio Legale")),
            ),
            twilio=ConfigTwilio(
                account_sid=app.config.get("TWILIO_SID", ""),
                auth_token=app.config.get("TWILIO_TOKEN", ""),
                numero_sms=app.config.get("TWILIO_NUMERO", ""),
                numero_whatsapp=app.config.get("TWILIO_NUMERO", ""),
            ),
            studio_nome=app.config.get("STUDIO_NOME", "Studio Legale"),
        )
        return GestioneMessaggi(
            config=cfg,
            db_path=app.config["MESSAGGI_DB"],
            studio_db=get_studio_db(),
        )

    def get_backup() -> GestioneBackup:
        data_paths = {
            "agenda": app.config["AGENDA_DB"],
            "clienti": app.config["CLIENTI_DB"],
            "fascicoli": app.config["FASCICOLI_DB"],
            "messaggi": app.config["MESSAGGI_DB"],
            "documenti": app.config["FASCICOLI_DOCS"],
        }
        return GestioneBackup(
            directory_backup=app.config["BACKUP_DIR"],
            percorsi_dati=data_paths,
        )

    def get_utenti() -> GestioneUtenti:
        if not hasattr(g, "_utenti"):
            # In modalitÃ  multi-tenant, il primo utente globale deve essere SUPERADMIN
            # per poter accedere al pannello /admin/ e creare studi.
            ruolo_default = (
                RuoloUtente.SUPERADMIN
                if app.config.get("MULTI_TENANT")
                else RuoloUtente.AMMINISTRATORE
            )
            g._utenti = GestioneUtenti(
                db_path=app.config["AUTH_DB"],
                audit_path=app.config["AUDIT_DB"],
                secret_key=app.secret_key,
                ruolo_default=ruolo_default,
                studio_db=get_studio_db(),
                bootstrap_admin_password=app.config.get("BOOTSTRAP_ADMIN_PASSWORD", ""),
                bootstrap_admin_credentials_path=app.config.get(
                    "BOOTSTRAP_ADMIN_CREDENTIALS_PATH", ""
                ),
            )
        return g._utenti

    def get_scadenziario() -> GestioneScadenziario:
        if not hasattr(g, "_scadenziario"):
            g._scadenziario = GestioneScadenziario(
                db_path=_cfg_data_path("SCADENZIARIO_DB"),
                studio_db=get_studio_db(),
            )
        return g._scadenziario

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
                soggetti_path=app.config["SOGGETTI_DB"],
                parti_path=app.config["SOGGETTI_PARTI_DB"],
            )
        return g._soggetti

    def get_indice() -> IndiceRicerca:
        if not hasattr(g, "_indice"):
            g._indice = IndiceRicerca(index_path=app.config["SEARCH_INDEX"])
        return g._indice

    def get_trattamenti() -> GestioneTrattamenti:
        if not hasattr(g, "_trattamenti"):
            g._trattamenti = GestioneTrattamenti(
                db_path=app.config["PRIVACY_DB"],
                studio_db=get_studio_db(),
            )
        return g._trattamenti

    def get_condivisioni() -> GestioneCondivisioni:
        if not hasattr(g, "_condivisioni"):
            g._condivisioni = GestioneCondivisioni(
                db_path=app.config["CONDIVISIONI_DB"],
                secret_key=app.config["SECRET_KEY"],
            )
        return g._condivisioni

    def cliente_accessibile(id_cliente: str, richiesto: RuoloCondivisione = RuoloCondivisione.LETTURA) -> bool:
        """
        Verifica se l'utente corrente puÃ² accedere alla cartella di un cliente.
        - Utenti con permesso globale 'clienti.leggi' â†’ sempre True
        - Altri â†’ solo se la cartella Ã¨ stata condivisa con loro al livello richiesto
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

    _bootstrap_runtime_data_modules()

    # Singleton di sincronizzazione (uno per processo Flask)
    _sync = get_gestore()

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

    def sync_pubblica(tipo: str, modulo: str, id_risorsa: str = ""):
        """Pubblica un evento di sincronizzazione a tutti gli operatori connessi."""
        u = g.utente_corrente
        _sync.pubblica(
            tipo=tipo,
            modulo=modulo,
            id_risorsa=id_risorsa,
            utente=u.username if u else "sistema",
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
                "Spazio di archiviazione insufficiente sul server HACS. "
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
        caricato_da: str,
        note: str,
    ) -> list[str]:
        try:
            gf.sostituisci_documento(
                id_fasc=id_fasc,
                id_doc=id_doc,
                nome_file=nome_file,
                contenuto=contenuto,
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
                caricato_da=caricato_da,
                note=note,
                preserve_version_snapshot=False,
                reuse_existing_path=True,
            )
            return ["storage_compact"]

    # ---------------------------------------------------------------- context
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
        app_version=APP_VERSION,
        connected_operators=lambda: _sync.n_connessi,
    )

    # ================================================================ PWA / ERRORI
    register_pwa_routes(app)
    register_error_handlers(app)

    register_auth_management_routes(
        app,
        get_utenti=get_utenti,
        audit=audit,
    )

    register_scadenziario_routes(
        app,
        get_agenda=get_agenda,
        get_scadenziario=get_scadenziario,
        get_fascicoli=get_fascicoli,
        get_utenti=get_utenti,
        get_config_studio=get_config_studio,
        _studio_patron_rule_from_config=_studio_patron_rule_from_config,
        _resolve_judicial_office_by_code=_resolve_judicial_office_by_code,
        audit=audit,
        sync_pubblica=sync_pubblica,
    )

    register_workspace_routes(
        app,
        get_workspace_intelligente=get_workspace_intelligente,
        get_local_ai_service=get_local_ai_service,
    )

    register_dashboard_routes(
        app,
        get_agenda=get_agenda,
        get_scadenziario=get_scadenziario,
        get_fascicoli=get_fascicoli,
        get_clienti=get_clienti,
        get_condivisioni=get_condivisioni,
        get_workspace_intelligente=get_workspace_intelligente,
        get_calendar_sync=get_calendar_sync,
        audit=audit,
        sync_pubblica=sync_pubblica,
        track_recente=track_recente,
    )

    register_fascicoli_ai_routes(
        app,
        get_fascicoli=get_fascicoli,
        get_agenda=get_agenda,
        get_scadenziario=get_scadenziario,
        get_workspace_intelligente=get_workspace_intelligente,
        get_local_ai_service=get_local_ai_service,
        cfg_data_path=_cfg_data_path,
        build_fascicolo_workspace=_build_fascicolo_workspace,
    )

    register_admin_database_routes(
        app,
        get_database=get_database,
        audit=audit,
        latest_sqlite_snapshot_path=_latest_sqlite_snapshot_path,
        cfg_data_path=_cfg_data_path,
    )

    register_privacy_routes(
        app,
        get_trattamenti=get_trattamenti,
        get_clienti=get_clienti,
        get_fascicoli=get_fascicoli,
        get_utenti=get_utenti,
        audit=audit,
    )

    register_calendar_routes(
        app,
        cfg_data_path=_cfg_data_path,
        get_agenda=get_agenda,
        get_scadenziario=get_scadenziario,
        get_calendar_sync=get_calendar_sync,
    )

    register_checklist_routes(
        app,
        get_fascicoli=get_fascicoli,
        get_config_studio=get_config_studio,
        encrypt_doc=_encrypt_doc,
        audit=audit,
    )

    register_soggetti_routes(
        app,
        get_soggetti=get_soggetti,
        get_clienti=get_clienti,
        get_fascicoli=get_fascicoli,
        audit=audit,
    )

    register_messages_routes(
        app,
        get_messaggi=get_messaggi,
        get_clienti=get_clienti,
    )

    register_clienti_routes(
        app,
        get_clienti=get_clienti,
        get_condivisioni=get_condivisioni,
        get_fascicoli=get_fascicoli,
        get_agenda=get_agenda,
        cliente_accessibile=cliente_accessibile,
        track_recente=track_recente,
        sync_pubblica=sync_pubblica,
        audit=audit,
    )

    register_clienti_workspace_routes(
        app,
        get_clienti=get_clienti,
        get_fascicoli=get_fascicoli,
        get_agenda=get_agenda,
        get_messaggi=get_messaggi,
        get_scadenziario=get_scadenziario,
        get_config_studio=get_config_studio,
        cliente_accessibile=cliente_accessibile,
        track_recente=track_recente,
        audit=audit,
    )

    register_condivisioni_routes(
        app,
        get_condivisioni=get_condivisioni,
        get_clienti=get_clienti,
        get_fascicoli=get_fascicoli,
        get_utenti=get_utenti,
        get_messaggi=get_messaggi,
        cliente_accessibile=cliente_accessibile,
        audit=audit,
        sync_manager=_sync,
    )

    register_backup_routes(
        app,
        get_backup=get_backup,
    )

    register_health_routes(
        app,
        get_clienti=get_clienti,
        get_fascicoli=get_fascicoli,
        get_agenda=get_agenda,
        get_scadenziario=get_scadenziario,
    )

    register_export_routes(
        app,
        get_clienti=get_clienti,
        get_fascicoli=get_fascicoli,
        get_scadenziario=get_scadenziario,
        audit=audit,
    )

    register_search_routes(
        app,
        get_indice=get_indice,
        get_clienti=get_clienti,
        get_fascicoli=get_fascicoli,
        get_agenda=get_agenda,
        get_scadenziario=get_scadenziario,
        audit=audit,
        ocr_supportato=ocr_supportato,
        accoda_ocr=_accoda_ocr,
        ocr_queue=_ocr_queue,
        ocr_stats=_ocr_stats,
        ocr_stats_lock=_ocr_stats_lock,
    )

    register_sync_runtime_routes(
        app,
        sync_manager=_sync,
        get_fascicoli=get_fascicoli,
        audit=audit,
    )

    register_fascicoli_management_routes(
        app,
        get_fascicoli=get_fascicoli,
        get_clienti=get_clienti,
        get_scadenziario=get_scadenziario,
        get_agenda=get_agenda,
        get_soggetti=get_soggetti,
        get_config_studio=get_config_studio,
        cliente_accessibile=cliente_accessibile,
        audit=audit,
        sync_pubblica=sync_pubblica,
        build_responsabile_conformita_fascicolo=_build_responsabile_conformita_fascicolo,
        fascicolo_form_correction_context=_fascicolo_form_correction_context,
    )

    register_fascicoli_document_routes(
        app,
        get_fascicoli=get_fascicoli,
        audit=audit,
        salva_documento_fascicolo=_salva_documento_fascicolo,
        portale_ufficiale_label=_portale_ufficiale_label,
        espandi_file_importato_portale=_espandi_file_importato_portale,
        pst_import_dir_for_fascicolo=_pst_import_dir_for_fascicolo,
        leggi_staging_documenti_portale=_leggi_staging_documenti_portale,
        salva_albero_originale_documenti_portale=_salva_albero_originale_documenti_portale,
        importa_documenti_portale_items=_importa_documenti_portale_items,
        decode_portale_downloaded_items=_decode_portale_downloaded_items,
        decrypt_doc=_decrypt_doc,
        firma_payload_corrente_o_sibling=_firma_payload_corrente_o_sibling,
        estrai_contenuto_p7m_per_preview=_estrai_contenuto_p7m_per_preview,
        nome_preview_documento=_nome_preview_documento,
        mime_preview_documento=_mime_preview_documento,
        payload_preview_da_versioni_documento=_payload_preview_da_versioni_documento,
        applica_timbro_firma_visibile=_applica_timbro_firma_visibile,
    )

    register_fascicoli_editor_routes(
        app,
        get_fascicoli=get_fascicoli,
        audit=audit,
        decrypt_doc=_decrypt_doc,
        encrypt_doc=_encrypt_doc,
        accoda_ocr=_accoda_ocr,
    )

    register_fascicoli_signature_routes(
        app,
        get_fascicoli=get_fascicoli,
        get_config_studio=get_config_studio,
        decrypt_doc=_decrypt_doc,
        encrypt_doc=_encrypt_doc,
        salva_documento_firmato_resiliente=_salva_documento_firmato_resiliente,
        audit_and_sync_best_effort=_audit_and_sync_best_effort,
        signature_storage_error_message=_signature_storage_error_message,
        normalizza_modalita_firma_visibile=_normalizza_modalita_firma_visibile,
        luogo_timbro_firma_visibile=_luogo_timbro_firma_visibile,
        audit=audit,
    )

    register_tariffario_routes(app)

    # ---------------------------------------------------------------- PolisWeb â€“ Consultazione e importazione fascicoli

    def _polis_auth_mode() -> str:
        """
        Restituisce la modalitÃ  di autenticazione PST:
          'reale'  â€” certificato P12/PEM configurato, SOAP mTLS disponibile
          'pkcs11' â€” token PKCS#11 locale, autenticazione gestita dal dispositivo
          'demo'   â€” nessun certificato, modalitÃ  demo offline
        """
        # Controllo config studio (impostazioni UI)
        try:
            cfg = get_config_studio().config.firma
            preferito = getattr(cfg, "backend_preferito_normalizzato", "auto")
            fmt = getattr(cfg, "backend_firma_effettivo_safe", "nessuno")
            if fmt == "pkcs11":
                # Token USB: la chiave privata non Ã¨ esportabile e non Ã¨ accessibile
                # dal container Linux su Windows â†’ autenticazione PST solo via browser
                return "pkcs11"
            if fmt in ("p12", "pem"):
                return "reale"
            if preferito != "auto":
                return "demo"
        except Exception:
            pass
        # Fallback legacy su variabili d'ambiente solo in assenza di scelta esplicita
        if os.getenv("PCT_FIRMA_P12"):
            return "reale"
        if os.getenv("PCT_FIRMA_CERT") and os.getenv("PCT_FIRMA_KEY"):
            return "reale"
        return "demo"

    def _polis_demo_mode() -> bool:
        """True solo se non esiste alcun canale reale configurato (nÃ© P12/PEM nÃ© token PKCS#11)."""
        return _polis_auth_mode() == "demo"

    register_deposito_routes(
        app,
        get_fascicoli=get_fascicoli,
        get_config_studio=get_config_studio,
        audit=audit,
        sync_pubblica=sync_pubblica,
        run_deposito_validation=_run_deposito_validation,
        infer_canale_deposito=_infer_canale_deposito,
        resolve_ufficio_destinatario=_resolve_ufficio_destinatario,
        deposito_correction_context=_deposito_correction_context,
        luogo_timbro_firma_visibile=_luogo_timbro_firma_visibile,
        polis_demo_mode=_polis_demo_mode,
    )

    def _portale_usa_local_signer(portale: str) -> bool:
        return (portale or "").strip().lower() in {"pst", "pdp", "pat", "ptt"} and _polis_auth_mode() == "pkcs11"

    def _portale_browser_channel_required(portale: str) -> bool:
        """PAT e PTT usano sempre il canale browser ufficiale; PDP resta opt-in via env."""
        portale_norm = (portale or "").strip().lower()
        if _polis_demo_mode() or portale_norm not in {"pdp", "pat", "ptt"}:
            return False
        if portale_norm in {"pat", "ptt"}:
            return True
        truthy = {"1", "true", "yes", "on"}
        return (
            str(os.getenv("PCT_PORTALI_BROWSER_ONLY", "") or "").strip().lower() in truthy
            or str(os.getenv(f"PCT_{portale_norm.upper()}_BROWSER_ONLY", "") or "").strip().lower() in truthy
        )

    def _portale_local_channel_enabled(portale: str) -> bool:
        return _portale_usa_local_signer(portale) or _portale_browser_channel_required(portale)

    def _codice_fiscale_avvocato_portale() -> str:
        try:
            cfg = get_config_studio().config
            return (
                str(getattr(cfg.firma, "cf_avvocato", "") or "").strip().upper()
                or str(getattr(cfg.studio, "codice_fiscale_avvocato", "") or "").strip().upper()
            )
        except Exception:
            return ""

    def _polis_cert_preferences() -> dict:
        prefer_cf = ""
        try:
            cfg = get_config_studio().config
            prefer_cf = (
                str(getattr(cfg.firma, "cf_avvocato", "") or "").strip().upper()
                or str(getattr(cfg.studio, "codice_fiscale_avvocato", "") or "").strip().upper()
            )
        except Exception:
            prefer_cf = ""

        if not prefer_cf:
            prefer_cf = str(os.getenv("PCT_CF_AVVOCATO", "") or "").strip().upper()

        match = re.search(r"\b([A-Z]{6}[0-9A-Z]{2}[A-Z][0-9A-Z]{2}[A-Z][0-9A-Z]{3}[A-Z])\b", prefer_cf)
        prefer_cf = match.group(1) if match else ""

        return {
            "auto": True,
            "prefer_issuer": "ArubaPEC EU Authentica Certificates CA G1|ArubaPEC EU Qualified Certificates CA G1|ArubaPEC",
            "prefer_subject": "auth|autent|autentica|client|tls|web",
            "prefer_cf": prefer_cf,
        }

    _PORTALE_ACQUISIZIONE_SPECS: dict[str, dict[str, Any]] = {
        "pst": {
            "id": "pst",
            "label": "PST / PolisWeb",
            "title": "Importa pratica da PST",
            "subtitle": "Ricerca, verifica e acquisizione guidata del fascicolo telematico",
            "color": "primary",
            "icon": "bi-building-fill-check",
            "home_endpoint": "polisWeb_home",
            "source_label": "Portale Servizi Telematici",
            "requires_local_signer": True,
            "quick_filters": ["civile", "lavoro", "famiglia", "esecuzioni", "volontaria", "recenti"],
        },
        "pdp": {
            "id": "pdp",
            "label": "PDP Penale",
            "title": "Importa pratica da PDP Penale",
            "subtitle": "Ricerca, verifica e integrazione guidata del fascicolo penale",
            "color": "danger",
            "icon": "bi-shield-exclamation",
            "home_endpoint": "pdp_home",
            "source_label": "Portale Deposito Atti Penale",
            "requires_local_signer": True,
            "quick_filters": ["dibattimento", "gip", "gup", "esecuzioni", "attivi", "recenti"],
            "search_ui": {
                "assistito_label": "Imputato / indagato",
                "assistito_placeholder": "Nome imputato o indagato...",
                "show_controparte": False,
                "show_cf": False,
                "show_oggetto": False,
            },
        },
        "pat": {
            "id": "pat",
            "label": "PAT Amministrativo",
            "title": "Importa pratica da PAT",
            "subtitle": "Acquisizione guidata del fascicolo amministrativo con verifica conflitti",
            "color": "success",
            "icon": "bi-building-check",
            "home_endpoint": "pat_home",
            "source_label": "Processo Amministrativo Telematico",
            "requires_local_signer": True,
            "quick_filters": ["appalti", "urbanistica", "personale", "tributi", "attivi", "recenti"],
        },
        "ptt": {
            "id": "ptt",
            "label": "PTT Tributario",
            "title": "Importa pratica da PTT",
            "subtitle": "Acquisizione guidata del fascicolo tributario con controllo dati e scadenze",
            "color": "warning",
            "icon": "bi-receipt-cutoff",
            "home_endpoint": "sigit_home",
            "source_label": "Processo Tributario Telematico",
            "requires_local_signer": True,
            "quick_filters": ["iva", "irpef", "imu", "registro", "attivi", "recenti"],
        },
    }

    def _spec_portale_acquisizione(portale: str) -> dict[str, Any]:
        spec = _PORTALE_ACQUISIZIONE_SPECS.get((portale or "").strip().lower())
        if not spec:
            raise KeyError(f"Portale non supportato: {portale}")
        return spec

    def _portale_import_log_path() -> Path:
        return Path(_cfg_data_path("PORTALE_IMPORT_LOG_DB"))

    def _read_json_list(path: Path) -> list[dict]:
        if not path.exists():
            return []
        try:
            raw = json.loads(path.read_text(encoding="utf-8") or "[]")
        except Exception:
            return []
        return raw if isinstance(raw, list) else []

    def _write_json_list(path: Path, rows: list[dict]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    def _new_import_log_id(portale: str) -> str:
        return f"{portale.upper()}-{datetime.now().strftime('%Y%m%d%H%M%S')}-{os.urandom(3).hex().upper()}"

    def _append_portale_import_log(entry: dict[str, Any]) -> str:
        path = _portale_import_log_path()
        rows = _read_json_list(path)
        payload = dict(entry)
        log_id = str(payload.get("id") or _new_import_log_id(str(payload.get("portale") or "PORT")))
        payload["id"] = log_id
        payload.setdefault("created_at", datetime.now().isoformat())
        rows.append(payload)
        _write_json_list(path, rows)
        return log_id

    def _last_portale_import_log(portale: str) -> dict[str, Any]:
        sorgente = _portale_source_name(portale).strip().upper()
        for row in reversed(_read_json_list(_portale_import_log_path())):
            if str(row.get("portale") or "").strip().upper() == sorgente:
                return dict(row)
        return {}

    def _resolve_ufficio_nome(codice: str) -> str:
        codice = str(codice or "").strip()
        if not codice:
            return ""
        try:
            from pct.uffici_giudiziari import get_gestore as _get_uff

            cache_path = os.getenv("PCT_UFFICI_DB", "/data/uffici/uffici_giudiziari.json")
            uff = next((u for u in _get_uff(cache_path).carica() if u.get("codice") == codice), None)
            return str((uff or {}).get("nome") or codice).strip()
        except Exception:
            return codice

    def _portale_source_name(portale: str) -> str:
        return {
            "pst": "PST",
            "pdp": "PDP",
            "pat": "PAT",
            "ptt": "PTT",
        }.get((portale or "").strip().lower(), (portale or "").upper())

    def _telematico_channel_family(portale: str) -> str:
        return {
            "pst": "ministero",
            "pdp": "ministero",
            "pat": "amministrativo",
            "ptt": "tributario",
        }.get((portale or "").strip().lower(), "ministero")

    def _telematico_service_code(portale: str) -> str:
        return {
            "pst": "polisweb_consultazione",
            "pdp": "pdp_penale",
            "pat": "pat_siga",
            "ptt": "ptt_sigit",
        }.get((portale or "").strip().lower(), "polisweb_consultazione")

    def _telematico_internal_status(
        *,
        sync_status: str = "",
        native_status: str = "",
        has_documents: bool = False,
        documents_imported: bool = False,
        needs_manual_review: bool = False,
    ) -> str:
        native = str(native_status or "").strip().upper()
        sync = str(sync_status or "").strip().upper()
        if native in {"RIFIUTATO", "ERRORE_TECNICO"}:
            return "rejected" if native == "RIFIUTATO" else "technical_error"
        if needs_manual_review:
            return "manual_review_required"
        if documents_imported or sync in {"IMPORTATO", "SINCRONIZZATO"}:
            return "import_completed"
        if has_documents:
            return "download_available"
        if native in {"ACCETTATO", "AUTHORIZED"}:
            return "accepted"
        if native in {"INVIATO", "IN_TRANSITO", "IN_VERIFICA"}:
            return "submitted"
        return "draft"

    def _telematico_transmission_status(native_status: str = "", has_documents: bool = False) -> str:
        native = str(native_status or "").strip().upper()
        if native == "RIFIUTATO":
            return "rejected"
        if native == "ERRORE_TECNICO":
            return "technical_error"
        if native in {"INVIATO", "IN_TRANSITO", "IN_VERIFICA"}:
            return "submitted"
        if native in {"ACCETTATO", "AUTHORIZED"} or has_documents:
            return "accepted"
        return "closed"

    def _telematico_document_role(doc: dict[str, Any]) -> str:
        tipo = str((doc or {}).get("tipo_atto") or (doc or {}).get("tipo") or "").upper()
        nome = str((doc or {}).get("nome") or "").upper()
        testo = f"{tipo} {nome}"
        if "SENTENZA" in testo:
            return "judgment"
        if "ORDINANZA" in testo or "DECRETO" in testo or "PROVVEDIMENTO" in testo:
            return "judicial_order"
        if "VERBALE" in testo or "UDIENZA" in testo:
            return "hearing_minutes"
        return "main_act" if "RICORSO" in testo or "ATTO" in testo or "MEMORIA" in testo else "attachment"

    def _is_portale_dns_error(exc: Exception) -> bool:
        text = str(exc or "").lower()
        return any(
            marker in text
            for marker in (
                "nameresolutionerror",
                "failed to resolve",
                "getaddrinfo failed",
                "impossibile risolvere il nome remoto",
                "name or service not known",
                "nodename nor servname provided",
            )
        )

    def _portale_browser_guided_message(portale: str) -> str:
        labels = {
            "pst": "PST / PolisWeb",
            "pdp": "PDP Penale",
            "pat": "PAT",
            "ptt": "PTT",
        }
        label = labels.get((portale or "").strip().lower(), (portale or "").upper())
        if (portale or "").strip().lower() == "pat":
            return (
                "Per PAT la consultazione pratica passa dal Portale dell'Avvocato ufficiale. "
                "Usa l'acquisizione guidata, poi importa nel fascicolo interno documenti, ricevute ed esiti "
                "gia consultati o scaricati dal portale."
            )
        if (portale or "").strip().lower() == "ptt":
            return (
                "Per PTT / SIGIT HACS non promette una sincronizzazione live del fascicolo ministeriale. "
                "Usa l'acquisizione guidata, apri il portale ufficiale o Telecontenzioso nel browser, "
                "consulta o scarica il fascicolo processuale e poi importa nel fascicolo tributario interno "
                "documenti, ricevute, provvedimenti ed esiti."
            )
        return (
            f"L'endpoint ufficiale di {label} non Ã¨ raggiungibile dal backend server. "
            "Usa l'acquisizione guidata dal browser con Local Signer su questo PC."
        )

    def _normalize_portale_documents(documenti: list[dict]) -> list[dict]:
        def _effective_id_cat(item: dict[str, Any]) -> str:
            explicit = str(item.get("id_cat") or "").strip()
            if explicit:
                return explicit
            candidates = []
            for value in list(item.get("id_documento_candidates") or []):
                candidate = str(value or "").strip()
                if candidate and candidate not in candidates:
                    candidates.append(candidate)
            for value in (
                item.get("id_documento"),
                item.get("id_documento_portale"),
                item.get("numero_documento"),
                item.get("id_doc_mittente"),
            ):
                candidate = str(value or "").strip()
                if candidate and candidate not in candidates:
                    candidates.append(candidate)
            return candidates[0] if candidates else ""

        rows: list[dict] = []
        for row in documenti or []:
            item = dict(row or {})
            candidates = [
                str(value or "").strip()
                for value in list(item.get("id_documento_candidates") or [])
                if str(value or "").strip()
            ]
            id_documento = str(item.get("id_documento") or item.get("id_documento_portale") or "").strip()
            if id_documento and id_documento not in candidates:
                candidates.insert(0, id_documento)
            id_cat = _effective_id_cat(item)
            rows.append(
                {
                    "id_documento": id_documento,
                    "nome": str(item.get("nome") or item.get("nome_documento") or "").strip(),
                    "tipo": str(item.get("tipo") or "").strip(),
                    "tipo_atto": str(item.get("tipo_atto") or item.get("tipo") or "").strip(),
                    "data_deposito": str(item.get("data_deposito") or item.get("data_documento") or "").strip(),
                    "mittente": str(item.get("mittente") or "").strip(),
                    "dimensione_bytes": int(item.get("dimensione_bytes") or 0),
                    "disponibile": bool(item.get("disponibile", True)),
                    "id_deposito": str(item.get("id_deposito") or item.get("id_deposito_esterno") or "").strip(),
                    "id_cat": id_cat,
                    "id_repeatto": str(item.get("id_repeatto") or "").strip(),
                    "msg_id": str(item.get("msg_id") or "").strip(),
                    "numero_documento": str(item.get("numero_documento") or "").strip(),
                    "id_doc_mittente": str(item.get("id_doc_mittente") or "").strip(),
                    "id_documento_candidates": candidates,
                }
            )
        rows.sort(
            key=lambda doc: (
                doc.get("data_deposito") or "",
                doc.get("nome") or "",
                doc.get("id_documento") or "",
            ),
            reverse=True,
        )
        return rows

    def _group_portale_documents(documenti: list[dict]) -> list[dict]:
        from collections import OrderedDict

        def _solo_data(d: str) -> str:
            """Normalizza a YYYY-MM-DD (coerente con _chiave_deposito_polisweb).

            Gestisce formati multipli (ISO, italiano dd/mm/yyyy, dd-mm-yyyy)
            esattamente come _parse_data in polisWeb.py â€” altrimenti le chiavi
            di raggruppamento differiscono e lo stesso deposito appare duplicato.
            """
            if not d:
                return ""
            testo = str(d).strip()
            if isinstance(d, date):
                return d.strftime("%Y-%m-%d")
            # Strip parte oraria (T o spazio)
            for sep in ("T", " "):
                if sep in testo:
                    testo = testo.split(sep)[0]
                    break
            candidati = [testo]
            if len(testo) >= 10:
                candidati.append(testo[:10])
            for candidato in candidati:
                for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
                    try:
                        return datetime.strptime(candidato, fmt).strftime("%Y-%m-%d")
                    except ValueError:
                        continue
            return testo[:10] if len(testo) >= 10 else testo

        gruppi: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
        for doc in _normalize_portale_documents(documenti):
            chiave = doc["id_deposito"] or f"__{_solo_data(doc['data_deposito'])}__{doc['mittente']}"
            group = gruppi.setdefault(
                chiave,
                {
                    "id_deposito": chiave,
                    "tipo_atto": doc.get("tipo_atto") or doc.get("tipo") or "Deposito",
                    "data_deposito": doc.get("data_deposito") or "",
                    "mittente": doc.get("mittente") or "",
                    "documenti": [],
                },
            )
            group["documenti"].append(doc)
        return list(gruppi.values())

    def _serialize_portale_search_item(portale: str, fascicolo: Any) -> dict[str, Any]:
        portale = (portale or "").lower()
        if portale == "pst":
            payload = {
                "id_fascicolo": getattr(fascicolo, "id_fascicolo", ""),
                "numero_rg": fascicolo.numero_rg,
                "anno_rg": fascicolo.anno_rg,
                "ruolo": fascicolo.ruolo,
                "stato": fascicolo.stato,
                "oggetto": fascicolo.oggetto,
                "sezione": fascicolo.sezione,
                "giudice": fascicolo.giudice,
                "data_iscrizione": fascicolo.data_iscrizione,
                "data_udienza": fascicolo.data_udienza,
                "parti": list(fascicolo.parti or []),
                "parti_dettaglio": list(fascicolo.parti_dettaglio or []),
                "note": fascicolo.note,
                "codice_ufficio": fascicolo.codice_ufficio,
                "nome_ufficio": fascicolo.nome_ufficio,
                "sub_procedimento": getattr(fascicolo, "sub_procedimento", ""),
            }
            numero = fascicolo.numero_rg
            anno = fascicolo.anno_rg
            uff_cod = fascicolo.codice_ufficio
            uff_nome = fascicolo.nome_ufficio
            procedimento = fascicolo.ruolo.replace("_", " ").title()
            oggetto = fascicolo.oggetto
            assistiti = list(fascicolo.parti or [])
            controparti = []
            ultima_attivita = fascicolo.data_udienza or fascicolo.data_iscrizione
            stato = fascicolo.stato
        elif portale == "pdp":
            payload = {
                "numero_rg": fascicolo.numero_rg,
                "anno_rg": fascicolo.anno_rg,
                "tipo_registro": fascicolo.tipo_registro,
                "fase": fascicolo.fase,
                "stato": fascicolo.stato,
                "reato": fascicolo.reato,
                "sezione": fascicolo.sezione,
                "giudice": fascicolo.giudice,
                "data_iscrizione": fascicolo.data_iscrizione,
                "data_udienza": fascicolo.data_udienza,
                "imputati": list(fascicolo.imputati or []),
                "parti_offese": list(fascicolo.parti_offese or []),
                "note": fascicolo.note,
                "codice_ufficio": fascicolo.codice_ufficio,
                "nome_ufficio": fascicolo.nome_ufficio,
            }
            numero = fascicolo.numero_rg
            anno = fascicolo.anno_rg
            uff_cod = fascicolo.codice_ufficio
            uff_nome = fascicolo.nome_ufficio
            procedimento = fascicolo.tipo_registro
            oggetto = fascicolo.reato
            assistiti = list(fascicolo.imputati or [])
            controparti = list(fascicolo.parti_offese or [])
            ultima_attivita = fascicolo.data_udienza or fascicolo.data_iscrizione
            stato = fascicolo.stato
        elif portale == "pat":
            payload = {
                "numero_ricorso": fascicolo.numero_ricorso,
                "anno": fascicolo.anno,
                "tipo": fascicolo.tipo,
                "stato": fascicolo.stato,
                "materia": fascicolo.materia,
                "sezione": fascicolo.sezione,
                "giudice_relatore": fascicolo.giudice_relatore,
                "data_deposito": fascicolo.data_deposito,
                "data_udienza": fascicolo.data_udienza,
                "ricorrenti": list(fascicolo.ricorrenti or []),
                "resistenti": list(fascicolo.resistenti or []),
                "controinteressati": list(getattr(fascicolo, "controinteressati", []) or []),
                "oggetto": fascicolo.oggetto,
                "note": fascicolo.note,
                "codice_ufficio": fascicolo.codice_ufficio,
                "nome_ufficio": fascicolo.nome_ufficio,
            }
            numero = fascicolo.numero_ricorso
            anno = fascicolo.anno
            uff_cod = fascicolo.codice_ufficio
            uff_nome = fascicolo.nome_ufficio
            procedimento = fascicolo.tipo
            oggetto = fascicolo.oggetto or fascicolo.materia
            assistiti = list(fascicolo.ricorrenti or [])
            controparti = list(fascicolo.resistenti or [])
            ultima_attivita = fascicolo.data_udienza or fascicolo.data_deposito
            stato = fascicolo.stato
        else:
            payload = {
                "numero_rgt": fascicolo.numero_rgt,
                "anno_rgt": fascicolo.anno_rgt,
                "tipo": fascicolo.tipo,
                "stato": fascicolo.stato,
                "materia": fascicolo.materia,
                "sezione": fascicolo.sezione,
                "giudice_relatore": fascicolo.giudice_relatore,
                "data_deposito": fascicolo.data_deposito,
                "data_udienza": fascicolo.data_udienza,
                "ricorrenti": list(fascicolo.ricorrenti or []),
                "resistenti": list(fascicolo.resistenti or []),
                "oggetto_controversia": fascicolo.oggetto_controversia,
                "valore_controversia": getattr(fascicolo, "valore_controversia", 0.0),
                "note": fascicolo.note,
                "codice_commissione": fascicolo.codice_commissione,
                "nome_commissione": fascicolo.nome_commissione,
            }
            numero = fascicolo.numero_rgt
            anno = fascicolo.anno_rgt
            uff_cod = fascicolo.codice_commissione
            uff_nome = fascicolo.nome_commissione
            procedimento = fascicolo.tipo
            oggetto = fascicolo.oggetto_controversia or fascicolo.materia
            assistiti = list(fascicolo.ricorrenti or [])
            controparti = list(fascicolo.resistenti or [])
            ultima_attivita = fascicolo.data_udienza or fascicolo.data_deposito
            stato = fascicolo.stato

        return {
            "external_id": f"{uff_cod}:{numero}:{anno}:{procedimento}",
            "id_fascicolo": str(payload.get("id_fascicolo") or "").strip(),
            "numero": str(numero or "").strip(),
            "anno": int(anno or 0),
            "ufficio_codice": str(uff_cod or "").strip(),
            "ufficio_nome": str(uff_nome or _resolve_ufficio_nome(str(uff_cod or ""))).strip(),
            "procedimento": str(procedimento or "").strip(),
            "sub_procedimento": str(payload.get("sub_procedimento") or "").strip(),
            "sezione": str(payload.get("sezione") or "").strip(),
            "stato": str(stato or "").strip(),
            "oggetto": str(oggetto or "").strip(),
            "parti": assistiti,
            "controparti": controparti,
            "ultima_attivita": str(ultima_attivita or "").strip(),
            "payload": payload,
        }

    def _build_portale_preview(portale: str, selection: dict[str, Any], documenti: list[dict]) -> dict[str, Any]:
        payload = dict((selection or {}).get("payload") or {})
        docs = _normalize_portale_documents(documenti or [])
        depositi = _group_portale_documents(docs)
        def _clean(value: Any) -> str:
            return str(value or "").strip()

        def _first_value(*values: Any) -> str:
            for value in values:
                cleaned = _clean(value)
                if cleaned:
                    return cleaned
            return ""

        def _sortable_date(raw: Any) -> tuple[int, datetime]:
            value = _clean(raw)
            if not value:
                return (0, datetime.min)
            for fmt in (
                "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S.%f",
                "%Y-%m-%d %H:%M:%S",
                "%d/%m/%Y %H:%M:%S.%f",
                "%d/%m/%Y %H:%M:%S",
                "%d/%m/%Y %H:%M",
                "%Y-%m-%d",
                "%d/%m/%Y",
            ):
                try:
                    return (1, datetime.strptime(value, fmt))
                except ValueError:
                    continue
            return (0, datetime.min)

        provvedimenti_count = sum(
            1
            for doc in docs
            if any(token in (doc.get("tipo_atto") or doc.get("tipo") or "").upper() for token in ("SENTENZA", "ORDINANZA", "DECRETO", "PROVVEDIMENTO"))
        )
        data_iscrizione = _first_value(payload.get("data_iscrizione"), payload.get("data_deposito"))
        data_udienza = _first_value(payload.get("data_udienza"))
        latest_doc_date = ""
        doc_dates = [_clean(doc.get("data_deposito")) for doc in docs if _clean(doc.get("data_deposito"))]
        if doc_dates:
            latest_doc_date = max(doc_dates, key=_sortable_date)
        procedimento = _first_value(
            selection.get("procedimento"),
            payload.get("ruolo"),
            payload.get("tipo_registro"),
            payload.get("tipo"),
            payload.get("sub_procedimento"),
        )
        stato = _first_value(selection.get("stato"), payload.get("stato"), payload.get("fase"))
        oggetto = _first_value(
            selection.get("oggetto"),
            payload.get("oggetto"),
            payload.get("reato"),
            payload.get("oggetto_controversia"),
            payload.get("materia"),
        )
        ultima_attivita = _first_value(
            selection.get("ultima_attivita"),
            latest_doc_date,
            data_udienza,
            data_iscrizione,
        )
        eventi = []
        if data_iscrizione:
            eventi.append({"label": "Iscrizione / deposito originario", "data": data_iscrizione, "tipo": "iscrizione"})
        if data_udienza:
            eventi.append({"label": "Udienza rilevata", "data": data_udienza, "tipo": "udienza"})
        return {
            "identity": {
                "id_fascicolo": _first_value(selection.get("id_fascicolo"), payload.get("id_fascicolo")),
                "numero": str(selection.get("numero") or "").strip(),
                "anno": int(selection.get("anno") or 0),
                "ufficio_nome": str(selection.get("ufficio_nome") or "").strip(),
                "ufficio_codice": str(selection.get("ufficio_codice") or "").strip(),
                "procedimento": procedimento,
                "sub_procedimento": _first_value(selection.get("sub_procedimento"), payload.get("sub_procedimento")),
                "sezione": _first_value(selection.get("sezione"), payload.get("sezione")),
                "oggetto": oggetto,
                "stato": stato,
                "data_iscrizione": data_iscrizione,
                "data_udienza": data_udienza,
                "ultima_attivita": ultima_attivita,
            },
            "parti": list(selection.get("parti") or []),
            "controparti": list(selection.get("controparti") or []),
            "difensori": [x for x in list(payload.get("difensori") or []) if str(x).strip()],
            "eventi": eventi,
            "documenti": docs,
            "depositi": depositi,
            "counts": {
                "parti": len(list(selection.get("parti") or [])) + len(list(selection.get("controparti") or [])),
                "difensori": len(list(payload.get("difensori") or [])),
                "eventi": len(eventi),
                "udienze": 1 if data_udienza else 0,
                "documenti": len(docs),
                "provvedimenti": provvedimenti_count,
                "depositi": len(depositi),
                "esiti": len(depositi),
            },
        }

    def _portale_doc_is_provvedimento(doc: dict[str, Any]) -> bool:
        tipo = str((doc or {}).get("tipo_atto") or (doc or {}).get("tipo") or "").upper()
        return any(token in tipo for token in ("SENTENZA", "ORDINANZA", "DECRETO", "PROVVEDIMENTO"))

    def _preview_richiede_file_portale(options: dict[str, bool]) -> bool:
        return bool(options.get("importa_documenti") or options.get("importa_provvedimenti"))

    def _filter_portale_preview_by_options(preview: dict[str, Any], options: dict[str, bool]) -> dict[str, Any]:
        view = dict(preview or {})
        docs = _normalize_portale_documents(list(view.get("documenti") or []))
        include_docs = bool(options.get("importa_documenti", True))
        include_provvedimenti = bool(options.get("importa_provvedimenti", True))
        if include_docs and include_provvedimenti:
            filtered_docs = docs
        else:
            filtered_docs = [
                doc
                for doc in docs
                if (
                    _portale_doc_is_provvedimento(doc) and include_provvedimenti
                ) or (
                    not _portale_doc_is_provvedimento(doc) and include_docs
                )
            ]
        filtered_depositi = _group_portale_documents(filtered_docs)
        counts = dict(view.get("counts") or {})
        counts["documenti"] = len(filtered_docs)
        counts["provvedimenti"] = sum(1 for doc in filtered_docs if _portale_doc_is_provvedimento(doc))
        counts["depositi"] = len(filtered_depositi)
        view["documenti"] = filtered_docs
        view["depositi"] = filtered_depositi
        view["counts"] = counts
        return view

    def _normalize_portale_match_text(value: Any) -> str:
        text = str(value or "").strip().upper()
        text = re.sub(r"\s+", " ", text)
        return text

    def _expected_fascicolo_types_for_portale(
        portale: str, selection: dict[str, Any] | None = None
    ) -> set[str]:
        portale_norm = str(portale or "").strip().lower()
        selection = selection or {}
        procedimento = _normalize_portale_match_text(selection.get("procedimento"))
        if portale_norm == "pdp":
            return {"PENALE"}
        if portale_norm == "pat":
            return {"AMMINISTRATIVO"}
        if portale_norm == "ptt":
            return {"TRIBUTARIO", "ALTRO"}
        if procedimento == "PENALE":
            return {"PENALE"}
        if procedimento == "LAVORO":
            return {"LAVORO", "CIVILE"}
        if procedimento in {"FAMIGLIA", "MINORI"}:
            return {"FAMIGLIA", "CIVILE"}
        return {"CIVILE", "LAVORO", "FAMIGLIA", "ALTRO"}

    def _is_fascicolo_type_compatible_for_portale(
        fasc: Fascicolo, portale: str, selection: dict[str, Any] | None = None
    ) -> bool:
        expected = _expected_fascicolo_types_for_portale(portale, selection)
        fasc_type = _normalize_portale_match_text(getattr(getattr(fasc, "tipo", None), "value", ""))
        return not expected or fasc_type in expected

    def _selection_rg_identity(selection: dict[str, Any]) -> dict[str, Any]:
        numero = str(selection.get("numero") or "").strip()
        try:
            anno = int(selection.get("anno") or 0)
        except (TypeError, ValueError):
            anno = 0
        ufficio_nome = str(
            selection.get("ufficio_nome")
            or _resolve_ufficio_nome(str(selection.get("ufficio_codice") or ""))
        ).strip()
        external_id = str(selection.get("external_id") or "").strip()
        return {
            "numero": numero,
            "anno": anno,
            "ufficio_nome": ufficio_nome,
            "external_id": external_id,
        }

    def _fascicolo_matches_selection(
        fasc: Fascicolo,
        portale: str,
        selection: dict[str, Any],
        *,
        strict: bool,
    ) -> bool:
        if not _is_fascicolo_type_compatible_for_portale(fasc, portale, selection):
            return False
        identity = _selection_rg_identity(selection)
        sel_numero = identity["numero"]
        sel_anno = int(identity["anno"] or 0)
        sel_ufficio = _normalize_portale_match_text(identity["ufficio_nome"])
        fasc_numero = str(getattr(fasc, "numero_rg", "") or "").strip()
        try:
            fasc_anno = int(getattr(fasc, "anno_rg", 0) or 0)
        except (TypeError, ValueError):
            fasc_anno = 0
        fasc_ufficio = _normalize_portale_match_text(getattr(fasc, "tribunale", ""))
        if strict:
            return bool(
                sel_numero
                and sel_anno
                and sel_ufficio
                and fasc_numero == sel_numero
                and fasc_anno == sel_anno
                and fasc_ufficio == sel_ufficio
            )
        if fasc_numero and sel_numero and fasc_numero != sel_numero:
            return False
        if fasc_anno and sel_anno and fasc_anno != sel_anno:
            return False
        if fasc_ufficio and sel_ufficio and fasc_ufficio != sel_ufficio:
            return False
        return True

    def _find_exact_fascicolo_locale_portale(
        portale: str, selection: dict[str, Any]
    ) -> Optional[Fascicolo]:
        identity = _selection_rg_identity(selection)
        expected_external_id = identity["external_id"]
        fascicoli = list(get_fascicoli().tutti())
        if expected_external_id:
            for fasc in fascicoli:
                if not _is_fascicolo_type_compatible_for_portale(fasc, portale, selection):
                    continue
                if str(getattr(fasc, "source_external_id", "") or "").strip() == expected_external_id:
                    return fasc
        for fasc in fascicoli:
            if _fascicolo_matches_selection(fasc, portale, selection, strict=True):
                return fasc
        return None

    def _resolve_portale_import_target(
        portale: str,
        selection: dict[str, Any],
        mapping: dict[str, str],
    ) -> tuple[str, Optional[Fascicolo], bool]:
        gf = get_fascicoli()
        requested_mode = mapping.get("mode") or "create_new"
        target_id = str(mapping.get("target_fascicolo_id") or "").strip()
        if requested_mode in {"attach_existing", "update_existing"}:
            if not target_id:
                raise ValueError("Fascicolo locale selezionato non trovato.")
            target = gf.get(target_id)
            if not target:
                raise ValueError("Fascicolo locale selezionato non trovato.")
            if not _fascicolo_matches_selection(target, portale, selection, strict=False):
                raise ValueError("Il fascicolo locale selezionato non Ã¨ compatibile con il fascicolo del portale.")
            resolved_mode = "update_existing" if requested_mode == "update_existing" else "attach_existing"
            return resolved_mode, target, False
        exact = _find_exact_fascicolo_locale_portale(portale, selection)
        if exact:
            return "update_existing", exact, True
        return "create_new", None, False

    def _find_matching_fascicoli_locali(selection: dict[str, Any]) -> list[dict[str, Any]]:
        matches: list[dict[str, Any]] = []
        numero = str(selection.get("numero") or "").strip()
        anno = int(selection.get("anno") or 0)
        ufficio_nome = str(selection.get("ufficio_nome") or "").strip().upper()
        tokens = [token.strip().upper() for token in list(selection.get("parti") or [])[:2] if token.strip()]
        for fasc in get_fascicoli().tutti():
            same_rg = numero and fasc.numero_rg == numero and int(getattr(fasc, "anno_rg", 0) or 0) == anno
            same_ufficio = ufficio_nome and str(fasc.tribunale or "").strip().upper() == ufficio_nome
            text_hit = any(token in str(fasc.titolo or "").upper() for token in tokens)
            if same_rg or (same_ufficio and text_hit):
                matches.append(
                    {
                        "id": fasc.id,
                        "numero": fasc.numero,
                        "titolo": fasc.titolo,
                        "rg_completo": fasc.rg_completo,
                        "tribunale": fasc.tribunale,
                        "stato": fasc.stato.value,
                        "source": getattr(fasc, "source", "") or "",
                    }
                )
        return matches

    def _sync_existing_fascicolo_from_portale(
        portale: str,
        target: Fascicolo,
        selection: dict[str, Any],
        preview: dict[str, Any],
        *,
        preserve_blank: bool,
        append_import_note: bool,
        user_name: str,
        log_id: str = "",
    ) -> Fascicolo:
        identity = dict(preview.get("identity") or {})
        payload = dict(selection.get("payload") or {})

        def _take(current: Any, incoming: Any) -> Any:
            if preserve_blank and str(current or "").strip():
                return current
            return incoming

        tipo_procedimento = (
            str(selection.get("procedimento") or "").strip()
            or str(payload.get("tipo_registro") or payload.get("tipo") or "").strip()
            or str(target.tipo_procedimento or "").strip()
        )
        update_fields: dict[str, Any] = {
            "tribunale": _take(
                target.tribunale,
                selection.get("ufficio_nome") or identity.get("ufficio_nome") or target.tribunale,
            ),
            "numero_rg": _take(target.numero_rg, selection.get("numero") or target.numero_rg),
            "anno_rg": target.anno_rg or int(selection.get("anno") or 0),
            "oggetto": _take(target.oggetto, identity.get("oggetto") or target.oggetto),
            "sezione": _take(target.sezione, identity.get("sezione") or target.sezione),
            "giudice": _take(
                target.giudice,
                payload.get("giudice") or payload.get("giudice_relatore") or target.giudice,
            ),
            "tipo_procedimento": _take(target.tipo_procedimento, tipo_procedimento),
        }
        if append_import_note:
            nota_import = f"Sincronizzato da {_portale_source_name(portale)} il {date.today().isoformat()}"
            update_fields["note"] = " | ".join(part for part in [target.note.strip(), nota_import] if part)
        stato_portale = stato_fascicolo_da_descrizione_portale(
            identity.get("stato") or selection.get("stato") or payload.get("stato"),
            default=None,
        )
        if stato_portale and stato_portale != target.stato:
            update_fields["stato"] = stato_portale
        updated = get_fascicoli().aggiorna(target.id, **update_fields)
        get_fascicoli().registra_onboarding(
            target.id,
            f"Acquisizione guidata da {_portale_source_name(portale)}",
            note=f"Import log {log_id}" if log_id else "",
            avvocato=user_name,
        )
        return updated

    def _coerce_import_options(data: dict[str, Any]) -> dict[str, bool]:
        def _b(key: str, default: bool = False) -> bool:
            value = data.get(key, default)
            if isinstance(value, bool):
                return value
            return str(value or "").strip().lower() in {"1", "true", "yes", "si", "s", "on"}

        return {
            "importa_dati_pratica": _b("importa_dati_pratica", True),
            "importa_parti": _b("importa_parti", True),
            "importa_difensori": _b("importa_difensori", True),
            "importa_eventi": _b("importa_eventi", True),
            "importa_udienze": _b("importa_udienze", True),
            "importa_scadenze": _b("importa_scadenze", True),
            "importa_documenti": _b("importa_documenti", True),
            "importa_provvedimenti": _b("importa_provvedimenti", True),
            "importa_cronologia_depositi": _b("importa_cronologia_depositi", True),
            "importa_esiti_telematici": _b("importa_esiti_telematici", True),
            "solo_nuovi": _b("solo_nuovi", True),
            "aggiorna_pratica_esistente": _b("aggiorna_pratica_esistente", False),
            "sovrascrivi_solo_vuoti": _b("sovrascrivi_solo_vuoti", True),
            "non_toccare_note_interne": _b("non_toccare_note_interne", True),
            "non_duplicare_documenti": _b("non_duplicare_documenti", True),
            "conserva_log_origine_pst": _b("conserva_log_origine_pst", True),
            "scarica_originale_portale": _b("scarica_originale_portale", True),
            "mantieni_albero_originale": _b("mantieni_albero_originale", False),
        }

    def _coerce_mapping(data: dict[str, Any]) -> dict[str, str]:
        return {
            "mode": str(data.get("mode") or "create_new").strip() or "create_new",
            "target_fascicolo_id": str(data.get("target_fascicolo_id") or "").strip(),
            "area_pratica": str(data.get("area_pratica") or "").strip(),
            "materia": str(data.get("materia") or "").strip(),
            "procedimento": str(data.get("procedimento") or "").strip(),
            "grado": str(data.get("grado") or "").strip(),
            "stato_iniziale": str(data.get("stato_iniziale") or "").strip(),
        }

    def _analyze_portale_import(
        portale: str,
        selection: dict[str, Any],
        preview: dict[str, Any],
        options: dict[str, bool],
        mapping: dict[str, str],
    ) -> dict[str, Any]:
        blockers: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        oks: list[dict[str, Any]] = []
        candidates = _find_matching_fascicoli_locali(selection)
        resolved_mode = mapping.get("mode") or "create_new"
        auto_target: Optional[Fascicolo] = None
        auto_integrated = False
        try:
            resolved_mode, auto_target, auto_integrated = _resolve_portale_import_target(portale, selection, mapping)
        except Exception as target_error:
            if (mapping.get("mode") or "create_new") in {"attach_existing", "update_existing"}:
                blockers.append(
                    {
                        "label": "Pratica locale non compatibile",
                        "detail": str(target_error),
                        "tone": "danger",
                    }
                )
        counts = dict(preview.get("counts") or {})
        mode = mapping.get("mode") or "create_new"
        target_id = mapping.get("target_fascicolo_id") or ""
        payload = dict(selection.get("payload") or {})
        manual_mode = bool(selection.get("manual_mode") or payload.get("manual_mode"))

        if not selection.get("ufficio_codice"):
            blockers.append({"label": "Ufficio giudiziario mancante", "detail": "Seleziona un ufficio valido prima di proseguire.", "tone": "danger"})
        else:
            oks.append({"label": "Ufficio giudiziario risolto", "detail": selection.get("ufficio_nome") or selection.get("ufficio_codice"), "tone": "success"})

        if not selection.get("numero") or not selection.get("anno"):
            blockers.append({"label": "RG incompleto", "detail": "Numero e anno del fascicolo sono obbligatori per una pratica governabile.", "tone": "danger"})
        else:
            oks.append({"label": "IdentitÃ  fascicolo pronta", "detail": f"{selection.get('numero')}/{selection.get('anno')}", "tone": "success"})

        if options.get("importa_parti") and counts.get("parti", 0) <= 0:
            if manual_mode and portale in {"pdp", "pat", "ptt"}:
                warnings.append({
                    "label": "Parti da completare manualmente",
                    "detail": "Il portale non ha restituito parti strutturate: completa assistiti e controparti dal browser ufficiale o direttamente nel gestionale dopo l'importazione.",
                    "tone": "warning",
                })
            else:
                blockers.append({"label": "Parti non disponibili", "detail": "Il fascicolo remoto non espone parti sufficienti per l'importazione guidata.", "tone": "danger"})
        elif counts.get("parti", 0) > 0:
            oks.append({"label": "Parti rilevate", "detail": f"{counts.get('parti', 0)} soggetti disponibili", "tone": "success"})

        if options.get("importa_documenti") and counts.get("documenti", 0) == 0:
            warnings.append({
                "label": "Nessun documento disponibile",
                "detail": (
                    "Puoi importare la pratica anche senza documenti, ma la vista fascicolo restera' parziale."
                    if not manual_mode
                    else "Il catalogo documentale non e' stato esposto dal servizio remoto: importa la pratica e completa documenti e depositi dal portale ufficiale."
                ),
                "tone": "warning",
            })
        elif counts.get("documenti", 0) > 0:
            oks.append({"label": "Catalogo documentale disponibile", "detail": f"{counts.get('documenti', 0)} documenti / {counts.get('depositi', 0)} buste", "tone": "success"})

        if mode in {"attach_existing", "update_existing"} and not target_id:
            blockers.append({"label": "Pratica locale non selezionata", "detail": "Per collegare o aggiornare devi scegliere un fascicolo esistente.", "tone": "danger"})

        if auto_integrated and auto_target is not None:
            warnings.append(
                {
                    "label": "Pratica locale giÃ  presente",
                    "detail": f"L'importazione aggiornerÃ  automaticamente {auto_target.titolo} invece di creare un duplicato.",
                    "tone": "warning",
                }
            )
        elif mode == "create_new" and candidates:
            warnings.append({"label": "Possibile duplicato locale", "detail": f"Esistono {len(candidates)} fascicoli con RG o parti compatibili.", "tone": "warning"})

        if options.get("importa_scadenze") and not preview.get("identity", {}).get("data_udienza"):
            warnings.append({"label": "Nessuna udienza importabile", "detail": "Il portale non espone una prossima udienza da tradurre in scadenziario.", "tone": "warning"})

        score = max(0, min(100, 100 - len(blockers) * 18 - len(warnings) * 7))
        status = "ok" if not blockers and not warnings else ("warning" if not blockers else "block")
        return {
            "status": status,
            "score": score,
            "blockers": blockers,
            "warnings": warnings,
            "ok": oks,
            "existing_matches": candidates,
            "resolved_mode": resolved_mode,
            "auto_integrated": auto_integrated,
            "auto_target_fascicolo_id": getattr(auto_target, "id", "") if auto_target else "",
            "summary_text": (
                "Importazione pronta: nessun blocco rilevato."
                if not blockers
                else f"Risolvi {len(blockers)} blocchi e verifica {len(warnings)} avvisi prima dell'importazione."
            ),
            "next_step": blockers[0] if blockers else (warnings[0] if warnings else {"label": "Pronto per importare", "detail": "Puoi procedere con l'acquisizione guidata.", "tone": "success"}),
        }

    def _selection_to_fascicolo_dataclass(portale: str, selection: dict[str, Any]) -> Any:
        payload = dict((selection or {}).get("payload") or {})
        if portale == "pst":
            from pct.polisWeb import FascicoloPolisWeb

            return FascicoloPolisWeb(
                numero_rg=str(payload.get("numero_rg") or selection.get("numero") or "").strip(),
                anno_rg=int(payload.get("anno_rg") or selection.get("anno") or 0),
                ruolo=str(payload.get("ruolo") or selection.get("procedimento") or "").strip(),
                stato=str(payload.get("stato") or selection.get("stato") or "").strip(),
                oggetto=str(payload.get("oggetto") or selection.get("oggetto") or "").strip(),
                sezione=str(payload.get("sezione") or selection.get("sezione") or "").strip(),
                giudice=str(payload.get("giudice") or "").strip(),
                data_iscrizione=str(payload.get("data_iscrizione") or "").strip(),
                data_udienza=str(payload.get("data_udienza") or "").strip(),
                parti=list(payload.get("parti") or selection.get("parti") or []),
                parti_dettaglio=list(payload.get("parti_dettaglio") or []),
                note=str(payload.get("note") or "").strip(),
                codice_ufficio=str(payload.get("codice_ufficio") or selection.get("ufficio_codice") or "").strip(),
                nome_ufficio=str(payload.get("nome_ufficio") or selection.get("ufficio_nome") or "").strip(),
            )
        if portale == "pdp":
            from pct.pdp import FascicoloPDP

            return FascicoloPDP(
                numero_rg=str(payload.get("numero_rg") or selection.get("numero") or "").strip(),
                anno_rg=int(payload.get("anno_rg") or selection.get("anno") or 0),
                tipo_registro=str(payload.get("tipo_registro") or selection.get("procedimento") or "").strip(),
                fase=str(payload.get("fase") or "").strip(),
                stato=str(payload.get("stato") or selection.get("stato") or "").strip(),
                reato=str(payload.get("reato") or selection.get("oggetto") or "").strip(),
                sezione=str(payload.get("sezione") or selection.get("sezione") or "").strip(),
                giudice=str(payload.get("giudice") or "").strip(),
                data_iscrizione=str(payload.get("data_iscrizione") or "").strip(),
                data_udienza=str(payload.get("data_udienza") or "").strip(),
                imputati=list(payload.get("imputati") or selection.get("parti") or []),
                parti_offese=list(payload.get("parti_offese") or selection.get("controparti") or []),
                note=str(payload.get("note") or "").strip(),
                codice_ufficio=str(payload.get("codice_ufficio") or selection.get("ufficio_codice") or "").strip(),
                nome_ufficio=str(payload.get("nome_ufficio") or selection.get("ufficio_nome") or "").strip(),
            )
        if portale == "pat":
            from pct.pat import FascicoloPAT

            return FascicoloPAT(
                numero_ricorso=str(payload.get("numero_ricorso") or selection.get("numero") or "").strip(),
                anno=int(payload.get("anno") or selection.get("anno") or 0),
                tipo=str(payload.get("tipo") or selection.get("procedimento") or "").strip(),
                stato=str(payload.get("stato") or selection.get("stato") or "").strip(),
                materia=str(payload.get("materia") or "").strip(),
                sezione=str(payload.get("sezione") or selection.get("sezione") or "").strip(),
                giudice_relatore=str(payload.get("giudice_relatore") or "").strip(),
                data_deposito=str(payload.get("data_deposito") or payload.get("data_iscrizione") or "").strip(),
                data_udienza=str(payload.get("data_udienza") or "").strip(),
                ricorrenti=list(payload.get("ricorrenti") or selection.get("parti") or []),
                resistenti=list(payload.get("resistenti") or selection.get("controparti") or []),
                controinteressati=list(payload.get("controinteressati") or []),
                oggetto=str(payload.get("oggetto") or selection.get("oggetto") or "").strip(),
                note=str(payload.get("note") or "").strip(),
                codice_ufficio=str(payload.get("codice_ufficio") or selection.get("ufficio_codice") or "").strip(),
                nome_ufficio=str(payload.get("nome_ufficio") or selection.get("ufficio_nome") or "").strip(),
            )
        from pct.sigit import FascicoloSIGIT

        return FascicoloSIGIT(
            numero_rgt=str(payload.get("numero_rgt") or selection.get("numero") or "").strip(),
            anno_rgt=int(payload.get("anno_rgt") or selection.get("anno") or 0),
            tipo=str(payload.get("tipo") or selection.get("procedimento") or "").strip(),
            stato=str(payload.get("stato") or selection.get("stato") or "").strip(),
            materia=str(payload.get("materia") or "").strip(),
            sezione=str(payload.get("sezione") or selection.get("sezione") or "").strip(),
            giudice_relatore=str(payload.get("giudice_relatore") or "").strip(),
            data_deposito=str(payload.get("data_deposito") or payload.get("data_iscrizione") or "").strip(),
            data_udienza=str(payload.get("data_udienza") or "").strip(),
            ricorrenti=list(payload.get("ricorrenti") or selection.get("parti") or []),
            resistenti=list(payload.get("resistenti") or selection.get("controparti") or []),
            oggetto_controversia=str(payload.get("oggetto_controversia") or selection.get("oggetto") or "").strip(),
            valore_controversia=float(payload.get("valore_controversia") or 0),
            note=str(payload.get("note") or "").strip(),
            codice_commissione=str(payload.get("codice_commissione") or selection.get("ufficio_codice") or "").strip(),
            nome_commissione=str(payload.get("nome_commissione") or selection.get("ufficio_nome") or "").strip(),
        )

    def _documents_to_portale_dataclasses(portale: str, rows: list[dict]) -> list[Any]:
        docs = _normalize_portale_documents(rows)
        if portale != "pst":
            return []
        from pct.polisWeb import DocumentoPolisWeb

        return [
            DocumentoPolisWeb(
                id_documento=row["id_documento"],
                nome=row["nome"],
                tipo=row["tipo"],
                data_deposito=row["data_deposito"],
                mittente=row["mittente"],
                dimensione_bytes=row["dimensione_bytes"],
                disponibile=row["disponibile"],
                id_deposito=row["id_deposito"],
                tipo_atto=row["tipo_atto"],
            )
            for row in docs
        ]

    def _sync_portale_metadata_on_fascicolo(
        portale: str,
        id_fasc: str,
        preview: dict[str, Any],
        registrato_da: str = "",
    ) -> int:
        gf = get_fascicoli()
        synced = 0
        for deposito in list(preview.get("depositi") or []):
            docs = list(deposito.get("documenti") or [])
            if not docs:
                continue
            gf.sincronizza_deposito_portale(
                id_fasc,
                fonte=_portale_source_name(portale),
                id_deposito_esterno=str(deposito.get("id_deposito") or "").strip(),
                tipo_atto=str(deposito.get("tipo_atto") or "").strip(),
                data_deposito=str(deposito.get("data_deposito") or "").strip(),
                mittente=str(deposito.get("mittente") or "").strip(),
                documenti_portale=docs,
                registrato_da=registrato_da,
                note=f"Catalogo ufficiale importato da {_portale_source_name(portale)}",
                nome_atto_principale=str((docs[0] or {}).get("nome") or "").strip(),
                stato="IMPORTATO_DA_PORTALE",
                servizio_portale="DocumentiFascicolo",
            )
            synced += 1
        return synced

    def _sync_udienza_e_scadenza(
        id_fasc: str,
        preview: dict[str, Any],
        *,
        crea_attivita: bool,
        crea_scadenza: bool,
        avvocato: str = "",
    ) -> dict[str, int]:
        gf = get_fascicoli()
        gs = get_scadenziario()
        fasc = gf.get(id_fasc)
        if not fasc:
            return {"attivita": 0, "scadenze": 0}
        data_udienza = str(preview.get("identity", {}).get("data_udienza") or "").strip()
        if not data_udienza:
            return {"attivita": 0, "scadenze": 0}
        created = {"attivita": 0, "scadenze": 0}
        if crea_attivita:
            exists = any(att.tipo == TipoAttivita.UDIENZA and att.data == data_udienza for att in fasc.attivita)
            if not exists:
                gf.aggiungi_attivita(
                    id_fasc,
                    tipo=TipoAttivita.UDIENZA,
                    data=data_udienza,
                    titolo="Udienza sincronizzata da portale",
                    descrizione=f"Evento importato da {fasc.source or 'portale'}",
                    avvocato=avvocato,
                )
                created["attivita"] += 1
        if crea_scadenza:
            exists = [
                sc for sc in gs.tutte(id_fascicolo=id_fasc, solo_aperte=False)
                if sc.data_scadenza == data_udienza and "udienza" in sc.titolo.lower()
            ]
            if not exists:
                gs.nuova(
                    titolo="Udienza da portale",
                    tipo=TipoTermine.UDIENZA,
                    data_scadenza=data_udienza,
                    id_fascicolo=id_fasc,
                    descrizione=f"Scadenza generata da sincronizzazione {fasc.source or 'portale'}",
                    id_utente_responsabile=getattr(g.utente_corrente, "id", "") if getattr(g, "utente_corrente", None) else "",
                )
                created["scadenze"] += 1
        return created

    def _update_fascicolo_sync_metadata(
        id_fasc: str,
        *,
        portale: str,
        selection: dict[str, Any],
        import_log_id: str,
        has_conflicts: bool,
        document_sync_enabled: bool,
        events_sync_enabled: bool,
        sync_status: str,
    ) -> Fascicolo:
        return get_fascicoli().aggiorna(
            id_fasc,
            source=_portale_source_name(portale),
            source_external_id=str(selection.get("external_id") or "").strip(),
            last_sync_at=datetime.now().isoformat(),
            sync_status=sync_status,
            import_log_id=import_log_id,
            has_conflicts=has_conflicts,
            document_sync_enabled=document_sync_enabled,
            events_sync_enabled=events_sync_enabled,
        )

    def _selection_preview_from_existing_fascicolo_telematico(fasc: Fascicolo) -> tuple[str, dict[str, Any], dict[str, Any]]:
        source_map = {
            "PST": "pst",
            "PDP": "pdp",
            "PAT": "pat",
            "PTT": "ptt",
        }
        portale = source_map.get(str(getattr(fasc, "source", "") or "").strip().upper(), "")
        if not portale:
            return "", {}, {}
        documenti: list[dict[str, Any]] = []
        for dep in list(getattr(fasc, "depositi_pct", []) or []):
            if getattr(dep, "documenti_portale", None):
                documenti.extend(list(dep.documenti_portale or []))
        if not documenti:
            for doc in list(getattr(fasc, "documenti", []) or []):
                if not str(getattr(doc, "id_deposito_pct", "") or "").strip():
                    continue
                documenti.append(
                    {
                        "id_documento": str(doc.id),
                        "nome": str(doc.nome or "").strip(),
                        "tipo": getattr(getattr(doc, "tipo", None), "value", ""),
                        "data_deposito": str(getattr(doc, "data_documento", "") or "").strip(),
                        "mittente": str(fasc.avvocato_referente or fasc.avvocato_dominus or "").strip(),
                        "dimensione_bytes": int(getattr(doc, "dimensione_bytes", 0) or 0),
                        "disponibile": True,
                        "id_deposito": str(getattr(doc, "id_deposito_pct", "") or "").strip(),
                        "tipo_atto": "",
                    }
                )
        selection = {
            "external_id": str(getattr(fasc, "source_external_id", "") or "").strip()
            or f"{fasc.tribunale}:{fasc.numero_rg}:{fasc.anno_rg}:{fasc.tipo_procedimento or getattr(getattr(fasc, 'tipo', None), 'value', '')}",
            "numero": str(getattr(fasc, "numero_rg", "") or "").strip(),
            "anno": int(getattr(fasc, "anno_rg", 0) or 0),
            "ufficio_codice": "",
            "ufficio_nome": str(getattr(fasc, "tribunale", "") or "").strip(),
            "procedimento": str(getattr(fasc, "tipo_procedimento", "") or getattr(getattr(fasc, "tipo", None), "value", "")).strip(),
            "sezione": str(getattr(fasc, "sezione", "") or "").strip(),
            "stato": str(getattr(fasc, "sync_status", "") or getattr(getattr(fasc, "stato", None), "value", "")).strip(),
            "oggetto": str(getattr(fasc, "oggetto", "") or "").strip(),
            "parti": [str(getattr(fasc, "nome_cliente", "") or "").strip()] if str(getattr(fasc, "nome_cliente", "") or "").strip() else [],
            "controparti": [str(getattr(fasc, "controparte", "") or "").strip()] if str(getattr(fasc, "controparte", "") or "").strip() else [],
            "ultima_attivita": str(getattr(fasc, "last_sync_at", "") or getattr(fasc, "modificato_il", "") or "").strip(),
            "payload": {},
        }
        preview = _build_portale_preview(portale, selection, documenti)
        return portale, selection, preview

    def _sync_telematico_case_from_portale(
        portale: str,
        *,
        id_fasc: str,
        selection: dict[str, Any],
        preview: dict[str, Any],
        import_log_id: str = "",
        sync_status: str = "",
        document_sync_enabled: bool = False,
        workflow_url: str = "",
        user_name: str = "",
        backfill: bool = False,
    ) -> dict[str, Any]:
        fasc = get_fascicoli().get(id_fasc)
        if not fasc:
            return {}
        repo = get_telematico()
        cfg = get_config_studio().config
        identity = dict((preview or {}).get("identity") or {})
        native_status = str(identity.get("stato") or selection.get("stato") or "").strip().upper()
        has_documents = int((preview.get("counts") or {}).get("documenti", 0) or 0) > 0
        portal_case_ref = str(selection.get("external_id") or getattr(fasc, "source_external_id", "") or "").strip()
        existing_case = repo.find_case(
            practice_id=id_fasc,
            service_code=_telematico_service_code(portale),
            portal_case_ref=portal_case_ref or None,
            office_name=str(selection.get("ufficio_nome") or getattr(fasc, "tribunale", "") or "").strip() or None,
            register_type=str(selection.get("procedimento") or getattr(fasc, "tipo_procedimento", "") or "").strip() or None,
            register_number=str(selection.get("numero") or getattr(fasc, "numero_rg", "") or "").strip() or None,
            register_year=int(selection.get("anno") or getattr(fasc, "anno_rg", 0) or 0) or None,
        )
        counsel_name = (
            str(getattr(fasc, "avvocato_referente", "") or "").strip()
            or str(getattr(fasc, "avvocato_dominus", "") or "").strip()
            or str(getattr(cfg.studio, "nome_avvocato", "") or "").strip()
            or str(user_name or "").strip()
        )
        counsel_cf = (
            str(getattr(cfg.firma, "cf_avvocato", "") or "").strip().upper()
            or str(getattr(cfg.studio, "codice_fiscale_avvocato", "") or "").strip().upper()
        )
        case = repo.upsert_case(
            id=str((existing_case or {}).get("id") or "").strip() or None,
            practice_id=id_fasc,
            channel_family=_telematico_channel_family(portale),
            service_code=_telematico_service_code(portale),
            office_name=str(selection.get("ufficio_nome") or getattr(fasc, "tribunale", "") or "").strip() or "Ufficio da completare",
            office_type="",
            district="",
            register_type=str(selection.get("procedimento") or getattr(fasc, "tipo_procedimento", "") or "").strip(),
            register_number=str(selection.get("numero") or getattr(fasc, "numero_rg", "") or "").strip(),
            register_year=int(selection.get("anno") or getattr(fasc, "anno_rg", 0) or 0),
            subject_name=str((selection.get("parti") or [getattr(fasc, "nome_cliente", "")])[0] or getattr(fasc, "nome_cliente", "")).strip() or "Parte non definita",
            subject_cf="",
            counterparty_name=str((selection.get("controparti") or [getattr(fasc, "controparte", "")])[0] or getattr(fasc, "controparte", "")).strip(),
            counsel_name=counsel_name or "Difensore da completare",
            counsel_cf=counsel_cf or "N/D",
            portal_case_ref=portal_case_ref or None,
            portal_case_url="",
            workflow_url=workflow_url or None,
            internal_status=_telematico_internal_status(
                sync_status=sync_status or getattr(fasc, "sync_status", ""),
                native_status=native_status,
                has_documents=has_documents,
                documents_imported=bool(document_sync_enabled),
                needs_manual_review=bool(getattr(fasc, "has_conflicts", False)),
            ),
            native_status=native_status or None,
            import_log_id=import_log_id or getattr(fasc, "import_log_id", "") or None,
            notes=str(getattr(fasc, "note", "") or "").strip() or None,
            last_sync_at=str(getattr(fasc, "last_sync_at", "") or datetime.now().isoformat()),
        )
        if not (backfill and existing_case):
            repo.add_event(
                str(case["id"]),
                event_type="telematico_sync",
                event_source="import" if not backfill else "system",
                title=f"{_portale_source_name(portale)} sincronizzato nel core telematico",
                description=f"Pratica {getattr(fasc, 'numero', '')} allineata con il canale {_portale_source_name(portale)}.",
                payload_json={
                    "practice_id": id_fasc,
                    "import_log_id": import_log_id,
                    "documents": int((preview.get('counts') or {}).get('documenti', 0) or 0),
                },
                created_by_user_id=getattr(getattr(g, "utente_corrente", None), "id", "") or None,
            )
        depositi = list(preview.get("depositi") or [])
        if not depositi and list(preview.get("documenti") or []):
            depositi = _group_portale_documents(list(preview.get("documenti") or []))
        for deposito in depositi:
            transmission = repo.upsert_transmission(
                str(case["id"]),
                transmission_type="case_import",
                act_type=str(deposito.get("tipo_atto") or "Deposito ufficiale").strip(),
                portal_reference=str(deposito.get("id_deposito") or import_log_id or portal_case_ref or "").strip() or None,
                internal_status=_telematico_transmission_status(native_status, has_documents=bool(deposito.get("documenti"))),
                native_status=native_status or None,
                submitted_at=str(deposito.get("data_deposito") or identity.get("data_iscrizione") or "").strip() or None,
                outcome_at=str(identity.get("ultima_attivita") or deposito.get("data_deposito") or "").strip() or None,
                notes=f"Catalogo {_portale_source_name(portale)} allineato nel core telematico.",
            )
            for doc in list(deposito.get("documenti") or []):
                doc_ref = str(doc.get("id_cat") or doc.get("id_documento") or "").strip()
                tele_doc = repo.upsert_document(
                    str(case["id"]),
                    document_role=_telematico_document_role(doc),
                    document_category=str(doc.get("tipo") or "").strip() or None,
                    title=str(doc.get("nome") or "Documento ufficiale").strip(),
                    original_filename=str(doc.get("nome") or "").strip() or None,
                    file_size_bytes=int(doc.get("dimensione_bytes") or 0) or None,
                    source_type="portal",
                    signed=1 if str(doc.get("nome") or "").lower().endswith(".p7m") else 0,
                    portal_document_ref=doc_ref or None,
                    portal_document_date=str(doc.get("data_deposito") or "").strip() or None,
                    id_deposito=str(deposito.get("id_deposito") or "").strip(),
                    tipo_atto=str(deposito.get("tipo_atto") or doc.get("tipo_atto") or "").strip(),
                    data_deposito=str(doc.get("data_deposito") or deposito.get("data_deposito") or "").strip() or None,
                    mittente=str(doc.get("mittente") or deposito.get("mittente") or "").strip() or None,
                    notes=f"Documento censito da {_portale_source_name(portale)}.",
                )
                repo.link_document_to_transmission(
                    str(transmission["id"]),
                    str(tele_doc["id"]),
                    relation_type="main_act" if tele_doc.get("document_role") == "main_act" else "attachment",
                )
        if has_documents and not document_sync_enabled:
            repo.ensure_task(
                str(case["id"]),
                task_type="download_case_file",
                title="Completare acquisizione documenti dal portale ufficiale",
                description=f"Il fascicolo {_portale_source_name(portale)} ha documenti censiti ma non ancora integrati nel fascicolo locale.",
                priority="high",
                assigned_user_id=getattr(getattr(g, "utente_corrente", None), "id", "") or "",
            )
        else:
            repo.close_tasks(str(case["id"]), task_type="download_case_file")
        return case

    def _backfill_telematico_from_existing_fascicoli() -> dict[str, int]:
        summary = {"processed": 0, "failed": 0}
        for fasc in get_fascicoli().tutti():
            if str(getattr(fasc, "source", "") or "").strip().upper() not in {"PST", "PDP", "PAT", "PTT"}:
                continue
            portale, selection, preview = _selection_preview_from_existing_fascicolo_telematico(fasc)
            if not portale or not selection:
                continue
            try:
                _sync_telematico_case_from_portale(
                    portale,
                    id_fasc=fasc.id,
                    selection=selection,
                    preview=preview,
                    import_log_id=str(getattr(fasc, "import_log_id", "") or ""),
                    sync_status=str(getattr(fasc, "sync_status", "") or ""),
                    document_sync_enabled=bool(getattr(fasc, "document_sync_enabled", False)),
                    user_name=getattr(getattr(g, "utente_corrente", None), "username", "") or "",
                    backfill=True,
                )
                summary["processed"] += 1
            except Exception as e:
                summary["failed"] += 1
                app.logger.exception(
                    "Errore backfill telematico fascicolo %s (%s): %s",
                    getattr(fasc, "id", ""),
                    getattr(fasc, "numero", ""),
                    e,
                )
        return summary

    def _telematico_dashboard_warning_message(error: Exception) -> str:
        message = str(error).strip().lower()
        if "archivio telematico temporaneamente non disponibile" in message or "database or disk is full" in message:
            return (
                "Archivio telematico temporaneamente non disponibile. HACS ha messo in pausa "
                "l'aggiornamento SQLite e continuera' a riprovare automaticamente."
            )
        if "temporaneamente occupato" in message or "database is locked" in message:
            return (
                "Archivio telematico temporaneamente occupato da un aggiornamento in corso. "
                "La pagina resta disponibile e il sistema riprovera' automaticamente."
            )
        return (
            "Cabina telematica disponibile in modalita' ridotta. "
            "Il sistema ha intercettato un errore tecnico e continuera' a lavorare in sicurezza."
        )

    def _importa_o_collega_fascicolo_portale(
        portale: str,
        selection: dict[str, Any],
        preview: dict[str, Any],
        options: dict[str, bool],
        mapping: dict[str, str],
        downloaded_files: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        user_name = getattr(getattr(g, "utente_corrente", None), "username", "") or ""
        selection_dc = _selection_to_fascicolo_dataclass(portale, selection)
        analysis = _analyze_portale_import(portale, selection, preview, options, mapping)
        if analysis["blockers"]:
            raise ValueError("Sono presenti blocchi da risolvere prima dell'importazione.")

        preview_for_files = _filter_portale_preview_by_options(preview, options)
        importa_file_portale = _preview_richiede_file_portale(options)
        files = list(downloaded_files or [])
        counts = preview_for_files.get("counts") or {}
        documenti_attesi = int(counts.get("documenti", 0) or 0)
        selected_doc_ids = {
            str(doc.get("id_documento") or "").strip()
            for doc in list(preview_for_files.get("documenti") or [])
            if str(doc.get("id_documento") or "").strip()
        }
        decoded_items: list[dict[str, Any]] = []
        if importa_file_portale and portale == "pst" and documenti_attesi > 0:
            if not files:
                raise ValueError(
                    "Hai scelto di importare i documenti, ma il wizard non ha ricevuto alcun file scaricato dal portale. "
                    "Riprova l'acquisizione con download batch attivo."
                )
            decoded_items = _decode_portale_downloaded_items(files)
            if selected_doc_ids:
                decoded_items = [
                    item
                    for item in decoded_items
                    if str(item.get("id_documento_portale") or "").strip() in selected_doc_ids
                ]
            if not decoded_items:
                raise ValueError("Il lotto scaricato dal portale non contiene file importabili.")

        log_id = _append_portale_import_log(
            {
                "portale": _portale_source_name(portale),
                "selection": selection,
                "preview_counts": preview.get("counts") or {},
                "options": options,
                "mapping": mapping,
                "analysis": analysis,
                "utente": user_name,
            }
        )

        gf = get_fascicoli()
        gc = get_clienti()
        gsog = get_soggetti()
        mode, resolved_target, auto_integrated = _resolve_portale_import_target(portale, selection, mapping)
        id_fasc = ""
        created = False

        if mode == "create_new":
            if portale == "pst":
                from pct.polisWeb import ClientPolisWebImportOnly, crea_client

                if _portale_local_channel_enabled(portale):
                    client = ClientPolisWebImportOnly()
                else:
                    client = crea_client(demo=_polis_demo_mode())
                documenti_pw = _documents_to_portale_dataclasses(portale, preview_for_files.get("documenti") or []) if importa_file_portale else None
                risultato = client.importa_fascicolo(
                    fascicolo_pw=selection_dc,
                    gestione_fascicoli=gf,
                    gestione_clienti=gc,
                    avvocato_referente=user_name,
                    gestione_soggetti=gsog,
                    documenti_pw=documenti_pw,
                )
            elif portale == "pdp":
                if _portale_local_channel_enabled(portale):
                    from pct.pdp import ClientPDP

                    client = ClientPDP(
                        codice_fiscale_avvocato=str(
                            getattr(get_config_studio().config.firma, "cf_avvocato", "") or ""
                        ).strip().upper()
                    )
                else:
                    from pct.pdp import crea_client_pdp

                    client = crea_client_pdp(demo=_polis_demo_mode())
                risultato = client.importa_fascicolo(selection_dc, gf, gc, user_name)
            elif portale == "pat":
                if _portale_local_channel_enabled(portale):
                    from pct.pat import ClientPAT

                    client = ClientPAT(
                        codice_fiscale_avvocato=str(
                            getattr(get_config_studio().config.firma, "cf_avvocato", "") or ""
                        ).strip().upper()
                    )
                else:
                    from pct.pat import crea_client_pat

                    client = crea_client_pat(demo=_polis_demo_mode())
                risultato = client.importa_fascicolo(selection_dc, gf, gc, user_name)
            else:
                if _portale_local_channel_enabled(portale):
                    from pct.sigit import ClientSIGIT

                    client = ClientSIGIT(
                        codice_fiscale_avvocato=str(
                            getattr(get_config_studio().config.firma, "cf_avvocato", "") or ""
                        ).strip().upper()
                    )
                else:
                    from pct.sigit import crea_client_sigit

                    client = crea_client_sigit(demo=_polis_demo_mode())
                risultato = client.importa_fascicolo(selection_dc, gf, gc, user_name)
            if not risultato.successo or not risultato.id_fascicolo_locale:
                raise ValueError(risultato.messaggio or "Importazione non riuscita.")
            id_fasc = risultato.id_fascicolo_locale
            created = True
        else:
            target = resolved_target
            if not target:
                raise ValueError("Fascicolo locale selezionato non trovato.")
            if portale == "pst":
                from pct.polisWeb import ClientPolisWebImportOnly, crea_client

                if _portale_local_channel_enabled(portale):
                    client = ClientPolisWebImportOnly()
                else:
                    client = crea_client(demo=_polis_demo_mode())
                documenti_pw = _documents_to_portale_dataclasses(portale, preview_for_files.get("documenti") or []) if importa_file_portale else None
                risultato = client.sincronizza_fascicolo_esistente(
                    fascicolo_pw=selection_dc,
                    fascicolo_locale=target,
                    gestione_fascicoli=gf,
                    gestione_clienti=gc,
                    avvocato_referente=user_name,
                    gestione_soggetti=gsog,
                    documenti_pw=documenti_pw,
                )
                if not risultato.successo or not risultato.id_fascicolo_locale:
                    raise ValueError(risultato.messaggio or "Sincronizzazione PST non riuscita.")
                id_fasc = risultato.id_fascicolo_locale
            else:
                target = _sync_existing_fascicolo_from_portale(
                    portale,
                    target,
                    selection,
                    preview,
                    preserve_blank=options.get("sovrascrivi_solo_vuoti", True),
                    append_import_note=not options.get("non_toccare_note_interne", True),
                    user_name=user_name,
                    log_id=log_id,
                )
                id_fasc = target.id

        import_result: dict[str, Any] = {
            "documenti_importati": 0,
            "depositi_agganciati": [],
            "lotto_generico": "",
            "staging_archived": "",
        }
        albero_originale_salvato = ""
        if importa_file_portale:
            _sync_portale_metadata_on_fascicolo(portale, id_fasc, preview_for_files, registrato_da=user_name)
            if files:
                fasc_import = gf.get(id_fasc)
                if not fasc_import:
                    raise ValueError("Fascicolo importato non trovato durante l'acquisizione documenti.")
                if not decoded_items:
                    decoded_items = _decode_portale_downloaded_items(files)
                    if selected_doc_ids:
                        decoded_items = [
                            item
                            for item in decoded_items
                            if str(item.get("id_documento_portale") or "").strip() in selected_doc_ids
                        ]
                if not decoded_items:
                    raise ValueError("Il lotto scaricato dal portale non contiene file importabili.")
                if options.get("mantieni_albero_originale"):
                    albero_originale_salvato = _salva_albero_originale_documenti_portale(fasc_import, decoded_items)
                import_result = _importa_documenti_portale_items(
                    gf=gf,
                    fasc=fasc_import,
                    items=decoded_items,
                    note_importazione=f"Acquisizione guidata da {_portale_source_name(portale)}",
                )
            elif portale == "pst" and documenti_attesi > 0:
                raise ValueError(
                    "Hai scelto di importare i documenti, ma il wizard non ha ricevuto alcun file scaricato dal portale. "
                    "Riprova l'acquisizione con download batch attivo."
                )

        udienza_result = _sync_udienza_e_scadenza(
            id_fasc,
            preview,
            crea_attivita=options.get("importa_eventi") or options.get("importa_udienze"),
            crea_scadenza=options.get("importa_scadenze", False),
            avvocato=user_name,
        )

        _update_fascicolo_sync_metadata(
            id_fasc,
            portale=portale,
            selection=selection,
            import_log_id=log_id,
            has_conflicts=bool(analysis["warnings"]),
            document_sync_enabled=importa_file_portale,
            events_sync_enabled=options.get("importa_eventi", False) or options.get("importa_udienze", False),
            sync_status="IMPORTATO" if created else "SINCRONIZZATO",
        )

        workflow_url = ""
        if portale == "pdp":
            case = _ensure_pdp_penale_case_after_import(
                id_fasc=id_fasc,
                selection=selection,
                preview=preview,
                user_name=user_name,
                imported_documents=int(import_result.get("documenti_importati", 0) or 0),
                downloaded_files=decoded_items or files,
            )
            if case:
                workflow_url = url_for("pdp_penale_workspace", id_fasc=id_fasc, case_id=case["id"])

        _sync_telematico_case_from_portale(
            portale,
            id_fasc=id_fasc,
            selection=selection,
            preview=preview_for_files if preview_for_files else preview,
            import_log_id=log_id,
            sync_status="IMPORTATO" if created else "SINCRONIZZATO",
            document_sync_enabled=bool(importa_file_portale),
            workflow_url=workflow_url,
            user_name=user_name,
        )

        fasc = gf.get(id_fasc)
        return {
            "id_fascicolo": id_fasc,
            "created": created,
            "resolved_mode": mode,
            "auto_integrated": auto_integrated,
            "import_log_id": log_id,
            "quadro_url": url_for("quadro_fascicolo", id_fasc=id_fasc),
            "dettaglio_url": url_for("dettaglio_fascicolo", id_fasc=id_fasc),
            "scadenziario_url": url_for("dettaglio_fascicolo", id_fasc=id_fasc) + "#sezione-udienze-scadenze",
            "timeline_url": url_for("dettaglio_fascicolo", id_fasc=id_fasc) + "#sezione-attivita-processuali",
            "documenti_url": url_for("dettaglio_fascicolo", id_fasc=id_fasc) + "#sezione-documenti-fascicolo",
            "workflow_url": workflow_url,
            "summary": {
                "numero_pratica": getattr(fasc, "numero", ""),
                "titolo": getattr(fasc, "titolo", ""),
                "documenti": int(import_result.get("documenti_importati", 0) or 0),
                "depositi": len(import_result.get("depositi_agganciati") or [])
                or int(preview.get("counts", {}).get("depositi", 0) or 0),
                "scadenze_generate": udienza_result["scadenze"],
                "eventi_generati": udienza_result["attivita"],
                "conflitti_risolti": len(analysis["warnings"]),
                "lotto_generico": str(import_result.get("lotto_generico") or ""),
                "modalita_documento_portale": "originale" if options.get("scarica_originale_portale", True) else "copia",
                "albero_originale_salvato": bool(albero_originale_salvato),
            },
        }

    def _register_direct_portale_import_sync(
        portale: str,
        selection: dict[str, Any],
        preview: dict[str, Any],
        *,
        id_fasc: str,
        created: bool,
        user_name: str,
    ) -> str:
        log_id = _append_portale_import_log(
            {
                "portale": _portale_source_name(portale),
                "selection": selection,
                "preview_counts": preview.get("counts") or {},
                "options": {"direct_import": True},
                "mapping": {"mode": "create_new"},
                "analysis": {},
                "utente": user_name,
            }
        )
        fasc = get_fascicoli().get(id_fasc)
        if not fasc:
            return log_id
        _update_fascicolo_sync_metadata(
            id_fasc,
            portale=portale,
            selection=selection,
            import_log_id=log_id,
            has_conflicts=False,
            document_sync_enabled=False,
            events_sync_enabled=False,
            sync_status="IMPORTATO" if created else "SINCRONIZZATO",
        )
        if portale == "pdp":
            case = _ensure_pdp_penale_case_after_import(
                id_fasc=id_fasc,
                selection=selection,
                preview=preview,
                user_name=user_name,
                imported_documents=0,
                downloaded_files=[],
            )
            workflow_url = url_for("pdp_penale_workspace", id_fasc=id_fasc, case_id=case["id"]) if case else ""
        else:
            workflow_url = ""
        _sync_telematico_case_from_portale(
            portale,
            id_fasc=id_fasc,
            selection=selection,
            preview=preview,
            import_log_id=log_id,
            sync_status="IMPORTATO" if created else "SINCRONIZZATO",
            document_sync_enabled=False,
            workflow_url=workflow_url,
            user_name=user_name,
        )
        return log_id

    def _build_access_status_payload(portale: str) -> dict[str, Any]:
        spec = _spec_portale_acquisizione(portale)
        cfg = get_config_studio().config
        firma_cfg = cfg.firma
        auth_mode = _polis_auth_mode()
        demo_mode = auth_mode == "demo"
        pkcs11_mode = _portale_usa_local_signer(portale) and not demo_mode
        browser_channel_required = _portale_browser_channel_required(portale)
        ultimo_log = _last_portale_import_log(portale)
        if demo_mode:
            status_text = "ModalitÃ  demo / fallback"
            environment_label = "Simulazione / compatibilitÃ "
        elif browser_channel_required:
            if portale == "pat":
                status_text = "Consultazione via Portale dell'Avvocato"
            elif portale == "ptt":
                status_text = "Consultazione via PTT / SIGIT"
            else:
                status_text = "Consultazione via browser ufficiale"
            environment_label = "Produzione guidata assistita"
        elif pkcs11_mode:
            status_text = "Accesso via Local Signer / Aruba Key"
            environment_label = "Produzione guidata via browser locale"
        else:
            status_text = "Connessione pronta"
            environment_label = "Produzione guidata"
        return {
            "portale": portale,
            "spec": spec,
            "avvocato": str(getattr(cfg.studio, "nome_avvocato", "") or getattr(g.utente_corrente, "username", "") or "").strip(),
            "codice_fiscale_avvocato": str(getattr(firma_cfg, "cf_avvocato", "") or getattr(cfg.studio, "codice_fiscale_avvocato", "") or "").strip().upper(),
            "backend_firma": str(getattr(firma_cfg, "backend_firma_effettivo_safe", "nessuno") or "").strip(),
            "auth_mode": auth_mode,
            "demo_mode": demo_mode,
            "pkcs11_mode": pkcs11_mode,
            "browser_channel_required": browser_channel_required,
            "cert_preferences": _polis_cert_preferences() if (pkcs11_mode or browser_channel_required) else {},
            "status_text": status_text,
            "test_ok": not demo_mode,
            "last_sync_at": str(ultimo_log.get("created_at") or "").strip(),
            "last_import_log_id": str(ultimo_log.get("id") or "").strip(),
            "environment_label": environment_label,
        }

    def _search_fascicoli_portale_server(portale: str, query: dict[str, Any]) -> list[dict[str, Any]]:
        portale = (portale or "").strip().lower()
        numero = str(query.get("numero") or "").strip() or None
        anno_raw = str(query.get("anno") or "").strip()
        anno = int(anno_raw) if anno_raw.isdigit() else None
        assistito = str(query.get("assistito") or "").strip() or None
        controparte = str(query.get("controparte") or "").strip() or None
        cf = str(query.get("cf") or "").strip() or None
        oggetto = str(query.get("oggetto") or "").strip().lower()
        stato_filter = str(query.get("stato") or "").strip().lower()
        quick = str(query.get("quick_filter") or "").strip().lower()

        try:
            if portale == "pst":
                if _portale_local_channel_enabled(portale):
                    raise ValueError("Per PST la ricerca guidata usa il Local Signer dal browser.")
                from pct.polisWeb import crea_client

                ufficio = str(query.get("ufficio_codice") or "").strip()
                if not ufficio:
                    raise ValueError("Seleziona un ufficio giudiziario.")
                fascicoli = crea_client(demo=_polis_demo_mode()).ricerca_fascicoli(
                    tribunale=ufficio,
                    numero_rg=numero,
                    anno_rg=anno,
                    nome_parte=assistito or controparte,
                    codice_fiscale_parte=cf,
                )
            elif portale == "pdp":
                if _portale_local_channel_enabled(portale):
                    raise ValueError("Per PDP Penale la ricerca guidata usa il Local Signer dal browser.")
                from pct.pdp import crea_client_pdp

                ufficio = str(query.get("ufficio_codice") or "").strip()
                if not ufficio:
                    raise ValueError("Seleziona un ufficio giudiziario.")
                fascicoli = crea_client_pdp(demo=_polis_demo_mode()).ricerca_fascicoli(
                    ufficio=ufficio,
                    numero_rg=numero,
                    anno_rg=anno,
                    nome_imputato=assistito,
                    tipo_registro=str(query.get("registro") or "").strip() or None,
                )
            elif portale == "pat":
                raise ValueError(
                    "Per PAT l'acquisizione guidata non promette una ricerca live diretta da SIGA. "
                    "Apri il Portale dell'Avvocato ufficiale dal browser e usa HACS per il fascicolo interno, "
                    "le ricevute e l'import guidato dei file gia scaricati."
                )
            else:
                raise ValueError(
                    "Per PTT / SIGIT l'acquisizione guidata non promette una ricerca live diretta del fascicolo. "
                    "Apri il portale ufficiale o Telecontenzioso nel browser, consulta il fascicolo processuale e "
                    "poi usa HACS per il fascicolo tributario interno e per l'import guidato dei file gia scaricati."
                )
        except Exception as e:
            if _is_portale_dns_error(e):
                raise ValueError(_portale_browser_guided_message(portale)) from e
            raise

        rows = [_serialize_portale_search_item(portale, fascicolo) for fascicolo in fascicoli]
        if oggetto:
            rows = [row for row in rows if oggetto in str(row.get("oggetto") or "").lower()]
        if stato_filter:
            rows = [row for row in rows if stato_filter in str(row.get("stato") or "").lower()]
        if quick:
            rows = [
                row for row in rows
                if quick in str(row.get("procedimento") or "").lower()
                or quick in str(row.get("oggetto") or "").lower()
                or quick in str(row.get("stato") or "").lower()
            ]
        return rows

    def _preview_documenti_portale_server(portale: str, selection: dict[str, Any]) -> list[dict]:
        portale = (portale or "").strip().lower()
        try:
            if portale == "pst":
                if _portale_local_channel_enabled(portale):
                    raise ValueError("Anteprima documenti PST via browser locale richiesta.")
                from pct.polisWeb import crea_client

                docs = crea_client(demo=_polis_demo_mode()).consulta_documenti(
                    str(selection.get("ufficio_codice") or "").strip(),
                    str(selection.get("numero") or "").strip(),
                    int(selection.get("anno") or 0),
                )
            elif portale == "pdp":
                if _portale_local_channel_enabled(portale):
                    raise ValueError("Anteprima documenti PDP via browser locale richiesta.")
                from pct.pdp import crea_client_pdp

                docs = crea_client_pdp(demo=_polis_demo_mode()).consulta_documenti(
                    str(selection.get("ufficio_codice") or "").strip(),
                    str(selection.get("numero") or "").strip(),
                    int(selection.get("anno") or 0),
                )
            elif portale == "pat":
                raise ValueError(
                    "Per PAT la consultazione del fascicolo si completa nel Portale dell'Avvocato ufficiale. "
                    "In HACS puoi continuare con il fascicolo PAT interno e con l'import guidato di documenti, "
                    "provvedimenti e ricevute gia scaricati dal portale."
                )
            else:
                raise ValueError(
                    "Per PTT / SIGIT la consultazione del fascicolo si completa nel portale ufficiale e nei servizi "
                    "collegati, come Telecontenzioso. In HACS prosegui con il fascicolo tributario interno e con "
                    "l'import guidato di documenti, ricevute, provvedimenti ed esiti gia scaricati."
                )
        except Exception as e:
            if _is_portale_dns_error(e):
                raise ValueError(_portale_browser_guided_message(portale)) from e
            raise
        return [dict(vars(doc)) for doc in docs]

    def _local_signer_tools_dir() -> Path:
        return Path(__file__).parent.parent / "tools"

    def _local_signer_dist_dir() -> Path:
        return _local_signer_tools_dir() / "dist"

    def _local_signer_source_path() -> Path:
        return _local_signer_tools_dir() / "local_signer.py"

    def _local_ai_bridge_source_path() -> Path:
        return _local_signer_tools_dir() / "local_ai_host_bridge.py"

    def _local_ai_lex_context_source_path() -> Path:
        return _local_signer_tools_dir() / "lex_document_context.py"

    def _local_signer_visible_signature_source_path() -> Path:
        return Path(__file__).parent.parent / "visible_signature.py"

    def _local_signer_version() -> str:
        source = _local_signer_source_path().read_text(encoding="utf-8")
        match = re.search(r'(?m)^VERSION\s*=\s*"([^"]+)"', source)
        if not match:
            raise ValueError("Versione Local Signer non trovata in tools/local_signer.py")
        return match.group(1)

    def _local_signer_windows_cmd_name() -> str:
        return f"SetupLocalSigner-{_local_signer_version()}.cmd"

    def _local_signer_windows_cmd_path() -> Path:
        return _local_signer_dist_dir() / _local_signer_windows_cmd_name()

    def _local_signer_windows_exe_name() -> str:
        return f"SetupLocalSigner-{_local_signer_version()}.exe"

    def _local_signer_windows_ps1_name() -> str:
        return f"InstallaLocalSigner-{_local_signer_version()}.ps1"

    def _local_signer_windows_offline_ps1_name() -> str:
        """PS1 offline self-contained (generato da build_dist.py) â€” alternativa all'EXE."""
        return f"SetupLocalSigner-{_local_signer_version()}.ps1"

    def _local_signer_windows_offline_ps1_path() -> Path:
        return _local_signer_dist_dir() / _local_signer_windows_offline_ps1_name()

    def _local_signer_macos_name() -> str:
        return f"InstallaLocalSigner-{_local_signer_version()}.command"

    def _local_signer_linux_name() -> str:
        return f"InstallaLocalSigner-{_local_signer_version()}.run"

    def _local_signer_python_name() -> str:
        return f"local_signer-{_local_signer_version()}.py"

    def _local_ai_bridge_python_name() -> str:
        return f"local_ai_host_bridge-{_local_signer_version()}.py"

    def _local_ai_lex_context_python_name() -> str:
        return f"lex_document_context-{_local_signer_version()}.py"

    def _local_signer_visible_signature_python_name() -> str:
        return f"visible_signature-{_local_signer_version()}.py"

    def _local_signer_windows_exe_path() -> Path:
        # Restituisce solo il path dell'exe versionato (es. SetupLocalSigner-1.5.10.exe).
        # NON cade in fallback sul generico SetupLocalSigner.exe (potrebbe essere
        # una versione precedente) â€” se l'exe versionato non esiste il chiamante
        # deve usare la PS1 offline.
        return _local_signer_dist_dir() / _local_signer_windows_exe_name()

    def _local_signer_uffici_path() -> Path:
        return Path(__file__).parent.parent / "pct" / "data" / "uffici_ministero.json"

    def _local_signer_macos_installer_path() -> Path:
        preferred = _local_signer_dist_dir() / _local_signer_macos_name()
        legacy = _local_signer_dist_dir() / "InstallaLocalSigner.command"
        if preferred.exists():
            return preferred
        return legacy

    def _local_signer_linux_installer_path() -> Path:
        preferred = _local_signer_dist_dir() / _local_signer_linux_name()
        legacy_run = _local_signer_dist_dir() / "InstallaLocalSigner.run"
        legacy = _local_signer_dist_dir() / "installa_local_signer.sh"
        if preferred.exists():
            return preferred
        if legacy_run.exists():
            return legacy_run
        return legacy

    def _local_signer_allowed_origins(base_url: str) -> str:
        origini = {base_url.rstrip("/")}
        configured = os.getenv("PCT_BASE_URL", "").rstrip("/")
        if configured:
            origini.add(configured)
        origini.add("https://studio-legale-pct-production.up.railway.app")
        return ",".join(sorted(o for o in origini if o))

    def _render_local_signer_windows_ps1(base_url: str) -> str:
        allowed_origins = _local_signer_allowed_origins(base_url)
        version = _local_signer_version()
        return f"""# HACS Local Signer v{version} - Installazione automatica Windows
# Eseguire in PowerShell come utente normale (non richiede amministratore)
# Punto ufficiale download: https://studio-legale-pct-production.up.railway.app/impostazioni?tab=firma

$ErrorActionPreference = 'Stop'
$dir    = "$env:APPDATA\\HACS\\LocalSigner"
$venv   = "$dir\\.venv"
$py     = "$dir\\local_signer.py"
$aiBridge = "$dir\\local_ai_host_bridge.py"
$lexContext = "$dir\\lex_document_context.py"
$visibleSignature = "$dir\\visible_signature.py"
$dataDir = "$dir\\data"
$uffici = "$dataDir\\uffici_ministero.json"
$starterCmd = "$dir\\\\start_local_signer.cmd"
$starterVbs = "$dir\\\\start_local_signer.vbs"
$pyExe  = "$venv\\\\Scripts\\\\python.exe"
$pywExe = "$venv\\\\Scripts\\\\pythonw.exe"
$allowedOrigins = "{allowed_origins}"
$version = "{version}"

Write-Host "HACS Local Signer v$version - Installazione..." -ForegroundColor Cyan

New-Item -ItemType Directory -Force -Path $dir | Out-Null
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null

Write-Host "  Scarico local_signer.py..."
Invoke-WebRequest "{base_url}/polisWeb/local-signer/download" -OutFile $py -UseBasicParsing
Write-Host "  Scarico bridge AI locale..."
Invoke-WebRequest "{base_url}/polisWeb/local-signer/download/local-ai-bridge" -OutFile $aiBridge -UseBasicParsing
Write-Host "  Scarico parser documenti per Lex..."
Invoke-WebRequest "{base_url}/polisWeb/local-signer/download/lex-document-context" -OutFile $lexContext -UseBasicParsing
Write-Host "  Scarico modulo firma visibile..."
Invoke-WebRequest "{base_url}/polisWeb/local-signer/download/visible-signature" -OutFile $visibleSignature -UseBasicParsing
Write-Host "  Scarico registro uffici PST..."
Invoke-WebRequest "{base_url}/polisWeb/local-signer/download/uffici" -OutFile $uffici -UseBasicParsing

try {{
    $v = python --version 2>&1
    Write-Host "  Python trovato: $v"
}} catch {{
    Write-Host "ERRORE: Python non trovato. Scaricarlo da https://python.org" -ForegroundColor Red
    Read-Host "Premere Invio per uscire"
    exit 1
}}

Write-Host "  Creo ambiente virtuale..."
python -m venv $venv

Write-Host "  Aggiorno pip..."
& $pyExe -m pip install --quiet --upgrade pip

Write-Host "  Installo dipendenze Local Signer..."
    & $pyExe -m pip install --quiet python-pkcs11 asn1crypto cryptography zeep pdfplumber mammoth pypdf

function Test-LocalSignerOnline {{
    try {{
        $resp = Invoke-RestMethod "http://127.0.0.1:27272/ping" -UseBasicParsing -TimeoutSec 2
        return [bool]$resp.ok
    }} catch {{
        return $false
    }}
}}

function Stop-LocalSignerProcesses {{
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object {{
            $_.Name -in @("python.exe", "pythonw.exe") -and
            $_.CommandLine -and
            $_.CommandLine -like "*$py*"
        }} |
        ForEach-Object {{
            try {{
                Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop
            }} catch {{
            }}
        }}
}}

Write-Host "  Preparo l'avvio contestuale da HACS..."
$cmd = @'
@echo off
setlocal
set "DIR=%~dp0"
set "PYW=%DIR%.venv\\Scripts\\pythonw.exe"
set "PY=%DIR%local_signer.py"
set "TARGET=%DIR%local_signer.py"
set "PCT_LOCAL_SIGNER_ALLOWED_ORIGINS=__ALLOWED_ORIGINS__"
set "FORCE_RESTART=0"
set "SILENT_MODE=0"

if /I "%~1"=="--force" set "FORCE_RESTART=1"
if /I "%~1"=="--silent" set "SILENT_MODE=1"
echo %~1 | find /I "hacs-local-signer://restart" >nul 2>&1 && set "FORCE_RESTART=1"

if "%FORCE_RESTART%"=="0" (
powershell -NoProfile -WindowStyle Hidden -Command "try {{ $r = Invoke-RestMethod 'http://127.0.0.1:27272/ping' -UseBasicParsing -TimeoutSec 2; if ($r.ok) {{ exit 0 }} }} catch {{}}; exit 1" >nul 2>&1
if not errorlevel 1 goto :online
)

powershell -NoProfile -WindowStyle Hidden -Command "$target = [regex]::Escape($env:TARGET); Get-CimInstance Win32_Process | Where-Object {{ $_.Name -in @('python.exe','pythonw.exe') -and $_.CommandLine -and $_.CommandLine -match $target }} | ForEach-Object {{ try {{ Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop }} catch {{}} }}" >nul 2>&1
powershell -NoProfile -WindowStyle Hidden -Command "Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 27272 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object {{ try {{ Stop-Process -Id $_ -Force -ErrorAction Stop }} catch {{}} }}" >nul 2>&1

if exist "%PYW%" if exist "%PY%" (
    powershell -NoProfile -WindowStyle Hidden -Command "Start-Process -WindowStyle Hidden -FilePath $env:PYW -ArgumentList @($env:PY)"
) else (
    exit /b 1
)

:online
if /I "%~1"=="--background" exit /b 0
if "%SILENT_MODE%"=="1" exit /b 0
timeout /t 2 >nul
start "" "http://127.0.0.1:27272/diagnosi"
exit /b 0
'@
$cmd = $cmd.Replace('__ALLOWED_ORIGINS__', $allowedOrigins)
Set-Content -Path $starterCmd -Value $cmd -Encoding ASCII
$vbs = @"
Set shell = CreateObject("WScript.Shell")
Dim extra
extra = " --background"
If WScript.Arguments.Count > 0 Then
  If InStr(LCase(WScript.Arguments(0)), "hacs-local-signer://restart") > 0 Then
    extra = extra & " --force"
  End If
End If
shell.Run Chr(34) & "$starterCmd" & Chr(34) & extra, 0, False
"@
Set-Content -Path $starterVbs -Value $vbs -Encoding ASCII

Write-Host "  Registro il protocollo locale hacs-local-signer://..."
$protocolRoot = "HKCU:\\Software\\Classes\\hacs-local-signer"
$commandKey = Join-Path $protocolRoot "shell\\open\\command"
$wscriptExe = Join-Path $env:SystemRoot "System32\\wscript.exe"
$command = "`"$wscriptExe`" `"$starterVbs`" `"%1`""
New-Item -Path $commandKey -Force | Out-Null
Set-Item -Path $protocolRoot -Value "URL:HACS Local Signer Protocol"
New-ItemProperty -Path $protocolRoot -Name "URL Protocol" -Value "" -PropertyType String -Force | Out-Null
Set-Item -Path $commandKey -Value $command

Write-Host "  Registro il servizio nel Task Scheduler..."
$taskName = "HACS Local Signer"
$cmdExe   = Join-Path $env:SystemRoot "System32\\cmd.exe"
$action   = New-ScheduledTaskAction -Execute $cmdExe -Argument "/c `"$starterCmd`" --background"
$trigger  = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERNAME"
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit 0 -RestartCount 3
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue | Out-Null
Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "HACS Local Signer - firma documenti con smart card e token CNS/CIE" `
    -Force | Out-Null

Write-Host "  Avvio Local Signer..."
Stop-LocalSignerProcesses
Start-Sleep -Milliseconds 500
Start-Process -FilePath $starterCmd -ArgumentList "--background" -WindowStyle Hidden

Write-Host "  Attendo che il servizio risponda su 127.0.0.1:27272..."
$online = $false
for ($i = 0; $i -lt 15; $i++) {{
    try {{
        $resp = Invoke-RestMethod "http://127.0.0.1:27272/ping" -UseBasicParsing -TimeoutSec 2
        if ($resp.ok) {{
            $online = $true
            break
        }}
    }} catch {{
    }}
    Start-Sleep -Seconds 1
}}

Write-Host ""
if ($online) {{
    Write-Host "Installazione completata! Local Signer v$version pronto." -ForegroundColor Green
    Write-Host "  Il Local Signer e' attivo su http://127.0.0.1:27272"
    Write-Host "  Si avviera' automaticamente ad ogni accesso Windows."
    Write-Host "  Da ora HACS puo' avviarlo automaticamente quando clicchi Cerca."
}} else {{
    Write-Host "Installazione completata con avviso." -ForegroundColor Yellow
    Write-Host "  Il servizio non ha ancora risposto su http://127.0.0.1:27272"
    Write-Host "  Tornare su HACS e usare 'Avvia Local Signer' oppure rieseguire l installer."
}}
Write-Host ""
Write-Host "Diagnostica locale: http://127.0.0.1:27272/diagnosi" -ForegroundColor Cyan
Read-Host "Premere Invio per chiudere"
"""

    def _render_local_signer_macos_command(base_url: str) -> str:
        allowed_origins = _local_signer_allowed_origins(base_url)
        version = _local_signer_version()
        return f"""#!/bin/bash
set -euo pipefail

BASE_URL="{base_url}"
ALLOWED_ORIGINS="{allowed_origins}"
VERSION="{version}"
DIR="$HOME/Library/Application Support/HACS/LocalSigner"
DATA_DIR="$DIR/data"
VENV="$DIR/.venv"
PY="$VENV/bin/python3"
PLIST="$HOME/Library/LaunchAgents/it.hacs.local-signer.plist"

echo "HACS Local Signer v$VERSION - Installazione macOS"

mkdir -p "$DIR" "$DATA_DIR" "$(dirname "$PLIST")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 non trovato. Installarlo prima da https://python.org"
  read -r -p "Premi Invio per uscire..." _
  exit 1
fi

curl -fsSL "$BASE_URL/polisWeb/local-signer/download" -o "$DIR/local_signer.py"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/local-ai-bridge" -o "$DIR/local_ai_host_bridge.py"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/lex-document-context" -o "$DIR/lex_document_context.py"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/visible-signature" -o "$DIR/visible_signature.py"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/uffici" -o "$DATA_DIR/uffici_ministero.json"
python3 -m venv "$VENV"
"$PY" -m pip install --quiet --upgrade pip
  "$PY" -m pip install --quiet python-pkcs11 asn1crypto cryptography zeep pdfplumber mammoth pypdf

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>it.hacs.local-signer</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PY</string>
    <string>$DIR/local_signer.py</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PCT_LOCAL_SIGNER_ALLOWED_ORIGINS</key>
    <string>$ALLOWED_ORIGINS</string>
  </dict>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>WorkingDirectory</key>
  <string>$DIR</string>
</dict>
</plist>
EOF

launchctl bootout "gui/$(id -u)" "$PLIST" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl kickstart -k "gui/$(id -u)/it.hacs.local-signer"

echo
echo "Installazione completata. Local Signer v$VERSION pronto."
echo "Local Signer attivo su http://127.0.0.1:27272"
echo "Pacchetto ufficiale sempre disponibile su: https://studio-legale-pct-production.up.railway.app/impostazioni?tab=firma"
echo "Tornare su HACS e cliccare Riverifica."
read -r -p "Premi Invio per chiudere..." _
"""

    def _render_local_signer_linux_sh(base_url: str) -> str:
        allowed_origins = _local_signer_allowed_origins(base_url)
        version = _local_signer_version()
        return f"""#!/usr/bin/env bash
set -euo pipefail

BASE_URL="{base_url}"
ALLOWED_ORIGINS="{allowed_origins}"
VERSION="{version}"
DIR="${{XDG_DATA_HOME:-$HOME/.local/share}}/hacs/local-signer"
DATA_DIR="$DIR/data"
VENV="$DIR/.venv"
PY="$VENV/bin/python"
SERVICE_DIR="${{XDG_CONFIG_HOME:-$HOME/.config}}/systemd/user"
SERVICE="$SERVICE_DIR/hacs-local-signer.service"

echo "HACS Local Signer v$VERSION - Installazione Linux"

mkdir -p "$DIR" "$DATA_DIR" "$SERVICE_DIR"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 non trovato. Installarlo prima con il gestore pacchetti della distribuzione."
  read -r -p "Premi Invio per uscire..." _
  exit 1
fi

curl -fsSL "$BASE_URL/polisWeb/local-signer/download" -o "$DIR/local_signer.py"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/local-ai-bridge" -o "$DIR/local_ai_host_bridge.py"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/lex-document-context" -o "$DIR/lex_document_context.py"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/visible-signature" -o "$DIR/visible_signature.py"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/uffici" -o "$DATA_DIR/uffici_ministero.json"
python3 -m venv "$VENV"
"$PY" -m pip install --quiet --upgrade pip
  "$PY" -m pip install --quiet python-pkcs11 asn1crypto cryptography zeep pdfplumber mammoth pypdf

cat > "$SERVICE" <<EOF
[Unit]
Description=HACS Local Signer
After=network.target

[Service]
Type=simple
WorkingDirectory=$DIR
Environment=PCT_LOCAL_SIGNER_ALLOWED_ORIGINS=$ALLOWED_ORIGINS
ExecStart=$PY $DIR/local_signer.py
Restart=on-failure

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now hacs-local-signer.service

echo
echo "Installazione completata. Local Signer v$VERSION pronto."
echo "Local Signer attivo su http://127.0.0.1:27272"
echo "Pacchetto ufficiale sempre disponibile su: https://studio-legale-pct-production.up.railway.app/impostazioni?tab=firma"
echo "Tornare su HACS e cliccare Riverifica."
read -r -p "Premi Invio per chiudere..." _
"""

    def _pdp_penale_workspace_url_for_fascicolo_early(id_fasc: str) -> str:
        id_fasc = str(id_fasc or "").strip()
        if not id_fasc:
            return ""
        try:
            cases = get_pdp_penale().list_cases_for_practice(id_fasc)
        except Exception:
            cases = []
        active_case = next((row for row in cases if str(row.get("id") or "").strip()), None)
        if active_case:
            return url_for(
                "pdp_penale_workspace",
                id_fasc=id_fasc,
                case_id=str(active_case["id"]),
            )
        return url_for("pdp_penale_workspace", id_fasc=id_fasc)

    register_portali_acquisizione_routes(
        app,
        get_fascicoli=get_fascicoli,
        _spec_portale_acquisizione=_spec_portale_acquisizione,
        _pdp_penale_workspace_url_for_fascicolo=_pdp_penale_workspace_url_for_fascicolo_early,
        _build_access_status_payload=_build_access_status_payload,
        _search_fascicoli_portale_server=_search_fascicoli_portale_server,
        _preview_documenti_portale_server=_preview_documenti_portale_server,
        _build_portale_preview=_build_portale_preview,
        _coerce_import_options=_coerce_import_options,
        _coerce_mapping=_coerce_mapping,
        _analyze_portale_import=_analyze_portale_import,
        _importa_o_collega_fascicolo_portale=_importa_o_collega_fascicolo_portale,
    )

    register_telematico_dashboard_routes(
        app,
        get_fascicoli=get_fascicoli,
        get_telematico=get_telematico,
        _backfill_telematico_from_existing_fascicoli=_backfill_telematico_from_existing_fascicoli,
        _build_access_status_payload=_build_access_status_payload,
        _telematico_dashboard_warning_message=_telematico_dashboard_warning_message,
    )

    register_telematico_local_signer_routes(
        app,
        local_signer_python_name=_local_signer_python_name,
        local_ai_bridge_source_path=_local_ai_bridge_source_path,
        local_ai_bridge_python_name=_local_ai_bridge_python_name,
        local_ai_lex_context_source_path=_local_ai_lex_context_source_path,
        local_ai_lex_context_python_name=_local_ai_lex_context_python_name,
        local_signer_visible_signature_source_path=_local_signer_visible_signature_source_path,
        local_signer_visible_signature_python_name=_local_signer_visible_signature_python_name,
        local_signer_uffici_path=_local_signer_uffici_path,
        local_signer_windows_cmd_path=_local_signer_windows_cmd_path,
        local_signer_windows_cmd_name=_local_signer_windows_cmd_name,
        local_signer_windows_exe_path=_local_signer_windows_exe_path,
        local_signer_windows_exe_name=_local_signer_windows_exe_name,
        local_signer_windows_offline_ps1_path=_local_signer_windows_offline_ps1_path,
        local_signer_windows_offline_ps1_name=_local_signer_windows_offline_ps1_name,
        render_local_signer_windows_ps1=_render_local_signer_windows_ps1,
        local_signer_windows_ps1_name=_local_signer_windows_ps1_name,
        local_signer_macos_installer_path=_local_signer_macos_installer_path,
        local_signer_macos_name=_local_signer_macos_name,
        render_local_signer_macos_command=_render_local_signer_macos_command,
        local_signer_linux_installer_path=_local_signer_linux_installer_path,
        local_signer_linux_name=_local_signer_linux_name,
        render_local_signer_linux_sh=_render_local_signer_linux_sh,
        get_base_url=lambda: _get_base_url(),
    )

    register_polisweb_routes(
        app,
        get_fascicoli=get_fascicoli,
        get_clienti=get_clienti,
        get_soggetti=get_soggetti,
        audit=audit,
        polis_auth_mode=_polis_auth_mode,
        polis_demo_mode=_polis_demo_mode,
        polis_cert_preferences=_polis_cert_preferences,
    )

    register_telematico_portali_routes(
        app,
        get_fascicoli=get_fascicoli,
        get_clienti=get_clienti,
        polis_demo_mode=_polis_demo_mode,
        portale_local_channel_enabled=_portale_local_channel_enabled,
        portale_browser_guided_message=_portale_browser_guided_message,
        is_portale_dns_error=_is_portale_dns_error,
        codice_fiscale_avvocato_portale=_codice_fiscale_avvocato_portale,
        serialize_portale_search_item=_serialize_portale_search_item,
        build_portale_preview=_build_portale_preview,
        find_exact_fascicolo_locale_portale=_find_exact_fascicolo_locale_portale,
        sync_existing_fascicolo_from_portale=_sync_existing_fascicolo_from_portale,
        register_direct_portale_import_sync=_register_direct_portale_import_sync,
    )

    register_reference_lookup_routes(
        app,
        audit=audit,
    )

    # ================================================================ CLIENTI

    # ================================================================ FASCICOLI

    import io

    def _pdp_penale_bool(value: Any) -> bool:
        return str(value or "").strip().lower() in {"1", "true", "on", "si", "yes"}

    def _pdp_penale_int(value: Any, default: int = 0) -> int:
        try:
            return int(str(value or "").strip())
        except Exception:
            return default

    def _pdp_penale_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(str(value or "").strip().replace(",", "."))
        except Exception:
            return default

    def _pdp_penale_status_label(value: Any) -> str:
        testo = str(value or "").strip()
        return testo.replace("_", " ").title() if testo else "â€”"

    def _pdp_penale_guess_office_type(office_name: str) -> str:
        testo = str(office_name or "").strip().lower()
        if "procura" in testo:
            return "Procura"
        if "gip" in testo or "gup" in testo:
            return "GIP/GUP"
        if "tribunale" in testo:
            return "Tribunale"
        if "corte" in testo:
            return "Corte"
        return ""

    def _pdp_penale_guess_district(office_name: str) -> str:
        testo = str(office_name or "").strip()
        if " di " in testo:
            return testo.split(" di ", 1)[1].strip()
        return ""

    def _require_pdp_penale_fascicolo(id_fasc: str) -> Fascicolo:
        fasc = get_fascicoli().get(id_fasc)
        if not fasc:
            raise KeyError("Fascicolo non trovato.")
        if fasc.tipo != TipoFascicolo.PENALE:
            raise ValueError("Il modulo PDP Penale Ã¨ disponibile solo per i fascicoli penali.")
        return fasc

    def _require_pdp_penale_case(repo: PDPPenaleWorkflowRepository, case_id: str, practice_id: str) -> dict[str, Any]:
        case = repo.get_case(case_id)
        if str(case.get("practice_id") or "") != str(practice_id):
            raise ValueError("Il fascicolo ministeriale PDP non appartiene a questa pratica.")
        return case

    def _pdp_penale_case_defaults(fasc: Fascicolo, cliente: Optional[Cliente] = None) -> dict[str, Any]:
        cfg = get_config_studio().config
        counsel_name = (
            fasc.avvocato_referente
            or fasc.avvocato_dominus
            or getattr(cfg.studio, "avvocato", "")
            or getattr(g.utente_corrente, "nome_completo", "")
            or getattr(g.utente_corrente, "username", "")
        )
        counsel_cf = (
            getattr(cfg.firma, "cf_avvocato", "")
            or getattr(cfg.studio, "codice_fiscale_avvocato", "")
            or ""
        ).strip().upper()
        office_name = str(fasc.tribunale or "").strip()
        register_number = str(fasc.numero_rg or fasc.numero or "").strip()
        register_year = int(fasc.anno_rg or date.today().year)
        assisted_party_name = (
            getattr(cliente, "nome_completo", "")
            or str(fasc.nome_cliente or "").strip()
            or str(fasc.controparte or "").strip()
        )
        assisted_party_cf = getattr(cliente, "codice_fiscale", "") if cliente else ""
        return {
            "practice_id": fasc.id,
            "minister_case_ref": str(fasc.source_external_id or "").strip(),
            "office_name": office_name,
            "office_type": _pdp_penale_guess_office_type(office_name),
            "district": _pdp_penale_guess_district(office_name),
            "register_type": str(fasc.tipo_procedimento or "RGNR").strip() or "RGNR",
            "register_number": register_number,
            "register_year": register_year,
            "proceeding_type": str(fasc.tipo_procedimento or "procedimento_penale").strip(),
            "prosecutor_name": "",
            "judge_name": str(fasc.giudice or "").strip(),
            "chamber_section": str(fasc.sezione or "").strip(),
            "assisted_party_name": assisted_party_name,
            "assisted_party_cf": assisted_party_cf,
            "defense_counsel_name": str(counsel_name or "").strip(),
            "defense_counsel_cf": counsel_cf,
            "nomination_status": "missing",
            "access_status": "draft",
            "import_status": "not_started",
            "current_ministry_status": "",
            "notes": "",
        }

    def _ensure_pdp_penale_case_after_import(
        *,
        id_fasc: str,
        selection: dict[str, Any],
        preview: dict[str, Any],
        user_name: str,
        imported_documents: int = 0,
        downloaded_files: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        fasc = get_fascicoli().get(id_fasc)
        if not fasc or getattr(getattr(fasc, "tipo", None), "value", "") != "PENALE":
            return {}
        cliente = get_clienti().get(fasc.id_cliente) if fasc.id_cliente else None
        defaults = _pdp_penale_case_defaults(fasc, cliente)
        payload = dict(selection.get("payload") or {})
        identity = dict(preview.get("identity") or {})
        repository = get_pdp_penale()
        minister_status = str(
            payload.get("ministry_status")
            or selection.get("current_ministry_status")
            or ""
        ).strip().upper()
        if minister_status not in {
            "INVIATO",
            "IN_TRANSITO",
            "ACCETTATO",
            "IN_VERIFICA",
            "RIFIUTATO",
            "ERRORE_TECNICO",
        }:
            minister_status = ""
        case_payload = dict(defaults)
        case_payload.update(
            {
                "practice_id": fasc.id,
                "minister_case_ref": str(
                    selection.get("external_id")
                    or payload.get("id_fascicolo")
                    or defaults.get("minister_case_ref")
                    or ""
                ).strip()
                or None,
                "office_name": str(selection.get("ufficio_nome") or defaults["office_name"]).strip(),
                "register_type": str(
                    selection.get("procedimento")
                    or payload.get("tipo_registro")
                    or defaults["register_type"]
                ).strip()
                or defaults["register_type"],
                "register_number": str(selection.get("numero") or defaults["register_number"]).strip(),
                "register_year": int(selection.get("anno") or defaults["register_year"] or date.today().year),
                "proceeding_type": str(
                    payload.get("fase")
                    or payload.get("tipo_registro")
                    or defaults["proceeding_type"]
                ).strip()
                or defaults["proceeding_type"],
                "judge_name": str(payload.get("giudice") or defaults["judge_name"]).strip(),
                "chamber_section": str(selection.get("sezione") or payload.get("sezione") or defaults["chamber_section"]).strip(),
                "assisted_party_name": str(
                    (selection.get("parti") or [defaults["assisted_party_name"]])[0]
                    if (selection.get("parti") or [defaults["assisted_party_name"]])
                    else defaults["assisted_party_name"]
                ).strip(),
                "current_ministry_status": minister_status or None,
            }
        )
        available_docs = int(preview.get("counts", {}).get("documenti", 0) or 0)
        downloaded_count = len(downloaded_files or [])
        if imported_documents > 0 or downloaded_count > 0:
            case_payload["import_status"] = "completed"
        elif available_docs > 0:
            case_payload["import_status"] = "waiting_download"
        office_name_norm = _normalize_portale_match_text(case_payload["office_name"])
        register_type_norm = _normalize_portale_match_text(case_payload["register_type"])
        register_number = str(case_payload["register_number"] or "").strip()
        register_year = int(case_payload["register_year"] or 0)
        minister_ref = str(case_payload.get("minister_case_ref") or "").strip()
        current_case = None
        for row in repository.list_cases_for_practice(fasc.id):
            if minister_ref and str(row.get("minister_case_ref") or "").strip() == minister_ref:
                current_case = row
                break
            if (
                _normalize_portale_match_text(row.get("office_name")) == office_name_norm
                and _normalize_portale_match_text(row.get("register_type")) == register_type_norm
                and str(row.get("register_number") or "").strip() == register_number
                and int(row.get("register_year") or 0) == register_year
            ):
                current_case = row
                break
        if current_case:
            case = repository.update_case(str(current_case["id"]), **case_payload)
            event_type = "guided_import_synced"
            title = "Workflow PDP aggiornato dall'acquisizione guidata"
        else:
            case = repository.create_case(**case_payload)
            event_type = "guided_import_created"
            title = "Workflow PDP creato dall'acquisizione guidata"
        repository.add_event(
            str(case["id"]),
            event_type=event_type,
            event_source="import",
            title=title,
            description=f"{case_payload['register_type']} {case_payload['register_number']}/{case_payload['register_year']}",
            payload_json={
                "import_status": case_payload.get("import_status") or "",
                "available_documents": available_docs,
                "imported_documents": imported_documents,
            },
            created_by_user_id=getattr(g.utente_corrente, "id", "") or user_name,
        )
        return case

    def _pdp_penale_workspace_url_for_fascicolo(id_fasc: str) -> str:
        id_fasc = str(id_fasc or "").strip()
        if not id_fasc:
            return ""
        try:
            cases = get_pdp_penale().list_cases_for_practice(id_fasc)
        except Exception:
            cases = []
        active_case = next(
            (
                row
                for row in cases
                if str(row.get("id") or "").strip()
            ),
            None,
        )
        if active_case:
            return url_for(
                "pdp_penale_workspace",
                id_fasc=id_fasc,
                case_id=str(active_case["id"]),
            )
        return url_for("pdp_penale_workspace", id_fasc=id_fasc)

    def _pdp_penale_access_status_from_request_status(request_status: str) -> str:
        mapping = {
            "draft": "draft",
            "prepared": "ready",
            "submitted": "submitted",
            "in_review": "waiting_authorization",
            "authorized": "authorized",
            "denied": "denied",
            "expired": "expired",
            "technical_error": "technical_error",
            "downloaded": "authorized",
            "closed": "authorized",
        }
        return mapping.get(str(request_status or "").strip(), "draft")

    def _pdp_penale_local_documents(fasc: Fascicolo, gf: GestioneFascicoli) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for doc in sorted(fasc.documenti or [], key=lambda item: item.data_caricamento or "", reverse=True):
            try:
                percorso = gf.percorso_documento(fasc.id, doc.id)
            except Exception:
                continue
            testo = _fascicolo_text(
                getattr(doc, "nome", ""),
                getattr(doc, "note", ""),
                getattr(getattr(doc, "tipo", None), "value", getattr(doc, "tipo", "")),
            )
            ruolo = "other"
            if "nomina" in testo or "procura" in testo:
                ruolo = "nomination"
            elif "accesso" in testo or "istanza" in testo or "richiesta" in testo:
                ruolo = "access_request"
            elif "pagopa" in testo or "contribut" in testo or "ricevuta" in testo:
                ruolo = "payment_receipt"
            elif "gratuito patrocinio" in testo or "patrocinio" in testo:
                ruolo = "legal_aid_order"
            elif "verbale" in testo:
                ruolo = "hearing_minutes"
            elif "ordinanza" in testo:
                ruolo = "ordinance"
            elif "sentenza" in testo:
                ruolo = "judgment"
            elif "decreto" in testo:
                ruolo = "decree"
            elif "memoria" in testo or "difesa" in testo:
                ruolo = "defense_brief"
            rows.append(
                {
                    "id": doc.id,
                    "nome": doc.nome,
                    "tipo": getattr(getattr(doc, "tipo", None), "value", ""),
                    "note": doc.note,
                    "percorso": str(percorso),
                    "dimensione_bytes": int(getattr(doc, "dimensione_bytes", 0) or 0),
                    "firmato": bool(getattr(doc, "firmato_digitalmente", False)),
                    "hash_sha256": str(getattr(doc, "hash_sha256", "") or "").strip(),
                    "role_suggestion": ruolo,
                    "data_documento": str(getattr(doc, "data_documento", "") or "").strip(),
                }
            )
        return rows

    def _pdp_penale_tipo_documento_locale(document_role: str) -> TipoDocumento:
        mapping = {
            "nomination": TipoDocumento.PROCURA,
            "access_request": TipoDocumento.ATTO_GIUDIZIARIO,
            "payment_receipt": TipoDocumento.COMUNICAZIONE,
            "legal_aid_order": TipoDocumento.ALLEGATO,
            "pec_message": TipoDocumento.COMUNICAZIONE,
            "download_package": TipoDocumento.ALLEGATO,
            "ministry_document": TipoDocumento.ALLEGATO,
            "hearing_minutes": TipoDocumento.VERBALE,
            "decree": TipoDocumento.DECRETO,
            "ordinance": TipoDocumento.ORDINANZA,
            "judgment": TipoDocumento.SENTENZA,
            "defense_brief": TipoDocumento.MEMORIA,
            "attachment": TipoDocumento.ALLEGATO,
            "other": TipoDocumento.ALLEGATO,
        }
        return mapping.get(str(document_role or "").strip(), TipoDocumento.ALLEGATO)

    def _pdp_penale_primary_access_request(access_requests: list[dict[str, Any]]) -> dict[str, Any]:
        aperte = [
            row for row in (access_requests or [])
            if str(row.get("request_status") or "").strip() not in {"closed", "expired", "denied"}
        ]
        return dict((aperte or access_requests or [{}])[0])

    def _pdp_penale_download_state(download_until: str) -> str:
        testo = str(download_until or "").strip()
        if not testo:
            return "missing"
        try:
            deadline = datetime.fromisoformat(testo.replace("Z", "+00:00"))
        except Exception:
            return "scheduled"
        now = datetime.now(deadline.tzinfo) if deadline.tzinfo else datetime.now()
        return "expired" if deadline < now else "open"

    def _pdp_penale_module_documents_enriched(
        fasc: Fascicolo,
        gf: GestioneFascicoli,
        module_documents: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        local_by_path: dict[str, Documento] = {}
        for doc in fasc.documenti or []:
            try:
                local_by_path[str(gf.percorso_documento(fasc.id, doc.id))] = doc
            except Exception:
                continue
        enriched: list[dict[str, Any]] = []
        for row in module_documents:
            item = dict(row)
            local_doc = local_by_path.get(str(item.get("file_path") or "").strip())
            if local_doc:
                item["local_doc_id"] = local_doc.id
                item["view_url"] = url_for("visualizza_documento", id_fasc=fasc.id, id_doc=local_doc.id)
                item["download_url"] = url_for("scarica_documento", id_fasc=fasc.id, id_doc=local_doc.id)
            classification = pdp_penale_classifica_documento(
                str(item.get("original_filename") or item.get("title") or ""),
                str(item.get("title") or ""),
                str(item.get("notes") or ""),
            )
            item["document_category"] = item.get("document_category") or classification["document_category"]
            enriched.append(item)
        return enriched

    def _pdp_penale_build_deposit_documents(local_documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        candidati = [
            dict(doc)
            for doc in (local_documents or [])
            if doc.get("firmato") or doc.get("role_suggestion") in {"access_request", "defense_brief", "nomination"}
        ]
        return candidati or list(local_documents or [])

    def _pdp_penale_request_reference(case_row: dict[str, Any]) -> str:
        numero = re.sub(r"[^A-Za-z0-9]+", "", str(case_row.get("register_number") or "").upper()) or "CASE"
        stamp = datetime.now().strftime("%Y%m%d%H%M")
        return f"PDP-ACCESS-{numero}-{stamp}"

    def _pdp_penale_generate_request_pdf(
        fasc: Fascicolo,
        cliente: Optional[Cliente],
        case_row: dict[str, Any],
        *,
        request_reference: str,
        nomination_docs: list[dict[str, Any]],
        payment_docs: list[dict[str, Any]],
        legal_aid_docs: list[dict[str, Any]],
    ) -> bytes:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=A4,
            topMargin=36,
            bottomMargin=36,
            leftMargin=42,
            rightMargin=42,
        )
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name="PDPBody", parent=styles["BodyText"], leading=15, spaceAfter=6))
        styles.add(ParagraphStyle(name="PDPTitle", parent=styles["Heading1"], textColor=colors.HexColor("#9f1239"), spaceAfter=14))
        story: list[Any] = []
        story.append(Paragraph("Richiesta di accesso al fascicolo PDP Penale", styles["PDPTitle"]))
        story.append(Paragraph(
            "Documento operativo generato dal gestionale per il deposito tramite il Portale Deposito Atti Penale.",
            styles["PDPBody"],
        ))
        righe = [
            ["Riferimento richiesta", request_reference],
            ["Ufficio giudiziario", str(case_row.get("office_name") or "")],
            ["Procedimento", f"{case_row.get('register_type') or 'RGNR'} {case_row.get('register_number')}/{case_row.get('register_year')}"],
            ["Assistito", str(case_row.get("assisted_party_name") or "")],
            ["Codice fiscale assistito", str(case_row.get("assisted_party_cf") or "") or "-"],
            ["Difensore", str(case_row.get("defense_counsel_name") or "")],
            ["Codice fiscale difensore", str(case_row.get("defense_counsel_cf") or "")],
            ["Pratica interna", f"{fasc.numero} - {fasc.titolo}"],
        ]
        table = Table(righe, colWidths=(160, 320))
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ]))
        story.append(table)
        story.append(Spacer(1, 14))
        assisted_cf = str(case_row.get("assisted_party_cf") or "").strip()
        cliente_label = getattr(cliente, "nome_completo", "") if cliente else ""
        story.append(Paragraph(
            (
                f"Il sottoscritto difensore {case_row.get('defense_counsel_name') or '-'} "
                f"chiede l'accesso al fascicolo digitale relativo al procedimento indicato, "
                f"nell'interesse di {case_row.get('assisted_party_name') or cliente_label or '-'}"
                + (f" (CF {assisted_cf})" if assisted_cf else "")
                + "."
            ),
            styles["PDPBody"],
        ))
        allegati = [
            f"Nomina / titolo di accesso: {len(nomination_docs)}",
            f"Ricevute pagamento: {len(payment_docs)}",
            f"Gratuito patrocinio: {len(legal_aid_docs)}",
        ]
        story.append(Paragraph("Checklist allegati predisposti:", styles["Heading3"]))
        for voce in allegati:
            story.append(Paragraph(f"- {voce}", styles["PDPBody"]))
        if case_row.get("notes"):
            story.append(Spacer(1, 10))
            story.append(Paragraph("Note operative", styles["Heading3"]))
            story.append(Paragraph(str(case_row.get("notes") or ""), styles["PDPBody"]))
        story.append(Spacer(1, 14))
        story.append(Paragraph(
            f"Documento generato il {date.today().strftime('%d/%m/%Y')} dal workflow PDP Penale HACS.",
            styles["PDPBody"],
        ))
        doc.build(story)
        return buf.getvalue()

    def _pdp_penale_email_text(email_row: Any) -> str:
        corpo_html = re.sub(r"<[^>]+>", " ", str(getattr(email_row, "corpo_html", "") or ""))
        return " ".join(
            str(part or "").strip()
            for part in [
                getattr(email_row, "oggetto", ""),
                getattr(email_row, "mittente", ""),
                getattr(email_row, "mittente_nome", ""),
                getattr(email_row, "destinatari", ""),
                getattr(email_row, "corpo_testo", ""),
                corpo_html,
            ]
            if str(part or "").strip()
        )

    def _pdp_penale_email_text_search(email_row: Any) -> str:
        return _fascicolo_text(
            getattr(email_row, "oggetto", ""),
            getattr(email_row, "mittente", ""),
            getattr(email_row, "mittente_nome", ""),
            getattr(email_row, "destinatari", ""),
            getattr(email_row, "corpo_testo", ""),
            re.sub(r"<[^>]+>", " ", str(getattr(email_row, "corpo_html", "") or "")),
        )

    def _pdp_penale_match_email_score(
        case_row: dict[str, Any],
        access_requests: list[dict[str, Any]],
        email_row: Any,
    ) -> int:
        testo = _pdp_penale_email_text_search(email_row)
        score = 0
        numero_rg = str(case_row.get("register_number") or "").strip().lower()
        anno_rg = str(case_row.get("register_year") or "").strip()
        if numero_rg and anno_rg and numero_rg in testo and anno_rg in testo:
            score += 6
        minister_ref = str(case_row.get("minister_case_ref") or "").strip().lower()
        if minister_ref and minister_ref in testo:
            score += 5
        office = str(case_row.get("office_name") or "").strip().lower()
        if office and office in testo:
            score += 3
        district = str(case_row.get("district") or "").strip().lower()
        if district and district in testo:
            score += 1
        assisted_tokens = [part for part in re.split(r"\s+", str(case_row.get("assisted_party_name") or "").strip().lower()) if len(part) > 2]
        if assisted_tokens and sum(1 for token in assisted_tokens if token in testo) >= min(2, len(assisted_tokens)):
            score += 3
        for req in access_requests[:3]:
            ref = str(req.get("request_reference") or "").strip().lower()
            if ref and ref in testo:
                score += 4
        if any(token in testo for token in ("password", "download", "fascicolo", "documenti disponibili")):
            score += 1
        return score

    def _pdp_penale_find_case_local_document(fasc: Fascicolo, doc_id: str) -> Documento | None:
        return next((doc for doc in fasc.documenti or [] if str(doc.id) == str(doc_id)), None)

    def _pdp_penale_sync_case_mailbox(
        fasc: Fascicolo,
        case_row: dict[str, Any],
        access_requests: list[dict[str, Any]],
    ) -> dict[str, Any]:
        from pct.email_client import GestioneEmailRicevute

        repo = get_pdp_penale()
        cfg = get_config_studio().config
        email_db = app.config.get("EMAIL_CASELLA_DB", os.environ.get("PCT_EMAIL_DB", "./email/casella.json"))
        ge = GestioneEmailRicevute(db_path=email_db)
        sync_result = {"nuove": 0, "errore": ""}
        if getattr(cfg, "pec", None) and getattr(cfg.pec, "imap_host", "") and getattr(cfg.pec, "indirizzo", "") and getattr(cfg.pec, "password", ""):
            sync_result = ge.sincronizza_imap(
                imap_host=cfg.pec.imap_host,
                imap_port=int(getattr(cfg.pec, "imap_port", 993) or 993),
                username=cfg.pec.indirizzo,
                password=cfg.pec.password,
                use_ssl=bool(getattr(cfg.pec, "use_ssl", True)),
                cartelle_imap=["INBOX"],
                limite=80,
            )
        emails = ge.tutte(cartella="INBOX", data_da=(date.today() - timedelta(days=30)).isoformat())
        existing_pec = repo.list_pec_messages(str(case_row.get("id") or ""))
        existing_headers = {
            str(row.get("message_id_header") or "").strip()
            for row in existing_pec
            if str(row.get("message_id_header") or "").strip()
        }
        matched = 0
        password_found = 0
        latest_deadline = ""
        detected_ministry_status = ""
        now_iso = datetime.now().isoformat(timespec="minutes")
        for email_row in emails:
            header_id = str(getattr(email_row, "message_id", "") or "").strip()
            if header_id and header_id in existing_headers:
                continue
            if _pdp_penale_match_email_score(case_row, access_requests, email_row) < 5:
                continue
            testo = _pdp_penale_email_text(email_row)
            testo_search = testo.lower()
            password = pdp_penale_estrai_password(testo, getattr(email_row, "oggetto", ""))
            scadenza = pdp_penale_estrai_scadenza_download(testo, getattr(email_row, "data", ""))
            if any(token in testo_search for token in ("rifiutat", "rigettat", "dinieg")):
                detected_ministry_status = "RIFIUTATO"
            elif "in verifica" in testo_search:
                detected_ministry_status = "IN_VERIFICA"
            elif any(token in testo_search for token in ("accettat", "autorizzat")) or password:
                detected_ministry_status = "ACCETTATO"
            elif "in transito" in testo_search:
                detected_ministry_status = "IN_TRANSITO"
            repo.register_pec_message(
                criminal_case_id=str(case_row.get("id") or ""),
                mailbox=str(getattr(cfg.pec, "indirizzo", "") or "").strip() or "PEC",
                sender=str(getattr(email_row, "mittente", "") or "").strip() or None,
                recipient=str(getattr(email_row, "destinatari", "") or "").strip() or None,
                subject=str(getattr(email_row, "oggetto", "") or "Comunicazione PDP Penale").strip(),
                message_date=str(getattr(email_row, "data", "") or "").strip() or None,
                message_id_header=header_id or None,
                body_text=str(getattr(email_row, "corpo_testo", "") or "").strip() or None,
                matched=1,
                matched_reason="pdp_penale_mailbox_sync",
                extracted_password=password or None,
                contains_download_notice=int(bool(scadenza) or ("download" in testo_search)),
                processed=1,
                processed_at=now_iso,
            )
            matched += 1
            if password:
                password_found += 1
            if scadenza and (not latest_deadline or scadenza > latest_deadline):
                latest_deadline = scadenza
            if header_id:
                existing_headers.add(header_id)

        case_changes: dict[str, Any] = {"last_sync_at": now_iso}
        if latest_deadline:
            case_changes["download_available_until"] = latest_deadline
            if str(case_row.get("import_status") or "") not in {"completed", "partial_import"}:
                case_changes["import_status"] = "waiting_download"
            case_changes["access_status"] = "authorized"
        if password_found:
            case_changes["pec_password_received"] = 1
        if matched:
            if detected_ministry_status:
                case_changes["current_ministry_status"] = detected_ministry_status
                if detected_ministry_status == "RIFIUTATO":
                    case_changes["access_status"] = "denied"
                elif detected_ministry_status == "IN_VERIFICA":
                    case_changes["access_status"] = "waiting_authorization"
            repo.update_case(str(case_row.get("id") or ""), **case_changes)
            request = _pdp_penale_primary_access_request(access_requests)
            if request and request.get("id"):
                request_changes = {
                    "pec_password_received_at": now_iso,
                    "download_link_available": 1 if latest_deadline else int(bool(request.get("download_link_available"))),
                }
                if detected_ministry_status:
                    request_changes["ministry_status"] = detected_ministry_status
                if latest_deadline:
                    request_changes["download_available_until"] = latest_deadline
                    if str(request.get("request_status") or "") in {"submitted", "in_review", "prepared"}:
                        request_changes["request_status"] = "authorized"
                elif detected_ministry_status == "RIFIUTATO":
                    request_changes["request_status"] = "denied"
                repo.update_access_request(str(request["id"]), **request_changes)
            repo.add_event(
                str(case_row.get("id") or ""),
                event_type="pec_sync_completed",
                event_source="pec",
                title="Sincronizzazione PEC PDP completata",
                description=f"{matched} messaggi associati al fascicolo ministeriale.",
                payload_json={
                    "matched_messages": matched,
                    "password_found": password_found,
                    "download_available_until": latest_deadline,
                    "nuove_email": int(sync_result.get("nuove", 0) or 0),
                },
                created_by_user_id=getattr(g.utente_corrente, "id", ""),
            )
            existing_tasks = repo.list_tasks(str(case_row.get("id") or ""), only_open=True)
            if latest_deadline and not any(str(task.get("task_type") or "") == "download_case_file" for task in existing_tasks):
                repo.create_task(
                    str(case_row.get("id") or ""),
                    task_type="download_case_file",
                    title="Scaricare fascicolo PDP entro la finestra disponibile",
                    description=f"Password PEC rilevata automaticamente. Download entro {latest_deadline}.",
                    priority="urgent",
                    due_at=latest_deadline[:10],
                    status="open",
                    assigned_user_id=getattr(g.utente_corrente, "id", "") or None,
                )
        return {
            "matched": matched,
            "password_found": password_found,
            "download_available_until": latest_deadline,
            "sync_result": sync_result,
        }

    def _pdp_penale_import_download_items(
        fasc: Fascicolo,
        case_row: dict[str, Any],
        *,
        items: list[dict[str, Any]],
        note_importazione: str = "",
    ) -> dict[str, Any]:
        gf = get_fascicoli()
        repo = get_pdp_penale()
        existing_module_paths = {
            str(doc.get("file_path") or "").strip()
            for doc in repo.list_case_documents(str(case_row.get("id") or ""))
        }
        existing_docs = {
            _normalizza_nome_match_portale(getattr(doc, "nome", "")): doc
            for doc in (fasc.documenti or [])
            if getattr(doc, "nome", "")
        }
        created_local: list[Documento] = []
        linked_module = 0
        for item in items:
            nome = str(item.get("nome") or "").strip()
            payload = item.get("contenuto", b"")
            if not nome or not payload:
                continue
            classification = pdp_penale_classifica_documento(
                nome,
                str(item.get("tipo_atto") or ""),
                str(item.get("origine") or ""),
            )
            nome_norm = _normalizza_nome_match_portale(nome)
            doc_locale = existing_docs.get(nome_norm)
            if doc_locale is None:
                doc_locale = _salva_documento_fascicolo(
                    gf=gf,
                    id_fasc=fasc.id,
                    nome_file=nome,
                    raw=payload,
                    tipo_doc=_pdp_penale_tipo_documento_locale(classification["document_role"]),
                    note=" | ".join(
                        part for part in [
                            "Importato da pacchetto PDP Penale",
                            note_importazione.strip(),
                            str(item.get("origine") or "").strip(),
                        ] if part
                    ),
                    data_documento=str(item.get("data_documento") or date.today().isoformat()),
                    firmato=nome.lower().endswith(".p7m"),
                    caricato_da=getattr(g.utente_corrente, "username", ""),
                )
                existing_docs[nome_norm] = doc_locale
                created_local.append(doc_locale)
            file_path = ""
            try:
                file_path = str(gf.percorso_documento(fasc.id, doc_locale.id))
            except Exception:
                file_path = ""
            if file_path and file_path not in existing_module_paths:
                repo.add_document(
                    str(case_row.get("id") or ""),
                    document_role=classification["document_role"],
                    document_category=classification["document_category"] or None,
                    title=doc_locale.nome,
                    original_filename=doc_locale.nome,
                    stored_filename=doc_locale.nome,
                    file_path=file_path,
                    file_size_bytes=int(getattr(doc_locale, "dimensione_bytes", 0) or 0),
                    sha256=str(getattr(doc_locale, "hash_sha256", "") or "").strip() or None,
                    source_type="download",
                    signed=int(bool(getattr(doc_locale, "firmato_digitalmente", False))),
                    minister_document_date=str(item.get("data_documento") or "").strip() or None,
                    imported_from_download=1,
                    notes=str(item.get("origine") or "").strip() or None,
                )
                existing_module_paths.add(file_path)
                linked_module += 1
        import_status = "completed"
        if created_local or linked_module:
            unknown_docs = [
                doc for doc in repo.list_case_documents(str(case_row.get("id") or ""))
                if int(doc.get("imported_from_download") or 0) == 1
                and str(doc.get("document_role") or "") in {"other", "attachment"}
            ]
            if unknown_docs:
                import_status = "partial_import"
            repo.update_case(
                str(case_row.get("id") or ""),
                import_status=import_status,
                last_download_at=datetime.now().isoformat(timespec="minutes"),
                access_status="authorized",
            )
            access_requests = repo.list_access_requests(str(case_row.get("id") or ""))
            request = _pdp_penale_primary_access_request(access_requests)
            if request and request.get("id"):
                repo.update_access_request(
                    str(request["id"]),
                    request_status="downloaded",
                    downloaded_at=datetime.now().isoformat(timespec="minutes"),
                )
            repo.add_event(
                str(case_row.get("id") or ""),
                event_type="download_imported",
                event_source="import",
                title="Pacchetto PDP importato nel fascicolo",
                description=f"{len(created_local)} nuovi documenti locali, {linked_module} documenti classificati.",
                payload_json={
                    "created_local": len(created_local),
                    "linked_module": linked_module,
                    "import_status": import_status,
                },
                created_by_user_id=getattr(g.utente_corrente, "id", ""),
            )
        return {
            "created_local": created_local,
            "linked_module": linked_module,
            "import_status": import_status,
        }

    def _pdp_penale_build_checklist(
        fasc: Fascicolo,
        case_form: dict[str, Any],
        active_case: dict[str, Any],
        local_documents: list[dict[str, Any]],
        module_documents: list[dict[str, Any]],
        access_requests: list[dict[str, Any]],
        pec_messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        nomina_docs = [
            doc for doc in (local_documents + module_documents)
            if str(doc.get("role_suggestion") or doc.get("document_role") or "") == "nomination"
        ]
        payment_docs = [
            doc for doc in (local_documents + module_documents)
            if str(doc.get("role_suggestion") or doc.get("document_role") or "") == "payment_receipt"
        ]
        legal_aid_docs = [
            doc for doc in (local_documents + module_documents)
            if str(doc.get("role_suggestion") or doc.get("document_role") or "") == "legal_aid_order"
        ]
        request = access_requests[0] if access_requests else {}
        password_received = bool(int(active_case.get("pec_password_received") or 0)) or any(
            str(msg.get("extracted_password") or "").strip() for msg in pec_messages
        )
        download_until = (
            str(request.get("download_available_until") or "").strip()
            or str(active_case.get("download_available_until") or "").strip()
        )
        ready_prereq = all(
            [
                str(case_form.get("office_name") or "").strip(),
                str(case_form.get("register_number") or "").strip(),
                _pdp_penale_int(case_form.get("register_year"), 0) > 0,
                str(case_form.get("assisted_party_name") or "").strip(),
                str(case_form.get("defense_counsel_name") or "").strip(),
                str(case_form.get("defense_counsel_cf") or "").strip(),
            ]
        )

        def _step(done: bool, warning: bool = False) -> str:
            if done:
                return "success"
            return "warning" if warning else "secondary"

        return [
            {
                "title": "Verifica prerequisiti",
                "variant": _step(ready_prereq, warning=bool(case_form.get("office_name") or case_form.get("register_number"))),
                "done": ready_prereq,
                "detail": "Difensore, codice fiscale, assistito, ufficio e riferimento procedimento.",
            },
            {
                "title": "Verifica titolo di accesso",
                "variant": _step(str(active_case.get("nomination_status") or "") in {"deposited", "accepted"}, warning=bool(nomina_docs)),
                "done": str(active_case.get("nomination_status") or "") in {"deposited", "accepted"},
                "detail": "Nomina presente o giÃ  depositata/accettata.",
            },
            {
                "title": "Verifica allegati obbligatori",
                "variant": _step(bool(nomina_docs), warning=bool(payment_docs or legal_aid_docs)),
                "done": bool(nomina_docs),
                "detail": f"Nomina: {len(nomina_docs)} Â· PagoPA: {len(payment_docs)} Â· Gratuito patrocinio: {len(legal_aid_docs)}",
            },
            {
                "title": "Generazione richiesta accesso atti",
                "variant": _step(bool(request), warning=str(active_case.get('access_status') or '') in {'ready', 'submitted'}),
                "done": bool(request),
                "detail": "Prepara la richiesta, registra il deposito e mantieni il riferimento interno.",
            },
            {
                "title": "Monitoraggio esito ministeriale",
                "variant": _step(
                    str(active_case.get("current_ministry_status") or "") in {"ACCETTATO", "IN_VERIFICA"},
                    warning=bool(active_case.get("current_ministry_status")),
                ),
                "done": str(active_case.get("current_ministry_status") or "") in {"ACCETTATO", "IN_VERIFICA"},
                "detail": f"Stato tecnico: {_pdp_penale_status_label(active_case.get('current_ministry_status'))}",
            },
            {
                "title": "PEC, password e finestra download",
                "variant": _step(password_received, warning=bool(download_until)),
                "done": password_received,
                "detail": f"Password PEC: {'ricevuta' if password_received else 'assente'}{f' Â· Disponibile fino al {download_until}' if download_until else ''}",
            },
            {
                "title": "Import fascicolo nel gestionale",
                "variant": _step(str(active_case.get("import_status") or "") == "completed", warning=str(active_case.get("import_status") or "") in {"waiting_download", "downloaded", "partial_import"}),
                "done": str(active_case.get("import_status") or "") == "completed",
                "detail": f"Stato import: {_pdp_penale_status_label(active_case.get('import_status'))}",
            },
        ]

    def _pdp_penale_build_workspace(fasc: Fascicolo, cliente: Optional[Cliente] = None) -> dict[str, Any]:
        repo = get_pdp_penale()
        gf = get_fascicoli()
        cases = repo.list_cases_for_practice(fasc.id)
        active_case_id = str(request.args.get("case_id") or "").strip()
        active_case = next((row for row in cases if str(row.get("id")) == active_case_id), None)
        if active_case is None and cases:
            active_case = cases[0]
        active_case = dict(active_case or {})
        case_form = _pdp_penale_case_defaults(fasc, cliente)
        if active_case:
            case_form.update({k: v for k, v in active_case.items() if v not in (None, "")})
        local_documents = _pdp_penale_local_documents(fasc, gf)
        module_documents = repo.list_case_documents(str(active_case.get("id") or "")) if active_case else []
        module_documents = _pdp_penale_module_documents_enriched(fasc, gf, module_documents)
        access_requests = repo.list_access_requests(str(active_case.get("id") or "")) if active_case else []
        pec_messages = repo.list_pec_messages(str(active_case.get("id") or "")) if active_case else []
        tasks = repo.list_tasks(str(active_case.get("id") or "")) if active_case else []
        open_tasks = [task for task in tasks if str(task.get("status") or "") in {"open", "in_progress"}]
        events = repo.list_case_events(str(active_case.get("id") or "")) if active_case else []
        primary_request = _pdp_penale_primary_access_request(access_requests) if access_requests else {}
        download_until = (
            str(primary_request.get("download_available_until") or "").strip()
            or str(active_case.get("download_available_until") or "").strip()
        )
        password_available = bool(int(active_case.get("pec_password_received") or 0)) or any(
            str(msg.get("extracted_password") or "").strip() for msg in pec_messages
        )
        checklist = _pdp_penale_build_checklist(
            fasc,
            case_form,
            active_case,
            local_documents,
            module_documents,
            access_requests,
            pec_messages,
        )
        return {
            "cases": cases,
            "active_case": active_case,
            "case_form": case_form,
            "events": events,
            "module_documents": module_documents,
            "local_documents": local_documents,
            "access_requests": access_requests,
            "primary_request": primary_request,
            "pec_messages": pec_messages,
            "tasks": tasks,
            "open_tasks": open_tasks,
            "wizard_checklist": checklist,
            "deposit_documents": _pdp_penale_build_deposit_documents(local_documents),
            "password_available": password_available,
            "download_available_until": download_until,
            "download_state": _pdp_penale_download_state(download_until),
            "stats": {
                "case_count": len(cases),
                "documents_count": len(module_documents),
                "requests_count": len(access_requests),
                "pec_count": len(pec_messages),
                "tasks_open": len(open_tasks),
            },
        }

    def _pdp_penale_summary_for_fascicolo(fasc: Fascicolo) -> dict[str, Any]:
        if fasc.tipo != TipoFascicolo.PENALE:
            return {}
        repo = get_pdp_penale()
        cases = repo.list_overview_for_practice(fasc.id)
        active = dict(cases[0]) if cases else {}
        return {
            "enabled": True,
            "url": url_for("pdp_penale_workspace", id_fasc=fasc.id),
            "case_count": len(cases),
            "active_case": active,
            "has_case": bool(active),
            "open_tasks": int(active.get("open_tasks_count") or 0) if active else 0,
            "documents_count": int(active.get("documents_count") or 0) if active else 0,
        }

    register_fascicoli_core_routes(
        app,
        get_fascicoli=get_fascicoli,
        get_clienti=get_clienti,
        get_agenda=get_agenda,
        get_scadenziario=get_scadenziario,
        get_soggetti=get_soggetti,
        get_workspace_intelligente=get_workspace_intelligente,
        get_config_studio=get_config_studio,
        sync_pubblica=sync_pubblica,
        track_recente=track_recente,
        build_responsabile_conformita_fascicolo=_build_responsabile_conformita_fascicolo,
        build_fascicolo_workspace=_build_fascicolo_workspace,
        fascicolo_form_correction_context=_fascicolo_form_correction_context,
        pst_import_dir_for_fascicolo=_pst_import_dir_for_fascicolo,
        pst_import_pending_count=_pst_import_pending_count,
        catalogo_documenti_portale_fascicolo=_catalogo_documenti_portale_fascicolo,
        gruppa_catalogo_documenti_portale=_gruppa_catalogo_documenti_portale,
        portale_ufficiale_label=_portale_ufficiale_label,
        pdp_penale_summary_for_fascicolo=_pdp_penale_summary_for_fascicolo,
        luogo_timbro_firma_visibile=_luogo_timbro_firma_visibile,
    )

    register_fascicoli_pdp_routes(
        app,
        get_fascicoli=get_fascicoli,
        get_clienti=get_clienti,
        get_pdp_penale=get_pdp_penale,
        get_config_studio=get_config_studio,
        audit=audit,
        sync_pubblica=sync_pubblica,
        require_pdp_penale_fascicolo=_require_pdp_penale_fascicolo,
        require_pdp_penale_case=_require_pdp_penale_case,
        pdp_penale_build_workspace=_pdp_penale_build_workspace,
        pdp_penale_case_defaults=_pdp_penale_case_defaults,
        pdp_penale_int=_pdp_penale_int,
        pdp_penale_float=_pdp_penale_float,
        pdp_penale_bool=_pdp_penale_bool,
        pdp_penale_request_reference=_pdp_penale_request_reference,
        pdp_penale_primary_access_request=_pdp_penale_primary_access_request,
        pdp_penale_access_status_from_request_status=_pdp_penale_access_status_from_request_status,
        pdp_penale_local_documents=_pdp_penale_local_documents,
        pdp_penale_module_documents_enriched=_pdp_penale_module_documents_enriched,
        pdp_penale_generate_request_pdf=_pdp_penale_generate_request_pdf,
        pdp_penale_find_case_local_document=_pdp_penale_find_case_local_document,
        pdp_penale_sync_case_mailbox=_pdp_penale_sync_case_mailbox,
        pdp_penale_import_download_items=_pdp_penale_import_download_items,
        pdp_penale_status_label=_pdp_penale_status_label,
        decrypt_doc=_decrypt_doc,
        resolve_ufficio_destinatario=_resolve_ufficio_destinatario,
        polis_demo_mode=_polis_demo_mode,
        salva_documento_fascicolo=_salva_documento_fascicolo,
        espandi_file_importato_portale=_espandi_file_importato_portale,
        pst_import_dir_for_fascicolo=_pst_import_dir_for_fascicolo,
        leggi_staging_documenti_portale=_leggi_staging_documenti_portale,
        archivia_staging_documenti_portale=_archivia_staging_documenti_portale,
    )

    # ================================================================ BLUEPRINTS
    register_blueprints(app)

    def _get_base_url() -> str:
        """Restituisce la base URL pubblica (sempre HTTPS in produzione).

        PrioritÃ :
        1. PCT_BASE_URL env var â€” impostare su Railway/Render per URL stabile
           (es. https://mio-studio.up.railway.app)
        2. request.host_url aggiornato da ProxyFix (funziona se X-Forwarded-Proto Ã¨ impostato)
        3. Fallback: forza https:// su qualunque schema rilevato

        Imposta PCT_BASE_URL nelle variabili d'ambiente Railway per eliminare
        qualsiasi ambiguitÃ  HTTP/HTTPS nei feed iCal.
        """
        # 1. URL esplicito configurato dall'amministratore
        configured = os.getenv("PCT_BASE_URL", "").rstrip("/")
        if configured:
            return configured
        # 2. Legge request.host_url (ProxyFix la aggiorna con X-Forwarded-Proto)
        #    e come safety net forza sempre https:// se il deploy Ã¨ in produzione
        base = request.host_url.rstrip("/")
        if base.startswith("http://"):
            # ProxyFix non ha ricevuto X-Forwarded-Proto â†’ forza https manualmente
            base = "https://" + base[len("http://"):]
        return base

    # ---- Avvio scheduler background
    from pct.scheduler import start_scheduler
    start_scheduler(app)

    return app
