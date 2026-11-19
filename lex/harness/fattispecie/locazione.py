"""Fattispecie di locazione: sfratto per morosità, sanatoria, cause di locazione (artt. 447-bis e 657 ss. c.p.c.)."""
from __future__ import annotations

import re

from ..comprensione import Comprensione
from ..fatti import Fatti, euro
from ..modello import Analisi, Punto, Rif
from ..norme import piano

_NUM = {"una": 1, "due": 2, "tre": 3, "quattro": 4, "cinque": 5, "sei": 6, "sette": 7, "otto": 8, "nove": 9, "dieci": 10}


def riconosci_sfratto(c: Comprensione, f: Fatti) -> int:
    t = piano(f.testo)
    if c.atto == "intimazione di sfratto" or (f.ha("locazione") and f.ha("morosita") and not re.search(r"sanar|sanator|termine di grazia", t)):
        return 3
    return 0


def analizza_sfratto(c: Comprensione, f: Fatti) -> Analisi:
    a = Analisi("sfratto_morosita", "locazione", modello="LOC_001")
    t = piano(f.testo)
    canone = f.importo("canone")
    m = re.search(r"(\d+|" + "|".join(_NUM) + r")\s+(?:mensilit|canoni|mesi)", t)
    mesi = (int(m.group(1)) if m.group(1).isdigit() else _NUM[m.group(1)]) if m else None
    luogo = f.luogo_immobile
    a.capito = [f"Locazione {'abitativa' if f.ha('abitativo') else '[uso da completare]'}"
                + (f" di un immobile in {luogo}" if luogo else "") + "; conduttore moroso"
                + (f" per {mesi} mensilità" if mesi else "") + (f" da {euro(canone.valore)}" if canone else "") + "."]
    if canone and mesi:
        a.valore = canone.valore * mesi
        a.capito.append(f"Canoni scaduti: {euro(a.valore)}.")
    a.inquadramento = [
        Punto("Il locatore può intimare lo sfratto per mancato pagamento del canone alle scadenze e citare il conduttore "
              "per la convalida; con lo stesso atto può chiedere l'ingiunzione per i canoni scaduti.",
              [Rif("cpc:658", "mancato pagamento del canone")]),
        Punto("Nella locazione abitativa il mancato pagamento del canone decorsi venti giorni dalla scadenza è motivo di "
              "risoluzione.", [Rif("l392:5", "decorsi venti giorni dalla scadenza")]),
        Punto("Il conduttore abitativo può sanare la morosità in udienza; il giudice può assegnare un termine non superiore "
              "a novanta giorni (termine di grazia).", [Rif("l392:55", "non superiore a giorni novanta")]),
    ]
    a.competenza = [Punto("È competente il tribunale del luogo in cui si trova la cosa locata"
                          + (f" (qui: Tribunale di {luogo})" if luogo else "") + ".",
                          [Rif("cpc:661", "luogo in cui si trova la cosa locata")])]
    a.giudice = f"Tribunale di {luogo}" if luogo else "Tribunale del luogo dell'immobile"
    a.procedibilita = [Punto("La mediazione obbligatoria in materia di locazione non si applica al procedimento per "
                             "convalida di sfratto fino al mutamento del rito; si applica dopo, se il giudizio prosegue "
                             "nel merito.", [Rif("dlgs28:5", "convalida di licenza o sfratto")])]
    a.rito = [Punto("Procedimento per convalida di sfratto (artt. 657 ss. c.p.c.); se c'è opposizione, il giudizio prosegue "
                    "con il rito delle locazioni.", [Rif("cpc:658", "mancato pagamento del canone"),
                                                      Rif("cpc:447bis", "locazione")])]
    a.conclusione = [Punto(f"Intimazione di sfratto per morosità con contestuale citazione per la convalida davanti al "
                           f"{a.giudice}, con domanda di ingiunzione per i canoni scaduti"
                           + (f" ({euro(a.valore)})" if a.valore else "") + ".",
                           [Rif("cpc:658", "mancato pagamento del canone"), Rif("cpc:661", "luogo in cui si trova la cosa locata")])]
    a.cosa_fare = ["Allegare contratto registrato, prospetto dei canoni non pagati e diffide.",
                   "Fissare l'udienza rispettando i termini a comparire del procedimento di convalida.",
                   "Prepararsi alla possibile sanatoria in udienza (termine di grazia fino a 90 giorni)."]
    if c.tipo == "redazione":
        from ..bozze import ricorso_generico

        a.bozza = ricorso_generico(
            "Atto di intimazione di sfratto per morosità e contestuale citazione per la convalida (artt. 658 ss. c.p.c.)",
            a.giudice, f, "convalida di sfratto per morosità e ingiunzione di pagamento dei canoni scaduti",
            ["Contratto di locazione registrato il [da completare], canone mensile " + (euro(canone.valore) if canone else "[da completare]") + ".",
             "Morosità: canoni non pagati " + (f"({mesi} mensilità)" if mesi else "[da completare]") + "; motivo di risoluzione (art. 5 l. 392/1978).",
             "Si intima lo sfratto e si cita il conduttore a comparire all'udienza del [da completare] per la convalida."],
            "convalidare lo sfratto e fissare la data dell'esecuzione; ingiungere il pagamento dei canoni scaduti e a scadere "
            "fino all'esecuzione; con vittoria di spese.", "contratto registrato, prospetto canoni, diffide.",
            "artt. 657, 658 e 660 c.p.c.")
    return a


def riconosci_sanatoria(c: Comprensione, f: Fatti) -> int:
    t = piano(f.testo)
    return 3 if re.search(r"sanar|sanator|termine di grazia", t) and re.search(r"moros|conduttor|canon", t) else 0


def analizza_sanatoria(c: Comprensione, f: Fatti) -> Analisi:
    a = Analisi("sanatoria_morosita", "locazione")
    a.capito = ["Sanatoria della morosità del conduttore nella locazione abitativa."]
    a.conclusione = [Punto("Sì: nella locazione abitativa il conduttore può sanare la morosità in udienza pagando canoni, "
                           "interessi e spese; se ci sono comprovate difficoltà il giudice può assegnare un termine non "
                           "superiore a novanta giorni. La sanatoria è ammessa per non più di tre volte in quattro anni.",
                           [Rif("l392:55", "non superiore a giorni novanta"), Rif("l392:55", "tre volte nel corso di un quadriennio")])]
    return a


def riconosci_cause_locazione(c: Comprensione, f: Fatti) -> int:
    t = piano(f.testo)
    if f.ha("locazione") and re.search(r"deposito cauzional|cauzion|restituzion|mediazione|competent|giudice", t) and not f.ha("morosita"):
        return 2
    return 0


def analizza_cause_locazione(c: Comprensione, f: Fatti) -> Analisi:
    a = Analisi("causa_locazione", "locazione")
    a.capito = ["Controversia in materia di locazione" + (f" per {euro(f.importi[0].valore)}" if f.importi else "") + "."]
    a.procedibilita = [Punto("Mediazione obbligatoria: la locazione è fra le materie dell'art. 5, comma 1, d.lgs. 28/2010; "
                             "per questo la negoziazione assistita non è condizione di procedibilità.",
                             [Rif("dlgs28:5", "locazione"), Rif("dl132:3", "articolo 5, comma 1-bis")])]
    a.rito = [Punto("Rito delle locazioni: le controversie in materia di locazione di immobili urbani seguono le norme del "
                    "rito del lavoro in quanto applicabili; sono nulle le clausole di deroga alla competenza.",
                    [Rif("cpc:447bis", "controversie in materia di locazione e di comodato di immobili urbani"),
                     Rif("cpc:447bis", "nulle le clausole di deroga alla competenza")])]
    a.competenza = [Punto("Per le cause in materia di locazione di immobili è competente il giudice del luogo dove è posto "
                          "l'immobile; il giudice è il tribunale, perché il giudice di pace è competente solo per le cause "
                          "su beni mobili e per le materie elencate dall'art. 7 c.p.c.",
                          [Rif("cpc:21", "locazione e comodato di immobili"), Rif("cpc:21", "luogo dove e posto l'immobile"),
                           Rif("cpc:7", "beni mobili di valore non superiore"),
                           Rif("cpc:9", "competente per tutte le cause che non sono di competenza di altro giudice")])]
    a.conclusione = [Punto("Prima della causa va avviata la mediazione; poi ricorso nel rito delle locazioni al tribunale "
                           "del luogo dell'immobile.", [Rif("dlgs28:5", "locazione"), Rif("cpc:447bis", "locazione")])]
    return a
