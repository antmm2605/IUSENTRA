"""
Gestione fascicoli (cartelle legali) dello studio.

Ogni fascicolo è legato a un cliente e raccoglie:
- Documenti (atti, allegati, comunicazioni, parcelle)
- Attività processuali (udienze, depositi, notifiche, scadenze)
- Stato di avanzamento della pratica
- Archivio con export ZIP quando la pratica è definita
"""

import json
import uuid
import zipfile
import hashlib
import shutil
from datetime import date, datetime
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass, field, asdict
from enum import Enum


# ------------------------------------------------------------------ Enums

class TipoFascicolo(str, Enum):
    CIVILE          = "CIVILE"
    PENALE          = "PENALE"
    AMMINISTRATIVO  = "AMMINISTRATIVO"
    STRAGIUDIZIALE  = "STRAGIUDIZIALE"
    CONSULENZA      = "CONSULENZA"
    LAVORO          = "LAVORO"
    FAMIGLIA        = "FAMIGLIA"
    SUCCESSIONI     = "SUCCESSIONI"
    ALTRO           = "ALTRO"


class StatoFascicolo(str, Enum):
    APERTO          = "APERTO"       # pratica in corso
    IN_CORSO        = "IN_CORSO"     # attività processuali avviate
    SOSPESO         = "SOSPESO"      # temporaneamente inattivo
    DEFINITO        = "DEFINITO"     # causa conclusa, pronto per archivio
    ARCHIVIATO      = "ARCHIVIATO"   # archiviato definitivamente


class TipoDocumento(str, Enum):
    ATTO_GIUDIZIARIO    = "ATTO_GIUDIZIARIO"
    MEMORIA             = "MEMORIA"
    RICORSO             = "RICORSO"
    CITAZIONE           = "CITAZIONE"
    COMPARSA            = "COMPARSA"
    SENTENZA            = "SENTENZA"
    ORDINANZA           = "ORDINANZA"
    DECRETO             = "DECRETO"
    CONTRATTO           = "CONTRATTO"
    PROCURA             = "PROCURA"
    PARCELLA            = "PARCELLA"
    COMUNICAZIONE       = "COMUNICAZIONE"
    ALLEGATO            = "ALLEGATO"
    DEPOSITO_PCT        = "DEPOSITO_PCT"
    NOTIFICA            = "NOTIFICA"
    VERBALE             = "VERBALE"
    ALTRO               = "ALTRO"


class TipoAttivita(str, Enum):
    UDIENZA             = "UDIENZA"
    DEPOSITO_ATTI       = "DEPOSITO_ATTI"
    NOTIFICA            = "NOTIFICA"
    CONSULTAZIONE       = "CONSULTAZIONE"
    TERMINE_SCADENZA    = "TERMINE_SCADENZA"
    ACCESSO_ATTI        = "ACCESSO_ATTI"
    MEDIAZIONE          = "MEDIAZIONE"
    CTU                 = "CTU"
    SENTENZA_EMESSA     = "SENTENZA_EMESSA"
    APPELLO             = "APPELLO"
    ESECUZIONE          = "ESECUZIONE"
    ACCORDO             = "ACCORDO"
    RINVIO              = "RINVIO"
    ALTRO               = "ALTRO"


class EsitoAttivita(str, Enum):
    IN_ATTESA       = "IN_ATTESA"
    FAVOREVOLE      = "FAVOREVOLE"
    PARZIALE        = "PARZIALE"
    SFAVOREVOLE     = "SFAVOREVOLE"
    RINVIATO        = "RINVIATO"
    ANNULLATO       = "ANNULLATO"
    NON_APPLICABILE = "NON_APPLICABILE"


# ------------------------------------------------------------------ Sub-modelli

@dataclass
class Documento:
    """Documento allegato al fascicolo."""
    id: str
    nome: str
    tipo: TipoDocumento
    percorso: str                  # path relativo a documents_dir
    dimensione_bytes: int = 0
    hash_sha256: str = ""
    firmato_digitalmente: bool = False
    data_caricamento: str = field(default_factory=lambda: datetime.now().isoformat())
    data_documento: str = ""       # data del documento (es. data atto)
    note: str = ""
    id_deposito_pct: str = ""      # collegamento a deposito PCT
    caricato_da: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["tipo"] = self.tipo.value
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Documento":
        d = dict(d)
        d["tipo"] = TipoDocumento(d["tipo"])
        return cls(**d)


@dataclass
class AttivitaProcessuale:
    """Singola attività processuale nel fascicolo."""
    id: str
    tipo: TipoAttivita
    data: str                       # YYYY-MM-DD
    titolo: str
    descrizione: str = ""
    esito: EsitoAttivita = EsitoAttivita.IN_ATTESA
    luogo: str = ""
    note: str = ""
    id_appuntamento: str = ""       # collegamento agenda
    id_deposito_pct: str = ""       # collegamento deposito PCT
    id_documento: str = ""          # documento risultante
    avvocato: str = ""
    creato_il: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        d = asdict(self)
        d["tipo"] = self.tipo.value
        d["esito"] = self.esito.value
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "AttivitaProcessuale":
        d = dict(d)
        d["tipo"] = TipoAttivita(d["tipo"])
        d["esito"] = EsitoAttivita(d["esito"])
        return cls(**d)


@dataclass
class AvanzamentoPratica:
    """Milestone di avanzamento della pratica."""
    data: str
    descrizione: str
    stato_precedente: str
    stato_nuovo: str
    note: str = ""
    avvocato: str = ""


@dataclass
class DatiArchivio:
    """Dati di archiviazione del fascicolo."""
    data_archiviazione: str
    motivo: str = ""                # accordo, sentenza, rinuncia…
    esito_finale: str = ""          # favorevole, sfavorevole, parziale
    note_archivio: str = ""
    percorso_zip: str = ""          # path dell'archivio ZIP
    hash_zip: str = ""
    archiviato_da: str = ""


# ------------------------------------------------------------------ Fascicolo

@dataclass
class Fascicolo:
    """Fascicolo / cartella legale dello studio."""

    id: str
    numero: str                     # numero progressivo (es. "2024/001")
    titolo: str
    tipo: TipoFascicolo
    stato: StatoFascicolo = StatoFascicolo.APERTO

    # --- Cliente
    id_cliente: str = ""
    nome_cliente: str = ""          # denormalizzato per visualizzazione rapida

    # --- Controparte
    controparte: str = ""
    cf_controparte: str = ""

    # --- Dati processuali
    tribunale: str = ""
    numero_rg: str = ""
    anno_rg: int = 0
    giudice: str = ""
    sezione: str = ""

    # --- Studio
    avvocato_referente: str = ""
    avvocato_dominus: str = ""
    oggetto: str = ""
    valore_causa: float = 0.0       # valore in euro

    # --- Date
    data_apertura: str = field(default_factory=lambda: date.today().isoformat())
    data_chiusura: str = ""
    data_prima_udienza: str = ""
    data_prossima_udienza: str = ""

    # --- Contenuto
    documenti: List[Documento] = field(default_factory=list)
    attivita: List[AttivitaProcessuale] = field(default_factory=list)
    avanzamento: List[AvanzamentoPratica] = field(default_factory=list)
    note: str = ""
    note_riservate: str = ""

    # --- Archivio
    archivio: Optional[DatiArchivio] = None

    # --- Metadati
    creato_il: str = field(default_factory=lambda: datetime.now().isoformat())
    modificato_il: str = field(default_factory=lambda: datetime.now().isoformat())

    # ---------------------------------------------------------------- Props

    @property
    def rg_completo(self) -> str:
        if self.numero_rg and self.anno_rg:
            return f"RG {self.numero_rg}/{self.anno_rg}"
        return self.numero_rg or ""

    @property
    def documenti_count(self) -> int:
        return len(self.documenti)

    @property
    def attivita_count(self) -> int:
        return len(self.attivita)

    @property
    def ultima_attivita(self) -> Optional[AttivitaProcessuale]:
        if not self.attivita:
            return None
        return max(self.attivita, key=lambda a: a.data)

    @property
    def prossima_scadenza(self) -> Optional[AttivitaProcessuale]:
        oggi = date.today().isoformat()
        future = [
            a for a in self.attivita
            if a.data >= oggi and a.esito == EsitoAttivita.IN_ATTESA
        ]
        return min(future, key=lambda a: a.data) if future else None

    @property
    def archivio_pronto(self) -> bool:
        return self.stato == StatoFascicolo.DEFINITO

    # ---------------------------------------------------------------- Serde

    def to_dict(self) -> dict:
        d = asdict(self)
        d["tipo"] = self.tipo.value
        d["stato"] = self.stato.value
        d["documenti"] = [doc.to_dict() for doc in self.documenti]
        d["attivita"] = [att.to_dict() for att in self.attivita]
        if self.archivio:
            d["archivio"] = asdict(self.archivio)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Fascicolo":
        d = dict(d)
        d["tipo"] = TipoFascicolo(d["tipo"])
        d["stato"] = StatoFascicolo(d["stato"])
        d["documenti"] = [
            Documento.from_dict(doc) for doc in (d.get("documenti") or [])
        ]
        d["attivita"] = [
            AttivitaProcessuale.from_dict(att) for att in (d.get("attivita") or [])
        ]
        d["avanzamento"] = [
            AvanzamentoPratica(**av) for av in (d.get("avanzamento") or [])
        ]
        arch = d.get("archivio")
        d["archivio"] = DatiArchivio(**arch) if arch else None
        return cls(**d)


# ------------------------------------------------------------------ Repository

class GestioneFascicoli:
    """
    Repository per la gestione dei fascicoli dello studio.

    - Persistenza JSON + file system per i documenti
    - Tracciamento automatico avanzamento stato
    - Archiviazione con export ZIP
    """

    def __init__(
        self,
        db_path: str = "./fascicoli/fascicoli.json",
        documents_dir: str = "./fascicoli/documenti",
        archive_dir: str = "./fascicoli/archivio",
    ):
        self.db_path = Path(db_path)
        self.documents_dir = Path(documents_dir)
        self.archive_dir = Path(archive_dir)
        for d in (self.db_path.parent, self.documents_dir, self.archive_dir):
            d.mkdir(parents=True, exist_ok=True)
        self._fascicoli: dict[str, Fascicolo] = {}
        self._carica()

    # ---------------------------------------------------------------- I/O

    def _carica(self) -> None:
        if self.db_path.exists():
            with open(self.db_path, encoding="utf-8") as f:
                raw = json.load(f)
            self._fascicoli = {k: Fascicolo.from_dict(v) for k, v in raw.items()}

    def _salva(self) -> None:
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(
                {k: v.to_dict() for k, v in self._fascicoli.items()},
                f,
                ensure_ascii=False,
                indent=2,
            )

    # ---------------------------------------------------------------- Numeri

    def _prossimo_numero(self) -> str:
        anno = date.today().year
        esistenti = [
            f.numero for f in self._fascicoli.values()
            if f.numero.startswith(str(anno))
        ]
        seq = len(esistenti) + 1
        return f"{anno}/{seq:03d}"

    # ---------------------------------------------------------------- CRUD fascicolo

    def nuovo(
        self,
        titolo: str,
        tipo: TipoFascicolo,
        id_cliente: str = "",
        nome_cliente: str = "",
        **kwargs,
    ) -> Fascicolo:
        """Crea un nuovo fascicolo."""
        if not titolo.strip():
            raise ValueError("Il titolo del fascicolo è obbligatorio.")
        f = Fascicolo(
            id=uuid.uuid4().hex[:8].upper(),
            numero=self._prossimo_numero(),
            titolo=titolo,
            tipo=tipo,
            id_cliente=id_cliente,
            nome_cliente=nome_cliente,
            **{k: v for k, v in kwargs.items() if hasattr(Fascicolo, k)},
        )
        self._fascicoli[f.id] = f
        self._salva()
        return f

    def aggiorna(self, id_fasc: str, **campi) -> Fascicolo:
        f = self._get_o_errore(id_fasc)
        for k, v in campi.items():
            if hasattr(f, k):
                setattr(f, k, v)
        f.modificato_il = datetime.now().isoformat()
        self._salva()
        return f

    def elimina(self, id_fasc: str) -> None:
        f = self._get_o_errore(id_fasc)
        # elimina documenti fisici
        fasc_dir = self.documents_dir / id_fasc
        if fasc_dir.exists():
            shutil.rmtree(fasc_dir)
        del self._fascicoli[id_fasc]
        self._salva()

    # ---------------------------------------------------------------- Stato

    def cambia_stato(
        self,
        id_fasc: str,
        nuovo_stato: StatoFascicolo,
        note: str = "",
        avvocato: str = "",
    ) -> Fascicolo:
        """
        Cambia lo stato del fascicolo e registra l'avanzamento.
        Se lo stato diventa DEFINITO, registra la data di chiusura.
        """
        f = self._get_o_errore(id_fasc)
        stato_prev = f.stato.value

        f.stato = nuovo_stato
        if nuovo_stato in (StatoFascicolo.DEFINITO, StatoFascicolo.ARCHIVIATO):
            if not f.data_chiusura:
                f.data_chiusura = date.today().isoformat()

        av = AvanzamentoPratica(
            data=datetime.now().isoformat(),
            descrizione=f"Stato cambiato da {stato_prev} a {nuovo_stato.value}",
            stato_precedente=stato_prev,
            stato_nuovo=nuovo_stato.value,
            note=note,
            avvocato=avvocato,
        )
        f.avanzamento.append(av)
        f.modificato_il = datetime.now().isoformat()
        self._salva()
        return f

    # ---------------------------------------------------------------- Documenti

    def aggiungi_documento(
        self,
        id_fasc: str,
        nome_file: str,
        tipo: TipoDocumento,
        contenuto: bytes,
        note: str = "",
        data_documento: str = "",
        firmato: bool = False,
        caricato_da: str = "",
        id_deposito_pct: str = "",
    ) -> Documento:
        """
        Aggiunge un documento al fascicolo salvandolo su disco.

        Returns:
            Documento creato
        """
        f = self._get_o_errore(id_fasc)
        fasc_dir = self.documents_dir / id_fasc
        fasc_dir.mkdir(parents=True, exist_ok=True)

        # evita collisioni di nome
        nome_safe = Path(nome_file).name
        dest = fasc_dir / nome_safe
        if dest.exists():
            stem = Path(nome_safe).stem
            suffix = Path(nome_safe).suffix
            nome_safe = f"{stem}_{uuid.uuid4().hex[:4]}{suffix}"
            dest = fasc_dir / nome_safe

        dest.write_bytes(contenuto)
        sha256 = hashlib.sha256(contenuto).hexdigest()

        doc = Documento(
            id=uuid.uuid4().hex[:8].upper(),
            nome=nome_file,
            tipo=tipo,
            percorso=str(dest.relative_to(self.documents_dir)),
            dimensione_bytes=len(contenuto),
            hash_sha256=sha256,
            firmato_digitalmente=firmato,
            note=note,
            data_documento=data_documento or date.today().isoformat(),
            caricato_da=caricato_da,
            id_deposito_pct=id_deposito_pct,
        )
        f.documenti.append(doc)
        f.modificato_il = datetime.now().isoformat()
        self._salva()
        return doc

    def rimuovi_documento(self, id_fasc: str, id_doc: str) -> None:
        f = self._get_o_errore(id_fasc)
        doc = next((d for d in f.documenti if d.id == id_doc), None)
        if not doc:
            raise KeyError(f"Documento '{id_doc}' non trovato nel fascicolo.")
        percorso = self.documents_dir / doc.percorso
        if percorso.exists():
            percorso.unlink()
        f.documenti = [d for d in f.documenti if d.id != id_doc]
        f.modificato_il = datetime.now().isoformat()
        self._salva()

    def percorso_documento(self, id_fasc: str, id_doc: str) -> Path:
        f = self._get_o_errore(id_fasc)
        doc = next((d for d in f.documenti if d.id == id_doc), None)
        if not doc:
            raise KeyError(f"Documento '{id_doc}' non trovato.")
        return self.documents_dir / doc.percorso

    # ---------------------------------------------------------------- Attività

    def aggiungi_attivita(
        self,
        id_fasc: str,
        tipo: TipoAttivita,
        data: str,
        titolo: str,
        **kwargs,
    ) -> AttivitaProcessuale:
        """Aggiunge un'attività processuale al fascicolo."""
        f = self._get_o_errore(id_fasc)
        att = AttivitaProcessuale(
            id=uuid.uuid4().hex[:8].upper(),
            tipo=tipo,
            data=data,
            titolo=titolo,
            **{k: v for k, v in kwargs.items() if hasattr(AttivitaProcessuale, k)},
        )
        f.attivita.append(att)

        # aggiorna prossima udienza se pertinente
        if tipo == TipoAttivita.UDIENZA and data >= date.today().isoformat():
            if not f.data_prossima_udienza or data < f.data_prossima_udienza:
                f.data_prossima_udienza = data
            if not f.data_prima_udienza:
                f.data_prima_udienza = data

        # passa automaticamente IN_CORSO se ancora APERTO
        if f.stato == StatoFascicolo.APERTO:
            self.cambia_stato(id_fasc, StatoFascicolo.IN_CORSO,
                              note="Avviata prima attività processuale")
            f = self._get_o_errore(id_fasc)

        f.modificato_il = datetime.now().isoformat()
        self._salva()
        return att

    def aggiorna_attivita(
        self,
        id_fasc: str,
        id_att: str,
        **campi,
    ) -> AttivitaProcessuale:
        f = self._get_o_errore(id_fasc)
        att = next((a for a in f.attivita if a.id == id_att), None)
        if not att:
            raise KeyError(f"Attività '{id_att}' non trovata.")
        for k, v in campi.items():
            if hasattr(att, k):
                setattr(att, k, v)
        f.modificato_il = datetime.now().isoformat()
        self._salva()
        return att

    # ---------------------------------------------------------------- Archivio

    def definisci(
        self,
        id_fasc: str,
        esito_finale: str = "",
        motivo: str = "",
        note: str = "",
        avvocato: str = "",
    ) -> Fascicolo:
        """Marca il fascicolo come DEFINITO (pronto per archiviazione)."""
        f = self._get_o_errore(id_fasc)
        if f.stato == StatoFascicolo.ARCHIVIATO:
            raise ValueError("Il fascicolo è già archiviato.")
        f.archivio = DatiArchivio(
            data_archiviazione="",
            motivo=motivo,
            esito_finale=esito_finale,
            note_archivio=note,
            archiviato_da=avvocato,
        )
        return self.cambia_stato(id_fasc, StatoFascicolo.DEFINITO, note=note, avvocato=avvocato)

    def archivia(
        self,
        id_fasc: str,
        crea_zip: bool = True,
        avvocato: str = "",
    ) -> Fascicolo:
        """
        Archivia definitivamente il fascicolo.

        Crea un archivio ZIP con tutti i documenti e i metadati JSON,
        poi segna il fascicolo come ARCHIVIATO.
        """
        f = self._get_o_errore(id_fasc)
        if f.stato not in (StatoFascicolo.DEFINITO, StatoFascicolo.IN_CORSO,
                           StatoFascicolo.APERTO, StatoFascicolo.SOSPESO):
            raise ValueError("Solo fascicoli non ancora archiviati possono essere archiviati.")

        zip_path = ""
        hash_zip = ""

        if crea_zip:
            zip_path, hash_zip = self._crea_archivio_zip(f)

        if f.archivio:
            f.archivio.data_archiviazione = date.today().isoformat()
            f.archivio.percorso_zip = zip_path
            f.archivio.hash_zip = hash_zip
            f.archivio.archiviato_da = avvocato
        else:
            f.archivio = DatiArchivio(
                data_archiviazione=date.today().isoformat(),
                percorso_zip=zip_path,
                hash_zip=hash_zip,
                archiviato_da=avvocato,
            )

        return self.cambia_stato(id_fasc, StatoFascicolo.ARCHIVIATO,
                                 note="Fascicolo archiviato", avvocato=avvocato)

    def ripristina_da_archivio(self, id_fasc: str, avvocato: str = "") -> Fascicolo:
        """Ripristina un fascicolo archiviato in stato APERTO."""
        f = self._get_o_errore(id_fasc)
        if f.stato != StatoFascicolo.ARCHIVIATO:
            raise ValueError("Il fascicolo non è archiviato.")
        f.data_chiusura = ""
        return self.cambia_stato(id_fasc, StatoFascicolo.APERTO,
                                 note="Ripristinato dall'archivio", avvocato=avvocato)

    def _crea_archivio_zip(self, f: Fascicolo) -> tuple[str, str]:
        """Crea un archivio ZIP del fascicolo e restituisce (path, hash)."""
        nome_zip = f"fascicolo_{f.numero.replace('/', '_')}_{f.id}.zip"
        zip_path = self.archive_dir / nome_zip

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # metadati JSON
            zf.writestr("fascicolo.json",
                        json.dumps(f.to_dict(), ensure_ascii=False, indent=2))
            # documenti fisici
            for doc in f.documenti:
                percorso_fisico = self.documents_dir / doc.percorso
                if percorso_fisico.exists():
                    zf.write(percorso_fisico, f"documenti/{percorso_fisico.name}")
            # indice documenti
            indice = [
                {"id": d.id, "nome": d.nome, "tipo": d.tipo.value,
                 "data": d.data_documento, "firmato": d.firmato_digitalmente}
                for d in f.documenti
            ]
            zf.writestr("indice_documenti.json",
                        json.dumps(indice, ensure_ascii=False, indent=2))

        # hash del ZIP
        sha256 = hashlib.sha256()
        with open(zip_path, "rb") as fh:
            for chunk in iter(lambda: fh.read(8192), b""):
                sha256.update(chunk)

        return str(zip_path), sha256.hexdigest()

    # ---------------------------------------------------------------- Query

    def get(self, id_fasc: str) -> Optional[Fascicolo]:
        return self._fascicoli.get(id_fasc)

    def tutti(
        self,
        stato: Optional[StatoFascicolo] = None,
        tipo: Optional[TipoFascicolo] = None,
        id_cliente: Optional[str] = None,
        archiviati: bool = False,
    ) -> List[Fascicolo]:
        fascicoli = sorted(
            self._fascicoli.values(),
            key=lambda f: f.numero,
            reverse=True,
        )
        if not archiviati:
            fascicoli = [f for f in fascicoli if f.stato != StatoFascicolo.ARCHIVIATO]
        if stato:
            fascicoli = [f for f in fascicoli if f.stato == stato]
        if tipo:
            fascicoli = [f for f in fascicoli if f.tipo == tipo]
        if id_cliente:
            fascicoli = [f for f in fascicoli if f.id_cliente == id_cliente]
        return fascicoli

    def archivio(self) -> List[Fascicolo]:
        """Restituisce solo i fascicoli archiviati."""
        return self.tutti(stato=StatoFascicolo.ARCHIVIATO, archiviati=True)

    def cerca(
        self,
        testo: str = "",
        stato: Optional[StatoFascicolo] = None,
        tipo: Optional[TipoFascicolo] = None,
        id_cliente: Optional[str] = None,
        archiviati: bool = False,
    ) -> List[Fascicolo]:
        risultati = self.tutti(stato=stato, tipo=tipo,
                               id_cliente=id_cliente, archiviati=archiviati)
        if testo:
            t = testo.lower()
            risultati = [
                f for f in risultati
                if t in f.titolo.lower()
                or t in f.numero.lower()
                or t in f.nome_cliente.lower()
                or t in f.controparte.lower()
                or t in f.numero_rg.lower()
                or t in f.oggetto.lower()
            ]
        return risultati

    def fascicoli_con_scadenze_imminenti(self, entro_giorni: int = 7) -> List[dict]:
        """Fascicoli con attività in scadenza entro N giorni."""
        oggi = date.today()
        soglia = (oggi.replace(day=oggi.day + entro_giorni)
                  if oggi.day + entro_giorni <= 28
                  else date(oggi.year, oggi.month + 1 if oggi.month < 12 else 1,
                            (oggi.day + entro_giorni) % 28 or 28)).isoformat()
        risultati = []
        for f in self.tutti():
            sc = f.prossima_scadenza
            if sc and sc.data <= soglia:
                risultati.append({"fascicolo": f, "scadenza": sc})
        return sorted(risultati, key=lambda x: x["scadenza"].data)

    def statistiche(self) -> dict:
        tutti = list(self._fascicoli.values())
        return {
            "totale": len(tutti),
            "attivi": sum(1 for f in tutti if f.stato not in
                         (StatoFascicolo.ARCHIVIATO, StatoFascicolo.DEFINITO)),
            "definiti": sum(1 for f in tutti if f.stato == StatoFascicolo.DEFINITO),
            "archiviati": sum(1 for f in tutti if f.stato == StatoFascicolo.ARCHIVIATO),
            "totale_documenti": sum(f.documenti_count for f in tutti),
            "totale_attivita": sum(f.attivita_count for f in tutti),
            "per_tipo": {
                t.value: sum(1 for f in tutti if f.tipo == t)
                for t in TipoFascicolo
            },
            "per_stato": {
                s.value: sum(1 for f in tutti if f.stato == s)
                for s in StatoFascicolo
            },
        }

    # ---------------------------------------------------------------- Utils

    def _get_o_errore(self, id_fasc: str) -> Fascicolo:
        f = self._fascicoli.get(id_fasc)
        if not f:
            raise KeyError(f"Fascicolo '{id_fasc}' non trovato.")
        return f
