"""
Gestione anagrafica clienti dello studio legale.

Supporta persone fisiche e persone giuridiche (società/enti),
con recapiti, documento d'identità, note e storico procedimenti.
"""

import json
import re
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass, field, asdict
from enum import Enum


class TipoCliente(str, Enum):
    PERSONA_FISICA = "PERSONA_FISICA"
    PERSONA_GIURIDICA = "PERSONA_GIURIDICA"


class TipoDocumento(str, Enum):
    CARTA_IDENTITA = "CARTA_IDENTITA"
    PASSAPORTO = "PASSAPORTO"
    PATENTE = "PATENTE"
    PERMESSO_SOGGIORNO = "PERMESSO_SOGGIORNO"
    ALTRO = "ALTRO"


class StatoCliente(str, Enum):
    ATTIVO = "ATTIVO"
    INATTIVO = "INATTIVO"
    POTENZIALE = "POTENZIALE"
    ARCHIVIATO = "ARCHIVIATO"


# ------------------------------------------------------------------ sub-models

@dataclass
class Indirizzo:
    via: str = ""
    civico: str = ""
    cap: str = ""
    comune: str = ""
    provincia: str = ""
    nazione: str = "Italia"

    def __str__(self) -> str:
        parts = []
        if self.via:
            parts.append(f"{self.via} {self.civico}".strip())
        if self.cap or self.comune:
            parts.append(f"{self.cap} {self.comune} ({self.provincia})".strip(" ()"))
        if self.nazione and self.nazione != "Italia":
            parts.append(self.nazione)
        return ", ".join(p for p in parts if p)


@dataclass
class Recapiti:
    telefono: str = ""
    cellulare: str = ""
    email: str = ""
    pec: str = ""
    fax: str = ""
    sito_web: str = ""


@dataclass
class DocumentoIdentita:
    tipo: TipoDocumento = TipoDocumento.CARTA_IDENTITA
    numero: str = ""
    rilasciato_da: str = ""
    data_rilascio: str = ""     # YYYY-MM-DD
    data_scadenza: str = ""     # YYYY-MM-DD

    @property
    def scaduto(self) -> bool:
        if not self.data_scadenza:
            return False
        return date.fromisoformat(self.data_scadenza) < date.today()


@dataclass
class RiferimentoProcedimento:
    """Riferimento leggero a un procedimento collegato al cliente."""
    numero_rg: str
    anno: int
    tribunale: str
    descrizione: str = ""
    data_apertura: str = ""
    data_chiusura: str = ""
    attivo: bool = True


# ------------------------------------------------------------------ Cliente

@dataclass
class Cliente:
    """
    Anagrafica completa di un cliente dello studio legale.

    Gestisce sia persone fisiche che giuridiche con tutti i dati
    anagrafici, recapiti, documento d'identità e procedimenti collegati.
    """

    id: str
    tipo: TipoCliente
    stato: StatoCliente = StatoCliente.ATTIVO

    # --- Persona fisica
    nome: str = ""
    cognome: str = ""
    codice_fiscale: str = ""
    data_nascita: str = ""          # YYYY-MM-DD
    luogo_nascita: str = ""
    provincia_nascita: str = ""
    nazionalita: str = "Italiana"
    sesso: str = ""                 # M / F

    # --- Persona giuridica
    ragione_sociale: str = ""
    partita_iva: str = ""
    forma_giuridica: str = ""       # Srl, SpA, SAS, ecc.
    codice_ateco: str = ""
    data_costituzione: str = ""     # YYYY-MM-DD
    rappresentante_legale: str = ""
    cf_rappresentante: str = ""

    # --- Recapiti e indirizzi
    indirizzo_residenza: Indirizzo = field(default_factory=Indirizzo)
    indirizzo_domicilio: Indirizzo = field(default_factory=Indirizzo)
    indirizzo_sede_legale: Indirizzo = field(default_factory=Indirizzo)
    recapiti: Recapiti = field(default_factory=Recapiti)

    # --- Documento
    documento: DocumentoIdentita = field(default_factory=DocumentoIdentita)

    # --- Studio
    avvocato_referente: str = ""
    data_prima_acquisizione: str = field(
        default_factory=lambda: date.today().isoformat()
    )
    provenienza: str = ""           # passaparola, web, ecc.
    note: str = ""
    note_riservate: str = ""
    procedimenti: List[RiferimentoProcedimento] = field(default_factory=list)
    tag: List[str] = field(default_factory=list)

    # --- Metadati
    creato_il: str = field(default_factory=lambda: datetime.now().isoformat())
    modificato_il: str = field(default_factory=lambda: datetime.now().isoformat())

    # ---------------------------------------------------------------- props

    @property
    def nome_completo(self) -> str:
        if self.tipo == TipoCliente.PERSONA_GIURIDICA:
            return self.ragione_sociale
        return f"{self.cognome} {self.nome}".strip()

    @property
    def identificativo_fiscale(self) -> str:
        if self.tipo == TipoCliente.PERSONA_GIURIDICA:
            return self.partita_iva or self.codice_fiscale
        return self.codice_fiscale

    @property
    def eta(self) -> Optional[int]:
        if not self.data_nascita:
            return None
        nascita = date.fromisoformat(self.data_nascita)
        oggi = date.today()
        return oggi.year - nascita.year - (
            (oggi.month, oggi.day) < (nascita.month, nascita.day)
        )

    @property
    def procedimenti_attivi(self) -> List[RiferimentoProcedimento]:
        return [p for p in self.procedimenti if p.attivo]

    # ---------------------------------------------------------------- serde

    def to_dict(self) -> dict:
        d = asdict(self)
        d["tipo"] = self.tipo.value
        d["stato"] = self.stato.value
        if d.get("documento"):
            d["documento"]["tipo"] = self.documento.tipo.value
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Cliente":
        d = dict(d)
        d["tipo"] = TipoCliente(d["tipo"])
        d["stato"] = StatoCliente(d["stato"])

        for f_name, f_cls in [
            ("indirizzo_residenza", Indirizzo),
            ("indirizzo_domicilio", Indirizzo),
            ("indirizzo_sede_legale", Indirizzo),
        ]:
            if isinstance(d.get(f_name), dict):
                d[f_name] = f_cls(**d[f_name])

        if isinstance(d.get("recapiti"), dict):
            d["recapiti"] = Recapiti(**d["recapiti"])

        if isinstance(d.get("documento"), dict):
            doc = dict(d["documento"])
            doc["tipo"] = TipoDocumento(doc["tipo"])
            d["documento"] = DocumentoIdentita(**doc)

        if isinstance(d.get("procedimenti"), list):
            d["procedimenti"] = [
                RiferimentoProcedimento(**p) if isinstance(p, dict) else p
                for p in d["procedimenti"]
            ]

        return cls(**d)


# ------------------------------------------------------------------ Repository

class GestioneClienti:
    """
    Repository per la gestione dell'anagrafica clienti.
    Persistenza su file JSON locale.
    """

    def __init__(self, db_path: str = "./clienti/anagrafica.json"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._clienti: dict[str, Cliente] = {}
        self._carica()

    # ---------------------------------------------------------------- I/O

    def _carica(self) -> None:
        if self.db_path.exists():
            with open(self.db_path, encoding="utf-8") as f:
                raw = json.load(f)
            self._clienti = {k: Cliente.from_dict(v) for k, v in raw.items()}

    def _salva(self) -> None:
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(
                {k: v.to_dict() for k, v in self._clienti.items()},
                f,
                ensure_ascii=False,
                indent=2,
            )

    # ---------------------------------------------------------------- CRUD

    def nuovo(
        self,
        tipo: TipoCliente,
        *,
        nome: str = "",
        cognome: str = "",
        ragione_sociale: str = "",
        codice_fiscale: str = "",
        partita_iva: str = "",
        **kwargs,
    ) -> Cliente:
        """Crea un nuovo cliente."""
        if tipo == TipoCliente.PERSONA_FISICA and not (nome or cognome):
            raise ValueError("Nome o cognome obbligatorio per persona fisica.")
        if tipo == TipoCliente.PERSONA_GIURIDICA and not ragione_sociale:
            raise ValueError("Ragione sociale obbligatoria per persona giuridica.")

        if codice_fiscale:
            cf = codice_fiscale.upper().strip()
            if self._cerca_per_cf(cf):
                raise ValueError(f"Cliente con CF '{cf}' già presente.")
            codice_fiscale = cf

        cliente = Cliente(
            id=uuid.uuid4().hex[:8].upper(),
            tipo=tipo,
            nome=nome,
            cognome=cognome,
            ragione_sociale=ragione_sociale,
            codice_fiscale=codice_fiscale,
            partita_iva=partita_iva,
            **{k: v for k, v in kwargs.items() if hasattr(Cliente, k)},
        )
        self._clienti[cliente.id] = cliente
        self._salva()
        return cliente

    def aggiorna(self, id_cliente: str, **campi) -> Cliente:
        """Aggiorna i campi di un cliente."""
        c = self._get_o_errore(id_cliente)
        for k, v in campi.items():
            if hasattr(c, k):
                setattr(c, k, v)
        c.modificato_il = datetime.now().isoformat()
        self._salva()
        return c

    def aggiorna_indirizzo(
        self,
        id_cliente: str,
        tipo: str,   # residenza | domicilio | sede_legale
        **campi,
    ) -> Cliente:
        """Aggiorna un indirizzo del cliente."""
        c = self._get_o_errore(id_cliente)
        attr = f"indirizzo_{tipo}"
        ind: Indirizzo = getattr(c, attr)
        for k, v in campi.items():
            if hasattr(ind, k):
                setattr(ind, k, v)
        c.modificato_il = datetime.now().isoformat()
        self._salva()
        return c

    def aggiorna_recapiti(self, id_cliente: str, **campi) -> Cliente:
        c = self._get_o_errore(id_cliente)
        for k, v in campi.items():
            if hasattr(c.recapiti, k):
                setattr(c.recapiti, k, v)
        c.modificato_il = datetime.now().isoformat()
        self._salva()
        return c

    def aggiorna_documento(self, id_cliente: str, **campi) -> Cliente:
        c = self._get_o_errore(id_cliente)
        for k, v in campi.items():
            if hasattr(c.documento, k):
                setattr(c.documento, k, v)
        c.modificato_il = datetime.now().isoformat()
        self._salva()
        return c

    def aggiungi_procedimento(
        self, id_cliente: str, proc: RiferimentoProcedimento
    ) -> Cliente:
        c = self._get_o_errore(id_cliente)
        c.procedimenti.append(proc)
        c.modificato_il = datetime.now().isoformat()
        self._salva()
        return c

    def elimina(self, id_cliente: str) -> None:
        self._get_o_errore(id_cliente)
        del self._clienti[id_cliente]
        self._salva()

    def archivia(self, id_cliente: str) -> Cliente:
        return self.aggiorna(id_cliente, stato=StatoCliente.ARCHIVIATO)

    # ---------------------------------------------------------------- Query

    def get(self, id_cliente: str) -> Optional[Cliente]:
        return self._clienti.get(id_cliente)

    def tutti(
        self,
        stato: Optional[StatoCliente] = None,
        tipo: Optional[TipoCliente] = None,
    ) -> List[Cliente]:
        clienti = sorted(
            self._clienti.values(),
            key=lambda c: c.nome_completo.upper(),
        )
        if stato:
            clienti = [c for c in clienti if c.stato == stato]
        if tipo:
            clienti = [c for c in clienti if c.tipo == tipo]
        return clienti

    def cerca(
        self,
        testo: str = "",
        tipo: Optional[TipoCliente] = None,
        stato: Optional[StatoCliente] = None,
        avvocato: Optional[str] = None,
        tag: Optional[str] = None,
    ) -> List[Cliente]:
        """Ricerca full-text su nome, CF, P.IVA, email, procedimento."""
        risultati = self.tutti(stato=stato, tipo=tipo)

        if testo:
            t = testo.lower()
            risultati = [
                c for c in risultati
                if t in c.nome_completo.lower()
                or t in c.codice_fiscale.lower()
                or t in c.partita_iva.lower()
                or t in c.recapiti.email.lower()
                or t in c.recapiti.pec.lower()
                or t in c.recapiti.telefono
                or t in c.recapiti.cellulare
                or any(t in p.numero_rg.lower() for p in c.procedimenti)
                or t in c.note.lower()
            ]

        if avvocato:
            risultati = [
                c for c in risultati
                if avvocato.lower() in c.avvocato_referente.lower()
            ]
        if tag:
            risultati = [c for c in risultati if tag in c.tag]

        return risultati

    def statistiche(self) -> dict:
        tutti = list(self._clienti.values())
        return {
            "totale": len(tutti),
            "per_tipo": {
                t.value: sum(1 for c in tutti if c.tipo == t)
                for t in TipoCliente
            },
            "per_stato": {
                s.value: sum(1 for c in tutti if c.stato == s)
                for s in StatoCliente
            },
            "con_procedimenti_attivi": sum(
                1 for c in tutti if c.procedimenti_attivi
            ),
            "documenti_scaduti": sum(
                1 for c in tutti if c.documento.scaduto
            ),
        }

    # ---------------------------------------------------------------- utils

    def _get_o_errore(self, id_cliente: str) -> Cliente:
        c = self._clienti.get(id_cliente)
        if not c:
            raise KeyError(f"Cliente '{id_cliente}' non trovato.")
        return c

    def _cerca_per_cf(self, cf: str) -> Optional[Cliente]:
        for c in self._clienti.values():
            if c.codice_fiscale.upper() == cf.upper():
                return c
        return None

    @staticmethod
    def valida_cf(cf: str) -> bool:
        """Validazione sintattica del codice fiscale italiano (16 char)."""
        pattern = r"^[A-Z]{6}[0-9LMNPQRSTUV]{2}[ABCDEHLMPRST]{1}[0-9LMNPQRSTUV]{2}[A-Z]{1}[0-9LMNPQRSTUV]{3}[A-Z]{1}$"
        return bool(re.match(pattern, cf.upper()))

    @staticmethod
    def valida_piva(piva: str) -> bool:
        """Validazione sintattica della partita IVA italiana (11 cifre)."""
        return bool(re.match(r"^\d{11}$", piva.strip()))
