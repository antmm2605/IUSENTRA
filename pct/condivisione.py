"""
Gestione condivisione cartelle clienti tra collaboratori.

Funzionalità:
  - Tre livelli di accesso per cartella cliente: LETTURA | SCRITTURA | GESTORE
  - Scadenza automatica degli accessi (data_scadenza)
  - Tag per organizzare e filtrare le condivisioni
  - Permessi per singolo fascicolo (CondivisioneFascicolo)
  - Link di accesso temporaneo via token HMAC per clienti/consulenti esterni
  - Audit e statistiche complete

Gli utenti con il permesso globale 'clienti.leggi' (Avvocati, Amministratori)
vedono sempre TUTTE le cartelle. Questo meccanismo si applica ai ruoli
con accesso ristretto (Collaboratori, Praticanti, Segreteria, Contabili).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


# ================================================================ Enums

class RuoloCondivisione(str, Enum):
    LETTURA   = "LETTURA"   # solo visualizzazione
    SCRITTURA = "SCRITTURA" # visualizzazione + modifica
    GESTORE   = "GESTORE"   # scrittura + gestione collaboratori

    def include(self, altro: "RuoloCondivisione") -> bool:
        """True se questo ruolo include i permessi di 'altro'."""
        ordine = [RuoloCondivisione.LETTURA, RuoloCondivisione.SCRITTURA, RuoloCondivisione.GESTORE]
        return ordine.index(self) >= ordine.index(altro)


# ================================================================ AccessoCondiviso

@dataclass
class AccessoCondiviso:
    """Accesso di un singolo utente a una cartella cliente."""
    id_utente: str
    username: str
    nome_completo: str
    ruolo: RuoloCondivisione
    condiviso_da: str        # username di chi ha aggiunto questo accesso
    data_condivisione: str   # ISO datetime
    note: str = ""
    # #2 — Scadenza automatica
    data_scadenza: str = ""  # ISO date (YYYY-MM-DD). Vuoto = nessuna scadenza
    # #9 — Tag di organizzazione
    tags: List[str] = field(default_factory=list)

    @property
    def is_scaduto(self) -> bool:
        """True se l'accesso è scaduto (data_scadenza nel passato)."""
        if not self.data_scadenza:
            return False
        try:
            return datetime.fromisoformat(self.data_scadenza).date() < datetime.now().date()
        except ValueError:
            return False

    @property
    def giorni_alla_scadenza(self) -> Optional[int]:
        """Giorni mancanti alla scadenza. None se nessuna scadenza, negativo se già scaduto."""
        if not self.data_scadenza:
            return None
        try:
            delta = datetime.fromisoformat(self.data_scadenza).date() - datetime.now().date()
            return delta.days
        except ValueError:
            return None

    @classmethod
    def from_dict(cls, d: dict) -> "AccessoCondiviso":
        return cls(
            id_utente=d["id_utente"],
            username=d["username"],
            nome_completo=d.get("nome_completo", ""),
            ruolo=RuoloCondivisione(d["ruolo"]),
            condiviso_da=d.get("condiviso_da", ""),
            data_condivisione=d.get("data_condivisione", ""),
            note=d.get("note", ""),
            data_scadenza=d.get("data_scadenza", ""),
            tags=d.get("tags", []),
        )

    def to_dict(self) -> dict:
        d = asdict(self)
        d["ruolo"] = self.ruolo.value
        return d


# ================================================================ CondivisioneCartella

@dataclass
class CondivisioneCartella:
    """Registro delle condivisioni per una cartella cliente."""
    id: str
    id_cliente: str
    accessi: List[AccessoCondiviso] = field(default_factory=list)
    creato_il: str = ""
    modificato_il: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "CondivisioneCartella":
        return cls(
            id=d["id"],
            id_cliente=d["id_cliente"],
            accessi=[AccessoCondiviso.from_dict(a) for a in d.get("accessi", [])],
            creato_il=d.get("creato_il", ""),
            modificato_il=d.get("modificato_il", ""),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "id_cliente": self.id_cliente,
            "accessi": [a.to_dict() for a in self.accessi],
            "creato_il": self.creato_il,
            "modificato_il": self.modificato_il,
        }

    def utente(self, id_utente: str) -> Optional[AccessoCondiviso]:
        for a in self.accessi:
            if a.id_utente == id_utente:
                return a
        return None


# ================================================================ #5 CondivisioneFascicolo

@dataclass
class AccessoFascicolo:
    """Accesso di un utente a un singolo fascicolo."""
    id_utente: str
    username: str
    nome_completo: str
    ruolo: RuoloCondivisione
    condiviso_da: str
    data_condivisione: str
    note: str = ""
    data_scadenza: str = ""
    tags: List[str] = field(default_factory=list)

    @property
    def is_scaduto(self) -> bool:
        if not self.data_scadenza:
            return False
        try:
            return datetime.fromisoformat(self.data_scadenza).date() < datetime.now().date()
        except ValueError:
            return False

    @classmethod
    def from_dict(cls, d: dict) -> "AccessoFascicolo":
        return cls(
            id_utente=d["id_utente"],
            username=d["username"],
            nome_completo=d.get("nome_completo", ""),
            ruolo=RuoloCondivisione(d["ruolo"]),
            condiviso_da=d.get("condiviso_da", ""),
            data_condivisione=d.get("data_condivisione", ""),
            note=d.get("note", ""),
            data_scadenza=d.get("data_scadenza", ""),
            tags=d.get("tags", []),
        )

    def to_dict(self) -> dict:
        d = asdict(self)
        d["ruolo"] = self.ruolo.value
        return d


@dataclass
class CondivisioneFascicolo:
    """Accessi a un singolo fascicolo (indipendenti dalla cartella cliente)."""
    id: str
    id_fascicolo: str
    id_cliente: str           # denormalizzato per query rapide
    accessi: List[AccessoFascicolo] = field(default_factory=list)
    creato_il: str = ""
    modificato_il: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "CondivisioneFascicolo":
        return cls(
            id=d["id"],
            id_fascicolo=d["id_fascicolo"],
            id_cliente=d.get("id_cliente", ""),
            accessi=[AccessoFascicolo.from_dict(a) for a in d.get("accessi", [])],
            creato_il=d.get("creato_il", ""),
            modificato_il=d.get("modificato_il", ""),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "id_fascicolo": self.id_fascicolo,
            "id_cliente": self.id_cliente,
            "accessi": [a.to_dict() for a in self.accessi],
            "creato_il": self.creato_il,
            "modificato_il": self.modificato_il,
        }

    def utente(self, id_utente: str) -> Optional[AccessoFascicolo]:
        for a in self.accessi:
            if a.id_utente == id_utente:
                return a
        return None


# ================================================================ #6 LinkTemporaneo

@dataclass
class LinkTemporaneo:
    """
    Link di accesso temporaneo a una cartella cliente o singolo fascicolo.
    Genera un token HMAC-SHA256 per accesso senza credenziali di sistema
    (utile per clienti o consulenti esterni).
    """
    id: str
    token_hash: str          # SHA-256 del token grezzo
    id_cliente: str
    id_fascicolo: str = ""   # vuoto = intera cartella
    ruolo: RuoloCondivisione = RuoloCondivisione.LETTURA
    scade_il: str = ""       # ISO datetime
    creato_da: str = ""      # username
    creato_il: str = ""
    usato: bool = False      # True dopo il primo utilizzo (se monouso)
    monouso: bool = False    # True = si autorevoca dopo primo accesso
    descrizione: str = ""    # nome/email del destinatario esterno

    @property
    def is_valido(self) -> bool:
        """False se scaduto o già usato (quando monouso)."""
        if self.monouso and self.usato:
            return False
        if not self.scade_il:
            return True
        try:
            return datetime.fromisoformat(self.scade_il) > datetime.now()
        except ValueError:
            return False

    @classmethod
    def from_dict(cls, d: dict) -> "LinkTemporaneo":
        return cls(
            id=d["id"],
            token_hash=d["token_hash"],
            id_cliente=d["id_cliente"],
            id_fascicolo=d.get("id_fascicolo", ""),
            ruolo=RuoloCondivisione(d.get("ruolo", RuoloCondivisione.LETTURA.value)),
            scade_il=d.get("scade_il", ""),
            creato_da=d.get("creato_da", ""),
            creato_il=d.get("creato_il", ""),
            usato=d.get("usato", False),
            monouso=d.get("monouso", False),
            descrizione=d.get("descrizione", ""),
        )

    def to_dict(self) -> dict:
        d = asdict(self)
        d["ruolo"] = self.ruolo.value
        return d


# ================================================================ GestioneCondivisioni

class GestioneCondivisioni:
    """
    Manager unico per:
    - Condivisioni cartelle cliente (AccessoCondiviso)
    - Condivisioni singoli fascicoli (CondivisioneFascicolo)
    - Link temporanei di accesso esterno (LinkTemporaneo)

    Persistenza: file JSON unico con sezioni 'cartelle', 'fascicoli', 'link'.
    """

    def __init__(self, db_path: str, secret_key: str = ""):
        self.db_path = Path(db_path)
        self._secret = secret_key or "condivisione-default-secret"
        # id_cliente → CondivisioneCartella
        self._cartelle: Dict[str, CondivisioneCartella] = {}
        # id_fascicolo → CondivisioneFascicolo
        self._fascicoli: Dict[str, CondivisioneFascicolo] = {}
        # id_link → LinkTemporaneo
        self._link: Dict[str, LinkTemporaneo] = {}
        self._carica()

    # ---------------------------------------------------------------- I/O

    def _carica(self) -> None:
        if not self.db_path.exists():
            return
        try:
            raw = json.loads(self.db_path.read_text(encoding="utf-8"))
            # Retrocompatibilità: vecchio formato {id_cliente: {...}}
            if raw and next(iter(raw.values()), None) and "accessi" in next(iter(raw.values()), {}):
                # vecchio formato piatto → migra a nuovo
                self._cartelle = {k: CondivisioneCartella.from_dict(v) for k, v in raw.items()}
            else:
                self._cartelle = {
                    k: CondivisioneCartella.from_dict(v)
                    for k, v in raw.get("cartelle", {}).items()
                }
                self._fascicoli = {
                    k: CondivisioneFascicolo.from_dict(v)
                    for k, v in raw.get("fascicoli", {}).items()
                }
                self._link = {
                    k: LinkTemporaneo.from_dict(v)
                    for k, v in raw.get("link", {}).items()
                }
        except (json.JSONDecodeError, KeyError, TypeError):
            pass

    def _salva(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path.write_text(
            json.dumps(
                {
                    "cartelle": {k: v.to_dict() for k, v in self._cartelle.items()},
                    "fascicoli": {k: v.to_dict() for k, v in self._fascicoli.items()},
                    "link": {k: v.to_dict() for k, v in self._link.items()},
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def _get_o_crea_cartella(self, id_cliente: str) -> CondivisioneCartella:
        if id_cliente not in self._cartelle:
            self._cartelle[id_cliente] = CondivisioneCartella(
                id=uuid.uuid4().hex[:8],
                id_cliente=id_cliente,
                creato_il=datetime.now().isoformat(),
                modificato_il=datetime.now().isoformat(),
            )
        return self._cartelle[id_cliente]

    def _get_o_crea_fascicolo(self, id_fascicolo: str, id_cliente: str = "") -> CondivisioneFascicolo:
        if id_fascicolo not in self._fascicoli:
            self._fascicoli[id_fascicolo] = CondivisioneFascicolo(
                id=uuid.uuid4().hex[:8],
                id_fascicolo=id_fascicolo,
                id_cliente=id_cliente,
                creato_il=datetime.now().isoformat(),
                modificato_il=datetime.now().isoformat(),
            )
        return self._fascicoli[id_fascicolo]

    # ================================================================ CARTELLE — CRUD

    def condividi(
        self,
        id_cliente: str,
        id_utente: str,
        username: str,
        nome_completo: str,
        ruolo: RuoloCondivisione,
        condiviso_da: str,
        note: str = "",
        data_scadenza: str = "",
        tags: Optional[List[str]] = None,
    ) -> CondivisioneCartella:
        """Aggiunge o aggiorna l'accesso di un utente alla cartella di un cliente."""
        c = self._get_o_crea_cartella(id_cliente)
        c.accessi = [a for a in c.accessi if a.id_utente != id_utente]
        c.accessi.append(AccessoCondiviso(
            id_utente=id_utente,
            username=username,
            nome_completo=nome_completo,
            ruolo=ruolo,
            condiviso_da=condiviso_da,
            data_condivisione=datetime.now().isoformat(),
            note=note,
            data_scadenza=data_scadenza,
            tags=tags or [],
        ))
        c.modificato_il = datetime.now().isoformat()
        self._salva()
        return c

    def revoca(self, id_cliente: str, id_utente: str) -> bool:
        """Rimuove l'accesso di un utente alla cartella. True se trovato e rimosso."""
        if id_cliente not in self._cartelle:
            return False
        c = self._cartelle[id_cliente]
        prima = len(c.accessi)
        c.accessi = [a for a in c.accessi if a.id_utente != id_utente]
        rimosso = len(c.accessi) < prima
        if rimosso:
            if not c.accessi:
                del self._cartelle[id_cliente]
            else:
                c.modificato_il = datetime.now().isoformat()
            self._salva()
        return rimosso

    def revoca_tutti(self, id_cliente: str) -> int:
        """Rimuove TUTTI gli accessi a una cartella. Restituisce il numero rimosso."""
        c = self._cartelle.pop(id_cliente, None)
        if c:
            n = len(c.accessi)
            self._salva()
            return n
        return 0

    def revoca_scaduti(self) -> int:
        """
        Rimuove automaticamente tutti gli accessi scaduti (cartelle + fascicoli).
        Restituisce il numero totale rimosso.
        """
        rimossi = 0
        for id_c in list(self._cartelle.keys()):
            c = self._cartelle[id_c]
            prima = len(c.accessi)
            c.accessi = [a for a in c.accessi if not a.is_scaduto]
            rimossi += prima - len(c.accessi)
            if not c.accessi:
                del self._cartelle[id_c]
        for id_f in list(self._fascicoli.keys()):
            cf = self._fascicoli[id_f]
            prima = len(cf.accessi)
            cf.accessi = [a for a in cf.accessi if not a.is_scaduto]
            rimossi += prima - len(cf.accessi)
            if not cf.accessi:
                del self._fascicoli[id_f]
        if rimossi:
            self._salva()
        return rimossi

    def accessi_scaduti(self) -> List[Tuple[str, AccessoCondiviso]]:
        """Restituisce [(id_cliente, accesso)] per tutti gli accessi scaduti."""
        risultato = []
        for id_c, c in self._cartelle.items():
            for a in c.accessi:
                if a.is_scaduto:
                    risultato.append((id_c, a))
        return risultato

    def accessi_in_scadenza(self, entro_giorni: int = 7) -> List[Tuple[str, AccessoCondiviso]]:
        """Accessi che scadono entro N giorni (non ancora scaduti)."""
        risultato = []
        for id_c, c in self._cartelle.items():
            for a in c.accessi:
                gg = a.giorni_alla_scadenza
                if gg is not None and 0 <= gg <= entro_giorni:
                    risultato.append((id_c, a))
        return risultato

    # ================================================================ CARTELLE — Accesso

    def ha_accesso(
        self,
        id_utente: str,
        id_cliente: str,
        richiesto: RuoloCondivisione = RuoloCondivisione.LETTURA,
    ) -> bool:
        """True se l'utente ha accesso valido (non scaduto) al livello richiesto."""
        c = self._cartelle.get(id_cliente)
        if not c:
            return False
        accesso = c.utente(id_utente)
        if not accesso or accesso.is_scaduto:
            return False
        return accesso.ruolo.include(richiesto)

    def ruolo_accesso(self, id_utente: str, id_cliente: str) -> Optional[RuoloCondivisione]:
        c = self._cartelle.get(id_cliente)
        if not c:
            return None
        accesso = c.utente(id_utente)
        if not accesso or accesso.is_scaduto:
            return None
        return accesso.ruolo

    # ================================================================ CARTELLE — Query

    def collaboratori_di(self, id_cliente: str) -> List[AccessoCondiviso]:
        c = self._cartelle.get(id_cliente)
        if not c:
            return []
        return sorted(c.accessi, key=lambda a: a.data_condivisione)

    def cartelle_condivise_con(self, id_utente: str) -> List[Tuple[str, AccessoCondiviso]]:
        risultato: List[Tuple[str, AccessoCondiviso]] = []
        for id_c, cond in self._cartelle.items():
            for a in cond.accessi:
                if a.id_utente == id_utente:
                    risultato.append((id_c, a))
                    break
        risultato.sort(key=lambda x: x[1].data_condivisione, reverse=True)
        return risultato

    def ids_clienti_accessibili(self, id_utente: str) -> Set[str]:
        """Set di id_cliente con accesso valido (non scaduto)."""
        return {
            id_c for id_c, a in self.cartelle_condivise_con(id_utente)
            if not a.is_scaduto
        }

    def clienti_condivisi_da(self, id_utente_gestore: str) -> List[str]:
        return [
            id_c for id_c, cond in self._cartelle.items()
            if any(a.id_utente == id_utente_gestore and a.ruolo == RuoloCondivisione.GESTORE
                   for a in cond.accessi)
        ]

    def n_collaboratori(self, id_cliente: str) -> int:
        c = self._cartelle.get(id_cliente)
        return len(c.accessi) if c else 0

    # ================================================================ #5 FASCICOLI — CRUD

    def condividi_fascicolo(
        self,
        id_fascicolo: str,
        id_cliente: str,
        id_utente: str,
        username: str,
        nome_completo: str,
        ruolo: RuoloCondivisione,
        condiviso_da: str,
        note: str = "",
        data_scadenza: str = "",
        tags: Optional[List[str]] = None,
    ) -> CondivisioneFascicolo:
        """Condivide un singolo fascicolo con un utente."""
        cf = self._get_o_crea_fascicolo(id_fascicolo, id_cliente)
        cf.accessi = [a for a in cf.accessi if a.id_utente != id_utente]
        cf.accessi.append(AccessoFascicolo(
            id_utente=id_utente,
            username=username,
            nome_completo=nome_completo,
            ruolo=ruolo,
            condiviso_da=condiviso_da,
            data_condivisione=datetime.now().isoformat(),
            note=note,
            data_scadenza=data_scadenza,
            tags=tags or [],
        ))
        cf.modificato_il = datetime.now().isoformat()
        self._salva()
        return cf

    def revoca_fascicolo(self, id_fascicolo: str, id_utente: str) -> bool:
        cf = self._fascicoli.get(id_fascicolo)
        if not cf:
            return False
        prima = len(cf.accessi)
        cf.accessi = [a for a in cf.accessi if a.id_utente != id_utente]
        rimosso = len(cf.accessi) < prima
        if rimosso:
            if not cf.accessi:
                del self._fascicoli[id_fascicolo]
            else:
                cf.modificato_il = datetime.now().isoformat()
            self._salva()
        return rimosso

    def ha_accesso_fascicolo(
        self,
        id_utente: str,
        id_fascicolo: str,
        richiesto: RuoloCondivisione = RuoloCondivisione.LETTURA,
    ) -> bool:
        cf = self._fascicoli.get(id_fascicolo)
        if not cf:
            return False
        accesso = cf.utente(id_utente)
        if not accesso or accesso.is_scaduto:
            return False
        return accesso.ruolo.include(richiesto)

    def fascicoli_condivisi_con(self, id_utente: str) -> List[Tuple[str, AccessoFascicolo]]:
        """Restituisce [(id_fascicolo, accesso)] per l'utente dato."""
        risultato: List[Tuple[str, AccessoFascicolo]] = []
        for id_f, cf in self._fascicoli.items():
            for a in cf.accessi:
                if a.id_utente == id_utente and not a.is_scaduto:
                    risultato.append((id_f, a))
                    break
        return sorted(risultato, key=lambda x: x[1].data_condivisione, reverse=True)

    def collaboratori_fascicolo(self, id_fascicolo: str) -> List[AccessoFascicolo]:
        cf = self._fascicoli.get(id_fascicolo)
        if not cf:
            return []
        return sorted(cf.accessi, key=lambda a: a.data_condivisione)

    def ids_fascicoli_accessibili(self, id_utente: str) -> Set[str]:
        return {id_f for id_f, _ in self.fascicoli_condivisi_con(id_utente)}

    # ================================================================ #6 LINK TEMPORANEI

    def _hash_token(self, token: str) -> str:
        return hmac.new(
            self._secret.encode(),
            token.encode(),
            hashlib.sha256,
        ).hexdigest()

    def crea_link_temporaneo(
        self,
        id_cliente: str,
        creato_da: str,
        ruolo: RuoloCondivisione = RuoloCondivisione.LETTURA,
        ore_validita: int = 72,
        id_fascicolo: str = "",
        monouso: bool = False,
        descrizione: str = "",
    ) -> Tuple[str, LinkTemporaneo]:
        """
        Crea un link di accesso temporaneo.
        Restituisce (token_grezzo, LinkTemporaneo).
        Il token grezzo va trasmesso all'esterno (mai il token_hash).
        """
        token = secrets.token_urlsafe(32)
        scade = datetime.now() + timedelta(hours=ore_validita)
        link = LinkTemporaneo(
            id=uuid.uuid4().hex[:8],
            token_hash=self._hash_token(token),
            id_cliente=id_cliente,
            id_fascicolo=id_fascicolo,
            ruolo=ruolo,
            scade_il=scade.isoformat(),
            creato_da=creato_da,
            creato_il=datetime.now().isoformat(),
            monouso=monouso,
            descrizione=descrizione,
        )
        self._link[link.id] = link
        self._salva()
        return token, link

    def verifica_link_temporaneo(self, token: str) -> Optional[LinkTemporaneo]:
        """
        Verifica un token grezzo.
        Restituisce LinkTemporaneo se valido, None altrimenti.
        Se monouso, lo marca come usato.
        """
        token_h = self._hash_token(token)
        for link in self._link.values():
            if hmac.compare_digest(link.token_hash, token_h):
                if not link.is_valido:
                    return None
                if link.monouso:
                    link.usato = True
                    self._salva()
                return link
        return None

    def revoca_link_temporaneo(self, id_link: str) -> bool:
        if id_link in self._link:
            del self._link[id_link]
            self._salva()
            return True
        return False

    def link_attivi_per_cliente(self, id_cliente: str) -> List[LinkTemporaneo]:
        return [
            l for l in self._link.values()
            if l.id_cliente == id_cliente and l.is_valido
        ]

    def pulisci_link_scaduti(self) -> int:
        """Rimuove link scaduti o monouso già usati. Restituisce il numero rimosso."""
        da_eliminare = [lid for lid, l in self._link.items() if not l.is_valido]
        for lid in da_eliminare:
            del self._link[lid]
        if da_eliminare:
            self._salva()
        return len(da_eliminare)

    # ================================================================ Statistiche

    def statistiche(self) -> dict:
        n_cartelle = len(self._cartelle)
        n_accessi = sum(len(c.accessi) for c in self._cartelle.values())
        per_ruolo: Dict[str, int] = {}
        for c in self._cartelle.values():
            for a in c.accessi:
                per_ruolo[a.ruolo.value] = per_ruolo.get(a.ruolo.value, 0) + 1

        top = sorted(
            [(id_c, len(c.accessi)) for id_c, c in self._cartelle.items()],
            key=lambda x: x[1], reverse=True,
        )[:5]

        n_scaduti = len(self.accessi_scaduti())
        n_in_scadenza = len(self.accessi_in_scadenza(entro_giorni=7))
        n_link_attivi = sum(1 for l in self._link.values() if l.is_valido)
        n_fascicoli_condivisi = len(self._fascicoli)

        return {
            "cartelle_condivise": n_cartelle,
            "accessi_totali": n_accessi,
            "per_ruolo": per_ruolo,
            "top_clienti": top,
            "accessi_scaduti": n_scaduti,
            "accessi_in_scadenza_7gg": n_in_scadenza,
            "link_temporanei_attivi": n_link_attivi,
            "fascicoli_condivisi": n_fascicoli_condivisi,
        }
