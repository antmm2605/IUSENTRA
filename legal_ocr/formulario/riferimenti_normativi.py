"""I riferimenti normativi non sono date: «l. 69/2023» è la legge 69 del 2023.

Negli atti la citazione di una norma ha la forma «abbreviazione + numero /
anno»: «l. 69/2023», «D.Lgs. 149/2022», «art. 5/2026», «n. 12/2026». Un
lettore che cerca date ci vede tre pezzi separati da una barra e, peggio,
scambia la «l» di «legge» per un 1: «l. 5/2026» diventerebbe il 1° maggio
2026 e finirebbe nello scadenziario come termine. Qui l'eccezione è
dichiarata una volta per tutte: dentro un riferimento normativo il formulario
non corregge nulla e il lettore non trova date.

L'elenco delle abbreviazioni segue l'uso forense e le fonti citate dal
gestionale: leggi e decreti (L., D.Lgs., D.L., D.P.R., D.M., D.P.C.M., R.D.,
D.P.C.S.G.A.), articoli e commi (art., artt., comma, co., lett.), numerazioni
(n., nn., num.), provvedimenti citati (sent., ord., decr., Cass., Sez.),
numeri di ruolo (R.G., R.G.N.R., N.R.G., proc.), fonti europee (Reg. UE, Dir.)
e le numerazioni d'ufficio che non sono date (prot., fattura, versione).
"""

from __future__ import annotations

import re

# Quanto testo si guarda prima del token per riconoscere l'abbreviazione.
FINESTRA_PRIMA = 30

# (chiave, espressione dell'abbreviazione, che cosa cita)
ABBREVIAZIONI: tuple[tuple[str, str, str], ...] = (
    ("legge", r"l(?:egge)?", "legge dello Stato"),
    ("decreto_legislativo", r"d\.?\s*lgs\.?|decreto\s+legislativo", "decreto legislativo"),
    ("decreto_legge", r"d\.?\s*l\.?|decreto[\s-]legge", "decreto legge"),
    ("dpr", r"d\.?\s*p\.?\s*r\.?", "decreto del Presidente della Repubblica"),
    ("dm", r"d\.?\s*m\.?|decreto\s+ministeriale", "decreto ministeriale"),
    ("dpcm", r"d\.?\s*p\.?\s*c\.?\s*m\.?", "decreto del Presidente del Consiglio dei ministri"),
    ("dpcsga", r"d\.?\s*p\.?\s*c\.?\s*s\.?\s*g\.?\s*a\.?", "decreto del Presidente del Consiglio di Stato"),
    ("regio_decreto", r"r\.?\s*d\.?", "regio decreto"),
    ("articolo", r"artt?\.?|articol[oi]", "articolo di legge"),
    ("comma", r"co\.?|comma|commi", "comma"),
    ("lettera", r"lett\.?", "lettera del comma"),
    ("numero", r"nn?\.?|num\.?|numero", "numerazione dell'atto o della norma"),
    ("provvedimento", r"sent\.?|sentenza|ord\.?|ordinanza|decr\.?|provv\.?", "provvedimento citato"),
    ("cassazione", r"cass\.?|sez\.?\s*un\.?|sez\.?", "sezione o corte citata"),
    ("ruolo", r"r\.?\s*g\.?\s*n\.?\s*r\.?|n\.?\s*r\.?\s*g\.?|r\.?\s*g\.?|proc\.?|procedimento", "numero di ruolo o di procedimento"),
    ("europa", r"reg\.?(?:\s*\((?:ue|ce)\))?|regolamento|dir\.?|direttiva", "fonte dell'Unione europea"),
    ("protocollo", r"prot\.?|protocollo|fatt\.?|fattura|parcella|vers\.?|versione|rif\.?", "numerazione d'ufficio"),
)
# Due confini obbligatori. Quello iniziale: senza, la «l» di «del», «al», «il»
# verrebbe scambiata per l'abbreviazione di «legge» e «udienza del 10/11/2026»
# non sarebbe più una data. Quello finale: l'abbreviazione deve essere chiusa da
# un punto o da uno spazio, altrimenti «con» si leggerebbe come «co.» + «n.» e
# ogni parola dopo «con» finirebbe dentro un riferimento normativo.
_PRIMA = re.compile(
    r"(?<![\w'’])(?:" + "|".join(espressione for _, espressione, _ in ABBREVIAZIONI) + r")(?:\.|\s)[\s.:]*(?:n(?:\.|\s)[\s.:]*)?$",
    re.IGNORECASE,
)
# Il token stesso può inglobare l'abbreviazione quando la lettera somiglia a una
# cifra: «l. 5/2026» viene letto come giorno «l», mese 5, anno 2026.
_TOKEN_CON_ABBREVIAZIONE = re.compile(
    r"^(?:" + "|".join(espressione for _, espressione, _ in ABBREVIAZIONI) + r")\s*\.\s",
    re.IGNORECASE,
)


def abbreviazione_prima(testo: str, inizio: int) -> str:
    """L'abbreviazione normativa che precede il token, se c'è."""
    prima = str(testo or "")[max(0, inizio - FINESTRA_PRIMA):inizio]
    match = _PRIMA.search(prima)
    return " ".join(match.group(0).split()) if match else ""


def e_riferimento_normativo(testo: str, inizio: int, fine: int) -> str:
    """Il riferimento normativo che contiene il token, oppure stringa vuota.

    Vale quando il token stesso comincia con l'abbreviazione (la «l» di
    «legge» letta come giorno) e quando l'abbreviazione precede il token senza
    parole in mezzo: «l. 5/2026», «art. 2.3.2026», «D.Lgs. 1/2/2026», «prot.
    12/3/26». Una data introdotta da una preposizione — «del 10/11/2026», «in
    data 05/09/2026», «lì 20/09/2026» — non è un riferimento: fra
    l'abbreviazione e la data c'è sempre la parola che la annuncia.
    """
    grezzo = str(testo or "")
    token = grezzo[inizio:fine]
    if _TOKEN_CON_ABBREVIAZIONE.match(token):
        return " ".join(token.split())
    abbreviazione = abbreviazione_prima(grezzo, inizio)
    if not abbreviazione:
        return ""
    return " ".join(f"{abbreviazione} {token}".split())


def descrizione(chiave: str) -> str:
    for voce, _espressione, cosa_cita in ABBREVIAZIONI:
        if voce == chiave:
            return cosa_cita
    return ""


__all__ = ["ABBREVIAZIONI", "FINESTRA_PRIMA", "abbreviazione_prima", "descrizione", "e_riferimento_normativo"]
