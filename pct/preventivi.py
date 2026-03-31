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
        return VocePreventivo(
            descrizione=d.get("descrizione", ""),
            importo=float(d.get("importo", 0.0)),
            tipo=TipoVoce(d.get("tipo", TipoVoce.ONORARIO.value)),
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
    tipo_compenso:        str   = ""    # es. "Compenso fisso", "Per fasi processuali (D.M. 55/2014)"
    tipo_procedimento:    str   = ""    # es. "Civile — fase di cognizione"
    valore_controversia:  float = 0.0  # €, 0 = indeterminabile
    tariffa_oraria:       float = 0.0  # €/ora (solo se compenso orario)
    ore_stimate:          float = 0.0  # ore stimate (solo se compenso orario)
    complessita:          str   = ""   # art. 13 co. 5 L. 247/2012

    # Piano di pagamento / acconti / rate
    piano_pagamenti: List[VoceScadenza] = field(default_factory=list)

    # Log calcolo normativo (JSON serializzato del RisultatoMotore)
    log_calcolo: Optional[str] = None  # JSON string

    # Token portale cliente (accesso pubblico read-only)
    token_portale: Optional[str] = None
    token_portale_il: Optional[str] = None  # ISO datetime generazione
    portale_aperto_il: Optional[str] = None  # ISO datetime prima apertura

    # Versione/revisione
    versione: int = 1
    id_preventivo_precedente: Optional[str] = None  # se revisione

    # Più assistiti (nomi aggiuntivi oltre al cliente principale)
    co_assistiti: List[str] = field(default_factory=list)

    # Dati studio per PDF
    studio_piva:      str = ""
    studio_cf:        str = ""
    studio_indirizzo: str = ""

    # ---------------------------------------------------------------- Calcoli

    @property
    def imponibile(self) -> float:
        return round(sum(v.importo for v in self.voci), 2)

    @property
    def cassa_forense(self) -> float:
        return round(self.imponibile * 0.04, 2) if self.applica_cassa else 0.0

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
    numero_iscrizione_albo: str   = ""
    ordine_avvocati:        str   = ""
    tipo_compenso:          str   = ""
    tipo_procedimento:      str   = ""
    tariffa_oraria:         float = 0.0
    patto_palmario:         bool  = False
    quota_palmario_pct:     float = 0.0   # % sul risultato (es. 10.0)

    # Obblighi informativi art. 13 L. 247/2012
    informativa_art13_resa: bool = False
    clausola_adr_resa:      bool = False

    # Dati studio per PDF
    studio_piva:      str = ""
    studio_cf:        str = ""
    studio_indirizzo: str = ""

    # ---------------------------------------------------------------- Serde

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["stato"] = self.stato.value
        return d

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "ConferimentoIncarico":
        d = dict(d)
        d["stato"] = StatoConferimento(d.get("stato", "ATTIVO"))
        campi = set(ConferimentoIncarico.__dataclass_fields__)
        return ConferimentoIncarico(**{k: v for k, v in d.items() if k in campi})


# ================================================================ Repository

class GestionePreventivi:
    """Gestisce preventivi e conferimenti di incarico."""

    def __init__(self, db_path: str = "./preventivi/preventivi.json"):
        self.db_path = db_path
        self._conf_path = os.path.join(
            os.path.dirname(db_path), "conferimenti.json"
        )
        self._preventivi:   Dict[str, Preventivo]          = {}
        self._conferimenti: Dict[str, ConferimentoIncarico] = {}
        self._carica()

    # ---------------------------------------------------------------- I/O

    def _carica(self):
        if os.path.exists(self.db_path):
            with open(self.db_path, encoding="utf-8") as f:
                raw = json.load(f)
            self._preventivi = {k: Preventivo.from_dict(v) for k, v in raw.items()}

        if os.path.exists(self._conf_path):
            with open(self._conf_path, encoding="utf-8") as f:
                raw = json.load(f)
            self._conferimenti = {
                k: ConferimentoIncarico.from_dict(v) for k, v in raw.items()
            }

    def _salva_preventivi(self):
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(
                {k: v.to_dict() for k, v in self._preventivi.items()},
                f, ensure_ascii=False, indent=2,
            )

    def _salva_conferimenti(self):
        os.makedirs(os.path.dirname(self._conf_path) or ".", exist_ok=True)
        with open(self._conf_path, "w", encoding="utf-8") as f:
            json.dump(
                {k: v.to_dict() for k, v in self._conferimenti.items()},
                f, ensure_ascii=False, indent=2,
            )

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
                        tipo_compenso:       str   = "",
                        tipo_procedimento:   str   = "",
                        valore_controversia: float = 0.0,
                        tariffa_oraria:      float = 0.0,
                        ore_stimate:         float = 0.0,
                        complessita:         str   = "",
                        studio_piva:    str = "",
                        studio_cf:      str = "",
                        studio_indirizzo: str = "") -> Preventivo:
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
            tipo_compenso=tipo_compenso,
            tipo_procedimento=tipo_procedimento,
            valore_controversia=valore_controversia,
            tariffa_oraria=tariffa_oraria,
            ore_stimate=ore_stimate,
            complessita=complessita,
            creato_da=creato_da,
            studio_piva=studio_piva,
            studio_cf=studio_cf,
            studio_indirizzo=studio_indirizzo,
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

    def aggiorna_preventivo(self, id_preventivo: str, **kwargs) -> Preventivo:
        p = self._preventivi[id_preventivo]
        for k, v in kwargs.items():
            if hasattr(p, k):
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
                          numero_iscrizione_albo: str   = "",
                          ordine_avvocati:        str   = "",
                          tipo_compenso:          str   = "",
                          tipo_procedimento:      str   = "",
                          tariffa_oraria:         float = 0.0,
                          patto_palmario:         bool  = False,
                          quota_palmario_pct:     float = 0.0,
                          informativa_art13_resa: bool  = False,
                          clausola_adr_resa:      bool  = False,
                          studio_piva:        str = "",
                          studio_cf:          str = "",
                          studio_indirizzo:   str = "") -> ConferimentoIncarico:
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
            numero_iscrizione_albo=numero_iscrizione_albo,
            ordine_avvocati=ordine_avvocati,
            tipo_compenso=tipo_compenso,
            tipo_procedimento=tipo_procedimento,
            tariffa_oraria=tariffa_oraria,
            patto_palmario=patto_palmario,
            quota_palmario_pct=quota_palmario_pct,
            informativa_art13_resa=informativa_art13_resa,
            clausola_adr_resa=clausola_adr_resa,
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
                setattr(c, k, v)
        self._salva_conferimenti()
        return c

    def cambia_stato_conferimento(self, id_conferimento: str, stato: StatoConferimento):
        c = self._conferimenti[id_conferimento]
        c.stato = stato
        self._salva_conferimenti()

    def elimina_conferimento(self, id_conferimento: str):
        if id_conferimento in self._conferimenti:
            del self._conferimenti[id_conferimento]
            self._salva_conferimenti()
