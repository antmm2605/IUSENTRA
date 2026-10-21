"""Schede del processo amministrativo (AMM).

Base normativa: codice del processo amministrativo (D.Lgs. 104/2010) artt. 29-120; L. 241/1990 (accesso, silenzio,
autotutela); codice dei contratti D.Lgs. 36/2023; art. 52 D.Lgs. 196/2003 (oscuramento).
Sospensione feriale: i termini processuali sono sospesi dal 1° al 31 agosto, salvo il procedimento cautelare (art. 54
c.p.a.). I termini «liberi» escludono giorno iniziale e finale e si calcolano con un giorno in più.
"""
from scripts.schede_compilazione.comuni import (IN_AVANTI, T, assistito, avvocato, calcolo, causa_pendente, controparte, data_luogo, difensore,
                                                documento, letto, procura)
from scripts.schede_compilazione.costruisci import scheda

CPA = "codice_processo_amministrativo"
FERIALE_CPA = (CPA, "54", "sospensione feriale esclusa nel cautelare")


def _parti(ric="Ricorrente", res="Amministrazione resistente"):
    return [difensore(), procura(), data_luogo(), assistito(ric), controparte(res),
            avvocato("controinteressati", "Controinteressati", "Chi trae vantaggio dall’atto? Almeno uno va evocato a pena di inammissibilità",
                     norma=[(CPA, "41", "notifica ad almeno un controinteressato")])]


def _provvedimento():
    return [documento("atto", "Provvedimento impugnato", "provvedimento amministrativo", ["provvedimento", "determina", "decreto", "delibera", "aggiudicazione"],
                      se_manca="astensione: serve il provvedimento"),
            letto("conoscenza", "Notifica, comunicazione o piena conoscenza", "notifica", "notifica, PEC o pubblicazione",
                  [{"categoria": "data", "campo": "notifica"}, {"categoria": "data", "campo": "comunicazione"}],
                  se_manca="chiedere la data di piena conoscenza: il termine decorre da lì")]


def _deposito():
    return calcolo("deposito", "Deposito del ricorso", "entro 30 giorni dall’ultima notifica (15 nei riti dimezzati), con sospensione feriale salvo cautelare",
                   norma=[(CPA, "45", "deposito del ricorso"), (CPA, "119", "termini dimezzati")])


def _udienza_memorie():
    return [letto("udienza", "Udienza di discussione", "udienza", "avviso di fissazione", [{"categoria": "data", "campo": "udienza"}], obbligatorio=False),
            calcolo("documenti", "Ultimo giorno per i documenti", termine=T("udienza", 41, ritroso=True), regola="40 giorni liberi prima dell’udienza (dimezzati nei riti accelerati)",
                    norma=[(CPA, "73", "documenti"), FERIALE_CPA]),
            calcolo("memorie", "Ultimo giorno per le memorie", termine=T("udienza", 31, ritroso=True), regola="30 giorni liberi prima dell’udienza",
                    norma=[(CPA, "73", "memorie")]),
            calcolo("repliche", "Ultimo giorno per le repliche", termine=T("udienza", 21, ritroso=True), regola="20 giorni liberi prima dell’udienza",
                    norma=[(CPA, "73", "repliche")])]


SCHEDE = [
    scheda("AMM_001", "Ricorso al TAR di annullamento (anche concessioni e sanzioni di settore)", ["AMM_001", "AMM_016", "AMM_017"],
           [(CPA, "29", "azione di annullamento"), (CPA, "40", "contenuto del ricorso"), (CPA, "41", "notifica e termine"), (CPA, "45", "deposito"),
            (CPA, "13", "competenza territoriale inderogabile"), ("legge_241_1990", "21octies", "annullabilità"), ("legge_241_1990", "21quinquies", "revoca"),
            ("legge_241_1990", "21novies", "annullamento d’ufficio"), FERIALE_CPA],
           _parti() + _provvedimento() + [
               calcolo("termine", "Ultimo giorno per notificare il ricorso", termine=T("notifica", 60),
                       regola="60 giorni dalla notifica, comunicazione o piena conoscenza, con sospensione feriale" + IN_AVANTI, norma=[(CPA, "41", "sessanta giorni")]),
               avvocato("motivi", "Motivi", "Incompetenza, violazione di legge, eccesso di potere: per ciascun motivo, norma e vizio", norma=[(CPA, "40", "motivi specifici")]),
               avvocato("giurisdizione", "Giurisdizione e competenza", "La materia è del giudice amministrativo? Quale TAR (sede dell’autorità o effetti dell’atto)?",
                        norma=[(CPA, "13", "competenza")]),
               avvocato("cautelare", "Domanda cautelare", "Si chiede la sospensione? Con quale danno grave e irreparabile?", obbligatorio=False,
                        norma=[(CPA, "55", "misure cautelari")]),
               _deposito(), *_udienza_memorie()],
           [("Fatto", "provvedimento e vicenda"), ("Diritto", "motivi"), ("Conclusioni", "annullamento, eventuale risarcimento e cautela")],
           ["provvedimento non presente", "termine di 60 giorni scaduto", "nessun controinteressato evocato quando esiste"]),

    scheda("AMM_002", "Motivi aggiunti e ricorso incidentale", ["AMM_002", "AMM_003", "AMM_010"],
           [(CPA, "43", "motivi aggiunti"), (CPA, "42", "ricorso incidentale"), (CPA, "117", "ricorso avverso il silenzio"), ("legge_241_1990", "2", "termini del procedimento"),
            FERIALE_CPA],
           _parti("Parte assistita", "Controparte") + [causa_pendente(),
               avvocato("atto", "Atto nuovo o ragione", "Motivi aggiunti contro atti nuovi, ricorso incidentale del controinteressato, o ricorso contro il silenzio?",
                        norma=[(CPA, "43", "atti connessi"), (CPA, "42", "interesse sorto dal ricorso principale"), (CPA, "117", "silenzio")]),
               calcolo("termine", "Termine (diverso per ciascuna azione)",
                       regola="60 giorni dalla conoscenza dell’atto nuovo o dalla notifica del ricorso principale; contro il silenzio finché dura e non oltre un anno dalla scadenza del termine del procedimento",
                       norma=[(CPA, "43", "termini del ricorso"), (CPA, "42", "sessanta giorni"), (CPA, "31", "un anno per il silenzio")])],
           [("Atto", "motivi o domanda con richiesta")], ["causa non pendente per motivi aggiunti o incidentale"]),

    scheda("AMM_004", "Domanda cautelare e istanza di prelievo", ["AMM_004", "AMM_007"],
           [(CPA, "55", "misure cautelari collegiali"), (CPA, "56", "misure monocratiche"), (CPA, "71", "istanza di prelievo"), FERIALE_CPA],
           _parti("Parte assistita", "Controparte") + [causa_pendente(),
               avvocato("pregiudizio", "Danno grave e irreparabile o urgenza", "Quale pregiudizio, e perché non si può attendere?", norma=[(CPA, "55", "presupposti")]),
               calcolo("camera", "Camera di consiglio", "primo giorno utile dopo 20 giorni dall’ultima notifica e 10 dal deposito; senza sospensione feriale",
                       norma=[(CPA, "55", "termini"), FERIALE_CPA])],
           [("Istanza", "fumus, periculum e misure")], ["urgenza non motivata"]),

    scheda("AMM_005", "Memoria, replica e istanze di accesso al fascicolo o di oscuramento", ["AMM_005", "AMM_006", "AMM_008", "AMM_018"],
           [(CPA, "73", "termini per documenti, memorie e repliche"), (CPA, "46", "costituzione delle parti intimate"), ("codice_privacy", "52", "oscuramento dei dati"), FERIALE_CPA],
           _parti("Parte assistita", "Controparte") + [causa_pendente(), *_udienza_memorie(),
               avvocato("atto", "Atto richiesto", "Memoria, replica, accesso al fascicolo o oscuramento dei dati identificativi?",
                        norma=[("codice_privacy", "52", "motivi legittimi")])],
           [("Atto", "difese o istanza")], ["udienza non nota per memorie e repliche"]),

    scheda("AMM_009", "Ricorso per l’accesso agli atti", ["AMM_009"],
           [(CPA, "116", "rito dell’accesso"), ("legge_241_1990", "22", "diritto di accesso"), ("legge_241_1990", "25", "diniego e silenzio"), FERIALE_CPA],
           _parti() + [
               documento("istanza", "Istanza di accesso e diniego", "istanza e risposta dell’amministrazione", ["accesso", "istanza", "diniego"],
                         se_manca="astensione: serve l’istanza di accesso"),
               letto("conoscenza", "Data del diniego o del silenzio", "comunicazione", "risposta o istanza", [{"categoria": "data", "campo": "comunicazione"}]),
               calcolo("termine", "Ultimo giorno per il ricorso", termine=T("comunicazione", 30), regola="30 giorni dal diniego espresso; in caso di silenzio inserire come data la formazione del silenzio-rigetto (30 giorni dopo l’istanza)" + IN_AVANTI,
                       norma=[(CPA, "116", "trenta giorni"), ("legge_241_1990", "25", "silenzio-diniego")])],
           [("Ricorso", "interesse diretto, concreto e attuale; documenti richiesti")], ["istanza di accesso non presentata"]),

    scheda("AMM_011", "Appello al Consiglio di Stato", ["AMM_011"],
           [(CPA, "92", "termini"), (CPA, "101", "contenuto dell’appello"), (CPA, "104", "nuove domande e prove"), FERIALE_CPA],
           _parti("Appellante", "Appellato") + [
               documento("sentenza", "Sentenza appellata", "sentenza del TAR", ["sentenza"], se_manca="astensione: serve la sentenza"),
               letto("notifica", "Notifica della sentenza", "notifica", "relata", [{"categoria": "data", "campo": "notifica"}], obbligatorio=False),
               calcolo("termine_breve", "Appello dalla notifica", termine=T("notifica", 60), regola="60 giorni dalla notifica (30 nei riti dimezzati), con sospensione feriale" + IN_AVANTI,
                       norma=[(CPA, "92", "sessanta giorni"), (CPA, "119", "dimezzamento")]),
               calcolo("termine_lungo", "Appello senza notifica", termine=T("provvedimento", mesi=6), regola="6 mesi dalla pubblicazione (3 nei riti dimezzati)" + IN_AVANTI,
                       norma=[(CPA, "92", "sei mesi")]),
               avvocato("motivi", "Motivi specifici", "Capi impugnati e critiche", norma=[(CPA, "101", "specificità")])],
           [("Motivi", "censure"), ("Conclusioni", "riforma")], ["sentenza non presente", "termini scaduti"]),

    scheda("AMM_012", "Opposizione a decreto presidenziale", ["AMM_012"],
           [(CPA, "85", "opposizione ai decreti di estinzione o improcedibilità")],
           _parti("Parte assistita", "Controparte") + [causa_pendente(),
               letto("comunicazione", "Comunicazione del decreto", "comunicazione", "PEC di segreteria", [{"categoria": "data", "campo": "comunicazione"}]),
               calcolo("termine", "Ultimo giorno per l’opposizione", termine=T("comunicazione", 60), regola="60 giorni dalla comunicazione del decreto" + IN_AVANTI,
                       norma=[(CPA, "85", "opposizione al collegio")])],
           [("Opposizione", "ragioni per cui il decreto non doveva essere emesso")], ["decreto non comunicato o non presente"]),

    scheda("AMM_013", "Ricorso per l’ottemperanza", ["AMM_013"],
           [(CPA, "112", "azione di ottemperanza"), (CPA, "113", "giudice competente"), (CPA, "114", "procedimento e prescrizione decennale")],
           _parti() + [
               documento("titolo", "Sentenza da eseguire con attestazione del passaggio in giudicato o esecutiva", "sentenza", ["sentenza", "giudicato"],
                         se_manca="astensione: serve il titolo"),
               documento("diffida", "Notifica della sentenza e diffida all’amministrazione", "notifica e diffida", ["diffida", "notifica"], obbligatorio=False),
               avvocato("inadempimento", "Inadempimento", "Cosa non ha fatto l’amministrazione? Per crediti, prudenzialmente, attendere 120 giorni dalla notifica del titolo",
                        norma=[(CPA, "114", "procedimento")])],
           [("Ricorso", "titolo, inadempimento, nomina del commissario ad acta e penalità")], ["titolo non presente"]),

    scheda("AMM_014", "Ricorso in materia di appalti pubblici ed esclusione da gara", ["AMM_014", "AMM_015"],
           [(CPA, "119", "rito abbreviato"), (CPA, "120", "rito degli appalti: trenta giorni; appello entro tre mesi dalla pubblicazione"), (CPA, "116", "rito sull’accesso agli atti di gara: dieci giorni"), ("36/2023", "90", "comunicazioni dell’aggiudicazione"),
            ("36/2023", "36", "accesso agli atti di gara"), FERIALE_CPA],
           _parti("Concorrente", "Stazione appaltante") + _provvedimento() + [
               calcolo("termine", "Ultimo giorno per notificare il ricorso", termine=T("comunicazione", 30),
                       regola="30 giorni dalla ricezione della comunicazione dell’art. 90 D.Lgs. 36/2023 o dalla messa a disposizione degli atti di gara (art. 36), con sospensione feriale; per i bandi autonomamente lesivi dalla pubblicazione" + IN_AVANTI,
                       norma=[(CPA, "120", "trenta giorni e decorrenza"), ("36/2023", "90", "comunicazione"), ("36/2023", "36", "messa a disposizione degli atti")]),
               avvocato("motivi", "Motivi", "Vizi dell’aggiudicazione o dell’esclusione e interesse strumentale"),
               _deposito(), avvocato("cautelare", "Domanda cautelare", "Si chiede la sospensione dell’aggiudicazione o della stipula?", obbligatorio=False)],
           [("Fatto", "gara e provvedimento"), ("Diritto", "motivi"), ("Conclusioni", "annullamento, subentro o risarcimento")],
           ["provvedimento o comunicazione non presenti", "trenta giorni scaduti"]),
]
