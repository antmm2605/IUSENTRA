"""Fattispecie di locazione: sfratto per morosità, sanatoria, cause di locazione (artt. 447-bis e 657 ss. c.p.c.)."""
from __future__ import annotations

import re

from ..comprensione import Comprensione
from ..fatti import Fatti, euro
from ..modello import Analisi, Punto, Rif
from ..norme import piano
from .. import procedura as P
from ..termini import data_breve

_NUM = {"una": 1, "due": 2, "tre": 3, "quattro": 4, "cinque": 5, "sei": 6, "sette": 7, "otto": 8, "nove": 9, "dieci": 10}


_DIFESA_CONDUTTORE = (r"(?:difendo|assisto|rappresento|il mio cliente(?: e)?|la mia cliente(?: e)?|per conto di) [^,.]{3,60}, "
                      r"(?:conduttor|conduttric|inquilin)|(?:siamo|sono|e) (?:il|la|l) (?:conduttor|conduttric|inquilin)\w* intimat|"
                      r"(?:il locatore|la locatrice|il proprietario|la proprietaria) (?:ci |gli |le |mi )?ha intimato[^?]{0,120}"
                      r"(?:non (?:erano|sono) dovut|vizi|difes|oppor)|(?:opporci|opporsi|difenderci) (?:alla|dalla|allo) "
                      r"(?:convalida|sfratto)")


def difesa_del_conduttore(f: Fatti) -> bool:
    """La parte assistita è il conduttore intimato: lo sfratto si subisce, non si intima."""
    return re.search(r"conduttor|conduttric|inquilin|intimat", piano(f.assistita.ruolo)) is not None or re.search(
        _DIFESA_CONDUTTORE, piano(f.testo)) is not None


def riconosci_sfratto(c: Comprensione, f: Fatti) -> int:
    t = piano(f.testo)
    if difesa_del_conduttore(f):
        return 0
    if c.atto == "intimazione di sfratto" or (f.ha("locazione") and f.ha("morosita") and not re.search(r"sanar|sanator|termine di grazia", t)):
        return 3
    return 0


def analizza_sfratto(c: Comprensione, f: Fatti) -> Analisi:
    a = Analisi("sfratto_morosita", "locazione", modello="LOC_001")
    t = piano(f.testo)
    canone = f.importo("canone")
    m_can = re.search(r"canone mensile (?:di )?(?:euro\s*)?([\d.]+)", t)
    if m_can:
        from ..fatti import Importo

        canone = Importo(float(m_can.group(1).replace(".", "")), "canone", m_can.group(0))
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
    a.giudice = P.ufficio("Tribunale", luogo) if luogo else "Tribunale del luogo dell'immobile"
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
    if re.search(r"sanar|sanator|termine di grazia", t) and re.search(r"moros|conduttor|canon", t):
        return 3
    # Conduttore intimato che chiede come difendersi da uno sfratto per morosità (abitativo).
    return 3 if difesa_del_conduttore(f) and re.search(r"sfratt", t) and re.search(r"moros|canon", t) else 0


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
    cauzione_locativa = re.search(r"deposito cauzional|cauzione", t) and not re.search(r"sequestr|cautelar|669|appalt|gara", t)
    if (f.ha("locazione") or cauzione_locativa) and re.search(r"deposito cauzional|cauzion|restituzion|mediazione|competent|giudice", t) and not f.ha("morosita"):
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


# ------------------------------------------------------------------- sfratto per locazione ad uso diverso (commerciale)
def riconosci_sfratto_commerciale(c: Comprensione, f: Fatti) -> int:
    t = piano(f.testo)
    return 5 if re.search(r"sfratt", t) and re.search(r"commercial|uso diverso|\bbar\b|negozio|ufficio", t) and re.search(
        r"termine di grazia|art\. 55|memoria|opposizion|udienza", t) else 0


def analizza_sfratto_commerciale(c: Comprensione, f: Fatti) -> Analisi:
    from .strumenti import data_dopo, forma, importi_in, frase

    t = piano(f.testo)
    a = Analisi("opposizione_sfratto_commerciale", "locazione", modello="LOC_004", forma=forma(c))
    udienza = data_dopo(f, r"udienza di convalida fissata al") or data_dopo(f, r"udienza")
    canoni = (importi_in(frase(f, r"canoni non pagati|non pagati")) or [None])[-1]
    offerto = (importi_in(frase(f, r"pagare euro|puo pagare|dichiara di poter pagare")) or [None])[0]
    luogo = (re.search(r"davanti al (tribunale di [a-z]+)", t) or [None, ""])[1].title()
    a.capito = ["Locazione ad uso diverso dall'abitazione (commerciale), sfratto per morosità con udienza di convalida"
                + (f" il {udienza.strftime('%d/%m/%Y')}" if udienza else "") + (f"; canoni non pagati {euro(canoni)}" if canoni else "")
                + "; il conduttore lamenta vizi del locale segnalati per iscritto."]
    a.rimedio = ("comparsa di costituzione e opposizione alla convalida (art. 665 c.p.c.), non l'istanza di termine di grazia "
                 "dell'art. 55 l. 392/1978")
    a.giudice = luogo or "tribunale dell'udienza di convalida"
    a.inquadramento = [
        Punto("Il termine di grazia dell'art. 55 l. 392/1978 riguarda la morosità «di cui all'articolo 5», cioè la locazione "
              "abitativa: per la locazione ad uso diverso non è applicabile (orientamento della Cassazione a Sezioni Unite "
              "indicato nella scheda, da leggere nell'archivio prima di citarlo).",
              [Rif("l392:55", "di cui all'articolo 5"), Rif("l392:5", "decorsi venti giorni dalla scadenza")]),
        Punto("Se l'intimato non compare o non si oppone, il giudice convalida lo sfratto; la convalida per morosità richiede "
              "che la morosità persista all'udienza.", [Rif("cpc:663", "non compare"), Rif("cpc:663", "morosita' persiste")]),
        Punto("Con l'opposizione fondata su prova scritta e in presenza di gravi motivi il giudice può negare l'ordinanza "
              "provvisoria di rilascio; poi il giudizio prosegue con il mutamento del rito.",
              [Rif("cpc:665", "prova scritta"), Rif("cpc:667", "mutamento")]),
        Punto("Il locatore deve mantenere la cosa in buono stato locativo ed eseguire le riparazioni necessarie; per i vizi che "
              "diminuiscono il godimento il conduttore può chiedere la riduzione del corrispettivo, ma sospendere del tutto il "
              "canone per un vizio parziale è un'autoriduzione rischiosa.",
              [Rif("cc:1575", "mantenerla in stato da servire all'uso convenuto"), Rif("cc:1578", "riduzione del corrispettivo"),
               Rif("cc:1460", "contrario alla buona fede"), Rif("cc:1587", "dare il corrispettivo")]),
    ]
    a.procedibilita = [Punto("Con l'opposizione e il mutamento del rito scatta la mediazione obbligatoria in materia di "
                             "locazione.", [Rif("dlgs28:5", "convalida di licenza o sfratto"), Rif("dlgs28:5", "locazione")])]
    righe = []
    if canoni:
        righe.append(f"canoni scaduti {euro(canoni)}")
        if offerto:
            righe.append(f"residuo dopo il versamento immediato offerto di {euro(offerto)}: {euro(canoni - offerto)}")
    a.conclusione = [Punto("Costituirsi all'udienza e opporsi alla convalida, chiedendo di negare l'ordinanza di rilascio "
                           "sulla base della PEC e delle foto dei vizi, il mutamento del rito e nel merito la riduzione del "
                           "canone e le riparazioni" + ("; " + "; ".join(righe) if righe else "") + ".",
                           [Rif("cpc:665", "prova scritta"), Rif("cpc:667", "mutamento")])]
    a.avvertenze = ["La richiesta (termine di grazia di novanta giorni ex art. 55) è inadatta alla locazione commerciale: va "
                    "detto espressamente al cliente.",
                    "L'unico modo per evitare con certezza la convalida è pagare integralmente canoni, interessi e spese entro l'udienza.",
                    "Tentare subito un accordo con la locatrice sul piano di rientro."]
    a.dati_mancanti = ["interessi e spese per la somma da versare in udienza", "eventuale deposito cauzionale"]
    a.termini = [Punto("Durata della locazione commerciale: sei anni rinnovabili.", [Rif("l392:27", "sei anni")])]
    if c.tipo == "redazione":
        from ..bozze import ricorso_generico

        a.bozza = ricorso_generico(
            "Comparsa di costituzione e opposizione alla convalida di sfratto (artt. 665 e 667 c.p.c.)", a.giudice, f,
            "opposizione alla convalida, rigetto dell'ordinanza di rilascio, mutamento del rito e riduzione del canone",
            ["Inadempimento della locatrice all'obbligo di riparazione e vizi che riducono il godimento (artt. 1575, 1576 e "
             "1578 c.c.), documentati con PEC e fotografie.", "Opposizione fondata su prova scritta e gravi motivi: va negata "
             "l'ordinanza di rilascio (art. 665 c.p.c.).", "Disponibilità al versamento immediato e al saldo rateale."],
            "rigettare la richiesta di convalida; negare il provvedimento provvisorio di rilascio; disporre il mutamento del "
            "rito; nel merito ridurre il canone in proporzione al minor godimento e condannare la locatrice alle riparazioni; "
            "con vittoria di spese.", "contratto, intimazione, PEC, fotografie.", "artt. 665 e 667 c.p.c.")
    return a


# ------------------------------------------------------------------- negoziazione chiesta per lo sfratto (strumento inadatto)
def riconosci_negoziazione_locazione(c: Comprensione, f: Fatti) -> int:
    t = piano(f.testo)
    return 5 if "negoziazione" in t and f.ha("locazione") and f.ha("morosita") else 0


def analizza_negoziazione_locazione(c: Comprensione, f: Fatti) -> Analisi:
    a = analizza_sfratto(Comprensione("redazione", "intimazione di sfratto", c.racconto, True), f)
    a.regola = "negoziazione_locazione_inadatta"
    a.forma = "atto"
    a.rimedio = ("intimazione di sfratto per morosità con contestuale citazione per la convalida e richiesta di ingiunzione "
                 "per i canoni (art. 658 c.p.c.); nessun invito alla negoziazione assistita")
    a.inquadramento.insert(0, Punto(
        "Lo strumento chiesto è inadatto: la negoziazione assistita non è condizione di procedibilità in materia di "
        "locazione, che rientra nei casi di mediazione obbligatoria esclusi dall'art. 3 d.l. 132/2014; e la mediazione non "
        "si applica al procedimento di convalida fino al mutamento del rito.",
        [Rif("dl132:3", "articolo 5, comma 1-bis"), Rif("dlgs28:5", "locazione"), Rif("dlgs28:5", "convalida di licenza o sfratto")]))
    a.avvertenze = ["Il conduttore può sanare in prima udienza o chiedere il termine di grazia fino a novanta giorni: la "
                    "convalida richiede che la morosità persista.", "Il deposito cauzionale non va imputato ai canoni nell'atto."]
    if not f.luogo_immobile:
        a.dati_mancanti.append("comune e indirizzo dell'immobile (competenza del tribunale del luogo dell'immobile)")
    a.dati_mancanti.append("pagamento o meno dell'ultimo canone scaduto")
    return a


# ------------------------------------------------------------------- morosità: condizioni di procedibilità chieste liberamente
_PROCEDIBILITA = (r"mediazion|procedibil|tentativo (?:obbligatorio )?di concilia|conciliazion|prima di (?:agire|andare|fare causa|"
                  r"procedere|intimare|notificare|rivolgerci)|dobbiamo prima|serve prima|occorre prima|bisogna prima|"
                  r"passaggi? obbligatori|condizion\w* per agire|organismo")


def riconosci_procedibilita_locazione(c: Comprensione, f: Fatti) -> int:
    t = piano(f.testo)
    if "negoziazione" in t or difesa_del_conduttore(f):
        return 0
    return 6 if f.ha("locazione") and f.ha("morosita") and re.search(_PROCEDIBILITA, t) else 0


def analizza_procedibilita_locazione(c: Comprensione, f: Fatti) -> Analisi:
    a = analizza_sfratto(Comprensione(c.tipo, "intimazione di sfratto" if c.tipo == "redazione" else c.atto, c.racconto, True), f)
    a.regola = "procedibilita_locazione"
    a.forma = "atto" if c.tipo == "redazione" else "parere (consulenza)"
    a.rimedio = ("intimazione di sfratto per morosità con citazione per la convalida, senza mediazione preventiva; mediazione "
                 "da avviare dopo il mutamento del rito, se il giudizio prosegue nel merito")
    a.procedibilita = [
        Punto("La locazione è fra le materie di mediazione obbligatoria: per un'azione ordinaria (per esempio la sola "
              "risoluzione o il pagamento dei canoni con citazione) la mediazione è condizione di procedibilità della domanda.",
              [Rif("dlgs28:5", "locazione"), Rif("dlgs28:5", "e' tenuto preliminarmente a esperire il procedimento di mediazione"),
               Rif("dlgs28:5", "condizione di procedibilita' della domanda")]),
        Punto("La mediazione però non si applica al procedimento per convalida di sfratto fino al mutamento del rito previsto "
              "dall'art. 667 c.p.c.: l'intimazione di sfratto per morosità si notifica subito, senza mediazione preventiva.",
              [Rif("dlgs28:5", "nei procedimenti per convalida di licenza o sfratto, fino al mutamento del rito di cui "
                               "all'articolo 667")]),
        Punto("Se il conduttore si oppone e il giudice dispone il mutamento del rito, la mediazione diventa condizione di "
              "procedibilità del giudizio di merito: il giudice che la rileva non esperita fissa l'udienza successiva dopo la "
              "durata della mediazione, e se la condizione manca la domanda è dichiarata improcedibile.",
              [Rif("dlgs28:5", "fissa la successiva udienza dopo la scadenza del termine di cui all'articolo 6"),
               Rif("dlgs28:5", "dichiara l'improcedibilita' della domanda giudiziale")]),
        Punto("La condizione si considera avverata se il primo incontro davanti al mediatore si chiude senza accordo.",
              [Rif("dlgs28:5", "si conclude senza l'accordo di conciliazione")]),
        Punto("Anche il ricorso per decreto ingiuntivo per i soli canoni è escluso dalla mediazione fino alla pronuncia sulla "
              "provvisoria esecuzione nell'eventuale opposizione.",
              [Rif("dlgs28:5", "procedimenti per ingiunzione, inclusa l'opposizione, fino alla pronuncia sulle istanze di "
                               "concessione e sospensione della provvisoria esecuzione")]),
        Punto("La negoziazione assistita non è condizione di procedibilità: la locazione rientra nei casi di mediazione "
              "obbligatoria che l'art. 3 d.l. 132/2014 esclude.", [Rif("dl132:3", "articolo 5, comma 1-bis")]),
    ]
    a.conclusione = [Punto("Per la morosità non serve alcun passaggio preventivo: si notifica l'intimazione di sfratto con "
                           f"citazione per la convalida davanti al {a.giudice}, chiedendo anche l'ingiunzione per i canoni. La "
                           "mediazione andrà avviata solo se, dopo l'opposizione del conduttore, il giudizio prosegue con il "
                           "mutamento del rito.",
                           [Rif("cpc:658", "mancato pagamento del canone"),
                            Rif("dlgs28:5", "convalida di licenza o sfratto, fino al mutamento del rito")])]
    a.avvertenze = ["Dopo il mutamento del rito conviene che sia il locatore, che ha interesse alla risoluzione, a depositare "
                    "subito la domanda di mediazione: senza mediazione la domanda di merito diventa improcedibile.",
                    "Una citazione ordinaria per la sola risoluzione o per i soli canoni richiede invece la mediazione prima "
                    "della causa."]
    return a


# ------------------------------------------------------------------- restituzione delle somme oltre il canone registrato
def riconosci_indebito_locazione(c: Comprensione, f: Fatti) -> int:
    t = piano(f.testo)
    return 5 if f.ha("locazione") and re.search(r"in nero|non registrat|extra canone|oltre (?:al|il) canone|indebit|maggior canone|canone superiore", t) and re.search(
        r"restitu|indietro|riavere", t) else 0


def analizza_indebito_locazione(c: Comprensione, f: Fatti) -> Analisi:
    from ..termini import termine_mesi
    from .strumenti import data_di, forma

    t = piano(f.testo)
    a = Analisi("restituzione_canone_non_registrato", "locazione", forma=forma(c))
    riconsegna = data_di(f, r"riconsegn")
    m_mese = re.search(r"ulteriori\s*euro\s*([\d.]+)\s*al mese|euro\s*([\d.]+)\s*al mese", t)
    mensile = float((m_mese.group(1) or m_mese.group(2)).replace(".", "")) if m_mese else None
    m_n = re.search(r"per (\d+) mensilita", t)
    n = int(m_n.group(1)) if m_n else None
    m_rest = re.search(r"versa al conduttore euro\s*([\d.]+)", t)
    restituito = float(m_rest.group(1).replace(".", "")) if m_rest else 0
    a.rimedio = ("azione di restituzione delle somme pagate oltre il canone registrato (art. 13, comma 2, l. 431/1998), "
                 "preceduta dalla mediazione obbligatoria da avviare prima della scadenza")
    a.giudice = "organismo di mediazione e poi tribunale del luogo dell'immobile"
    a.inquadramento = [
        Punto("È nullo il patto che fissa un canone superiore a quello del contratto scritto e registrato; il conduttore può "
              "chiederne la restituzione con azione proponibile nel termine di sei mesi dalla riconsegna dell'immobile.",
              [Rif("l431:13", "superiore a quello risultante dal contratto scritto e registrato"),
               Rif("l431:13", "sei mesi dalla riconsegna")]),
        Punto("È un termine di decadenza: non si interrompe con una diffida; lo impedisce solo il compimento dell'atto previsto.",
              [Rif("cc:2964", "interruzione"), Rif("cc:2966", "compimento dell'atto previsto")]),
        Punto("La materia è a mediazione obbligatoria (locazione); la domanda di mediazione comunicata alle altre parti impedisce "
              "la decadenza per una sola volta.", [Rif("dlgs28:5", "locazione"), Rif("dlgs28:8", "decadenza per una sola volta")]),
    ]
    if riconsegna:
        lim = termine_mesi(riconsegna, 6, sostanziale=True)
        a.termini = [Punto(f"Riconsegna il {data_breve(riconsegna)}: l'azione (o la domanda di mediazione) va proposta entro "
                           f"{data_breve(lim)}.", [Rif("l431:13", "sei mesi dalla riconsegna")])]
        a.avvertenze.append(f"La prescrizione decennale indicata nella richiesta non è il termine giusto: c'è la decadenza di sei "
                            f"mesi, che scade il {lim.strftime('%d/%m/%Y')}; la diffida non la impedisce, quindi non si può "
                            "«trattare con calma».")
    if mensile and n:
        tot = mensile * n
        a.conclusione = [Punto(f"Somme extra versate: {euro(mensile)} per {n} mensilità = {euro(tot)}; restituiti "
                               f"{euro(restituito)}; residuo da chiedere {euro(tot - restituito)}.",
                               [Rif("l431:13", "superiore a quello risultante dal contratto scritto e registrato")])]
    a.cosa_fare = ["Depositare subito la domanda di mediazione presso un organismo del luogo del giudice competente e "
                   "comunicarla alla locatrice prima della scadenza.", "Conservare ricevute, scrittura non registrata e "
                   "verbale di riconsegna."]
    a.dati_mancanti = ["data di comunicazione della domanda di mediazione alla controparte"]
    return a


# ------------------------------------------------------------------- finita locazione
def _finita(t: str) -> bool:
    return bool(re.search(r"finita locazione|licenza per finita|dopo la scadenza|alla scadenza|contratto (?:e )?scadut|"
                          r"scadenza del contratto|non (?:vuole )?lascia\w*|rimast\w* (?:nell immobile|dopo)", t))


def riconosci_finita(c: Comprensione, f: Fatti) -> int:
    t = piano(f.testo)
    if f.ha("morosita") or difesa_del_conduttore(f) or not _finita(t) or riconosci_rilascio(c, f):
        return 0
    return 6 if f.ha("locazione") or "finita locazione" in t else 0


def analizza_finita_locazione(c: Comprensione, f: Fatti) -> Analisi:
    from .strumenti import forma

    a = Analisi("sfratto_finita_locazione", "locazione — finita locazione", modello="LOC_001", forma=forma(c))
    luogo = f.luogo_immobile
    a.capito = ["Contratto di locazione scaduto o in scadenza; il conduttore non rilascia l'immobile."]
    a.rimedio = ("intimazione di licenza (prima della scadenza) o di sfratto (dopo la scadenza) per finita locazione, con "
                 "citazione per la convalida")
    a.conclusione = [Punto("Il locatore può intimare licenza per finita locazione prima della scadenza del contratto, con "
                           "contestuale citazione per la convalida, rispettando i termini del contratto, della legge o degli usi; "
                           "dopo la scadenza può intimare lo sfratto con la stessa citazione.",
                           [Rif("cpc:657", "licenza per finita locazione, prima della scadenza del contratto"),
                            Rif("cpc:657", "Puo' altresi' intimare lo sfratto")])]
    a.competenza = [Punto("È competente il tribunale del luogo in cui si trova la cosa locata"
                          + (f" (qui: Tribunale di {luogo})" if luogo else "") + ".",
                          [Rif("cpc:661", "luogo in cui si trova la cosa locata")])]
    a.giudice = P.ufficio("Tribunale", luogo) if luogo else "Tribunale del luogo dell'immobile"
    a.procedibilita = [Punto("La mediazione obbligatoria non si applica al procedimento per convalida fino al mutamento del rito.",
                             [Rif("dlgs28:5", "convalida di licenza o sfratto, fino al mutamento del rito")])]
    a.dati_mancanti += ["data di scadenza del contratto e disdetta inviata (data e modalità)", "tipo di locazione (abitativa o "
                        "uso diverso: per l'abitativa la prima scadenza richiede una disdetta motivata)"]
    return a


# ------------------------------------------------------------------- esecuzione del rilascio
def riconosci_rilascio(c: Comprensione, f: Fatti) -> int:
    t = piano(f.testo)
    if not (f.ha("locazione") or re.search(r"immobil|sfratt|sloggio|rilascio|appartament|casa|locale", t)):
        return 0
    # Il titolo per il rilascio da solo non basta: la domanda deve riguardare la liberazione dell'immobile.
    if not re.search(r"uscir|non esce|non se ne va|lascia\w* (?:l immobile|la casa|il locale|l appartamento)|liberar|rilascio dell|"
                     r"precetto (?:per|di) rilascio|sloggio|immission\w* nel possesso|chiavi|esecuzione dello sfratto|"
                     r"esegu\w* lo sfratto|forza pubblica|ancora nell", t):
        return 0
    if re.search(r"convalidat\w* (?:lo )?sfratto|sfratto (?:e stato )?convalidat|sentenza di (?:rilascio|risoluzione)", t) and re.search(
            r"ancora nell|non (?:esce|se ne va|lascia|libera|vuole uscire)|fare uscire|facciamo uscire|eseguir|esecuzion", t):
        return 7
    return 7 if re.search(r"avviso di sloggio|precetto (?:per|di) rilascio|esecuzione (?:dello sfratto|del rilascio)|"
                          r"(?:abbiamo|ottenuto|ha ottenuto|c e) (?:la )?convalida|ordinanza di (?:rilascio|convalida)|"
                          r"esegu\w* lo sfratto|si esegue lo sfratto|forza pubblica|ufficiale giudiziario[^.?]{0,40}(?:rilascio|sfratto)", t) else 0


def analizza_rilascio(c: Comprensione, f: Fatti) -> Analisi:
    from .strumenti import forma

    a = Analisi("rilascio", "esecuzione per rilascio", modello="ESE_001", forma=forma(c))
    a.capito = ["Titolo per il rilascio dell'immobile (convalida o sentenza) già ottenuto; il conduttore non lascia l'immobile."]
    a.rimedio = "precetto per rilascio, poi avviso di sloggio dell'ufficiale giudiziario almeno dieci giorni prima dell'accesso"
    a.conclusione = [
        Punto("Il precetto per il rilascio di immobili deve contenere anche la descrizione sommaria dei beni; se il titolo fissa "
              "il termine del rilascio, l'intimazione va fatta con riferimento a quel termine.",
              [Rif("cpc:605", "deve contenere, oltre le indicazioni di cui all'articolo 480, anche la descrizione sommaria"),
               Rif("cpc:605", "l'intimazione va fatta con riferimento a tale termine")]),
        Punto("L'esecuzione inizia con la notifica dell'avviso con cui l'ufficiale giudiziario comunica, almeno dieci giorni "
              "prima, il giorno e l'ora in cui procederà; quel giorno immette la parte istante nel possesso e le consegna le "
              "chiavi.",
              [Rif("cpc:608", "almeno dieci giorni prima"), Rif("cpc:608", "immette la parte istante")]),
        Punto("Prima del precetto il titolo esecutivo va notificato; il precetto intima di adempiere in un termine non minore di "
              "dieci giorni.", [Rif("cpc:479", "notificazione del titolo esecutivo"), Rif("cpc:480", "non minore di dieci giorni")]),
    ]
    return a


# ------------------------------------------------------------------- opposizione del conduttore alla convalida
def riconosci_opposizione_convalida(c: Comprensione, f: Fatti) -> int:
    t = piano(f.testo)
    if not (difesa_del_conduttore(f) and re.search(r"sfratt|convalida|licenza", t)):
        return 0
    # Per la sola morosità del conduttore abitativo la difesa tipica è la sanatoria: l'opposizione serve se si contesta.
    contesta = re.search(r"non (?:erano|sono|era|e) dovut|vizi|contest|oppor|eccezion|nullit|gia pagat|pagat\w* tutto|"
                         r"infiltrazion|finita locazione|scadenza", t)
    return 4 if contesta or not (f.ha("morosita") or re.search(r"moros", t)) else 0


def analizza_opposizione_convalida(c: Comprensione, f: Fatti) -> Analisi:
    from .strumenti import forma

    t = piano(f.testo)
    a = Analisi("opposizione_convalida", "locazione — difesa del conduttore intimato", forma=forma(c))
    a.capito = ["Il conduttore ha ricevuto un'intimazione di licenza o di sfratto con citazione per la convalida."]
    a.rimedio = "comparire all'udienza e opporsi, con le eccezioni documentate; per la morosità abitativa valutare la sanatoria"
    a.conclusione = [
        Punto("Se l'intimato non compare o, comparendo, non si oppone, il giudice convalida con ordinanza esecutiva: "
              "l'opposizione va fatta all'udienza indicata nell'atto.",
              [Rif("cpc:663", "Se l'intimato non compare o comparendo non si oppone, il giudice convalida")]),
        Punto("Se le eccezioni non sono fondate su prova scritta, il giudice su istanza del locatore può comunque pronunciare "
              "ordinanza di rilascio immediatamente esecutiva, con riserva delle eccezioni; conviene quindi portare documenti.",
              [Rif("cpc:665", "oppone eccezioni non fondate su prova scritta"),
               Rif("cpc:665", "con riserva delle eccezioni del convenuto")]),
        Punto("Dopo i provvedimenti sul rilascio il giudizio prosegue con il rito speciale, previa ordinanza di mutamento del rito.",
              [Rif("cpc:667", "il giudizio prosegue nelle forme del rito speciale")]),
    ]
    if f.ha("morosita") or re.search(r"canon|moros", t):
        a.conclusione.insert(1, Punto(
            "Se si contesta l'ammontare dei canoni, il giudice può ordinare il pagamento della somma non controversa entro un "
            "termine non superiore a venti giorni; se il conduttore non paga, convalida.",
            [Rif("cpc:666", "il pagamento della somma non controversa"), Rif("cpc:666", "non superiore a venti giorni")]))
        a.avvertenze.append("Nella locazione abitativa il conduttore può sanare in udienza o chiedere il termine di grazia fino a "
                            "novanta giorni (art. 55 l. 392/1978).")
    return a
