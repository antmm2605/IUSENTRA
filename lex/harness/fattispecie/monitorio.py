"""Procedimento monitorio: ricorso per decreto ingiuntivo e suoi termini (artt. 633 ss. c.p.c.)."""
from __future__ import annotations

import re

from ..comprensione import Comprensione
from ..fatti import Fatti, euro
from ..modello import Analisi, Punto, Rif
from ..norme import piano
from .. import procedura as P


def riconosci_ricorso_di(c: Comprensione, f: Fatti) -> int:
    t = piano(f.testo)
    if c.atto == "ricorso per decreto ingiuntivo" and not re.search(r"oppo|contributo unificato", t) and not (
            c.tipo == "termine" and re.search(r"notificat|emess|notifica", t)):
        return 3
    return 0


def analizza_ricorso_di(c: Comprensione, f: Fatti) -> Analisi:
    a = Analisi("decreto_ingiuntivo", "monitorio", modello="MON_001")
    credito = f.importo("credito") or (f.importi[0] if f.importi else None)
    valore = credito.valore if credito else None
    a.valore = valore
    a.capito = [f"Credito di {euro(valore) if valore else '[importo da completare]'} di {f.assistita.nome or '[creditore]'} "
                f"verso {f.controparte.nome or '[debitore]'}" + (" documentato da fattura." if f.ha("fattura") else ".")]
    a.inquadramento = [
        Punto("Il decreto ingiuntivo si chiede per un credito di una somma liquida di danaro di cui si dà prova scritta.",
              [Rif("cpc:633", "somma liquida di danaro"), Rif("cpc:633", "prova scritta")]),
        Punto("Per i crediti di imprenditori relativi a somministrazioni di merci e di danaro o a prestazioni di servizi "
              "sono prova scritta anche gli estratti autentici delle scritture contabili.",
              [Rif("cpc:634", "estratti autentici delle scritture contabili")]),
        Punto("L'esecuzione provvisoria si può chiedere, fra l'altro, se il credito è fondato su cambiale, assegno o "
              "atto ricevuto da notaio, o se c'è pericolo di grave pregiudizio nel ritardo.",
              [Rif("cpc:642", "pericolo di grave pregiudizio nel ritardo")]),
    ]
    a.competenza = [Punto("Competente è il giudice di pace o il tribunale che sarebbe competente per la domanda proposta "
                          "in via ordinaria.", [Rif("cpc:637", "competente per la domanda proposta in via ordinaria")])]
    if valore:
        giudice, punti = P.giudice_per_valore(valore)
        a.competenza += punti
        citta, foro = P.foro_convenuto(f)
        a.competenza += foro
        a.giudice = P.ufficio(giudice, citta) if giudice else giudice
        if a.giudice:
            a.competenza.append(Punto("Per i crediti pecuniari liquidi concorre anche il domicilio del creditore, dove "
                                      "l'obbligazione deve eseguirsi.", [Rif("cc:1182", "domicilio che il creditore ha al tempo della scadenza"),
                                                                         Rif("cpc:20", "deve eseguirsi l'obbligazione")]))
    a.procedibilita = [Punto("Né mediazione né negoziazione assistita sono condizioni di procedibilità del ricorso per "
                             "decreto ingiuntivo: entrambe le discipline escludono i procedimenti per ingiunzione.",
                             [Rif("dl132:3", "procedimenti per ingiunzione, inclusa l'opposizione"),
                              Rif("dlgs28:5", "procedimenti per ingiunzione, inclusa l'opposizione")])]
    a.termini = [
        Punto("Il decreto va notificato entro sessanta giorni dalla pronuncia (novanta se all'estero), altrimenti diventa "
              "inefficace.", [Rif("cpc:644", "sessanta giorni")]),
        Punto("Il debitore può proporre opposizione entro quaranta giorni dalla notificazione.",
              [Rif("cpc:641", "quaranta giorni")]),
    ]
    a.conclusione = [Punto(f"Ricorso per decreto ingiuntivo al {a.giudice or 'giudice competente per valore'}"
                           + (f" per {euro(valore)}" if valore else "") + ", oltre interessi e spese; richiesta di provvisoria "
                           "esecuzione solo se ne ricorrono i presupposti.", [Rif("cpc:633", "somma liquida di danaro"),
                                                                              Rif("cpc:637", "competente per la domanda proposta in via ordinaria")])]
    a.cosa_fare = ["Allegare fattura ed estratto autentico delle scritture contabili (o altra prova scritta).",
                   "Calcolare il contributo unificato (ridotto alla metà per il procedimento d'ingiunzione).",
                   "Annotare il termine di sessanta giorni per la notificazione del decreto."]
    if c.tipo == "redazione":
        from ..bozze import ricorso_generico

        a.bozza = ricorso_generico(
            "Ricorso per decreto ingiuntivo (artt. 633 ss. c.p.c.)", a.giudice, f,
            "ingiunzione di pagamento" + (f" di {euro(valore)}" if valore else ""),
            ["Il credito è liquido, certo ed esigibile e risulta da prova scritta (art. 633 c.p.c.): fattura n. [da completare] "
             "ed estratto autentico delle scritture contabili (art. 634 c.p.c.).",
             "Competenza: art. 637 c.p.c. in relazione al valore e ai fori degli artt. 19 e 20 c.p.c.",
             "[Eventuale] Esecuzione provvisoria: presupposti dell'art. 642 c.p.c. [da completare]."],
            f"ingiungere a {f.controparte.nome or '[debitore]'} di pagare entro quaranta giorni dalla notificazione la somma di "
            + (euro(valore) if valore else "[da completare]") + ", oltre interessi e spese della procedura, con l'avvertimento "
            "che entro lo stesso termine può proporre opposizione.", "fattura, estratto autentico, solleciti.",
            "artt. 633, 634, 637 e 641 c.p.c.")
    return a


def riconosci_notifica_di(c: Comprensione, f: Fatti) -> int:
    t = piano(f.testo)
    return 3 if "decreto ingiuntivo" in t and re.search(r"entro quan\w* va notificat|notificar\w* (?:il decreto|entro)|termine per (?:la )?notific", t) else 0


def analizza_notifica_di(c: Comprensione, f: Fatti) -> Analisi:
    a = Analisi("notifica_decreto_ingiuntivo", "monitorio")
    a.conclusione = [Punto("Il decreto ingiuntivo va notificato entro sessanta giorni dalla pronuncia, novanta se la "
                           "notificazione si fa all'estero; altrimenti diventa inefficace.", [Rif("cpc:644", "sessanta giorni")])]
    return a


# ------------------------------------------------------------------- opposizione a decreto ingiuntivo
def riconosci_opposizione_di(c: Comprensione, f: Fatti) -> int:
    return 5 if c.atto == "opposizione a decreto ingiuntivo" or (
        re.search(r"opposizion", piano(f.testo)) and re.search(r"decreto ingiuntivo n\.", piano(f.testo))) else 0


def analizza_opposizione_di(c: Comprensione, f: Fatti) -> Analisi:
    from ..termini import data_breve, termine_anni, termine_giorni
    from .strumenti import date_in, forma

    t = piano(f.testo)
    a = Analisi("opposizione_decreto_ingiuntivo", "monitorio", modello="MON_011", forma=forma(c))
    m_not = re.search(r"(\d{1,2}/\d{1,2}/\d{4})\s*-\s*viene notificato[^.]{0,80}decreto ingiuntivo", t) or re.search(
        r"decreto ingiuntivo[^.]{0,80}notificat\w*[^.]{0,20}(\d{1,2}/\d{1,2}/\d{4})", t)
    notifica = date_in(m_not.group(1))[0] if m_not else None
    m_uff = re.search(r"del (tribunale di [a-z]+)", t)
    ufficio = m_uff.group(1).title() if m_uff else "ufficio che ha emesso il decreto"
    fatture = [(m.group(2), date_in(m.group(1))[0], float(m.group(3).replace(".", "")))
               for m in re.finditer(r"(\d{1,2}/\d{1,2}/\d{4})\s*-(?:(?!\d{1,2}/\d{1,2}/\d{4}).){0,160}?fattura n\.\s*(\d+) di euro ([\d.]+)", t)]
    scadenze = {m.group(1): date_in(m.group(2))[0] for m in re.finditer(r"fattura n\.\s*(\d+)(?:(?!\d{1,2}/\d{1,2}/\d{4}).){0,120}?scadenz\w*[^0-9]{0,20}(\d{1,2}/\d{1,2}/\d{4})", t)}
    m_ing = re.search(r"ingiunge il pagamento di euro ([\d.]+)|per euro ([\d.]+) \(fatture", t)
    ingiunto = float((m_ing.group(1) or m_ing.group(2)).replace(".", "")) if m_ing else sum(v for *_, v in fatture)
    m_pag = re.search(r"paga a [^.]{0,40}?euro ([\d.]+)[^.]{0,80}?fattura n\.\s*(\d+)", t)
    deposito = (date_in((re.search(r"(\d{1,2}/\d{1,2}/\d{4})\s*-[^.]{0,40}deposita ricorso", t) or [None, ""])[1] or "") or [None])[0]
    a.rimedio = "atto di citazione in opposizione a decreto ingiuntivo (artt. 641 e 645 c.p.c.)"
    a.giudice = ufficio
    a.inquadramento = [
        Punto("L'opposizione si propone entro quaranta giorni dalla notificazione, con atto di citazione davanti all'ufficio "
              "giudiziario al quale appartiene il giudice che ha emesso il decreto.",
              [Rif("cpc:641", "quaranta giorni"), Rif("cpc:645", "ufficio giudiziario al quale appartiene il giudice")]),
    ]
    prescritte = []
    for n, d, v in fatture:
        sc = scadenze.get(n)
        if sc and deposito and termine_anni(sc, 10) < deposito and re.search(r"mai chiesto per iscritto|mai riconosciut", t):
            prescritte.append((n, sc, v))
            a.inquadramento.append(Punto(
                f"La fattura n. {n} ({euro(v)}) scadeva il {sc.strftime('%d/%m/%Y')}: la prescrizione decorre dal giorno in cui "
                f"il diritto può essere fatto valere e il termine ordinario è di dieci anni, maturati il "
                f"{termine_anni(sc, 10).strftime('%d/%m/%Y')}, prima del ricorso e senza atti interruttivi: si eccepisce la prescrizione.",
                [Rif("cc:2935", "dal giorno in cui il diritto puo essere fatto valere"), Rif("cc:2946", "dieci anni")]))
    pagato = None
    if m_pag:
        pagato = (float(m_pag.group(1).replace(".", "")), m_pag.group(2))
        a.inquadramento.append(Punto(
            f"Chi ha più debiti verso la stessa persona può dichiarare, quando paga, quale intende soddisfare: il pagamento di "
            f"{euro(pagato[0])} va imputato alla fattura n. {pagato[1]}, come da causale.", [Rif("cc:1193", "dichiarare")]))
    if notifica:
        lim = termine_giorni(notifica, 40)
        a.termini = [Punto(f"Decreto notificato il {data_breve(notifica)}: opposizione entro {data_breve(lim)} (quaranta "
                           "giorni, termine processuale).", [Rif("cpc:641", "quaranta giorni")])]
        if lim >= f.oggi:
            a.avvertenze.append("Il termine è ancora aperto: l'opposizione tardiva (art. 650 c.p.c.) non serve.")
    dovuto = ingiunto - sum(v for *_, v in prescritte) - (pagato[0] if pagato else 0)
    a.conclusione = [Punto(f"Somma ingiunta {euro(ingiunto)}; non dovuti {euro(ingiunto - dovuto)}"
                           + (f" (fattura prescritta e pagamento)" if prescritte and pagato else "") +
                           f"; somma effettivamente dovuta in linea capitale {euro(dovuto)}. Chiedere la revoca del decreto e "
                           "l'accertamento della minor somma, senza contestare le forniture non contestabili.",
                           [Rif("cpc:645", "ufficio giudiziario al quale appartiene il giudice")])]
    a.procedibilita = [Punto("La negoziazione assistita non si applica ai procedimenti per ingiunzione, inclusa "
                             "l'opposizione; la mediazione, se la materia la richiede, non si applica fino alla pronuncia sulle "
                             "istanze di provvisoria esecuzione.", [Rif("dl132:3", "procedimenti per ingiunzione, inclusa l'opposizione"),
                                                                   Rif("dlgs28:5", "procedimenti per ingiunzione, inclusa l'opposizione")])]
    a.dati_mancanti = ["codici fiscali e PEC delle parti", "data dell'udienza nel rispetto dei termini a comparire"]
    if c.tipo == "redazione":
        from ..bozze import ricorso_generico

        a.bozza = ricorso_generico(
            "Atto di citazione in opposizione a decreto ingiuntivo (artt. 641 e 645 c.p.c.)", ufficio.upper(), f,
            "revoca del decreto ingiuntivo e accertamento della minor somma dovuta",
            ["Tempestività: opposizione proposta nei quaranta giorni davanti all'ufficio che ha emesso il decreto (artt. 641 e "
             "645 c.p.c.).", "Prescrizione decennale della fattura scaduta da oltre dieci anni (artt. 2935 e 2946 c.c.).",
             "Pagamento parziale imputato dal debitore alla fattura indicata in causale (art. 1193 c.c.).",
             f"Somma dovuta in linea capitale: {euro(dovuto)}."],
            "revocare il decreto ingiuntivo; dichiarare prescritto il credito della fattura indicata e parzialmente estinto per "
            f"pagamento quello della fattura saldata in parte; accertare che l'opponente deve la sola somma di {euro(dovuto)}; "
            "con vittoria di spese.", "decreto notificato, fatture, contabile del bonifico.",
            "artt. 163, 641 e 645 c.p.c.")
    return a
