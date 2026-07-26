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

    # --- Consenso trattamento dati (GDPR)
    consenso_trattamento: bool = False
    data_consenso: str = ""           # YYYY-MM-DD
    modalita_consenso: str = ""       # cartaceo | email | digitale | orale

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

    @property
    def profilo_minimo_per_preventivo(self) -> bool:
        if self.tipo == TipoCliente.PERSONA_GIURIDICA:
            return bool(self.ragione_sociale and (self.partita_iva or self.codice_fiscale))
        return bool(self.nome and self.cognome and self.codice_fiscale)

    @property
    def campi_mancanti_per_conferimento(self) -> List[str]:
        mancanti: List[str] = []
        recapito_presente = any([
            self.recapiti.telefono,
            self.recapiti.cellulare,
            self.recapiti.email,
            self.recapiti.pec,
        ])
        if self.tipo == TipoCliente.PERSONA_GIURIDICA:
            if not self.ragione_sociale:
                mancanti.append("ragione sociale")
            if not (self.partita_iva or self.codice_fiscale):
                mancanti.append("partita IVA o codice fiscale")
            if not self.indirizzo_sede_legale.via or not self.indirizzo_sede_legale.comune:
                mancanti.append("sede legale")
            if not recapito_presente:
                mancanti.append("almeno un recapito")
            return mancanti

        if not self.nome:
            mancanti.append("nome")
        if not self.cognome:
            mancanti.append("cognome")
        if not self.codice_fiscale:
            mancanti.append("codice fiscale")
        if not self.indirizzo_residenza.via or not self.indirizzo_residenza.comune:
            mancanti.append("residenza")
        if not recapito_presente:
            mancanti.append("almeno un recapito")
        return mancanti

    @property
    def profilo_completo_per_conferimento(self) -> bool:
        return not self.campi_mancanti_per_conferimento

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
            rec = dict(d["recapiti"])
            if "email" not in rec and "email_principale" in rec:
                rec["email"] = rec.get("email_principale", "")
            if "telefono" not in rec and "telefono_principale" in rec:
                rec["telefono"] = rec.get("telefono_principale", "")
            d["recapiti"] = Recapiti(**{k: v for k, v in rec.items() if k in Recapiti.__dataclass_fields__})

        if isinstance(d.get("documento"), dict):
            doc = dict(d["documento"])
            doc["tipo"] = TipoDocumento(doc["tipo"])
            d["documento"] = DocumentoIdentita(
                **{k: v for k, v in doc.items() if k in DocumentoIdentita.__dataclass_fields__}
            )

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

    def __init__(
        self,
        db_path: str = "./clienti/anagrafica.json",
        studio_db=None,
    ):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._studio_db = studio_db
        self._clienti: dict[str, Cliente] = {}
        self._carica()

    # ---------------------------------------------------------------- I/O

    def _carica(self) -> None:
        if self._studio_db is not None:
            rows = self._studio_db.carica_tabella("clienti")
            self._clienti = {}
            for d in rows:
                try:
                    c = Cliente.from_dict(d)
                    self._clienti[c.id] = c
                except Exception:
                    pass
            return
        from pct import cache as _cache
        raw = _cache.load(self.db_path)
        if isinstance(raw, dict):
            payloads = raw.values()
        elif isinstance(raw, list):
            payloads = raw
        else:
            payloads = []
        self._clienti = {}
        for payload in payloads:
            try:
                cliente = Cliente.from_dict(payload)
            except Exception:
                continue
            self._clienti[cliente.id] = cliente

    def _salva(self) -> None:
        if self._studio_db is not None:
            import json as _json
            def _insert(conn, c):
                d = c.to_dict()
                rec = d.get("recapiti") or {}
                conn.execute("""
                    INSERT INTO clienti
                    (id, tipo, stato, cognome, nome, ragione_sociale,
                     codice_fiscale, partita_iva, email, telefono, note,
                     creato_il, modificato_il, dati_json)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    c.id, c.tipo.value, c.stato.value,
                    c.cognome, c.nome, c.ragione_sociale,
                    c.codice_fiscale, c.partita_iva,
                    rec.get("email", "") if isinstance(rec, dict) else "",
                    rec.get("telefono", "") if isinstance(rec, dict) else "",
                    c.note, c.creato_il,
                    __import__("datetime").datetime.now().isoformat(),
                    _json.dumps(d, ensure_ascii=False),
                ))
            self._studio_db.salva_tabella("clienti", list(self._clienti.values()), _insert)
            return
        from pct import cache as _cache
        _cache.save(self.db_path, {k: v.to_dict() for k, v in self._clienti.items()})

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
            if not self.valida_cf(cf):
                raise ValueError("Codice fiscale non valido.")
            if self._cerca_per_cf(cf):
                raise ValueError(f"Cliente con CF '{cf}' già presente.")
            codice_fiscale = cf
        if partita_iva:
            piva = partita_iva.strip()
            if not self.valida_piva(piva):
                raise ValueError("Partita IVA non valida.")
            partita_iva = piva

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
        if "codice_fiscale" in campi:
            cf = str(campi.get("codice_fiscale") or "").strip().upper()
            if cf:
                if not self.valida_cf(cf):
                    raise ValueError("Codice fiscale non valido.")
                existing = self._cerca_per_cf(cf)
                if existing and existing.id != c.id:
                    raise ValueError(f"Cliente con CF '{cf}' già presente.")
            campi["codice_fiscale"] = cf
        if "partita_iva" in campi:
            piva = str(campi.get("partita_iva") or "").strip()
            if piva and not self.valida_piva(piva):
                raise ValueError("Partita IVA non valida.")
            campi["partita_iva"] = piva
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

    def get_by_codice_fiscale(self, cf: str) -> Optional[Cliente]:
        cf = (cf or "").strip().upper()
        if not cf:
            return None
        return self._cerca_per_cf(cf)

    def get_by_partita_iva(self, piva: str) -> Optional[Cliente]:
        piva = (piva or "").strip()
        if not piva:
            return None
        for c in self._clienti.values():
            if (c.partita_iva or "").strip() == piva:
                return c
        return None

    def crea_o_recupera_potenziale(
        self,
        *,
        tipo: TipoCliente,
        nome: str = "",
        cognome: str = "",
        ragione_sociale: str = "",
        codice_fiscale: str = "",
        partita_iva: str = "",
        provenienza: str = "Preventivo guidato",
        avvocato_referente: str = "",
        note: str = "",
    ) -> tuple[Cliente, bool]:
        codice_fiscale = (codice_fiscale or "").strip().upper()
        partita_iva = (partita_iva or "").strip()

        if tipo == TipoCliente.PERSONA_FISICA:
            if not nome.strip() or not cognome.strip():
                raise ValueError("Per il cliente rapido inserisci nome e cognome.")
            if not codice_fiscale:
                raise ValueError("Per il cliente rapido inserisci il codice fiscale.")
            if not self.valida_cf(codice_fiscale):
                raise ValueError("Il codice fiscale rapido non ha un formato valido.")
            esistente = self.get_by_codice_fiscale(codice_fiscale)
            if esistente:
                return esistente, False
            cliente = self.nuovo(
                tipo=tipo,
                nome=nome.strip(),
                cognome=cognome.strip(),
                codice_fiscale=codice_fiscale,
                stato=StatoCliente.POTENZIALE,
                provenienza=provenienza,
                avvocato_referente=avvocato_referente,
                note=note.strip(),
            )
            return cliente, True

        if not ragione_sociale.strip():
            raise ValueError("Per il cliente rapido persona giuridica inserisci la ragione sociale.")
        if not partita_iva and not codice_fiscale:
            raise ValueError("Per il cliente rapido persona giuridica inserisci partita IVA oppure codice fiscale.")
        if partita_iva and not self.valida_piva(partita_iva):
            raise ValueError("La partita IVA rapida non ha un formato valido.")
        if codice_fiscale and len(codice_fiscale) not in {11, 16}:
            raise ValueError("Il codice fiscale della persona giuridica non ha un formato valido.")
        esistente = None
        if partita_iva:
            esistente = self.get_by_partita_iva(partita_iva)
        if not esistente and codice_fiscale:
            esistente = self.get_by_codice_fiscale(codice_fiscale)
        if esistente:
            return esistente, False
        cliente = self.nuovo(
            tipo=tipo,
            ragione_sociale=ragione_sociale.strip(),
            codice_fiscale=codice_fiscale,
            partita_iva=partita_iva,
            stato=StatoCliente.POTENZIALE,
            provenienza=provenienza,
            avvocato_referente=avvocato_referente,
            note=note.strip(),
        )
        return cliente, True

    @staticmethod
    def valida_cf(cf: str) -> bool:
        """Validazione sintattica del codice fiscale italiano (16 char)."""
        pattern = r"^[A-Z]{6}[0-9LMNPQRSTUV]{2}[ABCDEHLMPRST]{1}[0-9LMNPQRSTUV]{2}[A-Z]{1}[0-9LMNPQRSTUV]{3}[A-Z]{1}$"
        return bool(re.match(pattern, cf.upper()))

    @staticmethod
    def valida_piva(piva: str) -> bool:
        """Validazione sintattica della partita IVA italiana (11 cifre)."""
        return bool(re.match(r"^\d{11}$", piva.strip()))
