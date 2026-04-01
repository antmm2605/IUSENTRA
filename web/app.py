"""
Flask web application — Studio Legale PCT.

Avvio:
    python -m web
    oppure: flask --app web.app run --debug
"""

import csv
import io
import os
import json
import queue
import shutil
import threading
import zipfile as _zipfile
from datetime import date, datetime, timedelta
from pathlib import Path

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    send_file,
    Response,
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
    TipoDocumento as TipoDocumentoCliente,
    Indirizzo,
    Recapiti,
    DocumentoIdentita,
    RiferimentoProcedimento,
)
from pct.fascicoli import (
    GestioneFascicoli,
    Fascicolo,
    TipoFascicolo,
    StatoFascicolo,
    TipoDocumento,
    TipoAttivita,
    EsitoAttivita,
    AttivitaProcessuale,
    Documento,
    DocumentoVersione,
)
from pct.messaggi import (
    GestioneMessaggi,
    CanaleMsggio,
    StatoMessaggio,
    TipoAutomazione,
    ConfigEmail,
    ConfigTwilio,
    ConfigMessaggistica,
)
from pct.backup import (
    GestioneBackup,
    TipoBackup,
    StatoBackup,
    FrequenzaBackup,
    ConfigBackup,
)
from pct.auth import (
    GestioneUtenti,
    Utente,
    RuoloUtente,
    PERMESSI,
    TUTTI_PERMESSI,
    DESCRIZIONI_RUOLI,
    genera_totp_secret,
    verifica_totp,
    totp_uri,
)
from pct.privacy import GestioneTrattamenti, TrattamentoDati
from pct.soggetti import (
    GestioneSoggetti,
    Soggetto,
    TipoSoggetto,
    RuoloSoggetto,
    ParteProcessuale,
)
from pct.scadenziario import (
    GestioneScadenziario,
    Scadenza,
    TipoTermine,
    PrioritaTermine,
    StatoTermine,
    PRESET_TERMINI,
    calcola_termine,
    festività_italiane,
    è_giorno_lavorativo,
)
from pct.search_index import IndiceRicerca
from pct.ocr import estrai_testo as ocr_estrai_testo, estensione_supportata as ocr_supportato
from pct.reports import fascicolo_pdf, scadenze_pdf, faldone_pdf, lista_fascicoli_pdf, lista_clienti_pdf
from pct.database import GestioneDatabase
from pct.sync import GestoreSincronizzazione, get_gestore
from pct.condivisione import GestioneCondivisioni, RuoloCondivisione
from pct import __version__ as APP_VERSION

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
    """Decifra i byte del documento. No-op se il file non è cifrato (magic header assente)."""
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


# Avvia il worker all'import del modulo (daemon → termina con il processo)
_ocr_thread = threading.Thread(target=_ocr_worker, daemon=True, name="ocr-worker")
_ocr_thread.start()


def _accoda_ocr(percorso: str, hash_sha256: str, id_fasc: str, id_doc: str,
                nome_doc: str, tipo_doc: str, index_path: str):
    """Accoda un job OCR se il file è di un tipo supportato."""
    if not ocr_supportato(nome_doc):
        return
    with _ocr_stats_lock:
        _ocr_stats["totale"] += 1
        _ocr_stats["in_coda"] = _ocr_queue.qsize() + 1
    _ocr_queue.put((percorso, hash_sha256, id_fasc, id_doc, nome_doc, tipo_doc, index_path))


# ------------------------------------------------------------------ factory

def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")

    # ProxyFix: necessario su Railway/Render/Heroku e qualsiasi reverse proxy.
    # Senza questo, request.scheme è sempre "http" (schema interno) →
    # url_for() e request.host_url generano link http:// invece di https://,
    # rompendo i feed iCal sottoscritti da Google Calendar (che richiede HTTPS).
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    app.secret_key = os.getenv("PCT_SECRET_KEY", "dev-secret-pct-2024")
    app.config["SECRET_KEY"] = app.secret_key

    # Sicurezza sessioni
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=8)
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = os.getenv("PCT_HTTPS", "").lower() in ("1", "true", "yes")

    cfg = config or {}
    app.config["AGENDA_DB"] = cfg.get(
        "AGENDA_DB", os.getenv("PCT_AGENDA_DB", "./agenda/appuntamenti.json")
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
    app.config["STUDIO_NOME"] = os.getenv("PCT_STUDIO_NOME", "Studio Legale PCT")
    app.config["PORTALE_DB"] = cfg.get(
        "PORTALE_DB", os.getenv("PCT_PORTALE_DB", "./portale/portali.json")
    )
    app.config["PORTALE_UPLOADS"] = cfg.get(
        "PORTALE_UPLOADS", os.getenv("PCT_PORTALE_UPLOADS", "./portale/uploads")
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
    # Scheduler
    app.config["BACKUP_ORA"]       = os.getenv("PCT_BACKUP_ORA", "02:00")
    app.config["WA_REMINDER_ORA"]  = os.getenv("PCT_WA_REMINDER_ORA", "18:00")
    # Assistente virtuale PCT (Ollama locale)
    app.config["OLLAMA_URL"]       = os.getenv("PCT_OLLAMA_URL", "http://localhost:11434")
    app.config["OLLAMA_MODEL"]     = os.getenv("PCT_OLLAMA_MODEL", "mistral")
    # Pagamenti digitali
    app.config["PAGAMENTI_DIR"] = cfg.get(
        "PAGAMENTI_DIR", os.getenv("PCT_PAGAMENTI_DIR", "./pagamenti")
    )
    # Multi-tenant
    app.config["TENANTS_REGISTRY"] = cfg.get(
        "TENANTS_REGISTRY", os.getenv("PCT_TENANTS_REGISTRY", "./data/tenants.json")
    )
    app.config["MULTI_TENANT"] = os.getenv("PCT_MULTI_TENANT", "1").lower() not in ("0", "false", "no")
    # Impostazioni studio persistenti (PEC, firma, SMTP, WhatsApp, scheduler)
    app.config["STUDIO_CONFIG"] = cfg.get(
        "STUDIO_CONFIG", os.getenv("PCT_STUDIO_CONFIG", "./config/studio.json")
    )
    # ── Carica config studio da JSON al boot (prevale sulle env vars se esiste) ──
    try:
        from pct.config_studio import GestioneConfigStudio as _GCS
        _gs_boot = _GCS(app.config["STUDIO_CONFIG"])
        _sc = _gs_boot.config
        # Dati studio
        if _sc.studio.nome:
            app.config["STUDIO_NOME"]      = _sc.studio.nome
            app.config["STUDIO_AVVOCATO"]  = _sc.studio.avvocato
            app.config["STUDIO_PIVA"]      = _sc.studio.piva
            app.config["STUDIO_CF"]        = _sc.studio.cf
            app.config["STUDIO_INDIRIZZO"] = _sc.studio.indirizzo
            app.config["STUDIO_IBAN"]      = _sc.studio.iban
        # WhatsApp
        if _sc.whatsapp.twilio_sid:
            app.config["TWILIO_SID"]    = _sc.whatsapp.twilio_sid
            app.config["TWILIO_TOKEN"]  = _sc.whatsapp.twilio_token
            app.config["TWILIO_NUMERO"] = _sc.whatsapp.twilio_numero
        if _sc.whatsapp.callmebot_key:
            app.config["CALLMEBOT_KEY"] = _sc.whatsapp.callmebot_key
        # Scheduler
        if _sc.scheduler.backup_ora:
            app.config["BACKUP_ORA"]       = _sc.scheduler.backup_ora
            app.config["WA_REMINDER_ORA"]  = _sc.scheduler.wa_reminder_ora
        # SMTP — conservati in chiavi proprie per get_messaggi()
        app.config["SMTP_HOST"]     = _sc.smtp.host or os.getenv("PCT_SMTP_HOST", "")
        app.config["SMTP_PORT"]     = _sc.smtp.port or int(os.getenv("PCT_SMTP_PORT", "587"))
        app.config["SMTP_USER"]     = _sc.smtp.username or os.getenv("PCT_SMTP_USER", "")
        app.config["SMTP_PASS"]     = _sc.smtp.password or os.getenv("PCT_SMTP_PASS", "")
        app.config["SMTP_FROM"]     = _sc.smtp.from_address or os.getenv("PCT_SMTP_FROM", "")
        app.config["SMTP_FROM_NAME"]= _sc.smtp.from_name or app.config.get("STUDIO_NOME", "Studio Legale")
        app.config["SMTP_USE_TLS"]  = _sc.smtp.use_tls
    except Exception:
        # Fallback: usa solo env vars (già impostati sopra)
        app.config.setdefault("SMTP_HOST",      os.getenv("PCT_SMTP_HOST", ""))
        app.config.setdefault("SMTP_PORT",      int(os.getenv("PCT_SMTP_PORT", "587")))
        app.config.setdefault("SMTP_USER",      os.getenv("PCT_SMTP_USER", ""))
        app.config.setdefault("SMTP_PASS",      os.getenv("PCT_SMTP_PASS", ""))
        app.config.setdefault("SMTP_FROM",      os.getenv("PCT_SMTP_FROM", ""))
        app.config.setdefault("SMTP_FROM_NAME", app.config.get("STUDIO_NOME", "Studio Legale"))
        app.config.setdefault("SMTP_USE_TLS",   True)

    def get_agenda() -> Agenda:
        if not hasattr(g, "_agenda"):
            g._agenda = Agenda(db_path=app.config["AGENDA_DB"])
        return g._agenda

    def get_clienti() -> GestioneClienti:
        if not hasattr(g, "_clienti"):
            g._clienti = GestioneClienti(db_path=app.config["CLIENTI_DB"])
        return g._clienti

    def get_fascicoli() -> GestioneFascicoli:
        if not hasattr(g, "_fascicoli"):
            g._fascicoli = GestioneFascicoli(
                db_path=app.config["FASCICOLI_DB"],
                documents_dir=app.config["FASCICOLI_DOCS"],
                archive_dir=app.config["FASCICOLI_ARCH"],
            )
        return g._fascicoli

    def _portale_ufficiale_label(fasc: Fascicolo) -> str:
        if fasc.tipo == TipoFascicolo.PENALE:
            return "PDP"
        if fasc.tipo == TipoFascicolo.AMMINISTRATIVO:
            return "PAT"
        return "PolisWeb / PST"

    def _tipo_lotto_portale(fasc: Fascicolo) -> str:
        if fasc.tipo == TipoFascicolo.PENALE:
            return "Acquisizione documenti PDP"
        if fasc.tipo == TipoFascicolo.AMMINISTRATIVO:
            return "Acquisizione documenti PAT"
        return "Acquisizione documenti PolisWeb"

    def _pst_import_dir_for_fascicolo(fasc: Fascicolo) -> Path:
        return Path(app.config["PST_IMPORT_DIR"]) / fasc.id

    def _pst_import_pending_count(fasc: Fascicolo) -> int:
        cartella = _pst_import_dir_for_fascicolo(fasc)
        if not cartella.exists():
            return 0
        return sum(1 for path in cartella.rglob("*") if path.is_file())

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
        _accoda_ocr(
            percorso=str(gf.percorso_documento(id_fasc, doc.id)),
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
        return GestioneMessaggi(config=cfg, db_path=app.config["MESSAGGI_DB"])

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
            g._utenti = GestioneUtenti(
                db_path=app.config["AUTH_DB"],
                audit_path=app.config["AUDIT_DB"],
                secret_key=app.secret_key,
            )
        return g._utenti

    def get_scadenziario() -> GestioneScadenziario:
        if not hasattr(g, "_scadenziario"):
            g._scadenziario = GestioneScadenziario(db_path=app.config["SCADENZIARIO_DB"])
        return g._scadenziario

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
            g._trattamenti = GestioneTrattamenti(db_path=app.config["PRIVACY_DB"])
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
        Verifica se l'utente corrente può accedere alla cartella di un cliente.
        - Utenti con permesso globale 'clienti.leggi' → sempre True
        - Altri → solo se la cartella è stata condivisa con loro al livello richiesto
        """
        u = g.utente_corrente
        if not u:
            return False
        if u.ha_permesso("clienti.leggi"):
            return True
        return get_condivisioni().ha_accesso(u.id, id_cliente, richiesto)

    def get_database() -> GestioneDatabase:
        return GestioneDatabase({
            "clienti": app.config["CLIENTI_DB"],
            "fascicoli": app.config["FASCICOLI_DB"],
            "appuntamenti": app.config["AGENDA_DB"],
            "scadenze": app.config["SCADENZIARIO_DB"],
            "messaggi": app.config["MESSAGGI_DB"],
            "utenti": app.config["AUTH_DB"],
            "audit": app.config["AUDIT_DB"],
            "search_index": app.config["SEARCH_INDEX"],
        })

    # Singleton di sincronizzazione (uno per processo Flask)
    _sync = get_gestore()

    # ---------------------------------------------------------------- auth middleware

    from flask import session, g, abort

    @app.before_request
    def carica_utente_corrente():
        """Inietta g.utente_corrente ad ogni request; verifica inattività (8h)."""
        g.utente_corrente = None
        uid = session.get("user_id")
        if uid:
            last = session.get("last_activity")
            if last:
                try:
                    delta = datetime.now() - datetime.fromisoformat(last)
                    if delta.total_seconds() > 8 * 3600:
                        session.clear()
                        return redirect(url_for("login", next=request.path, timeout=1))
                except ValueError:
                    pass
            session["last_activity"] = datetime.now().isoformat()
            # Multi-tenant: carica utente dal corretto auth db in base al tenant in sessione
            tenant_slug = session.get("tenant_slug", "")
            if tenant_slug and app.config.get("MULTI_TENANT"):
                from pct.tenant import GestioneTenant
                tm = GestioneTenant(registry_path=app.config["TENANTS_REGISTRY"])
                percorsi = tm.percorsi_dati(tenant_slug)
                gu = GestioneUtenti(
                    db_path=percorsi["AUTH_DB"],
                    audit_path=percorsi["AUDIT_DB"],
                    secret_key=app.secret_key,
                    crea_admin_se_vuoto=False,
                )
            else:
                gu = get_utenti()
            g.utente_corrente = gu.get(uid)

    @app.before_request
    def carica_tenant():
        """
        Inietta g.tenant (StudioLegale) in base al tenant_slug nella sessione.
        Se multi-tenant attivo, sovrascrive i percorsi dati in g.data_paths.
        """
        g.tenant = None
        g.data_paths = {}  # paths per-request; vuoto = usa config globale
        if not app.config.get("MULTI_TENANT"):
            return
        u = getattr(g, "utente_corrente", None)
        tenant_slug = session.get("tenant_slug") or (u.tenant_slug if u else "")
        if not tenant_slug:
            return
        from pct.tenant import GestioneTenant
        tm = GestioneTenant(registry_path=app.config["TENANTS_REGISTRY"])
        studio = tm.get(tenant_slug)
        if studio:
            g.tenant = studio
            g.data_paths = tm.percorsi_dati(tenant_slug)

    # Route pubbliche che non richiedono login.
    # Le route del Local Signer devono essere scaricabili senza sessione:
    # - il browser può aprire il download in un contesto senza cookie;
    # - lo script PowerShell scarica local_signer.py senza autenticarsi.
    _ROUTE_PUBBLICHE = {
        "login",
        "login_2fa",
        "static",
        "logout",
        "admin.esci_impersonazione",
        "polis_local_signer_download",
        "polis_local_signer_download_uffici",
        "polis_local_signer_installa",
        "polis_local_signer_setup_windows",
        "polis_local_signer_setup_windows_exe",
        "polis_local_signer_setup_macos",
        "polis_local_signer_setup_linux",
    }

    @app.before_request
    def richiedi_login():
        if request.endpoint in _ROUTE_PUBBLICHE:
            return
        if request.endpoint and request.endpoint.startswith(("api_", "portale")):
            return  # API e portale gestiscono autonomamente
        if g.utente_corrente is None:
            return redirect(url_for("login", next=request.path))

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

    # ---------------------------------------------------------------- context

    @app.template_filter("fmt_data")
    def fmt_data(val: str) -> str:
        if not val:
            return "—"
        try:
            from datetime import date
            d = date.fromisoformat(val[:10])
            return d.strftime("%d/%m/%Y")
        except ValueError:
            return val

    @app.context_processor
    def inject_globals():
        return {
            "oggi": date.today(),
            "ora_adesso": datetime.now().strftime("%H:%M"),
            "TipoAppuntamento": TipoAppuntamento,
            "StatoAppuntamento": StatoAppuntamento,
            "TipoCliente": TipoCliente,
            "StatoCliente": StatoCliente,
            "TipoFascicolo": TipoFascicolo,
            "StatoFascicolo": StatoFascicolo,
            "TipoAttivita": TipoAttivita,
            "EsitoAttivita": EsitoAttivita,
            "utente_corrente": g.get("utente_corrente"),
            "RuoloUtente": RuoloUtente,
            "DESCRIZIONI_RUOLI": DESCRIZIONI_RUOLI,
            "n_operatori_connessi": _sync.n_connessi,
            "RuoloCondivisione": RuoloCondivisione,
            "recenti": session.get("recenti", []),
            "app_version": APP_VERSION,
        }

    # ================================================================ PWA

    @app.route("/sw.js")
    def service_worker():
        """Service Worker servito dalla root per scope '/'."""
        return send_file(
            app.root_path + "/static/sw.js",
            mimetype="application/javascript",
        )

    @app.route("/offline")
    def offline():
        """Pagina fallback mostrata dal service worker quando si è offline."""
        return render_template("offline.html")

    # ================================================================ ERRORI

    @app.errorhandler(403)
    def errore_403(e):
        return render_template("errori/403.html"), 403

    @app.errorhandler(404)
    def errore_404(e):
        return render_template("errori/404.html"), 404

    @app.errorhandler(500)
    def errore_500(e):
        import traceback as _tb
        # e.__traceback__ è l'unico modo affidabile per ottenere il traceback
        # fuori dal contesto dell'eccezione (come in Flask error handler)
        tb_str = "".join(_tb.format_exception(type(e), e, e.__traceback__))
        app.logger.error("500 Internal Server Error: %s\n%s", e, tb_str)
        return render_template("errori/500.html"), 500

    # ================================================================ AUTH

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if g.utente_corrente:
            return redirect(url_for("dashboard"))
        errore = None
        if request.method == "POST":
            studio_slug = request.form.get("studio_slug", "").strip().lower()
            # Multi-tenant: se è specificato uno studio, carica auth da quel tenant
            if studio_slug and app.config.get("MULTI_TENANT"):
                from pct.tenant import GestioneTenant
                tm = GestioneTenant(registry_path=app.config["TENANTS_REGISTRY"])
                studio = tm.get(studio_slug)
                if not studio:
                    return render_template("auth/login.html", errore="Studio non trovato.", multi_tenant=True)
                percorsi = tm.percorsi_dati(studio_slug)
                gu = GestioneUtenti(
                    db_path=percorsi["AUTH_DB"],
                    audit_path=percorsi["AUDIT_DB"],
                    secret_key=app.secret_key,
                    crea_admin_se_vuoto=False,
                )
            else:
                gu = get_utenti()
            utente = gu.autentica(
                request.form.get("username", ""),
                request.form.get("password", ""),
            )
            if utente:
                if utente.totp_attivato:
                    # Credenziali OK ma serve verifica 2FA
                    session.clear()
                    session["totp_pending_uid"] = utente.id
                    session["totp_pending_next"] = request.args.get("next") or url_for("dashboard")
                    return redirect(url_for("login_2fa"))
                session.clear()
                session["user_id"] = utente.id
                session["tenant_slug"] = utente.tenant_slug or ""
                session["last_activity"] = datetime.now().isoformat()
                session.permanent = True
                gu.registra_evento(
                    "auth.login",
                    id_utente=utente.id,
                    username=utente.username,
                    ip=request.remote_addr or "",
                )
                next_url = request.args.get("next") or url_for("dashboard")
                return redirect(next_url)
            else:
                errore = "Credenziali non valide o utente disabilitato."
                gu.registra_evento(
                    "auth.login_fallito",
                    username=request.form.get("username", ""),
                    ip=request.remote_addr or "",
                    esito="ERRORE",
                )
        return render_template(
            "auth/login.html",
            errore=errore,
            multi_tenant=app.config.get("MULTI_TENANT", False),
        )

    @app.route("/logout", methods=["POST"])
    def logout():
        u = g.utente_corrente
        if u:
            get_utenti().registra_evento(
                "auth.logout",
                id_utente=u.id,
                username=u.username,
                ip=request.remote_addr or "",
            )
        session.clear()
        flash("Disconnessione effettuata.", "info")
        return redirect(url_for("login"))

    @app.route("/login/2fa", methods=["GET", "POST"])
    def login_2fa():
        """Secondo step di login: verifica codice TOTP."""
        uid = session.get("totp_pending_uid")
        if not uid:
            return redirect(url_for("login"))
        gu = get_utenti()
        utente = gu.get(uid)
        if not utente or not utente.totp_attivato:
            session.pop("totp_pending_uid", None)
            return redirect(url_for("login"))
        errore = None
        if request.method == "POST":
            codice = request.form.get("codice", "").strip()
            if verifica_totp(utente.totp_secret, codice):
                next_url = session.pop("totp_pending_next", url_for("dashboard"))
                session.clear()
                session["user_id"] = utente.id
                session["tenant_slug"] = utente.tenant_slug or ""
                session["last_activity"] = datetime.now().isoformat()
                session.permanent = True
                gu.registra_evento("auth.login", id_utente=utente.id,
                                   username=utente.username, ip=request.remote_addr or "")
                return redirect(next_url)
            errore = "Codice non valido. Riprova."
            gu.registra_evento("auth.2fa_fallito", id_utente=utente.id,
                               username=utente.username, ip=request.remote_addr or "",
                               esito="ERRORE")
        return render_template("auth/login_2fa.html", errore=errore, username=utente.username)

    @app.route("/profilo", methods=["GET", "POST"])
    def profilo():
        u = g.utente_corrente
        if request.method == "POST":
            azione = request.form.get("azione")
            gu = get_utenti()
            if azione == "aggiorna":
                try:
                    gu.aggiorna(u.id,
                                nome_completo=request.form.get("nome_completo", ""),
                                email=request.form.get("email", ""))
                    flash("Profilo aggiornato.", "success")
                except ValueError as e:
                    flash(str(e), "danger")
            elif azione == "password":
                pwd_old = request.form.get("password_old", "")
                pwd_new = request.form.get("password_new", "")
                if not gu.autentica(u.username, pwd_old):
                    flash("Password attuale non corretta.", "danger")
                elif len(pwd_new) < 8:
                    flash("La nuova password deve avere almeno 8 caratteri.", "danger")
                else:
                    gu.cambia_password(u.id, pwd_new)
                    audit("auth.cambia_password")
                    flash("Password aggiornata.", "success")
            elif azione == "2fa_genera":
                segreto = genera_totp_secret()
                session["totp_temp_secret"] = segreto
                flash("Segreto 2FA generato. Scansiona il QR code e conferma con un codice.", "info")
            elif azione == "2fa_conferma":
                segreto = session.get("totp_temp_secret", "")
                codice = request.form.get("codice_2fa", "").strip()
                if segreto and verifica_totp(segreto, codice):
                    gu.aggiorna(u.id, totp_secret=segreto, totp_attivato=True)
                    session.pop("totp_temp_secret", None)
                    audit("auth.2fa_attivato")
                    flash("Autenticazione a due fattori attivata.", "success")
                else:
                    flash("Codice non valido. Riprova a scansionare il QR code.", "danger")
            elif azione == "2fa_disattiva":
                pwd = request.form.get("pwd_disattiva", "")
                if gu.autentica(u.username, pwd):
                    gu.aggiorna(u.id, totp_secret="", totp_attivato=False)
                    session.pop("totp_temp_secret", None)
                    audit("auth.2fa_disattivato")
                    flash("2FA disattivato.", "success")
                else:
                    flash("Password non corretta.", "danger")
            return redirect(url_for("profilo"))
        totp_temp = session.get("totp_temp_secret", "")
        uri_qr = totp_uri(totp_temp, u.username) if totp_temp else ""
        return render_template("auth/profilo.html", utente=u,
                               totp_temp_secret=totp_temp, totp_uri_qr=uri_qr,
                               oggi=date.today())

    # ---- Gestione utenti (solo AMMINISTRATORE)

    @app.route("/utenti")
    def lista_utenti():
        u = g.utente_corrente
        if not u or not u.ha_permesso("utenti.leggi"):
            abort(403)
        gu = get_utenti()
        utenti = gu.tutti()
        stats = gu.statistiche()
        return render_template("auth/utenti.html",
                               utenti=utenti, stats=stats, ruoli=list(RuoloUtente),
                               oggi=date.today())

    @app.route("/utenti/nuovo", methods=["GET", "POST"])
    def nuovo_utente():
        u = g.utente_corrente
        if not u or not u.ha_permesso("utenti.scrivi"):
            abort(403)
        if request.method == "POST":
            gu = get_utenti()
            try:
                nuovo = gu.crea(
                    username=request.form["username"],
                    password=request.form["password"],
                    ruolo=RuoloUtente(request.form["ruolo"]),
                    email=request.form.get("email", ""),
                    nome_completo=request.form.get("nome_completo", ""),
                )
                audit("utenti.crea", "utente", nuovo.id, f"username={nuovo.username}")
                flash(f"Utente '{nuovo.username}' creato.", "success")
                return redirect(url_for("lista_utenti"))
            except ValueError as e:
                flash(str(e), "danger")
        return render_template("auth/form_utente.html", ruoli=list(RuoloUtente), utente=None,
                               oggi=date.today())

    @app.route("/utenti/<id_utente>/modifica", methods=["GET", "POST"])
    def modifica_utente(id_utente):
        u = g.utente_corrente
        if not u or not u.ha_permesso("utenti.scrivi"):
            abort(403)
        gu = get_utenti()
        target = gu.get(id_utente)
        if not target:
            flash("Utente non trovato.", "warning")
            return redirect(url_for("lista_utenti"))
        if request.method == "POST":
            try:
                gu.aggiorna(id_utente,
                            nome_completo=request.form.get("nome_completo", ""),
                            email=request.form.get("email", ""),
                            ruolo=request.form.get("ruolo", target.ruolo.value),
                            attivo=request.form.get("attivo") == "1")
                if request.form.get("nuova_password"):
                    gu.cambia_password(id_utente, request.form["nuova_password"])
                audit("utenti.modifica", "utente", id_utente)
                flash("Utente aggiornato.", "success")
                return redirect(url_for("lista_utenti"))
            except ValueError as e:
                flash(str(e), "danger")
        return render_template("auth/form_utente.html",
                               ruoli=list(RuoloUtente), utente=target, oggi=date.today())

    @app.route("/utenti/<id_utente>/elimina", methods=["POST"])
    def elimina_utente(id_utente):
        u = g.utente_corrente
        if not u or not u.ha_permesso("utenti.elimina"):
            abort(403)
        gu = get_utenti()
        try:
            gu.elimina(id_utente)
            audit("utenti.elimina", "utente", id_utente)
            flash("Utente eliminato.", "success")
        except ValueError as e:
            flash(str(e), "danger")
        return redirect(url_for("lista_utenti"))

    @app.route("/audit")
    def audit_log():
        u = g.utente_corrente
        if not u or not u.ha_permesso("audit.leggi"):
            abort(403)
        gu = get_utenti()
        id_utente = request.args.get("id_utente", "")
        azione = request.args.get("azione", "")
        eventi = gu.audit_log(id_utente=id_utente, azione=azione, limit=200)
        utenti = gu.tutti()
        return render_template("auth/audit.html",
                               eventi=eventi, utenti=utenti,
                               filtro_utente=id_utente, filtro_azione=azione,
                               oggi=date.today())

    @app.route("/api/utenti/statistiche")
    def api_utenti_statistiche():
        u = g.utente_corrente
        if not u or not u.ha_permesso("utenti.leggi"):
            abort(403)
        try:
            return jsonify(get_utenti().statistiche())
        except Exception as e:
            app.logger.exception("Errore api_utenti_statistiche: %s", e)
            return jsonify({"errore": str(e)}), 200

    # ---- Gestione profili / matrice permessi

    @app.route("/profili")
    def profili():
        """Pagina matrice ruoli × permessi."""
        u = g.utente_corrente
        if not u or not u.ha_permesso("utenti.leggi"):
            abort(403)
        gu = get_utenti()
        utenti_per_ruolo = {r: gu.per_ruolo(r) for r in RuoloUtente}
        return render_template(
            "auth/profili.html",
            ruoli=list(RuoloUtente),
            tutti_permessi=TUTTI_PERMESSI,
            permessi=PERMESSI,
            descrizioni=DESCRIZIONI_RUOLI,
            utenti_per_ruolo=utenti_per_ruolo,
            oggi=date.today(),
        )

    @app.route("/utenti/<id_utente>/permessi", methods=["GET", "POST"])
    def permessi_utente(id_utente):
        """Gestione override permessi per un singolo utente."""
        u = g.utente_corrente
        if not u or not u.ha_permesso("utenti.scrivi"):
            abort(403)
        gu = get_utenti()
        target = gu.get(id_utente)
        if not target:
            flash("Utente non trovato.", "warning")
            return redirect(url_for("lista_utenti"))
        if request.method == "POST":
            extra = request.form.getlist("permessi_extra")
            negati = request.form.getlist("permessi_negati")
            try:
                gu.aggiorna_permessi(id_utente, extra, negati)
                audit("utenti.aggiorna_permessi",
                      risorsa_tipo="utente", risorsa_id=id_utente,
                      dettagli=f"extra={extra} negati={negati}")
                flash(f"Permessi di {target.username} aggiornati.", "success")
            except ValueError as e:
                flash(str(e), "danger")
            return redirect(url_for("permessi_utente", id_utente=id_utente))
        return render_template(
            "auth/permessi_utente.html",
            target=target,
            tutti_permessi=TUTTI_PERMESSI,
            permessi_ruolo=PERMESSI.get(target.ruolo, []),
            descrizioni=DESCRIZIONI_RUOLI,
            oggi=date.today(),
        )

    # ================================================================ SCADENZIARIO

    @app.route("/scadenziario")
    def scadenziario():
        gs = get_scadenziario()
        filtro_tipo = request.args.get("tipo", "")
        filtro_priorita = request.args.get("priorita", "")
        id_fascicolo = request.args.get("id_fascicolo", "")
        scadenze = gs.tutte(
            tipo=TipoTermine(filtro_tipo) if filtro_tipo else None,
            priorita=PrioritaTermine(filtro_priorita) if filtro_priorita else None,
            id_fascicolo=id_fascicolo,
        )
        scadute = gs.scadute()
        imminenti = gs.imminenti(entro_giorni=7)
        stats = gs.statistiche()
        return render_template(
            "scadenziario/lista.html",
            scadenze=scadenze,
            scadute=scadute,
            imminenti=imminenti,
            stats=stats,
            tipi=list(TipoTermine),
            priorita_list=list(PrioritaTermine),
            filtro_tipo=filtro_tipo,
            filtro_priorita=filtro_priorita,
            id_fascicolo=id_fascicolo,
        )

    @app.route("/scadenziario/nuova", methods=["GET", "POST"])
    def nuova_scadenza():
        if request.method == "POST":
            gs = get_scadenziario()
            f = request.form
            from_cliente = f.get("from_cliente", "")
            try:
                preset = f.get("preset", "")
                data_scadenza = f.get("data_scadenza", "").strip()
                if not preset and not data_scadenza:
                    raise ValueError("Data scadenza obbligatoria")
                if preset:
                    data_decorrenza = f.get("data_decorrenza", "").strip()
                    if not data_decorrenza:
                        raise ValueError("Seleziona la data decorrenza per il calcolo automatico del termine")
                    sc = gs.nuova_da_preset(
                        preset_key=preset,
                        titolo=f["titolo"].strip(),
                        data_decorrenza=data_decorrenza,
                        id_fascicolo=f.get("id_fascicolo", ""),
                        perentorio=f.get("perentorio") == "1",
                        id_utente_responsabile=f.get("id_utente", ""),
                    )
                else:
                    sc = gs.nuova(
                        titolo=f["titolo"].strip(),
                        tipo=TipoTermine(f["tipo"]),
                        data_scadenza=data_scadenza,
                        id_fascicolo=f.get("id_fascicolo", ""),
                        descrizione=f.get("descrizione", ""),
                        data_decorrenza=f.get("data_decorrenza", "").strip(),
                        perentorio=f.get("perentorio") == "1",
                        id_utente_responsabile=f.get("id_utente", ""),
                    )
                audit("scadenziario.crea", "scadenza", sc.id, sc.titolo)
                flash(f"Scadenza '{sc.titolo}' creata.", "success")
                sync_pubblica("crea", "scadenze", sc.id)
                if from_cliente:
                    return redirect(url_for("cartella_cliente", id_cliente=from_cliente))
                return redirect(url_for("scadenziario"))
            except (ValueError, KeyError) as e:
                flash(str(e), "danger")
        gf = get_fascicoli()
        gu = get_utenti()
        id_cliente_get = request.args.get("id_cliente", "")
        from_cliente_get = request.args.get("from_cliente", "")
        # Fascicoli pre-filtrati per cliente se arrivato dalla cartella
        fascicoli = gf.tutti()
        id_fascicolo_presel = ""
        if id_cliente_get:
            fascicoli_cliente = [f for f in fascicoli if f.id_cliente == id_cliente_get]
            if fascicoli_cliente:
                fascicoli = fascicoli_cliente
                id_fascicolo_presel = fascicoli_cliente[0].id
        return render_template(
            "scadenziario/form.html",
            tipi=list(TipoTermine),
            preset_list=PRESET_TERMINI,
            fascicoli=fascicoli,
            utenti=gu.tutti(solo_attivi=True),
            scadenza=None,
            id_cliente=id_cliente_get,
            from_cliente=from_cliente_get,
            id_fascicolo_presel=id_fascicolo_presel,
        )

    @app.route("/scadenziario/<id_sc>")
    def dettaglio_scadenza(id_sc):
        gs = get_scadenziario()
        sc = gs.get(id_sc)
        if not sc:
            flash("Scadenza non trovata.", "warning")
            return redirect(url_for("scadenziario"))
        return render_template("scadenziario/dettaglio.html", sc=sc)

    @app.route("/scadenziario/<id_sc>/modifica", methods=["GET", "POST"])
    def modifica_scadenza(id_sc):
        gs = get_scadenziario()
        sc = gs.get(id_sc)
        if not sc:
            flash("Scadenza non trovata.", "warning")
            return redirect(url_for("scadenziario"))
        if request.method == "POST":
            f = request.form
            try:
                gs.aggiorna(
                    id_sc,
                    titolo=f.get("titolo", sc.titolo),
                    tipo=f.get("tipo", sc.tipo.value),
                    data_scadenza=f.get("data_scadenza", sc.data_scadenza),
                    descrizione=f.get("descrizione", sc.descrizione),
                    perentorio=f.get("perentorio") == "1",
                    note=f.get("note", sc.note),
                )
                audit("scadenziario.modifica", "scadenza", id_sc)
                flash("Scadenza aggiornata.", "success")
                sync_pubblica("modifica", "scadenze", id_sc)
                return redirect(url_for("scadenziario"))
            except (ValueError, KeyError) as e:
                flash(str(e), "danger")
        gf = get_fascicoli()
        gu = get_utenti()
        return render_template(
            "scadenziario/form.html",
            tipi=list(TipoTermine),
            preset_list=PRESET_TERMINI,
            fascicoli=gf.tutti(),
            utenti=gu.tutti(solo_attivi=True),
            scadenza=sc,
        )

    @app.route("/scadenziario/<id_sc>/completa", methods=["POST"])
    def completa_scadenza(id_sc):
        gs = get_scadenziario()
        note = request.form.get("note", "")
        try:
            gs.completa(id_sc, note=note)
            audit("scadenziario.completa", "scadenza", id_sc)
            sync_pubblica("modifica", "scadenze", id_sc)
        except ValueError as e:
            if request.headers.get("HX-Request"):
                return f'<tr id="sc-{id_sc}"><td colspan="7" class="text-danger small p-2">{e}</td></tr>', 422
            flash(str(e), "danger")
            return redirect(url_for("scadenziario"))
        # htmx: rimuove la riga dalla tabella con animazione
        if request.headers.get("HX-Request"):
            return f'<tr id="sc-{id_sc}" class="sc-completed"><td colspan="7"></td></tr>', 200
        flash("Scadenza segnata come completata.", "success")
        return redirect(url_for("scadenziario"))

    @app.route("/scadenziario/bulk-completa", methods=["POST"])
    def bulk_completa_scadenze():
        """Completa più scadenze in un colpo solo."""
        u = g.utente_corrente
        if not u or not u.ha_permesso("scadenziario.scrivi"):
            flash("Permesso insufficiente.", "danger")
            return redirect(url_for("scadenziario"))
        ids = request.form.getlist("ids")
        if not ids:
            flash("Nessuna scadenza selezionata.", "warning")
            return redirect(url_for("scadenziario"))
        gs = get_scadenziario()
        completate = 0
        for id_sc in ids:
            try:
                gs.completa(id_sc)
                audit("scadenziario.completa", "scadenza", id_sc, dettagli="bulk")
                completate += 1
            except ValueError:
                pass
        if completate:
            sync_pubblica("modifica", "scadenze", "bulk")
            flash(f"{completate} scadenza/e segnata/e come completata/e.", "success")
        return redirect(url_for("scadenziario"))

    @app.route("/api/notifiche/pending")
    def notifiche_pending():
        """Restituisce notifiche urgenti da mostrare via Browser Notification API."""
        if not g.utente_corrente:
            return jsonify([])
        try:
            gs = get_scadenziario()
            alerts = []
            oggi = date.today()
            scadute = [s for s in gs.imminenti(entro_giorni=0) if s.giorni_alla_scadenza is not None and s.giorni_alla_scadenza < 0]
            critiche_oggi = [s for s in gs.imminenti(entro_giorni=1) if s.giorni_alla_scadenza == 0]
            imminenti = [s for s in gs.imminenti(entro_giorni=3) if s.perentorio and (s.giorni_alla_scadenza or 0) > 0]
            if scadute:
                alerts.append({
                    "titolo": f"⚠️ {len(scadute)} scadenza/e SCADUTA/E",
                    "corpo": " • ".join(s.titolo for s in scadute[:3]),
                    "url": "/scadenziario",
                    "delay": 2000,
                })
            if critiche_oggi:
                alerts.append({
                    "titolo": f"🔴 {len(critiche_oggi)} scadenza/e OGGI",
                    "corpo": " • ".join(s.titolo for s in critiche_oggi[:3]),
                    "url": "/scadenziario",
                    "delay": 4000,
                })
            if imminenti:
                alerts.append({
                    "titolo": f"🔔 {len(imminenti)} termine/i perentorio/i imminente/i",
                    "corpo": " • ".join(s.titolo for s in imminenti[:3]),
                    "url": "/scadenziario",
                    "delay": 6000,
                })
            return jsonify(alerts)
        except Exception as e:
            app.logger.exception("Errore notifiche_pending: %s", e)
            return jsonify([])

    @app.route("/api/notifiche/inbox")
    def notifiche_inbox():
        """Centro notifiche in-app: scadenze urgenti + appuntamenti imminenti."""
        if not g.utente_corrente:
            return jsonify([])
        try:
            from datetime import timedelta
            gs = get_scadenziario()
            ag = get_agenda()
            alerts = []
            oggi = date.today()
            domani = oggi + timedelta(days=1)

            # Scadenze scadute
            scadute = [s for s in gs.imminenti(entro_giorni=0)
                       if s.giorni_alla_scadenza is not None and s.giorni_alla_scadenza < 0]
            if scadute:
                alerts.append({
                    "id": f"scad-scadute-{oggi.isoformat()}",
                    "tipo": "danger",
                    "icona": "alarm-fill",
                    "titolo": f"{len(scadute)} scadenza/e SCADUTA/E",
                    "corpo": " • ".join(s.titolo for s in scadute[:3]),
                    "url": "/scadenziario",
                    "ts": oggi.isoformat(),
                    "priorita": 1,
                })

            # Scadenze oggi
            sc_oggi = [s for s in gs.imminenti(entro_giorni=1) if s.giorni_alla_scadenza == 0]
            if sc_oggi:
                alerts.append({
                    "id": f"scad-oggi-{oggi.isoformat()}",
                    "tipo": "danger",
                    "icona": "exclamation-circle-fill",
                    "titolo": f"{len(sc_oggi)} scadenza/e OGGI",
                    "corpo": " • ".join(s.titolo for s in sc_oggi[:3]),
                    "url": "/scadenziario",
                    "ts": oggi.isoformat(),
                    "priorita": 2,
                })

            # Scadenze perentorie imminenti entro 3 giorni
            imminenti = [s for s in gs.imminenti(entro_giorni=3)
                         if s.perentorio and (s.giorni_alla_scadenza or 0) > 0]
            if imminenti:
                alerts.append({
                    "id": f"scad-perent-{oggi.isoformat()}",
                    "tipo": "warning",
                    "icona": "clock-history",
                    "titolo": f"{len(imminenti)} termine/i perentorio/i (entro 3 gg)",
                    "corpo": " • ".join(
                        f"{s.titolo} ({s.giorni_alla_scadenza}gg)" for s in imminenti[:3]
                    ),
                    "url": "/scadenziario",
                    "ts": oggi.isoformat(),
                    "priorita": 3,
                })

            # Appuntamenti oggi
            app_oggi = sorted(
                [a for a in ag.tutti() if a.data_ora_dt.date() == oggi],
                key=lambda a: a.data_ora,
            )
            if app_oggi:
                alerts.append({
                    "id": f"app-oggi-{oggi.isoformat()}",
                    "tipo": "primary",
                    "icona": "calendar-check-fill",
                    "titolo": f"{len(app_oggi)} appuntamento/i oggi",
                    "corpo": " • ".join(
                        f"{a.titolo} {a.data_ora_dt.strftime('%H:%M')}" for a in app_oggi[:3]
                    ),
                    "url": "/agenda",
                    "ts": oggi.isoformat(),
                    "priorita": 4,
                })

            # Appuntamenti domani
            app_domani = sorted(
                [a for a in ag.tutti() if a.data_ora_dt.date() == domani],
                key=lambda a: a.data_ora,
            )
            if app_domani:
                alerts.append({
                    "id": f"app-domani-{domani.isoformat()}",
                    "tipo": "info",
                    "icona": "calendar-event",
                    "titolo": f"{len(app_domani)} appuntamento/i domani",
                    "corpo": " • ".join(
                        f"{a.titolo} {a.data_ora_dt.strftime('%H:%M')}" for a in app_domani[:3]
                    ),
                    "url": "/agenda",
                    "ts": domani.isoformat(),
                    "priorita": 5,
                })

            alerts.sort(key=lambda x: x["priorita"])
            return jsonify(alerts)
        except Exception as e:
            app.logger.exception("Errore notifiche_inbox: %s", e)
            return jsonify([])

    @app.route("/scadenziario/<id_sc>/elimina", methods=["POST"])
    def elimina_scadenza(id_sc):
        gs = get_scadenziario()
        try:
            gs.elimina(id_sc)
            audit("scadenziario.elimina", "scadenza", id_sc)
            flash("Scadenza eliminata.", "success")
            sync_pubblica("elimina", "scadenze", id_sc)
        except ValueError as e:
            flash(str(e), "danger")
        return redirect(url_for("scadenziario"))

    @app.route("/scadenziario/calcola-termine", methods=["POST"])
    def calcola_termine_route():
        """API AJAX per il calcolo dinamico del termine."""
        data = request.get_json() or {}
        try:
            d_inizio = date.fromisoformat(data["data_inizio"])
            giorni = int(data["giorni"])
            tipo = data.get("tipo", "liberi")
            sospensione = data.get("sospensione_feriale", True)
            d_scadenza = calcola_termine(d_inizio, giorni, tipo, sospensione)
            return jsonify({
                "data_scadenza": d_scadenza.isoformat(),
                "lavorativo": è_giorno_lavorativo(d_scadenza),
            })
        except (KeyError, ValueError) as e:
            return jsonify({"errore": str(e)}), 400

    @app.route("/api/scadenziario/imminenti")
    def api_scadenze_imminenti():
        try:
            giorni = int(request.args.get("giorni", 7))
            gs = get_scadenziario()
            sc = gs.imminenti(entro_giorni=giorni)
            return jsonify([s.to_dict() for s in sc])
        except Exception as e:
            app.logger.exception("Errore api_scadenze_imminenti: %s", e)
            return jsonify([])

    @app.route("/api/scadenziario/statistiche")
    def api_scadenziario_statistiche():
        try:
            return jsonify(get_scadenziario().statistiche())
        except Exception as e:
            app.logger.exception("Errore api_scadenziario_statistiche: %s", e)
            return jsonify({"errore": str(e)})

    # ---------------------------------------------------------------- dashboard

    @app.route("/")
    def dashboard():
        agenda = get_agenda()
        oggi = date.today()
        apps_oggi = agenda.per_giorno(oggi)
        apps_settimana = agenda.per_settimana(oggi)
        reminder = agenda.prossimi_reminder(entro_minuti=120)
        stats = agenda.statistiche()
        # Scadenze imminenti per dashboard
        gs = get_scadenziario()
        scadenze_critiche = gs.imminenti(entro_giorni=3)
        scadenze_imminenti = gs.imminenti(entro_giorni=7)
        stats_sc = gs.statistiche()
        stats_fascicoli = get_fascicoli().statistiche()
        stats_clienti = get_clienti().statistiche()
        # #4 — Cartelle condivise per collaboratori
        u_dash = g.utente_corrente
        cartelle_mie = []
        accessi_in_scadenza = []
        if u_dash and not u_dash.ha_permesso("clienti.leggi"):
            gcd = get_condivisioni()
            gc = get_clienti()
            cartelle_mie = [
                (gc.get(id_c), ac)
                for id_c, ac in gcd.cartelle_condivise_con(u_dash.id)
                if gc.get(id_c) and not ac.is_scaduto
            ][:5]
            accessi_in_scadenza = gcd.accessi_in_scadenza(entro_giorni=7)
        # Widget documenti d'identità scaduti (solo admin/avvocati con accesso globale)
        clienti_doc_scaduti = []
        if u_dash and u_dash.ha_permesso("clienti.leggi"):
            try:
                clienti_doc_scaduti = [
                    c for c in get_clienti().tutti()
                    if c.documento.scaduto and c.documento.numero
                ][:10]
            except Exception:
                pass
        return render_template(
            "dashboard.html",
            apps_oggi=apps_oggi,
            apps_settimana=apps_settimana,
            reminder=reminder,
            stats=stats,
            scadenze_critiche=scadenze_critiche,
            scadenze_imminenti=scadenze_imminenti,
            stats_sc=stats_sc,
            stats_fascicoli=stats_fascicoli,
            stats_clienti=stats_clienti,
            cartelle_mie=cartelle_mie,
            accessi_in_scadenza=accessi_in_scadenza,
            clienti_doc_scaduti=clienti_doc_scaduti,
        )

    # ---------------------------------------------------------------- agenda

    @app.route("/agenda")
    def agenda_view():
        agenda = get_agenda()
        vista = request.args.get("vista", "settimana")
        oggi = date.today()

        # navigazione settimana / mese
        offset = int(request.args.get("offset", 0))

        if vista == "giorno":
            giorno = oggi + timedelta(days=offset)
            apps = agenda.per_giorno(giorno)
            return render_template(
                "agenda.html",
                vista=vista,
                apps=apps,
                giorno=giorno,
                offset=offset,
            )

        if vista == "mese":
            # offset in mesi
            anno = oggi.year
            mese = oggi.month + offset
            while mese > 12:
                mese -= 12
                anno += 1
            while mese < 1:
                mese += 12
                anno -= 1
            apps = agenda.per_mese(anno, mese)
            primo = date(anno, mese, 1)
            # padding giorni iniziali per griglia
            pad = primo.weekday()  # lunedì=0
            import calendar
            giorni_mese = calendar.monthrange(anno, mese)[1]
            return render_template(
                "agenda.html",
                vista=vista,
                apps=apps,
                anno=anno,
                mese=mese,
                primo=primo,
                pad=pad,
                giorni_mese=giorni_mese,
                offset=offset,
                nomi_mesi=[
                    "", "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio",
                    "Giugno", "Luglio", "Agosto", "Settembre", "Ottobre",
                    "Novembre", "Dicembre",
                ],
            )

        # default: settimana
        inizio = oggi + timedelta(weeks=offset) - timedelta(days=oggi.weekday())
        fine = inizio + timedelta(days=6)
        apps = agenda.per_settimana(inizio)
        giorni = [inizio + timedelta(days=i) for i in range(7)]
        apps_per_giorno = {g: [a for a in apps if a.data_ora_dt.date() == g] for g in giorni}
        return render_template(
            "agenda.html",
            vista=vista,
            apps=apps,
            apps_per_giorno=apps_per_giorno,
            giorni=giorni,
            inizio=inizio,
            fine=fine,
            offset=offset,
        )

    @app.route("/agenda/nuovo", methods=["GET", "POST"])
    def nuovo_appuntamento():
        if request.method == "POST":
            agenda = get_agenda()
            data = request.form.get("data", "")
            ora = request.form.get("ora", "09:00")
            data_ora = f"{data}T{ora}:00" if data else ""
            id_cliente_post = request.form.get("id_cliente", "")
            from_cliente = request.form.get("from_cliente", "")
            try:
                new_app = agenda.aggiungi(
                    titolo=request.form["titolo"],
                    tipo=TipoAppuntamento(request.form["tipo"]),
                    data_ora=data_ora,
                    durata_minuti=int(request.form.get("durata", 60)),
                    luogo=request.form.get("luogo", ""),
                    cliente=request.form.get("cliente", ""),
                    cf_cliente=request.form.get("cf_cliente", ""),
                    id_cliente=id_cliente_post,
                    procedimento=request.form.get("procedimento", ""),
                    tribunale=request.form.get("tribunale", ""),
                    avvocato=request.form.get("avvocato", ""),
                    note=request.form.get("note", ""),
                    reminder_minuti=int(request.form.get("reminder", 60)),
                )
                flash(f"Appuntamento '{new_app.titolo}' aggiunto.", "success")
                if from_cliente:
                    return redirect(url_for("cartella_cliente", id_cliente=from_cliente))
                return redirect(url_for("dettaglio_appuntamento", id_app=new_app.id))
            except ValueError as e:
                flash(str(e), "danger")

        data_default = request.args.get("data", "")
        id_cliente_get = request.args.get("id_cliente", "")
        from_cliente_get = request.args.get("from_cliente", "")
        cliente_presel = None
        if id_cliente_get:
            cliente_presel = get_clienti().get(id_cliente_get)
        return render_template(
            "form_appuntamento.html",
            app=None,
            tipi=list(TipoAppuntamento),
            data_default=data_default,
            id_cliente=id_cliente_get,
            from_cliente=from_cliente_get,
            cliente_presel=cliente_presel,
        )

    @app.route("/agenda/<id_app>")
    def dettaglio_appuntamento(id_app):
        agenda = get_agenda()
        app = agenda.get(id_app)
        if not app:
            flash("Appuntamento non trovato.", "warning")
            return redirect(url_for("agenda_view"))
        track_recente("appuntamento", id_app, app.titolo,
                      url_for("dettaglio_appuntamento", id_app=id_app), "bi-calendar-event")
        return render_template("dettaglio_appuntamento.html", app=app)

    @app.route("/agenda/<id_app>/modifica", methods=["GET", "POST"])
    def modifica_appuntamento(id_app):
        agenda = get_agenda()
        app = agenda.get(id_app)
        if not app:
            flash("Appuntamento non trovato.", "warning")
            return redirect(url_for("agenda_view"))

        if request.method == "POST":
            data = request.form.get("data", "")
            ora = request.form.get("ora", "09:00")
            campi = {
                "titolo": request.form["titolo"],
                "tipo": TipoAppuntamento(request.form["tipo"]),
                "data_ora": f"{data}T{ora}:00" if data else app.data_ora,
                "durata_minuti": int(request.form.get("durata", app.durata_minuti)),
                "luogo": request.form.get("luogo", ""),
                "cliente": request.form.get("cliente", ""),
                "cf_cliente": request.form.get("cf_cliente", ""),
                "id_cliente": request.form.get("id_cliente", app.id_cliente),
                "procedimento": request.form.get("procedimento", ""),
                "tribunale": request.form.get("tribunale", ""),
                "avvocato": request.form.get("avvocato", ""),
                "note": request.form.get("note", ""),
                "reminder_minuti": int(request.form.get("reminder", app.reminder_minuti)),
            }
            try:
                agenda.modifica(id_app, **campi)
                flash("Appuntamento aggiornato.", "success")
                sync_pubblica("modifica", "agenda", id_app)
                return redirect(url_for("dettaglio_appuntamento", id_app=id_app))
            except (ValueError, KeyError) as e:
                flash(str(e), "danger")

        return render_template(
            "form_appuntamento.html",
            app=app,
            tipi=list(TipoAppuntamento),
        )

    @app.route("/agenda/<id_app>/stato", methods=["POST"])
    def cambia_stato(id_app):
        agenda = get_agenda()
        nuovo = request.form.get("stato")
        try:
            agenda.cambia_stato(id_app, StatoAppuntamento(nuovo))
            flash("Stato aggiornato.", "success")
        except (KeyError, ValueError) as e:
            flash(str(e), "danger")
        return redirect(url_for("dettaglio_appuntamento", id_app=id_app))

    @app.route("/agenda/<id_app>/elimina", methods=["POST"])
    def elimina_appuntamento(id_app):
        agenda = get_agenda()
        try:
            agenda.elimina(id_app)
            flash("Appuntamento eliminato.", "success")
            sync_pubblica("elimina", "agenda", id_app)
        except KeyError as e:
            flash(str(e), "danger")
        return redirect(url_for("agenda_view"))

    # ---------------------------------------------------------------- Importa calendario

    @app.route("/agenda/importa", methods=["GET", "POST"])
    def importa_calendario():
        """
        Importazione eventi da file .ics (Google Calendar, Outlook, Apple, ecc.).

        Flusso in due fasi:
          GET  /agenda/importa              → form selezione sorgente + upload
          POST /agenda/importa fase=upload  → parse file, mostra preview
          POST /agenda/importa fase=importa → importa eventi selezionati
        """
        import json as _json
        from pct.ical_import import parse_ics, evento_to_dict, dict_to_evento
        from pct.agenda import TipoAppuntamento, StatoAppuntamento

        fase = request.form.get("fase", "")

        # ── Fase 1: upload + parsing
        if request.method == "POST" and fase == "upload":
            sorgente = request.form.get("sorgente", "generico")
            file = request.files.get("file_ics")
            if not file or not file.filename:
                flash("Nessun file selezionato.", "warning")
                return render_template("importa_calendario.html",
                                       fase="upload_form", sorgente=sorgente,
                                       oggi=date.today())
            # Leggi contenuto
            raw = file.read()
            # Rileva encoding (UTF-16 usato da alcune versioni Outlook/Apple)
            try:
                testo = raw.decode("utf-8-sig")
            except UnicodeDecodeError:
                try:
                    testo = raw.decode("utf-16")
                except UnicodeDecodeError:
                    testo = raw.decode("latin-1", errors="replace")

            try:
                eventi = parse_ics(testo)
            except Exception as e:
                app.logger.exception("Errore parsing ICS: %s", e)
                flash(f"Errore nell'analisi del file: {e}", "danger")
                return render_template("importa_calendario.html",
                                       fase="upload_form", sorgente=sorgente,
                                       oggi=date.today())

            if not eventi:
                flash("Il file non contiene eventi validi.", "warning")
                return render_template("importa_calendario.html",
                                       fase="upload_form", sorgente=sorgente,
                                       oggi=date.today())

            eventi_dict = [evento_to_dict(e) for e in eventi]
            return render_template(
                "importa_calendario.html",
                fase="preview",
                sorgente=sorgente,
                eventi=eventi,
                eventi_json=_json.dumps(eventi_dict, ensure_ascii=False),
                oggi=date.today(),
            )

        # ── Fase 2: importa eventi selezionati
        if request.method == "POST" and fase == "importa":
            import json as _json
            sorgente = request.form.get("sorgente", "generico")
            # Gli indici degli eventi selezionati
            selezionati_str = request.form.getlist("sel")
            eventi_json_str = request.form.get("eventi_json", "[]")

            try:
                tutti_eventi_dict = _json.loads(eventi_json_str)
            except Exception:
                flash("Errore nei dati del form. Riprova.", "danger")
                return redirect(url_for("importa_calendario"))

            selezionati_idx = set()
            for s in selezionati_str:
                try:
                    selezionati_idx.add(int(s))
                except ValueError:
                    pass

            eventi_da_importare = [
                dict_to_evento(tutti_eventi_dict[i])
                for i in sorted(selezionati_idx)
                if 0 <= i < len(tutti_eventi_dict)
            ]

            if not eventi_da_importare:
                flash("Nessun evento selezionato.", "warning")
                return redirect(url_for("importa_calendario"))

            agenda = get_agenda()
            importati   = 0
            saltati     = 0
            conflitti   = 0
            titoli_err: list = []

            for ev in eventi_da_importare:
                # Gli eventi tutto-giorno diventano appuntamenti ALTRO alle 09:00
                if ev.tutto_giorno:
                    data_ora_str = f"{ev.data_ora}T09:00:00"
                    durata = min(ev.durata_minuti, 1440)  # max 1 giorno
                else:
                    data_ora_str = ev.data_ora
                    durata = ev.durata_minuti

                # Mappa stato iCal → stato HACS
                if ev.stato_ical == "CANCELLED":
                    stato = StatoAppuntamento.ANNULLATO
                elif ev.stato_ical == "TENTATIVE":
                    stato = StatoAppuntamento.PROGRAMMATO
                else:
                    stato = StatoAppuntamento.PROGRAMMATO

                # Note: aggiungi info sorgente
                note_parts = []
                if ev.descrizione:
                    note_parts.append(ev.descrizione)
                if ev.organizzatore:
                    note_parts.append(f"Organizzatore: {ev.organizzatore}")
                if ev.rrule:
                    note_parts.append(f"[Evento ricorrente — importata solo la prima occorrenza]")
                note_parts.append(f"Importato da: {sorgente.capitalize()}")
                note = "\n".join(note_parts)

                try:
                    agenda.aggiungi(
                        titolo=ev.titolo,
                        tipo=TipoAppuntamento.ALTRO,
                        data_ora=data_ora_str,
                        durata_minuti=max(durata, 1),
                        luogo=ev.luogo,
                        stato=stato,
                        note=note,
                        reminder_minuti=60,
                    )
                    importati += 1
                except ValueError as e:
                    # Conflitto di orario
                    conflitti += 1
                    titoli_err.append(f"{ev.titolo} ({e})")
                except Exception as e:
                    saltati += 1
                    app.logger.warning("Import evento '%s': %s", ev.titolo, e)

            msg_parts = [f"{importati} eventi importati con successo."]
            if conflitti:
                msg_parts.append(f"{conflitti} con conflitto di orario (saltati).")
            if saltati:
                msg_parts.append(f"{saltati} non importati per errore.")
            flash(" ".join(msg_parts), "success" if importati else "warning")

            if titoli_err:
                flash("Conflitti: " + "; ".join(titoli_err[:5]), "warning")

            return redirect(url_for("agenda_view"))

        # ── GET: mostra form iniziale
        return render_template("importa_calendario.html",
                               fase="upload_form",
                               sorgente="generico",
                               oggi=date.today())

    # ---------------------------------------------------------------- API JSON

    @app.route("/api/agenda/<id_app>/sposta", methods=["POST"])
    def api_sposta_appuntamento(id_app):
        """Sposta un appuntamento in una nuova data/ora (drag-and-drop)."""
        if not g.utente_corrente or not g.utente_corrente.ha_permesso("agenda.scrivi"):
            return jsonify({"errore": "Non autorizzato"}), 403
        ag = get_agenda()
        appt = ag.get(id_app)
        if not appt:
            return jsonify({"errore": "Appuntamento non trovato"}), 404
        payload = request.get_json(silent=True) or {}
        nuova_data = payload.get("data")          # "YYYY-MM-DD"
        nuova_data_ora = payload.get("data_ora")  # "YYYY-MM-DDTHH:MM:SS"
        if nuova_data and not nuova_data_ora:
            ora_orig = appt.data_ora_dt.strftime("%H:%M:%S")
            nuova_data_ora = f"{nuova_data}T{ora_orig}"
        if not nuova_data_ora:
            return jsonify({"errore": "Parametro 'data' o 'data_ora' richiesto"}), 400
        try:
            appt = ag.modifica(id_app, data_ora=nuova_data_ora)
            audit("agenda.sposta", "appuntamento", id_app,
                  dettagli=f"→ {nuova_data_ora}")
            return jsonify({"ok": True, "data_ora": appt.data_ora})
        except (ValueError, KeyError) as e:
            return jsonify({"errore": str(e)}), 409

    @app.route("/api/agenda")
    def api_agenda():
        try:
            agenda = get_agenda()
            da_str = request.args.get("da")
            a_str = request.args.get("a")
            da = date.fromisoformat(da_str) if da_str else None
            a = date.fromisoformat(a_str) if a_str else None
            apps = agenda.cerca(da=da, a=a)
            return jsonify([a.to_dict() for a in apps])
        except Exception as e:
            app.logger.exception("Errore api_agenda: %s", e)
            return jsonify([])

    @app.route("/api/agenda/<id_app>")
    def api_appuntamento(id_app):
        try:
            agenda = get_agenda()
            appt = agenda.get(id_app)
            if not appt:
                return jsonify({"errore": "Non trovato"}), 404
            return jsonify(appt.to_dict())
        except Exception as e:
            app.logger.exception("Errore api_appuntamento: %s", e)
            return jsonify({"errore": str(e)})

    @app.route("/api/reminder")
    def api_reminder():
        try:
            agenda = get_agenda()
            entro = int(request.args.get("entro", 60))
            apps = agenda.prossimi_reminder(entro_minuti=entro)
            return jsonify([a.to_dict() for a in apps])
        except Exception as e:
            app.logger.exception("Errore api_reminder: %s", e)
            return jsonify([])

    @app.route("/api/statistiche")
    def api_statistiche():
        try:
            return jsonify(get_agenda().statistiche())
        except Exception as e:
            app.logger.exception("Errore api_statistiche: %s", e)
            return jsonify({"errore": str(e)})

    # ---------------------------------------------------------------- tariffario DM 55/2014

    @app.route("/tariffario", methods=["GET", "POST"])
    def tariffario():
        from pct.tariffario import (calcola_compenso, tutte_le_materie,
                                    tutti_i_gradi, tutte_le_fasi,
                                    Materia, Grado, Fase)
        risultato = None
        materia_sel = request.form.get("materia", "")
        grado_sel   = request.form.get("grado", "")
        valore_str  = request.form.get("valore", "0").replace(",", ".").strip()
        fasi_sel    = request.form.getlist("fasi")
        bonus_tel   = request.form.get("bonus_telematico") == "1"
        spese_gen   = request.form.get("spese_generali", "1") == "1"

        if request.method == "POST":
            try:
                materia = Materia(materia_sel)
                grado   = Grado(grado_sel)
                valore  = float(valore_str) if valore_str else 0.0
                fasi    = [Fase(f) for f in fasi_sel if f]
                if not fasi:
                    fasi = list(Fase)
                risultato = calcola_compenso(materia, grado, valore, fasi,
                                             bonus_telematico=bonus_tel,
                                             includi_spese_generali=spese_gen)
            except (ValueError, KeyError) as e:
                flash(str(e), "danger")

        return render_template(
            "tariffario.html",
            materie=tutte_le_materie(),
            gradi=tutti_i_gradi(),
            fasi=tutte_le_fasi(),
            risultato=risultato,
            materia_sel=materia_sel,
            grado_sel=grado_sel,
            valore_str=valore_str,
            fasi_sel=fasi_sel,
            bonus_tel=bonus_tel,
            spese_gen=spese_gen,
            oggi=date.today(),
        )

    # ---------------------------------------------------------------- PolisWeb — Consultazione e importazione fascicoli

    def _polis_auth_mode() -> str:
        """
        Restituisce la modalità di autenticazione PST:
          'reale'  — certificato P12/PEM configurato, SOAP mTLS disponibile
          'pkcs11' — token PKCS#11 locale, autenticazione gestita dal dispositivo
          'demo'   — nessun certificato, modalità demo offline
        """
        # Controllo variabili d'ambiente (P12 / PEM)
        if os.getenv("PCT_FIRMA_P12"):
            return "reale"
        if os.getenv("PCT_FIRMA_CERT") and os.getenv("PCT_FIRMA_KEY"):
            return "reale"
        # Controllo config studio (impostazioni UI)
        try:
            cfg = get_config_studio().config.firma
            fmt = cfg.formato_attivo
            if fmt == "pkcs11":
                # Token USB: la chiave privata non è esportabile e non è accessibile
                # dal container Linux su Windows → autenticazione PST solo via browser
                return "pkcs11"
            if fmt in ("p12", "pem"):
                return "reale"
        except Exception:
            pass
        return "demo"

    def _polis_demo_mode() -> bool:
        """True se non c'è un certificato P12/PEM per il SOAP mTLS (include modalità pkcs11)."""
        return _polis_auth_mode() != "reale"

    def _local_signer_tools_dir() -> Path:
        return Path(__file__).parent.parent / "tools"

    def _local_signer_windows_exe_path() -> Path:
        return _local_signer_tools_dir() / "dist" / "SetupLocalSigner.exe"

    def _local_signer_uffici_path() -> Path:
        return Path(__file__).parent.parent / "pct" / "data" / "uffici_ministero.json"

    def _local_signer_allowed_origins(base_url: str) -> str:
        origini = {base_url.rstrip("/")}
        configured = os.getenv("PCT_BASE_URL", "").rstrip("/")
        if configured:
            origini.add(configured)
        origini.add("https://studio-legale-pct-production.up.railway.app")
        return ",".join(sorted(o for o in origini if o))

    def _render_local_signer_windows_ps1(base_url: str) -> str:
        allowed_origins = _local_signer_allowed_origins(base_url)
        return f"""# HACS Local Signer - Installazione automatica Windows
# Eseguire in PowerShell come utente normale (non richiede amministratore)

$ErrorActionPreference = 'Stop'
$dir    = "$env:APPDATA\\HACS\\LocalSigner"
$venv   = "$dir\\.venv"
$py     = "$dir\\local_signer.py"
$dataDir = "$dir\\data"
$uffici = "$dataDir\\uffici_ministero.json"
$starterCmd = "$dir\\\\start_local_signer.cmd"
$starterVbs = "$dir\\\\start_local_signer.vbs"
$pyExe  = "$venv\\\\Scripts\\\\python.exe"
$pywExe = "$venv\\\\Scripts\\\\pythonw.exe"
$allowedOrigins = "{allowed_origins}"

Write-Host "HACS Local Signer - Installazione..." -ForegroundColor Cyan

New-Item -ItemType Directory -Force -Path $dir | Out-Null
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null

Write-Host "  Scarico local_signer.py..."
Invoke-WebRequest "{base_url}/polisWeb/local-signer/download" -OutFile $py -UseBasicParsing
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
& $pyExe -m pip install --quiet python-pkcs11 asn1crypto cryptography

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

powershell -NoProfile -Command "try {{ $r = Invoke-RestMethod 'http://127.0.0.1:27272/ping' -UseBasicParsing -TimeoutSec 2; if ($r.ok) {{ exit 0 }} }} catch {{}}; exit 1" >nul 2>&1
if not errorlevel 1 goto :online

powershell -NoProfile -Command "$target = [regex]::Escape($env:TARGET); Get-CimInstance Win32_Process | Where-Object {{ $_.Name -in @('python.exe','pythonw.exe') -and $_.CommandLine -and $_.CommandLine -match $target }} | ForEach-Object {{ try {{ Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop }} catch {{}} }}" >nul 2>&1

if exist "%PYW%" if exist "%PY%" (
    start "" "%PYW%" "%PY%"
) else (
    exit /b 1
)

:online
if /I "%~1"=="--background" exit /b 0
timeout /t 2 >nul
start "" "http://127.0.0.1:27272/diagnosi"
exit /b 0
'@
$cmd = $cmd.Replace('__ALLOWED_ORIGINS__', $allowedOrigins)
Set-Content -Path $starterCmd -Value $cmd -Encoding ASCII
$vbs = @"
Set shell = CreateObject("WScript.Shell")
shell.Run Chr(34) & "$starterCmd" & Chr(34) & " --background", 0, False
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
    Write-Host "Installazione completata!" -ForegroundColor Green
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
        return f"""#!/bin/bash
set -euo pipefail

BASE_URL="{base_url}"
ALLOWED_ORIGINS="{allowed_origins}"
DIR="$HOME/Library/Application Support/HACS/LocalSigner"
DATA_DIR="$DIR/data"
VENV="$DIR/.venv"
PY="$VENV/bin/python3"
PLIST="$HOME/Library/LaunchAgents/it.hacs.local-signer.plist"

echo "HACS Local Signer - Installazione macOS"

mkdir -p "$DIR" "$DATA_DIR" "$(dirname "$PLIST")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 non trovato. Installarlo prima da https://python.org"
  read -r -p "Premi Invio per uscire..." _
  exit 1
fi

curl -fsSL "$BASE_URL/polisWeb/local-signer/download" -o "$DIR/local_signer.py"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/uffici" -o "$DATA_DIR/uffici_ministero.json"
python3 -m venv "$VENV"
"$PY" -m pip install --quiet --upgrade pip
"$PY" -m pip install --quiet python-pkcs11 asn1crypto cryptography

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
echo "Installazione completata."
echo "Local Signer attivo su http://127.0.0.1:27272"
echo "Tornare su HACS e cliccare Riverifica."
read -r -p "Premi Invio per chiudere..." _
"""

    def _render_local_signer_linux_sh(base_url: str) -> str:
        allowed_origins = _local_signer_allowed_origins(base_url)
        return f"""#!/usr/bin/env bash
set -euo pipefail

BASE_URL="{base_url}"
ALLOWED_ORIGINS="{allowed_origins}"
DIR="${{XDG_DATA_HOME:-$HOME/.local/share}}/hacs/local-signer"
DATA_DIR="$DIR/data"
VENV="$DIR/.venv"
PY="$VENV/bin/python"
SERVICE_DIR="${{XDG_CONFIG_HOME:-$HOME/.config}}/systemd/user"
SERVICE="$SERVICE_DIR/hacs-local-signer.service"

echo "HACS Local Signer - Installazione Linux"

mkdir -p "$DIR" "$DATA_DIR" "$SERVICE_DIR"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 non trovato. Installarlo prima con il gestore pacchetti della distribuzione."
  read -r -p "Premi Invio per uscire..." _
  exit 1
fi

curl -fsSL "$BASE_URL/polisWeb/local-signer/download" -o "$DIR/local_signer.py"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/uffici" -o "$DATA_DIR/uffici_ministero.json"
python3 -m venv "$VENV"
"$PY" -m pip install --quiet --upgrade pip
"$PY" -m pip install --quiet python-pkcs11 asn1crypto cryptography

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
echo "Installazione completata."
echo "Local Signer attivo su http://127.0.0.1:27272"
echo "Tornare su HACS e cliccare Riverifica."
read -r -p "Premi Invio per chiudere..." _
"""

    @app.route("/polisWeb/local-signer/download")
    def polis_local_signer_download():
        """Serve il file local_signer.py per il download diretto dal browser."""
        import traceback as _tb
        try:
            ls_path = Path(__file__).parent.parent / "tools" / "local_signer.py"
            if not ls_path.exists():
                return "File non trovato", 404
            return send_file(
                ls_path,
                as_attachment=True,
                download_name="local_signer.py",
                mimetype="text/x-python",
            )
        except Exception as e:
            return str(e), 500

    @app.route("/polisWeb/local-signer/download/uffici")
    def polis_local_signer_download_uffici():
        """Serve il registro uffici PST per l'uso standalone del Local Signer."""
        try:
            uffici_path = _local_signer_uffici_path()
            if not uffici_path.exists():
                return "Registro uffici non trovato", 404
            return send_file(
                uffici_path,
                as_attachment=True,
                download_name="uffici_ministero.json",
                mimetype="application/json",
            )
        except Exception as e:
            app.logger.exception("Errore download registro uffici Local Signer: %s", e)
            return str(e), 500

    @app.route("/polisWeb/local-signer/setup/windows-exe")
    def polis_local_signer_setup_windows_exe():
        """Serve l'installer Windows .exe quando presente nel repository."""
        try:
            exe_path = _local_signer_windows_exe_path()
            if not exe_path.exists():
                return (
                    "Installer Windows .exe non ancora generato. "
                    "Usare temporaneamente l'installer PowerShell.",
                    404,
                )
            return send_file(
                exe_path,
                as_attachment=True,
                download_name="SetupLocalSigner.exe",
                mimetype="application/octet-stream",
            )
        except Exception as e:
            return str(e), 500

    @app.route("/polisWeb/local-signer/setup/windows")
    def polis_local_signer_setup_windows():
        """Serve il miglior installer Windows disponibile: .exe, altrimenti PowerShell."""
        exe_path = _local_signer_windows_exe_path()
        base_url = _get_base_url()
        if exe_path.exists():
            return send_file(
                exe_path,
                as_attachment=True,
                download_name="SetupLocalSigner.exe",
                mimetype="application/octet-stream",
            )
        return Response(
            _render_local_signer_windows_ps1(base_url),
            mimetype="text/plain; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="installa_local_signer.ps1"'},
        )

    @app.route("/polisWeb/local-signer/installa-windows")
    def polis_local_signer_installa():
        """
        Genera e serve lo script PowerShell legacy/compatibile per Windows.
        """
        import traceback as _tb
        try:
            return Response(
                _render_local_signer_windows_ps1(_get_base_url()),
                mimetype="text/plain; charset=utf-8",
                headers={
                    "Content-Disposition": 'attachment; filename="installa_local_signer.ps1"'
                },
            )
        except Exception as e:
            app.logger.exception("Errore generazione script installer: %s", e)
            return str(e), 500

    @app.route("/polisWeb/local-signer/setup/macos")
    def polis_local_signer_setup_macos():
        """Serve l'installer macOS (.command) del Local Signer."""
        try:
            return Response(
                _render_local_signer_macos_command(_get_base_url()),
                mimetype="text/plain; charset=utf-8",
                headers={"Content-Disposition": 'attachment; filename="InstallaLocalSigner.command"'},
            )
        except Exception as e:
            app.logger.exception("Errore generazione installer macOS: %s", e)
            return str(e), 500

    @app.route("/polisWeb/local-signer/setup/linux")
    def polis_local_signer_setup_linux():
        """Serve l'installer Linux (.sh) del Local Signer."""
        try:
            return Response(
                _render_local_signer_linux_sh(_get_base_url()),
                mimetype="text/plain; charset=utf-8",
                headers={"Content-Disposition": 'attachment; filename="installa_local_signer.sh"'},
            )
        except Exception as e:
            app.logger.exception("Errore generazione installer Linux: %s", e)
            return str(e), 500

    @app.route("/polisWeb", methods=["GET"])
    def polisWeb_home():
        import traceback as _tb
        try:
            auth_mode = _polis_auth_mode()
            demo_mode = auth_mode != "reale"
            pkcs11_mode = auth_mode == "pkcs11"
            id_fasc = request.args.get("id_fasc", "")
            fascicolo_ctx = get_fascicoli().get(id_fasc) if id_fasc else None
            return render_template("polisWeb.html", demo_mode=demo_mode,
                                   pkcs11_mode=pkcs11_mode,
                                   fascicolo=fascicolo_ctx, id_fasc=id_fasc)
        except Exception as e:
            tb = "".join(_tb.format_exception(type(e), e, e.__traceback__))
            app.logger.error("ERRORE polisWeb_home:\n%s", tb)
            return f"<pre style='color:red;padding:2em'><b>Errore PolisWeb:</b>\n{tb}</pre>", 500

    @app.route("/polisWeb/ricerca", methods=["POST"])
    def polisWeb_ricerca():
        f = request.form
        tribunale  = f.get("tribunale", "").strip()
        auth_mode  = _polis_auth_mode()
        demo_mode  = f.get("demo_mode") == "1" or auth_mode != "reale"
        pkcs11_mode = auth_mode == "pkcs11"

        if not tribunale:
            flash("Seleziona un tribunale.", "danger")
            return redirect(url_for("polisWeb_home"))

        id_fasc       = f.get("id_fasc", "").strip()
        fascicolo_ctx = get_fascicoli().get(id_fasc) if id_fasc else None
        try:
            numero_rg  = f.get("numero_rg", "").strip() or None
            anno_rg    = int(f.get("anno_rg") or 0) or None
            nome_parte = f.get("nome_parte", "").strip() or None
            cf_parte   = f.get("cf_parte", "").strip() or None
        except (ValueError, TypeError) as e:
            flash(f"Parametri non validi: {e}", "danger")
            return redirect(url_for("polisWeb_home"))

        try:
            from pct.polisWeb import crea_client
            client = crea_client(demo=demo_mode)
            fascicoli = client.ricerca_fascicoli(
                tribunale=tribunale,
                numero_rg=numero_rg,
                anno_rg=anno_rg,
                nome_parte=nome_parte,
                codice_fiscale_parte=cf_parte,
            )
        except Exception as e:
            app.logger.exception("Errore polisWeb_ricerca: %s", e)
            flash(f"Errore ricerca PST: {e}", "danger")
            return redirect(url_for("polisWeb_home"))

        try:
            from pct.uffici_giudiziari import get_gestore as _get_uff
            _cache = os.getenv("PCT_UFFICI_DB", "/data/uffici/uffici_giudiziari.json")
            _uff = next((u for u in _get_uff(_cache).carica() if u.get("codice") == tribunale), None)
            tribunale_sel_nome = _uff["nome"] if _uff else tribunale
        except Exception as e:
            app.logger.warning("Errore risoluzione nome ufficio '%s': %s", tribunale, e)
            tribunale_sel_nome = tribunale

        return render_template(
            "polisWeb.html",
            fascicoli=fascicoli,
            tribunale_sel=tribunale,
            tribunale_sel_nome=tribunale_sel_nome,
            numero_rg=numero_rg or "",
            anno_rg=anno_rg or "",
            nome_parte=nome_parte or "",
            cf_parte=cf_parte or "",
            demo_mode=demo_mode,
            pkcs11_mode=pkcs11_mode,
            fascicolo=fascicolo_ctx,
            id_fasc=id_fasc,
        )

    @app.route("/polisWeb/documenti", methods=["GET"])
    def polisWeb_documenti():
        codice_ufficio = request.args.get("codice_ufficio", "")
        numero_rg      = request.args.get("numero_rg", "")
        auth_mode      = _polis_auth_mode()
        demo_mode      = auth_mode != "reale"
        try:
            anno_rg = int(request.args.get("anno_rg", 0) or 0)
        except (ValueError, TypeError):
            anno_rg = 0
        try:
            from pct.polisWeb import crea_client
            client = crea_client(demo=demo_mode)
            documenti = client.consulta_documenti(codice_ufficio, numero_rg, anno_rg)
        except Exception as e:
            app.logger.exception("Errore polisWeb_documenti: %s", e)
            flash(str(e), "danger")
            return redirect(url_for("polisWeb_home"))

        # Risolvi nome ufficio dal codice
        nome_ufficio = codice_ufficio
        try:
            from pct.uffici_giudiziari import get_gestore as _get_uff
            _uff = next(
                (u for u in _get_uff(
                    os.getenv("PCT_UFFICI_DB", "/data/uffici/uffici_giudiziari.json")
                ).carica() if u.get("codice") == codice_ufficio),
                None,
            )
            nome_ufficio = _uff["nome"] if _uff else codice_ufficio
        except Exception:
            pass

        # Raggruppa per id_deposito → lista ordinata per data (più recenti prima)
        from collections import OrderedDict
        _gruppi: dict = OrderedDict()
        for doc in sorted(documenti, key=lambda d: d.data_deposito or "", reverse=True):
            chiave = doc.id_deposito or f"__{doc.data_deposito}__{doc.mittente}"
            if chiave not in _gruppi:
                _gruppi[chiave] = {
                    "id_deposito": doc.id_deposito or chiave,
                    "tipo_atto": doc.tipo_atto or doc.tipo.replace("_", " ").title(),
                    "data_deposito": doc.data_deposito,
                    "mittente": doc.mittente,
                    "documenti": [],
                }
            _gruppi[chiave]["documenti"].append(doc)
        depositi = list(_gruppi.values())

        return render_template(
            "polisWeb_documenti.html",
            documenti=documenti,
            depositi=depositi,
            numero_rg=numero_rg,
            anno_rg=anno_rg,
            codice_ufficio=codice_ufficio,
            nome_ufficio=nome_ufficio,
            demo_mode=demo_mode,
        )

    @app.route("/polisWeb/importa", methods=["POST"])
    def polisWeb_importa():
        """Importa una pratica PolisWeb come nuovo fascicolo nel gestionale."""
        import json as _json
        from pct.polisWeb import crea_client, FascicoloPolisWeb, DocumentoPolisWeb, _parse_data
        from pct.uffici_giudiziari import risolvi_ufficio
        f = request.form
        demo_mode = f.get("demo_mode") == "1" or _polis_demo_mode()
        u = g.utente_corrente
        try:
            def _as_bool(value):
                if isinstance(value, bool):
                    return value
                if isinstance(value, (int, float)):
                    return bool(value)
                text = str(value or "").strip().lower()
                if text in {"1", "true", "yes", "si", "s", "ok"}:
                    return True
                if text in {"0", "false", "no", "n", "", "none", "null"}:
                    return False
                return bool(value)

            numero_rg_imp = f.get("numero_rg", "")
            anno_rg_imp   = int(f.get("anno_rg", 0) or 0)
            nome_ufficio_imp = f.get("nome_ufficio", "")
            codice_ufficio_imp = f.get("codice_ufficio", "")
            documenti_prefetch_error = f.get("documenti_prefetch_error", "").strip()
            if not nome_ufficio_imp and codice_ufficio_imp:
                ufficio = risolvi_ufficio(codice_ufficio_imp)
                if isinstance(ufficio, dict):
                    nome_ufficio_imp = str(ufficio.get("nome") or "").strip()

            fascicolo_pw = FascicoloPolisWeb(
                numero_rg=numero_rg_imp,
                anno_rg=anno_rg_imp,
                ruolo=f.get("ruolo", "CIVILE_COGNIZIONE"),
                stato=f.get("stato", "PENDENTE"),
                oggetto=f.get("oggetto", ""),
                sezione=f.get("sezione", ""),
                giudice=f.get("giudice", ""),
                data_iscrizione=_parse_data(f.get("data_iscrizione", "")),
                data_udienza=_parse_data(f.get("data_udienza", "")),
                parti=_json.loads(f.get("parti_json", "[]") or "[]"),
                parti_dettaglio=_json.loads(f.get("parti_dettaglio_json", "[]") or "[]"),
                codice_ufficio=codice_ufficio_imp,
                nome_ufficio=nome_ufficio_imp,
            )
            documenti_json_raw = f.get("documenti_json", "").strip()
            documenti_pw = None
            if documenti_json_raw:
                documenti_pw = []
                for row in _json.loads(documenti_json_raw or "[]"):
                    row = dict(row or {})
                    documenti_pw.append(
                        DocumentoPolisWeb(
                            id_documento=str(row.get("id_documento") or "").strip(),
                            nome=str(row.get("nome") or "").strip(),
                            tipo=str(row.get("tipo") or "").strip(),
                            data_deposito=_parse_data(str(row.get("data_deposito") or "").strip()),
                            mittente=str(row.get("mittente") or "").strip(),
                            dimensione_bytes=int(row.get("dimensione_bytes") or 0),
                            disponibile=_as_bool(row.get("disponibile", True)),
                            id_deposito=str(row.get("id_deposito") or "").strip(),
                            tipo_atto=str(row.get("tipo_atto") or "").strip(),
                        )
                    )
            client = crea_client(demo=demo_mode)
            gf = get_fascicoli()
            gc = get_clienti()
            gs = get_soggetti()

            fc_esistente = None
            id_fasc_target = f.get("id_fasc", "").strip()
            if id_fasc_target:
                fascicolo_target = gf.get(id_fasc_target)
                if (
                    fascicolo_target
                    and fascicolo_target.numero_rg == numero_rg_imp
                    and fascicolo_target.anno_rg == anno_rg_imp
                    and (not fascicolo_target.tribunale or fascicolo_target.tribunale == nome_ufficio_imp)
                ):
                    fc_esistente = fascicolo_target

            if fc_esistente is None:
                for fascicolo_esistente in gf.tutti():
                    if (
                        fascicolo_esistente.numero_rg == numero_rg_imp
                        and fascicolo_esistente.anno_rg == anno_rg_imp
                        and fascicolo_esistente.tribunale == nome_ufficio_imp
                    ):
                        fc_esistente = fascicolo_esistente
                        break

            if fc_esistente:
                risultato = client.sincronizza_fascicolo_esistente(
                    fascicolo_pw=fascicolo_pw,
                    fascicolo_locale=fc_esistente,
                    gestione_fascicoli=gf,
                    gestione_clienti=gc,
                    avvocato_referente=u.username if u else "",
                    gestione_soggetti=gs,
                    documenti_pw=documenti_pw,
                )
            else:
                risultato = client.importa_fascicolo(
                    fascicolo_pw=fascicolo_pw,
                    gestione_fascicoli=gf,
                    gestione_clienti=gc,
                    avvocato_referente=u.username if u else "",
                    gestione_soggetti=gs,
                    documenti_pw=documenti_pw,
                )
            if risultato.successo:
                for avviso in risultato.avvisi:
                    # I messaggi di creazione automatica sono informativi, non warning bloccanti
                    livello = "info" if avviso.startswith(("Nuovo soggetto", "Nuova parte")) else "warning"
                    flash(avviso, livello)
                if documenti_prefetch_error and not (risultato.depositi_importati or risultato.documenti_importati):
                    flash(documenti_prefetch_error, "warning")
                flash(risultato.messaggio, "success")
                audit(
                    "polisWeb.sincronizza" if fc_esistente else "polisWeb.importa",
                    "fascicolo",
                    risultato.id_fascicolo_locale,
                    dettagli=f"RG {fascicolo_pw.numero_rg}/{fascicolo_pw.anno_rg}",
                )
                return redirect(url_for("dettaglio_fascicolo",
                                        id_fasc=risultato.id_fascicolo_locale))
            flash(risultato.messaggio, "danger")
        except Exception as e:
            flash(str(e), "danger")
        return redirect(url_for("polisWeb_home"))

    # ---------------------------------------------------------------- PDP Penale — Portale Deposito Atti

    @app.route("/pdp", methods=["GET"])
    def pdp_home():
        demo_mode = _polis_demo_mode()
        id_fasc = request.args.get("id_fasc", "")
        fascicolo_ctx = get_fascicoli().get(id_fasc) if id_fasc else None
        return render_template("pdp.html", demo_mode=demo_mode, oggi=date.today(),
                               fascicolo=fascicolo_ctx, id_fasc=id_fasc)

    @app.route("/pdp/ricerca", methods=["POST"])
    def pdp_ricerca():
        from pct.pdp import crea_client_pdp
        f          = request.form
        ufficio    = f.get("ufficio", "").strip()
        demo_mode  = f.get("demo_mode") == "1" or _polis_demo_mode()

        if not ufficio:
            flash("Seleziona un ufficio giudiziario.", "warning")
            return redirect(url_for("pdp_home"))

        id_fasc       = f.get("id_fasc", "").strip()
        fascicolo_ctx = get_fascicoli().get(id_fasc) if id_fasc else None
        numero_rg     = f.get("numero_rg", "").strip() or None
        anno_rg_str   = f.get("anno_rg", "").strip()
        anno_rg       = int(anno_rg_str) if anno_rg_str.isdigit() else None
        nome_imputato = f.get("nome_imputato", "").strip() or None
        tipo_registro = f.get("tipo_registro", "").strip() or None

        try:
            client = crea_client_pdp(demo=demo_mode)
            fascicoli = client.ricerca_fascicoli(
                ufficio=ufficio,
                numero_rg=numero_rg,
                anno_rg=anno_rg,
                nome_imputato=nome_imputato,
                tipo_registro=tipo_registro,
            )
            # Risolvi nome ufficio dal codice
            try:
                from pct.uffici_giudiziari import get_gestore as _get_uff
                _uff = next(
                    (u for u in _get_uff(
                        os.getenv("PCT_UFFICI_DB", "/data/uffici/uffici_giudiziari.json")
                    ).carica() if u.get("codice") == ufficio),
                    None,
                )
                ufficio_sel_nome = _uff["nome"] if _uff else ufficio
            except Exception:
                ufficio_sel_nome = ufficio
            return render_template(
                "pdp.html",
                demo_mode=demo_mode,
                fascicoli=fascicoli,
                ufficio_sel=ufficio,
                ufficio_sel_nome=ufficio_sel_nome,
                numero_rg=numero_rg or "",
                anno_rg=anno_rg or "",
                nome_imputato=nome_imputato or "",
                tipo_registro=tipo_registro or "",
                fascicolo=fascicolo_ctx,
                id_fasc=id_fasc,
                oggi=date.today(),
            )
        except Exception as e:
            app.logger.exception("Errore pdp_ricerca: %s", e)
            flash(str(e), "danger")
            return redirect(url_for("pdp_home", id_fasc=id_fasc) if id_fasc else url_for("pdp_home"))

    @app.route("/pdp/documenti")
    def pdp_documenti():
        from pct.pdp import crea_client_pdp
        codice_ufficio = request.args.get("codice_ufficio", "")
        numero_rg      = request.args.get("numero_rg", "")
        anno_rg_str    = request.args.get("anno_rg", "0")
        anno_rg        = int(anno_rg_str) if anno_rg_str.isdigit() else 0
        demo_mode      = _polis_demo_mode()
        try:
            client    = crea_client_pdp(demo=demo_mode)
            documenti = client.consulta_documenti(codice_ufficio, numero_rg, anno_rg)
        except Exception as e:
            app.logger.exception("Errore pdp_documenti: %s", e)
            documenti = []
            flash(str(e), "danger")

        # Risolvi nome ufficio dal codice
        nome_ufficio = codice_ufficio
        try:
            from pct.uffici_giudiziari import get_gestore as _get_uff
            _uff = next(
                (u for u in _get_uff(
                    os.getenv("PCT_UFFICI_DB", "/data/uffici/uffici_giudiziari.json")
                ).carica() if u.get("codice") == codice_ufficio),
                None,
            )
            nome_ufficio = _uff["nome"] if _uff else codice_ufficio
        except Exception:
            pass

        # Raggruppa per id_deposito → lista ordinata per data (più recenti prima)
        from collections import OrderedDict
        _gruppi: dict = OrderedDict()
        for doc in sorted(documenti, key=lambda d: d.data_deposito or "", reverse=True):
            chiave = doc.id_deposito or f"__{doc.data_deposito}__{doc.mittente}"
            if chiave not in _gruppi:
                _gruppi[chiave] = {
                    "id_deposito": doc.id_deposito or chiave,
                    "tipo_atto": doc.tipo_atto or doc.tipo.replace("_", " ").title(),
                    "data_deposito": doc.data_deposito,
                    "mittente": doc.mittente,
                    "documenti": [],
                }
            _gruppi[chiave]["documenti"].append(doc)
        depositi = list(_gruppi.values())

        return render_template(
            "pdp_documenti.html",
            documenti=documenti,
            depositi=depositi,
            numero_rg=numero_rg,
            anno_rg=anno_rg,
            codice_ufficio=codice_ufficio,
            nome_ufficio=nome_ufficio,
            demo_mode=demo_mode,
        )

    @app.route("/pdp/importa", methods=["POST"])
    def pdp_importa():
        from pct.pdp import crea_client_pdp, FascicoloPDP
        import json
        f         = request.form
        demo_mode = f.get("demo_mode") == "1" or _polis_demo_mode()
        try:
            fascicolo = FascicoloPDP(
                numero_rg=f.get("numero_rg", ""),
                anno_rg=int(f.get("anno_rg", 0) or 0),
                tipo_registro=f.get("tipo_registro", ""),
                fase=f.get("fase", ""),
                stato=f.get("stato", ""),
                reato=f.get("reato", ""),
                sezione=f.get("sezione", ""),
                giudice=f.get("giudice", ""),
                data_iscrizione=f.get("data_iscrizione", ""),
                data_udienza=f.get("data_udienza", ""),
                imputati=json.loads(f.get("imputati_json", "[]")),
                parti_offese=json.loads(f.get("parti_offese_json", "[]")),
                codice_ufficio=f.get("codice_ufficio", ""),
                nome_ufficio=f.get("nome_ufficio", ""),
            )
            client    = crea_client_pdp(demo=demo_mode)
            avv       = g.utente_corrente.username if g.utente_corrente else ""
            risultato = client.importa_fascicolo(fascicolo, get_fascicoli(), get_clienti(), avv)
            for avviso in risultato.avvisi:
                flash(avviso, "warning")
            if risultato.successo and risultato.id_fascicolo_locale:
                flash(risultato.messaggio, "success")
                return redirect(url_for("dettaglio_fascicolo",
                                        id_fasc=risultato.id_fascicolo_locale))
            flash(risultato.messaggio, "danger")
        except Exception as e:
            flash(str(e), "danger")
        return redirect(url_for("pdp_home"))

    # ---------------------------------------------------------------- PAT Amministrativo — SIGA

    @app.route("/pat", methods=["GET"])
    def pat_home():
        demo_mode = _polis_demo_mode()
        id_fasc = request.args.get("id_fasc", "")
        fascicolo_ctx = get_fascicoli().get(id_fasc) if id_fasc else None
        return render_template("pat.html", demo_mode=demo_mode, oggi=date.today(),
                               fascicolo=fascicolo_ctx, id_fasc=id_fasc)

    @app.route("/pat/ricerca", methods=["POST"])
    def pat_ricerca():
        from pct.pat import crea_client_pat
        f         = request.form
        ufficio   = f.get("ufficio", "").strip()
        demo_mode = f.get("demo_mode") == "1" or _polis_demo_mode()

        if not ufficio:
            flash("Seleziona un ufficio giudiziario.", "warning")
            return redirect(url_for("pat_home"))

        id_fasc         = f.get("id_fasc", "").strip()
        fascicolo_ctx   = get_fascicoli().get(id_fasc) if id_fasc else None
        numero_ricorso  = f.get("numero_ricorso", "").strip() or None
        anno_str        = f.get("anno", "").strip()
        anno            = int(anno_str) if anno_str.isdigit() else None
        nome_ricorrente = f.get("nome_ricorrente", "").strip() or None
        materia         = f.get("materia", "").strip() or None

        try:
            client    = crea_client_pat(demo=demo_mode)
            fascicoli = client.ricerca_fascicoli(
                ufficio=ufficio,
                numero_ricorso=numero_ricorso,
                anno=anno,
                nome_ricorrente=nome_ricorrente,
                materia=materia,
            )
            try:
                from pct.uffici_giudiziari import get_gestore as _get_uff
                _uff = next(
                    (u for u in _get_uff(
                        os.getenv("PCT_UFFICI_DB", "/data/uffici/uffici_giudiziari.json")
                    ).carica() if u.get("codice") == ufficio),
                    None,
                )
                ufficio_sel_nome = _uff["nome"] if _uff else ufficio
            except Exception:
                ufficio_sel_nome = ufficio
            return render_template(
                "pat.html",
                demo_mode=demo_mode,
                fascicoli=fascicoli,
                ufficio_sel=ufficio,
                ufficio_sel_nome=ufficio_sel_nome,
                numero_ricorso=numero_ricorso or "",
                anno=anno or "",
                nome_ricorrente=nome_ricorrente or "",
                materia=materia or "",
                fascicolo=fascicolo_ctx,
                id_fasc=id_fasc,
                oggi=date.today(),
            )
        except Exception as e:
            app.logger.exception("Errore pat_ricerca: %s", e)
            flash(str(e), "danger")
            return redirect(url_for("pat_home", id_fasc=id_fasc) if id_fasc else url_for("pat_home"))

    @app.route("/pat/documenti")
    def pat_documenti():
        from pct.pat import crea_client_pat
        codice_ufficio = request.args.get("codice_ufficio", "")
        numero_ricorso = request.args.get("numero_ricorso", "")
        anno_str       = request.args.get("anno", "0")
        anno           = int(anno_str) if anno_str.isdigit() else 0
        demo_mode      = _polis_demo_mode()
        try:
            client    = crea_client_pat(demo=demo_mode)
            documenti = client.consulta_documenti(codice_ufficio, numero_ricorso, anno)
        except Exception as e:
            app.logger.exception("Errore pat_documenti: %s", e)
            documenti = []
            flash(str(e), "danger")

        # Risolvi nome ufficio dal codice
        nome_ufficio = codice_ufficio
        try:
            from pct.uffici_giudiziari import get_gestore as _get_uff
            _uff = next(
                (u for u in _get_uff(
                    os.getenv("PCT_UFFICI_DB", "/data/uffici/uffici_giudiziari.json")
                ).carica() if u.get("codice") == codice_ufficio),
                None,
            )
            nome_ufficio = _uff["nome"] if _uff else codice_ufficio
        except Exception:
            pass

        # Raggruppa per id_deposito → lista ordinata per data (più recenti prima)
        from collections import OrderedDict
        _gruppi: dict = OrderedDict()
        for doc in sorted(documenti, key=lambda d: d.data_deposito or "", reverse=True):
            chiave = doc.id_deposito or f"__{doc.data_deposito}__{doc.mittente}"
            if chiave not in _gruppi:
                _gruppi[chiave] = {
                    "id_deposito": doc.id_deposito or chiave,
                    "tipo_atto": doc.tipo_atto or doc.tipo.replace("_", " ").title(),
                    "data_deposito": doc.data_deposito,
                    "mittente": doc.mittente,
                    "documenti": [],
                }
            _gruppi[chiave]["documenti"].append(doc)
        depositi = list(_gruppi.values())

        return render_template(
            "pat_documenti.html",
            documenti=documenti,
            depositi=depositi,
            numero_ricorso=numero_ricorso,
            anno=anno,
            codice_ufficio=codice_ufficio,
            nome_ufficio=nome_ufficio,
            demo_mode=demo_mode,
        )

    @app.route("/pat/importa", methods=["POST"])
    def pat_importa():
        from pct.pat import crea_client_pat, FascicoloPAT
        import json
        f         = request.form
        demo_mode = f.get("demo_mode") == "1" or _polis_demo_mode()
        try:
            fascicolo = FascicoloPAT(
                numero_ricorso=f.get("numero_ricorso", ""),
                anno=int(f.get("anno", 0) or 0),
                tipo=f.get("tipo", ""),
                stato=f.get("stato", ""),
                materia=f.get("materia", ""),
                sezione=f.get("sezione", ""),
                giudice_relatore=f.get("giudice_relatore", ""),
                data_deposito=f.get("data_deposito", ""),
                data_udienza=f.get("data_udienza", ""),
                oggetto=f.get("oggetto", ""),
                ricorrenti=json.loads(f.get("ricorrenti_json", "[]")),
                resistenti=json.loads(f.get("resistenti_json", "[]")),
                codice_ufficio=f.get("codice_ufficio", ""),
                nome_ufficio=f.get("nome_ufficio", ""),
            )
            client    = crea_client_pat(demo=demo_mode)
            avv       = g.utente_corrente.username if g.utente_corrente else ""
            risultato = client.importa_fascicolo(fascicolo, get_fascicoli(), get_clienti(), avv)
            for avviso in risultato.avvisi:
                flash(avviso, "warning")
            if risultato.successo and risultato.id_fascicolo_locale:
                flash(risultato.messaggio, "success")
                return redirect(url_for("dettaglio_fascicolo",
                                        id_fasc=risultato.id_fascicolo_locale))
            flash(risultato.messaggio, "danger")
        except Exception as e:
            flash(str(e), "danger")
        return redirect(url_for("pat_home"))

    # ---------------------------------------------------------------- PTT Tributario / SIGIT

    @app.route("/sigit", methods=["GET"])
    def sigit_home():
        demo_mode = _polis_demo_mode()
        id_fasc = request.args.get("id_fasc", "")
        fascicolo = get_fascicoli().get(id_fasc) if id_fasc else None
        return render_template("sigit.html",
                               demo_mode=demo_mode,
                               id_fasc=id_fasc,
                               fascicolo=fascicolo,
                               commissione_sel=None,
                               numero_rgt=None,
                               anno_rgt=None,
                               materia=None,
                               nome_ricorrente=None,
                               oggi=date.today())

    @app.route("/sigit/ricerca", methods=["POST"])
    def sigit_ricerca():
        from pct.sigit import crea_client_sigit
        f         = request.form
        demo_mode = f.get("demo_mode") == "1" or _polis_demo_mode()
        commissione   = f.get("commissione", "").strip()
        numero_rgt    = f.get("numero_rgt", "").strip() or None
        anno_rgt_str  = f.get("anno_rgt", "").strip()
        anno_rgt      = int(anno_rgt_str) if anno_rgt_str.isdigit() else None
        materia       = f.get("materia", "").strip() or None
        nome_ricorrente = f.get("nome_ricorrente", "").strip() or None
        id_fasc       = f.get("id_fasc", "")
        fascicolo     = get_fascicoli().get(id_fasc) if id_fasc else None
        fascicoli = []
        try:
            client    = crea_client_sigit(demo=demo_mode)
            fascicoli = client.ricerca_fascicoli(
                commissione=commissione,
                numero_rgt=numero_rgt,
                anno_rgt=anno_rgt,
                nome_ricorrente=nome_ricorrente,
                tipo=materia,
            )
        except Exception as e:
            flash(str(e), "danger")
        return render_template("sigit.html",
                               demo_mode=demo_mode,
                               id_fasc=id_fasc,
                               fascicolo=fascicolo,
                               commissione_sel=commissione,
                               numero_rgt=numero_rgt or "",
                               anno_rgt=anno_rgt or "",
                               materia=materia or "",
                               nome_ricorrente=nome_ricorrente or "",
                               fascicoli=fascicoli,
                               oggi=date.today())

    @app.route("/sigit/documenti")
    def sigit_documenti():
        from pct.sigit import crea_client_sigit
        demo_mode        = _polis_demo_mode()
        codice_commissione = request.args.get("codice_commissione", "")
        numero_rgt       = request.args.get("numero_rgt", "")
        anno_rgt_str     = request.args.get("anno_rgt", "")
        anno_rgt         = int(anno_rgt_str) if anno_rgt_str.isdigit() else 0
        documenti = []
        depositi  = []
        nome_commissione = codice_commissione
        try:
            client    = crea_client_sigit(demo=demo_mode)
            documenti = client.recupera_documenti(
                commissione=codice_commissione,
                numero_rgt=numero_rgt,
                anno_rgt=anno_rgt,
            )
            # Raggruppa per id_deposito (regola buste CLAUDE.md)
            from collections import OrderedDict
            buste: dict = OrderedDict()
            for doc in documenti:
                chiave = doc.id_deposito if doc.id_deposito else f"__{doc.data_deposito}__{doc.mittente}"
                if chiave not in buste:
                    buste[chiave] = {
                        "id_deposito":   doc.id_deposito,
                        "tipo_atto":     doc.tipo_atto or doc.tipo,
                        "data_deposito": doc.data_deposito,
                        "mittente":      doc.mittente,
                        "documenti":     [],
                    }
                buste[chiave]["documenti"].append(doc)
            depositi = sorted(buste.values(), key=lambda b: b["data_deposito"] or "", reverse=True)
        except Exception as e:
            flash(str(e), "danger")
        return render_template("sigit_documenti.html",
                               demo_mode=demo_mode,
                               codice_commissione=codice_commissione,
                               nome_commissione=nome_commissione,
                               numero_rgt=numero_rgt,
                               anno_rgt=anno_rgt,
                               documenti=documenti,
                               depositi=depositi,
                               oggi=date.today())

    @app.route("/sigit/importa", methods=["POST"])
    def sigit_importa():
        from pct.sigit import crea_client_sigit, FascicoloSIGIT
        import json
        f         = request.form
        demo_mode = f.get("demo_mode") == "1" or _polis_demo_mode()
        try:
            fascicolo = FascicoloSIGIT(
                numero_rgt=f.get("numero_rgt", ""),
                anno_rgt=int(f.get("anno_rgt", 0) or 0),
                tipo=f.get("tipo", ""),
                stato=f.get("stato", ""),
                materia=f.get("materia", ""),
                sezione=f.get("sezione", ""),
                giudice_relatore=f.get("giudice_relatore", ""),
                data_deposito=f.get("data_deposito", ""),
                data_udienza=f.get("data_udienza", ""),
                oggetto_controversia=f.get("oggetto_controversia", ""),
                valore_controversia=float(f.get("valore_controversia") or 0),
                ricorrenti=json.loads(f.get("ricorrenti_json", "[]")),
                resistenti=json.loads(f.get("resistenti_json", "[]")),
                codice_commissione=f.get("codice_commissione", ""),
                nome_commissione=f.get("nome_commissione", ""),
            )
            client    = crea_client_sigit(demo=demo_mode)
            avv       = g.utente_corrente.username if g.utente_corrente else ""
            risultato = client.importa_fascicolo(fascicolo, get_fascicoli(), get_clienti(), avv)
            for avviso in risultato.avvisi:
                flash(avviso, "warning")
            if risultato.successo and risultato.id_fascicolo_locale:
                flash(risultato.messaggio, "success")
                return redirect(url_for("dettaglio_fascicolo",
                                        id_fasc=risultato.id_fascicolo_locale))
            flash(risultato.messaggio, "danger")
        except Exception as e:
            flash(str(e), "danger")
        return redirect(url_for("sigit_home"))

    # ---------------------------------------------------------------- Checklist deposito telematico

    @app.route("/deposito/checklist")
    def deposito_checklist():
        """Checklist operativa per il deposito telematico, per tipo di procedimento."""
        return render_template("deposito_checklist.html")

    @app.route("/guida/firma-digitale")
    def guida_firma_digitale():
        """Guida interattiva su come ottenere e configurare il certificato di firma digitale."""
        return render_template("guida_firma_digitale.html")

    # ---------------------------------------------------------------- API autocomplete uffici giudiziari

    @app.route("/api/uffici")
    def api_uffici():
        """Autocomplete uffici giudiziari — usa la cache aggiornata del GestoreUfficiGiudiziari."""
        try:
            from pct.uffici_giudiziari import get_gestore
            q    = request.args.get("q", "").strip()
            tipo = request.args.get("tipo", "")
            cache_path = os.getenv("PCT_UFFICI_DB", "/data/uffici/uffici_giudiziari.json")
            gestore = get_gestore(cache_path)
            return jsonify(gestore.cerca(q, tipo))
        except Exception as e:
            app.logger.exception("Errore api_uffici: %s", e)
            return jsonify([]), 200  # restituisce lista vuota per non bloccare l'autocomplete

    @app.route("/api/uffici/aggiorna", methods=["POST"])
    def api_uffici_aggiorna():
        """Forza l'aggiornamento della cache degli uffici giudiziari (solo admin)."""
        u = g.utente_corrente
        if not u or not u.ha_permesso("utenti.leggi"):
            return jsonify({"ok": False, "messaggio": "Non autorizzato"}), 403
        try:
            from pct.uffici_giudiziari import get_gestore
            cache_path = os.getenv("PCT_UFFICI_DB", "/data/uffici/uffici_giudiziari.json")
            gestore = get_gestore(cache_path)
            url_personalizzato = request.json.get("url", "") if request.is_json else ""
            ok, messaggio = gestore.aggiorna(url=url_personalizzato)
            stato = gestore.stato()
            audit("uffici.aggiorna", "sistema", None, dettagli=messaggio)
            return jsonify({"ok": ok, "messaggio": messaggio, "stato": stato})
        except Exception as e:
            app.logger.exception("Errore api_uffici_aggiorna: %s", e)
            return jsonify({"ok": False, "messaggio": str(e)}), 200

    @app.route("/api/uffici/stato")
    def api_uffici_stato():
        """Stato della cache degli uffici giudiziari (solo admin)."""
        u = g.utente_corrente
        if not u or not u.ha_permesso("utenti.leggi"):
            return jsonify({"ok": False}), 403
        try:
            from pct.uffici_giudiziari import get_gestore
            cache_path = os.getenv("PCT_UFFICI_DB", "/data/uffici/uffici_giudiziari.json")
            return jsonify(get_gestore(cache_path).stato())
        except Exception as e:
            app.logger.exception("Errore api_uffici_stato: %s", e)
            return jsonify({"ok": False, "errore": str(e)}), 200

    @app.route("/api/uffici/variazioni")
    def api_uffici_variazioni():
        """Ultimo report di verifica variazioni uffici (solo admin)."""
        u = g.utente_corrente
        if not u or not u.ha_permesso("utenti.leggi"):
            return jsonify({"ok": False}), 403
        try:
            from pct.uffici_giudiziari import get_gestore
            cache_path = os.getenv("PCT_UFFICI_DB", "/data/uffici/uffici_giudiziari.json")
            report = get_gestore(cache_path).carica_report_variazioni()
            if report is None:
                return jsonify({"ok": False, "errore": "Nessun controllo eseguito ancora"})
            return jsonify(report)
        except Exception as e:
            app.logger.exception("Errore api_uffici_variazioni: %s", e)
            return jsonify({"ok": False, "errore": str(e)}), 200

    @app.route("/api/uffici/variazioni/esegui", methods=["POST"])
    def api_uffici_variazioni_esegui():
        """Avvia manualmente la verifica variazioni uffici (solo admin)."""
        u = g.utente_corrente
        if not u or not u.ha_permesso("utenti.leggi"):
            return jsonify({"ok": False}), 403
        try:
            from pct.uffici_giudiziari import get_gestore
            cache_path = os.getenv("PCT_UFFICI_DB", "/data/uffici/uffici_giudiziari.json")
            report = get_gestore(cache_path).verifica_variazioni()
            audit("uffici.verifica_variazioni", u.username, None,
                  dettagli=f"n_variazioni={report.get('n_variazioni', 0)}")
            return jsonify(report)
        except Exception as e:
            app.logger.exception("Errore api_uffici_variazioni_esegui: %s", e)
            return jsonify({"ok": False, "errore": str(e)}), 200

    @app.route("/api/uffici/sync/report")
    def api_uffici_sync_report():
        """Restituisce l'ultimo report di sync multi-sorgente (solo admin)."""
        u = g.utente_corrente
        if not u or not u.ha_permesso("utenti.leggi"):
            return jsonify({"ok": False}), 403
        try:
            from pct.sync_uffici import carica_ultimo_report
            cache_path = os.getenv("PCT_UFFICI_DB", "/data/uffici/uffici_giudiziari.json")
            report = carica_ultimo_report(cache_path)
            if report is None:
                return jsonify({"ok": False, "errore": "Nessun sync eseguito ancora"})
            return jsonify(report)
        except Exception as e:
            app.logger.exception("Errore api_uffici_sync_report: %s", e)
            return jsonify({"ok": False, "errore": str(e)}), 200

    @app.route("/api/uffici/sync/esegui", methods=["POST"])
    def api_uffici_sync_esegui():
        """Avvia manualmente il sync multi-sorgente degli uffici (solo admin)."""
        u = g.utente_corrente
        if not u or not u.ha_permesso("utenti.leggi"):
            return jsonify({"ok": False}), 403
        try:
            from pct.sync_uffici import esegui_sync_completo
            cache_path = os.getenv("PCT_UFFICI_DB", "/data/uffici/uffici_giudiziari.json")
            report = esegui_sync_completo(cache_path)
            audit("uffici.sync_eseguito", u.username, None,
                  dettagli=f"n_totale={report.get('n_totale_post',0)} "
                           f"nuovi={report.get('n_nuovi',0)} "
                           f"pec={report.get('n_pec_aggiornate',0)}")
            return jsonify(report)
        except Exception as e:
            app.logger.exception("Errore api_uffici_sync_esegui: %s", e)
            return jsonify({"ok": False, "errore": str(e)}), 200

    # ---------------------------------------------------------------- codice fiscale

    @app.route("/api/cf/decodifica")
    def api_cf_decodifica():
        """Decodifica un codice fiscale e restituisce i dati anagrafici."""
        cf = request.args.get("cf", "").strip()
        try:
            from pct.codice_fiscale import decodifica
            risultato = decodifica(cf)
            if risultato is None:
                return jsonify({"errore": "CF non valido o troppo corto"}), 200
            return jsonify(risultato)
        except Exception as e:
            app.logger.exception("Errore api_cf_decodifica: %s", e)
            return jsonify({"errore": str(e)}), 200

    # ---------------------------------------------------------------- tribunali

    @app.route("/tribunali")
    def tribunali():
        reginde = ClientReGINde()
        uffici = reginde.elenca_uffici()
        return render_template("tribunali.html", uffici=uffici)

    # ================================================================ CLIENTI

    @app.route("/clienti")
    def lista_clienti():
        gc = get_clienti()
        u = g.utente_corrente
        testo = request.args.get("q", "").strip()
        tipo_f = request.args.get("tipo")
        stato_f = request.args.get("stato", "ATTIVO")

        tipo = TipoCliente(tipo_f) if tipo_f else None
        stato = StatoCliente(stato_f) if stato_f else None

        clienti = gc.cerca(testo=testo, tipo=tipo, stato=stato) if testo else gc.tutti(stato=stato, tipo=tipo)

        # Utenti senza accesso globale vedono solo i clienti condivisi con loro
        if u and not u.ha_permesso("clienti.leggi"):
            ids_accessibili = get_condivisioni().ids_clienti_accessibili(u.id)
            clienti = [c for c in clienti if c.id in ids_accessibili]

        stats = gc.statistiche()
        return render_template(
            "clienti/lista.html",
            clienti=clienti,
            stats=stats,
            q=testo,
            tipo_filtro=tipo_f or "",
            stato_filtro=stato_f or "",
            tipi=list(TipoCliente),
            stati=list(StatoCliente),
        )

    @app.route("/clienti/nuovo", methods=["GET", "POST"])
    def nuovo_cliente():
        gc = get_clienti()
        if request.method == "POST":
            f = request.form
            tipo = TipoCliente(f["tipo"])
            try:
                c = gc.nuovo(
                    tipo=tipo,
                    nome=f.get("nome", ""),
                    cognome=f.get("cognome", ""),
                    ragione_sociale=f.get("ragione_sociale", ""),
                    codice_fiscale=f.get("codice_fiscale", "").upper(),
                    partita_iva=f.get("partita_iva", ""),
                    forma_giuridica=f.get("forma_giuridica", ""),
                    data_nascita=f.get("data_nascita", ""),
                    luogo_nascita=f.get("luogo_nascita", ""),
                    provincia_nascita=f.get("provincia_nascita", ""),
                    sesso=f.get("sesso", ""),
                    nazionalita=f.get("nazionalita", "Italiana"),
                    rappresentante_legale=f.get("rappresentante_legale", ""),
                    cf_rappresentante=f.get("cf_rappresentante", "").upper(),
                    avvocato_referente=f.get("avvocato_referente", ""),
                    provenienza=f.get("provenienza", ""),
                    note=f.get("note", ""),
                )
                # indirizzi e recapiti
                _salva_indirizzo(gc, c.id, "residenza", f)
                _salva_indirizzo(gc, c.id, "domicilio", f, prefix="dom_")
                _salva_indirizzo(gc, c.id, "sede_legale", f, prefix="sl_")
                gc.aggiorna_recapiti(c.id,
                    telefono=f.get("telefono", ""),
                    cellulare=f.get("cellulare", ""),
                    email=f.get("email", ""),
                    pec=f.get("pec", ""),
                    fax=f.get("fax", ""),
                    sito_web=f.get("sito_web", ""),
                )
                flash(f"Cliente '{c.nome_completo}' aggiunto.", "success")
                sync_pubblica("crea", "clienti", c.id)
                return redirect(url_for("dettaglio_cliente", id_cliente=c.id))
            except (ValueError, KeyError) as e:
                flash(str(e), "danger")

        return render_template(
            "clienti/form.html",
            cliente=None,
            tipi=list(TipoCliente),
            stati=list(StatoCliente),
            tipi_doc=list(TipoDocumentoCliente),
        )

    @app.route("/clienti/<id_cliente>")
    def dettaglio_cliente(id_cliente):
        gc = get_clienti()
        c = gc.get(id_cliente)
        if not c:
            flash("Cliente non trovato.", "warning")
            return redirect(url_for("lista_clienti"))
        if not cliente_accessibile(id_cliente):
            flash("Non hai accesso a questa cartella cliente.", "danger")
            return redirect(url_for("lista_clienti"))
        agenda = get_agenda()
        apps_cliente = agenda.cerca(cliente=c.nome_completo)
        gcd = get_condivisioni()
        n_collaboratori = gcd.n_collaboratori(id_cliente)
        u = g.utente_corrente
        ruolo_cond = gcd.ruolo_accesso(u.id, id_cliente) if u else None
        # #3 — Audit: registra accesso a cartella condivisa
        if u and not u.ha_permesso("clienti.leggi") and ruolo_cond:
            audit("condivisione.accesso", "cliente", id_cliente,
                  dettagli=f"accesso lettura [{ruolo_cond.value}]")
        link_attivi = gcd.link_attivi_per_cliente(id_cliente)
        # Fascicoli del cliente — preview inline (max 5)
        fascicoli_cliente = [
            f for f in get_fascicoli().tutti()
            if f.id_cliente == id_cliente
        ][:5]
        track_recente("cliente", id_cliente, c.nome_completo,
                      url_for("dettaglio_cliente", id_cliente=id_cliente), "bi-person")
        return render_template(
            "clienti/dettaglio.html",
            cliente=c,
            apps_cliente=apps_cliente,
            n_collaboratori=n_collaboratori,
            ruolo_condivisione=ruolo_cond,
            link_attivi=link_attivi,
            fascicoli_cliente=fascicoli_cliente,
        )

    # ================================================================ CARTELLA CLIENTE
    # Vista unificata: tutti i fascicoli di un cliente in un unico workspace

    @app.route("/clienti/<id_cliente>/cartella")
    def cartella_cliente(id_cliente):
        gc = get_clienti()
        gf = get_fascicoli()
        c = gc.get(id_cliente)
        if not c:
            flash("Cliente non trovato.", "warning")
            return redirect(url_for("lista_clienti"))
        if not cliente_accessibile(id_cliente):
            flash("Non hai accesso a questa cartella cliente.", "danger")
            return redirect(url_for("lista_clienti"))
        try:
            tutti = gf.cerca(id_cliente=id_cliente, archiviati=True)
            _stati_chiusi = {StatoFascicolo.ARCHIVIATO, StatoFascicolo.DEFINITO}
            fascicoli_attivi    = [f for f in tutti if f.stato not in _stati_chiusi]
            fascicoli_archiviati = [f for f in tutti if f.stato in _stati_chiusi]
            fascicoli_archiviati.sort(
                key=lambda x: (x.archivio.data_archiviazione if x.archivio else ""),
                reverse=True,
            )
            n_documenti = sum(f.documenti_count for f in tutti)
            from datetime import timedelta
            oggi = date.today()
            soglia = (oggi + timedelta(days=7)).isoformat()
            scadenze_imminenti = []
            for f in fascicoli_attivi:
                ps = f.prossima_scadenza
                if ps and ps.data and ps.data <= soglia:
                    scadenze_imminenti.append((f, ps))
            scadenze_imminenti.sort(key=lambda x: x[1].data)
            timeline = []
            for f in fascicoli_attivi:
                for att in f.attivita:
                    timeline.append((f, att))
            timeline.sort(key=lambda x: x[1].data if x[1].data else "", reverse=True)
            timeline = timeline[:30]
            # Appuntamenti del cliente
            agenda_obj = get_agenda()
            appuntamenti_cliente = agenda_obj.per_cliente(id_cliente)
            # fallback: cerca anche per nome se ci sono appuntamenti senza id_cliente
            if not appuntamenti_cliente:
                appuntamenti_cliente = agenda_obj.cerca(cliente=c.nome_completo)

            # Messaggi del cliente
            gm = get_messaggi()
            messaggi_cliente = gm.per_cliente(id_cliente)

            # Parcelle del cliente
            from pct.fatturazione import GestioneFatturazione
            gfatt_path = app.config.get("FATTURAZIONE_DB", "./fatturazione/parcelle.json")
            gfatt = GestioneFatturazione(gfatt_path)
            parcelle_cliente = gfatt.per_cliente(id_cliente)

            # Preventivi e conferimenti del cliente
            from pct.preventivi import GestionePreventivi
            gp_path = app.config.get("PREVENTIVI_DB", "./preventivi/preventivi.json")
            gp = GestionePreventivi(gp_path)
            preventivi_cliente = gp.preventivi_per_cliente(id_cliente)
            conferimenti_cliente = gp.conferimenti_per_cliente(id_cliente)

            track_recente("cliente", id_cliente, c.nome_completo,
                          url_for("cartella_cliente", id_cliente=id_cliente),
                          "bi-folder2-open")
            return render_template(
                "clienti/cartella.html",
                cliente=c,
                fascicoli_attivi=fascicoli_attivi,
                fascicoli_archiviati=fascicoli_archiviati,
                n_documenti=n_documenti,
                scadenze_imminenti=scadenze_imminenti,
                timeline=timeline,
                oggi=oggi,
                appuntamenti_cliente=appuntamenti_cliente,
                messaggi_cliente=messaggi_cliente,
                parcelle_cliente=parcelle_cliente,
                preventivi_cliente=preventivi_cliente,
                conferimenti_cliente=conferimenti_cliente,
                tipi_fascicolo=list(TipoFascicolo),
            )
        except Exception as e:
            app.logger.exception("Errore cartella_cliente %s: %s", id_cliente, e)
            flash(f"Errore nel caricamento della cartella: {e}", "danger")
            return redirect(url_for("dettaglio_cliente", id_cliente=id_cliente))

    # ================================================================ FALDONE DIGITALE
    # Vista unificata per tipo: fascicoli, atti, PEC, depositi, scadenze

    @app.route("/clienti/<id_cliente>/faldone")
    def faldone_cliente(id_cliente):
        """Faldone digitale: tutte le pratiche del cliente organizzate per tipologia."""
        try:
            gc = get_clienti()
            c = gc.get(id_cliente)
            if not c:
                flash("Cliente non trovato.", "warning")
                return redirect(url_for("lista_clienti"))
            if not cliente_accessibile(id_cliente):
                flash("Non hai accesso a questa cartella cliente.", "danger")
                return redirect(url_for("lista_clienti"))

            gf = get_fascicoli()
            gs = get_scadenziario()

            tutti = gf.cerca(id_cliente=id_cliente, archiviati=True)

            # Gruppa fascicoli per tipo (solo attivi/in_corso/sospesi in primo piano)
            _stati_chiusi = {StatoFascicolo.ARCHIVIATO, StatoFascicolo.DEFINITO}
            fascicoli_attivi    = [f for f in tutti if f.stato not in _stati_chiusi]
            fascicoli_archiviati = [f for f in tutti if f.stato in _stati_chiusi]

            # Ordine fisso dei tipi
            _ordine_tipi = [
                "CIVILE", "PENALE", "LAVORO", "FAMIGLIA", "AMMINISTRATIVO",
                "STRAGIUDIZIALE", "SUCCESSIONI", "CONSULENZA", "ALTRO",
            ]
            fascicoli_per_tipo: dict = {}
            for tipo in _ordine_tipi:
                gruppo = [f for f in fascicoli_attivi if f.tipo.value == tipo]
                if gruppo:
                    fascicoli_per_tipo[tipo] = gruppo
            # Eventuali tipi non in lista ordine
            for f in fascicoli_attivi:
                if f.tipo.value not in fascicoli_per_tipo:
                    fascicoli_per_tipo.setdefault(f.tipo.value, []).append(f)

            # Scadenze aperte da scadenziario per ciascun fascicolo
            scadenze_per_fascicolo: dict = {}
            for f in tutti:
                sc_list = gs.tutte(id_fascicolo=f.id, stato=None)
                if sc_list:
                    scadenze_per_fascicolo[f.id] = sc_list

            # Tutte le scadenze aggregate (aperte), ordinate per data
            from pct.scadenziario import StatoTermine
            scadenze_aperte = sorted(
                [
                    (f, sc)
                    for f in tutti
                    for sc in scadenze_per_fascicolo.get(f.id, [])
                    if sc.stato == StatoTermine.APERTO and sc.data_scadenza
                ],
                key=lambda x: x[1].data_scadenza,
            )

            # Tutti i documenti aggregati (attivi + archiviati), più recenti prima
            tutti_documenti = sorted(
                [(f, doc) for f in tutti for doc in f.documenti],
                key=lambda x: x[1].data_caricamento,
                reverse=True,
            )

            # Tutti i depositi PCT aggregati
            tutti_depositi = sorted(
                [(f, dep) for f in tutti for dep in f.depositi_pct],
                key=lambda x: x[1].timestamp,
                reverse=True,
            )

            # Stats
            n_doc      = sum(f.documenti_count for f in tutti)
            n_dep      = sum(len(f.depositi_pct) for f in tutti)
            n_scad     = len(scadenze_aperte)
            n_att      = sum(f.attivita_count for f in fascicoli_attivi)

            # Note interne e audit trail
            note_faldone = _carica_note_faldone(id_cliente)

            # Ultimi 20 accessi al faldone (audit)
            try:
                from pct.auth import GestioneUtenti
                _ga = GestioneUtenti(db_path=app.config["AUTH_DB"],
                                     audit_path=app.config["AUDIT_DB"])
                audit_trail = _ga.audit_log(limit=500)
                audit_trail = [e for e in audit_trail if e.risorsa_id == id_cliente][:20]
            except Exception:
                audit_trail = []

            track_recente("cliente", id_cliente, c.nome_completo,
                          url_for("faldone_cliente", id_cliente=id_cliente),
                          "bi-folder2-open")
            audit("faldone.accesso", "cliente", id_cliente)

            return render_template(
                "clienti/faldone.html",
                cliente=c,
                tutti=tutti,
                fascicoli_attivi=fascicoli_attivi,
                fascicoli_archiviati=fascicoli_archiviati,
                fascicoli_per_tipo=fascicoli_per_tipo,
                scadenze_per_fascicolo=scadenze_per_fascicolo,
                scadenze_aperte=scadenze_aperte,
                tutti_documenti=tutti_documenti[:60],
                tutti_depositi=tutti_depositi[:60],
                n_doc=n_doc,
                n_dep=n_dep,
                n_scad=n_scad,
                n_att=n_att,
                note_faldone=note_faldone,
                audit_trail=audit_trail,
                oggi=date.today(),
            )
        except Exception as e:
            app.logger.exception("Errore faldone_cliente %s: %s", id_cliente, e)
            flash(f"Errore nel caricamento del faldone: {e}", "danger")
            return redirect(url_for("dettaglio_cliente", id_cliente=id_cliente))

    # --- Helper note faldone (JSON semplice chiavato per id_cliente) ---
    def _carica_note_faldone(id_cliente: str) -> dict:
        import json as _j
        try:
            with open(app.config["NOTE_FALDONE_DB"]) as fh:
                return _j.load(fh).get(id_cliente, {})
        except (FileNotFoundError, ValueError):
            return {}

    def _salva_note_faldone(id_cliente: str, note: dict) -> None:
        import json as _j
        p = app.config["NOTE_FALDONE_DB"]
        try:
            with open(p) as fh:
                tutti = _j.load(fh)
        except (FileNotFoundError, ValueError):
            tutti = {}
        tutti[id_cliente] = note
        import os as _os
        _os.makedirs(_os.path.dirname(_os.path.abspath(p)), exist_ok=True)
        with open(p, "w") as fh:
            _j.dump(tutti, fh, ensure_ascii=False, indent=2)

    @app.route("/clienti/<id_cliente>/faldone/note", methods=["POST"])
    def faldone_salva_note(id_cliente):
        """Salva le note interne del faldone via AJAX."""
        try:
            gc = get_clienti()
            if not gc.get(id_cliente):
                return jsonify({"ok": False, "errore": "Cliente non trovato"}), 404
            if not cliente_accessibile(id_cliente, RuoloCondivisione.SCRITTURA):
                return jsonify({"ok": False, "errore": "Non autorizzato"}), 403
            dati = request.get_json(silent=True) or {}
            sezione = dati.get("sezione", "generale")
            testo   = dati.get("testo", "")
            note    = _carica_note_faldone(id_cliente)
            note[sezione] = testo
            note["_modificato_il"] = date.today().isoformat()
            u = g.utente_corrente
            note["_modificato_da"] = u.username if u else ""
            _salva_note_faldone(id_cliente, note)
            audit("faldone.note", "cliente", id_cliente,
                  dettagli=f"sezione={sezione}")
            return jsonify({"ok": True})
        except Exception as e:
            app.logger.exception("Errore faldone_salva_note %s: %s", id_cliente, e)
            return jsonify({"ok": False, "errore": str(e)}), 200

    @app.route("/clienti/<id_cliente>/faldone/pdf")
    def faldone_pdf_export(id_cliente):
        """Genera e scarica il PDF «Indice Faldone Digitale»."""
        try:
            gc = get_clienti()
            c  = gc.get(id_cliente)
            if not c:
                flash("Cliente non trovato.", "warning")
                return redirect(url_for("lista_clienti"))
            if not cliente_accessibile(id_cliente):
                flash("Non hai accesso a questa cartella cliente.", "danger")
                return redirect(url_for("lista_clienti"))

            gf = get_fascicoli()
            gs = get_scadenziario()
            from pct.scadenziario import StatoTermine

            tutti = gf.cerca(id_cliente=id_cliente, archiviati=True)
            _stati_chiusi = {StatoFascicolo.ARCHIVIATO, StatoFascicolo.DEFINITO}
            fascicoli_attivi = [f for f in tutti if f.stato not in _stati_chiusi]

            _ordine = ["CIVILE","PENALE","LAVORO","FAMIGLIA","AMMINISTRATIVO",
                       "STRAGIUDIZIALE","SUCCESSIONI","CONSULENZA","ALTRO"]
            fasc_per_tipo_raw: dict = {}
            for tipo in _ordine:
                gruppo = [f.to_dict() for f in fascicoli_attivi if f.tipo.value == tipo]
                if gruppo:
                    fasc_per_tipo_raw[tipo] = gruppo
            for f in fascicoli_attivi:
                if f.tipo.value not in fasc_per_tipo_raw:
                    fasc_per_tipo_raw.setdefault(f.tipo.value, []).append(f.to_dict())

            # Scadenze aperte
            scad_pdf = []
            for f in tutti:
                for sc in gs.tutte(id_fascicolo=f.id, stato=None):
                    if sc.stato == StatoTermine.APERTO and sc.data_scadenza:
                        scad_pdf.append({
                            "data_scadenza": sc.data_scadenza,
                            "fascicolo_numero": f.numero,
                            "titolo": sc.titolo,
                            "priorita": sc.priorita.value,
                            "perentorio": sc.perentorio,
                        })
            scad_pdf.sort(key=lambda x: x["data_scadenza"])

            # Timeline
            tl_pdf = sorted(
                [{"data": a.data, "fascicolo_numero": f.numero,
                  "tipo": a.tipo.value, "titolo": a.titolo, "esito": a.esito.value}
                 for f in tutti for a in f.attivita],
                key=lambda x: x["data"] or "", reverse=True,
            )

            # Stats
            stats = {
                "n_doc":  sum(f.documenti_count for f in tutti),
                "n_dep":  sum(len(f.depositi_pct) for f in tutti),
                "n_att":  sum(f.attivita_count for f in fascicoli_attivi),
                "n_scad": len(scad_pdf),
            }
            note = _carica_note_faldone(id_cliente)

            cfg_studio = get_config_studio()
            studio_nome = cfg_studio.nome or app.config.get("PCT_STUDIO_NOME", "Studio Legale PCT")

            import tempfile, io
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp_path = tmp.name

            cli_dict = {
                "nome_completo": c.nome_completo,
                "codice_fiscale": c.codice_fiscale or "",
                "partita_iva": getattr(c, "partita_iva", "") or "",
            }
            faldone_pdf(
                cliente_dict=cli_dict,
                fascicoli_per_tipo=fasc_per_tipo_raw,
                scadenze_aperte=scad_pdf,
                timeline=tl_pdf[:20],
                note=note,
                studio_nome=studio_nome,
                output_path=tmp_path,
                stats=stats,
            )
            audit("faldone.pdf", "cliente", id_cliente)
            nome_file = f"faldone_{c.nome_completo.replace(' ', '_').lower()}_{date.today().isoformat()}.pdf"
            with open(tmp_path, "rb") as fh:
                data = fh.read()
            import os as _os2
            _os2.unlink(tmp_path)
            return send_file(
                io.BytesIO(data),
                mimetype="application/pdf",
                as_attachment=True,
                download_name=nome_file,
            )
        except Exception as e:
            app.logger.exception("Errore faldone_pdf_export %s: %s", id_cliente, e)
            flash(f"Errore generazione PDF: {e}", "danger")
            return redirect(url_for("faldone_cliente", id_cliente=id_cliente))

    # ================================================================ COPERTINE

    @app.route("/clienti/<id_cliente>/faldone/copertina")
    def copertina_faldone(id_cliente):
        """Copertina stampabile del faldone digitale cliente."""
        try:
            gc = get_clienti()
            c = gc.get(id_cliente)
            if not c:
                flash("Cliente non trovato.", "warning")
                return redirect(url_for("lista_clienti"))
            if not cliente_accessibile(id_cliente):
                flash("Non hai accesso a questa cartella cliente.", "danger")
                return redirect(url_for("lista_clienti"))
            gf = get_fascicoli()
            tutti = gf.cerca(id_cliente=id_cliente, archiviati=True)
            _stati_chiusi = {StatoFascicolo.ARCHIVIATO, StatoFascicolo.DEFINITO}
            fascicoli_attivi = [f for f in tutti if f.stato not in _stati_chiusi]
            fascicoli_archiviati = [f for f in tutti if f.stato in _stati_chiusi]
            cfg_studio = get_config_studio()
            studio_nome = cfg_studio.nome or app.config.get("PCT_STUDIO_NOME", "Studio Legale")
            return render_template(
                "clienti/copertina_faldone.html",
                cliente=c,
                fascicoli_attivi=fascicoli_attivi,
                fascicoli_archiviati=fascicoli_archiviati,
                tutti=tutti,
                studio_nome=studio_nome,
                oggi=date.today(),
            )
        except Exception as e:
            app.logger.exception("Errore copertina_faldone %s: %s", id_cliente, e)
            flash(f"Errore copertina faldone: {e}", "danger")
            return redirect(url_for("faldone_cliente", id_cliente=id_cliente))

    @app.route("/fascicoli/<id_fasc>/copertina")
    def copertina_fascicolo(id_fasc):
        """Copertina stampabile del fascicolo."""
        try:
            gf = get_fascicoli()
            gc = get_clienti()
            fasc = gf.get(id_fasc)
            if not fasc:
                flash("Fascicolo non trovato.", "warning")
                return redirect(url_for("lista_fascicoli"))
            cliente = gc.get(fasc.id_cliente) if fasc.id_cliente else None
            if fasc.id_cliente and not cliente_accessibile(fasc.id_cliente):
                flash("Non hai accesso a questo fascicolo.", "danger")
                return redirect(url_for("lista_fascicoli"))
            cfg_studio = get_config_studio()
            studio_nome = cfg_studio.nome or app.config.get("PCT_STUDIO_NOME", "Studio Legale")
            return render_template(
                "fascicoli/copertina.html",
                fascicolo=fasc,
                cliente=cliente,
                studio_nome=studio_nome,
                oggi=date.today(),
            )
        except Exception as e:
            app.logger.exception("Errore copertina_fascicolo %s: %s", id_fasc, e)
            flash(f"Errore copertina fascicolo: {e}", "danger")
            return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))

    # ================================================================ PORTALE CLIENTE
    # Pannello avvocato per gestire il portale self-service del cliente

    def _get_portale_mgr():
        from pct.portale import GestionePortale
        return GestionePortale(
            db_path=app.config["PORTALE_DB"],
            uploads_dir=app.config["PORTALE_UPLOADS"],
        )

    @app.route("/clienti/<id_cliente>/portale", methods=["GET"])
    def portale_config(id_cliente):
        try:
            gc = get_clienti()
            c = gc.get(id_cliente)
            if not c:
                flash("Cliente non trovato.", "warning")
                return redirect(url_for("lista_clienti"))
            gp = _get_portale_mgr()
            portale_obj = gp.get_by_cliente(id_cliente)
            # Se esiste un portale, costruisci il link da mostrare
            link_portale = None
            if portale_obj and portale_obj.is_attivo:
                base = request.host_url.rstrip("/")
                raw_token = session.pop("portale_token_grezzo", None)
                if raw_token:
                    link_portale = f"{base}/portale/{raw_token}"
                    session["portale_link_cache"] = link_portale
                else:
                    link_portale = session.get("portale_link_cache")
            return render_template(
                "clienti/portale_config.html",
                cliente=c,
                portale_obj=portale_obj,
                link_portale=link_portale,
                oggi=date.today(),
                studio_nome=app.config.get("STUDIO_NOME", "Studio Legale PCT"),
            )
        except Exception as e:
            app.logger.exception("Errore portale_config [%s]: %s", id_cliente, e)
            flash(f"Errore caricamento portale: {e}", "danger")
            return redirect(url_for("dettaglio_cliente", id_cliente=id_cliente))

    @app.route("/clienti/<id_cliente>/portale/attiva", methods=["POST"])
    def portale_attiva(id_cliente):
        gc = get_clienti()
        c = gc.get(id_cliente)
        if not c:
            flash("Cliente non trovato.", "warning")
            return redirect(url_for("lista_clienti"))
        from pct.portale import GestionePortale, PermessiPortale
        gp = GestionePortale(
            db_path=app.config["PORTALE_DB"],
            uploads_dir=app.config["PORTALE_UPLOADS"],
        )
        f = request.form
        permessi = PermessiPortale(
            vedi_anagrafica=bool(f.get("vedi_anagrafica")),
            modifica_anagrafica=bool(f.get("modifica_anagrafica")),
            vedi_fascicoli=bool(f.get("vedi_fascicoli")),
            vedi_attivita=bool(f.get("vedi_attivita")),
            vedi_appuntamenti=bool(f.get("vedi_appuntamenti")),
            vedi_scadenze=bool(f.get("vedi_scadenze")),
            carica_documenti=bool(f.get("carica_documenti")),
            firma_privacy=bool(f.get("firma_privacy")),
            max_upload_mb=int(f.get("max_upload_mb", 10)),
        )
        scade_il = f.get("scade_il", "").strip() or None
        if scade_il:
            # Converti da date a datetime ISO
            scade_il = scade_il + "T23:59:59"
        u = g.utente_corrente
        creato_da = u.username if u else "avvocato"
        token_grezzo, _ = gp.crea(
            id_cliente=id_cliente,
            creato_da=creato_da,
            permessi=permessi,
            scade_il=scade_il,
        )
        session["portale_token_grezzo"] = token_grezzo
        session.pop("portale_link_cache", None)
        flash("Portale attivato. Il link è pronto per essere inviato al cliente.", "success")
        return redirect(url_for("portale_config", id_cliente=id_cliente))

    @app.route("/clienti/<id_cliente>/portale/revoca", methods=["POST"])
    def portale_revoca(id_cliente):
        from pct.portale import GestionePortale
        gp = GestionePortale(
            db_path=app.config["PORTALE_DB"],
            uploads_dir=app.config["PORTALE_UPLOADS"],
        )
        portale_obj = gp.get_by_cliente(id_cliente)
        if portale_obj:
            gp.revoca(portale_obj.id)
            session.pop("portale_token_grezzo", None)
            session.pop("portale_link_cache", None)
            flash("Accesso al portale revocato.", "success")
        return redirect(url_for("portale_config", id_cliente=id_cliente))

    @app.route("/clienti/<id_cliente>/modifica", methods=["GET", "POST"])
    def modifica_cliente(id_cliente):
        gc = get_clienti()
        c = gc.get(id_cliente)
        if not c:
            flash("Cliente non trovato.", "warning")
            return redirect(url_for("lista_clienti"))
        if not cliente_accessibile(id_cliente, RuoloCondivisione.SCRITTURA):
            flash("Non hai permesso di modificare questa cartella cliente.", "danger")
            return redirect(url_for("dettaglio_cliente", id_cliente=id_cliente))

        if request.method == "POST":
            f = request.form
            try:
                gc.aggiorna(id_cliente,
                    nome=f.get("nome", c.nome),
                    cognome=f.get("cognome", c.cognome),
                    ragione_sociale=f.get("ragione_sociale", c.ragione_sociale),
                    codice_fiscale=f.get("codice_fiscale", c.codice_fiscale).upper(),
                    partita_iva=f.get("partita_iva", c.partita_iva),
                    forma_giuridica=f.get("forma_giuridica", c.forma_giuridica),
                    data_nascita=f.get("data_nascita", c.data_nascita),
                    luogo_nascita=f.get("luogo_nascita", c.luogo_nascita),
                    provincia_nascita=f.get("provincia_nascita", c.provincia_nascita),
                    sesso=f.get("sesso", c.sesso),
                    nazionalita=f.get("nazionalita", c.nazionalita),
                    rappresentante_legale=f.get("rappresentante_legale", c.rappresentante_legale),
                    cf_rappresentante=f.get("cf_rappresentante", c.cf_rappresentante).upper(),
                    avvocato_referente=f.get("avvocato_referente", c.avvocato_referente),
                    provenienza=f.get("provenienza", c.provenienza),
                    note=f.get("note", c.note),
                    stato=StatoCliente(f.get("stato", c.stato.value)),
                )
                _salva_indirizzo(gc, id_cliente, "residenza", f)
                _salva_indirizzo(gc, id_cliente, "domicilio", f, prefix="dom_")
                _salva_indirizzo(gc, id_cliente, "sede_legale", f, prefix="sl_")
                gc.aggiorna_recapiti(id_cliente,
                    telefono=f.get("telefono", ""),
                    cellulare=f.get("cellulare", ""),
                    email=f.get("email", ""),
                    pec=f.get("pec", ""),
                    fax=f.get("fax", ""),
                    sito_web=f.get("sito_web", ""),
                )
                gc.aggiorna_documento(id_cliente,
                    tipo=TipoDocumentoCliente(f.get("doc_tipo", c.documento.tipo.value)),
                    numero=f.get("doc_numero", ""),
                    rilasciato_da=f.get("doc_rilasciato_da", ""),
                    data_rilascio=f.get("doc_data_rilascio", ""),
                    data_scadenza=f.get("doc_data_scadenza", ""),
                )
                flash("Cliente aggiornato.", "success")
                sync_pubblica("modifica", "clienti", id_cliente)
                return redirect(url_for("dettaglio_cliente", id_cliente=id_cliente))
            except (ValueError, KeyError) as e:
                flash(str(e), "danger")

        return render_template(
            "clienti/form.html",
            cliente=c,
            tipi=list(TipoCliente),
            stati=list(StatoCliente),
            tipi_doc=list(TipoDocumentoCliente),
        )

    @app.route("/clienti/<id_cliente>/elimina", methods=["POST"])
    def elimina_cliente(id_cliente):
        gc = get_clienti()
        try:
            gc.elimina(id_cliente)
            flash("Cliente eliminato.", "success")
            sync_pubblica("elimina", "clienti", id_cliente)
        except KeyError as e:
            flash(str(e), "danger")
        return redirect(url_for("lista_clienti"))

    @app.route("/clienti/<id_cliente>/procedimento", methods=["POST"])
    def aggiungi_procedimento(id_cliente):
        gc = get_clienti()
        f = request.form
        try:
            proc = RiferimentoProcedimento(
                numero_rg=f["numero_rg"],
                anno=int(f.get("anno", datetime.now().year)),
                tribunale=f.get("tribunale", ""),
                descrizione=f.get("descrizione", ""),
                data_apertura=f.get("data_apertura", date.today().isoformat()),
            )
            gc.aggiungi_procedimento(id_cliente, proc)
            flash("Procedimento aggiunto.", "success")
        except (ValueError, KeyError) as e:
            flash(str(e), "danger")
        return redirect(url_for("dettaglio_cliente", id_cliente=id_cliente))

    # ---- API clienti

    @app.route("/api/clienti")
    def api_clienti():
        try:
            gc = get_clienti()
            q = request.args.get("q", "")
            clienti = gc.cerca(testo=q) if q else gc.tutti()
            return jsonify([c.to_dict() for c in clienti])
        except Exception as e:
            app.logger.exception("Errore api_clienti: %s", e)
            return jsonify([])

    @app.route("/api/clienti/<id_cliente>")
    def api_cliente(id_cliente):
        try:
            gc = get_clienti()
            c = gc.get(id_cliente)
            if not c:
                return jsonify({"errore": "Non trovato"}), 404
            return jsonify(c.to_dict())
        except Exception as e:
            app.logger.exception("Errore api_cliente: %s", e)
            return jsonify({"errore": str(e)})

    @app.route("/api/clienti/statistiche")
    def api_clienti_statistiche():
        try:
            return jsonify(get_clienti().statistiche())
        except Exception as e:
            app.logger.exception("Errore api_clienti_statistiche: %s", e)
            return jsonify({"errore": str(e)})

    # ---------------------------------------------------------------- helpers

    def _salva_indirizzo(gc, id_c, tipo, f, prefix=""):
        gc.aggiorna_indirizzo(id_c, tipo,
            via=f.get(f"{prefix}via", ""),
            civico=f.get(f"{prefix}civico", ""),
            cap=f.get(f"{prefix}cap", ""),
            comune=f.get(f"{prefix}comune", ""),
            provincia=f.get(f"{prefix}provincia", ""),
            nazione=f.get(f"{prefix}nazione", "Italia"),
        )

    # ================================================================ CONDIVISIONE CARTELLE

    @app.route("/cartelle-condivise")
    def cartelle_condivise():
        """Elenco delle cartelle clienti condivise con l'utente corrente."""
        u = g.utente_corrente
        gcd = get_condivisioni()
        gc = get_clienti()

        # Utenti con accesso globale vedono le cartelle che LORO hanno condiviso
        if u.ha_permesso("clienti.leggi"):
            # Mostra statistiche e chi gestisco
            accessi_da_me = [
                (gc.get(id_c), ac)
                for id_c, ac in gcd.cartelle_condivise_con(u.id)
                if gc.get(id_c)
            ]
            cartelle_gestite = [
                (c, gcd.collaboratori_di(c.id))
                for c in gc.tutti(stato=None)
                if gcd.n_collaboratori(c.id) > 0
            ]
            return render_template(
                "clienti/cartelle_condivise.html",
                modalita="gestore",
                cartelle_gestite=cartelle_gestite,
                accessi_da_me=accessi_da_me,
                stats=gcd.statistiche(),
            )

        # Utenti con accesso limitato vedono le cartelle condivise con loro
        condivisioni = gcd.cartelle_condivise_con(u.id)
        cartelle = [
            (gc.get(id_c), accesso)
            for id_c, accesso in condivisioni
            if gc.get(id_c)
        ]
        return render_template(
            "clienti/cartelle_condivise.html",
            modalita="collaboratore",
            cartelle=cartelle,
            stats=gcd.statistiche(),
        )

    @app.route("/clienti/<id_cliente>/collaboratori", methods=["GET", "POST"])
    def gestione_collaboratori(id_cliente):
        """
        Gestione collaboratori di una cartella cliente.
        Accessibile a chi ha il permesso globale clienti.scrivi
        oppure è GESTORE della specifica cartella.
        """
        gc = get_clienti()
        c = gc.get(id_cliente)
        if not c:
            flash("Cliente non trovato.", "warning")
            return redirect(url_for("lista_clienti"))

        u = g.utente_corrente
        puo_gestire = (
            u.ha_permesso("clienti.scrivi")
            or get_condivisioni().ha_accesso(u.id, id_cliente, RuoloCondivisione.GESTORE)
        )
        if not puo_gestire:
            flash("Non hai il permesso di gestire i collaboratori di questa cartella.", "danger")
            return redirect(url_for("dettaglio_cliente", id_cliente=id_cliente))

        gcd = get_condivisioni()
        gu = get_utenti()

        if request.method == "POST":
            azione = request.form.get("azione", "condividi")

            if azione == "condividi":
                id_dest = request.form.get("id_utente", "").strip()
                ruolo_str = request.form.get("ruolo", RuoloCondivisione.LETTURA.value)
                note = request.form.get("note", "").strip()
                # #2 — Scadenza accesso
                data_scadenza = request.form.get("data_scadenza", "").strip()
                # #9 — Tag
                tags_raw = request.form.get("tags", "").strip()
                tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
                utente_dest = gu.get(id_dest)
                if not utente_dest:
                    flash("Utente non trovato.", "danger")
                else:
                    try:
                        gcd.condividi(
                            id_cliente=id_cliente,
                            id_utente=utente_dest.id,
                            username=utente_dest.username,
                            nome_completo=utente_dest.nome_completo or utente_dest.username,
                            ruolo=RuoloCondivisione(ruolo_str),
                            condiviso_da=u.username,
                            note=note,
                            data_scadenza=data_scadenza,
                            tags=tags,
                        )
                        flash(
                            f"Cartella condivisa con {utente_dest.username} "
                            f"({RuoloCondivisione(ruolo_str).value}).",
                            "success",
                        )
                        audit("condivisione.condividi", "cliente", id_cliente,
                              dettagli=f"→ {utente_dest.username} [{ruolo_str}]"
                                       + (f" scade {data_scadenza}" if data_scadenza else ""))
                        _sync.pubblica("info", "clienti", id_cliente, u.username,
                                       messaggio=f"Cartella condivisa con {utente_dest.username}")
                        # #1 — Notifica email all'utente destinatario
                        if utente_dest.email:
                            try:
                                get_messaggi().invia_email(
                                    destinatario=utente_dest.email,
                                    oggetto=f"Cartella condivisa: {c.nome_completo}",
                                    corpo_testo=(
                                        f"Ciao {utente_dest.nome_completo or utente_dest.username},\n\n"
                                        f"{u.nome_completo or u.username} ha condiviso con te "
                                        f"la cartella cliente di {c.nome_completo} "
                                        f"con accesso {RuoloCondivisione(ruolo_str).value}.\n"
                                        + (f"L'accesso scade il {data_scadenza}.\n" if data_scadenza else "")
                                        + (f"Note: {note}\n" if note else "")
                                        + "\nAccedi allo studio per visualizzare la cartella."
                                    ),
                                    nome_destinatario=utente_dest.nome_completo or utente_dest.username,
                                )
                            except Exception:
                                pass  # Notifica email non bloccante
                    except ValueError as e:
                        flash(str(e), "danger")

            elif azione == "revoca":
                id_dest = request.form.get("id_utente", "").strip()
                utente_dest = gu.get(id_dest)
                username_dest = utente_dest.username if utente_dest else id_dest
                if gcd.revoca(id_cliente, id_dest):
                    flash(f"Accesso revocato per {username_dest}.", "success")
                    audit("condivisione.revoca", "cliente", id_cliente,
                          dettagli=f"→ {username_dest}")
                    _sync.pubblica("info", "clienti", id_cliente, u.username,
                                   messaggio=f"Accesso revocato per {username_dest}")
                    # #1 — Notifica revoca
                    if utente_dest and utente_dest.email:
                        try:
                            get_messaggi().invia_email(
                                destinatario=utente_dest.email,
                                oggetto=f"Accesso revocato: {c.nome_completo}",
                                corpo_testo=(
                                    f"Ciao {utente_dest.nome_completo or utente_dest.username},\n\n"
                                    f"Il tuo accesso alla cartella cliente di {c.nome_completo} "
                                    f"è stato revocato da {u.nome_completo or u.username}."
                                ),
                                nome_destinatario=utente_dest.nome_completo or utente_dest.username,
                            )
                        except Exception:
                            pass
                else:
                    flash("Accesso non trovato.", "warning")

            elif azione == "crea_link":
                # #6 — Crea link temporaneo
                ore = int(request.form.get("ore_validita", 72))
                ruolo_str = request.form.get("ruolo", RuoloCondivisione.LETTURA.value)
                monouso = request.form.get("monouso") == "1"
                descrizione = request.form.get("descrizione", "").strip()
                token, link = gcd.crea_link_temporaneo(
                    id_cliente=id_cliente,
                    creato_da=u.username,
                    ruolo=RuoloCondivisione(ruolo_str),
                    ore_validita=ore,
                    monouso=monouso,
                    descrizione=descrizione,
                )
                audit("condivisione.link_creato", "cliente", id_cliente,
                      dettagli=f"link {link.id} [{ruolo_str}] {ore}h")
                link_url = url_for("accesso_link_temporaneo", token=token, _external=True)
                flash(
                    f"Link creato (valido {ore}h). Copialo e invialo al destinatario.",
                    "success",
                )
                # Mostra il link nella pagina (non nel redirect)
                collaboratori = gcd.collaboratori_di(id_cliente)
                ids_collaboratori = {a.id_utente for a in collaboratori}
                tutti_utenti = [
                    ut for ut in gu.tutti(solo_attivi=True)
                    if ut.id != u.id and ut.id not in ids_collaboratori
                ]
                return render_template(
                    "clienti/collaboratori.html",
                    cliente=c,
                    collaboratori=collaboratori,
                    utenti_disponibili=tutti_utenti,
                    ruoli_condivisione=list(RuoloCondivisione),
                    link_temporanei=gcd.link_attivi_per_cliente(id_cliente),
                    nuovo_link_url=link_url,
                )

            elif azione == "revoca_link":
                id_link = request.form.get("id_link", "").strip()
                if gcd.revoca_link_temporaneo(id_link):
                    flash("Link revocato.", "success")
                    audit("condivisione.link_revocato", "cliente", id_cliente,
                          dettagli=f"link {id_link}")
                else:
                    flash("Link non trovato.", "warning")

            return redirect(url_for("gestione_collaboratori", id_cliente=id_cliente))

        # GET — mostra pagina di gestione
        collaboratori = gcd.collaboratori_di(id_cliente)
        ids_collaboratori = {a.id_utente for a in collaboratori}
        tutti_utenti = [
            ut for ut in gu.tutti(solo_attivi=True)
            if ut.id != u.id and ut.id not in ids_collaboratori
        ]
        return render_template(
            "clienti/collaboratori.html",
            cliente=c,
            collaboratori=collaboratori,
            utenti_disponibili=tutti_utenti,
            ruoli_condivisione=list(RuoloCondivisione),
            link_temporanei=gcd.link_attivi_per_cliente(id_cliente),
            nuovo_link_url=None,
        )

    # ================================================================ #6 LINK TEMPORANEI

    @app.route("/accesso/<token>")
    def accesso_link_temporaneo(token):
        """Accesso a una cartella via link temporaneo (senza login obbligatorio)."""
        gcd = get_condivisioni()
        link = gcd.verifica_link_temporaneo(token)
        if not link:
            return render_template("clienti/link_scaduto.html"), 410

        gc = get_clienti()
        cliente = gc.get(link.id_cliente)
        if not cliente:
            return render_template("clienti/link_scaduto.html"), 404

        fascicolo = None
        if link.id_fascicolo:
            gf = get_fascicoli()
            fascicolo = gf.get(link.id_fascicolo)

        audit("condivisione.link_accesso", "cliente", link.id_cliente,
              dettagli=f"link {link.id} desc={link.descrizione}")

        return render_template(
            "clienti/link_temporaneo.html",
            cliente=cliente,
            fascicolo=fascicolo,
            link=link,
            ruolo=link.ruolo,
        )

    # ================================================================ #8 EXPORT CARTELLA ZIP

    @app.route("/clienti/<id_cliente>/esporta")
    def esporta_cartella(id_cliente):
        """Esporta l'intera cartella cliente come ZIP (anagrafica + fascicoli + documenti)."""
        if not cliente_accessibile(id_cliente):
            flash("Non hai accesso a questa cartella cliente.", "danger")
            return redirect(url_for("lista_clienti"))

        gc = get_clienti()
        cliente = gc.get(id_cliente)
        if not cliente:
            flash("Cliente non trovato.", "warning")
            return redirect(url_for("lista_clienti"))

        gf = get_fascicoli()
        fascicoli_cliente = [f for f in gf.tutti() if f.id_cliente == id_cliente]

        buf = io.BytesIO()
        with _zipfile.ZipFile(buf, "w", _zipfile.ZIP_DEFLATED) as zf:
            # Anagrafica cliente
            zf.writestr(
                "anagrafica.json",
                json.dumps(cliente.__dict__ if hasattr(cliente, "__dict__") else vars(cliente),
                           default=str, ensure_ascii=False, indent=2),
            )
            # Fascicoli e documenti
            for fasc in fascicoli_cliente:
                prefix = f"fascicoli/{fasc.numero or fasc.id}/"
                fasc_dict = fasc.to_dict() if hasattr(fasc, "to_dict") else vars(fasc)
                zf.writestr(prefix + "fascicolo.json",
                            json.dumps(fasc_dict, default=str, ensure_ascii=False, indent=2))
                for doc in fasc.documenti:
                    try:
                        percorso = gf.percorso_documento(fasc.id, doc.id)
                        if percorso.exists():
                            zf.write(percorso, prefix + "documenti/" + doc.nome)
                    except (KeyError, OSError):
                        pass
            # Indice
            indice = {
                "cliente": cliente.nome_completo,
                "fascicoli": [{"id": f.id, "numero": f.numero, "titolo": f.titolo}
                               for f in fascicoli_cliente],
                "esportato_il": datetime.now().isoformat(),
                "esportato_da": g.utente_corrente.username if g.utente_corrente else "—",
            }
            zf.writestr("indice.json", json.dumps(indice, ensure_ascii=False, indent=2))

        buf.seek(0)
        audit("condivisione.esporta", "cliente", id_cliente,
              dettagli=f"ZIP cartella {cliente.nome_completo}")
        nome_zip = f"cartella_{cliente.nome_completo.replace(' ', '_')}.zip"
        return send_file(buf, as_attachment=True, download_name=nome_zip,
                         mimetype="application/zip")

    # ================================================================ #5 FASCICOLI CONDIVISI

    @app.route("/fascicoli/<id_fasc>/collaboratori", methods=["GET", "POST"])
    def gestione_collaboratori_fascicolo(id_fasc):
        """Gestione collaboratori di un singolo fascicolo."""
        gf = get_fascicoli()
        fasc = gf.get(id_fasc)
        if not fasc:
            flash("Fascicolo non trovato.", "warning")
            return redirect(url_for("lista_fascicoli"))

        u = g.utente_corrente
        puo_gestire = (
            u.ha_permesso("fascicoli.scrivi")
            or get_condivisioni().ha_accesso_fascicolo(u.id, id_fasc, RuoloCondivisione.GESTORE)
        )
        if not puo_gestire:
            flash("Non hai il permesso di gestire i collaboratori di questo fascicolo.", "danger")
            return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))

        gcd = get_condivisioni()
        gu = get_utenti()

        if request.method == "POST":
            azione = request.form.get("azione", "condividi")
            id_dest = request.form.get("id_utente", "").strip()
            utente_dest = gu.get(id_dest)

            if azione == "condividi" and utente_dest:
                ruolo_str = request.form.get("ruolo", RuoloCondivisione.LETTURA.value)
                note = request.form.get("note", "").strip()
                data_scadenza = request.form.get("data_scadenza", "").strip()
                tags = [t.strip() for t in request.form.get("tags", "").split(",") if t.strip()]
                gcd.condividi_fascicolo(
                    id_fascicolo=id_fasc,
                    id_cliente=fasc.id_cliente,
                    id_utente=utente_dest.id,
                    username=utente_dest.username,
                    nome_completo=utente_dest.nome_completo or utente_dest.username,
                    ruolo=RuoloCondivisione(ruolo_str),
                    condiviso_da=u.username,
                    note=note,
                    data_scadenza=data_scadenza,
                    tags=tags,
                )
                flash(f"Fascicolo condiviso con {utente_dest.username}.", "success")
                audit("condivisione.fascicolo.condividi", "fascicolo", id_fasc,
                      dettagli=f"→ {utente_dest.username} [{ruolo_str}]")
            elif azione == "revoca":
                username_dest = utente_dest.username if utente_dest else id_dest
                if gcd.revoca_fascicolo(id_fasc, id_dest):
                    flash(f"Accesso fascicolo revocato per {username_dest}.", "success")
                    audit("condivisione.fascicolo.revoca", "fascicolo", id_fasc,
                          dettagli=f"→ {username_dest}")
                else:
                    flash("Accesso non trovato.", "warning")
            return redirect(url_for("gestione_collaboratori_fascicolo", id_fasc=id_fasc))

        collaboratori = gcd.collaboratori_fascicolo(id_fasc)
        ids_collab = {a.id_utente for a in collaboratori}
        tutti_utenti = [
            ut for ut in gu.tutti(solo_attivi=True)
            if ut.id != u.id and ut.id not in ids_collab
        ]
        return render_template(
            "fascicoli/collaboratori_fascicolo.html",
            fascicolo=fasc,
            collaboratori=collaboratori,
            utenti_disponibili=tutti_utenti,
            ruoli_condivisione=list(RuoloCondivisione),
        )

    # ================================================================ #7 DOCUMENT VERSIONING

    @app.route("/fascicoli/<id_fasc>/documenti/<id_doc>/sostituisci", methods=["POST"])
    def sostituisci_documento(id_fasc, id_doc):
        """Sostituisce un documento mantenendo lo storico delle versioni."""
        gf = get_fascicoli()
        if "file" not in request.files or not request.files["file"].filename:
            flash("Nessun file selezionato.", "warning")
            return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))
        file = request.files["file"]
        note = request.form.get("note", "").strip()
        u = g.utente_corrente
        try:
            doc = gf.sostituisci_documento(
                id_fasc=id_fasc,
                id_doc=id_doc,
                nome_file=file.filename,
                contenuto=_encrypt_doc(file.read()),
                caricato_da=u.username if u else "",
                note=note,
            )
            flash(f"Documento '{doc.nome}' aggiornato (versione precedente archiviata).", "success")
            audit("fascicoli.documento.sostituisci", "fascicolo", id_fasc,
                  dettagli=f"doc {id_doc} → {doc.nome}")
        except (ValueError, KeyError) as e:
            flash(str(e), "danger")
        return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))

    # ================================================================ #10 API REST

    @app.route("/api/v1/clienti/<id_cliente>/condivisioni", methods=["GET"])
    def api_condivisioni_cliente(id_cliente):
        """API REST: collaboratori di una cartella cliente."""
        if not cliente_accessibile(id_cliente):
            return jsonify({"errore": "Accesso negato"}), 403
        try:
            gcd = get_condivisioni()
            collaboratori = gcd.collaboratori_di(id_cliente)
            return jsonify({
                "id_cliente": id_cliente,
                "collaboratori": [a.to_dict() for a in collaboratori],
                "n_collaboratori": len(collaboratori),
                "link_attivi": len(gcd.link_attivi_per_cliente(id_cliente)),
                "statistiche": gcd.statistiche(),
            })
        except Exception as e:
            app.logger.exception("Errore api_condivisioni_cliente: %s", e)
            return jsonify({"errore": str(e)})

    @app.route("/api/v1/clienti/<id_cliente>/condivisioni", methods=["POST"])
    def api_aggiungi_collaboratore(id_cliente):
        """API REST: aggiunge un collaboratore a una cartella cliente."""
        u = g.utente_corrente
        puo = u and (u.ha_permesso("clienti.scrivi")
                     or get_condivisioni().ha_accesso(u.id, id_cliente, RuoloCondivisione.GESTORE))
        if not puo:
            return jsonify({"errore": "Permesso insufficiente"}), 403

        data = request.get_json(silent=True) or {}
        gu = get_utenti()
        utente_dest = gu.get(data.get("id_utente", ""))
        if not utente_dest:
            return jsonify({"errore": "Utente non trovato"}), 404

        ruolo_str = data.get("ruolo", RuoloCondivisione.LETTURA.value)
        try:
            ruolo = RuoloCondivisione(ruolo_str)
        except ValueError:
            return jsonify({"errore": f"Ruolo '{ruolo_str}' non valido"}), 400

        gcd = get_condivisioni()
        gcd.condividi(
            id_cliente=id_cliente,
            id_utente=utente_dest.id,
            username=utente_dest.username,
            nome_completo=utente_dest.nome_completo or utente_dest.username,
            ruolo=ruolo,
            condiviso_da=u.username,
            note=data.get("note", ""),
            data_scadenza=data.get("data_scadenza", ""),
            tags=data.get("tags", []),
        )
        audit("condivisione.api.condividi", "cliente", id_cliente,
              dettagli=f"→ {utente_dest.username} [{ruolo_str}]")
        return jsonify({"stato": "ok", "username": utente_dest.username, "ruolo": ruolo_str}), 201

    @app.route("/api/v1/clienti/<id_cliente>/condivisioni/<id_utente>", methods=["DELETE"])
    def api_revoca_collaboratore(id_cliente, id_utente):
        """API REST: revoca accesso di un utente a una cartella cliente."""
        u = g.utente_corrente
        puo = u and (u.ha_permesso("clienti.scrivi")
                     or get_condivisioni().ha_accesso(u.id, id_cliente, RuoloCondivisione.GESTORE))
        if not puo:
            return jsonify({"errore": "Permesso insufficiente"}), 403
        try:
            rimosso = get_condivisioni().revoca(id_cliente, id_utente)
            if rimosso:
                audit("condivisione.api.revoca", "cliente", id_cliente, dettagli=f"→ {id_utente}")
                return jsonify({"stato": "ok"}), 200
            return jsonify({"errore": "Accesso non trovato"}), 404
        except Exception as e:
            app.logger.exception("Errore api_revoca_collaboratore: %s", e)
            return jsonify({"errore": str(e)})

    @app.route("/api/v1/condivisioni/statistiche")
    def api_statistiche_condivisioni():
        """API REST: statistiche globali condivisioni."""
        u = g.utente_corrente
        if not u or not u.ha_permesso("utenti.leggi"):
            return jsonify({"errore": "Permesso insufficiente"}), 403
        try:
            return jsonify(get_condivisioni().statistiche())
        except Exception as e:
            app.logger.exception("Errore api_statistiche_condivisioni: %s", e)
            return jsonify({"errore": str(e)})

    @app.route("/api/v1/condivisioni/pulizia-scaduti", methods=["POST"])
    def api_pulizia_scaduti():
        """API REST: revoca automatica accessi scaduti (utile come cron task)."""
        u = g.utente_corrente
        if not u or not u.ha_permesso("utenti.scrivi"):
            return jsonify({"errore": "Permesso insufficiente"}), 403
        try:
            gcd = get_condivisioni()
            n_scaduti = gcd.revoca_scaduti()
            n_link = gcd.pulisci_link_scaduti()
            audit("condivisione.pulizia", "sistema", "",
                  dettagli=f"rimossi {n_scaduti} accessi + {n_link} link scaduti")
            return jsonify({"accessi_rimossi": n_scaduti, "link_rimossi": n_link})
        except Exception as e:
            app.logger.exception("Errore api_pulizia_scaduti: %s", e)
            return jsonify({"errore": str(e)})

    # ================================================================ FASCICOLI

    import io

    def _fascicoli_kwargs(tmp=None):
        return dict(
            db_path=app.config["FASCICOLI_DB"],
            documents_dir=tmp or app.config["FASCICOLI_DOCS"],
            archive_dir=app.config["FASCICOLI_ARCH"],
        )

    @app.route("/fascicoli")
    def lista_fascicoli():
        gf = get_fascicoli()
        gc = get_clienti()
        testo = request.args.get("q", "").strip()
        stato_f = request.args.get("stato", "")
        tipo_f = request.args.get("tipo", "")
        stato = StatoFascicolo(stato_f) if stato_f else None
        tipo = TipoFascicolo(tipo_f) if tipo_f else None
        fascicoli = gf.cerca(testo=testo, stato=stato, tipo=tipo) if testo else gf.tutti(stato=stato, tipo=tipo)
        stats = gf.statistiche()
        scadenze = gf.fascicoli_con_scadenze_imminenti(entro_giorni=7)
        return render_template(
            "fascicoli/lista.html",
            fascicoli=fascicoli,
            stats=stats,
            scadenze=scadenze,
            q=testo,
            stato_filtro=stato_f,
            tipo_filtro=tipo_f,
            tipi=list(TipoFascicolo),
            stati=list(StatoFascicolo),
        )

    @app.route("/fascicoli/archivio")
    def lista_archivio():
        gf = get_fascicoli()
        testo = request.args.get("q", "").strip()
        fascicoli = gf.cerca(testo=testo, stato=StatoFascicolo.ARCHIVIATO, archiviati=True)
        return render_template("fascicoli/archivio.html", fascicoli=fascicoli, q=testo)

    @app.route("/fascicoli/nuovo", methods=["GET", "POST"])
    def nuovo_fascicolo():
        gc = get_clienti()
        gf = get_fascicoli()
        if request.method == "POST":
            f = request.form
            id_cliente = f.get("id_cliente", "")
            nome_cliente = ""
            if id_cliente:
                c = gc.get(id_cliente)
                nome_cliente = c.nome_completo if c else ""
            try:
                fasc = gf.nuovo(
                    titolo=f["titolo"],
                    tipo=TipoFascicolo(f["tipo"]),
                    id_cliente=id_cliente,
                    nome_cliente=nome_cliente,
                    controparte=f.get("controparte", ""),
                    tribunale=f.get("tribunale", ""),
                    numero_rg=f.get("numero_rg", ""),
                    anno_rg=int(f.get("anno_rg") or 0),
                    giudice=f.get("giudice", ""),
                    sezione=f.get("sezione", ""),
                    avvocato_referente=f.get("avvocato_referente", ""),
                    avvocato_dominus=f.get("avvocato_dominus", ""),
                    oggetto=f.get("oggetto", ""),
                    valore_causa=float(f.get("valore_causa") or 0),
                    note=f.get("note", ""),
                )
                flash(f"Fascicolo {fasc.numero} creato.", "success")
                sync_pubblica("crea", "fascicoli", fasc.id)
                # Se arriva dalla cartella cliente, torna lì
                if id_cliente:
                    return redirect(url_for("cartella_cliente", id_cliente=id_cliente))
                return redirect(url_for("dettaglio_fascicolo", id_fasc=fasc.id))
            except (ValueError, KeyError) as e:
                flash(str(e), "danger")

        clienti = gc.tutti(stato=None)
        return render_template(
            "fascicoli/form.html",
            fascicolo=None,
            clienti=clienti,
            tipi=list(TipoFascicolo),
            stati=list(StatoFascicolo),
            id_cliente_pre=request.args.get("id_cliente", ""),
        )

    @app.route("/fascicoli/<id_fasc>")
    def dettaglio_fascicolo(id_fasc):
        gf = get_fascicoli()
        gc = get_clienti()
        fasc = gf.get(id_fasc)
        if not fasc:
            flash("Fascicolo non trovato.", "warning")
            return redirect(url_for("lista_fascicoli"))
        cliente = gc.get(fasc.id_cliente) if fasc.id_cliente else None
        agenda = get_agenda()
        # appuntamenti collegati al procedimento
        apps = []
        if fasc.numero_rg:
            apps = agenda.cerca(testo=fasc.numero_rg)
        track_recente("fascicolo", id_fasc, f"{fasc.numero} — {fasc.titolo}",
                      url_for("dettaglio_fascicolo", id_fasc=id_fasc), "bi-folder2-open")
        # PEC del tribunale dal registro ReGINde
        pec_tribunale = ""
        if fasc.tribunale:
            uff = ClientReGINde().cerca_ufficio_giudiziario(fasc.tribunale)
            pec_tribunale = uff.pec if uff else ""
        from pct.checklist_atti import TUTTI_I_TEMPLATE
        parti = get_soggetti().parti_fascicolo(id_fasc)
        pst_import_dir = _pst_import_dir_for_fascicolo(fasc)
        pst_import_dir.mkdir(parents=True, exist_ok=True)
        pst_import_pending = _pst_import_pending_count(fasc)
        polisweb_importato = "Importato da PolisWeb" in (fasc.note or "")
        ha_udienza_importata = any(
            getattr(att.tipo, "value", att.tipo) == "UDIENZA"
            for att in (fasc.attivita or [])
        )
        ha_metadati_portale = any(
            getattr(dep, "documenti_portale", None)
            for dep in (fasc.depositi_pct or [])
        )
        polisweb_sync_needed = polisweb_importato and (
            not fasc.id_cliente
            or not parti
            or not fasc.attivita
            or not fasc.tribunale
            or not fasc.data_apertura
            or (ha_udienza_importata and not fasc.data_prima_udienza)
            or not ha_metadati_portale
        )
        return render_template(
            "fascicoli/dettaglio.html",
            fascicolo=fasc,
            cliente=cliente,
            apps=apps,
            tipi_doc=list(TipoDocumento),
            tipi_att=list(TipoAttivita),
            esiti=list(EsitoAttivita),
            pec_tribunale=pec_tribunale,
            checklist_templates=TUTTI_I_TEMPLATE,
            parti=parti,
            RuoloSoggetto=RuoloSoggetto,
            pst_import_pending=pst_import_pending,
            pst_portale_label=_portale_ufficiale_label(fasc),
            pst_import_dir=str(pst_import_dir),
            polisweb_sync_needed=polisweb_sync_needed,
            oggi=date.today(),
        )

    @app.route("/fascicoli/<id_fasc>/modifica", methods=["GET", "POST"])
    def modifica_fascicolo(id_fasc):
        gf = get_fascicoli()
        gc = get_clienti()
        fasc = gf.get(id_fasc)
        if not fasc:
            flash("Fascicolo non trovato.", "warning")
            return redirect(url_for("lista_fascicoli"))
        if request.method == "POST":
            f = request.form
            id_cliente = f.get("id_cliente", fasc.id_cliente)
            nome_cliente = fasc.nome_cliente
            if id_cliente:
                c = gc.get(id_cliente)
                nome_cliente = c.nome_completo if c else nome_cliente
            try:
                gf.aggiorna(id_fasc,
                    titolo=f.get("titolo", fasc.titolo),
                    tipo=TipoFascicolo(f.get("tipo", fasc.tipo.value)),
                    id_cliente=id_cliente,
                    nome_cliente=nome_cliente,
                    controparte=f.get("controparte", ""),
                    tribunale=f.get("tribunale", ""),
                    numero_rg=f.get("numero_rg", ""),
                    anno_rg=int(f.get("anno_rg") or 0),
                    giudice=f.get("giudice", ""),
                    sezione=f.get("sezione", ""),
                    avvocato_referente=f.get("avvocato_referente", ""),
                    avvocato_dominus=f.get("avvocato_dominus", ""),
                    oggetto=f.get("oggetto", ""),
                    valore_causa=float(f.get("valore_causa") or 0),
                    note=f.get("note", ""),
                )
                flash("Fascicolo aggiornato.", "success")
                sync_pubblica("modifica", "fascicoli", id_fasc)
                return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))
            except (ValueError, KeyError) as e:
                flash(str(e), "danger")

        clienti = gc.tutti(stato=None)
        return render_template(
            "fascicoli/form.html",
            fascicolo=fasc,
            clienti=clienti,
            tipi=list(TipoFascicolo),
            stati=list(StatoFascicolo),
            id_cliente_pre="",
        )

    @app.route("/fascicoli/<id_fasc>/stato", methods=["POST"])
    def cambia_stato_fascicolo(id_fasc):
        gf = get_fascicoli()
        f = request.form
        nuovo = f.get("stato")
        try:
            gf.cambia_stato(
                id_fasc,
                StatoFascicolo(nuovo),
                note=f.get("note", ""),
                avvocato=f.get("avvocato", ""),
            )
            flash("Stato aggiornato.", "success")
        except (ValueError, KeyError) as e:
            flash(str(e), "danger")
        return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))

    @app.route("/fascicoli/<id_fasc>/definisci", methods=["POST"])
    def definisci_fascicolo(id_fasc):
        gf = get_fascicoli()
        f = request.form
        try:
            gf.definisci(
                id_fasc,
                esito_finale=f.get("esito_finale", ""),
                motivo=f.get("motivo", ""),
                note=f.get("note", ""),
                avvocato=f.get("avvocato", ""),
            )
            flash("Fascicolo definito. Pronto per l'archiviazione.", "success")
        except (ValueError, KeyError) as e:
            flash(str(e), "danger")
        return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))

    @app.route("/fascicoli/<id_fasc>/archivia", methods=["POST"])
    def archivia_fascicolo(id_fasc):
        gf = get_fascicoli()
        f = request.form
        try:
            gf.archivia(
                id_fasc,
                crea_zip=f.get("crea_zip", "1") == "1",
                avvocato=f.get("avvocato", ""),
            )
            flash("Fascicolo archiviato con successo.", "success")
            return redirect(url_for("lista_archivio"))
        except (ValueError, KeyError) as e:
            flash(str(e), "danger")
            return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))

    @app.route("/fascicoli/<id_fasc>/ripristina", methods=["POST"])
    def ripristina_fascicolo(id_fasc):
        gf = get_fascicoli()
        try:
            gf.ripristina_da_archivio(id_fasc, avvocato=request.form.get("avvocato", ""))
            flash("Fascicolo ripristinato dall'archivio.", "success")
            return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))
        except (ValueError, KeyError) as e:
            flash(str(e), "danger")
            return redirect(url_for("lista_archivio"))

    @app.route("/fascicoli/<id_fasc>/elimina", methods=["POST"])
    def elimina_fascicolo(id_fasc):
        gf = get_fascicoli()
        try:
            gf.elimina(id_fasc)
            flash("Fascicolo eliminato.", "success")
            sync_pubblica("elimina", "fascicoli", id_fasc)
        except KeyError as e:
            flash(str(e), "danger")
        return redirect(url_for("lista_fascicoli"))

    # ---- Documenti

    @app.route("/fascicoli/<id_fasc>/documenti/carica", methods=["POST"])
    def carica_documento(id_fasc):
        gf = get_fascicoli()
        if "file" not in request.files:
            flash("Nessun file selezionato.", "warning")
            return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))
        file = request.files["file"]
        if not file.filename:
            flash("Nome file non valido.", "warning")
            return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))
        f = request.form
        u = g.utente_corrente
        try:
            raw = file.read()
            tipo_doc = TipoDocumento(f.get("tipo_doc", "ALTRO"))
            doc = _salva_documento_fascicolo(
                gf=gf,
                id_fasc=id_fasc,
                nome_file=file.filename,
                raw=raw,
                tipo_doc=tipo_doc,
                note=f.get("note", ""),
                data_documento=f.get("data_documento", ""),
                firmato=f.get("firmato") == "1",
                caricato_da=u.username if u else "",
            )
            flash(f"Documento '{file.filename}' caricato.", "success")
            audit("fascicoli.documento.carica", "fascicolo", id_fasc,
                  dettagli=f"file: {file.filename}")
        except (ValueError, KeyError) as e:
            flash(str(e), "danger")
        return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))

    @app.route("/fascicoli/<id_fasc>/documenti/importa-portale", methods=["POST"])
    def importa_documenti_portale(id_fasc):
        gf = get_fascicoli()
        fasc = gf.get(id_fasc)
        if not fasc:
            flash("Fascicolo non trovato.", "warning")
            return redirect(url_for("lista_fascicoli"))

        u = g.utente_corrente
        fonte = _portale_ufficiale_label(fasc)
        note_importazione = (request.form.get("note_importazione", "") or "").strip()
        uploaded_items: list[dict] = []

        for storage in request.files.getlist("files"):
            if not storage or not storage.filename:
                continue
            payload = storage.read()
            if not payload:
                continue
            uploaded_items.extend(
                _espandi_file_importato_portale(
                    nome_file=storage.filename,
                    contenuto=payload,
                    data_documento=date.today().isoformat(),
                    origine=f"upload:{storage.filename}",
                )
            )

        staging_items: list[dict] = []
        staging_dir = _pst_import_dir_for_fascicolo(fasc)
        usa_staging = not uploaded_items
        if usa_staging:
            staging_items, staging_dir = _leggi_staging_documenti_portale(fasc)

        items = uploaded_items or staging_items
        if not items:
            flash(
                f"Nessun file ufficiale trovato. Seleziona i download del {fonte} oppure riprova dopo averli copiati nella inbox tecnica del fascicolo.",
                "warning",
            )
            return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))

        try:
            documenti_creati: list[Documento] = []
            for item in items:
                nome = item.get("nome", "").strip()
                payload = item.get("contenuto", b"")
                if not nome or not payload:
                    continue
                tipo_doc = _tipo_documento_da_nome_portale(nome)
                note_doc = [f"Importato da {fonte} il {date.today().isoformat()}"]
                if note_importazione:
                    note_doc.append(note_importazione)
                origine = (item.get("origine", "") or "").strip()
                if origine and origine != nome:
                    note_doc.append(f"Origine: {origine}")
                documenti_creati.append(
                    _salva_documento_fascicolo(
                        gf=gf,
                        id_fasc=id_fasc,
                        nome_file=nome,
                        raw=payload,
                        tipo_doc=tipo_doc,
                        note=" | ".join(note_doc),
                        data_documento=item.get("data_documento", "") or date.today().isoformat(),
                        firmato=nome.lower().endswith(".p7m"),
                        caricato_da=u.username if u else "",
                    )
                )

            if not documenti_creati:
                flash("I file selezionati non contengono documenti importabili.", "warning")
                return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))

            pec_tribunale = ""
            if fasc.tribunale:
                try:
                    uff = ClientReGINde().cerca_ufficio_giudiziario(fasc.tribunale)
                    pec_tribunale = uff.pec if uff else ""
                except Exception:
                    pec_tribunale = ""

            tipo_atto = _tipo_lotto_portale(fasc)
            principale = next(
                (
                    doc.nome
                    for doc in documenti_creati
                    if doc.tipo
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
                ),
                documenti_creati[0].nome,
            )
            descrizione_lotto = (
                f"{len(documenti_creati)} documenti ufficiali acquisiti da {fonte}."
                + (f" {note_importazione}" if note_importazione else "")
            ).strip()
            deposito = gf.registra_import_documenti_portale(
                id_fasc=id_fasc,
                fonte=fonte,
                documenti_ids=[doc.id for doc in documenti_creati],
                tipo_atto=tipo_atto,
                note=descrizione_lotto,
                registrato_da=u.username if u else "",
                pec_destinatario=pec_tribunale,
                nome_atto_principale=principale,
            )

            staging_archived = ""
            if usa_staging:
                staging_archived = _archivia_staging_documenti_portale(staging_dir)

            audit(
                "fascicoli.documento.importa_portale",
                "fascicolo",
                id_fasc,
                dettagli=f"{fonte}: {len(documenti_creati)} file — lotto {deposito.id}",
            )
            _sync.pubblica("modifica", "fascicoli", id_fasc, utente=u.username if u else "")
            if staging_archived:
                flash(
                    f"Importati {len(documenti_creati)} file ufficiali da {fonte}. Inbox temporanea archiviata.",
                    "success",
                )
            else:
                flash(f"Importati {len(documenti_creati)} file ufficiali da {fonte}.", "success")
        except (ValueError, KeyError) as e:
            flash(str(e), "danger")
        except Exception as e:
            app.logger.exception("Errore importa_documenti_portale %s: %s", id_fasc, e)
            flash(f"Errore importazione file ufficiali: {e}", "danger")
        return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))

    @app.route("/fascicoli/<id_fasc>/documenti/<id_doc>/scarica")
    def scarica_documento(id_fasc, id_doc):
        gf = get_fascicoli()
        try:
            percorso = gf.percorso_documento(id_fasc, id_doc)
            fasc = gf.get(id_fasc)
            doc = next(d for d in fasc.documenti if d.id == id_doc)
            data = _decrypt_doc(percorso.read_bytes())
            audit("fascicoli.documento.scarica", "fascicolo", id_fasc,
                  dettagli=f"doc {id_doc} — {doc.nome}")
            return send_file(io.BytesIO(data), as_attachment=True, download_name=doc.nome)
        except (KeyError, StopIteration, ValueError) as e:
            flash(str(e), "danger")
            return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))

    @app.route("/fascicoli/<id_fasc>/documenti/<id_doc>/visualizza")
    def visualizza_documento(id_fasc, id_doc):
        """Serve il documento decriptato inline per la visualizzazione nel browser."""
        gf = get_fascicoli()
        try:
            percorso = gf.percorso_documento(id_fasc, id_doc)
            fasc = gf.get(id_fasc)
            doc = next(d for d in fasc.documenti if d.id == id_doc)
            data = _decrypt_doc(percorso.read_bytes())
            nome = doc.nome.lower()
            if nome.endswith(".pdf"):
                mime = "application/pdf"
            elif nome.endswith((".jpg", ".jpeg")):
                mime = "image/jpeg"
            elif nome.endswith(".png"):
                mime = "image/png"
            elif nome.endswith(".gif"):
                mime = "image/gif"
            else:
                # Formato non visualizzabile inline: scarica normalmente
                return send_file(io.BytesIO(data), as_attachment=True, download_name=doc.nome)
            audit("fascicoli.documento.visualizza", "fascicolo", id_fasc,
                  dettagli=f"doc {id_doc} — {doc.nome}")
            return send_file(io.BytesIO(data), mimetype=mime, as_attachment=False,
                             download_name=doc.nome)
        except (KeyError, StopIteration, ValueError) as e:
            return str(e), 404

    # ---- Editor inline documenti

    @app.route("/fascicoli/<id_fasc>/documenti/<id_doc>/editor")
    def editor_documento(id_fasc, id_doc):
        """Apre l'editor inline per il documento (solo formati supportati)."""
        from pct.editor import estensione_editabile
        gf = get_fascicoli()
        try:
            fasc = gf.get(id_fasc)
            if not fasc:
                flash("Fascicolo non trovato.", "warning")
                return redirect(url_for("lista_fascicoli"))
            doc = next((d for d in fasc.documenti if d.id == id_doc), None)
            if not doc:
                flash("Documento non trovato.", "warning")
                return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))
            if not estensione_editabile(doc.nome):
                flash(f"Formato '{doc.nome.split('.')[-1].upper()}' non supportato dall'editor.", "warning")
                return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))
            return render_template(
                "fascicoli/editor_documento.html",
                id_fasc=id_fasc,
                fasc=fasc,
                doc=doc,
                oggi=date.today(),
            )
        except Exception as e:
            app.logger.exception("Errore editor_documento: %s", e)
            flash(str(e), "danger")
            return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))

    @app.route("/fascicoli/<id_fasc>/documenti/<id_doc>/converti-pdfa", methods=["POST"])
    def converti_documento_pdfa(id_fasc, id_doc):
        """Converte un documento PDF in PDF/A-2B tramite Ghostscript (D.M. 44/2011 art. 12)."""
        from pct.validazione import converti_pdfa
        gf = get_fascicoli()
        try:
            fasc = gf.get(id_fasc)
            if not fasc:
                flash("Fascicolo non trovato.", "warning")
                return redirect(url_for("lista_fascicoli"))
            doc = next((d for d in fasc.documenti if d.id == id_doc), None)
            if not doc:
                flash("Documento non trovato.", "warning")
                return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))
            if not doc.nome.lower().endswith(".pdf"):
                flash(f"La conversione PDF/A è disponibile solo per file PDF (file: {doc.nome}).", "warning")
                return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))
            percorso = gf.percorso_documento(id_fasc, id_doc)
            esito = converti_pdfa(str(percorso))
            if esito["ok"]:
                flash(f"Documento convertito in PDF/A-2B con successo. {esito['messaggio']}", "success")
                audit("documento.converti_pdfa", id_fasc=id_fasc, id_doc=id_doc, nome=doc.nome)
            else:
                flash(f"Conversione PDF/A non riuscita: {esito['messaggio']}", "danger")
        except Exception as e:
            app.logger.exception("Errore converti_documento_pdfa: %s", e)
            flash(f"Errore durante la conversione: {e}", "danger")
        return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))

    @app.route("/api/editor/<id_fasc>/<id_doc>/html")
    def api_editor_carica_html(id_fasc, id_doc):
        """Restituisce il contenuto HTML del documento per l'editor."""
        from pct.editor import documento_to_html
        gf = get_fascicoli()
        try:
            percorso = gf.percorso_documento(id_fasc, id_doc)
            fasc = gf.get(id_fasc)
            doc = next(d for d in fasc.documenti if d.id == id_doc)
            raw = _decrypt_doc(percorso.read_bytes())
            html, avvisi, meta = documento_to_html(raw, doc.nome)
            return jsonify({"ok": True, "html": html, "avvisi": avvisi,
                            "nome": doc.nome, "meta": meta})
        except Exception as e:
            app.logger.exception("Errore api_editor_carica_html: %s", e)
            return jsonify({"ok": False, "html": f"<p>{e}</p>", "avvisi": [str(e)], "meta": {}})

    @app.route("/api/editor/<id_fasc>/<id_doc>/salva", methods=["POST"])
    def api_editor_salva(id_fasc, id_doc):
        """Salva il contenuto HTML come nuova versione del documento (.docx o .html)."""
        from pct.editor import html_to_docx
        gf = get_fascicoli()
        u = g.utente_corrente
        try:
            body = request.get_json(force=True) or {}
            html = body.get("html", "")
            auto = body.get("auto", False)

            fasc = gf.get(id_fasc)
            doc = next(d for d in fasc.documenti if d.id == id_doc)

            nome = doc.nome
            ext = nome.rsplit(".", 1)[-1].lower() if "." in nome else ""

            if ext == "docx":
                contenuto_raw = html_to_docx(html, titolo=nome.rsplit(".", 1)[0])
                nome_salvato = nome
            elif ext == "pdf":
                from pct.editor import html_to_pdf
                contenuto_raw = html_to_pdf(html, titolo=nome.rsplit(".", 1)[0])
                nome_salvato = nome  # rimane .pdf
            else:
                # Per .txt e altri: salva come .html
                contenuto_raw = html.encode("utf-8")
                nome_salvato = nome.rsplit(".", 1)[0] + ".html" if "." in nome else nome + ".html"

            contenuto_enc = _encrypt_doc(contenuto_raw)
            doc_salvato = gf.sostituisci_documento(
                id_fasc, id_doc,
                nome_file=nome_salvato,
                contenuto=contenuto_enc,
                caricato_da=u.username if u else "editor",
                note="Salvato dall'editor" + (" (auto)" if auto else ""),
            )
            # Aggiorna OCR index
            _accoda_ocr(
                percorso=str(gf.percorso_documento(id_fasc, doc_salvato.id)),
                hash_sha256=doc_salvato.hash_sha256,
                id_fasc=id_fasc,
                id_doc=doc_salvato.id,
                nome_doc=doc_salvato.nome,
                tipo_doc=doc_salvato.tipo.value,
                index_path=app.config["SEARCH_INDEX"],
            )
            audit("fascicoli.documento.editor_salva", "fascicolo", id_fasc,
                  dettagli=f"doc {id_doc} — {nome}")
            return jsonify({"ok": True, "auto": auto})
        except Exception as e:
            app.logger.exception("Errore api_editor_salva: %s", e)
            return jsonify({"ok": False, "errore": str(e)})

    @app.route("/api/editor/<id_fasc>/<id_doc>/pdf", methods=["POST"])
    def api_editor_pdf(id_fasc, id_doc):
        """Genera PDF dal contenuto HTML dell'editor."""
        from pct.editor import html_to_pdf
        try:
            body = request.get_json(force=True) or {}
            html = body.get("html", "<p></p>")
            gf = get_fascicoli()
            fasc = gf.get(id_fasc)
            doc = next((d for d in fasc.documenti if d.id == id_doc), None)
            titolo = doc.nome.rsplit(".", 1)[0] if doc else "documento"
            pdf_bytes = html_to_pdf(html, titolo=titolo)
            nome_pdf = titolo + ".pdf"
            audit("fascicoli.documento.editor_pdf", "fascicolo", id_fasc,
                  dettagli=f"doc {id_doc}")
            return send_file(
                io.BytesIO(pdf_bytes),
                mimetype="application/pdf",
                as_attachment=True,
                download_name=nome_pdf,
            )
        except ImportError as e:
            return jsonify({"errore": str(e)}), 503
        except Exception as e:
            app.logger.exception("Errore api_editor_pdf: %s", e)
            return str(e), 500

    @app.route("/api/editor/<id_fasc>/<id_doc>/docx", methods=["POST"])
    def api_editor_docx(id_fasc, id_doc):
        """Esporta il contenuto HTML come file .docx scaricabile."""
        from pct.editor import html_to_docx
        try:
            body = request.get_json(force=True) or {}
            html = body.get("html", "<p></p>")
            gf = get_fascicoli()
            fasc = gf.get(id_fasc)
            doc = next((d for d in fasc.documenti if d.id == id_doc), None)
            titolo = doc.nome.rsplit(".", 1)[0] if doc else "documento"
            docx_bytes = html_to_docx(html, titolo=titolo)
            nome_docx = titolo + ".docx"
            audit("fascicoli.documento.editor_docx", "fascicolo", id_fasc,
                  dettagli=f"doc {id_doc}")
            return send_file(
                io.BytesIO(docx_bytes),
                mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                as_attachment=True,
                download_name=nome_docx,
            )
        except ImportError as e:
            return jsonify({"errore": str(e)}), 503
        except Exception as e:
            app.logger.exception("Errore api_editor_docx: %s", e)
            return str(e), 500

    # ── PKCS#11 — firma in-device (Aruba Key) ────────────────────────────────

    @app.route("/api/firma/pkcs11/status", methods=["GET"])
    def api_pkcs11_status():
        """
        Controlla la disponibilità della libreria PKCS#11 e lista i token connessi.
        Non richiede PIN — usa solo operazioni pubbliche sul token.

        Response JSON:
          { disponibile, libreria, token: [{slot_id, label, manufacturer, ha_cert}] }
        """
        try:
            from pct.firma_pkcs11 import libreria_disponibile, lista_token
            cfg_studio = get_config_studio().config
            firma_cfg  = cfg_studio.firma if cfg_studio else None

            # Usa la libreria configurata o quella auto-rilevata
            lib_path = (
                getattr(firma_cfg, "pkcs11_library", "") or libreria_disponibile()
                if firma_cfg else libreria_disponibile()
            )

            if not lib_path:
                return jsonify({
                    "disponibile": False,
                    "libreria": None,
                    "token": [],
                    "messaggio": (
                        "Nessuna libreria PKCS#11 trovata. "
                        "Installare opensc (apt install opensc) e pcscd, oppure "
                        "specificare il percorso in Impostazioni → Firma Digitale → Token PKCS#11."
                    ),
                })

            token_list = lista_token(lib_path)
            return jsonify({
                "disponibile": True,
                "libreria": lib_path,
                "token": [t.as_dict() for t in token_list],
                "messaggio": (
                    f"{len(token_list)} token rilevato/i."
                    if token_list else
                    "Libreria PKCS#11 disponibile ma nessun token inserito. "
                    "Inserire smart card/token o collegare il lettore."
                ),
            })
        except Exception as e:
            app.logger.exception("Errore api_pkcs11_status: %s", e)
            return jsonify({"disponibile": False, "libreria": None, "token": [],
                            "messaggio": str(e)})

    @app.route("/api/firma/pkcs11/firma-documento", methods=["POST"])
    def api_pkcs11_firma_documento():
        """
        Firma un documento del fascicolo tramite token PKCS#11 (in-device).

        Request JSON:
          { fascicolo_id, documento_id, pin, slot_id? }

        Response JSON:
          { ok, nome_firmato, intestatario, scadenza, messaggio }

        Il PIN non viene mai salvato — viene usato una volta per la sessione e scartato.
        """
        try:
            from pct.firma_pkcs11 import FirmaPKCS11, libreria_disponibile

            data          = request.get_json(force=True) or {}
            id_fasc       = data.get("fascicolo_id", "").strip()
            id_doc        = data.get("documento_id", "").strip()
            pin           = data.get("pin", "")
            slot_raw      = data.get("slot_id")

            if not id_fasc or not id_doc:
                return jsonify({"ok": False, "messaggio": "fascicolo_id e documento_id obbligatori."}), 400
            if not pin:
                return jsonify({"ok": False, "messaggio": "PIN obbligatorio per la firma in-device."}), 400

            u  = g.utente_corrente
            gf = get_fascicoli()
            fasc = gf.get(id_fasc)
            if not fasc:
                return jsonify({"ok": False, "messaggio": "Fascicolo non trovato."}), 404

            doc = next((d for d in fasc.documenti if d.id == id_doc), None)
            if not doc:
                return jsonify({"ok": False, "messaggio": "Documento non trovato."}), 404

            if doc.firmato_digitalmente:
                return jsonify({
                    "ok": True,
                    "nome_firmato": doc.nome,
                    "messaggio": "Documento già firmato digitalmente.",
                })

            # Percorso fisico del documento
            doc_path = gf.percorso_documento(id_fasc, id_doc)
            if not doc_path or not doc_path.exists():
                return jsonify({"ok": False,
                                "messaggio": "File documento non trovato su disco."}), 404

            # Config PKCS#11
            cfg_studio = get_config_studio().config
            firma_cfg  = cfg_studio.firma if cfg_studio else None
            lib_path   = (
                getattr(firma_cfg, "pkcs11_library", "") or libreria_disponibile()
                if firma_cfg else libreria_disponibile()
            )
            if not lib_path:
                return jsonify({
                    "ok": False,
                    "messaggio": "Libreria PKCS#11 non disponibile. Installare opensc.",
                }), 500

            slot = None
            if slot_raw is not None:
                try:
                    slot = int(slot_raw)
                except (ValueError, TypeError):
                    pass
            elif firma_cfg:
                slot_cfg = getattr(firma_cfg, "pkcs11_slot", "")
                if str(slot_cfg).strip().isdigit():
                    slot = int(slot_cfg)

            label = getattr(firma_cfg, "pkcs11_label", "") if firma_cfg else None

            # Leggi il documento
            with open(doc_path, "rb") as fh:
                contenuto = fh.read()

            # Firma in-device (PIN usato e scartato in questa funzione)
            with FirmaPKCS11(library_path=lib_path, slot_id=slot,
                             pin=pin, label=label or None) as firma:
                stato_cert = firma.verifica_scadenza()
                if stato_cert["scaduto"]:
                    return jsonify({
                        "ok": False,
                        "messaggio": stato_cert["messaggio"],
                    })

                # Salva la versione firmata (aggiunge .p7m)
                output_path = str(doc_path) + ".p7m"
                firma.salva_documento_firmato(contenuto, str(doc_path), formato="cades")
                # salva_documento_firmato aggiunge .p7m se non presente
                firmato_path = output_path if output_path.endswith(".p7m") else str(doc_path) + ".p7m"

                intestatario = firma.intestatario
                scadenza_str = stato_cert["scadenza"]

            # Aggiorna il record documento nel fascicolo
            import os as _os
            nome_firmato = doc.nome
            if not nome_firmato.endswith(".p7m"):
                nome_firmato = nome_firmato + ".p7m"
            doc.nome = nome_firmato
            doc.firmato_digitalmente = True
            if _os.path.exists(firmato_path):
                doc.dimensione_bytes = _os.path.getsize(firmato_path)

            fasc.modificato_il = __import__("datetime").datetime.now().isoformat()
            gf._salva()

            audit("firma.pkcs11", "documento", id_doc,
                  dettagli=f"Firmato via PKCS#11 da {intestatario} — {nome_firmato}")
            _sync.pubblica("modifica", "fascicoli", id_fasc,
                           utente=u.username if u else "")

            return jsonify({
                "ok": True,
                "nome_firmato": nome_firmato,
                "intestatario": intestatario,
                "scadenza": scadenza_str,
                "avviso_scadenza": stato_cert.get("avviso_imminente", False),
                "messaggio": (
                    f"Documento firmato con successo da {intestatario}. "
                    + (stato_cert["messaggio"] if stato_cert.get("avviso_imminente") else "")
                ),
            })

        except Exception as e:
            app.logger.exception("Errore api_pkcs11_firma_documento: %s", e)
            return jsonify({"ok": False, "messaggio": str(e)})

    # ─────────────────────────────────────────────────────────────────────────

    @app.route("/fascicoli/<id_fasc>/documenti/<id_doc>/firma", methods=["POST"])
    def firma_documento(id_fasc, id_doc):
        """Carica la versione firmata (.p7m/.pdf) e marca il documento come firmato."""
        gf = get_fascicoli()
        u = g.utente_corrente
        try:
            if "file" in request.files and request.files["file"].filename:
                file = request.files["file"]
                note = request.form.get("note", "Versione firmata per deposito").strip()
                gf.sostituisci_documento(
                    id_fasc=id_fasc,
                    id_doc=id_doc,
                    nome_file=file.filename,
                    contenuto=_encrypt_doc(file.read()),
                    caricato_da=u.username if u else "",
                    note=note,
                )
            doc = gf.segna_firmato(id_fasc, id_doc)
            flash(f"Documento '{doc.nome}' contrassegnato come firmato per deposito.", "success")
            audit("fascicoli.documento.firma", "fascicolo", id_fasc,
                  dettagli=f"doc {id_doc} — {doc.nome}")
            _sync.pubblica("modifica", "fascicoli", id_fasc, utente=u.username if u else "")
        except (ValueError, KeyError) as e:
            flash(str(e), "danger")
        return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))

    @app.route("/fascicoli/<id_fasc>/documenti/<id_doc>/elimina", methods=["POST"])
    def elimina_documento(id_fasc, id_doc):
        gf = get_fascicoli()
        try:
            gf.rimuovi_documento(id_fasc, id_doc)
            flash("Documento eliminato.", "success")
        except KeyError as e:
            flash(str(e), "danger")
        return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))

    # ---- Attività processuali

    @app.route("/fascicoli/<id_fasc>/attivita/aggiungi", methods=["POST"])
    def aggiungi_attivita(id_fasc):
        gf = get_fascicoli()
        f = request.form
        try:
            gf.aggiungi_attivita(
                id_fasc,
                tipo=TipoAttivita(f["tipo"]),
                data=f["data"],
                titolo=f["titolo"],
                descrizione=f.get("descrizione", ""),
                luogo=f.get("luogo", ""),
                esito=EsitoAttivita(f.get("esito", "IN_ATTESA")),
                note=f.get("note", ""),
                avvocato=f.get("avvocato", ""),
                id_appuntamento=f.get("id_appuntamento", ""),
            )
            flash("Attività aggiunta.", "success")
        except (ValueError, KeyError) as e:
            flash(str(e), "danger")
        return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))

    @app.route("/fascicoli/<id_fasc>/attivita/<id_att>/esito", methods=["POST"])
    def aggiorna_esito_attivita(id_fasc, id_att):
        gf = get_fascicoli()
        try:
            gf.aggiorna_attivita(
                id_fasc, id_att,
                esito=EsitoAttivita(request.form["esito"]),
                note=request.form.get("note", ""),
            )
            flash("Esito aggiornato.", "success")
        except (ValueError, KeyError) as e:
            flash(str(e), "danger")
        return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))

    # ---- Attestazione di conformità

    @app.route("/fascicoli/<id_fasc>/documenti/<id_doc>/attestazione", methods=["POST"])
    def attestazione_conformita(id_fasc, id_doc):
        """
        Appone un'attestazione di conformità al documento PDF e lo restituisce.
        Utilizza pyhanko per aggiungere un'annotazione visibile al PDF.
        """
        gf = get_fascicoli()
        u = g.utente_corrente
        try:
            percorso = gf.percorso_documento(id_fasc, id_doc)
            fasc = gf.get(id_fasc)
            doc = next(d for d in fasc.documenti if d.id == id_doc)
            data_raw = _decrypt_doc(percorso.read_bytes())

            nome_avvocato = (u.nome_completo if hasattr(u, "nome_completo") else u.username) if u else "Avvocato"
            data_oggi = __import__("datetime").date.today().strftime("%d/%m/%Y")
            testo = (
                f"Copia conforme all'originale\n"
                f"ai sensi dell'art. 22, co. 2, D.Lgs. 82/2005 (CAD)\n"
                f"Avv. {nome_avvocato} — {data_oggi}"
            )

            try:
                from pyhanko.pdf_utils.reader import PdfFileReader
                from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
                from pyhanko.stamp import TextStamp, TextStampStyle, TextStampBox
                from pyhanko.pdf_utils import generic

                buf_in = io.BytesIO(data_raw)
                reader = PdfFileReader(buf_in)
                writer = IncrementalPdfFileWriter(buf_in)

                style = TextStampStyle(
                    stamp_text=testo,
                    background_opacity=0.85,
                )
                stamp = TextStamp(
                    writer=writer,
                    style=style,
                    dest_page=0,
                    x=20, y=20,
                    width=350, height=65,
                )
                stamp.apply()

                buf_out = io.BytesIO()
                writer.write(buf_out)
                buf_out.seek(0)
                attested = buf_out.read()

            except Exception:
                # Fallback: aggiunge una pagina di attestazione con reportlab
                import reportlab.lib.pagesizes as pagesizes
                from reportlab.pdfgen import canvas as rlcanvas
                buf_att = io.BytesIO()
                c = rlcanvas.Canvas(buf_att, pagesize=pagesizes.A4)
                c.setFont("Helvetica-Bold", 11)
                c.drawString(50, 780, "ATTESTAZIONE DI CONFORMITÀ")
                c.setFont("Helvetica", 10)
                for i, riga in enumerate(testo.split("\n")):
                    c.drawString(50, 760 - i * 18, riga)
                c.save()
                buf_att.seek(0)
                # Combina con reportlab
                try:
                    from reportlab.lib.pagesizes import A4
                    attested = data_raw + buf_att.read()
                except Exception:
                    attested = data_raw

            audit("fascicoli.documento.attestazione", "fascicolo", id_fasc,
                  dettagli=f"doc {id_doc} — {doc.nome}")
            nome_out = doc.nome.replace(".pdf", "_conf.pdf") if doc.nome.endswith(".pdf") else doc.nome + "_conf.pdf"
            return send_file(io.BytesIO(attested), mimetype="application/pdf",
                             as_attachment=True, download_name=nome_out)
        except (KeyError, StopIteration, ValueError) as e:
            flash(str(e), "danger")
            return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))

    # ---- Registra esito deposito PCT

    @app.route("/fascicoli/<id_fasc>/depositi/aggiungi", methods=["POST"])
    def aggiungi_esito_deposito(id_fasc):
        """Registra manualmente un esito di deposito telematico nel fascicolo."""
        gf = get_fascicoli()
        u = g.utente_corrente
        f = request.form
        try:
            gf.aggiungi_esito_deposito(
                id_fasc=id_fasc,
                tipo_atto=f.get("tipo_atto", "ATTO"),
                pec_destinatario=f.get("pec_destinatario", ""),
                stato=f.get("stato", "INVIATO"),
                messaggio=f.get("messaggio", ""),
                ricevuta_accettazione=f.get("ricevuta_accettazione", ""),
                ricevuta_consegna=f.get("ricevuta_consegna", ""),
                ricevuta_controlli_automatici=f.get("ricevuta_controlli_automatici", ""),
                esito_controlli=f.get("esito_controlli", ""),
                ricevuta_cancelleria=f.get("ricevuta_cancelleria", ""),
                note=f.get("note", ""),
                registrato_da=u.username if u else "",
            )
            flash("Esito deposito registrato nel fascicolo.", "success")
            audit("fascicoli.deposito.aggiungi", "fascicolo", id_fasc)
            _sync.pubblica("modifica", "fascicoli", id_fasc, utente=u.username if u else "")
        except (ValueError, KeyError) as e:
            flash(str(e), "danger")
        return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))

    @app.route("/fascicoli/<id_fasc>/depositi/<id_dep>/modifica", methods=["POST"])
    def modifica_esito_deposito(id_fasc, id_dep):
        """Modifica manualmente un esito di deposito telematico nel fascicolo."""
        gf = get_fascicoli()
        u = g.utente_corrente
        f = request.form
        try:
            gf.modifica_esito_deposito(
                id_fasc=id_fasc,
                id_dep=id_dep,
                tipo_atto=f.get("tipo_atto", "ATTO"),
                pec_destinatario=f.get("pec_destinatario", ""),
                stato=f.get("stato", "INVIATO"),
                messaggio=f.get("messaggio", ""),
                ricevuta_accettazione=f.get("ricevuta_accettazione", ""),
                ricevuta_consegna=f.get("ricevuta_consegna", ""),
                ricevuta_controlli_automatici=f.get("ricevuta_controlli_automatici", ""),
                esito_controlli=f.get("esito_controlli", ""),
                ricevuta_cancelleria=f.get("ricevuta_cancelleria", ""),
                note=f.get("note", ""),
                modificato_da=u.username if u else "",
            )
            flash("Deposito aggiornato.", "success")
            audit("fascicoli.deposito.modifica", "fascicolo", id_fasc)
            _sync.pubblica("modifica", "fascicoli", id_fasc, utente=u.username if u else "")
        except (ValueError, KeyError) as e:
            flash(str(e), "danger")
        return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))

    # ---- Wizard deposito telematico PCT

    @app.route("/fascicoli/<id_fasc>/deposito/genera-busta", methods=["POST"])
    def deposito_genera_busta(id_fasc):
        """
        Genera la busta telematica (.enc) reale da importare in Consolle dell'Avvocato.
        Restituisce il file come download diretto.
        """
        import os as _os
        import tempfile as _tmp
        from flask import send_file as _send_file
        from pct.busta import BustaTelematica, DatiBusta, Allegato as AllegatoBusta

        gf   = get_fascicoli()
        u    = g.utente_corrente
        f    = request.form
        fasc = gf.get(id_fasc)
        if not fasc:
            flash("Fascicolo non trovato.", "danger")
            return redirect(url_for("lista_fascicoli"))

        tipo_atto       = f.get("tipo_atto", "ATTO").strip()
        codice_registro = f.get("codice_registro", "RG").strip()
        oggetto         = f.get("oggetto", "").strip() or fasc.titolo
        atto_id         = f.get("atto_principale_id", "").strip()
        allegati_ids    = request.form.getlist("allegati_ids")

        if not atto_id:
            flash("Seleziona l'atto principale da includere nella busta.", "danger")
            return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))

        # Risolvi documento principale
        try:
            atto_path = str(gf.percorso_documento(id_fasc, atto_id))
        except KeyError:
            flash("Documento principale non trovato nel fascicolo.", "danger")
            return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))

        # Risolvi allegati
        allegati_busta = []
        for all_id in allegati_ids:
            if all_id == atto_id:
                continue
            try:
                all_doc  = next((d for d in fasc.documenti if d.id == all_id), None)
                all_path = str(gf.percorso_documento(id_fasc, all_id))
                allegati_busta.append(
                    AllegatoBusta(percorso=all_path,
                                  descrizione=all_doc.nome if all_doc else all_id)
                )
            except (KeyError, Exception):
                pass

        # Risolvi codice ufficio dal nome tribunale (o usa il nome direttamente)
        codice_ufficio = fasc.tribunale
        try:
            from pct.uffici_giudiziari import get_gestore as _get_uff
            _cache = _os.getenv("PCT_UFFICI_DB", "/data/uffici/uffici_giudiziari.json")
            _uff = next(
                (x for x in _get_uff(_cache).carica()
                 if x.get("nome", "").lower() == fasc.tribunale.lower()),
                None,
            )
            if _uff:
                codice_ufficio = _uff["codice"]
        except Exception:
            pass

        dati = DatiBusta(
            codice_ufficio=codice_ufficio or fasc.tribunale or "SCONOSCIUTO",
            codice_registro=codice_registro,
            oggetto=oggetto,
            tipo_atto=tipo_atto,
            atto_principale=atto_path,
            allegati=allegati_busta,
            numero_rg=fasc.numero_rg or None,
            anno_rg=fasc.anno_rg or None,
            operatore=u.username if u else "",
            cf_mittente="",
        )

        # Genera busta in directory temporanea e invia come download
        try:
            out_dir = _os.getenv("PCT_DEPOSITI_DIR", _tmp.gettempdir())
            busta   = BustaTelematica(dati)
            enc_path = busta.crea_busta(out_dir)
            nome_file = f"Busta_{fasc.numero.replace('/', '-')}_{tipo_atto}.enc"
            audit("fascicoli.deposito.genera_busta", "fascicolo", id_fasc,
                  dettagli=f"Busta {busta.id_busta[:8]} — {tipo_atto}")
            return _send_file(
                enc_path,
                as_attachment=True,
                download_name=nome_file,
                mimetype="application/octet-stream",
            )
        except Exception as exc:
            app.logger.exception("Errore genera_busta %s: %s", id_fasc, exc)
            flash(f"Errore nella generazione della busta: {exc}", "danger")
            return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))

    @app.route("/fascicoli/<id_fasc>/deposito/invia-pec", methods=["POST"])
    def deposito_invia_pec(id_fasc):
        """
        Crea la busta telematica e la invia via PEC all'ufficio giudiziario.
        Risponde sempre con JSON per essere chiamata via fetch() dal modal.
        """
        import uuid as _uuid
        import os as _os
        import tempfile as _tmp
        from datetime import datetime as _dt
        from pct.busta import BustaTelematica, DatiBusta, Allegato as AllegatoBusta
        from pct.pec import ClientPEC, ConfigPEC as PecCfg
        from pct.fascicoli import EsitoDepositoPCT

        gf   = get_fascicoli()
        u    = g.utente_corrente
        f    = request.form
        fasc = gf.get(id_fasc)
        if not fasc:
            return jsonify({"ok": False, "errore": "Fascicolo non trovato."}), 404

        tipo_atto       = f.get("tipo_atto", "ATTO").strip()
        codice_registro = f.get("codice_registro", "RG").strip()
        oggetto         = f.get("oggetto", "").strip() or fasc.titolo
        atto_id         = f.get("atto_principale_id", "").strip()
        allegati_ids    = request.form.getlist("allegati_ids")
        note            = f.get("note", "").strip()

        if not atto_id:
            return jsonify({"ok": False, "errore": "Seleziona l'atto principale."}), 400

        # Documento principale
        try:
            atto_path = str(gf.percorso_documento(id_fasc, atto_id))
        except KeyError:
            return jsonify({"ok": False, "errore": "Documento principale non trovato."}), 400

        # Allegati
        allegati_busta = []
        for all_id in allegati_ids:
            if all_id == atto_id:
                continue
            try:
                all_doc  = next((d for d in fasc.documenti if d.id == all_id), None)
                all_path = str(gf.percorso_documento(id_fasc, all_id))
                allegati_busta.append(
                    AllegatoBusta(percorso=all_path,
                                  descrizione=all_doc.nome if all_doc else all_id)
                )
            except Exception:
                pass

        # Codice ufficio e PEC tribunale
        codice_ufficio = fasc.tribunale or "SCONOSCIUTO"
        pec_dest       = ""
        try:
            from pct.uffici_giudiziari import get_gestore as _get_uff
            _cache = _os.getenv("PCT_UFFICI_DB", "/data/uffici/uffici_giudiziari.json")
            _uff = next(
                (x for x in _get_uff(_cache).carica()
                 if x.get("nome", "").lower() == fasc.tribunale.lower()),
                None,
            ) if fasc.tribunale else None
            if _uff:
                codice_ufficio = _uff.get("codice", codice_ufficio)
                pec_dest       = _uff.get("pec", "")
        except Exception:
            pass

        if not pec_dest:
            return jsonify({
                "ok": False,
                "errore": f"Indirizzo PEC non trovato per '{fasc.tribunale}'. "
                          "Verifica il tribunale nel fascicolo."
            }), 400

        # Config PEC studio
        pec_cfg    = None
        modalita_demo = False
        try:
            from pct.config_studio import GestioneConfigStudio as _GCS
            _gcs    = _GCS(app.config.get("STUDIO_CONFIG", "./config/studio.json"))
            _scfg   = _gcs.config
            pec_cfg = _scfg.pec if _scfg else None
            if not pec_cfg or not pec_cfg.indirizzo or not pec_cfg.password:
                modalita_demo = True
                pec_cfg = None
        except Exception:
            modalita_demo = True
            pec_cfg = None

        # Crea busta
        try:
            dati = DatiBusta(
                codice_ufficio=codice_ufficio,
                codice_registro=codice_registro,
                oggetto=oggetto,
                tipo_atto=tipo_atto,
                atto_principale=atto_path,
                allegati=allegati_busta,
                numero_rg=fasc.numero_rg or None,
                anno_rg=fasc.anno_rg or None,
                operatore=u.username if u else "",
                cf_mittente=getattr(pec_cfg, "cf_mittente", "") or "",
            )
            out_dir  = _os.getenv("PCT_DEPOSITI_DIR", _tmp.gettempdir())
            busta    = BustaTelematica(dati)
            enc_path = busta.crea_busta(out_dir)
        except Exception as exc:
            app.logger.exception("Errore creazione busta %s: %s", id_fasc, exc)
            return jsonify({"ok": False, "errore": f"Errore creazione busta: {exc}"}), 500

        # id_dep e ts definiti subito dopo la busta, usati da tutti i blocchi seguenti
        id_dep = busta.id_busta[:8].upper()
        ts     = _dt.now().isoformat()

        # Invia via PEC (reale o simulata)
        if modalita_demo:
            # Modalità demo: simula risposta PEC senza connessione reale
            import hashlib as _hl
            fake_mid = _hl.md5(f"{id_dep}{ts}".encode()).hexdigest()[:16].upper()
            ris = {
                "inviato": True,
                "message_id": f"DEMO-{fake_mid}@pst.giustizia.it",
                "demo": True,
            }
            app.logger.info("Deposito DEMO %s — busta creata, invio PEC simulato", id_dep)
        else:
            try:
                config_pec = PecCfg(
                    indirizzo=pec_cfg.indirizzo,
                    password=pec_cfg.password,
                    smtp_host=getattr(pec_cfg, "smtp_host", "smtp.pec.aruba.it"),
                    smtp_port=getattr(pec_cfg, "smtp_port", 465),
                    imap_host=getattr(pec_cfg, "imap_host", ""),
                    imap_port=getattr(pec_cfg, "imap_port", 993),
                    use_ssl=getattr(pec_cfg, "use_ssl", True),
                )
                client_pec = ClientPEC(config_pec)
                oggetto_pec = (
                    f"DEPOSITO TELEMATICO - {tipo_atto} - RG {fasc.numero_rg}/{fasc.anno_rg}"
                    if fasc.numero_rg and fasc.anno_rg else
                    f"DEPOSITO TELEMATICO - {tipo_atto} - {fasc.tribunale}"
                )
                ris = client_pec.invia_busta(
                    destinatario_pec=pec_dest,
                    busta_path=enc_path,
                    oggetto=oggetto_pec,
                )
                if not ris.get("inviato"):
                    errore_pec = ris.get("errore") or "Invio PEC fallito senza dettagli."
                    return jsonify({"ok": False, "errore": f"Errore PEC: {errore_pec}"}), 500
            except Exception as exc:
                app.logger.exception("Errore invio PEC %s: %s", id_fasc, exc)
                return jsonify({"ok": False, "errore": f"Errore invio PEC: {exc}"}), 500

        # Salva esito nel fascicolo
        try:
            from datetime import datetime as _dtnow
            from pct.fascicoli import (AttivitaProcessuale, EsitoAttivita,
                                       TIPO_ATTO_LABEL, _tipo_attivita_da_tipo_atto)
            _msg_demo = "[DEMO] " if modalita_demo else ""
            # Raccoglie ID e nome atto principale per il tracking
            _atto_doc = next((d for d in fasc.documenti if d.id == atto_id), None)
            _tutti_ids = [atto_id] + [aid for aid in allegati_ids if aid != atto_id]
            esito = EsitoDepositoPCT(
                id=id_dep,
                timestamp=ts,
                stato="INVIATO",
                tipo_atto=tipo_atto,
                pec_destinatario=pec_dest,
                messaggio=f"{_msg_demo}Busta {id_dep} inviata via PEC a {pec_dest}. Message-ID: {ris.get('message_id','')}",
                note=("[SIMULAZIONE DEMO — nessun atto realmente inviato] " + note).strip() if modalita_demo else note,
                registrato_da=u.username if u else "",
                documenti_ids=_tutti_ids,
                nome_atto_principale=_atto_doc.nome if _atto_doc else "",
            )
            fasc.depositi_pct.append(esito)

            # Marca i documenti inclusi con l'id del deposito
            for _doc in fasc.documenti:
                if _doc.id in _tutti_ids:
                    _doc.id_deposito_pct = id_dep

            # Auto-crea attività processuale collegata (PST: evento nel fascicolo informatico)
            _label = TIPO_ATTO_LABEL.get(tipo_atto, tipo_atto)
            fasc.attivita.append(AttivitaProcessuale(
                id=__import__("uuid").uuid4().hex[:8].upper(),
                tipo=_tipo_attivita_da_tipo_atto(tipo_atto),
                data=date.today().isoformat(),
                titolo=f"Deposito telematico — {_label}",
                descrizione=f"Tipo atto: {_label}. PEC: {pec_dest}. Busta: {id_dep}.",
                esito=EsitoAttivita.IN_ATTESA,
                id_deposito_pct=id_dep,
                avvocato=u.username if u else "",
            ))
            fasc.modificato_il = _dtnow.now().isoformat()
            gf._salva()
            audit("fascicoli.deposito.invia_pec", "fascicolo", id_fasc,
                  dettagli=f"Deposito {id_dep} — {tipo_atto} → {pec_dest}")
            _sync.pubblica("modifica", "fascicoli", id_fasc, utente=u.username if u else "")
        except Exception as exc:
            app.logger.exception("Errore salvataggio esito PEC %s: %s", id_fasc, exc)
            # L'invio è andato a buon fine anche se il salvataggio fallisce
            return jsonify({
                "ok": True,
                "demo": modalita_demo,
                "avviso": f"Busta inviata ma errore nel salvataggio: {exc}",
                "id_deposito": id_dep,
                "pec_dest": pec_dest,
                "tipo_atto": tipo_atto,
            })

        return jsonify({
            "ok": True,
            "demo": modalita_demo,
            "id_deposito": id_dep,
            "pec_dest": pec_dest,
            "tipo_atto": tipo_atto,
            "timestamp": ts,
        })

    @app.route("/fascicoli/<id_fasc>/deposito/prepara", methods=["GET"])
    def deposito_prepara(id_fasc):
        """Mostra il riepilogo documenti e la guida al deposito telematico."""
        import os as _os
        gf = get_fascicoli()
        fasc = gf.get(id_fasc)
        if not fasc:
            flash("Fascicolo non trovato.", "danger")
            return redirect(url_for("lista_fascicoli"))

        # Cerca PEC del tribunale dal nome salvato nel fascicolo
        pec_tribunale = ""
        if fasc.tribunale:
            try:
                from pct.uffici_giudiziari import get_gestore as _get_uff
                _cache = _os.getenv("PCT_UFFICI_DB", "/data/uffici/uffici_giudiziari.json")
                _uff = next(
                    (u for u in _get_uff(_cache).carica()
                     if u.get("nome", "").lower() == fasc.tribunale.lower()),
                    None,
                )
                pec_tribunale = _uff["pec"] if _uff else ""
            except Exception:
                pass

        # Verifica conformità PDF/A per ogni documento del fascicolo
        pdfa_stato: dict = {}
        try:
            from pct.validazione import verifica_pdfa, verifica_dimensione
            for doc in fasc.documenti:
                try:
                    percorso = str(gf.percorso_documento(id_fasc, doc.id))
                    pdfa = verifica_pdfa(percorso)
                    dim  = verifica_dimensione(percorso)
                    pdfa_stato[doc.id] = {**pdfa, "dimensione": dim}
                except Exception:
                    pass
        except Exception:
            pass

        # Verifica PEC studio configurata (mittente)
        pec_configurata = False
        try:
            _cfg = get_config_studio().config
            pec_configurata = bool(
                _cfg and _cfg.pec and _cfg.pec.indirizzo and _cfg.pec.password
            )
        except Exception:
            pass

        return render_template(
            "fascicoli/deposito_prepara.html",
            fascicolo=fasc,
            pec_tribunale=pec_tribunale,
            pec_configurata=pec_configurata,
            pdfa_stato=pdfa_stato,
            oggi=date.today(),
        )

    @app.route("/fascicoli/<id_fasc>/deposito/invia", methods=["POST"])
    def deposito_invia(id_fasc):
        """
        Crea la busta telematica e la invia via PEC all'ufficio giudiziario.
        In demo mode simula l'invio senza connessioni reali.
        """
        import uuid as _uuid
        from datetime import datetime as _dt
        from pct.fascicoli import EsitoDepositoPCT

        gf  = get_fascicoli()
        u   = g.utente_corrente
        f   = request.form
        fasc = gf.get(id_fasc)
        if not fasc:
            flash("Fascicolo non trovato.", "danger")
            return redirect(url_for("lista_fascicoli"))

        demo_mode        = f.get("demo_mode") == "1" or _polis_demo_mode()
        tipo_atto        = f.get("tipo_atto", "ATTO").strip()
        codice_registro  = f.get("codice_registro", "RG").strip()
        numero_rg        = f.get("numero_rg", "").strip()
        anno_rg_str      = f.get("anno_rg", "").strip()
        oggetto          = f.get("oggetto", "").strip() or fasc.titolo
        note             = f.get("note", "").strip()
        tribunale_nome   = f.get("tribunale_nome", "").strip()
        tribunale_pec    = f.get("tribunale_pec", "").strip()
        codice_ufficio   = f.get("codice_ufficio", "").strip()
        atto_id          = f.get("atto_principale_id", "").strip()
        allegati_ids     = request.form.getlist("allegati_ids")

        if not tribunale_nome:
            flash("Seleziona un ufficio giudiziario destinatario.", "danger")
            return redirect(url_for("deposito_prepara", id_fasc=id_fasc))
        if not atto_id:
            flash("Seleziona l'atto principale da includere nella busta.", "danger")
            return redirect(url_for("deposito_prepara", id_fasc=id_fasc))

        anno_rg = int(anno_rg_str) if anno_rg_str.isdigit() else (fasc.anno_rg or 0)
        id_dep  = _uuid.uuid4().hex[:8].upper()
        ts      = _dt.now().isoformat()

        if demo_mode:
            # Simulazione: nessun file su disco, nessuna PEC reale
            esito = EsitoDepositoPCT(
                id=id_dep,
                timestamp=ts,
                stato="INVIATO",
                tipo_atto=tipo_atto,
                pec_destinatario=tribunale_pec or f"{tribunale_nome.lower().replace(' ','.')}@pec.demo",
                messaggio=(
                    f"[DEMO] Busta {id_dep} creata e PEC simulata per {tribunale_nome}. "
                    f"Atto: {tipo_atto} — RG {numero_rg}/{anno_rg}."
                ),
                note=note,
                registrato_da=u.username if u else "demo",
            )
        else:
            # Deposito reale: crea busta + firma + invia PEC
            try:
                from pct.busta import BustaTelematica, DatiBusta, Allegato as AllegatoBusta
                from pct.deposito import DepositoCivile
                from pct.pec import ClientPEC, ConfigPEC
                from pct.firma import FirmaDigitale
                import os as _os

                # Risolvi percorsi documenti
                atto_doc = next((d for d in fasc.documenti if d.id == atto_id), None)
                if not atto_doc:
                    flash("Documento selezionato come atto principale non trovato.", "danger")
                    return redirect(url_for("deposito_prepara", id_fasc=id_fasc))

                atto_path = str(gf.percorso_documento(id_fasc, atto_id))

                allegati_busta = []
                for all_id in allegati_ids:
                    if all_id == atto_id:
                        continue  # evita duplicati
                    all_doc = next((d for d in fasc.documenti if d.id == all_id), None)
                    if all_doc:
                        all_path = str(gf.percorso_documento(id_fasc, all_id))
                        allegati_busta.append(
                            AllegatoBusta(percorso=all_path, descrizione=all_doc.nome)
                        )

                dati = DatiBusta(
                    codice_ufficio=codice_ufficio or tribunale_nome,
                    codice_registro=codice_registro,
                    oggetto=oggetto,
                    tipo_atto=tipo_atto,
                    atto_principale=atto_path,
                    allegati=allegati_busta,
                    numero_rg=numero_rg or None,
                    anno_rg=anno_rg or None,
                    operatore=u.username if u else "",
                    cf_mittente="",
                )

                # Config PEC e firma dalla config studio
                cfg_studio = get_config_studio().config
                pec_cfg    = cfg_studio.pec if cfg_studio and hasattr(cfg_studio, 'pec') else None
                firma_cfg  = cfg_studio.firma if cfg_studio and hasattr(cfg_studio, 'firma') else None

                if not pec_cfg or not pec_cfg.indirizzo:
                    raise RuntimeError(
                        "Configurazione PEC non trovata. Configura le credenziali PEC nelle impostazioni."
                    )

                config_pec = ConfigPEC(
                    indirizzo=pec_cfg.indirizzo,
                    password=pec_cfg.password,
                    smtp_host=getattr(pec_cfg, 'smtp_host', 'smtp.pec.provider.it'),
                    smtp_port=getattr(pec_cfg, 'smtp_port', 465),
                    imap_host=getattr(pec_cfg, 'imap_host', ''),
                    imap_port=getattr(pec_cfg, 'imap_port', 993),
                )

                firma = None
                if firma_cfg and getattr(firma_cfg, 'configurato', False):
                    try:
                        firma = FirmaDigitale.da_config(firma_cfg)
                    except Exception as _fe:
                        app.logger.warning("FirmaDigitale non inizializzata: %s", _fe)

                output_dir = _os.getenv("PCT_DEPOSITI_DIR", "/data/depositi")
                dep = DepositoCivile(config_pec=config_pec, firma=firma, output_dir=output_dir)

                # Risolvi PEC tribunale
                pec_dest = tribunale_pec
                if not pec_dest and codice_ufficio:
                    try:
                        from pct.uffici_giudiziari import get_gestore as _get_uff
                        _cache = _os.getenv("PCT_UFFICI_DB", "/data/uffici/uffici_giudiziari.json")
                        _uff = next(
                            (x for x in _get_uff(_cache).carica() if x.get("codice") == codice_ufficio),
                            None,
                        )
                        pec_dest = _uff["pec"] if _uff else ""
                    except Exception:
                        pass

                if not pec_dest:
                    raise RuntimeError(
                        f"Indirizzo PEC non trovato per l'ufficio '{tribunale_nome}'. "
                        "Verifica la selezione o imposta manualmente la PEC."
                    )

                # Invia senza attendere ricevute (polling successivo)
                esito_dep = dep.deposita(
                    dati=dati,
                    tribunale=codice_ufficio or tribunale_nome,
                    attendi_ricevute=False,
                )
                dep.salva_esito(esito_dep)

                esito = EsitoDepositoPCT(
                    id=esito_dep.id_deposito,
                    timestamp=esito_dep.timestamp,
                    stato=esito_dep.stato,
                    tipo_atto=tipo_atto,
                    pec_destinatario=esito_dep.pec_destinatario,
                    messaggio=esito_dep.messaggio,
                    ricevuta_accettazione=esito_dep.ricevuta_accettazione or "",
                    ricevuta_consegna=esito_dep.ricevuta_consegna or "",
                    note=note,
                    registrato_da=u.username if u else "",
                )

            except Exception as _exc:
                app.logger.exception("Errore deposito_invia %s: %s", id_fasc, _exc)
                flash(f"Errore durante il deposito: {_exc}", "danger")
                return redirect(url_for("deposito_prepara", id_fasc=id_fasc))

        # Salva esito nel fascicolo
        try:
            from datetime import datetime as _dtnow
            fasc.depositi_pct.append(esito)
            fasc.modificato_il = _dtnow.now().isoformat()
            gf._salva()
            audit("fascicoli.deposito.invia", "fascicolo", id_fasc,
                  dettagli=f"Deposito {esito.id} — {tipo_atto} verso {esito.pec_destinatario}")
            _sync.pubblica("modifica", "fascicoli", id_fasc, utente=u.username if u else "")
            if demo_mode:
                flash(
                    f"[DEMO] Deposito simulato con ID {esito.id}. "
                    "In modalità reale la busta verrebbe firmata e inviata via PEC.",
                    "warning",
                )
            else:
                flash(
                    f"Deposito {esito.id} inviato via PEC a {esito.pec_destinatario}. "
                    "Ricevute di accettazione e consegna saranno disponibili a breve.",
                    "success",
                )
        except Exception as _se:
            app.logger.exception("Errore salvataggio esito deposito %s: %s", id_fasc, _se)
            flash(f"Deposito inviato ma errore nel salvataggio: {_se}", "warning")

        return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))

    @app.route("/api/fascicoli/<id_fasc>/depositi/<id_dep>/controlla", methods=["POST"])
    def deposito_controlla_ricevute(id_fasc, id_dep):
        """
        Controlla via IMAP se sono arrivate nuove ricevute PEC per un deposito.
        Aggiorna il fascicolo e restituisce lo stato aggiornato in JSON.
        """
        gf   = get_fascicoli()
        u    = g.utente_corrente
        fasc = gf.get(id_fasc)
        if not fasc:
            return jsonify({"errore": "Fascicolo non trovato"}), 200

        dep = next((d for d in fasc.depositi_pct if d.id == id_dep), None)
        if not dep:
            return jsonify({"errore": "Deposito non trovato"}), 200

        try:
            cfg_studio = get_config_studio().config
            pec_cfg    = cfg_studio.pec if cfg_studio and hasattr(cfg_studio, 'pec') else None

            if not pec_cfg or not pec_cfg.imap_host:
                return jsonify({
                    "stato": dep.stato,
                    "ricevuta_accettazione": bool(dep.ricevuta_accettazione),
                    "ricevuta_consegna": bool(dep.ricevuta_consegna),
                    "info": "IMAP non configurato — verifica manuale necessaria.",
                })

            from pct.pec import ClientPEC, ConfigPEC
            config_pec = ConfigPEC(
                indirizzo=pec_cfg.indirizzo,
                password=pec_cfg.password,
                smtp_host=getattr(pec_cfg, 'smtp_host', ''),
                imap_host=pec_cfg.imap_host,
                imap_port=getattr(pec_cfg, 'imap_port', 993),
            )
            client_pec = ClientPEC(config_pec)
            ricevute   = client_pec.attendi_ricevute(timeout=15)  # check rapido

            aggiornato = False

            # Fase 4 — ricevuta accettazione PEC
            if ricevute.get("accettazione") and not dep.ricevuta_accettazione:
                dep.ricevuta_accettazione = ricevute["accettazione"]
                if dep.stato in ("INVIATO",):
                    dep.stato = "ACCETTATO_PEC"
                aggiornato = True

            # Fase 5 — ricevuta avvenuta consegna
            if ricevute.get("consegna") and not dep.ricevuta_consegna:
                dep.ricevuta_consegna = ricevute["consegna"]
                if dep.stato not in ("WARN_CONTROLLI", "ERRORE_CONTROLLI",
                                     "ACCETTATO_CANCELLERIA", "RIFIUTATO_CANCELLERIA"):
                    dep.stato = "CONSEGNATO"
                aggiornato = True

            # Fase 6 — esito controlli automatici
            if ricevute.get("controlli") and not dep.ricevuta_controlli_automatici:
                dep.ricevuta_controlli_automatici = ricevute["controlli"]
                ec = ricevute.get("esito_controlli", "OK").upper()
                dep.esito_controlli = ec
                if ec == "ERROR":
                    dep.stato = "ERRORE_CONTROLLI"
                elif ec == "WARN":
                    dep.stato = "WARN_CONTROLLI"
                # OK: stato resta CONSEGNATO, si attende cancelleria
                aggiornato = True

            # Fase 7 — esito cancelleria
            if ricevute.get("cancelleria") and not dep.ricevuta_cancelleria:
                dep.ricevuta_cancelleria = ricevute["cancelleria"]
                if ricevute.get("cancelleria_accettato", True):
                    dep.stato = "ACCETTATO_CANCELLERIA"
                else:
                    dep.stato = "RIFIUTATO_CANCELLERIA"
                aggiornato = True

            if aggiornato:
                gf._salva()
                audit("fascicoli.deposito.ricevute", "fascicolo", id_fasc,
                      dettagli=f"Deposito {id_dep} aggiornato a {dep.stato}")

            return jsonify({
                "stato": dep.stato,
                "ricevuta_accettazione": bool(dep.ricevuta_accettazione),
                "ricevuta_consegna": bool(dep.ricevuta_consegna),
                "ricevuta_controlli": bool(dep.ricevuta_controlli_automatici),
                "esito_controlli": dep.esito_controlli,
                "ricevuta_cancelleria": bool(dep.ricevuta_cancelleria),
                "aggiornato": aggiornato,
            })

        except Exception as e:
            app.logger.exception("deposito_controlla_ricevute %s/%s: %s", id_fasc, id_dep, e)
            return jsonify({"errore": str(e), "stato": dep.stato})

    # ---- Sfoglia e download da archivio ZIP

    @app.route("/fascicoli/<id_fasc>/archivio/contenuto")
    def archivio_contenuto(id_fasc):
        """API: restituisce la lista dei file nel ZIP dell'archivio (JSON)."""
        gf = get_fascicoli()
        try:
            files = gf.contenuto_archivio(id_fasc)
            return jsonify(files)
        except Exception as e:
            app.logger.exception("archivio_contenuto %s: %s", id_fasc, e)
            return jsonify({"errore": str(e)}), 200

    @app.route("/fascicoli/<id_fasc>/archivio/file/<path:nome_file>")
    def archivio_scarica_file(id_fasc, nome_file):
        """Estrae e serve un singolo file dal ZIP senza decomprimere l'intero archivio."""
        gf = get_fascicoli()
        try:
            dati = gf.estrai_file_archivio(id_fasc, nome_file)
        except FileNotFoundError as e:
            flash(str(e), "warning")
            return redirect(url_for("lista_archivio"))
        import io, mimetypes
        mime, _ = mimetypes.guess_type(nome_file)
        return send_file(
            io.BytesIO(dati),
            mimetype=mime or "application/octet-stream",
            as_attachment=True,
            download_name=Path(nome_file).name,
        )

    @app.route("/fascicoli/<id_fasc>/archivio/scarica")
    def scarica_archivio(id_fasc):
        gf = get_fascicoli()
        fasc = gf.get(id_fasc)
        if not fasc or not fasc.archivio or not fasc.archivio.percorso_zip:
            flash("Archivio ZIP non disponibile.", "warning")
            return redirect(url_for("lista_archivio"))
        p = Path(fasc.archivio.percorso_zip)
        if not p.exists():
            flash("File archivio non trovato su disco.", "danger")
            return redirect(url_for("lista_archivio"))
        return send_file(p, as_attachment=True,
                         download_name=f"fascicolo_{fasc.numero.replace('/','_')}.zip")

    # ---- API fascicoli

    @app.route("/api/fascicoli")
    def api_fascicoli():
        try:
            gf = get_fascicoli()
            q = request.args.get("q", "")
            archiviati = request.args.get("archiviati", "0") == "1"
            fascicoli = gf.cerca(testo=q, archiviati=archiviati)
            return jsonify([f.to_dict() for f in fascicoli])
        except Exception as e:
            app.logger.exception("Errore api_fascicoli: %s", e)
            return jsonify([])

    @app.route("/api/fascicoli/<id_fasc>")
    def api_fascicolo(id_fasc):
        try:
            gf = get_fascicoli()
            f = gf.get(id_fasc)
            if not f:
                return jsonify({"errore": "Non trovato"}), 404
            return jsonify(f.to_dict())
        except Exception as e:
            app.logger.exception("Errore api_fascicolo: %s", e)
            return jsonify({"errore": str(e)})

    @app.route("/api/fascicoli/statistiche")
    def api_fascicoli_statistiche():
        try:
            return jsonify(get_fascicoli().statistiche())
        except Exception as e:
            app.logger.exception("Errore api_fascicoli_statistiche: %s", e)
            return jsonify({"errore": str(e)})

    # ================================================================ MESSAGGI

    @app.route("/messaggi")
    def lista_messaggi():
        gm = get_messaggi()
        canale = request.args.get("canale", "")
        stato = request.args.get("stato", "")
        q = request.args.get("q", "")
        messaggi = gm.tutti(
            canale=CanaleMsggio(canale) if canale else None,
            stato=StatoMessaggio(stato) if stato else None,
        )
        if q:
            ql = q.lower()
            messaggi = [
                m for m in messaggi
                if ql in (m.email_destinatario or m.telefono_destinatario or "").lower()
                or ql in m.nome_destinatario.lower()
                or ql in m.oggetto.lower()
                or ql in m.corpo.lower()
            ]
        return render_template(
            "messaggi/lista.html",
            messaggi=messaggi,
            canali=list(CanaleMsggio),
            stati=list(StatoMessaggio),
            canale=canale,
            stato=stato,
            q=q,
            stats=gm.statistiche(),
        )

    @app.route("/messaggi/nuovo", methods=["GET", "POST"])
    def nuovo_messaggio():
        gm = get_messaggi()
        gc = get_clienti()
        clienti = gc.tutti()
        ha_wa_api = bool(app.config.get("TWILIO_SID") and app.config.get("TWILIO_TOKEN"))
        if request.method == "POST":
            f = request.form
            canale_str = f["canale"]
            canale = CanaleMsggio(canale_str)
            destinatario = f["destinatario"].strip()
            testo = f.get("testo", "").strip()
            oggetto = f.get("oggetto", "").strip()
            id_cliente = f.get("id_cliente", "") or ""
            from_cliente = f.get("from_cliente", "")
            try:
                if canale == CanaleMsggio.EMAIL:
                    gm.invia_email(
                        destinatario=destinatario,
                        oggetto=oggetto,
                        corpo_testo=testo,
                        id_cliente=id_cliente,
                    )
                elif canale == CanaleMsggio.SMS:
                    gm.invia_sms(
                        telefono=destinatario,
                        testo=testo,
                        id_cliente=id_cliente,
                    )
                else:
                    msg_wa = gm.invia_whatsapp(
                        telefono=destinatario,
                        testo=testo,
                        id_cliente=id_cliente,
                    )
                    if msg_wa.sid_esterno and msg_wa.sid_esterno.startswith("https://wa.me"):
                        # Nessuna API — mostra link WhatsApp Web all'utente
                        return render_template(
                            "messaggi/form.html",
                            clienti=clienti,
                            canali=list(CanaleMsggio),
                            tipi_automazione=list(TipoAutomazione),
                            id_cliente=id_cliente,
                            canale_default="WHATSAPP",
                            from_cliente=from_cliente,
                            cliente_presel=gc.get(id_cliente) if id_cliente else None,
                            ha_wa_api=ha_wa_api,
                            wa_link=msg_wa.sid_esterno,
                        )
                flash("Messaggio inviato.", "success")
                if from_cliente:
                    return redirect(url_for("cartella_cliente", id_cliente=from_cliente))
                return redirect(url_for("lista_messaggi"))
            except Exception as e:
                flash(str(e), "danger")
        id_cliente_get = request.args.get("id_cliente", "")
        canale_get = request.args.get("canale", "EMAIL")
        from_cliente_get = request.args.get("from_cliente", "")
        cliente_presel = gc.get(id_cliente_get) if id_cliente_get else None
        return render_template(
            "messaggi/form.html",
            clienti=clienti,
            canali=list(CanaleMsggio),
            tipi_automazione=list(TipoAutomazione),
            id_cliente=id_cliente_get,
            canale_default=canale_get,
            from_cliente=from_cliente_get,
            cliente_presel=cliente_presel,
            ha_wa_api=ha_wa_api,
        )

    @app.route("/messaggi/<id_msg>")
    def dettaglio_messaggio(id_msg):
        gm = get_messaggi()
        msg = gm.get(id_msg)
        if not msg:
            flash("Messaggio non trovato.", "warning")
            return redirect(url_for("lista_messaggi"))
        return render_template("messaggi/dettaglio.html", msg=msg)

    @app.route("/messaggi/<id_msg>/elimina", methods=["POST"])
    def elimina_messaggio(id_msg):
        gm = get_messaggi()
        try:
            gm.elimina(id_msg)
            flash("Messaggio eliminato.", "success")
        except ValueError as e:
            flash(str(e), "danger")
        return redirect(url_for("lista_messaggi"))

    @app.route("/api/messaggi/statistiche")
    def api_messaggi_statistiche():
        try:
            return jsonify(get_messaggi().statistiche())
        except Exception as e:
            app.logger.exception("Errore api_messaggi_statistiche: %s", e)
            return jsonify({"errore": str(e)})

    # ================================================================ BACKUP

    @app.route("/backup")
    def lista_backup():
        gb = get_backup()
        backup_list = gb.tutti()
        stats = gb.statistiche()
        return render_template(
            "backup/lista.html",
            backup_list=backup_list,
            stats=stats,
            config=gb.config,
            tipi=list(TipoBackup),
            stati=list(StatoBackup),
        )

    @app.route("/backup/esegui", methods=["POST"])
    def esegui_backup():
        gb = get_backup()
        tipo = TipoBackup(request.form.get("tipo", "COMPLETO"))
        nota = request.form.get("nota", "")
        componenti_raw = request.form.getlist("componenti")
        componenti = componenti_raw if componenti_raw else None
        try:
            record = gb.esegui_backup(tipo=tipo, componenti=componenti, nota=nota)
            if record.stato == StatoBackup.OK:
                flash(f"Backup completato: {record.num_file} file, "
                      f"{round(record.dimensione_bytes/1024/1024, 2)} MB.", "success")
            else:
                flash(f"Backup fallito: {record.errore}", "danger")
        except Exception as e:
            flash(str(e), "danger")
        return redirect(url_for("lista_backup"))

    @app.route("/backup/<id_bk>/verifica", methods=["POST"])
    def verifica_backup(id_bk):
        gb = get_backup()
        try:
            ris = gb.verifica_integrita(id_bk)
            if ris["ok"]:
                flash("Integrità verificata: backup integro.", "success")
            else:
                flash("ATTENZIONE: integrità compressa! Il file potrebbe essere corrotto.", "danger")
        except Exception as e:
            flash(str(e), "danger")
        return redirect(url_for("lista_backup"))

    @app.route("/backup/<id_bk>/elimina", methods=["POST"])
    def elimina_backup(id_bk):
        gb = get_backup()
        try:
            gb.elimina(id_bk)
            flash("Backup eliminato.", "success")
        except Exception as e:
            flash(str(e), "danger")
        return redirect(url_for("lista_backup"))

    @app.route("/backup/<id_bk>/scarica")
    def scarica_backup(id_bk):
        gb = get_backup()
        record = gb.get(id_bk)
        if not record:
            flash("Backup non trovato.", "warning")
            return redirect(url_for("lista_backup"))
        p = Path(record.percorso_file)
        if not p.exists():
            flash("File backup non trovato su disco.", "danger")
            return redirect(url_for("lista_backup"))
        return send_file(p, as_attachment=True, download_name=p.name)

    @app.route("/backup/<id_bk>/ripristina", methods=["GET", "POST"])
    def ripristina_backup(id_bk):
        gb = get_backup()
        record = gb.get(id_bk)
        if not record:
            flash("Backup non trovato.", "warning")
            return redirect(url_for("lista_backup"))
        if request.method == "POST":
            dest = request.form.get("destinazione", "./ripristino").strip()
            componenti_raw = request.form.getlist("componenti")
            componenti = componenti_raw if componenti_raw else None
            sovrascrivi = request.form.get("sovrascrivi") == "1"
            password = request.form.get("password", "")
            try:
                ris = gb.ripristina(
                    id_bk, dest,
                    componenti=componenti,
                    password=password,
                    sovrascrivi=sovrascrivi,
                )
                flash(
                    f"Ripristino completato: {ris['file_ripristinati']} file ripristinati, "
                    f"{ris['file_saltati']} saltati.",
                    "success",
                )
                return redirect(url_for("lista_backup"))
            except Exception as e:
                flash(str(e), "danger")
        return render_template("backup/ripristina.html", record=record)

    @app.route("/api/backup/statistiche")
    def api_backup_statistiche():
        try:
            return jsonify(get_backup().statistiche())
        except Exception as e:
            app.logger.exception("Errore api_backup_statistiche: %s", e)
            return jsonify({"errore": str(e)})

    # ================================================================ HEALTH CHECK

    @app.route("/api/health")
    def api_health():
        """Endpoint di salute per monitoring — non richiede autenticazione."""
        stato = {"ok": True, "timestamp": datetime.now().isoformat(), "moduli": {}}
        try:
            gc = get_clienti()
            stato["moduli"]["clienti"] = {"ok": True, "totale": gc.statistiche()["totale"]}
        except Exception as e:
            stato["moduli"]["clienti"] = {"ok": False, "errore": str(e)}
            stato["ok"] = False
        try:
            gf = get_fascicoli()
            stato["moduli"]["fascicoli"] = {"ok": True, "attivi": gf.statistiche()["attivi"]}
        except Exception as e:
            stato["moduli"]["fascicoli"] = {"ok": False, "errore": str(e)}
            stato["ok"] = False
        try:
            ga = get_agenda()
            stato["moduli"]["agenda"] = {"ok": True, "totale": ga.statistiche()["totale"]}
        except Exception as e:
            stato["moduli"]["agenda"] = {"ok": False, "errore": str(e)}
            stato["ok"] = False
        try:
            gs = get_scadenziario()
            stato["moduli"]["scadenziario"] = {"ok": True, "aperte": gs.statistiche()["aperte"]}
        except Exception as e:
            stato["moduli"]["scadenziario"] = {"ok": False, "errore": str(e)}
            stato["ok"] = False
        codice = 200 if stato["ok"] else 503
        return jsonify(stato), codice

    # ================================================================ CSV EXPORT

    def _csv_response(righe: list[dict], nome_file: str) -> Response:
        """Genera una risposta CSV da una lista di dizionari."""
        if not righe:
            output = io.StringIO()
            output.write("# Nessun dato da esportare\n")
            csv_data = output.getvalue()
        else:
            output = io.StringIO()
            writer = csv.DictWriter(
                output, fieldnames=righe[0].keys(),
                extrasaction="ignore", lineterminator="\n"
            )
            writer.writeheader()
            writer.writerows(righe)
            csv_data = output.getvalue()
        return Response(
            csv_data,
            mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{nome_file}"'},
        )

    @app.route("/clienti/export.csv")
    def export_clienti_csv():
        gc = get_clienti()
        testo = request.args.get("q", "").strip()
        tipo_f = request.args.get("tipo")
        stato_f = request.args.get("stato", "")
        tipo = TipoCliente(tipo_f) if tipo_f else None
        stato = StatoCliente(stato_f) if stato_f else None
        clienti = gc.cerca(testo=testo, tipo=tipo, stato=stato) if testo else gc.tutti(stato=stato, tipo=tipo)
        righe = []
        for c in clienti:
            d = c.to_dict()
            ind = d.get("indirizzo") or {}
            righe.append({
                "id": d["id"],
                "cognome": d.get("cognome", ""),
                "nome": d.get("nome", ""),
                "ragione_sociale": d.get("ragione_sociale", ""),
                "tipo": d.get("tipo", ""),
                "stato": d.get("stato", ""),
                "codice_fiscale": d.get("codice_fiscale", ""),
                "partita_iva": d.get("partita_iva", ""),
                "email": d.get("email", ""),
                "telefono": d.get("telefono", ""),
                "citta": ind.get("citta", "") if isinstance(ind, dict) else "",
            })
        audit("clienti.export_csv")
        return _csv_response(righe, f"clienti_{date.today().isoformat()}.csv")

    @app.route("/fascicoli/export.csv")
    def export_fascicoli_csv():
        gf = get_fascicoli()
        testo = request.args.get("q", "").strip()
        stato_f = request.args.get("stato", "")
        tipo_f = request.args.get("tipo", "")
        stato = StatoFascicolo(stato_f) if stato_f else None
        tipo = TipoFascicolo(tipo_f) if tipo_f else None
        fascicoli = gf.cerca(testo=testo, stato=stato, tipo=tipo) if testo else gf.tutti(stato=stato, tipo=tipo)
        righe = []
        for f in fascicoli:
            d = f.to_dict()
            righe.append({
                "numero": d.get("numero", ""),
                "titolo": d.get("titolo", ""),
                "tipo": d.get("tipo", ""),
                "stato": d.get("stato", ""),
                "tribunale": d.get("tribunale", ""),
                "numero_rg": d.get("numero_rg", ""),
                "anno_rg": d.get("anno_rg", ""),
                "nome_cliente": d.get("nome_cliente", ""),
                "controparte": d.get("controparte", ""),
                "avvocato_referente": d.get("avvocato_referente", ""),
                "data_apertura": d.get("data_apertura", ""),
                "data_chiusura": d.get("data_chiusura", ""),
            })
        audit("fascicoli.export_csv")
        return _csv_response(righe, f"fascicoli_{date.today().isoformat()}.csv")

    @app.route("/fascicoli/export.pdf")
    def export_fascicoli_pdf():
        """Export PDF lista fascicoli con filtri correnti."""
        gf = get_fascicoli()
        testo = request.args.get("q", "").strip()
        stato_f = request.args.get("stato", "")
        tipo_f = request.args.get("tipo", "")
        try:
            stato = StatoFascicolo(stato_f) if stato_f else None
            tipo = TipoFascicolo(tipo_f) if tipo_f else None
            fascicoli = gf.cerca(testo=testo, stato=stato, tipo=tipo) if testo else gf.tutti(stato=stato, tipo=tipo)
            studio_nome = os.getenv("PCT_STUDIO_NOME", "Studio Legale")
            _mesi_it = ["Gennaio","Febbraio","Marzo","Aprile","Maggio","Giugno",
                        "Luglio","Agosto","Settembre","Ottobre","Novembre","Dicembre"]
            _oggi = date.today()
            mese_label = f"{_mesi_it[_oggi.month - 1]} {_oggi.year}"
            titolo = f"Elenco Fascicoli — {mese_label}"
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                out = tmp.name
            lista_fascicoli_pdf([f.to_dict() for f in fascicoli], out, titolo=titolo, studio_nome=studio_nome)
            audit("fascicoli.export_pdf")
            nome_file = f"fascicoli_{date.today().isoformat()}.pdf"
            return send_file(out, as_attachment=True, download_name=nome_file, mimetype="application/pdf")
        except Exception as e:
            app.logger.exception("Errore export_fascicoli_pdf: %s", e)
            flash(f"Impossibile generare il PDF: {e}", "danger")
            return redirect(url_for("lista_fascicoli"))

    @app.route("/clienti/export.pdf")
    def export_clienti_pdf():
        """Export PDF lista clienti con filtri correnti."""
        gc = get_clienti()
        testo = request.args.get("q", "").strip()
        tipo_f = request.args.get("tipo")
        stato_f = request.args.get("stato", "ATTIVO")
        try:
            tipo = TipoCliente(tipo_f) if tipo_f else None
            stato = StatoCliente(stato_f) if stato_f else None
            clienti = gc.cerca(testo=testo, tipo=tipo, stato=stato) if testo else gc.tutti(stato=stato, tipo=tipo)
            studio_nome = os.getenv("PCT_STUDIO_NOME", "Studio Legale")
            _mesi_it = ["Gennaio","Febbraio","Marzo","Aprile","Maggio","Giugno",
                        "Luglio","Agosto","Settembre","Ottobre","Novembre","Dicembre"]
            _oggi = date.today()
            mese_label = f"{_mesi_it[_oggi.month - 1]} {_oggi.year}"
            titolo = f"Elenco Clienti — {mese_label}"
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                out = tmp.name
            lista_clienti_pdf([c.to_dict() for c in clienti], out, titolo=titolo, studio_nome=studio_nome)
            audit("clienti.export_pdf")
            nome_file = f"clienti_{date.today().isoformat()}.pdf"
            return send_file(out, as_attachment=True, download_name=nome_file, mimetype="application/pdf")
        except Exception as e:
            app.logger.exception("Errore export_clienti_pdf: %s", e)
            flash(f"Impossibile generare il PDF: {e}", "danger")
            return redirect(url_for("lista_clienti"))

    @app.route("/scadenziario/export.csv")
    def export_scadenziario_csv():
        gs = get_scadenziario()
        filtro_tipo = request.args.get("tipo", "")
        filtro_priorita = request.args.get("priorita", "")
        id_fascicolo = request.args.get("id_fascicolo", "")
        solo_aperte = request.args.get("stato", "aperte") != "tutte"
        scadenze = gs.tutte(
            tipo=TipoTermine(filtro_tipo) if filtro_tipo else None,
            priorita=PrioritaTermine(filtro_priorita) if filtro_priorita else None,
            id_fascicolo=id_fascicolo,
            solo_aperte=solo_aperte,
        )
        righe = []
        for s in scadenze:
            d = s.to_dict() if hasattr(s, "to_dict") else vars(s)
            righe.append({
                "titolo": d.get("titolo", ""),
                "tipo": d.get("tipo", ""),
                "data_scadenza": d.get("data_scadenza", ""),
                "priorita": d.get("priorita", ""),
                "stato": d.get("stato", ""),
                "perentorio": d.get("perentorio", ""),
                "id_fascicolo": d.get("id_fascicolo", ""),
                "giorni_preavviso": str(d.get("giorni_preavviso", "")),
                "completata_il": d.get("completata_il", ""),
                "note": d.get("note", ""),
            })
        audit("scadenziario.export_csv")
        return _csv_response(righe, f"scadenziario_{date.today().isoformat()}.csv")

    # ================================================================ SEARCH

    @app.route("/api/cerca")
    def api_cerca():
        """Ricerca globale full-text — usata dall'autocomplete topbar."""
        try:
            q = request.args.get("q", "").strip()
            tipi_raw = request.args.getlist("tipo")
            limit = min(int(request.args.get("limit", 20)), 50)
            if not q:
                return jsonify([])
            indice = get_indice()
            risultati = indice.cerca(q, tipi=tipi_raw or None, limit=limit)
            return jsonify([
                {
                    "tipo": r.tipo,
                    "id": r.id,
                    "titolo": r.titolo,
                    "sottotitolo": r.sottotitolo,
                    "url": r.url,
                    "icona": r.icona,
                    "snippet": r.snippet,
                }
                for r in risultati
            ])
        except Exception as e:
            app.logger.exception("Errore api_cerca: %s", e)
            return jsonify([])

    @app.route("/cerca")
    def cerca():
        """Pagina di ricerca completa."""
        q = request.args.get("q", "").strip()
        risultati = {}
        if q:
            indice = get_indice()
            risultati = indice.cerca_globale(q, limit=30)
        return render_template("cerca.html", q=q, risultati=risultati)

    @app.route("/api/ricerca/ricostruisci", methods=["POST"])
    def api_ricerca_ricostruisci():
        """Ricostruisce l'indice di ricerca (solo admin)."""
        u = g.utente_corrente
        if not u or not u.ha_permesso("utenti.leggi"):
            return jsonify({"errore": "Non autorizzato"}), 403
        try:
            indice = get_indice()
            gf = get_fascicoli()
            # Raccoglie testo OCR dalla cache per tutti i documenti dei fascicoli
            documenti_ocr = []
            for fasc in gf.tutti():
                d = fasc.to_dict() if hasattr(fasc, "to_dict") else fasc
                for doc in d.get("documenti", []):
                    testo = indice.get_ocr_cache(doc.get("hash_sha256", ""))
                    if testo:
                        documenti_ocr.append((
                            d["id"], doc["id"], doc.get("nome", ""),
                            testo, doc.get("tipo", ""),
                        ))
                    elif ocr_supportato(doc.get("nome", "")):
                        # Accoda OCR per i file non ancora processati
                        try:
                            percorso = str(gf.percorso_documento(d["id"], doc["id"]))
                            _accoda_ocr(
                                percorso=percorso,
                                hash_sha256=doc.get("hash_sha256", ""),
                                id_fasc=d["id"],
                                id_doc=doc["id"],
                                nome_doc=doc.get("nome", ""),
                                tipo_doc=doc.get("tipo", ""),
                                index_path=app.config["SEARCH_INDEX"],
                            )
                        except Exception:
                            pass
            indice.ricostruisci(
                clienti=get_clienti().tutti(),
                fascicoli=gf.tutti(),
                appuntamenti=get_agenda().tutti(),
                scadenze=get_scadenziario().tutte(solo_aperte=False),
                documenti_ocr=documenti_ocr,
            )
            audit("ricerca.ricostruisci_indice")
            return jsonify({"ok": True, "statistiche": indice.statistiche()})
        except Exception as e:
            app.logger.exception("Errore api_ricerca_ricostruisci: %s", e)
            return jsonify({"ok": False, "errore": str(e)})

    @app.route("/api/ocr/stato")
    def api_ocr_stato():
        """Stato del worker OCR asincrono (coda, completati, errori)."""
        try:
            with _ocr_stats_lock:
                stats = dict(_ocr_stats)
            stats["in_coda"] = _ocr_queue.qsize()
            return jsonify(stats)
        except Exception as e:
            return jsonify({"errore": str(e)}), 200

    # ================================================================ PDF EXPORT

    @app.route("/fascicoli/<id_fasc>/pdf")
    def fascicolo_pdf_export(id_fasc):
        gf = get_fascicoli()
        fasc = gf.get(id_fasc)
        if not fasc:
            flash("Fascicolo non trovato.", "warning")
            return redirect(url_for("lista_fascicoli"))
        studio_nome = os.getenv("PCT_STUDIO_NOME", "Studio Legale")
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            out = tmp.name
        fascicolo_pdf(fasc.to_dict(), out, studio_nome=studio_nome)
        nome_file = f"fascicolo_{fasc.numero or id_fasc}.pdf".replace("/", "-").replace(" ", "_")
        audit("fascicoli.esporta_pdf", risorsa_tipo="fascicolo", risorsa_id=id_fasc)
        return send_file(out, as_attachment=True, download_name=nome_file, mimetype="application/pdf")

    @app.route("/scadenziario/pdf")
    def scadenziario_pdf_export():
        gs = get_scadenziario()
        stato_raw = request.args.get("stato", "")
        solo_aperte = stato_raw != "tutte"
        lista = gs.tutte(solo_aperte=solo_aperte)
        studio_nome = os.getenv("PCT_STUDIO_NOME", "Studio Legale")
        mese_label = date.today().strftime("%B %Y").capitalize()
        titolo_pdf = f"Scadenziario — {mese_label}"
        dati = [
            {
                "scadenza": s.data_scadenza,
                "titolo": s.titolo,
                "tipo": s.tipo.value if hasattr(s.tipo, "value") else str(s.tipo),
                "fascicolo": s.id_fascicolo or "",
                "priorita": s.priorita.value if hasattr(s.priorita, "value") else str(s.priorita),
                "perentorio": s.perentorio,
            }
            for s in lista
        ]
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            out = tmp.name
        scadenze_pdf(dati, out, titolo=titolo_pdf, studio_nome=studio_nome)
        nome_file = f"scadenziario_{date.today().isoformat()}.pdf"
        audit("scadenziario.esporta_pdf")
        return send_file(out, as_attachment=True, download_name=nome_file, mimetype="application/pdf")

    # ================================================================ SINCRONIZZAZIONE REAL-TIME

    @app.route("/api/eventi")
    def api_eventi():
        """
        SSE endpoint per notifiche in tempo reale agli operatori connessi.
        Ogni client connesso riceve gli aggiornamenti degli altri operatori.
        """
        if not g.utente_corrente:
            return jsonify({"errore": "Non autenticato"}), 401

        user_key = g.utente_corrente.username if g.utente_corrente else ""
        client_id, q = _sync.subscribe(user_key=user_key)
        # Notifica subito tutti gli altri client del nuovo conteggio
        _sync.notifica_connessi()

        def genera():
            yield from _sync.sse_stream(client_id, q)

        return Response(
            genera(),
            content_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-store",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    @app.route("/api/sync/stato")
    def api_sync_stato():
        """Stato sincronizzazione: operatori connessi e versioni file."""
        try:
            return jsonify({
                "connessi": _sync.n_connessi,
                "versioni": {
                    "clienti": _sync.versione_file(app.config["CLIENTI_DB"]),
                    "fascicoli": _sync.versione_file(app.config["FASCICOLI_DB"]),
                    "scadenze": _sync.versione_file(app.config["SCADENZIARIO_DB"]),
                    "agenda": _sync.versione_file(app.config["AGENDA_DB"]),
                    "messaggi": _sync.versione_file(app.config["MESSAGGI_DB"]),
                },
            })
        except Exception as e:
            app.logger.exception("Errore api_sync_stato: %s", e)
            return jsonify({"errore": str(e)})

    @app.route("/api/sync/broadcast", methods=["POST"])
    def api_sync_broadcast():
        """Invia un messaggio informativo a tutti gli operatori (solo admin)."""
        u = g.utente_corrente
        if not u or not u.ha_permesso("utenti.leggi"):
            return jsonify({"errore": "Non autorizzato"}), 403
        try:
            msg = request.json.get("messaggio", "") if request.is_json else request.form.get("messaggio", "")
            if not msg:
                return jsonify({"errore": "Messaggio obbligatorio"}), 400
            n = _sync.pubblica_broadcast(msg, utente=u.username)
            audit("sync.broadcast", dettagli=msg)
            return jsonify({"ok": True, "raggiunti": n})
        except Exception as e:
            app.logger.exception("Errore api_sync_broadcast: %s", e)
            return jsonify({"ok": False, "errore": str(e)})

    # ================================================================ ADMIN DATABASE

    @app.route("/admin/database")
    def admin_database():
        """Dashboard gestione database — solo amministratori."""
        u = g.utente_corrente
        if not u or not u.ha_permesso("utenti.leggi"):
            flash("Accesso riservato agli amministratori.", "danger")
            return redirect(url_for("dashboard"))
        db = get_database()
        statistiche = db.statistiche()
        uso = db.analisi_uso()
        sqlite_info = db.statistiche_sqlite(
            os.path.join(app.config.get("BACKUP_DIR", "./backup"), "studio_legale.db")
        )
        return render_template(
            "admin/database.html",
            statistiche=statistiche,
            uso=uso,
            sqlite_info=sqlite_info,
        )

    @app.route("/admin/database/verifica")
    def admin_database_verifica():
        """Verifica integrità referenziale di tutti i moduli."""
        u = g.utente_corrente
        if not u or not u.ha_permesso("utenti.leggi"):
            return jsonify({"errore": "Non autorizzato"}), 403
        db = get_database()
        problemi = db.verifica_integrita()
        audit("database.verifica_integrita")
        return jsonify({
            "ok": True,
            "n_problemi": len(problemi),
            "problemi": [
                {
                    "livello": p.severita,
                    "modulo": p.modulo,
                    "tipo": p.tipo,
                    "descrizione": p.messaggio,
                    "id_risorsa": p.id_record,
                    "campo": p.campo,
                    "suggerimento": p.suggerimento,
                }
                for p in problemi
            ],
        })

    @app.route("/admin/database/ottimizza", methods=["POST"])
    def admin_database_ottimizza():
        """Esegue ottimizzazione su tutti i moduli (JSON compaction + SQLite VACUUM)."""
        u = g.utente_corrente
        if not u or not u.ha_permesso("utenti.leggi"):
            return jsonify({"errore": "Non autorizzato"}), 403
        db = get_database()
        risultati = db.ottimizza()
        audit("database.ottimizza")
        return jsonify({
            "ok": True,
            "risultati": [
                {
                    "modulo": r.modulo,
                    "operazione": r.operazione,
                    "riuscita": r.riuscita,
                    "dettagli": r.dettagli,
                    "ms": r.ms,
                }
                for r in risultati
            ],
        })

    @app.route("/admin/database/migra", methods=["POST"])
    def admin_database_migra():
        """Migra tutti i dati JSON verso un singolo database SQLite."""
        u = g.utente_corrente
        if not u or not u.ha_permesso("utenti.leggi"):
            return jsonify({"errore": "Non autorizzato"}), 403
        percorso_db = os.path.join(
            app.config.get("BACKUP_DIR", "./backup"),
            f"studio_legale_{date.today().isoformat()}.db",
        )
        db = get_database()
        risultato = db.migra_verso_sqlite(percorso_db)
        audit("database.migra_sqlite", risorsa_tipo="db", risorsa_id=percorso_db)
        totale = sum(risultato.record_migrati.values()) if risultato.record_migrati else 0
        return jsonify({
            "ok": risultato.riuscita,
            "percorso_db": risultato.percorso_db,
            "record_migrati": totale,
            "per_modulo": risultato.record_migrati,
            "errori": risultato.errori,
            "durata_secondi": round(risultato.ms / 1000, 3),
        })

    # ================================================================ REGISTRO TRATTAMENTI (GDPR Art. 30)

    @app.route("/privacy/registro")
    def registro_trattamenti():
        u = g.utente_corrente
        if not u or not u.ha_permesso("utenti.leggi"):
            abort(403)
        gt = get_trattamenti()
        return render_template("privacy/registro.html", trattamenti=gt.tutti())

    @app.route("/privacy/registro/nuovo", methods=["GET", "POST"])
    def nuovo_trattamento():
        u = g.utente_corrente
        if not u or not u.ha_permesso("utenti.leggi"):
            abort(403)
        if request.method == "POST":
            f = request.form
            gt = get_trattamenti()
            gt.nuovo(
                nome=f.get("nome", ""),
                finalita=f.get("finalita", ""),
                categoria_dati=f.get("categoria_dati", ""),
                base_giuridica=f.get("base_giuridica", ""),
                soggetti_interessati=f.get("soggetti_interessati", ""),
                destinatari=f.get("destinatari", ""),
                trasferimento_extra_ue=f.get("trasferimento_extra_ue") == "1",
                paese_destinazione=f.get("paese_destinazione", ""),
                termine_conservazione=f.get("termine_conservazione", ""),
                misure_sicurezza=f.get("misure_sicurezza", ""),
                responsabile=f.get("responsabile", ""),
                note=f.get("note", ""),
            )
            audit("privacy.registro.nuovo")
            flash("Trattamento aggiunto al registro.", "success")
            return redirect(url_for("registro_trattamenti"))
        return render_template("privacy/registro.html",
                               trattamenti=get_trattamenti().tutti(), form_nuovo=True)

    @app.route("/privacy/registro/<id_t>/elimina", methods=["POST"])
    def elimina_trattamento(id_t):
        u = g.utente_corrente
        if not u or not u.ha_permesso("utenti.leggi"):
            abort(403)
        try:
            get_trattamenti().elimina(id_t)
            audit("privacy.registro.elimina", risorsa_id=id_t)
            flash("Trattamento eliminato.", "success")
        except KeyError as e:
            flash(str(e), "danger")
        return redirect(url_for("registro_trattamenti"))

    # ================================================================ GDPR & PRIVACY

    @app.route("/clienti/<id_cliente>/consenso", methods=["POST"])
    def aggiorna_consenso(id_cliente):
        """Registra/aggiorna il consenso al trattamento dati del cliente."""
        if not g.utente_corrente or not g.utente_corrente.ha_permesso("clienti.scrivi"):
            abort(403)
        gc = get_clienti()
        c = gc.get(id_cliente)
        if not c:
            abort(404)
        f = request.form
        consenso = f.get("consenso_trattamento") == "1"
        gc.aggiorna(id_cliente,
                    consenso_trattamento=consenso,
                    data_consenso=f.get("data_consenso", date.today().isoformat()),
                    modalita_consenso=f.get("modalita_consenso", ""))
        audit("clienti.consenso", "cliente", id_cliente,
              dettagli=f"{'concesso' if consenso else 'revocato'} via {f.get('modalita_consenso','')}")
        flash("Consenso aggiornato.", "success")
        return redirect(url_for("dettaglio_cliente", id_cliente=id_cliente))

    @app.route("/clienti/<id_cliente>/informativa.pdf")
    def informativa_privacy_pdf(id_cliente):
        """Genera PDF dell'informativa privacy per il cliente (GDPR Art. 13)."""
        u = g.utente_corrente
        if not u or not u.ha_permesso("clienti.leggi"):
            abort(403)
        gc = get_clienti()
        c = gc.get(id_cliente)
        if not c:
            abort(404)
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
        from reportlab.lib import colors
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4,
                                leftMargin=2.5*cm, rightMargin=2.5*cm,
                                topMargin=2.5*cm, bottomMargin=2.5*cm)
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle("title", parent=styles["Title"],
                                     fontSize=14, spaceAfter=6)
        h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=11, spaceAfter=4)
        body = ParagraphStyle("body", parent=styles["Normal"], fontSize=9,
                              spaceAfter=6, leading=14)
        studio = os.getenv("PCT_STUDIO_NOME", "Studio Legale")
        elementi = [
            Paragraph("INFORMATIVA SUL TRATTAMENTO DEI DATI PERSONALI", title_style),
            Paragraph("ai sensi degli artt. 13-14 del Regolamento UE 2016/679 (GDPR)", body),
            HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1a3a5c")),
            Spacer(1, 0.4*cm),
            Paragraph("1. Titolare del trattamento", h2),
            Paragraph(f"{studio} — i recapiti sono disponibili presso lo studio.", body),
            Paragraph("2. Finalità e base giuridica del trattamento", h2),
            Paragraph("I Suoi dati personali sono trattati per l'erogazione di servizi legali, "
                      "la gestione dei fascicoli e procedimenti giudiziari e stragiudiziali, "
                      "nonché per adempiere ad obblighi legali e contabili. "
                      "La base giuridica è l'esecuzione di un contratto (art. 6.1.b GDPR) "
                      "e l'adempimento di obblighi legali (art. 6.1.c GDPR).", body),
            Paragraph("3. Categorie di dati trattati", h2),
            Paragraph("Dati anagrafici e di contatto, codice fiscale, dati relativi a procedimenti "
                      "giudiziari, dati economici e patrimoniali strettamente necessari "
                      "all'esercizio dell'attività professionale.", body),
            Paragraph("4. Destinatari dei dati", h2),
            Paragraph("I Suoi dati possono essere comunicati ad autorità giudiziarie e "
                      "amministrative, alla controparte e ai suoi difensori, nonché "
                      "a consulenti tecnici e periti nell'ambito dei procedimenti. "
                      "Non vengono trasferiti a Paesi terzi.", body),
            Paragraph("5. Periodo di conservazione", h2),
            Paragraph("I dati saranno conservati per l'intera durata del rapporto professionale "
                      "e per i successivi 10 anni, ai sensi dell'art. 2220 c.c. e delle norme "
                      "deontologiche forensi.", body),
            Paragraph("6. Diritti dell'interessato", h2),
            Paragraph("Ha diritto di accedere ai Suoi dati (art. 15), rettificarli (art. 16), "
                      "cancellarli (art. 17), limitarne il trattamento (art. 18), "
                      "riceverne copia portabile (art. 20) e opporsi al trattamento (art. 21). "
                      "Può esercitare tali diritti contattando direttamente lo studio.", body),
            Paragraph("7. Diritto di reclamo", h2),
            Paragraph("Ha il diritto di proporre reclamo al Garante per la protezione dei "
                      "dati personali (www.garanteprivacy.it).", body),
            Spacer(1, 1*cm),
            HRFlowable(width="100%", thickness=0.5, color=colors.grey),
            Spacer(1, 0.3*cm),
            Paragraph(f"Informativa generata il {date.today().strftime('%d/%m/%Y')} "
                      f"per: <b>{c.nome_completo}</b>", body),
        ]
        doc.build(elementi)
        buf.seek(0)
        audit("clienti.informativa_pdf", "cliente", id_cliente,
              dettagli=f"PDF Art.13 — {c.nome_completo}")
        nome = f"informativa_{c.nome_completo.replace(' ', '_').lower()}.pdf"
        resp = send_file(buf, as_attachment=True, download_name=nome,
                         mimetype="application/pdf")
        return resp

    @app.route("/clienti/<id_cliente>/porta-via")
    def gdpr_portabilita(id_cliente):
        """Esporta dati personali del cliente in JSON strutturato (GDPR Art. 20)."""
        u = g.utente_corrente
        if not u or not u.ha_permesso("clienti.leggi"):
            abort(403)
        gc = get_clienti()
        c = gc.get(id_cliente)
        if not c:
            abort(404)
        gf = get_fascicoli()
        fascicoli_cliente = [f for f in gf.tutti() if f.id_cliente == id_cliente]
        export = {
            "metadati": {
                "standard": "GDPR Art. 20 — Portabilità dei dati personali",
                "regolamento": "Reg. UE 2016/679",
                "data_estrazione": datetime.now().isoformat(),
                "estratto_da": u.username,
                "versione": "1.0",
            },
            "anagrafica": {
                "tipo": c.tipo.value,
                "nome": c.nome,
                "cognome": c.cognome,
                "ragione_sociale": c.ragione_sociale,
                "codice_fiscale": c.codice_fiscale,
                "partita_iva": c.partita_iva,
                "data_nascita": c.data_nascita,
                "luogo_nascita": c.luogo_nascita,
                "provincia_nascita": c.provincia_nascita,
                "nazionalita": c.nazionalita,
                "sesso": c.sesso,
                "forma_giuridica": c.forma_giuridica,
                "rappresentante_legale": c.rappresentante_legale,
            },
            "recapiti": {
                "telefono": c.recapiti.telefono,
                "cellulare": c.recapiti.cellulare,
                "email": c.recapiti.email,
                "pec": c.recapiti.pec,
                "fax": c.recapiti.fax,
            },
            "indirizzi": {
                "residenza": str(c.indirizzo_residenza) or None,
                "domicilio": str(c.indirizzo_domicilio) or None,
                "sede_legale": str(c.indirizzo_sede_legale) or None,
            },
            "dati_studio": {
                "avvocato_referente": c.avvocato_referente,
                "data_prima_acquisizione": c.data_prima_acquisizione,
                "stato": c.stato.value,
                "provenienza": c.provenienza,
                "note": c.note,
            },
            "procedimenti": [
                {
                    "numero_rg": p.numero_rg,
                    "anno": p.anno,
                    "tribunale": p.tribunale,
                    "descrizione": p.descrizione,
                    "data_apertura": p.data_apertura,
                    "data_chiusura": p.data_chiusura,
                    "attivo": p.attivo,
                }
                for p in c.procedimenti
            ],
            "fascicoli": [
                {
                    "numero": f.numero,
                    "titolo": f.titolo,
                    "tipo": f.tipo.value,
                    "stato": f.stato.value,
                    "data_apertura": f.data_apertura,
                    "n_documenti": len(f.documenti),
                }
                for f in fascicoli_cliente
            ],
        }
        audit("gdpr.portabilita", "cliente", id_cliente,
              dettagli=f"Export Art.20 — {c.nome_completo}")
        nome = f"dati_{c.nome_completo.replace(' ', '_').lower()}_{date.today().isoformat()}.json"
        resp = Response(
            json.dumps(export, ensure_ascii=False, indent=2),
            mimetype="application/json",
        )
        resp.headers["Content-Disposition"] = f'attachment; filename="{nome}"'
        return resp

    @app.route("/audit/esporta.csv")
    def esporta_audit_csv():
        """Esporta l'audit log come file CSV (richiede permesso audit.leggi)."""
        u = g.utente_corrente
        if not u or not u.ha_permesso("audit.leggi"):
            abort(403)
        gu = get_utenti()
        csv_data = gu.esporta_audit_csv(
            id_utente=request.args.get("id_utente", ""),
            azione=request.args.get("azione", ""),
            da=request.args.get("da") or None,
            a=request.args.get("a") or None,
        )
        audit("audit.esporta_csv")
        resp = Response(csv_data, mimetype="text/csv; charset=utf-8")
        resp.headers["Content-Disposition"] = (
            f'attachment; filename="audit_{date.today().isoformat()}.csv"'
        )
        return resp

    @app.route("/admin/database/export")
    def admin_database_export():
        """Esporta ZIP completo di tutti i dati."""
        u = g.utente_corrente
        if not u or not u.ha_permesso("utenti.leggi"):
            flash("Accesso riservato agli amministratori.", "danger")
            return redirect(url_for("dashboard"))
        import tempfile
        output_dir = tempfile.mkdtemp(prefix="hacs_export_")
        db = get_database()
        zip_path = db.esporta_tutto(output_dir)
        nome_file = f"export_{date.today().isoformat()}.zip"
        audit("database.esporta_zip")
        return send_file(zip_path, as_attachment=True, download_name=nome_file, mimetype="application/zip")

    # ================================================================ BLUEPRINTS
    # Importati qui (non in cima) per evitare import circolari:
    # i blueprint usano web.helpers che usa current_app, valido solo dentro create_app().
    from web.blueprints.api_v1 import api_v1        # REST API /api/v1/*
    app.register_blueprint(api_v1)

    from web.blueprints.portale import portale as portale_bp  # Portale cliente /portale/*
    app.register_blueprint(portale_bp)

    from web.blueprints.fatturazione import fatturazione as fatturazione_bp  # Parcelle /fatturazione/*
    app.register_blueprint(fatturazione_bp)

    from web.blueprints.notifiche import notifiche as notifiche_bp  # WhatsApp /notifiche/*
    app.register_blueprint(notifiche_bp)

    from web.blueprints.template_atti import template_atti as template_atti_bp  # Template atti /template-atti/*
    app.register_blueprint(template_atti_bp)

    from web.blueprints.statistiche import statistiche as statistiche_bp  # Statistiche /statistiche/*
    app.register_blueprint(statistiche_bp)

    from web.blueprints.legal_intelligence import legal_intelligence as legal_intelligence_bp  # Motori legali /legal-intelligence/*
    app.register_blueprint(legal_intelligence_bp)

    from web.blueprints.export_csv import export_csv as export_csv_bp  # Export CSV /export/*
    app.register_blueprint(export_csv_bp)

    from web.blueprints.pagamenti import pagamenti as pagamenti_bp  # Pagamenti digitali
    app.register_blueprint(pagamenti_bp)

    from web.blueprints.admin import admin_bp  # Pannello Admin multi-tenant /admin/*
    app.register_blueprint(admin_bp)

    from web.blueprints.impostazioni import impostazioni as impostazioni_bp  # Impostazioni studio /impostazioni/*
    app.register_blueprint(impostazioni_bp)

    from web.blueprints.email_client import email_client as email_client_bp  # Client email /email/*
    app.register_blueprint(email_client_bp)

    from web.blueprints.assistente import assistente as assistente_bp  # Assistente PCT /api/assistente/*
    app.register_blueprint(assistente_bp)

    from web.blueprints.preventivi import preventivi as preventivi_bp  # Preventivi e incarichi /preventivi/*
    app.register_blueprint(preventivi_bp)

    from web.blueprints.wizard_pro import wizard_pro_bp  # Wizard Pro /wizard-pro/*
    app.register_blueprint(wizard_pro_bp)

    # ----------------------------------------------------------------
    # iCal — download diretto (retrocompatibilità)
    # ----------------------------------------------------------------

    @app.route("/agenda/export.ics")
    def agenda_ical():
        from pct.ical import agenda_to_ical
        ag = get_agenda()
        studio_nome = app.config.get("STUDIO_NOME", "Studio Legale PCT")
        base_url = request.host_url.rstrip("/").replace("http://", "https://", 1)
        ical_str = agenda_to_ical(ag.tutti(), studio_nome=studio_nome, base_url=base_url)
        return Response(ical_str, mimetype="text/calendar; charset=utf-8",
                        headers={"Content-Disposition": "attachment; filename=agenda.ics"})

    @app.route("/scadenziario/export.ics")
    def scadenziario_ical():
        from pct.ical import scadenze_to_ical
        gs = get_scadenziario()
        studio_nome = app.config.get("STUDIO_NOME", "Studio Legale PCT")
        ical_str = scadenze_to_ical(gs.tutte(), studio_nome=studio_nome)
        return Response(ical_str, mimetype="text/calendar; charset=utf-8",
                        headers={"Content-Disposition": "attachment; filename=scadenze.ics"})

    # ----------------------------------------------------------------
    # WebCal — feed live per subscription automatica
    # URL: /cal/<token>/agenda.ics  (webcal:// o https://)
    # Token segreto: pct/cal_token.py  →  ./agenda/cal_token.json
    # ----------------------------------------------------------------

    def _cal_token_dir() -> str:
        """Directory dove viene salvato il token (accanto all'agenda DB)."""
        agenda_db = app.config.get("AGENDA_DB", "./agenda/appuntamenti.json")
        return os.path.dirname(os.path.abspath(agenda_db))

    def _cal_token_valido(token: str) -> bool:
        from pct.cal_token import get_token
        try:
            return get_token(_cal_token_dir()).get("token") == token
        except Exception:
            return False

    def _get_base_url() -> str:
        """Restituisce la base URL pubblica (sempre HTTPS in produzione).

        Priorità:
        1. PCT_BASE_URL env var — impostare su Railway/Render per URL stabile
           (es. https://mio-studio.up.railway.app)
        2. request.host_url aggiornato da ProxyFix (funziona se X-Forwarded-Proto è impostato)
        3. Fallback: forza https:// su qualunque schema rilevato

        Imposta PCT_BASE_URL nelle variabili d'ambiente Railway per eliminare
        qualsiasi ambiguità HTTP/HTTPS nei feed iCal.
        """
        # 1. URL esplicito configurato dall'amministratore
        configured = os.getenv("PCT_BASE_URL", "").rstrip("/")
        if configured:
            return configured
        # 2. Legge request.host_url (ProxyFix la aggiorna con X-Forwarded-Proto)
        #    e come safety net forza sempre https:// se il deploy è in produzione
        base = request.host_url.rstrip("/")
        if base.startswith("http://"):
            # ProxyFix non ha ricevuto X-Forwarded-Proto → forza https manualmente
            base = "https://" + base[len("http://"):]
        return base

    @app.route("/cal/<token>/agenda.ics")
    def cal_feed_agenda(token):
        if not _cal_token_valido(token):
            return Response("Token non valido.", status=403, mimetype="text/plain")
        from pct.ical import agenda_to_ical
        ag = get_agenda()
        studio_nome = app.config.get("STUDIO_NOME", "Studio Legale PCT")
        base_url = _get_base_url()
        ical_str = agenda_to_ical(ag.tutti(), studio_nome=studio_nome, base_url=base_url)
        return Response(ical_str, mimetype="text/calendar; charset=utf-8",
                        headers={"Cache-Control": "no-cache, no-store"})

    @app.route("/cal/<token>/scadenze.ics")
    def cal_feed_scadenze(token):
        if not _cal_token_valido(token):
            return Response("Token non valido.", status=403, mimetype="text/plain")
        from pct.ical import scadenze_to_ical
        gs = get_scadenziario()
        studio_nome = app.config.get("STUDIO_NOME", "Studio Legale PCT")
        ical_str = scadenze_to_ical(gs.tutte(), studio_nome=studio_nome)
        return Response(ical_str, mimetype="text/calendar; charset=utf-8",
                        headers={"Cache-Control": "no-cache, no-store"})

    @app.route("/cal/<token>/completo.ics")
    def cal_feed_completo(token):
        if not _cal_token_valido(token):
            return Response("Token non valido.", status=403, mimetype="text/plain")
        from pct.ical import agenda_scadenze_to_ical
        ag = get_agenda()
        gs = get_scadenziario()
        studio_nome = app.config.get("STUDIO_NOME", "Studio Legale PCT")
        base_url = _get_base_url()
        ical_str = agenda_scadenze_to_ical(
            ag.tutti(), gs.tutte(), studio_nome=studio_nome, base_url=base_url
        )
        return Response(ical_str, mimetype="text/calendar; charset=utf-8",
                        headers={"Cache-Control": "no-cache, no-store"})

    # ----------------------------------------------------------------
    # Impostazioni calendario — pannello subscription
    # ----------------------------------------------------------------

    @app.route("/impostazioni/calendario")
    def impostazioni_calendario():
        from pct.cal_token import get_token
        token_data = get_token(_cal_token_dir())
        token = token_data["token"]
        base = _get_base_url()
        feeds = {
            "agenda":   f"{base}/cal/{token}/agenda.ics",
            "scadenze": f"{base}/cal/{token}/scadenze.ics",
            "completo": f"{base}/cal/{token}/completo.ics",
        }
        # Link Google Calendar — forza sempre https:// (requisito Google)
        from urllib.parse import quote
        gcal_completo = (
            "https://calendar.google.com/calendar/r/settings/addbyurl"
            f"?url={quote(feeds['completo'], safe='')}"
        )
        return render_template(
            "impostazioni/calendario.html",
            token=token,
            token_creato=token_data.get("creato_il", ""),
            feeds=feeds,
            gcal_url=gcal_completo,
        )

    @app.route("/impostazioni/calendario/rigenera", methods=["POST"])
    def rigenera_token_calendario():
        from pct.cal_token import rigenera_token
        rigenera_token(_cal_token_dir())
        flash("Token calendario rigenerato. Aggiorna i link nei tuoi calendari.", "success")
        return redirect(url_for("impostazioni_calendario"))

    # ----------------------------------------------------------------
    # API — badge scadenze urgenti (in-app, usato da base.html JS)
    # ----------------------------------------------------------------

    @app.route("/api/scadenze/urgenti")
    def api_scadenze_urgenti():
        """Conta scadenze aperte entro 7 giorni — usato dal badge navbar."""
        try:
            from datetime import timedelta
            gs = get_scadenziario()
            oggi_str = date.today().isoformat()
            soglia = (date.today() + timedelta(days=7)).isoformat()
            n = sum(
                1 for s in gs.tutte()
                if getattr(s, "data_scadenza", "") and oggi_str <= s.data_scadenza <= soglia
                and getattr(s, "stato", None) and s.stato.value not in ("COMPLETATO", "ANNULLATO", "SCADUTO")
            )
            return jsonify({"n": n})
        except Exception as e:
            app.logger.exception("api_scadenze_urgenti: %s", e)
            return jsonify({"n": 0})

    # ---- OCR route (su documento di un fascicolo)
    @app.route("/fascicoli/<id_fasc>/documenti/<id_doc>/ocr", methods=["POST"])
    def ocr_documento(id_fasc, id_doc):
        gf = get_fascicoli()
        f = gf.get(id_fasc)
        if not f:
            abort(404)
        doc = next((d for d in getattr(f, "documenti", []) if d.id == id_doc), None)
        if not doc:
            abort(404)
        from pct.ocr import estrai_testo
        percorso = gf.percorso_documento(id_fasc, id_doc)
        testo = estrai_testo(percorso) if percorso else ""
        if testo:
            try:
                from web.helpers import get_indice
                indice = get_indice()
                indice.indicizza(
                    tipo="documento",
                    id=f"{id_fasc}_{id_doc}",
                    titolo=doc.nome_file,
                    testo=testo,
                    meta={"id_fascicolo": id_fasc},
                )
            except Exception:
                pass
            flash(f"Testo estratto ({len(testo)} caratteri) e indicizzato.", "success")
        else:
            flash("Nessun testo estraibile da questo documento.", "warning")
        return redirect(url_for("dettaglio_fascicolo", id_fascicolo=id_fasc))

    # ---------------------------------------------------------------- Checklist Atti
    @app.route("/checklist")
    def checklist_atti():
        from pct.checklist_atti import TUTTI_I_TEMPLATE, CATEGORIE, CAT_ICON, CAT_COL
        per_cat = {}
        for t in TUTTI_I_TEMPLATE:
            per_cat.setdefault(t.categoria, []).append(t)
        return render_template(
            "checklist/lista.html",
            per_cat=per_cat,
            categorie=CATEGORIE,
            cat_icon=CAT_ICON,
            cat_col=CAT_COL,
            oggi=date.today(),
        )

    @app.route("/checklist/<id_template>")
    def checklist_dettaglio(id_template):
        from pct.checklist_atti import get_template, nome_cartella_compilato, CAT_ICON, CAT_COL
        tmpl = get_template(id_template)
        if not tmpl:
            flash("Template non trovato.", "warning")
            return redirect(url_for("checklist_atti"))
        # Fascicolo opzionale — pre-compila i parametri se passato
        id_fasc  = request.args.get("id_fasc", "")
        fascicolo_ctx = None
        if id_fasc:
            fasc = get_fascicoli().get(id_fasc)
            if fasc:
                fascicolo_ctx = fasc
        # Parametri espliciti o derivati dal fascicolo
        parte = request.args.get("parte") or (fascicolo_ctx.controparte if fascicolo_ctx else "")
        rg    = request.args.get("rg")    or (getattr(fascicolo_ctx, "numero_rg", "") if fascicolo_ctx else "")
        data  = request.args.get("data", date.today().isoformat())
        cartella = nome_cartella_compilato(tmpl, parte=parte, rg=rg, data=data)
        return render_template(
            "checklist/dettaglio.html",
            tmpl=tmpl,
            cartella=cartella,
            parte=parte,
            rg=rg,
            data=data,
            id_fasc=id_fasc,
            fascicolo=fascicolo_ctx,
            cat_icon=CAT_ICON,
            cat_col=CAT_COL,
            oggi=date.today(),
        )

    # ---- Wizard guidato preparazione atto

    def _wizard_step_stato(fasc, doc_richiesto, id_template):
        """Ritorna 'done' o 'pending' per uno step del wizard."""
        nota_tag = f"[wizard:{id_template}:step{doc_richiesto.numero}]"
        nome_prefix = doc_richiesto.nome_file.lower()
        for d in fasc.documenti:
            if nota_tag in (d.note or ""):
                return "done"
            if d.nome.lower().startswith(nome_prefix):
                return "done"
        return "pending"

    def _trova_documento_wizard(fasc, doc_richiesto, id_template):
        """Cerca il documento nel fascicolo corrispondente allo step wizard."""
        nota_tag = f"[wizard:{id_template}:step{doc_richiesto.numero}]"
        nome_prefix = doc_richiesto.nome_file.lower()
        for d in fasc.documenti:
            if nota_tag in (d.note or ""):
                return d
            if d.nome.lower().startswith(nome_prefix):
                return d
        return None

    @app.route("/fascicoli/<id_fasc>/wizard/<id_template>")
    def wizard_atto_avvia(id_fasc, id_template):
        """Avvia o riprende il wizard: redirect al primo step obbligatorio incompleto."""
        from pct.checklist_atti import get_template
        gf = get_fascicoli()
        fasc = gf.get(id_fasc)
        if not fasc:
            flash("Fascicolo non trovato.", "danger")
            return redirect(url_for("lista_fascicoli"))
        tmpl = get_template(id_template)
        if not tmpl:
            flash("Template non trovato.", "danger")
            return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))
        # Trova primo step obbligatorio incompleto
        for doc in tmpl.documenti:
            if _wizard_step_stato(fasc, doc, id_template) == "pending" and doc.obbligatorio:
                return redirect(url_for("wizard_atto_step", id_fasc=id_fasc,
                                        id_template=id_template, n=doc.numero))
        # Tutti gli obbligatori completati → pagina di completamento
        return redirect(url_for("wizard_atto_completa", id_fasc=id_fasc,
                                id_template=id_template))

    @app.route("/fascicoli/<id_fasc>/wizard/<id_template>/step/<int:n>",
               methods=["GET", "POST"])
    def wizard_atto_step(id_fasc, id_template, n):
        from pct.checklist_atti import get_template, nome_cartella_compilato
        gf = get_fascicoli()
        fasc = gf.get(id_fasc)
        if not fasc:
            flash("Fascicolo non trovato.", "danger")
            return redirect(url_for("lista_fascicoli"))
        tmpl = get_template(id_template)
        if not tmpl:
            flash("Template non trovato.", "danger")
            return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))
        doc_step = next((d for d in tmpl.documenti if d.numero == n), None)
        if not doc_step:
            flash("Step non trovato.", "danger")
            return redirect(url_for("wizard_atto_avvia", id_fasc=id_fasc,
                                    id_template=id_template))

        if request.method == "POST":
            azione = request.form.get("azione", "carica")
            u = g.utente_corrente

            if azione == "salta" and not doc_step.obbligatorio:
                skip_key = f"wiz_skip_{id_fasc}_{id_template}"
                skipped = session.get(skip_key, [])
                if n not in skipped:
                    skipped.append(n)
                session[skip_key] = skipped
                flash(f"«{doc_step.descrizione}» saltato.", "info")

            elif azione == "carica":
                if "file" not in request.files or not request.files["file"].filename:
                    flash("Seleziona un file da caricare.", "warning")
                    return redirect(url_for("wizard_atto_step", id_fasc=id_fasc,
                                            id_template=id_template, n=n))
                file = request.files["file"]
                ext = Path(file.filename).suffix or ".pdf"
                nome_wizard = f"{doc_step.nome_file}{ext}"
                try:
                    contenuto = _encrypt_doc(file.read())
                    nota_w = f"[wizard:{id_template}:step{n}]"
                    nota_extra = request.form.get("note", "").strip()
                    if nota_extra:
                        nota_w += f" {nota_extra}"
                    gf.aggiungi_documento(
                        id_fasc,
                        nome_file=nome_wizard,
                        tipo=TipoDocumento(request.form.get("tipo_doc", "ALTRO")),
                        contenuto=contenuto,
                        note=nota_w,
                        data_documento=request.form.get("data_documento", ""),
                        firmato=request.form.get("firmato") == "1",
                        caricato_da=u.username if u else "",
                    )
                    flash(f"«{doc_step.descrizione}» caricato come {nome_wizard}.", "success")
                    audit("fascicoli.wizard.carica", "fascicolo", id_fasc,
                          dettagli=f"template:{id_template} step:{n} → {nome_wizard}")
                except (ValueError, KeyError) as e:
                    flash(str(e), "danger")
                    return redirect(url_for("wizard_atto_step", id_fasc=id_fasc,
                                            id_template=id_template, n=n))

            # Vai al prossimo step
            prossimo = n + 1
            if prossimo <= len(tmpl.documenti):
                return redirect(url_for("wizard_atto_step", id_fasc=id_fasc,
                                        id_template=id_template, n=prossimo))
            return redirect(url_for("wizard_atto_completa", id_fasc=id_fasc,
                                    id_template=id_template))

        # GET — prepara stato di tutti gli step
        skip_key = f"wiz_skip_{id_fasc}_{id_template}"
        skipped = session.get(skip_key, [])
        steps_stato = []
        for d in tmpl.documenti:
            stato = _wizard_step_stato(fasc, d, id_template)
            if stato == "pending" and not d.obbligatorio and d.numero in skipped:
                stato = "saltato"
            steps_stato.append({
                "doc": d,
                "stato": stato,
                "documento": _trova_documento_wizard(fasc, d, id_template),
            })

        doc_esistente = _trova_documento_wizard(fasc, doc_step, id_template)
        nome_cartella = nome_cartella_compilato(tmpl, fasc.controparte, fasc.numero_rg)
        return render_template(
            "fascicoli/wizard_atto.html",
            fascicolo=fasc,
            tmpl=tmpl,
            step_corrente=doc_step,
            step_n=n,
            step_totale=len(tmpl.documenti),
            steps_stato=steps_stato,
            doc_esistente=doc_esistente,
            nome_cartella=nome_cartella,
            oggi=date.today(),
            tipo_documento_choices=[(t.value, t.value.replace("_", " ").title())
                                    for t in TipoDocumento],
        )

    @app.route("/fascicoli/<id_fasc>/wizard/<id_template>/completa")
    def wizard_atto_completa(id_fasc, id_template):
        from pct.checklist_atti import (get_template, nome_cartella_compilato,
                                        CANALE_LABEL, CANALE_ICON, CANALE_COL)
        gf = get_fascicoli()
        fasc = gf.get(id_fasc)
        if not fasc:
            flash("Fascicolo non trovato.", "danger")
            return redirect(url_for("lista_fascicoli"))
        tmpl = get_template(id_template)
        if not tmpl:
            flash("Template non trovato.", "danger")
            return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))

        skip_key = f"wiz_skip_{id_fasc}_{id_template}"
        skipped = session.get(skip_key, [])
        steps_stato = []
        tutti_obbligatori = True
        for d in tmpl.documenti:
            stato = _wizard_step_stato(fasc, d, id_template)
            if stato == "pending" and not d.obbligatorio and d.numero in skipped:
                stato = "saltato"
            if d.obbligatorio and stato == "pending":
                tutti_obbligatori = False
            steps_stato.append({
                "doc": d,
                "stato": stato,
                "documento": _trova_documento_wizard(fasc, d, id_template),
            })

        nome_cartella = nome_cartella_compilato(tmpl, fasc.controparte, fasc.numero_rg)

        # Cerca PEC del tribunale per il modal deposito
        import os as _os
        pec_tribunale = ""
        if fasc.tribunale:
            try:
                from pct.uffici_giudiziari import get_gestore as _get_uff
                _cache = _os.getenv("PCT_UFFICI_DB", "/data/uffici/uffici_giudiziari.json")
                _uff = next(
                    (u for u in _get_uff(_cache).carica()
                     if u.get("nome", "").lower() == fasc.tribunale.lower()),
                    None,
                )
                pec_tribunale = _uff["pec"] if _uff else ""
            except Exception:
                pass

        # Verifica se PEC studio è configurata (per mostrare bottone invio diretto)
        pec_configurata = False
        try:
            _cfg = get_config_studio().config
            pec_configurata = bool(_cfg and _cfg.pec and _cfg.pec.indirizzo and _cfg.pec.password)
        except Exception:
            pass

        return render_template(
            "fascicoli/wizard_completa.html",
            fascicolo=fasc,
            tmpl=tmpl,
            steps_stato=steps_stato,
            tutti_obbligatori=tutti_obbligatori,
            nome_cartella=nome_cartella,
            pec_tribunale=pec_tribunale,
            pec_configurata=pec_configurata,
            canale_label=CANALE_LABEL,
            canale_icon=CANALE_ICON,
            canale_col=CANALE_COL,
            oggi=date.today(),
        )

    @app.route("/fascicoli/<id_fasc>/wizard/<id_template>/genera-indice", methods=["POST"])
    def wizard_genera_indice(id_fasc, id_template):
        from pct.checklist_atti import get_template, nome_cartella_compilato
        from datetime import datetime as _dt
        gf = get_fascicoli()
        fasc = gf.get(id_fasc)
        if not fasc:
            flash("Fascicolo non trovato.", "danger")
            return redirect(url_for("lista_fascicoli"))
        tmpl = get_template(id_template)
        if not tmpl:
            flash("Template non trovato.", "danger")
            return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))

        u = g.utente_corrente
        skip_key = f"wiz_skip_{id_fasc}_{id_template}"
        skipped = session.get(skip_key, [])
        nome_cartella = nome_cartella_compilato(tmpl, fasc.controparte, fasc.numero_rg)

        righe = []
        for d in tmpl.documenti:
            doc_fasc = _trova_documento_wizard(fasc, d, id_template)
            if doc_fasc:
                righe.append(
                    f"  {d.numero:02d}. {doc_fasc.nome}\n"
                    f"      {d.descrizione}"
                    f" | {doc_fasc.data_documento or 'data n.d.'}"
                    f" | sha256: {doc_fasc.hash_sha256[:16]}…"
                )
            elif not d.obbligatorio and d.numero in skipped:
                righe.append(f"  {d.numero:02d}. [non allegato] {d.nome_file}  ({d.descrizione} — facoltativo)")
            else:
                righe.append(f"  {d.numero:02d}. [MANCANTE] {d.nome_file}  ({d.descrizione})")

        sep = "═" * 64
        testo = "\n".join([
            sep,
            f"  INDICE DOCUMENTI — {tmpl.nome.upper()}",
            sep,
            f"  Fascicolo  : {fasc.titolo}",
            f"  RG         : {fasc.rg_completo or 'n.d.'}",
            f"  Cliente    : {fasc.nome_cliente}",
            f"  Controparte: {fasc.controparte}",
            f"  Tribunale  : {fasc.tribunale or 'n.d.'}",
            f"  Cartella   : {nome_cartella}",
            f"  Generato il: {_dt.now().strftime('%d/%m/%Y %H:%M')}",
            sep,
            "",
            *righe,
            "",
            sep,
        ])

        try:
            contenuto_enc = _encrypt_doc(testo.encode("utf-8"))
            nome_indice = f"00_Indice_{tmpl.id}.txt"
            gf.aggiungi_documento(
                id_fasc,
                nome_file=nome_indice,
                tipo=TipoDocumento.ALTRO,
                contenuto=contenuto_enc,
                note=f"[wizard:{id_template}:indice] Indice generato automaticamente",
                caricato_da=u.username if u else "",
            )
            flash(f"Indice «{nome_indice}» generato e aggiunto al fascicolo.", "success")
            audit("fascicoli.wizard.indice", "fascicolo", id_fasc,
                  dettagli=f"template:{id_template}")
        except Exception as e:
            app.logger.exception("Errore wizard_genera_indice %s: %s", id_fasc, e)
            flash(f"Errore generazione indice: {e}", "danger")

        return redirect(url_for("wizard_atto_completa", id_fasc=id_fasc,
                                id_template=id_template))

    # ================================================================ Soggetti
    # Anagrafica soggetti processuali (controparti, difensori, testimoni, ecc.)

    @app.route("/soggetti")
    def lista_soggetti():
        gs = get_soggetti()
        q = request.args.get("q", "").strip()
        tipo_f = request.args.get("tipo", "").strip()
        soggetti = gs.cerca(q=q, tipo=tipo_f)
        return render_template(
            "soggetti/lista.html",
            soggetti=soggetti,
            q=q,
            tipo_f=tipo_f,
            oggi=date.today(),
        )

    @app.route("/soggetti/nuovo", methods=["GET", "POST"])
    def nuovo_soggetto():
        gs = get_soggetti()
        clienti_list = get_clienti().tutti()
        if request.method == "POST":
            tipo_val = request.form.get("tipo", "PERSONA_FISICA")
            try:
                tipo = TipoSoggetto(tipo_val)
            except ValueError:
                tipo = TipoSoggetto.PERSONA_FISICA
            from pct.clienti import Indirizzo as _Ind, Recapiti as _Rec
            indirizzo = _Ind(
                via=request.form.get("via", ""),
                civico=request.form.get("civico", ""),
                cap=request.form.get("cap", ""),
                comune=request.form.get("comune", ""),
                provincia=request.form.get("provincia", ""),
                nazione=request.form.get("nazione", "Italia"),
            )
            recapiti = _Rec(
                telefono=request.form.get("telefono", ""),
                cellulare=request.form.get("cellulare", ""),
                email=request.form.get("email", ""),
                pec=request.form.get("pec", ""),
                fax=request.form.get("fax", ""),
                sito_web=request.form.get("sito_web", ""),
            )
            tag_raw = request.form.get("tag", "")
            tag = [t.strip() for t in tag_raw.split(",") if t.strip()]
            s = gs.crea(
                tipo=tipo,
                nome=request.form.get("nome", ""),
                cognome=request.form.get("cognome", ""),
                codice_fiscale=request.form.get("codice_fiscale", ""),
                data_nascita=request.form.get("data_nascita", ""),
                luogo_nascita=request.form.get("luogo_nascita", ""),
                sesso=request.form.get("sesso", ""),
                ragione_sociale=request.form.get("ragione_sociale", ""),
                partita_iva=request.form.get("partita_iva", ""),
                forma_giuridica=request.form.get("forma_giuridica", ""),
                rappresentante_legale=request.form.get("rappresentante_legale", ""),
                qualifica=request.form.get("qualifica", ""),
                ordine=request.form.get("ordine", ""),
                numero_iscrizione=request.form.get("numero_iscrizione", ""),
                indirizzo=indirizzo,
                recapiti=recapiti,
                id_cliente=request.form.get("id_cliente", ""),
                note=request.form.get("note", ""),
                tag=tag,
            )
            audit("soggetti.crea", "soggetto", s.id, dettagli=s.nome_completo)
            flash(f"Soggetto «{s.nome_completo}» creato.", "success")
            return redirect(url_for("dettaglio_soggetto", id_soggetto=s.id))
        # Pre-popola da query string (es. proveniente da scheda cliente)
        prefill = {k: request.args.get(k, "") for k in (
            "tipo", "nome", "cognome", "ragione_sociale",
            "codice_fiscale", "partita_iva",
            "email", "cellulare", "telefono", "pec", "id_cliente",
        )}
        return render_template(
            "soggetti/form.html",
            soggetto=None,
            clienti=clienti_list,
            TipoSoggetto=TipoSoggetto,
            oggi=date.today(),
            prefill=prefill,
        )

    @app.route("/soggetti/<id_soggetto>")
    def dettaglio_soggetto(id_soggetto):
        gs = get_soggetti()
        s = gs.get(id_soggetto)
        if not s:
            abort(404)
        ids_fascicoli = gs.fascicoli_con_soggetto(id_soggetto)
        gf = get_fascicoli()
        fascicoli_collegati = [f for f in [gf.get(i) for i in ids_fascicoli] if f]
        cliente_collegato = None
        if s.id_cliente:
            cliente_collegato = get_clienti().get(s.id_cliente)
        return render_template(
            "soggetti/dettaglio.html",
            soggetto=s,
            fascicoli_collegati=fascicoli_collegati,
            cliente_collegato=cliente_collegato,
            oggi=date.today(),
        )

    @app.route("/soggetti/<id_soggetto>/modifica", methods=["GET", "POST"])
    def modifica_soggetto(id_soggetto):
        gs = get_soggetti()
        s = gs.get(id_soggetto)
        if not s:
            abort(404)
        clienti_list = get_clienti().tutti()
        if request.method == "POST":
            tipo_val = request.form.get("tipo", s.tipo.value)
            try:
                tipo = TipoSoggetto(tipo_val)
            except ValueError:
                tipo = s.tipo
            from pct.clienti import Indirizzo as _Ind, Recapiti as _Rec
            indirizzo = _Ind(
                via=request.form.get("via", ""),
                civico=request.form.get("civico", ""),
                cap=request.form.get("cap", ""),
                comune=request.form.get("comune", ""),
                provincia=request.form.get("provincia", ""),
                nazione=request.form.get("nazione", "Italia"),
            )
            recapiti = _Rec(
                telefono=request.form.get("telefono", ""),
                cellulare=request.form.get("cellulare", ""),
                email=request.form.get("email", ""),
                pec=request.form.get("pec", ""),
                fax=request.form.get("fax", ""),
                sito_web=request.form.get("sito_web", ""),
            )
            tag_raw = request.form.get("tag", "")
            tag = [t.strip() for t in tag_raw.split(",") if t.strip()]
            gs.aggiorna(
                id_soggetto,
                tipo=tipo,
                nome=request.form.get("nome", ""),
                cognome=request.form.get("cognome", ""),
                codice_fiscale=request.form.get("codice_fiscale", ""),
                data_nascita=request.form.get("data_nascita", ""),
                luogo_nascita=request.form.get("luogo_nascita", ""),
                sesso=request.form.get("sesso", ""),
                ragione_sociale=request.form.get("ragione_sociale", ""),
                partita_iva=request.form.get("partita_iva", ""),
                forma_giuridica=request.form.get("forma_giuridica", ""),
                rappresentante_legale=request.form.get("rappresentante_legale", ""),
                qualifica=request.form.get("qualifica", ""),
                ordine=request.form.get("ordine", ""),
                numero_iscrizione=request.form.get("numero_iscrizione", ""),
                indirizzo=indirizzo,
                recapiti=recapiti,
                id_cliente=request.form.get("id_cliente", ""),
                note=request.form.get("note", ""),
                tag=tag,
            )
            audit("soggetti.modifica", "soggetto", id_soggetto, dettagli=s.nome_completo)
            flash("Soggetto aggiornato.", "success")
            return redirect(url_for("dettaglio_soggetto", id_soggetto=id_soggetto))
        return render_template(
            "soggetti/form.html",
            soggetto=s,
            clienti=clienti_list,
            TipoSoggetto=TipoSoggetto,
            oggi=date.today(),
        )

    @app.route("/soggetti/<id_soggetto>/elimina", methods=["POST"])
    def elimina_soggetto(id_soggetto):
        gs = get_soggetti()
        s = gs.get(id_soggetto)
        if s:
            nome = s.nome_completo
            gs.elimina(id_soggetto)
            audit("soggetti.elimina", "soggetto", id_soggetto, dettagli=nome)
            flash(f"Soggetto «{nome}» eliminato.", "success")
        return redirect(url_for("lista_soggetti"))

    @app.route("/api/soggetti")
    def api_soggetti():
        """Autocomplete JSON — restituisce soggetti che corrispondono a ?q=..."""
        try:
            q = request.args.get("q", "").strip()
            gs = get_soggetti()
            risultati = gs.cerca(q=q)[:20]
            return jsonify([{
                "id": s.id,
                "nome": s.nome_completo,
                "tipo": s.tipo.value,
                "sigla": s.sigla_tipo,
                "qualifica": s.qualifica,
                "identificativo": s.identificativo,
            } for s in risultati])
        except Exception as e:
            app.logger.exception("Errore api_soggetti: %s", e)
            return jsonify([])

    # ---- Parti processuali di un fascicolo

    @app.route("/fascicoli/<id_fasc>/parti/aggiungi", methods=["POST"])
    def aggiungi_parte_fascicolo(id_fasc):
        gf = get_fascicoli()
        f = gf.get(id_fasc)
        if not f:
            abort(404)
        gs = get_soggetti()
        id_soggetto = request.form.get("id_soggetto", "")
        ruolo_val = request.form.get("ruolo", "ALTRO")
        note = request.form.get("note", "")
        try:
            ruolo = RuoloSoggetto(ruolo_val)
        except ValueError:
            ruolo = RuoloSoggetto.ALTRO
        s = gs.get(id_soggetto)
        if not s:
            flash("Soggetto non trovato.", "danger")
            return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))
        gs.aggiungi_parte(id_fasc, id_soggetto, ruolo, note)
        audit("soggetti.aggiungi_parte", "fascicolo", id_fasc,
              dettagli=f"{s.nome_completo} → {ruolo.label}")
        flash(f"«{s.nome_completo}» aggiunto come {ruolo.label}.", "success")
        return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))

    @app.route("/fascicoli/<id_fasc>/parti/<id_parte>/rimuovi", methods=["POST"])
    def rimuovi_parte_fascicolo(id_fasc, id_parte):
        gs = get_soggetti()
        gs.rimuovi_parte(id_fasc, id_parte)
        audit("soggetti.rimuovi_parte", "fascicolo", id_fasc, dettagli=id_parte)
        flash("Parte rimossa dal fascicolo.", "success")
        return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))

    # ---- Avvio scheduler background
    from pct.scheduler import start_scheduler
    start_scheduler(app)

    return app
