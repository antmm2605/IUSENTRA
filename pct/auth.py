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
import logging
import os
import secrets
import struct
import time as _time
import base64 as _base64
from urllib.parse import quote as _quote
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from functools import wraps


logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ TOTP (RFC 6238) — implementazione nativa

def _hotp(key_bytes: bytes, counter: int) -> int:
    """HMAC-based OTP (RFC 4226)."""
    msg = struct.pack(">Q", counter)
    h = hmac.new(key_bytes, msg, hashlib.sha1).digest()
    offset = h[-1] & 0x0F
    code = struct.unpack(">I", h[offset:offset + 4])[0] & 0x7FFFFFFF
    return code % 1_000_000


def genera_totp_secret() -> str:
    """Genera un segreto TOTP casuale (160 bit, codifica base32)."""
    return _base64.b32encode(secrets.token_bytes(20)).decode()


def verifica_totp(secret_b32: str, codice: str, finestra: int = 1) -> bool:
    """Verifica un codice TOTP con tolleranza ±finestra periodi (30s)."""
    try:
        key = _base64.b32decode(secret_b32.upper().replace(" ", ""))
    except Exception:
        return False
    t_now = int(_time.time()) // 30
    codice = codice.strip().replace(" ", "")
    for delta in range(-finestra, finestra + 1):
        if str(_hotp(key, t_now + delta)).zfill(6) == codice:
            return True
    return False


def totp_uri(secret_b32: str, username: str, issuer: str = "IUSENTRA") -> str:
    """Genera l'URI otpauth:// per Google Authenticator / Aegis."""
    return (
        f"otpauth://totp/{_quote(issuer)}:{_quote(username)}"
        f"?secret={secret_b32}&issuer={_quote(issuer)}&algorithm=SHA1&digits=6&period=30"
    )


# ------------------------------------------------------------------ Ruoli

class RuoloUtente(str, Enum):
    SUPERADMIN     = "SUPERADMIN"       # Amministratore della piattaforma (multi-tenant)
    AMMINISTRATORE = "AMMINISTRATORE"
    AVVOCATO       = "AVVOCATO"
    COLLABORATORE  = "COLLABORATORE"
    PRATICANTE     = "PRATICANTE"
    SEGRETERIA     = "SEGRETERIA"
    CONTABILE      = "CONTABILE"


# ------------------------------------------------------------------ Descrizioni ruoli

DESCRIZIONI_RUOLI: Dict[RuoloUtente, Dict[str, str]] = {
    RuoloUtente.SUPERADMIN: {
        "descrizione": "Amministratore piattaforma IUSENTRA — gestione studi e tenant.",
        "colore": "dark",
        "icona": "bi-building-gear",
    },
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
    ("Tenant",       "tenant.leggi",         "Visibilita tenant"),
    ("Tenant",       "tenant.configura",     "Configura tenant"),
    ("Tenant",       "tenant.impersona",     "Impersona tenant"),
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
    ("Fatturazione", "fatturazione.leggi",   "Visualizza"),
    ("Fatturazione", "fatturazione.scrivi",  "Crea / Modifica"),
    ("Telematico",   "telematico.leggi",     "Consultazione"),
    ("Telematico",   "telematico.importa",   "Importa / Sincronizza"),
    ("Telematico",   "telematico.valida",    "Predeposito"),
    ("Telematico",   "telematico.deposita",  "Deposita"),
    ("Telematico",   "telematico.configura", "Configura canali"),
    ("AI",           "ai.usa",               "Usa assistenti"),
    ("AI",           "ai.configura",         "Configura runtime"),
    ("AI",           "ai.audit",             "Audit AI"),
    ("Legal Skills", "legal_skills.leggi",   "Consulta"),
    ("Legal Skills", "legal_skills.esegui",  "Esegui"),
    ("Legal Skills", "legal_skills.approva", "Approva"),
    ("Legal Skills", "legal_skills.esporta", "Esporta"),
    ("Legal Skills", "legal_skills.profilo.scrivi", "Configura profilo"),
    ("Legal Skills", "legal_skills.trust_check", "Verifica fiducia"),
    ("Legal Skills", "legal_skills.scheduled.esegui", "Agenti schedulati"),
    ("Backup",       "backup.leggi",         "Visualizza"),
    ("Backup",       "backup.esegui",        "Esegui"),
    ("Admin",        "admin.leggi",          "Accedi pannelli"),
    ("Admin",        "admin.configura",      "Configura studio"),
    ("Autorizzazioni", "autorizzazioni.leggi",  "Leggi policy"),
    ("Autorizzazioni", "autorizzazioni.scrivi", "Gestisci policy"),
    ("Utenti",       "utenti.leggi",         "Visualizza"),
    ("Utenti",       "utenti.scrivi",        "Crea / Modifica"),
    ("Utenti",       "utenti.elimina",       "Elimina"),
    ("Audit",        "audit.leggi",          "Visualizza log"),
    ("Audit",        "audit.esporta",        "Esporta log"),
]

# Set di permessi di default per ogni ruolo
PERMESSI: Dict[RuoloUtente, List[str]] = {
    RuoloUtente.SUPERADMIN:     [p for _, p, _ in TUTTI_PERMESSI],  # tutti + accesso admin
    RuoloUtente.AMMINISTRATORE: [p for _, p, _ in TUTTI_PERMESSI],

    RuoloUtente.AVVOCATO: [
        "fascicoli.leggi", "fascicoli.scrivi", "fascicoli.archivia",
        "clienti.leggi", "clienti.scrivi",
        "agenda.leggi", "agenda.scrivi", "agenda.elimina",
        "messaggi.leggi", "messaggi.scrivi",
        "scadenziario.leggi", "scadenziario.scrivi",
        "fatturazione.leggi", "fatturazione.scrivi",
        "telematico.leggi", "telematico.importa", "telematico.valida", "telematico.deposita",
        "ai.usa",
        "legal_skills.leggi", "legal_skills.esegui", "legal_skills.approva",
        "legal_skills.esporta", "legal_skills.profilo.scrivi", "legal_skills.trust_check",
        "legal_skills.scheduled.esegui",
        "backup.leggi",
    ],

    RuoloUtente.COLLABORATORE: [
        "fascicoli.leggi", "fascicoli.scrivi",
        "clienti.leggi", "clienti.scrivi",
        "agenda.leggi", "agenda.scrivi",
        "messaggi.leggi", "messaggi.scrivi",
        "scadenziario.leggi", "scadenziario.scrivi",
        "fatturazione.leggi", "fatturazione.scrivi",
        "telematico.leggi", "telematico.importa", "telematico.valida",
        "ai.usa",
        "legal_skills.leggi", "legal_skills.esegui",
    ],

    RuoloUtente.PRATICANTE: [
        "fascicoli.leggi",
        "clienti.leggi",
        "agenda.leggi", "agenda.scrivi",
        "messaggi.leggi",
        "scadenziario.leggi",
        "fatturazione.leggi",
        "telematico.leggi",
        "ai.usa",
        "legal_skills.leggi",
    ],

    RuoloUtente.SEGRETERIA: [
        "fascicoli.leggi",
        "clienti.leggi", "clienti.scrivi",
        "agenda.leggi", "agenda.scrivi",
        "messaggi.leggi", "messaggi.scrivi",
        "scadenziario.leggi",
        "fatturazione.leggi", "fatturazione.scrivi",
        "telematico.leggi",
    ],

    RuoloUtente.CONTABILE: [
        "fascicoli.leggi",
        "clienti.leggi",
        "fatturazione.leggi", "fatturazione.scrivi",
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
    must_change_password: bool = False
    creato_il: str = field(default_factory=lambda: datetime.now().isoformat())
    ultimo_accesso: str = ""
    reset_token: str = ""
    reset_token_scade: str = ""
    # Override per-utente
    permessi_extra: List[str] = field(default_factory=list)   # aggiuntivi rispetto al ruolo
    permessi_negati: List[str] = field(default_factory=list)  # rimossi rispetto al ruolo
    # Multi-tenant: slug dello studio di appartenenza (vuoto = SUPERADMIN)
    tenant_slug: str = ""
    # 2FA (TOTP - RFC 6238)
    totp_secret: str = ""
    totp_attivato: bool = False

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

    @property
    def is_superadmin(self) -> bool:
        return self.ruolo == RuoloUtente.SUPERADMIN

    def ha_permesso(self, permesso: str) -> bool:
        """Verifica un permesso applicando gli override per-utente."""
        if self.ruolo == RuoloUtente.SUPERADMIN:
            return True
        if permesso in self.permessi_negati:
            return False
        if permesso.startswith("tenant.") and permesso not in self.permessi_extra:
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
        if self.ruolo != RuoloUtente.SUPERADMIN:
            base = {permesso for permesso in base if not permesso.startswith("tenant.")}
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
        d.setdefault("totp_secret", "")
        d.setdefault("totp_attivato", False)
        d.setdefault("tenant_slug", "")
        d.setdefault("must_change_password", False)
        allowed = Utente.__dataclass_fields__.keys()
        return Utente(**{k: v for k, v in d.items() if k in allowed})


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
        crea_admin_se_vuoto: bool = True,
        ruolo_default: "RuoloUtente | None" = None,
        studio_db=None,
        bootstrap_admin_password: str = "",
        bootstrap_admin_credentials_path: str = "",
        tenant_slug_context: str = "",
    ):
        self.db_path = Path(db_path)
        self.audit_path = Path(audit_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._studio_db = studio_db
        self._crea_admin_se_vuoto = crea_admin_se_vuoto
        self._ruolo_default = ruolo_default
        self._bootstrap_admin_password = (bootstrap_admin_password or "").strip()
        self._tenant_slug_context = str(tenant_slug_context or "").strip().lower()
        self._bootstrap_admin_credentials_path = (
            Path(bootstrap_admin_credentials_path)
            if bootstrap_admin_credentials_path
            else self.db_path.parent / "bootstrap_admin.json"
        )
        self._secret = secret_key or secrets.token_hex(32)
        self._retention_days = retention_days
        self._utenti: Dict[str, Utente] = {}
        self._audit: List[EventoAudit] = []
        self._ensure_studio_db_schema()
        self._carica()
        if not self._utenti and self._crea_admin_se_vuoto:
            self._crea_admin_default()

    def _disable_studio_db(self, exc: Exception, *, operation: str) -> None:
        if self._studio_db is None:
            return
        logger.warning(
            "GestioneUtenti: backend studio non disponibile durante %s, fallback su archivio locale (%s)",
            operation,
            exc,
        )
        self._studio_db = None

    def _load_json_utenti(self) -> Dict[str, Utente]:
        from pct import cache as _cache

        try:
            raw = _cache.load(self.db_path)
            return {k: Utente.from_dict(v) for k, v in raw.items()}
        except Exception:
            return {}

    def _load_json_audit(self) -> List[EventoAudit]:
        from pct import cache as _cache

        try:
            raw_audit = _cache.load(self.audit_path, default=[])
            return [EventoAudit.from_dict(e) for e in raw_audit]
        except Exception:
            return []

    def _save_json_utenti(self) -> None:
        from pct import cache as _cache

        _cache.save(self.db_path, {k: v.to_dict() for k, v in self._utenti.items()})

    def _save_json_audit(self, recenti: List[EventoAudit]) -> None:
        from pct import cache as _cache

        _cache.save(self.audit_path, [e.to_dict() for e in recenti])

    def _apply_tenant_context_to_users(self, users: Dict[str, Utente]) -> bool:
        if not self._tenant_slug_context:
            return False
        changed = False
        for user in users.values():
            if user.ruolo == RuoloUtente.SUPERADMIN:
                continue
            if str(user.tenant_slug or "").strip():
                continue
            user.tenant_slug = self._tenant_slug_context
            changed = True
        return changed

    @staticmethod
    def _user_membership_signature(users: Dict[str, Utente]) -> Dict[str, tuple[str, str, bool]]:
        signature: Dict[str, tuple[str, str, bool]] = {}
        for user in users.values():
            username = str(user.username or "").strip().lower()
            if not username:
                continue
            signature[username] = (
                str(user.email or "").strip().lower(),
                str(getattr(user.ruolo, "value", user.ruolo) or "").strip().upper(),
                bool(user.attivo),
            )
        return signature

    def _tenant_json_should_repair_sqlite(
        self,
        legacy_users: Dict[str, Utente],
        sqlite_users: Dict[str, Utente],
    ) -> bool:
        if not self._tenant_slug_context:
            return False
        if not legacy_users or not sqlite_users:
            return False
        return self._user_membership_signature(legacy_users) != self._user_membership_signature(sqlite_users)

    # ---- persistenza

    def _ensure_studio_db_schema(self):
        if self._studio_db is None:
            return
        try:
            cols = {
                row["name"]
                for row in self._studio_db.conn.execute("PRAGMA table_info(utenti)").fetchall()
            }
            if "must_change_password" not in cols:
                self._studio_db.conn.execute(
                    "ALTER TABLE utenti ADD COLUMN must_change_password INTEGER DEFAULT 0"
                )
            if "tenant_slug" not in cols:
                self._studio_db.conn.execute(
                    "ALTER TABLE utenti ADD COLUMN tenant_slug TEXT DEFAULT ''"
                )
                self._studio_db.conn.commit()
        except Exception:
            # Best effort: in assenza di schema SQLite o migrazione non disponibile
            # il backend JSON continua a funzionare senza interrompere l'avvio.
            pass

    def _carica(self):
        legacy_utenti = self._load_json_utenti()
        legacy_changed = self._apply_tenant_context_to_users(legacy_utenti)
        legacy_audit = self._load_json_audit()

        if self._studio_db is not None:
            import json as _json

            try:
                user_cols = {
                    row["name"]
                    for row in self._studio_db.conn.execute("PRAGMA table_info(utenti)").fetchall()
                }
                has_tenant_slug = "tenant_slug" in user_cols
                select_fields = [
                    "id",
                    "username",
                    "email",
                    "nome_completo",
                    "ruolo",
                    "password_hash",
                    "attivo",
                    "permessi_extra",
                    "permessi_negati",
                    "creato_il",
                    "ultimo_accesso",
                    "must_change_password",
                ]
                if has_tenant_slug:
                    select_fields.append("tenant_slug")
                rows = self._studio_db.conn.execute(
                    f"SELECT {', '.join(select_fields)} FROM utenti"
                ).fetchall()
                self._utenti = {}
                for row in rows:
                    d = dict(row)
                    d["permessi_extra"] = _json.loads(d.get("permessi_extra") or "[]")
                    d["permessi_negati"] = _json.loads(d.get("permessi_negati") or "[]")
                    d["attivo"] = bool(d.get("attivo", 1))
                    d["must_change_password"] = bool(d.get("must_change_password", 0))
                    if (
                        self._tenant_slug_context
                        and not str(d.get("tenant_slug") or "").strip()
                        and str(d.get("ruolo") or "").strip().upper() != RuoloUtente.SUPERADMIN.value
                    ):
                        d["tenant_slug"] = self._tenant_slug_context
                    try:
                        u = Utente.from_dict(d)
                        self._utenti[u.id] = u
                    except Exception:
                        pass
                sqlite_changed = self._apply_tenant_context_to_users(self._utenti)
                if self._tenant_json_should_repair_sqlite(legacy_utenti, self._utenti):
                    logger.warning(
                        "GestioneUtenti: riallineo studio.db da archivio utenti locale per tenant=%s db=%s",
                        self._tenant_slug_context,
                        self.db_path,
                    )
                    self._utenti = legacy_utenti
                    self._salva_utenti()
                elif not self._utenti and legacy_utenti:
                    self._utenti = legacy_utenti
                    self._salva_utenti()
                elif sqlite_changed:
                    self._salva_utenti()
                elif legacy_changed:
                    self._save_json_utenti()

                rows = self._studio_db.conn.execute(
                    "SELECT id, timestamp, id_utente, username, azione, "
                    "risorsa_tipo, risorsa_id, dettagli, ip, esito FROM audit_log"
                ).fetchall()
                self._audit = []
                for row in rows:
                    try:
                        self._audit.append(EventoAudit.from_dict(dict(row)))
                    except Exception:
                        pass
                if not self._audit:
                    if legacy_audit:
                        self._audit = legacy_audit
                        self._salva_audit()
                return
            except Exception as exc:
                self._disable_studio_db(exc, operation="caricamento utenti e audit")
        self._utenti = legacy_utenti
        self._audit = legacy_audit
        if legacy_changed:
            self._save_json_utenti()

    def _salva_utenti(self):
        if self._studio_db is not None:
            import json as _json

            def _insert(conn, u):
                conn.execute(
                    """
                    INSERT INTO utenti
                    (id, username, email, nome_completo, ruolo, password_hash,
                     attivo, permessi_extra, permessi_negati, creato_il, ultimo_accesso,
                     must_change_password, tenant_slug)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        u.id, u.username, u.email, u.nome_completo,
                        u.ruolo.value, u.password_hash,
                        1 if u.attivo else 0,
                        _json.dumps(u.permessi_extra or [], ensure_ascii=False),
                        _json.dumps(u.permessi_negati or [], ensure_ascii=False),
                        u.creato_il, u.ultimo_accesso,
                        1 if u.must_change_password else 0,
                        str(u.tenant_slug or "").strip().lower(),
                    ),
                )

            try:
                self._studio_db.salva_tabella("utenti", list(self._utenti.values()), _insert)
                self._save_json_utenti()
                return
            except Exception as exc:
                self._disable_studio_db(exc, operation="salvataggio utenti")
        self._save_json_utenti()

    def _salva_audit(self):
        if self._studio_db is not None:
            cutoff = (datetime.now() - timedelta(days=self._retention_days)).isoformat()
            recenti = [e for e in self._audit if e.timestamp >= cutoff]
            recenti = recenti[-10000:]
            self._audit = recenti

            def _insert(conn, e):
                conn.execute(
                    """
                    INSERT INTO audit_log
                    (id, timestamp, id_utente, username, azione,
                     risorsa_tipo, risorsa_id, dettagli, ip, esito)
                    VALUES (?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        e.id, e.timestamp, e.id_utente, e.username,
                        e.azione, e.risorsa_tipo, e.risorsa_id,
                        e.dettagli, e.ip, e.esito,
                    ),
                )

            try:
                self._studio_db.salva_tabella("audit_log", recenti, _insert)
                self._save_json_audit(recenti)
                return
            except Exception as exc:
                self._disable_studio_db(exc, operation="salvataggio audit")
        cutoff = (datetime.now() - timedelta(days=self._retention_days)).isoformat()
        recenti = [e for e in self._audit if e.timestamp >= cutoff]
        recenti = recenti[-10000:]  # hard cap di sicurezza
        self._audit = recenti
        self._save_json_audit(recenti)

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
        ruolo = self._ruolo_default or RuoloUtente.AMMINISTRATORE
        nome = "Super Amministratore" if ruolo == RuoloUtente.SUPERADMIN else "Amministratore"
        bootstrap_password = self._bootstrap_admin_password
        if (
            not bootstrap_password
            and os.getenv("PYTEST_CURRENT_TEST")
            and str(self._secret or "").strip().lower() == "test"
        ):
            bootstrap_password = "admin"
        if not bootstrap_password:
            bootstrap_password = secrets.token_urlsafe(18)
        admin = Utente(
            username="admin",
            email="admin@studio.local",
            nome_completo=nome,
            ruolo=ruolo,
            password_hash=self._hash_password(bootstrap_password),
            must_change_password=True,
        )
        self._utenti[admin.id] = admin
        self._salva_utenti()
        self._salva_bootstrap_admin_credentials(bootstrap_password)

    def _salva_bootstrap_admin_credentials(self, password: str) -> None:
        payload = {
            "username": "admin",
            "password": password,
            "must_change_password": True,
            "creato_il": datetime.now().isoformat(),
        }
        self._bootstrap_admin_credentials_path.parent.mkdir(parents=True, exist_ok=True)
        self._bootstrap_admin_credentials_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def bootstrap_admin_credentials(self) -> Optional[Dict[str, Any]]:
        path = self._bootstrap_admin_credentials_path
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def clear_bootstrap_admin_credentials(self) -> None:
        path = self._bootstrap_admin_credentials_path
        try:
            path.unlink(missing_ok=True)
        except TypeError:
            if path.exists():
                path.unlink()

    # ---- password

    @staticmethod
    def _hash_password(password: str) -> str:
        from werkzeug.security import generate_password_hash
        return generate_password_hash(password)

    @staticmethod
    def _verifica_password(password: str, hash_: str) -> bool:
        from werkzeug.security import check_password_hash
        return check_password_hash(hash_, password)

    def _valida_ruolo_tenant(self, *, ruolo: RuoloUtente, tenant_slug: str = "", user_id: str = "") -> None:
        tenant_slug_norm = str(tenant_slug or "").strip().lower()
        if ruolo != RuoloUtente.SUPERADMIN:
            return
        if tenant_slug_norm:
            raise ValueError(
                "Il ruolo SUPERADMIN e' riservato alla piattaforma e non puo' appartenere a uno studio."
            )
        existing = next(
            (
                user
                for user in self._utenti.values()
                if user.ruolo == RuoloUtente.SUPERADMIN and str(user.id or "") != str(user_id or "")
            ),
            None,
        )
        if existing is not None:
            raise ValueError(
                "Esiste gia' un solo SUPERADMIN di piattaforma. Usa l'account esistente o promuovilo esplicitamente."
            )

    def ensure_platform_superadmin(self, *, preferred_username: str = "admin") -> Utente | None:
        """Promuove un admin piattaforma legacy a SUPERADMIN se il ruolo radice manca."""
        platform_superadmins = [
            user
            for user in self._utenti.values()
            if user.ruolo == RuoloUtente.SUPERADMIN and not str(user.tenant_slug or "").strip()
        ]
        if platform_superadmins:
            return platform_superadmins[0]

        platform_admins = [
            user
            for user in self._utenti.values()
            if user.ruolo == RuoloUtente.AMMINISTRATORE
            and not str(user.tenant_slug or "").strip()
            and user.attivo
        ]
        if not platform_admins:
            return None

        preferred = str(preferred_username or "").strip().lower()
        target = next(
            (user for user in platform_admins if str(user.username or "").strip().lower() == preferred),
            platform_admins[0],
        )
        target.ruolo = RuoloUtente.SUPERADMIN
        self._salva_utenti()
        return target

    def crea_o_promuovi_superadmin_piattaforma(
        self,
        *,
        username: str,
        password: str,
        email: str = "",
        nome_completo: str = "",
        must_change_password: bool = True,
    ) -> Utente:
        username_norm = str(username or "").strip().lower()
        if not username_norm:
            raise ValueError("Username obbligatorio")
        if len(password) < 8:
            raise ValueError("La password deve avere almeno 8 caratteri")

        esistente = self.get_by_username(username_norm)
        if esistente is not None:
            if str(esistente.tenant_slug or "").strip():
                raise ValueError(
                    "Esiste gia' un account con questo username dentro uno studio. "
                    "Il SUPERADMIN deve nascere solo nella piattaforma."
                )
            self._valida_ruolo_tenant(
                ruolo=RuoloUtente.SUPERADMIN,
                tenant_slug="",
                user_id=esistente.id,
            )
            esistente.ruolo = RuoloUtente.SUPERADMIN
            esistente.email = str(email or "").strip()
            esistente.nome_completo = str(nome_completo or "").strip()
            esistente.attivo = True
            esistente.must_change_password = must_change_password
            esistente.password_hash = self._hash_password(password)
            self._salva_utenti()
            return esistente

        return self.crea(
            username=username_norm,
            password=password,
            ruolo=RuoloUtente.SUPERADMIN,
            email=email,
            nome_completo=nome_completo,
            tenant_slug="",
            must_change_password=must_change_password,
        )

    def genera_superadmin_piattaforma(
        self,
        *,
        username: str,
        password: str,
        email: str = "",
        nome_completo: str = "",
        must_change_password: bool = True,
        ruolo_superadmin_precedente: "RuoloUtente | str" = RuoloUtente.AMMINISTRATORE,
    ) -> Utente:
        username_norm = str(username or "").strip().lower()
        if not username_norm:
            raise ValueError("Username obbligatorio")
        if len(password) < 8:
            raise ValueError("La password deve avere almeno 8 caratteri")

        superadmin_corrente = next(
            (
                u for u in self._utenti.values()
                if not str(u.tenant_slug or "").strip()
                and u.ruolo == RuoloUtente.SUPERADMIN
                and u.attivo
            ),
            None,
        )
        if superadmin_corrente is None:
            return self.crea_o_promuovi_superadmin_piattaforma(
                username=username_norm,
                password=password,
                email=email,
                nome_completo=nome_completo,
                must_change_password=must_change_password,
            )

        esistente = self.get_by_username(username_norm)
        if esistente is not None and str(esistente.tenant_slug or "").strip():
            raise ValueError(
                "Esiste gia' un account con questo username dentro uno studio. "
                "Il SUPERADMIN deve nascere solo nella piattaforma."
            )

        if esistente is not None and esistente.id == superadmin_corrente.id:
            superadmin_corrente.email = str(email or "").strip()
            superadmin_corrente.nome_completo = str(nome_completo or "").strip()
            superadmin_corrente.attivo = True
            superadmin_corrente.must_change_password = must_change_password
            superadmin_corrente.password_hash = self._hash_password(password)
            self._salva_utenti()
            return superadmin_corrente

        creato_ora = False
        target = esistente
        if target is None:
            target = self.crea(
                username=username_norm,
                password=password,
                ruolo=RuoloUtente.AMMINISTRATORE,
                email=email,
                nome_completo=nome_completo,
                tenant_slug="",
                must_change_password=must_change_password,
            )
            creato_ora = True
        else:
            target.email = str(email or "").strip()
            target.nome_completo = str(nome_completo or "").strip()
            target.attivo = True
            target.must_change_password = must_change_password
            target.password_hash = self._hash_password(password)
            self._salva_utenti()

        try:
            return self.trasferisci_superadmin_piattaforma(
                source_id=superadmin_corrente.id,
                target_id=target.id,
                ruolo_sorgente=ruolo_superadmin_precedente,
            )
        except Exception:
            if creato_ora:
                self.elimina(target.id, force=True)
            raise

    def trasferisci_superadmin_piattaforma(
        self,
        *,
        source_id: str,
        target_id: str,
        ruolo_sorgente: "RuoloUtente | str" = RuoloUtente.AMMINISTRATORE,
    ) -> Utente:
        sorgente = self._get_or_raise(source_id)
        destinazione = self._get_or_raise(target_id)

        if str(sorgente.tenant_slug or "").strip() or str(destinazione.tenant_slug or "").strip():
            raise ValueError("Il trasferimento del SUPERADMIN e' ammesso solo tra account globali di piattaforma.")
        if sorgente.id == destinazione.id:
            raise ValueError("Seleziona un account diverso per trasferire il ruolo SUPERADMIN.")
        if sorgente.ruolo != RuoloUtente.SUPERADMIN:
            raise ValueError("L'account sorgente non e' il SUPERADMIN di piattaforma.")

        ruolo_sorgente_norm = RuoloUtente(ruolo_sorgente)
        if ruolo_sorgente_norm == RuoloUtente.SUPERADMIN:
            raise ValueError("Il ruolo precedente del sorgente non puo' restare SUPERADMIN.")

        destinazione.ruolo = RuoloUtente.SUPERADMIN
        destinazione.attivo = True
        sorgente.ruolo = ruolo_sorgente_norm
        self._salva_utenti()
        return destinazione

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
        tenant_slug: str = "",
        must_change_password: bool = True,
    ) -> Utente:
        username = username.strip().lower()
        if not username:
            raise ValueError("Username obbligatorio")
        if len(password) < 8:
            raise ValueError("La password deve avere almeno 8 caratteri")
        if not isinstance(ruolo, RuoloUtente):
            ruolo = RuoloUtente(ruolo)
        self._valida_ruolo_tenant(ruolo=ruolo, tenant_slug=tenant_slug)
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
            tenant_slug=tenant_slug,
            must_change_password=must_change_password,
        )
        self._utenti[utente.id] = utente
        self._salva_utenti()
        return utente

    def aggiorna(self, id_utente: str, **kwargs) -> Utente:
        u = self._get_or_raise(id_utente)
        campi_consentiti = {"email", "nome_completo", "ruolo", "attivo"}
        ruolo_target = u.ruolo
        for k, v in kwargs.items():
            if k not in campi_consentiti:
                raise ValueError(f"Campo non modificabile: {k}")
            if k == "ruolo":
                v = RuoloUtente(v)
                ruolo_target = v
        self._valida_ruolo_tenant(
            ruolo=ruolo_target,
            tenant_slug=u.tenant_slug,
            user_id=u.id,
        )
        for k, v in kwargs.items():
            if k == "ruolo":
                v = RuoloUtente(v)
            setattr(u, k, v)
        self._salva_utenti()
        return u

    def importa_utente_esistente(
        self,
        utente: Utente,
        *,
        ruolo: "RuoloUtente | str | None" = None,
        tenant_slug: str = "",
        preserve_id: bool = True,
    ) -> Utente:
        """Importa un utente esistente in questo repository preservando credenziali e auditabilità."""
        if not isinstance(utente, Utente):
            raise ValueError("Utente sorgente non valido")
        ruolo_target = RuoloUtente(ruolo) if ruolo is not None else utente.ruolo
        tenant_slug_norm = str(tenant_slug or "").strip().lower()
        self._valida_ruolo_tenant(ruolo=ruolo_target, tenant_slug=tenant_slug_norm)

        username = str(utente.username or "").strip().lower()
        if not username:
            raise ValueError("Username obbligatorio")
        if any(existing.username == username for existing in self._utenti.values()):
            raise ValueError(f"Username '{username}' gia' in uso nella destinazione")

        imported_id = str(utente.id or "").strip() if preserve_id else ""
        if not imported_id or imported_id in self._utenti:
            imported_id = str(uuid.uuid4())

        imported = Utente(
            id=imported_id,
            username=username,
            email=str(utente.email or "").strip(),
            nome_completo=str(utente.nome_completo or "").strip(),
            ruolo=ruolo_target,
            password_hash=str(utente.password_hash or ""),
            attivo=bool(utente.attivo),
            must_change_password=bool(utente.must_change_password),
            creato_il=str(utente.creato_il or datetime.now().isoformat()),
            ultimo_accesso=str(utente.ultimo_accesso or ""),
            reset_token="",
            reset_token_scade="",
            permessi_extra=list(utente.permessi_extra or []),
            permessi_negati=list(utente.permessi_negati or []),
            tenant_slug=tenant_slug_norm,
            totp_secret=str(utente.totp_secret or ""),
            totp_attivato=bool(utente.totp_attivato),
        )
        self._utenti[imported.id] = imported
        self._salva_utenti()
        return imported

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

    def cambia_password(
        self,
        id_utente: str,
        nuova_password: str,
        *,
        must_change_password: bool = False,
    ) -> Utente:
        if len(nuova_password) < 8:
            raise ValueError("La password deve avere almeno 8 caratteri")
        u = self._get_or_raise(id_utente)
        u.password_hash = self._hash_password(nuova_password)
        u.must_change_password = must_change_password
        self._salva_utenti()
        if u.username == "admin":
            if must_change_password:
                self._salva_bootstrap_admin_credentials(nuova_password)
            else:
                self.clear_bootstrap_admin_credentials()
        return u

    def elimina(self, id_utente: str, *, force: bool = False):
        u = self._get_or_raise(id_utente)
        if not force and u.ruolo == RuoloUtente.SUPERADMIN:
            superadmin_count = sum(
                1 for x in self._utenti.values()
                if x.ruolo == RuoloUtente.SUPERADMIN and x.attivo
            )
            if superadmin_count <= 1:
                raise ValueError(
                    "Impossibile eliminare l'unico superadmin di piattaforma. "
                    "Trasferisci prima il ruolo a un altro account globale dal pannello piattaforma."
                )
        if not force and u.ruolo == RuoloUtente.AMMINISTRATORE:
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
            email = str(u.email or "").strip().lower()
            if (u.username == username or (email and email == username)) and u.attivo:
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

    def lista(self, solo_attivi: bool = False) -> List[Utente]:
        """Alias retrocompatibile usato dal pannello admin multi-tenant."""
        return self.tutti(solo_attivi=solo_attivi)

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
                    u.must_change_password = False
                    self._salva_utenti()
                    if u.username == "admin":
                        self.clear_bootstrap_admin_credentials()
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

