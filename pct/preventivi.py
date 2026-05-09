"""
pct/preventivi.py — Preventivi e conferimenti di incarico.

Gestisce:
  - Preventivo professionale con voci onorari/spese
  - ConferimentoIncarico (lettera di incarico firmata dal cliente)
  - Cassa Forense 4% e IVA 22% sul preventivo
  - Numerazione progressiva per anno (es. 2025/001)
"""
from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pct.preventivi_repository import (
    GestionePreventiviRepository,
    derive_preventivi_field_map_json_path,
    derive_preventivi_repository_db_path,
    derive_preventivi_repository_json_path,
    derive_preventivi_rules_json_path,
    derive_preventivi_workflow_states_json_path,
)
from pct.legal_platform_catalog import build_operational_fields
from pct.compensi_a_tempo import normalizza_tipo_compenso


# ================================================================ Enumerazioni

class TipoVoce(str, Enum):
    ONORARIO           = "Onorario"
    SPESA_FORFETTARIA  = "Spesa forfettaria"
    SPESA_VIVA         = "Spesa viva"


class StatoPreventivo(str, Enum):
    BOZZA         = "BOZZA"
    IN_CALCOLO    = "IN_CALCOLO"    # wizard in corso
    GENERATO      = "GENERATO"      # documento prodotto, non ancora inviato
    VERIFICATO    = "VERIFICATO"    # verificato dall'avvocato prima dell'invio
    INVIATO       = "INVIATO"       # inviato al cliente
    APERTO        = "APERTO"        # aperto dal cliente sul portale
    ACCETTATO     = "ACCETTATO"     # accettato dal cliente
    RIFIUTATO     = "RIFIUTATO"     # rifiutato dal cliente
    SCADUTO       = "SCADUTO"       # scaduto senza risposta
    REVISIONATO   = "REVISIONATO"   # nuova versione emessa
    CONVERTITO    = "CONVERTITO"    # convertito in incarico attivo

    @classmethod
    def stati_attivi(cls) -> List["StatoPreventivo"]:
        return [cls.BOZZA, cls.IN_CALCOLO, cls.GENERATO, cls.VERIFICATO,
                cls.INVIATO, cls.APERTO]

    @classmethod
    def badge_color(cls, stato: "StatoPreventivo") -> str:
        _map = {
            cls.BOZZA:       "secondary",
            cls.IN_CALCOLO:  "info",
            cls.GENERATO:    "primary",
            cls.VERIFICATO:  "info",
            cls.INVIATO:     "primary",
            cls.APERTO:      "warning",
            cls.ACCETTATO:   "success",
            cls.RIFIUTATO:   "danger",
            cls.SCADUTO:     "warning",
            cls.REVISIONATO: "secondary",
            cls.CONVERTITO:  "success",
        }
        return _map.get(stato, "secondary")


class StatoConferimento(str, Enum):
    ATTIVO   = "ATTIVO"
    DEFINITO = "DEFINITO"
    REVOCATO = "REVOCATO"


def _normalize_workflow_channel(value: str | None) -> str:
    channel = str(value or "").strip().upper()
    return channel if channel in {"STUDIO", "ONLINE"} else "STUDIO"


def _normalizza_classificazioni_tassonomiche(
    rows: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for raw in list(rows or []):
        if not isinstance(raw, dict):
            continue
        item = {
            "uid": str(raw.get("uid") or "").strip(),
            "area_pratica": str(raw.get("area_pratica") or "").strip(),
            "area_tassonomica_code": str(raw.get("area_tassonomica_code") or "").strip(),
            "area_tassonomica": str(raw.get("area_tassonomica") or "").strip(),
            "macro_area_tassonomica_code": str(raw.get("macro_area_tassonomica_code") or "").strip(),
            "macro_area_tassonomica": str(raw.get("macro_area_tassonomica") or "").strip(),
            "sottobranca_tassonomica_code": str(raw.get("sottobranca_tassonomica_code") or "").strip(),
            "sottobranca_tassonomica": str(raw.get("sottobranca_tassonomica") or "").strip(),
            "tassonomia_codice": str(raw.get("tassonomia_codice") or "").strip(),
            "tipologia_pratica_id": str(raw.get("tipologia_pratica_id") or "").strip(),
            "tipologia_pratica_label": str(raw.get("tipologia_pratica_label") or "").strip(),
            "tipo_compenso": str(raw.get("tipo_compenso") or "").strip(),
        }
        if not any(
            item[key]
            for key in (
                "area_tassonomica",
                "area_pratica",
                "macro_area_tassonomica",
                "sottobranca_tassonomica",
                "tipologia_pratica_id",
                "tipologia_pratica_label",
            )
        ):
            continue
        normalized.append(item)
    return normalized


CLAUSOLA_CONTROVERSIE_NESSUNA = "NESSUNA"
CLAUSOLA_CONTROVERSIE_TUTELA_CLIENTE = "TUTELA_CLIENTE_CONSUMATORE"
CLAUSOLA_CONTROVERSIE_MULTISTEP = "MULTISTEP_MEDIAZIONE_ARBITRATO"

_CLAUSOLA_CONTROVERSIE_MODELLI: Dict[str, Dict[str, str]] = {
    CLAUSOLA_CONTROVERSIE_NESSUNA: {
        "label": "Nessuna clausola specifica",
        "source": "",
        "default_text": "",
    },
    CLAUSOLA_CONTROVERSIE_TUTELA_CLIENTE: {
        "label": "Tutela cliente / consumatore",
        "source": (
            "Presidio IUSENTRA per conferimento di incarico: usare con particolare "
            "attenzione se il cliente opera come consumatore e documentare sempre una "
            "trattativa seria, effettiva e individuale sulla clausola."
        ),
        "default_text": (
            "Le parti convengono che, in caso di controversie relative al presente "
            "incarico, prima di adire l'autorita giudiziaria sara valutato un tentativo "
            "di composizione stragiudiziale o di mediazione, ove compatibile con la "
            "materia trattata e con l'interesse concreto del cliente.\n\n"
            "Resta fermo che, qualora il cliente rivesta la qualita di consumatore, "
            "la presente clausola puo essere inserita nel conferimento solo a seguito "
            "di trattativa individuale seria, effettiva e documentabile, con piena "
            "informazione sugli effetti della clausola stessa e salva ogni tutela "
            "inderogabile prevista dalla legge."
        ),
    },
    CLAUSOLA_CONTROVERSIE_MULTISTEP: {
        "label": "Clausola multistep (mediazione + arbitrato)",
        "source": (
            "Modello IUSENTRA per conferimento di incarico: mediazione ex d.lgs. "
            "28/2010, D.M. 150/2023 e arbitrato rituale ex artt. 806 ss. c.p.c.; "
            "verificare organismo, regolamento applicabile e trattativa individuale "
            "quando il cliente opera come consumatore."
        ),
        "default_text": (
            "Le parti concordano espressamente che, in caso di controversia nascente "
            "dall'interpretazione, esecuzione o validita del presente conferimento di "
            "incarico, le stesse valuteranno in via preventiva un tentativo di "
            "composizione stragiudiziale e, ove la materia lo consenta, daranno corso a "
            "un tentativo di mediazione secondo le disposizioni del d.lgs. 4 marzo 2010 "
            "n. 28 e del D.M. 24 ottobre 2023 n. 150 presso un organismo iscritto nel "
            "Registro tenuto dal Ministero della Giustizia, da indicare nel conferimento "
            "o concordare per iscritto tra le parti.\n\n"
            "In caso di esito negativo della mediazione, e salvo diverso accordo scritto, "
            "le parti potranno convenire che la controversia sia definita mediante "
            "arbitrato rituale di diritto ai sensi degli artt. 806 e seguenti del c.p.c., "
            "secondo il regolamento dell'organismo o della camera arbitrale indicata nel "
            "conferimento. L'arbitro unico, o il collegio arbitrale se espressamente "
            "previsto, sara nominato secondo tale regolamento e potra adottare le misure "
            "consentite dalla legge e non vietate da norme inderogabili applicabili al "
            "procedimento. La sede e le modalita di svolgimento, anche telematiche, "
            "saranno definite nel conferimento o in separato accordo scritto."
        ),
    },
}

_LEGACY_MULTISTEP_FONTE_MARKERS = (
    "Studio Cataldi",
    "Primavera Forense",
)


def _is_legacy_clausola_multistep(value: str | None) -> bool:
    text = str(value or "")
    return any(marker in text for marker in _LEGACY_MULTISTEP_FONTE_MARKERS)


def normalizza_modello_clausola_controversie(value: str | None) -> str:
    modello = str(value or "").strip().upper()
    return modello if modello in _CLAUSOLA_CONTROVERSIE_MODELLI else CLAUSOLA_CONTROVERSIE_NESSUNA


def catalogo_clausola_controversie() -> List[Dict[str, str]]:
    return [
        {
            "id": key,
            "label": meta["label"],
            "source": meta["source"],
            "default_text": meta["default_text"],
        }
        for key, meta in _CLAUSOLA_CONTROVERSIE_MODELLI.items()
    ]


def label_modello_clausola_controversie(value: str | None) -> str:
    modello = normalizza_modello_clausola_controversie(value)
    return _CLAUSOLA_CONTROVERSIE_MODELLI[modello]["label"]


def fonte_modello_clausola_controversie(value: str | None) -> str:
    modello = normalizza_modello_clausola_controversie(value)
    return _CLAUSOLA_CONTROVERSIE_MODELLI[modello]["source"]


def testo_predefinito_clausola_controversie(value: str | None) -> str:
    modello = normalizza_modello_clausola_controversie(value)
    return _CLAUSOLA_CONTROVERSIE_MODELLI[modello]["default_text"]


def normalizza_fonte_clausola_controversie(modello: str | None, fonte: str | None) -> str:
    fonte_norm = str(fonte or "").strip()
    modello_norm = normalizza_modello_clausola_controversie(modello)
    if modello_norm == CLAUSOLA_CONTROVERSIE_MULTISTEP and _is_legacy_clausola_multistep(fonte_norm):
        return fonte_modello_clausola_controversie(modello_norm)
    return fonte_norm


def normalizza_testo_clausola_controversie(modello: str | None, testo: str | None) -> str:
    testo_norm = str(testo or "").strip()
    modello_norm = normalizza_modello_clausola_controversie(modello)
    if modello_norm == CLAUSOLA_CONTROVERSIE_MULTISTEP and _is_legacy_clausola_multistep(testo_norm):
        return testo_predefinito_clausola_controversie(modello_norm)
    return testo_norm


def prepara_clausola_controversie(
    *,
    attiva: bool | None,
    modello: str | None,
    testo: str | None,
    trattativa_individuale: bool | None = False,
    fonte: str | None = "",
) -> Dict[str, Any]:
    modello_norm = normalizza_modello_clausola_controversie(modello)
    is_active = bool(attiva) and modello_norm != CLAUSOLA_CONTROVERSIE_NESSUNA
    if not is_active:
        return {
            "attiva": False,
            "modello": CLAUSOLA_CONTROVERSIE_NESSUNA,
            "testo": "",
            "trattativa_individuale": False,
            "fonte": "",
        }
    testo_norm = normalizza_testo_clausola_controversie(
        modello_norm, testo
    ) or testo_predefinito_clausola_controversie(modello_norm)
    return {
        "attiva": True,
        "modello": modello_norm,
        "testo": testo_norm,
        "trattativa_individuale": bool(trattativa_individuale),
        "fonte": normalizza_fonte_clausola_controversie(
            modello_norm,
            fonte or fonte_modello_clausola_controversie(modello_norm),
        ),
    }


# ================================================================ Piano pagamenti

@dataclass
class VoceScadenza:
    """Singola rata del piano di pagamento."""
    descrizione: str
    importo:     float
    scadenza:    str            # ISO date
    pagato:      bool  = False
    data_pagamento: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "descrizione": self.descrizione,
            "importo":     self.importo,
            "scadenza":    self.scadenza,
            "pagato":      self.pagato,
            "data_pagamento": self.data_pagamento,
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "VoceScadenza":
        return VoceScadenza(
            descrizione=d.get("descrizione", ""),
            importo=float(d.get("importo", 0)),
            scadenza=d.get("scadenza", ""),
            pagato=bool(d.get("pagato", False)),
            data_pagamento=d.get("data_pagamento"),
        )


# ================================================================ VocePreventivo

@dataclass
class VocePreventivo:
    """Singola voce del preventivo."""
    descrizione: str
    importo:     float = 0.0
    tipo:        TipoVoce = TipoVoce.ONORARIO

    def to_dict(self) -> Dict[str, Any]:
        return {
            "descrizione": self.descrizione,
            "importo":     self.importo,
            "tipo":        self.tipo.value,
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "VocePreventivo":
        raw_tipo = d.get("tipo", TipoVoce.ONORARIO.value)
        try:
            tipo = TipoVoce(raw_tipo)
        except Exception:
            normalized = str(raw_tipo or "").strip().upper()
            fallback_map = {item.name: item for item in TipoVoce}
            tipo = fallback_map.get(normalized, TipoVoce.ONORARIO)
        return VocePreventivo(
            descrizione=d.get("descrizione", ""),
            importo=float(d.get("importo", 0.0)),
            tipo=tipo,
        )


# ================================================================ Preventivo

@dataclass
class Preventivo:
    """Preventivo professionale dello studio legale."""
    id:              str
    numero:          str            # es. "2025/001"
    id_cliente:      str
    id_fascicolo:    Optional[str]
    data_emissione:  str            # ISO date
    data_scadenza:   Optional[str]  # ISO date
    oggetto:         str
    voci:            List[VocePreventivo]
    stato:           StatoPreventivo = StatoPreventivo.BOZZA

    applica_cassa:   bool = True    # Cassa Forense 4%
    applica_iva:     bool = True    # IVA 22%

    # Legge 124/2017 + Art. 15 DPR 633/72
    # Le anticipazioni in nome e per conto del cliente (marche, contributo unificato,
    # notifiche, perizie, ecc.) sono ESCLUSE da imponibile, CPA e IVA (Art. 15 c.1 n.3)
    anticipazioni_art15: float = 0.0   # importo anticipazioni esenti IVA (Art. 15)

    note:            str = ""
    creato_da:       str = ""
    creato_il:       str = field(default_factory=lambda: datetime.now().isoformat())

    # Parametri incarico (art. 13 L. 247/2012 + D.M. 55/2014)
    id_pratica:            str   = ""    # slug tipologia motore preventivo
    area_pratica:          str   = ""    # macro-area pratica
    area_tassonomica:      str   = ""
    macro_area_tassonomica: str  = ""
    sottobranca_tassonomica: str = ""
    tassonomia_codice:     str   = ""
    fonti_tassonomia:      List[Dict[str, Any]] = field(default_factory=list)
    classificazioni_tassonomiche: List[Dict[str, Any]] = field(default_factory=list)
    procedura_operativa_codice: str = ""
    procedura_operativa_nome: str = ""
    subbranch_operativa_codice: str = ""
    workflow_operativo_codice: str = ""
    copertura_operativa: str = ""
    canale_operativo: str = ""
    registro_operativo: str = ""
    tipo_compenso:        str   = ""    # es. "Compenso fisso", "Per fasi processuali (D.M. 55/2014)"
    tipo_procedimento:    str   = ""    # es. "Civile — fase di cognizione"
    valore_controversia:  float = 0.0  # €, 0 = indeterminabile
    tariffa_oraria:       float = 0.0  # €/ora (solo se compenso orario)
    ore_stimate:          float = 0.0  # ore stimate (solo se compenso orario)
    criterio_arrotondamento_orario: str = "ora_frazione_oltre_30"
    minuti_stimati: int = 0
    ore_fatturabili_calcolate: float = 0.0
    compenso_orario_base: float = 0.0
    massimale_ore: float = 0.0
    soglia_preapprovazione_ore: float = 0.0
    richiede_consenso_superamento_soglia: bool = True
    attivita_orarie_incluse: str = ""
    attivita_orarie_escluse: str = ""
    warning_compenso_orario: List[str] = field(default_factory=list)
    complessita:          str   = ""   # art. 13 co. 5 L. 247/2012

    # Piano di pagamento / acconti / rate
    piano_pagamenti: List[VoceScadenza] = field(default_factory=list)

    # Log calcolo normativo (JSON serializzato del RisultatoMotore)
    log_calcolo: Optional[str] = None  # JSON string

    # Token portale cliente (accesso pubblico read-only)
    token_portale: Optional[str] = None
    token_portale_il: Optional[str] = None  # ISO datetime generazione
    portale_aperto_il: Optional[str] = None  # ISO datetime prima apertura
    workflow_channel: str = "STUDIO"
    inviato_cliente_il: Optional[str] = None
    accettato_il: Optional[str] = None
    accettato_via: str = ""
    accettato_ip: str = ""
    accettato_user_agent: str = ""

    # Versione/revisione
    versione: int = 1
    id_preventivo_precedente: Optional[str] = None  # se revisione

    # Più assistiti (nomi aggiuntivi oltre al cliente principale)
    co_assistiti: List[str] = field(default_factory=list)

    # Dati studio per PDF
    studio_piva:      str = ""
    studio_cf:        str = ""
    studio_indirizzo: str = ""
    clausola_controversie_attiva: bool = False
    clausola_controversie_modello: str = CLAUSOLA_CONTROVERSIE_NESSUNA
    clausola_controversie_testo: str = ""
    clausola_controversie_trattativa_individuale: bool = False
    clausola_controversie_fonte: str = ""

    # ---------------------------------------------------------------- Calcoli

    @property
    def imponibile(self) -> float:
        return round(sum(v.importo for v in self.voci), 2)

    @property
    def cassa_forense(self) -> float:
        return round(self.imponibile * self._aliquota_cassa(), 2) if self.applica_cassa else 0.0

    def _aliquota_cassa(self) -> float:
        """Aliquota contributo integrativo Cassa Forense letta dalla tabella normativa.
        Fallback: 0.04 (4%) se la tabella non è disponibile."""
        try:
            from pct.normative_tables import GestioneTabelleNormative
            year = None
            if self.data_emissione:
                try:
                    from datetime import datetime as _dt
                    year = _dt.fromisoformat(self.data_emissione).year
                except Exception:
                    pass
            nt = GestioneTabelleNormative()
            return nt.cassa_forense_aliquota_integrativa(year) / 100.0
        except Exception:
            return 0.04

    @property
    def base_iva(self) -> float:
        return round(self.imponibile + self.cassa_forense, 2)

    @property
    def iva(self) -> float:
        return round(self.base_iva * 0.22, 2) if self.applica_iva else 0.0

    @property
    def totale(self) -> float:
        # Le anticipazioni Art. 15 si sommano al netto DOPO IVA/CPA (sono esenti)
        return round(self.base_iva + self.iva + self.anticipazioni_art15, 2)

    # ---------------------------------------------------------------- Serde

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["stato"] = self.stato.value
        d["voci"]  = [v.to_dict() for v in self.voci]
        d["piano_pagamenti"] = [r.to_dict() for r in self.piano_pagamenti]
        return d

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Preventivo":
        d = dict(d)
        stato_raw = d.get("stato", "BOZZA")
        # Retrocompatibilità: stati vecchi rimangono validi
        try:
            d["stato"] = StatoPreventivo(stato_raw)
        except ValueError:
            d["stato"] = StatoPreventivo.BOZZA
        d["workflow_channel"] = _normalize_workflow_channel(d.get("workflow_channel"))
        d["tipo_compenso"] = normalizza_tipo_compenso(d.get("tipo_compenso", ""))
        if not isinstance(d.get("warning_compenso_orario"), list):
            d["warning_compenso_orario"] = []
        d["clausola_controversie_modello"] = normalizza_modello_clausola_controversie(
            d.get("clausola_controversie_modello")
        )
        d["clausola_controversie_testo"] = normalizza_testo_clausola_controversie(
            d["clausola_controversie_modello"],
            d.get("clausola_controversie_testo", ""),
        )
        d["clausola_controversie_fonte"] = normalizza_fonte_clausola_controversie(
            d["clausola_controversie_modello"],
            d.get("clausola_controversie_fonte", ""),
        )
        d["classificazioni_tassonomiche"] = _normalizza_classificazioni_tassonomiche(
            d.get("classificazioni_tassonomiche")
        )
        if d.get("log_calcolo"):
            try:
                from pct.economico_context import dump_log_calcolo, sincronizza_contesto_economico

                sincronizzato = sincronizza_contesto_economico(d.get("log_calcolo"))
                d["log_calcolo"] = dump_log_calcolo(sincronizzato) if sincronizzato else d.get("log_calcolo")
            except Exception:
                if isinstance(d.get("log_calcolo"), dict):
                    d["log_calcolo"] = json.dumps(d["log_calcolo"], ensure_ascii=False, separators=(",", ":"))
        d["voci"] = [VocePreventivo.from_dict(v) for v in d.get("voci", [])]
        d["piano_pagamenti"] = [VoceScadenza.from_dict(r) for r in d.get("piano_pagamenti", [])]
        campi = set(Preventivo.__dataclass_fields__)
        return Preventivo(**{k: v for k, v in d.items() if k in campi})

    def genera_token_portale(self) -> str:
        """Genera (o rigenera) il token di accesso al portale cliente."""
        self.token_portale = str(uuid.uuid4()).replace("-", "")
        self.token_portale_il = datetime.now().isoformat()
        return self.token_portale


# ================================================================ ConferimentoIncarico

@dataclass
class ConferimentoIncarico:
    """Lettera di conferimento di incarico professionale."""
    id:                  str
    numero:              str            # es. "2025/001"
    id_preventivo:       Optional[str]
    id_cliente:          str
    id_fascicolo:        Optional[str]
    data_incarico:       str            # ISO date
    oggetto:             str
    avvocato_referente:  str
    compenso_pattuito:   float = 0.0   # importo concordato (può differire dal preventivo)
    note:                str = ""
    stato:               StatoConferimento = StatoConferimento.ATTIVO
    creato_da:           str = ""
    creato_il:           str = field(default_factory=lambda: datetime.now().isoformat())

    # Dati avvocato e modalità compenso
    id_pratica:               str   = ""
    area_pratica:             str   = ""
    area_tassonomica:         str   = ""
    macro_area_tassonomica:   str   = ""
    sottobranca_tassonomica:  str   = ""
    tassonomia_codice:        str   = ""
    fonti_tassonomia:         List[Dict[str, Any]] = field(default_factory=list)
    classificazioni_tassonomiche: List[Dict[str, Any]] = field(default_factory=list)
    procedura_operativa_codice: str = ""
    procedura_operativa_nome: str = ""
    subbranch_operativa_codice: str = ""
    workflow_operativo_codice: str = ""
    copertura_operativa: str = ""
    canale_operativo: str = ""
    registro_operativo: str = ""
    numero_iscrizione_albo: str   = ""
    ordine_avvocati:        str   = ""
    tipo_compenso:          str   = ""
    tipo_procedimento:      str   = ""
    tariffa_oraria:         float = 0.0
    criterio_arrotondamento_orario: str = "ora_frazione_oltre_30"
    massimale_ore: float = 0.0
    soglia_preapprovazione_ore: float = 0.0
    richiede_consenso_superamento_soglia: bool = True
    attivita_orarie_incluse: str = ""
    attivita_orarie_escluse: str = ""
    warning_compenso_orario: List[str] = field(default_factory=list)
    patto_palmario:         bool  = False
    quota_palmario_pct:     float = 0.0   # % sul risultato (es. 10.0)

    # Obblighi informativi art. 13 L. 247/2012
    informativa_art13_resa: bool = False
    clausola_adr_resa:      bool = False
    clausola_controversie_attiva: bool = False
    clausola_controversie_modello: str = CLAUSOLA_CONTROVERSIE_NESSUNA
    clausola_controversie_testo: str = ""
    clausola_controversie_trattativa_individuale: bool = False
    clausola_controversie_fonte: str = ""

    # Dati studio per PDF
    studio_piva:      str = ""
    studio_cf:        str = ""
    studio_indirizzo: str = ""
    workflow_channel: str = "STUDIO"
    firma_cliente_richiesta: bool = True
    firma_cliente_eseguita: bool = False
    firma_cliente_il: Optional[str] = None
    firma_cliente_via: str = ""
    firma_cliente_ip: str = ""
    firma_cliente_user_agent: str = ""
    fascicolo_aperto_il: Optional[str] = None

    # ---------------------------------------------------------------- Serde

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["stato"] = self.stato.value
        return d

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "ConferimentoIncarico":
        d = dict(d)
        d["stato"] = StatoConferimento(d.get("stato", "ATTIVO"))
        d["workflow_channel"] = _normalize_workflow_channel(d.get("workflow_channel"))
        d["tipo_compenso"] = normalizza_tipo_compenso(d.get("tipo_compenso", ""))
        if not isinstance(d.get("warning_compenso_orario"), list):
            d["warning_compenso_orario"] = []
        d["clausola_controversie_modello"] = normalizza_modello_clausola_controversie(
            d.get("clausola_controversie_modello")
        )
        d["clausola_controversie_testo"] = normalizza_testo_clausola_controversie(
            d["clausola_controversie_modello"],
            d.get("clausola_controversie_testo", ""),
        )
        d["clausola_controversie_fonte"] = normalizza_fonte_clausola_controversie(
            d["clausola_controversie_modello"],
            d.get("clausola_controversie_fonte", ""),
        )
        d["classificazioni_tassonomiche"] = _normalizza_classificazioni_tassonomiche(
            d.get("classificazioni_tassonomiche")
        )
        campi = set(ConferimentoIncarico.__dataclass_fields__)
        return ConferimentoIncarico(**{k: v for k, v in d.items() if k in campi})


# ================================================================ Repository

class GestionePreventivi:
    """Gestisce preventivi e conferimenti di incarico."""

    def __init__(
        self,
        db_path: str = "./preventivi/preventivi.json",
        studio_db=None,
        *,
        sync_repository_on_init: bool = True,
    ):
        self.db_path = db_path
        self._studio_db = studio_db
        self._conf_path = os.path.join(
            os.path.dirname(db_path), "conferimenti.json"
        )
        self._preventivi:   Dict[str, Preventivo]          = {}
        self._conferimenti: Dict[str, ConferimentoIncarico] = {}
        self._repository: GestionePreventiviRepository | None = None
        self._carica()
        self.repository_db_path = derive_preventivi_repository_db_path(self.db_path)
        self.repository_json_path = derive_preventivi_repository_json_path(self.db_path)
        self.repository_workflow_states_json_path = derive_preventivi_workflow_states_json_path(self.db_path)
        self.repository_field_map_json_path = derive_preventivi_field_map_json_path(self.db_path)
        self.repository_rules_json_path = derive_preventivi_rules_json_path(self.db_path)
        self._repository = GestionePreventiviRepository(
            self.repository_db_path,
            json_path=self.repository_json_path,
            workflow_states_json_path=self.repository_workflow_states_json_path,
            field_map_json_path=self.repository_field_map_json_path,
            rules_json_path=self.repository_rules_json_path,
        )
        if sync_repository_on_init:
            self._sync_repository()

    # ---------------------------------------------------------------- I/O

    def _carica(self):
        if self._studio_db is not None:
            self._preventivi = {}
            for row in self._studio_db.carica_tabella("preventivi_records"):
                try:
                    preventivo = Preventivo.from_dict(row)
                except Exception:
                    continue
                self._preventivi[preventivo.id] = preventivo
            self._conferimenti = {}
            for row in self._studio_db.carica_tabella("conferimenti_records"):
                try:
                    conferimento = ConferimentoIncarico.from_dict(row)
                except Exception:
                    continue
                self._conferimenti[conferimento.id] = conferimento
            return
        if os.path.exists(self.db_path):
            with open(self.db_path, encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, dict):
                payloads = raw.values()
            elif isinstance(raw, list):
                payloads = raw
            else:
                payloads = []
            self._preventivi = {}
            for payload in payloads:
                try:
                    preventivo = Preventivo.from_dict(payload)
                except Exception:
                    continue
                self._preventivi[preventivo.id] = preventivo

        if os.path.exists(self._conf_path):
            with open(self._conf_path, encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, dict):
                payloads = raw.values()
            elif isinstance(raw, list):
                payloads = raw
            else:
                payloads = []
            self._conferimenti = {}
            for payload in payloads:
                try:
                    conferimento = ConferimentoIncarico.from_dict(payload)
                except Exception:
                    continue
                self._conferimenti[conferimento.id] = conferimento

    def _salva_preventivi(self):
        if self._studio_db is not None:
            def _insert(conn, preventivo: Preventivo):
                payload = preventivo.to_dict()
                conn.execute(
                    """
                    INSERT INTO preventivi_records
                    (preventivo_id, numero, id_cliente, id_fascicolo, data_emissione, data_scadenza,
                     oggetto, stato, workflow_channel, tipo_compenso, tipo_procedimento,
                     area_pratica, id_pratica, procedura_operativa_codice, procedura_operativa_nome,
                     canale_operativo, registro_operativo, classificazioni_tassonomiche_json,
                     criterio_arrotondamento_orario, minuti_stimati, ore_fatturabili_calcolate,
                     compenso_orario_base, massimale_ore, soglia_preapprovazione_ore,
                     warning_compenso_orario_json,
                     totale, accettato_il, id_preventivo_precedente, token_portale, creato_il, dati_json)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        preventivo.id,
                        preventivo.numero,
                        preventivo.id_cliente,
                        preventivo.id_fascicolo or None,
                        preventivo.data_emissione,
                        preventivo.data_scadenza or "",
                        preventivo.oggetto,
                        preventivo.stato.value,
                        preventivo.workflow_channel,
                        preventivo.tipo_compenso,
                        preventivo.tipo_procedimento,
                        preventivo.area_pratica,
                        preventivo.id_pratica,
                        preventivo.procedura_operativa_codice,
                        preventivo.procedura_operativa_nome,
                        preventivo.canale_operativo,
                        preventivo.registro_operativo,
                        json.dumps(
                            preventivo.classificazioni_tassonomiche or [],
                            ensure_ascii=False,
                        ),
                        preventivo.criterio_arrotondamento_orario or "",
                        int(preventivo.minuti_stimati or 0),
                        float(preventivo.ore_fatturabili_calcolate or 0.0),
                        float(preventivo.compenso_orario_base or 0.0),
                        float(preventivo.massimale_ore or 0.0),
                        float(preventivo.soglia_preapprovazione_ore or 0.0),
                        json.dumps(preventivo.warning_compenso_orario or [], ensure_ascii=False),
                        float(preventivo.totale or 0.0),
                        preventivo.accettato_il or "",
                        preventivo.id_preventivo_precedente or "",
                        preventivo.token_portale or "",
                        preventivo.creato_il,
                        json.dumps(payload, ensure_ascii=False),
                    ),
                )

            self._studio_db.salva_tabella(
                "preventivi_records",
                list(self._preventivi.values()),
                _insert,
            )
            self._sync_repository()
            return
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(
                {k: v.to_dict() for k, v in self._preventivi.items()},
                f, ensure_ascii=False, indent=2,
            )
        self._sync_repository()

    def _salva_conferimenti(self):
        if self._studio_db is not None:
            def _insert(conn, conferimento: ConferimentoIncarico):
                payload = conferimento.to_dict()
                conn.execute(
                    """
                    INSERT INTO conferimenti_records
                    (conferimento_id, numero, id_preventivo, id_cliente, id_fascicolo,
                     data_incarico, oggetto, stato, workflow_channel, tipo_compenso,
                     tipo_procedimento, area_pratica, id_pratica, procedura_operativa_codice,
                     procedura_operativa_nome, canale_operativo, registro_operativo,
                     classificazioni_tassonomiche_json,
                     criterio_arrotondamento_orario, massimale_ore, soglia_preapprovazione_ore,
                     warning_compenso_orario_json, compenso_pattuito,
                     firma_cliente_eseguita, fascicolo_aperto_il, dati_json)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        conferimento.id,
                        conferimento.numero,
                        conferimento.id_preventivo or "",
                        conferimento.id_cliente,
                        conferimento.id_fascicolo or None,
                        conferimento.data_incarico,
                        conferimento.oggetto,
                        conferimento.stato.value,
                        conferimento.workflow_channel,
                        conferimento.tipo_compenso,
                        conferimento.tipo_procedimento,
                        conferimento.area_pratica,
                        conferimento.id_pratica,
                        conferimento.procedura_operativa_codice,
                        conferimento.procedura_operativa_nome,
                        conferimento.canale_operativo,
                        conferimento.registro_operativo,
                        json.dumps(
                            conferimento.classificazioni_tassonomiche or [],
                            ensure_ascii=False,
                        ),
                        conferimento.criterio_arrotondamento_orario or "",
                        float(conferimento.massimale_ore or 0.0),
                        float(conferimento.soglia_preapprovazione_ore or 0.0),
                        json.dumps(conferimento.warning_compenso_orario or [], ensure_ascii=False),
                        float(conferimento.compenso_pattuito or 0.0),
                        1 if conferimento.firma_cliente_eseguita else 0,
                        conferimento.fascicolo_aperto_il or "",
                        json.dumps(payload, ensure_ascii=False),
                    ),
                )

            self._studio_db.salva_tabella(
                "conferimenti_records",
                list(self._conferimenti.values()),
                _insert,
            )
            self._sync_repository()
            return
        os.makedirs(os.path.dirname(self._conf_path) or ".", exist_ok=True)
        with open(self._conf_path, "w", encoding="utf-8") as f:
            json.dump(
                {k: v.to_dict() for k, v in self._conferimenti.items()},
                f, ensure_ascii=False, indent=2,
            )
        self._sync_repository()

    def _sync_repository(self) -> None:
        if not self._repository:
            return
        self._repository.synchronize_runtime(
            preventivi=self.tutti_preventivi(),
            conferimenti=self.tutti_conferimenti(),
            preventivo_model=Preventivo,
            conferimento_model=ConferimentoIncarico,
            export_json=True,
        )

    def statistiche_repository(self) -> Dict[str, Any]:
        if not self._repository:
            return {}
        return self._repository.storage_stats()

    def repository_payload(self) -> Dict[str, Any]:
        if not self._repository:
            return {}
        return self._repository.load_repository_payload()

    def export_preventivi_repository(self, path: str | None = None) -> str:
        if not self._repository:
            raise RuntimeError("Repository preventivi non inizializzato.")
        return self._repository.export_repository_json(path)

    def export_preventivi_repository_split(self, base_dir: str | None = None) -> Dict[str, str]:
        if not self._repository:
            raise RuntimeError("Repository preventivi non inizializzato.")
        return self._repository.export_split_jsons(base_dir)

    def select_best_preventivi_runtime(self, question: str, *, limit: int = 3) -> Dict[str, Any]:
        if not self._repository:
            return {"best_preventivo": None, "alternatives": [], "matches": []}
        return self._repository.select_best_preventivi(question, limit=limit)

    def select_best_pratiche_preventivo(self, question: str, *, limit: int = 3) -> Dict[str, Any]:
        if not self._repository:
            return {"best_practice": None, "alternatives": [], "matches": []}
        return self._repository.select_best_practices(question, limit=limit)

    # ---------------------------------------------------------------- Numerazione

    def _prossimo_numero_preventivo(self, anno: Optional[int] = None) -> str:
        anno = anno or date.today().year
        prefix = f"{anno}/"
        numeri = [
            int(p.numero[len(prefix):])
            for p in self._preventivi.values()
            if p.numero.startswith(prefix) and p.numero[len(prefix):].isdigit()
        ]
        n = (max(numeri) + 1) if numeri else 1
        return f"{anno}/{n:03d}"

    def _prossimo_numero_conferimento(self, anno: Optional[int] = None) -> str:
        anno = anno or date.today().year
        prefix = f"{anno}/"
        numeri = [
            int(c.numero[len(prefix):])
            for c in self._conferimenti.values()
            if c.numero.startswith(prefix) and c.numero[len(prefix):].isdigit()
        ]
        n = (max(numeri) + 1) if numeri else 1
        return f"{anno}/{n:03d}"

    # ================================================================ CRUD Preventivi

    def crea_preventivo(self,
                        id_cliente:     str,
                        oggetto:        str,
                        voci:           List[VocePreventivo],
                        creato_da:      str = "",
                        id_fascicolo:   Optional[str] = None,
                        data_emissione: Optional[str] = None,
                        data_scadenza:  Optional[str] = None,
                        applica_cassa:  bool = True,
                        applica_iva:    bool = True,
                        anticipazioni_art15: float = 0.0,
                        note:           str = "",
                        id_pratica:           str   = "",
                        area_pratica:         str   = "",
                        area_tassonomica:     str   = "",
                        macro_area_tassonomica: str = "",
                        sottobranca_tassonomica: str = "",
                        tassonomia_codice:    str   = "",
                        fonti_tassonomia: Optional[List[Dict[str, Any]]] = None,
                        classificazioni_tassonomiche: Optional[List[Dict[str, Any]]] = None,
                        procedura_operativa_codice: str = "",
                        tipo_compenso:       str   = "",
                        tipo_procedimento:   str   = "",
                        valore_controversia: float = 0.0,
                        tariffa_oraria:      float = 0.0,
                        ore_stimate:         float = 0.0,
                        criterio_arrotondamento_orario: str = "ora_frazione_oltre_30",
                        minuti_stimati: int = 0,
                        ore_fatturabili_calcolate: float = 0.0,
                        compenso_orario_base: float = 0.0,
                        massimale_ore: float = 0.0,
                        soglia_preapprovazione_ore: float = 0.0,
                        richiede_consenso_superamento_soglia: bool = True,
                        attivita_orarie_incluse: str = "",
                        attivita_orarie_escluse: str = "",
                        warning_compenso_orario: Optional[List[str]] = None,
                         complessita:         str   = "",
                         log_calcolo:    Optional[str] = None,
                         workflow_channel: str = "STUDIO",
                         studio_piva:    str = "",
                         studio_cf:      str = "",
                         studio_indirizzo: str = "",
                         clausola_controversie_attiva: bool = False,
                         clausola_controversie_modello: str = CLAUSOLA_CONTROVERSIE_NESSUNA,
                         clausola_controversie_testo: str = "",
                         clausola_controversie_trattativa_individuale: bool = False,
                         clausola_controversie_fonte: str = "") -> Preventivo:
        operational_fields = build_operational_fields(
            procedure_code=procedura_operativa_codice,
            practice_id=id_pratica,
            area_pratica=area_pratica,
            tipo_procedimento=tipo_procedimento,
            oggetto=oggetto,
        )
        clausola_payload = prepara_clausola_controversie(
            attiva=clausola_controversie_attiva,
            modello=clausola_controversie_modello,
            testo=clausola_controversie_testo,
            trattativa_individuale=clausola_controversie_trattativa_individuale,
            fonte=clausola_controversie_fonte,
        )
        p = Preventivo(
            id=str(uuid.uuid4()),
            numero=self._prossimo_numero_preventivo(),
            id_cliente=id_cliente,
            id_fascicolo=id_fascicolo,
            data_emissione=data_emissione or date.today().isoformat(),
            data_scadenza=data_scadenza,
            oggetto=oggetto,
            voci=voci,
            stato=StatoPreventivo.BOZZA,
            applica_cassa=applica_cassa,
            applica_iva=applica_iva,
            anticipazioni_art15=anticipazioni_art15,
            note=note,
            id_pratica=id_pratica,
            area_pratica=area_pratica,
            area_tassonomica=area_tassonomica,
            macro_area_tassonomica=macro_area_tassonomica,
            sottobranca_tassonomica=sottobranca_tassonomica,
            tassonomia_codice=tassonomia_codice,
            fonti_tassonomia=list(fonti_tassonomia or []),
            classificazioni_tassonomiche=_normalizza_classificazioni_tassonomiche(
                classificazioni_tassonomiche
            ),
            procedura_operativa_codice=operational_fields.get("procedura_operativa_codice", ""),
            procedura_operativa_nome=operational_fields.get("procedura_operativa_nome", ""),
            subbranch_operativa_codice=operational_fields.get("subbranch_operativa_codice", ""),
            workflow_operativo_codice=operational_fields.get("workflow_operativo_codice", ""),
            copertura_operativa=operational_fields.get("copertura_operativa", ""),
            canale_operativo=operational_fields.get("canale_operativo", ""),
            registro_operativo=operational_fields.get("registro_operativo", ""),
            tipo_compenso=normalizza_tipo_compenso(tipo_compenso),
            tipo_procedimento=tipo_procedimento,
            valore_controversia=valore_controversia,
            tariffa_oraria=tariffa_oraria,
            ore_stimate=ore_stimate,
            criterio_arrotondamento_orario=criterio_arrotondamento_orario or "ora_frazione_oltre_30",
            minuti_stimati=int(minuti_stimati or 0),
            ore_fatturabili_calcolate=float(ore_fatturabili_calcolate or 0.0),
            compenso_orario_base=float(compenso_orario_base or 0.0),
            massimale_ore=float(massimale_ore or 0.0),
            soglia_preapprovazione_ore=float(soglia_preapprovazione_ore or 0.0),
            richiede_consenso_superamento_soglia=bool(richiede_consenso_superamento_soglia),
            attivita_orarie_incluse=attivita_orarie_incluse,
            attivita_orarie_escluse=attivita_orarie_escluse,
            warning_compenso_orario=list(warning_compenso_orario or []),
            complessita=complessita,
            log_calcolo=log_calcolo,
            workflow_channel=_normalize_workflow_channel(workflow_channel),
            creato_da=creato_da,
            studio_piva=studio_piva,
            studio_cf=studio_cf,
            studio_indirizzo=studio_indirizzo,
            clausola_controversie_attiva=clausola_payload["attiva"],
            clausola_controversie_modello=clausola_payload["modello"],
            clausola_controversie_testo=clausola_payload["testo"],
            clausola_controversie_trattativa_individuale=clausola_payload["trattativa_individuale"],
            clausola_controversie_fonte=clausola_payload["fonte"],
        )
        self._preventivi[p.id] = p
        self._salva_preventivi()
        return p

    def get_preventivo(self, id_preventivo: str) -> Optional[Preventivo]:
        return self._preventivi.get(id_preventivo)

    def tutti_preventivi(self) -> List[Preventivo]:
        return sorted(self._preventivi.values(), key=lambda p: p.data_emissione, reverse=True)

    def preventivi_per_cliente(self, id_cliente: str) -> List[Preventivo]:
        return [p for p in self.tutti_preventivi() if p.id_cliente == id_cliente]

    def preventivi_per_fascicolo(self, id_fascicolo: str) -> List[Preventivo]:
        return [p for p in self.tutti_preventivi() if p.id_fascicolo == id_fascicolo]

    def conferimenti_per_preventivo(self, id_preventivo: str) -> List["ConferimentoIncarico"]:
        return [c for c in self.tutti_conferimenti() if c.id_preventivo == id_preventivo]

    def aggiorna_preventivo(self, id_preventivo: str, **kwargs) -> Preventivo:
        p = self._preventivi[id_preventivo]
        for k, v in kwargs.items():
            if hasattr(p, k):
                if k == "workflow_channel":
                    v = _normalize_workflow_channel(v)
                elif k == "tipo_compenso":
                    v = normalizza_tipo_compenso(v)
                setattr(p, k, v)
        self._salva_preventivi()
        return p

    def cambia_stato_preventivo(self, id_preventivo: str, stato: StatoPreventivo):
        p = self._preventivi[id_preventivo]
        p.stato = stato
        self._salva_preventivi()

    def elimina_preventivo(self, id_preventivo: str):
        if id_preventivo in self._preventivi:
            del self._preventivi[id_preventivo]
            self._salva_preventivi()

    def aggiorna_scaduti(self):
        """Marca come SCADUTO i preventivi INVIATI/APERTI con data_scadenza passata."""
        oggi = date.today().isoformat()
        modificato = False
        stati_inviati = {StatoPreventivo.INVIATO, StatoPreventivo.APERTO}
        for p in self._preventivi.values():
            if p.stato in stati_inviati and p.data_scadenza and p.data_scadenza < oggi:
                p.stato = StatoPreventivo.SCADUTO
                modificato = True
        if modificato:
            self._salva_preventivi()

    def get_preventivo_by_token(self, token: str) -> Optional[Preventivo]:
        """Cerca un preventivo per token portale cliente."""
        for p in self._preventivi.values():
            if p.token_portale and p.token_portale == token:
                return p
        return None

    def aggiorna_piano_pagamenti(self, id_preventivo: str, rate: List[VoceScadenza]):
        """Aggiorna il piano di pagamento del preventivo."""
        p = self._preventivi[id_preventivo]
        p.piano_pagamenti = rate
        self._salva_preventivi()

    def crea_revisione(self, id_preventivo: str) -> "Preventivo":
        """Crea una nuova revisione del preventivo, marcando il precedente come REVISIONATO."""
        p_old = self._preventivi.get(id_preventivo)
        if not p_old:
            raise KeyError(id_preventivo)
        import copy
        p_new = copy.deepcopy(p_old)
        p_new.id = str(uuid.uuid4())
        p_new.numero = self._prossimo_numero_preventivo()
        p_new.versione = p_old.versione + 1
        p_new.id_preventivo_precedente = id_preventivo
        p_new.stato = StatoPreventivo.BOZZA
        p_new.token_portale = None
        p_new.token_portale_il = None
        p_new.portale_aperto_il = None
        p_new.inviato_cliente_il = None
        p_new.accettato_il = None
        p_new.accettato_via = ""
        p_new.accettato_ip = ""
        p_new.accettato_user_agent = ""
        p_new.creato_il = datetime.now().isoformat()
        # Marca il precedente come revisionato
        p_old.stato = StatoPreventivo.REVISIONATO
        self._preventivi[p_new.id] = p_new
        self._salva_preventivi()
        return p_new

    # ================================================================ CRUD Conferimenti

    def crea_conferimento(self,
                          id_cliente:         str,
                          oggetto:            str,
                          avvocato_referente: str,
                          creato_da:          str = "",
                          id_preventivo:      Optional[str] = None,
                          id_fascicolo:       Optional[str] = None,
                          data_incarico:      Optional[str] = None,
                          compenso_pattuito:  float = 0.0,
                          note:               str = "",
                          id_pratica:             str   = "",
                          area_pratica:           str   = "",
                          area_tassonomica:       str   = "",
                          macro_area_tassonomica: str   = "",
                          sottobranca_tassonomica: str  = "",
                          tassonomia_codice:      str   = "",
                          fonti_tassonomia: Optional[List[Dict[str, Any]]] = None,
                          classificazioni_tassonomiche: Optional[List[Dict[str, Any]]] = None,
                          procedura_operativa_codice: str = "",
                          numero_iscrizione_albo: str   = "",
                          ordine_avvocati:        str   = "",
                          tipo_compenso:          str   = "",
                          tipo_procedimento:      str   = "",
                          tariffa_oraria:         float = 0.0,
                          criterio_arrotondamento_orario: str = "",
                          massimale_ore: float = 0.0,
                          soglia_preapprovazione_ore: float = 0.0,
                          richiede_consenso_superamento_soglia: bool = True,
                          attivita_orarie_incluse: str = "",
                          attivita_orarie_escluse: str = "",
                          warning_compenso_orario: Optional[List[str]] = None,
                          patto_palmario:         bool  = False,
                          quota_palmario_pct:     float = 0.0,
                          informativa_art13_resa: bool  = False,
                          clausola_adr_resa:      bool  = False,
                          clausola_controversie_attiva: bool | None = None,
                          clausola_controversie_modello: str = "",
                          clausola_controversie_testo: str = "",
                          clausola_controversie_trattativa_individuale: bool | None = None,
                          clausola_controversie_fonte: str = "",
                          workflow_channel:       str = "",
                          firma_cliente_richiesta: bool = True,
                          studio_piva:        str = "",
                          studio_cf:          str = "",
                          studio_indirizzo:   str = "") -> ConferimentoIncarico:
        if id_preventivo:
            preventivo = self._preventivi.get(id_preventivo)
            if preventivo:
                if not id_pratica:
                    id_pratica = preventivo.id_pratica
                if not area_pratica:
                    area_pratica = preventivo.area_pratica
                if not area_tassonomica:
                    area_tassonomica = preventivo.area_tassonomica
                if not macro_area_tassonomica:
                    macro_area_tassonomica = preventivo.macro_area_tassonomica
                if not sottobranca_tassonomica:
                    sottobranca_tassonomica = preventivo.sottobranca_tassonomica
                if not tassonomia_codice:
                    tassonomia_codice = preventivo.tassonomia_codice
                if not fonti_tassonomia:
                    fonti_tassonomia = list(preventivo.fonti_tassonomia or [])
                if not classificazioni_tassonomiche:
                    classificazioni_tassonomiche = list(
                        preventivo.classificazioni_tassonomiche or []
                    )
                if not procedura_operativa_codice:
                    procedura_operativa_codice = preventivo.procedura_operativa_codice
                if not tipo_compenso:
                    tipo_compenso = preventivo.tipo_compenso
                if not tipo_procedimento:
                    tipo_procedimento = preventivo.tipo_procedimento
                if not tariffa_oraria:
                    tariffa_oraria = preventivo.tariffa_oraria
                if not criterio_arrotondamento_orario:
                    criterio_arrotondamento_orario = preventivo.criterio_arrotondamento_orario
                if not massimale_ore:
                    massimale_ore = preventivo.massimale_ore
                if not soglia_preapprovazione_ore:
                    soglia_preapprovazione_ore = preventivo.soglia_preapprovazione_ore
                if not attivita_orarie_incluse:
                    attivita_orarie_incluse = preventivo.attivita_orarie_incluse
                if not attivita_orarie_escluse:
                    attivita_orarie_escluse = preventivo.attivita_orarie_escluse
                if not warning_compenso_orario:
                    warning_compenso_orario = list(preventivo.warning_compenso_orario or [])
                richiede_consenso_superamento_soglia = preventivo.richiede_consenso_superamento_soglia
                if not compenso_pattuito:
                    compenso_pattuito = preventivo.totale
                if clausola_controversie_attiva is None:
                    clausola_controversie_attiva = preventivo.clausola_controversie_attiva
                if not clausola_controversie_modello:
                    clausola_controversie_modello = preventivo.clausola_controversie_modello
                if not clausola_controversie_testo:
                    clausola_controversie_testo = preventivo.clausola_controversie_testo
                if clausola_controversie_trattativa_individuale is None:
                    clausola_controversie_trattativa_individuale = (
                        preventivo.clausola_controversie_trattativa_individuale
                    )
                if not clausola_controversie_fonte:
                    clausola_controversie_fonte = preventivo.clausola_controversie_fonte
                workflow_channel = workflow_channel or preventivo.workflow_channel
        operational_fields = build_operational_fields(
            procedure_code=procedura_operativa_codice,
            practice_id=id_pratica,
            area_pratica=area_pratica,
            tipo_procedimento=tipo_procedimento,
            oggetto=oggetto,
        )
        clausola_payload = prepara_clausola_controversie(
            attiva=clausola_controversie_attiva,
            modello=clausola_controversie_modello,
            testo=clausola_controversie_testo,
            trattativa_individuale=clausola_controversie_trattativa_individuale,
            fonte=clausola_controversie_fonte,
        )
        c = ConferimentoIncarico(
            id=str(uuid.uuid4()),
            numero=self._prossimo_numero_conferimento(),
            id_preventivo=id_preventivo,
            id_cliente=id_cliente,
            id_fascicolo=id_fascicolo,
            data_incarico=data_incarico or date.today().isoformat(),
            oggetto=oggetto,
            avvocato_referente=avvocato_referente,
            compenso_pattuito=compenso_pattuito,
            note=note,
            stato=StatoConferimento.ATTIVO,
            creato_da=creato_da,
            id_pratica=id_pratica,
            area_pratica=area_pratica,
            area_tassonomica=area_tassonomica,
            macro_area_tassonomica=macro_area_tassonomica,
            sottobranca_tassonomica=sottobranca_tassonomica,
            tassonomia_codice=tassonomia_codice,
            fonti_tassonomia=list(fonti_tassonomia or []),
            classificazioni_tassonomiche=_normalizza_classificazioni_tassonomiche(
                classificazioni_tassonomiche
            ),
            procedura_operativa_codice=operational_fields.get("procedura_operativa_codice", ""),
            procedura_operativa_nome=operational_fields.get("procedura_operativa_nome", ""),
            subbranch_operativa_codice=operational_fields.get("subbranch_operativa_codice", ""),
            workflow_operativo_codice=operational_fields.get("workflow_operativo_codice", ""),
            copertura_operativa=operational_fields.get("copertura_operativa", ""),
            canale_operativo=operational_fields.get("canale_operativo", ""),
            registro_operativo=operational_fields.get("registro_operativo", ""),
            numero_iscrizione_albo=numero_iscrizione_albo,
            ordine_avvocati=ordine_avvocati,
            tipo_compenso=normalizza_tipo_compenso(tipo_compenso),
            tipo_procedimento=tipo_procedimento,
            tariffa_oraria=tariffa_oraria,
            criterio_arrotondamento_orario=criterio_arrotondamento_orario or "ora_frazione_oltre_30",
            massimale_ore=float(massimale_ore or 0.0),
            soglia_preapprovazione_ore=float(soglia_preapprovazione_ore or 0.0),
            richiede_consenso_superamento_soglia=bool(richiede_consenso_superamento_soglia),
            attivita_orarie_incluse=attivita_orarie_incluse,
            attivita_orarie_escluse=attivita_orarie_escluse,
            warning_compenso_orario=list(warning_compenso_orario or []),
            patto_palmario=patto_palmario,
            quota_palmario_pct=quota_palmario_pct,
            informativa_art13_resa=informativa_art13_resa,
            clausola_adr_resa=clausola_adr_resa,
            clausola_controversie_attiva=clausola_payload["attiva"],
            clausola_controversie_modello=clausola_payload["modello"],
            clausola_controversie_testo=clausola_payload["testo"],
            clausola_controversie_trattativa_individuale=clausola_payload["trattativa_individuale"],
            clausola_controversie_fonte=clausola_payload["fonte"],
            workflow_channel=_normalize_workflow_channel(workflow_channel),
            firma_cliente_richiesta=bool(firma_cliente_richiesta),
            studio_piva=studio_piva,
            studio_cf=studio_cf,
            studio_indirizzo=studio_indirizzo,
        )
        self._conferimenti[c.id] = c
        self._salva_conferimenti()
        return c

    def get_conferimento(self, id_conferimento: str) -> Optional[ConferimentoIncarico]:
        return self._conferimenti.get(id_conferimento)

    def tutti_conferimenti(self) -> List[ConferimentoIncarico]:
        return sorted(self._conferimenti.values(), key=lambda c: c.data_incarico, reverse=True)

    def conferimenti_per_cliente(self, id_cliente: str) -> List[ConferimentoIncarico]:
        return [c for c in self.tutti_conferimenti() if c.id_cliente == id_cliente]

    def conferimenti_per_fascicolo(self, id_fascicolo: str) -> List[ConferimentoIncarico]:
        return [c for c in self.tutti_conferimenti() if c.id_fascicolo == id_fascicolo]

    def aggiorna_conferimento(self, id_conferimento: str, **kwargs) -> ConferimentoIncarico:
        c = self._conferimenti[id_conferimento]
        for k, v in kwargs.items():
            if hasattr(c, k):
                if k == "workflow_channel":
                    v = _normalize_workflow_channel(v)
                elif k == "tipo_compenso":
                    v = normalizza_tipo_compenso(v)
                setattr(c, k, v)
        self._salva_conferimenti()
        return c

    def get_conferimento_principale_preventivo(self, id_preventivo: str) -> Optional["ConferimentoIncarico"]:
        rows = sorted(
            [c for c in self.tutti_conferimenti() if c.id_preventivo == id_preventivo],
            key=lambda c: (c.data_incarico or "", c.creato_il or ""),
            reverse=True,
        )
        return rows[0] if rows else None

    def registra_invio_preventivo(
        self,
        id_preventivo: str,
        *,
        workflow_channel: str = "ONLINE",
    ) -> Preventivo:
        p = self._preventivi[id_preventivo]
        p.workflow_channel = _normalize_workflow_channel(workflow_channel)
        p.stato = StatoPreventivo.INVIATO
        p.inviato_cliente_il = datetime.now().isoformat()
        self._salva_preventivi()
        return p

    def crea_conferimento_da_preventivo(
        self,
        id_preventivo: str,
        *,
        creato_da: str = "",
        avvocato_referente: str = "",
        note: str = "",
        workflow_channel: str = "",
        informativa_art13_resa: bool = True,
        clausola_adr_resa: bool = True,
        studio_piva: str = "",
        studio_cf: str = "",
        studio_indirizzo: str = "",
        numero_iscrizione_albo: str = "",
        ordine_avvocati: str = "",
    ) -> ConferimentoIncarico:
        preventivo = self._preventivi.get(id_preventivo)
        if not preventivo:
            raise KeyError(id_preventivo)
        existing = self.get_conferimento_principale_preventivo(id_preventivo)
        if existing:
            return existing
        oggetto = f"Conferimento incarico - {preventivo.oggetto}".strip(" -")
        return self.crea_conferimento(
            id_cliente=preventivo.id_cliente,
            oggetto=oggetto,
            avvocato_referente=avvocato_referente or preventivo.creato_da or "Avv. referente",
            creato_da=creato_da,
            id_preventivo=preventivo.id,
            id_fascicolo=preventivo.id_fascicolo,
            compenso_pattuito=preventivo.totale,
            note=note,
            id_pratica=preventivo.id_pratica,
            area_pratica=preventivo.area_pratica,
            tipo_compenso=preventivo.tipo_compenso,
            tipo_procedimento=preventivo.tipo_procedimento,
            tariffa_oraria=preventivo.tariffa_oraria,
            numero_iscrizione_albo=numero_iscrizione_albo,
            ordine_avvocati=ordine_avvocati,
            criterio_arrotondamento_orario=preventivo.criterio_arrotondamento_orario,
            massimale_ore=preventivo.massimale_ore,
            soglia_preapprovazione_ore=preventivo.soglia_preapprovazione_ore,
            richiede_consenso_superamento_soglia=preventivo.richiede_consenso_superamento_soglia,
            attivita_orarie_incluse=preventivo.attivita_orarie_incluse,
            attivita_orarie_escluse=preventivo.attivita_orarie_escluse,
            warning_compenso_orario=list(preventivo.warning_compenso_orario or []),
            informativa_art13_resa=informativa_art13_resa,
            clausola_adr_resa=clausola_adr_resa,
            workflow_channel=workflow_channel or preventivo.workflow_channel,
            firma_cliente_richiesta=True,
            studio_piva=studio_piva or preventivo.studio_piva,
            studio_cf=studio_cf or preventivo.studio_cf,
            studio_indirizzo=studio_indirizzo or preventivo.studio_indirizzo,
        )

    def registra_accettazione_preventivo(
        self,
        id_preventivo: str,
        *,
        workflow_channel: str = "STUDIO",
        via: str = "",
        ip: str = "",
        user_agent: str = "",
        creato_da: str = "",
        avvocato_referente: str = "",
        auto_crea_conferimento: bool = True,
        studio_piva: str = "",
        studio_cf: str = "",
        studio_indirizzo: str = "",
        numero_iscrizione_albo: str = "",
        ordine_avvocati: str = "",
    ) -> tuple[Preventivo, Optional["ConferimentoIncarico"]]:
        p = self._preventivi[id_preventivo]
        p.workflow_channel = _normalize_workflow_channel(workflow_channel)
        p.stato = StatoPreventivo.ACCETTATO
        p.accettato_il = datetime.now().isoformat()
        p.accettato_via = str(via or "").strip()
        p.accettato_ip = str(ip or "").strip()
        p.accettato_user_agent = (user_agent or "").strip()[:300]
        self._salva_preventivi()

        conferimento = self.get_conferimento_principale_preventivo(id_preventivo)
        if not conferimento and auto_crea_conferimento:
            conferimento = self.crea_conferimento_da_preventivo(
                id_preventivo,
                creato_da=creato_da,
                avvocato_referente=avvocato_referente,
                workflow_channel=p.workflow_channel,
                studio_piva=studio_piva,
                studio_cf=studio_cf,
                studio_indirizzo=studio_indirizzo,
                numero_iscrizione_albo=numero_iscrizione_albo,
                ordine_avvocati=ordine_avvocati,
                note=(
                    "Conferimento creato automaticamente dal workflow commerciale "
                    "dopo accettazione del preventivo."
                ),
            )
        return p, conferimento

    def registra_firma_conferimento(
        self,
        id_conferimento: str,
        *,
        via: str = "",
        workflow_channel: str = "",
        ip: str = "",
        user_agent: str = "",
    ) -> ConferimentoIncarico:
        c = self._conferimenti[id_conferimento]
        c.workflow_channel = _normalize_workflow_channel(workflow_channel or c.workflow_channel)
        c.firma_cliente_richiesta = True
        c.firma_cliente_eseguita = True
        c.firma_cliente_il = datetime.now().isoformat()
        c.firma_cliente_via = str(via or "").strip()
        c.firma_cliente_ip = str(ip or "").strip()
        c.firma_cliente_user_agent = (user_agent or "").strip()[:300]
        self._salva_conferimenti()
        return c

    def cambia_stato_conferimento(self, id_conferimento: str, stato: StatoConferimento):
        c = self._conferimenti[id_conferimento]
        c.stato = stato
        self._salva_conferimenti()

    def collega_fascicolo(
        self,
        id_fascicolo: str,
        *,
        id_preventivo: Optional[str] = None,
        id_conferimento: Optional[str] = None,
        converti_preventivo: bool = False,
    ) -> None:
        modifica_preventivi = False
        modifica_conferimenti = False
        if id_preventivo and id_preventivo in self._preventivi:
            p = self._preventivi[id_preventivo]
            p.id_fascicolo = id_fascicolo
            if converti_preventivo:
                p.stato = StatoPreventivo.CONVERTITO
            modifica_preventivi = True
        if id_conferimento and id_conferimento in self._conferimenti:
            c = self._conferimenti[id_conferimento]
            c.id_fascicolo = id_fascicolo
            c.fascicolo_aperto_il = datetime.now().isoformat()
            modifica_conferimenti = True
            if c.id_preventivo and c.id_preventivo in self._preventivi:
                p = self._preventivi[c.id_preventivo]
                p.id_fascicolo = id_fascicolo
                if converti_preventivo:
                    p.stato = StatoPreventivo.CONVERTITO
                modifica_preventivi = True
        if modifica_preventivi:
            self._salva_preventivi()
        if modifica_conferimenti:
            self._salva_conferimenti()

    def elimina_conferimento(self, id_conferimento: str):
        if id_conferimento in self._conferimenti:
            del self._conferimenti[id_conferimento]
            self._salva_conferimenti()
