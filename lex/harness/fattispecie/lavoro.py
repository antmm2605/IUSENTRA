"""Fattispecie di lavoro: crediti retributivi e impugnazione del licenziamento (rito del lavoro, artt. 409 ss. c.p.c.)."""
from __future__ import annotations

import re

from ..comprensione import Comprensione
from ..fatti import Fatti, euro
from ..modello import Analisi, Punto, Rif
from ..norme import piano
from .. import procedura as P
from ..termini import data_breve, termine_giorni


def _comuni(a: Analisi, f: Fatti) -> None:
    luogo = f.luogo_lavoro or f.residenza_convenuto
    a.competenza = [
        Punto("Giudice: il tribunale in funzione di giudice del lavoro, per le controversie relative a rapporti di lavoro "
              "subordinato privato.", [Rif("cpc:409", "rapporti di lavoro subordinato privato"), Rif("cpc:413", "tribunale in funzione di giudice del lavoro")]),
        Punto("Foro: è competente il giudice nella cui circoscrizione è sorto il rapporto ovvero si trova l'azienda o la "
              "dipendenza alla quale è addetto il lavoratore" + (f" (qui: {luogo})" if luogo else " [luogo da completare]") + ".",
              [Rif("cpc:413", "e sorto il rapporto ovvero si trova l'azienda")]),
    ]
    a.giudice = (P.ufficio("Tribunale", luogo) + " in funzione di giudice del lavoro") if luogo else "Tribunale in funzione di giudice del lavoro"
    a.procedibilita = [Punto("Il tentativo di conciliazione è facoltativo: chi intende agire «può promuovere» il tentativo "
                             "previsto dall'art. 410 c.p.c.; mediazione e negoziazione assistita non sono condizioni di "
                             "procedibilità per queste controversie.", [Rif("cpc:410", "puo promuovere")])]
    a.rito = [Punto("Rito del lavoro: la domanda si propone con ricorso depositato nella cancelleria del giudice "
                    "competente.", [Rif("cpc:414", "si propone con ricorso")])]


def riconosci_crediti(c: Comprensione, f: Fatti) -> int:
    t = piano(f.testo)
    if f.ha("licenziamento"):
        return 0
    if re.search(r"differenz\w* retributiv|retribuz|stipend|tfr|trattamento di fine rapporto|straordinar", t) and (
            f.ha("lavoro_subordinato") or "lavor" in t):
        return 3
    return 0


def analizza_crediti(c: Comprensione, f: Fatti) -> Analisi:
    a = Analisi("crediti_lavoro", "lavoro", modello="LAV_005")
    credito = f.importo("retribuzione") or (f.importi[0] if f.importi else None)
    a.capito = [f"Lavoratore {f.assistita.nome or '[da completare]'} contro il datore {f.controparte.nome or '[da completare]'}"
                + (f"; credito indicato {euro(credito.valore)}" if credito else "; importo del credito [da completare]") + "."]
    _comuni(a, f)
    a.inquadramento = [
        Punto("Sui crediti di lavoro il giudice, oltre agli interessi nella misura legale, determina il maggior danno per "
              "la diminuzione di valore del credito (rivalutazione).", [Rif("cpc:429", "il maggior danno eventualmente subito dal lavoratore")]),
        Punto("Prescrizione: si prescrivono in cinque anni le somme da pagare periodicamente ad anno o in termini più "
              "brevi, come le retribuzioni.", [Rif("cc:2948", "si prescrivono in cinque anni")]),
    ]
    a.conclusione = [Punto(f"Ricorso al {a.giudice} nel rito del lavoro per la condanna del datore al pagamento "
                           + (f"di {euro(credito.valore)}" if credito else "delle differenze retributive") +
                           ", oltre interessi legali e rivalutazione monetaria.",
                           [Rif("cpc:414", "si propone con ricorso"), Rif("cpc:429", "interessi nella misura legale")])]
    a.cosa_fare = ["Raccogliere buste paga, contratto, CCNL applicato e conteggi delle differenze.",
                   "Verificare la prescrizione per ogni mensilità (cinque anni).",
                   "Valutare il tentativo di conciliazione facoltativo (art. 410 c.p.c.) prima del ricorso."]
    if c.tipo == "redazione":
        from ..bozze import ricorso_generico

        a.bozza = ricorso_generico(
            "Ricorso ex art. 414 c.p.c.", a.giudice, f,
            "condanna al pagamento di differenze retributive" + (f" per {euro(credito.valore)}" if credito else ""),
            ["Rapporto di lavoro subordinato, mansioni, livello e CCNL applicato: [da completare].",
             "Differenze dovute e conteggi analitici: [da completare] (allegati).",
             "Interessi legali e rivalutazione monetaria ai sensi dell'art. 429, comma 3, c.p.c."],
            "condannare il resistente al pagamento in favore del ricorrente della somma di "
            + (euro(credito.valore) if credito else "[da completare]") + ", oltre interessi legali e rivalutazione monetaria "
            "dalle singole scadenze al saldo; con vittoria di spese.",
            "contratto di lavoro, buste paga, CCNL, conteggi, corrispondenza.", "artt. 409, 413 e 414 c.p.c.")
    return a


def riconosci_licenziamento(c: Comprensione, f: Fatti) -> int:
    return 3 if f.ha("licenziamento") and (c.tipo in {"redazione", "parere", "termine"}) else 0


def _data_ricezione_licenziamento(f: Fatti):
    from .strumenti import date_in, frase

    x = frase(f, r"licenzia\w*[^.]{0,200}(?:consegnat|ricev|comunicat|sottoscritt)|(?:consegnat|ricev)\w*[^.]{0,80}licenzia")
    d = date_in(x)
    return d[-1] if d else (f.eventi[0].data if f.eventi else None)


def analizza_licenziamento(c: Comprensione, f: Fatti) -> Analisi:
    from .strumenti import data_di, date_in, forma, frase

    t = piano(f.testo)
    a = Analisi("impugnazione_licenziamento", "lavoro", modello="LAV_003", forma=forma(c))
    _comuni(a, f)
    ricezione = _data_ricezione_licenziamento(f)
    x_imp = frase(f, r"impugna\w*[^.]{0,60}(?:pec|raccomandat|lettera)|(?:pec|raccomandat)[^.]{0,60}impugna")
    impugnazione = (date_in(x_imp) or [None])[0] if x_imp and not re.search(r"\bnon\b|nessun", piano(x_imp)) else None
    assunzione = data_di(f, r"assunt\w*")
    m_dip = re.search(r"(\d+)\s+dipendenti", t)
    dipendenti = int(m_dip.group(1)) if m_dip else None
    m_ret = re.search(r"retribuzione[^.]{0,60}?(?:euro\s*)?([\d.]+(?:,\d+)?)\s*(?:euro)?", t)
    retribuzione = float(m_ret.group(1).replace(".", "").replace(",", ".")) if m_ret else None
    gmo = bool(re.search(r"giustificato motivo oggettivo|\bgmo\b|soppressione|riorganizzazione", t))
    a.capito = [f"Licenziamento {'per giustificato motivo oggettivo' if gmo else ('per giusta causa' if 'giusta causa' in t else '')} "
                f"ricevuto il {ricezione.strftime('%d/%m/%Y') if ricezione else '[da completare]'}"
                + (f"; assunzione il {assunzione.strftime('%d/%m/%Y')}" if assunzione else "")
                + (f"; {dipendenti} dipendenti" if dipendenti else "")
                + (f"; impugnazione scritta del {impugnazione.strftime('%d/%m/%Y')}" if impugnazione else "; nessuna impugnazione scritta") + "."]
    a.termini = [
        Punto("Il licenziamento va impugnato, a pena di decadenza, entro sessanta giorni dalla ricezione della sua "
              "comunicazione in forma scritta, con qualsiasi atto scritto anche extragiudiziale; poi entro centottanta giorni "
              "va depositato il ricorso o chiesta la conciliazione o l'arbitrato. La regola vale per tutti i casi di invalidità "
              "del licenziamento.", [Rif("l604:6", "entro sessanta giorni dalla ricezione della sua comunicazione"),
                                     Rif("l604:6", "centottanta giorni"), Rif("l183:32", "invalidita del licenziamento")]),
    ]
    scaduto = False
    if ricezione:
        lim = termine_giorni(ricezione, 60, sostanziale=True)
        a.termini.append(Punto(f"Ricezione del {data_breve(ricezione)}: impugnazione stragiudiziale entro {data_breve(lim)} "
                               "(decadenza sostanziale, senza sospensione feriale).",
                               [Rif("l604:6", "entro sessanta giorni dalla ricezione della sua comunicazione")]))
        scaduto = lim < f.oggi and not impugnazione
        if impugnazione and impugnazione <= lim:
            dep = termine_giorni(impugnazione, 180, sostanziale=True)
            a.termini.append(Punto(f"Impugnazione tempestiva del {data_breve(impugnazione)}: ricorso da depositare entro "
                                   f"{data_breve(dep)} (centottanta giorni, decadenza sostanziale).", [Rif("l604:6", "centottanta giorni")]))
        elif not impugnazione and not scaduto:
            a.avvertenze.append(f"Inviare subito l'impugnazione scritta (PEC o raccomandata A/R) entro il {lim.strftime('%d/%m/%Y')}; "
                                "il termine di centottanta giorni per il ricorso decorre dall'impugnazione, non ancora inviata.")
    if scaduto:
        a.forma = "parere (consulenza)"
        a.rimedio = ("nessuna impugnazione allo stato: la decadenza è maturata; parere scritto al cliente e azione per i soli "
                     "crediti di fine rapporto (TFR, ultime retribuzioni, ferie)")
        a.conclusione = [Punto("Il termine per impugnare è scaduto: una lettera inviata oggi e il ricorso per la reintegrazione "
                               "sarebbero respinti per decadenza, che non si interrompe (una telefonata al sindacato non è atto "
                               "scritto). Restano i crediti non legati all'illegittimità del recesso, a partire dal TFR.",
                               [Rif("l604:6", "entro sessanta giorni dalla ricezione della sua comunicazione"),
                                Rif("cc:2964", "interruzione"), Rif("cc:2120", "trattamento di fine rapporto")])]
        a.avvertenze += ["La richiesta (impugnare oggi e chiedere la reintegra) è inadatta: va detto per iscritto al cliente.",
                         "Prima di chiudere verificare la data effettiva di ricezione e se il sindacato o il lavoratore abbiano "
                         "inviato comunicazioni scritte."]
        a.dati_mancanti = ["conferma della data di ricezione e di eventuali comunicazioni scritte del sindacato",
                           "conteggi di TFR, ferie e ultime retribuzioni"]
        return a
    if assunzione and assunzione.year >= 2015 and (assunzione.year > 2015 or assunzione.month >= 3):
        a.inquadramento.append(Punto("Lavoratore assunto a tempo indeterminato dopo il 7 marzo 2015: si applicano le tutele "
                                     "crescenti del d.lgs. 23/2015 e non l'art. 18 dello Statuto dei lavoratori.",
                                     [Rif("dlgs23:1", "a decorrere dalla data di entrata in vigore")]))
        a.inquadramento.append(Punto("Se non ricorrono gli estremi del giustificato motivo oggettivo, il giudice dichiara estinto "
                                     "il rapporto e condanna al pagamento di un'indennità non inferiore a sei e non superiore a "
                                     "trentasei mensilità dell'ultima retribuzione di riferimento per il TFR; nei casi di "
                                     "insussistenza del fatto la tutela può essere la reintegrazione con indennità fino a dodici "
                                     "mensilità (per il GMO dopo la pronuncia della Corte costituzionale indicata nella scheda, da "
                                     "leggere prima di citarla).",
                                     [Rif("dlgs23:3", "non inferiore a sei e non superiore a trentasei mensilita"),
                                      Rif("dlgs23:3", "dodici mensilita")]))
        a.rito.append(Punto("Ai licenziamenti soggetti al d.lgs. 23/2015 non si applica il rito speciale della legge 92/2012: "
                            "ricorso ordinario nel rito del lavoro.", [Rif("dlgs23:11", "non si applicano")]))
        if retribuzione:
            a.conclusione.append(Punto(f"Importi su retribuzione mensile di {euro(retribuzione)}: minimo sei mensilità "
                                       f"{euro(6 * retribuzione)}; massimo dodici mensilità con la reintegrazione "
                                       f"{euro(12 * retribuzione)}; massimo trentasei mensilità {euro(36 * retribuzione)}.",
                                       [Rif("dlgs23:3", "non inferiore a sei e non superiore a trentasei mensilita")]))
        if not re.search(r"offerta di conciliazione[^.]{0,40}ricevut", t) or "nessuna offerta" in t:
            a.inquadramento.append(Punto("Un'eventuale offerta di conciliazione del datore va valutata se arriva.",
                                         [Rif("dlgs23:6", "offerta")]))
    if gmo:
        a.inquadramento.append(Punto("Il giustificato motivo oggettivo riguarda ragioni inerenti all'attività produttiva e "
                                     "all'organizzazione del lavoro; l'onere della prova spetta al datore. Una nuova assunzione "
                                     "sulle stesse mansioni subito dopo prova contro la soppressione del posto.",
                                     [Rif("l604:3", "attivita produttiva"), Rif("l604:5", "onere della prova")]))
    a.forma = a.forma or forma(c)
    a.rimedio = ("impugnazione stragiudiziale scritta (se non già fatta) e ricorso ex art. 414 c.p.c. al tribunale in funzione "
                 "di giudice del lavoro del luogo di lavoro")
    a.conclusione.insert(0, Punto(f"Ricorso al {a.giudice} nel rito del lavoro per l'accertamento dell'illegittimità del "
                                  "licenziamento e la tutela prevista.", [Rif("cpc:414", "si propone con ricorso"),
                                                                       Rif("cpc:413", "e sorto il rapporto ovvero si trova l'azienda")]))
    a.dati_mancanti = ["codici fiscali e PEC delle parti", "retribuzione utile ai fini del TFR (busta paga)"]
    a.cosa_fare = ["Inviare o conservare la prova dell'impugnazione scritta e annotare il termine di centottanta giorni.",
                   "Chiedere l'esibizione del libro unico e del contratto del nuovo assunto; indicare i testimoni."]
    if c.tipo == "redazione":
        from ..bozze import ricorso_generico

        a.bozza = ricorso_generico(
            "Ricorso ex art. 414 c.p.c. avverso licenziamento", a.giudice, f,
            "accertamento dell'illegittimità del licenziamento e condanna alle tutele di legge",
            ["Rapporto di lavoro, mansioni, CCNL e dimensioni del datore: [da completare].",
             "Il licenziamento è stato impugnato tempestivamente (art. 6 l. 604/1966).",
             "Insussistenza del giustificato motivo oggettivo: il datore ha assunto un altro lavoratore con le stesse mansioni "
             "nello stesso reparto; l'onere della prova grava sul datore (artt. 3 e 5 l. 604/1966).",
             "Tutela: art. 3 d.lgs. 23/2015 (reintegrazione e indennità fino a dodici mensilità; in subordine indennità da sei "
             "a trentasei mensilità)."],
            "accertare l'illegittimità del licenziamento; ordinare la reintegrazione con l'indennità risarcitoria; in "
            "subordine condannare il datore all'indennità nella misura massima; con vittoria di spese.",
            "lettera di assunzione, licenziamento, impugnazione, buste paga, comunicazione obbligatoria della nuova assunzione.",
            "artt. 409, 413 e 414 c.p.c.")
    return a


def riconosci_competenza_lavoro(c: Comprensione, f: Fatti) -> int:
    t = piano(f.testo)
    return 2 if f.ha("lavoro_subordinato") and re.search(r"giudice|competen|foro|tribunale", t) else 0


def analizza_competenza_lavoro(c: Comprensione, f: Fatti) -> Analisi:
    a = Analisi("competenza_lavoro", "lavoro")
    _comuni(a, f)
    a.capito = ["Giudice competente per una controversia di lavoro subordinato"
                + (f" (luogo di lavoro: {f.luogo_lavoro})" if f.luogo_lavoro else "") + "."]
    a.conclusione = [Punto(f"È competente il {a.giudice}.", [Rif("cpc:413", "tribunale in funzione di giudice del lavoro"),
                                                         Rif("cpc:413", "e sorto il rapporto ovvero si trova l'azienda")])]
    return a
