"""La voce di lavoro del Controllo Studio e le fasce di tempo in cui si ordina."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any

AREE = {
    "scadenze": "Scadenze",
    "agenda": "Udienze e appuntamenti",
    "notifiche": "Notifiche",
    "comunicazioni": "Comunicazioni",
    "incassi": "Incassi",
}
FASCE = {
    "scaduto": "Scaduto: da recuperare subito",
    "oggi": "Oggi",
    "domani": "Domani",
    "settimana": "Nei prossimi 7 giorni",
    "prossimi": "Entro 30 giorni",
    "da_leggere": "Comunicazioni da leggere",
    "senza_data": "Termine da determinare / data da verificare",
}
GRAVITA = ("critica", "alta", "normale")


@dataclass
class Azione:
    etichetta: str
    href: str = ""
    endpoint: str = ""  # azione diretta (POST) al posto del collegamento
    conferma: str = ""
    principale: bool = False


@dataclass
class Voce:
    id: str
    area: str
    titolo: str
    dettaglio: str = ""
    data: str = ""  # ISO (giorno)
    ora: str = ""
    data_riferimento: str = ""
    tipo_data_riferimento: str = ""
    gravita: str = "normale"
    etichetta: str = ""
    fascicolo: dict[str, str] = field(default_factory=dict)
    importo: float = 0.0
    azioni: list[Azione] = field(default_factory=list)
    fascia: str = ""

    def to_dict(self) -> dict[str, Any]:
        dati = asdict(self)
        dati["area_etichetta"] = AREE.get(self.area, self.area)
        return dati


def fascia(giorno: str, oggi: date) -> str:
    try:
        quando = date.fromisoformat(str(giorno or "")[:10])
    except ValueError:
        return "senza_data"
    delta = (quando - oggi).days
    if delta < 0:
        return "scaduto"
    if delta == 0:
        return "oggi"
    if delta == 1:
        return "domani"
    if delta <= 7:
        return "settimana"
    return "prossimi"


def quando_etichetta(giorno: str, oggi: date) -> str:
    """«Scaduta da 3 giorni», «Oggi», «Domani», «Tra 5 giorni»: il testo che l'avvocato legge."""

    try:
        delta = (date.fromisoformat(str(giorno or "")[:10]) - oggi).days
    except ValueError:
        return ""
    if delta < -1:
        return f"Da {-delta} giorni"
    if delta == -1:
        return "Da ieri"
    if delta == 0:
        return "Oggi"
    if delta == 1:
        return "Domani"
    return f"Tra {delta} giorni"


def ordina(voci: list[Voce], oggi: date) -> list[Voce]:
    ordine_fasce = list(FASCE)
    for voce in voci:
        if voce.fascia != "da_leggere":
            voce.fascia = fascia(voce.data, oggi)
    return sorted(voci, key=lambda v: (ordine_fasce.index(v.fascia), GRAVITA.index(v.gravita) if v.gravita in GRAVITA else 2,
                                       v.data or "9999", v.ora or "99:99", v.titolo))


__all__ = ["AREE", "FASCE", "GRAVITA", "Azione", "Voce", "fascia", "ordina", "quando_etichetta"]
