"""Fase stragiudiziale: diffida e messa in mora fra imprese (d.lgs. 231/2002) e sinistro stradale (cod. ass.)."""
from __future__ import annotations

import re

from ..comprensione import Comprensione
from ..fatti import Fatti, data_it, euro
from ..modello import Analisi, Punto, Rif
from ..norme import piano
from .. import procedura as P
from ..termini import data_breve, termine_anni, termine_giorni
from .strumenti import date_in, forma, frase


_IMP = r"(?:euro\s*|€\s*)?([\d.]+(?:,\d+)?)(?:\s*euro|\s*€)?"


def _fatture(t: str) -> list[tuple[str, object, float]]:
    """Fatture «n. 88 del 30/04/2026 per 15.200 euro», «n. 12 del 10/03/2026 di euro 8.500», «n. 19 del … (€ 6.200)»."""
    out = []
    for m in re.finditer(r"n\.\s*(\d+)\s+del\s+(\d{1,2}/\d{1,2}/\d{4})\s*(?:,\s*)?(?:per|di|da|\(|importo|pari a)\s*" + _IMP, t):
        try:
            out.append((m.group(1), date_in(m.group(2))[0], float(m.group(3).replace(".", "").replace(",", "."))))
        except (ValueError, IndexError):
            continue
    return [x for x in out if x[2] > 0]


_DIFFIDA_GIA_FATTA = (r"nonostante (?:la|una) (?:diffida|messa in mora)|(?:diffida|messa in mora)[^.]{0,40}(?:senza esito|rimast\w* "
                      r"senza|inutilmente|senza risposta|ignorat)|gia (?:mandato|inviato|spedito|fatto)[^.]{0,30}(?:diffida|messa in mora)")


def riconosci_diffida_commerciale(c: Comprensione, f: Fatti) -> int:
    t = piano(f.testo)
    richiesta = piano(f.richiesta) or t
    # La diffida è la risposta solo se è l'atto chiesto: se è già stata inviata senza esito, il passo è il giudizio.
    if re.search(_DIFFIDA_GIA_FATTA, t) and not re.search(r"diffida|messa in mora|lettera", richiesta):
        return 0
    return 4 if re.search(r"diffida|messa in mora|costituzione in mora", richiesta) and "fattur" in t and (
        f.ha("professionista_impresa") or "interessi commerciali" in t) and not re.search(r"sfratt|locazion", t) else 0


def analizza_diffida_commerciale(c: Comprensione, f: Fatti) -> Analisi:
    t = piano(f.testo)
    a = Analisi("diffida_commerciale", "stragiudiziale — crediti fra imprese", modello="STR_001", forma=forma(c))
    fatture = _fatture(t)
    giorni = int((re.search(r"pagamento a (\d+) giorni", t) or [None, "0"])[1]) or None
    acconto_m = re.search(r"acconto di ([\d.]+)\s*euro[^.]{0,80}?fattura n\.\s*(\d+)", t)
    acconto = (float(acconto_m.group(1).replace(".", "")), acconto_m.group(2)) if acconto_m else None
    totale = sum(x[2] for x in fatture)
    residuo = totale - (acconto[0] if acconto else 0)
    a.capito = [f"Credito di {f.assistita.nome or '[creditore]'} verso {f.controparte.nome or '[debitore]'} per "
                f"{len(fatture)} fatture" + (f" (totale {euro(totale)})" if fatture else "") +
                (f", acconto di {euro(acconto[0])} imputato alla fattura n. {acconto[1]}" if acconto else "") + "."]
    a.rimedio = ("lettera di diffida e messa in mora via PEC con intimazione a pagare entro 15 giorni, richiesta degli "
                 "interessi moratori del d.lgs. 231/2002 e interruzione della prescrizione; poi ricorso per decreto ingiuntivo")
    a.giudice = "stragiudiziale (destinataria la sede legale della debitrice)"
    a.inquadramento = [
        Punto("L'intimazione o richiesta fatta per iscritto costituisce in mora il debitore.",
              [Rif("cc:1219", "intimazione o richiesta fatta per iscritto")]),
        Punto("La stessa diffida interrompe la prescrizione, perché è un atto che vale a costituire in mora il debitore.",
              [Rif("cc:2943", "costituire in mora il debitore")]),
        Punto("Nelle transazioni commerciali gli interessi moratori decorrono, senza che sia necessaria la costituzione in "
              "mora, dal giorno successivo alla scadenza del termine di pagamento, nella misura degli interessi legali di mora "
              "(tasso di riferimento maggiorato di otto punti percentuali), salvo diverso accordo che qui manca.",
              [Rif("dlgs231:4", "senza che sia necessaria la costituzione in mora"), Rif("dlgs231:5", "interessi legali di mora"),
               Rif("dlgs231:2", "maggiorato di otto punti percentuali")]),
        Punto("Spetta inoltre l'importo forfettario di 40 euro per i costi di recupero, salvo la prova del maggior danno.",
              [Rif("dlgs231:6", "40 euro")]),
    ]
    a.procedibilita = [
        Punto("Per il ricorso per decreto ingiuntivo non serve la negoziazione assistita.",
              [Rif("dl132:3", "procedimenti per ingiunzione, inclusa l'opposizione")]),
        Punto(f"Se invece si agisse con causa ordinaria per il pagamento di somme non eccedenti {euro(P.soglia_negoziazione() or 0)}, "
              "l'invito alla negoziazione assistita sarebbe condizione di procedibilità.",
              [Rif("dl132:3", "pagamento a qualsiasi titolo di somme non eccedenti")]),
    ]
    for n, d, v in fatture:
        if giorni:
            scad = termine_giorni(d, giorni, sostanziale=True)
            a.termini.append(Punto(f"Fattura n. {n} del {data_it(d)} ({euro(v)}): pagamento a {giorni} giorni, scadenza "
                                   f"{data_breve(scad)}; gli interessi moratori decorrono dal giorno successivo.",
                                   [Rif("dlgs231:4", "dal giorno successivo alla scadenza del termine")]))
    if fatture:
        righe = [f"Totale fatture: {euro(totale)}."]
        if acconto:
            v88 = next((v for n, _, v in fatture if n == acconto[1]), None)
            if v88 is not None:
                righe.append(f"Residuo della fattura n. {acconto[1]}: {euro(v88 - acconto[0])}.")
        righe.append(f"Residuo complessivo da intimare (capitale): {euro(residuo)}.")
        a.conclusione = [Punto(" ".join(righe) + " Intimare il pagamento entro 15 giorni dal ricevimento, con gli interessi "
                               "moratori dalle singole scadenze e il preavviso del ricorso per decreto ingiuntivo.",
                               [Rif("cc:1219", "intimazione o richiesta fatta per iscritto"), Rif("dlgs231:5", "interessi legali di mora")])]
    a.avvertenze = ["Gli interessi moratori si indicano al tasso legale di mora ma si calcolano a parte, per semestri, con il "
                    "tasso di riferimento della BCE.", "Il termine di 15 giorni decorre dal ricevimento della diffida."]
    a.dati_mancanti = ["data di ricevimento della diffida (ricevuta PEC)", "tasso di riferimento BCE dei semestri interessati"]
    if c.tipo == "redazione":
        a.bozza = "\n".join([
            "PEC — DIFFIDA E COSTITUZIONE IN MORA", f"Spett.le {f.controparte.nome or '[debitore]'}, sede legale [da completare]",
            "Oggetto: fatture " + ", ".join(f"n. {n} del {data_it(d)} ({euro(v)})" for n, d, v in fatture) + ".",
            f"Per conto di {f.assistita.nome or '[creditore]'} vi intimo e diffido a pagare entro 15 giorni dal ricevimento "
            f"della presente la somma di {euro(residuo)} a saldo delle fatture indicate, oltre agli interessi moratori nella "
            "misura degli interessi legali di mora dal giorno successivo alla scadenza di ciascuna fattura (artt. 4 e 5 d.lgs. "
            "231/2002) e all'importo forfettario di 40 euro per ciascuna fattura (art. 6 d.lgs. 231/2002).",
            "La presente vale come costituzione in mora (art. 1219 c.c.) e come atto interruttivo della prescrizione "
            "(art. 2943 c.c.).",
            "In mancanza di pagamento nel termine, si procederà senza ulteriore avviso con ricorso per decreto ingiuntivo, "
            "con aggravio di spese.", "[luogo e data da completare] — Avv. [da completare]",
            "— Bozza preparata da Lex: da rivedere, non inviata. —"])
    return a


# ------------------------------------------------------------------------------------------ sinistro stradale
def riconosci_sinistro(c: Comprensione, f: Fatti) -> int:
    t = piano(f.testo)
    return 4 if re.search(r"tamponat|sinistro|incidente", t) and re.search(r"assicura", t) and f.ha("circolazione") or (
        re.search(r"tamponat", t) and "assicura" in t) else 0


def analizza_sinistro(c: Comprensione, f: Fatti) -> Analisi:
    t = piano(f.testo)
    a = Analisi("sinistro_stradale", "stragiudiziale — responsabilità civile auto", modello="RCD_015", forma=forma(c))
    d_sin = (date_in(frase(f, r"tamponat|sinistro|incidente")) or [None])[0]
    lesioni = bool(re.search(r"frusta|distorsione|lesion|pronto soccorso", t))
    cai = bool(re.search(r"\bcai\b|constatazione amichevole", t))
    danni = [float(m.replace(".", "")) for m in re.findall(r"danni per ([\d.]+)\s*euro", t)]
    spese = [float(m.replace(".", "")) for m in re.findall(r"fatture[^.]{0,40}?per ([\d.]+)\s*euro", t)]
    patrimoniali = sum(danni) + sum(spese)
    m_ass = re.search(r"assicuratore di \w+ (?:è|e) ([A-Z][\w ]{2,40}? S\.p\.A\.)", f.testo)
    propria = m_ass.group(1) if m_ass else "la propria impresa di assicurazione"
    a.capito = [f"Sinistro del {data_it(d_sin)}: tamponamento con responsabilità riconosciuta" + (" nel modulo CAI firmato da entrambi" if cai else "")
                + "; danni al veicolo" + (" e lesioni lievi del conducente" if lesioni else "") + "."]
    a.rimedio = (f"richiesta di risarcimento diretto a {propria} (artt. 149 e 148 d.lgs. 209/2005); se l'esito non è "
                 "soddisfacente, invito alla negoziazione assistita e poi causa davanti al giudice di pace")
    a.giudice = "giudice di pace competente per territorio (luogo del sinistro o residenza del convenuto)"
    a.inquadramento = [
        Punto("Sinistro fra due veicoli identificati e assicurati con danni ai veicoli o ai conducenti: il danneggiato chiede "
              "il risarcimento alla propria impresa di assicurazione (risarcimento diretto), anche per le lesioni di lieve entità "
              "del conducente.", [Rif("dlgs209:149", "identificati ed assicurati")]),
        Punto("La richiesta deve contenere i dati previsti e mettere il veicolo a disposizione per l'ispezione; l'impresa "
              "formula l'offerta entro sessanta giorni, ridotti a trenta se il modulo di denuncia è firmato da entrambi i "
              "conducenti, ed entro novanta giorni per le lesioni.", [Rif("dlgs209:148", "trenta giorni"),
                                                                       Rif("dlgs209:148", "novanta giorni")]),
        Punto("L'azione giudiziale è proponibile solo dopo sessanta giorni (novanta per le lesioni) dalla richiesta.",
              [Rif("dlgs209:145", "sessanta giorni"), Rif("dlgs209:145", "novanta in caso di danno alla persona")]),
    ]
    a.procedibilita = [
        Punto("Prima della causa la negoziazione assistita è condizione di procedibilità per il risarcimento del danno da "
              "circolazione di veicoli, qualunque sia il valore; la mediazione non è richiesta.",
              [Rif("dl132:3", "circolazione di veicoli e natanti")]),
        Punto("L'invito alla negoziazione avverte che la mancata risposta entro trenta giorni dalla ricezione o il rifiuto "
              "possono essere valutati dal giudice.", [Rif("dl132:4", "trenta giorni")]),
    ]
    a.competenza = [Punto(f"Il giudice di pace è competente per il risarcimento del danno da circolazione fino a "
                          f"{euro(P.limite_gdp_circolazione() or 0)}.",
                          [Rif("cpc:7", "purche il valore della controversia non superi venticinquemila euro")])]
    if d_sin:
        pres = termine_anni(d_sin, 2)
        a.termini = [Punto(f"Prescrizione biennale dal sinistro: {data_breve(pres)}; la richiesta all'assicuratore la interrompe.",
                           [Rif("cc:2947", "due anni")])]
    if patrimoniali:
        a.conclusione = [Punto(f"Danni patrimoniali documentati: {euro(patrimoniali)} (carrozzeria e spese mediche), oltre il "
                               "danno biologico da lesioni lievi da liquidare con le tabelle di legge.",
                               [Rif("dlgs209:139", "lieve entita")])]
    a.cosa_fare = [f"Inviare a {propria} (raccomandata A/R o PEC; per conoscenza all'assicuratore del responsabile) la "
                   "richiesta completa, con referto e fatture, e lasciare il veicolo a disposizione per l'ispezione.",
                   "Non riparare il veicolo prima dell'ispezione.", "Attendere l'offerta nei termini e valutarla; in caso di "
                   "diniego o offerta incongrua, invito alla negoziazione assistita.", "Se la negoziazione fallisce, causa "
                   "davanti al giudice di pace contro l'impresa, chiamando anche il responsabile (art. 144 d.lgs. 209/2005)."]
    a.avvertenze = ["I termini per l'offerta e per la proponibilità decorrono dalla ricezione della richiesta, non ancora inviata.",
                    "La negoziazione assistita è obbligatoria per il danno da circolazione a prescindere dal valore."]
    a.dati_mancanti = ["data di invio e ricezione della richiesta", "certificazione medica di guarigione ed eventuali postumi",
                       "luogo del sinistro (competenza territoriale)"]
    return a
