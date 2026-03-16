"""
Sistema di autenticazione, profili e gestione permessi per lo studio legale.

Funzionalità:
  - Ruoli: AMMINISTRATORE, AVVOCATO, COLLABORATORE, PRATICANTE,
           SEGRETERIA, CONTABILE
  - Permessi granulari per categoria (fascicoli, clienti, agenda, …)
  - Override per-utente: permessi_extra e permessi_negati
  - Hash password PBKDF2 (werkzeug)
  - Audit log completo (chi, cosa, quando, IP, esito)
  - Token password reset (HMAC-SHA256)
"""

import json
import uuid
import hmac
import hashlib
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from functools import wraps


# ------------------------------------------------------------------ Ruoli

class RuoloUtente(str, Enum):
    AMMINISTRATORE = "AMMINISTRATORE"
    AVVOCATO       = "AVVOCATO"
    COLLABORATORE  = "COLLABORATORE"
    PRATICANTE     = "PRATICANTE"
    SEGRETERIA     = "SEGRETERIA"
    CONTABILE      = "CONTABILE"


# ------------------------------------------------------------------ Descrizioni ruoli

DESCRIZIONI_RUOLI: Dict[RuoloUtente, Dict[str, str]] = {
    RuoloUtente.AMMINISTRATORE: {
        "descrizione": "Accesso completo a tutti i moduli e alla gestione utenti.",
        "colore": "danger",
        "icona": "bi-shield-fill",
    },
    RuoloUtente.AVVOCATO: {
        "descrizione": "Gestione completa di fascicoli, clienti, agenda e scadenziario.",
        "colore": "primary",
        "icona": "bi-briefcase-fill",
    },
    RuoloUtente.COLLABORATORE: {
        "descrizione": "Avvocato collaboratore — operatività completa senza poter eliminare fascicoli/clienti.",
        "colore": "info",
        "icona": "bi-person-workspace",
    },
    RuoloUtente.PRATICANTE: {
        "descrizione": "Accesso in sola lettura con possibilità di gestire l'agenda.",
        "colore": "success",
        "icona": "bi-mortarboard-fill",
    },
    RuoloUtente.SEGRETERIA: {
        "descrizione": "Gestione agenda, anagrafica clienti e messaggistica. Fascicoli in sola lettura.",
        "colore": "warning",
        "icona": "bi-telephone-fill",
    },
    RuoloUtente.CONTABILE: {
        "descrizione": "Visualizzazione fascicoli e scadenziario per attività contabili/fatturazione.",
        "colore": "secondary",
        "icona": "bi-calculator-fill",
    },
}


# ------------------------------------------------------------------ Permessi

# Tutti i permessi disponibili nel sistema, raggruppati per categoria.
# Ogni voce: (categoria, chiave_permesso, etichetta_breve)
TUTTI_PERMESSI: List[Tuple[str, str, str]] = [
    ("Fascicoli",    "fascicoli.leggi",      "Visualizza"),
    ("Fascicoli",    "fascicoli.scrivi",     "Crea / Modifica"),
    ("Fascicoli",    "fascicoli.archivia",   "Archivia"),
    ("Fascicoli",    "fascicoli.elimina",    "Elimina"),
    ("Clienti",      "clienti.leggi",        "Visualizza"),
    ("Clienti",      "clienti.scrivi",       "Crea / Modifica"),
    ("Clienti",      "clienti.elimina",      "Elimina"),
    ("Agenda",       "agenda.leggi",         "Visualizza"),
    ("Agenda",       "agenda.scrivi",        "Crea / Modifica"),
    ("Agenda",       "agenda.elimina",       "Elimina"),
    ("Messaggi",     "messaggi.leggi",       "Visualizza"),
    ("Messaggi",     "messaggi.scrivi",      "Invia"),
    ("Scadenziario", "scadenziario.leggi",   "Visualizza"),
    ("Scadenziario", "scadenziario.scrivi",  "Crea / Modifica"),
    ("Backup",       "backup.leggi",         "Visualizza"),
    ("Backup",       "backup.esegui",        "Esegui"),
    ("Utenti",       "utenti.leggi",         "Visualizza"),
    ("Utenti",       "utenti.scrivi",        "Crea / Modifica"),
    ("Utenti",       "utenti.elimina",       "Elimina"),
    ("Audit",        "audit.leggi",          "Visualizza log"),
]

# Set di permessi di default per ogni ruolo
PERMESSI: Dict[RuoloUtente, List[str]] = {
    RuoloUtente.AMMINISTRATORE: [p for _, p, _ in TUTTI_PERMESSI],  # tutti

    RuoloUtente.AVVOCATO: [
        "fascicoli.leggi", "fascicoli.scrivi", "fascicoli.archivia",
        "clienti.leggi", "clienti.scrivi",
        "agenda.leggi", "agenda.scrivi", "agenda.elimina",
        "messaggi.leggi", "messaggi.scrivi",
        "scadenziario.leggi", "scadenziario.scrivi",
        "backup.leggi",
    ],

    RuoloUtente.COLLABORATORE: [
        "fascicoli.leggi", "fascicoli.scrivi",
        "clienti.leggi", "clienti.scrivi",
        "agenda.leggi", "agenda.scrivi",
        "messaggi.leggi", "messaggi.scrivi",
        "scadenziario.leggi", "scadenziario.scrivi",
    ],

    RuoloUtente.PRATICANTE: [
        "fascicoli.leggi",
        "clienti.leggi",
        "agenda.leggi", "agenda.scrivi",
        "messaggi.leggi",
        "scadenziario.leggi",
    ],

    RuoloUtente.SEGRETERIA: [
        "fascicoli.leggi",
        "clienti.leggi", "clienti.scrivi",
        "agenda.leggi", "agenda.scrivi",
        "messaggi.leggi", "messaggi.scrivi",
        "scadenziario.leggi",
    ],

    RuoloUtente.CONTABILE: [
        "fascicoli.leggi",
        "clienti.leggi",
        "scadenziario.leggi",
        "backup.leggi",
    ],
}


# ------------------------------------------------------------------ Utente

@dataclass
class Utente:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    username: str = ""
    email: str = ""
    nome_completo: str = ""
    ruolo: RuoloUtente = RuoloUtente.SEGRETERIA
    password_hash: str = ""
    attivo: bool = True
    creato_il: str = field(default_factory=lambda: datetime.now().isoformat())
    ultimo_accesso: str = ""
    reset_token: str = ""
    reset_token_scade: str = ""
    # Override per-utente
    permessi_extra: List[str] = field(default_factory=list)   # aggiuntivi rispetto al ruolo
    permessi_negati: List[str] = field(default_factory=list)  # rimossi rispetto al ruolo

    # ---- Flask-Login interface
    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def is_active(self) -> bool:
        return self.attivo

    @property
    def is_anonymous(self) -> bool:
        return False

    def get_id(self) -> str:
        return self.id

    # ---- permessi

    def ha_permesso(self, permesso: str) -> bool:
        """Verifica un permesso applicando gli override per-utente."""
        if permesso in self.permessi_negati:
            return False
        if permesso in self.permessi_extra:
            return True
        return permesso in PERMESSI.get(self.ruolo, [])

    def ha_ruolo(self, *ruoli: RuoloUtente) -> bool:
        return self.ruolo in ruoli

    @property
    def permessi_effettivi(self) -> List[str]:
        """Restituisce la lista completa di permessi effettivi dell'utente."""
        base = set(PERMESSI.get(self.ruolo, []))
        base.update(self.permessi_extra)
        base.difference_update(self.permessi_negati)
        return sorted(base)

    @property
    def ha_override(self) -> bool:
        """True se l'utente ha permessi personalizzati rispetto al suo ruolo."""
        return bool(self.permessi_extra or self.permessi_negati)

    @property
    def descrizione_ruolo(self) -> str:
        return DESCRIZIONI_RUOLI.get(self.ruolo, {}).get("descrizione", "")

    @property
    def colore_ruolo(self) -> str:
        return DESCRIZIONI_RUOLI.get(self.ruolo, {}).get("colore", "secondary")

    @property
    def icona_ruolo(self) -> str:
        return DESCRIZIONI_RUOLI.get(self.ruolo, {}).get("icona", "bi-person")

    # ---- serializzazione

    def to_dict(self) -> Dict:
        d = asdict(self)
        d["ruolo"] = self.ruolo.value
        return d

    @staticmethod
    def from_dict(d: Dict) -> "Utente":
        d = dict(d)
        d["ruolo"] = RuoloUtente(d.get("ruolo", "SEGRETERIA"))
        # Compatibilità backward: campi aggiunti dopo la versione iniziale
        d.setdefault("permessi_extra", [])
        d.setdefault("permessi_negati", [])
        return Utente(**d)


# ------------------------------------------------------------------ Audit log

@dataclass
class EventoAudit:
    """Singolo evento di audit."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    id_utente: str = ""
    username: str = ""
    azione: str = ""        # es. "fascicoli.crea", "clienti.elimina"
    risorsa_tipo: str = ""  # es. "fascicolo", "cliente"
    risorsa_id: str = ""
    dettagli: str = ""
    ip: str = ""
    esito: str = "OK"       # OK | ERRORE | NEGATO

    def to_dict(self) -> Dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: Dict) -> "EventoAudit":
        return EventoAudit(**d)


# ------------------------------------------------------------------ Gestione utenti

class GestioneUtenti:
    """
    Gestisce utenti, profili, permessi e audit log.

    Struttura file:
        <db_path>    ← JSON utenti
        <audit_path> ← JSON audit log
    """

    def __init__(
        self,
        db_path: str = "./auth/utenti.json",
        audit_path: str = "./auth/audit.json",
        secret_key: str = "",
        retention_days: int = 730,
    ):
        self.db_path = Path(db_path)
        self.audit_path = Path(audit_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._secret = secret_key or secrets.token_hex(32)
        self._retention_days = retention_days
        self._utenti: Dict[str, Utente] = {}
        self._audit: List[EventoAudit] = []
        self._carica()
        if not self._utenti:
            self._crea_admin_default()

    # ---- persistenza

    def _carica(self):
        if self.db_path.exists():
            try:
                raw = json.loads(self.db_path.read_text("utf-8"))
                self._utenti = {k: Utente.from_dict(v) for k, v in raw.items()}
            except Exception:
                self._utenti = {}
        if self.audit_path.exists():
            try:
                raw = json.loads(self.audit_path.read_text("utf-8"))
                self._audit = [EventoAudit.from_dict(e) for e in raw]
            except Exception:
                self._audit = []

    def _salva_utenti(self):
        self.db_path.write_text(
            json.dumps({k: v.to_dict() for k, v in self._utenti.items()},
                       indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _salva_audit(self):
        cutoff = (datetime.now() - timedelta(days=self._retention_days)).isoformat()
        recenti = [e for e in self._audit if e.timestamp >= cutoff]
        recenti = recenti[-10000:]  # hard cap di sicurezza
        self._audit = recenti
        self.audit_path.write_text(
            json.dumps([e.to_dict() for e in recenti], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def esporta_audit_csv(
        self,
        id_utente: str = "",
        azione: str = "",
        da: Optional[str] = None,
        a: Optional[str] = None,
    ) -> str:
        """Esporta l'audit log come stringa CSV (UTF-8 con BOM per Excel)."""
        import csv as _csv
        import io as _io
        eventi = self.audit_log(id_utente=id_utente, azione=azione, da=da, a=a, limit=10000)
        out = _io.StringIO()
        out.write("\ufeff")  # BOM per compatibilità Excel
        w = _csv.DictWriter(
            out,
            fieldnames=["timestamp", "username", "azione", "risorsa_tipo",
                        "risorsa_id", "dettagli", "ip", "esito"],
        )
        w.writeheader()
        for e in eventi:
            w.writerow({
                "timestamp": e.timestamp,
                "username": e.username,
                "azione": e.azione,
                "risorsa_tipo": e.risorsa_tipo,
                "risorsa_id": e.risorsa_id,
                "dettagli": e.dettagli,
                "ip": e.ip,
                "esito": e.esito,
            })
        return out.getvalue()

    def _crea_admin_default(self):
        admin = Utente(
            username="admin",
            email="admin@studio.local",
            nome_completo="Amministratore",
            ruolo=RuoloUtente.AMMINISTRATORE,
            password_hash=self._hash_password("admin"),
        )
        self._utenti[admin.id] = admin
        self._salva_utenti()

    # ---- password

    @staticmethod
    def _hash_password(password: str) -> str:
        from werkzeug.security import generate_password_hash
        return generate_password_hash(password)

    @staticmethod
    def _verifica_password(password: str, hash_: str) -> bool:
        from werkzeug.security import check_password_hash
        return check_password_hash(hash_, password)

    # ---- CRUD utenti

    def crea(
        self,
        username: str,
        password: str,
        ruolo: RuoloUtente,
        email: str = "",
        nome_completo: str = "",
        permessi_extra: Optional[List[str]] = None,
        permessi_negati: Optional[List[str]] = None,
    ) -> Utente:
        username = username.strip().lower()
        if not username:
            raise ValueError("Username obbligatorio")
        if len(password) < 8:
            raise ValueError("La password deve avere almeno 8 caratteri")
        if any(u.username == username for u in self._utenti.values()):
            raise ValueError(f"Username '{username}' già in uso")
        utente = Utente(
            username=username,
            email=email.strip(),
            nome_completo=nome_completo.strip(),
            ruolo=ruolo,
            password_hash=self._hash_password(password),
            permessi_extra=permessi_extra or [],
            permessi_negati=permessi_negati or [],
        )
        self._utenti[utente.id] = utente
        self._salva_utenti()
        return utente

    def aggiorna(self, id_utente: str, **kwargs) -> Utente:
        u = self._get_or_raise(id_utente)
        campi_consentiti = {"email", "nome_completo", "ruolo", "attivo"}
        for k, v in kwargs.items():
            if k not in campi_consentiti:
                raise ValueError(f"Campo non modificabile: {k}")
            if k == "ruolo":
                v = RuoloUtente(v)
            setattr(u, k, v)
        self._salva_utenti()
        return u

    def aggiorna_permessi(
        self,
        id_utente: str,
        permessi_extra: List[str],
        permessi_negati: List[str],
    ) -> Utente:
        """Aggiorna gli override di permesso per un utente specifico."""
        u = self._get_or_raise(id_utente)
        # Validazione: solo permessi esistenti nel sistema
        chiavi_valide = {p for _, p, _ in TUTTI_PERMESSI}
        for p in permessi_extra + permessi_negati:
            if p not in chiavi_valide:
                raise ValueError(f"Permesso non riconosciuto: {p!r}")
        # Un permesso non può essere sia extra che negato
        conflitti = set(permessi_extra) & set(permessi_negati)
        if conflitti:
            raise ValueError(f"Permessi in conflitto: {conflitti}")
        u.permessi_extra = list(set(permessi_extra))
        u.permessi_negati = list(set(permessi_negati))
        self._salva_utenti()
        return u

    def cambia_password(self, id_utente: str, nuova_password: str) -> Utente:
        if len(nuova_password) < 8:
            raise ValueError("La password deve avere almeno 8 caratteri")
        u = self._get_or_raise(id_utente)
        u.password_hash = self._hash_password(nuova_password)
        self._salva_utenti()
        return u

    def elimina(self, id_utente: str):
        u = self._get_or_raise(id_utente)
        if u.ruolo == RuoloUtente.AMMINISTRATORE:
            admin_count = sum(
                1 for x in self._utenti.values()
                if x.ruolo == RuoloUtente.AMMINISTRATORE and x.attivo
            )
            if admin_count <= 1:
                raise ValueError("Impossibile eliminare l'unico amministratore")
        del self._utenti[id_utente]
        self._salva_utenti()

    # ---- autenticazione

    def autentica(self, username: str, password: str) -> Optional[Utente]:
        username = username.strip().lower()
        for u in self._utenti.values():
            if u.username == username and u.attivo:
                if self._verifica_password(password, u.password_hash):
                    u.ultimo_accesso = datetime.now().isoformat()
                    self._salva_utenti()
                    return u
        return None

    def get(self, id_utente: str) -> Optional[Utente]:
        return self._utenti.get(id_utente)

    def get_by_username(self, username: str) -> Optional[Utente]:
        username = username.strip().lower()
        return next((u for u in self._utenti.values() if u.username == username), None)

    def tutti(self, solo_attivi: bool = False) -> List[Utente]:
        result = list(self._utenti.values())
        if solo_attivi:
            result = [u for u in result if u.attivo]
        return sorted(result, key=lambda u: u.username)

    def per_ruolo(self, ruolo: RuoloUtente) -> List[Utente]:
        return [u for u in self._utenti.values() if u.ruolo == ruolo]

    # ---- reset password

    def genera_reset_token(self, email: str) -> Optional[str]:
        u = next((u for u in self._utenti.values() if u.email == email and u.attivo), None)
        if not u:
            return None
        token = secrets.token_urlsafe(32)
        u.reset_token = hmac.new(
            self._secret.encode(), token.encode(), hashlib.sha256
        ).hexdigest()
        u.reset_token_scade = (datetime.now() + timedelta(hours=24)).isoformat()
        self._salva_utenti()
        return token

    def reset_password_con_token(self, token: str, nuova_password: str) -> bool:
        if len(nuova_password) < 8:
            raise ValueError("La password deve avere almeno 8 caratteri")
        token_hash = hmac.new(
            self._secret.encode(), token.encode(), hashlib.sha256
        ).hexdigest()
        for u in self._utenti.values():
            if u.reset_token == token_hash:
                if datetime.fromisoformat(u.reset_token_scade) > datetime.now():
                    u.password_hash = self._hash_password(nuova_password)
                    u.reset_token = ""
                    u.reset_token_scade = ""
                    self._salva_utenti()
                    return True
        return False

    # ---- audit log

    def registra_evento(
        self,
        azione: str,
        id_utente: str = "",
        username: str = "",
        risorsa_tipo: str = "",
        risorsa_id: str = "",
        dettagli: str = "",
        ip: str = "",
        esito: str = "OK",
    ) -> EventoAudit:
        evento = EventoAudit(
            id_utente=id_utente,
            username=username,
            azione=azione,
            risorsa_tipo=risorsa_tipo,
            risorsa_id=risorsa_id,
            dettagli=dettagli,
            ip=ip,
            esito=esito,
        )
        self._audit.append(evento)
        self._salva_audit()
        return evento

    def audit_log(
        self,
        id_utente: str = "",
        azione: str = "",
        da: Optional[str] = None,
        a: Optional[str] = None,
        limit: int = 100,
    ) -> List[EventoAudit]:
        result = list(self._audit)
        if id_utente:
            result = [e for e in result if e.id_utente == id_utente]
        if azione:
            result = [e for e in result if azione in e.azione]
        if da:
            result = [e for e in result if e.timestamp >= da]
        if a:
            result = [e for e in result if e.timestamp <= a]
        return list(reversed(result))[:limit]

    # ---- statistiche

    def statistiche(self) -> Dict[str, Any]:
        return {
            "totale_utenti": len(self._utenti),
            "attivi": sum(1 for u in self._utenti.values() if u.attivo),
            "per_ruolo": {
                r.value: sum(1 for u in self._utenti.values() if u.ruolo == r)
                for r in RuoloUtente
            },
            "con_override": sum(1 for u in self._utenti.values() if u.ha_override),
            "totale_eventi_audit": len(self._audit),
        }

    # ---- helper

    def _get_or_raise(self, id_utente: str) -> Utente:
        u = self._utenti.get(id_utente)
        if not u:
            raise ValueError(f"Utente {id_utente!r} non trovato")
        return u


# ------------------------------------------------------------------ Decoratori Flask

def login_required_custom(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        from flask import session, redirect, url_for, request
        if "user_id" not in session:
            return redirect(url_for("login", next=request.url))
        return f(*args, **kwargs)
    return decorated


def permesso_richiesto(permesso: str):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            from flask import g, abort
            utente = getattr(g, "utente_corrente", None)
            if not utente or not utente.ha_permesso(permesso):
                abort(403)
            return f(*args, **kwargs)
        return decorated
    return decorator


def ruolo_richiesto(*ruoli: RuoloUtente):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            from flask import g, abort
            utente = getattr(g, "utente_corrente", None)
            if not utente or not utente.ha_ruolo(*ruoli):
                abort(403)
            return f(*args, **kwargs)
        return decorated
    return decorator
