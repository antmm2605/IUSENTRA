"""I provvedimenti collettivi: un solo testo, più gruppi di cause, ognuno con la sua udienza.

Caso reale (Tribunale di Palmi, esecuzioni mobiliari, comunicazione del G.E. del 03/07/2026): «I
procedimenti recanti n. 340/24; 565/25; … 792/25; 319/26 sono rinviati all'udienza del 2.11.2026 che
sarà trattata in presenza. I procedimenti recanti n. 344/21; 83/25 + sub.1; … sono rinviati
all'udienza del 9.11.2026 che sostituisce con il deposito di note scritte ex art. 127 ter c.p.c.
entro il termine perentorio del 4.11.2026». Per la causa 792/2025 vale solo la prima frase: udienza
del 02/11/2026 **in presenza**; il termine del 04/11/2026 e la trattazione scritta riguardano le
altre cause. Attribuire al fascicolo il termine dell'altro gruppo mette in scadenziario un
adempimento che il giudice non gli ha imposto e gli toglie un'udienza da presenziare.

Regola: quando il testo elenca due o più gruppi di numeri di ruolo, ogni data, termine e modalità
si legge solo nella clausola del gruppo che contiene il ruolo del fascicolo. La clausola di un
gruppo va dall'elenco dei suoi numeri all'elenco del gruppo successivo (o alla fine del testo).
Se il ruolo del fascicolo non compare in alcun gruppo, il testo resta com'è: decidere a quale
gruppo appartiene la causa non spetta al lettore.

Base normativa: il provvedimento del giudice vale per la causa in cui è pronunciato (art. 175 c.p.c.,
direzione del procedimento; art. 484 c.p.c. per il giudice dell'esecuzione); i termini e le
modalità d'udienza (art. 127-ter c.p.c.) si applicano alle sole cause per cui sono disposti.

Modulo puro: niente I/O.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: un numero di ruolo abbreviato: «792/25», «n.792/2025», «807/25 + sub.1»
_RG = r"(?:n\.?\s*)?(\d{1,6})\s*/\s*(\d{4}|\d{2})(?!\d)(?:\s*\+\s*sub\.?\s*\d+)?"
_RE_RG = re.compile(_RG, re.I)
#: un elenco: almeno due numeri di ruolo separati da «;» o «,»
_RE_ELENCO = re.compile(_RG + r"(?:\s*[;,]\s*" + _RG + r")+", re.I)


@dataclass(frozen=True, slots=True)
class Gruppo:
    """Un gruppo di cause e la clausola del provvedimento che lo riguarda (posizioni nel testo)."""

    inizio: int
    fine: int
    ruoli: frozenset[tuple[int, int]]


def _anno(valore: str) -> int:
    anno = int(valore)
    if len(valore) == 2:
        return 2000 + anno if anno <= 69 else 1900 + anno
    return anno


def _ruoli(elenco: str) -> frozenset[tuple[int, int]]:
    return frozenset((int(m.group(1)), _anno(m.group(2))) for m in _RE_RG.finditer(elenco))


def gruppi_di_cause(testo: str) -> list[Gruppo]:
    """I gruppi di cause del provvedimento collettivo; lista vuota se il testo non ne elenca almeno due."""
    testo = str(testo or "")
    elenchi = list(_RE_ELENCO.finditer(testo))
    if len(elenchi) < 2:
        return []
    gruppi: list[Gruppo] = []
    for indice, elenco in enumerate(elenchi):
        fine = elenchi[indice + 1].start() if indice + 1 < len(elenchi) else len(testo)
        if indice + 1 < len(elenchi):
            # la clausola successiva comincia con la frase che introduce il suo elenco
            # («I procedimenti recanti n. …»): si torna all'ultimo punto fermo.
            punto = max(testo.rfind(". ", elenco.end(), fine), testo.rfind(".\n", elenco.end(), fine))
            if punto > elenco.end():
                fine = punto + 1
        gruppi.append(Gruppo(elenco.start(), fine, _ruoli(elenco.group(0))))
    return gruppi


def ruolo_del_fascicolo(numero: str | int, anno: str | int) -> tuple[int, int] | None:
    try:
        numero_int, anno_int = int(str(numero).strip()), _anno(str(anno).strip())
    except (TypeError, ValueError):
        return None
    return (numero_int, anno_int) if numero_int and anno_int else None


def clausole_di_altre_cause(testo: str, numero: str | int, anno: str | int) -> list[Gruppo]:
    """Le clausole dei gruppi che non contengono il ruolo del fascicolo.

    Lista vuota se il testo non è collettivo o se il ruolo non compare in esattamente un gruppo.
    """
    ruolo = ruolo_del_fascicolo(numero, anno)
    gruppi = gruppi_di_cause(testo)
    if ruolo is None or not gruppi:
        return []
    propri = [g for g in gruppi if ruolo in g.ruoli]
    if len(propri) != 1:
        return []
    return [g for g in gruppi if g is not propri[0]]


def fuori_dal_gruppo(posizione: int, altre: list[Gruppo]) -> Gruppo | None:
    """Il gruppo di altre cause nella cui clausola cade la posizione, se c'è."""
    return next((g for g in altre if g.inizio <= posizione < g.fine), None)


def testo_per_il_ruolo(testo: str, numero: str | int, anno: str | int) -> str:
    """Il testo con le clausole delle altre cause oscurate da spazi (le posizioni restano le stesse).

    Così le regole a valle (modalità d'udienza, art. 127-ter, termini) leggono solo ciò che il
    provvedimento dispone per la causa del fascicolo.
    """
    testo = str(testo or "")
    altre = clausole_di_altre_cause(testo, numero, anno)
    if not altre:
        return testo
    caratteri = list(testo)
    for gruppo in altre:
        for indice in range(gruppo.inizio, min(gruppo.fine, len(caratteri))):
            if caratteri[indice] not in "\n":
                caratteri[indice] = " "
    return "".join(caratteri)


def allegati_per_il_ruolo(allegati: list[dict], numero_rg: str) -> list[dict]:
    """Gli allegati di una PEC con il testo letto per il ruolo del fascicolo («792/2025»).

    Copie dei soli allegati che cambiano: la busta e i file restano quelli ricevuti; il presidio PEC
    (modalità d'udienza, art. 127-ter, opposizione) vede solo la clausola della causa.
    """
    trovato = _RE_RG.fullmatch(str(numero_rg or "").strip().split("/EC")[0].strip())
    if not trovato:
        return list(allegati)
    numero, anno = trovato.group(1), trovato.group(2)
    esito = []
    for allegato in allegati:
        if isinstance(allegato, dict):
            for chiave in ("ocr_text", "text"):
                testo = allegato.get(chiave)
                if isinstance(testo, str) and testo:
                    ridotto = testo_per_il_ruolo(testo, numero, anno)
                    if ridotto != testo:
                        allegato = {**allegato, chiave: ridotto}
        esito.append(allegato)
    return esito


def motivo_altre_cause(gruppo: Gruppo) -> str:
    ruoli = ", ".join(f"{n}/{a}" for n, a in sorted(gruppo.ruoli)[:6]) + ("…" if len(gruppo.ruoli) > 6 else "")
    return (
        "Provvedimento collettivo: la data è disposta per un altro gruppo di cause (" + ruoli + "), "
        "non per il ruolo del fascicolo."
    )


__all__ = [
    "Gruppo", "allegati_per_il_ruolo", "clausole_di_altre_cause", "fuori_dal_gruppo", "gruppi_di_cause", "motivo_altre_cause",
    "ruolo_del_fascicolo", "testo_per_il_ruolo",
]
