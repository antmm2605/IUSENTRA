"""Pubblico impiego, previdenza, esecuzione contro la pubblica amministrazione e opposizione all'ordinanza-ingiunzione:
strumenti che, senza regola, finivano su regole del lavoro privato, del precetto o del decreto ingiuntivo."""
from __future__ import annotations

import re

from ..comprensione import Comprensione
from ..fatti import Fatti, data_it
from ..modello import Analisi, Punto, Rif
from ..norme import piano
from ..termini import data_breve, termine_giorni
from .strumenti import data_dopo, data_di, forma

_PA = (r"tesoreria|dello stato\b|contro l amministrazione|l amministrazione non|pubblic\w* amministrazion|amministrazion\w* (?:dello stato|statal|pubblic)|\bpa\b|ministero|ministeri|comune|regione|"
       r"provincia|\basl\b|azienda sanitaria|ospedale pubblico|universita|scuola statale|istituto scolastico|ufficio scolastico|"
       r"agenzia delle entrate|prefettura|questura|inps|inail|ente pubblico")


def _t(f: Fatti) -> str:
    return piano(f.testo)


# ------------------------------------------------------------------- dipendente pubblico (art. 63 d.lgs. 165/2001)
def riconosci_dipendente_pubblico(c: Comprensione, f: Fatti) -> int:
    t = _t(f)
    dipendente = re.search(r"dipendent\w* pubblic|pubblico impiego|impiegat\w* pubblic|dipendent\w* (?:del|della|dei|delle|di un|di una) "
                           r"(?:ministero|comune|regione|provincia|asl|amministrazion|scuola|universita|ente pubblico)|"
                           r"docent\w* (?:di ruolo|precari|della scuola statale)|personale (?:ata|docente|scolastico)|"
                           r"dipendenti delle amministrazioni", t)
    if not dipendente or re.search(r"concors\w* (?:per l assunzione|pubblic)|bando di concorso|graduatoria del concorso", t):
        return 0
    return 6 if re.search(r"giudice|foro|competen|tribunale|tar\b|causa|ricorso|scatti|stipend|retribu|differenz|indennit|"
                          r"mansioni|demansionament|licenzia|sanzion|trasferiment|progression", t) else 0


def analizza_dipendente_pubblico(c: Comprensione, f: Fatti) -> Analisi:
    a = Analisi("ricorso_dipendente_pubblico", "pubblico impiego", modello="LAV_001", forma=forma(c))
    a.capito = ["Controversia di un dipendente di una pubblica amministrazione sul proprio rapporto di lavoro."]
    a.rimedio = ("ricorso al tribunale in funzione di giudice del lavoro del luogo dell'ufficio cui il dipendente è (o era) "
                 "addetto")
    a.giudice = "Tribunale, sezione lavoro, del luogo dell'ufficio cui il dipendente è addetto"
    a.conclusione = [
        Punto("Le controversie sui rapporti di lavoro alle dipendenze delle pubbliche amministrazioni sono devolute al giudice "
              "ordinario in funzione di giudice del lavoro, anche quando vengono in questione atti amministrativi presupposti.",
              [Rif("dlgs165:63", "Sono devolute al giudice ordinario, in funzione di giudice del lavoro"),
               Rif("dlgs165:63", "ancorche' vengano in questione atti amministrativi presupposti")]),
        Punto("È competente per territorio il giudice nella cui circoscrizione ha sede l'ufficio al quale il dipendente è "
              "addetto, o era addetto al momento della cessazione del rapporto: non il foro dell'azienda o del luogo in cui è "
              "sorto il rapporto, che valgono per il lavoro privato.",
              [Rif("cpc:413", "ha sede l'ufficio al quale il dipendente e' addetto o era addetto al momento della cessazione del rapporto")]),
        Punto("Se è parte un'amministrazione dello Stato non si applica il foro erariale dell'Avvocatura dello Stato.",
              [Rif("cpc:413", "non si applicano le disposizioni dell'articolo 6 del regio decreto 30 ottobre 1933, n. 1611")]),
    ]
    a.rito = [Punto("Si applica il rito del lavoro, che riguarda anche i rapporti di lavoro dei dipendenti di enti pubblici.",
                    [Rif("cpc:409", "rapporti di lavoro dei dipendenti di enti pubblici")])]
    a.inquadramento = [Punto("Restano al giudice amministrativo le controversie sulle procedure concorsuali per l'assunzione e "
                             "quelle del personale in regime di diritto pubblico (magistrati, avvocati dello Stato, militari, "
                             "forze di polizia, personale diplomatico, professori universitari e gli altri dell'art. 3).",
                             [Rif("dlgs165:63", "procedure concorsuali per l'assunzione"),
                              Rif("dlgs165:63", "controversie relative ai rapporti di lavoro di cui all'articolo 3")])]
    if not re.search(r"(?:ufficio|sede) (?:di|a) [a-z]+|addett\w* (?:a|al|alla|presso)", _t(f)):
        a.dati_mancanti.append("ufficio e sede di servizio del dipendente (decide il foro)")
    return a


# ------------------------------------------------------------------- previdenza: ricorso amministrativo e giudice
def riconosci_previdenza(c: Comprensione, f: Fatti) -> int:
    t = _t(f)
    if re.search(r"fondo di garanzia|fallit|445[- ]bis|accertamento tecnico|\batp\b|atpo", t):
        return 0
    prestazione = re.search(r"naspi|\binps\b|\binail\b|\bpension|invalidit\w* civil|assegno (?:ordinario|sociale|di invalidit|unico)|"
                            r"indennita di (?:disoccupazione|accompagnamento|malattia|maternita)|accompagnamento|legge 104|"
                            r"contribut\w* previdenzial|cassa (?:forense|professionale)|prestazion\w* previdenzial", t)
    return 6 if prestazione and re.search(r"diniego|negat|respint|rigett|revoc|sospes|ricors|giudice|tribunale|tar\b|impugn|"
                                          r"non (?:ci )?(?:paga|riconosce|eroga)", t) else 0


def riconosci_causa_previdenziale(c: Comprensione, f: Fatti) -> int:
    t = _t(f)
    return 7 if riconosci_previdenza(c, f) and re.search(r"giudice|tribunale|causa|giudiziale|facciamo causa|competen", t) and not re.search(
        r"ricorso amministrativo|comitato", t) else 0


def analizza_causa_previdenziale(c: Comprensione, f: Fatti) -> Analisi:
    a = analizza_previdenza(c, f)
    a.regola = "ricorso_442"
    a.rimedio = ("ricorso al tribunale in funzione di giudice del lavoro del luogo di residenza, dopo il ricorso "
                 "amministrativo o decorsi centottanta giorni")
    return a


def analizza_previdenza(c: Comprensione, f: Fatti) -> Analisi:
    a = Analisi("ricorso_amministrativo_inps", "previdenza e assistenza", forma=forma(c))
    a.capito = ["Diniego o revoca di una prestazione previdenziale o assistenziale."]
    a.rimedio = ("ricorso amministrativo all'ente nei termini delle leggi speciali; poi ricorso al tribunale in funzione di "
                 "giudice del lavoro del luogo di residenza")
    a.giudice = "Tribunale, sezione lavoro, del luogo di residenza dell'assistito"
    a.conclusione = [
        Punto("Il giudice non è il TAR: le controversie in materia di previdenza e assistenza obbligatorie seguono il rito del "
              "lavoro e sono di competenza del tribunale in funzione di giudice del lavoro del luogo di residenza dell'attore.",
              [Rif("cpc:442", "ogni altra forma di previdenza e di assistenza obbligatorie"),
               Rif("cpc:444", "nella cui circoscrizione ha la residenza l'attore")]),
        Punto("La domanda giudiziale non è procedibile finché non sono esauriti i ricorsi amministrativi previsti dalle leggi "
              "speciali o non sono decorsi i termini per deciderli, e comunque centottanta giorni dalla proposizione del ricorso "
              "amministrativo; se il giudice rileva l'improcedibilità sospende il giudizio e assegna un termine.",
              [Rif("cpc:443", "non e' procedibile se non quando siano esauriti i procedimenti prescritti dalle leggi speciali"),
               Rif("cpc:443", "decorsi 180 giorni dalla data in cui e' stato proposto il ricorso amministrativo")]),
    ]
    a.dubbi.append("Il termine e l'organo del ricorso amministrativo (comitato provinciale INPS o altro organo) sono fissati "
                   "dalla legge speciale della prestazione, che la biblioteca non contiene (art. 46 l. 88/1989): leggerli nel "
                   "provvedimento di diniego, che deve indicarli.")
    a.cosa_fare = ["Presentare il ricorso amministrativo nel termine indicato nel provvedimento.",
                   "Conservare la prova della data di presentazione: da essa decorrono i centottanta giorni.",
                   "Per l'invalidità civile valutare l'accertamento tecnico preventivo obbligatorio prima del merito."]
    return a


# ------------------------------------------------------------------- esecuzione contro la pubblica amministrazione
def riconosci_esecuzione_pa(c: Comprensione, f: Fatti) -> int:
    t = _t(f)
    if not re.search(_PA, t) or re.search(r"\btar\b.{0,40}(?:sentenza|giudicato)|sentenza del (?:tar|consiglio di stato)", t):
        return 0
    return 7 if re.search(r"precett|pignor|esecuzion\w* forzat|120 giorni|centoventi giorni|titolo esecutivo|"
                          r"non paga (?:le somme|quanto)", t) and (not re.search(r"ottemperanza", t) or re.search(r"precett", t)) and re.search(
        r"sentenz|decreto ingiuntivo|titolo|lodo|ordinanza|precett|giudice del lavoro|tribunale", t) else 0


def analizza_esecuzione_pa(c: Comprensione, f: Fatti) -> Analisi:
    a = Analisi("esecuzione_contro_pa", "esecuzione contro la pubblica amministrazione", modello="ESE_001", forma=forma(c))
    a.capito = ["Titolo esecutivo per una somma di denaro contro una pubblica amministrazione che non paga."]
    a.rimedio = ("attendere centoventi giorni dalla notificazione del titolo, poi precetto ed esecuzione forzata; se il titolo è "
                 "passato in giudicato, in alternativa il giudizio di ottemperanza")
    a.conclusione = [
        Punto("Le amministrazioni dello Stato, gli enti pubblici non economici e l'Agenzia delle entrate-Riscossione hanno "
              "centoventi giorni dalla notificazione del titolo esecutivo per pagare: prima di tale termine il creditore non "
              "può procedere a esecuzione forzata né notificare il precetto.",
              [Rif("dl669:14", "entro il termine di centoventi giorni dalla notificazione del titolo esecutivo"),
               Rif("dl669:14", "Prima di tale termine il creditore non può procedere ad esecuzione forzata né alla notifica di atto di precetto")]),
        Punto("Per le sentenze del giudice ordinario passate in giudicato, e i provvedimenti equiparati, si può chiedere in "
              "alternativa l'ottemperanza al giudice amministrativo; per una sentenza solo esecutiva, non passata in "
              "giudicato, resta l'esecuzione forzata ordinaria.",
              [Rif("cpa:112", "delle sentenze passate in giudicato e degli altri provvedimenti ad esse equiparati del giudice ordinario")]),
    ]
    a.inquadramento = [Punto("Atti di precetto e pignoramento verso gli enti pubblici vanno notificati, a pena di nullità, "
                             "presso la struttura territoriale dell'ente nella cui circoscrizione risiede il creditore.",
                             [Rif("dl669:14", "devono essere notificati a pena di nullità presso la struttura territoriale")])]
    notifica = data_dopo(f, r"(?:titolo |sentenza )?notificat\w*") or data_di(f, r"notific")
    if notifica:
        a.termini.append(Punto(f"Titolo notificato il {data_it(notifica)}: precetto non prima del "
                               f"{data_breve(termine_giorni(notifica, 120, sospensione_feriale=False, sostanziale=True))} "
                               "(centoventi giorni).", [Rif("dl669:14", "centoventi giorni dalla notificazione del titolo esecutivo")]))
    else:
        a.dati_mancanti.append("data di notificazione del titolo esecutivo all'amministrazione")
    return a


# ------------------------------------------------------------------- opposizione all'ordinanza-ingiunzione
def riconosci_ordinanza_ingiunzione(c: Comprensione, f: Fatti) -> int:
    return 8 if re.search(r"ordinanza[- ]ingiunzion|ordinanza di ingiunzione", _t(f)) else 0


def analizza_ordinanza_ingiunzione(c: Comprensione, f: Fatti) -> Analisi:
    a = Analisi("ordinanza_ingiunzione", "violazioni amministrative", modello="GDP_004", forma=forma(c))
    t = _t(f)
    a.capito = ["Ordinanza-ingiunzione di pagamento di una sanzione amministrativa da impugnare."]
    a.rimedio = ("ricorso in opposizione all'ordinanza-ingiunzione (art. 22 l. 689/1981, art. 6 d.lgs. 150/2011) entro trenta "
                 "giorni dalla notificazione; non è un'opposizione a decreto ingiuntivo")
    a.conclusione = [
        Punto("Contro l'ordinanza-ingiunzione si propone opposizione davanti all'autorità giudiziaria ordinaria, regolata "
              "dall'art. 6 d.lgs. 150/2011, con il rito del lavoro.",
              [Rif("l689:22", "contro l'ordinanza-ingiunzione di pagamento"),
               Rif("l689:22", "L'opposizione e' regolata dall'articolo 6 del decreto legislativo 1 settembre 2011, n. 150"),
               Rif("dlgs150:6", "sono regolate dal rito del lavoro")]),
        Punto("Il ricorso va proposto, a pena di inammissibilità, entro trenta giorni dalla notificazione del provvedimento "
              "(sessanta se il ricorrente risiede all'estero).",
              [Rif("dlgs150:6", "a pena di inammissibilita', entro trenta giorni dalla notificazione del provvedimento")]),
    ]
    a.competenza = [
        Punto("È competente il giudice del luogo in cui è stata commessa la violazione; di regola il giudice di pace.",
              [Rif("dlgs150:6", "davanti al giudice del luogo in cui e' stata commessa la violazione"),
               Rif("dlgs150:6", "l'opposizione si propone davanti al giudice di pace")]),
        Punto("Va invece al tribunale per le violazioni in materia di lavoro, previdenza, ambiente, alimenti, valutaria e "
              "antiriciclaggio, e quando la sanzione prevista supera nel massimo 15.493 euro o non è solo pecuniaria.",
              [Rif("dlgs150:6", "L'opposizione si propone davanti al tribunale quando la sanzione e' stata applicata"),
               Rif("dlgs150:6", "superiore nel massimo a 15.493 euro")]),
    ]
    a.inquadramento = [Punto("L'efficacia esecutiva dell'ordinanza può essere sospesa su istanza nel ricorso; in primo grado "
                             "l'opponente può stare in giudizio personalmente.",
                             [Rif("dlgs150:6", "L'efficacia esecutiva del provvedimento impugnato puo' essere sospesa"),
                              Rif("dlgs150:6", "possono stare in giudizio personalmente")])]
    notifica = data_dopo(f, r"notificat\w*")
    if notifica:
        a.termini.append(Punto(f"Notificata il {data_it(notifica)}: ricorso entro il {data_breve(termine_giorni(notifica, 30))} "
                               "(trenta giorni, con la sospensione feriale).",
                               [Rif("dlgs150:6", "entro trenta giorni dalla notificazione del provvedimento"),
                                Rif("l742:1", "giurisdizioni ordinarie ed a quelle amministrative")]))
    else:
        a.dati_mancanti.append("data di notificazione dell'ordinanza-ingiunzione")
    if not re.search(r"euro|€", t):
        a.dati_mancanti.append("materia della violazione e importo della sanzione (decidono giudice di pace o tribunale)")
    return a
