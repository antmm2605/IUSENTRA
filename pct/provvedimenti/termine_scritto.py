"""Il termine scritto nel provvedimento: quale data è il termine, se è perentorio, che cosa rischia la parte.

Tre regole che valgono per ogni materia e che il motore delle letture, il presidio PEC e lo
scadenziario usano allo stesso modo.

1. **Il termine scritto dal giudice prevale sulla regola generica.** Quando il provvedimento
   «rinvia all'udienza del 21.12.2026 che sostituisce con il deposito di note scritte ex art. 127-ter
   c.p.c. entro il termine perentorio del 16.12.2026», il termine per le note è il 16/12/2026: è quello
   che il giudice assegna (art. 127-ter, primo comma: «il giudice assegna un termine perentorio … per
   il deposito delle note») e il suo giorno di scadenza «è considerato data di udienza a tutti gli
   effetti». La data dell'udienza sostituita resta l'udienza del ruolo, non il termine.
   Una data che il testo dice udienza «tenuta» o «non tenuta» è l'udienza in cui il provvedimento
   nasce o quella rinviata, mai il termine.

2. **Un termine dichiarato perentorio nel testo è perentorio.** Il giudice può stabilire termini a
   pena di decadenza solo se la legge lo permette (art. 152 c.p.c.) e quando lo fa lo scrive; i
   termini perentori non si abbreviano né si prorogano (art. 153 c.p.c.) e la decadenza si evita
   solo con la rimessione in termini per causa non imputabile. Per questo «termine perentorio del
   16.12.2026», «entro il 16.12.2026, termine perentorio» e «a pena di decadenza» fanno del termine
   un termine perentorio, qualunque sia la preposizione («del», «al», «sino al», «entro il»).

3. **La seconda diserzione estingue il processo.** Se nessuna parte compare (o nessuno deposita le
   note) il giudice fissa una nuova udienza; se nessuno compare neppure a quella, il processo si
   estingue: art. 631 c.p.c. nel processo esecutivo (salvo l'udienza di vendita), art. 181, primo
   comma, c.p.c. nel processo di cognizione, art. 127-ter, terzo comma, c.p.c. per le note scritte
   («se nessuna delle parti deposita le note nel nuovo termine o compare all'udienza, il giudice …
   dichiara l'estinzione del processo»). Un provvedimento che rinvia «poiché nessuno è presente» o
   «per mancata comparizione delle parti» apre quindi l'udienza (o il termine) da cui dipende la
   sopravvivenza del processo: va detto all'avvocato.

Testi verificati nell'archivio Normattiva del software (artt. 127-ter, 152, 153, 181, 630, 631 c.p.c.,
r.d. 1443/1940, testo vigente) il 10/11/2026.

Modulo puro: niente I/O.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_SPAZIO = r"[\s ]+"
#: «termine perentorio del», «termine perentorio sino al», «perentorio termine di giorni … al»,
#: «termine, perentorio, fino al», «entro il termine perentorio del»
_RE_PERENTORIO_PRIMA = re.compile(
    r"(?:termine\W{0,3}(?:\w+\W+){0,2}?perentori\w*|perentori\w*\W+termine)"
    r"(?:\W+\w+){0,6}?\W+(?:del|dal|al|sino\s+al|fino\s+al|entro\s+il|entro|di|il)\W*$",
    re.I,
)
#: «… entro il 16.12.2026, termine perentorio» / «… (termine perentorio)» / «a pena di decadenza»
_RE_PERENTORIO_DOPO = re.compile(r"^\W{0,4}(?:\(?\s*termine\s+)?perentori\w*|^\W{0,4}(?:\w+\W+){0,3}?a\s+pena\s+di\s+decadenza", re.I)
_RE_DECADENZA_PRIMA = re.compile(r"a\s+pena\s+di\s+decadenza(?:\W+\w+){0,8}?\W+(?:entro\s+il|entro|sino\s+al|fino\s+al|al|del)\W*$", re.I)
#: la data preceduta da «termine … del/al/sino al/entro il» o da «entro il»
_RE_TERMINE_PRIMA = re.compile(
    r"(?:\btermin\w*(?:\W+\w+){0,6}?\W+(?:del|al|sino\s+al|fino\s+al|entro\s+il|entro|il)"
    r"|\bentro\s+(?:e\s+non\s+oltre\s+)?(?:il|la\s+data\s+del)|\bnon\s+oltre\s+il)\W*$",
    re.I,
)
#: l'udienza nella quale il provvedimento è pronunciato o quella che non si tiene
_RE_UDIENZA_TENUTA_DOPO = re.compile(
    r"^\W{0,3}(?:\w+\W+){0,1}?(?:tenut[ao]|celebrat[ao]|svolt[ao]|non\s+sar[àa]\s+tenut|non\s+si\s+terr|è\s+revocat|revocat)",
    re.I,
)
#: l'udienza sostituita dalle note («che sostituisce con il deposito di note scritte», «sostituita dal deposito»)
_RE_UDIENZA_SOSTITUITA_DOPO = re.compile(
    r"^.{0,40}?(?:sostitu\w*|trattazione\s+scritta|note\s+scritte|127\W*ter)", re.I | re.S,
)
_RE_DISPOSIZIONE_SOSTITUTIVA = re.compile(
    r"^(?:(?:che\s+)?sostitui(?:sce|t[ao])|(?:è|e')\s+sostituit[ao])"
    r"\s+(?:con|dall?[oae]?)\s+(?:il\s+)?deposito\s+(?:di|delle)\s+"
    r"(?:(?:note|noet)\s+scritte|note\s+di\s+trattazione\s+scritta)\b",
    re.I,
)
_RE_NOTE_VICINE = re.compile(r"note|127\W*ter|trattazione\s+scritta", re.I)


def _prima(testo: str, inizio: int, ampiezza: int = 160) -> str:
    return " ".join(str(testo or "")[max(0, inizio - ampiezza):inizio].split())


def _dopo(testo: str, fine: int, ampiezza: int = 120) -> str:
    return " ".join(str(testo or "")[fine:fine + ampiezza].split())


def perentorio_dichiarato(testo: str, inizio: int, fine: int) -> bool:
    """Il testo dichiara perentorio proprio il termine che scade nella data fra ``inizio`` e ``fine``.

    L'attributo deve riguardare quella data (art. 152 c.p.c.: il termine giudiziario perentorio
    va dichiarato): «termine perentorio del 16.12.2026», «entro il 16.12.2026, termine perentorio»,
    «a pena di decadenza entro il …». Un'altra data citata nello stesso brano non lo eredita.
    """
    prima = _prima(testo, inizio)
    dopo = _dopo(testo, fine, 60)
    return bool(_RE_PERENTORIO_PRIMA.search(prima) or _RE_DECADENZA_PRIMA.search(prima) or _RE_PERENTORIO_DOPO.search(dopo))


def termine_assegnato(testo: str, inizio: int) -> bool:
    """La data è introdotta come scadenza di un termine («termine … del», «entro il», «non oltre il»)."""
    return bool(_RE_TERMINE_PRIMA.search(_prima(testo, inizio)))


def udienza_tenuta_o_rinviata(testo: str, fine: int) -> bool:
    """«All'udienza del 2.11.2026 tenuta dal G.E.», «l'udienza del 6.7.2026 non sarà tenuta»."""
    return bool(_RE_UDIENZA_TENUTA_DOPO.search(_dopo(testo, fine, 60)))


def data_udienza_sostituita_nel_brano(testo: str, data_letta: str) -> bool:
    """Il brano collega la data del rinvio alla sostituzione con le note."""
    if not data_letta or not re.fullmatch(r"[0-9./-]{5,12}", data_letta):
        return False
    prima = re.compile(r"\budienza\s+(?:del|in\s+data)\s*$", re.I)
    data = re.compile(r"(?<!\d)" + re.escape(data_letta) + r"(?!\d)")
    return any(
        prima.search(_prima(testo, m.start(), 60)) and _RE_DISPOSIZIONE_SOSTITUTIVA.search(_dopo(testo, m.end()).lstrip(" ,"))
        for m in data.finditer(testo)
    )


@dataclass(frozen=True, slots=True)
class DataLetta:
    """Una data del testo con il campo che le ha dato il lettore («udienza», «termine», …)."""

    inizio: int
    fine: int
    campo: str


def termine_note_127_ter(testo: str, date: list[DataLetta]) -> int | None:
    """L'indice della data che è il termine per le note scritte (art. 127-ter c.p.c.), o None.

    1. la data introdotta come termine («entro il termine perentorio del …») con le note, l'art.
       127-ter o la trattazione scritta nominati poco prima: è il termine che il giudice assegna;
    2. altrimenti l'udienza «che sostituisce con il deposito di note»/«sostituita»: il decreto che
       non scrive un termine distinto fissa le note sino a quella data;
    3. altrimenti, se resta una sola data che non sia l'udienza tenuta o rinviata, quella.
    Le udienze «tenute» o «non tenute» non sono mai il termine.
    """
    candidati = [i for i, d in enumerate(date) if d.campo in {"termine", "udienza", "costituzione"}]
    for i in candidati:
        d = date[i]
        if termine_assegnato(testo, d.inizio) and _RE_NOTE_VICINE.search(_prima(testo, d.inizio, 220)):
            return i
    for i in candidati:
        d = date[i]
        if d.campo == "udienza" and not udienza_tenuta_o_rinviata(testo, d.fine) and _RE_UDIENZA_SOSTITUITA_DOPO.search(_dopo(testo, d.fine, 80)):
            return i
    restanti = [i for i in candidati if not (date[i].campo == "udienza" and udienza_tenuta_o_rinviata(testo, date[i].fine))]
    return restanti[0] if len(restanti) == 1 else None


_RE_DISERZIONE = re.compile(
    r"nessun[oa]\s+(?:delle\s+parti\s+)?(?:è\s+)?(?:present|compar)\w*|poich[ée]\s+nessuno|"
    r"mancata\s+comparizione(?:\s+delle)?\s+parti|assenza\s+di\s+tutte\s+le\s+parti|"
    r"non\s+(?:è\s+)?comparsa?\s+alcuna\s+(?:delle\s+)?parti|nessuna\s+delle\s+parti\s+ha\s+depositato",
    re.I,
)
_RE_631 = re.compile(r"\b631\b", re.I)
_RE_ESECUZIONE = re.compile(r"\bG\.?\s*E\.?\b|giudice\s+dell['’]\s*esecuzione|\bR\.?\s*G\.?\s*E(?:s|\.)?\b|esecuzion\w+\s+(?:mobiliar|immobiliar|forzat|presso)|pignorament", re.I)
_RE_181 = re.compile(r"\b181\b|\b309\b", re.I)


@dataclass(frozen=True, slots=True)
class RischioEstinzione:
    """La seconda diserzione estingue il processo: che cosa dice la norma, in breve."""

    norma: str
    avviso: str
    breve: str


def rischio_estinzione(testo: str) -> RischioEstinzione | None:
    """Il provvedimento rinvia per diserzione delle parti: la prossima diserzione estingue il processo.

    Esecuzione (art. 631 c.p.c., anche quando la nuova udienza è sostituita da note scritte ex art.
    127-ter c.p.c.), cognizione (art. 181, primo comma, c.p.c.). None se il testo non dice che
    nessuna parte è comparsa o non richiama gli articoli.
    """
    testo = " ".join(str(testo or "").split())
    if not _RE_DISERZIONE.search(testo) and not (_RE_631.search(testo) and re.search(r"compariz", testo, re.I)):
        return None
    if _RE_631.search(testo) or _RE_ESECUZIONE.search(testo):
        return RischioEstinzione(
            "art. 631 c.p.c.",
            "Seconda udienza dopo la mancata comparizione di tutte le parti (art. 631 c.p.c.): se nessuna "
            "parte compare o, con la trattazione scritta, nessuna deposita le note nel termine (art. 127-ter "
            "c.p.c.), il giudice dichiara con ordinanza l'estinzione del processo esecutivo.",
            "art. 631 c.p.c.: senza deposito l'esecuzione si estingue",
        )
    if _RE_181.search(testo) or re.search(r"\bcausa\b|\bgiudizio\b", testo, re.I):
        return RischioEstinzione(
            "art. 181 c.p.c.",
            "Nuova udienza dopo la mancata comparizione di tutte le parti (art. 181, primo comma, c.p.c.): se "
            "nessuna parte compare (o nessuna deposita le note, art. 127-ter c.p.c.), la causa è cancellata "
            "dal ruolo e il processo si estingue.",
            "art. 181 c.p.c.: senza comparizione il processo si estingue",
        )
    return None


__all__ = [
    "DataLetta", "RischioEstinzione", "data_udienza_sostituita_nel_brano", "perentorio_dichiarato", "rischio_estinzione", "termine_assegnato",
    "termine_note_127_ter", "udienza_tenuta_o_rinviata",
]
