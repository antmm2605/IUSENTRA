"""Riletture mirate: le fonti già lette che una regola nuova leggerebbe diversamente.

Il rilascio non riavvia una rilettura generale (``VERSIONI_MOTORE_DOCUMENTI_COMPATIBILI``). Quando però
una regola corregge un errore giuridico, i fatti già registrati con la regola vecchia continuano ad
alimentare scadenziario e agenda: il termine per le note ex art. 127-ter c.p.c. sul giorno dell'udienza
sostituita, il termine di un'altra causa preso da un provvedimento collettivo. Qui si individuano,
dai soli fatti già in archivio (brani salvati, nessun file aperto), le fonti che la regola nuova
riguarda: si rileggono una volta, dal testo già salvato, con la versione corrente del motore.

Regole e norme:
* ``termine-scritto`` — il termine per le note è quello assegnato dal giudice (art. 127-ter, primo
  comma, c.p.c.), perentorio per legge; la seconda diserzione estingue (artt. 181, 631 c.p.c.);
* ``collettivi`` — il provvedimento che elenca più gruppi di cause vale, per ogni data, solo per il
  gruppo che contiene il ruolo del fascicolo (art. 175 c.p.c.; art. 484 c.p.c.).

Modulo puro: riceve i fatti e le versioni delle letture, restituisce gli oggetti da rileggere.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

#: il segno che la lettura è stata fatta con le regole di questo modulo
REGOLE_TERMINE_SCRITTO = "termine-scritto:v1"

_RE_127_TER = re.compile(r"127\W{0,3}ter|trattazione\s+scritta|note\s+(?:scritte|in\s+sost)", re.I)
_RE_ELENCO_RUOLI = re.compile(r"\d{1,6}\s*/\s*\d{2,4}(?:\s*\+\s*sub\.?\s*\d+)?\s*[;,]\s*(?:n\.?\s*)?\d{1,6}\s*/\s*\d{2,4}", re.I)
_CAMPI = {"udienza", "termine", "costituzione"}


def motivo_rilettura(fatti_oggetto: Iterable[Any]) -> str:
    """Perché i fatti di una fonte vanno riletti con le regole correnti; stringa vuota se non serve."""
    date = [f for f in fatti_oggetto if getattr(f, "categoria", "") == "data" and getattr(f, "campo", "") in _CAMPI]
    if not date:
        return ""
    contesti = " | ".join(str(getattr(f, "contesto", "") or "") for f in date)
    if _RE_ELENCO_RUOLI.search(contesti):
        return "provvedimento che elenca più cause: le date si leggono per il ruolo del fascicolo"
    if _RE_127_TER.search(contesti) and len({str(getattr(f, "valore", ""))[:10] for f in date}) >= 2:
        return "trattazione scritta: il termine per le note è quello assegnato dal giudice (art. 127-ter c.p.c.)"
    return ""


def oggetti_da_rileggere(fatti: Iterable[Any], versioni_lette: dict[tuple[str, str], str]) -> dict[tuple[str, str], str]:
    """Le fonti (tipo, oggetto) lette prima delle regole correnti e toccate da esse, con il motivo.

    ``versioni_lette`` dà la versione del motore con cui ogni fonte è stata letta: una fonte già letta
    con ``REGOLE_TERMINE_SCRITTO`` non si rilegge (una volta sola, mai a ogni giro). Le decisioni
    dell'avvocato non entrano qui: la rilettura le conserva (``registra_fatti``).
    """
    per_oggetto: dict[tuple[str, str], list[Any]] = {}
    for fatto in fatti:
        chiave = (str(getattr(fatto, "tipo", "") or ""), str(getattr(fatto, "oggetto_id", "") or ""))
        if chiave[0] in {"documento", "allegato_pec"}:
            per_oggetto.setdefault(chiave, []).append(fatto)
    esito: dict[tuple[str, str], str] = {}
    for chiave, elenco in per_oggetto.items():
        versione = versioni_lette.get(chiave)
        if versione is None or REGOLE_TERMINE_SCRITTO in versione:
            continue
        motivo = motivo_rilettura(elenco)
        if motivo:
            esito[chiave] = motivo
    return esito


__all__ = ["REGOLE_TERMINE_SCRITTO", "motivo_rilettura", "oggetti_da_rileggere"]
