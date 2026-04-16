"""
Gestione multi-tenant IUSENTRA — Studi Legali.

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
import shutil
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional


TENANT_FILE_SEED_PATHS: tuple[str, ...] = (
    "agenda/appuntamenti.json",
    "agenda/calendar_sync.json",
    "auth/utenti.json",
    "auth/audit.json",
    "backup/config.json",
    "backup/registro.json",
    "clienti/anagrafica.json",
    "clienti/condivisioni.json",
    "clienti/note_faldone.json",
    "config/studio.json",
    "email/casella.json",
    "fascicoli/fascicoli.json",
    "fatturazione/parcelle.json",
    "intelligence/assistente_redazionale.json",
    "intelligence/giurisprudenza.json",
    "intelligence/local_ai.db",
    "intelligence/motori.json",
    "intelligence/tabelle_normative.json",
    "intelligence/validation_runs.json",
    "intelligence/workspace_intelligence.json",
    "messaggi/storico.json",
    "notifiche/log.json",
    "portale/portali.json",
    "preventivi/conferimenti.json",
    "preventivi/preventivi.json",
    "privacy/registro.json",
    "scadenziario/scadenze.json",
    "search/index.db",
    "soggetti/anagrafica.json",
    "soggetti/parti.json",
    "studio.db",
    "template_atti/editor_layout.json",
    "template_atti/templates.json",
    "wizard_pro/sessioni.json",
)

TENANT_DIRECTORY_MERGE_PATHS: tuple[str, ...] = (
    "backup",
    "fascicoli/archivio",
    "fascicoli/documenti",
    "intelligence/downloads",
    "intelligence/models",
    "portale/uploads",
)


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
    JSON       = "JSON"        # JSON su filesystem (default, zero dipendenze)
    SQLITE     = "SQLITE"      # SQLite per studio (studio.db)
    POSTGRESQL = "POSTGRESQL"  # PostgreSQL via SQLAlchemy
    MYSQL      = "MYSQL"       # Compatibilità legacy
    LOCAL      = JSON          # Alias legacy


def normalize_db_mode(value: Any) -> str:
    raw = str(value or "").strip().upper()
    aliases = {
        "": DbMode.SQLITE,
        "LOCAL": DbMode.JSON,
        "FILESYSTEM": DbMode.JSON,
        "JSON": DbMode.JSON,
        "SQLITE": DbMode.SQLITE,
        "SQLITE3": DbMode.SQLITE,
        "POSTGRES": DbMode.POSTGRESQL,
        "POSTGRESQL": DbMode.POSTGRESQL,
        "MYSQL": DbMode.MYSQL,
        "MARIADB": DbMode.MYSQL,
    }
    return aliases.get(raw, DbMode.SQLITE)


SELECTABLE_DB_MODES: tuple[str, ...] = (
    DbMode.JSON,
    DbMode.SQLITE,
    DbMode.POSTGRESQL,
)


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

DB_MODE_INFO = {
    DbMode.JSON: {
        "nome": "JSON locale",
        "icona": "bi-hdd-fill",
        "colore": "secondary",
        "porta": None,
        "desc": "Dati core su filesystem JSON. Ideale per studi piccoli, cache locali e ambienti senza database dedicato.",
        "badge": "Incluso in tutti i piani",
        "piano_min": None,
        "selectable": True,
        "runtime": "json",
    },
    DbMode.SQLITE: {
        "nome": "SQLite per studio",
        "icona": "bi-database-fill",
        "colore": "info",
        "porta": None,
        "desc": "Backend transazionale locale per tenant in studio.db. Consigliato per installazioni single-tenant robuste.",
        "badge": "Consigliato in locale",
        "piano_min": None,
        "selectable": True,
        "runtime": "sqlite",
    },
    DbMode.POSTGRESQL: {
        "nome": "PostgreSQL",
        "icona": "bi-database-fill-gear",
        "colore": "primary",
        "porta": 5432,
        "desc": "PostgreSQL per distribuzione cloud e multi-tenant seria. Scelta raccomandata per ambienti professionali centralizzati.",
        "badge": "Cloud / distribuzione",
        "piano_min": "ENTERPRISE",
        "selectable": True,
        "runtime": "postgresql",
    },
    DbMode.MYSQL: {
        "nome": "MySQL / MariaDB (legacy)",
        "icona": "bi-database-fill",
        "colore": "warning",
        "porta": 3306,
        "desc": "Compatibilità per installazioni pregresse. Non è il backend consigliato per i nuovi studi.",
        "badge": "Compatibilità legacy",
        "piano_min": "PROFESSIONAL",
        "selectable": False,
        "runtime": "mysql",
    },
}


@dataclass
class DatabaseConfig:
    """
    Configurazione del database per un tenant.
    Per modalità LOCAL tutti i campi sono vuoti (non usati).
    """
    mode: str = DbMode.SQLITE

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
        return defaults.get(self.normalized_mode, 0)

    @property
    def normalized_mode(self) -> str:
        return normalize_db_mode(self.mode)

    @property
    def is_json(self) -> bool:
        return self.normalized_mode == DbMode.JSON

    @property
    def is_sqlite(self) -> bool:
        return self.normalized_mode == DbMode.SQLITE

    @property
    def is_external_sql(self) -> bool:
        return self.normalized_mode in (DbMode.POSTGRESQL, DbMode.MYSQL)

    @property
    def runtime_kind(self) -> str:
        return str(DB_MODE_INFO.get(self.normalized_mode, {}).get("runtime", "json"))

    @property
    def effective_runtime_kind(self) -> str:
        """Backend realmente attivo oggi per i moduli core compatibili."""
        if self.is_sqlite:
            return "sqlite"
        return "json"

    @property
    def connection_url(self) -> str:
        if self.is_json or self.is_sqlite:
            return ""

        if self.normalized_mode == DbMode.MYSQL:
            driver = "mysql+pymysql"
            ssl_suffix = "?ssl=true" if self.ssl else ""
            return (
                f"{driver}://{self.utente}:{self.password}"
                f"@{self.host}:{self.porta_effettiva}/{self.db_name}{ssl_suffix}"
            )

        if self.normalized_mode == DbMode.POSTGRESQL:
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
        if self.is_json:
            return "filesystem://json"
        if self.is_sqlite:
            return "sqlite:///studio.db"

        driver = (
            "mysql+pymysql"
            if self.normalized_mode == DbMode.MYSQL
            else "postgresql+psycopg2"
        )
        return f"{driver}://{self.utente}:***@{self.host}:{self.porta_effettiva}/{self.db_name}"

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["mode"] = self.normalized_mode
        return payload

    @staticmethod
    def from_dict(d: dict | str | None) -> "DatabaseConfig":
        if isinstance(d, DatabaseConfig):
            return d
        if d is None:
            d = {}
        elif isinstance(d, str):
            d = {"mode": normalize_db_mode(d)}
        elif not isinstance(d, dict):
            d = {}
        else:
            d = dict(d)
            if not d.get("mode"):
                for legacy_key in ("db_mode", "database_mode", "tipo", "engine"):
                    legacy_mode = d.get(legacy_key)
                    if isinstance(legacy_mode, str):
                        d["mode"] = normalize_db_mode(legacy_mode)
                        break

        d["mode"] = normalize_db_mode(d.get("mode"))
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
    nome_sistema:      str = "IUSENTRA"

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "BrandingStudio":
        return BrandingStudio(**{k: v for k, v in d.items() if k in BrandingStudio.__dataclass_fields__})


@dataclass
class StudioLegale:
    """
    Tenant rappresentante uno studio legale sulla piattaforma IUSENTRA.
    """
    id:               str  = field(default_factory=lambda: str(uuid.uuid4()))
    storage_key:      str  = ""
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
            d["db_config"] = {"mode": normalize_db_mode(legacy_db)}
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
        if not str(d.get("storage_key", "") or "").strip():
            legacy_directory = ""
            try:
                legacy_directory = str((d.get("db_config") or {}).get("directory_dati", "") or "")
            except Exception:
                legacy_directory = ""
            if legacy_directory:
                d["storage_key"] = Path(legacy_directory).name
            else:
                d["storage_key"] = str(d.get("slug", "") or "")
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

    def _tenant_user_directory_path(self) -> Path:
        return self.registry_path.parent / "tenant_user_directory.json"

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

    def _resolve_registry_key(self, slug_or_id: str) -> str:
        slug_norm = self._normalizza_slug(slug_or_id or "")
        studi = self._carica()
        if slug_or_id in studi:
            return str(slug_or_id)
        if slug_norm in studi:
            return slug_norm
        for key, studio in studi.items():
            if str(getattr(studio, "id", "") or "").strip() == str(slug_or_id or "").strip():
                return key
            if self._normalizza_slug(str(getattr(studio, "slug", "") or "")) == slug_norm:
                return key
        return ""

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
        if not studio.storage_key:
            studio.storage_key = slug

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
        self._scrivi_storage_manifest(slug, studio)
        return studio

    def aggiorna(self, slug: str, **kwargs) -> Optional[StudioLegale]:
        studi = self._carica()
        registry_key = self._resolve_registry_key(slug)
        if not registry_key:
            return None
        studio = studi.get(registry_key)
        if not studio:
            return None
        for k, v in kwargs.items():
            if hasattr(studio, k):
                setattr(studio, k, v)
        studi[registry_key] = studio
        self._salva(studi)
        return studio

    def elimina(self, slug: str, elimina_dati: bool = False) -> bool:
        """
        Rimuove il tenant dal registry.
        Se elimina_dati=True cancella anche la directory dati (IRREVERSIBILE).
        """
        studi = self._carica()
        registry_key = self._resolve_registry_key(slug)
        if not registry_key:
            return False
        del studi[registry_key]
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
        studio = self.aggiorna(slug, db_config=config.to_dict())
        if studio:
            self._scrivi_storage_manifest(slug, studio)
        return studio

    def testa_connessione(self, slug: str) -> Dict[str, Any]:
        """
        Testa la connessione al database del tenant.
        Ritorna { ok: bool, messaggio: str, latenza_ms: int }.
        Aggiorna anche db_config.connessione_ok e ultimo_test.
        """
        import time as _t
        studi = self._carica()
        registry_key = self._resolve_registry_key(slug)
        if not registry_key:
            return {"ok": False, "messaggio": "Studio non trovato", "latenza_ms": 0}
        studio = studi.get(registry_key)
        if not studio:
            return {"ok": False, "messaggio": "Studio non trovato", "latenza_ms": 0}

        db = studio.database

        if db.is_json:
            data_dir = self._data_dir(slug)
            ok = data_dir.exists()
            msg = "Directory locale accessibile." if ok else f"Directory non trovata: {data_dir}"
            db.connessione_ok = ok
            db.ultimo_test = datetime.now().isoformat()
            db.errore_connessione = "" if ok else msg
            studio.db_config = db.to_dict()
            studi[registry_key] = studio
            self._salva(studi)
            return {"ok": ok, "messaggio": msg, "latenza_ms": 0}

        if db.is_sqlite:
            studio_db_path = Path(self.percorsi_dati(slug)["STUDIO_DB"])
            ok = studio_db_path.exists()
            msg = "Database SQLite pronto." if ok else f"Database SQLite non trovato: {studio_db_path}"
            db.connessione_ok = ok
            db.ultimo_test = datetime.now().isoformat()
            db.errore_connessione = "" if ok else msg
            studio.db_config = db.to_dict()
            studi[registry_key] = studio
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
            studi[registry_key] = studio
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
        studi[registry_key] = studio
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
        studio = self.get(slug)
        if studio:
            storage_key = str(getattr(studio, "storage_key", "") or "").strip()
            if storage_key:
                candidate = Path(storage_key)
                if candidate.is_absolute():
                    return candidate
                return self.registry_path.parent / "tenants" / storage_key

            try:
                legacy_directory = str((studio.db_config or {}).get("directory_dati", "") or "").strip()
            except Exception:
                legacy_directory = ""
            if legacy_directory:
                return Path(legacy_directory)
        return self.registry_path.parent / "tenants" / slug

    def _legacy_alias_data_dirs(self, slug: str) -> list[Path]:
        studio = self.get(slug)
        if not studio:
            return []
        candidates: list[Path] = []
        canonical = self._data_dir(slug)
        slug_dir = self.registry_path.parent / "tenants" / str(studio.slug or slug)
        for candidate in (slug_dir,):
            if candidate != canonical and candidate.exists():
                candidates.append(candidate)
        return candidates

    def reconcile_storage_aliases(self, slug: str) -> Dict[str, Any]:
        """
        Consolida eventuali directory legacy del tenant nel percorso canonico.

        In alcuni ambienti storici il registry punta ancora a `storage_key` opachi
        mentre una parte dei dati applicativi e' stata bootstrapata nel percorso
        basato su `slug`. Questa routine copia solo i file mancanti e unisce le
        directory documentali, senza sovrascrivere dati gia' presenti nel percorso
        canonico.
        """
        canonical = self._data_dir(slug)
        aliases = self._legacy_alias_data_dirs(slug)
        if not aliases:
            return {"ok": True, "copied_files": {}, "merged_dirs": {}, "canonical": str(canonical)}

        canonical.mkdir(parents=True, exist_ok=True)
        copied_files: Dict[str, str] = {}
        merged_dirs: Dict[str, str] = {}
        for alias in aliases:
            for relative in TENANT_FILE_SEED_PATHS:
                source = alias / relative
                destination = canonical / relative
                if self._path_needs_seed(source, destination):
                    copied_files[f"{alias.name}:{relative}"] = self._copy_seed_path(source, destination)
            for relative in TENANT_DIRECTORY_MERGE_PATHS:
                source_dir = alias / relative
                destination_dir = canonical / relative
                if not source_dir.exists() or not source_dir.is_dir():
                    continue
                if not any(source_dir.iterdir()):
                    continue
                destination_dir.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(source_dir, destination_dir, dirs_exist_ok=True)
                merged_dirs[f"{alias.name}:{relative}"] = str(destination_dir)

        return {
            "ok": True,
            "canonical": str(canonical),
            "copied_files": copied_files,
            "merged_dirs": merged_dirs,
        }

    def data_dir(self, slug: str) -> Path:
        self.reconcile_storage_aliases(slug)
        return self._data_dir(slug)

    @staticmethod
    def _json_has_records(path: Path) -> bool:
        if not path.exists() or not path.is_file():
            return False
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return path.stat().st_size > 2
        if isinstance(payload, dict):
            return len(payload) > 0
        if isinstance(payload, list):
            return len(payload) > 0
        return bool(payload)

    @classmethod
    def _path_has_data(cls, path: Path) -> bool:
        if not path.exists():
            return False
        if path.is_dir():
            return any(path.iterdir())
        if path.suffix.lower() == ".json":
            return cls._json_has_records(path)
        return path.stat().st_size > 0

    @classmethod
    def _path_needs_seed(cls, source: Path, destination: Path) -> bool:
        if not cls._path_has_data(source):
            return False
        if source.resolve() == destination.resolve():
            return False
        return not cls._path_has_data(destination)

    @staticmethod
    def _copy_seed_path(source: Path, destination: Path) -> str:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(source, destination)
        return str(destination)

    @staticmethod
    def _sqlite_table_has_records(db_path: Path, table_name: str) -> bool:
        import sqlite3

        if not db_path.exists():
            return False
        try:
            with sqlite3.connect(db_path) as conn:
                row = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
        except sqlite3.Error:
            return False
        return bool(row and int(row[0] or 0) > 0)

    def _legacy_directory_referenced_slugs(self) -> set[str]:
        directory_path = self.registry_path.parent / "tenant_user_directory.json"
        if not directory_path.exists():
            return set()
        try:
            payload = json.loads(directory_path.read_text(encoding="utf-8"))
        except Exception:
            return set()

        studios = self.lista()
        by_slug = {str(studio.slug or "").strip().lower(): studio for studio in studios}
        by_id = {str(studio.id or "").strip(): studio for studio in studios}
        by_storage_key = {
            str(getattr(studio, "storage_key", "") or "").strip(): studio
            for studio in studios
            if str(getattr(studio, "storage_key", "") or "").strip()
        }

        resolved: set[str] = set()
        for section in ("users", "emails"):
            block = payload.get(section, {})
            if not isinstance(block, dict):
                continue
            for entry in block.values():
                if not isinstance(entry, dict):
                    continue

                slug = str(entry.get("tenant_slug", "") or "").strip().lower()
                if slug and slug in by_slug:
                    resolved.add(slug)
                    continue

                tenant_id = str(entry.get("tenant_id", "") or "").strip()
                if tenant_id and tenant_id in by_id:
                    resolved.add(str(by_id[tenant_id].slug or "").strip().lower())
                    continue

                storage_key = str(entry.get("tenant_storage_key", "") or "").strip()
                if storage_key and storage_key in by_storage_key:
                    resolved.add(str(by_storage_key[storage_key].slug or "").strip().lower())
        return {slug for slug in resolved if slug}

    def resolve_legacy_bootstrap_target_slug(self, legacy_paths: Dict[str, str]) -> str:
        """
        Individua il tenant che deve ereditare i dati root legacy.

        Ordine di priorita':
        1. mapping esplicito in tenant_user_directory.json
        2. fallback single-tenant legacy (un solo studio attivo)
        """
        probe_keys = (
            "CLIENTI_DB",
            "FASCICOLI_DB",
            "AGENDA_DB",
            "SCADENZIARIO_DB",
            "EMAIL_CASELLA_DB",
            "CONFIG_STUDIO_DB",
            "PREVENTIVI_DB",
            "SOGGETTI_DB",
        )
        if not any(
            self._path_has_data(Path(str(legacy_paths.get(key, "") or "").strip()))
            for key in probe_keys
            if str(legacy_paths.get(key, "") or "").strip()
        ):
            return ""

        referenced_slugs = self._legacy_directory_referenced_slugs()
        if len(referenced_slugs) == 1:
            return next(iter(referenced_slugs))

        active_states = {"ATTIVO", "TRIAL"}
        active_slugs = [
            str(studio.slug or "").strip().lower()
            for studio in self.lista()
            if str(getattr(studio, "stato", "") or "").upper() in active_states
        ]
        if len(active_slugs) == 1:
            return active_slugs[0]
        return ""

    def _inizializza_directory(self, slug: str) -> None:
        base = self._data_dir(slug)
        for subdir in [
            "auth", "clienti", "fascicoli", "fascicoli/documenti", "fascicoli/archivio",
            "agenda", "scadenziario", "fatturazione", "messaggi", "backup",
            "notifiche", "pagamenti", "portale", "portale/uploads",
            "privacy", "condivisioni", "template_atti", "wizard_pro",
            "intelligence", "search", "config",
            # directory aggiuntive per moduli preventivi, email e soggetti
            "preventivi", "email", "soggetti",
        ]:
            (base / subdir).mkdir(parents=True, exist_ok=True)

    def bootstrap_legacy_runtime_data(
        self,
        slug: str,
        legacy_paths: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        Importa dati legacy single-tenant nella root del tenant.

        Viene usato come ponte di compatibilità per installazioni storiche dove:
        - auth multi-tenant è già attivo
        - i dati di lavoro reali stanno ancora nella root ./data/
        - esiste un solo studio attivo e deve "ereditare" i dati legacy
        """
        studio = self.get(slug)
        if not studio:
            return {"ok": False, "copied": {}, "sqlite_migrated": False}

        self._inizializza_directory(slug)
        tenant_paths = self.percorsi_dati(slug)
        copied: Dict[str, str] = {}
        sqlite_migrated = False
        sqlite_records: Dict[str, int] = {}

        copy_keys = (
            "CLIENTI_DB",
            "CONDIVISIONI_DB",
            "NOTE_FALDONE_DB",
            "FASCICOLI_DB",
            "FASCICOLI_DOCS",
            "FASCICOLI_ARCH",
            "AGENDA_DB",
            "SCADENZIARIO_DB",
            "MESSAGGI_DB",
            "EMAIL_CASELLA_DB",
            "PRIVACY_DB",
            "PORTALE_DB",
            "FATTURAZIONE_DB",
            "PREVENTIVI_DB",
            "SOGGETTI_DB",
            "SOGGETTI_PARTI_DB",
            "TEMPLATE_ATTI_DB",
            "TEMPLATE_ATTI_PREFS_DB",
            "WIZARD_PRO_DB",
            "CONFIG_STUDIO_DB",
        )

        for key in copy_keys:
            source_raw = str(legacy_paths.get(key, "") or "").strip()
            destination_raw = str(tenant_paths.get(key, "") or "").strip()
            if not source_raw or not destination_raw:
                continue
            source = Path(source_raw)
            destination = Path(destination_raw)
            if self._path_needs_seed(source, destination):
                copied[key] = self._copy_seed_path(source, destination)

        if studio.database.is_sqlite:
            studio_db_path = Path(tenant_paths["STUDIO_DB"])
            sqlite_empty = not any(
                self._sqlite_table_has_records(studio_db_path, table)
                for table in ("clienti", "fascicoli", "appuntamenti", "scadenze", "messaggi")
            )
            if sqlite_empty:
                from pct.database import GestioneDatabase

                migrate_sources = {
                    "clienti": legacy_paths.get("CLIENTI_DB", ""),
                    "fascicoli": legacy_paths.get("FASCICOLI_DB", ""),
                    "appuntamenti": legacy_paths.get("AGENDA_DB", ""),
                    "scadenze": legacy_paths.get("SCADENZIARIO_DB", ""),
                    "messaggi": legacy_paths.get("MESSAGGI_DB", ""),
                    "privacy": legacy_paths.get("PRIVACY_DB", ""),
                    "search_index": legacy_paths.get("SEARCH_INDEX", ""),
                }
                if any(
                    self._path_has_data(Path(str(path)))
                    for path in migrate_sources.values()
                    if str(path).strip()
                ):
                    migratore = GestioneDatabase(migrate_sources)
                    risultato = migratore.migra_verso_sqlite(str(studio_db_path))
                    sqlite_records = dict(risultato.record_migrati)
                    sqlite_migrated = bool(
                        risultato.riuscita and any(int(v or 0) > 0 for v in sqlite_records.values())
                    )

        if copied or sqlite_migrated:
            self._scrivi_storage_manifest(slug, studio)

        return {
            "ok": True,
            "copied": copied,
            "sqlite_migrated": sqlite_migrated,
            "sqlite_records": sqlite_records,
        }

    def percorsi_dati(self, slug: str) -> Dict[str, str]:
        """Restituisce il dizionario di configurazione data paths per questo tenant."""
        self.reconcile_storage_aliases(slug)
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
            "GIURISPRUDENZA_DB": f"{base}/intelligence/giurisprudenza.json",
            "WORKSPACE_INTELLIGENCE_DB": f"{base}/intelligence/workspace_intelligence.json",
            "LOCAL_AI_DB": f"{base}/intelligence/local_ai.db",
            "LOCAL_AI_MODELS_DIR": f"{base}/intelligence/models",
            "VALIDATION_RUNS_DB": f"{base}/intelligence/validation_runs.json",
            "REDACTION_ASSISTANT_DB": f"{base}/intelligence/assistente_redazionale.json",
            "CONFIG_STUDIO_DB": f"{base}/config/studio.json",
            "STORAGE_CONFIG": f"{base}/config/storage.json",
            "STUDIO_DB": f"{base}/studio.db",
            # Percorsi aggiuntivi necessari per isolamento tenant completo
            "NOTE_FALDONE_DB":   f"{base}/clienti/note_faldone.json",
            "EMAIL_CASELLA_DB":  f"{base}/email/casella.json",
            "PREVENTIVI_DB":     f"{base}/preventivi/preventivi.json",
            "SOGGETTI_DB":       f"{base}/soggetti/anagrafica.json",
            "SOGGETTI_PARTI_DB": f"{base}/soggetti/parti.json",
        }

    def build_user_directory(self, *, secret_key: str = "") -> Dict[str, Any]:
        from pct.auth import GestioneUtenti
        from pct.storage import StudioDB
        import sqlite3

        users: Dict[str, Dict[str, Any]] = {}
        emails: Dict[str, Dict[str, Any]] = {}
        conflicts: list[dict[str, str]] = []

        for studio in self.lista():
            slug = str(studio.slug or "").strip().lower()
            if not slug:
                continue
            self.reconcile_storage_aliases(slug)
            paths = self.percorsi_dati(slug)
            studio_db = None
            if studio.database.is_sqlite:
                try:
                    studio_db = StudioDB.get(paths["STUDIO_DB"])
                except (OSError, sqlite3.Error):
                    studio_db = None
            manager = GestioneUtenti(
                db_path=paths["AUTH_DB"],
                audit_path=paths["AUDIT_DB"],
                secret_key=secret_key,
                crea_admin_se_vuoto=False,
                studio_db=studio_db,
            )
            for user in manager.lista():
                tenant_slug = str(user.tenant_slug or slug).strip().lower()
                entry = {
                    "user_id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "tenant_id": studio.id,
                    "tenant_slug": tenant_slug,
                    "tenant_storage_key": str(getattr(studio, "storage_key", "") or "").strip(),
                    "studio_nome": studio.nome,
                    "auth_db": paths["AUTH_DB"],
                    "audit_db": paths["AUDIT_DB"],
                    "ruolo": str(getattr(user.ruolo, "value", user.ruolo)),
                    "attivo": bool(user.attivo),
                }
                username_key = str(user.username or "").strip().lower()
                if username_key:
                    previous = users.get(username_key)
                    if previous and previous.get("tenant_slug") != tenant_slug:
                        conflicts.append(
                            {
                                "kind": "username",
                                "key": username_key,
                                "tenant_slug": tenant_slug,
                                "existing_tenant_slug": str(previous.get("tenant_slug", "")),
                            }
                        )
                    else:
                        users[username_key] = entry

                email_key = str(user.email or "").strip().lower()
                if email_key:
                    previous = emails.get(email_key)
                    if previous and previous.get("tenant_slug") != tenant_slug:
                        conflicts.append(
                            {
                                "kind": "email",
                                "key": email_key,
                                "tenant_slug": tenant_slug,
                                "existing_tenant_slug": str(previous.get("tenant_slug", "")),
                            }
                        )
                    else:
                        emails[email_key] = entry

        return {
            "generated_at": datetime.now().isoformat(),
            "users": users,
            "emails": emails,
            "conflicts": conflicts,
        }

    def sync_user_directory(self, *, secret_key: str = "") -> Dict[str, Any]:
        payload = self.build_user_directory(secret_key=secret_key)
        path = self._tenant_user_directory_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return payload

    def storage_manifest(self, slug: str) -> Dict[str, Any]:
        studio = self.get(slug)
        if not studio:
            return {}
        db = studio.database
        paths = self.percorsi_dati(slug)
        info = DB_MODE_INFO.get(db.normalized_mode, {})
        return {
            "slug": slug,
            "selected_mode": db.normalized_mode,
            "runtime_kind": db.runtime_kind,
            "effective_runtime_kind": db.effective_runtime_kind,
            "external_sql_configured": db.is_external_sql,
            "activation_state": (
                "active"
                if not db.is_external_sql
                else "external-tested"
                if db.connessione_ok
                else "external-pending"
            ),
            "nome": info.get("nome", db.normalized_mode),
            "data_dir": str(self._data_dir(slug)),
            "json_root": str(self._data_dir(slug)),
            "studio_db_path": paths["STUDIO_DB"],
            "connection_url_safe": db.connection_url_safe,
            "connessione_ok": bool(db.connessione_ok),
            "ultimo_test": db.ultimo_test,
            "errore_connessione": db.errore_connessione,
        }

    def _scrivi_storage_manifest(self, slug: str, studio: Optional[StudioLegale] = None) -> None:
        studio = studio or self.get(slug)
        if not studio:
            return
        manifest_path = Path(self.percorsi_dati(slug)["STORAGE_CONFIG"])
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(self.storage_manifest(slug), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def provision_storage_backend(self, slug: str, *, migrate_existing: bool = False) -> Dict[str, Any]:
        studio = self.get(slug)
        if not studio:
            raise ValueError("Studio non trovato")

        self._inizializza_directory(slug)
        paths = self.percorsi_dati(slug)
        db = studio.database
        payload: Dict[str, Any] = {
            "ok": True,
            "mode": db.normalized_mode,
            "migrated": False,
            "studio_db_path": paths["STUDIO_DB"],
        }

        if db.is_sqlite:
            if migrate_existing:
                from pct.database import GestioneDatabase

                migratore = GestioneDatabase(
                    {
                        "clienti": paths["CLIENTI_DB"],
                        "fascicoli": paths["FASCICOLI_DB"],
                        "appuntamenti": paths["AGENDA_DB"],
                        "scadenze": paths["SCADENZIARIO_DB"],
                        "messaggi": paths["MESSAGGI_DB"],
                        "utenti": paths["AUTH_DB"],
                        "audit": paths["AUDIT_DB"],
                        "privacy": paths["PRIVACY_DB"],
                        "notifiche": paths["NOTIFICHE_LOG"],
                        "backup": str(Path(paths["BACKUP_DIR"]) / "registro.json"),
                        "search_index": paths["SEARCH_INDEX"],
                    }
                )
                risultato = migratore.migra_verso_sqlite(paths["STUDIO_DB"])
                payload["migrated"] = bool(risultato.riuscita)
                payload["migration_errors"] = list(risultato.errori)
                payload["migration_warnings"] = list(risultato.avvisi)
                payload["migration_records"] = dict(risultato.record_migrati)

            from pct.storage import StudioDB

            studio_db = StudioDB.get(paths["STUDIO_DB"])
            payload["sqlite_ready"] = bool(studio_db.db_path.exists())

        self._scrivi_storage_manifest(slug, studio)
        return payload

    # ---- Helper

    @staticmethod
    def _normalizza_slug(slug: str) -> str:
        return slug.lower().strip().replace(" ", "-")

    @staticmethod
    def _slug_valido(slug: str) -> bool:
        return bool(re.match(r'^[a-z0-9][a-z0-9\-]{1,48}[a-z0-9]$', slug))

