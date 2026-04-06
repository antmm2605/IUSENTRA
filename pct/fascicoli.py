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

from pct.pst_servizi_catalogo import SERVIZIO_PST_DOCUMENTI_FASCICOLO


# ------------------------------------------------------------------ Enums

class TipoFascicolo(str, Enum):
    CIVILE          = "CIVILE"
    PENALE          = "PENALE"
    AMMINISTRATIVO  = "AMMINISTRATIVO"
    TRIBUTARIO      = "TRIBUTARIO"
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
    UDIENZA                  = "UDIENZA"
    DEPOSITO_ATTI            = "DEPOSITO_ATTI"
    ISCRIZIONE_A_RUOLO       = "ISCRIZIONE_A_RUOLO"    # PST: avvio causa / iscrizione a ruolo
    NOTIFICA                 = "NOTIFICA"
    CONSULTAZIONE            = "CONSULTAZIONE"
    TERMINE_SCADENZA         = "TERMINE_SCADENZA"
    ACCESSO_ATTI             = "ACCESSO_ATTI"
    MEDIAZIONE               = "MEDIAZIONE"
    CTU                      = "CTU"
    SENTENZA_EMESSA          = "SENTENZA_EMESSA"
    PROVVEDIMENTO            = "PROVVEDIMENTO"          # PST: ordinanza / decreto del giudice
    COMUNICAZIONE_CANCELLERIA = "COMUNICAZIONE_CANCELLERIA"  # PST: comunicazione / esito cancelleria
    APPELLO                  = "APPELLO"
    ESECUZIONE               = "ESECUZIONE"
    ACCORDO                  = "ACCORDO"
    RINVIO                   = "RINVIO"
    ALTRO                    = "ALTRO"


# Mapping tipo_atto (codice PST) → label italiana leggibile
TIPO_ATTO_LABEL: dict = {
    "RICORSO":              "Ricorso",
    "CITAZIONE":            "Atto di citazione",
    "MEMORIA":              "Memoria",
    "COMPARSA":             "Comparsa di risposta",
    "REPLICA":              "Replica",
    "ISTANZA":              "Istanza",
    "NOTA_SPESE":           "Nota spese",
    "PROCURA":              "Procura alle liti",
    "DECRETO_INGIUNTIVO":   "Ricorso per decreto ingiuntivo",
    "OPPOSIZIONE":          "Atto di opposizione",
    "APPELLO":              "Atto di appello",
    "RECLAMO":              "Reclamo",
    "ATTO_DIFESA":          "Atto di difesa",
    "IMPUGNAZIONE":         "Atto di impugnazione",
    "RICHIESTA_RIESAME":    "Richiesta di riesame",
    "MOTIVI_NUOVI":         "Motivi nuovi",
    "DEPOSITO_DOCUMENTI":   "Deposito documenti",
    "MOTIVI_AGGIUNTI":      "Motivi aggiunti",
    "RICORSO_INCIDENTALE":  "Ricorso incidentale",
    "ALTRO":                "Altro atto",
}


def _tipo_attivita_da_tipo_atto(tipo_atto: str) -> "TipoAttivita":
    """Deriva il TipoAttivita PST dal codice tipo_atto del deposito."""
    _iscrizione = {"CITAZIONE", "DECRETO_INGIUNTIVO", "RICORSO", "RICORSO_INCIDENTALE"}
    _appello    = {"APPELLO", "IMPUGNAZIONE"}
    if tipo_atto in _iscrizione:
        return TipoAttivita.ISCRIZIONE_A_RUOLO
    if tipo_atto in _appello:
        return TipoAttivita.APPELLO
    return TipoAttivita.DEPOSITO_ATTI


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
class DocumentoVersione:
    """Versione precedente di un documento (storico modifiche)."""
    hash_sha256: str
    percorso: str
    dimensione_bytes: int
    sostituito_il: str   # ISO datetime
    sostituito_da: str   # username

    @classmethod
    def from_dict(cls, d: dict) -> "DocumentoVersione":
        return cls(
            hash_sha256=d.get("hash_sha256", ""),
            percorso=d.get("percorso", ""),
            dimensione_bytes=d.get("dimensione_bytes", 0),
            sostituito_il=d.get("sostituito_il", ""),
            sostituito_da=d.get("sostituito_da", ""),
        )


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
    ocr_estratto: bool = False     # True dopo OCR completato e testo indicizzato
    # #7 — Storico versioni (versioni precedenti del documento)
    versioni: List["DocumentoVersione"] = field(default_factory=list)

    @property
    def firmato(self) -> bool:
        """Alias retrocompatibile usato da template e viste legacy."""
        return bool(self.firmato_digitalmente)

    @firmato.setter
    def firmato(self, value: bool) -> None:
        self.firmato_digitalmente = bool(value)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["tipo"] = self.tipo.value
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Documento":
        d = dict(d)
        d["tipo"] = TipoDocumento(d["tipo"])
        d["versioni"] = [DocumentoVersione.from_dict(v) for v in d.get("versioni", [])]
        d.setdefault("ocr_estratto", False)
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
    dimensione_zip: int = 0         # dimensione in byte del file ZIP


# ------------------------------------------------------------------ Esito deposito PCT

STATI_DEPOSITO_PCT_CANONICI = {
    "INVIATO",
    "ACCETTATO_PEC",
    "CONSEGNATO",
    "WARN_CONTROLLI",
    "ERRORE_CONTROLLI",
    "ACCETTATO_CANCELLERIA",
    "RIFIUTATO_CANCELLERIA",
    "ERRORE",
    "IMPORTATO_DA_PORTALE",
    "IMPORTATO_DA_PST",
}

_STATI_DEPOSITO_PCT_LEGACY_MAP = {
    "ACCETTATO": "ACCETTATO_PEC",
    "RIFIUTATO": "RIFIUTATO_CANCELLERIA",
}


def _normalizza_stato_deposito_pct(stato: str) -> str:
    """Normalizza e valida gli stati deposito PCT verso il set canonico."""
    valore = str(stato or "INVIATO").strip().upper()
    valore = _STATI_DEPOSITO_PCT_LEGACY_MAP.get(valore, valore)
    if valore not in STATI_DEPOSITO_PCT_CANONICI:
        raise ValueError(f"Stato deposito non valido: {stato}")
    return valore


def normalizza_stato_deposito_pct(stato: str) -> str:
    """Alias retrocompatibile della normalizzazione stati deposito PCT."""
    return _normalizza_stato_deposito_pct(stato)


def _normalizza_esito_controlli(esito: str) -> str:
    """Normalizza e valida l'esito dei controlli automatici PCT."""
    valore = str(esito or "").strip().upper()
    if not valore:
        return ""
    if valore not in {"OK", "WARN", "ERROR"}:
        raise ValueError(f"Esito controlli non valido: {esito}")
    return valore


def _migra_payload_depositi_pct(payload_fascicolo: dict) -> bool:
    """Migra in-place gli stati legacy dei depositi già salvati nel JSON."""
    cambiato = False
    for dep in payload_fascicolo.get("depositi_pct") or []:
        stato_orig = dep.get("stato", "INVIATO")
        stato_norm = _normalizza_stato_deposito_pct(stato_orig)
        if stato_norm != stato_orig:
            dep["stato"] = stato_norm
            cambiato = True

        esito_orig = dep.get("esito_controlli", "")
        esito_norm = _normalizza_esito_controlli(esito_orig)
        if esito_norm != esito_orig:
            dep["esito_controlli"] = esito_norm
            cambiato = True
    return cambiato

@dataclass
class EsitoDepositoPCT:
    """
    Esito di un deposito telematico archiviato nel fascicolo.

    Flusso ufficiale PCT (4 fasi):
      Fase 4 → ACCETTATO_PEC        : ricevuta accettazione PEC (gestore mittente)
      Fase 5 → CONSEGNATO            : ricevuta avvenuta consegna (sistema MinGiustizia)
      Fase 6 → WARN_CONTROLLI /
               ERRORE_CONTROLLI      : esito controlli automatici busta
      Fase 7 → ACCETTATO_CANCELLERIA : deposito accettato dalla cancelleria (definitivo)
               RIFIUTATO_CANCELLERIA : deposito rifiutato dalla cancelleria

    Stati legacy mantenuti per retro-compatibilità:
      INVIATO, ACCETTATO (= ACCETTATO_PEC), RIFIUTATO, ERRORE
    """
    id: str
    timestamp: str                  # ISO datetime dell'invio
    stato: str                      # vedi docstring sopra
    tipo_atto: str                  # es. "MEMORIA", "RICORSO"
    pec_destinatario: str           # PEC del tribunale
    messaggio: str = ""
    # ── Fase 4: ricevuta accettazione PEC ──────────────────────────
    ricevuta_accettazione: str = ""
    # ── Fase 5: ricevuta avvenuta consegna ─────────────────────────
    ricevuta_consegna: str = ""
    # ── Fase 6: esito controlli automatici ─────────────────────────
    ricevuta_controlli_automatici: str = ""   # messaggio PEC fase 6
    esito_controlli: str = ""                 # OK | WARN | ERROR
    # ── Fase 7: esito cancelleria ──────────────────────────────────
    ricevuta_cancelleria: str = ""            # messaggio PEC fase 7
    note: str = ""
    registrato_da: str = ""
    registrato_il: str = field(default_factory=lambda: datetime.now().isoformat())
    # ── Documenti inclusi nella busta ──────────────────────────────
    documenti_ids: List[str] = field(default_factory=list)   # ID dei Documento inclusi
    nome_atto_principale: str = ""                            # nome file atto principale
    id_deposito_esterno: str = ""                             # id busta/registro del portale ufficiale
    documenti_portale: List[dict] = field(default_factory=list)  # metadati documenti ufficiali
    fonte_portale: str = ""                                   # PolisWeb / PDP / PAT
    servizio_portale: str = ""                                # servizio ufficiale sorgente (es. DocumentiFascicolo)
    busta_path: str = ""                                      # percorso busta .enc locale

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "stato": self.stato,
            "tipo_atto": self.tipo_atto,
            "pec_destinatario": self.pec_destinatario,
            "messaggio": self.messaggio,
            "ricevuta_accettazione": self.ricevuta_accettazione,
            "ricevuta_consegna": self.ricevuta_consegna,
            "ricevuta_controlli_automatici": self.ricevuta_controlli_automatici,
            "esito_controlli": self.esito_controlli,
            "ricevuta_cancelleria": self.ricevuta_cancelleria,
            "note": self.note,
            "registrato_da": self.registrato_da,
            "registrato_il": self.registrato_il,
            "documenti_ids": self.documenti_ids,
            "nome_atto_principale": self.nome_atto_principale,
            "id_deposito_esterno": self.id_deposito_esterno,
            "documenti_portale": self.documenti_portale,
            "fonte_portale": self.fonte_portale,
            "servizio_portale": self.servizio_portale,
            "busta_path": self.busta_path,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "EsitoDepositoPCT":
        d = dict(d or {})
        if not d.get("id") and d.get("id_deposito"):
            d["id"] = d["id_deposito"]
        d["stato"] = _normalizza_stato_deposito_pct(d.get("stato", "INVIATO"))
        d["esito_controlli"] = _normalizza_esito_controlli(d.get("esito_controlli", ""))
        campi = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in campi})

    @property
    def id_deposito(self) -> str:
        """Alias legacy del campo id usato dal vecchio motore deposito."""
        return self.id


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
    data_notifica_citazione: str = ""
    data_prossima_udienza: str = ""

    # --- Contenuto
    documenti: List[Documento] = field(default_factory=list)
    attivita: List[AttivitaProcessuale] = field(default_factory=list)
    avanzamento: List[AvanzamentoPratica] = field(default_factory=list)
    depositi_pct: List[EsitoDepositoPCT] = field(default_factory=list)
    note: str = ""
    note_riservate: str = ""

    # --- Sorgente / sincronizzazione portali
    source: str = ""                    # PST | PDP | PAT | PTT
    source_external_id: str = ""        # chiave esterna stabile del fascicolo sul portale
    last_sync_at: str = ""              # ISO datetime ultimo allineamento
    sync_status: str = ""               # IMPORTATO | SINCRONIZZATO | DA_VERIFICARE
    import_log_id: str = ""             # id log acquisizione guidata
    has_conflicts: bool = False
    document_sync_enabled: bool = False
    events_sync_enabled: bool = False

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
        d["depositi_pct"] = [dep.to_dict() for dep in self.depositi_pct]
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
        d["depositi_pct"] = [
            EsitoDepositoPCT.from_dict(dep) for dep in (d.get("depositi_pct") or [])
        ]
        arch = d.get("archivio")
        d["archivio"] = DatiArchivio(**arch) if arch else None
        campi = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in d.items() if k in campi})


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
        studio_db=None,
    ):
        self.db_path = Path(db_path)
        self.documents_dir = Path(documents_dir)
        self.archive_dir = Path(archive_dir)
        for d in (self.db_path.parent, self.documents_dir, self.archive_dir):
            d.mkdir(parents=True, exist_ok=True)
        self._studio_db = studio_db
        self._fascicoli: dict[str, Fascicolo] = {}
        self._carica()

    # ---------------------------------------------------------------- I/O

    @staticmethod
    def _row_to_fascicolo(row) -> Optional["Fascicolo"]:
        """Ricostruisce un Fascicolo da una riga SQLite (dict o sqlite3.Row)."""
        import json as _json
        try:
            d = dict(row)
            dati = d.get("dati_json")
            if dati:
                payload = _json.loads(dati)
            else:
                # Fallback colonne: ricostruisce i campi complessi dai JSON figli
                payload = d.copy()
                payload["attivita"] = _json.loads(d.get("attivita_json") or "[]")
                payload["documenti"] = _json.loads(d.get("documenti_json") or "[]")
                payload["depositi_pct"] = _json.loads(d.get("scadenze_json") or "[]")
                for k in ("attivita_json", "documenti_json", "scadenze_json", "dati_json"):
                    payload.pop(k, None)
            _migra_payload_depositi_pct(payload)
            return Fascicolo.from_dict(payload)
        except Exception:
            return None

    def _carica(self) -> None:
        if self._studio_db is not None:
            import sqlite3 as _sqlite3
            rows = self._studio_db.conn.execute(
                "SELECT * FROM fascicoli"
            ).fetchall()
            self._fascicoli = {}
            migrato = False
            for row in rows:
                f = self._row_to_fascicolo(row)
                if f:
                    self._fascicoli[f.id] = f
                    # Se era dati_json NULL (primo carico post-migrazione) → riscrivi
                    if not dict(row).get("dati_json"):
                        migrato = True
            if migrato:
                self._salva()
            return
        from pct import cache as _cache
        raw = _cache.load(self.db_path)
        migrato = False
        for payload in raw.values():
            migrato = _migra_payload_depositi_pct(payload) or migrato
        self._fascicoli = {k: Fascicolo.from_dict(v) for k, v in raw.items()}
        if migrato:
            self._salva()

    def _salva(self) -> None:
        if self._studio_db is not None:
            import json as _json

            def _insert(conn, f):
                d = f.to_dict()
                conn.execute(
                    """
                    INSERT INTO fascicoli
                    (id, numero, titolo, tipo, stato, id_cliente, nome_cliente,
                     tribunale, sezione, giudice, numero_rg, anno_rg,
                     controparte, avvocato_referente, avvocato_dominus,
                     data_apertura, data_chiusura, oggetto, note, creato_il,
                     attivita_json, documenti_json, scadenze_json, dati_json)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        f.id, f.numero, f.titolo,
                        f.tipo.value, f.stato.value,
                        f.id_cliente or None, f.nome_cliente,
                        f.tribunale, f.sezione, f.giudice,
                        f.numero_rg, str(f.anno_rg) if f.anno_rg else "",
                        f.controparte, f.avvocato_referente, f.avvocato_dominus,
                        f.data_apertura, f.data_chiusura,
                        f.oggetto, f.note, f.creato_il,
                        _json.dumps(d.get("attivita", []), ensure_ascii=False),
                        _json.dumps(d.get("documenti", []), ensure_ascii=False),
                        _json.dumps(d.get("depositi_pct", []), ensure_ascii=False),
                        _json.dumps(d, ensure_ascii=False),
                    ),
                )

            self._studio_db.salva_tabella("fascicoli", list(self._fascicoli.values()), _insert)
            return
        from pct import cache as _cache
        _cache.save(self.db_path, {k: v.to_dict() for k, v in self._fascicoli.items()})

    def segna_ocr_estratto(self, id_fasc: str, id_doc: str) -> None:
        """Segna un documento come indicizzato via OCR e persiste."""
        f = self._fascicoli.get(id_fasc)
        if not f:
            return
        doc = next((d for d in f.documenti if d.id == id_doc), None)
        if doc and not doc.ocr_estratto:
            doc.ocr_estratto = True
            self._salva()

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

    def registra_onboarding(
        self,
        id_fasc: str,
        descrizione: str,
        *,
        note: str = "",
        avvocato: str = "",
    ) -> Fascicolo:
        """Registra nel fascicolo l'apertura guidata senza alterare lo stato operativo."""
        f = self._get_o_errore(id_fasc)
        f.avanzamento.append(AvanzamentoPratica(
            data=datetime.now().isoformat(),
            descrizione=descrizione,
            stato_precedente=f.stato.value,
            stato_nuovo=f.stato.value,
            note=note,
            avvocato=avvocato,
        ))
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

    def sostituisci_documento(
        self,
        id_fasc: str,
        id_doc: str,
        nome_file: str,
        contenuto: bytes,
        caricato_da: str = "",
        note: str = "",
    ) -> "Documento":
        """
        Sostituisce il file di un documento esistente mantenendo lo storico
        della versione precedente in doc.versioni.
        """
        f = self._get_o_errore(id_fasc)
        doc = next((d for d in f.documenti if d.id == id_doc), None)
        if not doc:
            raise KeyError(f"Documento '{id_doc}' non trovato nel fascicolo.")

        # Archivia versione precedente
        doc.versioni.append(DocumentoVersione(
            hash_sha256=doc.hash_sha256,
            percorso=doc.percorso,
            dimensione_bytes=doc.dimensione_bytes,
            sostituito_il=datetime.now().isoformat(),
            sostituito_da=caricato_da,
        ))

        # Salva nuovo file (path basato sul nuovo nome per evitare collisioni)
        fasc_dir = self.documents_dir / id_fasc
        fasc_dir.mkdir(parents=True, exist_ok=True)
        nome_safe = Path(nome_file).name
        dest = fasc_dir / nome_safe
        if dest.exists() and str(dest.relative_to(self.documents_dir)) != doc.percorso:
            stem, suffix = Path(nome_safe).stem, Path(nome_safe).suffix
            nome_safe = f"{stem}_{uuid.uuid4().hex[:4]}{suffix}"
            dest = fasc_dir / nome_safe
        dest.write_bytes(contenuto)

        doc.percorso = str(dest.relative_to(self.documents_dir))
        doc.nome = nome_file
        doc.dimensione_bytes = len(contenuto)
        doc.hash_sha256 = hashlib.sha256(contenuto).hexdigest()
        doc.caricato_da = caricato_da or doc.caricato_da
        if note:
            doc.note = note
        doc.data_caricamento = datetime.now().isoformat()

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

    def aggiungi_esito_deposito(
        self,
        id_fasc: str,
        tipo_atto: str,
        pec_destinatario: str,
        stato: str = "INVIATO",
        messaggio: str = "",
        ricevuta_accettazione: str = "",
        ricevuta_consegna: str = "",
        ricevuta_controlli_automatici: str = "",
        esito_controlli: str = "",
        ricevuta_cancelleria: str = "",
        note: str = "",
        registrato_da: str = "",
        documenti_ids: Optional[List[str]] = None,
        nome_atto_principale: str = "",
    ) -> EsitoDepositoPCT:
        """Registra nel fascicolo l'esito di un deposito telematico."""
        f = self._get_o_errore(id_fasc)
        stato = _normalizza_stato_deposito_pct(stato)
        esito_controlli = _normalizza_esito_controlli(esito_controlli)
        esito = EsitoDepositoPCT(
            id=uuid.uuid4().hex[:8].upper(),
            timestamp=datetime.now().isoformat(),
            stato=stato,
            tipo_atto=tipo_atto,
            pec_destinatario=pec_destinatario,
            messaggio=messaggio,
            ricevuta_accettazione=ricevuta_accettazione,
            ricevuta_consegna=ricevuta_consegna,
            ricevuta_controlli_automatici=ricevuta_controlli_automatici,
            esito_controlli=esito_controlli,
            ricevuta_cancelleria=ricevuta_cancelleria,
            note=note,
            registrato_da=registrato_da,
            documenti_ids=list(documenti_ids) if documenti_ids else [],
            nome_atto_principale=nome_atto_principale,
        )
        f.depositi_pct.append(esito)

        # Marca i documenti inclusi con l'id del deposito
        for doc in f.documenti:
            if doc.id in esito.documenti_ids:
                doc.id_deposito_pct = esito.id
        f.modificato_il = datetime.now().isoformat()

        # Auto-crea attività processuale collegata al deposito (PST: evento nel fascicolo)
        tipo_att = _tipo_attivita_da_tipo_atto(tipo_atto)
        label    = TIPO_ATTO_LABEL.get(tipo_atto, tipo_atto)
        att = AttivitaProcessuale(
            id=uuid.uuid4().hex[:8].upper(),
            tipo=tipo_att,
            data=date.today().isoformat(),
            titolo=f"Deposito telematico — {label}",
            descrizione=f"Tipo atto: {label}. Stato: {esito.stato}.",
            esito=EsitoAttivita.IN_ATTESA,
            id_deposito_pct=esito.id,
            avvocato=registrato_da,
        )
        f.attivita.append(att)
        f.modificato_il = datetime.now().isoformat()

        self._salva()
        return esito

    def registra_import_documenti_portale(
        self,
        id_fasc: str,
        fonte: str,
        documenti_ids: List[str],
        tipo_atto: str = "DOCUMENTI_UFFICIALI",
        note: str = "",
        registrato_da: str = "",
        pec_destinatario: str = "",
        nome_atto_principale: str = "",
    ) -> EsitoDepositoPCT:
        """
        Registra l'acquisizione di file già scaricati dal portale ufficiale.

        Non rappresenta un invio telematico, ma un lotto di consultazione/import
        da fascicolo telematico ufficiale (PST / PDP / PAT).
        """
        f = self._get_o_errore(id_fasc)
        if not documenti_ids:
            raise ValueError("Nessun documento selezionato per l'importazione dal portale.")

        doc_ids = set(documenti_ids)
        if not any(doc.id in doc_ids for doc in f.documenti):
            raise ValueError("I documenti indicati non appartengono al fascicolo.")

        descrizione = note.strip() or f"File ufficiali acquisiti da {fonte}."
        esito = EsitoDepositoPCT(
            id=uuid.uuid4().hex[:8].upper(),
            timestamp=datetime.now().isoformat(),
            stato="IMPORTATO_DA_PORTALE",
            tipo_atto=tipo_atto,
            pec_destinatario=pec_destinatario or fonte,
            messaggio=f"Acquisizione da {fonte}",
            note=descrizione,
            registrato_da=registrato_da,
            documenti_ids=list(documenti_ids),
            nome_atto_principale=nome_atto_principale,
            fonte_portale=fonte,
            servizio_portale=SERVIZIO_PST_DOCUMENTI_FASCICOLO,
        )
        f.depositi_pct.append(esito)

        for doc in f.documenti:
            if doc.id in doc_ids:
                doc.id_deposito_pct = esito.id

        att = AttivitaProcessuale(
            id=uuid.uuid4().hex[:8].upper(),
            tipo=TipoAttivita.CONSULTAZIONE,
            data=date.today().isoformat(),
            titolo=f"Acquisizione file ufficiali — {fonte}",
            descrizione=f"{len(documenti_ids)} documenti importati. {descrizione}",
            esito=EsitoAttivita.NON_APPLICABILE,
            id_deposito_pct=esito.id,
            avvocato=registrato_da,
        )
        f.attivita.append(att)
        f.modificato_il = datetime.now().isoformat()
        self._salva()
        return esito

    def collega_documenti_a_deposito_portale(
        self,
        id_fasc: str,
        id_dep: str,
        documenti_ids: List[str],
        *,
        note: str = "",
        registrato_da: str = "",
    ) -> EsitoDepositoPCT:
        """
        Collega documenti già presenti nel fascicolo a un deposito ufficiale già censito.

        Usa questo metodo quando i metadati del portale sono già stati importati
        e successivamente vengono acquisiti i file binari corrispondenti.
        """
        f = self._get_o_errore(id_fasc)
        dep = next((d for d in f.depositi_pct if d.id == id_dep), None)
        if not dep:
            raise KeyError(f"Deposito '{id_dep}' non trovato nel fascicolo.")
        if not documenti_ids:
            raise ValueError("Nessun documento da collegare al deposito ufficiale.")

        doc_ids_presenti = {doc.id for doc in f.documenti}
        nuovi_ids = [
            doc_id for doc_id in documenti_ids
            if doc_id in doc_ids_presenti and doc_id not in dep.documenti_ids
        ]
        if not nuovi_ids:
            return dep

        dep.documenti_ids.extend(nuovi_ids)
        for doc in f.documenti:
            if doc.id in nuovi_ids:
                doc.id_deposito_pct = dep.id

        descrizione = note.strip()
        if descrizione:
            dep.note = " | ".join(
                part for part in [dep.note.strip(), descrizione] if part
            )
        if registrato_da and not dep.registrato_da:
            dep.registrato_da = registrato_da
        f.modificato_il = datetime.now().isoformat()
        self._salva()
        return dep

    def sincronizza_deposito_portale(
        self,
        id_fasc: str,
        *,
        fonte: str,
        id_deposito_esterno: str,
        tipo_atto: str = "",
        data_deposito: str = "",
        mittente: str = "",
        documenti_portale: Optional[List[dict]] = None,
        registrato_da: str = "",
        note: str = "",
        nome_atto_principale: str = "",
        stato: str = "IMPORTATO_DA_PST",
        servizio_portale: str = "",
    ) -> EsitoDepositoPCT:
        """
        Registra o aggiorna nel fascicolo un deposito già visibile sul portale ufficiale.

        Non scarica file binari: salva solo i metadati ufficiali della busta
        e dei documenti esposti dal canale ministeriale.
        """
        f = self._get_o_errore(id_fasc)
        chiave_portale = (id_deposito_esterno or "").strip()
        if not chiave_portale:
            raise ValueError("Identificativo del deposito portale mancante.")

        def _bool_portale(value: object) -> bool:
            if isinstance(value, bool):
                return value
            if isinstance(value, (int, float)):
                return bool(value)
            text = str(value or "").strip().lower()
            if text in {"1", "true", "yes", "si", "s", "ok"}:
                return True
            if text in {"0", "false", "no", "n", "", "none", "null"}:
                return False
            return bool(value)

        def _normalizza_doc_portale(item: dict) -> dict:
            row = dict(item or {})
            return {
                "id_documento": str(row.get("id_documento") or "").strip(),
                "id_cat": str(row.get("id_cat") or "").strip(),
                "nome": str(row.get("nome") or "").strip(),
                "tipo": str(row.get("tipo") or "").strip(),
                "data_deposito": str(row.get("data_deposito") or "").strip(),
                "mittente": str(row.get("mittente") or "").strip(),
                "dimensione_bytes": int(row.get("dimensione_bytes") or 0),
                "disponibile": _bool_portale(row.get("disponibile", True)),
                "id_deposito": str(row.get("id_deposito") or chiave_portale).strip(),
                "tipo_atto": str(row.get("tipo_atto") or tipo_atto or "").strip(),
            }

        def _merge_documenti_portale(*liste: List[dict]) -> List[dict]:
            merged: List[dict] = []
            visti: set[tuple[str, str, str]] = set()
            for lista in liste:
                for item in lista or []:
                    row = _normalizza_doc_portale(item)
                    chiave = (
                        row.get("id_documento") or "",
                        (row.get("nome") or "").upper(),
                        row.get("data_deposito") or "",
                    )
                    if chiave in visti:
                        continue
                    visti.add(chiave)
                    merged.append(row)
            merged.sort(
                key=lambda item: (
                    item.get("data_deposito") or "",
                    item.get("nome") or "",
                    item.get("id_documento") or "",
                ),
                reverse=True,
            )
            return merged

        def _timestamp_portale(data_iso: str) -> str:
            data_iso = (data_iso or "").strip()
            return f"{data_iso}T00:00:00" if data_iso else datetime.now().isoformat()

        def _tipo_attivita_portale(tipo_atto_portale: str, docs: List[dict]) -> TipoAttivita:
            testo = (tipo_atto_portale or "").upper()
            tipi_doc = " ".join(str(doc.get("tipo") or "").upper() for doc in docs)
            if any(token in testo or token in tipi_doc for token in ("PROVVED", "SENTENZA", "ORDINANZA", "DECRETO")):
                return TipoAttivita.PROVVEDIMENTO
            if "UDIENZA" in testo or "VERBALE" in tipi_doc:
                return TipoAttivita.UDIENZA
            return TipoAttivita.DEPOSITO_ATTI

        documenti_norm = _merge_documenti_portale(documenti_portale or [])
        descrizione = note.strip() or f"Metadati del deposito acquisiti da {fonte}."
        timestamp = _timestamp_portale(data_deposito)
        dep = next(
            (
                d for d in f.depositi_pct
                if (getattr(d, "id_deposito_esterno", "") or "").strip() == chiave_portale
            ),
            None,
        )

        if dep:
            dep.stato = _normalizza_stato_deposito_pct(stato or dep.stato)
            dep.timestamp = timestamp or dep.timestamp
            dep.tipo_atto = tipo_atto or dep.tipo_atto
            dep.pec_destinatario = mittente or dep.pec_destinatario or fonte
            dep.messaggio = f"Metadati importati da {fonte}"
            dep.note = descrizione
            dep.registrato_da = registrato_da or dep.registrato_da
            dep.nome_atto_principale = nome_atto_principale or dep.nome_atto_principale
            dep.id_deposito_esterno = chiave_portale
            dep.fonte_portale = fonte or dep.fonte_portale
            dep.servizio_portale = servizio_portale or dep.servizio_portale
            dep.documenti_portale = _merge_documenti_portale(dep.documenti_portale, documenti_norm)
            f.modificato_il = datetime.now().isoformat()
            self._salva()
            return dep

        dep = EsitoDepositoPCT(
            id=uuid.uuid4().hex[:8].upper(),
            timestamp=timestamp,
            stato=_normalizza_stato_deposito_pct(stato),
            tipo_atto=tipo_atto or "Deposito visibile su portale",
            pec_destinatario=mittente or fonte,
            messaggio=f"Metadati importati da {fonte}",
            note=descrizione,
            registrato_da=registrato_da,
            nome_atto_principale=nome_atto_principale,
            id_deposito_esterno=chiave_portale,
            documenti_portale=documenti_norm,
            fonte_portale=fonte,
            servizio_portale=servizio_portale,
        )
        f.depositi_pct.append(dep)

        att = AttivitaProcessuale(
            id=uuid.uuid4().hex[:8].upper(),
            tipo=_tipo_attivita_portale(dep.tipo_atto, documenti_norm),
            data=(data_deposito or date.today().isoformat()),
            titolo=f"Deposito da portale — {dep.tipo_atto}",
            descrizione=(
                f"{len(documenti_norm)} documenti censiti da {fonte}."
                + (f" Mittente: {mittente}." if mittente else "")
            ).strip(),
            esito=EsitoAttivita.NON_APPLICABILE,
            id_deposito_pct=dep.id,
            avvocato=registrato_da,
        )
        f.attivita.append(att)
        f.modificato_il = datetime.now().isoformat()
        self._salva()
        return dep

    def modifica_esito_deposito(
        self,
        id_fasc: str,
        id_dep: str,
        tipo_atto: str,
        pec_destinatario: str,
        stato: str = "INVIATO",
        messaggio: str = "",
        ricevuta_accettazione: str = "",
        ricevuta_consegna: str = "",
        ricevuta_controlli_automatici: str = "",
        esito_controlli: str = "",
        ricevuta_cancelleria: str = "",
        note: str = "",
        modificato_da: str = "",
    ) -> EsitoDepositoPCT:
        """Modifica i dati di un deposito telematico già registrato nel fascicolo."""
        f = self._get_o_errore(id_fasc)
        dep = next((d for d in f.depositi_pct if d.id == id_dep), None)
        if not dep:
            raise KeyError(f"Deposito '{id_dep}' non trovato nel fascicolo.")
        dep.tipo_atto = tipo_atto
        dep.pec_destinatario = pec_destinatario
        dep.stato = _normalizza_stato_deposito_pct(stato)
        dep.messaggio = messaggio
        dep.ricevuta_accettazione = ricevuta_accettazione
        dep.ricevuta_consegna = ricevuta_consegna
        dep.ricevuta_controlli_automatici = ricevuta_controlli_automatici
        dep.esito_controlli = _normalizza_esito_controlli(esito_controlli)
        dep.ricevuta_cancelleria = ricevuta_cancelleria
        dep.note = note
        f.modificato_il = datetime.now().isoformat()
        self._salva()
        return dep

    def segna_firmato(self, id_fasc: str, id_doc: str) -> "Documento":
        """Marca un documento come firmato digitalmente."""
        f = self._get_o_errore(id_fasc)
        doc = next((d for d in f.documenti if d.id == id_doc), None)
        if not doc:
            raise KeyError(f"Documento '{id_doc}' non trovato nel fascicolo.")
        doc.firmato_digitalmente = True
        f.modificato_il = datetime.now().isoformat()
        self._salva()
        return doc

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
        """
        Marca il fascicolo come DEFINITO e crea automaticamente il ZIP compresso.
        Da questo momento la pratica è accessibile nella cartella digitale del cliente
        in formato compresso; può essere sfogliata o ripristinata senza riaprire il fascicolo.
        """
        f = self._get_o_errore(id_fasc)
        if f.stato == StatoFascicolo.ARCHIVIATO:
            raise ValueError("Il fascicolo è già archiviato.")
        # Crea l'archivio ZIP in anticipo (compressione preventiva)
        zip_path, hash_zip, dim = self._crea_archivio_zip(f)
        f.archivio = DatiArchivio(
            data_archiviazione=date.today().isoformat(),
            motivo=motivo,
            esito_finale=esito_finale,
            note_archivio=note,
            archiviato_da=avvocato,
            percorso_zip=zip_path,
            hash_zip=hash_zip,
            dimensione_zip=dim,
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
        dimensione_zip = 0

        if crea_zip:
            # Riusa il ZIP creato da definisci() se già esistente e valido
            zip_esistente = (f.archivio and f.archivio.percorso_zip
                             and Path(f.archivio.percorso_zip).exists())
            if zip_esistente:
                zip_path = f.archivio.percorso_zip
                hash_zip = f.archivio.hash_zip
                dimensione_zip = f.archivio.dimensione_zip
            else:
                zip_path, hash_zip, dimensione_zip = self._crea_archivio_zip(f)

        if f.archivio:
            f.archivio.data_archiviazione = date.today().isoformat()
            f.archivio.percorso_zip = zip_path
            f.archivio.hash_zip = hash_zip
            f.archivio.dimensione_zip = dimensione_zip
            f.archivio.archiviato_da = avvocato
        else:
            f.archivio = DatiArchivio(
                data_archiviazione=date.today().isoformat(),
                percorso_zip=zip_path,
                hash_zip=hash_zip,
                dimensione_zip=dimensione_zip,
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

    def _crea_archivio_zip(self, f: Fascicolo) -> tuple[str, str, int]:
        """Crea un archivio ZIP del fascicolo e restituisce (path, hash, dimensione_bytes)."""
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

        # hash e dimensione del ZIP
        sha256 = hashlib.sha256()
        with open(zip_path, "rb") as fh:
            for chunk in iter(lambda: fh.read(8192), b""):
                sha256.update(chunk)
        dimensione = zip_path.stat().st_size

        return str(zip_path), sha256.hexdigest(), dimensione

    def contenuto_archivio(self, id_fasc: str) -> list[dict]:
        """Restituisce la lista dei file presenti nel ZIP dell'archivio."""
        f = self._get_o_errore(id_fasc)
        if not f.archivio or not f.archivio.percorso_zip:
            return []
        p = Path(f.archivio.percorso_zip)
        if not p.exists():
            return []
        with zipfile.ZipFile(p, "r") as zf:
            return [
                {
                    "nome": info.filename,
                    "dimensione": info.file_size,
                    "estensione": Path(info.filename).suffix.lower(),
                }
                for info in zf.infolist()
                if not info.is_dir()
            ]

    def estrai_file_archivio(self, id_fasc: str, nome_file: str) -> bytes:
        """Estrae e restituisce il contenuto di un singolo file dal ZIP."""
        f = self._get_o_errore(id_fasc)
        if not f.archivio or not f.archivio.percorso_zip:
            raise FileNotFoundError("Archivio ZIP non disponibile per questo fascicolo.")
        p = Path(f.archivio.percorso_zip)
        if not p.exists():
            raise FileNotFoundError("File ZIP non trovato su disco.")
        with zipfile.ZipFile(p, "r") as zf:
            nomi = zf.namelist()
            if nome_file not in nomi:
                raise FileNotFoundError(f"File '{nome_file}' non trovato nell'archivio.")
            return zf.read(nome_file)

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
