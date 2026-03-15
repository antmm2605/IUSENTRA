"""
Sistema di autenticazione e gestione utenti per lo studio legale.

Funzionalità:
  - Ruoli: AMMINISTRATORE, AVVOCATO, SEGRETERIA
  - Hash password bcrypt (werkzeug)
  - Audit log completo di ogni azione (chi, cosa, quando, IP)
  - Gestione sessioni via Flask-Login
  - Token password reset (HMAC-SHA256)
"""

import json
import uuid
import hmac
import hashlib
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field, asdict
from enum import Enum
from functools import wraps


# ------------------------------------------------------------------ Enums

class RuoloUtente(str, Enum):
    AMMINISTRATORE = "AMMINISTRATORE"
    AVVOCATO       = "AVVOCATO"
    SEGRETERIA     = "SEGRETERIA"


# Permessi per ruolo
PERMESSI: Dict[RuoloUtente, List[str]] = {
    RuoloUtente.AMMINISTRATORE: [
        "utenti.leggi", "utenti.scrivi", "utenti.elimina",
        "fascicoli.leggi", "fascicoli.scrivi", "fascicoli.elimina", "fascicoli.archivia",
        "clienti.leggi", "clienti.scrivi", "clienti.elimina",
        "agenda.leggi", "agenda.scrivi", "agenda.elimina",
        "messaggi.leggi", "messaggi.scrivi",
        "backup.leggi", "backup.esegui",
        "scadenziario.leggi", "scadenziario.scrivi",
        "audit.leggi",
    ],
    RuoloUtente.AVVOCATO: [
        "fascicoli.leggi", "fascicoli.scrivi", "fascicoli.archivia",
        "clienti.leggi", "clienti.scrivi",
        "agenda.leggi", "agenda.scrivi",
        "messaggi.leggi", "messaggi.scrivi",
        "scadenziario.leggi", "scadenziario.scrivi",
        "backup.leggi",
    ],
    RuoloUtente.SEGRETERIA: [
        "fascicoli.leggi",
        "clienti.leggi", "clienti.scrivi",
        "agenda.leggi", "agenda.scrivi",
        "messaggi.leggi",
        "scadenziario.leggi",
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

    # Flask-Login interface
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

    def ha_permesso(self, permesso: str) -> bool:
        return permesso in PERMESSI.get(self.ruolo, [])

    def ha_ruolo(self, *ruoli: RuoloUtente) -> bool:
        return self.ruolo in ruoli

    def to_dict(self) -> Dict:
        d = asdict(self)
        d["ruolo"] = self.ruolo.value
        return d

    @staticmethod
    def from_dict(d: Dict) -> "Utente":
        d = dict(d)
        d["ruolo"] = RuoloUtente(d.get("ruolo", "SEGRETERIA"))
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
    Gestisce utenti, autenticazione e audit log.

    Struttura file:
        <db_path>           ← JSON utenti
        <audit_path>        ← JSON audit log
    """

    def __init__(
        self,
        db_path: str = "./auth/utenti.json",
        audit_path: str = "./auth/audit.json",
        secret_key: str = "",
    ):
        self.db_path = Path(db_path)
        self.audit_path = Path(audit_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._secret = secret_key or secrets.token_hex(32)
        self._utenti: Dict[str, Utente] = {}
        self._audit: List[EventoAudit] = []
        self._carica()
        # Crea admin di default se DB vuoto
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
        self.audit_path.write_text(
            json.dumps([e.to_dict() for e in self._audit[-5000:]],
                       indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _crea_admin_default(self):
        """Crea l'utente amministratore di default al primo avvio."""
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
        """Hash password con werkzeug (bcrypt-like PBKDF2)."""
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
        """Verifica credenziali. Restituisce l'utente o None."""
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

    # ---- reset password

    def genera_reset_token(self, email: str) -> Optional[str]:
        """Genera un token di reset password valido 24h."""
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
        """Reimposta la password usando il token. Restituisce True se ok."""
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

    def statistiche(self) -> Dict[str, Any]:
        return {
            "totale_utenti": len(self._utenti),
            "attivi": sum(1 for u in self._utenti.values() if u.attivo),
            "per_ruolo": {
                r.value: sum(1 for u in self._utenti.values() if u.ruolo == r)
                for r in RuoloUtente
            },
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
    """Decorator che richiede autenticazione (usato fuori Flask-Login)."""
    @wraps(f)
    def decorated(*args, **kwargs):
        from flask import session, redirect, url_for, request
        if "user_id" not in session:
            return redirect(url_for("login", next=request.url))
        return f(*args, **kwargs)
    return decorated


def permesso_richiesto(permesso: str):
    """Decorator che verifica un permesso specifico."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            from flask import session, abort, g
            utente = getattr(g, "utente_corrente", None)
            if not utente or not utente.ha_permesso(permesso):
                abort(403)
            return f(*args, **kwargs)
        return decorated
    return decorator


def ruolo_richiesto(*ruoli: RuoloUtente):
    """Decorator che verifica un ruolo specifico."""
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
