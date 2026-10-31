"""La scheda di calcolo comune alle stime motivate e la lettura dei dati scritti dall'avvocato."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

STATO_DATI_INSUFFICIENTI = "dati_insufficienti"
STATO_DA_VERIFICARE = "stima_da_verificare"
STATO_VALIDATA = "proposta_validata_dallo_studio"

ETICHETTE_STATO = {
    STATO_DATI_INSUFFICIENTI: "Dati insufficienti: nessuna proposta numerica",
    STATO_DA_VERIFICARE: "Stima da verificare: restano presupposti o valutazioni da approvare",
    STATO_VALIDATA: "Proposta validata dallo studio (non è un importo garantito in giudizio)",
}

_IMPORTO = r"\d+(?:[.,]\d+)*"
_INTERVALLO = re.compile(rf"^\s*({_IMPORTO})\s*(?:-|–|÷|a)\s*({_IMPORTO})\s*$")


def _numero(testo: str) -> Optional[float]:
    grezzo = testo.strip().replace("€", "").replace(" ", "")
    if not grezzo:
        return None
    # 1.234,56 -> 1234.56 ; 1234.56 resta tale ; 1.500 -> 1500
    if "," in grezzo:
        grezzo = grezzo.replace(".", "").replace(",", ".")
    elif grezzo.count(".") == 1 and len(grezzo.split(".")[1]) == 3:
        grezzo = grezzo.replace(".", "")
    try:
        return float(grezzo)
    except ValueError:
        return None


def importo_o_intervallo(testo: Any) -> Optional[Tuple[float, float]]:
    """«900» -> (900, 900); «800-1000» -> (800, 1000); testo non numerico -> None."""
    valore = str(testo or "").strip()
    trovato = _INTERVALLO.match(valore)
    if trovato:
        basso, alto = _numero(trovato.group(1)), _numero(trovato.group(2))
        if basso is None or alto is None:
            return None
        return (min(basso, alto), max(basso, alto))
    unico = _numero(valore)
    return None if unico is None else (unico, unico)


def righe_testo(testo: Any, colonne: int) -> List[List[str]]:
    """Le righe non vuote di un campo a più righe, separate da «;», portate a `colonne` celle."""
    righe = []
    for riga in str(testo or "").splitlines():
        if not riga.strip():
            continue
        celle = [cella.strip() for cella in riga.split(";")]
        righe.append((celle + [""] * colonne)[:colonne])
    return righe


@dataclass
class SchedaDiCalcolo:
    """Metodo, dati, ipotesi, fonti, mancanze e valutazioni di una stima."""

    metodo: str
    versione: str
    dati: Dict[str, Any] = field(default_factory=dict)
    ipotesi: List[str] = field(default_factory=list)
    mancanti: List[str] = field(default_factory=list)
    valutazioni: List[Dict[str, str]] = field(default_factory=list)
    fonti: List[Dict[str, str]] = field(default_factory=list)
    validata: bool = False
    motivazione_avvocato: str = ""

    def stato(self, *, calcolabile: bool) -> str:
        if not calcolabile:
            return STATO_DATI_INSUFFICIENTI
        # La validazione dello studio vale solo se non manca nulla di essenziale e se è motivata.
        if self.validata and not self.mancanti and self.motivazione_avvocato.strip():
            return STATO_VALIDATA
        return STATO_DA_VERIFICARE

    def to_dict(self, *, calcolabile: bool) -> Dict[str, Any]:
        stato = self.stato(calcolabile=calcolabile)
        avvisi: List[str] = []
        if self.validata and stato != STATO_VALIDATA:
            avvisi.append(
                "La validazione dello studio non è applicata: "
                + ("mancano valutazioni essenziali." if self.mancanti else "manca la motivazione dell'avvocato.")
            )
        return {
            "stato": stato,
            "stato_label": ETICHETTE_STATO[stato],
            "scheda_di_calcolo": {
                "metodo": self.metodo,
                "versione": self.versione,
                "dati": dict(self.dati),
                "ipotesi": list(self.ipotesi),
                "da_completare": list(self.mancanti),
                "valutazioni": list(self.valutazioni),
                "motivazione_avvocato": self.motivazione_avvocato.strip(),
            },
            "avvisi_validazione": avvisi,
        }


__all__ = [
    "ETICHETTE_STATO",
    "STATO_DATI_INSUFFICIENTI",
    "STATO_DA_VERIFICARE",
    "STATO_VALIDATA",
    "SchedaDiCalcolo",
    "importo_o_intervallo",
    "righe_testo",
]
