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
        a.giudice = f"{giudice} di {citta}" if giudice and citta else giudice
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
