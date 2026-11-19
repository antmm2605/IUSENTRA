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
REGOLA_NOTE_ANTECEDENTI = "note-antecedenti:v1"
REGOLA_RUOLO_ALLEGATO = "ruolo-allegato-pec:v1"
REGOLA_IDENTITA_LIQUIDAZIONE = "identita-liquidazione:v1"

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


def oggetti_da_rileggere(
    fatti: Iterable[Any], versioni_lette: dict[tuple[str, str], str], *,
    buste_email: set[tuple[str, str]] | None = None,
) -> dict[tuple[str, str], str]:
    """Le fonti (tipo, oggetto) lette prima delle regole correnti e toccate da esse, con il motivo.

    ``versioni_lette`` dà la versione del motore con cui ogni fonte è stata letta: una fonte già letta
    con la regola pertinente non si rilegge. ``buste_email`` identifica le PEC dal riscontro
    di natura documentale già archiviato. Le decisioni dell'avvocato restano nel registro.
    """
    per_oggetto: dict[tuple[str, str], list[Any]] = {}
    for fatto in fatti:
        chiave = (str(getattr(fatto, "tipo", "") or ""), str(getattr(fatto, "oggetto_id", "") or ""))
        if chiave[0] in {"documento", "allegato_pec"}:
            per_oggetto.setdefault(chiave, []).append(fatto)
    esito: dict[tuple[str, str], str] = {}
    for chiave, elenco in per_oggetto.items():
        versione = versioni_lette.get(chiave)
        if versione is None:
            continue
        motivo = motivo_rilettura(elenco) if REGOLE_TERMINE_SCRITTO not in versione else ""
        if (not motivo and buste_email and chiave in buste_email and REGOLA_RUOLO_ALLEGATO not in versione
                and any(f.campo in _CAMPI and f.verifica in {"plausibile", "verificata"} for f in elenco)):
            motivo = "data giudiziale in una PEC: confrontare il ruolo nell’intestazione del singolo allegato"
        if not motivo and REGOLA_NOTE_ANTECEDENTI not in versione and any(
            f.categoria == "data" and f.campo == "termine"
            and any(prova.get("codice") == "istituto" and prova.get("dettaglio") == "note_127_ter" for prova in f.prove)
            for f in elenco
        ):
            motivo = "trattazione scritta: verificare se il decreto dispone il deposito prima della data d’udienza"
        if not motivo and REGOLA_IDENTITA_LIQUIDAZIONE not in versione and any(
            f.categoria == "importo" and f.campo == "liquidazione_giudice"
            and f.verifica in {"verificata", "corretta", "plausibile"} for f in elenco
        ):
            motivo = "liquidazione giudiziale: verificare se le fonti riproducono lo stesso dispositivo"
        if motivo:
            esito[chiave] = motivo
    return esito


__all__ = ["REGOLE_TERMINE_SCRITTO", "motivo_rilettura", "oggetti_da_rileggere"]
