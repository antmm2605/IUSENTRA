"""Classificatore deterministico: domanda giuridica o domanda sui dati dello studio.

Le domande giuridiche ("quali sono i presupposti della responsabilita' extracontrattuale?")
vanno alla ricerca giuridica (Normattiva, giurisprudenza); il livello operativo dello
studio risponde solo quando ci sono segnali di dati dello studio (clienti, fascicoli,
udienze, scadenze, R.G., PEC, nomi presenti in anagrafica).

Non usa il modello: punteggi su segnali lessicali, quindi e' ripetibile e verificabile
(tests/lex_routing/domande.json).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Iterable

GIURIDICA = "giuridica"
STUDIO = "studio"
INDETERMINATA = "indeterminata"


def _norm(testo: str) -> str:
    t = unicodedata.normalize("NFKD", str(testo or "").lower().replace("’", "'"))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", t).strip()


# --- segnali dello studio ---------------------------------------------------
_STUDIO_FORTI = tuple(
    re.compile(p)
    for p in (
        r"\br\.?\s?g\.?\s*(?:n\.?\s*)?\d{1,7}\s*/\s*\d{2,4}\b",
        r"\b(?:il|la|le|i|gli)\s+(?:mio|mia|miei|mie|nostro|nostra|nostri|nostre)\s+\w*\s*(?:client|fascicol|pratic|udienz|scadenz|agend|pec|appuntament|parcell|fattur|preventiv)",
        r"\b(?:mio|mia|miei|mie|nostro|nostra|nostri|nostre)\s+(?:client|fascicol|pratic|udienz|scadenz|pec)",
        r"\b(?:del|dei|al|ai|per il|per la|di un|dello)\s+client[ei]\b",
        r"\bprossim[aeoi]\s+(?:udienz|scadenz|appuntament)",
        r"\b(?:udienz|scadenz)[ae]\s+(?:di\s+|della\s+|del\s+|in\s+)?(?:oggi|domani|dopodomani|settimana|mese|questa|queste|ottobre|novembre|dicembre|gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre)",
        r"\b(?:ultim[aeoi]|nuov[aeoi]|ricevut[aeoi]|inviat[aeoi])\s+(?:pec|email|mail|messagg)",
        r"\b(?:pec|email|mail)\s+(?:ricevut|inviat|arrivat|non lett)",
        r"\bquando\s+(?:e|ho|abbiamo|c'e)\s+(?:l')?(?:udienz|scadenz)",
        r"\b(?:agenda|appuntamenti)\s+(?:di\s+)?(?:oggi|domani|settimana)",
        r"\b(?:fatture|parcelle|preventivi)\s+(?:da\s+|non\s+|aperte|scadut|emess|pagat)",
        r"\b(?:dammi|dimmi|mostrami|elencami|elenca|cerca|trova)\s+(?:i\s+|le\s+|il\s+|la\s+|tutti\s+i\s+|tutte\s+le\s+)?(?:dati|client|fascicol|udienz|scadenz|pec|document|recapit|pratic)",
        r"\b(?:guida|scheda)\s+(?:pratica|operativa)\b",
        r"\bchecklist\b",
        r"\b(?:template|catalogo)\s+(?:di\s+)?att[oi]\b",
        r"\banagrafica\b",
        r"\b(?:quanti|quante)\s+(?:client|fascicol|udienz|scadenz|pratic)",
        r"\bche\s+fascicoli\b",
        r"\bstato\s+(?:del\s+)?fascicolo\b",
    )
)
_STUDIO_DEBOLI = (
    "cliente",
    "clienti",
    "fascicolo",
    "fascicoli",
    "pratica",
    "pratiche",
    "udienza",
    "udienze",
    "scadenza",
    "scadenze",
    "pec",
    "agenda",
    "preventivo",
    "fattura",
    "parcella",
    "cancelleria",
    "studio",
)

# --- segnali giuridici ----------------------------------------------------------
_CODICI = r"(?:c\.?\s?c\.?|c\.?\s?p\.?\s?c\.?|c\.?\s?p\.?\s?p\.?|c\.?\s?p\.?|cost\.?|d\.?\s?lgs\.?|d\.?\s?l\.?|d\.?\s?p\.?\s?r\.?|l\.?|codice\s+(?:civile|penale|della\s+strada|del\s+consumo|di\s+procedura\s+\w+)|costituzione|tuel|cad|gdpr)"
_ARTICOLO_CODICE = re.compile(rf"\bart(?:icol[oi])?\.?\s*\d+(?:[-\s]?(?:bis|ter|quater))?(?:\s*(?:,|e|c\.\d+))?\s*(?:del\s+|della\s+|dello\s+)?{_CODICI}")
_ARTICOLO = re.compile(r"\bart(?:icol[oi])?\.?\s*\d+")
_ISTITUTI = (
    "responsabilita",
    "extracontrattual",
    "contrattual",
    "risarcimento",
    "danno",
    "inadempimento",
    "risoluzione",
    "rescissione",
    "nullita",
    "annullabilita",
    "prescrizione",
    "decadenza",
    "usucapione",
    "successione",
    "legittima",
    "testamento",
    "eredita",
    "locazione",
    "comodato",
    "mutuo",
    "fideiussione",
    "ipoteca",
    "pegno",
    "caparra",
    "clausola penale",
    "simulazione",
    "litisconsorzio",
    "litispendenza",
    "giudicato",
    "competenza",
    "giurisdizione",
    "onere della prova",
    "legittimazione",
    "azione revocatoria",
    "azione di",
    "buona fede",
    "dolo",
    "colpa",
    "nesso causale",
    "reato",
    "concorso di persone",
    "legittima difesa",
    "stato di necessita",
    "diritto di",
    "proprieta",
    "servitu",
    "possesso",
    "condominio",
    "separazione",
    "divorzio",
    "affidamento",
    "mantenimento",
    "licenziamento",
    "contratto",
    "obbligazion",
    "garanzia",
    "vizi",
    "trattamento dei dati",
    "interessi legali",
    "interessi moratori",
    "opposizione a decreto",
    "decreto ingiuntivo",
    "procedimento",
    "impugnazione",
    "appello",
    "ricorso per cassazione",
    "pignoramento",
    "esecuzione forzata",
    "fallimento",
    "insolvenza",
)
_APERTURE_GIURIDICHE = tuple(
    re.compile(p)
    for p in (
        r"^(?:quali|che)\s+(?:sono|cosa)\s+(?:i|le|gli|il|la)\s+(?:presuppost|requisit|elementi|condizioni|effetti|differenz|limiti|termini|conseguenz|caratteristiche)",
        r"\b(?:quali|quanti)\s+(?:sono\s+)?(?:i|le|gli)\s+(?:presuppost|requisit|elementi|effetti|termini|limiti|casi)",
        r"\bcosa\s+(?:prevede|dice|stabilisce|dispone|sancisce|regola)\b",
        r"\bche\s+cosa\s+(?:prevede|dice|stabilisce|dispone)\b",
        r"\bcos'e\s+(?:la|il|l'|lo|un|una)\b",
        r"\bin\s+cosa\s+consiste\b",
        r"\bche\s+differenza\s+c'e\s+tra\b",
        r"\bqual\s*e\s+(?:la|il)\s+(?:differenza|disciplina|normativa|termine\s+di\s+prescrizione|termine\s+di\s+decadenza|natura|funzione)",
        r"\bquando\s+(?:si\s+applica|si\s+prescrive|decade|si\s+configura|scatta|e\s+(?:possibile|ammissibile|valido|nullo|dovuto))\b",
        r"\bcome\s+(?:funziona|si\s+calcola|si\s+prova|si\s+dimostra)\b",
        r"\bspiega(?:mi)?\s+(?:la|il|le|i|l')\b",
        r"\bsi\s+puo\b",
        r"\bin\s+quali\s+casi\b",
    )
)
_TERMINI_GIURIDICI = (
    "normativa",
    "norma",
    "norme",
    "legge",
    "articolo",
    "codice civile",
    "codice penale",
    "costituzione",
    "gazzetta ufficiale",
    "normattiva",
    "giurisprudenza",
    "sentenza",
    "sentenze",
    "cassazione",
    "orientamento",
    "massima",
    "dottrina",
    "disciplina",
    "vigente",
)
_TERMINI_GIURISPRUDENZA = (
    "giurisprudenza",
    "sentenza",
    "sentenze",
    "cassazione",
    "orientamento",
    "orientamenti",
    "massima",
    "massime",
    "pronuncia",
    "pronunce",
    "sezioni unite",
    "corte costituzionale",
    "consiglio di stato",
)


@dataclass(frozen=True, slots=True)
class Classificazione:
    tipo: str
    tipo_ricerca: str = ""  # "normativa" | "giurisprudenza" (solo per le domande giuridiche)
    punteggio_giuridico: int = 0
    punteggio_studio: int = 0
    motivi: tuple[str, ...] = field(default_factory=tuple)

    @property
    def giuridica(self) -> bool:
        return self.tipo == GIURIDICA

    @property
    def studio(self) -> bool:
        return self.tipo == STUDIO


def _contiene(testo: str, chiave: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(chiave)}", testo) is not None


def _parola(testo: str, chiave: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(chiave)}(?![a-z0-9])", testo) is not None


def classifica_domanda(domanda: str, nomi_anagrafica: Iterable[str] = ()) -> Classificazione:
    """Classifica la domanda; ``nomi_anagrafica`` sono i nomi (clienti, controparti) noti allo studio."""

    t = _norm(domanda)
    if not t:
        return Classificazione(INDETERMINATA)
    motivi: list[str] = []
    studio = 0
    giuridico = 0

    for modello in _STUDIO_FORTI:
        if modello.search(t):
            studio += 4
            motivi.append(f"studio:{modello.pattern[:28]}")
    for nome in nomi_anagrafica:
        n = _norm(nome)
        if len(n) >= 4 and _parola(t, n):
            studio += 5
            motivi.append(f"anagrafica:{n}")
    deboli = [w for w in _STUDIO_DEBOLI if _parola(t, w)]
    studio += len(deboli)
    if deboli:
        motivi.append("studio-deboli:" + ",".join(deboli[:4]))

    if _ARTICOLO_CODICE.search(t):
        giuridico += 5
        motivi.append("articolo+codice")
    elif _ARTICOLO.search(t):
        giuridico += 2
    istituti = [w for w in _ISTITUTI if _contiene(t, w)]
    giuridico += min(len(istituti), 3) * 2
    if istituti:
        motivi.append("istituti:" + ",".join(istituti[:4]))
    if any(m.search(t) for m in _APERTURE_GIURIDICHE):
        giuridico += 2
        motivi.append("apertura-giuridica")
    termini = [w for w in _TERMINI_GIURIDICI if _parola(t, w)]
    giuridico += min(len(termini), 2) * 2
    if termini:
        motivi.append("termini:" + ",".join(termini[:3]))

    if giuridico == 0 and studio == 0:
        tipo = INDETERMINATA
    elif studio > giuridico or (studio == giuridico and studio >= 4):
        tipo = STUDIO
    elif giuridico >= 2 and giuridico > studio:
        tipo = GIURIDICA
    else:
        tipo = INDETERMINATA
    ricerca = ""
    if tipo == GIURIDICA:
        ricerca = "giurisprudenza" if any(_contiene(t, w) for w in _TERMINI_GIURISPRUDENZA) else "normativa"
    return Classificazione(tipo, ricerca, giuridico, studio, tuple(motivi))


def e_domanda_giuridica(domanda: str, nomi_anagrafica: Iterable[str] = ()) -> bool:
    return classifica_domanda(domanda, nomi_anagrafica).giuridica


__all__ = ["Classificazione", "GIURIDICA", "INDETERMINATA", "STUDIO", "classifica_domanda", "e_domanda_giuridica"]
