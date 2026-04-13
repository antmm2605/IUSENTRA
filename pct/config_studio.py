"""
pct/config_studio.py — Configurazione persistente dello studio legale.

Salva tutte le impostazioni in un singolo file JSON:
  /data/config/studio.json  (o percorso configurabile)

Le password sono cifrate con Fernet (AES-128-CBC) derivando la chiave da
PCT_SECRET_KEY. Se la variabile non è impostata i valori vengono salvati
in chiaro (solo in ambienti di sviluppo — in produzione impostare sempre
PCT_SECRET_KEY).

Include:
  - Dati anagrafici studio
  - Configurazione PEC  (SMTP/IMAP)
  - Firma digitale
  - Email SMTP normale
  - WhatsApp (Twilio / CallMeBot)
  - Scheduler (ore esecuzione job automatici)
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional


# ──────────────────────────────────────────────────────────── cifratura

_ENC_PREFIX = "ENC:"
_CAMPI_CIFRATI: List[tuple[str, str]] = [
    ("pec",       "password"),
    ("firma",     "password"),
    ("firma",     "key_pem_password"),
    ("smtp",      "password"),
    ("whatsapp",  "twilio_token"),
]


def _fernet_instance(secret: str | None = None):
    """Restituisce un'istanza Fernet o None se la libreria manca / chiave assente."""
    if secret is None:
        secret = os.getenv("PCT_SECRET_KEY", "")
    # In modalità dev non cifriamo (chiave default debole)
    if not secret or secret.startswith("dev-secret"):
        return None
    try:
        from cryptography.fernet import Fernet
        key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
        return Fernet(key)
    except Exception:
        return None


def _cifra(valore: str, f) -> str:
    """Cifra un valore stringa. Restituisce il valore invariato se Fernet non disponibile."""
    if not valore or f is None:
        return valore
    return _ENC_PREFIX + f.encrypt(valore.encode()).decode()


def _decifra(valore: str, f) -> str:
    """Decifra un valore cifrato. Gestisce in modo sicuro valori in chiaro legacy."""
    if not valore or f is None:
        return valore
    if not valore.startswith(_ENC_PREFIX):
        return valore  # valore legacy in chiaro — restituisce così com'è
    try:
        return f.decrypt(valore[len(_ENC_PREFIX):].encode()).decode()
    except Exception:
        return valore  # chiave cambiata o dato corrotto — meglio "" che crash


def _applica_cifratura(d: Dict[str, Any], f, cifra: bool) -> Dict[str, Any]:
    """Cifra o decifra tutti i campi sensibili nel dizionario seriale."""
    fn = _cifra if cifra else _decifra
    for sezione, campo in _CAMPI_CIFRATI:
        if sezione in d and campo in d[sezione]:
            d[sezione][campo] = fn(d[sezione][campo] or "", f)
    return d


# ──────────────────────────────────────────────────────────── dataclasses

@dataclass
class ConfigDatiStudio:
    nome: str = "Studio Legale PCT"
    avvocato: str = ""
    piva: str = ""
    cf: str = ""
    indirizzo: str = ""
    city: str = ""
    province: str = ""
    patron_name: str = ""
    patron_day: int = 0
    patron_month: int = 0
    telefono: str = ""
    email: str = ""
    sito_web: str = ""
    iban: str = ""
    banca: str = ""
    codice_fiscale_avvocato: str = ""   # usato per depositi PCT


@dataclass
class ConfigPEC:
    indirizzo: str = ""
    password: str = ""
    smtp_host: str = "smtp.pec.aruba.it"
    smtp_port: int = 465
    imap_host: str = "imaps.pec.aruba.it"
    imap_port: int = 993
    use_ssl: bool = True


@dataclass
class ConfigFirma:
    # ── Formato P12/PFX (PKCS#12 — bundle cert+chiave in un unico file) ──────
    p12_path: str = ""
    password: str = ""          # password del P12 (cifrata a riposo)

    # ── Formato PEM (cert e chiave in file separati) ─────────────────────────
    # Usare quando il provider non rilascia il formato P12 (es. alcuni token
    # Namirial / Aruba / InfoCert forniscono .crt + .key o .pem separati).
    cert_pem_path: str = ""     # percorso al file .crt / .pem (solo certificato)
    key_pem_path:  str = ""     # percorso al file .key / .pem (chiave privata)
    key_pem_password: str = ""  # password chiave privata cifrata (lasciare vuoto se non cifrata)

    # ── Formato PKCS#11 (token USB — Aruba Key, Namirial, ecc.) ─────────────
    # La chiave privata non lascia mai il dispositivo (in-device signing).
    # Richiede: apt install pcscd opensc   +   pip install python-pkcs11 asn1crypto
    # Docker: montare /run/pcscd/pcscd.comm:/run/pcscd/pcscd.comm
    pkcs11_library: str = ""    # percorso alla .so/.dll (es. /usr/lib/.../opensc-pkcs11.so)
    pkcs11_slot:    str = ""    # slot ID (lasciare vuoto = primo slot disponibile)
    pkcs11_label:   str = ""    # etichetta certificato nel token (opzionale)
    # NOTA: il PIN NON viene salvato qui per sicurezza — viene chiesto all'utente
    # ogni volta nella UI di deposito (modal "Firma con Aruba Key").

    # ── Comune a tutti i formati ─────────────────────────────────────────────
    cf_avvocato: str = ""
    backend_preferito: str = "auto"  # auto | pkcs11 | p12 | pem

    @property
    def backend_preferito_normalizzato(self) -> str:
        valore = str(self.backend_preferito or "auto").strip().lower()
        if valore in {"auto", "pkcs11", "p12", "pem"}:
            return valore
        return "auto"

    @property
    def formato_attivo(self) -> str:
        """Restituisce il backend rilevato tecnicamente: 'pkcs11', 'p12', 'pem' o 'nessuno'."""
        import os as _os
        from pct.firma_pkcs11 import libreria_disponibile as _lib_disp
        # PKCS#11: configurato se libreria specificata o auto-rilevata
        if self.pkcs11_library and _os.path.exists(self.pkcs11_library):
            return "pkcs11"
        if not self.pkcs11_library and _lib_disp():
            # Libreria auto-rilevata e almeno uno degli altri campi pkcs11 impostati
            # (anche solo library auto-detected è sufficiente per offrire il formato)
            pass  # non attivare pkcs11 automaticamente senza configurazione esplicita
        if self.p12_path and _os.path.exists(self.p12_path):
            return "p12"
        if self.cert_pem_path and self.key_pem_path and \
           _os.path.exists(self.cert_pem_path) and _os.path.exists(self.key_pem_path):
            return "pem"
        return "nessuno"

    @property
    def pkcs11_configurato(self) -> bool:
        """
        True se il backend PKCS#11 è stato scelto/configurato in modo esplicito.

        Non basta che sul sistema esista una DLL rilevabile automaticamente:
        per evitare fallback silenziosi su Aruba Key / token USB, consideriamo
        il backend attivo solo quando c'è almeno un indizio di configurazione
        esplicita (libreria salvata, slot/label salvati, oppure override env).
        """
        import os as _os
        from pct.firma_pkcs11 import libreria_disponibile as _lib_disp

        if self.pkcs11_library:
            return _os.path.exists(self.pkcs11_library)

        env_lib = _os.getenv("PCT_PKCS11_LIBRARY", "").strip()
        if env_lib:
            return _os.path.exists(env_lib)

        if self.pkcs11_slot or self.pkcs11_label:
            return _lib_disp() is not None

        return False

    @property
    def backend_firma_effettivo(self) -> str:
        """Restituisce il backend effettivo rispettando la scelta salvata dell'utente."""
        import os as _os

        preferito = self.backend_preferito_normalizzato
        if preferito == "pkcs11":
            if self.pkcs11_configurato:
                return "pkcs11"
            raise FileNotFoundError("PKCS#11 selezionato ma libreria/token non disponibili.")
        if preferito == "p12":
            if self.p12_path and _os.path.exists(self.p12_path):
                return "p12"
            raise FileNotFoundError("P12 selezionato ma file non disponibile.")
        if preferito == "pem":
            if (
                self.cert_pem_path and self.key_pem_path
                and _os.path.exists(self.cert_pem_path)
                and _os.path.exists(self.key_pem_path)
            ):
                return "pem"
            raise FileNotFoundError("PEM selezionato ma certificato/chiave non disponibili.")
        return self.formato_attivo

    @property
    def backend_firma_effettivo_safe(self) -> str:
        try:
            return self.backend_firma_effettivo
        except Exception:
            return "nessuno"

    @property
    def backend_firma_errore(self) -> str:
        try:
            self.backend_firma_effettivo
        except Exception as exc:
            return str(exc)
        return ""

    @property
    def configurato(self) -> bool:
        return self.backend_firma_effettivo_safe != "nessuno"

    @property
    def formati_firma_consentiti(self) -> list[str]:
        """Restituisce i formati firma consentiti per il backend attivo."""
        formato = self.backend_firma_effettivo_safe
        if formato == "pkcs11":
            return ["cades"]
        if formato in ("p12", "pem"):
            return ["cades", "pades"]
        return []

    def valida_formato_firma(self, formato: str) -> str:
        """Valida il formato richiesto rispetto al backend di firma attivo."""
        valore = str(formato or "cades").strip().lower()
        backend = self.backend_firma_effettivo
        consentiti = self.formati_firma_consentiti
        if not consentiti:
            raise ValueError("Nessun backend di firma configurato.")
        if valore not in consentiti:
            if backend == "pkcs11":
                raise ValueError(
                    "Con Aruba Key / PKCS#11 è consentito solo CAdES (.p7m). "
                    "Per PAdES usare una firma P12 o PEM."
                )
            raise ValueError(
                f"Formato firma non consentito: {valore}. "
                f"Consentiti: {', '.join(consentiti)}"
            )
        return valore


@dataclass
class ConfigSMTP:
    host: str = ""
    port: int = 587
    username: str = ""
    password: str = ""
    from_address: str = ""
    from_name: str = ""
    use_tls: bool = True


@dataclass
class ConfigWhatsApp:
    twilio_sid: str = ""
    twilio_token: str = ""
    twilio_numero: str = ""
    callmebot_key: str = ""


@dataclass
class ConfigScheduler:
    backup_ora: str = "02:00"
    wa_reminder_ora: str = "18:00"
    backup_abilitato: bool = True
    wa_reminder_abilitato: bool = False


@dataclass
class ConfigLocalAI:
    enabled: bool = True
    base_url: str = "http://127.0.0.1:11434/api"
    auto_bootstrap: bool = True
    chat_model: str = ""
    embed_model: str = ""
    keep_alive: str = "10m"
    auto_index_documents: bool = True


@dataclass
class ConfigStudio:
    studio: ConfigDatiStudio = field(default_factory=ConfigDatiStudio)
    pec: ConfigPEC = field(default_factory=ConfigPEC)
    firma: ConfigFirma = field(default_factory=ConfigFirma)
    smtp: ConfigSMTP = field(default_factory=ConfigSMTP)
    whatsapp: ConfigWhatsApp = field(default_factory=ConfigWhatsApp)
    scheduler: ConfigScheduler = field(default_factory=ConfigScheduler)
    ai: ConfigLocalAI = field(default_factory=ConfigLocalAI)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ConfigStudio":
        def _pick(klass, data):
            return klass(**{k: v for k, v in data.items()
                            if k in klass.__dataclass_fields__})
        return cls(
            studio=_pick(ConfigDatiStudio, d.get("studio", {})),
            pec=_pick(ConfigPEC, d.get("pec", {})),
            firma=_pick(ConfigFirma, d.get("firma", {})),
            smtp=_pick(ConfigSMTP, d.get("smtp", {})),
            whatsapp=_pick(ConfigWhatsApp, d.get("whatsapp", {})),
            scheduler=_pick(ConfigScheduler, d.get("scheduler", {})),
            ai=_pick(ConfigLocalAI, d.get("ai", {})),
        )


# ──────────────────────────────────────────────────────────── gestore

class GestioneConfigStudio:
    """
    Carica e salva la configurazione dello studio da/verso un file JSON.
    Le password sono cifrate con Fernet usando PCT_SECRET_KEY.
    Se il file non esiste, pre-popola dai valori delle variabili d'ambiente.
    """

    def __init__(self, config_path: str = "./config/studio.json", db_path: str | None = None):
        # `db_path` resta supportato per retrocompatibilita' con chiamanti legacy
        # che trattavano la config studio come un "db". La sorgente canonica resta
        # comunque il file JSON indicato da `config_path`.
        self._path = Path(db_path or config_path)
        self._cfg: Optional[ConfigStudio] = None

    # ── I/O ──────────────────────────────────────────────────────────

    def _carica(self) -> ConfigStudio:
        if self._path.exists():
            try:
                f = _fernet_instance()
                raw = json.loads(self._path.read_text(encoding="utf-8"))
                raw = _applica_cifratura(raw, f, cifra=False)
                return ConfigStudio.from_dict(raw)
            except Exception:
                pass
        # Prima volta: pre-popola dai valori env (compatibilità backward)
        return self._da_env()

    def _salva(self, cfg: ConfigStudio) -> None:
        f = _fernet_instance()
        d = cfg.to_dict()
        d = _applica_cifratura(d, f, cifra=True)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(d, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _da_env() -> ConfigStudio:
        """Costruisce ConfigStudio leggendo le variabili d'ambiente esistenti."""
        return ConfigStudio(
            studio=ConfigDatiStudio(
                nome=os.getenv("PCT_STUDIO_NOME", "Studio Legale PCT"),
                avvocato=os.getenv("PCT_STUDIO_AVVOCATO", ""),
                piva=os.getenv("PCT_STUDIO_PIVA", ""),
                cf=os.getenv("PCT_STUDIO_CF", ""),
                indirizzo=os.getenv("PCT_STUDIO_INDIRIZZO", ""),
                city=os.getenv("PCT_STUDIO_CITY", ""),
                province=os.getenv("PCT_STUDIO_PROVINCE", ""),
                patron_name=os.getenv("PCT_STUDIO_PATRON_NAME", ""),
                patron_day=int(os.getenv("PCT_STUDIO_PATRON_DAY", "0") or "0"),
                patron_month=int(os.getenv("PCT_STUDIO_PATRON_MONTH", "0") or "0"),
                iban=os.getenv("PCT_STUDIO_IBAN", ""),
                codice_fiscale_avvocato=os.getenv("PCT_CF_AVVOCATO", ""),
            ),
            pec=ConfigPEC(
                indirizzo=os.getenv("PCT_PEC_INDIRIZZO", ""),
                password=os.getenv("PCT_PEC_PASSWORD", ""),
                smtp_host=os.getenv("PCT_PEC_SMTP_HOST", "smtp.pec.aruba.it"),
                smtp_port=int(os.getenv("PCT_PEC_SMTP_PORT", "465")),
                imap_host=os.getenv("PCT_PEC_IMAP_HOST", "imaps.pec.aruba.it"),
                imap_port=int(os.getenv("PCT_PEC_IMAP_PORT", "993")),
            ),
            firma=ConfigFirma(
                p12_path=os.getenv("PCT_FIRMA_P12", ""),
                password=os.getenv("PCT_FIRMA_PASSWORD", ""),
                cert_pem_path=os.getenv("PCT_FIRMA_CERT", ""),
                key_pem_path=os.getenv("PCT_FIRMA_KEY", ""),
                key_pem_password=os.getenv("PCT_FIRMA_KEY_PASSWORD", ""),
                pkcs11_library=os.getenv("PCT_PKCS11_LIBRARY", ""),
                pkcs11_slot=os.getenv("PCT_PKCS11_SLOT", ""),
                pkcs11_label=os.getenv("PCT_PKCS11_LABEL", ""),
                cf_avvocato=os.getenv("PCT_CF_AVVOCATO", ""),
                backend_preferito=os.getenv("PCT_FIRMA_BACKEND", "auto"),
            ),
            smtp=ConfigSMTP(
                host=os.getenv("PCT_SMTP_HOST", ""),
                port=int(os.getenv("PCT_SMTP_PORT", "587")),
                username=os.getenv("PCT_SMTP_USER", ""),
                password=os.getenv("PCT_SMTP_PASS", ""),
                from_address=os.getenv("PCT_SMTP_FROM", ""),
                from_name=os.getenv("PCT_STUDIO_NOME", "Studio Legale"),
            ),
            whatsapp=ConfigWhatsApp(
                twilio_sid=os.getenv("PCT_TWILIO_SID", ""),
                twilio_token=os.getenv("PCT_TWILIO_TOKEN", ""),
                twilio_numero=os.getenv("PCT_TWILIO_NUMERO", ""),
                callmebot_key=os.getenv("PCT_CALLMEBOT_KEY", ""),
            ),
            scheduler=ConfigScheduler(
                backup_ora=os.getenv("PCT_BACKUP_ORA", "02:00"),
                wa_reminder_ora=os.getenv("PCT_WA_REMINDER_ORA", "18:00"),
            ),
            ai=ConfigLocalAI(
                enabled=os.getenv("PCT_LOCAL_AI_ENABLED", "1").lower() not in {"0", "false", "no"},
                base_url=os.getenv("PCT_LOCAL_AI_BASE_URL", "http://127.0.0.1:11434/api"),
                auto_bootstrap=os.getenv("PCT_LOCAL_AI_AUTO_BOOTSTRAP", "1").lower() not in {"0", "false", "no"},
                chat_model=os.getenv("PCT_LOCAL_AI_CHAT_MODEL", ""),
                embed_model=os.getenv("PCT_LOCAL_AI_EMBED_MODEL", ""),
                keep_alive=os.getenv("PCT_LOCAL_AI_KEEP_ALIVE", "10m"),
                auto_index_documents=os.getenv("PCT_LOCAL_AI_AUTO_INDEX_DOCUMENTS", "1").lower() not in {"0", "false", "no"},
            ),
        )

    # ── API pubblica ──────────────────────────────────────────────────

    @property
    def config(self) -> ConfigStudio:
        if self._cfg is None:
            self._cfg = self._carica()
        return self._cfg

    @property
    def file_esiste(self) -> bool:
        return self._path.exists()

    def aggiorna(self, cfg: ConfigStudio) -> None:
        self._cfg = cfg
        self._salva(cfg)

    def aggiorna_sezione(self, sezione: str, dati: Dict[str, Any]) -> ConfigStudio:
        """Aggiorna solo una sezione senza toccare le altre."""
        cfg = self.config
        d = cfg.to_dict()
        if sezione not in d:
            raise ValueError(f"Sezione sconosciuta: {sezione}")
        d[sezione].update(dati)
        nuovo = ConfigStudio.from_dict(d)
        self.aggiorna(nuovo)
        return nuovo


def percorso_config_studio_corrente(config_path: str | None = None) -> str:
    """
    Restituisce il percorso canonico della configurazione studio.

    Priorità:
      1. parametro esplicito
      2. PCT_CONFIG_STUDIO_DB
      3. PCT_STUDIO_CONFIG
      4. fallback legacy locale
    """
    return str(
        config_path
        or os.getenv("PCT_CONFIG_STUDIO_DB")
        or os.getenv("PCT_STUDIO_CONFIG")
        or "./config/studio.json"
    )


def risolvi_config_firma_corrente(config_path: str | None = None) -> Dict[str, str]:
    """
    Risolve la configurazione firma combinando file studio e variabili legacy.

    Il file `config/studio.json` resta la fonte canonica salvata dalla UI, ma i
    campi mancanti continuano a ereditare le vecchie variabili `PCT_FIRMA_*`.
    """
    path = percorso_config_studio_corrente(config_path)
    cfg: Optional[ConfigStudio] = None
    try:
        cfg = GestioneConfigStudio(config_path=path).config
    except Exception:
        cfg = None

    firma = getattr(cfg, "firma", None)
    studio = getattr(cfg, "studio", None)

    def _pick(value: Any, env_name: str) -> str:
        resolved = str(value or "").strip()
        if resolved:
            return resolved
        return str(os.getenv(env_name, "") or "").strip()

    cf_cfg = str(
        getattr(firma, "cf_avvocato", "")
        or getattr(studio, "codice_fiscale_avvocato", "")
        or ""
    ).strip().upper()

    return {
        "config_path": path,
        "p12_path": _pick(getattr(firma, "p12_path", ""), "PCT_FIRMA_P12"),
        "p12_password": _pick(getattr(firma, "password", ""), "PCT_FIRMA_PASSWORD"),
        "cert_pem_path": _pick(getattr(firma, "cert_pem_path", ""), "PCT_FIRMA_CERT"),
        "key_pem_path": _pick(getattr(firma, "key_pem_path", ""), "PCT_FIRMA_KEY"),
        "key_pem_password": _pick(
            getattr(firma, "key_pem_password", ""),
            "PCT_FIRMA_KEY_PASSWORD",
        ),
        "cf_avvocato": cf_cfg or str(os.getenv("PCT_CF_AVVOCATO", "") or "").strip().upper(),
    }


# ──────────────────────────────────────────────────────────── test connessioni

import smtplib as _smtplib
import socket as _socket_mod


def _resolve_ipv4(hostname: str, port: int) -> str | None:
    """Risolve hostname in IPv4 usando il resolver DNS di sistema.

    Usa direttamente socket.getaddrinfo() con il resolver DNS di Railway/sistema.
    Il tentativo DoH via IP diretto (1.1.1.1, 8.8.8.8) è stato rimosso perché
    Railway blocca le connessioni HTTPS verso quegli IP e restituiva IP errati
    (es. IP Google invece di server Brevo), causando timeout di rete.

    Se necessario, impostare PCT_DNS_SERVERS=8.8.8.8,1.1.1.1 per DNS custom
    (riservato a uso futuro — per ora il resolver di sistema è sufficiente).
    """
    try:
        infos = _socket_mod.getaddrinfo(hostname, port, _socket_mod.AF_INET, _socket_mod.SOCK_STREAM)
        if infos:
            return infos[0][4][0]
    except _socket_mod.gaierror:
        pass
    return None


class _SMTPv4(_smtplib.SMTP):
    """SMTP con connessione forzata su IPv4 tramite il resolver DNS di sistema.

    Usa _resolve_ipv4() per ottenere l'indirizzo IPv4 e connettersi direttamente,
    preservando l'hostname originale in self._host per SNI/TLS.
    """
    def _get_socket(self, host, port, timeout):
        ipv4_addr = _resolve_ipv4(host, port)
        if ipv4_addr:
            sock = _socket_mod.socket(_socket_mod.AF_INET, _socket_mod.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((ipv4_addr, port))  # errori propagati direttamente
            return sock
        return super()._get_socket(host, port, timeout)


class _SMTP_SSLv4(_smtplib.SMTP_SSL):
    """SMTP_SSL con connessione forzata su IPv4 tramite il resolver DNS di sistema."""
    def _ssl_context(self):
        ctx = getattr(self, "context", None) or getattr(self, "_context", None)
        if ctx is None:
            import ssl as _ssl
            ctx = _ssl.create_default_context()
            try:
                self.context = ctx
            except Exception:
                self._context = ctx
        return ctx

    def _get_socket(self, host, port, timeout):
        ipv4_addr = _resolve_ipv4(host, port)
        if ipv4_addr:
            raw = _socket_mod.socket(_socket_mod.AF_INET, _socket_mod.SOCK_STREAM)
            raw.settimeout(timeout)
            raw.connect((ipv4_addr, port))
            return self._ssl_context().wrap_socket(raw, server_hostname=host)
        return super()._get_socket(host, port, timeout)


def _msg_errore_rete(e: Exception, prefisso: str) -> str:
    """Trasforma eccezioni di rete in messaggi leggibili per l'utente."""
    import errno as _errno
    import socket
    codice = getattr(e, "errno", None)
    # DNS failure: hostname non trovato o non risolvibile
    if isinstance(e, socket.gaierror):
        host_info = ""
        args = getattr(e, "args", ())
        if len(args) >= 2:
            host_info = f" ({args[1]})"
        return (
            f"{prefisso}: hostname non trovato{host_info} — "
            "verificare che l'indirizzo del server sia corretto (es. smtp.gmail.com, "
            "smtp.office365.com). Se il problema persiste in Docker, "
            "aggiungere 'dns: [8.8.8.8, 8.8.4.4]' al servizio nel docker-compose.yml."
        )
    if codice == _errno.ENETUNREACH:
        return (
            f"{prefisso}: server SMTP non raggiungibile via IPv4. "
            "Cause comuni su Railway/cloud: (1) il provider SMTP blocca IP di hosting "
            "per anti-spam — richiedere whitelist o usare relay cloud-friendly "
            "(Brevo, SendGrid, Mailgun, Amazon SES); "
            "(2) porta chiusa — verificare 587 STARTTLS o 465 SSL."
        )
    if codice == _errno.ECONNREFUSED:
        return f"{prefisso}: connessione rifiutata — host o porta errati, o il server non è in ascolto."
    if codice == _errno.ETIMEDOUT or isinstance(e, TimeoutError):
        return (
            f"{prefisso}: timeout di rete — il server non risponde entro il tempo limite. "
            "Su Railway/cloud il problema più comune NON è la porta 25 (se stai già usando 587/465), "
            "ma un blocco anti-spam dell'IP di hosting lato provider SMTP. "
            "Verificare host/porta, provare 587 (STARTTLS) o 465 (SSL), "
            "ed eventualmente usare un relay cloud-friendly (Brevo/SendGrid/Mailgun/SES) "
            "o richiedere whitelist dell'IP."
        )
    return f"{prefisso}: {e}"


def test_pec_smtp(cfg: ConfigPEC) -> Dict[str, Any]:
    """Testa la connessione SMTP PEC. Restituisce {'ok': bool, 'messaggio': str}."""
    import smtplib
    import ssl as _ssl
    try:
        ctx = _ssl.create_default_context()
        if cfg.use_ssl:
            with _SMTP_SSLv4(cfg.smtp_host, cfg.smtp_port, context=ctx, timeout=10) as s:
                s.login(cfg.indirizzo, cfg.password)
        else:
            with _SMTPv4(cfg.smtp_host, cfg.smtp_port, timeout=10) as s:
                s.starttls(context=ctx)
                s.login(cfg.indirizzo, cfg.password)
        return {"ok": True, "messaggio": "Connessione SMTP PEC riuscita."}
    except Exception as e:
        return {"ok": False, "messaggio": _msg_errore_rete(e, "Errore SMTP PEC")}


def test_pec_imap(cfg: ConfigPEC) -> Dict[str, Any]:
    """Testa la connessione IMAP PEC. Restituisce {'ok': bool, 'messaggio': str}."""
    import imaplib
    import ssl as _ssl
    try:
        ctx = _ssl.create_default_context()
        with imaplib.IMAP4_SSL(cfg.imap_host, cfg.imap_port,
                                ssl_context=ctx) as m:
            m.login(cfg.indirizzo, cfg.password)
        return {"ok": True, "messaggio": "Connessione IMAP PEC riuscita."}
    except Exception as e:
        return {"ok": False, "messaggio": _msg_errore_rete(e, "Errore IMAP PEC")}


def test_smtp_email(cfg: ConfigSMTP) -> Dict[str, Any]:
    """Testa la connessione SMTP email normale."""
    import smtplib
    import ssl as _ssl
    if not cfg.host:
        return {"ok": False, "messaggio": "Host SMTP non configurato. Vai in Impostazioni → Email SMTP e inserisci l'indirizzo del server (es. smtp.gmail.com)."}
    # Porta 25 è bloccata da GCP/Railway/AWS outbound (anti-spam) → timeout garantito
    if cfg.port == 25:
        return {"ok": False, "messaggio": (
            "Porta 25 bloccata: Railway/GCP blocca outbound porta 25 per prevenire spam. "
            "Usare porta 587 (STARTTLS) o 465 (SSL diretto)."
        )}
    # Risolvi IPv4 con lo stesso metodo usato dalla connessione (resolver DNS di sistema)
    _resolved_ip = _resolve_ipv4(cfg.host, cfg.port)
    _ip_tag = f" [{_resolved_ip}:{cfg.port}]" if _resolved_ip else ""
    try:
        ctx = _ssl.create_default_context()
        if cfg.use_tls:
            # STARTTLS (porta 587 — Gmail, Outlook, IONOS…)
            with _SMTPv4(cfg.host, cfg.port, timeout=15) as s:
                s.starttls(context=ctx)
                if cfg.username:
                    s.login(cfg.username, cfg.password)
        else:
            # SSL diretto (porta 465 — Aruba, altri provider con SSL nativo)
            with _SMTP_SSLv4(cfg.host, cfg.port, context=ctx, timeout=15) as s:
                if cfg.username:
                    s.login(cfg.username, cfg.password)
        return {"ok": True, "messaggio": f"Connessione SMTP email riuscita{_ip_tag}."}
    except Exception as e:
        return {"ok": False, "messaggio": _msg_errore_rete(e, f"Errore SMTP email{_ip_tag}")}


def test_whatsapp(cfg: ConfigWhatsApp) -> Dict[str, Any]:
    """Testa la configurazione WhatsApp (Twilio o CallMeBot)."""
    if cfg.twilio_sid and cfg.twilio_token and cfg.twilio_numero:
        try:
            from pct.notifiche_wa import ConfigWA, invia_messaggio
            wa_cfg = ConfigWA(
                twilio_sid=cfg.twilio_sid,
                twilio_token=cfg.twilio_token,
                twilio_numero=cfg.twilio_numero,
                callmebot_key="",
            )
            risultato = invia_messaggio(cfg.twilio_numero, "Test PCT Studio — connessione OK.", wa_cfg)
            return {"ok": True, "messaggio": f"Twilio OK: {risultato.get('status', risultato)}"}
        except Exception as e:
            return {"ok": False, "messaggio": f"Errore Twilio: {e}"}
    if cfg.callmebot_key:
        try:
            from pct.notifiche_wa import ConfigWA, invia_messaggio
            wa_cfg = ConfigWA(
                twilio_sid="", twilio_token="", twilio_numero="",
                callmebot_key=cfg.callmebot_key,
            )
            risultato = invia_messaggio("", "Test PCT Studio — connessione OK.", wa_cfg)
            return {"ok": True, "messaggio": f"CallMeBot OK: {risultato}"}
        except Exception as e:
            return {"ok": False, "messaggio": f"Errore CallMeBot: {e}"}
    return {"ok": False, "messaggio": "Nessun provider WhatsApp configurato."}
