"""Schede del rito del lavoro e previdenziale (LAV).

Base normativa: artt. 409-447 c.p.c.; L. 604/1966 e D.Lgs. 23/2015 sui licenziamenti; art. 18 L. 300/1970;
D.Lgs. 81/2015 sui contratti a termine e sulle collaborazioni; artt. 2087, 2103, 2109, 2113, 2120, 2948 c.c.
Sospensione feriale esclusa per le controversie di lavoro e previdenza (art. 3 L. 742/1969, art. 92 ord. giud.);
i termini di impugnazione del licenziamento e del termine sono sostanziali e non si sospendono.
"""
from scripts.schede_compilazione.comuni import (CC, CPC, IN_AVANTI, SENZA_FERIALE, T, A_RITROSO, assistito, avvocato, calcolo,
                                                causa_pendente, controparte, data_luogo, difensore, documento, fatti_documentati, letto, lex, procura,
                                                udienza, ufficio_da_adire)
from scripts.schede_compilazione.costruisci import scheda

ESTENSIONI = {}
COMPETENZA = [(CPC, "413", "giudice del lavoro del luogo in cui è sorto il rapporto o si trova l’azienda o la dipendenza")]


def _parti(ric="Lavoratore", res="Datore di lavoro"):
    return [difensore(), procura(), data_luogo(), assistito(ric), controparte(res)]


def _rapporto():
    return [documento("contratto", "Contratto, lettera di assunzione, buste paga", "contratto di lavoro e buste paga", ["contratto", "busta", "cedolino", "assunzione"],
                      se_manca="chiedere contratto o buste paga"),
            avvocato("rapporto", "Dati del rapporto", "Date di inizio e fine, inquadramento e CCNL, mansioni effettive, orario, retribuzione",
                     norma=[(CPC, "414", "esposizione dei fatti e degli elementi di diritto")])]


def _ricorso_414():
    return [ufficio_da_adire(COMPETENZA),
            avvocato("prove", "Mezzi di prova", "Testimoni con capitoli, documenti, richieste di esibizione: vanno indicati a pena di decadenza",
                     norma=[(CPC, "414", "indicazione specifica dei mezzi di prova")]),
            calcolo("notifica", "Notifica di ricorso e decreto", "almeno 30 giorni prima dell’udienza (40 se all’estero), entro 10 giorni dal decreto; senza sospensione feriale",
                    termine=T("udienza", 30, ritroso=True, feriale=False), norma=[(CPC, "415", "termini di notifica"), *SENZA_FERIALE])]


def _certificazione_sanitaria():
    return documento("sanitaria", "Documentazione sanitaria o contributiva", "certificati medici o estratto contributivo", ["certificato", "estratto", "contributivo"],
                     obbligatorio=False)


SCHEDE = [
    scheda("LAV_002", "Memoria difensiva nel rito del lavoro", ["LAV_002"],
           [(CPC, "416", "costituzione del convenuto"), (CPC, "418", "domanda riconvenzionale"), *SENZA_FERIALE],
           _parti("Parte convenuta", "Ricorrente") + [causa_pendente(), udienza(),
               documento("ricorso", "Ricorso e decreto notificati", "ricorso introduttivo notificato", ["ricorso"], se_manca="astensione: serve il ricorso"),
               calcolo("costituzione", "Ultimo giorno per costituirsi", termine=T("udienza", 10, ritroso=True, feriale=False),
                       regola="almeno 10 giorni prima dell’udienza, senza sospensione feriale" + A_RITROSO, norma=[(CPC, "416", "dieci giorni")]),
               avvocato("difese", "Eccezioni e prese di posizione", "Eccezioni processuali e di merito non rilevabili d’ufficio, presa di posizione precisa su ogni fatto",
                        norma=[(CPC, "416", "decadenza e onere di contestazione")]),
               avvocato("prove", "Mezzi di prova", "Testimoni con capitoli e documenti: a pena di decadenza", norma=[(CPC, "416", "mezzi di prova")]),
               avvocato("riconvenzionale", "Domanda riconvenzionale", "C’è una domanda riconvenzionale? Va chiesto lo spostamento dell’udienza",
                        obbligatorio=False, norma=[(CPC, "418", "nuova udienza")])],
           [("Difese", "contestazione specifica dei fatti, eccezioni, prove"), ("Conclusioni", "rigetto ed eventuale riconvenzionale")],
           ["ricorso non presente", "udienza non nota", "costituzione tardiva: decadenza da eccezioni e prove"]),

    scheda("LAV_003", "Ricorso per impugnazione del licenziamento e reintegrazione", ["LAV_003", "LAV_004"],
           [(CPC, "414", "ricorso"), ("legge_604_1966", "6", "impugnazione entro sessanta giorni e deposito entro centottanta"),
            ("legge_604_1966", "2", "forma scritta e motivazione"), ("23/2015", "2", "licenziamento nullo o discriminatorio"),
            ("23/2015", "3", "licenziamento ingiustificato"), ("legge_300_1970", "18", "tutela reintegratoria per gli assunti prima del 7 marzo 2015"), *SENZA_FERIALE],
           _parti() + _rapporto() + [
               documento("lettera", "Lettera di licenziamento", "comunicazione di licenziamento", ["licenziamento"], se_manca="astensione: serve la lettera"),
               documento("impugnazione", "Impugnazione stragiudiziale con prova della ricezione", "lettera o PEC di impugnazione", ["impugnazione"],
                         se_manca="segnalare il termine di 60 giorni dalla comunicazione"),
               calcolo("termine_impugnazione", "Ultimo giorno per l’impugnazione stragiudiziale", termine=T("comunicazione", 60, feriale=False),
                       regola="60 giorni dalla ricezione della comunicazione; termine sostanziale, senza sospensione feriale" + IN_AVANTI,
                       norma=[("legge_604_1966", "6", "sessanta giorni")]),
               calcolo("termine_deposito", "Ultimo giorno per depositare il ricorso", termine=T("evento", 180, feriale=False),
                       regola="180 giorni dalla trasmissione dell’impugnazione stragiudiziale (evento); se la conciliazione o l’arbitrato sono rifiutati o falliscono, 60 giorni da lì",
                       norma=[("legge_604_1966", "6", "centottanta giorni e sessanta dopo il rifiuto")]),
               avvocato("prioritario", "Domanda di reintegra", "Si chiede la reintegra? Si applica la trattazione prioritaria", obbligatorio=False,
                        norma=[(CPC, "441bis", "trattazione prioritaria dei licenziamenti con reintegra")]),
               avvocato("regime", "Regime di tutela", "Data di assunzione, numero di dipendenti, tipo di vizio (nullità, discriminazione, giusta causa, giustificato motivo)",
                        norma=[("23/2015", "1", "campo di applicazione"), ("legge_300_1970", "18", "requisiti dimensionali")])] + _ricorso_414(),
           [("Fatti", "rapporto, licenziamento e impugnazione"), ("Diritto", "vizi del licenziamento e tutela applicabile"), ("Conclusioni", "reintegra o indennità")],
           ["lettera di licenziamento non presente", "impugnazione oltre 60 giorni o ricorso oltre 180: segnalare la decadenza"]),

    scheda("LAV_005", "Ricorso per crediti di lavoro (differenze retributive, TFR, ferie e permessi)", ["LAV_005", "LAV_006", "LAV_007"],
           [(CPC, "414", "ricorso"), (CC, "2099", "retribuzione"), (CC, "2120", "trattamento di fine rapporto"), (CC, "2109", "ferie"),
            (CC, "2948", "prescrizione quinquennale"), (CPC, "429", "rivalutazione e interessi"), *SENZA_FERIALE],
           _parti() + _rapporto() + [
               lex("conteggi", "Conteggi", "calcolare le differenze mese per mese dai documenti caricati e dal CCNL indicato, senza stime; se mancano dati, dirlo"),
               avvocato("prescrizione", "Prescrizione", "Da quando decorre la prescrizione (cessazione del rapporto o in corso) e ci sono atti interruttivi?",
                        norma=[(CC, "2948", "cinque anni"), (CC, "2943", "interruzione")])] + _ricorso_414(),
           [("Fatti", "rapporto e voci non pagate"), ("Conteggi", "prospetto analitico"), ("Conclusioni", "condanna con rivalutazione e interessi")],
           ["buste paga o CCNL non disponibili per i conteggi"]),

    scheda("LAV_008", "Ricorso per la qualificazione del rapporto o la conversione del contratto a termine", ["LAV_008", "LAV_009"],
           [(CPC, "414", "ricorso"), (CC, "2094", "lavoro subordinato"), ("81/2015", "2", "collaborazioni etero-organizzate"),
            ("81/2015", "19", "durata e causali del contratto a termine"), ("81/2015", "28", "impugnazione entro centottanta giorni e indennità"), *SENZA_FERIALE],
           _parti() + _rapporto() + [fatti_documentati("Indici della subordinazione o vizi del termine"),
               calcolo("termine", "Impugnazione del contratto a termine", termine=T("evento", 180, feriale=False),
                       regola="180 giorni dalla cessazione del singolo contratto, poi ricorso entro 180 giorni dall’impugnazione; senza sospensione feriale",
                       norma=[("81/2015", "28", "impugnazione"), ("legge_604_1966", "6", "deposito del ricorso")])] + _ricorso_414(),
           [("Fatti", "modalità della prestazione o successione dei contratti"), ("Conclusioni", "accertamento, conversione, indennità")],
           ["contratto a termine impugnato oltre 180 giorni dalla cessazione"]),

    scheda("LAV_010", "Ricorso per mobbing o demansionamento", ["LAV_010", "LAV_011"],
           [(CPC, "414", "ricorso"), (CC, "2087", "tutela dell’integrità fisica e della personalità morale"), (CC, "2103", "mansioni"), *SENZA_FERIALE],
           _parti() + _rapporto() + [fatti_documentati("Condotte, mansioni prima e dopo, periodo, documenti e certificazioni"),
               avvocato("danno", "Danni lamentati", "Danno professionale, biologico, morale: con quali prove (certificazioni, testimoni)?",
                        norma=[(CC, "2087", "responsabilità del datore")])] + _ricorso_414(),
           [("Fatti", "condotte specifiche e collegamento con il danno"), ("Conclusioni", "accertamento, reintegra nelle mansioni, risarcimento")],
           ["condotte non specificate con date e fatti"]),

    scheda("LAV_013", "Ricorso previdenziale e assistenziale (INPS, invalidità, accompagnamento)", ["LAV_013", "LAV_014", "LAV_015"],
           [(CPC, "442", "controversie previdenziali"), (CPC, "443", "domanda amministrativa e ricorso amministrativo"),
            (CPC, "444", "giudice competente: residenza dell’attore"), ("dpr_639_1970", "47", "decadenza previdenziale"), ("dl_269_2003", "42", "decadenza semestrale nell’invalidità civile"), (CPC, "445bis", "accertamento tecnico preventivo obbligatorio solo per invalidità civile, handicap e prestazioni sanitarie"), *SENZA_FERIALE],
           _parti("Assicurato o assistito", "Ente previdenziale") + [
               documento("domanda", "Domanda amministrativa e provvedimento dell’ente", "domanda, verbale o diniego dell’ente", ["domanda", "verbale", "diniego", "inps"],
                         se_manca="astensione: la domanda giudiziale è improcedibile senza la domanda amministrativa"),
               _certificazione_sanitaria(),
               avvocato("fase", "Fase", "Ricorso per ATP, dichiarazione di dissenso o ricorso dopo l’ATP?",
                        norma=[(CPC, "445bis", "dissenso entro il termine assegnato, ricorso entro trenta giorni dal deposito del dissenso")]),
               letto("comunicazione", "Comunicazione del provvedimento o della decisione sul ricorso amministrativo", "comunicazione", "lettera o PEC dell’ente",
                     [{"categoria": "data", "campo": "comunicazione"}]),
               calcolo("decadenza_invalidita", "Ultimo giorno per l’azione in invalidità civile", termine=T("comunicazione", mesi=6, feriale=False),
                       regola="invalidità civile, handicap e accompagnamento: sei mesi dalla comunicazione del provvedimento amministrativo, a pena di decadenza; termine sostanziale",
                       norma=[("dl_269_2003", "42", "sei mesi")]),
               calcolo("decadenza_inps", "Decadenza nelle prestazioni previdenziali INPS",
                       "pensioni: tre anni; altre prestazioni (gestione dell’art. 24 L. 88/1989): un anno; dalla comunicazione della decisione sul ricorso amministrativo o dalla scadenza dei termini per deciderlo, e per le prestazioni riconosciute in parte dal riconoscimento parziale",
                       norma=[("dpr_639_1970", "47", "tre anni e un anno")]),
               calcolo("ufficio", "Giudice competente", "tribunale in funzione di giudice del lavoro del luogo di residenza dell’attore", norma=[(CPC, "444", "competenza")])],
           [("Ricorso", "prestazione, domanda amministrativa, requisiti sanitari o contributivi")],
           ["domanda amministrativa non presente"]),

    scheda("LAV_016", "Appello o reclamo in materia di lavoro", ["LAV_016", "LAV_017"],
           [(CPC, "433", "appello"), (CPC, "434", "contenuto dell’appello"), (CPC, "435", "decreto e notifica"), (CPC, "325", "trenta giorni dalla notifica"),
            (CPC, "327", "sei mesi dalla pubblicazione"), (CPC, "669terdecies", "reclamo cautelare entro quindici giorni"), *SENZA_FERIALE],
           _parti("Appellante o reclamante", "Appellato") + [
               documento("sentenza", "Sentenza o ordinanza impugnata", "provvedimento impugnato", ["sentenza", "ordinanza"], se_manca="astensione: serve il provvedimento"),
               letto("notifica", "Data di notifica del provvedimento", "notifica", "relata", [{"categoria": "data", "campo": "notifica"}, {"categoria": "prova_notifica"}],
                     obbligatorio=False),
               calcolo("termine_breve", "Ultimo giorno per l’appello", termine=T("notifica", 30, feriale=False),
                       regola="30 giorni dalla notifica della sentenza, senza sospensione feriale" + IN_AVANTI, norma=[(CPC, "325", "termine breve")]),
               calcolo("termine_lungo", "Ultimo giorno senza notifica", termine=T("provvedimento", mesi=6, feriale=False),
                       regola="6 mesi dalla pubblicazione, senza sospensione feriale" + IN_AVANTI, norma=[(CPC, "327", "termine lungo")]),
               avvocato("motivi", "Motivi", "Per ogni capo: parte impugnata, modifiche richieste, violazioni di legge e rilevanza",
                        norma=[(CPC, "434", "motivi specifici a pena di inammissibilità")])],
           [("Motivi", "censure specifiche per capo"), ("Conclusioni", "riforma")],
           ["provvedimento non presente", "termini scaduti"]),

    scheda("LAV_018", "Verbale di conciliazione in sede protetta", ["LAV_018"],
           [(CPC, "410", "tentativo di conciliazione"), (CPC, "411", "processo verbale"), (CC, "2113", "rinunzie e transazioni")],
           _parti() + _rapporto() + [
               avvocato("accordo", "Contenuto dell’accordo", "Somme, causali, rinunce, tempi di pagamento", norma=[(CC, "2113", "validità in sede protetta")]),
               avvocato("sede", "Sede della conciliazione", "Commissione presso l’ispettorato, sede sindacale, commissione di certificazione, giudice o negoziazione assistita (art. 2-ter D.L. 132/2014)?",
                        norma=[(CPC, "411", "esecutività del verbale")])],
           [("Verbale", "parti, controversia, accordo e rinunce")], ["sede non protetta: le rinunce restano impugnabili per sei mesi"]),

    scheda("LAV_019", "Diffida e messa in mora del datore di lavoro", ["LAV_019", "LAV_020"],
           [(CC, "1219", "costituzione in mora"), (CC, "2943", "interruzione della prescrizione"), (CC, "2948", "prescrizione quinquennale")],
           _parti() + _rapporto() + [
               avvocato("crediti", "Crediti o inadempimenti", "Quali somme o obblighi si chiedono, con quali scadenze?"),
               avvocato("termine", "Termine assegnato", "Entro quanti giorni il datore deve adempiere?")],
           [("Diffida", "crediti, termine, effetto interruttivo")], ["crediti non indicati"]),
]
