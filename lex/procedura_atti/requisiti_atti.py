"""Requisiti obbligatori per modello d'atto: la struttura dipende dall'atto scelto nella scheda.

Ogni requisito dichiara la norma da cui deriva e i segnali testuali con cui si riconosce nella bozza. Il controllo e'
di presenza, non di correttezza: un requisito non rilevato rende la bozza «incompleta» finche' l'avvocato non lo
verifica. Catalogo versione 2026-10-23, da riscontrare sul testo vigente delle norme indicate.
"""
from __future__ import annotations

import re

R = lambda id_, descr, norma, *segnali: {"id": id_, "descrizione": descr, "norma": norma, "segnali": segnali}  # noqa: E731

COMUNI_RICORSO = [
    R("giudice", "giudice o ufficio adito", "", r"tribunale|giudice di pace|corte|t\.?a\.?r|ill\.?mo|ecc\.?mo"),
    R("parti", "parti con le generalita'", "", r"c\.?\s?f\.?|codice fiscale|nato a|con sede in|\[dato mancante"),
    R("fatti", "esposizione dei fatti", "", r"\bfatt[oi]\b|in fatto|premesso che"),
    R("diritto", "ragioni di diritto", "", r"diritto|motiv"),
    R("conclusioni", "conclusioni / domande", "", r"conclusion|p\.?\s?q\.?\s?m|chiede che|voglia"),
    R("difensore", "difensore e procura", "art. 83 c.p.c.", r"procura|avv\.|difensore"),
]
CATALOGO = {
    "citazione": [
        R("ufficio", "indicazione del tribunale/giudice", "art. 163 c. 3 n. 1 c.p.c.", r"tribunale|giudice di pace|corte d.appello"),
        R("parti", "attore e convenuto con codice fiscale", "art. 163 c. 3 n. 2 c.p.c.", r"c\.?\s?f\.?|codice fiscale|\[dato mancante"),
        R("oggetto", "oggetto della domanda", "art. 163 c. 3 n. 3 c.p.c.", r"oggetto|domanda"),
        R("fatti_diritto", "fatti ed elementi di diritto", "art. 163 c. 3 n. 4 c.p.c.", r"in fatto|fatti|in diritto"),
        R("prove", "mezzi di prova e documenti", "art. 163 c. 3 n. 5 c.p.c.", r"mezzi di prova|documenti|si produc|prova testimoniale|allegat"),
        R("difensore", "procuratore e procura", "art. 163 c. 3 n. 6 c.p.c.", r"procura|avv\."),
        R("vocatio", "invito a comparire all'udienza con data", "art. 163 c. 3 n. 7 c.p.c.", r"cita|a comparire|udienza del"),
        R("avvertimenti", "avvertimenti su costituzione e decadenze", "art. 163 c. 3 n. 7 c.p.c.", r"decadenz|settanta giorni|costituirsi"),
        R("conclusioni", "conclusioni", "art. 163 c. 3 n. 4 c.p.c.", r"conclusion|p\.?\s?q\.?\s?m|voglia"),
    ],
    "ricorso_lavoro": [*COMUNI_RICORSO, R("prove", "mezzi di prova e documenti", "art. 414 n. 5 c.p.c.", r"mezzi di prova|document|testimon|allegat")],
    "intimazione_sfratto": [
        R("intimazione", "intimazione di sfratto", "art. 657-658 c.p.c.", r"intima"),
        R("citazione_convalida", "citazione per la convalida", "art. 660 c.p.c.", r"convalida"),
        R("avvertimento_663", "avvertimento sugli effetti della mancata comparizione", "artt. 660 e 663 c.p.c.", r"non compar|mancata comparizione|non si opp"),
        R("canoni", "indicazione dei canoni non pagati", "art. 658 c.p.c.", r"canon"),
    ],
    "comparsa": [
        R("ufficio", "giudice e causa", "art. 167 c.p.c.", r"tribunale|giudice"),
        R("posizione", "presa di posizione sui fatti e difese", "art. 167 c. 1 c.p.c.", r"contest|difes|eccep"),
        R("prove", "mezzi di prova e documenti", "art. 167 c. 1 c.p.c.", r"prov|document"),
        R("conclusioni", "conclusioni", "art. 167 c. 1 c.p.c.", r"conclusion|voglia|p\.?\s?q\.?\s?m"),
    ],
    "ricorso_generico": COMUNI_RICORSO,
    "domanda_passivo": [
        R("procedura", "indicazione della procedura", "art. 201 CCII", r"liquidazione|procedura|curatore"),
        R("somma", "somma chiesta", "art. 201 CCII", r"euro|€"),
        R("ragioni", "fatti e ragioni della domanda", "art. 201 CCII", r"titolo|rapporto|credito"),
        R("privilegio", "eventuale titolo di prelazione", "art. 201 CCII", r"privilegi|prelazion|chirograf"),
        R("pec", "indirizzo PEC per le comunicazioni", "art. 201 CCII", r"pec|posta elettronica certificata"),
    ],
    "appello_penale": [
        R("provvedimento", "provvedimento impugnato", "art. 581 c.p.p.", r"sentenza"),
        R("capi", "capi o punti impugnati", "art. 581 c. 1 lett. a c.p.p.", r"capi|punt"),
        R("richieste", "richieste", "art. 581 c. 1 lett. c c.p.p.", r"chiede|richiest|riform"),
        R("motivi", "motivi con ragioni di diritto ed elementi di fatto", "art. 581 c. 1 lett. d c.p.p.", r"motiv"),
    ],
    "ricorso_tributario": [
        R("giudice", "Corte di giustizia tributaria", "art. 18 d.lgs. 546/1992", r"corte di giustizia tributaria"),
        R("ente", "ente impositore / agente della riscossione", "art. 18 d.lgs. 546/1992", r"agenzia|ente|riscossione"),
        R("atto", "atto impugnato e oggetto", "art. 18 d.lgs. 546/1992", r"avviso|cartella|atto impugnato"),
        R("motivi", "motivi", "art. 18 d.lgs. 546/1992", r"motiv"),
    ],
    "lettera": [
        R("destinatario", "destinatario", "", r"spett|egregi|alla|al sig"),
        R("intimazione", "richiesta e termine", "art. 1219 c.c.", r"entro|intima|invit"),
    ],
}
SCELTA = [("citazione", r"citazione"), ("intimazione_sfratto", r"sfratto"), ("comparsa", r"comparsa"),
          ("ricorso_lavoro", r"414"), ("domanda_passivo", r"passivo"), ("appello_penale", r"appello.*c\.?p\.?p|581"),
          ("ricorso_tributario", r"tributari"), ("lettera", r"lettera|diffida"), ("ricorso_generico", r"ricorso")]


def modello_per(scheda: dict) -> str | None:
    if scheda.get("forma_risposta") != "atto":
        return None
    s = scheda.get("modello_atto") or scheda.get("rimedio", {}).get("strumento", "")
    return next((m for m, rx in SCELTA if re.search(rx, s, re.I)), "ricorso_generico")


def requisiti_mancanti(bozza: str, modello: str | None) -> list[dict]:
    if not modello:
        return []
    return [{k: r[k] for k in ("id", "descrizione", "norma")} for r in CATALOGO[modello]
            if not any(re.search(sg, bozza or "", re.I) for sg in r["segnali"])]
