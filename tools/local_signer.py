#!/usr/bin/env python3
"""
HACS Local Signer — v1.5.23

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
    GET  /certificati            → elenca certificati Windows MY store
    GET  /seleziona-certificato  → apre dialog nativo Windows di selezione cert
    POST /firma                  → firma documento CAdES-BES
    POST /firma-batch            → firma più documenti con una sola sessione PIN
    POST /pst/preflight-auth     → verifica certificato + prompt PIN per accesso PST
    POST /pst/ricerca            → ricerca fascicoli PST (curl mTLS Windows)
    POST /pst/documenti          → documenti fascicolo PST (curl mTLS Windows)
    POST /downloads/raccogli     → raccoglie file già scaricati nei download locali
    GET  /pst/status             → stato connettività PST

Note sicurezza:
    - Ascolta SOLO su 127.0.0.1 (non accessibile da rete)
    - CORS abilitato solo per origini localhost/127.0.0.1
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
import subprocess
import sys
import tempfile
import threading
import unicodedata
import xml.etree.ElementTree as ET
from email import policy
from email.parser import BytesParser
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlparse

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

try:
    from pct.uffici_giudiziari import risolvi_base_pst as _risolvi_base_pst_hacs
    from pct.uffici_giudiziari import risolvi_codice_ministero as _risolvi_codice_ministero_hacs
except Exception:
    _risolvi_base_pst_hacs = None
    _risolvi_codice_ministero_hacs = None

# ── Configurazione ─────────────────────────────────────────────────────────────
PORT = int(os.getenv("HACS_SIGNER_PORT", "27272"))
VERSION = "1.5.24"
LOG_LEVEL = os.getenv("HACS_SIGNER_LOG", "INFO")
PST_SOAP_MAX_TIME = int(os.getenv("HACS_SIGNER_PST_MAX_TIME", "90"))
PST_SOAP_CONNECT_TIMEOUT = int(os.getenv("HACS_SIGNER_PST_CONNECT_TIMEOUT", "15"))
PST_PREFLIGHT_MAX_TIME = int(os.getenv("HACS_SIGNER_PST_PREFLIGHT_MAX_TIME", "30"))
PST_PREFLIGHT_CONNECT_TIMEOUT = int(os.getenv("HACS_SIGNER_PST_PREFLIGHT_CONNECT_TIMEOUT", "10"))
PIN_SESSION_TTL_SECONDS = max(int(os.getenv("HACS_SIGNER_PIN_SESSION_TTL", "900")), 60)
PIN_SESSION_MAX_ACTIVE = max(int(os.getenv("HACS_SIGNER_PIN_SESSION_MAX_ACTIVE", "4")), 1)
PST_SESSION_TTL_SECONDS = max(
    int(os.getenv("HACS_SIGNER_PST_SESSION_TTL", str(PIN_SESSION_TTL_SECONDS))),
    60,
)
PST_SESSION_MAX_ACTIVE = max(int(os.getenv("HACS_SIGNER_PST_SESSION_MAX_ACTIVE", "6")), 1)
LOCAL_SIGNER_ALLOWED_ORIGINS = os.getenv(
    "PCT_LOCAL_SIGNER_ALLOWED_ORIGINS",
    os.getenv("HACS_SIGNER_ALLOWED_ORIGINS", ""),
)

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [LocalSigner] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("local_signer")

_PST_PORTALE_URL = "https://pst.giustizia.it"
_PST_PROXY_PDA_URL = "https://pda.processotelematico.giustizia.it"
_PST_PROXY_SH_URL = "https://ext.processotelematico.giustizia.it"
_PST_LEGACY_BASE = "https://wspa.giustizia.it/wspa"
_PST_SERVIZI_DEFAULT = ("JPW_SICID", "JPW_SIECIC", "JPW_SIGP")
_PST_QBUILDER_NAMESPACES = {
    "JPW_SICID": "urn:CONS-SICC-BE",
}
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
_pin_session_cache: dict[str, dict] = {}
_pin_session_lock = threading.Lock()
_pst_session_cache: dict[str, dict] = {}
_pst_session_lock = threading.Lock()
_LOCALHOST_ORIGIN_HOSTS = {"localhost", "127.0.0.1", "::1"}

# Host PST dove il tentativo cookie-only ha fallito (mTLS obbligatorio).
# Salvato in memoria per saltare il tentativo inutile nelle chiamate successive
# della stessa sessione, così tutte le chiamate arrivano al cert più velocemente
# e rientrano nella finestra di cache-PIN di Windows (Bit4id/Aruba Key).
_mTLS_required_hosts: set[str] = set()
_mTLS_required_lock = threading.Lock()


def _utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


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


def _normalizza_origin(origin: str) -> str:
    """Restituisce un'origin canonicale per i controlli CORS."""
    origin = (origin or "").strip().rstrip("/")
    if not origin:
        return ""
    parsed = urlparse(origin)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return ""
    host = parsed.hostname.lower()
    port = parsed.port
    default_port = 80 if parsed.scheme == "http" else 443
    if port and port != default_port:
        return f"{parsed.scheme}://{host}:{port}"
    return f"{parsed.scheme}://{host}"


def _origin_loopback(origin: str) -> bool:
    parsed = urlparse((origin or "").strip())
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False
    return parsed.hostname.lower() in _LOCALHOST_ORIGIN_HOSTS


def _origini_hacs_consentite() -> set[str]:
    origini: set[str] = set()
    for chunk in re.split(r"[,\s;]+", LOCAL_SIGNER_ALLOWED_ORIGINS or ""):
        origin = _normalizza_origin(chunk)
        if origin:
            origini.add(origin)
    return origini


def _origin_cors_consentita(origin: str) -> bool:
    if not origin:
        return True
    if _origin_loopback(origin):
        return True
    return _normalizza_origin(origin) in _origini_hacs_consentite()


def _risolvi_base_pst_da_snapshot(codice_o_nome: str) -> str:
    ufficio = _risolvi_ufficio_da_snapshot(codice_o_nome)
    if not ufficio:
        raise ValueError(
            "Impossibile determinare codice GL/servizio PST dell'ufficio selezionato. "
            "Verificare il registro uffici locale o configurare PCT_PST_BASE_URL completo."
        )

    codice_gl = str(ufficio.get("codice_gl") or "").strip()
    servizi = [
        str(servizio).strip().upper()
        for servizio in (ufficio.get("servizi_ministero") or [])
        if str(servizio).strip()
    ]
    servizi_jpw = [servizio for servizio in servizi if servizio.startswith("JPW_")]
    preferenze = []
    env_pref = os.getenv("PCT_PST_SERVIZIO_DEFAULT", "").strip().upper()
    if env_pref:
        preferenze.append(env_pref)
    servizio_default = str(ufficio.get("servizio_pst_predefinito") or "").strip().upper()
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
        return base_env
    root = base_env or os.getenv("PCT_PST_PROXY_ROOT", "").strip().rstrip("/") or _PST_PROXY_SH_URL
    if root.startswith(_PST_LEGACY_BASE):
        root = _PST_PROXY_SH_URL
    return f"{root}/pda/pycons/{codice_gl}/{servizio}"


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
        "Sessione accesso PST scaduta o non disponibile. Esegui di nuovo il test connessione per riaprire il canale autenticato."
    )


def _estrai_codice_fiscale_testo(valore: str) -> str:
    match = _CF_PATTERN.search((valore or "").upper())
    return match.group(1) if match else ""


def _trova_certificato_windows(cert_thumbprint: Optional[str]) -> dict:
    thumbprint = _certificato_windows_effettivo(cert_thumbprint).replace(" ", "").upper()
    cached = dict(_ultimo_certificato_windows or {})
    cached_thumb = str(cached.get("thumbprint") or "").replace(" ", "").upper()
    if thumbprint and cached_thumb == thumbprint:
        return cached
    if not thumbprint and cached:
        return cached
    if sys.platform != "win32":
        return cached
    for cert in _windows_lista_certificati():
        cert_thumb = str(cert.get("thumbprint") or "").replace(" ", "").upper()
        if cert_thumb == thumbprint:
            return dict(cert)
    return cached


def _cf_avvocato_pst(cf_avvocato: str, cert_thumbprint: Optional[str] = None) -> str:
    explicit = _estrai_codice_fiscale_testo(cf_avvocato)
    if explicit:
        return explicit
    cert = _trova_certificato_windows(cert_thumbprint)
    for campo in ("codice_fiscale", "soggetto", "soggetto_completo", "emittente", "emittente_completo"):
        resolved = _estrai_codice_fiscale_testo(str(cert.get(campo) or ""))
        if resolved:
            return resolved
    return ""


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
                "label":        (tok.label or "").strip(),
                "manufacturer": (tok.manufacturer_id or "").strip(),
                "model":        (tok.model or "").strip(),
                "serial":       (tok.serial or "").strip(),
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


def _create_pst_session(
    *,
    cert_thumbprint: str,
    tribunale: str = "",
    base_url: str = "",
    cf_avvocato: str = "",
    cookie_file: Optional[str] = None,
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
        "cookie_file": _ensure_cookie_file(cookie_file),
        "auth_ready": False,
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


def _ensure_pst_session_entry(
    requested_session_id: Optional[str],
    *,
    tribunale: str,
    base_url: str,
    cf_avvocato: str,
    cert_thumbprint: str,
) -> tuple[dict, bool]:
    session_entry = _resolve_pst_session_entry(requested_session_id) if requested_session_id else None
    created = False
    if not session_entry:
        session_entry = _create_pst_session(
            cert_thumbprint=cert_thumbprint or "",
            tribunale=tribunale,
            base_url=base_url,
            cf_avvocato=cf_avvocato,
        )
        created = True
    return session_entry, created


def _pst_session_can_use_cookie_only(session_entry: Optional[dict], *, created_now: bool = False) -> bool:
    if not session_entry or created_now:
        return False
    cookie_file = str(session_entry.get("cookie_file") or "").strip()
    if not cookie_file:
        return False
    return bool(session_entry.get("auth_ready"))


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
    host = _pst_host(_pst_url_ricerca(base_url))
    host_needs_mtls = host in _mTLS_required_hosts

    if not force and _pst_session_can_use_cookie_only(session_entry):
        return session_entry, not host_needs_mtls

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
        auth_ready=True,
    )
    refreshed = _resolve_pst_session_entry(session_entry["session_id"]) or session_entry
    # Dopo preflight, controlla se l'host richiede mTLS (potrebbe essere
    # stato registrato da una sessione precedente nella stessa istanza).
    prefer_cookie = host not in _mTLS_required_hosts
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


def _firma_documento_via_sessione(pin_session_id: str, documento: bytes) -> tuple[bytes, dict]:
    entry = _get_pin_session(pin_session_id)
    if not entry:
        raise RuntimeError(
            "Sessione PIN scaduta o non disponibile. Inserisci di nuovo il PIN per riaprire il token."
        )

    signer = entry["signer"]
    try:
        firmato = signer.firma_cades(documento, detached=False)
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
                     pin_session_id: Optional[str] = None) -> tuple[bytes, dict]:
    """
    Firma CAdES-BES il documento usando il token PKCS#11.

    Prova prima a importare pct.firma_pkcs11 (se l'utente è nella dir del progetto);
    altrimenti usa l'implementazione inline.

    Ritorna (firmato_bytes, info_dict).
    """
    requested_session_id = (pin_session_id or "").strip()
    if requested_session_id:
        return _firma_documento_via_sessione(requested_session_id, documento)

    # Aggiungi la directory del progetto al path se possibile
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_dir not in sys.path:
        sys.path.insert(0, project_dir)

    try:
        session_id, firma = _create_pin_session(lib_path, pin, slot_id)
        try:
            firmato = firma.firma_cades(documento, detached=False)
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
    return _firma_inline(lib_path, documento, pin, slot_id)


def _firma_inline(lib_path: str, documento: bytes, pin: str,
                  slot_id: Optional[int] = None) -> tuple[bytes, dict]:
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

        # Firma RSA-PKCS1v15-SHA256 in-device
        firma_bytes = bytes(session.sign(
            privkeys[0], documento, mechanism=Mechanism.SHA256_RSA_PKCS
        ))

    # CAdES-BES minimale usando asn1crypto
    try:
        from pct.firma_pkcs11 import _build_cades_bes
        firmato = _build_cades_bes(documento, firma_bytes, cert_der)
    except ImportError:
        firmato = _build_cades_bes_inline(documento, firma_bytes, cert_der)

    # Informazioni certificato
    try:
        from cryptography import x509 as cx509
        from cryptography.hazmat.backends import default_backend
        cert_obj = cx509.load_der_x509_certificate(cert_der, default_backend())
        cn_list = cert_obj.subject.get_attributes_for_oid(cx509.NameOID.COMMON_NAME)
        intestatario = cn_list[0].value if cn_list else ""
        scadenza = _format_cert_not_valid_after(cert_obj)
    except Exception:
        intestatario = ""
        scadenza = ""

    return firmato, {"intestatario": intestatario, "scadenza": scadenza}


def _build_cades_bes_inline(documento: bytes, firma: bytes, cert_der: bytes) -> bytes:
    """
    Costruisce una busta CAdES-BES minimale (PKCS#7 SignedData).
    Usato solo se pct.firma_pkcs11 non è disponibile.
    """
    try:
        from asn1crypto import cms, algos, core, pem as asn1_pem
        from cryptography import x509 as cx509
        from cryptography.hazmat.backends import default_backend

        cert_obj = cx509.load_der_x509_certificate(cert_der, default_backend())
        issuer_der = cert_obj.issuer.public_bytes(default_backend())
        serial = cert_obj.serial_number

        doc_digest = hashlib.sha256(documento).digest()

        # SignedAttributes minimali
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

        signer_info = cms.SignerInfo({
            "version": "v1",
            "sid": cms.SignerIdentifier({
                "issuer_and_serial_number": cms.IssuerAndSerialNumber({
                    "issuer": cx509.Name.from_der(issuer_der),
                    "serial_number": serial,
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
            "encap_content_info": cms.EncapsulatedContentInfo({
                "content_type": cms.ContentType("data"),
            }),
            "certificates": cms.CertificateSet([
                cms.CertificateChoices({"certificate": cx509.Certificate.load(cert_der)})
            ]),
            "signer_infos": cms.SignerInfos([signer_info]),
        })

        envelope = cms.ContentInfo({
            "content_type": cms.ContentType("signed_data"),
            "content": signed_data,
        })
        return envelope.dump()

    except Exception as e:
        log.warning("_build_cades_bes_inline fallback: %s", e)
        # Ultima risorsa: ritorna firma grezza avvolta in PKCS#7 dummy
        return firma


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
        "L'endpoint PST predefinito di HACS punta ancora a wspa.giustizia.it, "
        "ma questo host al 29 marzo 2026 non risulta più pubblicato nel DNS pubblico.\n"
        "I proxy PST oggi documentati dal Ministero sono:\n"
        f"  - {_PST_PROXY_PDA_URL}\n"
        f"  - {_PST_PROXY_SH_URL}\n"
        "Con il registro uffici aggiornato HACS prova a comporre automaticamente "
        "il proxy corretto; se l'ufficio non ha metadati PST configurare "
        "PCT_PST_BASE_URL con l'URL completo del proxy fornito dal proprio PdA/software house.\n"
        "Verifica rapida:\n"
        f"  nslookup {_PST_PROXY_PDA_URL.replace('https://', '')} 8.8.8.8\n"
        f"  nslookup {_PST_PROXY_SH_URL.replace('https://', '')} 8.8.8.8"
    )


def _pst_servizio_proxy(base_url: str) -> str:
    return (base_url or "").rstrip("/").split("/")[-1].strip().upper()


def _pst_namespace_qbuilder(base_url: str) -> str:
    return _PST_QBUILDER_NAMESPACES.get(_pst_servizio_proxy(base_url), "")


def _pst_usa_qbuilder(base_url: str) -> bool:
    return bool(_pst_namespace_qbuilder(base_url))


def _pst_url_ricerca(base_url: str) -> str:
    if _pst_usa_qbuilder(base_url):
        return base_url.rstrip("/")
    return f"{base_url.rstrip('/')}/RicercaFascicoliRegistroService"


def _pst_url_documenti(base_url: str) -> str:
    if _pst_usa_qbuilder(base_url):
        return base_url.rstrip("/")
    return f"{base_url.rstrip('/')}/ConsultazioneAvanzataDocumentiService"


def _pst_registro_da_base_url(base_url: str) -> str:
    raw = (base_url or "").strip()
    if not raw:
        return ""
    marker = "/pda/pycons/"
    if marker not in raw:
        return ""
    tail = raw.split(marker, 1)[1]
    return tail.split("/", 1)[0].strip()


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


def _curl_disponibile() -> bool:
    """Verifica che curl sia disponibile nel PATH."""
    try:
        r = subprocess.run(
            ["curl", "--version"], capture_output=True, timeout=5
        )
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
        "Il certificato del server PST non è verificabile.\n"
        "Aggiungere --ssl-no-revoke oppure verificare la catena CA del MinGiust."
    ),
    77: (
        "Permesso negato alla lettura del certificato.\n"
        "Eseguire il Local Signer come amministratore o verificare i permessi."
    ),
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
                        soap_action: str = "",
                        cookie_file: Optional[str] = None) -> tuple[bytes, str]:
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
            "curl", "-s", "-S",
            "--max-time", str(PST_SOAP_MAX_TIME),
            "--connect-timeout", str(PST_SOAP_CONNECT_TIMEOUT),
            "--location",
            "--dump-header", header_file,
            "-X", "POST",
            "-H", "Content-Type: text/xml; charset=utf-8",
            "-H", f'SOAPAction: "{soap_action}"',
            "--data", f"@{soap_file}",
        ]
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
            # --ssl-no-revoke per evitare problemi con CRL offline
            cmd.append("--ssl-no-revoke")
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

        result = subprocess.run(
            cmd, capture_output=True,
            timeout=PST_SOAP_MAX_TIME + 10
        )

        if result.returncode != 0:
            raise RuntimeError(
                _curl_errore_leggibile(
                    result.returncode,
                    result.stderr.decode("utf-8", "replace"),
                    url,
                    timeout_sec=PST_SOAP_MAX_TIME,
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
                f"max-time = {PST_SOAP_MAX_TIME}",
                f"connect-timeout = {PST_SOAP_CONNECT_TIMEOUT}",
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
                cfg_lines.append("ssl-no-revoke")
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
        result = subprocess.run(
            ["curl", "-s", "-S", "-K", cfg_file],
            capture_output=True,
            timeout=(PST_SOAP_MAX_TIME + 10) * len(requests),
        )
        if result.returncode != 0:
            raise RuntimeError(
                _curl_errore_leggibile(
                    result.returncode,
                    result.stderr.decode("utf-8", "replace"),
                    transfers[0]["url"],
                    timeout_sec=PST_SOAP_MAX_TIME,
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
                f"max-time = {PST_SOAP_MAX_TIME}",
                f"connect-timeout = {PST_SOAP_CONNECT_TIMEOUT}",
                "location",
            ]
            if t["cookie_file"]:
                cp = _qp(_ensure_cookie_file(t["cookie_file"]))
                cfg_lines += [f'cookie = "{cp}"', f'cookie-jar = "{cp}"']
            if sys.platform == "win32":
                if cert_spec:
                    cfg_lines.append(f'cert = "{_curl_config_escape(cert_spec)}"')
                cfg_lines.append("ssl-no-revoke")
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

        result = subprocess.run(
            ["curl", "-s", "-S", "-K", cfg_file],
            capture_output=True,
            timeout=(PST_SOAP_MAX_TIME + 10) * len(requests),
        )
        if result.returncode != 0:
            raise RuntimeError(
                _curl_errore_leggibile(
                    result.returncode,
                    result.stderr.decode("utf-8", "replace"),
                    transfers[0]["url"],
                    timeout_sec=PST_SOAP_MAX_TIME,
                )
            )

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
                    soap_action: str = "",
                    cookie_file: Optional[str] = None) -> str:
    body_bytes, _headers = _soap_call_curl_raw(
        url=url,
        soap_body=soap_body,
        cert_thumbprint=cert_thumbprint,
        pkcs11_uri=pkcs11_uri,
        extra_headers=extra_headers,
        soap_action=soap_action,
        cookie_file=cookie_file,
    )
    return body_bytes.decode("utf-8", "replace")


def _soap_call_pst_session(
    *,
    url: str,
    soap_body: str,
    cert_thumbprint: Optional[str] = None,
    extra_headers: Optional[list[str]] = None,
    soap_action: str = "",
    cookie_file: Optional[str] = None,
    prefer_cookie_only: bool = False,
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
        )

    if prefer_cookie_only and cookie_file and host not in _mTLS_required_hosts:
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
        )

    if prefer_cookie_only and cookie_file and host not in _mTLS_required_hosts:
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
            return _soap_call_curl_batch_raw_best_effort(
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
    return _soap_call_curl_batch_raw_best_effort(
        effective_requests,
        cert_thumbprint=cert_thumbprint,
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
            "curl", "-s", "-S",
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
            cmd.append("--ssl-no-revoke")
        elif pkcs11_uri:
            cmd.extend([
                "--engine", "pkcs11",
                "--key-type", "ENG",
                "--key", pkcs11_uri,
                "--cert-type", "ENG",
                "--cert", pkcs11_uri,
            ])

        cmd.append(url)

        result = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=PST_PREFLIGHT_MAX_TIME + 10, encoding="utf-8", errors="replace"
        )

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
                                  cf_avvocato: str = "") -> str:
    """Costruisce il body SOAP per RicercaFascicoliRegistro o qbuilder SICID."""
    namespace = _pst_namespace_qbuilder(base_url)
    if namespace:
        if numero_rg and anno_rg:
            numero_value = str(int(str(numero_rg).strip())) if str(numero_rg).strip().isdigit() else str(numero_rg).strip()
            return _soap_qbuilder_execute_body(
                namespace,
                "RicercaInformazioniFascicoloPerTipo",
                [
                    ("idUfficio", "string", codice_ufficio),
                    ("tipo", "string", "RGN"),
                    ("numero", "integer", numero_value),
                    ("anno", "string", str(anno_rg)),
                ],
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
                ("parte", "string", parte),
            ],
            role="AVV",
            group=codice_ufficio,
            order_entries=[("ANNORUOLO, NUMERORUOLO", "asc")],
        )

    def tag(name, value):
        if value:
            return f"<{name}>{_esc(str(value))}</{name}>"
        return ""

    body_inner = "".join([
        tag("cfAvvocato", cf_avvocato),
        tag("codiceUfficio", codice_ufficio),
        tag("numeroRG", numero_rg),
        tag("annoRG", anno_rg),
        tag("nomeParte", nome_parte),
        tag("codiceFiscaleParte", cf_parte),
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
        values = [
            ("idUfficio", "string", codice_ufficio),
            ("anno", "string", str(anno_rg)),
            ("numero", "string", numero_value),
        ]
        if sub_procedimento:
            values.append(("subpro", "string", sub_procedimento))
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


def _soap_profilo_fascicolo_body(base_url: str, codice_ufficio: str, numero_rg: str,
                                 anno_rg: int, sub_procedimento: str = "") -> str:
    namespace = _pst_namespace_qbuilder(base_url)
    if not namespace:
        return ""
    numero_value = str(int(str(numero_rg).strip())) if str(numero_rg).strip().isdigit() else str(numero_rg).strip()
    values = [
        ("idUfficio", "string", codice_ufficio),
        ("anno", "string", str(anno_rg)),
        ("numero", "string", numero_value),
        ("fascPrecedente", "boolean", "false"),
        ("scadTermini", "boolean", "false"),
    ]
    if sub_procedimento:
        values.append(("subpro", "string", sub_procedimento))
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
    for parte in (row.get("__subrows") or {}).get("InfoParte", []):
        nome = " ".join(
            chunk for chunk in [str(parte.get("COGNOME") or "").strip(), str(parte.get("NOME") or "").strip()]
            if chunk
        )
        dettaglio.append({
            "nome": nome,
            "tipo": str(parte.get("TIPO") or "").strip(),
            "codice_fiscale": str(parte.get("CODICEFISCALEPARTE") or "").strip(),
            "avvocato": str(parte.get("AVVOCATO") or "").strip(),
            "cf_avvocato": str(parte.get("CODICEFISCALEAVVOCATO") or "").strip(),
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
    codice_ufficio = str(
        row.get("IDUFFICIO")
        or row.get("CODICEUFFICIO")
        or row.get("UFFICIO")
        or ""
    ).strip()
    ufficio = _risolvi_ufficio_da_snapshot(codice_ufficio)
    return {
        "id_fascicolo": str(row.get("IDFASCICOLO") or "").strip(),
        "numero_rg": _qbuilder_numero_rg(str(row.get("NUMERORUOLO") or row.get("NUMERO") or "")),
        "anno_rg": int(str(row.get("ANNORUOLO") or row.get("ANNO") or 0) or 0),
        "ruolo": str(row.get("RUOLODESCRIZIONE") or row.get("RUOLO") or row.get("DESCRUOLO") or row.get("RITO") or "").strip(),
        "stato": str(row.get("STATOFASCICOLODESCRIZIONE") or row.get("STATOFASCICOLO") or row.get("DESCSTATO") or row.get("STATO") or "").strip(),
        "oggetto": str(row.get("OGGETTOFASCICOLO") or row.get("OGGETTO") or row.get("DESCOGGETTO") or "").strip(),
        "sezione": str(row.get("SEZIONE") or row.get("DESCRIZIONESEZIONE") or row.get("DESCSEZIONE") or "").strip(),
        "giudice": str(row.get("GIUDICE") or row.get("MAGISTRATO") or "").strip(),
        "data_iscrizione": _normalizza_data_pst(str(row.get("DATAISCRIZIONERUOLO") or row.get("DATAISCRIZIONE") or "").strip()),
        "data_udienza": _normalizza_data_pst(str(row.get("DATAPROSSIMAUDIENZA") or row.get("DATAUDIENZA") or row.get("DATAPRIMACOMPARIZIONE") or row.get("DATAULTIMAUDIENZA") or "").strip()),
        "codice_ufficio": codice_ufficio,
        "nome_ufficio": str((ufficio or {}).get("nome") or "").strip(),
        "sub_procedimento": str(row.get("SUBPROCEDIMENTO") or "").strip(),
        "parti": [parte["nome"] for parte in parti_dettaglio if parte.get("nome")],
        "parti_dettaglio": parti_dettaglio,
    }


def _map_qbuilder_documento(row: dict) -> dict:
    tipo = _qbuilder_tipo_documento(str(row.get("TIPO") or ""))
    id_cat = str(row.get("IDCAT") or row.get("IDCATEGORIA") or "").strip()
    id_documento = str(
        row.get("IDDOCUMENTO")
        or row.get("NUMERODOCUMENTO")
        or row.get("IDDOCMITTENTE")
        or ""
    ).strip()
    numero_documento = str(row.get("NUMERODOCUMENTO") or "").strip()
    id_doc_mittente = str(row.get("IDDOCMITTENTE") or "").strip()
    if id_doc_mittente.startswith("#"):
        id_doc_mittente = ""
    id_repeatto = str(row.get("IDREPEATTO") or row.get("ID_REPEATTO") or "").strip()
    msg_id = str(row.get("MSGID") or row.get("MSG_ID") or "").strip()
    numero_doc = _qbuilder_numero_rg(numero_documento or id_documento)
    id_deposito = id_doc_mittente
    id_documento_candidates: list[str] = []
    for candidate in (
        str(row.get("IDDOCUMENTO") or "").strip(),
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
        "data_deposito": str(row.get("DATADEPOSITO") or "").strip(),
        "mittente": str(row.get("AUTORE") or "").strip(),
        "dimensione_bytes": 0,
        "id_deposito": id_deposito,
        "tipo_atto": tipo,
        "disponibile": str(row.get("STATO") or "").strip().lower() != "non_disponibile",
        "stato": str(row.get("STATO") or "").strip(),
        "sub_procedimento": str(row.get("SUBPROCEDIMENTO") or "").strip(),
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
        if "rowListType" in xml_clean or "InfoFascicoloExt" in xml_clean or "ProfiloFascicolo" in xml_clean:
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
        if "rowListType" in xml_clean or "DocumentoFascicolo" in xml_clean:
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


def _parse_profilo_documento_xml(xml_str: str) -> dict:
    try:
        root = _strip_namespaces(ET.fromstring(_normalizza_xml_pst(xml_str)))

        def _text(path: str) -> str:
            el = root.find(path)
            return (el.text or "").strip() if el is not None and el.text else ""

        data_deposito = _normalizza_data_pst(
            _text(".//dataDeposito")
            or _text(".//dataCreazione")
            or _text(".//dataAggiornamentoFascicolo")
        )
        return {
            "id_documento": _text(".//idDocumento"),
            "id_cat": _text(".//idCat"),
            "id_repeatto": _text(".//idRepeatTo") or _text(".//idrepeatto"),
            "msg_id": _text(".//msgId") or _text(".//msgid"),
            "content_id": _text(".//contentId"),
            "nome_file_originale": _text(".//nomeFileOriginale"),
            "codice_ufficio": _text(".//codiceUfficio"),
            "data_documento": data_deposito,
        }
    except Exception as e:
        log.warning("_parse_profilo_documento_xml: %s", e)
        return {}


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


def _soap_sigp_download_body(id_repeatto: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:y="urn:sigp-consultazioneDocumenti">
  <soapenv:Header/>
  <soapenv:Body>
    <y:downloadAtto>
      <idrepeatto>{_esc(id_repeatto)}</idrepeatto>
    </y:downloadAtto>
  </soapenv:Body>
</soapenv:Envelope>"""


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
    original: bool = True,
    cookie_file: Optional[str] = None,
    prefer_cookie_only: bool = False,
) -> dict:
    servizio = _pst_servizio_proxy(base_url)
    url_documenti = _pst_url_documenti(base_url)
    extra_headers: list[str] = []
    soap_action = ""
    profilo: dict = {}

    if servizio == "JPW_SICID":
        registro = _pst_registro_da_base_url(base_url)
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
                cookie_file=cookie_file,
                prefer_cookie_only=prefer_cookie_only,
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
                cookie_file=cookie_file,
                prefer_cookie_only=prefer_cookie_only,
            )
            profilo = _parse_profilo_documento_xml(profilo_xml)
    elif servizio == "JPW_SIGP":
        soap_action = "downloadAtto"
        download_id_repeatto = str(id_repeatto or id_documento).strip()
        if not download_id_repeatto:
            raise RuntimeError("Il servizio Cassazione richiede idRepeatTo per il download dell'atto.")
        soap_body = _soap_sigp_download_body(download_id_repeatto)
    else:
        raise RuntimeError(f"Servizio PST non supportato per il download diretto: {servizio or 'sconosciuto'}.")

    body_bytes, headers_text = _soap_call_pst_session_raw(
        url=url_documenti,
        soap_body=soap_body,
        cert_thumbprint=cert_thumbprint,
        extra_headers=extra_headers,
        soap_action=soap_action,
        cookie_file=cookie_file,
        prefer_cookie_only=prefer_cookie_only,
    )
    content_type = _http_header_value(headers_text, "Content-Type")
    parsed = _parse_download_documento_response(body_bytes, content_type)

    nome_finale = str(parsed.get("filename") or "").strip()
    if not nome_finale:
        nome_finale = (nome_documento or "").strip()
    if not nome_finale:
        nome_finale = str(profilo.get("nome_file_originale") or "").strip()
    if not nome_finale:
        nome_finale = f"documento_{id_documento}"
    if _looks_like_pkcs7_signed(parsed["content"], parsed.get("content_type", ""), nome_finale):
        if not nome_finale.lower().endswith(".p7m"):
            nome_finale += ".p7m"
    elif parsed["content"].startswith(b"%PDF") and not nome_finale.lower().endswith(".pdf"):
        nome_finale += ".pdf"

    return {
        "nome": nome_finale,
        "contenuto_b64": base64.b64encode(parsed["content"]).decode("ascii"),
        "content_type": parsed.get("content_type") or "application/octet-stream",
        "id_documento_portale": id_documento,
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
    original: bool = True,
) -> dict:
    """Costruisce il payload file da una risposta PST parsed."""
    nome_finale = str(parsed.get("filename") or "").strip()
    if not nome_finale:
        nome_finale = (nome_documento or "").strip()
    if not nome_finale:
        nome_finale = f"documento_{id_documento}"
    if _looks_like_pkcs7_signed(parsed["content"], parsed.get("content_type", ""), nome_finale):
        if not nome_finale.lower().endswith(".p7m"):
            nome_finale += ".p7m"
    elif parsed["content"].startswith(b"%PDF") and not nome_finale.lower().endswith(".pdf"):
        nome_finale += ".pdf"
    return {
        "nome": nome_finale,
        "contenuto_b64": base64.b64encode(parsed["content"]).decode("ascii"),
        "content_type": parsed.get("content_type") or "application/octet-stream",
        "id_documento_portale": id_documento,
        "id_cat": str(item.get("id_cat") or "").strip(),
        "id_repeatto": str(item.get("id_repeatto") or "").strip(),
        "msg_id": str(item.get("msg_id") or "").strip(),
        "data_documento": str(item.get("data_deposito") or item.get("data_documento") or "").strip(),
        "nome_file_originale": str(parsed.get("filename") or "").strip(),
        "original_documento_portale": bool(original),
        "modalita_documento_portale": "originale" if original else "copia",
        "servizio_portale": "DocumentiFascicolo",
        "origine": f"pst:{_pst_servizio_proxy(base_url) or 'download'}:{id_documento}",
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


def _pst_download_documenti_batch_payloads(
    *,
    base_url: str,
    codice_ufficio: str,
    cert_thumbprint: str,
    cf_avvocato: str,
    documenti: list[dict],
    do_preflight: bool = True,
    cookie_file: Optional[str] = None,
    original: bool = True,
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
        prefer_cookie_only = bool(cookie_file)
        servizio = _pst_servizio_proxy(base_url)
        url_documenti = _pst_url_documenti(base_url)
        usa_wasp = servizio in ("JPW_SICID", "JPW_SIECIC")
        extra_base = [f"X-WASP-User: {cf_avvocato}"] if (usa_wasp and cf_avvocato) else []

        # ── Fase 1: risolvi id_cat e metadati mancanti per SICID/SIECIC ──
        # Un solo processo curl per tutti i profili da recuperare.
        if usa_wasp:
            need_prof: list[int] = []
            for i, raw in enumerate(documenti):
                if not isinstance(raw, dict):
                    continue
                id_doc = str(raw.get("id_documento") or raw.get("id_documento_portale") or "").strip()
                if not id_doc:
                    continue
                miss_cat = not _pst_effective_id_cat(raw, id_doc)
                miss_meta = not str(raw.get("nome_documento") or raw.get("nome") or "").strip()
                if miss_cat or (servizio == "JPW_SIECIC" and miss_meta):
                    need_prof.append(i)

            if need_prof:
                prof_reqs: list[dict] = []
                prof_meta: list[tuple[int, str]] = []
                for i in need_prof:
                    item = documenti[i]
                    for id_doc in _pst_document_id_candidates(item):
                        if servizio == "JPW_SICID":
                            registro = _pst_registro_da_base_url(base_url)
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
                            "cookie_file": cookie_file,
                        })
                        prof_meta.append((i, id_doc))
                try:
                    prof_results = _soap_call_pst_session_batch_raw_best_effort(
                        prof_reqs,
                        cert_thumbprint=cert_thumbprint,
                        cookie_file=cookie_file,
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

        allow_single_fallback = len(documenti) == 1

        for raw in documenti:
            item = raw if isinstance(raw, dict) else {}
            id_doc = str(item.get("id_documento") or item.get("id_documento_portale") or "").strip()
            nome_doc = str(item.get("nome_documento") or item.get("nome") or "").strip()
            if not id_doc:
                failures.append({"id_documento": "", "nome_documento": nome_doc,
                                  "errore": "Identificativo documento mancante nel lotto PST."})
                continue
            try:
                if servizio == "JPW_SIGP":
                    id_repeatto = str(item.get("id_repeatto") or id_doc).strip()
                    if not id_repeatto:
                        raise RuntimeError("idRepeatTo mancante nel lotto Cassazione.")
                    soap_body = _soap_sigp_download_body(id_repeatto)
                    soap_action = "downloadAtto"
                    extra_h: list[str] = []
                elif servizio == "JPW_SICID":
                    id_cat = _pst_effective_id_cat(item, id_doc)
                    if not id_cat:
                        if allow_single_fallback:
                            # Per il lotto singolo mantieni il fallback puntuale.
                            files.append(
                                _pst_download_documento_payload(
                                    base_url=base_url,
                                    codice_ufficio=codice_ufficio,
                                    id_documento=id_doc,
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
                                    cookie_file=cookie_file,
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
                    "cookie_file": cookie_file,
                })
                dl_meta.append({"id_documento": id_doc, "nome_documento": nome_doc, "item": item})
            except Exception as e:
                failures.append({"id_documento": id_doc, "nome_documento": nome_doc, "errore": str(e)})

        if not dl_reqs:
            return {
                "ok": True, "files": files, "failures": failures,
                "preflight": preflight,
                "documenti_richiesti": len(documenti), "documenti_scaricati": len(files),
            }

        # ── Fase 3: UN SOLO processo curl per tutti i download ──
        try:
            batch_results = _soap_call_pst_session_batch_raw(
                dl_reqs,
                cert_thumbprint=cert_thumbprint,
                cookie_file=cookie_file,
                prefer_cookie_only=prefer_cookie_only,
            )
            for (body_bytes, hdr_text), meta in zip(batch_results, dl_meta):
                try:
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
        except RuntimeError as batch_err:
            if len(dl_reqs) == 1:
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
                    "Batch download PST fallito senza fallback singoli per evitare prompt PIN ripetuti: %s",
                    batch_err,
                )
                for meta in dl_meta:
                    failures.append({
                        "id_documento": meta["id_documento"],
                        "nome_documento": meta["nome_documento"],
                        "errore": (
                            "Download batch PST non riuscito. "
                            "Il lotto non ricade sui download singoli per evitare richieste PIN ripetute. "
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

    def log_message(self, fmt, *args):  # noqa: override
        log.debug("[%s] %s", self.address_string(), fmt % args)

    def _cors_ok(self) -> bool:
        """Verifica che l'origine sia localhost o una origin HACS esplicitamente fidata."""
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
            "Content-Type, X-Signer-Token"
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

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if not length:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

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
        if path in {"/ping", "/seleziona-certificato", "/pst/status"}:
            log.info("HTTP GET %s", path)
        if path == "/ping":
            self._ping()
        elif path == "/diagnosi":
            self._diagnosi()
        elif path == "/certificati":
            self._certificati()
        elif path == "/seleziona-certificato":
            self._seleziona_certificato()
        elif path == "/pst/status":
            self._pst_status()
        else:
            self._send_json({"errore": "Not found"}, 404)

    def do_POST(self):  # noqa: N802
        if not self._cors_ok():
            self._send_json({"errore": "CORS: origine non consentita"}, 403)
            return
        path = urlparse(self.path).path
        if path in {"/pst/preflight-auth", "/pst/ricerca", "/pst/documenti", "/pst/download-documenti-batch"}:
            log.info("HTTP POST %s", path)
        if path == "/firma":
            self._firma()
        elif path == "/firma-batch":
            self._firma_batch()
        elif path == "/pst/preflight-auth":
            self._pst_preflight_auth()
        elif path == "/pst/ricerca":
            self._pst_ricerca()
        elif path == "/pst/documenti":
            self._pst_documenti()
        elif path == "/pst/download-documento":
            self._pst_download_documento()
        elif path == "/pst/download-documenti-batch":
            self._pst_download_documenti_batch()
        elif path == "/downloads/raccogli":
            self._downloads_raccogli()
        else:
            self._send_json({"errore": "Not found"}, 404)

    # ── Handlers ────────────────────────────────────────────────────────────────

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
                selected = preferred or cached
                if selected.get("thumbprint"):
                    resp["certificato_windows_selezionato"] = {
                        "thumbprint": selected.get("thumbprint"),
                        "soggetto": selected.get("soggetto", ""),
                        "emittente": selected.get("emittente", ""),
                        "scadenza": selected.get("scadenza", ""),
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
            except Exception as e:
                resp["errore_token"] = f"Errore inatteso: {e}"
        self._send_json(resp)

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
        Controlla il portale PST, i proxy documentati e l'endpoint configurato in HACS.
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
                r = subprocess.run(
                    ["curl", "-s", "-o", null_dev,
                     "-w", "%{http_code}",
                     "--max-time", "10",
                     "--connect-timeout", "8",
                     url],
                    capture_output=True, text=True, timeout=15
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
        Body: {documento: <base64>, pin?: "...", pin_session_id?: "...", slot_id?: 0}
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
        Body: {documenti:[{documento:<base64>, nome?}], pin?: "...", pin_session_id?: "...", slot_id?: 0}
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
        Body: {tribunale, cert_thumbprint?, pst_session_id?}
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
        session_cleanup_id = requested_session_id

        try:
            session_entry = _resolve_pst_session_entry(requested_session_id) if requested_session_id else None
            if session_entry and not data.get("force_auth"):
                self._send_json({
                    "ok": True,
                    "tribunale": tribunale or str(session_entry.get("tribunale") or "").strip(),
                    "cached": True,
                    "nota": "Sessione accesso PST gia' attiva nel Local Signer.",
                    "pst_session_id": session_entry["session_id"],
                    "pst_session_ttl_seconds": PST_SESSION_TTL_SECONDS,
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
            if not session_entry:
                session_entry, _created = _ensure_pst_session_entry(
                    requested_session_id,
                    tribunale=tribunale,
                    base_url=base_url,
                    cf_avvocato=cf_avvocato,
                    cert_thumbprint=cert_thumbprint,
                )
                session_cleanup_id = session_entry["session_id"]
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
                last_http_code=esito.get("http_code"),
                last_content_type=esito.get("content_type"),
                auth_ready=True,
            )
            self._send_json({
                "ok": True,
                "tribunale": tribunale,
                **esito,
                "cached": False,
                "pst_session_id": session_entry["session_id"],
                "pst_session_ttl_seconds": PST_SESSION_TTL_SECONDS,
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
            base_url = _risolvi_base_pst_runtime(tribunale)
            url_ricerca = _pst_url_ricerca(base_url)
            codice_pst = _risolvi_codice_ufficio_pst(tribunale)
        except Exception as e:
            self._send_json({"ok": False, "errore": str(e)}, 503)
            return

        try:
            requested_session_id = str(data.get("pst_session_id") or "").strip()
            cert_thumbprint = _require_certificato_pst(
                data.get("cert_thumbprint")
            )
            cf_avvocato = _cf_avvocato_pst(data.get("cf_avvocato", ""), cert_thumbprint)
            if _pst_namespace_qbuilder(base_url) and not cf_avvocato:
                raise RuntimeError(
                    "Impossibile determinare il codice fiscale dell'avvocato dal certificato selezionato.\n"
                    "Riselezionare il certificato CNS/CIE oppure indicare esplicitamente il codice fiscale."
                )
            session_entry, session_created = _ensure_pst_session_entry(
                requested_session_id,
                tribunale=tribunale,
                base_url=base_url,
                cf_avvocato=cf_avvocato,
                cert_thumbprint=cert_thumbprint,
            )
            if session_entry and not cf_avvocato:
                cf_avvocato = str(session_entry.get("cf_avvocato") or "").strip()
            session_entry, prefer_cookie_only = _pst_prepare_authenticated_session(
                session_entry,
                tribunale=tribunale,
                base_url=base_url,
                cf_avvocato=cf_avvocato,
                cert_thumbprint=cert_thumbprint,
                force=session_created,
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
            )
            extra_headers = [f"X-WASP-User: {cf_avvocato}"] if _pst_namespace_qbuilder(base_url) else []
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
                "pst_session_id": str((session_entry or {}).get("session_id") or ""),
                "pst_session_ttl_seconds": PST_SESSION_TTL_SECONDS,
            })
        except Exception as e:
            log.error("Errore PST ricerca: %s", e)
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
            requested_session_id = str(data.get("pst_session_id") or "").strip()
            cert_thumbprint = _require_certificato_pst(
                data.get("cert_thumbprint")
            )
            cf_avvocato = _cf_avvocato_pst(data.get("cf_avvocato", ""), cert_thumbprint)
            if _pst_namespace_qbuilder(base_url) and not cf_avvocato:
                raise RuntimeError(
                    "Impossibile determinare il codice fiscale dell'avvocato dal certificato selezionato.\n"
                    "Riselezionare il certificato CNS/CIE oppure indicare esplicitamente il codice fiscale."
                )
            session_entry, session_created = _ensure_pst_session_entry(
                requested_session_id,
                tribunale=codice,
                base_url=base_url,
                cf_avvocato=cf_avvocato,
                cert_thumbprint=cert_thumbprint,
            )
            if session_entry and not cf_avvocato:
                cf_avvocato = str(session_entry.get("cf_avvocato") or "").strip()
            session_entry, prefer_cookie_only = _pst_prepare_authenticated_session(
                session_entry,
                tribunale=codice,
                base_url=base_url,
                cf_avvocato=cf_avvocato,
                cert_thumbprint=cert_thumbprint,
                force=session_created,
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
            xml_resp = _soap_call_pst_session(
                url=url_documenti,
                soap_body=soap,
                cert_thumbprint=cert_thumbprint,
                extra_headers=extra_headers,
                cookie_file=cookie_file,
                prefer_cookie_only=prefer_cookie_only,
            )
            fault = _estrai_fault_soap(xml_resp)
            if fault:
                raise RuntimeError(f"Il PST ha restituito una SOAP Fault: {fault}")
            documenti = _parse_documenti_xml(xml_resp)
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
                "pst_session_id": str((session_entry or {}).get("session_id") or ""),
                "pst_session_ttl_seconds": PST_SESSION_TTL_SECONDS,
            })
        except Exception as e:
            log.error("Errore PST documenti: %s", e)
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
            base_url = _risolvi_base_pst_runtime(tribunale)
            codice_pst = _risolvi_codice_ufficio_pst(tribunale)
            cert_thumbprint = _require_certificato_pst(
                data.get("cert_thumbprint")
            )
            cf_avvocato = _cf_avvocato_pst(data.get("cf_avvocato", ""), cert_thumbprint)
            session_entry, session_created = _ensure_pst_session_entry(
                requested_session_id,
                tribunale=tribunale,
                base_url=base_url,
                cf_avvocato=cf_avvocato,
                cert_thumbprint=cert_thumbprint,
            )
            if session_entry and not cf_avvocato:
                cf_avvocato = str(session_entry.get("cf_avvocato") or "").strip()
            session_entry, prefer_cookie_only = _pst_prepare_authenticated_session(
                session_entry,
                tribunale=tribunale,
                base_url=base_url,
                cf_avvocato=cf_avvocato,
                cert_thumbprint=cert_thumbprint,
                force=session_created,
            )
            cookie_file = str((session_entry or {}).get("cookie_file") or "")
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
                    data.get("original", True)
                    if isinstance(data.get("original", True), bool)
                    else str(data.get("original", True)).strip().lower() not in {"0", "false", "no", "off"}
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
                "pst_session_id": str((session_entry or {}).get("session_id") or ""),
                "pst_session_ttl_seconds": PST_SESSION_TTL_SECONDS,
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
            base_url = _risolvi_base_pst_runtime(tribunale)
            codice_pst = _risolvi_codice_ufficio_pst(tribunale)
            cert_thumbprint = _require_certificato_pst(
                data.get("cert_thumbprint")
            )
            cf_avvocato = _cf_avvocato_pst(data.get("cf_avvocato", ""), cert_thumbprint)
            session_entry, session_created = _ensure_pst_session_entry(
                requested_session_id,
                tribunale=tribunale,
                base_url=base_url,
                cf_avvocato=cf_avvocato,
                cert_thumbprint=cert_thumbprint,
            )
            if session_entry and not cf_avvocato:
                cf_avvocato = str(session_entry.get("cf_avvocato") or "").strip()
            session_entry, _prefer_cookie_only = _pst_prepare_authenticated_session(
                session_entry,
                tribunale=tribunale,
                base_url=base_url,
                cf_avvocato=cf_avvocato,
                cert_thumbprint=cert_thumbprint,
                force=session_created or bool(data.get("preflight_auth", False)),
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
                    data.get("original", True)
                    if isinstance(data.get("original", True), bool)
                    else str(data.get("original", True)).strip().lower() not in {"0", "false", "no", "off"}
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
                esito["pst_session_id"] = session_entry["session_id"]
                esito["pst_session_ttl_seconds"] = PST_SESSION_TTL_SECONDS
            self._send_json(esito)
        except Exception as e:
            log.error("Errore PST download batch documenti: %s", e)
            self._send_json({"ok": False, "errore": str(e)}, 500)

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
        description="HACS Local Signer — firma documenti con smart card e token CNS/CIE",
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

    print("=" * 60)
    print(f"  HACS Local Signer v{VERSION}")
    print(f"  In ascolto su  http://127.0.0.1:{args.port}")
    print(f"  Piattaforma:   {sys.platform}")
    print("=" * 60)

    lib = _trova_libreria()
    if lib:
        print(f"  Libreria PKCS#11 : {lib}")
        try:
            tokens = _info_token(lib)
            if tokens:
                for tok in tokens:
                    label = tok.get("label") or tok.get("manufacturer") or "Token"
                    print(f"  Token trovato    : {label} (slot {tok['slot_id']})")
            else:
                print("  Token            : libreria OK — inserire smart card/token")
        except RuntimeError as e:
            # Messaggio di errore su più righe → prima riga in console
            print(f"  AVVISO token     : {str(e).splitlines()[0]}")
        except Exception as e:
            print(f"  AVVISO token     : {e}")
    else:
        print("  AVVISO: Libreria PKCS#11 non trovata.")
        print("  → Verificare che il middleware PKCS#11 del dispositivo sia installato.")
        print("  → Oppure impostare: set PCT_PKCS11_LIBRARY=C:\\percorso\\bit4xpki.dll")
        print(f"  → Diagnostica completa: http://127.0.0.1:{args.port}/diagnosi")

    if _curl_disponibile():
        print(f"  curl             : disponibile (PST abilitato)")
    else:
        print("  AVVISO: curl non trovato nel PATH (PST non disponibile)")

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
