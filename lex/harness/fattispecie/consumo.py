"""Garanzia legale di conformità nella vendita di beni al consumatore (artt. 128 ss. d.lgs. 206/2005, testo dopo il
d.lgs. 170/2021)."""
from __future__ import annotations

import re
from datetime import date

from ..comprensione import Comprensione
from ..fatti import Fatti, data_it, euro
from ..modello import Analisi, Punto, Rif
from ..norme import piano
from .. import procedura as P
from ..termini import termine_anni, termine_mesi
from .strumenti import data_di, data_dopo, date_in, forma, frase

_ACQUISTO = (r"acquistat|comprat|acquisto|compravendit|ordinat|negozio|rivenditor|concessionari|venditore|e commerce|"
             r"sito (?:online|internet)|online|grande distribuzione|centro commerciale")
_DIFETTO = (r"difett|non funzion|guast|rott[oaie]\b|smess\w* di funzionar|si e spent|si spegne|vizi|non conform|malfunzion|"
            r"si blocca|difform|non si accende|non carica|perde acqua|si e rott|si e guastat")
_NON_CONSUMO = (r"appalt|installator|impresa edile|fornitura e posa|commissionat|locazion|conduttor|sinistro|tamponat|"
                r"per la (?:sua |mia |nostra )?(?:azienda|attivita|impresa|societa|ditta)|partita iva|tra imprese")
_PROFESSIONISTA_ACQUIRENTE = r"\b(?:s\.?r\.?l|s\.?p\.?a|s\.?n\.?c|s\.?a\.?s)\b[^.]{0,60}(?:ha acquistat|ha comprat|acquirente)"


def riconosci_garanzia_consumo(c: Comprensione, f: Fatti) -> int:
    t = piano(f.testo)
    if re.search(_NON_CONSUMO, t) or re.search(_PROFESSIONISTA_ACQUIRENTE, t):
        return 0
    if not (re.search(_ACQUISTO, t) and re.search(_DIFETTO, t)):
        return 0
    return 5 if f.ha("consumatore") or re.search(r"garanzi|venditor|negozi|rivenditor|concessionari|sostituzion|riparazion|"
                                                   r"rimborso|restituzion del prezzo|reso", t) else 0


def _consegna(f: Fatti) -> date | None:
    return (data_dopo(f, r"(?:consegnat|ricevut|ritirat)\w*") or data_di(f, r"consegn|ritirat|ricevut")
            or data_di(f, r"acquist|comprat|ordinat"))


def analizza_garanzia_consumo(c: Comprensione, f: Fatti) -> Analisi:
    a = Analisi("garanzia_conformita", "consumatori — vendita di beni", forma=forma(c))
    t = piano(f.testo)
    consegna = _consegna(f)
    successive = [d for d in date_in(frase(f, _DIFETTO)) if not consegna or d > consegna]
    manifestato = successive[0] if successive else None
    prezzo = max((i.valore for i in f.importi), default=None)
    a.valore = prezzo
    usato = bool(re.search(r"\busat[oaie]\b|di seconda mano|ricondizionat", t))
    a.capito = ["Vendita di un bene " + ("usato " if usato else "") + "da un venditore professionale a un consumatore"
                + (f", prezzo {euro(prezzo)}" if prezzo else "") + (f", consegna il {data_it(consegna)}" if consegna else "")
                + "; difetto" + (f" manifestato il {data_it(manifestato)}" if manifestato else " lamentato") + "."]
    a.rimedio = ("richiesta scritta al venditore di riparazione o sostituzione gratuita; in subordine riduzione del prezzo o "
                 "risoluzione del contratto")
    a.inquadramento = [
        Punto("Si applica la garanzia legale di conformità del codice del consumo: riguarda i contratti di vendita conclusi "
              "tra consumatore e venditore, e il bene deve essere conforme al contratto.",
              [Rif("dlgs206:128", "contratti di vendita conclusi tra consumatore e venditore"),
               Rif("dlgs206:129", "Per essere conforme al contratto di vendita")]),
        Punto("Il venditore risponde di qualsiasi difetto di conformità esistente alla consegna che si manifesta entro due "
              "anni da tale momento.", [Rif("dlgs206:133", "si manifesta entro due anni da tale momento")]),
        Punto("Se il difetto si manifesta entro un anno dalla consegna si presume, salvo prova contraria, che esistesse già "
              "alla consegna: la prova contraria tocca al venditore.",
              [Rif("dlgs206:135", "si manifesta entro un anno dal momento in cui il bene e' stato consegnato")]),
        Punto("Il testo vigente non prevede più un termine di decadenza per denunciare il difetto: la riparazione o la "
              "sostituzione vanno fatte entro un tempo ragionevole da quando il venditore è stato informato, quindi conviene "
              "informarlo subito per iscritto. Il nuovo regime si applica ai contratti conclusi dal 1° gennaio 2022.",
              [Rif("dlgs206:135ter", "dal momento in cui il venditore e' stato informato dal consumatore del difetto di conformita'"),
               Rif("dlgs206:135", "si applica ai contratti conclusi successivamente a tale data")]),
    ]
    a.conclusione = [
        Punto("Il consumatore sceglie fra riparazione e sostituzione, salvo che il rimedio scelto sia impossibile o "
              "sproporzionato; sono gratuite, entro un tempo ragionevole e senza notevoli inconvenienti.",
              [Rif("dlgs206:135bis", "il consumatore puo' scegliere tra riparazione e sostituzione"),
               Rif("dlgs206:135ter", "a titolo gratuito")]),
        Punto("Può chiedere la riduzione proporzionale del prezzo o la risoluzione se il venditore non ripara né sostituisce, "
              "se il difetto ricompare, se è così grave da giustificarle subito o se il venditore ha dichiarato che non "
              "rimedierà; la risoluzione non spetta per un difetto di lieve entità.",
              [Rif("dlgs206:135bis", "riduzione proporzionale del prezzo o alla risoluzione del contratto di vendita"),
               Rif("dlgs206:135bis", "solo di lieve entita'")]),
        Punto("La risoluzione si esercita con una dichiarazione al venditore; il bene si restituisce a spese del venditore, "
              "che rimborsa il prezzo.",
              [Rif("dlgs206:135quater", "mediante una dichiarazione diretta al venditore"),
               Rif("dlgs206:135quater", "il venditore rimborsa al consumatore il prezzo pagato")]),
    ]
    a.termini = []
    if consegna:
        due = termine_anni(consegna, 2)
        ventisei = termine_mesi(consegna, 26, sospensione_feriale=False, sostanziale=True)
        a.termini.append(Punto(f"Il difetto deve manifestarsi entro il {data_it(due)} (due anni dalla consegna del "
                               f"{data_it(consegna)})" + (f": qui si è manifestato il {data_it(manifestato)}, nel termine."
                                                          if manifestato and manifestato <= due else "."),
                               [Rif("dlgs206:133", "si manifesta entro due anni da tale momento")]))
        if manifestato and manifestato > due:
            a.avvertenze.append(f"Il difetto si è manifestato il {data_it(manifestato)}, oltre i due anni dalla consegna: la "
                                "garanzia legale del codice del consumo non copre più il bene.")
        a.termini.append(Punto(f"L'azione per i difetti non dolosamente occultati si prescrive il {data_it(ventisei)} (ventisei "
                               "mesi dalla consegna); il consumatore convenuto per il pagamento può sempre far valere i rimedi.",
                               [Rif("dlgs206:133", "ventisei mesi dalla consegna del bene")]))
        if f.oggi and ventisei < f.oggi:
            a.avvertenze.append(f"Il termine di prescrizione di ventisei mesi è scaduto il {data_it(ventisei)}: l'azione è "
                                "prescritta, salvo atti interruttivi da verificare.")
    else:
        a.termini.append(Punto("Responsabilità del venditore per i difetti che si manifestano entro due anni dalla consegna; "
                               "prescrizione dell'azione in ventisei mesi dalla consegna.",
                               [Rif("dlgs206:133", "si manifesta entro due anni da tale momento"),
                                Rif("dlgs206:133", "ventisei mesi dalla consegna del bene")]))
        a.dati_mancanti.append("data di consegna del bene (da essa decorrono i due anni e i ventisei mesi)")
    if usato:
        a.avvertenze.append("Bene usato: le parti possono aver ridotto la durata della responsabilità e la prescrizione fino a "
                            "un anno; controllare il contratto o lo scontrino.")
        a.termini.append(Punto("Per i beni usati le parti possono limitare responsabilità e prescrizione a non meno di un anno.",
                               [Rif("dlgs206:133", "non inferiore ad un anno")]))
    a.procedibilita = [Punto("Per i contratti fra professionisti e consumatori la negoziazione assistita per il pagamento di "
                             "somme non è condizione di procedibilità; la vendita non è fra le materie di mediazione "
                             "obbligatoria dell'art. 5, comma 1, d.lgs. 28/2010.",
                             [Rif("dl132:3", "contratti conclusi tra professionisti e consumatori"),
                              Rif("dlgs28:5", "e' tenuto preliminarmente a esperire il procedimento di mediazione")])]
    a.competenza = [Punto("Foro del consumatore: per la causa resta competente il giudice del luogo di residenza o domicilio "
                          "elettivo del consumatore; è vessatoria la clausola che fissa un foro diverso.",
                          [Rif("dlgs206:33", "residenza o domicilio elettivo del consumatore")])]
    if prezzo:
        giudice, punti = P.giudice_per_valore(prezzo)
        a.competenza += punti
        a.giudice = giudice
    a.cosa_fare = ["Inviare subito al venditore (non al produttore) PEC o raccomandata con la descrizione del difetto e la "
                   "scelta fra riparazione e sostituzione, mettendo il bene a sua disposizione.",
                   "Conservare scontrino o fattura, documento di consegna, foto e corrispondenza.",
                   "Se il venditore non provvede in un tempo ragionevole: dichiarazione di riduzione del prezzo o di "
                   "risoluzione, e in mancanza azione davanti al giudice del luogo del consumatore."]
    if not re.search(r"\bconsumator|privat|per uso personale|per casa|per la famiglia", t):
        a.dati_mancanti.append("conferma che l'acquirente ha comprato come consumatore (fuori dall'attività professionale)")
    if not frase(f, r"scontrino|fattura|ricevuta"):
        a.dati_mancanti.append("prova dell'acquisto (scontrino o fattura)")
    return a
