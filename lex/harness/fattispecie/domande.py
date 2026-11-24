"""Domande puntuali: procedibilità, competenza, rito, termini di esecuzione, condominio, consumatori, amministrativo e
penale. Ogni risposta porta la norma vigente e, se l'avvocato indica una data, la scadenza calcolata dal motore."""
from __future__ import annotations

import re

from ..comprensione import Comprensione
from ..fatti import Fatti, euro
from ..modello import Analisi, Punto, Rif
from ..norme import piano
from .. import procedura as P
from ..termini import data_breve, termine, termine_giorni, termine_mesi, tocca_agosto


def _t(f: Fatti) -> str:
    return piano(f.testo)


def _prima_data(f: Fatti):
    return f.eventi[0].data if f.eventi else None


# ---------------------------------------------------------------------------------- negoziazione / mediazione puntuali
def riconosci_negoziazione(c: Comprensione, f: Fatti) -> int:
    t = _t(f)
    if f.importi and not c.racconto and not f.ha("caparra_confirmatoria") and re.search(
            r"serve (?:qualcosa|altro|un passaggio|un tentativo) prima|prima (?:della causa|di fare causa|di agire|di andare dal giudice)|"
            r"condizion\w* di procedibil|passaggi? (?:obbligatori|preliminari)|tentativo obbligatorio", t) and not f.ha("locazione") and re.search(
            r"prestit|prestat|fattur|credit|soldi|somm|pagament|restitu", t) and not re.search(
            r"sequestr|cautel|urgenz|blocc|congel|svuot|quale giudice|competen|sinistr|incident|circolazion|lavor|condomin|eredit|medic", t):
        return 7
    if "negoziazione" in t and f.importi and not f.ha("caparra_confirmatoria") and not f.ha("consumatore") and not re.search(
            r"sinistr|incident|circolazion|tamponat|consumator", t) and re.search(
            r"obbligatori|serve|occorre|necessari|condizion|devo|dobbiamo|bisogna|prima", t):
        return 5
    return 3 if "negoziazione" in t and f.importi and not c.racconto and not f.ha("caparra_confirmatoria") else 0


def analizza_negoziazione(c: Comprensione, f: Fatti) -> Analisi:
    valore = max(i.valore for i in f.importi)
    a = Analisi("negoziazione_obbligatoria", "procedibilità", valore=valore)
    consumatore = f.ha("consumatore")
    a.capito = [f"Domanda di pagamento di {euro(valore)}: serve la negoziazione assistita prima della causa?"]
    a.conclusione = P.negoziazione_pagamento(valore, consumatore=consumatore)
    a.procedibilita = [
        Punto("Esclusioni: non si applica alle controversie su obbligazioni contrattuali da contratti fra professionisti e "
              "consumatori, ai procedimenti per ingiunzione inclusa l'opposizione, alla consulenza tecnica preventiva, alle "
              "opposizioni nell'esecuzione forzata, ai procedimenti in camera di consiglio e all'azione civile nel processo "
              "penale; né quando la parte può stare in giudizio personalmente; né nei casi di mediazione obbligatoria.",
              [Rif("dl132:3", "contratti conclusi tra professionisti e consumatori"),
               Rif("dl132:3", "procedimenti per ingiunzione, inclusa l'opposizione"),
               Rif("dl132:3", "articolo 5, comma 1-bis")]),
        P.improcedibilita_rimedio(),
    ]
    return a


def riconosci_mediazione(c: Comprensione, f: Fatti) -> int:
    t = _t(f)
    if "mediazion" in t and re.search(r"obbligatori|serve|occorre|necessari|condizion|devo (?:fare|prima)|dobbiamo (?:fare|prima)|bisogna", t) \
            and not re.search(r"quale giudice|competen", t):
        # Chi chiede espressamente della mediazione riceve lo strumento, anche se nomina la materia (locazione, condominio).
        return 4
    return 0


def _materia_mediazione(t: str) -> str | None:
    for nome, parola in (("condominio", "condomin"), ("locazione", "locazion"), ("diritti reali", "servitu|usucapion|proprieta"),
                         ("diffamazione con la stampa o altro mezzo di pubblicità", "diffamazion"),
                         ("patti di famiglia", "patto di famiglia|patti di famiglia"), ("affitto di aziende", "affitto d\\w* azienda"),
                         ("associazione in partecipazione", "associazione in partecipazione"), ("consorzio", "consorzi"),
                         ("franchising", "franchising"), ("somministrazione", "somministrazion"),
                         ("società di persone", "societa di persone|\\bs\\.?n\\.?c\\b|\\bs\\.?a\\.?s\\b"),
                         ("subfornitura", "subfornitur"),
                         ("successioni ereditarie", "eredit|successi"), ("divisione", "divisione"), ("comodato", "comodato"),
                         ("contratti assicurativi, bancari e finanziari", "banca|bancari|assicurat|finanziari|mutuo"),
                         ("responsabilità medica e sanitaria", "medic|sanitari|ospedal")):
        if re.search(parola, t):
            return nome
    return None


def analizza_mediazione(c: Comprensione, f: Fatti) -> Analisi:
    t = _t(f)
    materia = _materia_mediazione(t)
    a = Analisi("mediazione_obbligatoria", "procedibilità")
    a.capito = ["Verifica della mediazione obbligatoria per la controversia descritta."]
    a.conclusione = P.mediazione_obbligatoria(materia)
    if materia is None:
        a.dubbi.append("Materia non riconosciuta fra quelle dell'art. 5, comma 1: indica l'oggetto preciso della lite.")
    return a


# ---------------------------------------------------------------------------------- rito semplificato
def riconosci_semplificato(c: Comprensione, f: Fatti) -> int:
    return 3 if re.search(r"rito semplificato|procedimento semplificato|281-?decies", _t(f)) and not c.racconto else 0


def analizza_semplificato(c: Comprensione, f: Fatti) -> Analisi:
    a = Analisi("rito_semplificato", "civile — rito")
    a.conclusione = [Punto("Il procedimento semplificato di cognizione si usa quando i fatti di causa non sono controversi, "
                           "oppure la domanda è fondata su prova documentale, è di pronta soluzione o richiede "
                           "un'istruzione non complessa; nelle cause in cui il tribunale giudica in composizione "
                           "monocratica la domanda può sempre essere proposta in questa forma. Si introduce con ricorso.",
                           [Rif("cpc:281decies", "fatti di causa non sono controversi"),
                            Rif("cpc:281decies", "composizione monocratica"), Rif("cpc:281undecies", "si propone con ricorso")])]
    return a


# ---------------------------------------------------------------------------------- appello lavoro
def riconosci_appello_lavoro(c: Comprensione, f: Fatti) -> int:
    t = _t(f)
    return 3 if c.tipo == "termine" and re.search(r"appell", t) and re.search(r"lavoro", t) else 0


def analizza_appello_lavoro(c: Comprensione, f: Fatti) -> Analisi:
    a = Analisi("appello_lavoro", "lavoro")
    d = _prima_data(f)
    a.conclusione = [Punto("Nel rito del lavoro l'appello si deposita entro trenta giorni dalla notificazione della "
                           "sentenza (termine breve).", [Rif("cpc:434", "trenta giorni dalla notificazione della sentenza")])]
    a.termini = [Punto("La sospensione feriale dei termini non si applica alle controversie di lavoro.",
                       [Rif("l742:3", "429")])]
    if d:
        scad = termine("LEX_LAV_APPELLO_434", d)
        a.conclusione.append(Punto(f"Sentenza notificata il {data_breve(d)}: appello entro {data_breve(scad)} (senza "
                                   "sospensione feriale).", [Rif("cpc:434", "trenta giorni dalla notificazione della sentenza")]))
    return a


# ---------------------------------------------------------------------------------- esecuzione
def riconosci_opposizione_atti(c: Comprensione, f: Fatti) -> int:
    t = _t(f)
    if re.search(r"opposizione agli atti esecutivi|617", t):
        return 5
    # Vizi di forma del titolo, del precetto o di un atto esecutivo: non si contesta il diritto, ma la regolarità.
    return 5 if re.search(r"precett|pignorament|atto esecutiv|titolo esecutivo", t) and re.search(
        r"\bnull\w*|irregolar|vizi\w* (?:di )?form|manca (?:l |la |il )?(?:avvertiment|indicazion|sottoscrizion|firma)|"
        r"notifica\w* (?:nulla|irregolare|viziata)|difett\w* di (?:forma|notifica)", t) else 0


def analizza_opposizione_atti(c: Comprensione, f: Fatti) -> Analisi:
    a = Analisi("opposizione_atti_esecutivi", "esecuzione")
    a.conclusione = [Punto("L'opposizione agli atti esecutivi si propone entro venti giorni dalla notificazione del titolo "
                           "o del precetto, oppure dal compimento dell'atto esecutivo contestato o dalla sua conoscenza.",
                           [Rif("cpc:617", "venti giorni")])]
    d = _prima_data(f)
    if d:
        a.conclusione.append(Punto(f"Dal {data_breve(d)}: scadenza {data_breve(termine('ESE_OPPOSIZIONE_ATTI_617', d))}, "
                                   "senza sospensione feriale: l'art. 92 ord. giud. esclude le cause di opposizione "
                                   "all'esecuzione e la Cassazione vi comprende l'opposizione agli atti esecutivi (Cass. ord. "
                                   "21568/2017).", [Rif("cpc:617", "venti giorni"), Rif("rd12:92", "opposizione all'esecuzione")]))
    return a


# ---------------------------------------------------------------------------------- condominio
def riconosci_delibera(c: Comprensione, f: Fatti) -> int:
    t = _t(f)
    return 3 if (re.search(r"delibera|deliberazion", t) or re.search(
        r"(?:l |dell |in )assemblea\b[^.]{0,120}(?:approvat|deciso|votat|stabilit)", t)) and "condomin" in t else 0


def analizza_delibera(c: Comprensione, f: Fatti) -> Analisi:
    a = Analisi("impugnazione_delibera", "condominio")
    a.conclusione = [Punto("La delibera contraria alla legge o al regolamento si impugna davanti all'autorità giudiziaria "
                           "nel termine perentorio di trenta giorni, che decorre dalla data della deliberazione per i "
                           "dissenzienti o astenuti e dalla data di comunicazione per gli assenti.",
                           [Rif("cc:1137", "termine perentorio di trenta giorni"), Rif("cc:1137", "comunicazione")])]
    a.procedibilita = P.mediazione_obbligatoria("condominio")
    d = _prima_data(f)
    if d:
        con = termine("CIV_IMPUGNAZIONE_DELIBERA_1137", d)
        senza = termine_giorni(d, 30, sostanziale=True)
        a.conclusione.append(Punto(f"Dal {data_breve(d)}: trenta giorni scadono {data_breve(con)} (termine di decadenza; "
                                   "la sospensione feriale si applica per la sentenza della Corte costituzionale n. 49/1990)"
                                   + (f". Per prudenza conviene agire entro {data_breve(senza)}, la scadenza senza sospensione"
                                      if tocca_agosto(d, senza) else "") + ".",
                                   [Rif("cc:1137", "termine perentorio di trenta giorni"), Rif("l742:1", "sospeso di diritto")]))
    a.avvertenze.append(Punto("La domanda di mediazione, dal momento in cui la comunicazione perviene alle altre parti, "
                              "impedisce la decadenza per una sola volta: va depositata entro i trenta giorni.",
                              [Rif("dlgs28:8", "impedisce la decadenza per una sola volta")]))
    return a


def riconosci_lite_condominio(c: Comprensione, f: Fatti) -> int:
    t = _t(f)
    return 2 if "condomin" in t and re.search(r"mediazione|infiltraz|lastrico|danni|parti comuni|cosa comune|facciata|"
                                              r"canna fumaria|cortile|abusiv", t) and not re.search(r"delibera", t) else 0


def analizza_lite_condominio(c: Comprensione, f: Fatti) -> Analisi:
    a = Analisi("lite_condominio", "condominio")
    a.conclusione = P.mediazione_obbligatoria("condominio")
    return a


# ---------------------------------------------------------------------------------- consumatori
def riconosci_consumatore(c: Comprensione, f: Fatti) -> int:
    return 3 if f.ha("consumatore") and f.importi and re.search(r"giudice|foro|competen|negoziazione", _t(f)) else 0


def analizza_consumatore(c: Comprensione, f: Fatti) -> Analisi:
    valore = max(i.valore for i in f.importi)
    a = Analisi("consumatore", "consumatori", valore=valore)
    giudice, punti = P.giudice_per_valore(valore)
    a.competenza = punti + [Punto("Foro del consumatore: nei contratti fra professionista e consumatore è vessatoria la "
                                  "clausola che fissa un foro diverso da quello di residenza o domicilio elettivo del consumatore, "
                                  "che resta quindi il foro della causa (per le controversie sulle Sezioni I-IV del capo sui diritti dei "
                                  "consumatori nei contratti lo dice espressamente l'art. 66-bis).", [Rif("dlgs206:33", "residenza o domicilio elettivo del consumatore")])]
    a.procedibilita = P.negoziazione_pagamento(valore, consumatore=True)
    a.conclusione = [Punto(f"{giudice} del luogo di residenza o domicilio del consumatore; negoziazione assistita non "
                           "obbligatoria per i contratti fra professionisti e consumatori.",
                           (punti[0].rif if punti else []) + [Rif("dlgs206:33", "residenza o domicilio elettivo del consumatore"),
                                                              Rif("dl132:3", "contratti conclusi tra professionisti e consumatori")])]
    a.giudice = giudice
    return a


# ---------------------------------------------------------------------------------- amministrativo
def riconosci_straordinario(c: Comprensione, f: Fatti) -> int:
    return 4 if re.search(r"ricorso straordinario|ricorso al (?:presidente della repubblica|capo dello stato)", _t(f)) else 0


def analizza_straordinario(c: Comprensione, f: Fatti) -> Analisi:
    a = Analisi("ricorso_straordinario", "amministrativo")
    a.conclusione = [Punto("Il ricorso straordinario al Presidente della Repubblica si propone entro centoventi giorni "
                           "dalla notificazione o comunicazione dell'atto impugnato o da quando l'interessato ne ha avuto "
                           "piena conoscenza.", [Rif("dpr1199:9", "centoventi giorni")])]
    a.inquadramento = [
        Punto("Il ricorso straordinario è ammesso contro gli atti amministrativi definitivi, per soli motivi di legittimità, ed "
              "è alternativo al ricorso al TAR: se l'atto è già stato impugnato in sede giurisdizionale dallo stesso "
              "interessato, il ricorso straordinario non è ammesso.",
              [Rif("dpr1199:8", "Contro gli atti amministrativi definitivi"), Rif("dpr1199:8", "per motivi di legittimita'"),
               Rif("dpr1199:8", "non e' ammesso il ricorso straordinario da parte dello stesso interessato")]),
        Punto("I controinteressati, entro sessanta giorni dalla notificazione del ricorso, possono chiedere che sia deciso in "
              "sede giurisdizionale (trasposizione): il ricorrente che vuole insistere deve costituirsi davanti al giudice "
              "amministrativo entro sessanta giorni dal ricevimento dell'opposizione.",
              [Rif("dpr1199:10", "entro il termine di sessanta giorni dalla notificazione del ricorso"),
               Rif("dpr1199:10", "nel termine di sessanta giorni dal ricevimento dell'atto di opposizione")]),
    ]
    a.rimedio = "ricorso straordinario al Presidente della Repubblica entro centoventi giorni, in alternativa al TAR"
    a.forma = "atto" if c.tipo == "redazione" else "parere (consulenza)"
    return a


# ---------------------------------------------------------------------------------- penale
def riconosci_querela(c: Comprensione, f: Fatti) -> int:
    if "querel" not in _t(f) or not re.search(r"termin|entro|quando|tempo|mesi|parere", _t(f)):
        return 0
    # La domanda sul termine della querela nella richiesta prevale sul racconto della diffamazione (risarcimento civile).
    richiesta = piano(f.richiesta)
    if re.search(r"querel", richiesta) and re.search(r"termin|entro|quando|tempo|mesi|scad|aspett|ancora in tempo", richiesta):
        return 7
    return 3


def analizza_querela(c: Comprensione, f: Fatti) -> Analisi:
    a = Analisi("termine_querela", "penale", modello="PEN_009")
    a.conclusione = [Punto("Salvo che la legge disponga altrimenti, il diritto di querela si esercita entro tre mesi dal "
                           "giorno della notizia del fatto che costituisce il reato.", [Rif("cp:124", "tre mesi")])]
    d = _prima_data(f)
    if d:
        a.conclusione.append(Punto(f"Notizia del fatto il {data_breve(d)}: querela entro {data_breve(termine("PEN_QUERELA_124", d))}.",
                                   [Rif("cp:124", "tre mesi")]))
    a.avvertenze.append(Punto("Il termine di tre mesi vale salvo che la legge disponga altrimenti: alcuni reati hanno "
                              "termini diversi, da verificare sulla norma del reato specifico.",
                              [Rif("cp:124", "Salvo che la legge disponga altrimenti")]))
    t = _t(f)
    from .strumenti import data_di

    notizia = data_di(f, r"apprende|viene a sapere|ha saputo|notizia")
    if notizia:
        lim = termine("PEN_QUERELA_124", notizia)
        a.conclusione = [Punto(f"Il termine decorre dalla notizia del fatto ({notizia.strftime('%d/%m/%Y')}), non dalla "
                               f"pubblicazione: querela entro {data_breve(lim)}.", [Rif("cp:124", "tre mesi")])]
    if re.search(r"facebook|instagram|tiktok|social|\bpost\b|pubblic|online|sul web|in rete", t):
        a.inquadramento.append(Punto("Offesa all'altrui reputazione comunicando con più persone: diffamazione, aggravata se "
                                     "commessa con un mezzo di pubblicità come un social network.",
                                     [Rif("cp:595", "comunicando con piu persone"), Rif("cp:595", "mezzo di pubblicita")]))
        a.inquadramento.append(Punto("La diffamazione è punibile a querela della persona offesa, presentata nelle forme dell'art. "
                                     "336 c.p.p.", [Rif("cp:597", "querela della persona offesa"), Rif("cpp:336", "querela")]))
        a.rimedio = "querela per diffamazione aggravata entro tre mesi dalla notizia, senza atti che valgano rinuncia"
        a.giudice = "Procura della Repubblica competente"
        a.forma = "parere (consulenza)"
        if re.search(r"sei mesi|6 mesi|febbraio|piu tardi|con calma", t):
            a.avvertenze.append(Punto("Il termine è di tre mesi dalla notizia del fatto: aspettare oltre farebbe perdere la "
                                      "querela" + ("; i «sei mesi» della richiesta sono sbagliati." if re.search(r"sei mesi|6 mesi", t)
                                                   else "."), [Rif("cp:124", "tre mesi")]))
        if re.search(r"cancell|rimuov|togli|lasci\w* perdere|in cambio|accordo|ritratt", t):
            a.avvertenze.append(Punto("Accettare la proposta di cancellare il post in cambio di «lasciar perdere» può valere "
                                      "come rinuncia tacita: non accettarla prima di aver presentato querela.",
                                      [Rif("cp:124", "rinuncia espressa o tacita")]))
        else:
            a.avvertenze.append(Punto("Atti incompatibili con la volontà di querelare possono valere come rinuncia tacita: "
                                      "nessun accordo con l'autore del post prima di aver presentato querela.",
                                      [Rif("cp:124", "rinuncia espressa o tacita")]))
        a.inquadramento.append(Punto("Il diritto di querela non si esercita se c'è stata rinuncia espressa o tacita.",
                                     [Rif("cp:124", "rinuncia espressa o tacita")]))
        a.dati_mancanti = ["screenshot con data e link del post", "dati del querelato"]
    return a


def riconosci_appello_penale(c: Comprensione, f: Fatti) -> int:
    t = _t(f)
    return 3 if re.search(r"appell|impugnazion", t) and re.search(r"penal|imputat|reato", t) and c.tipo in {"termine", "parere"} else 0


def analizza_appello_penale(c: Comprensione, f: Fatti) -> Analisi:
    a = Analisi("impugnazione_penale", "penale")
    a.conclusione = [Punto("Il termine per l'impugnazione penale è di quindici giorni se la motivazione è contestuale, di "
                           "trenta giorni se la motivazione è depositata entro il quindicesimo giorno, di quarantacinque "
                           "giorni se il giudice fissa un termine più lungo per la motivazione.",
                           [Rif("cpp:585", "quindici giorni"), Rif("cpp:585", "trenta giorni"), Rif("cpp:585", "quarantacinque giorni")])]
    a.dubbi.append("Per il difensore dell'imputato giudicato in assenza i termini sono aumentati di quindici giorni: "
                   "verifica il caso concreto sul testo dell'art. 585 c.p.p.")
    return a


# ---------------------------------------------------------------------------------- TAR e tributario
def riconosci_tar(c: Comprensione, f: Fatti) -> int:
    t = _t(f)
    atto_amministrativo = re.search(r"\btar\b|tribunale amministrativo|diniego|permesso di costruire|ordinanza (?:sindacale|di demolizione)|"
                                    r"aggiudicazion|esclusione dalla gara|provvedimento (?:amministrativo|del comune|della regione)|"
                                    r"revoca dell autorizzazione|annullamento d ufficio", t)
    if re.search(r"ricorso straordinario|presidente della repubblica|capo dello stato", t):
        return 0
    # Provvedimenti che non vanno al TAR: protezione internazionale, unità familiare, prestazioni previdenziali.
    if re.search(r"protezione (?:internazionale|sussidiaria|speciale)|asilo|rifugiat|ricongiungimento|motivi familiari|"
                 r"naspi|\binps\b|pension|invalidit|indennita di disoccupazione", t):
        return 0
    return 3 if atto_amministrativo and re.search(r"impugn|ricors|termin|entro", t) else 0


def analizza_tar(c: Comprensione, f: Fatti) -> Analisi:
    a = Analisi("ricorso_tar", "amministrativo", modello="AMM_001")
    a.conclusione = [Punto("L'azione di annullamento davanti al TAR si propone nel termine di decadenza di sessanta giorni, "
                           "che decorre dalla notificazione, comunicazione o piena conoscenza del provvedimento.",
                           [Rif("cpa:29", "termine di decadenza di sessanta giorni"),
                            Rif("cpa:41", "piena conoscenza")])]
    a.termini = [Punto("La sospensione feriale dei termini (1-31 agosto) si applica anche ai termini del processo "
                       "amministrativo.", [Rif("l742:1", "giurisdizioni ordinarie ed a quelle amministrative")])]
    from .strumenti import data_di as _data_di

    d = _data_di(f, r"notificat|comunicat") or _prima_data(f)
    if d:
        a.conclusione.append(Punto(f"Provvedimento notificato il {data_breve(d)}: ricorso da notificare entro "
                                   f"{data_breve(termine('AMM_RICORSO_29', d))} (sessanta giorni con la sospensione feriale).",
                                   [Rif("cpa:29", "sessanta giorni"), Rif("l742:1", "giurisdizioni ordinarie ed a quelle amministrative")]))
    a.avvertenze += [
        Punto("I sessanta giorni non valgono per tutti i riti: per gli atti delle procedure di affidamento di lavori, servizi "
              "e forniture il ricorso si propone nel termine di trenta giorni.",
              [Rif("cpa:120", "sono proposti nel termine di trenta giorni")]),
        Punto("Nelle materie del rito abbreviato i termini processuali ordinari sono dimezzati, ma non quello per notificare "
              "il ricorso introduttivo.",
              [Rif("cpa:119", "Tutti i termini processuali ordinari sono dimezzati"),
               Rif("cpa:119", "quelli per la notificazione del ricorso introduttivo")]),
        Punto("Contro il silenzio dell'amministrazione si agisce finché perdura l'inadempimento e comunque non oltre un anno "
              "dalla scadenza del termine di conclusione del procedimento.",
              [Rif("cpa:31", "non oltre un anno dalla scadenza del termine di conclusione del procedimento")]),
    ]
    a.avvertenze.append(Punto("Per l'accesso ai documenti il rito è speciale: il ricorso si propone entro trenta giorni "
                              "dalla conoscenza della determinazione o dalla formazione del silenzio.",
                              [Rif("cpa:116", "il ricorso e' proposto entro trenta giorni dalla conoscenza della "
                                              "determinazione impugnata o dalla formazione del silenzio")]))
    t = _t(f)
    if re.search(r"annullamento d ufficio|autotutela", t):
        from .strumenti import data_di

        rilascio = data_di(f, r"rilascia")
        annull = data_di(f, r"adotta la determinazione|adotta\w*[^.]{0,60}annullamento") or data_di(f, r"annullamento d ufficio")
        a.forma = "atto" if c.tipo == "redazione" else "parere (consulenza)"
        a.rimedio = "ricorso al TAR per l'annullamento dell'atto di annullamento d'ufficio, con istanza cautelare"
        a.giudice = "TAR competente per territorio (sede dell'ente)"
        m_com = re.search(r"comune di ([a-z ]+?)(?: rilascia| \(|,|\.| notific)", t)
        if m_com:
            try:
                from pct.territorio_italia import get_comune

                com = get_comune(nome=m_com.group(1).strip())
            except Exception:
                com = None
            if com:
                a.giudice = (f"TAR {com.regione} (sede o sezione competente per la provincia di {com.provincia}, da verificare) "
                             "— atto di un ente con sede nella regione")
        a.inquadramento.append(Punto(
            "L'annullamento d'ufficio dei provvedimenti di autorizzazione è possibile entro un termine ragionevole, comunque "
            "non superiore a sei mesi dall'adozione, con motivazione sull'interesse pubblico e sugli interessi dei destinatari; "
            "il limite non vale per i provvedimenti ottenuti con false rappresentazioni o dichiarazioni mendaci.",
            [Rif("l241:21nonies", "non superiore a sei mesi dal momento dell'adozione"), Rif("l241:21nonies", "false rappresentazioni")]))
        if rilascio:
            lim6 = termine_mesi(rilascio, 6, sostanziale=True)
            a.termini.append(Punto(f"Permesso adottato il {rilascio.strftime('%d/%m/%Y')}: potere di annullamento fino al "
                                   f"{data_breve(lim6)}" + (f"; l'annullamento del {annull.strftime('%d/%m/%Y')} è tardivo." if annull and annull > lim6 else "."),
                                   [Rif("l241:21nonies", "non superiore a sei mesi dal momento dell'adozione")]))
        a.rito = [Punto("Il ricorso è notificato all'amministrazione e ad almeno un controinteressato entro il termine, poi "
                        "depositato; contiene gli elementi dell'art. 40 c.p.a.",
                        [Rif("cpa:41", "controinteressati"), Rif("cpa:40", "motivi")])]
        a.dati_mancanti = ["codice fiscale della ricorrente", "indirizzo del controinteressato"]
        m_sp = re.search(r"spese documentate per euro ([\d.]+)", t)
        if m_sp:
            a.capito.append(f"Spese già sostenute per i lavori: {euro(float(m_sp.group(1).replace('.', '')))} (rilevano per "
                            "l'affidamento e per il danno grave nell'istanza cautelare).")
        if c.tipo == "redazione":
            from ..bozze import ricorso_generico

            a.bozza = ricorso_generico(
                "Ricorso al TAR con istanza cautelare (artt. 29, 40 e 41 c.p.a.)", a.giudice, f,
                "annullamento della determinazione di annullamento d'ufficio del permesso di costruire",
                ["Violazione dell'art. 21-nonies l. 241/1990: annullamento adottato oltre sei mesi dall'adozione del permesso, "
                 "senza false rappresentazioni.", "Difetto di motivazione sull'interesse pubblico e sull'affidamento della titolare.",
                 "Istanza cautelare: danno grave e irreparabile (lavori avviati e spese sostenute)."],
                "annullare l'atto impugnato, previa sospensione cautelare; con vittoria di spese.",
                "permesso di costruire, atto impugnato con notifica, documentazione delle spese.", "artt. 40 e 41 c.p.a.")
    return a


def riconosci_tributario(c: Comprensione, f: Fatti) -> int:
    t = _t(f)
    return 3 if re.search(r"avviso di accertamento|cartella|tributar|agenzia delle entrate|intimazione di pagamento fiscal|avviso (?:imu|tari)|\bimu\b|\btari\b", t) and re.search(r"ricors|impugn|termin|entro", t) else 0


def analizza_tributario(c: Comprensione, f: Fatti) -> Analisi:
    a = Analisi("ricorso_tributario", "tributario", modello="TRI_001")
    a.conclusione = [Punto("Il ricorso alla Corte di giustizia tributaria di primo grado si propone, a pena di "
                           "inammissibilità, entro sessanta giorni dalla notificazione dell'atto impugnato.",
                           [Rif("dlgs546:21", "entro sessanta giorni dalla data di notificazione")])]
    a.termini = [Punto("Il termine è sospeso dal 1° al 31 agosto.", [Rif("l742:1", "31 agosto")])]
    from .strumenti import data_di as _data_di

    d = _data_di(f, r"notifica\w*[^.]{0,80}avviso|avviso[^.]{0,40}notificat") or _prima_data(f)
    if d:
        cost = termine("TRIB_COSTITUZIONE_22", termine("TRIB_RICORSO_21", d))
        a.termini.append(Punto(f"Costituzione in giudizio entro trenta giorni dalla notifica del ricorso: se il ricorso è "
                               f"notificato l'ultimo giorno utile, entro {data_breve(cost)}.", [Rif("dlgs546:22", "trenta giorni")]))
    if d:
        a.conclusione.append(Punto(f"Atto notificato il {data_breve(d)}: ricorso da notificare entro "
                                   f"{data_breve(termine('TRIB_RICORSO_21', d))} (sessanta giorni con la sospensione feriale).",
                                   [Rif("dlgs546:21", "entro sessanta giorni dalla data di notificazione")]))
    t = _t(f)
    from .strumenti import data_di

    dich = data_di(f, r"presenta la dichiarazione|dichiarazione dei redditi")
    if dich:
        from datetime import date as _date

        lim = _date(dich.year + 5, 12, 31)
        notif = data_di(f, r"notifica[^.]{0,40}avviso|avviso di accertamento")
        a.inquadramento = [Punto(
            f"Gli avvisi di accertamento vanno notificati, a pena di decadenza, entro il 31 dicembre del quinto anno successivo "
            f"a quello di presentazione della dichiarazione: dichiarazione del {dich.strftime('%d/%m/%Y')}, termine "
            f"{lim.strftime('%d/%m/%Y')}" + (f"; avviso notificato il {notif.strftime('%d/%m/%Y')}: l'Agenzia è decaduta "
                                            "(vizio assorbente da proporre come primo motivo)." if notif and notif > lim else "."),
            [Rif("dpr600:43", "entro il 31 dicembre del quinto anno successivo")])]
        a.forma = "atto" if c.tipo == "redazione" else "parere (consulenza)"
        a.rimedio = "ricorso alla Corte di giustizia tributaria di primo grado (artt. 18 e 21 d.lgs. 546/1992)"
        a.giudice = "Corte di giustizia tributaria di primo grado della provincia dell'ufficio che ha emesso l'atto"
        a.rito = [Punto("Il ricorso contiene gli elementi dell'art. 18 e il ricorrente si costituisce entro trenta giorni dalla "
                        "proposizione del ricorso.", [Rif("dlgs546:18", "ricorso"), Rif("dlgs546:22", "trenta giorni")])]
        a.dati_mancanti = ["codice fiscale e PEC del ricorrente", "relata di notifica dell'avviso"]
        m_imp = re.search(r"maggiore imposta di euro ([\d.]+)", t)
        if m_imp:
            a.capito.append(f"Maggiore imposta accertata: {euro(float(m_imp.group(1).replace('.', '')))}, oltre sanzioni e interessi.")
        if c.tipo == "redazione":
            from ..bozze import ricorso_generico

            a.bozza = ricorso_generico(
                "Ricorso alla Corte di giustizia tributaria di primo grado (artt. 18 e 21 d.lgs. 546/1992)", a.giudice, f,
                "annullamento dell'avviso di accertamento",
                ["Decadenza dell'Agenzia dal potere di accertamento (art. 43 d.P.R. 600/1973).",
                 "Nel merito: i versamenti sono la restituzione di un prestito, documentata.",],
                "annullare l'avviso per decadenza e, in subordine, nel merito; con vittoria di spese.",
                "avviso con relata, dichiarazione, scrittura di prestito, bonifici.", "art. 18 d.lgs. 546/1992")
    a.avvertenze.append(Punto(
        "L'istanza di accertamento con adesione presentata prima del ricorso sospende il termine per impugnare per novanta "
        "giorni dalla presentazione; dopo l'avviso è ammessa solo per gli atti per i quali non si applica il contraddittorio "
        "preventivo: verifica se è stata presentata.",
        [Rif("dlgs218:6", "sono sospesi per un periodo di novanta giorni dalla data di presentazione dell'istanza"),
         Rif("dlgs218:6", "per i quali non si applica il contraddittorio preventivo")]))
    return a
