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

    # ── Comune ai due formati ────────────────────────────────────────────────
    cf_avvocato: str = ""

    @property
    def formato_attivo(self) -> str:
        """Restituisce il formato rilevato: 'p12', 'pem' o 'nessuno'."""
        import os as _os
        if self.p12_path and _os.path.exists(self.p12_path):
            return "p12"
        if self.cert_pem_path and self.key_pem_path and \
           _os.path.exists(self.cert_pem_path) and _os.path.exists(self.key_pem_path):
            return "pem"
        return "nessuno"

    @property
    def configurato(self) -> bool:
        return self.formato_attivo != "nessuno"


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
class ConfigStudio:
    studio: ConfigDatiStudio = field(default_factory=ConfigDatiStudio)
    pec: ConfigPEC = field(default_factory=ConfigPEC)
    firma: ConfigFirma = field(default_factory=ConfigFirma)
    smtp: ConfigSMTP = field(default_factory=ConfigSMTP)
    whatsapp: ConfigWhatsApp = field(default_factory=ConfigWhatsApp)
    scheduler: ConfigScheduler = field(default_factory=ConfigScheduler)

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
        )


# ──────────────────────────────────────────────────────────── gestore

class GestioneConfigStudio:
    """
    Carica e salva la configurazione dello studio da/verso un file JSON.
    Le password sono cifrate con Fernet usando PCT_SECRET_KEY.
    Se il file non esiste, pre-popola dai valori delle variabili d'ambiente.
    """

    def __init__(self, config_path: str = "./config/studio.json"):
        self._path = Path(config_path)
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
                cf_avvocato=os.getenv("PCT_CF_AVVOCATO", ""),
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


# ──────────────────────────────────────────────────────────── test connessioni

import smtplib as _smtplib
import socket as _socket_mod


class _SMTPv4(_smtplib.SMTP):
    """SMTP con connessione forzata su IPv4.

    Railway e ambienti cloud analoghi non hanno routing IPv6 outbound.
    Python prova prima gli indirizzi IPv6 (AAAA) restituiti dal DNS → ENETUNREACH
    o 'Address family not supported'. Questa subclass sovrascrive _get_socket
    per risolvere l'hostname esclusivamente in IPv4, preservando l'hostname
    originale in self._host per la validazione TLS/SNI in fase di STARTTLS.
    """
    def _get_socket(self, host, port, timeout):
        try:
            infos = _socket_mod.getaddrinfo(
                host, port, _socket_mod.AF_INET, _socket_mod.SOCK_STREAM)
            if infos:
                ipv4_addr = infos[0][4][0]
                sock = _socket_mod.socket(_socket_mod.AF_INET, _socket_mod.SOCK_STREAM)
                sock.settimeout(timeout)
                sock.connect((ipv4_addr, port))
                return sock
        except (_socket_mod.gaierror, OSError):
            pass
        return super()._get_socket(host, port, timeout)


class _SMTP_SSLv4(_smtplib.SMTP_SSL):
    """SMTP_SSL con connessione forzata su IPv4 (stesso razionale di _SMTPv4).

    Risolve l'hostname in IPv4 e avvolge il socket con SSL usando l'hostname
    originale come server_hostname per la corretta validazione del certificato.
    """
    def _get_socket(self, host, port, timeout):
        try:
            infos = _socket_mod.getaddrinfo(
                host, port, _socket_mod.AF_INET, _socket_mod.SOCK_STREAM)
            if infos:
                ipv4_addr = infos[0][4][0]
                raw = _socket_mod.socket(_socket_mod.AF_INET, _socket_mod.SOCK_STREAM)
                raw.settimeout(timeout)
                raw.connect((ipv4_addr, port))
                # Avvolge con SSL usando l'hostname originale per SNI e verifica cert
                return self._context.wrap_socket(raw, server_hostname=host)
        except (_socket_mod.gaierror, OSError):
            pass
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
            f"{prefisso}: rete non raggiungibile — probabilmente IPv6 non supportato "
            "sul server. Il gestionale forza automaticamente IPv4; se l'errore persiste "
            "verificare che la porta SMTP sia aperta (587 STARTTLS o 465 SSL)."
        )
    if codice == _errno.ECONNREFUSED:
        return f"{prefisso}: connessione rifiutata — host o porta errati, o il server non è in ascolto."
    if codice == _errno.ETIMEDOUT or isinstance(e, TimeoutError):
        return f"{prefisso}: timeout — il server non risponde entro 10 secondi. Verificare host e porta."
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
    try:
        ctx = _ssl.create_default_context()
        if cfg.use_tls:
            # STARTTLS (porta 587 — Gmail, Outlook, IONOS…)
            with _SMTPv4(cfg.host, cfg.port, timeout=10) as s:
                s.starttls(context=ctx)
                if cfg.username:
                    s.login(cfg.username, cfg.password)
        else:
            # SSL diretto (porta 465 — Aruba, altri provider con SSL nativo)
            with _SMTP_SSLv4(cfg.host, cfg.port, context=ctx, timeout=10) as s:
                if cfg.username:
                    s.login(cfg.username, cfg.password)
        return {"ok": True, "messaggio": "Connessione SMTP email riuscita."}
    except Exception as e:
        return {"ok": False, "messaggio": _msg_errore_rete(e, "Errore SMTP email")}


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
