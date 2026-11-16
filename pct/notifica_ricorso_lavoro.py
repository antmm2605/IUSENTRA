"""Notifica del ricorso con il decreto di fissazione nel rito del lavoro: termini dell'art. 415 c.p.c.

Verifica sulle PEC reali del 31/10/2026: i decreti dei giudici del lavoro ordinano che «il ricorso con il
pedissequo decreto sia notificato a cura dell'istante alla controparte nei termini di legge», ma il software
non proponeva nessuna scadenza. Quando il giudice rinvia ai termini di legge, la fonte certa è la norma:

- art. 415, comma 4, c.p.c.: notifica entro dieci giorni dalla data di pronuncia del decreto (termine
  ordinatorio); la data di pronuncia è quella in calce al decreto («Vicenza, 24/07/2026»);
- art. 415, comma 5, c.p.c.: tra la notifica e l'udienza (o il termine per le note che la sostituisce,
  art. 127-ter c.p.c.) almeno trenta giorni, quaranta se la notifica va eseguita all'estero.

Le proposte sono bozze da confermare. Senza data di pronuncia leggibile non si propone il primo termine;
senza data dell'udienza non si propone il secondo: decide l'avvocato.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from pct.pec_change_receipt import date_it

from pct.pec_provvedimento_terms import TermProposal
from pct.termini_processuali import ItalianDeadlineCalculator

_ORDINE = re.compile(r"\b(?:ordina|dispone)\b[^.]{0,200}\bnotificat[oa]\b[^.]{0,200}\bnei\s+termini\s+di\s+legge\b", re.IGNORECASE)
_LAVORO = re.compile(r"\bgiudice\s+del\s+lavoro\b|\brito\s+del\s+lavoro\b|\bsezione\s+lavoro\b|\bart\.?\s*415\b", re.IGNORECASE)
_RICORSO_E_DECRETO = re.compile(r"\bricorso\b[^.]{0,80}\bdecreto\b", re.IGNORECASE)
_PRONUNCIA = re.compile(r"\b[A-ZÀ-Ü][a-zà-ù']+(?:\s+[A-ZÀ-Üa-zà-ù']+){0,2},\s*(?:lì\s*)?(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\s*\W{0,3}\s*(?:il\s+)?giudice", re.IGNORECASE)


def ordine_di_notifica_nei_termini_di_legge(testo: str) -> bool:
    """Il decreto del giudice del lavoro ordina di notificare ricorso e decreto «nei termini di legge»."""
    testo = " ".join(str(testo or "").split())
    return bool(_ORDINE.search(testo) and _LAVORO.search(testo) and _RICORSO_E_DECRETO.search(testo))


def data_di_pronuncia(testo: str) -> date | None:
    """La data in calce al decreto, prima della firma del giudice; solo se univoca."""
    trovate: set[date] = set()
    for trovata in _PRONUNCIA.finditer(" ".join(str(testo or "").split())):
        try:
            trovate.add(date(int(trovata.group(3)), int(trovata.group(2)), int(trovata.group(1))))
        except ValueError:
            continue
    return next(iter(trovate)) if len(trovate) == 1 else None


def proposte_art_415(testo: str, *, udienza: date | None, estero: bool | None = None) -> list[TermProposal]:
    """Le bozze dei termini di notifica dell'art. 415 c.p.c. ricavabili da fonti certe."""
    if not ordine_di_notifica_nei_termini_di_legge(testo):
        return []
    calcolatore = ItalianDeadlineCalculator()
    proposte: list[TermProposal] = []
    pronuncia = data_di_pronuncia(testo)
    if pronuncia is not None:
        esito = calcolatore.calculate(pronuncia, 10, direction="forward", matter_type="lavoro",
                                      reference_law="Art. 415, comma 4, c.p.c.")
        proposte.append(TermProposal(
            code="LAV_415_NOTIFICA_DIECI_GIORNI",
            title="Notifica di ricorso e decreto - entro 10 giorni dalla pronuncia",
            due_date=str(esito["deadline"]), dies_a_quo=pronuncia.isoformat(), norm="art. 415, comma 4, c.p.c.",
            note=(f"Il decreto del {pronuncia:%d/%m/%Y} ordina la notifica di ricorso e decreto nei termini di legge: "
                  "dieci giorni dalla pronuncia (termine ordinatorio)."),
            perentorio=False,
        ))
    if udienza is not None and estero is not None:
        giorni = 40 if estero else 30
        esito = calcolatore.calculate(udienza, giorni, direction="backward", matter_type="lavoro", free_term=True,
                                      reference_law="Art. 415, comma 5, c.p.c.")
        proposte.append(TermProposal(
            code="LAV_415_NOTIFICA_TRENTA_GIORNI",
            title=f"Notifica di ricorso e decreto - almeno {giorni} giorni prima dell'udienza",
            due_date=str(esito["deadline"]), dies_a_quo=udienza.isoformat(), norm="art. 415, comma 5, c.p.c.",
            note=(f"Tra la notifica e l'udienza (o il termine per le note che la sostituisce) del {udienza:%d/%m/%Y} "
                  f"devono intercorrere almeno {giorni} giorni: ultimo giorno utile, a giorni liberi."),
            perentorio=True,
        ))
    return proposte


_CODICI_NOTIFICA_415 = ("LAV_415_NOTIFICA_DIECI_GIORNI", "LAV_415_NOTIFICA_TRENTA_GIORNI")


def unifica_notifica_art_415(proposte: list[Any], *, oggi: str) -> list[Any]:
    """Riunisce i due vincoli già calcolati per il medesimo decreto e la stessa PEC."""
    vincoli = [voce for voce in proposte if voce.code in _CODICI_NOTIFICA_415]
    if len(vincoli) != 2 or {voce.code for voce in vincoli} != set(_CODICI_NOTIFICA_415):
        return proposte
    metadati = [dict(getattr(voce, "campi_scadenza", None) or {}) for voce in vincoli]
    if any(set(campi) - {"id_appuntamento"} for campi in metadati):
        return proposte
    appuntamenti = {campi["id_appuntamento"] for campi in metadati if campi.get("id_appuntamento")}
    if len(appuntamenti) > 1:
        return proposte
    vincoli.sort(key=lambda voce: (voce.due_date, not voce.perentorio))
    principale = next((voce for voce in vincoli if voce.due_date >= oggi), vincoli[0])
    spiegazioni = tuple(
        f"{'Termine ordinatorio dalla pronuncia' if voce.code == _CODICI_NOTIFICA_415[0] else 'Ultimo giorno utile prima dell’udienza'}"
        f": {date_it(voce.due_date)} ({voce.norm})"
        for voce in vincoli
    )
    unificata = TermProposal(
        code=principale.code, title="Notifica di ricorso e decreto",
        due_date=principale.due_date, dies_a_quo=principale.dies_a_quo,
        norm="art. 415, commi 4 e 5, c.p.c.",
        note=" ".join(voce.note for voce in vincoli), perentorio=principale.perentorio,
        altri_codici=tuple(voce.code for voce in vincoli if voce.code != principale.code),
        vincoli=spiegazioni,
        campi_scadenza={"id_appuntamento": appuntamenti.pop()} if appuntamenti else {},
    )
    return [*[voce for voce in proposte if voce.code not in _CODICI_NOTIFICA_415], unificata]


__all__ = ["data_di_pronuncia", "ordine_di_notifica_nei_termini_di_legge", "proposte_art_415", "unifica_notifica_art_415"]
