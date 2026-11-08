"""L'evento di cancelleria che fissa il termine per le note in sostituzione dell'udienza.

Caso reale (comunicazioni di cancelleria dei Tribunali di Palmi e Brescia, novembre 2026): il
registro di cancelleria (Comunicazione.xml) scrive «REVOCATA UDIENZA E FISSATO TERMINE PER NOTE
IN SOST. UDIENZA il 02/12/2026 09:30» oppure «FISSATO TERMINE PER NOTE IN SOSTITUZIONE UDIENZA il
20/05/2027 00:00». La data non è un'udienza da presenziare: è il **termine perentorio** per il
deposito delle note scritte assegnato dal giudice (art. 127-ter, comma 1, c.p.c., termine non
inferiore a quindici giorni), il cui giorno di scadenza vale come data di udienza. Dalla
comunicazione decorrono i **cinque giorni** per l'eventuale opposizione delle parti costituite
(art. 127-ter, comma 2, c.p.c.). L'ora del registro (09:30, 00:00) è quella dello slot d'udienza:
il deposito telematico è tempestivo entro la fine del giorno di scadenza (art. 196-sexies disp.
att. c.p.c.), salvo che il decreto inviti a depositare entro un'ora (``pct/note_127_ter/decreto``).

Testo verificato su Normattiva, art. 127-ter c.p.c. vigente (archivio del software aggiornato al
05/03/2026): https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:regio.decreto:1940-10-28;1443~art127ter

Il modulo è puro: niente I/O.
"""

from __future__ import annotations

import re
from typing import Any

#: «termine per note in sost. udienza», «note in sostituzione dell'udienza», «udienza … che sostituisce con
#: il deposito di note scritte». Un richiamo storico («già disposta la trattazione scritta ex art. 127-ter per
#: la precedente udienza») non basta: serve l'evento che sostituisce l'udienza con le note.
_RE_NOTE_IN_SOSTITUZIONE = re.compile(
    r"\bnote\b(?:\s+\w+){0,3}?\s+in\s+sost(?:\.|ituzione)?\s*(?:dell['’]\s*|di\s+)?udienz"
    r"|\bsostitu\w*\b.{0,40}\bdeposito\s+(?:di|delle)\s+\w{3,6}\s+scritte\b",
    re.I,
)
#: il giudice riassegna un nuovo termine perché le note non sono state depositate (art. 127-ter, comma 4):
#: non è il provvedimento che sostituisce l'udienza, quindi non riapre l'opposizione del comma 2
_RE_RIASSEGNAZIONE = re.compile(r"\briassegna\w*\b|\bnuovo\s+termine\b", re.I)
#: l'opposizione di una parte o il rigetto della trattazione scritta non fissano il termine per le note
_RE_NON_TERMINE = re.compile(r"\bopposizion\w*|\brigett\w*|\brevoca\w*\s+(?:della\s+)?trattazione\s+scritta", re.I)


def _testo_evento(profilo: dict[str, Any] | None) -> str:
    profilo = profilo if isinstance(profilo, dict) else {}
    return " ".join(
        " ".join(str(profilo.get(chiave) or "").split())
        for chiave in ("oggetto_evento", "descrizione_evento")
    ).strip()


def e_termine_note_127_ter(testo: str) -> bool:
    """Il testo dell'evento fissa (o riassegna) il termine per le note in sostituzione dell'udienza."""
    testo = str(testo or "")
    return bool(_RE_NOTE_IN_SOSTITUZIONE.search(testo)) and not _RE_NON_TERMINE.search(testo)


def evento_note_127_ter(profilo: dict[str, Any] | None) -> bool:
    """L'evento del registro (oggetto o descrizione) è il termine per le note ex art. 127-ter c.p.c."""
    return e_termine_note_127_ter(_testo_evento(profilo))


def apre_opposizione(profilo: dict[str, Any] | None) -> bool:
    """La comunicazione sostituisce l'udienza (non riassegna il termine): apre i 5 giorni del comma 2."""
    testo = _testo_evento(profilo)
    return e_termine_note_127_ter(testo) and not _RE_RIASSEGNAZIONE.search(testo)


CODICE_OPPOSIZIONE_127_TER = "CIV_OPPOSIZIONE_127_TER"
TITOLO_OPPOSIZIONE_127_TER = "Eventuale opposizione alla trattazione scritta (art. 127-ter, comma 2, c.p.c.)"


def proposta_opposizione(comunicata_il: Any, *, lavoro: bool, oggi: Any) -> Any | None:
    """La bozza dei cinque giorni per l'opposizione, dalla comunicazione (art. 127-ter, comma 2, c.p.c.).

    Calcolo del motore dei termini (modello ``CIV_OPPOSIZIONE_127_TER``): proroga al primo giorno non
    festivo (art. 155 c.p.c.) e sospensione feriale salvo lavoro e previdenza (art. 3 L. 742/1969).
    None se il termine è già decorso: un termine passato non si propone come scadenza.
    """
    from pct.provvedimenti.calcolo import calcola

    from .proposta import PropostaNote

    calcolo = calcola({"template": CODICE_OPPOSIZIONE_127_TER}, comunicata_il, materia="lavoro" if lavoro else "civile")
    if calcolo is None or calcolo.giorno < oggi:
        return None
    nota = (
        f"Comunicazione del {comunicata_il:%d/%m/%Y}: ciascuna parte costituita può opporsi alla sostituzione "
        "dell'udienza entro cinque giorni (art. 127-ter, comma 2, c.p.c.); il giudice provvede nei cinque giorni "
        f"successivi con decreto non impugnabile. Facoltativo: confermare solo se si intende opporsi. {calcolo.spiegazione}"
    ).strip()
    return PropostaNote(
        code=CODICE_OPPOSIZIONE_127_TER,
        title=TITOLO_OPPOSIZIONE_127_TER,
        due_date=calcolo.giorno.isoformat(),
        dies_a_quo=comunicata_il.isoformat(),
        norm="art. 127-ter, comma 2, c.p.c.",
        note=nota[:1200],
        perentorio=True,
        tipo_termine="DEPOSITO_ATTO",
    )


__all__ = [
    "CODICE_OPPOSIZIONE_127_TER", "TITOLO_OPPOSIZIONE_127_TER", "apre_opposizione", "e_termine_note_127_ter",
    "evento_note_127_ter", "proposta_opposizione",
]
