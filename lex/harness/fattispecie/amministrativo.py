"""Riti speciali del processo amministrativo e del processo tributario che non seguono il termine generale di sessanta giorni
del ricorso al TAR o del ricorso di primo grado: appalti (art. 120 c.p.a.), accesso, silenzio, motivi aggiunti, ottemperanza,
unità familiare dello straniero, appello e sospensione tributaria, reclamo-mediazione abrogato."""
from __future__ import annotations

import re

from ..comprensione import Comprensione
from ..fatti import Fatti, data_it
from ..modello import Analisi, Punto, Rif
from ..norme import piano
from ..termini import data_breve, termine_giorni, termine_mesi
from .strumenti import data_dopo, data_di, forma

_TRIB_SEMPLICE = r"agenzia delle entrate|cartella|avviso di accertamento"
_FERIALE = Rif("l742:1", "giurisdizioni ordinarie ed a quelle amministrative")


def _t(f: Fatti) -> str:
    return piano(f.testo)


def _notifica(f: Fatti, espr: str = r"(?:notificat|comunicat|ricevut|pubblicat)\w*"):
    return data_dopo(f, espr) or data_di(f, r"notific|comunicaz|ricevut|pubblicat")


def _scadenza(a: Analisi, d, giorni: int, cosa: str, rif: list[Rif]) -> None:
    if d:
        a.termini.append(Punto(f"Dal {data_it(d)}: {cosa} entro il {data_breve(termine_giorni(d, giorni))} ({giorni} giorni, con "
                               "la sospensione feriale dal 1° al 31 agosto).", rif + [_FERIALE]))
    else:
        a.dati_mancanti.append("data di notificazione, comunicazione o conoscenza dell'atto (da essa decorre il termine)")


# ------------------------------------------------------------------- appalti pubblici (art. 120 c.p.a.)
_GARA = r"subentr\w* nel contratto|rito appalti|\bappalti\b|aggiudicazion|gara d appalto|\bgara\b|bando di gara|procedura di affidamento|affidamento diretto|esclusione dalla gara|\bcig\b|appalto pubblic|contratti pubblici|stazione appaltante"


def riconosci_appalti(c: Comprensione, f: Fatti) -> int:
    t = _t(f)
    return 5 if re.search(_GARA, t) and not re.search(r"ricorso straordinario", t) else 0


def analizza_appalti(c: Comprensione, f: Fatti) -> Analisi:
    a = Analisi("appalti_120", "amministrativo — contratti pubblici", modello="AMM_001", forma=forma(c))
    a.capito = ["Impugnazione di un atto di una procedura di affidamento di un contratto pubblico."]
    a.rimedio = "ricorso al TAR nel rito speciale degli appalti, entro trenta giorni, con eventuale istanza cautelare"
    a.giudice = "TAR competente"
    a.conclusione = [Punto("Gli atti delle procedure di affidamento si impugnano unicamente con ricorso al TAR competente, e il "
                           "ricorso (come i motivi aggiunti) va proposto nel termine di trenta giorni, non nei sessanta del "
                           "rito ordinario.",
                           [Rif("cpa:120", "sono impugnabili unicamente mediante ricorso al tribunale amministrativo regionale"),
                            Rif("cpa:120", "sono proposti nel termine di trenta giorni")])]
    a.inquadramento = [
        Punto("Il termine decorre dalla ricezione della comunicazione dell'aggiudicazione o dalla messa a disposizione degli "
              "atti; per i bandi autonomamente lesivi decorre dalla pubblicazione.",
              [Rif("cpa:120", "dalla ricezione della comunicazione di cui all'articolo 90"),
               Rif("cpa:120", "Per i bandi e gli avvisi con cui si indice una gara che siano autonomamente lesivi")]),
        Punto("Se è mancata la pubblicità del bando, il ricorso va comunque proposto entro trenta giorni dalla pubblicazione "
              "dell'avviso di aggiudicazione; se mancano anche gli avvisi, non oltre sei mesi dalla stipulazione del contratto.",
              [Rif("cpa:120", "Nel caso in cui sia mancata la pubblicita' del bando"),
               Rif("cpa:120", "non oltre sei mesi dal giorno successivo alla data di stipulazione del contratto")]),
        Punto("In tutti gli atti di parte va indicato il codice identificativo di gara (CIG).",
              [Rif("cpa:120", "codice identificativo di gara (CIG)")]),
    ]
    _scadenza(a, _notifica(f, r"(?:comunicat|ricevut|notificat)\w*"), 30, "ricorso al TAR da notificare",
              [Rif("cpa:120", "sono proposti nel termine di trenta giorni")])
    a.cosa_fare = ["Chiedere subito l'accesso agli atti di gara e alle offerte, che fanno decorrere il termine.",
                   "Notificare il ricorso alla stazione appaltante e almeno a un controinteressato (l'aggiudicatario).",
                   "Valutare l'istanza cautelare per evitare la stipulazione del contratto."]
    a.dati_mancanti.append("CIG e data di ricezione della comunicazione di aggiudicazione")
    return a


# ------------------------------------------------------------------- accesso agli atti
def riconosci_accesso(c: Comprensione, f: Fatti) -> int:
    t = _t(f)
    if re.search(r"accesso (?:a|al|alla|ad|ai|alle) (?:un |una )?(?:programma|composizione|procedura|servizi|beneficio|misur|credito|fondo)", t):
        return 0
    if re.search(r"accesso (?:agli |ai )?(?:atti|documenti)|istanza di accesso|diritto di accesso|accesso documentale", t) and not re.search(_GARA, t):
        return 5
    return 5 if re.search(r"\baccesso\b|copia (?:del fascicolo|degli atti|dei documenti)", t) and re.search(
        r"comune|amministrazion|regione|ministero|prefettur|questur|\bpa\b|provincia|ufficio tecnico|pratica edilizia", t) else 0


def analizza_accesso(c: Comprensione, f: Fatti) -> Analisi:
    a = Analisi("accesso_atti", "amministrativo — accesso ai documenti", forma=forma(c))
    a.capito = ["Diniego, differimento o silenzio su un'istanza di accesso ai documenti amministrativi."]
    a.rimedio = "ricorso al TAR nel rito dell'accesso, oppure richiesta di riesame al difensore civico o alla Commissione per l'accesso"
    a.giudice = "TAR competente"
    a.conclusione = [
        Punto("Decorsi inutilmente trenta giorni dalla richiesta, l'accesso si intende respinto; contro il diniego espresso o "
              "tacito, o il differimento, si può ricorrere al TAR oppure chiedere il riesame al difensore civico (atti di "
              "comuni, province e regioni) o alla Commissione per l'accesso (amministrazioni dello Stato).",
              [Rif("l241:25", "Decorsi inutilmente trenta giorni dalla richiesta, questa si intende respinta"),
               Rif("l241:25", "il richiedente puo' presentare ricorso al tribunale amministrativo regionale"),
               Rif("l241:25", "Commissione per l'accesso")]),
        Punto("Se ci si rivolge al difensore civico o alla Commissione, il termine per il ricorso al TAR decorre dal ricevimento "
              "del loro esito.", [Rif("l241:25", "il termine di cui al comma 5 decorre dalla data di ricevimento")]),
        Punto("Le controversie sull'accesso seguono il codice del processo amministrativo, che ha per esse un rito apposito.",
              [Rif("l241:25", "sono disciplinate dal codice del processo amministrativo")]),
    ]
    a.dubbi.append("Il termine del rito dell'accesso (art. 116 c.p.a.) non si può leggere: nella biblioteca l'articolo "
                   "risulta senza testo. È più breve del termine ordinario di sessanta giorni: contarlo sul testo ufficiale "
                   "prima di fissare la scadenza.")
    richiesta = data_di(f, r"istanza|richiesta")
    if richiesta:
        a.termini.append(Punto(f"Istanza del {data_it(richiesta)}: in mancanza di risposta, si intende respinta dal "
                               f"{data_it(termine_giorni(richiesta, 30, sospensione_feriale=False, sostanziale=True))}.",
                               [Rif("l241:25", "Decorsi inutilmente trenta giorni dalla richiesta")]))
    return a


# ------------------------------------------------------------------- silenzio della pubblica amministrazione
def riconosci_silenzio(c: Comprensione, f: Fatti) -> int:
    t = _t(f)
    if re.search(r"accesso (?:agli |ai )?(?:atti|documenti)", t):
        return 0
    if re.search(r"silenzio[- ]inadempimento|rito del silenzio|(?:contro|avverso) il silenzio|silenzio della (?:pa|pubblica amministrazione)", t):
        return 5
    inerzia = re.search(r"silenzio|\btace\b|non decide|non (?:ci )?(?:ha )?(?:mai )?rispost\w*|non (?:ci )?rispond\w*|non conclude|non (?:si e|si sono) pronunciat|"
                        r"inerzia|non provvede|non ha provveduto", t)
    pa = re.search(r"comune|amministrazion|regione|ministero|prefettur|questur|\bpa\b|provincia|ente pubblico|procedimento", t)
    return 5 if inerzia and pa and re.search(r"istanza|domanda|procedimento|richiesta", t) and not re.search(_TRIB_SEMPLICE, t) else 0


def analizza_silenzio(c: Comprensione, f: Fatti) -> Analisi:
    a = Analisi("silenzio", "amministrativo — silenzio", forma=forma(c))
    a.capito = ["L'amministrazione non ha concluso il procedimento avviato con un'istanza."]
    a.rimedio = "ricorso al TAR avverso il silenzio, per l'accertamento dell'obbligo di provvedere"
    a.giudice = "TAR competente"
    a.conclusione = [
        Punto("Scaduti i termini di conclusione del procedimento, chi vi ha interesse può chiedere al TAR l'accertamento "
              "dell'obbligo dell'amministrazione di provvedere.",
              [Rif("cpa:31", "chi vi ha interesse puo' chiedere l'accertamento dell'obbligo dell'amministrazione di provvedere")]),
        Punto("L'azione si propone finché dura l'inadempimento e comunque non oltre un anno dalla scadenza del termine di "
              "conclusione del procedimento; il ricorso non richiede una diffida e va notificato all'amministrazione e ad "
              "almeno un controinteressato.",
              [Rif("cpa:31", "fintanto che perdura l'inadempimento e, comunque, non oltre un anno"),
               Rif("cpa:117", "anche senza previa diffida")]),
        Punto("Il giudice decide con sentenza in forma semplificata e, se accoglie, ordina di provvedere di norma entro trenta "
              "giorni, nominando se occorre un commissario ad acta.",
              [Rif("cpa:117", "sentenza in forma semplificata"), Rif("cpa:117", "commissario ad acta")]),
        Punto("Se nel giudizio sopravviene il provvedimento espresso, lo si impugna con motivi aggiunti nei termini e con il "
              "rito del nuovo provvedimento.", [Rif("cpa:117", "puo' essere impugnato anche con motivi aggiunti")]),
    ]
    a.dati_mancanti.append("data dell'istanza e termine di conclusione del procedimento (da esso decorre l'anno)")
    return a


# ------------------------------------------------------------------- motivi aggiunti
def riconosci_motivi_aggiunti(c: Comprensione, f: Fatti) -> int:
    t = _t(f)
    if "motivi aggiunti" in t and not re.search(_GARA, t):
        return 6
    return 5 if re.search(r"motivi aggiunti|nuovi vizi|nuovo (?:atto|provvedimento)[^.?]{0,60}(?:collegat|connesso|successiv)|"
                          r"(?:atto|provvedimento) (?:collegat|connesso|sopravvenut)", t) and re.search(r"\btar\b|ricorso|giudizio", t) and not re.search(_GARA, t) else 0


def analizza_motivi_aggiunti(c: Comprensione, f: Fatti) -> Analisi:
    a = Analisi("motivi_aggiunti", "amministrativo — motivi aggiunti", forma=forma(c))
    a.capito = ["Giudizio già pendente al TAR; l'amministrazione ha adottato un atto nuovo connesso a quello impugnato."]
    a.rimedio = "motivi aggiunti nel giudizio pendente, notificati alle parti costituite, nel termine del ricorso"
    a.conclusione = [
        Punto("Con i motivi aggiunti si introducono nuove ragioni o domande nuove purché connesse a quelle già proposte; si "
              "applica la disciplina del ricorso, compresi i termini.",
              [Rif("cpa:43", "domande nuove purche' connesse a quelle gia' proposte"),
               Rif("cpa:43", "ivi compresa quella relativa ai termini")]),
        Punto("Le notifiche alle controparti costituite si fanno ai difensori; se la domanda nuova è proposta con ricorso "
              "separato davanti allo stesso tribunale, il giudice riunisce i ricorsi.",
              [Rif("cpa:43", "articolo 170 del codice di procedura civile"), Rif("cpa:43", "provvede alla riunione dei ricorsi")]),
    ]
    a.termini.append(Punto("Il termine è quello del ricorso contro il nuovo atto: sessanta giorni nel rito ordinario, che "
                           "decorrono dalla notificazione, comunicazione o piena conoscenza.",
                           [Rif("cpa:29", "termine di decadenza di sessanta giorni"), Rif("cpa:43", "ivi compresa quella relativa ai termini")]))
    _scadenza(a, _notifica(f), 60, "motivi aggiunti da notificare", [Rif("cpa:29", "sessanta giorni")])
    return a


# ------------------------------------------------------------------- ottemperanza
def riconosci_ottemperanza(c: Comprensione, f: Fatti) -> int:
    t = _t(f)
    pa = re.search(r"amministrazion|ministero|comune|regione|provincia|\bpa\b|asl|inps|ente pubblico|universit|agenzia", t)
    return 6 if "ottemperanza" in t or (pa and re.search(r"giudicato", t) and re.search(r"non (?:paga|esegue|da esecuzione|ottempera|adempie)", t)) else 0


def analizza_ottemperanza(c: Comprensione, f: Fatti) -> Analisi:
    a = Analisi("ottemperanza", "amministrativo — ottemperanza", forma=forma(c))
    a.capito = ["L'amministrazione non esegue un provvedimento giurisdizionale."]
    a.rimedio = "ricorso per l'ottemperanza al giudice amministrativo, con nomina eventuale di un commissario ad acta"
    a.conclusione = [
        Punto("L'ottemperanza si può chiedere per le sentenze del giudice amministrativo passate in giudicato o esecutive e "
              "per le sentenze del giudice ordinario passate in giudicato e i provvedimenti equiparati, per ottenere che "
              "l'amministrazione si conformi.",
              [Rif("cpa:112", "delle sentenze del giudice amministrativo passate in giudicato"),
               Rif("cpa:112", "delle sentenze passate in giudicato e degli altri provvedimenti ad esse equiparati del giudice ordinario")]),
        Punto("Il ricorso si notifica all'amministrazione e alle altre parti del giudizio, anche senza diffida; con esso si "
              "deposita il provvedimento con la prova del passaggio in giudicato. L'azione si prescrive in dieci anni dal "
              "giudicato.",
              [Rif("cpa:114", "anche senza previa diffida"), Rif("cpa:114", "con l'eventuale prova del suo passaggio in giudicato"),
               Rif("cpa:114", "si prescrive con il decorso di dieci anni")]),
    ]
    t = _t(f)
    if re.search(r"decreto ingiuntivo|non (?:e )?passat\w* in giudicato|provvisoriamente esecutiv", t):
        a.avvertenze.append("Per i provvedimenti del giudice ordinario l'ottemperanza richiede il passaggio in giudicato (o un "
                            "provvedimento equiparato, come il decreto ingiuntivo non opposto e dichiarato esecutivo): prima "
                            "resta l'esecuzione forzata ordinaria.")
    return a


# ------------------------------------------------------------------- unità familiare dello straniero (non TAR)
def riconosci_unita_familiare(c: Comprensione, f: Fatti) -> int:
    t = _t(f)
    return 6 if re.search(r"ricongiungimento|motivi familiari|coesione familiare|unita familiare", t) and re.search(
        r"permesso|nulla osta|visto|diniego|negat|respint|revoca|rifiut", t) else 0


def analizza_unita_familiare(c: Comprensione, f: Fatti) -> Analisi:
    a = Analisi("permesso_soggiorno", "immigrazione — unità familiare", forma=forma(c))
    a.capito = ["Diniego o revoca di un provvedimento in materia di unità familiare dello straniero."]
    a.rimedio = "opposizione al tribunale ordinario (sezione specializzata immigrazione), non ricorso al TAR"
    a.giudice = "Tribunale sede della sezione specializzata immigrazione del luogo dell'autorità che ha adottato l'atto"
    a.conclusione = [
        Punto("Contro il diniego del nulla osta al ricongiungimento, del permesso di soggiorno per motivi familiari e gli altri "
              "provvedimenti sull'unità familiare si propone opposizione all'autorità giudiziaria ordinaria.",
              [Rif("dlgs286:30", "l'interessato puo' proporre opposizione all'autorita' giudiziaria ordinaria")]),
        Punto("È competente il tribunale sede della sezione specializzata in materia di immigrazione del luogo in cui ha sede "
              "l'autorità che ha adottato il provvedimento; il rito è il semplificato di cognizione.",
              [Rif("dlgs150:20", "E' competente il tribunale sede della sezione specializzata"),
               Rif("dlgs150:20", "sono regolate dal rito semplificato di cognizione")]),
    ]
    a.avvertenze.append("Il TAR non è il giudice di questi provvedimenti: un ricorso al TAR farebbe perdere tempo.")
    return a


# ------------------------------------------------------------------- tributario: appello, sospensione, reclamo abrogato
_TRIB = r"l agenzia|tributar|agenzia delle entrate|riscossione|cartella|avviso di accertamento|commissione tributaria|corte di giustizia tributaria|\bimu\b|\btari\b|irpef|\biva\b"


def riconosci_appello_tributario(c: Comprensione, f: Fatti) -> int:
    t = _t(f)
    return 6 if re.search(_TRIB, t) and re.search(r"appell|secondo grado|sentenza (?:di primo grado|della corte|tributaria)|"
                                                  r"(?:respint|rigettat|accolt)\w* (?:il )?(?:nostro )?ricorso", t) else 0


def analizza_appello_tributario(c: Comprensione, f: Fatti) -> Analisi:
    a = Analisi("appello_tributario", "tributario — appello", forma=forma(c))
    a.capito = ["Sentenza della Corte di giustizia tributaria di primo grado da impugnare."]
    a.rimedio = "appello alla Corte di giustizia tributaria di secondo grado"
    a.giudice = "Corte di giustizia tributaria di secondo grado competente"
    a.conclusione = [
        Punto("La sentenza di primo grado si appella alla Corte di giustizia tributaria di secondo grado.",
              [Rif("dlgs546:52", "puo' essere appellata")]),
        Punto("Il termine è di sessanta giorni dalla notificazione della sentenza fatta su istanza di parte; se nessuna parte la "
              "notifica, si applica il termine lungo dell'art. 327 c.p.c. (sei mesi dalla pubblicazione).",
              [Rif("dlgs546:51", "e' di sessanta giorni, decorrente dalla sua notificazione ad istanza di parte"),
               Rif("dlgs546:38", "si applica l'art. 327, comma 1"), Rif("cpc:327", "dalla pubblicazione della sentenza")]),
        Punto("L'appello deve indicare la corte, le parti, gli estremi della sentenza, i fatti, l'oggetto della domanda e i "
              "motivi specifici, a pena di inammissibilità.",
              [Rif("dlgs546:53", "i motivi specifici dell'impugnazione"), Rif("dlgs546:53", "e' inammissibile")]),
        Punto("In appello si può chiedere di sospendere in tutto o in parte l'esecutività della sentenza se ci sono gravi e "
              "fondati motivi.", [Rif("dlgs546:52", "se sussistono gravi e fondati motivi")]),
    ]
    notifica = data_dopo(f, r"(?:sentenza )?notificat\w*")
    deposito = data_dopo(f, r"(?:depositat|pubblicat)\w*")
    if notifica:
        a.termini.append(Punto(f"Sentenza notificata il {data_it(notifica)}: appello entro il "
                               f"{data_breve(termine_giorni(notifica, 60))} (sessanta giorni, sospensione feriale compresa).",
                               [Rif("dlgs546:51", "sessanta giorni"), Rif("l742:1", "31 agosto")]))
    elif deposito:
        a.termini.append(Punto(f"Sentenza pubblicata il {data_it(deposito)} e non notificata: appello entro il "
                               f"{data_breve(termine_mesi(deposito, 6))} (sei mesi, sospensione feriale compresa).",
                               [Rif("cpc:327", "dalla pubblicazione della sentenza"), Rif("l742:1", "31 agosto")]))
    else:
        a.dati_mancanti.append("data di pubblicazione della sentenza e, se c'è, data della sua notificazione")
    return a


def riconosci_sospensione_tributaria(c: Comprensione, f: Fatti) -> int:
    t = _t(f)
    return 7 if re.search(_TRIB, t) and re.search(r"sospensi|sospender|fermo amministrativ|ipoteca|pignoramento|danno grave", t) and re.search(
        r"sospensi|sospender", t) else 0


def analizza_sospensione_tributaria(c: Comprensione, f: Fatti) -> Analisi:
    a = Analisi("sospensione_tributaria", "tributario — sospensione", forma=forma(c))
    a.capito = ["Atto impositivo o della riscossione già impugnato (o da impugnare), con esecuzione imminente."]
    a.rimedio = "istanza motivata di sospensione dell'atto impugnato alla Corte di giustizia tributaria"
    a.conclusione = [
        Punto("Se dall'atto impugnato può derivare un danno grave e irreparabile, il ricorrente può chiedere la sospensione "
              "dell'esecuzione con istanza motivata, proposta nel ricorso o con atto separato notificato alle altre parti e "
              "depositato.",
              [Rif("dlgs546:47", "danno grave ed irreparabile"),
               Rif("dlgs546:47", "con istanza motivata proposta nel ricorso o con atto separato")]),
        Punto("Il presidente fissa la trattazione per la prima camera di consiglio utile e comunque non oltre il trentesimo "
              "giorno; in caso di eccezionale urgenza può sospendere subito con decreto motivato fino alla decisione.",
              [Rif("dlgs546:47", "non oltre il trentesimo giorno dalla presentazione"),
               Rif("dlgs546:47", "In caso di eccezionale urgenza")]),
    ]
    if re.search(r"appell|sentenza", _t(f)):
        a.conclusione.append(Punto("Se la causa è in appello, la sospensione dell'esecutività della sentenza si chiede alla "
                                   "Corte di secondo grado per gravi e fondati motivi.",
                                   [Rif("dlgs546:52", "se sussistono gravi e fondati motivi")]))
    a.cosa_fare = ["Documentare il danno grave e irreparabile (situazione patrimoniale, effetti del fermo o dell'ipoteca).",
                   "Allegare gli elementi di fondatezza del ricorso (fumus)."]
    return a


def riconosci_reclamo_tributario(c: Comprensione, f: Fatti) -> int:
    t = _t(f)
    return 7 if re.search(r"mediazione tributari|reclamo[- ]mediazione|reclamo tributari|17[- ]bis|effett\w* (?:di|del) reclamo", t) or (
        re.search(_TRIB + r"|\bavviso\b", t) and re.search(r"reclamo|mediazion", t)) else 0


def analizza_reclamo_tributario(c: Comprensione, f: Fatti) -> Analisi:
    a = Analisi("reclamo_mediazione_tributaria", "tributario — reclamo e mediazione", forma=forma(c))
    a.capito = ["Domanda sul reclamo-mediazione tributario."]
    a.rimedio = "ricorso diretto alla Corte di giustizia tributaria di primo grado, senza reclamo-mediazione"
    a.conclusione = [
        Punto("Il reclamo e la mediazione tributaria non esistono più: l'art. 17-bis d.lgs. 546/1992 è stato abrogato dal "
              "d.lgs. 30 dicembre 2023, n. 220, per i ricorsi notificati dopo la sua entrata in vigore. Oggi il ricorso, anche "
              "di piccolo valore, non produce effetti di reclamo e va proposto direttamente alla Corte di giustizia tributaria.",
              [Rif("dlgs546:17bis", "ARTICOLO ABROGATO DAL D.LGS. 30 DICEMBRE 2023, N. 220")]),
        Punto("Il ricorso si propone entro sessanta giorni dalla notificazione dell'atto impugnato.",
              [Rif("dlgs546:21", "entro sessanta giorni dalla data di notificazione")]),
        Punto("La mediazione civile del d.lgs. 28/2010 non riguarda le liti tributarie: le sue materie obbligatorie sono "
              "elencate tassativamente e non comprendono i tributi.",
              [Rif("dlgs28:5", "e' tenuto preliminarmente a esperire il procedimento di mediazione")]),
    ]
    return a
