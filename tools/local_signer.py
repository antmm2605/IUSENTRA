#!/usr/bin/env python3
"""
IUSENTRA Local Signer - v1.6.63

Servizio HTTP locale (localhost:27272) che firma documenti con smart card e token CNS/CIE
(o qualsiasi token PKCS#11) e consente l'accesso autenticato al PST.

La chiave privata NON lascia mai il dispositivo (in-device signing).

Avvio rapido:
    pip install python-pkcs11 asn1crypto cryptography flask
    python local_signer.py

    Con libreria esplicita:
    python local_signer.py --lib "C:\\Windows\\System32\\bit4xpki.dll"

API:
    GET  /ping                   → health + info token (senza PIN)
    GET  /diagnosi               → diagnostica completa: middleware, token, curl
    GET  /ai/status              → stato AI locale sul dispositivo cliente
    GET  /certificati            → elenca certificati Windows MY store
    GET  /seleziona-certificato  → apre dialog nativo Windows di selezione cert
    POST /ai/bootstrap           → provisioning runtime Ollama e modelli locali
    POST /ai/chat                → prompt locale inoltrato a Ollama
    POST /ai/chat/stream         → risposta streaming locale da Ollama
    POST /ai/rag/query           → risposta locale su contesto RAG preparato da IUSENTRA
    POST /ai/rag/query/stream    → risposta streaming locale su contesto RAG preparato da IUSENTRA
    POST /ai/embed               → embeddings locali inoltrati a Ollama
    POST /firma                  → firma documento CAdES-BES
    POST /firma-batch            → firma più documenti con una sola sessione PIN
    POST /pst/preflight-auth     → verifica certificato + prompt PIN per accesso PST
    POST /pst/ricerca            → ricerca fascicoli PST (curl mTLS Windows)
    POST /pst/documenti          → documenti fascicolo PST (curl mTLS Windows)
    POST /pst/fascicolo-snapshot → snapshot unico metadati/catalogo fascicolo PST
    POST /pdp/ricerca            → ricerca fascicoli PDP via Aruba Key / Windows cert store
    POST /pdp/documenti          → documenti fascicolo PDP via Aruba Key / Windows cert store
    POST /pat/ricerca            → ricerca fascicoli PAT via Aruba Key / Windows cert store
    POST /pat/documenti          → documenti fascicolo PAT via Aruba Key / Windows cert store
    POST /ptt/ricerca            → ricerca fascicoli PTT via Aruba Key / Windows cert store
    POST /ptt/documenti          → documenti fascicolo PTT via Aruba Key / Windows cert store
    POST /downloads/raccogli     → raccoglie file già scaricati nei download locali
    GET  /pst/status             → stato connettività PST

Note sicurezza:
    - Ascolta SOLO su 127.0.0.1 (non accessibile da rete)
    - CORS abilitato per origini localhost/127.0.0.1 e per il dominio
      ufficiale IUSENTRA https://app.iusentra.it
    - Il PIN viene usato solo per la firma, mai salvato né loggato
    - La selezione certificato usa la dialog nativa Windows: il PIN
      è gestito dal sistema operativo durante la sessione TLS
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unicodedata
import webbrowser
import xml.etree.ElementTree as ET
from email import policy
from email.parser import BytesParser
from datetime import UTC, date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlencode, urlparse

_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

try:
    from pct.uffici_giudiziari import risolvi_base_pst as _risolvi_base_pst_hacs
    from pct.uffici_giudiziari import risolvi_codice_ministero as _risolvi_codice_ministero_hacs
except Exception:
    _risolvi_base_pst_hacs = None
    _risolvi_codice_ministero_hacs = None

try:
    from local_ai_host_bridge import LocalAiHostBridge
except Exception:
    LocalAiHostBridge = None  # type: ignore[assignment]

try:
    from lex_document_context import build_attachment_prompt_block, parse_attachment_payloads
except Exception:
    build_attachment_prompt_block = None  # type: ignore[assignment]
    parse_attachment_payloads = None  # type: ignore[assignment]

from local_signer_mod.ai_handlers import LocalAiHandlerFacade  # noqa: E402
from local_signer_mod.security import (  # noqa: E402
    build_allowed_origins,
    is_allowed_origin,
    is_loopback_origin,
    normalize_origin,
)
from local_signer_mod.pec_bridge import send_pec_local, test_pec_smtp_local  # noqa: E402
from local_signer_mod.server_bootstrap import print_startup_banner  # noqa: E402

# ── Configurazione ─────────────────────────────────────────────────────────────
PORT = int(os.getenv("HACS_SIGNER_PORT", "27272"))
VERSION = "1.6.63"
LOG_LEVEL = os.getenv("HACS_SIGNER_LOG", "INFO")
PST_SOAP_MAX_TIME = int(os.getenv("HACS_SIGNER_PST_MAX_TIME", "90"))
PST_SOAP_CONNECT_TIMEOUT = int(os.getenv("HACS_SIGNER_PST_CONNECT_TIMEOUT", "15"))
PST_DOWNLOAD_MAX_TIME = int(os.getenv("HACS_SIGNER_PST_DOWNLOAD_MAX_TIME", "300"))
PST_DOWNLOAD_CONNECT_TIMEOUT = int(os.getenv("HACS_SIGNER_PST_DOWNLOAD_CONNECT_TIMEOUT", str(PST_SOAP_CONNECT_TIMEOUT)))
PST_PREFLIGHT_MAX_TIME = int(os.getenv("HACS_SIGNER_PST_PREFLIGHT_MAX_TIME", "30"))
PST_PREFLIGHT_CONNECT_TIMEOUT = int(os.getenv("HACS_SIGNER_PST_PREFLIGHT_CONNECT_TIMEOUT", "10"))
PIN_SESSION_TTL_SECONDS = max(int(os.getenv("HACS_SIGNER_PIN_SESSION_TTL", "1800")), 60)
PIN_SESSION_MAX_ACTIVE = max(int(os.getenv("HACS_SIGNER_PIN_SESSION_MAX_ACTIVE", "4")), 1)
PST_SESSION_TTL_SECONDS = max(
    int(os.getenv("HACS_SIGNER_PST_SESSION_TTL", str(PIN_SESSION_TTL_SECONDS))),
    60,
)
PST_SESSION_MAX_ACTIVE = max(int(os.getenv("HACS_SIGNER_PST_SESSION_MAX_ACTIVE", "6")), 1)
_DEFAULT_HACS_ALLOWED_ORIGINS = (
    "http://127.0.0.1:8080",
    "http://localhost:8080",
    "https://app.iusentra.it",
    "https://studio-legale-pct-production.up.railway.app",
)
LOCAL_SIGNER_ALLOWED_ORIGINS = os.getenv(
    "PCT_LOCAL_SIGNER_ALLOWED_ORIGINS",
    os.getenv("HACS_SIGNER_ALLOWED_ORIGINS", ""),
) or ",".join(_DEFAULT_HACS_ALLOWED_ORIGINS)
LOCAL_SIGNER_UPDATE_URL = os.getenv(
    "IUSENTRA_LOCAL_SIGNER_UPDATE_URL",
    "https://app.iusentra.it/polisWeb/local-signer/setup/windows",
)
_ZEEP_WSDL_CACHE: dict[str, Any] = {}
_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [LocalSigner] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("local_signer")


def _powershell_single_quote(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _local_signer_update_url() -> str:
    url = str(os.getenv("IUSENTRA_LOCAL_SIGNER_UPDATE_URL", LOCAL_SIGNER_UPDATE_URL) or "").strip()
    if not url.startswith("https://app.iusentra.it/"):
        raise RuntimeError("URL aggiornamento Local Signer non autorizzato.")
    return url


def _avvia_aggiornamento_local_signer() -> dict:
    """Scarica e avvia il pacchetto ufficiale Windows senza salvare dati sensibili."""
    update_url = _local_signer_update_url()
    if sys.platform != "win32":
        return {
            "ok": False,
            "errore": "Aggiornamento automatico disponibile solo su Windows.",
            "installer_url": update_url,
        }
    target = Path(tempfile.gettempdir()) / f"SetupLocalSigner-{secrets.token_hex(8)}.exe"
    ps_command = (
        "$ErrorActionPreference='Stop'; "
        f"$url={_powershell_single_quote(update_url)}; "
        "if (-not $url.StartsWith('https://app.iusentra.it/')) { exit 2 }; "
        f"$target={_powershell_single_quote(str(target))}; "
        "Invoke-WebRequest -Uri $url -UseBasicParsing -OutFile $target; "
        "Start-Process -WindowStyle Hidden -FilePath $target -ArgumentList @('/Q')"
    )
    subprocess.Popen(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-WindowStyle",
            "Hidden",
            "-Command",
            ps_command,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return {
        "ok": True,
        "versione_corrente": VERSION,
        "messaggio": "Aggiornamento Local Signer avviato dal pacchetto ufficiale.",
        "installer_url": update_url,
    }

_LOCAL_LOG_FILES = ("local_signer.err.log", "local_signer.out.log", "installer.log")
_LOCAL_LOG_MAX_BYTES = 160_000


def _redact_local_log_text(value: str) -> str:
    text = str(value or "")
    text = re.sub(r"(?i)\b(pin|password)\s*[:=]\s*\S+", r"\1=[omesso]", text)
    text = re.sub(r"(?i)\b(authorization|bearer)\s+[\w./+=:-]+", r"\1 [omesso]", text)
    return text


def _tail_local_log(path: Path, *, max_bytes: int = _LOCAL_LOG_MAX_BYTES, lines: int = 240) -> str:
    if not path.exists() or not path.is_file():
        return ""
    size = path.stat().st_size
    with path.open("rb") as handle:
        if size > max_bytes:
            handle.seek(max(0, size - max_bytes))
        raw = handle.read(max_bytes)
    text = raw.decode("utf-8", "replace")
    if lines > 0:
        text = "\n".join(text.splitlines()[-lines:])
    return _redact_local_log_text(text)

_PST_PORTALE_URL = "https://pst.giustizia.it"
_PST_PROXY_PDA_URL = "https://pda.processotelematico.giustizia.it"
_PST_PROXY_SH_URL = "https://ext.processotelematico.giustizia.it"
_PST_LEGACY_BASE = "https://wspa.giustizia.it/wspa"
_PST_SIL_ENDPOINT_SERVIZI = ("JPW_SIL_DISTR", "JPW_SIL", "JPW_SILP_DISTR", "JPW_SILP")
_PST_SICID_FAMILY_SERVIZI = (
    "JPW_SICID",
    *_PST_SIL_ENDPOINT_SERVIZI,
    "JPW_SIVG",
    "JPW_MIN",
    "JPW_SIMIN",
)
_PST_SERVIZI_DEFAULT = (
    "JPW_SICID",
    "JPW_SIL_DISTR",
    "JPW_SIL",
    "JPW_SILP_DISTR",
    "JPW_SILP",
    "JPW_SIVG",
    "JPW_MIN",
    "JPW_SIMIN",
    "JPW_SIECIC",
    "JPW_SIGP",
    "JPW_CASSCI",
    "JPW_CASSPE",
)
_PST_SERVIZI_ALIAS = {
    "JPW_CASS": "JPW_CASSCI",
    "CASSCI": "JPW_CASSCI",
    "CASSPE": "JPW_CASSPE",
    "SICID": "JPW_SICID",
    "SICC": "JPW_SICID",
    "CIVILE": "JPW_SICID",
    "SIL": "JPW_SIL_DISTR",
    "SILP": "JPW_SILP_DISTR",
    "LAV": "JPW_SIL_DISTR",
    "LAVORO": "JPW_SIL_DISTR",
    "PREVIDENZA": "JPW_SIL_DISTR",
    "PREVIDENZIALE": "JPW_SIL_DISTR",
    "ASSISTENZA": "JPW_SIL_DISTR",
    "ASSISTENZIALE": "JPW_SIL_DISTR",
    "SIVG": "JPW_SIVG",
    "VOLONTARIA": "JPW_SIVG",
    "VG": "JPW_SIVG",
    "MIN": "JPW_MIN",
    "MINORI": "JPW_MIN",
    "MINORENNI": "JPW_MIN",
    "SIMIN": "JPW_SIMIN",
    "SIECIC": "JPW_SIECIC",
    "ESECUZIONI": "JPW_SIECIC",
    "CONCORSUALI": "JPW_SIECIC",
    "SIGP": "JPW_SIGP",
    "GDP": "JPW_SIGP",
    "RGN": "JPW_SICID",
}
_PST_QBUILDER_NAMESPACES = {
    "JPW_SICID": "urn:CONS-SICC-BE",
    "JPW_SIL_DISTR": "urn:CONS-SIL-BE-DISTR",
    "JPW_SIL": "urn:CONS-SIL-BE-DISTR",
    "JPW_SILP_DISTR": "urn:CONS-SIL-BE-DISTR",
    "JPW_SILP": "urn:CONS-SIL-BE-DISTR",
    "JPW_SIVG": "urn:CONS-SIVG-BE",
    "JPW_MIN": "urn:CONS-MIN-BE",
    "JPW_SIMIN": "urn:CONS-MIN-BE",
    "JPW_SIECIC": "urn:CONS-SIECIC-BE",
    "JPW_SIGP": "urn:CONS-SIGP-BE",
    "JPW_CASSCI": "urn:CONS-CASSCI",
    "JPW_CASSPE": "urn:CONS-CASSPE",
}
_PST_QBUILDER_TIPO_RICERCA = {
    "JPW_SICID": "RGN",
    "JPW_SIL_DISTR": "LAV",
    "JPW_SIL": "LAV",
    "JPW_SILP_DISTR": "LAV",
    "JPW_SILP": "LAV",
    "JPW_SIVG": "VG",
    "JPW_MIN": "MIN",
    "JPW_SIMIN": "MIN",
    "JPW_SIGP": "GDP",
}
_PST_QBUILDER_HTTP_ENDPOINT_SERVIZI = {
    servizio: "JPW_SICID"
    for servizio in _PST_SICID_FAMILY_SERVIZI
    if servizio != "JPW_SICID"
}
_PST_TABELLE_MINISTERIALI_POLICY = {
    "JPW_SICID": {
        "tabella": "SICID_CONTENZIOSO_CIVILE",
        "registro": "JPW_SICID",
        "download": "downloadDocumento",
        "warmup": "calcolaHash_multi",
        "errore_lotto": "per_documento",
        "x_wasp_user": True,
    },
    "JPW_SIL": {
        "tabella": "SICID_LAVORO",
        "registro": "JPW_SIL",
        "download": "downloadDocumento",
        "warmup": "calcolaHash_multi",
        "errore_lotto": "per_documento",
        "x_wasp_user": True,
    },
    "JPW_SIL_DISTR": {
        "tabella": "SICID_LAVORO",
        "registro": "JPW_SIL",
        "download": "downloadDocumento",
        "warmup": "calcolaHash_multi",
        "errore_lotto": "per_documento",
        "x_wasp_user": True,
    },
    "JPW_SILP_DISTR": {
        "tabella": "SICID_LAVORO",
        "registro": "JPW_SIL",
        "download": "downloadDocumento",
        "warmup": "calcolaHash_multi",
        "errore_lotto": "per_documento",
        "x_wasp_user": True,
    },
    "JPW_SILP": {
        "tabella": "SICID_LAVORO",
        "registro": "JPW_SIL",
        "download": "downloadDocumento",
        "warmup": "calcolaHash_multi",
        "errore_lotto": "per_documento",
        "x_wasp_user": True,
    },
    "JPW_SIVG": {
        "tabella": "SICID_VOLONTARIA_GIURISDIZIONE",
        "registro": "JPW_SIVG",
        "download": "downloadDocumento",
        "warmup": "calcolaHash_multi",
        "errore_lotto": "per_documento",
        "x_wasp_user": True,
    },
    "JPW_MIN": {
        "tabella": "SICID_MINORI",
        "registro": "JPW_MIN",
        "download": "downloadDocumento",
        "warmup": "calcolaHash_multi",
        "errore_lotto": "per_documento",
        "x_wasp_user": True,
    },
    "JPW_SIMIN": {
        "tabella": "SICID_SIMIN",
        "registro": "JPW_SIMIN",
        "download": "downloadDocumento",
        "warmup": "calcolaHash_multi",
        "errore_lotto": "per_documento",
        "x_wasp_user": True,
    },
    "JPW_SIECIC": {
        "tabella": "SIECIC_ESECUZIONI_CONCORSUALI",
        "registro": "SIECIC",
        "download": "downloadDocumento",
        "warmup": "",
        "errore_lotto": "per_documento",
        "x_wasp_user": True,
    },
    "JPW_SIGP": {
        "tabella": "SIGP_GIUDICE_DI_PACE",
        "registro": "GDP",
        "download": "downloadAtto",
        "warmup": "calcolaHash_always",
        "errore_lotto": "per_documento",
        "x_wasp_user": True,
    },
}
_PDP_BASE = os.getenv("PCT_PDP_BASE_URL", "https://appweb.giustizia.it/snt").rstrip("/")
_PDP_OFFICIAL_BROWSER_URL = "https://servizipst.giustizia.it/PST/authentication/it/pst_ar.wp"
_WSDL_RICERCA_PENALE = f"{_PDP_BASE}/RicercaFascicoliPenaleService?wsdl"
_WSDL_CONSULTA_PENALE = f"{_PDP_BASE}/ConsultazioneDocumentiPenaleService?wsdl"
_PAT_BASE = os.getenv("PCT_PAT_BASE_URL", "https://pac.giustizia-amministrativa.it/pac").rstrip("/")
_WSDL_RICERCA_AMM = f"{_PAT_BASE}/RicercaRicorsiService?wsdl"
_WSDL_CONSULTA_AMM = f"{_PAT_BASE}/ConsultazioneDocumentiService?wsdl"
_SIGIT_BASE = os.getenv("PCT_SIGIT_BASE_URL", "https://sigit.finanze.it/ptt").rstrip("/")
_WSDL_RICERCA_TRIB = f"{_SIGIT_BASE}/RicercaFascicoliTributarioService?wsdl"
_WSDL_CONSULTA_TRIB = f"{_SIGIT_BASE}/ConsultazioneDocumentiTributarioService?wsdl"
_CF_PATTERN = re.compile(r"\b([A-Z]{6}[0-9A-Z]{2}[A-Z][0-9A-Z]{2}[A-Z][0-9A-Z]{3}[A-Z])\b")
_PST_CERT_ISSUER_PRIORITIES = (
    "ArubaPEC EU Authentica Certificates CA G1",
    "ArubaPEC EU Qualified Certificates CA G1",
    "ArubaPEC",
)
_PST_CERT_SUBJECT_HINTS = (
    "auth",
    "autent",
    "client",
    "tls",
    "web",
)

# ── Librerie PKCS#11 candidate ─────────────────────────────────────────────────
_DEFAULT_LIBS = [
    # Windows — Bit4id (Aruba Key) — tutte le varianti di installazione note
    r"C:\Windows\System32\bit4xpki.dll",           # percorso standard (64-bit)
    r"C:\Windows\SysWOW64\bit4xpki.dll",           # 32-bit su Windows 64-bit
    r"C:\Program Files\Bit4id\MinVa\bit4xpki.dll",        # MinVa v2+
    r"C:\Program Files (x86)\Bit4id\MinVa\bit4xpki.dll",  # MinVa 32-bit
    r"C:\Program Files\Bit4id\bit4xpki.dll",              # versioni precedenti
    r"C:\Program Files (x86)\Bit4id\bit4xpki.dll",
    r"C:\Program Files\Bit4id\MinVa\windows\bit4xpki.dll",
    r"C:\Program Files (x86)\Bit4id\MinVa\windows\bit4xpki.dll",
    # Windows — Namirial
    r"C:\Windows\System32\OkiPKCS11.dll",
    r"C:\Windows\SysWOW64\OkiPKCS11.dll",
    r"C:\Program Files\Namirial\pkcs11.dll",
    r"C:\Program Files (x86)\Namirial\pkcs11.dll",
    # Windows — Lextel / InfoCert
    r"C:\Windows\System32\cvP11.dll",
    r"C:\Windows\System32\cvcP11.dll",
    r"C:\Windows\SysWOW64\cvP11.dll",
    r"C:\Windows\SysWOW64\cvcP11.dll",
    # Linux — OpenSC
    "/usr/lib/x86_64-linux-gnu/opensc-pkcs11.so",
    "/usr/lib64/pkcs11/opensc-pkcs11.so",
    "/usr/lib/opensc-pkcs11.so",
    "/usr/lib/aarch64-linux-gnu/opensc-pkcs11.so",
    # macOS — OpenSC
    "/Library/OpenSC/lib/opensc-pkcs11.so",
    "/usr/local/lib/opensc-pkcs11.so",
]

_lib_cache: Optional[str] = None
_ultimo_certificato_windows: Optional[dict] = None
_uffici_snapshot_cache: Optional[dict[str, dict]] = None
_uffici_hacs_cache: Optional[list[dict[str, Any]]] = None
_pin_session_cache: dict[str, dict] = {}
_pin_session_lock = threading.Lock()
_pst_session_cache: dict[str, dict] = {}
_pst_session_lock = threading.Lock()
_LOCALHOST_ORIGIN_HOSTS = {"localhost", "127.0.0.1", "::1"}
_local_ai_bridge_instance = None

# Host PST dove almeno un tentativo cookie-only ha richiesto fallback mTLS.
# Segnale diagnostico: il riuso cookie resta comunque il primo tentativo, per
# della stessa sessione, così tutte le chiamate arrivano al cert più velocemente
# non riaprire un secondo prompt PIN quando la sessione e' ancora valida.
_mTLS_required_hosts: set[str] = set()
_mTLS_required_lock = threading.Lock()


def _utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _pkcs11_text(value: Any) -> str:
    if isinstance(value, bytes):
        for encoding in ("utf-8", "latin-1"):
            try:
                return value.decode(encoding).strip("\x00").strip()
            except Exception:
                continue
        return value.hex()
    return str(value or "").strip()


def _probe_token_info_fresh(lib_path: str) -> list[dict[str, Any]]:
    script = """
import json
import sys

try:
    import pkcs11
except Exception as exc:
    print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
    raise SystemExit(0)

def _clean(value):
    if isinstance(value, bytes):
        for encoding in ("utf-8", "latin-1"):
            try:
                return value.decode(encoding).strip("\\x00").strip()
            except Exception:
                continue
        return value.hex()
    return str(value or "").strip()

payload = {"ok": True, "token": []}
try:
    lib = pkcs11.lib(sys.argv[1])
    for slot in lib.get_slots(token_present=True):
        token = slot.get_token()
        payload["token"].append({
            "slot_id": getattr(slot, "slot_id", None),
            "label": _clean(getattr(token, "label", "")),
            "manufacturer": _clean(getattr(token, "manufacturer_id", "")),
            "model": _clean(getattr(token, "model", "")),
            "serial": _clean(getattr(token, "serial", "")),
        })
except Exception as exc:
    payload = {"ok": False, "error": str(exc), "token": []}

print(json.dumps(payload, ensure_ascii=False))
""".strip()

    try:
        proc = subprocess.run(
            [sys.executable, "-c", script, lib_path],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=8,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception as exc:
        log.debug("Probe PKCS#11 fresco non riuscito: %s", exc)
        return []

    raw = (proc.stdout or "").strip()
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        log.debug("Probe PKCS#11 fresco non decodificabile: %s", raw)
        return []
    if not payload.get("ok"):
        log.debug("Probe PKCS#11 fresco senza token: %s", payload.get("error"))
        return []
    token = payload.get("token") or []
    return token if isinstance(token, list) else []


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    return str(value).strip().lower() in _TRUE_VALUES


def _get_local_ai_bridge():
    global _local_ai_bridge_instance
    if _local_ai_bridge_instance is None:
        if LocalAiHostBridge is None:
            raise RuntimeError(
                "Bridge AI locale non disponibile in questo pacchetto del Local Signer. "
                "Aggiorna il Local Signer dall'area impostazioni di IUSENTRA."
            )
        _local_ai_bridge_instance = LocalAiHostBridge(root_dir=_THIS_DIR)
    return _local_ai_bridge_instance


def _snapshot_paths() -> list[Path]:
    base_dir = Path(__file__).resolve().parent
    return [
        base_dir / "data" / "uffici_ministero.json",
        base_dir / "uffici_ministero.json",
        _REPO_ROOT / "pct" / "data" / "uffici_ministero.json",
    ]


def _nome_ufficio_snapshot(row: dict) -> str:
    nome = str(row.get("nome") or "").strip()
    if nome:
        return nome

    comune = str(row.get("comune_ministero") or "").strip()
    descrizione = str(row.get("descrizione_ministero") or "").strip()
    tipo = str(row.get("tipo_ministero_descrizione") or "").strip().lower()

    if not comune and " - " in descrizione:
        _, _, maybe_comune = descrizione.partition(" - ")
        comune = maybe_comune.strip()

    mapping = {
        "tribunale ordinario": "Tribunale di {comune}",
        "procura della repubblica": "Procura della Repubblica di {comune}",
        "procura generale": "Procura Generale di {comune}",
        "corte di appello": "Corte d'Appello di {comune}",
        "tribunale per i minorenni": "Tribunale per i Minorenni di {comune}",
        "tribunale di sorveglianza": "Tribunale di Sorveglianza di {comune}",
        "corte di assise": "Corte d'Assise di {comune}",
        "ufficio del giudice di pace": "Ufficio del Giudice di Pace di {comune}",
    }
    template = mapping.get(tipo)
    if template and comune:
        return template.format(comune=comune)
    return descrizione or comune


def _carica_snapshot_uffici() -> dict[str, dict]:
    global _uffici_snapshot_cache
    if _uffici_snapshot_cache is not None:
        return _uffici_snapshot_cache

    for path in _snapshot_paths():
        if not path.exists():
            continue
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            uffici = raw.get("uffici", raw) if isinstance(raw, dict) else {}
            if not isinstance(uffici, dict):
                continue
            normalized: dict[str, dict] = {}
            for codice, info in uffici.items():
                if not isinstance(info, dict):
                    continue
                row = dict(info)
                row.setdefault("codice", str(codice))
                row.setdefault("nome", _nome_ufficio_snapshot(row))
                normalized[str(codice).strip()] = row
            if normalized:
                _uffici_snapshot_cache = normalized
                log.info("Registro uffici locale caricato da %s (%s uffici)", path, len(normalized))
                return normalized
        except Exception as e:
            log.warning("Impossibile caricare snapshot uffici da %s: %s", path, e)

    _uffici_snapshot_cache = {}
    return _uffici_snapshot_cache


def _normalizza_testo_ufficio(valore: str) -> str:
    import unicodedata

    base = unicodedata.normalize("NFKD", (valore or "").strip().lower())
    return "".join(ch for ch in base if not unicodedata.combining(ch)).replace("-", " ")


def _risolvi_ufficio_da_snapshot(codice_o_nome: str) -> Optional[dict]:
    chiave = (codice_o_nome or "").strip()
    if not chiave:
        return None

    uffici = _carica_snapshot_uffici()
    if not uffici:
        return None

    if chiave in uffici:
        return uffici[chiave]

    for ufficio in uffici.values():
        if chiave == str(ufficio.get("codice_ministero") or "").strip():
            return ufficio

    chiave_norm = _normalizza_testo_ufficio(chiave)
    for ufficio in uffici.values():
        campi = (
            ufficio.get("nome", ""),
            ufficio.get("descrizione_ministero", ""),
            ufficio.get("comune_ministero", ""),
        )
        for val in campi:
            if _normalizza_testo_ufficio(str(val)) == chiave_norm:
                return ufficio

    for ufficio in uffici.values():
        campi = (
            ufficio.get("nome", ""),
            ufficio.get("descrizione_ministero", ""),
            ufficio.get("comune_ministero", ""),
        )
        for val in campi:
            norm = _normalizza_testo_ufficio(str(val))
            if chiave_norm and chiave_norm in norm:
                return ufficio

    return None


def _supporto_auto_pst_disponibile() -> bool:
    if _risolvi_base_pst_hacs is not None and _risolvi_codice_ministero_hacs is not None:
        return True
    return bool(_carica_snapshot_uffici())


def _env_flag_enabled(name: str) -> bool:
    return str(os.getenv(name, "") or "").strip().lower() in _TRUE_VALUES


def _env_flag_default_enabled(name: str) -> bool:
    value = str(os.getenv(name, "") or "").strip().lower()
    if not value:
        return True
    return value not in _FALSE_VALUES


def _pst_register_fallback_enabled() -> bool:
    return _env_flag_default_enabled("HACS_SIGNER_PST_REGISTER_FALLBACK")


def _normalizza_servizio_pst_name(servizio: Any) -> str:
    valore = str(servizio or "").strip().upper()
    if not valore:
        return ""
    return _PST_SERVIZI_ALIAS.get(valore, valore)


def _carica_bundle_uffici_hacs() -> list[dict[str, Any]]:
    global _uffici_hacs_cache
    if _uffici_hacs_cache is not None:
        return _uffici_hacs_cache

    try:
        from pct.uffici_giudiziari import _build_bundle_completo

        bundle = _build_bundle_completo()
        _uffici_hacs_cache = bundle if isinstance(bundle, list) else []
    except Exception:
        _uffici_hacs_cache = []
    return _uffici_hacs_cache


def _risolvi_ufficio_hacs_bundle(
    valore: str,
    *,
    tipi: Optional[tuple[str, ...]] = None,
) -> Optional[dict[str, Any]]:
    chiave = (valore or "").strip()
    if not chiave:
        return None

    tipi_norm = {str(tipo).upper() for tipo in (tipi or ()) if str(tipo).strip()}
    bundle = _carica_bundle_uffici_hacs()
    if not bundle:
        return None

    chiave_upper = chiave.upper()
    chiave_norm = _normalizza_testo_ufficio(chiave)
    best_partial: Optional[dict[str, Any]] = None

    for ufficio in bundle:
        tipo = str(ufficio.get("tipo") or "").upper()
        if tipi_norm and tipo not in tipi_norm:
            continue

        codice = str(ufficio.get("codice") or "").strip()
        nome = str(ufficio.get("nome") or "").strip()
        distretto = str(ufficio.get("distretto") or "").strip()

        if codice and codice.upper() == chiave_upper:
            return ufficio

        campi = [nome, distretto, f"{nome} {distretto}".strip()]
        campi_norm = [_normalizza_testo_ufficio(campo) for campo in campi if campo]
        if chiave_norm in campi_norm:
            return ufficio

        if chiave_norm and not best_partial and any(
            chiave_norm in campo_norm for campo_norm in campi_norm if campo_norm
        ):
            best_partial = ufficio

    return best_partial


def _looks_like_pat_code(valore: str) -> bool:
    text = (valore or "").strip().upper()
    return bool(text) and (
        text.isdigit()
        or text.startswith("T")
        or text.startswith("CDS")
        or text.startswith("CGARS")
    )


def _looks_like_ptt_code(valore: str) -> bool:
    text = (valore or "").strip().upper()
    return bool(text) and (text.isdigit() or text.startswith(("CPT", "CGT")))


def _risolvi_codice_ufficio_pdp_runtime(valore: str) -> str:
    text = (valore or "").strip()
    if not text:
        return ""
    if text.isdigit():
        return text

    ufficio = _risolvi_ufficio_da_snapshot(text) or _risolvi_ufficio_hacs_bundle(
        text,
        tipi=(
            "TRIBUNALE",
            "PROCURA",
            "PROCURA_GENERALE",
            "CORTE_APPELLO",
            "TM",
            "SORVEGLIANZA",
            "CORTE_ASSISE",
            "CORTE_CASSAZIONE",
        ),
    )
    if ufficio:
        codice = str(ufficio.get("codice") or ufficio.get("codice_ministero") or "").strip()
        if codice:
            return codice

    raise ValueError(
        "Impossibile risolvere il codice ufficio PDP dal valore indicato. "
        "Selezionare l'ufficio dalla lista del wizard oppure verificare il registro uffici locale."
    )


def _risolvi_codice_ufficio_pat_runtime(valore: str) -> str:
    text = (valore or "").strip()
    if not text:
        return ""
    if _looks_like_pat_code(text):
        return text

    ufficio = _risolvi_ufficio_hacs_bundle(text, tipi=("TAR", "CDS", "CGARS"))
    if ufficio:
        codice = str(ufficio.get("codice") or "").strip()
        if codice:
            return codice

    raise ValueError(
        "Impossibile risolvere il codice ufficio PAT dal valore indicato. "
        "Selezionare l'ufficio dalla lista del wizard oppure aggiornare il registro portali."
    )


def _risolvi_codice_commissione_ptt_runtime(valore: str) -> str:
    text = (valore or "").strip()
    if not text:
        return ""
    if _looks_like_ptt_code(text):
        return text.upper()

    ufficio = _risolvi_ufficio_hacs_bundle(text, tipi=("CPT", "CGT"))
    if ufficio:
        codice = str(ufficio.get("codice") or "").strip().upper()
        if codice:
            return codice

    raise ValueError(
        "Impossibile risolvere il codice commissione PTT dal valore indicato. "
        "Selezionare la commissione dalla lista del wizard oppure aggiornare il registro portali."
    )


def _normalizza_origin(origin: str) -> str:
    return normalize_origin(origin)


def _origin_loopback(origin: str) -> bool:
    return is_loopback_origin(origin)


def _origini_hacs_consentite() -> set[str]:
    return build_allowed_origins(LOCAL_SIGNER_ALLOWED_ORIGINS)


def _origin_cors_consentita(origin: str) -> bool:
    return is_allowed_origin(origin, LOCAL_SIGNER_ALLOWED_ORIGINS)


def _risolvi_base_pst_da_snapshot(codice_o_nome: str) -> str:
    ufficio = _risolvi_ufficio_da_snapshot(codice_o_nome)
    if not ufficio:
        raise ValueError(
            "Impossibile determinare codice GL/servizio PST dell'ufficio selezionato. "
            "Verificare il registro uffici locale o configurare PCT_PST_BASE_URL completo."
        )

    codice_gl = str(ufficio.get("codice_gl") or "").strip()
    servizi = [
        _normalizza_servizio_pst_name(servizio)
        for servizio in (ufficio.get("servizi_ministero") or [])
        if str(servizio).strip()
    ]
    servizi_jpw = [servizio for servizio in servizi if servizio.startswith("JPW_")]
    preferenze = []
    env_pref = _normalizza_servizio_pst_name(os.getenv("PCT_PST_SERVIZIO_DEFAULT", ""))
    if env_pref:
        preferenze.append(env_pref)
    servizio_default = _normalizza_servizio_pst_name(ufficio.get("servizio_pst_predefinito") or "")
    if servizio_default:
        preferenze.append(servizio_default)
    preferenze.extend(_PST_SERVIZI_DEFAULT)

    servizio = next((candidate for candidate in preferenze if candidate in servizi_jpw), "")
    if not servizio and servizi_jpw:
        servizio = servizi_jpw[0]

    if not codice_gl or not servizio:
        raise ValueError(
            "Impossibile determinare codice GL/servizio PST dell'ufficio selezionato. "
            "Verificare il registro uffici locale o configurare PCT_PST_BASE_URL completo."
        )

    base_env = (os.getenv("PCT_PST_BASE_URL", "") or "").strip().rstrip("/")
    if base_env and "/pda/pycons/" in base_env:
        parsed = urlparse(base_env)
        path_parts = [part for part in parsed.path.rstrip("/").split("/") if part]
        if path_parts:
            path_parts[-1] = _normalizza_servizio_pst_name(path_parts[-1])
            normalized_path = "/" + "/".join(path_parts)
            if parsed.scheme and parsed.netloc:
                return f"{parsed.scheme}://{parsed.netloc}{normalized_path}"
            return normalized_path
        return base_env
    root = base_env or os.getenv("PCT_PST_PROXY_ROOT", "").strip().rstrip("/") or _PST_PROXY_SH_URL
    if root.startswith(_PST_LEGACY_BASE):
        root = _PST_PROXY_SH_URL
    return f"{root}/pda/pycons/{codice_gl}/{servizio}"


def _pst_base_url_con_servizio(base_url: str, servizio: str) -> str:
    servizio_norm = _normalizza_servizio_pst_name(servizio)
    raw = (base_url or "").strip().rstrip("/")
    if not raw or not servizio_norm or "/pda/pycons/" not in raw:
        return raw

    parsed = urlparse(raw)
    path = parsed.path if parsed.scheme and parsed.netloc else raw
    path_parts = [part for part in path.rstrip("/").split("/") if part]
    if not path_parts:
        return raw
    path_parts[-1] = servizio_norm
    normalized_path = "/" + "/".join(path_parts)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}{normalized_path}"
    return normalized_path if raw.startswith("/") else normalized_path.lstrip("/")


def _pst_hint_tokens_ministeriali(value: Any) -> list[str]:
    raw = str(value or "").strip()
    if not raw:
        return []
    normalized = unicodedata.normalize("NFKD", raw.upper())
    ascii_text = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.findall(r"[A-Z0-9_]+", ascii_text)


def _pst_servizio_ministeriale_da_tokens(tokens: list[str]) -> str:
    text = " ".join(tokens)
    keyword_groups = (
        ("JPW_CASSPE", (("CASS", "PENAL"),)),
        ("JPW_CASSCI", (("CASS", "CIVIL"),)),
        ("JPW_SIL_DISTR", (("LAVOR",), ("PREVIDENZ",), ("ASSISTENZ",))),
        ("JPW_SIVG", (("VOLONTARI",), ("VOLONTARI", "GIURISDIZIONE"))),
        ("JPW_MIN", (("MINORE",), ("MINORI",), ("MINORENN",))),
        ("JPW_SIECIC", (("ESECUZ",), ("CONCORS",))),
        ("JPW_SIGP", (("GIUDICE", "PACE"),)),
    )
    for servizio, groups in keyword_groups:
        if any(all(marker in text for marker in group) for group in groups):
            return servizio
    return ""


def _pst_servizio_ministeriale_da_payload(*payloads: Any) -> str:
    """
    Ricava la tabella ministeriale richiesta dal wizard o dal fascicolo.

    La scelta resta prudente: usa solo indizi espliciti di registro, schema,
    materia o tabella, e non prova a dedurre il rito dal solo numero di R.G.
    """
    explicit_keys = (
        "servizio_pst",
        "servizio_pst_preferito",
        "servizio",
        "registro_portale",
        "tabella_ministeriale",
    )
    hint_keys = (
        "registro",
        "tipo_registro",
        "materia",
        "schema",
        "quick_filter",
        "oggetto",
        "ruolo",
        "procedimento",
    )
    collected: list[str] = []
    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        for key in explicit_keys:
            value = payload.get(key)
            value_tokens = _pst_hint_tokens_ministeriali(value)
            servizio_keyword = _pst_servizio_ministeriale_da_tokens(value_tokens)
            if servizio_keyword:
                return servizio_keyword
            for token in value_tokens:
                servizio = _PST_SERVIZI_ALIAS.get(token, token)
                if servizio in _PST_QBUILDER_NAMESPACES:
                    return servizio
            if value not in (None, ""):
                collected.append(str(value))
        for key in hint_keys:
            value = payload.get(key)
            if value not in (None, ""):
                collected.append(str(value))

    tokens: list[str] = []
    for value in collected:
        tokens.extend(_pst_hint_tokens_ministeriali(value))
    servizio_keyword = _pst_servizio_ministeriale_da_tokens(tokens)
    if servizio_keyword:
        return servizio_keyword
    for token in tokens:
        servizio = _PST_SERVIZI_ALIAS.get(token, "")
        if servizio in _PST_QBUILDER_NAMESPACES:
            return servizio
    return ""


def _pst_base_url_con_preferenza_payload(base_url: str, *payloads: Any) -> str:
    servizio = _pst_servizio_ministeriale_da_payload(*payloads)
    if not servizio:
        return base_url.rstrip("/") if base_url else ""
    preferita = _pst_base_url_con_servizio(base_url, servizio)
    return preferita or (base_url.rstrip("/") if base_url else "")


def _pst_servizi_qbuilder_ufficio(codice_o_nome: str) -> list[str]:
    ufficio = _risolvi_ufficio_da_snapshot(codice_o_nome)
    if not ufficio:
        return []

    servizi: list[str] = []
    for servizio in ufficio.get("servizi_ministero") or []:
        servizio_norm = _normalizza_servizio_pst_name(servizio)
        if servizio_norm in _PST_QBUILDER_NAMESPACES and servizio_norm not in servizi:
            servizi.append(servizio_norm)
    return servizi


def _pst_base_varianti_ricerca_esatta(codice_o_nome: str, base_url: str) -> list[str]:
    """
    Per ricerche esatte RG/anno resta prioritario il servizio ufficiale
    dell'ufficio, ma alcuni Tribunali espongono fascicoli civili su registri
    paralleli dello stesso ufficio. Le varianti non cambiano GL, certificato
    o tenant: provano solo il canale ministeriale corretto.
    """
    if not _pst_register_fallback_enabled():
        return [base_url.rstrip("/")] if base_url else []

    current = _pst_servizio_proxy(base_url)
    servizi_ufficio = _pst_servizi_qbuilder_ufficio(codice_o_nome)
    candidati: list[str] = []

    def _aggiungi(servizio: str) -> None:
        servizio_norm = _normalizza_servizio_pst_name(servizio)
        if servizio_norm in _PST_QBUILDER_NAMESPACES and servizio_norm not in candidati:
            candidati.append(servizio_norm)

    _aggiungi(current)

    # Fallback anti-regressione: anche se il registro uffici non viene
    # risolto nel punto chiamante, una URL civile contiene gia' abbastanza
    # informazione per provare i registri ministeriali dello stesso ufficio.
    if current in _PST_SIL_ENDPOINT_SERVIZI:
        for servizio in _PST_SIL_ENDPOINT_SERVIZI:
            _aggiungi(servizio)
        _aggiungi("JPW_SICID")
        _aggiungi("JPW_SIVG")
        _aggiungi("JPW_MIN")
        _aggiungi("JPW_SIMIN")
        _aggiungi("JPW_SIECIC")
    elif current in _PST_SICID_FAMILY_SERVIZI:
        for servizio in _PST_SICID_FAMILY_SERVIZI:
            _aggiungi(servizio)
        _aggiungi("JPW_SIECIC")
    elif current == "JPW_SIECIC":
        for servizio in _PST_SICID_FAMILY_SERVIZI:
            _aggiungi(servizio)
    elif current == "SICID":
        for servizio in _PST_SICID_FAMILY_SERVIZI:
            _aggiungi(servizio)
        _aggiungi("JPW_SIECIC")
    elif current == "SIECIC":
        _aggiungi("JPW_SIECIC")
        for servizio in _PST_SICID_FAMILY_SERVIZI:
            _aggiungi(servizio)

    for servizio in (*_PST_SICID_FAMILY_SERVIZI, "JPW_SIECIC", "JPW_SIGP"):
        if servizio in servizi_ufficio:
            _aggiungi(servizio)
    for servizio in servizi_ufficio:
        _aggiungi(servizio)

    varianti: list[str] = []
    for servizio in candidati:
        variante = _pst_base_url_con_servizio(base_url, servizio)
        if variante and variante not in varianti:
            varianti.append(variante)
    return varianti or ([base_url.rstrip("/")] if base_url else [])


def _pst_codici_ufficio_ricerca_esatta(codice_pst: str, codice_richiesto: str) -> list[str]:
    codici: list[str] = []
    for index, codice in enumerate((codice_pst, codice_richiesto)):
        value = str(codice or "").strip()
        if index > 0 and value and not value.isdigit():
            continue
        if value and value not in codici:
            codici.append(value)
    return codici


def _cerca_lib_registro_windows() -> Optional[str]:
    """
    Cerca il percorso della DLL Bit4id nel Registro di Windows.
    Bit4id registra il percorso di installazione in HKLM\\SOFTWARE\\Bit4id.
    """
    if sys.platform != "win32":
        return None
    try:
        import winreg
        chiavi_reg = [
            r"SOFTWARE\Bit4id\MinVa",
            r"SOFTWARE\WOW6432Node\Bit4id\MinVa",
            r"SOFTWARE\Bit4id",
            r"SOFTWARE\WOW6432Node\Bit4id",
        ]
        valori_dir = ["InstallDir", "Path", "Install_Dir", ""]
        nomi_dll   = ["bit4xpki.dll", "pkcs11.dll", "bit4wpk.dll"]

        for chiave in chiavi_reg:
            try:
                k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, chiave)
                try:
                    for val in valori_dir:
                        try:
                            install_dir, _ = winreg.QueryValueEx(k, val) if val else (
                                winreg.QueryValueEx(k, ""), (None,)
                            )
                            for dll in nomi_dll:
                                p = os.path.join(install_dir, dll)
                                if os.path.exists(p):
                                    log.info("DLL trovata via registro: %s", p)
                                    return p
                                # Prova anche nella sottocartella windows/
                                p2 = os.path.join(install_dir, "windows", dll)
                                if os.path.exists(p2):
                                    log.info("DLL trovata via registro: %s", p2)
                                    return p2
                        except (FileNotFoundError, OSError):
                            pass
                finally:
                    winreg.CloseKey(k)
            except (FileNotFoundError, PermissionError, OSError):
                pass
    except ImportError:
        pass
    return None


def _cerca_lib_glob_windows() -> Optional[str]:
    """
    Cerca la DLL PKCS#11 tramite glob in System32, SysWOW64 e Program Files.
    Fallback quando i percorsi standard e il registro non hanno dato risultati.
    """
    if sys.platform != "win32":
        return None
    import glob as _glob
    pattern_nomi = [
        "bit4xpki.dll",
        "bit4wpk.dll",
        "OkiPKCS11.dll",
        "cvP11.dll",
        "cvcP11.dll",
        "*pkcs11*.dll",
    ]
    dirs_cerca   = [
        r"C:\Windows\System32",
        r"C:\Windows\SysWOW64",
        r"C:\Program Files",
        r"C:\Program Files (x86)",
    ]
    for d in dirs_cerca:
        for nome in pattern_nomi:
            for match in _glob.glob(os.path.join(d, "**", nome), recursive=True):
                if os.path.exists(match):
                    log.info("DLL trovata via glob: %s", match)
                    return match
    return None


def _candidate_pkcs11_libs(override: Optional[str] = None) -> list[str]:
    candidati: list[str] = []

    def _add(path: Optional[str]):
        if path and os.path.exists(path) and path not in candidati:
            candidati.append(path)

    _add(override)
    _add(_lib_cache if _lib_cache and os.path.exists(_lib_cache) else None)

    env = os.getenv("PCT_PKCS11_LIBRARY", "").strip()
    _add(env)

    for p in _DEFAULT_LIBS:
        _add(p)

    if sys.platform == "win32":
        _add(_cerca_lib_registro_windows())
        _add(_cerca_lib_glob_windows())

    return candidati


def _score_pkcs11_lib(lib_path: str) -> int:
    """
    3 = libreria caricabile con almeno un token presente
    1 = libreria caricabile ma senza token rilevati
    0 = libreria non utilizzabile
    """
    try:
        import pkcs11
    except Exception:
        return 0

    try:
        lib_obj = pkcs11.lib(lib_path)
    except Exception as e:
        log.debug("PKCS#11 non caricabile %s: %s", lib_path, e)
        return 0

    try:
        slots = lib_obj.get_slots(token_present=True)
        return 3 if slots else 1
    except Exception as e:
        log.debug("PKCS#11 caricata ma non interrogabile %s: %s", lib_path, e)
        return 1


def _trova_libreria(override: Optional[str] = None) -> Optional[str]:
    """
    Cerca la libreria PKCS#11 nell'ordine:
    1. Override esplicito (argomento o env PCT_PKCS11_LIBRARY)
    2. Cache (se già trovata in precedenza)
    3. Lista percorsi noti
    4. Registro Windows (solo Windows)
    5. Glob in System32/Program Files (solo Windows, ultimo tentativo)
    """
    global _lib_cache

    if override and os.path.exists(override):
        _lib_cache = override
        return override

    if _lib_cache and os.path.exists(_lib_cache):
        return _lib_cache

    candidati = _candidate_pkcs11_libs()
    if not candidati:
        return None

    scored = sorted(
        ((lib_path, _score_pkcs11_lib(lib_path)) for lib_path in candidati),
        key=lambda item: item[1],
        reverse=True,
    )
    best_path, best_score = scored[0]
    if best_score > 0:
        log.info("PKCS#11 selezionata: %s (score=%s)", best_path, best_score)
    else:
        log.info("PKCS#11 fallback su prima libreria disponibile: %s", best_path)
    _lib_cache = best_path
    return best_path


def _format_cert_not_valid_after(cert_obj) -> str:
    """
    Restituisce la scadenza del certificato in formato YYYY-MM-DD.
    Compatibile con cryptography >= 42 evitando l'uso di proprietà deprecate.
    """
    dt = getattr(cert_obj, "not_valid_after_utc", None)
    if dt is None:
        dt = cert_obj.not_valid_after
    return dt.strftime("%Y-%m-%d")


def _ricorda_certificato_windows(cert: Optional[dict]) -> None:
    global _ultimo_certificato_windows
    if cert and cert.get("thumbprint"):
        _ultimo_certificato_windows = dict(cert)


def _certificato_windows_effettivo(cert_thumbprint: Optional[str]) -> str:
    thumbprint = (cert_thumbprint or "").strip()
    if thumbprint:
        return thumbprint
    cached = _ultimo_certificato_windows or {}
    return (cached.get("thumbprint") or "").strip()


def _require_certificato_pst(cert_thumbprint: Optional[str]) -> Optional[str]:
    effective_thumbprint = _certificato_windows_effettivo(cert_thumbprint)
    if sys.platform == "win32" and not effective_thumbprint:
        raise RuntimeError(
            "Per la ricerca PST reale serve prima selezionare il certificato CNS/CIE "
            "di autenticazione web.\n"
            "Aprire 'Seleziona certificato' dal wizard oppure usare il pulsante "
            "'Cerca su PST', che adesso lo richiede automaticamente.\n"
            "Dopo la selezione del certificato, Windows richiedera' anche il PIN "
            "del dispositivo durante la connessione al PST."
        )
    return effective_thumbprint or None


def _resolve_pst_session_entry(session_id: Optional[str]) -> Optional[dict]:
    sid = (session_id or "").strip()
    if not sid:
        return None
    entry = _get_pst_session(sid)
    if entry:
        return entry
    raise RuntimeError(
        "session_expired: Sessione accesso PST scaduta o non disponibile. "
        "Per sicurezza reinserire il PIN una sola volta e riaprire il canale autenticato."
    )


def _estrai_codice_fiscale_testo(valore: str) -> str:
    match = _CF_PATTERN.search((valore or "").upper())
    return match.group(1) if match else ""


def _parse_optional_int(value: Any) -> Optional[int]:
    text = str(value or "").strip()
    return int(text) if text.isdigit() else None


def _parse_portale_data(valore: Any) -> str:
    if not valore:
        return ""
    if isinstance(valore, (date, datetime)):
        return valore.strftime("%Y-%m-%d")
    return str(valore)[:10]


def _parse_portale_lista(
    valore: Any,
    *,
    container_attrs: tuple[str, ...],
    value_attrs: tuple[str, ...] = ("nominativo",),
) -> list[str]:
    if not valore:
        return []
    if isinstance(valore, list):
        return [str(v) for v in valore if str(v).strip()]

    for attr in container_attrs:
        if not hasattr(valore, attr):
            continue
        items = getattr(valore, attr)
        if not isinstance(items, list):
            items = [items]
        risultati: list[str] = []
        for item in items:
            if item is None:
                continue
            testo = ""
            for value_attr in value_attrs:
                candidato = getattr(item, value_attr, None)
                if candidato:
                    testo = str(candidato)
                    break
            risultati.append(testo or str(item))
        return risultati

    return [str(valore)]


def _portale_items(risposta: Any, plural_attr: str, singular_attr: str) -> list[Any]:
    items = getattr(risposta, plural_attr, None) or getattr(risposta, singular_attr, None) or []
    if not isinstance(items, list):
        items = [items]
    return [item for item in items if item is not None]


def _parse_pdp_fascicoli_response(risposta: Any) -> list[dict[str, Any]]:
    fascicoli: list[dict[str, Any]] = []
    try:
        for item in _portale_items(risposta, "fascicoli", "fascicolo"):
            fascicoli.append({
                "numero_rg": str(getattr(item, "numeroRG", "") or ""),
                "anno_rg": int(getattr(item, "annoRG", 0) or 0),
                "tipo_registro": str(getattr(item, "tipoRegistro", "RGNR") or ""),
                "fase": str(getattr(item, "fase", "INDAGINI") or ""),
                "stato": str(getattr(item, "stato", "PENDENTE") or ""),
                "reato": str(getattr(item, "reato", "") or ""),
                "sezione": str(getattr(item, "sezione", "") or ""),
                "giudice": str(getattr(item, "giudice", "") or ""),
                "data_iscrizione": _parse_portale_data(getattr(item, "dataIscrizione", None)),
                "data_udienza": _parse_portale_data(getattr(item, "dataUdienza", None)),
                "imputati": _parse_portale_lista(
                    getattr(item, "imputati", None),
                    container_attrs=("imputato", "parte", "soggetto"),
                ),
                "parti_offese": _parse_portale_lista(
                    getattr(item, "partiOffese", None),
                    container_attrs=("parte", "soggetto", "imputato"),
                ),
                "codice_ufficio": str(getattr(item, "codiceUfficio", "") or ""),
                "nome_ufficio": str(getattr(item, "nomeUfficio", "") or ""),
            })
    except (AttributeError, TypeError, ValueError):
        return []
    return fascicoli


def _parse_pdp_documenti_response(risposta: Any) -> list[dict[str, Any]]:
    documenti: list[dict[str, Any]] = []
    try:
        for item in _portale_items(risposta, "documenti", "documento"):
            documenti.append({
                "id_documento": str(getattr(item, "idDocumento", "") or ""),
                "nome": str(getattr(item, "nomeFile", "") or ""),
                "tipo": str(getattr(item, "tipoDocumento", "ATTO") or ""),
                "data_deposito": _parse_portale_data(getattr(item, "dataDeposito", None)),
                "mittente": str(getattr(item, "mittente", "") or ""),
                "dimensione_bytes": int(getattr(item, "dimensione", 0) or 0),
                "disponibile": bool(getattr(item, "disponibile", True)),
                "id_deposito": str(getattr(item, "idDeposito", "") or ""),
                "tipo_atto": str(getattr(item, "tipoAtto", "") or ""),
            })
    except (AttributeError, TypeError, ValueError):
        return []
    return documenti


def _parse_pat_fascicoli_response(risposta: Any) -> list[dict[str, Any]]:
    fascicoli: list[dict[str, Any]] = []
    try:
        for item in _portale_items(risposta, "ricorsi", "ricorso"):
            fascicoli.append({
                "numero_ricorso": str(getattr(item, "numeroRicorso", "") or ""),
                "anno": int(getattr(item, "anno", 0) or 0),
                "tipo": str(getattr(item, "tipo", "RICORSO") or ""),
                "stato": str(getattr(item, "stato", "PENDENTE") or ""),
                "materia": str(getattr(item, "materia", "") or ""),
                "sezione": str(getattr(item, "sezione", "") or ""),
                "giudice_relatore": str(getattr(item, "giudiceRelatore", "") or ""),
                "data_deposito": _parse_portale_data(getattr(item, "dataDeposito", None)),
                "data_udienza": _parse_portale_data(getattr(item, "dataUdienza", None)),
                "ricorrenti": _parse_portale_lista(
                    getattr(item, "ricorrenti", None),
                    container_attrs=("soggetto", "parte", "ricorrente"),
                    value_attrs=("denominazione", "nominativo"),
                ),
                "resistenti": _parse_portale_lista(
                    getattr(item, "resistenti", None),
                    container_attrs=("soggetto", "parte", "resistente"),
                    value_attrs=("denominazione", "nominativo"),
                ),
                "controinteressati": _parse_portale_lista(
                    getattr(item, "controinteressati", None),
                    container_attrs=("soggetto", "parte"),
                    value_attrs=("denominazione", "nominativo"),
                ),
                "oggetto": str(getattr(item, "oggetto", "") or ""),
                "codice_ufficio": str(getattr(item, "codiceUfficio", "") or ""),
                "nome_ufficio": str(getattr(item, "nomeUfficio", "") or ""),
            })
    except (AttributeError, TypeError, ValueError):
        return []
    return fascicoli


def _parse_pat_documenti_response(risposta: Any) -> list[dict[str, Any]]:
    documenti: list[dict[str, Any]] = []
    try:
        for item in _portale_items(risposta, "documenti", "documento"):
            documenti.append({
                "id_documento": str(getattr(item, "idDocumento", "") or ""),
                "nome": str(getattr(item, "nomeFile", "") or ""),
                "tipo": str(getattr(item, "tipoDocumento", "ATTO") or ""),
                "data_deposito": _parse_portale_data(getattr(item, "dataDeposito", None)),
                "mittente": str(getattr(item, "mittente", "") or ""),
                "dimensione_bytes": int(getattr(item, "dimensione", 0) or 0),
                "disponibile": bool(getattr(item, "disponibile", True)),
                "id_deposito": str(getattr(item, "idDeposito", "") or ""),
                "tipo_atto": str(getattr(item, "tipoAtto", "") or ""),
            })
    except (AttributeError, TypeError, ValueError):
        return []
    return documenti


def _parse_ptt_fascicoli_response(risposta: Any) -> list[dict[str, Any]]:
    fascicoli: list[dict[str, Any]] = []
    try:
        for item in _portale_items(risposta, "fascicoli", "fascicolo"):
            fascicoli.append({
                "numero_rgt": str(getattr(item, "numeroRGT", "") or ""),
                "anno_rgt": int(getattr(item, "annoRGT", 0) or 0),
                "tipo": str(getattr(item, "tipoRicorso", "RICORSO") or ""),
                "stato": str(getattr(item, "stato", "PENDENTE") or ""),
                "materia": str(getattr(item, "materia", "") or ""),
                "sezione": str(getattr(item, "sezione", "") or ""),
                "giudice_relatore": str(getattr(item, "giudiceRelatore", "") or ""),
                "data_deposito": _parse_portale_data(getattr(item, "dataDeposito", None)),
                "data_udienza": _parse_portale_data(getattr(item, "dataUdienza", None)),
                "ricorrenti": _parse_portale_lista(
                    getattr(item, "ricorrenti", None),
                    container_attrs=("ricorrente", "soggetto", "parte"),
                ),
                "resistenti": _parse_portale_lista(
                    getattr(item, "resistenti", None),
                    container_attrs=("resistente", "soggetto", "parte"),
                ),
                "oggetto_controversia": str(getattr(item, "oggettoControversia", "") or ""),
                "valore_controversia": float(getattr(item, "valoreControversia", 0.0) or 0.0),
                "codice_commissione": str(getattr(item, "codiceCommissione", "") or ""),
                "nome_commissione": str(getattr(item, "nomeCommissione", "") or ""),
            })
    except (AttributeError, TypeError, ValueError):
        return []
    return fascicoli


def _parse_ptt_documenti_response(risposta: Any) -> list[dict[str, Any]]:
    documenti: list[dict[str, Any]] = []
    try:
        for item in _portale_items(risposta, "documenti", "documento"):
            documenti.append({
                "id_documento": str(getattr(item, "idDocumento", "") or ""),
                "nome": str(getattr(item, "nomeFile", "") or ""),
                "tipo": str(getattr(item, "tipoDocumento", "ATTO") or ""),
                "data_deposito": _parse_portale_data(getattr(item, "dataDeposito", None)),
                "mittente": str(getattr(item, "mittente", "") or ""),
                "dimensione_bytes": int(getattr(item, "dimensione", 0) or 0),
                "disponibile": bool(getattr(item, "disponibile", True)),
                "id_deposito": str(getattr(item, "idDeposito", "") or ""),
                "tipo_atto": str(getattr(item, "tipoAtto", "") or ""),
            })
    except (AttributeError, TypeError, ValueError):
        return []
    return documenti


def _trova_certificato_windows(cert_thumbprint: Optional[str]) -> dict:
    thumbprint = _certificato_windows_effettivo(cert_thumbprint).replace(" ", "").upper()
    cached = dict(_ultimo_certificato_windows or {})
    cached_thumb = str(cached.get("thumbprint") or "").replace(" ", "").upper()
    if thumbprint and cached_thumb == thumbprint:
        return cached
    if not thumbprint and cached:
        return cached
    if sys.platform != "win32":
        return {}
    for cert in _windows_lista_certificati():
        cert_thumb = str(cert.get("thumbprint") or "").replace(" ", "").upper()
        if cert_thumb == thumbprint:
            return dict(cert)
    return {}


def _cf_avvocato_pst(cf_avvocato: str, cert_thumbprint: Optional[str] = None) -> str:
    explicit = _estrai_codice_fiscale_testo(cf_avvocato)
    cert = _trova_certificato_windows(cert_thumbprint)
    for campo in ("codice_fiscale", "soggetto", "soggetto_completo", "emittente", "emittente_completo"):
        resolved = _estrai_codice_fiscale_testo(str(cert.get(campo) or ""))
        if resolved:
            return resolved
    if explicit:
        return explicit
    return ""


def _require_cf_avvocato_locale(cf_avvocato: str, cert_thumbprint: Optional[str]) -> str:
    resolved = _cf_avvocato_pst(cf_avvocato, cert_thumbprint)
    if resolved:
        return resolved
    raise RuntimeError(
        "Impossibile determinare il codice fiscale dell'avvocato dal certificato selezionato.\n"
        "Riselezionare il certificato CNS/CIE oppure configurare il codice fiscale in Impostazioni → Firma Digitale."
    )


# ── PKCS#11 helpers ────────────────────────────────────────────────────────────

def _info_token(lib_path: str) -> list[dict]:
    """
    Legge informazioni sul token senza PIN (operazione pubblica).
    Lancia eccezioni con messaggi esplicativi invece di restituire [] silenziosamente.
    """
    try:
        import pkcs11
    except ImportError:
        raise RuntimeError(
            "Il modulo 'python-pkcs11' non è installato.\n"
            "Eseguire: pip install python-pkcs11"
        )

    try:
        lib_obj = pkcs11.lib(lib_path)
    except Exception as e:
        raise RuntimeError(
            f"Impossibile caricare la libreria PKCS#11 ({lib_path}).\n"
            f"Dettaglio: {e}\n"
            "Verificare che il middleware PKCS#11 del dispositivo sia installato correttamente."
        )

    try:
        slots = lib_obj.get_slots(token_present=True)
    except Exception as e:
        raise RuntimeError(
            f"Errore nella lettura degli slot PKCS#11: {e}\n"
            "Provare a reinserire la smart card/token o il lettore."
        )

    if not slots:
        raise RuntimeError(
            "Nessun token PKCS#11 rilevato.\n"
            "Verificare che la smart card/token CNS-CIE sia inserita e che il middleware locale sia installato."
        )

    tokens = []
    for slot in slots:
        try:
            tok = slot.get_token()
            tokens.append({
                "slot_id": slot.slot_id,
                "label":        _pkcs11_text(getattr(tok, "label", "")),
                "manufacturer": _pkcs11_text(getattr(tok, "manufacturer_id", "")),
                "model":        _pkcs11_text(getattr(tok, "model", "")),
                "serial":       _pkcs11_text(getattr(tok, "serial", "")),
            })
        except Exception as e:
            log.warning("Slot %s: %s", getattr(slot, "slot_id", "?"), e)
    return tokens


# ── Windows Certificate Store (ctypes) ─────────────────────────────────────────

def _estrai_info_cert_ctx(crypt32, cert_ctx_addr: int) -> Optional[dict]:
    """
    Estrae thumbprint, soggetto, emittente, scadenza da un PCCERT_CONTEXT
    (indirizzo intero restituito da ctypes con restype=c_void_p).
    """
    import ctypes

    if not cert_ctx_addr:
        return None

    try:
        # Leggi DER bytes dal CERT_CONTEXT (dwCertEncodingType | pbCertEncoded | cbCertEncoded)
        class _CERT_CONTEXT(ctypes.Structure):
            _fields_ = [
                ("dwCertEncodingType", ctypes.c_uint32),
                ("pbCertEncoded",      ctypes.c_void_p),
                ("cbCertEncoded",      ctypes.c_uint32),
            ]

        ctx = _CERT_CONTEXT.from_address(cert_ctx_addr)
        der = b""
        if ctx.cbCertEncoded > 0 and ctx.pbCertEncoded:
            der = bytes((ctypes.c_ubyte * ctx.cbCertEncoded).from_address(ctx.pbCertEncoded))

        # Thumbprint SHA1 via CertGetCertificateContextProperty (CERT_SHA1_HASH_PROP_ID = 3)
        CERT_SHA1_HASH_PROP_ID = 3
        crypt32.CertGetCertificateContextProperty.restype = ctypes.c_bool
        crypt32.CertGetCertificateContextProperty.argtypes = [
            ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_uint),
        ]
        buf_size = ctypes.c_uint(0)
        crypt32.CertGetCertificateContextProperty(
            cert_ctx_addr, CERT_SHA1_HASH_PROP_ID, None, ctypes.byref(buf_size)
        )
        thumbprint = ""
        if buf_size.value > 0:
            buf = (ctypes.c_ubyte * buf_size.value)()
            if crypt32.CertGetCertificateContextProperty(
                cert_ctx_addr, CERT_SHA1_HASH_PROP_ID, buf, ctypes.byref(buf_size)
            ):
                thumbprint = bytes(buf).hex().upper()

        # Soggetto e Emittente via CertGetNameStringW (CERT_NAME_SIMPLE_DISPLAY_TYPE = 4)
        CERT_NAME_SIMPLE_DISPLAY_TYPE = 4
        CERT_NAME_ISSUER_FLAG = 0x1
        crypt32.CertGetNameStringW.restype = ctypes.c_uint
        crypt32.CertGetNameStringW.argtypes = [
            ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p,
            ctypes.c_wchar_p, ctypes.c_uint,
        ]

        def _nome(flags: int) -> str:
            sz = crypt32.CertGetNameStringW(
                cert_ctx_addr, CERT_NAME_SIMPLE_DISPLAY_TYPE, flags, None, None, 0
            )
            if sz <= 1:
                return ""
            buf_n = ctypes.create_unicode_buffer(sz)
            crypt32.CertGetNameStringW(
                cert_ctx_addr, CERT_NAME_SIMPLE_DISPLAY_TYPE, flags, None, buf_n, sz
            )
            return buf_n.value

        soggetto = _nome(0)
        emittente = _nome(CERT_NAME_ISSUER_FLAG)
        scadenza_iso = ""
        soggetto_completo = ""
        emittente_completo = ""
        codice_fiscale = ""

        # Scadenza — parse DER con cryptography se disponibile
        if der:
            try:
                from cryptography import x509 as cx509
                from cryptography.hazmat.backends import default_backend
                cert_obj = cx509.load_der_x509_certificate(der, default_backend())
                scadenza_iso = _format_cert_not_valid_after(cert_obj)
                soggetto_completo = cert_obj.subject.rfc4514_string()
                emittente_completo = cert_obj.issuer.rfc4514_string()
                codice_fiscale = _estrai_codice_fiscale_testo(soggetto_completo)
                if not soggetto:
                    cn = cert_obj.subject.get_attributes_for_oid(cx509.NameOID.COMMON_NAME)
                    soggetto = cn[0].value if cn else ""
                if not emittente:
                    cn = cert_obj.issuer.get_attributes_for_oid(cx509.NameOID.COMMON_NAME)
                    emittente = cn[0].value if cn else ""
            except Exception:
                pass

        return {
            "thumbprint": thumbprint,
            "soggetto":   soggetto,
            "soggetto_completo": soggetto_completo,
            "emittente":  emittente,
            "emittente_completo": emittente_completo,
            "scadenza":   scadenza_iso,
            "codice_fiscale": codice_fiscale,
        }

    except Exception as e:
        log.warning("_estrai_info_cert_ctx: %s", e)
        return None


def _windows_lista_certificati() -> list[dict]:
    """
    Elenca i certificati nel Windows Certificate Store (store 'MY').
    Ritorna lista di dict {thumbprint, soggetto, emittente, scadenza}.
    Solo su Windows (ritorna [] sulle altre piattaforme).
    """
    if sys.platform != "win32":
        return []
    import ctypes
    try:
        crypt32 = ctypes.WinDLL("Crypt32.dll", use_last_error=True)
        crypt32.CertOpenSystemStoreW.restype = ctypes.c_void_p
        crypt32.CertOpenSystemStoreW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
        crypt32.CertEnumCertificatesInStore.restype = ctypes.c_void_p
        crypt32.CertEnumCertificatesInStore.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        crypt32.CertCloseStore.restype = ctypes.c_bool
        crypt32.CertCloseStore.argtypes = [ctypes.c_void_p, ctypes.c_uint]

        h_store = crypt32.CertOpenSystemStoreW(None, "MY")
        if not h_store:
            raise RuntimeError(f"CertOpenSystemStoreW fallito (err {ctypes.get_last_error()})")

        certs: list[dict] = []
        # CertEnumCertificatesInStore trasferisce ownership: non liberare il ctx precedente
        cert_ctx = crypt32.CertEnumCertificatesInStore(h_store, None)
        while cert_ctx:
            info = _estrai_info_cert_ctx(crypt32, cert_ctx)
            if info:
                certs.append(info)
            cert_ctx = crypt32.CertEnumCertificatesInStore(h_store, cert_ctx)

        crypt32.CertCloseStore(h_store, 0)
        return certs
    except Exception as e:
        log.warning("_windows_lista_certificati: %s", e)
        return []


def _windows_seleziona_cert() -> Optional[dict]:
    """
    Apre la finestra nativa Windows di selezione certificato e restituisce
    il certificato scelto come dict compatibile con _windows_lista_certificati().

    Ritorna None se l'utente annulla. Disponibile solo su Windows.
    """
    if sys.platform != "win32":
        raise RuntimeError("Selezione nativa disponibile solo su Windows")

    import ctypes

    try:
        crypt32 = ctypes.WinDLL("Crypt32.dll", use_last_error=True)
        cryptui = ctypes.WinDLL("CryptUI.dll", use_last_error=True)
    except OSError as e:
        raise RuntimeError(
            "Componenti Windows per la selezione certificato non disponibili. "
            "Verificare l'installazione del sistema o del middleware smart card."
        ) from e

    crypt32.CertOpenSystemStoreW.restype = ctypes.c_void_p
    crypt32.CertOpenSystemStoreW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
    crypt32.CertCloseStore.restype = ctypes.c_bool
    crypt32.CertCloseStore.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    crypt32.CertFreeCertificateContext.restype = ctypes.c_bool
    crypt32.CertFreeCertificateContext.argtypes = [ctypes.c_void_p]

    cryptui.CryptUIDlgSelectCertificateFromStore.restype = ctypes.c_void_p
    cryptui.CryptUIDlgSelectCertificateFromStore.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_wchar_p,
        ctypes.c_wchar_p,
        ctypes.c_uint,
        ctypes.c_uint,
        ctypes.c_void_p,
    ]

    h_store = crypt32.CertOpenSystemStoreW(None, "MY")
    if not h_store:
        raise RuntimeError(f"CertOpenSystemStoreW fallito (err {ctypes.get_last_error()})")

    cert_ctx = None
    try:
        cert_ctx = cryptui.CryptUIDlgSelectCertificateFromStore(
            h_store,
            None,
            "IUSENTRA - Seleziona certificato PST",
            "Seleziona il certificato di autenticazione web per il PST "
            "(smart card o token CNS/CIE).",
            0,
            0,
            None,
        )
        if not cert_ctx:
            return None
        info = _estrai_info_cert_ctx(crypt32, cert_ctx)
        if not info:
            raise RuntimeError("Impossibile leggere il certificato selezionato.")
        return info
    finally:
        if cert_ctx:
            crypt32.CertFreeCertificateContext(cert_ctx)
        crypt32.CertCloseStore(h_store, 0)


def _cert_match_normalized(value: str) -> str:
    testo = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", testo.lower()).strip()


def _cert_match_keywords(raw: str | list[str] | tuple[str, ...]) -> list[str]:
    if isinstance(raw, (list, tuple)):
        parts = raw
    else:
        parts = re.split(r"[,\n;|]+", str(raw or ""))
    return [item for item in (_cert_match_normalized(part) for part in parts) if item]


def _cert_preferred_score(
    cert: dict,
    issuer_keywords: list[str],
    subject_keywords: list[str],
    prefer_cf: str = "",
) -> int:
    issuer = _cert_match_normalized(
        " ".join(
            [
                str(cert.get("emittente") or ""),
                str(cert.get("emittente_completo") or ""),
            ]
        )
    )
    subject = _cert_match_normalized(
        " ".join(
            [
                str(cert.get("soggetto") or ""),
                str(cert.get("soggetto_completo") or ""),
                str(cert.get("codice_fiscale") or ""),
            ]
        )
    )
    score = 0

    for idx, keyword in enumerate(issuer_keywords):
        if keyword and keyword in issuer:
            score = max(score, 100 - (idx * 10))
    for idx, keyword in enumerate(subject_keywords):
        if keyword and keyword in subject:
            score = max(score, 60 - (idx * 5))

    for hint in _PST_CERT_SUBJECT_HINTS:
        if hint in subject:
            score += 5

    cf = _estrai_codice_fiscale_testo(prefer_cf)
    if cf and cf in (
        f"{cert.get('codice_fiscale', '')} "
        f"{cert.get('soggetto', '')} "
        f"{cert.get('soggetto_completo', '')}"
    ).upper():
        score += 500

    return score


def _pick_preferred_windows_cert(
    certs: list[dict],
    *,
    prefer_issuer: str = "",
    prefer_subject: str = "",
    prefer_cf: str = "",
    auto: bool = False,
) -> Optional[dict]:
    lista = list(certs or [])
    if not lista:
        return None

    prefer_cf_norm = _estrai_codice_fiscale_testo(prefer_cf)

    # Se è richiesto un codice fiscale, l'auto-selezione deve lavorare
    # SOLO sui certificati che contengono davvero quel CF.
    # Se nessuno combacia, niente auto-pick: si aprirà il selettore Windows.
    if prefer_cf_norm:
        matching_cf = [
            cert for cert in lista
            if prefer_cf_norm in (
                f"{cert.get('codice_fiscale', '')} "
                f"{cert.get('soggetto', '')} "
                f"{cert.get('soggetto_completo', '')}"
            ).upper()
        ]
        if not matching_cf:
            return None
        lista = matching_cf
        if len(lista) == 1:
            return lista[0]

    issuer_keywords = _cert_match_keywords(prefer_issuer)
    subject_keywords = _cert_match_keywords(prefer_subject)

    if auto and not issuer_keywords:
        issuer_keywords = _cert_match_keywords(_PST_CERT_ISSUER_PRIORITIES)
    if auto and not subject_keywords:
        subject_keywords = _cert_match_keywords(_PST_CERT_SUBJECT_HINTS)

    # Se non ho keyword ma ho un CF valido, posso comunque scegliere
    # tra i certificati già filtrati per CF.
    if not issuer_keywords and not subject_keywords and not prefer_cf_norm:
        return None

    scored = []
    for cert in lista:
        score = _cert_preferred_score(
            cert,
            issuer_keywords,
            subject_keywords,
            prefer_cf=prefer_cf_norm,
        )

        # Se sto scegliendo solo in base al CF, assegno un punteggio minimo
        # per consentire la scelta del certificato unico compatibile.
        if prefer_cf_norm and not issuer_keywords and not subject_keywords:
            score = max(score, 1)

        if score > 0:
            scored.append((score, cert))

    if not scored:
        return None

    scored.sort(key=lambda item: item[0], reverse=True)

    if len(scored) == 1:
        return scored[0][1]

    # Se il primo è nettamente migliore, ok.
    if scored[0][0] > scored[1][0]:
        return scored[0][1]

    # Parità: meglio non scegliere automaticamente.
    return None


def _ping_query_preferences(path: str) -> dict:
    query = parse_qs(urlparse(path).query or "")
    prefer_cf = str((query.get("prefer_cf") or [""])[0] or "").strip()
    if not prefer_cf:
        prefer_cf = str(os.getenv("PCT_CF_AVVOCATO", "") or "").strip()
    return {
        "prefer_issuer": str((query.get("prefer_issuer") or [""])[0] or "").strip(),
        "prefer_subject": str((query.get("prefer_subject") or [""])[0] or "").strip(),
        "prefer_cf": prefer_cf,
        "auto": str((query.get("auto") or ["1"])[0] or "").strip().lower() in {"1", "true", "yes", "on"},
    }


def _ping_is_light(path: str) -> bool:
    query = parse_qs(urlparse(path).query or "")
    return str((query.get("light") or ["0"])[0] or "").strip().lower() in {"1", "true", "yes", "on"}


def _pick_preferred_windows_cert(
    certs: list[dict],
    *,
    prefer_issuer: str = "",
    prefer_subject: str = "",
    prefer_cf: str = "",
    auto: bool = False,
) -> Optional[dict]:
    lista = list(certs or [])
    if not lista:
        return None

    prefer_cf_norm = _estrai_codice_fiscale_testo(prefer_cf)

    if prefer_cf_norm:
        matching_cf = [
            cert for cert in lista
            if prefer_cf_norm in (
                f"{cert.get('codice_fiscale', '')} "
                f"{cert.get('soggetto', '')} "
                f"{cert.get('soggetto_completo', '')}"
            ).upper()
        ]
        if not matching_cf:
            return None
        lista = matching_cf
        if len(lista) == 1:
            return lista[0]

    issuer_keywords = _cert_match_keywords(prefer_issuer)
    subject_keywords = _cert_match_keywords(prefer_subject)

    if auto and not issuer_keywords:
        issuer_keywords = _cert_match_keywords(_PST_CERT_ISSUER_PRIORITIES)
    if auto and not subject_keywords:
        subject_keywords = _cert_match_keywords(_PST_CERT_SUBJECT_HINTS)

    if not issuer_keywords and not subject_keywords and not prefer_cf_norm:
        return None

    scored = []
    for cert in lista:
        score = _cert_preferred_score(
            cert,
            issuer_keywords,
            subject_keywords,
            prefer_cf=prefer_cf_norm,
        )

        issuer_norm = _cert_match_normalized(
            " ".join([
                str(cert.get("emittente") or ""),
                str(cert.get("emittente_completo") or ""),
            ])
        )
        subject_norm = _cert_match_normalized(
            " ".join([
                str(cert.get("soggetto") or ""),
                str(cert.get("soggetto_completo") or ""),
                str(cert.get("codice_fiscale") or ""),
            ])
        )

        has_authentica = "authentica" in issuer_norm
        has_web_hint = any(h in subject_norm for h in _PST_CERT_SUBJECT_HINTS)
        is_only_qualified = ("qualified" in issuer_norm) and not has_authentica and not has_web_hint

        # Se il certificato sembra solo "Qualified" e non da autenticazione web,
        # non deve mai essere auto-selezionato per PST.
        if is_only_qualified:
            continue

        if prefer_cf_norm and not issuer_keywords and not subject_keywords:
            score = max(score, 1)

        if score > 0:
            scored.append((score, cert))

    if not scored:
        return None

    scored.sort(key=lambda item: item[0], reverse=True)

    if len(scored) == 1:
        return scored[0][1]

    if scored[0][0] > scored[1][0]:
        return scored[0][1]

    return None


def _certificato_windows_compatibile_pst(
    cert: Optional[dict],
    *,
    prefer_issuer: str = "",
    prefer_subject: str = "",
    prefer_cf: str = "",
) -> bool:
    if not cert or not str(cert.get("thumbprint") or "").strip():
        return False

    prefer_cf_norm = _estrai_codice_fiscale_testo(prefer_cf)
    subject_raw = (
        f"{cert.get('codice_fiscale', '')} "
        f"{cert.get('soggetto', '')} "
        f"{cert.get('soggetto_completo', '')}"
    )
    if prefer_cf_norm and prefer_cf_norm not in subject_raw.upper():
        return False

    issuer_norm = _cert_match_normalized(
        " ".join([
            str(cert.get("emittente") or ""),
            str(cert.get("emittente_completo") or ""),
        ])
    )
    subject_norm = _cert_match_normalized(subject_raw)
    has_authentica = "authentica" in issuer_norm
    has_web_hint = any(h in subject_norm for h in _PST_CERT_SUBJECT_HINTS)
    is_only_qualified = ("qualified" in issuer_norm) and not has_authentica and not has_web_hint
    if is_only_qualified:
        return False

    issuer_keywords = _cert_match_keywords(prefer_issuer)
    subject_keywords = _cert_match_keywords(prefer_subject)
    if issuer_keywords or subject_keywords:
        return _cert_preferred_score(
            cert,
            issuer_keywords,
            subject_keywords,
            prefer_cf=prefer_cf_norm,
        ) > 0

    return True


def _close_pin_session_entry(entry: Optional[dict]) -> None:
    if not entry:
        return
    signer = entry.get("signer")
    if signer is None:
        return
    try:
        signer.close()
    except Exception:
        pass


def _ensure_cookie_file(cookie_file: Optional[str] = None) -> str:
    path = Path(cookie_file) if cookie_file else Path(tempfile.mkstemp(prefix="hacs_pst_", suffix=".cookies")[1])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(exist_ok=True)
    return str(path)


def _close_pst_session_entry(entry: Optional[dict]) -> None:
    if not entry:
        return
    cookie_file = str(entry.get("cookie_file") or "").strip()
    if not cookie_file:
        return
    try:
        Path(cookie_file).unlink(missing_ok=True)
    except Exception:
        pass


def _cleanup_pin_sessions(now: Optional[datetime] = None) -> int:
    current = now or _utcnow_naive()
    expired: list[dict] = []
    with _pin_session_lock:
        for session_id, entry in list(_pin_session_cache.items()):
            if entry.get("expires_at") and entry["expires_at"] <= current:
                expired.append(_pin_session_cache.pop(session_id))
    for entry in expired:
        _close_pin_session_entry(entry)
    return len(_pin_session_cache)


def _cleanup_pst_sessions(now: Optional[datetime] = None) -> int:
    current = now or _utcnow_naive()
    expired: list[dict] = []
    with _pst_session_lock:
        for session_id, entry in list(_pst_session_cache.items()):
            if entry.get("expires_at") and entry["expires_at"] <= current:
                expired.append(_pst_session_cache.pop(session_id))
    for entry in expired:
        _close_pst_session_entry(entry)
    return len(_pst_session_cache)


def _get_pin_session(session_id: str, *, refresh: bool = True) -> Optional[dict]:
    sid = (session_id or "").strip()
    if not sid:
        return None

    current = _utcnow_naive()
    expired_entry: Optional[dict] = None
    with _pin_session_lock:
        entry = _pin_session_cache.get(sid)
        if not entry:
            return None
        if entry.get("expires_at") and entry["expires_at"] <= current:
            expired_entry = _pin_session_cache.pop(sid, None)
            entry = None
        elif refresh:
            entry["last_used_at"] = current
            entry["expires_at"] = current + timedelta(seconds=PIN_SESSION_TTL_SECONDS)
    if expired_entry:
        _close_pin_session_entry(expired_entry)
    return entry


def _get_pst_session(session_id: str, *, refresh: bool = True) -> Optional[dict]:
    sid = (session_id or "").strip()
    if not sid:
        return None

    current = _utcnow_naive()
    expired_entry: Optional[dict] = None
    with _pst_session_lock:
        entry = _pst_session_cache.get(sid)
        if not entry:
            return None
        if entry.get("expires_at") and entry["expires_at"] <= current:
            expired_entry = _pst_session_cache.pop(sid, None)
            entry = None
        elif refresh:
            entry["last_used_at"] = current
            entry["expires_at"] = current + timedelta(seconds=PST_SESSION_TTL_SECONDS)
    if expired_entry:
        _close_pst_session_entry(expired_entry)
    return entry


def _drop_pin_session(session_id: str) -> None:
    sid = (session_id or "").strip()
    if not sid:
        return
    with _pin_session_lock:
        entry = _pin_session_cache.pop(sid, None)
    _close_pin_session_entry(entry)


def _drop_pst_session(session_id: str) -> None:
    sid = (session_id or "").strip()
    if not sid:
        return
    with _pst_session_lock:
        entry = _pst_session_cache.pop(sid, None)
    _close_pst_session_entry(entry)


def _reset_pst_session_cookie_after_auth_failure(cookie_file: Optional[str], reason: str = "") -> str:
    old_cookie = str(cookie_file or "").strip()
    new_cookie = _ensure_cookie_file()
    matched = False
    current = _utcnow_naive()
    with _pst_session_lock:
        for entry in _pst_session_cache.values():
            if str(entry.get("cookie_file") or "").strip() != old_cookie:
                continue
            entry["cookie_file"] = new_cookie
            entry["auth_ready"] = False
            entry["preflight_attempted"] = False
            entry["last_auth_error"] = str(reason or "").strip()
            entry["last_used_at"] = current
            entry["expires_at"] = current + timedelta(seconds=PST_SESSION_TTL_SECONDS)
            matched = True
    if old_cookie:
        try:
            Path(old_cookie).unlink(missing_ok=True)
        except Exception:
            pass
    if matched:
        log.info("PST sessione: cookie autenticazione scartato dopo rifiuto PST; prossimo tentativo richiede il certificato.")
    return new_cookie


def _update_pst_session(session_id: str, **updates) -> Optional[dict]:
    sid = (session_id or "").strip()
    if not sid:
        return None
    current = _utcnow_naive()
    with _pst_session_lock:
        entry = _pst_session_cache.get(sid)
        if not entry:
            return None
        for key, value in updates.items():
            if value not in (None, ""):
                entry[key] = value
        entry["last_used_at"] = current
        entry["expires_at"] = current + timedelta(seconds=PST_SESSION_TTL_SECONDS)
        return dict(entry)


def _pst_datetime_payload(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds") + "Z"
    return str(value or "")


def _pst_session_response_fields(session_entry: Optional[dict]) -> dict:
    if not session_entry:
        return {
            "pst_session_id": "",
            "pst_session_ttl_seconds": PST_SESSION_TTL_SECONDS,
            "pst_session_expires_at": "",
            "pst_session_purpose": "",
        }
    return {
        "pst_session_id": str(session_entry.get("session_id") or ""),
        "pst_session_ttl_seconds": PST_SESSION_TTL_SECONDS,
        "pst_session_expires_at": _pst_datetime_payload(session_entry.get("expires_at")),
        "pst_session_purpose": str(session_entry.get("purpose") or "view"),
    }


def _find_view_session_for_cert(cert_thumbprint: str, tribunale: str) -> Optional[dict]:
    """Restituisce la prima sessione view autenticata per lo stesso certificato e ufficio."""
    thumbprint = (cert_thumbprint or "").strip()
    trib = (tribunale or "").strip()
    now = _utcnow_naive()
    with _pst_session_lock:
        for entry in _pst_session_cache.values():
            if str(entry.get("purpose") or "view").lower() != "view":
                continue
            if thumbprint and entry.get("cert_thumbprint", "").strip() != thumbprint:
                continue
            if trib and entry.get("tribunale", "").strip() != trib:
                continue
            if entry.get("expires_at") and entry["expires_at"] <= now:
                continue
            if not entry.get("auth_ready"):
                continue
            return dict(entry)
    return None


def _reuse_view_session_id_if_available(session_id: str, cert_thumbprint: str, tribunale: str) -> str:
    """Riusa una sessione PST gia' autenticata quando il client non ne passa una."""
    requested_id = (session_id or "").strip()
    if requested_id:
        return requested_id
    view_entry = _find_view_session_for_cert(cert_thumbprint, tribunale)
    return str((view_entry or {}).get("session_id") or "").strip()


def _pst_existing_session_purpose(session_id: str, default: str = "view") -> str:
    fallback = (default or "view").strip().lower() or "view"
    if fallback not in {"view", "import"}:
        fallback = "view"
    requested_id = (session_id or "").strip()
    if not requested_id:
        return fallback
    try:
        session_entry = _resolve_pst_session_entry(requested_id)
    except Exception:
        return fallback
    purpose = str((session_entry or {}).get("purpose") or fallback).strip().lower() or fallback
    return purpose if purpose in {"view", "import"} else fallback


def _pst_session_lock_for(session_entry: Optional[dict]) -> threading.Lock:
    session_id = str((session_entry or {}).get("session_id") or "").strip()
    if session_id:
        with _pst_session_lock:
            live = _pst_session_cache.get(session_id)
            if live is not None:
                lock = live.get("lock")
                if not hasattr(lock, "acquire"):
                    lock = threading.Lock()
                    live["lock"] = lock
                return lock
    return threading.Lock()


def _create_pst_session(
    *,
    cert_thumbprint: str,
    tribunale: str = "",
    base_url: str = "",
    cf_avvocato: str = "",
    cookie_file: Optional[str] = None,
    purpose: str = "view",
    cert_key: str = "",
    cert_preferences: Optional[dict] = None,
) -> dict:
    thumbprint = (cert_thumbprint or "").strip()
    if not thumbprint:
        raise RuntimeError("Certificato client obbligatorio per aprire la sessione PST.")

    _cleanup_pst_sessions()

    created_at = _utcnow_naive()
    entry = {
        "session_id": secrets.token_urlsafe(18),
        "cert_thumbprint": thumbprint,
        "tribunale": (tribunale or "").strip(),
        "base_url": (base_url or "").strip(),
        "cf_avvocato": (cf_avvocato or "").strip(),
        "purpose": (purpose or "view").strip() or "view",
        "cert_key": (cert_key or cert_thumbprint or "").strip(),
        "cert_preferences": dict(cert_preferences or {}),
        "cookie_file": _ensure_cookie_file(cookie_file),
        "lock": threading.Lock(),
        "auth_ready": False,
        "preflight_attempted": False,
        "created_at": created_at,
        "last_used_at": created_at,
        "expires_at": created_at + timedelta(seconds=PST_SESSION_TTL_SECONDS),
    }

    stale_entries: list[dict] = []
    with _pst_session_lock:
        _pst_session_cache[entry["session_id"]] = entry
        if len(_pst_session_cache) > PST_SESSION_MAX_ACTIVE:
            overflow = sorted(
                _pst_session_cache.values(),
                key=lambda item: item.get("last_used_at") or item.get("created_at") or datetime.min,
            )[:-PST_SESSION_MAX_ACTIVE]
            for stale in overflow:
                removed = _pst_session_cache.pop(stale["session_id"], None)
                if removed is not None:
                    stale_entries.append(removed)
    for stale in stale_entries:
        _close_pst_session_entry(stale)

    return dict(entry)


def _get_or_create_pst_session(
    *,
    session_id: str = "",
    purpose: str = "view",
    tribunale: str = "",
    cert_key: str = "",
    force_new: bool = False,
    cert_preferences: Optional[dict] = None,
    base_url: str = "",
    cf_avvocato: str = "",
    cert_thumbprint: str = "",
) -> dict:
    requested_id = (session_id or "").strip()
    normalized_purpose = (purpose or "view").strip().lower() or "view"
    if normalized_purpose not in {"view", "import"}:
        normalized_purpose = "view"

    if requested_id and not force_new:
        session_entry = _resolve_pst_session_entry(requested_id)
        if str(session_entry.get("purpose") or "view").lower() == normalized_purpose:
            updates = {
                "tribunale": tribunale,
                "base_url": base_url,
                "cf_avvocato": cf_avvocato,
                "cert_thumbprint": cert_thumbprint,
                "cert_key": cert_key or cert_thumbprint,
                "cert_preferences": dict(cert_preferences or {}),
            }
            _update_pst_session(session_entry["session_id"], **updates)
            refreshed = _get_pst_session(session_entry["session_id"])
            return refreshed or session_entry

    return _create_pst_session(
        cert_thumbprint=cert_thumbprint or cert_key or "",
        tribunale=tribunale,
        base_url=base_url,
        cf_avvocato=cf_avvocato,
        purpose=normalized_purpose,
        cert_key=cert_key or cert_thumbprint or "",
        cert_preferences=cert_preferences,
    )


def _ensure_pst_session_entry(
    requested_session_id: Optional[str],
    *,
    tribunale: str,
    base_url: str,
    cf_avvocato: str,
    cert_thumbprint: str,
    purpose: str = "view",
    force_new: bool = False,
    cert_key: str = "",
    cert_preferences: Optional[dict] = None,
) -> tuple[dict, bool]:
    before_id = (requested_session_id or "").strip()
    session_entry = _get_or_create_pst_session(
        session_id=before_id,
        purpose=purpose,
        tribunale=tribunale,
        base_url=base_url,
        cf_avvocato=cf_avvocato,
        cert_thumbprint=cert_thumbprint,
        cert_key=cert_key,
        cert_preferences=cert_preferences,
        force_new=force_new,
    )
    created = not before_id or before_id != str(session_entry.get("session_id") or "")
    return session_entry, created


def _pst_session_can_use_cookie_only(session_entry: Optional[dict], *, created_now: bool = False) -> bool:
    if not session_entry or created_now:
        return False
    cookie_file = str(session_entry.get("cookie_file") or "").strip()
    if not cookie_file:
        return False
    return bool(session_entry.get("auth_ready"))


def _pst_download_can_use_cookie_only(base_url: str, cookie_file: Optional[str]) -> bool:
    return bool(_pst_download_cookie_file(base_url, cookie_file))


def _pst_download_cookie_file(base_url: str, cookie_file: Optional[str]) -> str:
    # Le operazioni documento del proxy QBuilder possono restare appese quando
    # ricevono cookie della ricerca. Per il download si usa quindi il certificato
    # direttamente senza inviare cookie; il batch multiplo resta un unico
    # processo curl, quindi Windows chiede comunque un solo PIN per il lotto.
    if _pst_namespace_qbuilder(base_url):
        return ""
    return str(cookie_file or "").strip()


def _pst_preflight_confirmed(esito: Optional[dict]) -> bool:
    """Il cookie-only e' affidabile solo se il preflight ha prodotto un HTTP reale."""
    if not esito or not esito.get("ok"):
        return False
    try:
        return int(esito.get("http_code") or 0) > 0
    except (TypeError, ValueError):
        return False


def _pst_prepare_authenticated_session(
    session_entry: Optional[dict],
    *,
    tribunale: str,
    base_url: str,
    cf_avvocato: str,
    cert_thumbprint: Optional[str],
    force: bool = False,
) -> tuple[Optional[dict], bool]:
    if not session_entry:
        return None, False

    # Se l'host è già noto come mTLS-obbligatorio, non tentare mai cookie-only:
    # andare direttamente al certificato riduce i prompt PIN perché tutte le
    # chiamate successive rientrano nella finestra di cache-PIN di Windows.
    if not force and _pst_session_can_use_cookie_only(session_entry):
        return session_entry, True
    if not force and session_entry.get("preflight_attempted") and not session_entry.get("auth_ready"):
        # Un preflight gia' tentato ma senza HTTP reale (tipicamente timeout
        # mentre Windows/Bit4id gestisce il PIN) non dimostra cookie validi:
        # evitare un secondo warm-up e andare direttamente al certificato nella
        # chiamata operativa riduce i prompt ripetuti.
        return session_entry, False

    cookie_file = str(session_entry.get("cookie_file") or "").strip()
    esito = _pst_preflight_auth_curl(
        url=_pst_url_ricerca(base_url),
        cert_thumbprint=cert_thumbprint,
        cookie_file=cookie_file,
    )
    _update_pst_session(
        session_entry["session_id"],
        tribunale=tribunale,
        base_url=base_url,
        cf_avvocato=cf_avvocato,
        last_http_code=esito.get("http_code"),
        last_content_type=esito.get("content_type"),
        auth_ready=_pst_preflight_confirmed(esito),
        preflight_attempted=True,
    )
    refreshed = _resolve_pst_session_entry(session_entry["session_id"]) or session_entry
    # Dopo preflight, controlla se l'host richiede mTLS (potrebbe essere
    # stato registrato da una sessione precedente nella stessa istanza).
    prefer_cookie = _pst_preflight_confirmed(esito)
    return refreshed, prefer_cookie


def _create_pin_session(lib_path: str, pin: str, slot_id: Optional[int] = None) -> tuple[str, object]:
    if not pin:
        raise RuntimeError("PIN obbligatorio per aprire la sessione locale del token.")

    _cleanup_pin_sessions()

    from pct.firma_pkcs11 import FirmaPKCS11

    signer = FirmaPKCS11(
        library_path=lib_path,
        slot_id=slot_id if slot_id is not None else 0,
        pin=pin,
    )
    # Forza l'apertura del token e il caricamento del certificato una sola volta.
    signer.verifica_scadenza(giorni_preavviso=0)

    created_at = _utcnow_naive()
    entry = {
        "session_id": secrets.token_urlsafe(18),
        "signer": signer,
        "lib_path": lib_path,
        "slot_id": slot_id if slot_id is not None else 0,
        "created_at": created_at,
        "last_used_at": created_at,
        "expires_at": created_at + timedelta(seconds=PIN_SESSION_TTL_SECONDS),
    }

    stale_entries: list[dict] = []
    with _pin_session_lock:
        _pin_session_cache[entry["session_id"]] = entry
        if len(_pin_session_cache) > PIN_SESSION_MAX_ACTIVE:
            overflow = sorted(
                _pin_session_cache.values(),
                key=lambda item: item.get("last_used_at") or item.get("created_at") or datetime.min,
            )[:-PIN_SESSION_MAX_ACTIVE]
            for stale in overflow:
                removed = _pin_session_cache.pop(stale["session_id"], None)
                if removed is not None:
                    stale_entries.append(removed)
    for stale in stale_entries:
        _close_pin_session_entry(stale)

    return entry["session_id"], signer


def _firma_info_dict(intestatario: str, scadenza, *, pin_session_id: Optional[str] = None,
                     pin_session_cached: bool = False) -> dict:
    info = {
        "intestatario": intestatario or "",
        "scadenza": scadenza.strftime("%Y-%m-%d") if scadenza else "",
    }
    if pin_session_id:
        info.update({
            "pin_session_id": pin_session_id,
            "pin_session_cached": pin_session_cached,
            "pin_session_ttl_seconds": PIN_SESSION_TTL_SECONDS,
        })
    return info


def _prepare_documento_firma_visibile(
    documento: bytes,
    intestatario: str = "",
    issuer: str = "",
    serial: str = "",
    visible_signature_mode: str = "laterale",
    visible_signature_place: str = "",
    visible_signature_datetime_mode: str = "data_ora",
) -> bytes:
    try:
        from visible_signature import prepare_document_for_signature, resolve_visible_signature_place

        luogo = resolve_visible_signature_place(
            city=visible_signature_place or os.getenv("PCT_STUDIO_CITY", ""),
            province=os.getenv("PCT_STUDIO_PROVINCIA", ""),
            address=os.getenv("PCT_STUDIO_INDIRIZZO", ""),
        )

        return prepare_document_for_signature(
            documento,
            intestatario=intestatario,
            data_firma=datetime.now(UTC),
            luogo=luogo,
            issuer=issuer,
            serial=serial,
            mode=visible_signature_mode,
            datetime_mode=visible_signature_datetime_mode,
        )
    except Exception as exc:
        log.warning("Impossibile applicare la firma visibile locale: %s", exc)
        return documento


def _firma_documento_via_sessione(
    pin_session_id: str,
    documento: bytes,
    *,
    visible_signature_mode: str = "laterale",
    visible_signature_place: str = "",
    visible_signature_datetime_mode: str = "data_ora",
) -> tuple[bytes, dict]:
    entry = _get_pin_session(pin_session_id)
    if not entry:
        raise RuntimeError(
            "Sessione PIN scaduta o non disponibile. Inserisci di nuovo il PIN per riaprire il token."
        )

    signer = entry["signer"]
    try:
        try:
            firmato = signer.firma_cades(
                documento,
                detached=False,
                visible_signature_mode=visible_signature_mode,
                visible_signature_place=visible_signature_place,
                visible_signature_datetime_mode=visible_signature_datetime_mode,
            )
        except TypeError as exc:
            if "visible_signature_datetime_mode" not in str(exc):
                raise
            firmato = signer.firma_cades(
                documento,
                detached=False,
                visible_signature_mode=visible_signature_mode,
                visible_signature_place=visible_signature_place,
            )
        info = _firma_info_dict(
            getattr(signer, "intestatario", "") or "",
            getattr(signer, "scadenza", None),
            pin_session_id=pin_session_id,
            pin_session_cached=True,
        )
        return firmato, info
    except Exception:
        _drop_pin_session(pin_session_id)
        raise


def _firma_documento(lib_path: str, documento: bytes, pin: str,
                     slot_id: Optional[int] = None,
                     pin_session_id: Optional[str] = None,
                     visible_signature_mode: str = "laterale",
                     visible_signature_place: str = "",
                     visible_signature_datetime_mode: str = "data_ora") -> tuple[bytes, dict]:
    """
    Firma CAdES-BES il documento usando il token PKCS#11.

    Prova prima a importare pct.firma_pkcs11 (se l'utente è nella dir del progetto);
    altrimenti usa l'implementazione inline.

    Ritorna (firmato_bytes, info_dict).
    """
    requested_session_id = (pin_session_id or "").strip()
    if requested_session_id:
        return _firma_documento_via_sessione(
            requested_session_id,
            documento,
            visible_signature_mode=visible_signature_mode,
            visible_signature_place=visible_signature_place,
            visible_signature_datetime_mode=visible_signature_datetime_mode,
        )

    # Aggiungi la directory del progetto al path se possibile
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_dir not in sys.path:
        sys.path.insert(0, project_dir)

    try:
        session_id, firma = _create_pin_session(lib_path, pin, slot_id)
        try:
            try:
                firmato = firma.firma_cades(
                    documento,
                    detached=False,
                    visible_signature_mode=visible_signature_mode,
                    visible_signature_place=visible_signature_place,
                    visible_signature_datetime_mode=visible_signature_datetime_mode,
                )
            except TypeError as exc:
                if "visible_signature_datetime_mode" not in str(exc):
                    raise
                firmato = firma.firma_cades(
                    documento,
                    detached=False,
                    visible_signature_mode=visible_signature_mode,
                    visible_signature_place=visible_signature_place,
                )
        except Exception:
            _drop_pin_session(session_id)
            raise
        info = _firma_info_dict(
            firma.intestatario or "",
            firma.scadenza,
            pin_session_id=session_id,
            pin_session_cached=False,
        )
        return firmato, info
    except ImportError:
        pass

    # Implementazione inline (fallback senza pct/)
    return _firma_inline(
        lib_path,
        documento,
        pin,
        slot_id,
        visible_signature_mode=visible_signature_mode,
        visible_signature_place=visible_signature_place,
        visible_signature_datetime_mode=visible_signature_datetime_mode,
    )


def _firma_inline(lib_path: str, documento: bytes, pin: str,
                  slot_id: Optional[int] = None,
                  visible_signature_mode: str = "laterale",
                  visible_signature_place: str = "",
                  visible_signature_datetime_mode: str = "data_ora") -> tuple[bytes, dict]:
    """CAdES-BES minimale senza dipendere da pct.firma_pkcs11."""
    import pkcs11
    from pkcs11 import Attribute, Mechanism, ObjectClass

    lib_obj = pkcs11.lib(lib_path)
    slots = lib_obj.get_slots(token_present=True)
    if not slots:
        raise RuntimeError("Nessun token PKCS#11 inserito")

    slot = slots[int(slot_id) if slot_id is not None else 0]
    token = slot.get_token()

    with token.open(user_pin=pin) as session:
        privkeys = list(session.get_objects({Attribute.CLASS: ObjectClass.PRIVATE_KEY}))
        certs = list(session.get_objects({Attribute.CLASS: ObjectClass.CERTIFICATE}))
        if not privkeys:
            raise RuntimeError("Nessuna chiave privata nel token")
        if not certs:
            raise RuntimeError("Nessun certificato nel token")

        cert_der = bytes(certs[0][Attribute.VALUE])
        try:
            from cryptography import x509 as cx509
            from cryptography.hazmat.backends import default_backend

            cert_obj = cx509.load_der_x509_certificate(cert_der, default_backend())
            cn_list = cert_obj.subject.get_attributes_for_oid(cx509.NameOID.COMMON_NAME)
            intestatario = cn_list[0].value if cn_list else ""
            scadenza = _format_cert_not_valid_after(cert_obj)
            issuer_cn_list = cert_obj.issuer.get_attributes_for_oid(cx509.NameOID.COMMON_NAME)
            issuer = issuer_cn_list[0].value if issuer_cn_list else ""
            serial = format(getattr(cert_obj, "serial_number", 0), "X")
        except Exception:
            intestatario = ""
            scadenza = ""
            issuer = ""
            serial = ""

        documento = _prepare_documento_firma_visibile(
            documento,
            intestatario,
            issuer,
            serial,
            visible_signature_mode=visible_signature_mode,
            visible_signature_place=visible_signature_place,
            visible_signature_datetime_mode=visible_signature_datetime_mode,
        )
        signed_attrs_der = _build_signed_attrs_der_inline(documento)

        # Firma RSA-PKCS1v15-SHA256 in-device sui SignedAttributes CAdES.
        # python-pkcs11 espone la firma sul private key object, non sulla sessione.
        firma_bytes = bytes(privkeys[0].sign(
            signed_attrs_der, mechanism=Mechanism.SHA256_RSA_PKCS
        ))

        # CAdES-BES minimale usando il builder condiviso se disponibile
    try:
        from pct.firma_pkcs11 import _build_cades_bes
        firmato = _build_cades_bes(
            documento=documento,
            signature_bytes=firma_bytes,
            cert_der=cert_der,
            signed_attrs_der=signed_attrs_der,
            detached=False,
        )
    except ImportError:
        firmato = _build_cades_bes_inline(
            documento,
            firma_bytes,
            cert_der,
            signed_attrs_der=signed_attrs_der,
        )

    return firmato, {"intestatario": intestatario, "scadenza": scadenza}


def _build_signed_attrs_der_inline(documento: bytes) -> bytes:
    from asn1crypto import cms, core

    doc_digest = hashlib.sha256(documento).digest()
    signed_attrs = cms.CMSAttributes([
        cms.CMSAttribute({
            "type": cms.CMSAttributeType("content_type"),
            "values": cms.SetOfContentType([cms.ContentType("data")]),
        }),
        cms.CMSAttribute({
            "type": cms.CMSAttributeType("message_digest"),
            "values": cms.SetOfOctetString([core.OctetString(doc_digest)]),
        }),
    ])
    return signed_attrs.dump()


def _build_cades_bes_inline(
    documento: bytes,
    firma: bytes,
    cert_der: bytes,
    signed_attrs_der: Optional[bytes] = None,
) -> bytes:
    """
    Costruisce una busta CAdES-BES minimale (PKCS#7 SignedData).
    Usato solo se pct.firma_pkcs11 non è disponibile.
    """
    try:
        from asn1crypto import cms, algos, core, x509 as asn1_x509
    except ImportError as exc:
        raise RuntimeError(
            "Dipendenza mancante nel Local Signer: installare asn1crypto per costruire la firma CAdES."
        ) from exc

    try:
        cert_asn1 = asn1_x509.Certificate.load(cert_der)
        tbs = cert_asn1["tbs_certificate"]
        signed_attrs_der = signed_attrs_der or _build_signed_attrs_der_inline(documento)
        signed_attrs = cms.CMSAttributes.load(signed_attrs_der)

        signer_info = cms.SignerInfo({
            "version": "v1",
            "sid": cms.SignerIdentifier({
                "issuer_and_serial_number": cms.IssuerAndSerialNumber({
                    "issuer": tbs["issuer"],
                    "serial_number": tbs["serial_number"],
                }),
            }),
            "digest_algorithm": algos.DigestAlgorithm({"algorithm": "sha256"}),
            "signed_attrs": signed_attrs,
            "signature_algorithm": algos.SignedDigestAlgorithm({"algorithm": "sha256_rsa"}),
            "signature": core.OctetString(firma),
        })

        signed_data = cms.SignedData({
            "version": "v1",
            "digest_algorithms": cms.DigestAlgorithms([
                algos.DigestAlgorithm({"algorithm": "sha256"})
            ]),
            "encap_content_info": {
                "content_type": "data",
                "content": documento,
            },
            "certificates": cms.CertificateSet([
                cms.CertificateChoices(name="certificate", value=cert_asn1)
            ]),
            "signer_infos": cms.SignerInfos([signer_info]),
        })

        envelope = cms.ContentInfo({
            "content_type": "signed_data",
            "content": signed_data,
        })
        return envelope.dump()

    except Exception as exc:
        log.exception("_build_cades_bes_inline fallita")
        raise RuntimeError(
            "Impossibile costruire una busta CAdES valida nel Local Signer. "
            "Aggiorna il pacchetto Local Signer e riprova."
        ) from exc


# ── PST helpers ────────────────────────────────────────────────────────────────

_SOAP_NS = "http://schemas.xmlsoap.org/soap/envelope/"
_PST_BASE = (os.getenv("PCT_PST_BASE_URL", _PST_LEGACY_BASE) or _PST_LEGACY_BASE).strip()


def _pst_host(url: str) -> str:
    try:
        return urlparse(url).netloc or url
    except Exception:
        return url


def _pst_endpoint_configurato_e_legacy(url: Optional[str] = None) -> bool:
    candidate = (url or _PST_BASE).strip()
    env_base = os.getenv("PCT_PST_BASE_URL", "").strip()
    if url is None and not env_base and _supporto_auto_pst_disponibile() and candidate == _PST_BASE:
        return False
    return _pst_host(candidate).lower() == "wspa.giustizia.it"


def _messaggio_endpoint_pst_legacy() -> str:
    return (
        "L'endpoint PST predefinito di IUSENTRA punta ancora a wspa.giustizia.it, "
        "ma questo host al 29 marzo 2026 non risulta più pubblicato nel DNS pubblico.\n"
        "I proxy PST oggi documentati dal Ministero sono:\n"
        f"  - {_PST_PROXY_PDA_URL}\n"
        f"  - {_PST_PROXY_SH_URL}\n"
        "Con il registro uffici aggiornato IUSENTRA prova a comporre automaticamente "
        "il proxy corretto; se l'ufficio non ha metadati PST configurare "
        "PCT_PST_BASE_URL con l'URL completo del proxy fornito dal proprio PdA/software house.\n"
        "Verifica rapida:\n"
        f"  nslookup {_PST_PROXY_PDA_URL.replace('https://', '')} 8.8.8.8\n"
        f"  nslookup {_PST_PROXY_SH_URL.replace('https://', '')} 8.8.8.8"
    )


def _pst_servizio_proxy(base_url: str) -> str:
    return _normalizza_servizio_pst_name((base_url or "").rstrip("/").split("/")[-1])


def _pst_namespace_qbuilder(base_url: str) -> str:
    return _PST_QBUILDER_NAMESPACES.get(_pst_servizio_proxy(base_url), "")


def _pst_servizio_sigp(base_url: str) -> bool:
    return _pst_servizio_proxy(base_url) == "JPW_SIGP"


def _pst_servizio_siecic(base_url: str) -> bool:
    return _pst_servizio_proxy(base_url) == "JPW_SIECIC"


def _pst_servizio_sicid_family(base_url: str) -> bool:
    return _pst_servizio_proxy(base_url) in _PST_SICID_FAMILY_SERVIZI


def _pst_tipo_ricerca_qbuilder(base_url: str) -> str:
    servizio = _pst_servizio_proxy(base_url)
    return _PST_QBUILDER_TIPO_RICERCA.get(servizio, "RGN")


def _pst_subpro_sigp(sub_procedimento: str = "") -> str:
    return (sub_procedimento or "").strip()


def _sigp_info_fascicolo_url(
    *,
    codice_ufficio: str,
    numero_rg: str,
    anno_rg: int | str,
    cf_avvocato: str = "",
) -> str:
    params = {
        "ufficioRicerca": str(codice_ufficio or "").strip(),
        "ruoloRicerca": "AVV@AVV",
        "numero": str(numero_rg or "").strip(),
        "anno": str(anno_rg or "").strip(),
        "registroRicerca": "GDP",
    }
    cf_clean = _estrai_codice_fiscale_testo(cf_avvocato or "")
    if cf_clean:
        params["pa"] = f"[{cf_clean}]"
    return f"https://servizipst.giustizia.it/PST/it/sigp_infofascicolo.wp?{urlencode(params)}"


def _sigp_fascicolo_fallback(
    *,
    codice_ufficio: str,
    numero_rg: str,
    anno_rg: int | str,
    cf_avvocato: str = "",
    motivo: str = "",
) -> dict:
    ufficio = _risolvi_ufficio_da_snapshot(codice_ufficio)
    nome_ufficio = str((ufficio or {}).get("nome") or "").strip()
    return {
        "id_fascicolo": "",
        "numero_rg": str(numero_rg or "").strip(),
        "anno_rg": int(str(anno_rg or 0) or 0),
        "ruolo": "GDP",
        "stato": "DA VERIFICARE SUL PORTALE UFFICIALE",
        "oggetto": "Scheda SIGP disponibile nel portale ufficiale autenticato",
        "sezione": "",
        "giudice": "",
        "data_iscrizione": "",
        "data_udienza": "",
        "codice_ufficio": str(codice_ufficio or "").strip(),
        "nome_ufficio": nome_ufficio,
        "sub_procedimento": _pst_subpro_sigp(),
        "parti": [],
        "parti_dettaglio": [],
        "registro_portale": "GDP",
        "canale_telematico": "PST/SIGP",
        "portale_url": _sigp_info_fascicolo_url(
            codice_ufficio=codice_ufficio,
            numero_rg=str(numero_rg or "").strip(),
            anno_rg=anno_rg,
            cf_avvocato=cf_avvocato,
        ),
        "verifica_browser_ufficiale": True,
        "sincronizzazione_autorizzata": "richiede_servizio_pst_pda_o_model_office",
        "download_autonomo": False,
        "adapter_richiesto": "PST/SIGP web service autorizzato o Punto di Accesso",
        "messaggio_operativo": (
            "Il fascicolo e' su SIGP/Giudice di Pace. Se il web service non "
            "espone la scheda completa, IUSENTRA non effettua scraping HTML del "
            "portale. Apri la scheda ufficiale nel browser autenticato oppure usa "
            "un adapter PST/PdA autorizzato o Model Office per la sincronizzazione."
        ),
        "motivo_fallback": motivo,
    }


def _pst_usa_qbuilder(base_url: str) -> bool:
    return bool(_pst_namespace_qbuilder(base_url))


def _pst_http_endpoint_base_url(base_url: str) -> str:
    raw = (base_url or "").strip().rstrip("/")
    if not raw:
        return ""
    servizio_logico = _pst_servizio_proxy(raw)
    servizio_http = _PST_QBUILDER_HTTP_ENDPOINT_SERVIZI.get(servizio_logico, servizio_logico)
    if not servizio_http or servizio_http == servizio_logico:
        return raw
    return _pst_base_url_con_servizio(raw, servizio_http) or raw


def _pst_url_ricerca(base_url: str) -> str:
    http_base_url = _pst_http_endpoint_base_url(base_url)
    if _pst_usa_qbuilder(base_url):
        return http_base_url.rstrip("/")
    return f"{http_base_url.rstrip('/')}/RicercaFascicoliRegistroService"


def _pst_url_documenti(base_url: str) -> str:
    http_base_url = _pst_http_endpoint_base_url(base_url)
    if _pst_usa_qbuilder(base_url):
        return http_base_url.rstrip("/")
    return f"{http_base_url.rstrip('/')}/ConsultazioneAvanzataDocumentiService"


def _pst_registro_da_base_url(base_url: str) -> str:
    raw = (base_url or "").strip()
    if not raw:
        return ""
    marker = "/pda/pycons/"
    if marker not in raw:
        return ""
    tail = raw.split(marker, 1)[1]
    return tail.split("/", 1)[0].strip()


def _pst_registro_documenti_sicid(base_url: str) -> str:
    return _pst_servizio_proxy(base_url) or _pst_registro_da_base_url(base_url)


def _pst_tabella_ministeriale_policy(base_url: str) -> dict:
    servizio = _pst_servizio_proxy(base_url)
    policy = dict(_PST_TABELLE_MINISTERIALI_POLICY.get(servizio or "", {}))
    if policy:
        policy.setdefault("servizio", servizio)
        return policy
    return {
        "servizio": servizio,
        "tabella": servizio or "PST",
        "registro": servizio or _pst_registro_da_base_url(base_url),
        "download": "",
        "warmup": "",
        "errore_lotto": "per_documento",
        "x_wasp_user": bool(_pst_namespace_qbuilder(base_url)),
    }


def _risolvi_codice_ufficio_pst(codice_o_nome: str) -> str:
    if _risolvi_codice_ministero_hacs is not None:
        return _risolvi_codice_ministero_hacs(codice_o_nome)
    ufficio = _risolvi_ufficio_da_snapshot(codice_o_nome)
    if ufficio:
        return str(ufficio.get("codice_ministero") or ufficio.get("codice") or codice_o_nome).strip()
    return (codice_o_nome or "").strip()


def _risolvi_base_pst_runtime(codice_o_nome: str) -> str:
    if _risolvi_base_pst_hacs is not None:
        return _risolvi_base_pst_hacs(codice_o_nome, base_url=_PST_BASE)
    if _carica_snapshot_uffici():
        return _risolvi_base_pst_da_snapshot(codice_o_nome)
    if _pst_endpoint_configurato_e_legacy():
        raise RuntimeError(_messaggio_endpoint_pst_legacy())
    return _PST_BASE


def _pst_base_diagnostico() -> str:
    env_base = os.getenv("PCT_PST_BASE_URL", "").strip()
    if env_base:
        return env_base
    if _supporto_auto_pst_disponibile():
        return "AUTO (da registro uffici locale)"
    return _PST_BASE


def _pst_base_monitoraggio() -> str:
    env_base = os.getenv("PCT_PST_BASE_URL", "").strip()
    if env_base:
        return env_base
    if _supporto_auto_pst_disponibile():
        return _PST_PROXY_SH_URL
    return _PST_BASE


def _windows_hidden_subprocess_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
    if sys.platform != "win32":
        return kwargs

    hidden_kwargs = dict(kwargs)
    no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    if no_window:
        hidden_kwargs["creationflags"] = int(hidden_kwargs.get("creationflags") or 0) | int(no_window)

    startupinfo = hidden_kwargs.get("startupinfo")
    startupinfo_factory = getattr(subprocess, "STARTUPINFO", None)
    if startupinfo is None and startupinfo_factory is not None:
        try:
            startupinfo = startupinfo_factory()
            hidden_kwargs["startupinfo"] = startupinfo
        except Exception:
            startupinfo = None

    if startupinfo is not None:
        try:
            startupinfo.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 0)
            startupinfo.wShowWindow = getattr(subprocess, "SW_HIDE", 0)
        except Exception:
            pass

    return hidden_kwargs


def _curl_disponibile() -> bool:
    """Verifica che curl sia disponibile nel PATH."""
    try:
        run_kwargs = _windows_hidden_subprocess_kwargs({"capture_output": True, "timeout": 5})
        r = subprocess.run([_curl_command(), "--version"], **run_kwargs)
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


# Mappa codici di uscita curl → messaggi operativi in italiano
_CURL_EXIT_CODES = {
    1:  "Protocollo non supportato da curl.",
    2:  "Errore di inizializzazione curl.",
    3:  "URL malformata.",
    5:  "Impossibile risolvere il proxy.",
    6:  (
        "Impossibile risolvere il nome host {host} (errore DNS).\n"
        "Verificare la connessione internet e il DNS configurato.\n"
        "Se il problema persiste: aprire il prompt dei comandi e digitare\n"
        "  nslookup {host} 8.8.8.8"
    ),
    7:  (
        "Connessione rifiutata da {host}.\n"
        "Il server PST potrebbe essere temporaneamente non disponibile."
    ),
    28: (
        "Timeout connessione a {host} ({timeout}s).\n"
        "Il servizio PST potrebbe essere sovraccarico. Riprovare tra qualche minuto."
    ),
    35: (
        "Errore SSL/TLS durante la connessione a {host}.\n"
        "Verificare che il certificato della smart card/token sia valido e non scaduto."
    ),
    58: (
        "Problema con il certificato client locale.\n"
        "Verificare che il certificato del dispositivo sia correttamente selezionato."
    ),
    60: (
        "La connessione sicura al PST non e' stata accettata dalla postazione locale.\n"
        "Il Local Signer usa automaticamente il canale Windows corretto; riprova dopo "
        "aver riavviato Local Signer e il browser. Se resta, verificare proxy/antivirus "
        "o certificati del Ministero installati sul PC."
    ),
    77: (
        "Permesso negato alla lettura del certificato.\n"
        "Eseguire il Local Signer come amministratore o verificare i permessi."
    ),
}


def _looks_like_dns_resolution_error(text: str) -> bool:
    value = str(text or "").strip().lower()
    if not value:
        return False
    markers = (
        "failed to resolve",
        "name resolution",
        "name or service not known",
        "getaddrinfo failed",
        "could not resolve host",
        "temporary failure in name resolution",
        "max retries exceeded",
    )
    return any(marker in value for marker in markers)


def _looks_like_http_forbidden_error(text: str) -> bool:
    value = str(text or "").strip().lower()
    if not value:
        return False
    markers = (
        "403 client error",
        "403 forbidden",
        "forbidden for url",
        "http 403",
    )
    return any(marker in value for marker in markers)


def _messaggio_dns_endpoint_portale(url: str) -> str:
    host = _pst_host(url)
    if "appweb.giustizia.it" in host:
        return (
            "Il PC non riesce a risolvere appweb.giustizia.it (PDP Penale).\n"
            "Verificare DNS, proxy, firewall o VPN e aprire prima il portale ufficiale nel browser.\n"
            "Se il Ministero o l'ufficio hanno comunicato un endpoint aggiornato, impostare PCT_PDP_BASE_URL."
        )
    if "pac.giustizia-amministrativa.it" in host:
        return (
            "Il PC non riesce a risolvere pac.giustizia-amministrativa.it (PAT).\n"
            "Verificare accesso e DNS del Portale Avvocato ufficiale https://www.giustizia-amministrativa.it/portale-avvocato.\n"
            "Se l'endpoint servizi e' stato aggiornato, impostare PCT_PAT_BASE_URL."
        )
    if "www.ptt.mef.gov.it" in host:
        return (
            "Il PC sta ancora puntando al vecchio host PTT www.ptt.mef.gov.it, non piu' usato da IUSENTRA.\n"
            "Aggiornare o reinstallare il Local Signer piu' recente: il default corretto e' https://sigit.finanze.it/ptt.\n"
            "In alternativa impostare esplicitamente PCT_SIGIT_BASE_URL."
        )
    if "sigit.finanze.it" in host:
        return (
            "Il PC non riesce a risolvere sigit.finanze.it (PTT / SIGIT).\n"
            "Verificare DNS, proxy, firewall o VPN e l'accesso al portale SIGIT dal browser.\n"
            "Se necessario, impostare un endpoint diverso tramite PCT_SIGIT_BASE_URL."
        )
    host_label = host or "l'host richiesto"
    return (
        f"Il PC non riesce a risolvere {host_label}.\n"
        "Verificare DNS, proxy, firewall o VPN e riprovare."
    )


def _portale_browser_url(portale: str) -> str:
    portale_norm = str(portale or "").strip().lower()
    if portale_norm == "pdp":
        return _PDP_OFFICIAL_BROWSER_URL
    if portale_norm == "pat":
        return "https://www.giustizia-amministrativa.it/portale-avvocato"
    if portale_norm == "ptt":
        return "https://sigit.giustiziatributaria.gov.it/Sigit/index.do"
    return ""


def _portale_wsdl_diretto_abilitato(portale: str) -> bool:
    portale_norm = str(portale or "").strip().lower()
    if portale_norm not in {"pdp", "pat", "ptt"}:
        return True
    if _env_flag_enabled("HACS_SIGNER_FORCE_BROWSER_ASSIST") or _env_flag_enabled("PCT_FORCE_BROWSER_ASSIST"):
        return False
    return not (
        _env_flag_enabled("HACS_SIGNER_DISABLE_PORTALI_WSDL")
        or _env_flag_enabled("PCT_DISABLE_PORTALI_WSDL")
        or _env_flag_enabled(f"HACS_SIGNER_DISABLE_{portale_norm.upper()}_WSDL")
        or _env_flag_enabled(f"PCT_DISABLE_{portale_norm.upper()}_WSDL")
    )


def _portale_browser_assist_payload(portale: str, phase: str) -> dict[str, Any]:
    portale_norm = str(portale or "").strip().lower()
    phase_norm = str(phase or "").strip().lower() or "ricerca"
    phase_label = "ricerca fascicolo" if phase_norm == "ricerca" else "catalogo documenti"
    if portale_norm == "pdp":
        errore = (
            "Consultazione via browser ufficiale: per PDP la "
            f"{phase_label} viene completata dal Portale Deposito atti Penali nel browser. "
            "IUSENTRA puo' proseguire con l'acquisizione assistita."
        )
    elif portale_norm == "pat":
        errore = (
            "Consultazione via browser ufficiale: per PAT la "
            f"{phase_label} viene completata dal Portale Avvocato nel browser. "
            "IUSENTRA puo' proseguire con l'acquisizione assistita."
        )
    else:
        errore = (
            "Consultazione via browser ufficiale: per PTT/SIGIT il "
            f"{phase_label} viene completato nel browser ufficiale. "
            "IUSENTRA puo' proseguire con l'acquisizione assistita."
        )
    return {
        "ok": False,
        "errore": errore,
        "manual_required": True,
        "manual_phase": phase_norm,
        "manual_title": "Consultazione via browser ufficiale",
        "manual_reason": (
            f"Local Signer {VERSION} sta usando la modalita browser-assistita per {portale_norm.upper()}. "
            "Il portale ufficiale resta la fonte per consultazione e documenti."
        ),
        "portale_url": _portale_browser_url(portale),
    }


_PORTAL_ASSISTANT_ALLOWED_EXTENSIONS = {".zip", ".pdf", ".p7m", ".xml", ".json", ".eml", ".msg", ".txt", ".html", ".htm"}
_portal_assistant_lock = threading.Lock()
_portal_assistant_sessions: dict[str, dict[str, Any]] = {}


def _portal_assistant_base_dir() -> Path:
    base = Path(os.getenv("HACS_SIGNER_PORTAL_ASSISTANT_DIR") or Path(tempfile.gettempdir()) / "iusentra_portal_assistant")
    base.mkdir(parents=True, exist_ok=True)
    return base


def _portal_assistant_public(session: dict[str, Any]) -> dict[str, Any]:
    return {
        "session_id": session.get("session_id", ""),
        "portale": session.get("portale", ""),
        "official_url": session.get("official_url", ""),
        "status": session.get("status", ""),
        "fascicolo_id": session.get("fascicolo_id", ""),
        "deposito_id": session.get("deposito_id", ""),
        "purpose": session.get("purpose", "acquisizione"),
        "downloads_dir": session.get("downloads_dir", ""),
        "files": list(session.get("files") or []),
        "message": session.get("message", ""),
    }


def _portal_assistant_get(session_id: str) -> dict[str, Any]:
    key = str(session_id or "").strip()
    with _portal_assistant_lock:
        session = _portal_assistant_sessions.get(key)
        if not session:
            raise RuntimeError("Sessione assistita non trovata.")
        return dict(session)


def _portal_assistant_save(session: dict[str, Any]) -> dict[str, Any]:
    session["updated_at"] = datetime.now(UTC).isoformat()
    with _portal_assistant_lock:
        _portal_assistant_sessions[str(session["session_id"])] = dict(session)
    return session


def _portal_assistant_start_local(data: dict[str, Any]) -> dict[str, Any]:
    portale = str(data.get("portale") or "").strip().lower()
    if portale not in {"ptt", "pat", "pdp"}:
        raise RuntimeError("Portale non supportato per la sessione assistita.")
    session_id = str(data.get("session_id") or secrets.token_urlsafe(18)).strip()
    session_dir = _portal_assistant_base_dir() / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    session = {
        "session_id": session_id,
        "portale": portale,
        "official_url": str(data.get("official_url") or _portale_browser_url(portale)).strip(),
        "fascicolo_id": str(data.get("fascicolo_id") or "").strip(),
        "deposito_id": str(data.get("deposito_id") or "").strip(),
        "purpose": str(data.get("purpose") or "acquisizione").strip() or "acquisizione",
        "status": "sessione_assistita_pronta",
        "downloads_dir": str(session_dir),
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
        "files": [],
        "message": "Sessione assistita locale pronta.",
    }
    _portal_assistant_save(session)
    return _portal_assistant_public(session)


def _portal_assistant_download_roots(session: dict[str, Any]) -> list[Path]:
    roots: list[Path] = []
    for raw in [
        session.get("downloads_dir", ""),
        os.getenv("HACS_SIGNER_DOWNLOADS_DIR", ""),
        str(Path.home() / "Downloads"),
        str(Path(os.environ.get("USERPROFILE", "")) / "Downloads") if os.environ.get("USERPROFILE") else "",
        str(Path(os.environ.get("OneDrive", "")) / "Downloads") if os.environ.get("OneDrive") else "",
    ]:
        text = str(raw or "").strip()
        if not text:
            continue
        path = Path(text).expanduser()
        if path.exists() and path.is_dir() and path not in roots:
            roots.append(path)
    return roots


def _portal_assistant_manifest_for_file(path: Path, *, max_inline_bytes: int = 8 * 1024 * 1024) -> dict[str, Any] | None:
    if not path.is_file() or path.suffix.lower() not in _PORTAL_ASSISTANT_ALLOWED_EXTENSIONS:
        return None
    if path.name.lower() in {".ds_store", "thumbs.db"} or path.suffix.lower() in {".crdownload", ".part", ".tmp"}:
        return None
    try:
        payload = path.read_bytes()
        stat = path.stat()
    except OSError:
        return None
    if not payload:
        return None
    row = {
        "filename": path.name,
        "size": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "detected_at": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
        "local_temp_ref": str(path),
    }
    if len(payload) <= max_inline_bytes:
        row["content_base64"] = base64.b64encode(payload).decode("ascii")
    return row


def _portal_assistant_collect_local(session_id: str, *, limit: int = 50, max_age_hours: int = 24) -> dict[str, Any]:
    session = _portal_assistant_get(session_id)
    created_at = session.get("created_at")
    if isinstance(created_at, datetime):
        cutoff = created_at - timedelta(minutes=5)
    else:
        cutoff = datetime.now(UTC) - timedelta(hours=max(1, int(max_age_hours or 24)))
    files: list[dict[str, Any]] = []
    seen: set[str] = set()
    for root in _portal_assistant_download_roots(session):
        for path in root.rglob("*"):
            if len(files) >= limit:
                break
            try:
                modified_at = datetime.fromtimestamp(path.stat().st_mtime, UTC)
            except OSError:
                continue
            if modified_at < cutoff:
                continue
            row = _portal_assistant_manifest_for_file(path)
            if not row or row["sha256"] in seen:
                continue
            seen.add(row["sha256"])
            files.append(row)
    session["files"] = files
    session["status"] = "file_ufficiali_raccolti" if files else session.get("status") or "sessione_assistita_pronta"
    session["message"] = "File ufficiali raccolti." if files else "Nessun file recente compatibile trovato."
    _portal_assistant_save(session)
    return _portal_assistant_public(session)


def _messaggio_endpoint_browser_guidato(portale: str, error: Exception | str) -> str:
    text = str(error or "").strip()
    portale_norm = str(portale or "").strip().lower()
    if portale_norm == "pdp":
        return (
            "Consultazione via browser ufficiale: apri il Portale Deposito atti Penali e usa l'inserimento manuale assistito di IUSENTRA.\n"
            f"Dettaglio tecnico: {text}"
        )
    if portale_norm == "pat":
        return (
            "Consultazione via browser ufficiale: apri la pagina ufficiale del Processo Amministrativo Telematico e accedi al Portale Avvocato, poi usa l'inserimento manuale assistito di IUSENTRA.\n"
            f"Dettaglio tecnico: {text}"
        )
    return (
        "Consultazione via browser ufficiale: apri la pagina ufficiale del Processo Tributario Telematico (PTT/SIGIT) e prosegui con l'inserimento manuale assistito di IUSENTRA.\n"
        f"Dettaglio tecnico: {text}"
    )


def _portale_manual_required_payload(portale: str, error: Exception | str, phase: str) -> dict[str, Any] | None:
    text = str(error or "").strip()
    if not text:
        return None
    if not (_looks_like_dns_resolution_error(text) or _looks_like_http_forbidden_error(text)):
        return None
    phase_norm = str(phase or "").strip().lower() or "ricerca"
    return {
        "ok": False,
        "errore": _messaggio_endpoint_browser_guidato(portale, text),
        "manual_required": True,
        "manual_phase": phase_norm,
        "manual_title": "Consultazione via browser ufficiale",
        "manual_reason": (
            "Il canale WSDL diretto non e' disponibile su questo PC. "
            "IUSENTRA puo' comunque proseguire con l'acquisizione assistita manuale."
        ),
        "portale_url": _portale_browser_url(portale),
    }


def _curl_errore_leggibile(
    returncode: int,
    stderr: str,
    url: str = "",
    timeout_sec: int = 30,
) -> str:
    """
    Traduce un returncode curl in un messaggio operativo.
    Estrae il nome host dall'URL per messaggi più contestuali.
    """
    host = _pst_host(url)

    if returncode == 6 and _pst_endpoint_configurato_e_legacy(url):
        return _messaggio_endpoint_pst_legacy()

    if returncode == 6:
        return _messaggio_dns_endpoint_portale(url)

    template = _CURL_EXIT_CODES.get(returncode)
    if template:
        msg = template.format(host=host, timeout=timeout_sec)
    else:
        # Messaggio generico con stderr
        stderr_breve = (stderr or "").strip()[:200]
        msg = f"curl uscito con codice {returncode}: {stderr_breve}"

    return msg


def _hint_pin_windows() -> str:
    return (
        "Se Windows mostra la finestra del dispositivo, inserire adesso il PIN "
        "della smart card o del token CNS/CIE e confermare."
    )


def _messaggio_timeout_preflight_non_bloccante(host: str) -> str:
    return (
        f"Il controllo preliminare del certificato verso {host} ha impiegato troppo tempo.\n"
        "Questo controllo serve solo ad anticipare la richiesta PIN e non blocca la ricerca reale.\n"
        f"{_hint_pin_windows()}\n"
        "Proseguo comunque con la chiamata PST effettiva."
    )


def _pst_cookie_retry_requires_cert(error: Exception) -> bool:
    """
    Decide se un errore emerso in modalita' cookie-only giustifica il retry
    col certificato client.

    Retry SI: segnali di sessione/certificato non accettato dal PST.
    Retry NO: timeout, DNS, host down, 5xx temporanei e simili, per evitare
    un secondo prompt PIN inutile quando il problema non e' l'autenticazione.
    """
    text = str(error or "").strip().lower()
    if not text:
        return False

    no_retry_markers = [
        "timeout connessione",
        "curl uscito con codice 28",
        "servizio pst potrebbe essere sovraccarico",
        "errore dns",
        "impossibile risolvere il nome host",
        "connessione rifiutata",
        "errore interno o temporaneo",
        "http 404",
        "http 500",
        "http 502",
        "http 503",
        "http 504",
    ]
    if any(marker in text for marker in no_retry_markers):
        return False

    retry_markers = [
        "http 401",
        "unauthorized",
        "http 403",
        "forbidden",
        "certificato cns/cie selezionato non",
        "certificato client",
        "sessione accesso pst scaduta",
        "riaprire il canale autenticato",
        "soap fault",
        "pagina html anzich",
        "accesso al servizio è stato negato",
        "accesso al servizio e' stato negato",
    ]
    return any(marker in text for marker in retry_markers)


def _pst_auth_failure_requires_fresh_session(error: Any) -> bool:
    text = str(error or "").strip().lower()
    if not text:
        return False
    markers = (
        "autenticazione pst non riuscita",
        "http 401",
        "unauthorized",
        "certificato cns/cie",
        "pin non",
        "pin della smart card",
        "certificato client",
    )
    return any(marker in text for marker in markers)


def _format_windows_cert_spec(cert_thumbprint: Optional[str]) -> str:
    """
    Formatta il certificato client per curl+Schannel.

    curl su Windows richiede la path dello store:
      CurrentUser\\MY\\<thumbprint>
    """
    thumbprint = (cert_thumbprint or "").strip().replace(" ", "")
    if not thumbprint:
        return ""
    if "\\" in thumbprint or "/" in thumbprint:
        return thumbprint
    return f"CurrentUser\\MY\\{thumbprint}"


def _curl_command() -> str:
    configured = os.getenv("HACS_SIGNER_CURL_PATH", "").strip()
    if configured:
        return configured
    if sys.platform == "win32":
        system_root = os.getenv("SystemRoot", r"C:\Windows").strip() or r"C:\Windows"
        system_curl = Path(system_root) / "System32" / "curl.exe"
        if system_curl.exists():
            return str(system_curl)
    return "curl"


def _curl_config_escape(value: str) -> str:
    """
    Escape minimo per i valori quotati nel file config di curl (-K).

    La sintassi del config file interpreta il backslash come escape anche
    dentro le stringhe quotate: per riferimenti come
    CurrentUser\\MY\\<thumbprint> dobbiamo quindi raddoppiare i backslash,
    altrimenti curl/schannel perde il path dello store certificati Windows.
    """
    text = str(value or "")
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _curl_windows_ssl_revoke_args() -> list[str]:
    return ["--ssl-no-revoke"] if sys.platform == "win32" else []


def _curl_windows_ssl_revoke_config_lines() -> list[str]:
    return ["ssl-no-revoke"] if sys.platform == "win32" else []


_WINDOWS_PIN_FOREGROUND_KEYWORDS = (
    "autenticazione",
    "accesso",
    "autorizzazione",
    "autorizza",
    "carta nazionale",
    "certificate",
    "certificato",
    "chiave privata",
    "credenziali",
    "credential",
    "credentialui",
    "dispositivo di sicurezza",
    "identita",
    "identità",
    "immettere il pin",
    "immetti il pin",
    "inserire il pin",
    "inserisci il pin",
    "lettore",
    "password",
    "pin",
    "private key",
    "richiesta pin",
    "sicurezza windows",
    "sicurezza di windows",
    "sicurezza",
    "windows security",
    "microsoft smart card",
    "smart card",
    "smartcard",
    "carta intelligente",
    "firma digitale",
    "cns",
    "cie",
    "bit4id",
    "aruba",
    "arubapec",
    "minva",
    "token",
)


_WINDOWS_PIN_FOREGROUND_CLASS_KEYWORDS = (
    "credential",
    "credential dialog xaml host",
    "smartcard",
    "cryptui",
    "bit4",
    "aruba",
)


_WINDOWS_PIN_FOREGROUND_PROCESS_KEYWORDS = (
    "credentialuibroker",
    "credential",
    "cryptui",
    "certenroll",
    "bit4",
    "aruba",
    "arubapec",
    "minva",
    "akutility",
    "smartcard",
    "carta",
    "cieid",
    "cns",
)


def _windows_pin_prompt_candidate_score(
    title: str,
    class_name: str = "",
    child_text: str = "",
    process_name: str = "",
) -> int:
    title_norm = (title or "").casefold()
    class_norm = (class_name or "").casefold()
    child_norm = (child_text or "").casefold()
    process_norm = (process_name or "").casefold()
    score = 0
    if title_norm and any(keyword in title_norm for keyword in _WINDOWS_PIN_FOREGROUND_KEYWORDS):
        score += 8
    if child_norm and any(keyword in child_norm for keyword in _WINDOWS_PIN_FOREGROUND_KEYWORDS):
        score += 6
    if class_norm and any(keyword in class_norm for keyword in _WINDOWS_PIN_FOREGROUND_CLASS_KEYWORDS):
        score += 5
    if process_norm and any(keyword in process_norm for keyword in _WINDOWS_PIN_FOREGROUND_PROCESS_KEYWORDS):
        score += 7
    if class_norm in {"applicationframewindow", "windows.ui.core.corewindow", "nativehwndhost"} and score:
        score += 2
    if class_norm == "#32770" and score:
        score += 1
    return score


def _windows_force_foreground_window(user32: Any, hwnd: Any) -> bool:
    """
    Best-effort robusto per finestre PIN Windows: restore, topmost temporaneo
    e attach del thread aiutano quando il dialog resta solo sulla taskbar.
    """
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        sw_show = 5
        sw_restore = 9
        hwnd_topmost = -1
        hwnd_notopmost = -2
        swp_nomove = 0x0002
        swp_nosize = 0x0001
        swp_showwindow = 0x0040
        swp_noownerzorder = 0x0200
        swp_nosendchanging = 0x0400
        swp_flags = swp_nomove | swp_nosize | swp_showwindow | swp_noownerzorder | swp_nosendchanging

        allow_set_foreground = getattr(user32, "AllowSetForegroundWindow", None)
        if allow_set_foreground:
            try:
                allow_set_foreground(-1)
            except Exception:
                pass

        current_thread = kernel32.GetCurrentThreadId()
        target_thread = user32.GetWindowThreadProcessId(hwnd, None)
        foreground_hwnd = user32.GetForegroundWindow()
        foreground_thread = user32.GetWindowThreadProcessId(foreground_hwnd, None) if foreground_hwnd else 0
        attached_threads: list[Any] = []
        attach_thread_input = getattr(user32, "AttachThreadInput", None)
        if attach_thread_input:
            for thread_id in {target_thread, foreground_thread}:
                if thread_id and thread_id != current_thread:
                    try:
                        if attach_thread_input(current_thread, thread_id, True):
                            attached_threads.append(thread_id)
                    except Exception:
                        continue

        try:
            if user32.IsIconic(hwnd):
                user32.ShowWindow(hwnd, sw_restore)
            else:
                user32.ShowWindow(hwnd, sw_show)
            show_window_async = getattr(user32, "ShowWindowAsync", None)
            if show_window_async:
                show_window_async(hwnd, sw_restore)

            set_window_pos = getattr(user32, "SetWindowPos", None)
            if set_window_pos:
                set_window_pos(hwnd, hwnd_topmost, 0, 0, 0, 0, swp_flags)
                time.sleep(0.08)

            user32.BringWindowToTop(hwnd)
            foreground_ok = bool(user32.SetForegroundWindow(hwnd))
            if not foreground_ok:
                user32.ShowWindow(hwnd, sw_restore)
                user32.BringWindowToTop(hwnd)
                foreground_ok = bool(user32.SetForegroundWindow(hwnd))
            try:
                user32.SetActiveWindow(hwnd)
                user32.SetFocus(hwnd)
            except Exception:
                pass

            switch_to_this_window = getattr(user32, "SwitchToThisWindow", None)
            if switch_to_this_window:
                switch_to_this_window(hwnd, True)

            if not foreground_ok:
                flash_window = getattr(user32, "FlashWindow", None)
                if flash_window:
                    try:
                        flash_window(hwnd, True)
                    except Exception:
                        pass
                # Windows a volte rifiuta SetForegroundWindow ma mostra comunque
                # il dialog se resta topmost per qualche istante.
                time.sleep(0.45)
                try:
                    foreground_ok = bool(user32.GetForegroundWindow() == hwnd)
                except Exception:
                    pass

            if set_window_pos:
                set_window_pos(hwnd, hwnd_notopmost, 0, 0, 0, 0, swp_flags)
            return foreground_ok
        finally:
            if attach_thread_input:
                for thread_id in attached_threads:
                    try:
                        attach_thread_input(current_thread, thread_id, False)
                    except Exception:
                        pass
    except Exception as exc:
        log.debug("Foreground PIN non applicabile alla finestra: %s", exc)
        return False


def _windows_try_foreground_pin_prompt_once() -> bool:
    """
    Best-effort: durante il TLS client-auth di curl, alcune dialog Windows
    per il PIN restano minimizzate o dietro al browser. Se ne troviamo una
    con titolo, classe o testo figlio coerente, la ripristiniamo e proviamo a
    portarla davanti.
    """
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        EnumChildWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        matched: list[tuple[int, Any]] = []

        def _window_text(hwnd: Any) -> str:
            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return ""
            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            return (buffer.value or "").strip()

        def _class_name(hwnd: Any) -> str:
            buffer = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, buffer, len(buffer))
            return (buffer.value or "").strip()

        def _process_name(hwnd: Any) -> str:
            pid = wintypes.DWORD()
            try:
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            except Exception:
                return ""
            if not pid.value:
                return ""
            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            open_process = getattr(kernel32, "OpenProcess", None)
            query_image = getattr(kernel32, "QueryFullProcessImageNameW", None)
            close_handle = getattr(kernel32, "CloseHandle", None)
            if not (open_process and query_image and close_handle):
                return ""
            handle = open_process(0x1000, False, pid.value)
            if not handle:
                return ""
            try:
                buffer = ctypes.create_unicode_buffer(1024)
                size = wintypes.DWORD(len(buffer))
                if query_image(handle, 0, buffer, ctypes.byref(size)):
                    return (buffer.value or "").strip()
            finally:
                try:
                    close_handle(handle)
                except Exception:
                    pass
            return ""

        def _child_text(hwnd: Any) -> str:
            parts: list[str] = []

            @EnumChildWindowsProc
            def _enum_child(child_hwnd, _child_lparam):
                text = _window_text(child_hwnd)
                if text:
                    parts.append(text)
                return len(parts) < 24

            user32.EnumChildWindows(hwnd, _enum_child, 0)
            return " ".join(parts)

        @EnumWindowsProc
        def _enum_window(hwnd, _lparam):
            if not user32.IsWindowVisible(hwnd) and not user32.IsIconic(hwnd):
                return True
            title = _window_text(hwnd)
            class_name = _class_name(hwnd)
            process_name = _process_name(hwnd)
            child_text = ""
            score = _windows_pin_prompt_candidate_score(title, class_name, child_text, process_name)
            if not score:
                child_text = _child_text(hwnd)
                score = _windows_pin_prompt_candidate_score(title, class_name, child_text, process_name)
            if score:
                matched.append((score, hwnd))
            return True

        user32.EnumWindows(_enum_window, 0)
        if not matched:
            return False

        matched.sort(key=lambda item: item[0], reverse=True)
        for _score, hwnd in matched[:3]:
            if _windows_force_foreground_window(user32, hwnd):
                return True
        return True
    except Exception as exc:
        log.debug("Helper foreground PIN non disponibile: %s", exc)
        return False


def _windows_pin_prompt_foreground_pump(stop_event: threading.Event, deadline_seconds: float) -> None:
    deadline = time.monotonic() + max(1.0, min(float(deadline_seconds or 1), 180.0))
    while not stop_event.is_set() and time.monotonic() < deadline:
        found = _windows_try_foreground_pin_prompt_once()
        stop_event.wait(0.22 if found else 0.25)


def _run_curl_with_pin_foreground(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess:
    run_kwargs = _windows_hidden_subprocess_kwargs(kwargs)
    if sys.platform != "win32":
        return subprocess.run(cmd, **run_kwargs)

    try:
        pump_seconds = float(run_kwargs.get("timeout") or PST_SOAP_MAX_TIME + 10)
    except (TypeError, ValueError):
        pump_seconds = float(PST_SOAP_MAX_TIME + 10)

    stop_event = threading.Event()
    worker = threading.Thread(
        target=_windows_pin_prompt_foreground_pump,
        args=(stop_event, pump_seconds),
        name="iusentra-pin-foreground",
        daemon=True,
    )
    worker.start()
    try:
        return subprocess.run(cmd, **run_kwargs)
    finally:
        stop_event.set()
        worker.join(timeout=0.5)


def _http_status_from_headers(header_text: str) -> Optional[int]:
    status = None
    for raw_line in (header_text or "").splitlines():
        line = raw_line.strip()
        if not line.startswith("HTTP/"):
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[1].isdigit():
            status = int(parts[1])
    return status


def _http_header_value(header_text: str, name: str) -> str:
    current_block: dict[str, str] = {}
    wanted = name.lower()
    for raw_line in (header_text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("HTTP/"):
            current_block = {}
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        current_block[key.strip().lower()] = value.strip()
    return current_block.get(wanted, "")


def _http_headers_dict(header_text: str) -> dict[str, str]:
    current_block: dict[str, str] = {}
    for raw_line in (header_text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("HTTP/"):
            current_block = {}
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        current_block[key.strip()] = value.strip()
    return current_block


def _body_preview(body: str, limit: int = 240) -> str:
    clean = " ".join((body or "").split())
    return clean[:limit]


def _normalizza_nome_download_match(nome: str) -> str:
    testo = Path(str(nome or "")).name.strip().lower()
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


def _score_download_match(file_key: str, expected_key: str) -> int:
    if not file_key or not expected_key:
        return 0
    if file_key == expected_key:
        return 100
    if len(file_key) >= 10 and len(expected_key) >= 10:
        if file_key in expected_key or expected_key in file_key:
            return 80
    return 0


def _download_dirs_candidate(base_dir: str = "") -> list[Path]:
    candidati: list[Path] = []
    for raw in [
        base_dir,
        os.getenv("HACS_SIGNER_DOWNLOADS_DIR", ""),
        str(Path.home() / "Downloads"),
        str(Path(os.environ.get("USERPROFILE", "")) / "Downloads") if os.environ.get("USERPROFILE") else "",
        str(Path(os.environ.get("OneDrive", "")) / "Downloads") if os.environ.get("OneDrive") else "",
    ]:
        testo = (raw or "").strip()
        if not testo:
            continue
        path = Path(testo).expanduser()
        if path.exists() and path.is_dir() and path not in candidati:
            candidati.append(path)
    return candidati


def _raccogli_download_recenti(
    expected_documents: list[dict],
    *,
    base_dir: str = "",
    max_age_hours: int = 72,
    limit: int = 25,
    max_total_bytes: int = 64 * 1024 * 1024,
) -> dict:
    candidati = _download_dirs_candidate(base_dir)
    if not candidati:
        raise RuntimeError(
            "Cartella Download non trovata sul computer locale. "
            "Seleziona i file manualmente oppure configura il percorso locale dei download."
        )

    expected_index: list[dict] = []
    for row in expected_documents or []:
        nome = str((row or {}).get("nome") or "").strip()
        key = _normalizza_nome_download_match(nome)
        if not nome or not key:
            continue
        expected_index.append({
            "nome": nome,
            "key": key,
            "id_deposito_esterno": str((row or {}).get("id_deposito_esterno") or "").strip(),
            "id_deposito_pct": str((row or {}).get("id_deposito_pct") or "").strip(),
            "tipo_atto": str((row or {}).get("tipo_atto") or "").strip(),
            "id_documento_portale": str((row or {}).get("id_documento_portale") or "").strip(),
            "data_deposito": str((row or {}).get("data_deposito") or "").strip(),
        })

    if not expected_index:
        raise RuntimeError(
            "Questo fascicolo non ha ancora metadati documentali ufficiali da confrontare. "
            "Prima sincronizza i documenti dal portale e poi ripeti la raccolta automatica."
        )

    cutoff = datetime.now() - timedelta(hours=max(1, int(max_age_hours or 72)))
    filesystem_candidates: list[Path] = []
    for root in candidati:
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.name.lower() in {".ds_store", "thumbs.db"}:
                continue
            if path.suffix.lower() in {".crdownload", ".part", ".tmp"}:
                continue
            try:
                modified_at = datetime.fromtimestamp(path.stat().st_mtime)
            except OSError:
                continue
            if modified_at < cutoff:
                continue
            filesystem_candidates.append(path)

    filesystem_candidates.sort(
        key=lambda item: item.stat().st_mtime if item.exists() else 0,
        reverse=True,
    )

    raccolti: list[dict] = []
    seen_match_keys: set[str] = set()
    total_bytes = 0

    for path in filesystem_candidates:
        file_key = _normalizza_nome_download_match(path.name)
        if not file_key:
            continue
        best_match = None
        best_score = 0
        for expected in expected_index:
            score = _score_download_match(file_key, expected["key"])
            if score > best_score:
                best_score = score
                best_match = expected
        if not best_match or best_score <= 0:
            continue

        dedupe_key = best_match.get("id_documento_portale") or (
            f'{best_match.get("id_deposito_esterno", "")}:{best_match.get("key", "")}'
        )
        if dedupe_key in seen_match_keys:
            continue

        try:
            payload = path.read_bytes()
        except OSError:
            continue
        if not payload:
            continue
        if total_bytes + len(payload) > max_total_bytes:
            break

        modified_at = datetime.fromtimestamp(path.stat().st_mtime)
        raccolti.append({
            "nome": path.name,
            "contenuto_b64": base64.b64encode(payload).decode("ascii"),
            "origine": str(path),
            "data_documento": modified_at.date().isoformat(),
            "dimensione_bytes": len(payload),
            "id_deposito_esterno": best_match.get("id_deposito_esterno", ""),
            "id_deposito_pct": best_match.get("id_deposito_pct", ""),
            "tipo_atto": best_match.get("tipo_atto", ""),
            "id_documento_portale": best_match.get("id_documento_portale", ""),
        })
        seen_match_keys.add(dedupe_key)
        total_bytes += len(payload)
        if len(raccolti) >= max(1, int(limit or 25)):
            break

    return {
        "files": raccolti,
        "directories": [str(path) for path in candidati],
        "matched": len(raccolti),
        "expected": len(expected_index),
        "total_bytes": total_bytes,
        "cutoff": cutoff.isoformat(),
    }


def _http_errore_leggibile(status_code: int, body: str, url: str = "", content_type: str = "") -> str:
    host = _pst_host(url)
    preview = _body_preview(body)
    suffix = ""
    if content_type:
        suffix = f"\nContent-Type risposta: {content_type}"
    if preview:
        suffix += f"\nAnteprima risposta: {preview}"

    if status_code == 401:
        return (
            f"Il PST ha risposto HTTP 401 Unauthorized da {host}.\n"
            "Il certificato CNS/CIE selezionato non è stato presentato oppure non è stato accettato dal proxy.\n"
            f"{_hint_pin_windows()}\n"
            "Verificare di avere selezionato il certificato corretto della smart card e riprovare."
            + suffix
        )
    if status_code == 403:
        return (
            f"Il PST ha risposto HTTP 403 Forbidden da {host}.\n"
            f"{_hint_pin_windows()}\n"
            "L'accesso al servizio è stato negato: verificare il proxy PST configurato e i permessi del certificato selezionato."
            + suffix
        )
    if status_code == 404:
        return (
            f"Il PST ha risposto HTTP 404 da {host}.\n"
            "L'endpoint del servizio non è stato trovato: verificare il proxy PST, il codice GL e il servizio JPW dell'ufficio selezionato."
            + suffix
        )
    if status_code >= 500:
        return (
            f"Il PST ha risposto HTTP {status_code} da {host}.\n"
            "Il servizio ministeriale ha restituito un errore interno o temporaneo. Riprovare tra qualche minuto."
            + suffix
        )
    return f"Il PST ha risposto HTTP {status_code} da {host}.{suffix}"


def _normalizza_xml_pst(xml_str: str) -> str:
    return (xml_str or "").lstrip("\ufeff\r\n\t ")


def _estrai_fault_soap(xml_str: str) -> str:
    """
    Estrae faultstring/Reason/Text da una SOAP Fault, se presente.
    """
    try:
        root = ET.fromstring(_normalizza_xml_pst(xml_str))
    except Exception:
        return ""

    for el in root.iter():
        if "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]

    fault = next(root.iter("Fault"), None)
    if fault is None:
        return ""

    fields = [
        fault.findtext("faultstring", default=""),
        fault.findtext("faultcode", default=""),
        fault.findtext("./Reason/Text", default=""),
        fault.findtext("./detail", default=""),
        fault.findtext("./Message", default=""),
    ]
    return " | ".join(part.strip() for part in fields if part and part.strip())


def _soap_call_curl_raw(url: str, soap_body: str,
                        cert_thumbprint: Optional[str] = None,
                        pkcs11_uri: Optional[str] = None,
                        extra_headers: Optional[list[str]] = None,
                        soap_action: Optional[str] = "",
                        content_type: str = "text/xml; charset=utf-8",
                        cookie_file: Optional[str] = None,
                        max_time: Optional[int] = None,
                        connect_timeout: Optional[int] = None) -> tuple[bytes, str]:
    """
    Esegue una chiamata SOAP usando curl.

    Su Windows (Schannel):
      - curl usa il Windows Certificate Store automaticamente
      - Aruba Key via Bit4id CSP è già registrata nello store
      - Non serve configurazione PKCS#11 esplicita
      - curl.exe incluso in Windows 10 1803+

    Su Linux:
      - curl con OpenSSL + PKCS#11 engine (richiede engine pkcs11 installato)
    """
    effective_max_time = int(max_time or PST_SOAP_MAX_TIME)
    effective_connect_timeout = int(connect_timeout or PST_SOAP_CONNECT_TIMEOUT)

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".xml", delete=False, encoding="utf-8"
    ) as f:
        f.write(soap_body)
        soap_file = f.name
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".hdr", delete=False, encoding="utf-8"
    ) as f_hdr:
        header_file = f_hdr.name

    try:
        cmd = [
            _curl_command(), "-s", "-S",
            "--max-time", str(effective_max_time),
            "--connect-timeout", str(effective_connect_timeout),
            "--location",
            "--dump-header", header_file,
            "-X", "POST",
            "-H", f"Content-Type: {content_type or 'text/xml; charset=utf-8'}",
            "--data", f"@{soap_file}",
        ]
        if soap_action is not None:
            cmd.extend(["-H", f'SOAPAction: "{soap_action}"'])
        for header in extra_headers or []:
            cmd.extend(["-H", header])
        if cookie_file:
            cookie_path = _ensure_cookie_file(cookie_file)
            cmd.extend(["--cookie", cookie_path, "--cookie-jar", cookie_path])

        if sys.platform == "win32":
            # Windows: Schannel usa Windows cert store → Aruba Key via Bit4id CSP
            # curl richiede il path CurrentUser\MY\<thumbprint>
            if cert_thumbprint:
                cmd.extend(["--cert", _format_windows_cert_spec(cert_thumbprint)])
            # Evita blocchi quando la revoca Schannel/CRL ministeriale non e' raggiungibile.
            cmd.extend(_curl_windows_ssl_revoke_args())
        elif pkcs11_uri:
            # Linux: curl con PKCS#11 engine
            cmd.extend([
                "--engine", "pkcs11",
                "--key-type", "ENG",
                "--key", pkcs11_uri,
                "--cert-type", "ENG",
                "--cert", pkcs11_uri,
            ])

        cmd.append(url)

        result = _run_curl_with_pin_foreground(
            cmd, capture_output=True,
            timeout=effective_max_time + 10
        )

        if result.returncode != 0:
            raise RuntimeError(
                _curl_errore_leggibile(
                    result.returncode,
                    result.stderr.decode("utf-8", "replace"),
                    url,
                    timeout_sec=effective_max_time,
                )
            )

        headers_text = Path(header_file).read_text(encoding="utf-8", errors="replace")
        status_code = _http_status_from_headers(headers_text)
        content_type = _http_header_value(headers_text, "Content-Type")
        body_text = result.stdout.decode("utf-8", "replace")
        if status_code and status_code >= 400:
            fault = _estrai_fault_soap(body_text)
            if fault:
                raise RuntimeError(f"Il PST ha restituito una SOAP Fault: {fault}")
            raise RuntimeError(
                _http_errore_leggibile(status_code, body_text, url, content_type)
            )
        if "html" in content_type.lower() and "<html" in body_text.lower():
            raise RuntimeError(
                "Il PST ha restituito una pagina HTML anziché XML SOAP.\n"
                "Verificare il certificato selezionato e il proxy PST configurato.\n"
                f"Anteprima risposta: {_body_preview(body_text)}"
            )

        return result.stdout, headers_text

    finally:
        try:
            os.unlink(soap_file)
        except OSError:
            pass
        try:
            os.unlink(header_file)
        except OSError:
            pass


def _soap_call_curl_batch_raw(
    requests: list[dict],
    cert_thumbprint: Optional[str] = None,
    pkcs11_uri: Optional[str] = None,
) -> list[tuple[bytes, str]]:
    """
    Esegue N chiamate SOAP in un unico processo curl → un solo prompt PIN Windows.

    Usa il file di configurazione curl (-K) con 'next' per concatenare tutte le
    richieste nello stesso subprocess: Windows Schannel/Aruba Key chiede il PIN
    una sola volta per l'intero batch invece di N volte.

    requests: lista di dict con chiavi:
        url, soap_body, soap_action (opt), extra_headers (opt), cookie_file (opt)
    Ritorna: lista di (body_bytes, headers_text) — stesso ordine di requests.
    """
    if not requests:
        return []
    # Con una sola richiesta usa il path diretto (nessun overhead da config file)
    if len(requests) == 1:
        r = requests[0]
        return [_soap_call_curl_raw(
            url=r["url"],
            soap_body=r["soap_body"],
            cert_thumbprint=cert_thumbprint,
            pkcs11_uri=pkcs11_uri,
            extra_headers=r.get("extra_headers"),
            soap_action=r.get("soap_action", ""),
            cookie_file=r.get("cookie_file"),
            max_time=r.get("max_time"),
            connect_timeout=r.get("connect_timeout"),
        )]

    tmp_files: list[str] = []
    try:
        transfers = []
        for i, req in enumerate(requests):
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=f"_bsb{i}.xml", delete=False, encoding="utf-8"
            ) as f:
                f.write(req["soap_body"])
                body_file = f.name
            tmp_files.append(body_file)

            resp_fd, resp_file = tempfile.mkstemp(suffix=f"_bsr{i}.bin")
            os.close(resp_fd)
            tmp_files.append(resp_file)

            hdr_fd, hdr_file = tempfile.mkstemp(suffix=f"_bsh{i}.txt")
            os.close(hdr_fd)
            tmp_files.append(hdr_file)

            transfers.append({
                "body_file": body_file,
                "resp_file": resp_file,
                "hdr_file": hdr_file,
                "url": req["url"],
                "soap_action": req.get("soap_action") or "",
                "extra_headers": list(req.get("extra_headers") or []),
                "cookie_file": str(req.get("cookie_file") or ""),
                "max_time": int(req.get("max_time") or PST_SOAP_MAX_TIME),
                "connect_timeout": int(req.get("connect_timeout") or PST_SOAP_CONNECT_TIMEOUT),
            })

        def _qp(p: str) -> str:
            """Path per curl config file: slash Unix su tutte le piattaforme."""
            return Path(p).as_posix() if p else ""

        cert_spec = (
            _format_windows_cert_spec(cert_thumbprint)
            if sys.platform == "win32" and cert_thumbprint
            else ""
        )

        cfg_lines: list[str] = []
        for i, t in enumerate(transfers):
            if i > 0:
                cfg_lines += ["next", ""]
            sa = (t["soap_action"] or "").replace('"', '\\"')
            cfg_lines += [
                f'url = "{t["url"]}"',
                "request = POST",
                'header = "Content-Type: text/xml; charset=utf-8"',
                f'header = "SOAPAction: \\"{sa}\\""',
            ]
            for hdr in t["extra_headers"]:
                cfg_lines.append(f'header = "{_curl_config_escape(hdr)}"')
            cfg_lines += [
                f'data = "@{_qp(t["body_file"])}"',
                f'output = "{_qp(t["resp_file"])}"',
                f'dump-header = "{_qp(t["hdr_file"])}"',
                f'max-time = {t["max_time"]}',
                f'connect-timeout = {t["connect_timeout"]}',
                "location",
            ]
            if t["cookie_file"]:
                cp = _qp(_ensure_cookie_file(t["cookie_file"]))
                cfg_lines += [f'cookie = "{cp}"', f'cookie-jar = "{cp}"']
            if sys.platform == "win32":
                if cert_spec:
                    # Nel config file di curl i backslash devono essere escape-ati:
                    # CurrentUser\MY\<thumbprint> va scritto come
                    # CurrentUser\\MY\\<thumbprint>, altrimenti Schannel non
                    # riesce a risolvere il certificato dal Windows Store.
                    cfg_lines.append(f'cert = "{_curl_config_escape(cert_spec)}"')
                cfg_lines.extend(_curl_windows_ssl_revoke_config_lines())
            elif pkcs11_uri:
                cfg_lines += [
                    "engine = pkcs11",
                    "key-type = ENG",
                    f'key = "{_curl_config_escape(pkcs11_uri)}"',
                    "cert-type = ENG",
                    f'cert = "{_curl_config_escape(pkcs11_uri)}"',
                ]
            cfg_lines.append("")

        with tempfile.NamedTemporaryFile(
            mode="w", suffix="_bscfg.cfg", delete=False, encoding="utf-8"
        ) as f:
            f.write("\n".join(cfg_lines))
            cfg_file = f.name
        tmp_files.append(cfg_file)

        log.debug("curl batch: %d richieste SOAP in un solo processo", len(transfers))
        result = _run_curl_with_pin_foreground(
            [_curl_command(), "-s", "-S", "-K", cfg_file],
            capture_output=True,
            timeout=sum((int(t["max_time"]) + 10) for t in transfers),
        )
        if result.returncode != 0:
            raise RuntimeError(
                _curl_errore_leggibile(
                    result.returncode,
                    result.stderr.decode("utf-8", "replace"),
                    transfers[0]["url"],
                    timeout_sec=max(int(t["max_time"]) for t in transfers),
                )
            )

        results: list[tuple[bytes, str]] = []
        for t in transfers:
            hdr_path = Path(t["hdr_file"])
            resp_path = Path(t["resp_file"])
            hdr_text = (
                hdr_path.read_text(encoding="utf-8", errors="replace")
                if hdr_path.exists() else ""
            )
            body_bytes = resp_path.read_bytes() if resp_path.exists() else b""
            status = _http_status_from_headers(hdr_text)
            if status and status >= 400:
                body_str = body_bytes.decode("utf-8", "replace")
                fault = _estrai_fault_soap(body_str)
                if fault:
                    raise RuntimeError(f"Il PST ha restituito una SOAP Fault: {fault}")
                ct = _http_header_value(hdr_text, "Content-Type")
                raise RuntimeError(_http_errore_leggibile(status, body_str, t["url"], ct))
            results.append((body_bytes, hdr_text))
        return results

    finally:
        for fp in tmp_files:
            try:
                Path(fp).unlink(missing_ok=True)
            except Exception:
                pass


def _soap_call_curl_batch_raw_best_effort(
    requests: list[dict],
    cert_thumbprint: Optional[str] = None,
    pkcs11_uri: Optional[str] = None,
) -> list[dict]:
    """
    Variante best-effort del batch curl:
    esegue tutte le richieste nello stesso processo ma non interrompe l'intero
    lotto se una singola richiesta restituisce HTTP >= 400, HTML o SOAP Fault.

    Ogni elemento della lista contiene:
      body_bytes, headers_text, status_code, error
    """
    if not requests:
        return []
    if len(requests) == 1:
        req = requests[0]
        try:
            body_bytes, headers_text = _soap_call_curl_raw(
                url=req["url"],
                soap_body=req["soap_body"],
                cert_thumbprint=cert_thumbprint,
                pkcs11_uri=pkcs11_uri,
                extra_headers=req.get("extra_headers"),
                soap_action=req.get("soap_action", ""),
                cookie_file=req.get("cookie_file"),
                max_time=req.get("max_time"),
                connect_timeout=req.get("connect_timeout"),
            )
            body_text = body_bytes.decode("utf-8", "replace")
            fault = _estrai_fault_soap(body_text)
            if fault:
                return [{
                    "body_bytes": body_bytes,
                    "headers_text": headers_text,
                    "status_code": _http_status_from_headers(headers_text),
                    "error": f"Il PST ha restituito una SOAP Fault: {fault}",
                }]
            return [{
                "body_bytes": body_bytes,
                "headers_text": headers_text,
                "status_code": _http_status_from_headers(headers_text),
                "error": "",
            }]
        except Exception as e:
            return [{
                "body_bytes": b"",
                "headers_text": "",
                "status_code": 0,
                "error": str(e),
            }]

    tmp_files: list[str] = []
    try:
        transfers = []
        for i, req in enumerate(requests):
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=f"_bsb{i}.xml", delete=False, encoding="utf-8"
            ) as f:
                f.write(req["soap_body"])
                body_file = f.name
            tmp_files.append(body_file)

            resp_fd, resp_file = tempfile.mkstemp(suffix=f"_bsr{i}.bin")
            os.close(resp_fd)
            tmp_files.append(resp_file)

            hdr_fd, hdr_file = tempfile.mkstemp(suffix=f"_bsh{i}.txt")
            os.close(hdr_fd)
            tmp_files.append(hdr_file)

            transfers.append({
                "body_file": body_file,
                "resp_file": resp_file,
                "hdr_file": hdr_file,
                "url": req["url"],
                "soap_action": req.get("soap_action") or "",
                "extra_headers": list(req.get("extra_headers") or []),
                "cookie_file": str(req.get("cookie_file") or ""),
                "max_time": int(req.get("max_time") or PST_SOAP_MAX_TIME),
                "connect_timeout": int(req.get("connect_timeout") or PST_SOAP_CONNECT_TIMEOUT),
            })

        def _qp(p: str) -> str:
            return Path(p).as_posix() if p else ""

        cert_spec = (
            _format_windows_cert_spec(cert_thumbprint)
            if sys.platform == "win32" and cert_thumbprint
            else ""
        )

        cfg_lines: list[str] = []
        for i, t in enumerate(transfers):
            if i > 0:
                cfg_lines += ["next", ""]
            sa = (t["soap_action"] or "").replace('"', '\\"')
            cfg_lines += [
                f'url = "{t["url"]}"',
                "request = POST",
                'header = "Content-Type: text/xml; charset=utf-8"',
                f'header = "SOAPAction: \\"{sa}\\""',
            ]
            for hdr in t["extra_headers"]:
                cfg_lines.append(f'header = "{_curl_config_escape(hdr)}"')
            cfg_lines += [
                f'data = "@{_qp(t["body_file"])}"',
                f'output = "{_qp(t["resp_file"])}"',
                f'dump-header = "{_qp(t["hdr_file"])}"',
                f'max-time = {t["max_time"]}',
                f'connect-timeout = {t["connect_timeout"]}',
                "location",
            ]
            if t["cookie_file"]:
                cp = _qp(_ensure_cookie_file(t["cookie_file"]))
                cfg_lines += [f'cookie = "{cp}"', f'cookie-jar = "{cp}"']
            if sys.platform == "win32":
                if cert_spec:
                    cfg_lines.append(f'cert = "{_curl_config_escape(cert_spec)}"')
                cfg_lines.extend(_curl_windows_ssl_revoke_config_lines())
            elif pkcs11_uri:
                cfg_lines += [
                    "engine = pkcs11",
                    "key-type = ENG",
                    f'key = "{_curl_config_escape(pkcs11_uri)}"',
                    "cert-type = ENG",
                    f'cert = "{_curl_config_escape(pkcs11_uri)}"',
                ]
            cfg_lines.append("")

        with tempfile.NamedTemporaryFile(
            mode="w", suffix="_bscfg.cfg", delete=False, encoding="utf-8"
        ) as f:
            f.write("\n".join(cfg_lines))
            cfg_file = f.name
        tmp_files.append(cfg_file)

        result = _run_curl_with_pin_foreground(
            [_curl_command(), "-s", "-S", "-K", cfg_file],
            capture_output=True,
            timeout=sum((int(t["max_time"]) + 10) for t in transfers),
        )
        batch_error = ""
        if result.returncode != 0:
            batch_error = _curl_errore_leggibile(
                result.returncode,
                result.stderr.decode("utf-8", "replace"),
                transfers[0]["url"],
                timeout_sec=max(int(t["max_time"]) for t in transfers),
            )
            log.warning("curl batch best-effort terminato con errore globale: %s", batch_error)

        results: list[dict] = []
        for t in transfers:
            hdr_path = Path(t["hdr_file"])
            resp_path = Path(t["resp_file"])
            hdr_text = (
                hdr_path.read_text(encoding="utf-8", errors="replace")
                if hdr_path.exists() else ""
            )
            body_bytes = resp_path.read_bytes() if resp_path.exists() else b""
            status = _http_status_from_headers(hdr_text)
            body_str = body_bytes.decode("utf-8", "replace")
            content_type = _http_header_value(hdr_text, "Content-Type")
            error = ""
            if status and status >= 400:
                fault = _estrai_fault_soap(body_str)
                if fault:
                    error = f"Il PST ha restituito una SOAP Fault: {fault}"
                else:
                    error = _http_errore_leggibile(status, body_str, t["url"], content_type)
            elif not hdr_text.strip() and not body_bytes and batch_error:
                error = batch_error
            elif "html" in content_type.lower() and "<html" in body_str.lower():
                error = (
                    "Il PST ha restituito una pagina HTML anziché XML SOAP.\n"
                    "Verificare il certificato selezionato e il proxy PST configurato.\n"
                    f"Anteprima risposta: {_body_preview(body_str)}"
                )
            else:
                fault = _estrai_fault_soap(body_str)
                if fault:
                    error = f"Il PST ha restituito una SOAP Fault: {fault}"

            results.append({
                "body_bytes": body_bytes,
                "headers_text": hdr_text,
                "status_code": status,
                "error": error,
            })
        return results
    finally:
        for fp in tmp_files:
            try:
                Path(fp).unlink(missing_ok=True)
            except Exception:
                pass


def _soap_call_curl(url: str, soap_body: str,
                    cert_thumbprint: Optional[str] = None,
                    pkcs11_uri: Optional[str] = None,
                    extra_headers: Optional[list[str]] = None,
                    soap_action: Optional[str] = "",
                    cookie_file: Optional[str] = None,
                    max_time: Optional[int] = None,
                    connect_timeout: Optional[int] = None) -> str:
    body_bytes, _headers = _soap_call_curl_raw(
        url=url,
        soap_body=soap_body,
        cert_thumbprint=cert_thumbprint,
        pkcs11_uri=pkcs11_uri,
        extra_headers=extra_headers,
        soap_action=soap_action,
        cookie_file=cookie_file,
        max_time=max_time,
        connect_timeout=connect_timeout,
    )
    return body_bytes.decode("utf-8", "replace")


def _get_zeep_wsdl_client(wsdl_url: str):
    client = _ZEEP_WSDL_CACHE.get(wsdl_url)
    if client is not None:
        return client
    try:
        import zeep
    except ImportError as exc:
        raise RuntimeError(
            "Dipendenza mancante nel Local Signer: installare zeep per l'accesso Aruba Key a PDP/PAT/PTT."
        ) from exc
    try:
        client = zeep.Client(wsdl=wsdl_url)
    except Exception as exc:
        if _looks_like_dns_resolution_error(exc):
            raise RuntimeError(_messaggio_dns_endpoint_portale(wsdl_url)) from exc
        raise
    _ZEEP_WSDL_CACHE[wsdl_url] = client
    return client


def _soap_call_zeep_operation_via_curl(
    *,
    wsdl_url: str,
    operation_name: str,
    payload: dict[str, Any],
    cert_thumbprint: Optional[str] = None,
    pkcs11_uri: Optional[str] = None,
) -> Any:
    try:
        from lxml import etree
        from requests import Response
    except ImportError as exc:
        raise RuntimeError(
            "Dipendenze incomplete nel Local Signer: servono lxml e requests per PDP/PAT/PTT."
        ) from exc

    client = _get_zeep_wsdl_client(wsdl_url)
    binding = client.service._binding
    operation = binding.get(operation_name)
    if operation is None:
        raise RuntimeError(f"Operazione SOAP non trovata: {operation_name}")

    envelope, http_headers = binding._create(
        operation_name,
        args=[],
        kwargs=payload,
        client=client,
    )
    soap_body = etree.tostring(
        envelope,
        encoding="utf-8",
        xml_declaration=True,
    ).decode("utf-8")

    raw_headers = dict(http_headers or {})
    content_type = (
        raw_headers.pop("Content-Type", None)
        or raw_headers.pop("content-type", None)
        or "text/xml; charset=utf-8"
    )
    soap_action = raw_headers.pop("SOAPAction", None) or raw_headers.pop("Soapaction", None)
    extra_headers = [f"{key}: {value}" for key, value in raw_headers.items()]
    address = str((client.service._binding_options or {}).get("address") or "").strip()
    if not address:
        address = wsdl_url.split("?", 1)[0]

    body_bytes, headers_text = _soap_call_curl_raw(
        url=address,
        soap_body=soap_body,
        cert_thumbprint=cert_thumbprint,
        pkcs11_uri=pkcs11_uri,
        extra_headers=extra_headers,
        soap_action=(str(soap_action).strip('"') if soap_action is not None else None),
        content_type=str(content_type),
    )

    response = Response()
    response.status_code = _http_status_from_headers(headers_text) or 200
    response._content = body_bytes
    response.headers.update(_http_headers_dict(headers_text))
    response.encoding = "utf-8"
    response.url = address
    return binding.process_reply(client, operation, response)


def _soap_call_pst_session(
    *,
    url: str,
    soap_body: str,
    cert_thumbprint: Optional[str] = None,
    extra_headers: Optional[list[str]] = None,
    soap_action: str = "",
    cookie_file: Optional[str] = None,
    prefer_cookie_only: bool = False,
    max_time: Optional[int] = None,
    connect_timeout: Optional[int] = None,
) -> str:
    """
    Riusa prima l'eventuale sessione HTTP del portale (cookie_file) e solo in
    fallback ripresenta il certificato client. Questo riduce drasticamente i
    prompt PIN ripetuti durante ricerca, anteprima e download batch.

    Ottimizzazione mTLS: se per questo host è già noto che il cookie-only
    fallisce (portale con mTLS obbligatorio), si salta direttamente al cert.
    Così tutte le chiamate successive alla prima arrivano velocemente al cert
    e rientrano nella finestra di cache-PIN di Windows (Bit4id/Aruba Key),
    riducendo i prompt PIN a uno solo per l'intera sessione batch.
    """
    host = _pst_host(url)

    def _run(cert_value: Optional[str]) -> str:
        return _soap_call_curl(
            url=url,
            soap_body=soap_body,
            cert_thumbprint=cert_value,
            extra_headers=extra_headers,
            soap_action=soap_action,
            cookie_file=cookie_file,
            max_time=max_time,
            connect_timeout=connect_timeout,
        )

    if prefer_cookie_only and cookie_file and (not host or host not in _mTLS_required_hosts):
        # Quando prefer_cookie_only=True il preflight ha già stabilito una sessione
        # autenticata con cookie validi. Tentiamo cookie-only solo se il portale
        # non è già noto come mTLS-obbligatorio (per evitare prompt PIN ripetuti).
        try:
            return _run(None)
        except Exception as e:
            if not _pst_cookie_retry_requires_cert(e):
                raise
            # Il portale richiede mTLS per ogni chiamata: registra l'host così le
            # chiamate successive saltano il tentativo cookie e vanno subito al cert,
            # restando all'interno della finestra di cache-PIN di Windows.
            with _mTLS_required_lock:
                _mTLS_required_hosts.add(host)
            log.info(
                "PST host %s: cookie-only rifiutato, prossime chiamate useranno"
                " direttamente il certificato (cache-PIN Windows).", host
            )
    return _run(cert_thumbprint)


def _soap_call_pst_session_raw(
    *,
    url: str,
    soap_body: str,
    cert_thumbprint: Optional[str] = None,
    extra_headers: Optional[list[str]] = None,
    soap_action: str = "",
    cookie_file: Optional[str] = None,
    prefer_cookie_only: bool = False,
    max_time: Optional[int] = None,
    connect_timeout: Optional[int] = None,
) -> tuple[bytes, str]:
    """Versione raw (bytes) di _soap_call_pst_session — stessa logica mTLS."""
    host = _pst_host(url)

    def _run(cert_value: Optional[str]) -> tuple[bytes, str]:
        return _soap_call_curl_raw(
            url=url,
            soap_body=soap_body,
            cert_thumbprint=cert_value,
            extra_headers=extra_headers,
            soap_action=soap_action,
            cookie_file=cookie_file,
            max_time=max_time,
            connect_timeout=connect_timeout,
        )

    if prefer_cookie_only and cookie_file and (not host or host not in _mTLS_required_hosts):
        # Stessa logica di _soap_call_pst_session: tenta cookie-only solo se il
        # portale non è già noto come mTLS-obbligatorio.
        try:
            return _run(None)
        except Exception as e:
            if not _pst_cookie_retry_requires_cert(e):
                raise
            with _mTLS_required_lock:
                _mTLS_required_hosts.add(host)
            log.info(
                "PST host %s (raw): cookie-only rifiutato, future chiamate"
                " useranno direttamente il certificato.", host
            )
    return _run(cert_thumbprint)


def _soap_call_pst_session_batch_raw(
    requests: list[dict],
    *,
    cert_thumbprint: Optional[str] = None,
    cookie_file: Optional[str] = None,
    prefer_cookie_only: bool = False,
) -> list[tuple[bytes, str]]:
    """
    Variante batch della logica session-aware PST:
    prova prima l'intero lotto in cookie-only e, se la sessione non basta,
    ritenta l'intero lotto col certificato in un solo processo curl.

    Questo evita il peggior fallback possibile su Windows, cioe' N download
    singoli con N potenziali prompt PIN.
    """
    effective_requests = [
        {
            **dict(req),
            "cookie_file": str((dict(req).get("cookie_file") or cookie_file or "")).strip(),
        }
        for req in (requests or [])
    ]
    first_url = str((effective_requests[0].get("url") if effective_requests else None) or "")
    host = _pst_host(first_url) if first_url else ""
    if prefer_cookie_only and cookie_file and (not host or host not in _mTLS_required_hosts):
        try:
            return _soap_call_curl_batch_raw(
                effective_requests,
                cert_thumbprint=None,
            )
        except Exception as e:
            if not _pst_cookie_retry_requires_cert(e):
                raise
            if host:
                with _mTLS_required_lock:
                    _mTLS_required_hosts.add(host)
                log.info(
                    "PST host %s (batch): cookie-only rifiutato, future chiamate"
                    " useranno direttamente il certificato.", host
                )
    return _soap_call_curl_batch_raw(
        effective_requests,
        cert_thumbprint=cert_thumbprint,
    )


def _soap_call_pst_session_batch_raw_best_effort(
    requests: list[dict],
    *,
    cert_thumbprint: Optional[str] = None,
    cookie_file: Optional[str] = None,
    prefer_cookie_only: bool = False,
) -> list[dict]:
    """
    Variante session-aware best-effort del batch PST:
    restituisce un risultato per ogni richiesta e lascia al chiamante decidere
    se ignorare i fault di singoli documenti senza perdere l'intero lotto.
    """
    effective_requests = [
        {
            **dict(req),
            "cookie_file": str((dict(req).get("cookie_file") or cookie_file or "")).strip(),
        }
        for req in (requests or [])
    ]
    first_url = str((effective_requests[0].get("url") if effective_requests else None) or "")
    host = _pst_host(first_url) if first_url else ""
    if prefer_cookie_only and cookie_file and (not host or host not in _mTLS_required_hosts):
        try:
            cookie_results = _soap_call_curl_batch_raw_best_effort(
                effective_requests,
                cert_thumbprint=None,
            )
        except Exception as e:
            if not _pst_cookie_retry_requires_cert(e):
                raise
            if host:
                with _mTLS_required_lock:
                    _mTLS_required_hosts.add(host)
                log.info(
                    "PST host %s (batch best-effort): cookie-only rifiutato,"
                    " future chiamate useranno direttamente il certificato.", host
                )
        else:
            blocking_error = _pst_best_effort_batch_blocking_error(cookie_results)
            if not blocking_error or not _pst_cookie_retry_requires_cert(RuntimeError(blocking_error)):
                return cookie_results
            if host:
                with _mTLS_required_lock:
                    _mTLS_required_hosts.add(host)
                log.info(
                    "PST host %s (batch best-effort): cookie-only ha restituito"
                    " autenticazione non valida, ritento subito col certificato.", host
                )

        fresh_cookie = _reset_pst_session_cookie_after_auth_failure(
            cookie_file,
            "cookie-only PST rifiutato; retry immediato col certificato",
        )
        effective_requests = [
            {**req, "cookie_file": fresh_cookie}
            for req in effective_requests
        ]
    cert_results = _soap_call_curl_batch_raw_best_effort(
        effective_requests,
        cert_thumbprint=cert_thumbprint,
    )
    final_blocking_error = _pst_best_effort_batch_blocking_error(cert_results)
    if final_blocking_error and _pst_auth_failure_requires_fresh_session(final_blocking_error):
        _reset_pst_session_cookie_after_auth_failure(
            cookie_file,
            "autenticazione PST rifiutata anche col certificato",
        )
    return cert_results


def _pst_best_effort_batch_blocking_error(items: list[dict]) -> str:
    """Restituisce l'errore bloccante quando nessuna richiesta PST e' valida."""
    if not items:
        return ""

    errors: list[str] = []
    has_success = False
    for item in items:
        if not isinstance(item, dict):
            continue
        error = str(item.get("error") or "").strip()
        body = item.get("body_bytes") or b""
        if error:
            errors.append(error)
            continue
        body_text = ""
        if isinstance(body, bytes) and body.strip():
            body_text = body.decode("utf-8", "replace")
        elif isinstance(body, str) and body.strip():
            body_text = body
        if body_text:
            fault = _estrai_fault_soap(body_text)
            if fault:
                errors.append(f"Il PST ha restituito una SOAP Fault: {fault}")
                continue
            has_success = True

    if has_success or not errors:
        return ""

    auth_errors = [
        error
        for error in errors
        if _pst_cookie_retry_requires_cert(RuntimeError(error))
        and ("401" in error or "Unauthorized" in error or "certificato" in error.lower())
    ]
    if auth_errors:
        return (
            "Autenticazione PST non riuscita: il portale ha rifiutato il certificato "
            "o il PIN non e' stato completato.\n"
            f"{auth_errors[0]}"
        )
    return errors[0]


def _pst_xml_response_valida_senza_fault(xml_str: str) -> bool:
    xml_clean = _normalizza_xml_pst(xml_str)
    if not xml_clean:
        return False
    if _estrai_fault_soap(xml_clean):
        return False
    try:
        ET.fromstring(xml_clean)
        return True
    except Exception:
        return False


def _pst_fault_ricerca_preferita(faults: list[str]) -> str:
    cleaned: list[str] = []
    for fault in faults:
        text = str(fault or "").strip()
        if text and text not in cleaned:
            cleaned.append(text)
    if not cleaned:
        return ""

    priority_markers = (
        "non puo' eseguire",
        "non può eseguire",
        "unauthorized",
        "certificato",
        "pin",
        "service",
        "base dati",
    )
    for marker in priority_markers:
        marker_lower = marker.lower()
        for fault in cleaned:
            if marker_lower in fault.lower():
                return fault
    return cleaned[0]


def _pst_ricerca_vuota_fault_message(faults: list[str]) -> str:
    fault = _pst_fault_ricerca_preferita(faults)
    if not fault:
        return ""
    return (
        "Il PST non ha restituito una risposta valida per la ricerca fascicolo.\n"
        f"Il PST ha restituito una SOAP Fault: {fault}"
    )


def _pst_preflight_auth_curl(url: str,
                             cert_thumbprint: Optional[str] = None,
                             pkcs11_uri: Optional[str] = None,
                             cookie_file: Optional[str] = None) -> dict:
    """
    Esegue una richiesta leggera verso il servizio PST per forzare la
    presentazione del certificato client e l'eventuale prompt PIN di Windows.

    Considera "autenticazione avviata correttamente" le risposte HTTP che
    dimostrano handshake TLS riuscito e servizio raggiungibile, anche se il
    metodo non e' quello atteso dal servizio SOAP.
    """
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".hdr", delete=False, encoding="utf-8"
    ) as f_hdr:
        header_file = f_hdr.name
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".body", delete=False, encoding="utf-8"
    ) as f_body:
        body_file = f_body.name

    accepted_statuses = {200, 204, 301, 302, 303, 307, 308, 400, 405, 415, 500}

    try:
        cmd = [
            _curl_command(), "-s", "-S",
            "--max-time", str(PST_PREFLIGHT_MAX_TIME),
            "--connect-timeout", str(PST_PREFLIGHT_CONNECT_TIMEOUT),
            "--location",
            "--dump-header", header_file,
            "-o", body_file,
            "-X", "GET",
        ]
        if cookie_file:
            cookie_path = _ensure_cookie_file(cookie_file)
            cmd.extend(["--cookie", cookie_path, "--cookie-jar", cookie_path])

        if sys.platform == "win32":
            if cert_thumbprint:
                cmd.extend(["--cert", _format_windows_cert_spec(cert_thumbprint)])
            cmd.extend(_curl_windows_ssl_revoke_args())
        elif pkcs11_uri:
            cmd.extend([
                "--engine", "pkcs11",
                "--key-type", "ENG",
                "--key", pkcs11_uri,
                "--cert-type", "ENG",
                "--cert", pkcs11_uri,
            ])

        cmd.append(url)

        try:
            result = _run_curl_with_pin_foreground(
                cmd, capture_output=True, text=True,
                timeout=PST_PREFLIGHT_MAX_TIME + 10, encoding="utf-8", errors="replace"
            )
        except subprocess.TimeoutExpired:
            return {
                "ok": True,
                "http_code": None,
                "content_type": None,
                "warning": _messaggio_timeout_preflight_non_bloccante(_pst_host(url)),
                "nota": "Preflight PST in timeout non bloccante; proseguo con la ricerca reale.",
            }

        if result.returncode == 28:
            return {
                "ok": True,
                "http_code": None,
                "content_type": None,
                "warning": _messaggio_timeout_preflight_non_bloccante(_pst_host(url)),
                "nota": "Preflight PST in timeout non bloccante; proseguo con la ricerca reale.",
            }

        if result.returncode != 0:
            raise RuntimeError(
                _curl_errore_leggibile(
                    result.returncode,
                    result.stderr,
                    url,
                    timeout_sec=PST_PREFLIGHT_MAX_TIME,
                )
                + "\n"
                + _hint_pin_windows()
            )

        headers_text = Path(header_file).read_text(encoding="utf-8", errors="replace")
        body_text = Path(body_file).read_text(encoding="utf-8", errors="replace")
        status_code = _http_status_from_headers(headers_text)
        content_type = _http_header_value(headers_text, "Content-Type")

        if status_code in accepted_statuses:
            return {
                "ok": True,
                "http_code": status_code,
                "content_type": content_type or None,
                "nota": (
                    "Certificato selezionato e richiesta PIN gestita dal sistema."
                ),
            }

        if status_code:
            raise RuntimeError(
                _http_errore_leggibile(status_code, body_text, url, content_type)
            )

        return {
            "ok": True,
            "http_code": None,
            "content_type": content_type or None,
            "nota": "Connessione PST avviata con certificato client.",
        }
    finally:
        try:
            os.unlink(header_file)
        except OSError:
            pass
        try:
            os.unlink(body_file)
        except OSError:
            pass


def _esc(v: str) -> str:
    return (v.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
              .replace('"', "&quot;").replace("'", "&apos;"))


def _strip_namespaces(root: ET.Element) -> ET.Element:
    for el in root.iter():
        if "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]
    return root


def _soap_qbuilder_envelope(namespace: str, body_inner: str, *, role: str, group: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">
  <soapenv:Header>
    <ws:InvocationDomain name="JPW" role="{_esc(role)}" group="{_esc(group)}"
        soapenv:mustUnderstand="1"
        soapenv:actor="http://schemas.xmlsoap.org/soap/actor/next"
        xmlns:ws="http://www.netserv.it/anag/security"/>
  </soapenv:Header>
  <soapenv:Body>
    {body_inner}
  </soapenv:Body>
</soapenv:Envelope>"""


def _soap_qbuilder_execute_body(
    namespace: str,
    service_name: str,
    values: list[tuple[str, str, str]],
    *,
    role: str,
    group: str,
    order_entries: Optional[list[tuple[str, str]]] = None,
    empty_order: bool = False,
) -> str:
    values_xml = "".join(
        f'<value name="{_esc(name)}" type="{_esc(value_type)}">{_esc(str(value))}</value>'
        for name, value_type, value in values
        if value not in ("", None)
    )
    order_xml = ""
    if order_entries:
        entries = "".join(
            f'<entry property="{_esc(prop)}" mode="{_esc(mode)}"/>'
            for prop, mode in order_entries
        )
        order_xml = f"<orderBy>{entries}</orderBy>"
    elif empty_order:
        order_xml = "<orderBy/>"
    body_inner = (
        f'<execute xmlns="{_esc(namespace)}">'
        f"<name>{_esc(service_name)}</name>"
        f"<valueSet>{values_xml}</valueSet>"
        f"{order_xml}"
        f"</execute>"
    )
    return _soap_qbuilder_envelope(namespace, body_inner, role=role, group=group)


def _parte_ricerca_qbuilder(nome_parte: Optional[str], cf_parte: Optional[str]) -> str:
    testo = " ".join((nome_parte or "").split()).strip()
    if testo:
        return testo.split()[0].upper()
    cf_clean = _estrai_codice_fiscale_testo(cf_parte or "")
    return cf_clean[:6] if cf_clean else ""


def _soap_ricerca_fascicoli_body(base_url: str, codice_ufficio: str, numero_rg: Optional[str] = None,
                                  anno_rg: Optional[int] = None,
                                  nome_parte: Optional[str] = None,
                                  cf_parte: Optional[str] = None,
                                  cf_avvocato: str = "",
                                  sub_procedimento: str = "") -> str:
    """Costruisce il body SOAP per RicercaFascicoliRegistro o qbuilder SICID."""
    namespace = _pst_namespace_qbuilder(base_url)
    if namespace:
        if numero_rg and anno_rg:
            numero_value = str(int(str(numero_rg).strip())) if str(numero_rg).strip().isdigit() else str(numero_rg).strip()
            if _pst_servizio_siecic(base_url):
                return _soap_qbuilder_execute_body(
                    namespace,
                    "InfoFascicolo",
                    [
                        ("idUfficio", "string", codice_ufficio),
                        ("numeroRuolo", "string", numero_value),
                        ("annoRuolo", "integer", str(anno_rg)),
                    ],
                    role="AVV",
                    group=codice_ufficio,
                    order_entries=[("annoRuolo, numeroRuolo", "asc")],
                )
            values = [
                ("idUfficio", "string", codice_ufficio),
                ("tipo", "string", _pst_tipo_ricerca_qbuilder(base_url)),
                ("numero", "integer", numero_value),
                ("anno", "string", str(anno_rg)),
            ]
            if _pst_servizio_sigp(base_url):
                sigp_subpro = _pst_subpro_sigp(sub_procedimento)
                if sigp_subpro:
                    values.append(("subpro", "string", sigp_subpro))
            return _soap_qbuilder_execute_body(
                namespace,
                "RicercaInformazioniFascicoloPerTipo",
                values,
                role="AVV",
                group=codice_ufficio,
                order_entries=[("ANNORUOLO, NUMERORUOLO", "asc")],
            )
        parte = _parte_ricerca_qbuilder(nome_parte, cf_parte)
        if not parte:
            raise RuntimeError(
                "Per la ricerca per parte sul registro civile indicare almeno il cognome o il nome della parte."
            )
        return _soap_qbuilder_execute_body(
            namespace,
            "RicercaInformazioniFascicoloPerPartiGiudiceDate",
            [
                ("idUfficio", "string", codice_ufficio),
                ("cognomeNome", "string", parte),
                ("codiceFiscale", "string", _estrai_codice_fiscale_testo(cf_parte or "").upper()),
                ("giudice", "string", ""),
                ("dataRuoloDa", "string", ""),
                ("dataRuoloA", "string", ""),
            ],
            role="AVV",
            group=codice_ufficio,
            order_entries=[("ANNORUOLO, NUMERORUOLO", "asc")],
        )

    def tag(name, value):
        if value:
            return f"<{name}>{_esc(str(value))}</{name}>"
        return ""

    exact_registry_lookup = bool(str(numero_rg or "").strip() and str(anno_rg or "").strip())
    filtered_nome_parte = None if exact_registry_lookup else nome_parte
    filtered_cf_parte = None if exact_registry_lookup else cf_parte

    body_inner = "".join([
        tag("cfAvvocato", cf_avvocato),
        tag("codiceUfficio", codice_ufficio),
        tag("numeroRG", numero_rg),
        tag("annoRG", anno_rg),
        tag("nomeParte", filtered_nome_parte),
        tag("codiceFiscaleParte", filtered_cf_parte),
    ])

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:pst="http://it.giustizia.pst.service">
  <soapenv:Header/>
  <soapenv:Body>
    <pst:ricercaFascicoliRegistroRequest>
      {body_inner}
    </pst:ricercaFascicoliRegistroRequest>
  </soapenv:Body>
</soapenv:Envelope>"""


def _soap_documenti_body(base_url: str, codice_ufficio: str, numero_rg: str,
                          anno_rg: int, cf_avvocato: str = "", sub_procedimento: str = "") -> str:
    """Costruisce il body SOAP per ConsultazioneAvanzataDocumenti o qbuilder SICID."""
    namespace = _pst_namespace_qbuilder(base_url)
    if namespace:
        numero_value = str(int(str(numero_rg).strip())) if str(numero_rg).strip().isdigit() else str(numero_rg).strip()
        if _pst_servizio_siecic(base_url):
            return _soap_qbuilder_execute_body(
                namespace,
                "ElencoDocumenti",
                [
                    ("idUfficio", "string", codice_ufficio),
                    ("numeroRuolo", "string", numero_value),
                    ("annoRuolo", "integer", str(anno_rg)),
                ],
                role="AVV",
                group=codice_ufficio,
                order_entries=[("dataDeposito", "desc")],
            )
        values = [
            ("idUfficio", "string", codice_ufficio),
            ("anno", "string", str(anno_rg)),
            ("numero", "string", numero_value),
        ]
        if _pst_servizio_sigp(base_url):
            sigp_subpro = _pst_subpro_sigp(sub_procedimento)
            if sigp_subpro:
                values.append(("subpro", "integer", sigp_subpro))
        elif sub_procedimento:
            values.append(("subProc", "string", sub_procedimento))
        return _soap_qbuilder_execute_body(
            namespace,
            "DocumentiFascicolo",
            values,
            role="AVV",
            group=codice_ufficio,
            order_entries=[("DATADEPOSITO", "desc")],
        )

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:pst="http://it.giustizia.pst.service">
  <soapenv:Header/>
  <soapenv:Body>
    <pst:consultazioneDocumentiRequest>
      <cfAvvocato>{_esc(cf_avvocato)}</cfAvvocato>
      <codiceUfficio>{_esc(codice_ufficio)}</codiceUfficio>
      <numeroRG>{_esc(numero_rg)}</numeroRG>
      <annoRG>{anno_rg}</annoRG>
    </pst:consultazioneDocumentiRequest>
  </soapenv:Body>
    </soapenv:Envelope>"""


def _soap_sigp_ricerca_atti_body(codice_ufficio: str, numero_rg: str, anno_rg: int) -> str:
    body_inner = f"""
    <y:ricercaAtti xmlns:y="urn:sigp-consultazioneDocumenti">
      <inputRA>
        <numRuolo>{_esc(str(numero_rg).strip())}</numRuolo>
        <annoRuolo>{_esc(str(anno_rg).strip())}</annoRuolo>
      </inputRA>
    </y:ricercaAtti>"""
    return _soap_qbuilder_envelope(
        "urn:sigp-consultazioneDocumenti",
        body_inner,
        role="AVV",
        group=codice_ufficio,
    )


def _soap_profilo_fascicolo_body(base_url: str, codice_ufficio: str, numero_rg: str,
                                 anno_rg: int, sub_procedimento: str = "") -> str:
    namespace = _pst_namespace_qbuilder(base_url)
    if not namespace:
        return ""
    numero_value = str(int(str(numero_rg).strip())) if str(numero_rg).strip().isdigit() else str(numero_rg).strip()
    if _pst_servizio_siecic(base_url):
        values = [
            ("idUfficio", "string", codice_ufficio),
            ("numeroRuolo", "string", numero_value),
            ("annoRuolo", "integer", str(anno_rg)),
            ("scadTermini", "boolean", "false"),
        ]
    else:
        values = [
            ("idUfficio", "string", codice_ufficio),
            ("anno", "string", str(anno_rg)),
            ("numero", "string", numero_value),
            ("fascPrecedente", "boolean", "false"),
            ("scadTermini", "boolean", "false"),
        ]
        if _pst_servizio_sigp(base_url):
            sigp_subpro = _pst_subpro_sigp(sub_procedimento)
            if sigp_subpro:
                values.append(("subpro", "string", sigp_subpro))
        elif sub_procedimento:
            values.append(("subProc", "string", sub_procedimento))
    return _soap_qbuilder_execute_body(
        namespace,
        "ProfiloFascicolo",
        values,
        role="AVV",
        group=codice_ufficio,
        empty_order=True,
    )


def _parse_qbuilder_row(row_el: ET.Element) -> dict:
    row: dict = {"__class": row_el.get("class", "")}
    for prop in row_el.findall("property"):
        nome = (prop.get("name") or "").strip()
        if nome:
            row[nome] = (prop.text or "").strip()
    subrows: dict[str, list[dict]] = {}
    for sub in row_el.findall("subRows"):
        sub_class = (sub.get("class") or "").strip() or "row"
        rows = [_parse_qbuilder_row(child) for child in sub.findall("row")]
        if rows:
            subrows[sub_class] = rows
    if subrows:
        row["__subrows"] = subrows
    return row


def _parse_qbuilder_row_list(xml_str: str) -> list[dict]:
    root = _strip_namespaces(ET.fromstring(_normalizza_xml_pst(xml_str)))
    righe: list[dict] = []
    for ritorno in root.findall(".//return"):
        for child in list(ritorno):
            if child.tag == "subRows":
                continue
            if child.tag == "row":
                righe.append(_parse_qbuilder_row(child))
                continue
            for nested in list(child):
                if nested.tag == "row":
                    righe.append(_parse_qbuilder_row(nested))
    return righe


def _qbuilder_value(row: dict, *names: str) -> str:
    wanted = {str(name or "").strip().upper() for name in names if str(name or "").strip()}
    for key, value in row.items():
        if str(key).strip().upper() in wanted:
            text = str(value or "").strip()
            if text:
                return text
    return ""


def _qbuilder_subrows(row: dict, class_name: str) -> list[dict]:
    wanted = str(class_name or "").strip().upper()
    subrows = row.get("__subrows") if isinstance(row.get("__subrows"), dict) else {}
    for key, rows in subrows.items():
        if str(key).strip().upper() == wanted and isinstance(rows, list):
            return rows
    return []


def _qbuilder_numero_rg(valore: str) -> str:
    testo = (valore or "").strip()
    if not testo:
        return ""
    try:
        return str(int(testo))
    except ValueError:
        return testo.lstrip("0") or testo


def _qbuilder_tipo_documento(valore: str) -> str:
    testo = (valore or "").strip()
    if ":" in testo:
        testo = testo.rsplit(":", 1)[-1]
    if "}" in testo:
        testo = testo.split("}", 1)[-1]
    if testo in {"", "%", "*"}:
        return "Documento"
    return testo


def _qbuilder_parti_dettaglio(row: dict) -> list[dict]:
    dettaglio = []
    for parte in _qbuilder_subrows(row, "InfoParte"):
        nome = " ".join(
            chunk for chunk in [_qbuilder_value(parte, "COGNOME"), _qbuilder_value(parte, "NOME")]
            if chunk
        )
        dettaglio.append({
            "nome": nome,
            "tipo": _qbuilder_value(parte, "TIPO"),
            "codice_fiscale": _qbuilder_value(parte, "CODICEFISCALEPARTE", "codiceFiscaleParte"),
            "avvocato": _qbuilder_value(parte, "AVVOCATO"),
            "cf_avvocato": _qbuilder_value(parte, "CODICEFISCALEAVVOCATO", "codiceFiscaleAvvocato"),
        })
    return dettaglio


def _normalizza_data_pst(valore: str) -> str:
    raw = str(valore or "").strip()
    if not raw:
        return ""
    candidati = [raw, raw[:10]]
    for candidato in candidati:
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(candidato, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
    return raw


def _map_qbuilder_fascicolo(row: dict) -> dict:
    parti_dettaglio = _qbuilder_parti_dettaglio(row)
    codice_ufficio = _qbuilder_value(row, "IDUFFICIO", "idUfficio", "CODICEUFFICIO", "codiceUfficio", "UFFICIO")
    ufficio = _risolvi_ufficio_da_snapshot(codice_ufficio)
    return {
        "id_fascicolo": _qbuilder_value(row, "IDFASCICOLO", "idFascicolo", "IDDFA", "idDfa"),
        "numero_rg": _qbuilder_numero_rg(_qbuilder_value(row, "NUMERORUOLO", "numeroRuolo", "NUMERO", "numero")),
        "anno_rg": int(_qbuilder_value(row, "ANNORUOLO", "annoRuolo", "ANNO", "anno") or 0),
        "ruolo": _qbuilder_value(row, "RUOLODESCRIZIONE", "ruoloDescrizione", "DESCRRITO", "descrRito", "RUOLO", "DESCRUOLO", "RITO"),
        "stato": _qbuilder_value(row, "STATOFASCICOLODESCRIZIONE", "statoFascicoloDescrizione", "STATOFASCICOLO", "DESCSTATO", "descStato", "STATO"),
        "oggetto": _qbuilder_value(row, "OGGETTOFASCICOLO", "oggettoFascicolo", "DESCOGGETTO", "descOggetto", "OGGETTO"),
        "sezione": _qbuilder_value(row, "SEZIONE", "DESCRIZIONESEZIONE", "DESCSEZIONE", "descSezione"),
        "giudice": _qbuilder_value(row, "GIUDICE", "MAGISTRATO", "magistrato"),
        "data_iscrizione": _normalizza_data_pst(_qbuilder_value(row, "DATAISCRIZIONERUOLO", "DATAISCRIZIONE", "DataIscrizione", "dataIscrizione")),
        "data_udienza": _normalizza_data_pst(_qbuilder_value(row, "DATAPROSSIMAUDIENZA", "DATAUDIENZA", "dataUdienza", "DATAPRIMACOMPARIZIONE", "DATAULTIMAUDIENZA", "dataUltimaUdienza")),
        "codice_ufficio": codice_ufficio,
        "nome_ufficio": str((ufficio or {}).get("nome") or "").strip(),
        "sub_procedimento": _qbuilder_value(row, "SUBPROCEDIMENTO", "subProcedimento"),
        "parti": [parte["nome"] for parte in parti_dettaglio if parte.get("nome")],
        "parti_dettaglio": parti_dettaglio,
    }


def _map_qbuilder_documento(row: dict) -> dict:
    tipo = _qbuilder_tipo_documento(_qbuilder_value(row, "TIPO", "tipo", "TIPODOCUMENTO", "tipoDocumento", "TIPOATTO", "tipoAtto"))
    id_cat = _qbuilder_value(row, "IDCAT", "idCat", "IDCATEGORIA", "idCategoria")
    id_documento = _qbuilder_value(row, "IDDOCUMENTO", "IdDocumento", "idDocumento", "NUMERODOCUMENTO", "numeroDocumento", "IDDOC", "idDoc", "IDATTO", "idAtto", "IDDOCMITTENTE", "idDocMittente")
    numero_documento = _qbuilder_value(row, "NUMERODOCUMENTO", "numeroDocumento")
    id_doc_mittente = _qbuilder_value(row, "IDDOCMITTENTE", "idDocMittente")
    if id_doc_mittente.startswith("#"):
        id_doc_mittente = ""
    id_repeatto = _qbuilder_value(row, "IDREPEATTO", "ID_REPEATTO", "idRepeatTo", "idrepeatto")
    msg_id = _qbuilder_value(row, "MSGID", "MSG_ID", "msgId", "msgid")
    numero_doc = _qbuilder_numero_rg(numero_documento or id_documento)
    id_deposito = id_doc_mittente
    id_documento_candidates: list[str] = []
    for candidate in (
        _qbuilder_value(row, "IDDOCUMENTO", "IdDocumento", "idDocumento", "IDATTO", "idAtto", "IDDOC", "idDoc"),
        numero_documento,
        id_doc_mittente,
    ):
        if candidate and candidate not in id_documento_candidates:
            id_documento_candidates.append(candidate)
    if not id_cat and id_documento_candidates:
        # Nei flussi SICID l'idCat coincide spesso con l'id documento esposto
        # nella lista fascicolo: usiamolo subito per evitare round-trip inutili.
        id_cat = id_documento_candidates[0]
    return {
        "id_documento": id_documento,
        "nome": f"{tipo}_{numero_doc}.pdf" if numero_doc else tipo,
        "tipo": tipo,
        "data_deposito": _normalizza_data_pst(_qbuilder_value(row, "DATADEPOSITO", "dataDeposito")),
        "mittente": _qbuilder_value(row, "AUTORE", "autore", "MITTENTE", "mittente", "PROVENIENZA", "provenienza"),
        "dimensione_bytes": 0,
        "id_deposito": id_deposito,
        "tipo_atto": tipo,
        "disponibile": _qbuilder_value(row, "STATO", "stato", "DECODEATTIVO", "decodeAttivo").lower() not in {"non_disponibile", "no", "false", "0"},
        "stato": _qbuilder_value(row, "STATO", "stato", "DECODEATTIVO", "decodeAttivo"),
        "sub_procedimento": _qbuilder_value(row, "SUBPROCEDIMENTO", "subProcedimento"),
        "numero_documento": numero_documento,
        "id_doc_mittente": id_doc_mittente,
        "id_repeatto": id_repeatto,
        "msg_id": msg_id,
        "id_cat": id_cat,
        "id_documento_candidates": id_documento_candidates,
    }


def _matches_parte_filters(fascicolo: dict, nome_parte: str = "", cf_parte: str = "") -> bool:
    nome_tokens = [token for token in _normalizza_testo_ufficio(nome_parte).split() if token]
    cf_clean = _estrai_codice_fiscale_testo(cf_parte or "")
    if not nome_tokens and not cf_clean:
        return True
    for parte in fascicolo.get("parti_dettaglio", []):
        parte_nome = _normalizza_testo_ufficio(str(parte.get("nome") or ""))
        parte_cf = _estrai_codice_fiscale_testo(str(parte.get("codice_fiscale") or ""))
        if cf_clean and parte_cf != cf_clean:
            continue
        if nome_tokens and not all(token in parte_nome for token in nome_tokens):
            continue
        return True
    return False


def _parse_fascicoli_xml(xml_str: str) -> list[dict]:
    """Parsa la risposta SOAP RicercaFascicoliRegistro o qbuilder."""
    try:
        xml_clean = _normalizza_xml_pst(xml_str)
        if (
            "rowListType" in xml_clean
            or "InfoFascicoloExt" in xml_clean
            or "InfoFascicolo" in xml_clean
            or "ProfiloFascicolo" in xml_clean
            or "RicercaArchivioPC" in xml_clean
            or "RicercaArchivioEI" in xml_clean
        ):
            return [_map_qbuilder_fascicolo(row) for row in _parse_qbuilder_row_list(xml_clean)]

        root = _strip_namespaces(ET.fromstring(xml_clean))
        fascicoli = []
        for item in root.iter("fascicolo"):
            def _t(tag):
                el = item.find(tag)
                return (el.text or "").strip() if el is not None else ""

            fascicoli.append({
                "numero_rg": _t("numeroRG") or _t("numRG"),
                "anno_rg": int(_t("annoRG") or _t("anno") or 0),
                "ruolo": _t("ruolo") or _t("tipoRuolo"),
                "stato": _t("stato") or _t("statoFascicolo"),
                "oggetto": _t("oggetto") or _t("descOggetto"),
                "sezione": _t("sezione"),
                "giudice": _t("giudice") or _t("nomeGiudice"),
                "data_iscrizione": _normalizza_data_pst(_t("dataIscrizione")),
                "data_udienza": _normalizza_data_pst(_t("dataUdienza") or _t("dataProssimaUdienza")),
                "codice_ufficio": _t("codiceUfficio"),
                "nome_ufficio": _t("nomeUfficio") or _t("denominazioneUfficio"),
                "parti": [p.text.strip() for p in item.findall(".//parte") if p.text],
            })
        return fascicoli
    except Exception as e:
        log.warning("_parse_fascicoli_xml: %s", e)
        return []


def _parse_documenti_xml(xml_str: str) -> list[dict]:
    """Parsa la risposta SOAP ConsultazioneAvanzataDocumenti o qbuilder."""
    try:
        xml_clean = _normalizza_xml_pst(xml_str)
        if (
            "rowListType" in xml_clean
            or "DocumentoFascicolo" in xml_clean
            or "ElencoDocumenti" in xml_clean
            or "DocumentoUtente" in xml_clean
        ):
            return [_map_qbuilder_documento(row) for row in _parse_qbuilder_row_list(xml_clean)]

        root = _strip_namespaces(ET.fromstring(xml_clean))
        documenti: list[dict] = []
        visti: set[tuple[str, str, str, str, str, str]] = set()
        campi_documento = {
            "iddocumento",
            "id",
            "nomefile",
            "nome",
            "tipo",
            "tipodocumento",
            "datadeposito",
            "mittente",
            "cfmittente",
            "dimensione",
            "iddeposito",
            "idbusta",
            "tipoatto",
            "desctipoatto",
            "idcat",
            "disponibile",
        }

        for item in root.iter():
            children = list(item)
            if not children:
                continue

            child_map: dict[str, str] = {}
            for child in children:
                tag = (child.tag or "").split("}")[-1].lower()
                if tag not in child_map:
                    child_map[tag] = (child.text or "").strip()

            if not any(tag in child_map for tag in campi_documento):
                continue

            def _t(*tags):
                for tag in tags:
                    value = child_map.get(tag.lower(), "")
                    if value:
                        return value
                return ""

            try:
                dimensione = int(_t("dimensione") or 0)
            except ValueError:
                dimensione = 0

            documento = {
                "id_documento": _t("idDocumento", "id"),
                "nome": _t("nomeFile", "nome"),
                "tipo": _t("tipo", "tipoDocumento"),
                "data_deposito": _normalizza_data_pst(_t("dataDeposito")),
                "mittente": _t("mittente", "cfMittente"),
                "dimensione_bytes": dimensione,
                "id_deposito": _t("idDeposito", "idBusta"),
                "tipo_atto": _t("tipoAtto", "descTipoAtto"),
                "id_cat": _t("idCat") or _t("idDocumento", "id"),
                "id_repeatto": _t("idRepeatTo", "idrepeatto"),
                "msg_id": _t("msgId", "msgid"),
                "disponibile": _t("disponibile").lower() != "false",
            }
            if not any(
                documento[key]
                for key in ("id_documento", "nome", "tipo", "data_deposito", "mittente", "id_deposito", "tipo_atto")
            ):
                continue

            chiave = (
                documento["id_documento"],
                documento["nome"],
                documento["tipo"],
                documento["data_deposito"],
                documento["mittente"],
                documento["id_deposito"],
            )
            if chiave in visti:
                continue
            visti.add(chiave)
            documenti.append(documento)
        return documenti
    except Exception as e:
        log.warning("_parse_documenti_xml: %s", e)
        return []


def _parse_sigp_ricerca_atti_ids(xml_str: str) -> list[str]:
    try:
        root = _strip_namespaces(ET.fromstring(_normalizza_xml_pst(xml_str)))
        ids: list[str] = []
        for item in root.findall(".//item"):
            value = (item.text or "").strip()
            if value and value not in ids:
                ids.append(value)
        return ids
    except Exception as e:
        log.warning("_parse_sigp_ricerca_atti_ids: %s", e)
        return []


def _parse_profilo_documento_xml(xml_str: str) -> dict:
    try:
        root = _strip_namespaces(ET.fromstring(_normalizza_xml_pst(xml_str)))

        def _text(path: str) -> str:
            el = root.find(path)
            return (el.text or "").strip() if el is not None and el.text else ""

        def _first(*paths: str) -> str:
            for path in paths:
                value = _text(path)
                if value:
                    return value
            return ""

        data_deposito = _normalizza_data_pst(
            _first(".//dataDeposito", ".//dataCreazione", ".//dataAggiornamentoFascicolo")
        )
        dimensione = 0
        try:
            dimensione = int(_first(".//dimensioneFile", ".//dimensione") or 0)
        except ValueError:
            dimensione = 0
        return {
            "id_documento": _text(".//idDocumento"),
            "id_cat": _text(".//idCat"),
            "id_repeatto": _text(".//idRepeatTo") or _text(".//idrepeatto"),
            "msg_id": _text(".//msgId") or _text(".//msgid"),
            "content_id": _text(".//contentId"),
            "nome_file_originale": _text(".//nomeFileOriginale"),
            "codice_ufficio": _text(".//codiceUfficio"),
            "data_documento": data_deposito,
            "data_deposito": data_deposito,
            "tipo": _first(".//datiSGR/tipoAtto/descrizione", ".//tipoOggetto/descrizione"),
            "tipo_atto": _first(".//datiSGR/tipoAtto/descrizione", ".//tipoOggetto/descrizione"),
            "mittente": _first(".//utentePubblicatore/cognome", ".//codFiscMittente", ".//autoreVersione"),
            "id_deposito": _text(".//idBusta"),
            "id_fascicolo": _text(".//idFascicolo"),
            "dimensione_bytes": dimensione,
            "tipo_mime": _text(".//tipoMIME"),
        }
    except Exception as e:
        log.warning("_parse_profilo_documento_xml: %s", e)
        return {}


def _documento_da_profilo_sigp(profilo: dict, id_doc: str) -> dict:
    document_id = str(profilo.get("id_documento") or id_doc or "").strip()
    id_cat = str(profilo.get("id_cat") or document_id).strip()
    nome_originale = str(profilo.get("nome_file_originale") or "").strip()
    tipo = _qbuilder_tipo_documento(str(profilo.get("tipo_atto") or profilo.get("tipo") or "Documento"))
    if nome_originale:
        nome = nome_originale
    elif document_id:
        nome = f"{tipo}_{document_id}.pdf"
    else:
        nome = tipo
    id_documento_candidates: list[str] = []
    for candidate in (document_id, id_cat, str(profilo.get("id_repeatto") or "").strip()):
        if candidate and candidate not in id_documento_candidates:
            id_documento_candidates.append(candidate)
    return {
        "id_documento": document_id,
        "nome": nome,
        "tipo": tipo,
        "data_deposito": str(profilo.get("data_deposito") or profilo.get("data_documento") or "").strip(),
        "mittente": str(profilo.get("mittente") or "").strip(),
        "dimensione_bytes": int(profilo.get("dimensione_bytes") or 0),
        "id_deposito": str(profilo.get("id_deposito") or "").strip(),
        "tipo_atto": tipo,
        "disponibile": True,
        "stato": "depositato",
        "sub_procedimento": "",
        "numero_documento": document_id,
        "id_doc_mittente": "",
        "id_repeatto": str(profilo.get("id_repeatto") or "").strip(),
        "msg_id": str(profilo.get("msg_id") or "").strip(),
        "id_cat": id_cat,
        "content_type": str(profilo.get("tipo_mime") or "").strip(),
        "id_documento_candidates": id_documento_candidates,
        "fonte_catalogo": "sigp_ricerca_atti",
    }


def _sigp_documenti_minimi_da_ids(ids: list[str]) -> list[dict]:
    documenti: list[dict] = []
    for id_doc_raw in ids or []:
        id_doc = str(id_doc_raw or "").strip()
        if not id_doc:
            continue
        documento = _documento_da_profilo_sigp(
            {
                "id_documento": id_doc,
                "id_cat": id_doc,
                "id_repeatto": id_doc,
                "tipo": "Atto",
            },
            id_doc,
        )
        documento["fonte_catalogo"] = "sigp_ricerca_atti_batch"
        documenti.append(documento)
    return documenti


def _sigp_documenti_minimi_da_ricerca_atti_xml(xml_str: str) -> list[dict]:
    return _sigp_documenti_minimi_da_ids(_parse_sigp_ricerca_atti_ids(xml_str))


def _pst_effective_id_cat(item: Optional[dict], id_documento: str = "") -> str:
    raw = dict(item or {})
    explicit = str(raw.get("id_cat") or "").strip()
    if explicit:
        return explicit
    if id_documento and not raw.get("id_documento"):
        raw["id_documento"] = id_documento
    for candidate in _pst_document_id_candidates(raw):
        return candidate
    return ""


def _normalizza_http_content_type(content_type: str) -> str:
    header = (content_type or "").strip()
    if ":" in header:
        nome, valore = header.split(":", 1)
        if nome.strip().lower() == "content-type":
            header = valore.strip()
    return header or "multipart/related"


def _mime_headers_from_http_content_type(content_type: str) -> bytes:
    header = _normalizza_http_content_type(content_type)
    return (
        f"Content-Type: {header}\r\n"
        "MIME-Version: 1.0\r\n"
        "\r\n"
    ).encode("utf-8")


def _parse_download_documento_response(body_bytes: bytes, content_type: str = "") -> dict:
    raw = (body_bytes or b"").lstrip(b"\r\n")
    if not raw:
        raise RuntimeError("Il PST non ha restituito alcun contenuto per il download del documento.")

    content_type_value = _normalizza_http_content_type(content_type)

    if raw.startswith(b"--"):
        raw = _mime_headers_from_http_content_type(content_type_value) + raw

    msg = BytesParser(policy=policy.default).parsebytes(raw)
    if not msg.is_multipart():
        payload = msg.get_payload(decode=True) or b""
        if payload:
            return {
                "soap_xml": "",
                "content": payload,
                "content_type": msg.get_content_type() or content_type_value or "application/octet-stream",
                "content_id": "",
            }
        raise RuntimeError("Risposta PST non multipart e priva di allegato documento.")

    soap_xml = ""
    attachment_part = None
    href_cid = ""

    for part in msg.iter_parts():
        ctype = (part.get_content_type() or "").lower()
        payload = part.get_payload(decode=True) or b""
        if ctype in {"text/xml", "application/soap+xml"}:
            soap_xml = payload.decode("utf-8", "replace")
            try:
                root = _strip_namespaces(ET.fromstring(_normalizza_xml_pst(soap_xml)))
                href = root.find(".//return")
                href_cid = str((href.get("href") if href is not None else "") or "").strip()
                if href_cid.lower().startswith("cid:"):
                    href_cid = href_cid[4:].strip("<>")
            except Exception:
                href_cid = ""
            continue
        if attachment_part is None:
            attachment_part = part

    if href_cid:
        for part in msg.iter_parts():
            cid = str(part.get("Content-ID") or "").strip().strip("<>")
            if cid == href_cid:
                attachment_part = part
                break

    if attachment_part is None:
        raise RuntimeError("Il PST ha restituito la risposta SOAP ma non l'allegato documento.")

    payload = attachment_part.get_payload(decode=True) or b""
    if not payload:
        raise RuntimeError("L'allegato restituito dal PST è vuoto.")

    return {
        "soap_xml": soap_xml,
        "content": payload,
        "content_type": attachment_part.get_content_type() or content_type_value or "application/octet-stream",
        "content_id": str(attachment_part.get("Content-ID") or "").strip().strip("<>"),
        "filename": str(attachment_part.get_filename() or "").strip(),
    }


def _looks_like_pkcs7_signed(payload: bytes, content_type: str = "", filename: str = "") -> bool:
    header = (content_type or "").lower()
    name = (filename or "").lower()
    if any(token in header for token in ("pkcs7", "p7m", "smime", "cms")):
        return True
    if name.endswith(".p7m"):
        return True
    if not payload:
        return False
    try:
        from asn1crypto import cms
    except Exception:
        return False
    try:
        info = cms.ContentInfo.load(payload)
        return info["content_type"].native == "signed_data"
    except Exception:
        return False


def _soap_bea_sicid_body(operation: str, parameters: list[tuple[str, str]], *, group: str, role: str = "AVV") -> str:
    params_xml = "".join(
        f"<{_esc(name)}>{_esc(str(value))}</{_esc(name)}>"
        for name, value in parameters
        if value not in ("", None)
    )
    body_inner = (
        f'<impl:{_esc(operation)} xmlns:impl="urn:BEAFascicoloInformatico-distr">'
        f"{params_xml}"
        f"</impl:{_esc(operation)}>"
    )
    return _soap_qbuilder_envelope("urn:BEAFascicoloInformatico-distr", body_inner, role=role, group=group)


def _soap_bea_siecic_body(operation: str, parameters: list[tuple[str, str]]) -> str:
    params_xml = "".join(
        f"<{_esc(name)}>{_esc(str(value))}</{_esc(name)}>"
        for name, value in parameters
        if value not in ("", None)
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:intf="http://elsagdatamat.com/bea/pct/siecic/ws/fascicolo">
  <soapenv:Header/>
  <soapenv:Body>
    <intf:{_esc(operation)}>
      {params_xml}
    </intf:{_esc(operation)}>
  </soapenv:Body>
</soapenv:Envelope>"""


def _soap_sigp_download_body(id_repeatto: str, codice_ufficio: str) -> str:
    body_inner = f"""
    <y:downloadAtto xmlns:y="urn:sigp-consultazioneDocumenti">
      <idrepeatto>{_esc(id_repeatto)}</idrepeatto>
    </y:downloadAtto>"""
    return _soap_qbuilder_envelope(
        "urn:sigp-consultazioneDocumenti",
        body_inner,
        role="AVV",
        group=codice_ufficio,
    )


def _pst_download_documento_payload(
    *,
    base_url: str,
    codice_ufficio: str,
    id_documento: str,
    nome_documento: str,
    cert_thumbprint: str,
    cf_avvocato: str,
    id_cat: str = "",
    id_repeatto: str = "",
    msg_id: str = "",
    data_documento: str = "",
    original: bool = False,
    cookie_file: Optional[str] = None,
    prefer_cookie_only: bool = False,
) -> dict:
    servizio = _pst_servizio_proxy(base_url)
    document_id_output = str(id_documento or id_cat or id_repeatto or "").strip()
    url_documenti = _pst_url_documenti(base_url)
    extra_headers: list[str] = []
    soap_action = ""
    profilo: dict = {}
    download_cookie_file = _pst_download_cookie_file(base_url, cookie_file)
    download_prefer_cookie_only = bool(prefer_cookie_only) and _pst_download_can_use_cookie_only(
        base_url,
        download_cookie_file,
    )

    if _pst_servizio_sicid_family(base_url):
        registro = _pst_registro_documenti_sicid(base_url)
        if not cf_avvocato:
            raise RuntimeError(
                "Il download ufficiale del documento richiede il codice fiscale dell'avvocato nell'header X-WASP-User."
            )
        extra_headers = [f"X-WASP-User: {cf_avvocato}"]
        id_cat = _pst_effective_id_cat({"id_cat": id_cat, "id_documento": id_documento}, id_documento)
        if not id_cat:
            profilo_xml = _soap_call_pst_session(
                url=url_documenti,
                soap_body=_soap_bea_sicid_body(
                    "estraiProfiloDocumento",
                    [
                        ("idUtenteCorrente", cf_avvocato),
                        ("idDoc", id_documento),
                        ("registro", registro),
                        ("ruoloApplicativo", "AVV"),
                    ],
                    group=codice_ufficio,
                ),
                cert_thumbprint=cert_thumbprint,
                extra_headers=extra_headers,
                cookie_file=download_cookie_file,
                prefer_cookie_only=download_prefer_cookie_only,
            )
            profilo = _parse_profilo_documento_xml(profilo_xml)
            id_cat = str(profilo.get("id_cat") or "").strip()
        if not id_cat:
            raise RuntimeError("Il PST non ha restituito l'identificativo idCat necessario al download del documento.")
        soap_body = _soap_bea_sicid_body(
            "downloadDocumento",
            [
                ("idUtenteCorrente", cf_avvocato),
                ("idCat", id_cat),
                ("original", "true" if original else "false"),
            ],
            group=codice_ufficio,
        )
    elif servizio == "JPW_SIECIC":
        if not cf_avvocato:
            raise RuntimeError(
                "Il download ufficiale del documento richiede il codice fiscale dell'avvocato nell'header X-WASP-User."
            )
        extra_headers = [f"X-WASP-User: {cf_avvocato}"]
        soap_body = _soap_bea_siecic_body(
            "downloadDocumento",
            [
                ("idDoc", id_documento),
                ("original", "true" if original else "false"),
            ],
        )
        if not data_documento or not nome_documento:
            profilo_xml = _soap_call_pst_session(
                url=url_documenti,
                soap_body=_soap_bea_siecic_body("estraiProfiloDocumento", [("idDoc", id_documento)]),
                cert_thumbprint=cert_thumbprint,
                extra_headers=extra_headers,
                cookie_file=download_cookie_file,
                prefer_cookie_only=download_prefer_cookie_only,
            )
            profilo = _parse_profilo_documento_xml(profilo_xml)
    elif servizio == "JPW_SIGP":
        soap_action = "downloadAtto"
        download_id_repeatto = str(id_repeatto or id_documento).strip()
        if not download_id_repeatto:
            raise RuntimeError("Il servizio SIGP richiede idRepeatTo per il download dell'atto.")
        soap_body = _soap_sigp_download_body(download_id_repeatto, codice_ufficio)
    else:
        raise RuntimeError(f"Servizio PST non supportato per il download diretto: {servizio or 'sconosciuto'}.")

    if servizio == "JPW_SIGP" and cf_avvocato and (id_documento or id_repeatto):
        _soap_call_pst_session(
            url=url_documenti,
            soap_body=_soap_bea_sicid_body(
                "calcolaHash",
                [
                    ("idUtenteCorrente", cf_avvocato),
                    ("idDoc", id_documento or id_repeatto),
                ],
                group=codice_ufficio,
            ),
            cert_thumbprint=cert_thumbprint,
            extra_headers=[f"X-WASP-User: {cf_avvocato}"],
            cookie_file=download_cookie_file,
            prefer_cookie_only=download_prefer_cookie_only,
        )

    body_bytes, headers_text = _soap_call_pst_session_raw(
        url=url_documenti,
        soap_body=soap_body,
        cert_thumbprint=cert_thumbprint,
        extra_headers=extra_headers,
        soap_action=soap_action,
        cookie_file=download_cookie_file,
        prefer_cookie_only=download_prefer_cookie_only,
        max_time=PST_DOWNLOAD_MAX_TIME,
        connect_timeout=PST_DOWNLOAD_CONNECT_TIMEOUT,
    )
    content_type = _http_header_value(headers_text, "Content-Type")
    parsed = _parse_download_documento_response(body_bytes, content_type)

    nome_finale = str(parsed.get("filename") or "").strip()
    if not nome_finale:
        nome_finale = (nome_documento or "").strip()
    if not nome_finale:
        nome_finale = str(profilo.get("nome_file_originale") or "").strip()
    if not nome_finale:
        nome_finale = f"documento_{document_id_output or 'pst'}"
    if _looks_like_pkcs7_signed(parsed["content"], parsed.get("content_type", ""), nome_finale):
        if not nome_finale.lower().endswith(".p7m"):
            nome_finale += ".p7m"
    elif parsed["content"].startswith(b"%PDF") and not nome_finale.lower().endswith(".pdf"):
        nome_finale += ".pdf"

    return {
        "nome": nome_finale,
        "contenuto_b64": base64.b64encode(parsed["content"]).decode("ascii"),
        "content_type": parsed.get("content_type") or "application/octet-stream",
        "id_documento_portale": document_id_output,
        "id_cat": id_cat or str(profilo.get("id_cat") or "").strip(),
        "id_repeatto": str(id_repeatto or profilo.get("id_repeatto") or "").strip(),
        "msg_id": str(msg_id or profilo.get("msg_id") or "").strip(),
        "data_documento": data_documento or str(profilo.get("data_documento") or "").strip(),
        "nome_file_originale": str(profilo.get("nome_file_originale") or "").strip(),
        "original_documento_portale": bool(original),
        "modalita_documento_portale": "originale" if original else "copia",
        "servizio_portale": "DocumentiFascicolo",
    }


def _assemble_download_file_payload(
    parsed: dict,
    item: dict,
    id_documento: str,
    nome_documento: str,
    base_url: str,
    *,
    original: bool = False,
) -> dict:
    """Costruisce il payload file da una risposta PST parsed."""
    document_id_output = str(
        id_documento
        or item.get("id_cat")
        or item.get("id_repeatto")
        or item.get("msg_id")
        or ""
    ).strip()
    nome_finale = str(parsed.get("filename") or "").strip()
    if not nome_finale:
        nome_finale = (nome_documento or "").strip()
    if not nome_finale:
        nome_finale = f"documento_{document_id_output or 'pst'}"
    if _looks_like_pkcs7_signed(parsed["content"], parsed.get("content_type", ""), nome_finale):
        if not nome_finale.lower().endswith(".p7m"):
            nome_finale += ".p7m"
    elif parsed["content"].startswith(b"%PDF") and not nome_finale.lower().endswith(".pdf"):
        nome_finale += ".pdf"
    return {
        "nome": nome_finale,
        "contenuto_b64": base64.b64encode(parsed["content"]).decode("ascii"),
        "content_type": parsed.get("content_type") or "application/octet-stream",
        "id_documento_portale": document_id_output,
        "id_cat": str(item.get("id_cat") or "").strip(),
        "id_repeatto": str(item.get("id_repeatto") or "").strip(),
        "msg_id": str(item.get("msg_id") or "").strip(),
        "data_documento": str(item.get("data_deposito") or item.get("data_documento") or "").strip(),
        "nome_file_originale": str(parsed.get("filename") or "").strip(),
        "original_documento_portale": bool(original),
        "modalita_documento_portale": "originale" if original else "copia",
        "servizio_portale": "DocumentiFascicolo",
        "origine": f"pst:{_pst_servizio_proxy(base_url) or 'download'}:{document_id_output or 'documento'}",
        "id_deposito_esterno": str(item.get("id_deposito_esterno") or "").strip(),
        "id_deposito_pct": str(item.get("id_deposito_pct") or "").strip(),
        "tipo_atto": str(item.get("tipo_atto") or "").strip(),
    }


def _pst_document_id_candidates(item: dict) -> list[str]:
    candidates: list[str] = []
    raw_candidates = item.get("id_documento_candidates")
    if isinstance(raw_candidates, (list, tuple)):
        for value in raw_candidates:
            candidate = str(value or "").strip()
            if candidate and not candidate.startswith("#") and candidate not in candidates:
                candidates.append(candidate)
    for value in (
        item.get("id_documento"),
        item.get("id_documento_portale"),
        item.get("numero_documento"),
        item.get("id_doc_mittente"),
    ):
        candidate = str(value or "").strip()
        if candidate and not candidate.startswith("#") and candidate not in candidates:
            candidates.append(candidate)
    return candidates


def _pst_primary_document_id(item: Optional[dict]) -> str:
    for candidate in _pst_document_id_candidates(dict(item or {})):
        return candidate
    return ""


def _sigp_document_merge_candidates(item: dict) -> list[str]:
    candidates = _pst_document_id_candidates(item)
    for field in ("id_cat", "id_repeatto", "msg_id"):
        candidate = str(item.get(field) or "").strip()
        if candidate and not candidate.startswith("#") and candidate not in candidates:
            candidates.append(candidate)
    return candidates


def _sigp_merge_documenti_con_profili(documenti: list[dict], profili: list[dict]) -> list[dict]:
    merged: list[dict] = []
    index: dict[str, dict] = {}
    for doc in documenti or []:
        doc_copy = dict(doc)
        candidates = _sigp_document_merge_candidates(doc_copy)
        target = next((index[candidate] for candidate in candidates if candidate in index), None)
        if target is not None:
            for key, value in doc_copy.items():
                if key == "id_documento_candidates":
                    continue
                if target.get(key) in ("", None, 0) and value not in ("", None, 0):
                    target[key] = value
            target.setdefault("id_documento_candidates", [])
            for candidate in candidates:
                if candidate and candidate not in target["id_documento_candidates"]:
                    target["id_documento_candidates"].append(candidate)
                    index.setdefault(candidate, target)
            continue
        merged.append(doc_copy)
        doc_copy.setdefault("id_documento_candidates", [])
        for candidate in candidates:
            if candidate and candidate not in doc_copy["id_documento_candidates"]:
                doc_copy["id_documento_candidates"].append(candidate)
            index.setdefault(candidate, doc_copy)

    for profilo_doc in profili or []:
        candidates = _sigp_document_merge_candidates(profilo_doc)
        target = next((index[candidate] for candidate in candidates if candidate in index), None)
        if target is None:
            merged.append(dict(profilo_doc))
            for candidate in candidates:
                index.setdefault(candidate, merged[-1])
            continue
        nome_originale = str(profilo_doc.get("nome") or "").strip()
        if nome_originale:
            target["nome"] = nome_originale
            target["nome_file_originale"] = nome_originale
        for campo in (
            "dimensione_bytes",
            "id_deposito",
            "id_cat",
            "id_repeatto",
            "msg_id",
            "content_type",
            "fonte_catalogo",
        ):
            value = profilo_doc.get(campo)
            if value not in ("", None, 0):
                target[campo] = value
        target.setdefault("id_documento_candidates", [])
        for candidate in candidates:
            if candidate and candidate not in target["id_documento_candidates"]:
                target["id_documento_candidates"].append(candidate)
    return merged


def _sigp_documenti_da_ricerca_atti(
    *,
    base_url: str,
    codice_ufficio: str,
    numero_rg: str,
    anno_rg: int,
    cf_avvocato: str,
    cert_thumbprint: str,
    cookie_file: str = "",
    prefer_cookie_only: bool = False,
) -> list[dict]:
    url_documenti = _pst_url_documenti(base_url)
    headers = [f"X-WASP-User: {cf_avvocato}"] if cf_avvocato else []
    xml_ids = _soap_call_pst_session(
        url=url_documenti,
        soap_body=_soap_sigp_ricerca_atti_body(codice_ufficio, numero_rg, anno_rg),
        cert_thumbprint=cert_thumbprint,
        extra_headers=headers,
        soap_action="ricercaAtti",
        cookie_file=cookie_file,
        prefer_cookie_only=prefer_cookie_only,
    )
    fault = _estrai_fault_soap(xml_ids)
    if fault:
        raise RuntimeError(f"Il PST ha restituito una SOAP Fault: {fault}")
    ids = _parse_sigp_ricerca_atti_ids(xml_ids)
    if not ids:
        return []

    requests = [
        {
            "url": url_documenti,
            "soap_body": _soap_bea_sicid_body(
                "estraiProfiloDocumento",
                [
                    ("idUtenteCorrente", cf_avvocato),
                    ("idDoc", id_doc),
                    ("registro", "GDP"),
                    ("ruoloApplicativo", "AVV"),
                ],
                group=codice_ufficio,
            ),
            "extra_headers": headers,
            "soap_action": "",
        }
        for id_doc in ids
    ]
    results = _soap_call_pst_session_batch_raw_best_effort(
        requests,
        cert_thumbprint=cert_thumbprint,
        cookie_file=cookie_file,
        prefer_cookie_only=prefer_cookie_only,
    )
    documenti: list[dict] = []
    for id_doc, result in zip(ids, results):
        if result.get("error"):
            log.debug("Profilo documento SIGP %s non importato: %s", id_doc, result["error"])
            continue
        xml = (result.get("body_bytes") or b"").decode("utf-8", "replace")
        profilo = _parse_profilo_documento_xml(xml)
        if not profilo:
            continue
        documenti.append(_documento_da_profilo_sigp(profilo, id_doc))
    return documenti


def _pst_download_documenti_batch_payloads(
    *,
    base_url: str,
    codice_ufficio: str,
    cert_thumbprint: str,
    cf_avvocato: str,
    documenti: list[dict],
    do_preflight: bool = True,
    cookie_file: Optional[str] = None,
    original: bool = False,
) -> dict:
    """
    Scarica N documenti PST con UN SOLO processo curl per l'intero batch.

    Questo elimina i prompt PIN ripetuti su Windows (Aruba Key, CNS/CIE):
    invece di lanciare N subprocess curl (uno per documento) → N richieste PIN,
    si costruisce un unico file di configurazione curl con 'next' che concatena
    tutti i download → Windows chiede il PIN una sola volta per tutta la sessione.
    """
    if not isinstance(documenti, list) or not documenti:
        raise RuntimeError("Il lotto download richiede almeno un documento ufficiale.")

    files: list[dict] = []
    failures: list[dict] = []
    preflight: Optional[dict] = None
    _tmp_cookie: Optional[str] = None
    if do_preflight and not cookie_file:
        _tmp_cookie = _ensure_cookie_file()
        cookie_file = _tmp_cookie

    try:
        if do_preflight:
            preflight = _pst_preflight_auth_curl(
                url=_pst_url_ricerca(base_url),
                cert_thumbprint=cert_thumbprint,
                cookie_file=cookie_file,
            )
        servizio = _pst_servizio_proxy(base_url)
        policy = _pst_tabella_ministeriale_policy(base_url)
        url_documenti = _pst_url_documenti(base_url)
        download_cookie_file = _pst_download_cookie_file(base_url, cookie_file)
        prefer_cookie_only = _pst_download_can_use_cookie_only(base_url, download_cookie_file)
        usa_wasp = bool(policy.get("x_wasp_user")) or _pst_servizio_sicid_family(base_url) or servizio == "JPW_SIECIC"
        extra_base = [f"X-WASP-User: {cf_avvocato}"] if (usa_wasp and cf_avvocato) else []

        # ── Fase 1: risolvi id_cat e metadati mancanti per SICID/SIECIC ──
        # Un solo processo curl per tutti i profili da recuperare.
        if usa_wasp:
            need_prof: list[int] = []
            for i, raw in enumerate(documenti):
                if not isinstance(raw, dict):
                    continue
                id_doc = _pst_primary_document_id(raw)
                id_cat = _pst_effective_id_cat(raw, id_doc)
                if not id_doc and not id_cat:
                    continue
                miss_cat = not id_cat
                miss_meta = not str(raw.get("nome_documento") or raw.get("nome") or "").strip()
                if miss_cat or (servizio == "JPW_SIECIC" and miss_meta):
                    need_prof.append(i)

            if need_prof:
                prof_reqs: list[dict] = []
                prof_meta: list[tuple[int, str]] = []
                for i in need_prof:
                    item = documenti[i]
                    for id_doc in _pst_document_id_candidates(item):
                        if _pst_servizio_sicid_family(base_url):
                            registro = _pst_registro_documenti_sicid(base_url)
                            soap = _soap_bea_sicid_body(
                                "estraiProfiloDocumento",
                                [
                                    ("idUtenteCorrente", cf_avvocato),
                                    ("idDoc", id_doc),
                                    ("registro", registro),
                                    ("ruoloApplicativo", "AVV"),
                                ],
                                group=codice_ufficio,
                            )
                        else:
                            soap = _soap_bea_siecic_body(
                                "estraiProfiloDocumento", [("idDoc", id_doc)]
                            )
                        prof_reqs.append({
                            "url": url_documenti,
                            "soap_body": soap,
                            "extra_headers": extra_base,
                            "soap_action": "",
                            "cookie_file": download_cookie_file,
                        })
                        prof_meta.append((i, id_doc))
                try:
                    prof_results = _soap_call_pst_session_batch_raw_best_effort(
                        prof_reqs,
                        cert_thumbprint=cert_thumbprint,
                        cookie_file=download_cookie_file,
                        prefer_cookie_only=prefer_cookie_only,
                    )
                    resolved_profili: set[int] = set()
                    unresolved_errors: dict[int, list[str]] = {}
                    for k, result in enumerate(prof_results):
                        idx, candidate_id = prof_meta[k]
                        if idx in resolved_profili:
                            continue
                        error = str(result.get("error") or "").strip()
                        if error:
                            unresolved_errors.setdefault(idx, []).append(f"{candidate_id}: {error}")
                            continue
                        body_bytes = result.get("body_bytes") or b""
                        xml_resp = body_bytes.decode("utf-8", "replace")
                        profilo = _parse_profilo_documento_xml(xml_resp)
                        if not profilo.get("id_cat") and not profilo.get("nome_file_originale"):
                            unresolved_errors.setdefault(idx, []).append(
                                f"{candidate_id}: profilo documento privo di idCat"
                            )
                            continue
                        item = documenti[idx]
                        if isinstance(item, dict):
                            updated = dict(item)
                            if profilo.get("id_cat"):
                                updated["id_cat"] = profilo["id_cat"]
                            if profilo.get("data_documento") and not str(item.get("data_deposito") or "").strip():
                                updated["data_deposito"] = profilo["data_documento"]
                            if profilo.get("nome_file_originale") and not str(item.get("nome") or item.get("nome_documento") or "").strip():
                                updated["nome"] = profilo["nome_file_originale"]
                            documenti[idx] = updated
                            resolved_profili.add(idx)
                    if unresolved_errors:
                        for idx, errors in unresolved_errors.items():
                            if idx in resolved_profili:
                                continue
                            log.warning(
                                "Profilo PST non risolto per %s: %s",
                                str(documenti[idx].get("id_documento") or ""),
                                " | ".join(errors[:3]),
                            )
                except Exception as e:
                    log.warning("Batch profile fetch PST fallito (continuo senza id_cat): %s", e)

        # ── Fase 2: costruisci SOAP body per ogni documento da scaricare ──
        dl_reqs: list[dict] = []
        dl_meta: list[dict] = []

        allow_single_fallback = False
        allow_runtime_single_fallback = False

        for raw in documenti:
            item = raw if isinstance(raw, dict) else {}
            id_doc = _pst_primary_document_id(item)
            id_cat = _pst_effective_id_cat(item, id_doc)
            id_output = id_doc or id_cat or str(item.get("id_repeatto") or "").strip()
            nome_doc = str(item.get("nome_documento") or item.get("nome") or "").strip()
            try:
                if servizio == "JPW_SIGP":
                    id_repeatto = str(item.get("id_repeatto") or id_doc or id_cat).strip()
                    if not id_repeatto:
                        raise RuntimeError("idRepeatTo mancante nel lotto SIGP.")
                    soap_body = _soap_sigp_download_body(id_repeatto, codice_ufficio)
                    soap_action = "downloadAtto"
                    extra_h: list[str] = []
                elif _pst_servizio_sicid_family(base_url):
                    if not id_cat:
                        if allow_single_fallback:
                            # Mantenuto disattivato: anche un lotto singolo deve
                            # restare nel percorso batch per non riaprire prompt PIN.
                            files.append(
                                _pst_download_documento_payload(
                                    base_url=base_url,
                                    codice_ufficio=codice_ufficio,
                                    id_documento=id_doc or id_cat or str(item.get("id_repeatto") or "").strip(),
                                    nome_documento=nome_doc,
                                    cert_thumbprint=cert_thumbprint,
                                    cf_avvocato=cf_avvocato,
                                    id_cat=id_cat,
                                    id_repeatto=str(item.get("id_repeatto") or "").strip(),
                                    msg_id=str(item.get("msg_id") or "").strip(),
                                    data_documento=str(
                                        item.get("data_deposito") or item.get("data_documento") or ""
                                    ).strip(),
                                    original=original,
                                    cookie_file=download_cookie_file,
                                    prefer_cookie_only=prefer_cookie_only,
                                )
                            )
                        else:
                            failures.append({
                                "id_documento": id_doc,
                                "nome_documento": nome_doc,
                                "errore": (
                                    "idCat mancante nel lotto PST. "
                                    "Il batch non ricade sul download singolo per evitare richieste PIN ripetute."
                                ),
                            })
                        continue
                    soap_body = _soap_bea_sicid_body(
                        "downloadDocumento",
                        [
                            ("idUtenteCorrente", cf_avvocato),
                            ("idCat", id_cat),
                            ("original", "true" if original else "false"),
                        ],
                        group=codice_ufficio,
                    )
                    soap_action = ""
                    extra_h = extra_base
                elif servizio == "JPW_SIECIC":
                    if not id_doc:
                        raise RuntimeError("idDoc mancante nel lotto SIECIC.")
                    soap_body = _soap_bea_siecic_body(
                        "downloadDocumento",
                        [("idDoc", id_doc), ("original", "true" if original else "false")],
                    )
                    soap_action = ""
                    extra_h = extra_base
                else:
                    raise RuntimeError(
                        f"Servizio PST non supportato per il download batch: {servizio or 'sconosciuto'}."
                    )
                dl_reqs.append({
                    "url": url_documenti,
                    "soap_body": soap_body,
                    "soap_action": soap_action,
                    "extra_headers": extra_h,
                    "cookie_file": download_cookie_file,
                    "max_time": PST_DOWNLOAD_MAX_TIME,
                    "connect_timeout": PST_DOWNLOAD_CONNECT_TIMEOUT,
                })
                dl_meta.append({"id_documento": id_output, "nome_documento": nome_doc, "item": item})
            except Exception as e:
                failures.append({"id_documento": id_output, "nome_documento": nome_doc, "errore": str(e)})

        if not dl_reqs:
            return {
                "ok": True, "files": files, "failures": failures,
                "preflight": preflight,
                "documenti_richiesti": len(documenti), "documenti_scaricati": len(files),
            }

        # ── Fase 3: UN SOLO processo curl per tutti i download ──
        try:
            warmup_reqs: list[dict] = []
            warmup_policy = str(policy.get("warmup") or "").strip()
            needs_hash_warmup = bool(
                cf_avvocato
                and (
                    warmup_policy == "calcolaHash_always"
                    or (warmup_policy == "calcolaHash_multi" and len(dl_reqs) > 1)
                )
            )
            if needs_hash_warmup:
                first_doc_id = str(
                    dl_meta[0]["item"].get("id_documento")
                    or dl_meta[0]["item"].get("id_documento_portale")
                    or dl_meta[0]["id_documento"]
                    or ""
                ).strip()
                if first_doc_id:
                    warmup_reqs.append({
                        "url": url_documenti,
                        "soap_body": _soap_bea_sicid_body(
                            "calcolaHash",
                            [
                                ("idUtenteCorrente", cf_avvocato),
                                ("idDoc", first_doc_id),
                            ],
                            group=codice_ufficio,
                        ),
                        "soap_action": "",
                        "extra_headers": extra_base or [f"X-WASP-User: {cf_avvocato}"],
                        "cookie_file": download_cookie_file,
                        "max_time": PST_DOWNLOAD_MAX_TIME,
                        "connect_timeout": PST_DOWNLOAD_CONNECT_TIMEOUT,
                    })
            batch_result_items = _soap_call_pst_session_batch_raw_best_effort(
                [*warmup_reqs, *dl_reqs],
                cert_thumbprint=cert_thumbprint,
                cookie_file=download_cookie_file,
                prefer_cookie_only=prefer_cookie_only,
            )
            if warmup_reqs:
                batch_result_items = batch_result_items[len(warmup_reqs):]
            for result, meta in zip(batch_result_items, dl_meta):
                try:
                    error = str((result or {}).get("error") or "").strip() if isinstance(result, dict) else ""
                    if error:
                        raise RuntimeError(error)
                    body_bytes = (result or {}).get("body_bytes") or b""
                    hdr_text = str((result or {}).get("headers_text") or "")
                    ct = _http_header_value(hdr_text, "Content-Type")
                    parsed = _parse_download_documento_response(body_bytes, ct)
                    files.append(
                        _assemble_download_file_payload(
                            parsed,
                            meta["item"],
                            meta["id_documento"],
                            meta["nome_documento"],
                            base_url,
                            original=original,
                        )
                    )
                except Exception as e:
                    failures.append({
                        "id_documento": meta["id_documento"],
                        "nome_documento": meta["nome_documento"],
                        "errore": str(e),
                    })
            if len(batch_result_items) < len(dl_meta):
                for meta in dl_meta[len(batch_result_items):]:
                    failures.append({
                        "id_documento": meta["id_documento"],
                        "nome_documento": meta["nome_documento"],
                        "errore": (
                            "Il lotto PST non ha restituito una risposta per questo documento. "
                            f"Tabella ministeriale: {policy.get('tabella') or servizio or 'PST'}."
                        ),
                    })
        except RuntimeError as batch_err:
            if allow_runtime_single_fallback and len(dl_reqs) == 1:
                log.warning("Batch download PST fallito, fallback download singolo: %s", batch_err)
                req = dl_reqs[0]
                meta = dl_meta[0]
                try:
                    body_bytes, hdr_text = _soap_call_curl_raw(
                        url=req["url"],
                        soap_body=req["soap_body"],
                        cert_thumbprint=cert_thumbprint,
                        extra_headers=req.get("extra_headers"),
                        soap_action=req.get("soap_action", ""),
                        cookie_file=req.get("cookie_file"),
                        max_time=req.get("max_time"),
                        connect_timeout=req.get("connect_timeout"),
                    )
                    ct = _http_header_value(hdr_text, "Content-Type")
                    parsed = _parse_download_documento_response(body_bytes, ct)
                    files.append(
                        _assemble_download_file_payload(
                            parsed,
                            meta["item"],
                            meta["id_documento"],
                            meta["nome_documento"],
                            base_url,
                            original=original,
                        )
                    )
                except Exception as e:
                    failures.append({
                        "id_documento": meta["id_documento"],
                        "nome_documento": meta["nome_documento"],
                        "errore": str(e),
                    })
            else:
                log.warning(
                    "Batch download PST fallito senza fallback singolo per evitare prompt PIN ripetuti: %s",
                    batch_err,
                )
                for meta in dl_meta:
                    failures.append({
                        "id_documento": meta["id_documento"],
                        "nome_documento": meta["nome_documento"],
                        "errore": (
                            "Download batch PST non riuscito. "
                            "Il lotto non ricade sul download singolo per evitare richieste PIN ripetute. "
                            f"Dettaglio: {batch_err}"
                        ),
                    })

        return {
            "ok": True,
            "files": files,
            "failures": failures,
            "preflight": preflight,
            "documenti_richiesti": len(documenti),
            "documenti_scaricati": len(files),
        }
    finally:
        if _tmp_cookie:
            try:
                Path(_tmp_cookie).unlink(missing_ok=True)
            except Exception:
                pass


def _arricchisci_fascicoli_con_profilo(
    fascicoli: list[dict],
    *,
    base_url: str,
    cert_thumbprint: Optional[str],
    cf_avvocato: str,
    cookie_file: Optional[str] = None,
    prefer_cookie_only: bool = False,
) -> list[dict]:
    if not _pst_namespace_qbuilder(base_url):
        return fascicoli
    if not fascicoli or len(fascicoli) > 5:
        return fascicoli
    headers = [f"X-WASP-User: {cf_avvocato}"]
    for fascicolo in fascicoli:
        soap = _soap_profilo_fascicolo_body(
            base_url=base_url,
            codice_ufficio=str(fascicolo.get("codice_ufficio") or "").strip(),
            numero_rg=str(fascicolo.get("numero_rg") or "").strip(),
            anno_rg=int(fascicolo.get("anno_rg") or 0),
            sub_procedimento=str(fascicolo.get("sub_procedimento") or "").strip(),
        )
        if not soap:
            continue
        try:
            xml_resp = _soap_call_pst_session(
                url=base_url.rstrip("/"),
                soap_body=soap,
                cert_thumbprint=cert_thumbprint,
                extra_headers=headers,
                cookie_file=cookie_file,
                prefer_cookie_only=prefer_cookie_only,
            )
            profili = _parse_fascicoli_xml(xml_resp)
            if not profili:
                continue
            profilo = profili[0]
            for campo in ("ruolo", "stato", "oggetto", "sezione", "giudice", "data_iscrizione", "data_udienza"):
                if profilo.get(campo):
                    fascicolo[campo] = profilo[campo]
            if profilo.get("parti"):
                fascicolo["parti"] = profilo["parti"]
                fascicolo["parti_dettaglio"] = profilo.get("parti_dettaglio", [])
        except Exception as e:
            log.debug("Arricchimento ProfiloFascicolo fallito per %s/%s: %s",
                      fascicolo.get("numero_rg"), fascicolo.get("anno_rg"), e)
    return fascicoli


def _fascicolo_richiede_arricchimento_profilo(fascicolo: dict) -> bool:
    if not fascicolo:
        return False
    if str(fascicolo.get("sub_procedimento") or "").strip():
        return True
    for campo in ("ruolo", "stato", "oggetto", "sezione", "data_iscrizione", "data_udienza"):
        if not str(fascicolo.get(campo) or "").strip():
            return True
    return False


# ── HTTP Handler ────────────────────────────────────────────────────────────────

class _ThreadingLocalSignerServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class _Handler(BaseHTTPRequestHandler):
    server_version = f"HACSSigner/{VERSION}"
    # Chiude ogni risposta: evita keep-alive pendenti dal browser.
    protocol_version = "HTTP/1.0"

    def log_message(self, fmt, *args):
        log.debug("[%s] %s", self.address_string(), fmt % args)

    def _cors_ok(self) -> bool:
        """Verifica che l'origine sia localhost o una origin IUSENTRA esplicitamente fidata."""
        origin = self.headers.get("Origin", "")
        return _origin_cors_consentita(origin)

    def _add_cors(self):
        origin = self.headers.get("Origin", "")
        allowed_origin = "*"
        if origin:
            allowed_origin = (
                _normalizza_origin(origin)
                if _origin_cors_consentita(origin)
                else "null"
            )
        self.send_header(
            "Access-Control-Allow-Origin",
            allowed_origin
        )
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type, X-Signer-Token, X-Requested-With"
        )
        self.send_header("Access-Control-Max-Age", "86400")
        self.send_header("Vary", "Origin")
        if origin or self.headers.get("Access-Control-Request-Private-Network"):
            self.send_header("Access-Control-Allow-Private-Network", "true")

    def _send_json(self, data: dict, status: int = 200):
        body = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self._add_cors()
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError) as e:
            log.debug("Client disconnesso durante la risposta %s: %s", self.path, e)
        finally:
            self.close_connection = True

    def _begin_sse(self, status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("Connection", "close")
        self._add_cors()
        self.end_headers()

    def _write_sse_event(self, payload: dict | str):
        if payload == "[DONE]":
            raw = b"data: [DONE]\n\n"
        else:
            raw = f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n".encode("utf-8")
        try:
            self.wfile.write(raw)
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError) as e:
            log.debug("Client disconnesso durante lo stream %s: %s", self.path, e)
            raise

    def _stream_sse(self, events):
        self._begin_sse()
        try:
            for payload in events:
                self._write_sse_event(payload)
                if isinstance(payload, dict) and payload.get("done"):
                    self._write_sse_event("[DONE]")
                    return
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            return
        except Exception as e:
            try:
                self._write_sse_event({"errore": str(e)})
                self._write_sse_event("[DONE]")
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass
        finally:
            self.close_connection = True

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if not length:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    def _query_params(self) -> dict[str, Any]:
        parsed = parse_qs(urlparse(self.path).query or "")
        return {key: values[0] for key, values in parsed.items() if values}

    def _local_ai_request_payload(self, payload_override: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = self._query_params()
        if payload_override is not None:
            payload.update(payload_override)
        elif self.command == "POST":
            payload.update(self._read_json())
        return {
            "enabled": _coerce_bool(payload.get("enabled"), True),
            "base_url": str(payload.get("base_url") or "http://127.0.0.1:11434/api").strip(),
            "auto_bootstrap": _coerce_bool(payload.get("auto_bootstrap"), True),
            "chat_model": str(payload.get("chat_model") or "").strip(),
            "embed_model": str(payload.get("embed_model") or "").strip(),
            "keep_alive": str(payload.get("keep_alive") or "10m").strip() or "10m",
            "auto_index_documents": _coerce_bool(payload.get("auto_index_documents"), True),
            "model": str(payload.get("model") or "").strip(),
            "prompt": str(payload.get("prompt") or "").strip(),
        }

    def _ai_facade(self) -> LocalAiHandlerFacade:
        return LocalAiHandlerFacade(
            get_bridge=_get_local_ai_bridge,
            request_payload_factory=self._local_ai_request_payload,
            read_json=self._read_json,
            send_json=self._send_json,
            stream_sse=self._stream_sse,
            logger=log,
            parse_attachment_payloads=parse_attachment_payloads,
            build_attachment_prompt_block=build_attachment_prompt_block,
        )

    def do_OPTIONS(self):  # noqa: N802
        self.send_response(204)
        self._add_cors()
        self.send_header("Content-Length", "0")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True

    def do_GET(self):  # noqa: N802
        if not self._cors_ok():
            self._send_json({"errore": "CORS: origine non consentita"}, 403)
            return
        path = urlparse(self.path).path
        if path in {"/", "/ping", "/update", "/seleziona-certificato", "/pst/status", "/ai/status"}:
            log.info("HTTP GET %s", path)
        if path in {"/", "/ping"}:
            self._ping()
        elif path == "/update":
            self._local_signer_update()
        elif path == "/diagnosi":
            self._diagnosi()
        elif path == "/logs/recent":
            self._logs_recent()
        elif path == "/ai/status":
            self._ai_status()
        elif path == "/certificati":
            self._certificati()
        elif path == "/seleziona-certificato":
            self._seleziona_certificato()
        elif path == "/pst/status":
            self._pst_status()
        elif re.fullmatch(r"/portal-assistant/session/[^/]+/status", path):
            self._portal_assistant_status(path)
        else:
            self._send_json({"errore": "Not found"}, 404)

    def do_POST(self):  # noqa: N802
        if not self._cors_ok():
            self._send_json({"errore": "CORS: origine non consentita"}, 403)
            return
        path = urlparse(self.path).path
        if path in {
            "/ai/bootstrap",
            "/ai/attachments/parse",
            "/ai/chat",
            "/ai/chat/stream",
            "/ai/rag/query",
            "/ai/rag/query/stream",
            "/ai/embed",
            "/update",
            "/pst/preflight-auth",
            "/pst/ricerca",
            "/pst/ricerca-snapshot",
            "/pst/documenti",
            "/pst/fascicolo-snapshot",
            "/pst/download-documenti-batch",
            "/pdp/ricerca",
            "/pdp/documenti",
            "/pat/ricerca",
            "/pat/documenti",
            "/ptt/ricerca",
            "/ptt/documenti",
            "/pec/smtp/test",
            "/pec/send",
            "/portal-assistant/session/start",
        }:
            log.info("HTTP POST %s", path)
        if path == "/ai/bootstrap":
            self._ai_bootstrap()
        elif path == "/ai/attachments/parse":
            self._ai_attachments_parse()
        elif path == "/ai/chat":
            self._ai_chat()
        elif path == "/ai/chat/stream":
            self._ai_chat_stream()
        elif path == "/ai/rag/query":
            self._ai_rag_query()
        elif path == "/ai/rag/query/stream":
            self._ai_rag_query_stream()
        elif path == "/ai/embed":
            self._ai_embed()
        elif path == "/update":
            self._local_signer_update()
        elif path == "/firma":
            self._firma()
        elif path == "/firma-batch":
            self._firma_batch()
        elif path == "/pst/preflight-auth":
            self._pst_preflight_auth()
        elif path == "/pst/ricerca":
            self._pst_ricerca()
        elif path == "/pst/ricerca-snapshot":
            self._pst_ricerca_snapshot()
        elif path == "/pst/documenti":
            self._pst_documenti()
        elif path == "/pst/fascicolo-snapshot":
            self._pst_fascicolo_snapshot()
        elif path == "/pdp/ricerca":
            self._pdp_ricerca()
        elif path == "/pdp/documenti":
            self._pdp_documenti()
        elif path == "/pat/ricerca":
            self._pat_ricerca()
        elif path == "/pat/documenti":
            self._pat_documenti()
        elif path == "/ptt/ricerca":
            self._ptt_ricerca()
        elif path == "/ptt/documenti":
            self._ptt_documenti()
        elif path == "/pst/download-documento":
            self._pst_download_documento()
        elif path == "/pst/download-documenti-batch":
            self._pst_download_documenti_batch()
        elif path == "/downloads/raccogli":
            self._downloads_raccogli()
        elif path == "/portal-assistant/session/start":
            self._portal_assistant_start()
        elif re.fullmatch(r"/portal-assistant/session/[^/]+/(open|watch-downloads|collect|close|cancel)", path):
            self._portal_assistant_action(path)
        elif path == "/pec/smtp/test":
            self._pec_smtp_test()
        elif path == "/pec/send":
            self._pec_send()
        else:
            self._send_json({"errore": "Not found"}, 404)

    # ── Handlers ────────────────────────────────────────────────────────────────

    def _local_signer_update(self):
        try:
            self._send_json(_avvia_aggiornamento_local_signer())
        except Exception as e:
            log.error("Aggiornamento Local Signer non avviato: %s", e)
            self._send_json({"ok": False, "errore": str(e)}, 500)

    def _ai_status(self):
        self._ai_facade().status()

    def _ai_bootstrap(self):
        self._ai_facade().bootstrap()

    def _ai_attachments_parse(self):
        self._ai_facade().attachments_parse()

    def _ai_chat(self):
        self._ai_facade().chat()

    def _ai_chat_stream(self):
        self._ai_facade().chat_stream()

    def _ai_rag_query(self):
        self._ai_facade().rag_query()

    def _ai_rag_query_stream(self):
        self._ai_facade().rag_query_stream()

    def _ai_embed(self):
        self._ai_facade().embed()

    def _pec_smtp_test(self):
        self._send_json(test_pec_smtp_local(self._read_json()))

    def _pec_send(self):
        self._send_json(send_pec_local(self._read_json()))

    def _ping(self):
        lib = _trova_libreria()
        prefs = _ping_query_preferences(getattr(self, "path", ""))
        light = _ping_is_light(getattr(self, "path", ""))
        resp: dict = {
            "ok": True,
            "versione":          VERSION,
            "piattaforma":       sys.platform,
            "libreria":          lib,
            "libreria_presente": lib is not None,
            "curl_disponibile":  _curl_disponibile(),
            "pin_sessioni_attive": _cleanup_pin_sessions(),
            "pin_session_ttl_seconds": PIN_SESSION_TTL_SECONDS,
            "pst_sessioni_attive": _cleanup_pst_sessions(),
            "pst_session_ttl_seconds": PST_SESSION_TTL_SECONDS,
            "light": light,
        }
        if light:
            resp["token"] = []
            resp["nota_light"] = (
                "Ping leggero: verifica raggiungibilita' del Local Signer senza interrogare "
                "lo store certificati Windows."
            )
            self._send_json(resp)
            return
        resp["token"] = []
        if sys.platform == "win32":
            try:
                certs = _windows_lista_certificati()
                resp["certificati_windows"] = len(certs)
                preferred = _pick_preferred_windows_cert(
                    certs,
                    prefer_issuer=prefs["prefer_issuer"],
                    prefer_subject=prefs["prefer_subject"],
                    prefer_cf=prefs["prefer_cf"],
                    auto=prefs["auto"],
                ) if certs else None
                cached = dict(_ultimo_certificato_windows or {})
                selected = preferred
                if not selected and _certificato_windows_compatibile_pst(
                    cached,
                    prefer_issuer=prefs["prefer_issuer"],
                    prefer_subject=prefs["prefer_subject"],
                    prefer_cf=prefs["prefer_cf"],
                ):
                    selected = cached
                if selected and selected.get("thumbprint"):
                    if preferred:
                        _ricorda_certificato_windows(selected)
                    resp["certificato_windows_selezionato"] = {
                        "thumbprint": selected.get("thumbprint"),
                        "soggetto": selected.get("soggetto", ""),
                        "soggetto_completo": selected.get("soggetto_completo", ""),
                        "emittente": selected.get("emittente", ""),
                        "emittente_completo": selected.get("emittente_completo", ""),
                        "scadenza": selected.get("scadenza", ""),
                        "codice_fiscale": selected.get("codice_fiscale", ""),
                        "auto_selezionato": bool(preferred),
                    }
                if prefs["prefer_cf"]:
                    resp["filtro_codice_fiscale"] = _estrai_codice_fiscale_testo(prefs["prefer_cf"])
                if certs:
                    resp["nota_autenticazione"] = (
                        "Su Windows la consultazione PST puo' usare anche il certificato "
                        "selezionato dal Certificate Store, anche se il token PKCS#11 non "
                        "viene rilevato nel ping."
                    )
            except Exception as e:
                resp["errore_certificati_windows"] = str(e)
        if not lib:
            resp["errore_libreria"] = (
                "Libreria PKCS#11 non trovata. "
                "Verificare che il middleware PKCS#11 del dispositivo sia installato "
                "e che smart card/token o lettore siano presenti. "
                "In alternativa impostare PCT_PKCS11_LIBRARY con il percorso della DLL."
            )
        else:
            try:
                resp["token"] = _info_token(lib)
            except RuntimeError as e:
                resp["errore_token"] = str(e)
                if sys.platform == "win32" and "Nessun token PKCS#11 rilevato" in resp["errore_token"]:
                    fresh_tokens = _probe_token_info_fresh(lib)
                    if fresh_tokens:
                        resp["token_probe_fresh"] = fresh_tokens
                        resp["riavvio_signer_consigliato"] = True
                        resp["nota_riavvio_signer"] = (
                            "Il token Aruba e' stato rilevato da un controllo fresco, "
                            "ma il processo Local Signer attivo non e' piu' allineato. "
                            "Riavvia il Local Signer da IUSENTRA e riprova."
                        )
            except Exception as e:
                resp["errore_token"] = f"Errore inatteso: {e}"
        self._send_json(resp)

    def _logs_recent(self):
        params = self._query_params()
        try:
            lines = max(20, min(int(params.get("lines", 240)), 1000))
        except (TypeError, ValueError):
            lines = 240
        try:
            max_bytes = max(10_000, min(int(params.get("bytes", _LOCAL_LOG_MAX_BYTES)), 500_000))
        except (TypeError, ValueError):
            max_bytes = _LOCAL_LOG_MAX_BYTES
        logs = []
        for filename in _LOCAL_LOG_FILES:
            path = _THIS_DIR / filename
            try:
                logs.append({
                    "name": filename,
                    "exists": path.exists() and path.is_file(),
                    "size": path.stat().st_size if path.exists() and path.is_file() else 0,
                    "tail": _tail_local_log(path, max_bytes=max_bytes, lines=lines),
                })
            except Exception as exc:
                logs.append({
                    "name": filename,
                    "exists": False,
                    "size": 0,
                    "tail": "",
                    "errore": str(exc),
                })
        self._send_json({
            "ok": True,
            "versione": VERSION,
            "piattaforma": sys.platform,
            "logs": logs,
        })

    def _diagnosi(self):
        """
        GET /diagnosi — diagnostica completa del sistema locale.
        Controlla middleware, token PKCS#11, python-pkcs11, curl.
        """
        risultati: dict = {
            "versione":    VERSION,
            "piattaforma": sys.platform,
            "ok":          True,
            "problemi":    [],
            "info":        [],
        }

        # 1. python-pkcs11
        try:
            import pkcs11 as _pk11  # noqa: F401
            risultati["pkcs11_modulo"] = True
            risultati["info"].append("python-pkcs11: installato")
        except ImportError:
            risultati["pkcs11_modulo"] = False
            risultati["ok"] = False
            risultati["problemi"].append(
                "python-pkcs11 NON installato. "
                "Eseguire: pip install python-pkcs11"
            )

        # 2. Ricerca libreria
        lib = _trova_libreria()
        risultati["libreria"] = lib
        if lib:
            risultati["info"].append(f"Libreria PKCS#11: {lib}")
        else:
            risultati["ok"] = False
            risultati["problemi"].append(
                "Libreria PKCS#11 non trovata.\n"
                "Verificare che il middleware PKCS#11 del dispositivo sia installato.\n"
                "Percorsi cercati: " + ", ".join(_DEFAULT_LIBS[:6]) + " … (e altri)\n"
                "Soluzione: installare il middleware del provider o impostare la variabile "
                "PCT_PKCS11_LIBRARY con il percorso completo della DLL."
            )

        # 3. Token PKCS#11
        if lib and risultati.get("pkcs11_modulo"):
            try:
                tokens = _info_token(lib)
                risultati["token"] = tokens
                if tokens:
                    for t in tokens:
                        risultati["info"].append(
                            f"Token: {t.get('label') or t.get('manufacturer')} "
                            f"(slot {t.get('slot_id')}, serial {t.get('serial') or 'n/d'})"
                        )
                else:
                    risultati["ok"] = False
                    risultati["problemi"].append(
                        "Libreria caricata ma nessun token rilevato.\n"
                        "Inserire smart card/token o collegare il lettore e riprovare."
                    )
            except RuntimeError as e:
                risultati["ok"] = False
                risultati["problemi"].append(str(e))
            except Exception as e:
                risultati["ok"] = False
                risultati["problemi"].append(f"Errore token: {e}")
        else:
            risultati["token"] = []

        # 4. Windows Certificate Store (solo Windows)
        if sys.platform == "win32":
            try:
                certs = _windows_lista_certificati()
                risultati["certificati_windows"] = len(certs)
                if certs:
                    risultati["info"].append(
                        f"Windows Certificate Store: {len(certs)} certificati trovati"
                    )
                    for c in certs[:3]:  # mostra al massimo 3
                        risultati["info"].append(
                            f"  • {c.get('soggetto')} — {c.get('emittente')} "
                            f"(scade {c.get('scadenza') or 'n/d'})"
                        )
                else:
                    risultati["problemi"].append(
                        "Windows Certificate Store (MY): nessun certificato.\n"
                        "Il middleware del dispositivo deve essere installato e la smart card/token inserita "
                        "perché il certificato venga registrato nello store."
                    )
            except Exception as e:
                risultati["problemi"].append(f"Errore lettura store Windows: {e}")

        # 5. curl
        curl_ok = _curl_disponibile()
        risultati["curl_disponibile"] = curl_ok
        if curl_ok:
            risultati["info"].append("curl: disponibile (PST abilitato)")
            risultati["info"].append(
                f"Timeout SOAP PST: {PST_SOAP_MAX_TIME}s (connessione {PST_SOAP_CONNECT_TIMEOUT}s)"
            )
        else:
            risultati["problemi"].append(
                "curl non trovato nel PATH. "
                "Su Windows 10+ è incluso nel sistema (C:\\Windows\\System32\\curl.exe). "
                "Aggiungere System32 al PATH."
            )

        risultati["pst_base"] = _pst_base_diagnostico()
        risultati["pst_endpoint_legacy"] = _pst_endpoint_configurato_e_legacy()
        if risultati["pst_endpoint_legacy"]:
            risultati["problemi"].append(_messaggio_endpoint_pst_legacy())
        else:
            if os.getenv("PCT_PST_BASE_URL", "").strip():
                risultati["info"].append(f"Endpoint PST configurato: {_pst_base_diagnostico()}")
            elif _supporto_auto_pst_disponibile():
                risultati["info"].append(
                    "Endpoint PST: risoluzione automatica dal registro uffici locale "
                    f"(proxy root {_PST_PROXY_SH_URL})"
                )
            else:
                risultati["info"].append(f"Endpoint PST configurato: {_pst_base_diagnostico()}")

        self._send_json(risultati)

    def _certificati(self):
        """GET /certificati — elenca certificati Windows MY store (senza dialog)."""
        if sys.platform == "win32":
            try:
                certs = _windows_lista_certificati()
                self._send_json({
                    "ok": True,
                    "piattaforma": "win32",
                    "certificati": certs,
                })
            except Exception as e:
                log.error("_certificati: %s", e)
                self._send_json({"ok": False, "errore": str(e)})
        else:
            # Fallback Linux/macOS: info token PKCS#11
            lib = _trova_libreria()
            tokens = _info_token(lib) if lib else []
            self._send_json({
                "ok": True,
                "piattaforma": sys.platform,
                "certificati": [],
                "token": tokens,
                "nota": "Selezione nativa disponibile solo su Windows",
            })

    def _seleziona_certificato(self):
        """
        GET /seleziona-certificato

        Windows: apre CryptUIDlgSelectCertificateFromStore (dialog nativa),
                 blocca finché l'utente sceglie o annulla.
        Linux:   restituisce info token PKCS#11 (fallback).
        """
        query = parse_qs(urlparse(self.path).query or "")
        prefer_issuer = str((query.get("prefer_issuer") or [""])[0] or "").strip()
        prefer_subject = str((query.get("prefer_subject") or [""])[0] or "").strip()
        prefer_cf = str((query.get("prefer_cf") or [""])[0] or "").strip()
        auto_select = str((query.get("auto") or ["0"])[0] or "").strip().lower() in {"1", "true", "yes", "on"}

        if sys.platform == "win32":
            try:
                cert = None
                auto_pick = False
                cached = dict(_ultimo_certificato_windows or {})
                if auto_select and _certificato_windows_compatibile_pst(
                    cached,
                    prefer_issuer=prefer_issuer,
                    prefer_subject=prefer_subject,
                    prefer_cf=prefer_cf,
                ):
                    cert = cached
                    auto_pick = True
                if cert is None:
                    cert = _pick_preferred_windows_cert(
                        _windows_lista_certificati(),
                        prefer_issuer=prefer_issuer,
                        prefer_subject=prefer_subject,
                        prefer_cf=prefer_cf,
                        auto=auto_select,
                    )
                    auto_pick = cert is not None
                if cert is None:
                    cert = _windows_seleziona_cert()
                    auto_pick = False
                if cert is None:
                    self._send_json({
                        "ok": False,
                        "annullato": True,
                        "errore": "Selezione annullata dall'utente",
                    })
                else:
                    _ricorda_certificato_windows(cert)
                    self._send_json({
                        "ok": True,
                        "piattaforma": "win32",
                        "auto_selezionato": auto_pick,
                        **cert,
                    })
            except Exception as e:
                log.error("_seleziona_certificato: %s", e)
                self._send_json({"ok": False, "errore": str(e)})
        else:
            # Fallback Linux/macOS: usa primo token PKCS#11 disponibile
            lib = _trova_libreria()
            if not lib:
                self._send_json({
                    "ok": False,
                    "errore": (
                        "Selezione nativa disponibile solo su Windows. "
                        "Su Linux inserire il token PKCS#11."
                    ),
                })
                return
            try:
                tokens = _info_token(lib)
                if not tokens:
                    self._send_json({"ok": False, "errore": "Nessun token PKCS#11 inserito"})
                    return
                tok = tokens[0]
                self._send_json({
                    "ok": True,
                    "piattaforma": sys.platform,
                    "soggetto": tok.get("label") or tok.get("manufacturer") or "Token PKCS#11",
                    "emittente": tok.get("manufacturer", ""),
                    "scadenza": "",
                    "thumbprint": None,
                    "token_slot": tok.get("slot_id"),
                    "nota": "Su Linux viene usato il token PKCS#11 direttamente",
                })
            except Exception as e:
                self._send_json({"ok": False, "errore": str(e)})

    def _pst_status(self):
        """
        Verifica raggiungibilità PST.
        Controlla il portale PST, i proxy documentati e l'endpoint configurato in IUSENTRA.
        """
        null_dev = "NUL" if sys.platform == "win32" else "/dev/null"
        risultati = {}

        for nome, url in [
            ("portale", _PST_PORTALE_URL),
            ("proxy_pda", _PST_PROXY_PDA_URL),
            ("proxy_sh", _PST_PROXY_SH_URL),
            ("endpoint_configurato", _pst_base_monitoraggio()),
        ]:
            try:
                run_kwargs = _windows_hidden_subprocess_kwargs({
                    "capture_output": True,
                    "text": True,
                    "timeout": 15,
                })
                r = subprocess.run(
                    [_curl_command(), "-s", "-o", null_dev,
                     "-w", "%{http_code}",
                     "--max-time", "10",
                     "--connect-timeout", "8",
                     url],
                    **run_kwargs,
                )
                code = r.stdout.strip()
                raggiungibile = r.returncode == 0 and code not in ("", "000")
                risultati[nome] = {
                    "url":           url,
                    "raggiungibile": raggiungibile,
                    "http_code":     code or None,
                    "errore":        (
                        _curl_errore_leggibile(r.returncode, r.stderr, url)
                        if r.returncode not in (0, 22)    # 22 = HTTP error (server risponde)
                        else None
                    ),
                }
            except Exception as e:
                risultati[nome] = {"url": url, "raggiungibile": False, "errore": str(e)}

        risultati["soap"] = risultati.get("endpoint_configurato", {})
        ok = any(item.get("raggiungibile", False) for item in risultati.values())

        payload = {
            "ok": ok,
            "pst_base": _pst_base_diagnostico(),
            "pst_endpoint_legacy": _pst_endpoint_configurato_e_legacy(),
            **risultati,
        }
        if payload["pst_endpoint_legacy"]:
            payload["nota_configurazione"] = _messaggio_endpoint_pst_legacy()

        self._send_json(payload)

    def _firma(self):
        """
        POST /firma
        Body: {documento: <base64>, pin?: "...", pin_session_id?: "...", slot_id?: 0, visible_signature_mode?: "laterale"|"basso_sinistra"|"basso_destra", visible_signature_place?: "Taurianova", visible_signature_datetime_mode?: "data_ora"|"solo_data"|"nessuna"}
        Response: {ok, firmato_b64, intestatario, scadenza, dimensione}
        """
        lib = _trova_libreria()
        if not lib:
            self._send_json({
                "ok": False,
                "errore": (
                    "Libreria PKCS#11 non trovata. "
                    "Verificare che il middleware PKCS#11 del dispositivo sia installato "
                    "e che smart card/token o lettore siano presenti."
                ),
            }, 400)
            return

        data = self._read_json()
        doc_b64 = data.get("documento")
        pin = data.get("pin", "")
        pin_session_id = str(data.get("pin_session_id") or "").strip()
        slot_id = data.get("slot_id")
        visible_signature_mode = str(data.get("visible_signature_mode") or "laterale").strip()
        visible_signature_place = str(data.get("visible_signature_place") or "").strip()
        visible_signature_datetime_mode = str(data.get("visible_signature_datetime_mode") or "data_ora").strip()

        if not doc_b64:
            self._send_json({"ok": False, "errore": "Campo 'documento' (base64) obbligatorio"}, 400)
            return
        if not pin and not pin_session_id:
            self._send_json({"ok": False, "errore": "PIN o pin_session_id obbligatorio"}, 400)
            return

        try:
            documento = base64.b64decode(doc_b64)
            firmato, info = _firma_documento(
                lib,
                documento,
                pin,
                slot_id,
                pin_session_id=pin_session_id or None,
                visible_signature_mode=visible_signature_mode,
                visible_signature_place=visible_signature_place,
                visible_signature_datetime_mode=visible_signature_datetime_mode,
            )
            self._send_json({
                "ok": True,
                "firmato_b64": base64.b64encode(firmato).decode(),
                "dimensione": len(firmato),
                **info,
            })
        except Exception as e:
            log.error("Errore firma: %s", e)
            self._send_json({"ok": False, "errore": str(e)}, 500)

    def _firma_batch(self):
        """
        POST /firma-batch
        Body: {documenti:[{documento:<base64>, nome?}], pin?: "...", pin_session_id?: "...", slot_id?: 0, visible_signature_mode?: "laterale"|"basso_sinistra"|"basso_destra", visible_signature_place?: "Taurianova", visible_signature_datetime_mode?: "data_ora"|"solo_data"|"nessuna"}
        Response: {ok, firmati, falliti, risultati:[...], pin_session_id?}
        """
        lib = _trova_libreria()
        if not lib:
            self._send_json({
                "ok": False,
                "errore": (
                    "Libreria PKCS#11 non trovata. "
                    "Verificare che il middleware PKCS#11 del dispositivo sia installato "
                    "e che smart card/token o lettore siano presenti."
                ),
            }, 400)
            return

        data = self._read_json()
        docs = data.get("documenti") or []
        pin = data.get("pin", "")
        slot_id = data.get("slot_id")
        current_session_id = str(data.get("pin_session_id") or "").strip()
        visible_signature_mode = str(data.get("visible_signature_mode") or "laterale").strip()
        visible_signature_place = str(data.get("visible_signature_place") or "").strip()
        visible_signature_datetime_mode = str(data.get("visible_signature_datetime_mode") or "data_ora").strip()

        if not isinstance(docs, list) or not docs:
            self._send_json({"ok": False, "errore": "Il batch richiede almeno un documento."}, 400)
            return
        if not pin and not current_session_id:
            self._send_json({"ok": False, "errore": "PIN o pin_session_id obbligatorio"}, 400)
            return

        risultati = []
        firmati = 0
        falliti = 0

        for idx, raw_doc in enumerate(docs):
            item = raw_doc if isinstance(raw_doc, dict) else {}
            doc_b64 = item.get("documento") or item.get("documento_b64")
            nome = str(item.get("nome") or item.get("nome_documento") or f"documento_{idx + 1}").strip()
            if not doc_b64:
                risultati.append({
                    "ok": False,
                    "indice": idx,
                    "nome": nome,
                    "errore": "Campo 'documento' (base64) obbligatorio",
                })
                falliti += 1
                continue

            try:
                documento = base64.b64decode(doc_b64)
                firmato, info = _firma_documento(
                    lib,
                    documento,
                    pin if not current_session_id else "",
                    slot_id,
                    pin_session_id=current_session_id or None,
                    visible_signature_mode=visible_signature_mode,
                    visible_signature_place=visible_signature_place,
                    visible_signature_datetime_mode=visible_signature_datetime_mode,
                )
                current_session_id = str(info.get("pin_session_id") or current_session_id or "")
                risultati.append({
                    "ok": True,
                    "indice": idx,
                    "nome": nome,
                    "firmato_b64": base64.b64encode(firmato).decode(),
                    "dimensione": len(firmato),
                    **info,
                })
                firmati += 1
            except Exception as e:
                current_session_id = ""
                risultati.append({
                    "ok": False,
                    "indice": idx,
                    "nome": nome,
                    "errore": str(e),
                })
                falliti += 1
                if "Sessione PIN scaduta" in str(e):
                    break

        payload = {
            "ok": falliti == 0,
            "firmati": firmati,
            "falliti": falliti,
            "risultati": risultati,
        }
        if current_session_id:
            payload["pin_session_id"] = current_session_id
            payload["pin_session_ttl_seconds"] = PIN_SESSION_TTL_SECONDS
        self._send_json(payload, 200 if firmati or not falliti else 500)

    def _pst_preflight_auth(self):
        """
        POST /pst/preflight-auth
        Body: {tribunale, cert_thumbprint?, pst_session_id?, purpose?}
        Response: {ok, http_code, nota, pst_session_id}
        """
        if not _curl_disponibile():
            self._send_json({
                "ok": False,
                "errore": (
                    "curl non disponibile. "
                    "Su Windows 10+ e' incluso in sistema. "
                    "Verificare che sia nel PATH."
                ),
            }, 400)
            return

        data = self._read_json()
        tribunale = (data.get("tribunale") or data.get("codice_ufficio") or "").strip()
        requested_session_id = str(data.get("pst_session_id") or "").strip()
        purpose = str(data.get("purpose") or "view").strip().lower() or "view"
        if purpose not in {"view", "import"}:
            purpose = "view"
        session_cleanup_id = requested_session_id

        try:
            session_entry = _resolve_pst_session_entry(requested_session_id) if requested_session_id else None
            if session_entry and str(session_entry.get("purpose") or "view").lower() != purpose:
                purpose = str(session_entry.get("purpose") or "view").lower()
            if session_entry and not data.get("force_auth") and not data.get("force_new"):
                self._send_json({
                    "ok": True,
                    "tribunale": tribunale or str(session_entry.get("tribunale") or "").strip(),
                    "cached": True,
                    "nota": "Sessione accesso PST gia' attiva nel Local Signer.",
                    **_pst_session_response_fields(session_entry),
                })
                return

            if not tribunale:
                self._send_json({
                    "ok": False,
                    "errore": "Campo 'tribunale' obbligatorio per aprire la sessione autenticata PST",
                }, 400)
                return

            base_url = _risolvi_base_pst_runtime(tribunale)
            cert_thumbprint = _require_certificato_pst(
                data.get("cert_thumbprint") or (session_entry or {}).get("cert_thumbprint")
            )
            cf_avvocato = _cf_avvocato_pst(
                data.get("cf_avvocato", "") or (session_entry or {}).get("cf_avvocato", ""),
                cert_thumbprint,
            )
            if not session_entry and purpose == "import":
                view_entry = _find_view_session_for_cert(cert_thumbprint, tribunale)
                if view_entry:
                    session_entry = view_entry
                    purpose = "view"
                    session_cleanup_id = str(session_entry.get("session_id") or "")
                    if not data.get("force_auth") and not data.get("force_new"):
                        self._send_json({
                            "ok": True,
                            "tribunale": tribunale or str(session_entry.get("tribunale") or "").strip(),
                            "cached": True,
                            "nota": "Sessione accesso PST gia' attiva nel Local Signer.",
                            **_pst_session_response_fields(session_entry),
                        })
                        return
            if not session_entry:
                session_entry, _created = _ensure_pst_session_entry(
                    requested_session_id,
                    tribunale=tribunale,
                    base_url=base_url,
                    cf_avvocato=cf_avvocato,
                    cert_thumbprint=cert_thumbprint,
                    purpose=purpose,
                    force_new=bool(data.get("force_new", False)),
                    cert_key=str(data.get("cert_key") or cert_thumbprint or ""),
                    cert_preferences=data.get("cert_preferences") if isinstance(data.get("cert_preferences"), dict) else None,
                )
                session_cleanup_id = session_entry["session_id"]
                # Per sessioni import appena create: eredita i cookie della sessione view attiva
                # (stesso certificato e ufficio). I cookie esistenti pre-autenticano il canale
                # TLS evitando un nuovo prompt PIN quando la sessione Windows e' ancora attiva.
                if purpose == "import" and _created:
                    view_entry = _find_view_session_for_cert(cert_thumbprint, tribunale)
                    if view_entry:
                        view_cookie = str(view_entry.get("cookie_file") or "").strip()
                        import_cookie = str(session_entry.get("cookie_file") or "").strip()
                        if view_cookie and import_cookie and view_cookie != import_cookie:
                            try:
                                shutil.copy2(view_cookie, import_cookie)
                            except Exception:
                                pass
            with _pst_session_lock_for(session_entry):
                esito = _pst_preflight_auth_curl(
                    url=_pst_url_ricerca(base_url),
                    cert_thumbprint=cert_thumbprint,
                    cookie_file=str(session_entry.get("cookie_file") or ""),
                )
            _update_pst_session(
                session_entry["session_id"],
                tribunale=tribunale,
                base_url=base_url,
                cf_avvocato=cf_avvocato,
                purpose=purpose,
                last_http_code=esito.get("http_code"),
                last_content_type=esito.get("content_type"),
                auth_ready=_pst_preflight_confirmed(esito),
                preflight_attempted=True,
            )
            self._send_json({
                "ok": True,
                "tribunale": tribunale,
                **esito,
                "cached": False,
                **_pst_session_response_fields(_get_pst_session(session_entry["session_id"], refresh=False) or session_entry),
            })
        except Exception as e:
            if session_cleanup_id:
                _drop_pst_session(session_cleanup_id)
            log.error("Errore PST preflight auth: %s", e)
            self._send_json({"ok": False, "errore": str(e)}, 500)

    def _pst_ricerca(self):
        """
        POST /pst/ricerca
        Body: {tribunale, numero_rg?, anno_rg?, nome_parte?, cf_parte?,
               cf_avvocato?, cert_thumbprint?}
        Response: {ok, fascicoli:[...]}
        """
        if not _curl_disponibile():
            self._send_json({
                "ok": False,
                "errore": (
                    "curl non disponibile. "
                    "Su Windows 10+ è incluso in sistema. "
                    "Verificare che sia nel PATH."
                ),
            }, 400)
            return

        data = self._read_json()
        tribunale = data.get("tribunale", "").strip()
        if not tribunale:
            self._send_json({"ok": False, "errore": "Campo 'tribunale' obbligatorio"}, 400)
            return

        try:
            servizio_hint = _pst_servizio_ministeriale_da_payload(data)
            base_url = _risolvi_base_pst_runtime(tribunale)
            base_url = _pst_base_url_con_preferenza_payload(base_url, data)
            url_ricerca = _pst_url_ricerca(base_url)
            codice_pst = _risolvi_codice_ufficio_pst(tribunale)
            log.info(
                "PST ricerca: ufficio richiesto=%s codice_pst=%s servizio=%s tabella_hint=%s rg=%s/%s fallback_registro=%s",
                tribunale,
                codice_pst,
                _pst_servizio_proxy(base_url),
                servizio_hint or "auto",
                str(data.get("numero_rg") or ""),
                str(data.get("anno_rg") or ""),
                _pst_register_fallback_enabled(),
            )
        except Exception as e:
            self._send_json({"ok": False, "errore": str(e)}, 503)
            return

        try:
            requested_session_id = str(data.get("pst_session_id") or "").strip()
            cert_thumbprint = _require_certificato_pst(
                data.get("cert_thumbprint")
            )
            cf_avvocato = _cf_avvocato_pst(data.get("cf_avvocato", ""), cert_thumbprint)
            existing_session = _resolve_pst_session_entry(requested_session_id) if requested_session_id else None
            session_base_url = str((existing_session or {}).get("base_url") or "").strip()
            if session_base_url and _pst_namespace_qbuilder(session_base_url):
                base_url = (
                    _pst_base_url_con_servizio(session_base_url, servizio_hint)
                    if servizio_hint
                    else session_base_url
                )
                url_ricerca = _pst_url_ricerca(base_url)
            if _pst_namespace_qbuilder(base_url) and not cf_avvocato:
                raise RuntimeError(
                    "Impossibile determinare il codice fiscale dell'avvocato dal certificato selezionato.\n"
                    "Riselezionare il certificato CNS/CIE oppure indicare esplicitamente il codice fiscale."
                )
            session_kwargs = {
                "tribunale": tribunale,
                "base_url": base_url,
                "cf_avvocato": cf_avvocato,
                "cert_thumbprint": cert_thumbprint,
                "purpose": "view",
                "cert_key": str(data.get("cert_key") or cert_thumbprint or ""),
                "cert_preferences": data.get("cert_preferences") if isinstance(data.get("cert_preferences"), dict) else None,
            }
            try:
                session_entry, _session_created = _ensure_pst_session_entry(
                    requested_session_id,
                    **session_kwargs,
                )
            except RuntimeError as exc:
                if not (requested_session_id and "session_expired" in str(exc)):
                    raise
                log.info(
                    "PST ricerca: sessione %s non piu' presente, apertura con nuova sessione",
                    requested_session_id,
                )
                session_entry, _session_created = _ensure_pst_session_entry(
                    "",
                    **session_kwargs,
                )
            if session_entry and not cf_avvocato:
                cf_avvocato = str(session_entry.get("cf_avvocato") or "").strip()
            with _pst_session_lock_for(session_entry):
                session_entry, prefer_cookie_only = _pst_prepare_authenticated_session(
                    session_entry,
                    tribunale=tribunale,
                    base_url=base_url,
                    cf_avvocato=cf_avvocato,
                    cert_thumbprint=cert_thumbprint,
                    force=_session_created,
                )
                cookie_file = str((session_entry or {}).get("cookie_file") or "")
            soap = _soap_ricerca_fascicoli_body(
                base_url=base_url,
                codice_ufficio=codice_pst,
                numero_rg=data.get("numero_rg") or None,
                anno_rg=int(data.get("anno_rg") or 0) or None,
                nome_parte=data.get("nome_parte") or None,
                cf_parte=data.get("cf_parte") or None,
                cf_avvocato=cf_avvocato,
                sub_procedimento=str(data.get("sub_procedimento") or data.get("subpro") or "").strip(),
            )
            extra_headers = [f"X-WASP-User: {cf_avvocato}"] if _pst_namespace_qbuilder(base_url) else []
            is_sigp_exact = (
                _pst_servizio_sigp(base_url)
                and bool(data.get("numero_rg"))
                and bool(data.get("anno_rg"))
            )
            xml_resp = ""
            fallback_motivo = ""
            try:
                xml_resp = _soap_call_pst_session(
                    url=url_ricerca,
                    soap_body=soap,
                    cert_thumbprint=cert_thumbprint,
                    extra_headers=extra_headers,
                    cookie_file=cookie_file,
                    prefer_cookie_only=prefer_cookie_only,
                )
                fault = _estrai_fault_soap(xml_resp)
                if fault:
                    raise RuntimeError(f"Il PST ha restituito una SOAP Fault: {fault}")
                fascicoli = _parse_fascicoli_xml(xml_resp)
            except Exception as pst_error:
                if not is_sigp_exact:
                    raise
                fallback_motivo = str(pst_error)
                log.warning("SIGP ricerca esatta in fallback guidato: %s", fallback_motivo)
                fascicoli = []
            if is_sigp_exact and not fascicoli:
                fascicoli = [
                    _sigp_fascicolo_fallback(
                        codice_ufficio=codice_pst,
                        numero_rg=str(data.get("numero_rg") or ""),
                        anno_rg=str(data.get("anno_rg") or ""),
                        cf_avvocato=cf_avvocato,
                        motivo=fallback_motivo or "Il web service SIGP non ha restituito righe per la ricerca esatta.",
                    )
                ]
            if _pst_namespace_qbuilder(base_url) and not (data.get("numero_rg") and data.get("anno_rg")):
                fascicoli = [
                    fascicolo for fascicolo in fascicoli
                    if _matches_parte_filters(
                        fascicolo,
                        nome_parte=data.get("nome_parte", ""),
                        cf_parte=data.get("cf_parte", ""),
                    )
                ]
            if fascicoli and any(_fascicolo_richiede_arricchimento_profilo(fascicolo) for fascicolo in fascicoli):
                fascicoli = _arricchisci_fascicoli_con_profilo(
                    fascicoli,
                    base_url=base_url,
                    cert_thumbprint=cert_thumbprint,
                    cf_avvocato=cf_avvocato,
                    cookie_file=cookie_file,
                    prefer_cookie_only=prefer_cookie_only,
                )
            if session_entry:
                _update_pst_session(
                    session_entry["session_id"],
                    tribunale=tribunale,
                    base_url=base_url,
                    cf_avvocato=cf_avvocato,
                    auth_ready=True,
                )
            self._send_json({
                "ok": True,
                "fascicoli": fascicoli,
                "raw_xml": xml_resp[:2000] if not fascicoli else None,
                **_pst_session_response_fields(session_entry),
            })
        except Exception as e:
            log.error("Errore PST ricerca: %s", e)
            self._send_json({"ok": False, "errore": str(e)}, 500)

    def _pst_ricerca_snapshot(self):
        """
        POST /pst/ricerca-snapshot
        Ricerca esatta RG/anno + catalogo documenti nello stesso processo curl.
        Serve a ridurre i prompt PIN quando il portale richiede mTLS per ogni
        round-trip e il driver Windows non persiste la cache tra subprocess.
        """
        if not _curl_disponibile():
            self._send_json({
                "ok": False,
                "errore": (
                    "curl non disponibile. "
                    "Su Windows 10+ e' incluso in sistema. "
                    "Verificare che sia nel PATH."
                ),
            }, 400)
            return

        data = self._read_json()
        tribunale = str(data.get("tribunale") or data.get("codice_ufficio") or "").strip()
        numero_rg = str(data.get("numero_rg") or "").strip()
        try:
            anno_rg = int(data.get("anno_rg") or 0)
        except (TypeError, ValueError):
            anno_rg = 0

        if not (tribunale and numero_rg and anno_rg):
            self._send_json({
                "ok": False,
                "errore": "Campi obbligatori: tribunale, numero_rg, anno_rg",
            }, 400)
            return

        try:
            servizio_hint = _pst_servizio_ministeriale_da_payload(data)
            base_url = _risolvi_base_pst_runtime(tribunale)
            base_url = _pst_base_url_con_preferenza_payload(base_url, data)
            url_ricerca = _pst_url_ricerca(base_url)
            url_documenti = _pst_url_documenti(base_url)
            codice_pst = _risolvi_codice_ufficio_pst(tribunale)
            log.info(
                "PST ricerca-snapshot: ufficio richiesto=%s codice_pst=%s servizio=%s tabella_hint=%s rg=%s/%s fallback_registro=%s",
                tribunale,
                codice_pst,
                _pst_servizio_proxy(base_url),
                servizio_hint or "auto",
                numero_rg,
                anno_rg,
                _pst_register_fallback_enabled(),
            )
        except Exception as e:
            self._send_json({"ok": False, "errore": str(e)}, 503)
            return

        try:
            requested_session_id = str(data.get("pst_session_id") or "").strip()
            cert_thumbprint = _require_certificato_pst(data.get("cert_thumbprint"))
            cf_avvocato = _cf_avvocato_pst(data.get("cf_avvocato", ""), cert_thumbprint)
            if _pst_namespace_qbuilder(base_url) and not cf_avvocato:
                raise RuntimeError(
                    "Impossibile determinare il codice fiscale dell'avvocato dal certificato selezionato.\n"
                    "Riselezionare il certificato CNS/CIE oppure indicare esplicitamente il codice fiscale."
                )
            session_kwargs = {
                "tribunale": tribunale,
                "base_url": base_url,
                "cf_avvocato": cf_avvocato,
                "cert_thumbprint": cert_thumbprint,
                "purpose": "view",
                "cert_key": str(data.get("cert_key") or cert_thumbprint or ""),
                "cert_preferences": data.get("cert_preferences") if isinstance(data.get("cert_preferences"), dict) else None,
            }
            try:
                session_entry, session_created = _ensure_pst_session_entry(
                    requested_session_id,
                    **session_kwargs,
                )
            except RuntimeError as exc:
                if not (requested_session_id and "session_expired" in str(exc)):
                    raise
                log.info(
                    "PST ricerca-snapshot: sessione %s non piu' presente, apertura batch con nuova sessione",
                    requested_session_id,
                )
                session_entry, session_created = _ensure_pst_session_entry(
                    "",
                    **session_kwargs,
                )
            if session_entry and not cf_avvocato:
                cf_avvocato = str(session_entry.get("cf_avvocato") or "").strip()

            sub_procedimento = str(data.get("sub_procedimento") or data.get("subpro") or "").strip()
            extra_headers = [f"X-WASP-User: {cf_avvocato}"] if _pst_namespace_qbuilder(base_url) else []
            soap_ricerca = _soap_ricerca_fascicoli_body(
                base_url=base_url,
                codice_ufficio=codice_pst,
                numero_rg=numero_rg,
                anno_rg=anno_rg,
                nome_parte=data.get("nome_parte") or None,
                cf_parte=data.get("cf_parte") or None,
                cf_avvocato=cf_avvocato,
                sub_procedimento=sub_procedimento,
            )
            soap_documenti = _soap_documenti_body(
                base_url=base_url,
                codice_ufficio=codice_pst,
                numero_rg=numero_rg,
                anno_rg=anno_rg,
                cf_avvocato=cf_avvocato,
                sub_procedimento=sub_procedimento,
            )
            soap_profilo = _soap_profilo_fascicolo_body(
                base_url=base_url,
                codice_ufficio=codice_pst,
                numero_rg=numero_rg,
                anno_rg=anno_rg,
                sub_procedimento=sub_procedimento,
            ) if _pst_namespace_qbuilder(base_url) else ""

            with _pst_session_lock_for(session_entry):
                # La ricerca-snapshot è già un lotto unico di ricerca, profilo e
                # documenti: usarla anche come gate certificato evita il doppio
                # prompt PIN causato da preflight + batch su alcuni driver Windows.
                cookie_file = str((session_entry or {}).get("cookie_file") or "")
                prefer_cookie_only = _pst_session_can_use_cookie_only(session_entry)
                batch_requests = [
                    {
                        "url": url_ricerca,
                        "soap_body": soap_ricerca,
                        "extra_headers": extra_headers,
                        "soap_action": "",
                        "cookie_file": cookie_file,
                        "servizio_logico": _pst_servizio_proxy(base_url),
                    },
                ]
                profile_index = None
                if soap_profilo:
                    profile_index = len(batch_requests)
                    batch_requests.append({
                        "url": url_ricerca,
                        "soap_body": soap_profilo,
                        "extra_headers": extra_headers,
                        "soap_action": "",
                        "cookie_file": cookie_file,
                        "servizio_logico": _pst_servizio_proxy(base_url),
                    })
                documenti_index = len(batch_requests)
                batch_requests.append({
                    "url": url_documenti,
                    "soap_body": soap_documenti,
                    "extra_headers": extra_headers,
                    "soap_action": "",
                    "cookie_file": cookie_file,
                    "servizio_logico": _pst_servizio_proxy(base_url),
                })
                sigp_atti_index = None
                if _pst_servizio_sigp(base_url):
                    sigp_atti_index = len(batch_requests)
                    batch_requests.append({
                        "url": url_documenti,
                        "soap_body": _soap_sigp_ricerca_atti_body(codice_pst, numero_rg, anno_rg),
                        "extra_headers": extra_headers,
                        "soap_action": "ricercaAtti",
                        "cookie_file": cookie_file,
                        "servizio_logico": _pst_servizio_proxy(base_url),
                    })
                fallback_batches = []
                if _pst_namespace_qbuilder(base_url):
                    fallback_targets: list[tuple[str, str]] = []
                    for codice_alternativo in _pst_codici_ufficio_ricerca_esatta(codice_pst, tribunale)[1:]:
                        fallback_targets.append((base_url, codice_alternativo))
                    for fallback_base_url in _pst_base_varianti_ricerca_esatta(codice_pst or tribunale, base_url)[1:]:
                        fallback_targets.append((fallback_base_url, codice_pst))

                    seen_fallback_targets: set[tuple[str, str]] = set()
                    for fallback_base_url, fallback_codice in fallback_targets:
                        fallback_base_url = fallback_base_url.rstrip("/")
                        fallback_codice = str(fallback_codice or codice_pst or tribunale).strip()
                        key = (fallback_base_url, fallback_codice)
                        if key in seen_fallback_targets:
                            continue
                        seen_fallback_targets.add(key)
                        if (
                            (fallback_base_url == base_url.rstrip("/") and fallback_codice == codice_pst)
                            or not _pst_namespace_qbuilder(fallback_base_url)
                        ):
                            continue
                        fallback_url_ricerca = _pst_url_ricerca(fallback_base_url)
                        fallback_url_documenti = _pst_url_documenti(fallback_base_url)
                        fallback_extra_headers = [f"X-WASP-User: {cf_avvocato}"]
                        fallback_soap_profilo = _soap_profilo_fascicolo_body(
                            base_url=fallback_base_url,
                            codice_ufficio=fallback_codice,
                            numero_rg=numero_rg,
                            anno_rg=anno_rg,
                            sub_procedimento=sub_procedimento,
                        )
                        fallback_info = {
                            "base_url": fallback_base_url,
                            "codice_ufficio": fallback_codice,
                            "url_ricerca": fallback_url_ricerca,
                            "url_documenti": fallback_url_documenti,
                            "ricerca_index": len(batch_requests),
                            "profilo_index": None,
                            "documenti_index": None,
                            "sigp_atti_index": None,
                        }
                        batch_requests.append({
                            "url": fallback_url_ricerca,
                            "soap_body": _soap_ricerca_fascicoli_body(
                                base_url=fallback_base_url,
                                codice_ufficio=fallback_codice,
                                numero_rg=numero_rg,
                                anno_rg=anno_rg,
                                nome_parte=None,
                                cf_parte=None,
                                cf_avvocato=cf_avvocato,
                                sub_procedimento=sub_procedimento,
                            ),
                            "extra_headers": fallback_extra_headers,
                            "soap_action": "",
                            "cookie_file": cookie_file,
                            "servizio_logico": _pst_servizio_proxy(fallback_base_url),
                        })
                        if fallback_soap_profilo:
                            fallback_info["profilo_index"] = len(batch_requests)
                            batch_requests.append({
                                "url": fallback_url_ricerca,
                                "soap_body": fallback_soap_profilo,
                                "extra_headers": fallback_extra_headers,
                                "soap_action": "",
                                "cookie_file": cookie_file,
                                "servizio_logico": _pst_servizio_proxy(fallback_base_url),
                            })
                        fallback_info["documenti_index"] = len(batch_requests)
                        batch_requests.append({
                            "url": fallback_url_documenti,
                            "soap_body": _soap_documenti_body(
                                base_url=fallback_base_url,
                                codice_ufficio=fallback_codice,
                                numero_rg=numero_rg,
                                anno_rg=anno_rg,
                                cf_avvocato=cf_avvocato,
                                sub_procedimento=sub_procedimento,
                            ),
                            "extra_headers": fallback_extra_headers,
                            "soap_action": "",
                            "cookie_file": cookie_file,
                            "servizio_logico": _pst_servizio_proxy(fallback_base_url),
                        })
                        if _pst_servizio_sigp(fallback_base_url):
                            fallback_info["sigp_atti_index"] = len(batch_requests)
                            batch_requests.append({
                                "url": fallback_url_documenti,
                                "soap_body": _soap_sigp_ricerca_atti_body(fallback_codice, numero_rg, anno_rg),
                                "extra_headers": fallback_extra_headers,
                                "soap_action": "ricercaAtti",
                                "cookie_file": cookie_file,
                                "servizio_logico": _pst_servizio_proxy(fallback_base_url),
                            })
                        fallback_batches.append(fallback_info)
                batch_result_items = _soap_call_pst_session_batch_raw_best_effort(
                    batch_requests,
                    cert_thumbprint=cert_thumbprint,
                    cookie_file=cookie_file,
                    prefer_cookie_only=prefer_cookie_only,
                )
                batch_results = [
                    (
                        (item.get("body_bytes") or b"") if isinstance(item, dict) else b"",
                        str(item.get("headers_text") or "") if isinstance(item, dict) else "",
                    )
                    for item in batch_result_items
                ]
                for idx, item in enumerate(batch_result_items):
                    if isinstance(item, dict) and item.get("error"):
                        servizio = str(
                            batch_requests[idx].get("servizio_logico")
                            or _pst_servizio_proxy(str(batch_requests[idx].get("url") or ""))
                        )
                        log.info("PST ricerca-snapshot: richiesta %s/%s non bloccante: %s", idx + 1, servizio, item.get("error"))
                blocking_error = _pst_best_effort_batch_blocking_error(batch_result_items)
                if blocking_error:
                    raise RuntimeError(blocking_error)

            xml_ricerca = batch_results[0][0].decode("utf-8", "replace") if batch_results else ""
            xml_profilo = (
                batch_results[profile_index][0].decode("utf-8", "replace")
                if profile_index is not None and len(batch_results) > profile_index
                else ""
            )
            xml_documenti = (
                batch_results[documenti_index][0].decode("utf-8", "replace")
                if len(batch_results) > documenti_index
                else ""
            )
            xml_sigp_atti = (
                batch_results[sigp_atti_index][0].decode("utf-8", "replace")
                if sigp_atti_index is not None and len(batch_results) > sigp_atti_index
                else ""
            )
            search_faults: list[str] = []
            valid_search_response_seen = _pst_xml_response_valida_senza_fault(xml_ricerca)
            fault = _estrai_fault_soap(xml_ricerca)
            if fault:
                search_faults.append(fault)
                if fallback_batches:
                    log.info(
                        "Ricerca PST non disponibile su %s, provo registro alternativo: %s",
                        _pst_servizio_proxy(base_url),
                        fault,
                    )
                    xml_ricerca = ""
                else:
                    raise RuntimeError(f"Il PST ha restituito una SOAP Fault: {fault}")
            fault = _estrai_fault_soap(xml_profilo)
            if fault and not _pst_servizio_sigp(base_url):
                if fallback_batches:
                    log.info(
                        "Profilo fascicolo PST non disponibile su %s, provo registro alternativo: %s",
                        _pst_servizio_proxy(base_url),
                        fault,
                    )
                    xml_profilo = ""
                else:
                    raise RuntimeError(f"Il PST ha restituito una SOAP Fault: {fault}")
            if fault and _pst_servizio_sigp(base_url):
                log.warning("Profilo fascicolo SIGP in snapshot non disponibile: %s", fault)
                xml_profilo = ""
            fault = _estrai_fault_soap(xml_documenti)
            if fault and not _pst_servizio_sigp(base_url):
                if fallback_batches:
                    log.info(
                        "Catalogo documenti PST non disponibile su %s, provo registro alternativo: %s",
                        _pst_servizio_proxy(base_url),
                        fault,
                    )
                    xml_documenti = ""
                else:
                    raise RuntimeError(f"Il PST ha restituito una SOAP Fault: {fault}")
            if fault and _pst_servizio_sigp(base_url):
                log.warning("Catalogo documenti SIGP qbuilder in snapshot non disponibile: %s", fault)
                xml_documenti = ""

            fallback_motivo = ""
            try:
                fascicoli = _parse_fascicoli_xml(xml_ricerca)
            except Exception as pst_error:
                if not _pst_servizio_sigp(base_url):
                    raise
                fallback_motivo = str(pst_error)
                log.warning("SIGP ricerca-snapshot esatta in fallback guidato: %s", fallback_motivo)
                fascicoli = []
            profili = _parse_fascicoli_xml(xml_profilo) if xml_profilo else []
            if profili:
                profilo = profili[0]
                if fascicoli:
                    fascicoli[0].update({
                        key: value
                        for key, value in profilo.items()
                        if value not in (None, "", [])
                    })
                else:
                    fascicoli = [profilo]
            if not fascicoli and _pst_namespace_qbuilder(base_url):
                for fallback_info in fallback_batches:
                    fallback_base_url = str(fallback_info.get("base_url") or "")
                    fallback_codice = str(fallback_info.get("codice_ufficio") or codice_pst or tribunale).strip()
                    try:
                        fallback_ricerca_index = int(fallback_info.get("ricerca_index"))
                        fallback_documenti_index = int(fallback_info.get("documenti_index"))
                        fallback_profile_index = fallback_info.get("profilo_index")
                        fallback_sigp_atti_index = fallback_info.get("sigp_atti_index")

                        fallback_xml_ricerca = (
                            batch_results[fallback_ricerca_index][0].decode("utf-8", "replace")
                            if len(batch_results) > fallback_ricerca_index
                            else ""
                        )
                        fallback_fault = _estrai_fault_soap(fallback_xml_ricerca)
                        if fallback_fault:
                            search_faults.append(fallback_fault)
                            log.info(
                                "PST ricerca-snapshot: servizio %s ignorato per SOAP Fault: %s",
                                _pst_servizio_proxy(fallback_base_url),
                                fallback_fault,
                            )
                            continue
                        if _pst_xml_response_valida_senza_fault(fallback_xml_ricerca):
                            valid_search_response_seen = True

                        fallback_xml_profilo = (
                            batch_results[int(fallback_profile_index)][0].decode("utf-8", "replace")
                            if fallback_profile_index is not None
                            and len(batch_results) > int(fallback_profile_index)
                            else ""
                        )
                        fallback_xml_documenti = (
                            batch_results[fallback_documenti_index][0].decode("utf-8", "replace")
                            if len(batch_results) > fallback_documenti_index
                            else ""
                        )
                        fallback_xml_sigp_atti = (
                            batch_results[int(fallback_sigp_atti_index)][0].decode("utf-8", "replace")
                            if fallback_sigp_atti_index is not None
                            and len(batch_results) > int(fallback_sigp_atti_index)
                            else ""
                        )
                        if _estrai_fault_soap(fallback_xml_profilo):
                            fallback_xml_profilo = ""
                        if _estrai_fault_soap(fallback_xml_documenti):
                            fallback_xml_documenti = ""
                        if _estrai_fault_soap(fallback_xml_sigp_atti):
                            fallback_xml_sigp_atti = ""

                        fallback_fascicoli = _parse_fascicoli_xml(fallback_xml_ricerca)
                        fallback_profili = _parse_fascicoli_xml(fallback_xml_profilo) if fallback_xml_profilo else []
                        if fallback_profili:
                            profilo = fallback_profili[0]
                            if fallback_fascicoli:
                                fallback_fascicoli[0].update({
                                    key: value
                                    for key, value in profilo.items()
                                    if value not in (None, "", [])
                                })
                            else:
                                fallback_fascicoli = [profilo]
                        fallback_documenti = _parse_documenti_xml(fallback_xml_documenti)
                        if fallback_xml_sigp_atti:
                            fallback_documenti = _sigp_merge_documenti_con_profili(
                                fallback_documenti,
                                _sigp_documenti_minimi_da_ricerca_atti_xml(fallback_xml_sigp_atti),
                            )
                        if not fallback_fascicoli and not fallback_documenti:
                            continue

                        log.info(
                            "PST ricerca-snapshot: servizio %s vuoto, uso %s per %s/%s ufficio %s",
                            _pst_servizio_proxy(base_url),
                            _pst_servizio_proxy(fallback_base_url),
                            numero_rg,
                            anno_rg,
                            fallback_codice,
                        )
                        base_url = fallback_base_url
                        codice_pst = fallback_codice
                        url_ricerca = str(fallback_info.get("url_ricerca") or _pst_url_ricerca(fallback_base_url))
                        url_documenti = str(
                            fallback_info.get("url_documenti") or _pst_url_documenti(fallback_base_url)
                        )
                        xml_ricerca = fallback_xml_ricerca
                        xml_profilo = fallback_xml_profilo
                        xml_documenti = fallback_xml_documenti
                        xml_sigp_atti = fallback_xml_sigp_atti
                        fascicoli = fallback_fascicoli
                        break
                    except Exception as fallback_error:
                        log.warning(
                            "PST ricerca-snapshot: fallback servizio %s non riuscito: %s",
                            _pst_servizio_proxy(fallback_base_url),
                            fallback_error,
                        )
            if _pst_servizio_sigp(base_url) and not fascicoli:
                fascicoli = [
                    _sigp_fascicolo_fallback(
                        codice_ufficio=codice_pst,
                        numero_rg=numero_rg,
                        anno_rg=anno_rg,
                        cf_avvocato=cf_avvocato,
                        motivo=fallback_motivo or "Il web service SIGP non ha restituito righe per la ricerca esatta.",
                    )
                ]

            documenti = _parse_documenti_xml(xml_documenti)
            if xml_sigp_atti:
                sigp_fault = _estrai_fault_soap(xml_sigp_atti)
                if sigp_fault:
                    log.warning("SIGP ricercaAtti in snapshot non disponibile: %s", sigp_fault)
                else:
                    documenti = _sigp_merge_documenti_con_profili(
                        documenti,
                        _sigp_documenti_minimi_da_ricerca_atti_xml(xml_sigp_atti),
                    )
            if not fascicoli and documenti:
                ufficio = _risolvi_ufficio_da_snapshot(codice_pst) or {}
                fascicoli = [
                    {
                        "numero_rg": numero_rg,
                        "anno_rg": anno_rg,
                        "codice_ufficio": codice_pst,
                        "nome_ufficio": str(ufficio.get("nome") or data.get("ufficio_nome") or tribunale),
                        "ruolo": "",
                        "oggetto": str(data.get("oggetto") or ""),
                        "stato": "",
                        "data_iscrizione": "",
                        "data_udienza": "",
                        "parti": [],
                        "controparti": [],
                    }
                ]
            if not fascicoli and not documenti and search_faults and not valid_search_response_seen:
                raise RuntimeError(_pst_ricerca_vuota_fault_message(search_faults))
            if session_entry:
                _update_pst_session(
                    session_entry["session_id"],
                    tribunale=tribunale,
                    base_url=base_url,
                    cf_avvocato=cf_avvocato,
                    auth_ready=True,
                )

            fascicolo_row = fascicoli[0] if fascicoli else {}
            snapshot = None
            if fascicolo_row or documenti:
                ufficio = _risolvi_ufficio_da_snapshot(str(fascicolo_row.get("codice_ufficio") or codice_pst))
                tabella_policy = _pst_tabella_ministeriale_policy(base_url)
                fascicolo = {
                    "codice_ufficio": str(fascicolo_row.get("codice_ufficio") or codice_pst or tribunale),
                    "ufficio_codice": str(fascicolo_row.get("codice_ufficio") or codice_pst or tribunale),
                    "ufficio_nome": str(
                        fascicolo_row.get("nome_ufficio")
                        or (ufficio or {}).get("nome")
                        or data.get("ufficio_nome")
                        or ""
                    ),
                    "numero": str(fascicolo_row.get("numero_rg") or numero_rg),
                    "numero_rg": str(fascicolo_row.get("numero_rg") or numero_rg),
                    "anno": int(fascicolo_row.get("anno_rg") or anno_rg),
                    "anno_rg": int(fascicolo_row.get("anno_rg") or anno_rg),
                    "id_fascicolo": str(fascicolo_row.get("id_fascicolo") or data.get("id_fascicolo") or ""),
                    "procedimento": str(fascicolo_row.get("ruolo") or ""),
                    "oggetto": str(fascicolo_row.get("oggetto") or data.get("oggetto") or ""),
                    "stato": str(fascicolo_row.get("stato") or ""),
                    "data_iscrizione": str(fascicolo_row.get("data_iscrizione") or ""),
                    "data_udienza": str(fascicolo_row.get("data_udienza") or ""),
                    "ultima_attivita": str(
                        fascicolo_row.get("data_udienza")
                        or fascicolo_row.get("data_iscrizione")
                        or ""
                    ),
                    "parti": fascicolo_row.get("parti") if isinstance(fascicolo_row.get("parti"), list) else [],
                    "controparti": fascicolo_row.get("controparti") if isinstance(fascicolo_row.get("controparti"), list) else [],
                    "servizio_pst": _pst_servizio_proxy(base_url),
                    "registro_portale": _pst_tipo_ricerca_qbuilder(base_url),
                    "tabella_ministeriale": str(tabella_policy.get("tabella") or ""),
                }
                snapshot = {
                    "fascicolo": fascicolo,
                    "documenti": documenti,
                    "catalogo": documenti,
                    "depositi": [],
                    "sezioni": {"documenti_fascicolo": documenti},
                    "eventi": [],
                    "parti": fascicolo["parti"],
                }

            self._send_json({
                "ok": True,
                "fascicoli": fascicoli,
                "snapshot": snapshot,
                "documenti": documenti,
                "raw_xml": xml_ricerca[:2000] if not fascicoli else None,
                **_pst_session_response_fields(_get_pst_session(session_entry["session_id"], refresh=False) or session_entry),
            })
        except Exception as e:
            log.error("Errore PST ricerca-snapshot: %s", e)
            self._send_json({"ok": False, "errore": str(e)}, 500)

    def _pst_documenti(self):
        """
        POST /pst/documenti
        Body: {codice_ufficio, numero_rg, anno_rg, cf_avvocato?, cert_thumbprint?}
        Response: {ok, documenti:[...]}
        """
        if not _curl_disponibile():
            self._send_json({
                "ok": False,
                "errore": "curl non disponibile nel PATH",
            }, 400)
            return

        data = self._read_json()
        codice = data.get("codice_ufficio", "").strip()
        rg = data.get("numero_rg", "").strip()
        anno = int(data.get("anno_rg") or 0)

        if not (codice and rg and anno):
            self._send_json({
                "ok": False,
                "errore": "Campi obbligatori: codice_ufficio, numero_rg, anno_rg",
            }, 400)
            return

        try:
            base_url = _risolvi_base_pst_runtime(codice)
            url_documenti = _pst_url_documenti(base_url)
            codice_pst = _risolvi_codice_ufficio_pst(codice)
        except Exception as e:
            self._send_json({"ok": False, "errore": str(e)}, 503)
            return

        try:
            servizio_hint = _pst_servizio_ministeriale_da_payload(data)
            base_url = _pst_base_url_con_preferenza_payload(base_url, data)
            url_documenti = _pst_url_documenti(base_url)
            requested_session_id = str(data.get("pst_session_id") or "").strip()
            existing_session = _resolve_pst_session_entry(requested_session_id) if requested_session_id else None
            session_base_url = str((existing_session or {}).get("base_url") or "").strip()
            if session_base_url and _pst_namespace_qbuilder(session_base_url):
                base_url = (
                    _pst_base_url_con_servizio(session_base_url, servizio_hint)
                    if servizio_hint
                    else session_base_url
                )
                url_documenti = _pst_url_documenti(base_url)
            cert_thumbprint = _require_certificato_pst(
                data.get("cert_thumbprint")
            )
            cf_avvocato = _cf_avvocato_pst(data.get("cf_avvocato", ""), cert_thumbprint)
            if _pst_namespace_qbuilder(base_url) and not cf_avvocato:
                raise RuntimeError(
                    "Impossibile determinare il codice fiscale dell'avvocato dal certificato selezionato.\n"
                    "Riselezionare il certificato CNS/CIE oppure indicare esplicitamente il codice fiscale."
                )
            session_entry, _session_created = _ensure_pst_session_entry(
                requested_session_id,
                tribunale=codice,
                base_url=base_url,
                cf_avvocato=cf_avvocato,
                cert_thumbprint=cert_thumbprint,
                purpose="view",
                cert_key=str(data.get("cert_key") or cert_thumbprint or ""),
                cert_preferences=data.get("cert_preferences") if isinstance(data.get("cert_preferences"), dict) else None,
            )
            if session_entry and not cf_avvocato:
                cf_avvocato = str(session_entry.get("cf_avvocato") or "").strip()
            with _pst_session_lock_for(session_entry):
                session_entry, prefer_cookie_only = _pst_prepare_authenticated_session(
                    session_entry,
                    tribunale=codice,
                    base_url=base_url,
                    cf_avvocato=cf_avvocato,
                    cert_thumbprint=cert_thumbprint,
                    force=_session_created,
                )
                cookie_file = str((session_entry or {}).get("cookie_file") or "")
            soap = _soap_documenti_body(
                base_url=base_url,
                codice_ufficio=codice_pst,
                numero_rg=rg,
                anno_rg=anno,
                cf_avvocato=cf_avvocato,
                sub_procedimento=str(data.get("sub_procedimento") or data.get("subpro") or "").strip(),
            )
            extra_headers = [f"X-WASP-User: {cf_avvocato}"] if _pst_namespace_qbuilder(base_url) else []
            is_sigp = _pst_servizio_sigp(base_url)
            xml_sigp_atti = ""
            if is_sigp:
                batch_results = _soap_call_pst_session_batch_raw(
                    [
                        {
                            "url": url_documenti,
                            "soap_body": soap,
                            "extra_headers": extra_headers,
                            "soap_action": "",
                            "cookie_file": cookie_file,
                        },
                        {
                            "url": url_documenti,
                            "soap_body": _soap_sigp_ricerca_atti_body(codice_pst, rg, anno),
                            "extra_headers": extra_headers,
                            "soap_action": "ricercaAtti",
                            "cookie_file": cookie_file,
                        },
                    ],
                    cert_thumbprint=cert_thumbprint,
                    cookie_file=cookie_file,
                    prefer_cookie_only=prefer_cookie_only,
                )
                xml_resp = batch_results[0][0].decode("utf-8", "replace") if batch_results else ""
                xml_sigp_atti = batch_results[1][0].decode("utf-8", "replace") if len(batch_results) > 1 else ""
            else:
                xml_resp = _soap_call_pst_session(
                    url=url_documenti,
                    soap_body=soap,
                    cert_thumbprint=cert_thumbprint,
                    extra_headers=extra_headers,
                    cookie_file=cookie_file,
                    prefer_cookie_only=prefer_cookie_only,
                )
            fault = _estrai_fault_soap(xml_resp)
            if fault and not is_sigp:
                raise RuntimeError(f"Il PST ha restituito una SOAP Fault: {fault}")
            if fault and is_sigp:
                log.warning("Catalogo documenti SIGP qbuilder non disponibile: %s", fault)
                documenti = []
            else:
                documenti = _parse_documenti_xml(xml_resp)
            if is_sigp and xml_sigp_atti:
                sigp_fault = _estrai_fault_soap(xml_sigp_atti)
                if sigp_fault:
                    log.warning("SIGP ricercaAtti nel catalogo documenti non disponibile: %s", sigp_fault)
                else:
                    documenti = _sigp_merge_documenti_con_profili(
                        documenti,
                        _sigp_documenti_minimi_da_ricerca_atti_xml(xml_sigp_atti),
                    )
            if session_entry:
                _update_pst_session(
                    session_entry["session_id"],
                    tribunale=codice,
                    base_url=base_url,
                    cf_avvocato=cf_avvocato,
                    auth_ready=True,
                )
            self._send_json({
                "ok": True,
                "documenti": documenti,
                "raw_xml": xml_resp[:2000] if not documenti else None,
                **_pst_session_response_fields(session_entry),
            })
        except Exception as e:
            log.error("Errore PST documenti: %s", e)
            self._send_json({"ok": False, "errore": str(e)}, 500)

    def _pst_fascicolo_snapshot(self):
        """
        POST /pst/fascicolo-snapshot
        Carica in una sola sessione di visualizzazione il catalogo necessario
        al wizard: dati pratica e documenti disponibili, senza scaricare file.
        """
        if not _curl_disponibile():
            self._send_json({"ok": False, "errore": "curl non disponibile nel PATH"}, 400)
            return

        data = self._read_json()
        selection = data.get("selection") if isinstance(data.get("selection"), dict) else {}
        codice = str(
            data.get("codice_ufficio")
            or data.get("tribunale")
            or selection.get("ufficio_codice")
            or ""
        ).strip()
        rg = str(data.get("numero_rg") or selection.get("numero") or "").strip()
        anno = int(data.get("anno_rg") or selection.get("anno") or 0)

        if not (codice and rg and anno):
            self._send_json({
                "ok": False,
                "errore": "Campi obbligatori: codice_ufficio, numero_rg, anno_rg",
            }, 400)
            return

        try:
            servizio_hint = _pst_servizio_ministeriale_da_payload(data, selection)
            base_url = _risolvi_base_pst_runtime(codice)
            base_url = _pst_base_url_con_preferenza_payload(base_url, data, selection)
            url_documenti = _pst_url_documenti(base_url)
            codice_pst = _risolvi_codice_ufficio_pst(codice)
        except Exception as e:
            self._send_json({"ok": False, "errore": str(e)}, 503)
            return

        try:
            requested_session_id = str(data.get("pst_session_id") or "").strip()
            existing_session = _resolve_pst_session_entry(requested_session_id) if requested_session_id else None
            session_base_url = str((existing_session or {}).get("base_url") or "").strip()
            if session_base_url and _pst_namespace_qbuilder(session_base_url):
                base_url = (
                    _pst_base_url_con_servizio(session_base_url, servizio_hint)
                    if servizio_hint
                    else session_base_url
                )
                url_documenti = _pst_url_documenti(base_url)
            cert_thumbprint = _require_certificato_pst(data.get("cert_thumbprint"))
            cf_avvocato = _cf_avvocato_pst(data.get("cf_avvocato", ""), cert_thumbprint)
            if _pst_namespace_qbuilder(base_url) and not cf_avvocato:
                raise RuntimeError(
                    "Impossibile determinare il codice fiscale dell'avvocato dal certificato selezionato.\n"
                    "Riselezionare il certificato CNS/CIE oppure indicare esplicitamente il codice fiscale."
                )
            session_entry, _session_created = _ensure_pst_session_entry(
                requested_session_id,
                tribunale=codice,
                base_url=base_url,
                cf_avvocato=cf_avvocato,
                cert_thumbprint=cert_thumbprint,
                purpose="view",
                cert_key=str(data.get("cert_key") or cert_thumbprint or ""),
                cert_preferences=data.get("cert_preferences") if isinstance(data.get("cert_preferences"), dict) else None,
            )
            if session_entry and not cf_avvocato:
                cf_avvocato = str(session_entry.get("cf_avvocato") or "").strip()

            with _pst_session_lock_for(session_entry):
                session_entry, prefer_cookie_only = _pst_prepare_authenticated_session(
                    session_entry,
                    tribunale=codice,
                    base_url=base_url,
                    cf_avvocato=cf_avvocato,
                    cert_thumbprint=cert_thumbprint,
                    force=_session_created,
                )
                cookie_file = str((session_entry or {}).get("cookie_file") or "")
                soap = _soap_documenti_body(
                    base_url=base_url,
                    codice_ufficio=codice_pst,
                    numero_rg=rg,
                    anno_rg=anno,
                    cf_avvocato=cf_avvocato,
                    sub_procedimento=str(
                        data.get("sub_procedimento")
                        or selection.get("sub_procedimento")
                        or data.get("subpro")
                        or ""
                    ).strip(),
                )
                extra_headers = [f"X-WASP-User: {cf_avvocato}"] if _pst_namespace_qbuilder(base_url) else []
                is_sigp = _pst_servizio_sigp(base_url)
                xml_sigp_atti = ""
                if is_sigp:
                    batch_results = _soap_call_pst_session_batch_raw(
                        [
                            {
                                "url": url_documenti,
                                "soap_body": soap,
                                "extra_headers": extra_headers,
                                "soap_action": "",
                                "cookie_file": cookie_file,
                            },
                            {
                                "url": url_documenti,
                                "soap_body": _soap_sigp_ricerca_atti_body(codice_pst, rg, anno),
                                "extra_headers": extra_headers,
                                "soap_action": "ricercaAtti",
                                "cookie_file": cookie_file,
                            },
                        ],
                        cert_thumbprint=cert_thumbprint,
                        cookie_file=cookie_file,
                        prefer_cookie_only=prefer_cookie_only,
                    )
                    xml_resp = batch_results[0][0].decode("utf-8", "replace") if batch_results else ""
                    xml_sigp_atti = batch_results[1][0].decode("utf-8", "replace") if len(batch_results) > 1 else ""
                else:
                    xml_resp = _soap_call_pst_session(
                        url=url_documenti,
                        soap_body=soap,
                        cert_thumbprint=cert_thumbprint,
                        extra_headers=extra_headers,
                        cookie_file=cookie_file,
                        prefer_cookie_only=prefer_cookie_only,
                    )
                fault = _estrai_fault_soap(xml_resp)
                if fault and not is_sigp:
                    raise RuntimeError(f"Il PST ha restituito una SOAP Fault: {fault}")
                if fault and is_sigp:
                    log.warning("Catalogo snapshot SIGP qbuilder non disponibile: %s", fault)
                    documenti = []
                else:
                    documenti = _parse_documenti_xml(xml_resp)
                if is_sigp and xml_sigp_atti:
                    sigp_fault = _estrai_fault_soap(xml_sigp_atti)
                    if sigp_fault:
                        log.warning("SIGP ricercaAtti nello snapshot non disponibile: %s", sigp_fault)
                    else:
                        documenti = _sigp_merge_documenti_con_profili(
                            documenti,
                            _sigp_documenti_minimi_da_ricerca_atti_xml(xml_sigp_atti),
                        )

            if session_entry:
                _update_pst_session(
                    session_entry["session_id"],
                    tribunale=codice,
                    base_url=base_url,
                    cf_avvocato=cf_avvocato,
                    auth_ready=True,
                )

            fascicolo = {
                "codice_ufficio": codice,
                "ufficio_codice": codice,
                "ufficio_nome": selection.get("ufficio_nome") or data.get("ufficio_nome") or "",
                "numero": rg,
                "numero_rg": rg,
                "anno": anno,
                "anno_rg": anno,
                "id_fascicolo": selection.get("id_fascicolo") or data.get("id_fascicolo") or "",
                "procedimento": selection.get("procedimento") or "",
                "oggetto": selection.get("oggetto") or "",
                "stato": selection.get("stato") or "",
                "parti": selection.get("parti") if isinstance(selection.get("parti"), list) else [],
                "controparti": selection.get("controparti") if isinstance(selection.get("controparti"), list) else [],
            }
            snapshot = {
                "fascicolo": fascicolo,
                "documenti": documenti,
                "catalogo": documenti,
                "depositi": [],
                "sezioni": {"documenti_fascicolo": documenti},
                "eventi": [],
                "parti": fascicolo["parti"],
            }
            self._send_json({
                "ok": True,
                "snapshot": snapshot,
                "documenti": documenti,
                "raw_xml": xml_resp[:2000] if not documenti else None,
                **_pst_session_response_fields(session_entry),
            })
        except Exception as e:
            log.error("Errore PST snapshot fascicolo: %s", e)
            self._send_json({"ok": False, "errore": str(e)}, 500)

    def _pdp_ricerca(self):
        data = self._read_json()
        ufficio = str(data.get("ufficio") or data.get("codice_ufficio") or "").strip()
        if not ufficio:
            self._send_json({"ok": False, "errore": "Campo 'ufficio' obbligatorio"}, 400)
            return
        if not _portale_wsdl_diretto_abilitato("pdp"):
            self._send_json(_portale_browser_assist_payload("pdp", "ricerca"))
            return
        if not _curl_disponibile():
            self._send_json({"ok": False, "errore": "curl non disponibile nel PATH"}, 400)
            return

        try:
            cert_thumbprint = _require_certificato_pst(data.get("cert_thumbprint"))
            cf_avvocato = _require_cf_avvocato_locale(data.get("cf_avvocato", ""), cert_thumbprint)
            payload: Dict[str, Any] = {
                "codiceFiscaleAvvocato": cf_avvocato,
                "codiceUfficio": _risolvi_codice_ufficio_pdp_runtime(ufficio),
                "maxRisultati": _parse_optional_int(data.get("max_risultati")) or 50,
            }
            numero_rg = str(data.get("numero_rg") or "").strip()
            anno_rg = _parse_optional_int(data.get("anno_rg"))
            nome_imputato = str(data.get("nome_imputato") or data.get("assistito") or "").strip()
            tipo_registro = str(data.get("tipo_registro") or data.get("registro") or "").strip()
            if numero_rg:
                payload["numeroRG"] = numero_rg
            if anno_rg:
                payload["annoRG"] = anno_rg
            if nome_imputato:
                payload["nominativoImputato"] = nome_imputato
            if tipo_registro:
                payload["tipoRegistro"] = tipo_registro
            risposta = _soap_call_zeep_operation_via_curl(
                wsdl_url=_WSDL_RICERCA_PENALE,
                operation_name="ricercaFascicoliPenale",
                payload=payload,
                cert_thumbprint=cert_thumbprint,
            )
            fascicoli = _parse_pdp_fascicoli_response(risposta)
            self._send_json({"ok": True, "fascicoli": fascicoli})
        except Exception as e:
            log.error("Errore PDP ricerca: %s", e)
            manual_payload = _portale_manual_required_payload("pdp", e, "ricerca")
            if manual_payload:
                self._send_json(manual_payload)
                return
            self._send_json({"ok": False, "errore": str(e)}, 500)

    def _pdp_documenti(self):
        data = self._read_json()
        codice_ufficio = str(data.get("codice_ufficio") or data.get("ufficio") or "").strip()
        numero_rg = str(data.get("numero_rg") or "").strip()
        anno_rg = _parse_optional_int(data.get("anno_rg"))
        if not (codice_ufficio and numero_rg and anno_rg):
            self._send_json(
                {"ok": False, "errore": "Campi obbligatori: codice_ufficio, numero_rg, anno_rg"},
                400,
            )
            return
        if not _portale_wsdl_diretto_abilitato("pdp"):
            self._send_json(_portale_browser_assist_payload("pdp", "documenti"))
            return
        if not _curl_disponibile():
            self._send_json({"ok": False, "errore": "curl non disponibile nel PATH"}, 400)
            return

        try:
            cert_thumbprint = _require_certificato_pst(data.get("cert_thumbprint"))
            cf_avvocato = _require_cf_avvocato_locale(data.get("cf_avvocato", ""), cert_thumbprint)
            risposta = _soap_call_zeep_operation_via_curl(
                wsdl_url=_WSDL_CONSULTA_PENALE,
                operation_name="consultaDocumentiPenale",
                payload={
                    "codiceFiscaleAvvocato": cf_avvocato,
                    "codiceUfficio": codice_ufficio,
                    "numeroRG": numero_rg,
                    "annoRG": anno_rg,
                },
                cert_thumbprint=cert_thumbprint,
            )
            documenti = _parse_pdp_documenti_response(risposta)
            self._send_json({"ok": True, "documenti": documenti})
        except Exception as e:
            log.error("Errore PDP documenti: %s", e)
            manual_payload = _portale_manual_required_payload("pdp", e, "documenti")
            if manual_payload:
                self._send_json(manual_payload)
                return
            self._send_json({"ok": False, "errore": str(e)}, 500)

    def _pat_ricerca(self):
        data = self._read_json()
        ufficio = str(data.get("ufficio") or data.get("codice_ufficio") or "").strip()
        if not ufficio:
            self._send_json({"ok": False, "errore": "Campo 'ufficio' obbligatorio"}, 400)
            return
        if not _portale_wsdl_diretto_abilitato("pat"):
            self._send_json(_portale_browser_assist_payload("pat", "ricerca"))
            return
        if not _curl_disponibile():
            self._send_json({"ok": False, "errore": "curl non disponibile nel PATH"}, 400)
            return

        try:
            cert_thumbprint = _require_certificato_pst(data.get("cert_thumbprint"))
            cf_avvocato = _require_cf_avvocato_locale(data.get("cf_avvocato", ""), cert_thumbprint)
            payload: Dict[str, Any] = {
                "codiceFiscaleAvvocato": cf_avvocato,
                "codiceUfficio": _risolvi_codice_ufficio_pat_runtime(ufficio),
                "maxRisultati": _parse_optional_int(data.get("max_risultati")) or 50,
            }
            numero_ricorso = str(data.get("numero_ricorso") or data.get("numero") or "").strip()
            anno = _parse_optional_int(data.get("anno"))
            nome_ricorrente = str(data.get("nome_ricorrente") or data.get("assistito") or "").strip()
            materia = str(data.get("materia") or "").strip()
            if numero_ricorso:
                payload["numeroRicorso"] = numero_ricorso
            if anno:
                payload["anno"] = anno
            if nome_ricorrente:
                payload["nominativoRicorrente"] = nome_ricorrente
            if materia:
                payload["materia"] = materia
            risposta = _soap_call_zeep_operation_via_curl(
                wsdl_url=_WSDL_RICERCA_AMM,
                operation_name="ricercaRicorsi",
                payload=payload,
                cert_thumbprint=cert_thumbprint,
            )
            fascicoli = _parse_pat_fascicoli_response(risposta)
            self._send_json({"ok": True, "fascicoli": fascicoli})
        except Exception as e:
            log.error("Errore PAT ricerca: %s", e)
            manual_payload = _portale_manual_required_payload("pat", e, "ricerca")
            if manual_payload:
                self._send_json(manual_payload)
                return
            self._send_json({"ok": False, "errore": str(e)}, 500)

    def _pat_documenti(self):
        data = self._read_json()
        codice_ufficio = str(data.get("codice_ufficio") or data.get("ufficio") or "").strip()
        numero_ricorso = str(data.get("numero_ricorso") or data.get("numero") or "").strip()
        anno = _parse_optional_int(data.get("anno"))
        if not (codice_ufficio and numero_ricorso and anno):
            self._send_json(
                {"ok": False, "errore": "Campi obbligatori: codice_ufficio, numero_ricorso, anno"},
                400,
            )
            return
        if not _portale_wsdl_diretto_abilitato("pat"):
            self._send_json(_portale_browser_assist_payload("pat", "documenti"))
            return
        if not _curl_disponibile():
            self._send_json({"ok": False, "errore": "curl non disponibile nel PATH"}, 400)
            return

        try:
            cert_thumbprint = _require_certificato_pst(data.get("cert_thumbprint"))
            cf_avvocato = _require_cf_avvocato_locale(data.get("cf_avvocato", ""), cert_thumbprint)
            risposta = _soap_call_zeep_operation_via_curl(
                wsdl_url=_WSDL_CONSULTA_AMM,
                operation_name="consultazioneDocumenti",
                payload={
                    "codiceFiscaleAvvocato": cf_avvocato,
                    "codiceUfficio": codice_ufficio,
                    "numeroRicorso": numero_ricorso,
                    "anno": anno,
                },
                cert_thumbprint=cert_thumbprint,
            )
            documenti = _parse_pat_documenti_response(risposta)
            self._send_json({"ok": True, "documenti": documenti})
        except Exception as e:
            log.error("Errore PAT documenti: %s", e)
            manual_payload = _portale_manual_required_payload("pat", e, "documenti")
            if manual_payload:
                self._send_json(manual_payload)
                return
            self._send_json({"ok": False, "errore": str(e)}, 500)

    def _ptt_ricerca(self):
        data = self._read_json()
        commissione = str(data.get("commissione") or data.get("codice_commissione") or "").strip()
        if not commissione:
            self._send_json({"ok": False, "errore": "Campo 'commissione' obbligatorio"}, 400)
            return
        if not _portale_wsdl_diretto_abilitato("ptt"):
            self._send_json(_portale_browser_assist_payload("ptt", "ricerca"))
            return
        if not _curl_disponibile():
            self._send_json({"ok": False, "errore": "curl non disponibile nel PATH"}, 400)
            return

        try:
            cert_thumbprint = _require_certificato_pst(data.get("cert_thumbprint"))
            cf_avvocato = _require_cf_avvocato_locale(data.get("cf_avvocato", ""), cert_thumbprint)
            payload: Dict[str, Any] = {
                "codiceFiscaleAvvocato": cf_avvocato,
                "codiceCommissione": _risolvi_codice_commissione_ptt_runtime(commissione),
                "maxRisultati": _parse_optional_int(data.get("max_risultati")) or 50,
            }
            numero_rgt = str(data.get("numero_rgt") or data.get("numero") or "").strip()
            anno_rgt = _parse_optional_int(data.get("anno_rgt") or data.get("anno"))
            nome_ricorrente = str(data.get("nome_ricorrente") or data.get("assistito") or "").strip()
            tipo = str(data.get("tipo") or data.get("materia") or "").strip()
            if numero_rgt:
                payload["numeroRGT"] = numero_rgt
            if anno_rgt:
                payload["annoRGT"] = anno_rgt
            if nome_ricorrente:
                payload["nominativoRicorrente"] = nome_ricorrente
            if tipo:
                payload["tipoRicorso"] = tipo
            risposta = _soap_call_zeep_operation_via_curl(
                wsdl_url=_WSDL_RICERCA_TRIB,
                operation_name="ricercaFascicoliTributari",
                payload=payload,
                cert_thumbprint=cert_thumbprint,
            )
            fascicoli = _parse_ptt_fascicoli_response(risposta)
            self._send_json({"ok": True, "fascicoli": fascicoli})
        except Exception as e:
            log.error("Errore PTT ricerca: %s", e)
            manual_payload = _portale_manual_required_payload("ptt", e, "ricerca")
            if manual_payload:
                self._send_json(manual_payload)
                return
            self._send_json({"ok": False, "errore": str(e)}, 500)

    def _ptt_documenti(self):
        data = self._read_json()
        codice_commissione = str(data.get("codice_commissione") or data.get("commissione") or "").strip()
        numero_rgt = str(data.get("numero_rgt") or data.get("numero") or "").strip()
        anno_rgt = _parse_optional_int(data.get("anno_rgt") or data.get("anno"))
        if not (codice_commissione and numero_rgt and anno_rgt):
            self._send_json(
                {"ok": False, "errore": "Campi obbligatori: codice_commissione, numero_rgt, anno_rgt"},
                400,
            )
            return
        if not _portale_wsdl_diretto_abilitato("ptt"):
            self._send_json(_portale_browser_assist_payload("ptt", "documenti"))
            return
        if not _curl_disponibile():
            self._send_json({"ok": False, "errore": "curl non disponibile nel PATH"}, 400)
            return

        try:
            cert_thumbprint = _require_certificato_pst(data.get("cert_thumbprint"))
            cf_avvocato = _require_cf_avvocato_locale(data.get("cf_avvocato", ""), cert_thumbprint)
            risposta = _soap_call_zeep_operation_via_curl(
                wsdl_url=_WSDL_CONSULTA_TRIB,
                operation_name="consultaDocumentiTributari",
                payload={
                    "codiceFiscaleAvvocato": cf_avvocato,
                    "codiceCommissione": codice_commissione,
                    "numeroRGT": numero_rgt,
                    "annoRGT": anno_rgt,
                },
                cert_thumbprint=cert_thumbprint,
            )
            documenti = _parse_ptt_documenti_response(risposta)
            self._send_json({"ok": True, "documenti": documenti})
        except Exception as e:
            log.error("Errore PTT documenti: %s", e)
            manual_payload = _portale_manual_required_payload("ptt", e, "documenti")
            if manual_payload:
                self._send_json(manual_payload)
                return
            self._send_json({"ok": False, "errore": str(e)}, 500)

    def _pst_download_documento(self):
        """
        POST /pst/download-documento
        Body: {
            tribunale|codice_ufficio,
            id_documento,
            nome_documento?,
            id_cat?,
            data_documento?,
            id_deposito_esterno?,
            id_deposito_pct?,
            tipo_atto?,
            cf_avvocato?,
            cert_thumbprint?,
            original?
        }
        Response: {ok, file:{...}}
        """
        if not _curl_disponibile():
            self._send_json({
                "ok": False,
                "errore": "curl non disponibile nel PATH",
            }, 400)
            return

        data = self._read_json()
        tribunale = (
            str(data.get("tribunale") or data.get("codice_ufficio") or "").strip()
        )
        id_documento = str(data.get("id_documento") or "").strip()
        nome_documento = str(data.get("nome_documento") or data.get("nome") or "").strip()

        if not tribunale:
            self._send_json({"ok": False, "errore": "Campo 'tribunale' obbligatorio."}, 400)
            return
        if not id_documento:
            self._send_json({"ok": False, "errore": "Campo 'id_documento' obbligatorio."}, 400)
            return

        try:
            requested_session_id = str(data.get("pst_session_id") or "").strip()
            download_purpose = _pst_existing_session_purpose(requested_session_id, "view")
            servizio_hint = _pst_servizio_ministeriale_da_payload(data)
            base_url = _risolvi_base_pst_runtime(tribunale)
            base_url = _pst_base_url_con_preferenza_payload(base_url, data)
            codice_pst = _risolvi_codice_ufficio_pst(tribunale)
            cert_thumbprint = _require_certificato_pst(
                data.get("cert_thumbprint")
            )
            cf_avvocato = _cf_avvocato_pst(data.get("cf_avvocato", ""), cert_thumbprint)
            requested_session_id = _reuse_view_session_id_if_available(
                requested_session_id,
                cert_thumbprint,
                tribunale,
            )
            existing_session = _resolve_pst_session_entry(requested_session_id) if requested_session_id else None
            session_base_url = str((existing_session or {}).get("base_url") or "").strip()
            if session_base_url and _pst_namespace_qbuilder(session_base_url):
                base_url = (
                    _pst_base_url_con_servizio(session_base_url, servizio_hint)
                    if servizio_hint
                    else session_base_url
                )
            session_entry, _session_created = _ensure_pst_session_entry(
                requested_session_id,
                tribunale=tribunale,
                base_url=base_url,
                cf_avvocato=cf_avvocato,
                cert_thumbprint=cert_thumbprint,
                purpose=download_purpose,
                cert_key=str(data.get("cert_key") or cert_thumbprint or ""),
                cert_preferences=data.get("cert_preferences") if isinstance(data.get("cert_preferences"), dict) else None,
            )
            if session_entry and not cf_avvocato:
                cf_avvocato = str(session_entry.get("cf_avvocato") or "").strip()
            with _pst_session_lock_for(session_entry):
                session_entry, prefer_cookie_only = _pst_prepare_authenticated_session(
                    session_entry,
                    tribunale=tribunale,
                    base_url=base_url,
                    cf_avvocato=cf_avvocato,
                    cert_thumbprint=cert_thumbprint,
                    force=_session_created,
                )
                cookie_file = str((session_entry or {}).get("cookie_file") or "")
                host = _pst_host(_pst_url_documenti(base_url))
                if host:
                    with _mTLS_required_lock:
                        _mTLS_required_hosts.add(host)
            file_payload = _pst_download_documento_payload(
                base_url=base_url,
                codice_ufficio=codice_pst,
                id_documento=id_documento,
                nome_documento=nome_documento,
                cert_thumbprint=cert_thumbprint,
                cf_avvocato=cf_avvocato,
                id_cat=str(data.get("id_cat") or "").strip(),
                id_repeatto=str(data.get("id_repeatto") or "").strip(),
                msg_id=str(data.get("msg_id") or "").strip(),
                data_documento=str(data.get("data_documento") or "").strip(),
                original=(
                    data.get("original", False)
                    if isinstance(data.get("original", False), bool)
                    else str(data.get("original", False)).strip().lower() not in {"", "0", "false", "no", "off"}
                ),
                cookie_file=cookie_file,
                prefer_cookie_only=prefer_cookie_only,
            )
            file_payload["origine"] = f"pst:{_pst_servizio_proxy(base_url) or 'download'}:{id_documento}"
            file_payload["id_deposito_esterno"] = str(data.get("id_deposito_esterno") or "").strip()
            file_payload["id_deposito_pct"] = str(data.get("id_deposito_pct") or "").strip()
            file_payload["tipo_atto"] = str(data.get("tipo_atto") or "").strip()
            if session_entry:
                _update_pst_session(
                    session_entry["session_id"],
                    tribunale=tribunale,
                    base_url=base_url,
                    cf_avvocato=cf_avvocato,
                    auth_ready=True,
                )
            self._send_json({
                "ok": True,
                "file": file_payload,
                **_pst_session_response_fields(session_entry),
            })
        except Exception as e:
            log.error("Errore PST download documento: %s", e)
            self._send_json({"ok": False, "errore": str(e)}, 500)

    def _pst_download_documenti_batch(self):
        """
        POST /pst/download-documenti-batch
        Body: {
            tribunale|codice_ufficio,
            documents:[{id_documento, nome_documento?, ...}],
            cert_thumbprint?,
            cf_avvocato?,
            preflight_auth?
        }
        Response: {ok, files:[...], failures:[...], preflight?}
        """
        if not _curl_disponibile():
            self._send_json({
                "ok": False,
                "errore": "curl non disponibile nel PATH",
            }, 400)
            return

        data = self._read_json()
        tribunale = (
            str(data.get("tribunale") or data.get("codice_ufficio") or "").strip()
        )
        documenti = data.get("documents") or data.get("documenti") or []

        if not tribunale:
            self._send_json({"ok": False, "errore": "Campo 'tribunale' obbligatorio."}, 400)
            return
        if not isinstance(documenti, list) or not documenti:
            self._send_json({"ok": False, "errore": "Campo 'documents' obbligatorio."}, 400)
            return

        try:
            requested_session_id = str(data.get("pst_session_id") or "").strip()
            download_purpose = _pst_existing_session_purpose(requested_session_id, "view")
            base_url = _risolvi_base_pst_runtime(tribunale)
            codice_pst = _risolvi_codice_ufficio_pst(tribunale)
            cert_thumbprint = _require_certificato_pst(
                data.get("cert_thumbprint")
            )
            cf_avvocato = _cf_avvocato_pst(data.get("cf_avvocato", ""), cert_thumbprint)
            requested_session_id = _reuse_view_session_id_if_available(
                requested_session_id,
                cert_thumbprint,
                tribunale,
            )
            existing_session = _resolve_pst_session_entry(requested_session_id) if requested_session_id else None
            session_base_url = str((existing_session or {}).get("base_url") or "").strip()
            if session_base_url and _pst_namespace_qbuilder(session_base_url):
                base_url = session_base_url
            session_kwargs = {
                "tribunale": tribunale,
                "base_url": base_url,
                "cf_avvocato": cf_avvocato,
                "cert_thumbprint": cert_thumbprint,
                "purpose": download_purpose,
                "cert_key": str(data.get("cert_key") or cert_thumbprint or ""),
                "cert_preferences": data.get("cert_preferences") if isinstance(data.get("cert_preferences"), dict) else None,
            }
            try:
                session_entry, session_created = _ensure_pst_session_entry(
                    requested_session_id,
                    **session_kwargs,
                )
            except RuntimeError as exc:
                if not (requested_session_id and "session_expired" in str(exc)):
                    raise
                log.info(
                    "PST download batch: sessione %s non piu' presente, apertura batch con nuova sessione",
                    requested_session_id,
                )
                session_entry, session_created = _ensure_pst_session_entry(
                    "",
                    **session_kwargs,
                )
            if session_entry and not cf_avvocato:
                cf_avvocato = str(session_entry.get("cf_avvocato") or "").strip()
            preflight_requested = bool(data.get("preflight_auth", False))
            with _pst_session_lock_for(session_entry):
                session_entry, _prefer_cookie_only = _pst_prepare_authenticated_session(
                    session_entry,
                    tribunale=tribunale,
                    base_url=base_url,
                    cf_avvocato=cf_avvocato,
                    cert_thumbprint=cert_thumbprint,
                    force=session_created or preflight_requested,
                )
                esito = _pst_download_documenti_batch_payloads(
                    base_url=base_url,
                    codice_ufficio=codice_pst,
                    cert_thumbprint=cert_thumbprint,
                    cf_avvocato=cf_avvocato,
                    documenti=documenti,
                    do_preflight=False,
                    cookie_file=str((session_entry or {}).get("cookie_file") or ""),
                    original=(
                        data.get("original", False)
                        if isinstance(data.get("original", False), bool)
                        else str(data.get("original", False)).strip().lower() not in {"", "0", "false", "no", "off"}
                    ),
                )
            if session_entry:
                _update_pst_session(
                    session_entry["session_id"],
                    tribunale=tribunale,
                    base_url=base_url,
                    cf_avvocato=cf_avvocato,
                    auth_ready=True,
                )
                esito.update(_pst_session_response_fields(session_entry))
            self._send_json(esito)
        except Exception as e:
            log.error("Errore PST download batch documenti: %s", e)
            self._send_json({"ok": False, "errore": str(e)}, 500)

    def _portal_assistant_start(self):
        try:
            session = _portal_assistant_start_local(self._read_json())
            self._send_json({"ok": True, **session})
        except Exception as e:
            log.error("Errore avvio sessione assistita portale: %s", e)
            self._send_json({"ok": False, "errore": str(e)}, 400)

    def _portal_assistant_status(self, path: str):
        try:
            match = re.fullmatch(r"/portal-assistant/session/([^/]+)/status", path)
            if not match:
                raise RuntimeError("Sessione assistita non valida.")
            session = _portal_assistant_get(match.group(1))
            self._send_json({"ok": True, **_portal_assistant_public(session)})
        except Exception as e:
            self._send_json({"ok": False, "errore": str(e)}, 404)

    def _portal_assistant_action(self, path: str):
        try:
            match = re.fullmatch(r"/portal-assistant/session/([^/]+)/(open|watch-downloads|collect|close|cancel)", path)
            if not match:
                raise RuntimeError("Azione sessione assistita non valida.")
            session_id, action = match.group(1), match.group(2)
            data = self._read_json()
            session = _portal_assistant_get(session_id)
            if action == "open":
                official_url = str(data.get("official_url") or session.get("official_url") or "").strip()
                if not official_url:
                    raise RuntimeError("URL ufficiale mancante.")
                webbrowser.open(official_url, new=1, autoraise=True)
                session["status"] = "portale_ufficiale_assistito_aperto"
                session["message"] = "Portale ufficiale aperto nella sessione assistita locale."
                _portal_assistant_save(session)
                self._send_json({"ok": True, **_portal_assistant_public(session)})
                return
            if action == "watch-downloads":
                session["status"] = "monitor_download_attivo"
                session["message"] = "Monitor download della sessione assistita attivo."
                _portal_assistant_save(session)
                self._send_json({"ok": True, **_portal_assistant_public(session)})
                return
            if action == "collect":
                collected = _portal_assistant_collect_local(
                    session_id,
                    limit=int(data.get("limit") or 50),
                    max_age_hours=int(data.get("max_age_hours") or 24),
                )
                self._send_json({"ok": True, **collected})
                return
            if action == "cancel":
                session["status"] = "sessione_annullata"
                session["files"] = []
                session["message"] = "Sessione assistita annullata. Nessun file verra' importato."
                try:
                    shutil.rmtree(str(session.get("downloads_dir") or ""), ignore_errors=True)
                except Exception:
                    pass
                _portal_assistant_save(session)
                self._send_json({"ok": True, **_portal_assistant_public(session)})
                return
            session["status"] = "sessione_chiusa"
            session["message"] = "Sessione assistita chiusa."
            _portal_assistant_save(session)
            self._send_json({"ok": True, **_portal_assistant_public(session)})
        except Exception as e:
            log.error("Errore azione sessione assistita portale: %s", e)
            self._send_json({"ok": False, "errore": str(e)}, 400)

    def _downloads_raccogli(self):
        """
        POST /downloads/raccogli
        Body: {expected_documents:[...], base_dir?, max_age_hours?, limit?}
        Response: {ok, files:[...], matched, expected, directories}
        """
        data = self._read_json()
        expected_documents = data.get("expected_documents") or []
        try:
            esito = _raccogli_download_recenti(
                expected_documents,
                base_dir=str(data.get("base_dir") or "").strip(),
                max_age_hours=int(data.get("max_age_hours") or 72),
                limit=int(data.get("limit") or 25),
            )
            if not esito["files"]:
                self._send_json({
                    "ok": False,
                    "errore": (
                        "Nessun download recente compatibile trovato nelle cartelle locali. "
                        "Scarica prima i file dal portale ufficiale nel browser e poi riprova."
                    ),
                    **esito,
                }, 404)
                return
            self._send_json({"ok": True, **esito})
        except Exception as e:
            log.error("Errore raccolta download locali: %s", e)
            self._send_json({"ok": False, "errore": str(e)}, 500)


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="IUSENTRA Local Signer — firma documenti con smart card e token CNS/CIE",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Esempi:
  python local_signer.py
  python local_signer.py --port 27272
  python local_signer.py --lib "C:\\Windows\\System32\\bit4xpki.dll"
  python local_signer.py --port 27272 --log DEBUG
        """,
    )
    parser.add_argument("--port", type=int, default=PORT, help=f"Porta HTTP (default: {PORT})")
    parser.add_argument("--lib", default=None, help="Percorso libreria PKCS#11")
    parser.add_argument("--log", default=LOG_LEVEL, help="Livello log (DEBUG/INFO/WARNING)")
    args = parser.parse_args()

    logging.getLogger().setLevel(getattr(logging, args.log.upper(), logging.INFO))

    if args.lib:
        os.environ["PCT_PKCS11_LIBRARY"] = args.lib
        _trova_libreria(args.lib)

    server = _ThreadingLocalSignerServer(("127.0.0.1", args.port), _Handler)

    lib = _trova_libreria()
    print_startup_banner(
        version=VERSION,
        port=args.port,
        platform_name=sys.platform,
        lib_path=lib,
        curl_available=_curl_disponibile(),
        token_info_fetcher=lambda lib_path: _info_token(lib_path),
    )

    if _pst_endpoint_configurato_e_legacy():
        print("  AVVISO PST       : endpoint legacy wspa.giustizia.it configurato")
        print(f"  Proxy PST attesi : {_PST_PROXY_PDA_URL}")
        print(f"                     {_PST_PROXY_SH_URL}")
        print("  Configurare      : variabile PCT_PST_BASE_URL con il proxy completo")
    elif _supporto_auto_pst_disponibile() and not os.getenv("PCT_PST_BASE_URL", "").strip():
        print("  PST              : risoluzione automatica dal registro uffici locale")
        print(f"  Proxy root       : {_PST_PROXY_SH_URL}")

    print("=" * 60)
    print(f"  Diagnostica: http://127.0.0.1:{args.port}/diagnosi")
    print("  Lasciare questa finestra aperta durante l'uso del gestionale.")
    print("  Premere Ctrl+C per fermare.\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nArresto LocalSigner.")
        server.shutdown()


if __name__ == "__main__":
    main()
