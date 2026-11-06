"""Che provvedimento è: titolo, ufficio e verbi del dispositivo.

Prima si interroga il catalogo dei documenti (``identita_dal_titolo``: titolo in testa
confermato da un segnale nel corpo, con la sua norma); poi si leggono le formule che il
giudice usa nel dispositivo («FISSA l'udienza», «AMMETTE la prova», «NOMINA CTU»,
«si riserva»…). Un verbale può contenere più provvedimenti (ammissione delle prove e
rinvio), quindi i tipi sono un elenco, dal più specifico.

Ogni tipo rimanda alle norme che lo governano; le regole sui termini sono nella
tabella versionata ``pct/data/provvedimenti_regole_v2026_11.json``.
"""

from __future__ import annotations

import re

from .rigetto_trattazione import ESPRESSIONE as _RIGETTO_TRATTAZIONE
from .testo import normalizza

_RICEVUTA_DEPOSITO = r"(?:\bricevuta\s+di\s+(?:avvenuto\s+)?deposito\b|\bdeposito\s+(?:degli\s+)?atti\s+penali\b)"
_DEPOSITO_PENALE = r"(?:\bfuori\s+udienza\b|\bart\.?\s*78\b.{0,12}\bc\.?\s?p\.?\s?p\b|" + _RICEVUTA_DEPOSITO[3:-1] + ")"
# «chiamata in causa del terzo», non la «dichiarazione di terzo» del pignoramento presso terzi (art. 547 c.p.c.)
_CHIAMATA_IN_CAUSA = (r"\b(?:chiamat\w+|chiamare)\s+(?:in\s+causa\s+(?:(?:del|dei|di\s+un|il|i|la|le)\s+)?|(?:del|dei|di\s+un)\s+)"
                      r"terz[oaie]\b")
_CHIAMATA_NEGATA = re.compile(r"\b(?:rigett\w*|respin\w*|non\s+autorizz\w*|inammissibil\w*|tardiv\w*)\b.{0,120}\bchiamat\w+\b.{0,40}\bterz", re.I)

#: tipo → (etichetta, espressione nel testo)
TIPI: dict[str, tuple[str, str]] = {
    "sentenza": ("Sentenza", r"\bin\s+nome\s+del\s+popolo\s+italiano\b|\bdefinitivamente\s+(?:pronunciando|decidendo)\b"),
    "decreto_ingiuntivo": ("Decreto ingiuntivo", r"\bdecreto\s+(?:d'\s*)?ingiuntivo\b|\bingiunge\b.{0,200}\bpagare\b"),
    "note_127_ter": ("Trattazione scritta (art. 127-ter c.p.c.)",
                     r"\b127\s*[-\s]?\s*ter\b(?=.{0,1500}\b(?:note\s+scritte|trattazione\s+scritta)\b)"
                     r"|\b(?:note\s+scritte|trattazione\s+scritta)\b(?=.{0,1500}\b127\s*[-\s]?\s*ter\b)"),
    "udienza_remota_127_bis": ("Udienza da remoto (art. 127-bis c.p.c.)",
                               r"\b127\s*[-\s]?\s*bis\b|\bcollegament\w+\s+audiovisiv\w+\b|\budienza\s+(?:da\s+remoto|in\s+videoconferenza)\b"),
    "decreto_415": ("Decreto di fissazione dell'udienza di discussione (art. 415 c.p.c.)",
                    r"\bfiss\w*\b.{0,80}\budienza\s+di\s+discussione\b|\bart\.?\s*415\b(?![\s-]*bis)(?!.{0,12}c\.?\s?p\.?\s?p)"),
    # Appello del lavoro (art. 435 c.p.c.): il decreto della Corte d'appello fissa l'udienza di discussione.
    "decreto_435": ("Decreto di fissazione dell'udienza nell'appello del lavoro (art. 435 c.p.c.)",
                    r"\bart\.?\s*435\b(?!.{0,12}c\.?\s?p\.?\s?p)(?=.{0,800}\bfiss\w*\b.{0,80}\b(?:udienza|discussione)\b)"
                    r"|\bcorte\s+d'\s*appello\b.{0,800}\bfiss\w*\b.{0,80}\budienza\s+di\s+discussione\b"),
    # Procedimento semplificato di cognizione (art. 281-undecies c.p.c.): decreto che fissa l'udienza di comparizione.
    "decreto_281undecies": ("Decreto di fissazione nel procedimento semplificato (art. 281-undecies c.p.c.)",
                            r"\b281\s*[-\s]?\s*undecies\b(?=.{0,800}\bfiss\w*\b.{0,80}\budienza\b)"
                            r"|\bfiss\w*\b.{0,80}\budienza\b.{0,800}\b281\s*[-\s]?\s*undecies\b"),
    # Giudice di pace penale (art. 27 D.Lgs. 274/2000): decreto di convocazione sul ricorso immediato della persona offesa.
    "decreto_gdp_ricorso_immediato": ("Decreto di convocazione sul ricorso immediato (art. 27 D.Lgs. 274/2000)",
                                      r"\bricorso\s+immediato\b(?=.{0,1500}\b(?:convoca|fissa)\w*\b)"
                                      r"|\bart\.?\s*27\b.{0,60}\b(?:d\.?\s?lgs\.?\s*(?:n\.?\s*)?)?274\s*/\s*2000\b"),
    # Litisconsorzio necessario: il giudice ordina di chiamare in causa le parti mancanti in un termine (art. 102 c.p.c.,
    # art. 49 c.p.a., art. 58 D.Lgs. 175/2024).
    "integrazione_contraddittorio": ("Ordine di integrazione del contraddittorio",
                                     r"\bintegrazione\s+del\s+contraddittorio\b|\bintegr\w+\s+il\s+contraddittorio\b"),
    # Nullità della citazione rilevata in contumacia del convenuto: rinnovazione della citazione (art. 164 c.p.c.).
    "rinnovazione_citazione": ("Ordine di rinnovazione della citazione (art. 164 c.p.c.)",
                               r"\bnullit\w+\s+della\s+citazione\b.{0,400}\brinnov\w+\b"
                               r"|\bart\.?\s*164\b.{0,12}\bc\.?\s?p\.?\s?c\b.{0,400}\brinnov\w+\b"),
    # Notificazione nulla e destinatario non costituito: rinnovazione (art. 291 c.p.c., art. 44 c.p.a.).
    "rinnovazione_notifica": ("Ordine di rinnovazione della notificazione",
                              r"\brinnov\w*\b.{0,60}\bnotific\w*\b|\bnotific\w*\b.{0,80}\brinnovarla\b"),
    # Chiamata del terzo autorizzata o udienza differita per consentirla (art. 269 c.p.c.).
    "chiamata_terzo": ("Chiamata in causa del terzo (art. 269 c.p.c.)",
                       r"\b(?:autorizz\w*|differisc\w*|differit\w*|spost\w*)\b.{0,250}" + _CHIAMATA_IN_CAUSA +
                       r"|" + _CHIAMATA_IN_CAUSA + r".{0,300}\b(?:autorizz\w*|differisc\w*|differit\w*)\b"),
    # Decreto cautelare senza sentire la controparte (art. 669-sexies, secondo comma, c.p.c.).
    "cautelare_inaudita": ("Decreto cautelare inaudita altera parte (art. 669-sexies c.p.c.)",
                           r"\binaudita\s+altera\s+parte\b(?=.{0,1500}\bnotific\w*\b)"
                           r"|\b669\s*[-\s]?\s*sexies\b.{0,300}\b(?:decreto|inaudita)\b(?=.{0,1500}\bnotific\w*\b)"),
    # Opposizioni nell'esecuzione: il giudice dell'esecuzione fissa udienza e termine per notificare (artt. 615, 617, 618, 619 c.p.c.).
    "opposizione_esecutiva": ("Decreto sull'opposizione nell'esecuzione (artt. 615-619 c.p.c.)",
                              r"(?:\bopposizione\s+(?:all'\s*esecuzione|agli\s+atti\s+esecutivi)\b"
                              r"|\bopposizione\s+di\s+terzo\b(?=.{0,600}\besecu\w*\b)"
                              r"|\bartt?\.?\s*(?:615|617|618|619)\b.{0,12}\bc\.?\s?p\.?\s?c\b)"
                              r"(?=.{0,1500}\bfiss\w*\b.{0,80}\budienza\b)"),
    # Penale: atti dello studio di cui la ricevuta di deposito conferma la presentazione fuori udienza.
    "deposito_costituzione_parte_civile": ("Costituzione di parte civile depositata fuori udienza (art. 78 c.p.p.)",
                                           r"\bcostituzione\s+(?:di\s+)?parte\s+civile\b(?=.{0,1500}" + _DEPOSITO_PENALE + ")"
                                           r"|" + _DEPOSITO_PENALE + r".{0,1500}\bcostituzione\s+(?:di\s+)?parte\s+civile\b"),
    "richiesta_incidente_probatorio": ("Richiesta di incidente probatorio depositata (art. 395 c.p.p.)",
                                       r"\brichiesta\s+di\s+incidente\s+probatorio\b(?=.{0,1500}" + _RICEVUTA_DEPOSITO + ")"
                                       r"|" + _RICEVUTA_DEPOSITO + r".{0,1500}\brichiesta\s+di\s+incidente\s+probatorio\b"),
    # Ordinanza che accoglie l'incidente probatorio: l'avviso lo fa notificare il giudice (art. 398 c.p.p.).
    "ordinanza_incidente_probatorio": ("Ordinanza che dispone l'incidente probatorio (art. 398 c.p.p.)",
                                       r"\bincidente\s+probatorio\b(?=.{0,1500}\b(?:accoglie|ammette)\b)"
                                       r"|\b(?:accoglie|ammette)\b.{0,300}\bincidente\s+probatorio\b"),
    # Codice della crisi: ricorso e decreto di convocazione notificati a cura dell'ufficio (art. 40 D.Lgs. 14/2019).
    "convocazione_liquidazione_giudiziale": ("Decreto di convocazione per la liquidazione giudiziale (art. 40 CCII)",
                                             r"\bliquidazione\s+giudiziale\b(?=.{0,1500}\bconvoc\w*\b)"
                                             r"|\bconvoc\w*\b.{0,1500}\bliquidazione\s+giudiziale\b"),
    "decreto_473bis": ("Decreto di fissazione nel rito della famiglia (art. 473-bis.14 c.p.c.)",
                       r"\b473\s*[-\s]?\s*bis\.?\s*14\b|\b473\s*[-\s]?\s*bis\b.{0,200}\bfiss\w*\b.{0,60}\budienza\b"),
    "verifiche_171bis": ("Decreto sulle verifiche preliminari (art. 171-bis c.p.c.)",
                         r"\b171\s*[-\s]?\s*bis\b|\bverifiche\s+preliminari\b"),
    "rimessione_decisione": ("Rimessione della causa in decisione (art. 189 c.p.c.)",
                             r"\bprecisazione\s+delle\s+conclusioni\b|\brimess\w+\b.{0,40}\b(?:in\s+decisione|al\s+collegio)\b|\bart\.?\s*189\b"),
    "ammissione_prove": ("Ordinanza di ammissione dei mezzi istruttori",
                         r"\bammett\w*\b.{0,120}\b(?:prova|prove|testi|testimon\w*|interrogatorio)\b"),
    "nomina_ctu": ("Nomina del consulente tecnico d'ufficio",
                   r"\bnomin\w*\b.{0,80}\b(?:c\.?\s?t\.?\s?u\.?|consulente\s+tecnico\s+d'\s*ufficio)\b|\bdispone\s+(?:la\s+)?c\.?t\.?u\b"),
    "riserva": ("Causa trattenuta in riserva",
                r"\bsi\s+riserva\s+(?:di\s+(?:decidere|provvedere)|la\s+decisione)\b|\btrattiene\s+(?:la\s+causa\s+)?in\s+riserva\b"),
    "scioglimento_riserva": ("Scioglimento della riserva", r"\bscioglimento\s+della\s+riserva\b|\bsciogliendo\s+la\s+riserva\b"),
    "trattazione_tributaria": ("Avviso di trattazione tributaria",
                               r"\bavviso\s+di\s+trattazione\b|\bcorte\s+di\s+giustizia\s+tributaria\b.{0,400}\b(?:trattazione|camera\s+di\s+consiglio|pubblica\s+udienza)\b"),
    "avviso_udienza_amministrativa": ("Avviso di udienza amministrativa",
                                      r"\b(?:tribunale\s+amministrativo\s+regionale|t\.?\s?a\.?\s?r\.?|consiglio\s+di\s+stato)\b.{0,600}"
                                      r"\b(?:fissa\w*|avviso|decreto\s+di\s+fissazione)\b.{0,120}\budienza\b"),
    "citazione_penale": ("Decreto di citazione a giudizio o che dispone il giudizio",
                         r"\bdecreto\s+(?:di\s+citazione\s+(?:diretta\s+)?a\s+giudizio|che\s+dispone\s+il\s+giudizio)\b|\bart\.?\s*(?:552|429)\s+c\.?p\.?p\b"),
    "rinvio": ("Rinvio dell'udienza", r"\brinvia\b.{0,120}\budienza\b|\bdifferisce\b.{0,80}\budienza\b"),
    "fissazione_udienza": ("Fissazione di udienza", r"\bfissa\b.{0,120}\b(?:udienza|camera\s+di\s+consiglio)\b"
                                                    r"|\budienza\b.{0,40}\bfissata\s+per\s+il\b"),
    "rigetto_trattazione_scritta": ("Rigetto dell'istanza di trattazione scritta (art. 127-ter c.p.c.)", _RIGETTO_TRATTAZIONE),
    # Ordinanza o decreto che assegna un termine a una parte (art. 175 c.p.c.; art. 39 c.p.a. che vi rinvia):
    # non è un tipo con regole di legge proprie, ma i suoi capi si leggono.
    "assegnazione_termine": ("Provvedimento che assegna un termine",
                             r"(?:assegna|concede|onera)\w*\b.{0,120}\btermine\b.{0,80}\b(?:giorni|gg\.?|entro|sino|fino)\b"),
}

#: voci del catalogo dei documenti (pct/document_intelligence) che sono già un tipo noto
CATALOGO_A_TIPO = {
    "decreto_ingiuntivo": "decreto_ingiuntivo",
    "decreto_127ter": "note_127_ter",
    "decreto_citazione_giudizio": "citazione_penale",
    "decreto_dispone_giudizio": "citazione_penale",
}
_TIPO_SENTENZA_CATALOGO = re.compile(r"^(?:pen_)?sentenza|_sentenza_", re.I)
_COMPILATI = {codice: re.compile(espressione, re.I) for codice, (_, espressione) in TIPI.items()}


def _dal_catalogo(testo: str) -> str:
    try:
        from pct.document_intelligence.catalog_titoli import identita_dal_titolo

        identita = identita_dal_titolo(testo) or {}
    except Exception:  # il catalogo non deve fermare la lettura del dispositivo
        return ""
    codice = str(identita.get("id") or identita.get("code") or "")
    if codice in CATALOGO_A_TIPO:
        return CATALOGO_A_TIPO[codice]
    return "sentenza" if _TIPO_SENTENZA_CATALOGO.search(codice) else ""


def riconosci_tipi(testo: str) -> tuple[str, ...]:
    """I tipi di provvedimento presenti nel testo, dal più specifico; vuoto se nessuno."""
    pulito = normalizza(testo)
    trovati: list[str] = []
    dal_catalogo = _dal_catalogo(testo)
    if dal_catalogo:
        trovati.append(dal_catalogo)
    for codice, espressione in _COMPILATI.items():
        if codice not in trovati and espressione.search(pulito):
            trovati.append(codice)
    if "sentenza" in trovati:
        # La sentenza richiama la storia del processo (udienze, 127-ter già svolte): non apre quei passaggi.
        return ("sentenza",)
    if "rigetto_trattazione_scritta" in trovati:
        # Il rigetto cita il 127-ter ma non sostituisce l'udienza: nessun termine per le note.
        trovati = [t for t in trovati if t != "note_127_ter"]
    if "scioglimento_riserva" in trovati and "riserva" in trovati:
        trovati.remove("riserva")
    if "decreto_435" in trovati:
        # Il decreto d'appello del lavoro fissa anch'esso l'«udienza di discussione»: valgono i termini dell'art. 435.
        trovati = [t for t in trovati if t != "decreto_415"]
    if "chiamata_terzo" in trovati and _CHIAMATA_NEGATA.search(pulito):
        trovati.remove("chiamata_terzo")
    if "rinnovazione_citazione" in trovati and "rinnovazione_notifica" in trovati:
        # «rinnovazione della citazione nulla» (art. 164) non è la rinnovazione della sola notifica (art. 291).
        trovati.remove("rinnovazione_notifica")
    if "richiesta_incidente_probatorio" in trovati and "ordinanza_incidente_probatorio" in trovati:
        trovati.remove("ordinanza_incidente_probatorio")
    if {"decreto_415", "decreto_435", "decreto_281undecies", "decreto_gdp_ricorso_immediato"} & set(trovati):
        trovati = [t for t in trovati if t != "fissazione_udienza"]
    return tuple(trovati)


def etichetta(tipo: str) -> str:
    return TIPI.get(tipo, (tipo, ""))[0]


__all__ = ["CATALOGO_A_TIPO", "TIPI", "etichetta", "riconosci_tipi"]
