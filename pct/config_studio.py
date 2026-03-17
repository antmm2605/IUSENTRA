"""
pct/config_studio.py — Configurazione persistente dello studio legale.

Salva tutte le impostazioni in un singolo file JSON:
  /data/config/studio.json  (o percorso configurabile)

Include:
  - Dati anagrafici studio
  - Configurazione PEC  (SMTP/IMAP)
  - Firma digitale
  - Email SMTP normale
  - WhatsApp (Twilio / CallMeBot)
  - Scheduler (ore esecuzione job automatici)
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, Optional


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
    p12_path: str = ""
    password: str = ""
    cf_avvocato: str = ""


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
        return cls(
            studio=ConfigDatiStudio(**{
                k: v for k, v in d.get("studio", {}).items()
                if k in ConfigDatiStudio.__dataclass_fields__
            }),
            pec=ConfigPEC(**{
                k: v for k, v in d.get("pec", {}).items()
                if k in ConfigPEC.__dataclass_fields__
            }),
            firma=ConfigFirma(**{
                k: v for k, v in d.get("firma", {}).items()
                if k in ConfigFirma.__dataclass_fields__
            }),
            smtp=ConfigSMTP(**{
                k: v for k, v in d.get("smtp", {}).items()
                if k in ConfigSMTP.__dataclass_fields__
            }),
            whatsapp=ConfigWhatsApp(**{
                k: v for k, v in d.get("whatsapp", {}).items()
                if k in ConfigWhatsApp.__dataclass_fields__
            }),
            scheduler=ConfigScheduler(**{
                k: v for k, v in d.get("scheduler", {}).items()
                if k in ConfigScheduler.__dataclass_fields__
            }),
        )


# ──────────────────────────────────────────────────────────── gestore

class GestioneConfigStudio:
    """
    Carica e salva la configurazione dello studio da/verso un file JSON.
    Se il file non esiste restituisce valori di default (dal env se presenti).
    """

    def __init__(self, config_path: str = "./config/studio.json"):
        self._path = Path(config_path)
        self._cfg: Optional[ConfigStudio] = None

    # ── I/O ──────────────────────────────────────────────────────────

    def _carica(self) -> ConfigStudio:
        if self._path.exists():
            try:
                raw = json.loads(self._path.read_text(encoding="utf-8"))
                return ConfigStudio.from_dict(raw)
            except Exception:
                pass
        # Prima volta: pre-popola dai valori env (compatibilità backward)
        return self._da_env()

    def _salva(self, cfg: ConfigStudio) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(cfg.to_dict(), ensure_ascii=False, indent=2),
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

    def aggiorna(self, cfg: ConfigStudio) -> None:
        self._cfg = cfg
        self._salva(cfg)

    def aggiorna_sezione(self, sezione: str, dati: Dict[str, Any]) -> ConfigStudio:
        """
        Aggiorna solo una sezione (es. "pec", "smtp") senza toccare le altre.
        Restituisce la configurazione aggiornata.
        """
        cfg = self.config
        d = cfg.to_dict()
        if sezione not in d:
            raise ValueError(f"Sezione sconosciuta: {sezione}")
        d[sezione].update(dati)
        nuovo = ConfigStudio.from_dict(d)
        self.aggiorna(nuovo)
        return nuovo


# ──────────────────────────────────────────────────────────── test connessioni

def test_pec_smtp(cfg: ConfigPEC) -> Dict[str, Any]:
    """Testa la connessione SMTP PEC. Restituisce {'ok': bool, 'messaggio': str}."""
    import smtplib
    import ssl as _ssl
    try:
        ctx = _ssl.create_default_context()
        if cfg.use_ssl:
            with smtplib.SMTP_SSL(cfg.smtp_host, cfg.smtp_port,
                                   context=ctx, timeout=10) as s:
                s.login(cfg.indirizzo, cfg.password)
        else:
            with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=10) as s:
                s.starttls(context=ctx)
                s.login(cfg.indirizzo, cfg.password)
        return {"ok": True, "messaggio": "Connessione SMTP PEC riuscita."}
    except Exception as e:
        return {"ok": False, "messaggio": f"Errore SMTP: {e}"}


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
        return {"ok": False, "messaggio": f"Errore IMAP: {e}"}


def test_smtp_email(cfg: ConfigSMTP) -> Dict[str, Any]:
    """Testa la connessione SMTP email normale."""
    import smtplib
    import ssl as _ssl
    try:
        ctx = _ssl.create_default_context()
        with smtplib.SMTP(cfg.host, cfg.port, timeout=10) as s:
            if cfg.use_tls:
                s.starttls(context=ctx)
            if cfg.username:
                s.login(cfg.username, cfg.password)
        return {"ok": True, "messaggio": "Connessione SMTP email riuscita."}
    except Exception as e:
        return {"ok": False, "messaggio": f"Errore SMTP email: {e}"}
