"""Regole pure di coerenza dei termini letti nei provvedimenti: chi è onerato, da quale udienza, che cosa fare.

Funzioni senza stato e senza scritture, riusabili dal motore del ragionamento processuale e dalla
riconvalida delle proposte automatiche già create. Ogni regola cita la norma vigente (testo
riscontrato nell'archivio Normattiva del software il 10/11/2026).

1. **Parte onerata** (``parte_onerata``). Un termine che il provvedimento pone a carico di una parte
   determinata è un adempimento dello studio solo se il cliente ha quel ruolo. La costituzione del
   convenuto (art. 416, comma 1, c.p.c.: «Il convenuto deve costituirsi almeno dieci giorni prima della
   udienza») è onere della controparte quando lo studio difende il ricorrente: non va in scadenziario
   come termine dello studio.

2. **Decadenze dell'art. 416 solo alla prima udienza** (``motivo_416_su_rinvio``). L'art. 416 collega
   costituzione e decadenze (domande riconvenzionali, eccezioni non rilevabili d'ufficio, mezzi di prova:
   commi 2 e 3) all'udienza fissata con il decreto dell'art. 415; l'art. 420 regola quella prima udienza.
   Un rinvio successivo, anche istruttorio (art. 421 c.p.c., poteri istruttori del giudice), non riapre
   quei termini: contare «dieci giorni prima» dall'udienza di rinvio produce un termine che la legge non
   prevede.

3. **Che cosa depositare** (``oggetto_del_deposito``, ``titolo_deposito``). Il termine che il giudice
   assegna per depositare (art. 421, comma 1, c.p.c. nel rito del lavoro; art. 175 c.p.c. negli altri
   riti) deve dire nel titolo che cosa si deposita, con le parole del provvedimento: «deposito
   (ricorrente)» non dice all'avvocato quale atto o documento preparare.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from .parte_assistita import ATTIVO, PASSIVO, spetta_al_cliente

STUDIO = "studio"
CONTROPARTE = "controparte"
COMUNE = "comune"
INCERTA = "incerta"

_CHI_COMUNI = frozenset({"", "parti", "parti costituite", "entrambe le parti", "tutte le parti"})
_CHI_UFFICIO = frozenset({"giudice", "cancelleria", "consulente", "ctu", "ufficio"})


def parte_onerata(chi: Any, ruolo_cliente: str) -> str:
    """Di chi è il termine rispetto allo studio: ``studio``, ``controparte``, ``comune`` o ``incerta``.

    ``chi`` è la parte a cui il provvedimento o la regola di legge pone il termine («ricorrente»,
    «convenuto», «parti»...); ``ruolo_cliente`` è ``ricorrente``/``resistente`` o "" se non certo.
    Senza ruolo certo la parte resta ``incerta`` (il chiamante decide se proporre in bozza).
    """
    soggetto = " ".join(str(chi or "").lower().split())
    if soggetto in _CHI_COMUNI:
        return COMUNE
    if soggetto in _CHI_UFFICIO:
        return COMUNE
    if ruolo_cliente not in {ATTIVO, PASSIVO}:
        return INCERTA
    return STUDIO if spetta_al_cliente(soggetto, ruolo_cliente) else CONTROPARTE


_CODICI_416 = frozenset({"LAV_416_COSTITUZIONE"})


def motivo_416_su_rinvio(codice: str, *, udienza_di_calcolo: date | None, udienza_del_decreto: date | None) -> str:
    """Perché un termine dell'art. 416 contato da un'udienza diversa da quella del decreto 415 non vale.

    Stringa vuota se il termine è coerente (stessa udienza, o dati insufficienti per dirlo).
    """
    if codice not in _CODICI_416 or udienza_di_calcolo is None or udienza_del_decreto is None:
        return ""
    if udienza_di_calcolo == udienza_del_decreto:
        return ""
    return (
        f"Il termine di costituzione dell'art. 416 c.p.c. si conta dall'udienza fissata con il decreto ex art. 415 "
        f"({udienza_del_decreto:%d/%m/%Y}), non dall'udienza del {udienza_di_calcolo:%d/%m/%Y}: le decadenze dell'art. 416 "
        "maturano alla prima udienza e il rinvio (anche istruttorio, art. 421 c.p.c.) non le riapre."
    )


# «per depositare …», «a depositare …», «di produrre …», «il deposito di …» fino alla fine della frase.
_RE_OGGETTO_DEPOSITO = re.compile(
    r"\b(?:per|a|di|ad)\s+(?:depositare|produrre|(?:il\s+|al\s+)?deposito\s+(?:di|del(?:la|le|l'|gli|i)?)|(?:la\s+|alla\s+)?produzione\s+(?:di|del(?:la|le|l'|gli|i)?))\s+"
    r"(?P<oggetto>[^.;:\n]{4,400})",
    re.I,
)
_RE_CODA = re.compile(
    r"\s*(?:,\s*)?(?:entro|nel\s+termine|sino|fino|a\s+pena|rinvia|e\s+rinvia|con\s+avvertimento|in\s+cancelleria|"
    r"in\s+via\s+telematica|telematicamente)\b.*$",
    re.I | re.S,
)


_RE_RELATIVA = re.compile(r"\s+(?:nell[ae]\s+qual[ei]|nei\s+quali|negli\s+quali|in\s+cui|dal(?:la|le)?\s+qual[ei]|che\s+(?:attest|dimostr|provi|risult))[^,;]*?(?=\s+(?:o|e|oppure|ovvero)\s+|,|$)", re.I)


def oggetto_del_deposito(testo_capo: str, *, massimo: int = 110) -> str:
    """Ciò che il giudice ordina di depositare, con le parole del capo; "" se il capo non lo dice.

    Se le parole sono troppe per un titolo si tolgono prima le relative che specificano il documento
    («nelle quali risulti il proprio nominativo»), poi si tronca alla parola: l'oggetto resta riconoscibile.
    """
    trovato = _RE_OGGETTO_DEPOSITO.search(" ".join(str(testo_capo or "").split()))
    if not trovato:
        return ""
    oggetto = _RE_CODA.sub("", trovato.group("oggetto")).strip(" ,")
    if len(oggetto) < 4:
        return ""
    if len(oggetto) > massimo:
        oggetto = _RE_RELATIVA.sub("", oggetto).strip(" ,")
    if len(oggetto) > massimo:
        taglio = oggetto[:massimo].rsplit(" ", 1)[0]
        oggetto = taglio.rstrip(" ,") + "…"
    return oggetto


def titolo_deposito(testo_capo: str, chi: str = "") -> str:
    """«Depositare le graduatorie aggiornate … (ricorrente) — termine del giudice», o "" se ignoto."""
    oggetto = oggetto_del_deposito(testo_capo)
    if not oggetto:
        return ""
    parte = f" ({chi})" if chi else ""
    return f"Depositare {oggetto}{parte} — termine del giudice"


__all__ = [
    "COMUNE", "CONTROPARTE", "INCERTA", "STUDIO", "motivo_416_su_rinvio", "oggetto_del_deposito",
    "parte_onerata", "titolo_deposito",
]
