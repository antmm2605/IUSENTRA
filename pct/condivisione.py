"""
Gestione condivisione cartelle clienti tra collaboratori.

Ogni cartella cliente può essere condivisa con utenti specifici
con tre livelli di accesso:
  - LETTURA   — visualizza cliente, fascicoli, documenti
  - SCRITTURA — tutto sopra + modifica cliente/fascicoli/upload documenti
  - GESTORE   — tutto sopra + gestisce i collaboratori della cartella

Gli utenti con il permesso globale 'clienti.leggi' (Avvocati, Amministratori)
vedono sempre TUTTE le cartelle. Questo meccanismo si applica ai ruoli
con accesso ristretto (Collaboratori, Praticanti, Segreteria, Contabili).
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


# ================================================================ Enums

class RuoloCondivisione(str, Enum):
    LETTURA   = "LETTURA"   # solo visualizzazione
    SCRITTURA = "SCRITTURA" # visualizzazione + modifica
    GESTORE   = "GESTORE"   # scrittura + gestione collaboratori

    # Ordine gerarchico: LETTURA < SCRITTURA < GESTORE
    def include(self, altro: "RuoloCondivisione") -> bool:
        """Restituisce True se questo ruolo contiene i permessi di 'altro'."""
        ordine = [RuoloCondivisione.LETTURA, RuoloCondivisione.SCRITTURA, RuoloCondivisione.GESTORE]
        return ordine.index(self) >= ordine.index(altro)


# ================================================================ Dataclasses

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
        )

    def to_dict(self) -> dict:
        d = asdict(self)
        d["ruolo"] = self.ruolo.value
        return d


@dataclass
class CondivisioneCartella:
    """
    Registro delle condivisioni per una cartella cliente.
    Una per ogni cliente che ha almeno un collaboratore associato.
    """
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
        """Restituisce l'accesso dell'utente se presente, altrimenti None."""
        for a in self.accessi:
            if a.id_utente == id_utente:
                return a
        return None


# ================================================================ Manager

class GestioneCondivisioni:
    """
    Gestione persistente delle condivisioni cartelle-clienti.

    Persistenza: file JSON con struttura {id_cliente: CondivisioneCartella}.
    """

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        # id_cliente → CondivisioneCartella
        self._condivisioni: Dict[str, CondivisioneCartella] = {}
        self._carica()

    # ---------------------------------------------------------------- I/O

    def _carica(self) -> None:
        if not self.db_path.exists():
            return
        try:
            raw = json.loads(self.db_path.read_text(encoding="utf-8"))
            self._condivisioni = {
                k: CondivisioneCartella.from_dict(v) for k, v in raw.items()
            }
        except (json.JSONDecodeError, KeyError):
            self._condivisioni = {}

    def _salva(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path.write_text(
            json.dumps(
                {k: v.to_dict() for k, v in self._condivisioni.items()},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def _get_o_crea(self, id_cliente: str) -> CondivisioneCartella:
        if id_cliente not in self._condivisioni:
            self._condivisioni[id_cliente] = CondivisioneCartella(
                id=uuid.uuid4().hex[:8],
                id_cliente=id_cliente,
                creato_il=datetime.now().isoformat(),
                modificato_il=datetime.now().isoformat(),
            )
        return self._condivisioni[id_cliente]

    # ---------------------------------------------------------------- CRUD condivisioni

    def condividi(
        self,
        id_cliente: str,
        id_utente: str,
        username: str,
        nome_completo: str,
        ruolo: RuoloCondivisione,
        condiviso_da: str,
        note: str = "",
    ) -> CondivisioneCartella:
        """
        Aggiunge o aggiorna l'accesso di un utente alla cartella di un cliente.
        Se l'utente era già presente, aggiorna il ruolo.
        """
        c = self._get_o_crea(id_cliente)
        # Rimuovi accesso precedente (se presente) per aggiornarlo
        c.accessi = [a for a in c.accessi if a.id_utente != id_utente]
        c.accessi.append(AccessoCondiviso(
            id_utente=id_utente,
            username=username,
            nome_completo=nome_completo,
            ruolo=ruolo,
            condiviso_da=condiviso_da,
            data_condivisione=datetime.now().isoformat(),
            note=note,
        ))
        c.modificato_il = datetime.now().isoformat()
        self._salva()
        return c

    def revoca(self, id_cliente: str, id_utente: str) -> bool:
        """
        Rimuove l'accesso di un utente alla cartella.
        Se non rimangono altri accessi, elimina il record di condivisione.
        Restituisce True se l'accesso esisteva ed è stato rimosso.
        """
        if id_cliente not in self._condivisioni:
            return False
        c = self._condivisioni[id_cliente]
        prima = len(c.accessi)
        c.accessi = [a for a in c.accessi if a.id_utente != id_utente]
        rimosso = len(c.accessi) < prima
        if rimosso:
            if not c.accessi:
                del self._condivisioni[id_cliente]
            else:
                c.modificato_il = datetime.now().isoformat()
            self._salva()
        return rimosso

    def revoca_tutti(self, id_cliente: str) -> int:
        """Rimuove TUTTI gli accessi a una cartella. Restituisce il numero rimosso."""
        c = self._condivisioni.pop(id_cliente, None)
        if c:
            n = len(c.accessi)
            self._salva()
            return n
        return 0

    # ---------------------------------------------------------------- Controllo accesso

    def ha_accesso(
        self,
        id_utente: str,
        id_cliente: str,
        richiesto: RuoloCondivisione = RuoloCondivisione.LETTURA,
    ) -> bool:
        """
        Verifica se un utente ha accesso a una cartella con almeno il livello richiesto.
        """
        c = self._condivisioni.get(id_cliente)
        if not c:
            return False
        accesso = c.utente(id_utente)
        if not accesso:
            return False
        return accesso.ruolo.include(richiesto)

    def ruolo_accesso(
        self, id_utente: str, id_cliente: str
    ) -> Optional[RuoloCondivisione]:
        """Restituisce il ruolo di condivisione dell'utente per il cliente."""
        c = self._condivisioni.get(id_cliente)
        if not c:
            return None
        accesso = c.utente(id_utente)
        return accesso.ruolo if accesso else None

    # ---------------------------------------------------------------- Query

    def collaboratori_di(self, id_cliente: str) -> List[AccessoCondiviso]:
        """Restituisce i collaboratori di una cartella cliente, ordinati per data."""
        c = self._condivisioni.get(id_cliente)
        if not c:
            return []
        return sorted(c.accessi, key=lambda a: a.data_condivisione)

    def cartelle_condivise_con(
        self, id_utente: str
    ) -> List[Tuple[str, AccessoCondiviso]]:
        """
        Restituisce le cartelle condivise con un utente:
        lista di (id_cliente, AccessoCondiviso) ordinata per data decrescente.
        """
        risultato: List[Tuple[str, AccessoCondiviso]] = []
        for id_c, cond in self._condivisioni.items():
            for a in cond.accessi:
                if a.id_utente == id_utente:
                    risultato.append((id_c, a))
                    break
        risultato.sort(key=lambda x: x[1].data_condivisione, reverse=True)
        return risultato

    def ids_clienti_accessibili(self, id_utente: str) -> Set[str]:
        """Set di id_cliente a cui l'utente ha accesso via condivisione."""
        return {id_c for id_c, _ in self.cartelle_condivise_con(id_utente)}

    def clienti_condivisi_da(self, id_utente_gestore: str) -> List[str]:
        """
        Restituisce gli id_cliente per cui l'utente è GESTORE
        (quindi può gestire le condivisioni).
        """
        ids = []
        for id_c, cond in self._condivisioni.items():
            for a in cond.accessi:
                if a.id_utente == id_utente_gestore and a.ruolo == RuoloCondivisione.GESTORE:
                    ids.append(id_c)
        return ids

    def n_collaboratori(self, id_cliente: str) -> int:
        """Numero di collaboratori con accesso alla cartella."""
        c = self._condivisioni.get(id_cliente)
        return len(c.accessi) if c else 0

    # ---------------------------------------------------------------- Statistiche

    def statistiche(self) -> dict:
        n_cartelle = len(self._condivisioni)
        n_accessi = sum(len(c.accessi) for c in self._condivisioni.values())
        per_ruolo: Dict[str, int] = {}
        for c in self._condivisioni.values():
            for a in c.accessi:
                per_ruolo[a.ruolo.value] = per_ruolo.get(a.ruolo.value, 0) + 1
        # Clienti più condivisi (top 5)
        top = sorted(
            [(id_c, len(c.accessi)) for id_c, c in self._condivisioni.items()],
            key=lambda x: x[1],
            reverse=True,
        )[:5]
        return {
            "cartelle_condivise": n_cartelle,
            "accessi_totali": n_accessi,
            "per_ruolo": per_ruolo,
            "top_clienti": top,
        }
