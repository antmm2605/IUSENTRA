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

    # ---- serializzazione

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    @staticmethod
    def from_dict(d: dict) -> "StudioLegale":
        d = dict(d)
        d.setdefault("moduli_override", [])
        d.setdefault("branding", {})
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
        return self._carica().get(slug)

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
            "privacy", "condivisioni", "template_atti", "search",
        ]:
            (base / subdir).mkdir(parents=True, exist_ok=True)

    def percorsi_dati(self, slug: str) -> Dict[str, str]:
        """Restituisce il dizionario di configurazione data paths per questo tenant."""
        base = str(self._data_dir(slug))
        return {
            "AGENDA_DB":         f"{base}/agenda/appuntamenti.json",
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
        }

    # ---- Helper

    @staticmethod
    def _normalizza_slug(slug: str) -> str:
        return slug.lower().strip().replace(" ", "-")

    @staticmethod
    def _slug_valido(slug: str) -> bool:
        return bool(re.match(r'^[a-z0-9][a-z0-9\-]{1,48}[a-z0-9]$', slug))
