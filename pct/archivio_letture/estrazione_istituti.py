"""Dalla data all'istituto: che cosa impone davvero quel provvedimento.

`estrazione_date` trova una data e la dice ancorata: «termine del 10/09/2026».
Qui quella data viene **qualificata** — deposito di note scritte ex art.
127-ter c.p.c. — e da quella qualificazione nascono i termini che il decreto
impone senza scriverne la data: la notifica trenta giorni prima, la
costituzione dieci giorni prima.

Perché nei motori e non nei presìdi: la qualificazione si legge una volta
sola, insieme alla data, e finisce nell'archivio con la sua norma. Un presidio
che la ricavasse da sé riaprirebbe il testo a ogni richiesta dell'avvocato, e
due presìdi potrebbero qualificare lo stesso decreto in due modi diversi.

I termini derivati non sono di legge in astratto: sono quelli che **il singolo
decreto** impone. Un decreto che non parla della notifica non fa nascere un
termine di notifica, e inventarlo metterebbe in scadenziario una data che
nessun giudice ha imposto.
"""

from __future__ import annotations

from datetime import date
from typing import Iterable

from pct.registro_letture.fatti_repository import Fatto

from .istituti_processuali import (
    NOTE_127_TER,
    UDIENZA_127_BIS,
    Istituto,
    cita_127_bis,
    cita_127_ter,
    derivati_da_note,
    derivati_da_udienza_remota,
)

VERSIONE_ESTRAZIONE_ISTITUTI = "2026.09.18.istituti.v1"

#: i campi che possono portare la data di partenza di un istituto
_CAMPI_ANCORA = {"termine", "udienza", "costituzione"}


def _giorno(valore: str) -> date | None:
    from pct.registro_letture.verifica_date import interpreta_data

    return interpreta_data(str(valore or "").split("T")[0])


def _prova_istituto(istituto: Istituto) -> dict[str, str]:
    return {"codice": "istituto", "esito": "ok", "dettaglio": istituto.codice}


def _prova_norma(istituto: Istituto) -> dict[str, str]:
    return {"codice": "norma", "esito": "ok", "dettaglio": istituto.norma}


def _qualifica(fatto: Fatto, istituto: Istituto, giorno: date) -> Fatto:
    """La data letta, con il nome del suo istituto e la norma che lo governa."""
    fatto.campo = istituto.campo
    fatto.etichetta = istituto.etichetta(giorno)
    fatto.contesto = fatto.contesto or istituto.descrizione
    fatto.prove = [p for p in fatto.prove if p.get("codice") not in {"istituto", "norma"}]
    fatto.prove += [_prova_istituto(istituto), _prova_norma(istituto)]
    return fatto


def _derivato(istituto: Istituto, giorno: date, *, origine: str, posizione: int, verifica: str) -> Fatto:
    """Un termine che il decreto impone contandolo dalla data principale."""
    return Fatto(
        categoria="data", campo=istituto.campo, valore=giorno.isoformat(),
        valore_letto="", etichetta=istituto.etichetta(giorno),
        contesto=istituto.descrizione, posizione=posizione, origine=origine,
        confidenza=0.9, verifica=verifica,
        prove=[
            _prova_istituto(istituto), _prova_norma(istituto),
            {"codice": "calcolo", "esito": "ok",
             "dettaglio": f"termine contato dal provvedimento a partire dal {giorno.strftime('%d/%m/%Y')}"},
        ],
    )


def qualifica_istituti(fatti: Iterable[Fatto], testo: str, *, origine: str = "") -> list[Fatto]:
    """I fatti con la data qualificata e i termini che ne discendono.

    Se il testo non cita nessuno degli istituti, i fatti tornano come sono: la
    qualificazione non si inventa.
    """
    elenco = list(fatti)
    testo = str(testo or "")
    per_127_ter = cita_127_ter(testo)
    per_127_bis = cita_127_bis(testo)
    if not per_127_ter and not per_127_bis:
        return elenco

    istituto = NOTE_127_TER if per_127_ter else UDIENZA_127_BIS
    ancora = next(
        (f for f in elenco
         if f.categoria == "data" and f.campo in _CAMPI_ANCORA and _giorno(f.valore) is not None),
        None,
    )
    if ancora is None:
        return elenco
    giorno = _giorno(ancora.valore)
    if giorno is None:  # pragma: no cover - gia' filtrato sopra
        return elenco

    _qualifica(ancora, istituto, giorno)
    derivati = derivati_da_note(testo, giorno) if per_127_ter else derivati_da_udienza_remota(testo, giorno)
    posizione = ancora.posizione
    for voce, quando in derivati:
        posizione += 1
        elenco.append(_derivato(voce, quando, origine=origine or ancora.origine,
                                posizione=posizione, verifica=ancora.verifica))
    return elenco


__all__ = ["VERSIONE_ESTRAZIONE_ISTITUTI", "qualifica_istituti"]
