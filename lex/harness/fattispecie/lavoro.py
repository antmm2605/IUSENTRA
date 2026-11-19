"""Fattispecie di lavoro: crediti retributivi e impugnazione del licenziamento (rito del lavoro, artt. 409 ss. c.p.c.)."""
from __future__ import annotations

import re

from ..comprensione import Comprensione
from ..fatti import Fatti, euro
from ..modello import Analisi, Punto, Rif
from ..norme import piano
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
    a.giudice = f"Tribunale di {luogo} in funzione di giudice del lavoro" if luogo else "Tribunale in funzione di giudice del lavoro"
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


def analizza_licenziamento(c: Comprensione, f: Fatti) -> Analisi:
    a = Analisi("impugnazione_licenziamento", "lavoro", modello="LAV_003")
    _comuni(a, f)
    a.capito = ["Impugnazione di un licenziamento."]
    a.termini = [
        Punto("Il licenziamento va impugnato, a pena di decadenza, entro sessanta giorni dalla ricezione della sua "
              "comunicazione in forma scritta, con qualsiasi atto scritto anche extragiudiziale.",
              [Rif("l604:6", "entro sessanta giorni dalla ricezione della sua comunicazione")]),
        Punto("L'impugnazione è inefficace se non è seguita, entro il successivo termine di centottanta giorni, dal "
              "deposito del ricorso nella cancelleria del tribunale in funzione di giudice del lavoro o dalla richiesta "
              "di conciliazione o arbitrato.", [Rif("l604:6", "centottanta giorni")]),
    ]
    data = f.eventi[0].data if f.eventi else None
    if data:
        scad = termine_giorni(data, 60, sospensione_feriale=False)
        a.termini.append(Punto(f"Licenziamento comunicato il {data_breve(data)}: impugnazione stragiudiziale entro il "
                               f"{data_breve(scad)} (sessanta giorni; termine sostanziale, senza sospensione feriale).",
                               [Rif("l604:6", "entro sessanta giorni dalla ricezione della sua comunicazione")]))
    a.conclusione = [a.termini[-1] if data else a.termini[0]]
    a.cosa_fare = ["Inviare subito l'impugnazione scritta (PEC o raccomandata) e conservarne la prova di ricezione.",
                   "Annotare il termine di 180 giorni per il deposito del ricorso o la richiesta di conciliazione.",
                   "Verificare dimensioni del datore e data di assunzione per la tutela applicabile."]
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
