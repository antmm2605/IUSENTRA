"""Rilettura del testo del provvedimento quando due fonti del software danno date diverse per lo stesso termine.

Regola dello studio (certezza): si decide sul testo. Il lettore è quello del modello della causa
(``pct.ragionamento.provvedimenti.leggi_provvedimento``) con il computo unico dei termini (``regole.calcolo``):
termini a ritroso dello studio a giorni liberi (decisione dell'avvocato del 29/10/2026), della controparte a giorni
pieni. Il testo è ambiguo se per lo stesso adempimento porta più date o nessuna: solo allora il guardiano registra
la data anteriore, con l'avviso «due date».

Modulo puro.
"""

from __future__ import annotations

from datetime import date

from pct.ragionamento.modello import Atto, Rito
from pct.ragionamento.provvedimenti import leggi_provvedimento
from pct.ragionamento.regole.calcolo import a_ritroso


# La parola con cui il lettore scrive l'adempimento (TermineAssegnato.adempimento) per ogni codice delle conclusioni.
_PAROLA = {"note_127ter": "note", "costituzione_convenuto": "costitu", "notifica_ordinata": "notific",
           "notifica_ricorso_decreto_415": "notific", "deposito_ordinato": "deposit"}


def date_dal_testo(testo: str, *, rg: str, data_atto: str, codice: str, rito_lavoro: bool, oggi: date,
                   dello_studio: bool = True) -> list[str]:
    """Le date (ISO, ordinate, senza doppioni) che il testo assegna all'adempimento ``codice``."""
    atto = Atto("rilettura", "provvedimento", "provvedimento", "Provvedimento", autore="giudice", data=data_atto,
                testo=testo or "")
    rito = Rito("lavoro" if rito_lavoro else "cognizione", "", "rilettura", sospensione_feriale=not rito_lavoro)
    date_lette: set[str] = set()
    for termine in leggi_provvedimento(atto, rg).termini:
        if _PAROLA.get(codice, codice) not in termine.adempimento.lower():
            continue
        if termine.formula.startswith("a_ritroso:"):
            _f, giorni, base = termine.formula.split(":")
            calcolato = a_ritroso(date.fromisoformat(base), int(giorni), rito=rito, oggi=oggi, perentorio=termine.perentorio,
                                  evento="udienza", norma="art. 155 c.p.c.", prudenziale=dello_studio)
            if calcolato.scadenza:
                date_lette.add(calcolato.scadenza)
        elif termine.scadenza:
            date_lette.add(termine.scadenza)
    return sorted(date_lette)


__all__ = ["date_dal_testo"]
