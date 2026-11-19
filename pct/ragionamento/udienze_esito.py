"""L'esito di un'udienza trascorsa, quando è già scritto in un provvedimento del giudice della causa.

Il passo «Registrare l'esito dell'udienza» serve finché l'esito non si conosce. Se il fascicolo contiene il
provvedimento che lo dà, l'esito è certo e non si chiede all'avvocato di cercarlo:

- il verbale o il provvedimento pronunciato nello stesso giorno dell'udienza (art. 126 c.p.c., processo verbale);
- il provvedimento successivo che richiama la data di quell'udienza («all'udienza del 03/11/2026 …»);
- per l'udienza sostituita dalle note scritte, il provvedimento pronunciato dopo la scadenza ed entro trenta giorni:
  «il giudice provvede entro trenta giorni» dalla scadenza del termine per le note (art. 127-ter, terzo comma, c.p.c.).

Modulo puro: legge solo gli atti del modello.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Iterable

from .modello import Atto, Fonte, Udienza
from .testo import data_it, date_nel_testo, giorno, pulito

GIORNI_PROVVEDIMENTO_NOTE = 30
_NON_DEFINITIVA = re.compile(r"\b(?:non\s+definitivament[eo]|sentenza\s+non\s+definitiva)\b", re.I)


def esito_udienza(data_udienza: date, atti: Iterable[Atto], udienze: Iterable[Udienza]) -> Fonte | None:
    """Il provvedimento del giudice che dà l'esito dell'udienza del giorno indicato, o None."""
    note_scritte = any(giorno(u.data) == data_udienza and u.modalita == "note_scritte" for u in udienze)
    candidati = sorted((a for a in atti if a.autore == "giudice" and a.appartenenza == "causa" and a.testo
                        and (d := giorno(a.data)) and d >= data_udienza), key=lambda a: a.data)
    for atto in candidati:
        pronuncia = giorno(atto.data)
        if atto.sentenza and not _NON_DEFINITIVA.search(atto.testo):
            # La causa è stata decisa dopo l'udienza: l'esito dell'udienza precedente non ha più effetti da registrare.
            return Fonte(atto.id, atto.nome, f"causa decisa con sentenza del {data_it(pronuncia)}", atto.data)
        if pronuncia == data_udienza:
            return Fonte(atto.id, atto.nome, f"provvedimento pronunciato il giorno dell'udienza ({data_it(pronuncia)})", atto.data)
        citata = next((pulito(atto.testo[max(0, i - 80):f + 80]) for i, f, d in date_nel_testo(atto.testo) if d == data_udienza), "")
        if citata:
            return Fonte(atto.id, atto.nome, citata, atto.data)
        if note_scritte and pronuncia <= data_udienza + timedelta(days=GIORNI_PROVVEDIMENTO_NOTE):
            return Fonte(atto.id, atto.nome, f"provvedimento sulle note scritte del {data_it(data_udienza)}, pronunciato il "
                                             f"{data_it(pronuncia)} (art. 127-ter, terzo comma, c.p.c.)", atto.data)
    return None


def esiti_udienze(date_udienze: Iterable[str], atti: list[Atto], udienze: list[Udienza], oggi: date) -> list[dict[str, str]]:
    """Per ogni udienza trascorsa il provvedimento che ne dà l'esito: data ISO, documento, brano."""
    esiti = []
    for valore in sorted(set(date_udienze)):
        data = giorno(valore)
        if not data or data >= oggi:
            continue
        fonte = esito_udienza(data, atti, udienze)
        if fonte:
            esiti.append({"data": data.isoformat(), "oggetto_id": fonte.oggetto_id, "nome": fonte.nome, "brano": fonte.brano,
                          "data_provvedimento": fonte.data})
    return esiti


__all__ = ["esito_udienza", "esiti_udienze"]
