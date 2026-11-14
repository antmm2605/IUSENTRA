"""Il motore delle letture applica le regole del termine scritto e dei provvedimenti collettivi.

Adattatore sottile: le regole stanno in ``pct/provvedimenti/termine_scritto`` (termine perentorio
dichiarato, artt. 152-153 c.p.c.) e ``pct/provvedimenti/collettivi`` (date disposte per altre cause);
qui diventano prove e verdetti dei fatti, prima che arrivino all'archivio.
"""

from __future__ import annotations

from typing import Iterable

from pct.provvedimenti.collettivi import clausole_di_altre_cause, fuori_dal_gruppo, motivo_altre_cause
from pct.provvedimenti.termine_scritto import perentorio_dichiarato
from pct.registro_letture.fatti_repository import Fatto

CAMPI_DISPOSTI = {"udienza", "termine", "costituzione"}
PROVA_PERENTORIO = "perentorieta_documentata"
PROVA_ALTRE_CAUSE = "provvedimento_collettivo"


def _fine(fatto: Fatto) -> int:
    return int(fatto.posizione or 0) + len(fatto.valore_letto or "")


def segna_perentori(fatti: Iterable[Fatto], testo: str) -> list[Fatto]:
    """Ogni termine che il testo dichiara perentorio porta la prova della perentorietà (art. 152 c.p.c.)."""
    elenco = list(fatti)
    for fatto in elenco:
        if fatto.categoria != "data" or fatto.campo != "termine" or not fatto.valore_letto:
            continue
        if any(p.get("codice") == PROVA_PERENTORIO for p in fatto.prove):
            continue
        if perentorio_dichiarato(testo, int(fatto.posizione or 0), _fine(fatto)):
            fatto.prove = list(fatto.prove) + [{"codice": PROVA_PERENTORIO, "esito": "ok",
                                                "dettaglio": "il provvedimento dichiara perentorio il termine (artt. 152-153 c.p.c.)"}]
    return elenco


def respingi_altre_cause(fatti: Iterable[Fatto], testo: str, numero_rg: str, anno_rg: str) -> list[Fatto]:
    """Le udienze e i termini disposti per altri gruppi di cause non sono fatti del fascicolo."""
    elenco = list(fatti)
    altre = clausole_di_altre_cause(testo, numero_rg, anno_rg) if numero_rg and anno_rg else []
    if not altre:
        return elenco
    for fatto in elenco:
        if fatto.categoria != "data" or fatto.campo not in CAMPI_DISPOSTI or fatto.verifica in {"corretta", "ignorata"}:
            continue
        gruppo = fuori_dal_gruppo(int(fatto.posizione or 0), altre)
        if gruppo is None:
            continue
        fatto.verifica = "respinta"
        fatto.prove = list(fatto.prove) + [{"codice": PROVA_ALTRE_CAUSE, "esito": "respinta", "dettaglio": motivo_altre_cause(gruppo)}]
    return elenco


__all__ = ["CAMPI_DISPOSTI", "PROVA_ALTRE_CAUSE", "PROVA_PERENTORIO", "respingi_altre_cause", "segna_perentori"]
