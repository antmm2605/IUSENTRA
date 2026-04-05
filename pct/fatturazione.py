"""
pct/fatturazione.py — Fatturazione e parcelle professionali.

Gestisce la generazione, numerazione e archiviazione di parcelle
per uno studio legale italiano, con:
  - Cassa Forense (CNPAF) 4 % sull'imponibile
  - IVA 22 % su (imponibile + cassa forense)
  - Ritenuta d'acconto 20 % (opzionale, per clienti PF/aziende)
  - Marca da bollo € 2,00 (se dovuta)
  - Numerazione progressiva per anno (es. 2024/001)
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

class StatoParcella(str, Enum):
    BOZZA   = "BOZZA"
    EMESSA  = "EMESSA"
    PAGATA  = "PAGATA"
    SCADUTA = "SCADUTA"
    ANNULLATA = "ANNULLATA"


class MetodoPagamento(str, Enum):
    BONIFICO   = "Bonifico bancario"
    CONTANTI   = "Contanti"
    ASSEGNO    = "Assegno"
    PAYPAL     = "PayPal"
    CARTA      = "Carta di credito"
    ALTRO      = "Altro"


# ================================================================ Voce parcella

@dataclass
class VoceParcella:
    """Singola voce della parcella (prestazione professionale)."""
    descrizione:      str
    quantita:         float = 1.0
    prezzo_unitario:  float = 0.0

    @property
    def importo(self) -> float:
        return round(self.quantita * self.prezzo_unitario, 2)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "descrizione":     self.descrizione,
            "quantita":        self.quantita,
            "prezzo_unitario": self.prezzo_unitario,
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "VoceParcella":
        return VoceParcella(
            descrizione=d.get("descrizione", ""),
            quantita=float(d.get("quantita", 1.0)),
            prezzo_unitario=float(d.get("prezzo_unitario", 0.0)),
        )


# ================================================================ Parcella

@dataclass
class Parcella:
    """Record completo di una parcella professionale."""
    id:               str
    numero:           str           # es. "2025/001"
    id_cliente:       str
    id_fascicolo:     Optional[str]
    data_emissione:   str           # ISO date
    data_scadenza:    Optional[str] # ISO date
    voci:             List[VoceParcella]
    stato:            StatoParcella = StatoParcella.BOZZA

    # Opzioni fiscali
    applica_iva:       bool  = True    # 22 %
    applica_cassa:     bool  = True    # Cassa Forense 4 %
    applica_ritenuta:  bool  = False   # Ritenuta d'acconto 20 %
    applica_bollo:     bool  = False   # Marca da bollo € 2,00

    note:              str   = ""
    creato_da:         str   = ""
    creato_il:         str   = field(default_factory=lambda: datetime.now().isoformat())
    data_pagamento:    Optional[str] = None
    metodo_pagamento:  Optional[str] = None

    # Provenienza e contesto economico
    origine:           str   = ""
    id_preventivo:     Optional[str] = None
    id_pratica:        str   = ""
    area_pratica:      str   = ""
    tipo_compenso:     str   = ""
    tipo_procedimento: str   = ""
    valore_controversia: float = 0.0
    complessita:       str   = ""
    log_calcolo:       Optional[str] = None

    # Dati studio (per il PDF — sovrascrivono config globale se impostati)
    studio_piva:       str = ""
    studio_cf:         str = ""
    studio_indirizzo:  str = ""
    studio_iban:       str = ""

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
    def ritenuta(self) -> float:
        return round(self.imponibile * 0.20, 2) if self.applica_ritenuta else 0.0

    @property
    def bollo(self) -> float:
        return 2.00 if self.applica_bollo else 0.0

    @property
    def totale(self) -> float:
        return round(self.base_iva + self.iva + self.bollo - self.ritenuta, 2)

    @property
    def netto_a_pagare(self) -> float:
        """Importo effettivo da versare (dopo ritenuta)."""
        return self.totale

    # ---------------------------------------------------------------- Serde

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["stato"] = self.stato.value
        d["voci"]  = [v.to_dict() for v in self.voci]
        return d

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Parcella":
        d = dict(d)
        d["stato"] = StatoParcella(d.get("stato", "BOZZA"))
        d["voci"]  = [VoceParcella.from_dict(v) for v in d.get("voci", [])]
        campi = set(Parcella.__dataclass_fields__)
        return Parcella(**{k: v for k, v in d.items() if k in campi})


# ================================================================ Gestore

class GestioneFatturazione:
    """Gestisce creazione, aggiornamento e ricerca delle parcelle."""

    def __init__(self, db_path: str = "./fatturazione/parcelle.json"):
        self.db_path = db_path
        self._parcelle: Dict[str, Parcella] = {}
        self._carica()

    # ---------------------------------------------------------------- I/O

    def _carica(self):
        if os.path.exists(self.db_path):
            with open(self.db_path, encoding="utf-8") as f:
                raw = json.load(f)
            self._parcelle = {k: Parcella.from_dict(v) for k, v in raw.items()}

    def _salva(self):
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(
                {k: v.to_dict() for k, v in self._parcelle.items()},
                f, ensure_ascii=False, indent=2
            )

    # ---------------------------------------------------------------- Numerazione

    def _prossimo_numero(self, anno: Optional[int] = None) -> str:
        anno = anno or date.today().year
        prefix = f"{anno}/"
        numeri = [
            int(p.numero[len(prefix):])
            for p in self._parcelle.values()
            if p.numero.startswith(prefix) and p.numero[len(prefix):].isdigit()
        ]
        n = (max(numeri) + 1) if numeri else 1
        return f"{anno}/{n:03d}"

    # ---------------------------------------------------------------- CRUD

    def crea(self,
             id_cliente:      str,
             voci:            List[VoceParcella],
             creato_da:       str = "",
             id_fascicolo:    Optional[str] = None,
             data_emissione:  Optional[str] = None,
             data_scadenza:   Optional[str] = None,
             applica_iva:     bool = True,
             applica_cassa:   bool = True,
             applica_ritenuta: bool = False,
             applica_bollo:   bool = False,
             note:            str = "",
             origine:         str = "",
             id_preventivo:   Optional[str] = None,
             id_pratica:      str = "",
             area_pratica:    str = "",
             tipo_compenso:   str = "",
             tipo_procedimento: str = "",
             valore_controversia: float = 0.0,
             complessita:     str = "",
             log_calcolo:     Optional[str] = None,
             studio_piva:     str = "",
             studio_cf:       str = "",
             studio_indirizzo: str = "",
             studio_iban:     str = "") -> Parcella:
        oggi = date.today().isoformat()
        p = Parcella(
            id=str(uuid.uuid4()),
            numero=self._prossimo_numero(),
            id_cliente=id_cliente,
            id_fascicolo=id_fascicolo,
            data_emissione=data_emissione or oggi,
            data_scadenza=data_scadenza,
            voci=voci,
            stato=StatoParcella.BOZZA,
            applica_iva=applica_iva,
            applica_cassa=applica_cassa,
            applica_ritenuta=applica_ritenuta,
            applica_bollo=applica_bollo,
            note=note,
            origine=origine,
            id_preventivo=id_preventivo,
            id_pratica=id_pratica,
            area_pratica=area_pratica,
            tipo_compenso=tipo_compenso,
            tipo_procedimento=tipo_procedimento,
            valore_controversia=valore_controversia,
            complessita=complessita,
            log_calcolo=log_calcolo,
            creato_da=creato_da,
            studio_piva=studio_piva,
            studio_cf=studio_cf,
            studio_indirizzo=studio_indirizzo,
            studio_iban=studio_iban,
        )
        self._parcelle[p.id] = p
        self._salva()
        return p

    def get(self, id_parcella: str) -> Optional[Parcella]:
        return self._parcelle.get(id_parcella)

    def tutte(self) -> List[Parcella]:
        return sorted(self._parcelle.values(), key=lambda p: p.data_emissione, reverse=True)

    def per_cliente(self, id_cliente: str) -> List[Parcella]:
        return [p for p in self.tutte() if p.id_cliente == id_cliente]

    def per_fascicolo(self, id_fascicolo: str) -> List[Parcella]:
        return [p for p in self.tutte() if p.id_fascicolo == id_fascicolo]

    def aggiorna(self, id_parcella: str, **kwargs) -> Parcella:
        p = self._parcelle[id_parcella]
        for k, v in kwargs.items():
            if hasattr(p, k):
                setattr(p, k, v)
        self._salva()
        return p

    def cambia_stato(self, id_parcella: str, stato: StatoParcella,
                     data_pagamento: Optional[str] = None,
                     metodo_pagamento: Optional[str] = None):
        p = self._parcelle[id_parcella]
        p.stato = stato
        if stato == StatoParcella.PAGATA:
            p.data_pagamento = data_pagamento or date.today().isoformat()
            if metodo_pagamento:
                p.metodo_pagamento = metodo_pagamento
        self._salva()

    def elimina(self, id_parcella: str):
        if id_parcella in self._parcelle:
            del self._parcelle[id_parcella]
            self._salva()

    # ---------------------------------------------------------------- Statistiche

    def statistiche(self, anno: Optional[int] = None) -> Dict[str, Any]:
        anno = anno or date.today().year
        prefix = f"{anno}/"
        parcelle_anno = [p for p in self._parcelle.values()
                         if p.data_emissione.startswith(str(anno))]
        emesse   = [p for p in parcelle_anno if p.stato != StatoParcella.BOZZA and p.stato != StatoParcella.ANNULLATA]
        pagate   = [p for p in emesse if p.stato == StatoParcella.PAGATA]
        scadute  = [p for p in emesse if p.stato == StatoParcella.SCADUTA]
        in_attesa = [p for p in emesse if p.stato == StatoParcella.EMESSA]
        return {
            "anno":              anno,
            "totale_emesse":     len(emesse),
            "totale_pagate":     len(pagate),
            "totale_scadute":    len(scadute),
            "totale_in_attesa":  len(in_attesa),
            "fatturato_lordo":   round(sum(p.totale for p in emesse), 2),
            "incassato":         round(sum(p.totale for p in pagate), 2),
            "da_incassare":      round(sum(p.totale for p in in_attesa), 2),
            "scaduto":           round(sum(p.totale for p in scadute), 2),
        }

    def aggiorna_scadute(self):
        """Marca come SCADUTA le parcelle EMESSE con data_scadenza passata."""
        oggi = date.today().isoformat()
        modificato = False
        for p in self._parcelle.values():
            if p.stato == StatoParcella.EMESSA and p.data_scadenza and p.data_scadenza < oggi:
                p.stato = StatoParcella.SCADUTA
                modificato = True
        if modificato:
            self._salva()
