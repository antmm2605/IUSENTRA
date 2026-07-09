"""
Gestione fascicoli (cartelle legali) dello studio.

Ogni fascicolo è legato a un cliente e raccoglie:
- Documenti (atti, allegati, comunicazioni, parcelle)
- Attività processuali (udienze, depositi, notifiche, scadenze)
- Stato di avanzamento della pratica
- Archivio con export ZIP quando la pratica è definita
"""

import copy
import json
import uuid
import zipfile
import hashlib
import re
import shutil
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable, Optional, List
from dataclasses import dataclass, field, asdict
from enum import Enum

from pct.profilo_deposito import costruisci_profilo_deposito
from pct.pst_servizi_catalogo import SERVIZIO_PST_DOCUMENTI_FASCICOLO
from pct.fascicolo_document_presidio import normalise_practice_duplicate_key

_PROFILO_DEPOSITO_FASCICOLO_FIELDS = {
    "tipo",
    "tribunale",
    "tipo_procedimento",
    "id_pratica",
    "area_pratica",
    "source",
    "canale_operativo",
    "registro_operativo",
    "procedura_operativa_codice",
    "codice_oggetto_pst",
    "fonte_codice_oggetto",
    "file_fonte_codice_oggetto",
}


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


_DOCUMENTO_SEMANTIC_DEDUPE_TIPI = {
    TipoDocumento.ATTO_GIUDIZIARIO,
    TipoDocumento.MEMORIA,
    TipoDocumento.RICORSO,
    TipoDocumento.CITAZIONE,
    TipoDocumento.COMPARSA,
    TipoDocumento.SENTENZA,
    TipoDocumento.ORDINANZA,
    TipoDocumento.DECRETO,
    TipoDocumento.CONTRATTO,
    TipoDocumento.PROCURA,
    TipoDocumento.NOTIFICA,
    TipoDocumento.VERBALE,
}


def _normalizza_nome_documento_dedupe(nome: str) -> str:
    value = Path(str(nome or "")).name.strip().casefold()
    value = re.sub(r"\s+", " ", value)
    return value


def _documento_semantic_identity_key(doc: "Documento") -> str:
    tipo = getattr(doc, "tipo", TipoDocumento.ALTRO)
    if not isinstance(tipo, TipoDocumento):
        try:
            tipo = TipoDocumento(str(tipo))
        except ValueError:
            return ""
    if tipo not in _DOCUMENTO_SEMANTIC_DEDUPE_TIPI:
        return ""
    name = _normalizza_nome_documento_dedupe(getattr(doc, "nome", "") or getattr(doc, "nome_originale", ""))
    if not name.endswith(".pdf"):
        return ""
    return f"pdfname:{tipo.value}:{name}"


def _documento_identity_name_key(doc: "Documento") -> str:
    return _normalizza_nome_documento_match(
        getattr(doc, "nome_originale", "") or getattr(doc, "nome_portale", "") or getattr(doc, "nome", "")
    )


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


def _estensione_documento(nome_file: str) -> str:
    nome = Path(str(nome_file or "")).name
    lower = nome.lower()
    if lower.endswith(".p7m"):
        inner = Path(nome[:-4]).suffix
        return f"{inner}.p7m" if inner else ".p7m"
    return Path(nome).suffix


def _normalizza_nome_documento(nuovo_nome: str, nome_corrente: str) -> str:
    raw = str(nuovo_nome or "").strip()
    if not raw:
        raise ValueError("Indica il nuovo nome del documento.")
    if "/" in raw or "\\" in raw:
        raise ValueError("Il nome del documento non può contenere percorsi.")
    base = Path(raw).name.strip()
    if base in {"", ".", ".."}:
        raise ValueError("Nome documento non valido.")
    base = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "-", base).strip(" .")
    if not base:
        raise ValueError("Nome documento non valido.")
    estensione_originale = _estensione_documento(nome_corrente)
    estensione_nuova = _estensione_documento(base)
    if estensione_nuova:
        if estensione_originale and estensione_nuova.casefold() != estensione_originale.casefold():
            raise ValueError(f"L'estensione del documento resta {estensione_originale}.")
        if len(base) <= 180:
            return base
        stem = base[: -len(estensione_nuova)] if estensione_nuova else Path(base).stem
        return f"{stem[: max(1, 180 - len(estensione_nuova))]}{estensione_nuova}"
    if estensione_originale:
        return f"{base[: max(1, 180 - len(estensione_originale))]}{estensione_originale}"
    return base[:180]


class EsitoAttivita(str, Enum):
    IN_ATTESA       = "IN_ATTESA"
    FAVOREVOLE      = "FAVOREVOLE"
    PARZIALE        = "PARZIALE"
    SFAVOREVOLE     = "SFAVOREVOLE"
    RINVIATO        = "RINVIATO"
    ANNULLATO       = "ANNULLATO"
    NON_APPLICABILE = "NON_APPLICABILE"


def stato_fascicolo_da_descrizione_portale(
    valore: str | StatoFascicolo | None,
    *,
    default: Optional[StatoFascicolo] = None,
) -> Optional[StatoFascicolo]:
    """Normalizza le descrizioni stato dei portali nel corrispondente stato locale."""
    if isinstance(valore, StatoFascicolo):
        return valore
    testo = re.sub(r"[_\-/]+", " ", str(valore or "").upper()).strip()
    if not testo:
        return default
    if any(token in testo for token in ("ARCHIVIAT", "ESTINT")):
        return StatoFascicolo.ARCHIVIATO
    if any(token in testo for token in ("DEFINIT", "CONCLUS", "CHIUS")):
        return StatoFascicolo.DEFINITO
    if any(token in testo for token in ("SOSPES", "RINVIAT")):
        return StatoFascicolo.SOSPESO
    if any(token in testo for token in ("PENDENT", "IN CORSO", "APERTO", "ATTIVO")):
        return StatoFascicolo.IN_CORSO
    return default


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
    hash_contenuto_sha256: str = ""
    firmato_digitalmente: bool = False
    signature_metadata: dict[str, Any] = field(default_factory=dict)
    data_caricamento: str = field(default_factory=lambda: datetime.now().isoformat())
    data_documento: str = ""       # data del documento (es. data atto)
    note: str = ""
    tags: List[str] = field(default_factory=list)
    id_deposito_pct: str = ""      # collegamento a deposito PCT
    caricato_da: str = ""
    fonte_documento: str = ""      # CARICAMENTO_STUDIO | PORTALE_TELEMATICO | IMPORT_ESTERNO
    nome_originale: str = ""       # nome file effettivamente acquisito
    nome_portale: str = ""         # nome censito dal portale ufficiale
    classificazione_portale: str = ""
    tipo_atto_portale: str = ""
    servizio_portale: str = ""
    mittente_portale: str = ""
    data_deposito_portale: str = ""
    id_documento_portale: str = ""
    id_cat_portale: str = ""
    id_repeatto_portale: str = ""
    msg_id_portale: str = ""
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
        d.setdefault("tags", [])
        d.setdefault("signature_metadata", {})
        d.setdefault("hash_contenuto_sha256", "")
        d.setdefault("fonte_documento", "")
        d.setdefault("nome_originale", "")
        d.setdefault("nome_portale", "")
        d.setdefault("classificazione_portale", "")
        d.setdefault("tipo_atto_portale", "")
        d.setdefault("servizio_portale", "")
        d.setdefault("mittente_portale", "")
        d.setdefault("data_deposito_portale", "")
        d.setdefault("id_documento_portale", "")
        d.setdefault("id_cat_portale", "")
        d.setdefault("id_repeatto_portale", "")
        d.setdefault("msg_id_portale", "")
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
    email_mittente: str = ""
    email_oggetto: str = ""
    email_uid_imap: str = ""
    email_testo: str = ""
    email_html: str = ""
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
    "PROVA_SENZA_INVIO",
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


def _normalizza_nome_documento_match(nome: str) -> str:
    testo = Path(str(nome or "").strip()).name.casefold()
    testo = re.sub(r"\.p7m$", "", testo)
    testo = re.sub(r"\s+", "", testo)
    return re.sub(r"[^a-z0-9]+", "", testo)


def _format_data_ui_italiana(value: str) -> str:
    text = str(value or "").strip()
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", text)
    if not match:
        return text
    return f"{match.group(3)}/{match.group(2)}/{match.group(1)}"


def _normalizza_nota_import_portale(note: str) -> str:
    text = str(note or "").strip()
    if not text:
        return ""
    return re.sub(
        r"(Importato da [^|]+? il )(\d{4}-\d{2}-\d{2})",
        lambda match: f"{match.group(1)}{_format_data_ui_italiana(match.group(2))}",
        text,
        count=1,
    )


def _estrai_ref_documento_portale(value: str) -> set[str]:
    text = str(value or "").strip()
    if not text:
        return set()
    refs: set[str] = set()
    lowered = text.casefold()
    for match in re.finditer(r"pst:[a-z0-9_:/-]+", lowered):
        token = match.group(0).strip()
        refs.add(token)
        tail = token.rsplit(":", 1)[-1].strip()
        if tail.isdigit() and len(tail) >= 6:
            refs.add(tail)
    basename = Path(text).name
    if basename:
        stem = re.sub(r"\.p7m$", "", basename, flags=re.IGNORECASE)
        stem = Path(stem).stem
        for match in re.finditer(r"(?<!\d)(\d{6,})(?!\d)", stem):
            refs.add(match.group(1))
    for match in re.finditer(r"\b(?:doc|msg|cat|rep)[-_:/]?[a-z0-9]+\b", lowered):
        refs.add(match.group(0).strip())
    return refs


def _documento_portale_payload(dep: "EsitoDepositoPCT", item: dict | None) -> dict[str, str]:
    row = dict(item or {})
    return {
        "fonte_documento": "PORTALE_TELEMATICO",
        "nome_portale": str(row.get("nome") or "").strip(),
        "classificazione_portale": str(row.get("tipo") or "").strip(),
        "tipo_atto_portale": str(row.get("tipo_atto") or getattr(dep, "tipo_atto", "") or "").strip(),
        "servizio_portale": str(getattr(dep, "servizio_portale", "") or "").strip(),
        "mittente_portale": str(row.get("mittente") or getattr(dep, "pec_destinatario", "") or "").strip(),
        "data_deposito_portale": str(row.get("data_deposito") or "").strip(),
        "id_documento_portale": str(row.get("id_documento") or "").strip(),
        "id_cat_portale": str(row.get("id_cat") or "").strip(),
        "id_repeatto_portale": str(row.get("id_repeatto") or "").strip(),
        "id_reperto_portale": str(row.get("id_reperto") or "").strip(),
        "msg_id_portale": str(row.get("msg_id") or "").strip(),
        "id_documento_padre_portale": str(row.get("id_documento_padre") or row.get("parent_id_documento") or "").strip(),
        "parent_nome_portale": str(row.get("parent_nome") or "").strip(),
        "allegato_portale": str(bool(row.get("is_allegato"))).lower(),
    }


def _deduplica_documenti_ids(documenti_ids: Iterable[str]) -> List[str]:
    normalizzati: List[str] = []
    visti: set[str] = set()
    for raw in documenti_ids or []:
        doc_id = str(raw or "").strip()
        if not doc_id or doc_id in visti:
            continue
        visti.add(doc_id)
        normalizzati.append(doc_id)
    return normalizzati


def _documento_portale_nome_keys(nome: str) -> set[str]:
    key = _normalizza_nome_documento_match(nome)
    return {key} if key else set()


def _documento_portale_ref_keys(item: dict[str, Any] | None) -> set[str]:
    row = dict(item or {})
    refs: set[str] = set()
    for field_name in ("id_documento", "id_cat", "id_repeatto", "id_reperto", "msg_id"):
        value = str(row.get(field_name) or "").strip()
        if value:
            refs.add(value.casefold())
            refs.update(_estrai_ref_documento_portale(value))
    refs.update(_estrai_ref_documento_portale(str(row.get("nome") or "")))
    return refs


def _documento_locale_nome_keys(doc: "Documento") -> set[str]:
    keys: set[str] = set()
    for value in (getattr(doc, "nome", ""), getattr(doc, "nome_originale", ""), getattr(doc, "nome_portale", "")):
        keys.update(_documento_portale_nome_keys(str(value or "")))
    return keys


def _documento_locale_ref_keys(doc: "Documento") -> set[str]:
    refs: set[str] = set()
    for value in (
        getattr(doc, "id_documento_portale", ""),
        getattr(doc, "id_cat_portale", ""),
        getattr(doc, "id_repeatto_portale", ""),
        getattr(doc, "msg_id_portale", ""),
    ):
        current = str(value or "").strip()
        if current:
            refs.add(current.casefold())
            refs.update(_estrai_ref_documento_portale(current))
    for value in (
        getattr(doc, "nome_originale", ""),
        getattr(doc, "nome_portale", ""),
        getattr(doc, "note", ""),
    ):
        refs.update(_estrai_ref_documento_portale(str(value or "")))
    return refs


def _documento_locale_ref_keys_origine(doc: "Documento") -> set[str]:
    refs: set[str] = set()
    for value in (
        getattr(doc, "nome_originale", ""),
        getattr(doc, "note", ""),
    ):
        refs.update(_estrai_ref_documento_portale(str(value or "")))
    return refs


def _documento_locale_nome_keys_origine(doc: "Documento") -> set[str]:
    keys: set[str] = set()
    for value in (
        getattr(doc, "nome_originale", ""),
        getattr(doc, "nome", ""),
    ):
        keys.update(_documento_portale_nome_keys(str(value or "")))
    return keys


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
    valore_preventivato: float = 0.0  # compenso pattuito da preventivo/conferimento

    # --- Pratica collegata (dal preventivo/conferimento)
    tipo_procedimento: str = ""
    id_pratica: str = ""
    area_pratica: str = ""
    codice_oggetto_pst: str = ""
    fonte_codice_oggetto: str = ""
    file_fonte_codice_oggetto: str = ""
    profilo_deposito: dict[str, Any] = field(default_factory=dict)
    codice_guida_pratica: str = ""  # codice scheda guida, anche alias interno non depositabile
    riferimento_cartaceo: str = ""
    attore_principale: str = ""
    istruttore_pm_gip: str = ""
    cancelliere: str = ""
    ctu: str = ""
    ctp: str = ""
    stato_pratica_operativa: str = ""
    personalizzabile: bool = False
    fascicolo_veloce: bool = False
    documenti_iniziali_count: int = 0
    email_iniziali_count: int = 0
    procedura_operativa_codice: str = ""
    procedura_operativa_nome: str = ""
    subbranch_operativa_codice: str = ""
    workflow_operativo_codice: str = ""
    copertura_operativa: str = ""
    canale_operativo: str = ""
    registro_operativo: str = ""
    compenso_pattuito: float = 0.0  # importo totale dal conferimento incarico
    pagamenti: dict[str, Any] = field(default_factory=dict)

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
    codice_ufficio_portale: str = ""    # codice ufficio ministeriale/portale usato per l'aggancio
    id_fascicolo_portale: str = ""      # id pratica/fascicolo esposto dal portale, se disponibile
    tipo_registro: str = ""             # registro nativo del portale (SICID/SIECIC/SIGP/PDP/PAT/PTT)
    registro_portale: str = ""          # registro normalizzato usato dal servizio portale
    servizio_pst: str = ""              # servizio PST/QBuilder effettivamente usato
    sub_procedimento: str = ""          # subprocedimento ministeriale quando necessario
    id_dfa: str = ""                    # identificativo DFA per SIECIC/SIGP quando disponibile
    ruolo_polisweb: str = ""            # ruolo usato nella consultazione PolisWeb
    last_sync_at: str = ""              # ISO datetime ultimo allineamento
    sync_status: str = ""               # IMPORTATO | SINCRONIZZATO | DA_VERIFICARE
    import_log_id: str = ""             # id log acquisizione guidata
    source_snapshot: dict[str, Any] = field(default_factory=dict)
    has_conflicts: bool = False
    document_sync_enabled: bool = False
    events_sync_enabled: bool = False
    compliance_controls_enabled: bool = True

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
        if not isinstance(d.get("profilo_deposito"), dict):
            d["profilo_deposito"] = {}
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
        documents_dir: Optional[str] = None,
        archive_dir: Optional[str] = None,
        studio_db=None,
    ):
        self.db_path = Path(db_path)
        self.documents_dir = (
            Path(documents_dir)
            if str(documents_dir or "").strip()
            else self.db_path.parent / "documenti"
        )
        self.archive_dir = (
            Path(archive_dir)
            if str(archive_dir or "").strip()
            else self.db_path.parent / "archivio"
        )
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
            profilo_sql = d.get("profilo_deposito_json")
            if profilo_sql:
                try:
                    profilo_payload = _json.loads(profilo_sql)
                except Exception:
                    profilo_payload = {}
                if isinstance(profilo_payload, dict) and profilo_payload:
                    payload["profilo_deposito"] = profilo_payload
            _migra_payload_depositi_pct(payload)
            return Fascicolo.from_dict(payload)
        except Exception:
            return None

    def _payloads_da_json_bootstrap(self) -> list[dict[str, Any]]:
        """Legge il mirror JSON solo come bootstrap controllato quando SQL e' vuoto."""
        from pct import cache as _cache

        raw = _cache.load(self.db_path)
        if isinstance(raw, dict):
            return [item for item in raw.values() if isinstance(item, dict)]
        if isinstance(raw, list):
            return [item for item in raw if isinstance(item, dict)]
        return []

    def _carica(self) -> None:
        if self._studio_db is not None:
            rows = self._studio_db.conn.execute(
                "SELECT * FROM fascicoli"
            ).fetchall()
            self._fascicoli = {}
            if not rows:
                for payload in self._payloads_da_json_bootstrap():
                    try:
                        _migra_payload_depositi_pct(payload)
                        fascicolo = Fascicolo.from_dict(payload)
                    except Exception:
                        continue
                    self._fascicoli[fascicolo.id] = fascicolo
                if self._fascicoli:
                    self._salva()
                return
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
        payloads = self._payloads_da_json_bootstrap()
        migrato = False
        for payload in payloads:
            migrato = _migra_payload_depositi_pct(payload) or migrato
        self._fascicoli = {}
        for payload in payloads:
            try:
                fascicolo = Fascicolo.from_dict(payload)
            except Exception:
                continue
            self._fascicoli[fascicolo.id] = fascicolo
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
                     attivita_json, documenti_json, scadenze_json,
                     profilo_deposito_json, dati_json)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
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
                        _json.dumps(d.get("profilo_deposito", {}), ensure_ascii=False),
                        _json.dumps(d, ensure_ascii=False),
                    ),
                )

            self._studio_db.salva_tabella("fascicoli", list(self._fascicoli.values()), _insert)
            try:
                from pct import cache as _cache
                _cache.save(self.db_path, {k: v.to_dict() for k, v in self._fascicoli.items()})
            except Exception:
                pass
            return
        from pct import cache as _cache
        _cache.save(self.db_path, {k: v.to_dict() for k, v in self._fascicoli.items()})

    def _rigenera_mirror_fascicoli_json(self) -> None:
        if self._studio_db is None:
            return
        try:
            from pct import cache as _cache
            _cache.save(self.db_path, {k: v.to_dict() for k, v in self._fascicoli.items()})
        except Exception:
            pass

    def _salva_fascicoli_parziale(
        self,
        fascicoli: Iterable["Fascicolo"],
        *,
        rigenera_mirror: bool = True,
    ) -> None:
        if self._studio_db is None:
            self._salva()
            return
        import json as _json

        rows = list(fascicoli)
        if not rows:
            return
        conn = self._studio_db.conn
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("BEGIN IMMEDIATE")
        try:
            for f in rows:
                d = f.to_dict()
                values = (
                    f.numero,
                    f.titolo,
                    f.tipo.value,
                    f.stato.value,
                    f.id_cliente or None,
                    f.nome_cliente,
                    f.tribunale,
                    f.sezione,
                    f.giudice,
                    f.numero_rg,
                    str(f.anno_rg) if f.anno_rg else "",
                    f.controparte,
                    f.avvocato_referente,
                    f.avvocato_dominus,
                    f.data_apertura,
                    f.data_chiusura,
                    f.oggetto,
                    f.note,
                    f.creato_il,
                    _json.dumps(d.get("attivita", []), ensure_ascii=False),
                    _json.dumps(d.get("documenti", []), ensure_ascii=False),
                    _json.dumps(d.get("depositi_pct", []), ensure_ascii=False),
                    _json.dumps(d.get("profilo_deposito", {}), ensure_ascii=False),
                    _json.dumps(d, ensure_ascii=False),
                    f.id,
                )
                cur = conn.execute(
                    """
                    UPDATE fascicoli
                    SET numero=?, titolo=?, tipo=?, stato=?, id_cliente=?, nome_cliente=?,
                        tribunale=?, sezione=?, giudice=?, numero_rg=?, anno_rg=?,
                        controparte=?, avvocato_referente=?, avvocato_dominus=?,
                        data_apertura=?, data_chiusura=?, oggetto=?, note=?, creato_il=?,
                        attivita_json=?, documenti_json=?, scadenze_json=?,
                        profilo_deposito_json=?, dati_json=?
                    WHERE id=?
                    """,
                    values,
                )
                if cur.rowcount:
                    continue
                conn.execute(
                    """
                    INSERT INTO fascicoli
                    (id, numero, titolo, tipo, stato, id_cliente, nome_cliente,
                     tribunale, sezione, giudice, numero_rg, anno_rg,
                     controparte, avvocato_referente, avvocato_dominus,
                     data_apertura, data_chiusura, oggetto, note, creato_il,
                     attivita_json, documenti_json, scadenze_json,
                     profilo_deposito_json, dati_json)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (f.id, *values[:-1]),
                )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        if rigenera_mirror:
            self._rigenera_mirror_fascicoli_json()

    def _rimuovi_fascicoli_parziale(
        self,
        fascicoli_ids: Iterable[str],
        *,
        rigenera_mirror: bool = True,
    ) -> None:
        ids = [str(item or "").strip() for item in fascicoli_ids if str(item or "").strip()]
        if not ids:
            return
        if self._studio_db is None:
            self._salva()
            return
        conn = self._studio_db.conn
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.executemany("DELETE FROM fascicoli WHERE id=?", [(item,) for item in ids])
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        if rigenera_mirror:
            self._rigenera_mirror_fascicoli_json()

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
        prefix = f"{anno}/"
        used = {
            str(f.numero or "").strip()
            for f in self._fascicoli.values()
            if str(f.numero or "").strip().startswith(prefix)
        }
        max_seq = 0
        for numero in used:
            match = re.match(rf"^{anno}/(\d+)$", numero)
            if match:
                max_seq = max(max_seq, int(match.group(1)))
        seq = max_seq + 1
        while True:
            candidate = f"{anno}/{seq:03d}"
            if candidate not in used:
                return candidate
            seq += 1

    # ---------------------------------------------------------------- Presidi qualità dati

    def _chiave_identita_pratica(self, fascicolo: "Fascicolo") -> str:
        return normalise_practice_duplicate_key(fascicolo)

    def _trova_fascicolo_duplicato(self, candidato: "Fascicolo") -> Optional["Fascicolo"]:
        key = self._chiave_identita_pratica(candidato)
        if not key:
            return None
        for fascicolo in self._fascicoli.values():
            if fascicolo.id == candidato.id:
                continue
            if self._chiave_identita_pratica(fascicolo) == key:
                return fascicolo
        return None

    @staticmethod
    def _stato_pagamento_vuoto(value: Any) -> bool:
        if not isinstance(value, dict):
            return value in {None, ""}
        amount = value.get("importo") if "importo" in value else value.get("amount")
        try:
            has_amount = abs(float(amount or 0)) > 0.01
        except (TypeError, ValueError):
            has_amount = False
        status = str(value.get("status") or value.get("stato") or "").strip().lower()
        if has_amount:
            return False
        return status in {"", "non_previsto", "da_registrare", "da_emettere"}

    @staticmethod
    def _campo_pagamento_vuoto(value: Any) -> bool:
        return value is None or value == "" or value == [] or value == {}

    @classmethod
    def _merge_pagamenti_preservando_manualita(
        cls,
        primary: dict[str, Any] | None,
        incoming: dict[str, Any] | None,
    ) -> dict[str, Any]:
        merged = dict(primary or {})
        for key, value in dict(incoming or {}).items():
            if key not in merged or cls._stato_pagamento_vuoto(merged.get(key)):
                merged[key] = copy.deepcopy(value)
                continue
            if isinstance(merged.get(key), dict) and isinstance(value, dict):
                current = dict(merged[key])
                for field_name, field_value in value.items():
                    if field_name not in current or cls._campo_pagamento_vuoto(current.get(field_name)):
                        current[field_name] = copy.deepcopy(field_value)
                merged[key] = current
        return merged

    @staticmethod
    def _preferisci_data_prossima(current: str, incoming: str) -> str:
        current = str(current or "").strip()
        incoming = str(incoming or "").strip()
        if not current:
            return incoming
        if not incoming:
            return current
        oggi = date.today().isoformat()
        if current >= oggi and incoming >= oggi:
            return min(current, incoming)
        if incoming >= oggi and current < oggi:
            return incoming
        return current

    def _assorbi_campi_base(self, primary: "Fascicolo", incoming: "Fascicolo") -> bool:
        changed = False
        fill_if_empty = (
            "titolo",
            "id_cliente",
            "nome_cliente",
            "controparte",
            "cf_controparte",
            "tribunale",
            "numero_rg",
            "anno_rg",
            "giudice",
            "sezione",
            "avvocato_referente",
            "avvocato_dominus",
            "oggetto",
            "tipo_procedimento",
            "id_pratica",
            "area_pratica",
            "codice_oggetto_pst",
            "fonte_codice_oggetto",
            "file_fonte_codice_oggetto",
            "riferimento_cartaceo",
            "attore_principale",
            "cancelliere",
            "ctu",
            "ctp",
            "source",
            "source_external_id",
            "codice_ufficio_portale",
            "id_fascicolo_portale",
            "tipo_registro",
            "registro_portale",
            "servizio_pst",
            "sub_procedimento",
            "id_dfa",
            "ruolo_polisweb",
            "sync_status",
            "import_log_id",
        )
        for field_name in fill_if_empty:
            current = getattr(primary, field_name, "")
            incoming_value = getattr(incoming, field_name, "")
            if current in {None, "", 0} and incoming_value not in {None, "", 0}:
                setattr(primary, field_name, copy.deepcopy(incoming_value))
                changed = True
        for field_name in ("valore_causa", "valore_preventivato", "compenso_pattuito"):
            if not float(getattr(primary, field_name, 0) or 0) and float(getattr(incoming, field_name, 0) or 0):
                setattr(primary, field_name, getattr(incoming, field_name))
                changed = True
        for field_name in ("data_apertura", "data_chiusura", "data_prima_udienza"):
            current = str(getattr(primary, field_name, "") or "").strip()
            incoming_value = str(getattr(incoming, field_name, "") or "").strip()
            if not current and incoming_value:
                setattr(primary, field_name, incoming_value)
                changed = True
        next_date = self._preferisci_data_prossima(primary.data_prossima_udienza, incoming.data_prossima_udienza)
        if next_date != primary.data_prossima_udienza:
            primary.data_prossima_udienza = next_date
            changed = True
        merged_payments = self._merge_pagamenti_preservando_manualita(primary.pagamenti, incoming.pagamenti)
        if merged_payments != (primary.pagamenti or {}):
            primary.pagamenti = merged_payments
            changed = True
        if not primary.profilo_deposito and incoming.profilo_deposito:
            primary.profilo_deposito = copy.deepcopy(incoming.profilo_deposito)
            changed = True
        if not primary.source_snapshot and incoming.source_snapshot:
            primary.source_snapshot = copy.deepcopy(incoming.source_snapshot)
            changed = True
        return changed

    @staticmethod
    def _documento_identity_keys(doc: "Documento") -> set[str]:
        keys: set[str] = set()
        semantic_key = _documento_semantic_identity_key(doc)
        if semantic_key:
            keys.add(semantic_key)
        name = _documento_identity_name_key(doc)
        raw_sha = str(getattr(doc, "hash_contenuto_sha256", "") or "").strip().lower()
        if raw_sha and name:
            keys.add(f"rawsha:{name}:{raw_sha}")
        sha = str(getattr(doc, "hash_sha256", "") or "").strip().lower()
        if sha and name:
            keys.add(f"sha:{name}:{sha}")
        for value in (
            getattr(doc, "id_documento_portale", ""),
            getattr(doc, "id_cat_portale", ""),
            getattr(doc, "id_repeatto_portale", ""),
            getattr(doc, "msg_id_portale", ""),
        ):
            text = str(value or "").strip().lower()
            if text:
                keys.add(f"portal:{text}")
        if name:
            keys.add(f"name:{name}:{int(getattr(doc, 'dimensione_bytes', 0) or 0)}")
        return keys

    @staticmethod
    def _assorbi_metadati_documento(
        primary: "Documento",
        duplicate: "Documento",
        *,
        conserva_file_come_versione: bool = False,
    ) -> bool:
        """Conserva il documento principale arricchendolo con metadati mancanti."""
        changed = False
        if primary.tipo == TipoDocumento.ALTRO and duplicate.tipo != TipoDocumento.ALTRO:
            primary.tipo = duplicate.tipo
            changed = True
        for field_name in (
            "note",
            "data_documento",
            "hash_contenuto_sha256",
            "id_deposito_pct",
            "caricato_da",
            "fonte_documento",
            "nome_originale",
            "nome_portale",
            "classificazione_portale",
            "tipo_atto_portale",
            "servizio_portale",
            "mittente_portale",
            "data_deposito_portale",
            "id_documento_portale",
            "id_cat_portale",
            "id_repeatto_portale",
            "msg_id_portale",
        ):
            current = str(getattr(primary, field_name, "") or "").strip()
            incoming = str(getattr(duplicate, field_name, "") or "").strip()
            if not current and incoming:
                setattr(primary, field_name, incoming)
                changed = True
        existing_tags = {str(tag or "").strip().casefold() for tag in primary.tags or [] if str(tag or "").strip()}
        tags = list(primary.tags or [])
        for tag in duplicate.tags or []:
            value = str(tag or "").strip()
            key = value.casefold()
            if value and key not in existing_tags:
                tags.append(value)
                existing_tags.add(key)
                changed = True
        if tags != (primary.tags or []):
            primary.tags = tags
        if duplicate.firmato_digitalmente and not primary.firmato_digitalmente:
            primary.firmato_digitalmente = True
            changed = True
        if not primary.signature_metadata and duplicate.signature_metadata:
            primary.signature_metadata = copy.deepcopy(duplicate.signature_metadata)
            changed = True
        known_versions = {
            (
                str(getattr(version, "hash_sha256", "") or ""),
                str(getattr(version, "percorso", "") or ""),
            )
            for version in primary.versioni or []
        }
        if conserva_file_come_versione and str(getattr(duplicate, "percorso", "") or "").strip():
            key = (
                str(getattr(duplicate, "hash_sha256", "") or ""),
                str(getattr(duplicate, "percorso", "") or ""),
            )
            if key not in known_versions:
                primary.versioni.append(
                    DocumentoVersione(
                        hash_sha256=str(getattr(duplicate, "hash_sha256", "") or ""),
                        percorso=str(getattr(duplicate, "percorso", "") or ""),
                        dimensione_bytes=int(getattr(duplicate, "dimensione_bytes", 0) or 0),
                        sostituito_il=str(getattr(duplicate, "data_caricamento", "") or datetime.now().isoformat()),
                        sostituito_da=str(
                            getattr(duplicate, "caricato_da", "")
                            or getattr(duplicate, "fonte_documento", "")
                            or "IUSENTRA"
                        ),
                    )
                )
                known_versions.add(key)
                changed = True
        if duplicate.versioni:
            for version in duplicate.versioni:
                key = (
                    str(getattr(version, "hash_sha256", "") or ""),
                    str(getattr(version, "percorso", "") or ""),
                )
                if key in known_versions:
                    continue
                primary.versioni.append(copy.deepcopy(version))
                known_versions.add(key)
                changed = True
        return changed

    @staticmethod
    def _documento_group_score(
        doc: "Documento",
        *,
        referenced_doc_ids: set[str],
        original_index: int,
    ) -> tuple[int, int, int, int, int]:
        source = str(getattr(doc, "fonte_documento", "") or "").strip().upper()
        source_score = 3 if source == "PORTALE_TELEMATICO" else 2 if source == "IMPORT_ESTERNO" else 1
        metadata_score = sum(
            1
            for field_name in (
                "id_documento_portale",
                "id_cat_portale",
                "id_repeatto_portale",
                "msg_id_portale",
                "nome_portale",
                "classificazione_portale",
                "tipo_atto_portale",
                "servizio_portale",
            )
            if str(getattr(doc, field_name, "") or "").strip()
        )
        return (
            1 if doc.id in referenced_doc_ids else 0,
            source_score,
            metadata_score,
            1 if bool(getattr(doc, "firmato_digitalmente", False)) else 0,
            -original_index,
        )

    def _riconcilia_documenti_duplicati_fascicolo(
        self,
        fascicolo: "Fascicolo",
        *,
        dry_run: bool,
    ) -> tuple[dict[str, Any], bool]:
        docs = list(fascicolo.documenti or [])
        report: dict[str, Any] = {
            "fascicoloId": fascicolo.id,
            "numero": fascicolo.numero,
            "titolo": fascicolo.titolo,
            "documenti": len(docs),
            "groups": [],
            "removed": 0,
        }
        if len(docs) < 2:
            return report, False

        parent = list(range(len(docs)))

        def find(index: int) -> int:
            while parent[index] != index:
                parent[index] = parent[parent[index]]
                index = parent[index]
            return index

        def union(left: int, right: int) -> None:
            root_left = find(left)
            root_right = find(right)
            if root_left != root_right:
                parent[root_right] = root_left

        seen_by_key: dict[str, int] = {}
        for index, doc in enumerate(docs):
            for key in self._documento_identity_keys(doc):
                previous = seen_by_key.get(key)
                if previous is None:
                    seen_by_key[key] = index
                else:
                    union(previous, index)

        groups_by_root: dict[int, list[int]] = {}
        for index in range(len(docs)):
            groups_by_root.setdefault(find(index), []).append(index)
        duplicate_groups = [indexes for indexes in groups_by_root.values() if len(indexes) > 1]
        if not duplicate_groups:
            return report, False

        referenced_doc_ids = {
            str(doc_id or "").strip()
            for dep in fascicolo.depositi_pct or []
            for doc_id in getattr(dep, "documenti_ids", []) or []
            if str(doc_id or "").strip()
        }
        referenced_doc_ids.update(
            str(getattr(att, "id_documento", "") or "").strip()
            for att in fascicolo.attivita or []
            if str(getattr(att, "id_documento", "") or "").strip()
        )

        removed_ids: set[str] = set()
        doc_id_map: dict[str, str] = {}
        changed = False
        for indexes in duplicate_groups:
            ordered = sorted(
                indexes,
                key=lambda idx: self._documento_group_score(
                    docs[idx],
                    referenced_doc_ids=referenced_doc_ids,
                    original_index=idx,
                ),
                reverse=True,
            )
            primary = docs[ordered[0]]
            duplicates = [docs[idx] for idx in ordered[1:]]
            report_group = {
                "primaryId": primary.id,
                "primaryName": primary.nome,
                "duplicates": [{"id": doc.id, "name": doc.nome} for doc in duplicates],
            }
            report["groups"].append(report_group)
            report["removed"] += len(duplicates)
            if dry_run:
                continue
            for duplicate in duplicates:
                doc_id_map[duplicate.id] = primary.id
                removed_ids.add(duplicate.id)
                conserva_file = (
                    bool(_documento_semantic_identity_key(primary))
                    and _documento_semantic_identity_key(primary) == _documento_semantic_identity_key(duplicate)
                    and str(getattr(primary, "hash_sha256", "") or "").strip().casefold()
                    != str(getattr(duplicate, "hash_sha256", "") or "").strip().casefold()
                )
                changed = (
                    self._assorbi_metadati_documento(
                        primary,
                        duplicate,
                        conserva_file_come_versione=conserva_file,
                    )
                    or changed
                )

        if dry_run or not removed_ids:
            return report, False

        for dep in fascicolo.depositi_pct or []:
            updated_ids = _deduplica_documenti_ids(
                doc_id_map.get(str(doc_id or "").strip(), str(doc_id or "").strip())
                for doc_id in getattr(dep, "documenti_ids", []) or []
            )
            if updated_ids != (dep.documenti_ids or []):
                dep.documenti_ids = updated_ids
                changed = True
        for att in fascicolo.attivita or []:
            current = str(getattr(att, "id_documento", "") or "").strip()
            replacement = doc_id_map.get(current)
            if replacement and replacement != current:
                att.id_documento = replacement
                changed = True

        fascicolo.documenti = [doc for doc in docs if doc.id not in removed_ids]
        fascicolo.avanzamento.append(
            AvanzamentoPratica(
                data=datetime.now().isoformat(),
                descrizione="Riconciliazione automatica documenti duplicati",
                stato_precedente=fascicolo.stato.value,
                stato_nuovo=fascicolo.stato.value,
                note=f"Assorbiti {len(removed_ids)} record documento duplicati mantenendo il documento principale.",
                avvocato="IUSENTRA",
            )
        )
        fascicolo.modificato_il = datetime.now().isoformat()
        return report, True

    def riconcilia_documenti_duplicati(
        self,
        id_fasc: str | None = None,
        *,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Assorbe record documento duplicati nello stesso fascicolo senza perdere riferimenti."""
        fascicoli = [self._get_o_errore(id_fasc)] if id_fasc else list(self._fascicoli.values())
        source_of_truth = (
            str(getattr(self._studio_db, "backend_kind", "") or "sqlite")
            if self._studio_db is not None
            else "json_mirror"
        )
        report: dict[str, Any] = {
            "ok": True,
            "dryRun": bool(dry_run),
            "source_of_truth": source_of_truth,
            "fascicoliAnalizzati": len(fascicoli),
            "fascicoliConDuplicati": 0,
            "documentiDuplicatiAssorbiti": 0,
            "groups": [],
        }
        touched = False
        touched_fascicoli: list[Fascicolo] = []
        for fascicolo in fascicoli:
            entry, changed = self._riconcilia_documenti_duplicati_fascicolo(fascicolo, dry_run=dry_run)
            if entry.get("removed"):
                report["fascicoliConDuplicati"] += 1
                report["documentiDuplicatiAssorbiti"] += int(entry.get("removed") or 0)
                report["groups"].append(entry)
            if changed:
                touched_fascicoli.append(fascicolo)
            touched = touched or changed
        if touched:
            self._salva_fascicoli_parziale(touched_fascicoli)
        return report

    def _copia_documento_su_fascicolo_principale(
        self,
        primary: "Fascicolo",
        source_fascicolo: "Fascicolo",
        doc: "Documento",
        *,
        existing_doc_ids: set[str],
    ) -> "Documento":
        cloned = copy.deepcopy(doc)
        old_id = cloned.id
        if cloned.id in existing_doc_ids:
            cloned.id = uuid.uuid4().hex[:8].upper()
        source_path = self.documents_dir / Path(str(getattr(doc, "percorso", "") or "").replace("\\", "/"))
        target_dir = self.documents_dir / primary.id
        target_dir.mkdir(parents=True, exist_ok=True)
        if source_path.exists():
            base_name = Path(cloned.percorso or cloned.nome or f"{cloned.id}.bin").name
            target_path = target_dir / base_name
            if target_path.exists():
                stem = target_path.stem
                suffix = target_path.suffix
                target_path = target_dir / f"{stem}_{uuid.uuid4().hex[:4]}{suffix}"
            shutil.copy2(source_path, target_path)
            cloned.percorso = str(target_path.relative_to(self.documents_dir))
        marker = f"Riconciliato da fascicolo {source_fascicolo.numero or source_fascicolo.id}."
        if marker not in str(cloned.note or ""):
            cloned.note = " ".join(part for part in [str(cloned.note or "").strip(), marker] if part)
        tags = list(cloned.tags or [])
        if "riconciliazione-doppione" not in tags:
            tags.append("riconciliazione-doppione")
        cloned.tags = tags
        existing_doc_ids.add(cloned.id)
        if old_id != cloned.id:
            cloned.note = " ".join(part for part in [cloned.note, f"ID origine {old_id}."] if part)
        return cloned

    @staticmethod
    def _unique_serialized_rows(rows: Iterable[Any], key_fields: tuple[str, ...]) -> set[tuple[str, ...]]:
        out: set[tuple[str, ...]] = set()
        for row in rows or []:
            out.add(tuple(str(getattr(row, field, "") or "").strip().casefold() for field in key_fields))
        return out

    @staticmethod
    def _score_fascicolo_principale(fascicolo: "Fascicolo") -> tuple[int, int, int, int, str]:
        active = 0 if fascicolo.stato == StatoFascicolo.ARCHIVIATO else 1
        payments = getattr(fascicolo, "pagamenti", {}) or {}
        economic = sum(1 for value in payments.values() if not GestioneFascicoli._stato_pagamento_vuoto(value))
        return (
            active,
            len(getattr(fascicolo, "documenti", []) or []),
            economic,
            1 if str(getattr(fascicolo, "data_prossima_udienza", "") or "").strip() else 0,
            str(getattr(fascicolo, "modificato_il", "") or ""),
        )

    def _segna_analisi_fascicolo_da_rieseguire(
        self,
        fascicolo: "Fascicolo",
        *,
        reason: str,
        document_id: str = "",
    ) -> None:
        payments = dict(fascicolo.pagamenti or {})
        payments["_presidio_documentale"] = {
            "status": "stale",
            "reason": reason,
            "document_id": str(document_id or "").strip(),
            "updated_at": datetime.now().isoformat(),
        }
        fascicolo.pagamenti = payments

    def riconcilia_doppioni_cliente_rg(self, *, dry_run: bool = False) -> dict[str, Any]:
        groups: dict[str, list[Fascicolo]] = {}
        for fascicolo in self._fascicoli.values():
            key = self._chiave_identita_pratica(fascicolo)
            if key:
                groups.setdefault(key, []).append(fascicolo)
        report: dict[str, Any] = {
            "ok": True,
            "dryRun": bool(dry_run),
            "source_of_truth": "sqlite" if self._studio_db is not None else "json",
            "groups": [],
            "merged": 0,
            "removedDuplicates": 0,
        }
        touched = False
        touched_fascicoli: dict[str, Fascicolo] = {}
        removed_ids: list[str] = []
        for key, rows in sorted(groups.items()):
            if len(rows) < 2:
                continue
            ordered = sorted(rows, key=self._score_fascicolo_principale, reverse=True)
            primary = ordered[0]
            group_touched = False
            entry = {
                "key": key,
                "primaryId": primary.id,
                "primaryRef": primary.numero or primary.rg_completo,
                "mergedIds": [row.id for row in ordered[1:]],
                "documentsAdded": 0,
                "documentsSkipped": 0,
                "activitiesAdded": 0,
                "depositsAdded": 0,
            }
            if dry_run:
                report["groups"].append(entry)
                continue
            existing_doc_ids = {doc.id for doc in primary.documenti}
            existing_doc_keys = {key for doc in primary.documenti for key in self._documento_identity_keys(doc)}
            existing_activities = self._unique_serialized_rows(
                primary.attivita,
                ("tipo", "data", "titolo", "descrizione", "id_deposito_pct", "id_documento"),
            )
            existing_deposits = self._unique_serialized_rows(
                primary.depositi_pct,
                ("id_deposito_esterno", "timestamp", "tipo_atto", "messaggio", "fonte_portale"),
            )
            for duplicate in ordered[1:]:
                if self._assorbi_campi_base(primary, duplicate):
                    group_touched = True
                    touched = True
                doc_id_map: dict[str, str] = {}
                for doc in list(duplicate.documenti or []):
                    doc_keys = self._documento_identity_keys(doc)
                    if doc_keys and existing_doc_keys.intersection(doc_keys):
                        doc_id_map[doc.id] = next((existing.id for existing in primary.documenti if self._documento_identity_keys(existing).intersection(doc_keys)), doc.id)
                        entry["documentsSkipped"] += 1
                        continue
                    cloned = self._copia_documento_su_fascicolo_principale(
                        primary,
                        duplicate,
                        doc,
                        existing_doc_ids=existing_doc_ids,
                    )
                    primary.documenti.append(cloned)
                    doc_id_map[doc.id] = cloned.id
                    existing_doc_keys.update(self._documento_identity_keys(cloned))
                    entry["documentsAdded"] += 1
                    group_touched = True
                    touched = True
                for dep in list(duplicate.depositi_pct or []):
                    dep_key = tuple(
                        str(getattr(dep, field, "") or "").strip().casefold()
                        for field in ("id_deposito_esterno", "timestamp", "tipo_atto", "messaggio", "fonte_portale")
                    )
                    if dep_key in existing_deposits:
                        continue
                    cloned_dep = copy.deepcopy(dep)
                    if cloned_dep.id in {item.id for item in primary.depositi_pct}:
                        old_dep_id = cloned_dep.id
                        cloned_dep.id = uuid.uuid4().hex[:8].upper()
                        for doc in primary.documenti:
                            if doc.id_deposito_pct == old_dep_id:
                                doc.id_deposito_pct = cloned_dep.id
                    cloned_dep.documenti_ids = _deduplica_documenti_ids(
                        doc_id_map.get(doc_id, doc_id) for doc_id in (cloned_dep.documenti_ids or [])
                    )
                    primary.depositi_pct.append(cloned_dep)
                    existing_deposits.add(dep_key)
                    entry["depositsAdded"] += 1
                    group_touched = True
                    touched = True
                for att in list(duplicate.attivita or []):
                    att_key = tuple(
                        str(getattr(att, field, "") or "").strip().casefold()
                        for field in ("tipo", "data", "titolo", "descrizione", "id_deposito_pct", "id_documento")
                    )
                    if att_key in existing_activities:
                        continue
                    cloned_att = copy.deepcopy(att)
                    if cloned_att.id in {item.id for item in primary.attivita}:
                        cloned_att.id = uuid.uuid4().hex[:8].upper()
                    if cloned_att.id_documento:
                        cloned_att.id_documento = doc_id_map.get(cloned_att.id_documento, cloned_att.id_documento)
                    primary.attivita.append(cloned_att)
                    existing_activities.add(att_key)
                    entry["activitiesAdded"] += 1
                    group_touched = True
                    touched = True
                primary.avanzamento.append(
                    AvanzamentoPratica(
                        data=datetime.now().isoformat(),
                        descrizione="Riconciliazione automatica doppione cliente/RG",
                        stato_precedente=primary.stato.value,
                        stato_nuovo=primary.stato.value,
                        note=f"Assorbito fascicolo {duplicate.numero or duplicate.id} ({duplicate.id}).",
                        avvocato="IUSENTRA",
                    )
                )
                self._segna_analisi_fascicolo_da_rieseguire(
                    primary,
                    reason="riconciliazione_doppione_cliente_rg",
                )
                group_touched = True
                del self._fascicoli[duplicate.id]
                removed_ids.append(duplicate.id)
                report["removedDuplicates"] += 1
                touched = True
            if group_touched:
                primary.modificato_il = datetime.now().isoformat()
                touched_fascicoli[primary.id] = primary
            report["groups"].append(entry)
            report["merged"] += 1
        if touched:
            if self._studio_db is not None:
                self._salva_fascicoli_parziale(touched_fascicoli.values(), rigenera_mirror=False)
                self._rimuovi_fascicoli_parziale(removed_ids, rigenera_mirror=False)
                self._rigenera_mirror_fascicoli_json()
            else:
                self._salva()
        return report

    # ---------------------------------------------------------------- CRUD fascicolo

    def _aggiorna_profilo_deposito_fascicolo(
        self,
        f: Fascicolo,
        *,
        verifica_certificato: bool,
        richiedi_ufficio: bool,
    ) -> None:
        f.profilo_deposito = costruisci_profilo_deposito(
            id_pratica=f.id_pratica,
            area_pratica=f.area_pratica,
            tipo_procedimento=f.tipo_procedimento,
            tipo=f.tipo.value if isinstance(f.tipo, TipoFascicolo) else str(f.tipo or ""),
            source=f.source,
            canale_operativo=f.canale_operativo,
            registro_operativo=f.registro_operativo,
            procedura_operativa_codice=f.procedura_operativa_codice,
            codice_oggetto_pst=f.codice_oggetto_pst,
            fonte_codice_oggetto=f.fonte_codice_oggetto,
            file_fonte_codice_oggetto=f.file_fonte_codice_oggetto,
            ufficio=f.tribunale,
            verifica_certificato=verifica_certificato,
            richiedi_ufficio=richiedi_ufficio,
            profilo_origine=f.profilo_deposito,
        )

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
            **{k: v for k, v in kwargs.items() if k in Fascicolo.__dataclass_fields__},
        )
        self._aggiorna_profilo_deposito_fascicolo(
            f,
            verifica_certificato=bool(f.tribunale),
            richiedi_ufficio=bool(f.tribunale or f.fascicolo_veloce),
        )
        existing = self._trova_fascicolo_duplicato(f)
        if existing is not None:
            changed = self._assorbi_campi_base(existing, f)
            existing.avanzamento.append(
                AvanzamentoPratica(
                    data=datetime.now().isoformat(),
                    descrizione="Creazione doppione bloccata: aggiornata la pratica esistente",
                    stato_precedente=existing.stato.value,
                    stato_nuovo=existing.stato.value,
                    note=f"Tentativo di nuova pratica con stesso cliente/RG ({existing.rg_completo}).",
                    avvocato="IUSENTRA",
                )
            )
            if changed:
                existing.modificato_il = datetime.now().isoformat()
            self._salva()
            return existing
        self._fascicoli[f.id] = f
        self._salva()
        return f

    def aggiorna(self, id_fasc: str, **campi) -> Fascicolo:
        f = self._get_o_errore(id_fasc)
        tocchi_profilo = False
        for k, v in campi.items():
            if hasattr(f, k):
                setattr(f, k, v)
                tocchi_profilo = tocchi_profilo or (k in _PROFILO_DEPOSITO_FASCICOLO_FIELDS)
        if tocchi_profilo and "profilo_deposito" not in campi:
            self._aggiorna_profilo_deposito_fascicolo(
                f,
                verifica_certificato=bool(f.tribunale),
                richiedi_ufficio=bool(f.tribunale or f.fascicolo_veloce),
            )
        f.modificato_il = datetime.now().isoformat()
        duplicate_key = self._chiave_identita_pratica(f)
        if duplicate_key and self._trova_fascicolo_duplicato(f) is not None:
            report = self.riconcilia_doppioni_cliente_rg()
            primary_id = next(
                (
                    str(group.get("primaryId") or "")
                    for group in report.get("groups", [])
                    if group.get("key") == duplicate_key
                ),
                "",
            )
            if primary_id and primary_id in self._fascicoli:
                return self._fascicoli[primary_id]
        self._salva()
        return f

    def elimina(self, id_fasc: str) -> None:
        self._get_o_errore(id_fasc)
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
        tags: Optional[List[str]] = None,
        data_documento: str = "",
        firmato: bool = False,
        caricato_da: str = "",
        id_deposito_pct: str = "",
        fonte_documento: str = "",
        nome_originale: str = "",
        nome_portale: str = "",
        classificazione_portale: str = "",
        tipo_atto_portale: str = "",
        servizio_portale: str = "",
        mittente_portale: str = "",
        data_deposito_portale: str = "",
        id_documento_portale: str = "",
        id_cat_portale: str = "",
        id_repeatto_portale: str = "",
        msg_id_portale: str = "",
        nome_archivio: str = "",
        hash_contenuto_sha256: str = "",
    ) -> Documento:
        """
        Aggiunge un documento al fascicolo salvandolo su disco.

        Returns:
            Documento creato
        """
        f = self._get_o_errore(id_fasc)
        fasc_dir = self.documents_dir / id_fasc
        fasc_dir.mkdir(parents=True, exist_ok=True)
        sha256 = hashlib.sha256(contenuto).hexdigest()
        raw_sha256 = str(hash_contenuto_sha256 or "").strip().lower()
        incoming_probe = Documento(
            id="",
            nome=nome_file,
            tipo=tipo,
            percorso="",
            dimensione_bytes=len(contenuto),
            hash_sha256=sha256,
            hash_contenuto_sha256=raw_sha256 or sha256,
        )
        incoming_semantic_key = _documento_semantic_identity_key(incoming_probe)
        incoming_name_key = _documento_identity_name_key(incoming_probe)
        existing_doc = next(
            (
                doc
                for doc in f.documenti
                if (
                    incoming_name_key
                    and incoming_name_key == _documento_identity_name_key(doc)
                    and str(getattr(doc, "hash_sha256", "") or "").strip().casefold() == sha256.casefold()
                )
                or (
                    incoming_name_key
                    and incoming_name_key == _documento_identity_name_key(doc)
                    and raw_sha256
                    and str(getattr(doc, "hash_contenuto_sha256", "") or "").strip().casefold()
                    == raw_sha256.casefold()
                )
                or (
                    incoming_semantic_key
                    and incoming_semantic_key == _documento_semantic_identity_key(doc)
                )
            ),
            None,
        )
        if existing_doc is not None:
            semantic_match = bool(incoming_semantic_key) and incoming_semantic_key == _documento_semantic_identity_key(
                existing_doc
            )
            conserva_file = (
                semantic_match
                and str(getattr(existing_doc, "hash_sha256", "") or "").strip().casefold() != sha256.casefold()
            )
            percorso_incoming = existing_doc.percorso
            if conserva_file:
                nome_safe = Path(nome_archivio or nome_file).name
                dest = fasc_dir / nome_safe
                if dest.exists():
                    stem = Path(nome_safe).stem
                    suffix = Path(nome_safe).suffix
                    nome_safe = f"{stem}_{uuid.uuid4().hex[:4]}{suffix}"
                    dest = fasc_dir / nome_safe
                dest.write_bytes(contenuto)
                percorso_incoming = str(dest.relative_to(self.documents_dir))
            incoming_doc = Documento(
                id=existing_doc.id,
                nome=nome_file,
                tipo=tipo,
                percorso=percorso_incoming,
                dimensione_bytes=len(contenuto),
                hash_sha256=sha256,
                hash_contenuto_sha256=raw_sha256 or sha256,
                firmato_digitalmente=firmato,
                note=note,
                tags=list(tags or []),
                data_documento=data_documento or date.today().isoformat(),
                caricato_da=caricato_da,
                id_deposito_pct=id_deposito_pct,
                fonte_documento=str(fonte_documento or "").strip(),
                nome_originale=str(nome_originale or nome_file or "").strip(),
                nome_portale=str(nome_portale or "").strip(),
                classificazione_portale=str(classificazione_portale or "").strip(),
                tipo_atto_portale=str(tipo_atto_portale or "").strip(),
                servizio_portale=str(servizio_portale or "").strip(),
                mittente_portale=str(mittente_portale or "").strip(),
                data_deposito_portale=str(data_deposito_portale or "").strip(),
                id_documento_portale=str(id_documento_portale or "").strip(),
                id_cat_portale=str(id_cat_portale or "").strip(),
                id_repeatto_portale=str(id_repeatto_portale or "").strip(),
                msg_id_portale=str(msg_id_portale or "").strip(),
            )
            if self._assorbi_metadati_documento(
                existing_doc,
                incoming_doc,
                conserva_file_come_versione=conserva_file,
            ):
                f.modificato_il = datetime.now().isoformat()
                self._salva()
            return existing_doc

        # evita collisioni di nome
        nome_safe = Path(nome_archivio or nome_file).name
        dest = fasc_dir / nome_safe
        if dest.exists():
            stem = Path(nome_safe).stem
            suffix = Path(nome_safe).suffix
            nome_safe = f"{stem}_{uuid.uuid4().hex[:4]}{suffix}"
            dest = fasc_dir / nome_safe

        dest.write_bytes(contenuto)
        signature_metadata: dict[str, Any] = {}
        if firmato:
            try:
                from pct.document_signature_state import (
                    document_bytes_have_real_digital_signature,
                    is_signed_container_name,
                )

                if document_bytes_have_real_digital_signature(contenuto, nome_file):
                    is_container = is_signed_container_name(nome_file)
                    signature_metadata = {
                        "signature_format": "cades" if is_container else "pades",
                        "signature_verified": True,
                        "is_signed_container": is_container,
                        "source": "upload",
                        "file_name": Path(str(nome_file or "")).name,
                    }
            except Exception:
                signature_metadata = {}

        doc = Documento(
            id=uuid.uuid4().hex[:8].upper(),
            nome=nome_file,
            tipo=tipo,
            percorso=str(dest.relative_to(self.documents_dir)),
            dimensione_bytes=len(contenuto),
            hash_sha256=sha256,
            hash_contenuto_sha256=raw_sha256 or sha256,
            firmato_digitalmente=firmato,
            signature_metadata=signature_metadata,
            note=note,
            tags=list(tags or []),
            data_documento=data_documento or date.today().isoformat(),
            caricato_da=caricato_da,
            id_deposito_pct=id_deposito_pct,
            fonte_documento=str(fonte_documento or "").strip(),
            nome_originale=str(nome_originale or nome_file or "").strip(),
            nome_portale=str(nome_portale or "").strip(),
            classificazione_portale=str(classificazione_portale or "").strip(),
            tipo_atto_portale=str(tipo_atto_portale or "").strip(),
            servizio_portale=str(servizio_portale or "").strip(),
            mittente_portale=str(mittente_portale or "").strip(),
            data_deposito_portale=str(data_deposito_portale or "").strip(),
            id_documento_portale=str(id_documento_portale or "").strip(),
            id_cat_portale=str(id_cat_portale or "").strip(),
            id_repeatto_portale=str(id_repeatto_portale or "").strip(),
            msg_id_portale=str(msg_id_portale or "").strip(),
        )
        original_docs = list(f.documenti)
        original_modificato = f.modificato_il
        original_pagamenti = dict(f.pagamenti or {})
        f.documenti.append(doc)
        self._segna_analisi_fascicolo_da_rieseguire(
            f,
            reason="nuovo_documento_fascicolo",
            document_id=doc.id,
        )
        f.modificato_il = datetime.now().isoformat()
        try:
            self._salva()
        except Exception:
            f.documenti = original_docs
            f.modificato_il = original_modificato
            f.pagamenti = original_pagamenti
            try:
                if dest.exists():
                    dest.unlink()
            except OSError:
                pass
            raise
        return doc

    def sostituisci_documento(
        self,
        id_fasc: str,
        id_doc: str,
        nome_file: str,
        contenuto: bytes,
        caricato_da: str = "",
        note: str = "",
        preserve_version_snapshot: bool = True,
        reuse_existing_path: bool = False,
    ) -> "Documento":
        """
        Sostituisce il file di un documento esistente mantenendo lo storico
        della versione precedente in doc.versioni.
        """
        f = self._get_o_errore(id_fasc)
        doc = next((d for d in f.documenti if d.id == id_doc), None)
        if not doc:
            raise KeyError(f"Documento '{id_doc}' non trovato nel fascicolo.")

        if preserve_version_snapshot:
            doc.versioni.append(DocumentoVersione(
                hash_sha256=doc.hash_sha256,
                percorso="" if reuse_existing_path else doc.percorso,
                dimensione_bytes=doc.dimensione_bytes,
                sostituito_il=datetime.now().isoformat(),
                sostituito_da=caricato_da,
            ))

        # Salva nuovo file (path basato sul nuovo nome per evitare collisioni)
        fasc_dir = self.documents_dir / id_fasc
        fasc_dir.mkdir(parents=True, exist_ok=True)
        if reuse_existing_path and doc.percorso:
            dest = self.documents_dir / doc.percorso
        else:
            nome_safe = Path(nome_file).name
            dest = fasc_dir / nome_safe
            if dest.exists() and str(dest.relative_to(self.documents_dir)) != doc.percorso:
                stem, suffix = Path(nome_safe).stem, Path(nome_safe).suffix
                nome_safe = f"{stem}_{uuid.uuid4().hex[:4]}{suffix}"
                dest = fasc_dir / nome_safe
        dest.write_bytes(contenuto)

        if not (reuse_existing_path and doc.percorso):
            doc.percorso = str(dest.relative_to(self.documents_dir))
        doc.nome = nome_file
        doc.dimensione_bytes = len(contenuto)
        doc.hash_sha256 = hashlib.sha256(contenuto).hexdigest()
        doc.caricato_da = caricato_da or doc.caricato_da
        if note:
            doc.note = note
        doc.data_caricamento = datetime.now().isoformat()

        self._segna_analisi_fascicolo_da_rieseguire(
            f,
            reason="documento_sostituito",
            document_id=doc.id,
        )
        f.modificato_il = datetime.now().isoformat()
        self._salva()
        return doc

    @staticmethod
    def _trova_documento_portale_correlato(
        doc: Documento,
        dep: "EsitoDepositoPCT",
    ) -> dict | None:
        documenti_portale = list(getattr(dep, "documenti_portale", []) or [])
        if not documenti_portale:
            return None

        doc_source_refs = _documento_locale_ref_keys_origine(doc)
        if doc_source_refs:
            matches = [
                item
                for item in documenti_portale
                if _documento_portale_ref_keys(item) & doc_source_refs
            ]
            if len(matches) == 1:
                return matches[0]

        doc_portale_id = str(getattr(doc, "id_documento_portale", "") or "").strip()
        if doc_portale_id:
            match = next(
                (
                    item
                    for item in documenti_portale
                    if str((item or {}).get("id_documento") or "").strip() == doc_portale_id
                ),
                None,
            )
            if match:
                return match

        id_cat = str(getattr(doc, "id_cat_portale", "") or "").strip()
        if id_cat:
            match = next(
                (
                    item
                    for item in documenti_portale
                    if str((item or {}).get("id_cat") or "").strip() == id_cat
                ),
                None,
            )
            if match:
                return match

        doc_original_name_keys = _documento_locale_nome_keys_origine(doc)
        original_matches = [
            item
            for item in documenti_portale
            if _documento_portale_nome_keys((item or {}).get("nome") or "") & doc_original_name_keys
        ]
        if len(original_matches) == 1:
            return original_matches[0]

        keys = {
            _normalizza_nome_documento_match(getattr(doc, "nome", "")),
            _normalizza_nome_documento_match(getattr(doc, "nome_originale", "")),
            _normalizza_nome_documento_match(getattr(doc, "nome_portale", "")),
        }
        keys.discard("")
        exact = [
            item
            for item in documenti_portale
            if _normalizza_nome_documento_match((item or {}).get("nome") or "") in keys
        ]
        if len(exact) == 1:
            return exact[0]

        if len(documenti_portale) == 1 and (
            getattr(doc, "id_deposito_pct", "") == getattr(dep, "id", "")
            or getattr(doc, "id", "") in (getattr(dep, "documenti_ids", []) or [])
        ):
            return documenti_portale[0]
        return None

    @staticmethod
    def _arricchisci_documento_da_deposito_portale(
        doc: Documento,
        dep: "EsitoDepositoPCT",
        item: dict | None,
    ) -> bool:
        def _label_servizio_portale(servizio: str) -> str:
            mapping = {
                SERVIZIO_PST_DOCUMENTI_FASCICOLO: "Documenti fascicolo",
                "DocumentiFascicolo": "Documenti fascicolo",
                "AttivitaProcessuali": "Attivita processuali",
                "UdienzeScadenze": "Udienze e scadenze",
                "ComunicazioniCancelleria": "Comunicazioni di cancelleria",
                "Istanze": "Istanze",
            }
            return mapping.get(str(servizio or "").strip(), str(servizio or "").strip())

        def _merge_tags(existing: list[str], incoming: list[str]) -> list[str]:
            normalized: list[str] = []
            seen: set[str] = set()
            for raw in list(existing or []) + list(incoming or []):
                tag = str(raw or "").strip()
                if not tag:
                    continue
                key = tag.casefold()
                if key in seen:
                    continue
                seen.add(key)
                normalized.append(tag)
            return normalized

        row = _documento_portale_payload(dep, item)
        changed = False

        if not getattr(doc, "fonte_documento", ""):
            doc.fonte_documento = row["fonte_documento"]
            changed = True
        if not doc.nome_originale:
            doc.nome_originale = doc.nome
            changed = True

        for field_name, value in row.items():
            if field_name == "fonte_documento":
                continue
            if not value:
                continue
            if getattr(doc, field_name, "") != value:
                setattr(doc, field_name, value)
                changed = True
        official_date = str(row.get("data_deposito_portale") or "").strip()
        if official_date and getattr(doc, "data_documento", "") != official_date:
            doc.data_documento = official_date
            changed = True
        nome_ufficiale = row.get("nome_portale", "")
        if (
            nome_ufficiale
            and doc.fonte_documento == "PORTALE_TELEMATICO"
            and getattr(doc, "nome", "") != nome_ufficiale
        ):
            if not doc.nome_originale:
                doc.nome_originale = doc.nome
            doc.nome = nome_ufficiale
            changed = True
        tags_portale = _merge_tags(
            list(getattr(doc, "tags", []) or []),
            [
                _label_servizio_portale(getattr(dep, "servizio_portale", "")),
                str(row.get("tipo_atto_portale") or "").strip(),
                str(row.get("classificazione_portale") or "").strip(),
                "Cancelleria" if "cancelleria" in str(row.get("mittente_portale") or "").casefold() else "",
            ],
        )
        if tags_portale != list(getattr(doc, "tags", []) or []):
            doc.tags = tags_portale
            changed = True
        note_normalized = _normalizza_nota_import_portale(getattr(doc, "note", ""))
        if note_normalized and note_normalized != getattr(doc, "note", ""):
            doc.note = note_normalized
            changed = True
        return changed

    @classmethod
    def _trova_deposito_portale_correlato(
        cls,
        doc: Documento,
        fascicolo: Fascicolo,
    ) -> tuple["EsitoDepositoPCT", dict] | None:
        doc_source_refs = _documento_locale_ref_keys_origine(doc)
        doc_source_name_keys = _documento_locale_nome_keys_origine(doc)
        doc_ref_keys = _documento_locale_ref_keys(doc)
        doc_name_keys = _documento_locale_nome_keys(doc)
        candidates: list[tuple[tuple[int, int, int, int, int, int], EsitoDepositoPCT, dict]] = []

        for dep in fascicolo.depositi_pct:
            match = cls._trova_documento_portale_correlato(doc, dep)
            if not match:
                continue
            item_ref_keys = _documento_portale_ref_keys(match)
            item_name_keys = _documento_portale_nome_keys(str((match or {}).get("nome") or ""))
            score = (
                len(doc_source_refs & item_ref_keys),
                len(doc_source_name_keys & item_name_keys),
                len(doc_ref_keys & item_ref_keys),
                len(doc_name_keys & item_name_keys),
                1 if getattr(doc, "id_deposito_pct", "") == getattr(dep, "id", "") else 0,
                1 if getattr(doc, "id", "") in (getattr(dep, "documenti_ids", []) or []) else 0,
            )
            candidates.append((score, dep, match))

        if not candidates:
            return None
        candidates.sort(key=lambda item: item[0], reverse=True)
        best_score = candidates[0][0]
        best = [(dep, match) for score, dep, match in candidates if score == best_score]
        if len(best) != 1:
            return None
        return best[0]

    @staticmethod
    def _trova_deposito_portale_da_overlap(
        fascicolo: Fascicolo,
        *,
        id_deposito_esterno: str,
        documenti_portale: list[dict],
        tipo_atto: str = "",
    ) -> Optional["EsitoDepositoPCT"]:
        incoming_name_keys = {
            key
            for item in documenti_portale
            for key in _documento_portale_nome_keys(str((item or {}).get("nome") or ""))
        }
        incoming_ref_keys = {
            ref
            for item in documenti_portale
            for ref in _documento_portale_ref_keys(item)
        }
        if not incoming_name_keys and not incoming_ref_keys:
            return None

        candidates: list[tuple[tuple[int, int, int, int, int, int], EsitoDepositoPCT]] = []
        normalized_tipo = str(tipo_atto or "").strip().casefold()
        for dep in fascicolo.depositi_pct:
            dep_esterno = str(getattr(dep, "id_deposito_esterno", "") or "").strip()
            if dep_esterno == id_deposito_esterno and dep_esterno:
                return dep
            if dep_esterno and dep_esterno != id_deposito_esterno:
                continue

            docs_locali = [
                doc
                for doc in fascicolo.documenti
                if doc.id_deposito_pct == dep.id or doc.id in (dep.documenti_ids or [])
            ]
            if not docs_locali:
                continue

            local_name_keys = {
                key
                for doc in docs_locali
                for key in _documento_locale_nome_keys(doc)
            }
            local_ref_keys = {
                ref
                for doc in docs_locali
                for ref in _documento_locale_ref_keys(doc)
            }
            overlap_refs = len(local_ref_keys & incoming_ref_keys)
            overlap_names = len(local_name_keys & incoming_name_keys)
            if overlap_refs == 0 and overlap_names == 0:
                continue

            score = (
                overlap_refs,
                overlap_names,
                1 if len(docs_locali) == len(documenti_portale) and documenti_portale else 0,
                1 if normalized_tipo and str(getattr(dep, "tipo_atto", "") or "").strip().casefold() == normalized_tipo else 0,
                1 if not getattr(dep, "documenti_portale", None) else 0,
                len(docs_locali),
            )
            candidates.append((score, dep))

        if not candidates:
            return None
        candidates.sort(key=lambda item: item[0], reverse=True)
        best_score = candidates[0][0]
        best = [dep for score, dep in candidates if score == best_score]
        if len(best) != 1:
            return None
        return best[0]

    def riconcilia_documenti_portale(self, id_fasc: str) -> dict[str, int]:
        f = self._get_o_errore(id_fasc)
        aggiornati = 0
        depositi_toccati: set[str] = set()
        for doc in f.documenti:
            resolved = self._trova_deposito_portale_correlato(doc, f)
            if not resolved:
                continue
            dep, match = resolved
            doc_changed = False
            if getattr(doc, "id_deposito_pct", "") != dep.id:
                for other_dep in f.depositi_pct:
                    if doc.id in (other_dep.documenti_ids or []) and other_dep.id != dep.id:
                        other_dep.documenti_ids = [doc_id for doc_id in (other_dep.documenti_ids or []) if doc_id != doc.id]
                        depositi_toccati.add(other_dep.id)
                doc.id_deposito_pct = dep.id
                doc_changed = True
            if doc.id not in (dep.documenti_ids or []):
                dep.documenti_ids.append(doc.id)
                doc_changed = True
            if self._arricchisci_documento_da_deposito_portale(doc, dep, match):
                doc_changed = True
            if doc_changed:
                aggiornati += 1
                depositi_toccati.add(dep.id)

        if aggiornati:
            f.modificato_il = datetime.now().isoformat()
            self._salva()
        return {
            "documenti_allineati": aggiornati,
            "depositi_toccati": len(depositi_toccati),
        }

    def rimuovi_documento(self, id_fasc: str, id_doc: str) -> None:
        f = self._get_o_errore(id_fasc)
        doc = next((d for d in f.documenti if d.id == id_doc), None)
        if not doc:
            raise KeyError(f"Documento '{id_doc}' non trovato nel fascicolo.")
        percorso = self.documents_dir / doc.percorso
        original_docs = list(f.documenti)
        original_modificato = f.modificato_il
        original_pagamenti = dict(f.pagamenti or {})
        f.documenti = [d for d in f.documenti if d.id != id_doc]
        self._segna_analisi_fascicolo_da_rieseguire(
            f,
            reason="documento_rimosso",
            document_id=id_doc,
        )
        f.modificato_il = datetime.now().isoformat()
        try:
            self._salva()
        except Exception:
            f.documenti = original_docs
            f.modificato_il = original_modificato
            f.pagamenti = original_pagamenti
            raise
        try:
            if percorso.exists():
                percorso.unlink()
        except OSError:
            pass

    def aggiorna_documento_metadati(
        self,
        id_fasc: str,
        id_doc: str,
        *,
        note: str | None = None,
        data_documento: str | None = None,
        tags: Optional[List[str]] = None,
    ) -> Documento:
        f = self._get_o_errore(id_fasc)
        doc = next((d for d in f.documenti if d.id == id_doc), None)
        if not doc:
            raise KeyError(f"Documento '{id_doc}' non trovato nel fascicolo.")
        if note is not None:
            doc.note = str(note or "").strip()
        if data_documento is not None:
            doc.data_documento = str(data_documento or "").strip()
        if tags is not None:
            normalized: list[str] = []
            seen: set[str] = set()
            for tag in tags:
                value = str(tag or "").strip()
                if not value:
                    continue
                key = value.casefold()
                if key in seen:
                    continue
                seen.add(key)
                normalized.append(value)
            doc.tags = normalized
        f.modificato_il = datetime.now().isoformat()
        self._salva()
        return doc

    def aggiorna_documento_deposito(
        self,
        id_fasc: str,
        id_doc: str,
        *,
        tipo: TipoDocumento | str | None = None,
        firmato: bool | None = None,
        classificazione_portale: str | None = None,
    ) -> Documento:
        """Aggiorna i metadati operativi usati dalla preparazione deposito."""

        f = self._get_o_errore(id_fasc)
        doc = next((d for d in f.documenti if d.id == id_doc), None)
        if not doc:
            raise KeyError(f"Documento '{id_doc}' non trovato nel fascicolo.")
        if tipo is not None:
            doc.tipo = tipo if isinstance(tipo, TipoDocumento) else TipoDocumento(str(tipo))
        if firmato is not None:
            doc.firmato_digitalmente = bool(firmato)
        if classificazione_portale is not None:
            doc.classificazione_portale = str(classificazione_portale or "").strip()
        f.modificato_il = datetime.now().isoformat()
        self._salva()
        return doc

    def aggiorna_documenti_deposito(
        self,
        id_fasc: str,
        updates: Iterable[dict[str, Any]],
    ) -> list[Documento]:
        """Aggiorna più metadati deposito e salva il fascicolo una sola volta."""

        f = self._get_o_errore(id_fasc)
        documents_by_id = {d.id: d for d in f.documenti}
        updated: list[Documento] = []
        touched = False
        for raw_update in updates:
            id_doc = str(raw_update.get("id_doc") or raw_update.get("document_id") or "").strip()
            if not id_doc:
                continue
            doc = documents_by_id.get(id_doc)
            if not doc:
                raise KeyError(f"Documento '{id_doc}' non trovato nel fascicolo.")
            if "tipo" in raw_update and raw_update.get("tipo") is not None:
                tipo = raw_update.get("tipo")
                next_tipo = tipo if isinstance(tipo, TipoDocumento) else TipoDocumento(str(tipo))
                if doc.tipo != next_tipo:
                    doc.tipo = next_tipo
                    touched = True
            if "firmato" in raw_update and raw_update.get("firmato") is not None:
                next_firmato = bool(raw_update.get("firmato"))
                if doc.firmato_digitalmente != next_firmato:
                    doc.firmato_digitalmente = next_firmato
                    touched = True
            if "classificazione_portale" in raw_update and raw_update.get("classificazione_portale") is not None:
                next_classificazione = str(raw_update.get("classificazione_portale") or "").strip()
                if doc.classificazione_portale != next_classificazione:
                    doc.classificazione_portale = next_classificazione
                    touched = True
            updated.append(doc)
        if touched:
            f.modificato_il = datetime.now().isoformat()
            self._salva()
        return updated

    def rinomina_documento(self, id_fasc: str, id_doc: str, nome_file: str) -> Documento:
        f = self._get_o_errore(id_fasc)
        doc = next((d for d in f.documenti if d.id == id_doc), None)
        if not doc:
            raise KeyError(f"Documento '{id_doc}' non trovato nel fascicolo.")

        nuovo_nome = _normalizza_nome_documento(nome_file, doc.nome)
        if nuovo_nome == doc.nome:
            return doc

        percorso_corrente = self.documents_dir / doc.percorso
        cartella = percorso_corrente.parent if percorso_corrente.parent.exists() else self.documents_dir / id_fasc
        cartella.mkdir(parents=True, exist_ok=True)
        destinazione = cartella / nuovo_nome
        if destinazione.exists() and destinazione.resolve() != percorso_corrente.resolve():
            suffix = _estensione_documento(nuovo_nome) or Path(nuovo_nome).suffix
            stem = Path(nuovo_nome[: -len(suffix)]).name if suffix else Path(nuovo_nome).stem
            while destinazione.exists():
                candidato = f"{stem}_{uuid.uuid4().hex[:4]}{suffix}"
                destinazione = cartella / candidato
                nuovo_nome = candidato

        old_nome = doc.nome
        old_percorso = doc.percorso
        old_modificato = f.modificato_il
        moved = False
        temp_case_path: Path | None = None
        try:
            if percorso_corrente.exists() and destinazione.resolve() != percorso_corrente.resolve():
                percorso_corrente.rename(destinazione)
                moved = True
            elif percorso_corrente.exists() and destinazione.name != percorso_corrente.name:
                temp_case_path = cartella / f".iusentra-rename-{uuid.uuid4().hex[:8]}{Path(percorso_corrente.name).suffix}"
                percorso_corrente.rename(temp_case_path)
                temp_case_path.rename(destinazione)
                moved = True
            doc.nome = nuovo_nome
            doc.percorso = str(destinazione.relative_to(self.documents_dir)) if destinazione.exists() else old_percorso
            f.modificato_il = datetime.now().isoformat()
            self._salva()
        except Exception:
            doc.nome = old_nome
            doc.percorso = old_percorso
            f.modificato_il = old_modificato
            if temp_case_path and temp_case_path.exists() and not percorso_corrente.exists():
                try:
                    temp_case_path.rename(percorso_corrente)
                except OSError:
                    pass
            if moved and destinazione.exists() and not percorso_corrente.exists():
                try:
                    destinazione.rename(percorso_corrente)
                except OSError:
                    pass
            raise
        return doc

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

        documenti_ids = _deduplica_documenti_ids(documenti_ids)
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
        dep.documenti_ids = _deduplica_documenti_ids(dep.documenti_ids)
        gia_collegati = set(dep.documenti_ids)
        nuovi_ids: List[str] = []
        for doc_id in _deduplica_documenti_ids(documenti_ids):
            if doc_id not in doc_ids_presenti or doc_id in gia_collegati:
                continue
            nuovi_ids.append(doc_id)
            gia_collegati.add(doc_id)
        if not nuovi_ids:
            return dep

        dep.documenti_ids.extend(nuovi_ids)
        for doc in f.documenti:
            if doc.id in nuovi_ids:
                doc.id_deposito_pct = dep.id
                match = self._trova_documento_portale_correlato(doc, dep)
                if match:
                    self._arricchisci_documento_da_deposito_portale(doc, dep, match)

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
                "id_repeatto": str(row.get("id_repeatto") or "").strip(),
                "id_reperto": str(row.get("id_reperto") or "").strip(),
                "msg_id": str(row.get("msg_id") or "").strip(),
                "nome": str(row.get("nome") or "").strip(),
                "tipo": str(row.get("tipo") or "").strip(),
                "data_deposito": str(row.get("data_deposito") or "").strip(),
                "mittente": str(row.get("mittente") or "").strip(),
                "dimensione_bytes": int(row.get("dimensione_bytes") or 0),
                "disponibile": _bool_portale(row.get("disponibile", True)),
                "id_deposito": str(row.get("id_deposito") or chiave_portale).strip(),
                "tipo_atto": str(row.get("tipo_atto") or tipo_atto or "").strip(),
                "id_documento_padre": str(row.get("id_documento_padre") or row.get("parent_id_documento") or "").strip(),
                "parent_nome": str(row.get("parent_nome") or "").strip(),
                "is_allegato": _bool_portale(row.get("is_allegato")),
            }

        def _merge_documenti_portale(*liste: List[dict]) -> List[dict]:
            merged: List[dict] = []
            visti: set[tuple[str, str, str]] = set()
            by_key: dict[tuple[str, str, str], dict] = {}

            def _identity_keys(row: dict) -> List[tuple[str, str, str]]:
                keys: List[tuple[str, str, str]] = []
                for field_name in ("id_documento", "id_cat", "id_repeatto", "id_reperto", "msg_id"):
                    value = str(row.get(field_name) or "").strip()
                    if value:
                        keys.append((field_name, value, ""))
                if not keys:
                    keys.append(
                        (
                            "nome",
                            (row.get("nome") or "").upper(),
                            (row.get("tipo") or row.get("tipo_atto") or "").upper(),
                        )
                    )
                return keys

            for lista in liste:
                for item in lista or []:
                    row = _normalizza_doc_portale(item)
                    keys = _identity_keys(row)
                    existing = next((by_key[key] for key in keys if key in visti), None)
                    if existing is not None:
                        for field_name, value in row.items():
                            if field_name == "dimensione_bytes":
                                if int(value or 0) > 0 and int(existing.get(field_name) or 0) <= 0:
                                    existing[field_name] = value
                            elif field_name == "disponibile":
                                existing[field_name] = bool(existing.get(field_name, True) or value)
                            elif field_name == "is_allegato":
                                existing[field_name] = bool(existing.get(field_name) or value)
                            elif str(value or "").strip() and not str(existing.get(field_name) or "").strip():
                                existing[field_name] = value
                        for key in keys:
                            visti.add(key)
                            by_key.setdefault(key, existing)
                        continue
                    for key in keys:
                        visti.add(key)
                        by_key[key] = row
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
            # Comunicazioni di cancelleria — servizio portale o keywords
            _serv = (servizio_portale or "").upper()
            if "COMUNICAZIONE" in _serv or "NOTIFICHE" in _serv:
                return TipoAttivita.COMUNICAZIONE_CANCELLERIA
            if any(t in testo or t in tipi_doc for t in ("COMUNICAZIONE", "CANCELLERIA", "NOTIFICA")):
                return TipoAttivita.COMUNICAZIONE_CANCELLERIA
            # Provvedimenti
            if any(token in testo or token in tipi_doc for token in ("PROVVED", "SENTENZA", "ORDINANZA", "DECRETO")):
                return TipoAttivita.PROVVEDIMENTO
            # Udienze
            if "UDIENZA" in testo or "VERBALE" in tipi_doc:
                return TipoAttivita.UDIENZA
            # Scadenze dal servizio portale
            if "SCADENZ" in _serv:
                return TipoAttivita.TERMINE_SCADENZA
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
        if dep is None and documenti_norm:
            dep = self._trova_deposito_portale_da_overlap(
                f,
                id_deposito_esterno=chiave_portale,
                documenti_portale=documenti_norm,
                tipo_atto=tipo_atto,
            )

        if dep:
            dep.documenti_ids = _deduplica_documenti_ids(dep.documenti_ids)
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
            for doc in f.documenti:
                if doc.id_deposito_pct == dep.id or doc.id in (dep.documenti_ids or []):
                    match = self._trova_documento_portale_correlato(doc, dep)
                    if match:
                        self._arricchisci_documento_da_deposito_portale(doc, dep, match)
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

        if str(servizio_portale or "").strip() != SERVIZIO_PST_DOCUMENTI_FASCICOLO:
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

    def segna_firmato(
        self,
        id_fasc: str,
        id_doc: str,
        *,
        signature_metadata: dict[str, Any] | None = None,
    ) -> "Documento":
        """Marca un documento come firmato digitalmente."""
        f = self._get_o_errore(id_fasc)
        doc = next((d for d in f.documenti if d.id == id_doc), None)
        if not doc:
            raise KeyError(f"Documento '{id_doc}' non trovato nel fascicolo.")
        doc.firmato_digitalmente = True
        if signature_metadata is not None:
            doc.signature_metadata = dict(signature_metadata)
        f.modificato_il = datetime.now().isoformat()
        self._salva()
        return doc

    def percorso_documento(self, id_fasc: str, id_doc: str) -> Path:
        f = self._get_o_errore(id_fasc)
        doc = next((d for d in f.documenti if d.id == id_doc), None)
        if not doc:
            raise KeyError(f"Documento '{id_doc}' non trovato.")
        return self.documents_dir / Path(str(doc.percorso or "").replace("\\", "/"))

    def percorso_documento_lettura(self, id_fasc: str, id_doc: str) -> Path:
        """Restituisce il file del documento, con recupero best-effort per duplicati storici.

        Alcune versioni cancellavano il file fisico prima di salvare la rimozione nel
        repository. Se il salvataggio falliva per lock SQLite, nel fascicolo restava
        una riga valida ma il file puntava al nome base ormai assente. In lettura
        possiamo usare una copia duplicata con stesso nome base, estensione e dimensione;
        la cancellazione continua invece a usare solo il percorso diretto.
        """
        f = self._get_o_errore(id_fasc)
        doc = next((d for d in f.documenti if d.id == id_doc), None)
        if not doc:
            raise KeyError(f"Documento '{id_doc}' non trovato.")
        rel = Path(str(doc.percorso or "").replace("\\", "/"))
        direct = self.documents_dir / rel
        if direct.exists():
            return direct
        if not rel.name:
            return direct
        fasc_dir = self.documents_dir / rel.parent
        if not fasc_dir.exists():
            return direct
        suffix = rel.suffix
        stem = rel.stem
        candidates = [
            path
            for path in fasc_dir.glob(f"{stem}_*{suffix}")
            if path.is_file() and (not doc.dimensione_bytes or path.stat().st_size == doc.dimensione_bytes)
        ]
        if not candidates:
            return direct
        candidates.sort(key=lambda path: path.stat().st_mtime)
        return candidates[0]

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

    def rimuovi_attivita(self, id_fasc: str, id_att: str) -> None:
        """Rimuove un'attivita' processuale mantenendo aggiornato il fascicolo."""
        f = self._get_o_errore(id_fasc)
        att = next((a for a in f.attivita if a.id == id_att), None)
        if not att:
            raise KeyError(f"Attivita' '{id_att}' non trovata.")
        f.attivita = [a for a in f.attivita if a.id != id_att]
        if att.tipo == TipoAttivita.UDIENZA:
            udienze_future = sorted(
                a.data
                for a in f.attivita
                if a.tipo == TipoAttivita.UDIENZA and a.data and a.data >= date.today().isoformat()
            )
            f.data_prossima_udienza = udienze_future[0] if udienze_future else ""
        f.modificato_il = datetime.now().isoformat()
        self._salva()

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
