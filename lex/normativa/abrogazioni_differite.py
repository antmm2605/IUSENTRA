"""Articoli vigenti oggi e abrogati da una data futura (abrogazioni con efficacia differita), con la fonte.

Caso verificato su Normattiva il 21/11/2026 (testi vigenti al 21/11/2026): i testi unici tributari abrogano le norme
che riordinano «a decorrere dalla data» della loro decorrenza, e quella data è il 1° gennaio 2027:
- d.lgs. 14 novembre 2024, n. 175 (giustizia tributaria): abrogazioni art. 130, decorrenza art. 131, comma 1;
- d.lgs. 24 marzo 2025, n. 33 (versamenti e riscossione): abrogazioni artt. 239 e 241, decorrenza art. 243, comma 1;
- d.lgs. 1° agosto 2025, n. 123 (registro e altri tributi indiretti): abrogazioni art. 204, decorrenza art. 205, c. 1;
- d.lgs. 19 gennaio 2026, n. 10 (IVA): abrogazioni art. 170, decorrenza art. 171, comma 1.
Per i primi tre la data era il 1° gennaio 2026, rinviata al 1° gennaio 2027 dall'art. 4, commi 3, 4 e 5, del d.l.
31 dicembre 2025, n. 200, convertito, con modificazioni, dalla l. 27 febbraio 2026, n. 26.

Fino a quella data l'articolo è vigente e un termine che vi cade dopo va calcolato sapendo che la norma cambia: la
scheda dell'articolo lo dice («Vigente fino al 31/12/2026; dal 01/01/2027 …»), con la disposizione corrispondente
del testo unico quando il testo unico la indica nell'intestazione dei propri articoli.

L'indice ``dati/abrogazioni_differite.json`` si genera dagli Akoma Ntoso ufficiali con
``scripts/abrogazioni_differite_da_akn.py``; qui si legge soltanto.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from lex.normativa.commi import chiave

INDICE = Path(__file__).with_name("dati") / "abrogazioni_differite.json"
ROMA = ZoneInfo("Europe/Rome")


@lru_cache(maxsize=1)
def _indice(percorso: str = str(INDICE)) -> dict[str, Any]:
    try:
        return json.loads(Path(percorso).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"voci": {}, "atti_abroganti": {}}


def _it(iso: str) -> str:
    anno, mese, giorno = iso.split("-")
    return f"{giorno}/{mese}/{anno}"


def nota(data_atto: str, numero: str, articolo: str, *, oggi: date | None = None) -> dict[str, Any] | None:
    """La vigenza nel tempo dell'articolo, se un'abrogazione differita lo riguarda; altrimenti None."""
    indice = _indice()
    voci = indice.get("voci", {})
    # «*»: l'atto è abrogato per intero (anche gli articoli che non sono nell'elenco).
    voce = voci.get(chiave(data_atto, numero, articolo)) or voci.get(chiave(data_atto, numero, "*"))
    if not voce:
        return None
    abrogante = indice.get("atti_abroganti", {}).get(voce["abrogante"], {})
    dal = date.fromisoformat(voce["dal"])
    oggi = oggi or datetime.now(ROMA).date()
    fino_al = (dal - timedelta(days=1)).isoformat()
    parte = f" ({voce['parziale']})" if voce.get("parziale") else ""
    corrispondenti = voce.get("corrispondenti") or []
    sostituito = (f" e sostituito dall'{' e dall'.join(corrispondenti)} dello stesso testo unico" if corrispondenti else "")
    abrogazione = f"abrogato{parte} dall'{voce['articolo_abrogante']} del {abrogante.get('estremi', voce['abrogante'])}"
    if oggi < dal:
        testo = f"Vigente fino al {_it(fino_al)}; dal {_it(voce['dal'])} {abrogazione}{sostituito}."
        stato = "vigente_fino_al"
    else:
        testo = f"Abrogato{parte} dal {_it(voce['dal'])}, dall'{voce['articolo_abrogante']} del {abrogante.get('estremi', voce['abrogante'])}{sostituito}."
        stato = "abrogato"
    return {"stato": stato, "fino_al": fino_al, "dal": voce["dal"], "testo": testo,
            "parziale": voce.get("parziale", ""), "corrispondenti": corrispondenti,
            "decorrenza": abrogante.get("decorrenza", ""), "url": abrogante.get("url", ""),
            "verificato_il": indice.get("verificato_il", "")}


def nota_articolo(item: dict[str, Any], *, oggi: date | None = None) -> dict[str, Any] | None:
    """La nota per un articolo della biblioteca (``data_atto``/``numero`` o, in mancanza, l'URN dell'atto)."""
    import re

    data, numero = str(item.get("data_atto") or ""), str(item.get("numero") or "")
    if not (data and numero):
        trovato = re.search(r":(\d{4}-\d{2}-\d{2});(\d+)", str(item.get("urn") or ""))
        if not trovato:
            return None
        data, numero = trovato.groups()
    return nota(data, numero, str(item.get("number") or ""), oggi=oggi)


__all__ = ["INDICE", "nota", "nota_articolo"]
