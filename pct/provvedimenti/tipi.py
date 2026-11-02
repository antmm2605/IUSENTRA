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

from .testo import normalizza

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
    "fissazione_udienza": ("Fissazione di udienza", r"\bfissa\b.{0,120}\budienza\b|\budienza\b.{0,40}\bfissata\s+per\s+il\b"),
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
    if "scioglimento_riserva" in trovati and "riserva" in trovati:
        trovati.remove("riserva")
    if "decreto_415" in trovati:
        trovati = [t for t in trovati if t != "fissazione_udienza"]
    return tuple(trovati)


def etichetta(tipo: str) -> str:
    return TIPI.get(tipo, (tipo, ""))[0]


__all__ = ["CATALOGO_A_TIPO", "TIPI", "etichetta", "riconosci_tipi"]
