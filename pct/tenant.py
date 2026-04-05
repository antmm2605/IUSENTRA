"""
Gestione multi-tenant HACS — Studi Legali.

Ogni tenant (studio legale) ha:
  - Dati isolati in  ./data/tenants/{slug}/
  - Propri utenti
  - Moduli autorizzati in base al piano o configurazione manuale
  - Branding personalizzato (logo, colori)
  - Stato (ATTIVO, TRIAL, SOSPESO, SCADUTO)

Registry globale: ./data/tenants.json  (gestito dal SUPERADMIN)
"""

from __future__ import annotations

import json
import uuid
import re
import secrets
from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional


# ============================================================== Moduli disponibili

MODULI_DISPONIBILI: Dict[str, Dict[str, str]] = {
    "fascicoli":     {"nome": "Fascicoli",        "icona": "bi-folder2-open",     "desc": "Gestione pratiche e documenti"},
    "clienti":       {"nome": "Clienti",           "icona": "bi-people-fill",      "desc": "Anagrafica clienti e CRM"},
    "agenda":        {"nome": "Agenda",             "icona": "bi-calendar3",        "desc": "Appuntamenti e calendario"},
    "scadenziario":  {"nome": "Scadenziario",       "icona": "bi-alarm-fill",       "desc": "Termini e scadenze processuali"},
    "fatturazione":  {"nome": "Fatturazione",       "icona": "bi-receipt-cutoff",   "desc": "Parcelle e fatture professionali"},
    "pagamenti":     {"nome": "Pagamenti",          "icona": "bi-credit-card-fill", "desc": "Link pagamento e provider digitali"},
    "pec":           {"nome": "PEC",                "icona": "bi-envelope-check",   "desc": "Posta Elettronica Certificata"},
    "firma":         {"nome": "Firma Digitale",     "icona": "bi-pen-fill",         "desc": "Firma CAdES/PAdES documenti"},
    "deposito":      {"nome": "Deposito PCT",       "icona": "bi-cloud-upload-fill","desc": "Invio telematico atti processuali"},
    "notifiche":     {"nome": "Notifiche",          "icona": "bi-bell-fill",        "desc": "WhatsApp / email automatici"},
    "template_atti": {"nome": "Template Atti",      "icona": "bi-file-earmark-text","desc": "Modelli atti con variabili"},
    "portale":       {"nome": "Portale Cliente",    "icona": "bi-person-circle",    "desc": "Accesso self-service per i clienti"},
    "reports":       {"nome": "Report PDF",         "icona": "bi-file-pdf-fill",    "desc": "Stampa fascicoli e scadenziari"},
    "statistiche":   {"nome": "Statistiche",        "icona": "bi-bar-chart-fill",   "desc": "Analisi e dashboard avanzata"},
    "export_csv":    {"nome": "Export CSV",         "icona": "bi-download",         "desc": "Esportazione dati in CSV"},
    "messaggi":      {"nome": "Messaggistica",      "icona": "bi-chat-dots-fill",   "desc": "Messaggi interni e comunicazioni"},
    "backup":        {"nome": "Backup",             "icona": "bi-safe-fill",        "desc": "Backup automatico e manuale"},
    "privacy":       {"nome": "Privacy / GDPR",     "icona": "bi-shield-check",     "desc": "Registro trattamenti e consensi"},
    "condivisione":  {"nome": "Condivisione",       "icona": "bi-share-fill",       "desc": "Condivisione fascicoli tra colleghi"},
    "reginde":       {"nome": "ReGINde",            "icona": "bi-search",           "desc": "Ricerca indirizzi PEC su registro"},
}


# ============================================================== Piani

class PianoTenant(str):
    TRIAL        = "TRIAL"
    STARTER      = "STARTER"
    PROFESSIONAL = "PROFESSIONAL"
    ENTERPRISE   = "ENTERPRISE"

PIANI: Dict[str, Dict[str, Any]] = {
    PianoTenant.TRIAL: {
        "nome":        "Trial (30 gg)",
        "durata_gg":   30,
        "max_utenti":  2,
        "max_storage_mb": 500,
        "moduli": ["fascicoli", "clienti", "agenda", "scadenziario"],
        "colore": "secondary",
    },
    PianoTenant.STARTER: {
        "nome":        "Starter",
        "durata_gg":   365,
        "max_utenti":  3,
        "max_storage_mb": 2_000,
        "moduli": [
            "fascicoli", "clienti", "agenda", "scadenziario",
            "export_csv", "backup", "privacy",
        ],
        "colore": "info",
    },
    PianoTenant.PROFESSIONAL: {
        "nome":        "Professional",
        "durata_gg":   365,
        "max_utenti":  10,
        "max_storage_mb": 20_000,
        "moduli": [
            "fascicoli", "clienti", "agenda", "scadenziario",
            "fatturazione", "pagamenti", "notifiche",
            "template_atti", "portale", "reports", "statistiche",
            "export_csv", "backup", "privacy", "messaggi", "condivisione",
        ],
        "colore": "primary",
    },
    PianoTenant.ENTERPRISE: {
        "nome":        "Enterprise",
        "durata_gg":   365,
        "max_utenti":  0,           # 0 = illimitati
        "max_storage_mb": 0,        # 0 = illimitato
        "moduli": list(MODULI_DISPONIBILI.keys()),
        "colore": "danger",
    },
}


# ============================================================== Modalità database

class DbMode(str):
    LOCAL      = "LOCAL"       # JSON su filesystem (default, zero dipendenze)
    MYSQL      = "MYSQL"       # MySQL / MariaDB via SQLAlchemy
    POSTGRESQL = "POSTGRESQL"  # PostgreSQL via SQLAlchemy


DB_MODE_INFO: Dict[str, Dict[str, Any]] = {
    DbMode.LOCAL: {
        "nome":    "Locale (JSON)",
        "icona":   "bi-hdd-fill",
        "colore":  "secondary",
        "porta":   None,
        "desc":    "Dati salvati su filesystem. Nessuna configurazione richiesta. "
                   "Ideale per studi con volumi ridotti o ambienti senza DB server.",
        "badge":   "Incluso in tutti i piani",
        "piano_min": None,  # disponibile sempre
    },
    DbMode.MYSQL: {
        "nome":    "MySQL / MariaDB",
        "icona":   "bi-database-fill",
        "colore":  "warning",
        "porta":   3306,
        "desc":    "Database relazionale MySQL/MariaDB. Prestazioni superiori per studi "
                   "con molti fascicoli. Richiede server MySQL accessibile.",
        "badge":   "Professional / Enterprise",
        "piano_min": "PROFESSIONAL",
    },
    DbMode.POSTGRESQL: {
        "nome":    "PostgreSQL",
        "icona":   "bi-database-fill-gear",
        "colore":  "primary",
        "porta":   5432,
        "desc":    "PostgreSQL — massima affidabilità, ACID compliant, supporto JSON nativo. "
                   "Consigliato per studi enterprise e deployment su cloud.",
        "badge":   "Enterprise (raccomandato)",
        "piano_min": "ENTERPRISE",
    },
}


from dataclasses import dataclass, asdict

@dataclass
class DatabaseConfig:
    """
    Configurazione del database per un tenant.
    Per modalità LOCAL tutti i campi sono vuoti (non usati).
    """
    mode: str = DbMode.LOCAL

    # Connessione (MySQL / PostgreSQL)
    host: str = "localhost"
    porta: int = 0  # 0 = porta default del driver
    db_name: str = ""
    utente: str = ""
    password: str = ""  # NB: cifrata con AES in produzione
    ssl: bool = False
    pool_size: int = 5
    pool_timeout: int = 30

    # Stato ultima verifica connessione
    connessione_ok: bool = False
    ultimo_test: str = ""  # ISO timestamp
    errore_connessione: str = ""

    @property
    def porta_effettiva(self) -> int:
        if self.porta:
            return self.porta
        defaults = {
            DbMode.MYSQL: 3306,
            DbMode.POSTGRESQL: 5432,
        }
        return defaults.get(self.mode, 0)

    @property
    def connection_url(self) -> str:
        if self.mode == DbMode.LOCAL:
            return ""

        if self.mode == DbMode.MYSQL:
            driver = "mysql+pymysql"
            ssl_suffix = "?ssl=true" if self.ssl else ""
            return (
                f"{driver}://{self.utente}:{self.password}"
                f"@{self.host}:{self.porta_effettiva}/{self.db_name}{ssl_suffix}"
            )

        if self.mode == DbMode.POSTGRESQL:
            driver = "postgresql+psycopg2"
            ssl_suffix = "?sslmode=require" if self.ssl else ""
            return (
                f"{driver}://{self.utente}:{self.password}"
                f"@{self.host}:{self.porta_effettiva}/{self.db_name}{ssl_suffix}"
            )

        return ""

    @property
    def connection_url_safe(self) -> str:
        """URL senza password (per display)."""
        if self.mode == DbMode.LOCAL:
            return "filesystem://local"

        driver = (
            "mysql+pymysql"
            if self.mode == DbMode.MYSQL
            else "postgresql+psycopg2"
        )
        return f"{driver}://{self.utente}:***@{self.host}:{self.porta_effettiva}/{self.db_name}"

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict | str | None) -> "DatabaseConfig":
        if isinstance(d, DatabaseConfig):
            return d
        if d is None:
            d = {}
        elif isinstance(d, str):
            mode = d.strip().upper()
            d = {"mode": mode} if mode in (DbMode.LOCAL, DbMode.MYSQL, DbMode.POSTGRESQL) else {}
        elif not isinstance(d, dict):
            d = {}
        else:
            d = dict(d)
            if not d.get("mode"):
                for legacy_key in ("db_mode", "database_mode", "tipo", "engine"):
                    legacy_mode = d.get(legacy_key)
                    if isinstance(legacy_mode, str):
                        normalized = legacy_mode.strip().upper()
                        if normalized in (DbMode.LOCAL, DbMode.MYSQL, DbMode.POSTGRESQL):
                            d["mode"] = normalized
                            break

        d.setdefault("mode", DbMode.LOCAL)
        d.setdefault("host", "localhost")
        d.setdefault("porta", 0)
        d.setdefault("db_name", "")
        d.setdefault("utente", "")
        d.setdefault("password", "")
        d.setdefault("ssl", False)
        d.setdefault("pool_size", 5)
        d.setdefault("pool_timeout", 30)
        d.setdefault("connessione_ok", False)
        d.setdefault("ultimo_test", "")
        d.setdefault("errore_connessione", "")

        return DatabaseConfig(
            **{k: v for k, v in d.items() if k in DatabaseConfig.__dataclass_fields__}
        )


# ============================================================== Stato tenant

class StatoTenant(str):
    ATTIVO  = "ATTIVO"
    TRIAL   = "TRIAL"
    SOSPESO = "SOSPESO"
    SCADUTO = "SCADUTO"


# ============================================================== Dataclasses

@dataclass
class BrandingStudio:
    """Configurazione estetica dello studio."""
    logo_url:          str = ""   # URL logo (es. /static/tenants/{slug}/logo.png)
    colore_primario:   str = "#1a3a5c"
    colore_secondario: str = "#2563eb"
    colore_accent:     str = "#3b82f6"
    nome_sistema:      str = "Studio Legale PCT"

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "BrandingStudio":
        return BrandingStudio(**{k: v for k, v in d.items() if k in BrandingStudio.__dataclass_fields__})


@dataclass
class StudioLegale:
    """
    Tenant rappresentante uno studio legale sulla piattaforma HACS.
    """
    id:               str  = field(default_factory=lambda: str(uuid.uuid4()))
    slug:             str  = ""           # URL-safe, unico (es. "studio-rossi")
    nome:             str  = ""           # Nome visualizzato
    piva:             str  = ""
    cf:               str  = ""
    indirizzo:        str  = ""
    telefono:         str  = ""
    email:            str  = ""
    pec:              str  = ""
    avvocato_ref:     str  = ""           # Nome avvocato titolare / referente

    # Piano e stato
    piano:            str  = PianoTenant.TRIAL
    stato:            str  = StatoTenant.TRIAL
    data_creazione:   str  = field(default_factory=lambda: datetime.now().isoformat())
    data_attivazione: str  = ""
    data_scadenza:    str  = ""
    note_admin:       str  = ""

    # Moduli autorizzati (se vuota → usa quelli del piano)
    moduli_override:  List[str] = field(default_factory=list)

    # Limiti (0 = usa quelli del piano)
    max_utenti:    int = 0
    max_storage_mb: int = 0

    # Branding
    branding: Dict[str, str] = field(default_factory=dict)

    # Configurazione database (LOCAL | MYSQL | POSTGRESQL)
    db_config: Dict[str, Any] = field(default_factory=dict)

    # API key dello studio (per REST API interna)
    api_key: str = field(default_factory=lambda: secrets.token_urlsafe(32))

    # ---- computed properties

    @property
    def moduli_attivi(self) -> List[str]:
        """Moduli effettivi: override se presente, altrimenti quelli del piano."""
        if self.moduli_override:
            return self.moduli_override
        return PIANI.get(self.piano, {}).get("moduli", [])

    @property
    def limite_utenti(self) -> int:
        if self.max_utenti:
            return self.max_utenti
        return PIANI.get(self.piano, {}).get("max_utenti", 2)

    @property
    def limite_storage_mb(self) -> int:
        if self.max_storage_mb:
            return self.max_storage_mb
        return PIANI.get(self.piano, {}).get("max_storage_mb", 500)

    @property
    def is_scaduto(self) -> bool:
        if not self.data_scadenza:
            return False
        try:
            return datetime.fromisoformat(self.data_scadenza) < datetime.now()
        except ValueError:
            return False

    @property
    def giorni_alla_scadenza(self) -> Optional[int]:
        if not self.data_scadenza:
            return None
        try:
            delta = datetime.fromisoformat(self.data_scadenza) - datetime.now()
            return delta.days
        except ValueError:
            return None

    @property
    def colore_piano(self) -> str:
        return PIANI.get(self.piano, {}).get("colore", "secondary")

    def modulo_attivo(self, modulo: str) -> bool:
        return modulo in self.moduli_attivi

    @property
    def database(self) -> DatabaseConfig:
        """Restituisce la configurazione DB tipizzata."""
        try:
            return DatabaseConfig.from_dict(self.db_config) if self.db_config else DatabaseConfig()
        except Exception:
            return DatabaseConfig()

    @property
    def db_mode(self) -> str:
        return self.database.mode

    # ---- serializzazione

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    @staticmethod
    def from_dict(d: dict) -> "StudioLegale":
        d = dict(d)
        legacy_db = d.get("db_config", d.get("database", {}))
        if isinstance(legacy_db, str):
            normalized = legacy_db.strip().upper()
            d["db_config"] = {"mode": normalized} if normalized in (DbMode.LOCAL, DbMode.MYSQL, DbMode.POSTGRESQL) else {}
        elif isinstance(legacy_db, dict):
            d["db_config"] = legacy_db
        else:
            d["db_config"] = {}

        branding = d.get("branding", {})
        d["branding"] = branding if isinstance(branding, dict) else {}

        override = d.get("moduli_override", [])
        if isinstance(override, list):
            d["moduli_override"] = [str(v).strip() for v in override if str(v).strip()]
        elif isinstance(override, str):
            d["moduli_override"] = [v.strip() for v in override.split(",") if v.strip()]
        else:
            d["moduli_override"] = []

        d.setdefault("moduli_override", [])
        d.setdefault("api_key", secrets.token_urlsafe(32))
        d.setdefault("note_admin", "")
        d.setdefault("avvocato_ref", "")
        d.setdefault("max_utenti", 0)
        d.setdefault("max_storage_mb", 0)
        d.setdefault("data_attivazione", "")
        return StudioLegale(**{k: v for k, v in d.items() if k in StudioLegale.__dataclass_fields__})


# ============================================================== GestioneTenant

class GestioneTenant:
    """
    Repository per la gestione degli studi legali (tenant).

    File:  <registry_path>  (default: ./data/tenants.json)
    Dati tenant: ./data/tenants/{slug}/
    """

    def __init__(self, registry_path: str = "./data/tenants.json"):
        self.registry_path = Path(registry_path)
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        self._cache: Optional[Dict[str, StudioLegale]] = None

    # ---- I/O

    def _carica(self) -> Dict[str, StudioLegale]:
        if self._cache is not None:
            return self._cache
        if not self.registry_path.exists():
            self._cache = {}
            return self._cache
        try:
            raw = json.loads(self.registry_path.read_text(encoding="utf-8"))
            self._cache = {slug: StudioLegale.from_dict(v) for slug, v in raw.items()}
        except Exception:
            self._cache = {}
        return self._cache

    def _salva(self, studi: Dict[str, StudioLegale]) -> None:
        self._cache = studi
        tmp = self.registry_path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps({slug: s.to_dict() for slug, s in studi.items()}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp.replace(self.registry_path)

    def _invalida_cache(self) -> None:
        self._cache = None

    # ---- CRUD

    def lista(self) -> List[StudioLegale]:
        return sorted(self._carica().values(), key=lambda s: s.nome.lower())

    def get(self, slug: str) -> Optional[StudioLegale]:
        slug_norm = self._normalizza_slug(slug or "")
        studi = self._carica()
        studio = studi.get(slug_norm) or studi.get(slug)
        if studio:
            return studio
        for candidato in studi.values():
            if self._normalizza_slug(candidato.slug or "") == slug_norm:
                return candidato
        return None

    def get_by_id(self, id_studio: str) -> Optional[StudioLegale]:
        for s in self._carica().values():
            if s.id == id_studio:
                return s
        return None

    def crea(
        self,
        nome: str,
        slug: str,
        piano: str = PianoTenant.TRIAL,
        **kwargs,
    ) -> StudioLegale:
        """Crea un nuovo studio e inizializza la sua directory dati."""
        slug = self._normalizza_slug(slug)
        studi = self._carica()
        if slug in studi:
            raise ValueError(f"Slug '{slug}' già in uso")
        if not self._slug_valido(slug):
            raise ValueError(f"Slug '{slug}' non valido (solo lettere, cifre, trattini)")

        studio = StudioLegale(nome=nome, slug=slug, piano=piano, **kwargs)

        # Calcola data scadenza in base al piano
        durata = PIANI.get(piano, {}).get("durata_gg", 30)
        studio.data_scadenza = (datetime.now() + timedelta(days=durata)).isoformat()
        if piano != PianoTenant.TRIAL:
            studio.stato = StatoTenant.ATTIVO
            studio.data_attivazione = datetime.now().isoformat()
        else:
            studio.stato = StatoTenant.TRIAL

        # Crea directory dati isolata
        self._inizializza_directory(slug)

        studi[slug] = studio
        self._salva(studi)
        return studio

    def aggiorna(self, slug: str, **kwargs) -> Optional[StudioLegale]:
        studi = self._carica()
        studio = studi.get(slug)
        if not studio:
            return None
        for k, v in kwargs.items():
            if hasattr(studio, k):
                setattr(studio, k, v)
        studi[slug] = studio
        self._salva(studi)
        return studio

    def elimina(self, slug: str, elimina_dati: bool = False) -> bool:
        """
        Rimuove il tenant dal registry.
        Se elimina_dati=True cancella anche la directory dati (IRREVERSIBILE).
        """
        studi = self._carica()
        if slug not in studi:
            return False
        del studi[slug]
        self._salva(studi)
        if elimina_dati:
            import shutil
            data_dir = self._data_dir(slug)
            if data_dir.exists():
                shutil.rmtree(data_dir)
        return True

    def sospendi(self, slug: str) -> bool:
        return bool(self.aggiorna(slug, stato=StatoTenant.SOSPESO))

    def riattiva(self, slug: str) -> bool:
        return bool(self.aggiorna(slug, stato=StatoTenant.ATTIVO))

    def aggiorna_piano(self, slug: str, piano: str, moduli_override: Optional[List[str]] = None) -> Optional[StudioLegale]:
        durata = PIANI.get(piano, {}).get("durata_gg", 365)
        nuova_scadenza = (datetime.now() + timedelta(days=durata)).isoformat()
        return self.aggiorna(
            slug,
            piano=piano,
            data_scadenza=nuova_scadenza,
            moduli_override=moduli_override or [],
            stato=StatoTenant.ATTIVO,
        )

    def aggiorna_moduli(self, slug: str, moduli: List[str]) -> Optional[StudioLegale]:
        return self.aggiorna(slug, moduli_override=moduli)

    def rigenera_api_key(self, slug: str) -> Optional[str]:
        nuova = secrets.token_urlsafe(32)
        studio = self.aggiorna(slug, api_key=nuova)
        return nuova if studio else None

    def aggiorna_db_config(self, slug: str, config: DatabaseConfig) -> Optional[StudioLegale]:
        """Salva la configurazione database del tenant."""
        return self.aggiorna(slug, db_config=config.to_dict())

    def testa_connessione(self, slug: str) -> Dict[str, Any]:
        """
        Testa la connessione al database del tenant.
        Ritorna { ok: bool, messaggio: str, latenza_ms: int }.
        Aggiorna anche db_config.connessione_ok e ultimo_test.
        """
        import time as _t
        studi = self._carica()
        studio = studi.get(slug)
        if not studio:
            return {"ok": False, "messaggio": "Studio non trovato", "latenza_ms": 0}

        db = studio.database

        if db.mode == DbMode.LOCAL:
            data_dir = self._data_dir(slug)
            ok = data_dir.exists()
            msg = "Directory locale accessibile." if ok else f"Directory non trovata: {data_dir}"
            db.connessione_ok = ok
            db.ultimo_test = datetime.now().isoformat()
            db.errore_connessione = "" if ok else msg
            studio.db_config = db.to_dict()
            self._salva(studi)
            return {"ok": ok, "messaggio": msg, "latenza_ms": 0}

        # MySQL / PostgreSQL
        url = db.connection_url
        if not url:
            return {"ok": False, "messaggio": "Configurazione DB incompleta.", "latenza_ms": 0}

        t0 = _t.monotonic()
        try:
            import sqlalchemy  # noqa: F401
            from sqlalchemy import create_engine, text
            engine = create_engine(url, pool_timeout=5, connect_args={"connect_timeout": 5})
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            latenza = int((_t.monotonic() - t0) * 1000)
            db.connessione_ok = True
            db.ultimo_test = datetime.now().isoformat()
            db.errore_connessione = ""
            studio.db_config = db.to_dict()
            self._salva(studi)
            return {"ok": True, "messaggio": f"Connessione riuscita in {latenza} ms.", "latenza_ms": latenza}
        except ImportError:
            msg = "SQLAlchemy non installato. Esegui: pip install sqlalchemy pymysql psycopg2-binary"
        except Exception as exc:
            msg = str(exc)
        latenza = int((_t.monotonic() - t0) * 1000)
        db.connessione_ok = False
        db.ultimo_test = datetime.now().isoformat()
        db.errore_connessione = msg
        studio.db_config = db.to_dict()
        self._salva(studi)
        return {"ok": False, "messaggio": msg, "latenza_ms": latenza}

    # ---- Statistiche globali

    def statistiche(self) -> Dict[str, Any]:
        tutti = self.lista()
        return {
            "totale":      len(tutti),
            "attivi":      sum(1 for s in tutti if s.stato == StatoTenant.ATTIVO),
            "trial":       sum(1 for s in tutti if s.stato == StatoTenant.TRIAL),
            "sospesi":     sum(1 for s in tutti if s.stato == StatoTenant.SOSPESO),
            "scaduti":     sum(1 for s in tutti if s.is_scaduto),
            "per_piano":   {p: sum(1 for s in tutti if s.piano == p) for p in PIANI},
        }

    def verifica_scadenze(self) -> List[StudioLegale]:
        """Aggiorna a SCADUTO gli studi la cui data_scadenza è passata."""
        studi = self._carica()
        aggiornati = []
        for slug, studio in studi.items():
            if studio.stato not in (StatoTenant.SOSPESO,) and studio.is_scaduto:
                studio.stato = StatoTenant.SCADUTO
                aggiornati.append(studio)
        if aggiornati:
            self._salva(studi)
        return aggiornati

    # ---- Directory dati

    def _data_dir(self, slug: str) -> Path:
        return self.registry_path.parent / "tenants" / slug

    def data_dir(self, slug: str) -> Path:
        return self._data_dir(slug)

    def _inizializza_directory(self, slug: str) -> None:
        base = self._data_dir(slug)
        for subdir in [
            "auth", "clienti", "fascicoli", "fascicoli/documenti", "fascicoli/archivio",
            "agenda", "scadenziario", "fatturazione", "messaggi", "backup",
            "notifiche", "pagamenti", "portale", "portale/uploads",
            "privacy", "condivisioni", "template_atti", "wizard_pro",
            "intelligence", "search",
            # directory aggiuntive per moduli preventivi, email e soggetti
            "preventivi", "email", "soggetti",
        ]:
            (base / subdir).mkdir(parents=True, exist_ok=True)

    def percorsi_dati(self, slug: str) -> Dict[str, str]:
        """Restituisce il dizionario di configurazione data paths per questo tenant."""
        base = str(self._data_dir(slug))
        return {
            "AGENDA_DB":         f"{base}/agenda/appuntamenti.json",
            "CALENDAR_SYNC_DB":  f"{base}/agenda/calendar_sync.json",
            "CLIENTI_DB":        f"{base}/clienti/anagrafica.json",
            "CONDIVISIONI_DB":   f"{base}/clienti/condivisioni.json",
            "FASCICOLI_DB":      f"{base}/fascicoli/fascicoli.json",
            "FASCICOLI_DOCS":    f"{base}/fascicoli/documenti",
            "FASCICOLI_ARCH":    f"{base}/fascicoli/archivio",
            "MESSAGGI_DB":       f"{base}/messaggi/storico.json",
            "BACKUP_DIR":        f"{base}/backup",
            "AUTH_DB":           f"{base}/auth/utenti.json",
            "AUDIT_DB":          f"{base}/auth/audit.json",
            "SCADENZIARIO_DB":   f"{base}/scadenziario/scadenze.json",
            "SEARCH_INDEX":      f"{base}/search/index.db",
            "PRIVACY_DB":        f"{base}/privacy/registro.json",
            "PORTALE_DB":        f"{base}/portale/portali.json",
            "PORTALE_UPLOADS":   f"{base}/portale/uploads",
            "FATTURAZIONE_DB":   f"{base}/fatturazione/parcelle.json",
            "NOTIFICHE_LOG":     f"{base}/notifiche/log.json",
            "PAGAMENTI_DIR":     f"{base}/pagamenti",
            "TEMPLATE_ATTI_DB":  f"{base}/template_atti/templates.json",
            "TEMPLATE_ATTI_PREFS_DB": f"{base}/template_atti/editor_layout.json",
            "WIZARD_PRO_DB":     f"{base}/wizard_pro/sessioni.json",
            "LEGAL_INTELLIGENCE_DB": f"{base}/intelligence/motori.json",
            "NORMATIVE_TABLES_DB": f"{base}/intelligence/tabelle_normative.json",
            "VALIDATION_RUNS_DB": f"{base}/intelligence/validation_runs.json",
            "REDACTION_ASSISTANT_DB": f"{base}/intelligence/assistente_redazionale.json",
            # Percorsi aggiuntivi necessari per isolamento tenant completo
            "NOTE_FALDONE_DB":   f"{base}/clienti/note_faldone.json",
            "EMAIL_CASELLA_DB":  f"{base}/email/casella.json",
            "PREVENTIVI_DB":     f"{base}/preventivi/preventivi.json",
            "SOGGETTI_DB":       f"{base}/soggetti/soggetti.json",
            "SOGGETTI_PARTI_DB": f"{base}/soggetti/soggetti_parti.json",
        }

    # ---- Helper

    @staticmethod
    def _normalizza_slug(slug: str) -> str:
        return slug.lower().strip().replace(" ", "-")

    @staticmethod
    def _slug_valido(slug: str) -> bool:
        return bool(re.match(r'^[a-z0-9][a-z0-9\-]{1,48}[a-z0-9]$', slug))
