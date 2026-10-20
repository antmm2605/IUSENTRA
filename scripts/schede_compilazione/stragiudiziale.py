"""Schede stragiudiziali, di studio, ADR e consumo (STR, STD, ADR, CON).

Base normativa: artt. 1219, 1454, 1957, 1965, 1988, 2943 c.c. (mora, diffida, fideiussione, transazione, ricognizione,
interruzione della prescrizione); D.Lgs. 28/2010 e D.L. 132/2014 (mediazione e negoziazione assistita); artt. 806-840
c.p.c. (arbitrato); L. 247/2012 e codice deontologico forense (incarico, preventivo, compensi, rinuncia);
D.M. 55/2014 (parametri); codice del consumo D.Lgs. 206/2005; Reg. UE 261/2004 (trasporto aereo).
I termini stragiudiziali sono sostanziali: nessuna sospensione feriale.
"""
from scripts.schede_compilazione.comuni import (CC, CPC, assistito, avvocato, calcolo, controparte, data_luogo, difensore, documento,
                                                fatti_documentati, lex, procura)
from scripts.schede_compilazione.costruisci import scheda

CONS = "codice_consumo"
CDF = "codice_deontologico_forense_2026"
LF = "legge_247_2012"
MED = "28/2010"
NEG = "dl_132_2014"


def _lettera(mitt="Mittente (assistito)", dest="Destinatario"):
    return [difensore(), data_luogo(), assistito(mitt), controparte(dest)]


def _credito():
    return [documento("titolo", "Documento del credito", "fattura, contratto, ordine o riconoscimento", ["fattura", "contratto", "ordine"],
                      se_manca="chiedere il documento da cui nasce il credito"),
            avvocato("importo", "Importo, scadenza e interessi", "Capitale, data di scadenza, interessi (legali o di mora commerciali) e spese",
                     norma=[(CC, "1224", "interessi moratori"), ("231/2002", "5", "interessi nelle transazioni commerciali")])]


def _studio(dest="Cliente"):
    return [difensore(), data_luogo(), assistito(dest)]


SCHEDE = [
    # ---------------- Recupero crediti e lettere stragiudiziali
    scheda("STR_001", "Solleciti, messa in mora e costituzione in mora", ["STR_001", "STR_002", "STR_003", "STR_004", "STR_012", "STR_020"],
           [(CC, "1219", "costituzione in mora con intimazione scritta"), (CC, "1224", "interessi moratori"), (CC, "2943", "interruzione della prescrizione"),
            ("231/2002", "4", "decorrenza automatica degli interessi commerciali")],
           _lettera("Creditore", "Debitore") + _credito() + [
               avvocato("termine", "Termine assegnato", "Entro quanti giorni pagare e con quali conseguenze (azione giudiziale, precetto)?")],
           [("Lettera", "credito, intimazione, termine, effetti di mora e interruttivi")], ["credito non documentato"]),

    scheda("STR_005", "Diffida ad adempiere e intimazione finale", ["STR_005", "STR_006"],
           [(CC, "1454", "diffida: termine non inferiore a quindici giorni, risoluzione di diritto"), (CC, "1219", "mora")],
           _lettera("Parte adempiente", "Parte inadempiente") + [
               documento("contratto", "Contratto", "contratto", ["contratto"], se_manca="astensione per la diffida ex art. 1454: serve un contratto a prestazioni corrispettive"),
               avvocato("inadempimento", "Inadempimento", "Quale obbligazione non è stata eseguita e da quando?"),
               avvocato("termine", "Termine", "Termine di adempimento (almeno 15 giorni salvo diversa pattuizione o natura del contratto)", norma=[(CC, "1454", "quindici giorni")])],
           [("Diffida", "obbligazione, termine, avvertimento della risoluzione")], ["inadempimento di scarsa importanza: valutare"]),

    scheda("STR_007", "Piano di rientro, ricognizione di debito, saldo e stralcio", ["STR_007", "STR_008", "STR_009"],
           [(CC, "1988", "promessa di pagamento e ricognizione"), (CC, "2944", "interruzione per riconoscimento"), (CC, "1236", "remissione del debito"),
            (CC, "1184", "termine di adempimento")],
           _lettera("Creditore o debitore", "Altra parte") + _credito() + [
               avvocato("accordo", "Condizioni", "Rate e scadenze, importo a saldo e stralcio, decadenza dal beneficio del termine, effetti sul residuo"),
               avvocato("decadenza", "Clausola di decadenza", "Cosa accade se una rata non è pagata?", obbligatorio=False, norma=[(CC, "1186", "decadenza dal termine")])],
           [("Accordo", "riconoscimento, piano, decadenza, quietanza")], ["importo non concordato"]),

    scheda("STR_010", "Transazione semplice o novativa", ["STR_010", "STR_011"],
           [(CC, "1965", "transazione"), (CC, "1966", "capacità e diritti disponibili"), (CC, "1967", "forma scritta ad probationem"), (CC, "1976", "risoluzione della transazione novativa")],
           _lettera("Parte", "Altra parte") + [fatti_documentati("Lite insorta o che può insorgere"),
               avvocato("concessioni", "Reciproche concessioni", "Cosa concede ciascuna parte?", norma=[(CC, "1965", "reciproche concessioni")]),
               avvocato("novativa", "Natura novativa", "Il rapporto originario si estingue ed è sostituito?", norma=[(CC, "1976", "effetti")])],
           [("Transazione", "premesse, concessioni, rinunce, spese")], ["diritti indisponibili"]),

    scheda("STR_013", "Costituzione in mora del fideiussore", ["STR_013"],
           [(CC, "1944", "obbligazione del fideiussore"), (CC, "1957", "decadenza se il creditore non agisce entro sei mesi dalla scadenza"), (CC, "1219", "mora")],
           _lettera("Creditore", "Fideiussore") + _credito() + [
               documento("fideiussione", "Fideiussione", "atto di fideiussione", ["fideiussione"], se_manca="astensione: serve la fideiussione"),
               calcolo("termine_1957", "Termine dell’art. 1957", "istanza giudiziale contro il debitore entro sei mesi dalla scadenza dell’obbligazione principale, salvo deroga pattizia; la lettera non basta",
                       norma=[(CC, "1957", "sei mesi")])],
           [("Lettera", "credito garantito, richiesta di pagamento")], ["fideiussione non presente"]),

    scheda("STR_014", "Diffida per restituzione di beni o cessazione di condotta lesiva", ["STR_014", "STR_015"],
           [(CC, "1219", "mora"), (CC, "948", "rivendicazione"), (CC, "2043", "fatto illecito"), (CC, "949", "azione negatoria")],
           _lettera("Assistito", "Destinatario") + [fatti_documentati("Bene da restituire o condotta lesiva, con date e prove"),
               avvocato("richiesta", "Richiesta e termine", "Cosa deve fare il destinatario ed entro quando?")],
           [("Diffida", "fatti, diritto leso, richiesta, termine")], ["nessun fatto documentato"]),

    scheda("STR_016", "Lettera interruttiva della prescrizione", ["STR_016"],
           [(CC, "2943", "interruzione con atto di costituzione in mora"), (CC, "2945", "nuovo periodo di prescrizione"), (CC, "1219", "mora")],
           _lettera("Creditore", "Debitore") + _credito() + [
               avvocato("prescrizione", "Prescrizione applicabile", "Termine di prescrizione del diritto (10, 5, 2 anni) e data di decorrenza", norma=[(CC, "2946", "ordinaria"), (CC, "2948", "quinquennale")]),
               lex("ricezione", "Ricezione", "ricordare che l’interruzione opera dalla ricezione: usare PEC o raccomandata con avviso")],
           [("Lettera", "diritto, richiesta, effetto interruttivo")], ["prescrizione già maturata"]),

    scheda("STR_017", "Invito a negoziazione assistita o a mediazione", ["STR_017", "STR_018", "ADR_001", "ADR_006"],
           [(NEG, "2", "convenzione di negoziazione"), (NEG, "3", "negoziazione obbligatoria"), (NEG, "4", "invito e risposta entro trenta giorni"),
            (MED, "5", "mediazione obbligatoria"), (MED, "8", "procedimento")],
           _lettera("Assistito", "Controparte") + [
               avvocato("oggetto", "Oggetto della lite e valore", "Materia e valore: rientra nella negoziazione obbligatoria (veicoli, pagamenti fino a 50.000 euro) o nella mediazione obbligatoria?",
                        norma=[(NEG, "3", "casi"), (MED, "5", "materie")]),
               lex("avvertimento", "Avvertimento", "inserire l’avvertimento che la mancata risposta entro 30 giorni o il rifiuto può essere valutato dal giudice ai fini delle spese",
                   norma=[(NEG, "4", "effetti della mancata risposta")])],
           [("Invito", "oggetto, domanda, avvertimenti")], ["materia esclusa dalla procedura"]),

    scheda("STR_019", "Riscontro a diffida ricevuta", ["STR_019"],
           [(CC, "1460", "eccezione di inadempimento"), (CC, "2697", "onere della prova")],
           _lettera("Assistito", "Mittente della diffida") + [
               documento("diffida", "Diffida ricevuta", "diffida", ["diffida"], se_manca="astensione: serve la diffida"),
               avvocato("posizione", "Posizione dell’assistito", "Cosa si contesta, cosa si riconosce, quali documenti?")],
           [("Riscontro", "contestazioni puntuali e riserve")], ["diffida non presente"]),

    # ---------------- ADR
    scheda("ADR_002", "Istanza, adesione e verbali di mediazione", ["ADR_002", "ADR_003", "ADR_004", "ADR_005"],
           [(MED, "4", "domanda di mediazione"), (MED, "8", "procedimento e presenza personale"), (MED, "11", "conclusione"), (MED, "12", "efficacia esecutiva"),
            (MED, "5", "condizione di procedibilità")],
           _lettera("Parte", "Altra parte") + [procura("serve la procura sostanziale se la parte delega l’avvocato in mediazione"),
               avvocato("organismo", "Organismo", "Organismo del luogo del giudice competente", norma=[(MED, "4", "competenza territoriale dell’organismo")]),
               avvocato("esito", "Esito o contenuto", "Domanda, adesione, accordo raggiunto (contenuto) o mancato accordo?", norma=[(MED, "11", "verbale")])],
           [("Atto", "parti, oggetto, ragioni o accordo")], ["organismo fuori dal territorio del giudice competente"]),

    scheda("ADR_007", "Accordo di negoziazione assistita o diniego", ["ADR_007", "ADR_008"],
           [(NEG, "2", "convenzione"), (NEG, "4", "rifiuto"), (NEG, "5", "esecutività dell’accordo e certificazione delle firme")],
           _lettera("Parte", "Altra parte") + [avvocato("contenuto", "Contenuto", "Accordo raggiunto o ragioni del rifiuto?")],
           [("Atto", "accordo con certificazione degli avvocati o diniego")], ["diritti indisponibili"]),

    scheda("ADR_009", "Arbitrato: clausola, domanda, nomina, difese", ["ADR_009", "ADR_010", "ADR_011", "ADR_012", "ADR_013"],
           [(CPC, "806", "controversie arbitrabili"), (CPC, "807", "compromesso"), (CPC, "808", "clausola compromissoria"), (CPC, "810", "nomina degli arbitri"),
            (CPC, "816bis", "svolgimento del procedimento"), (CPC, "820", "termine per il lodo")],
           _lettera("Parte", "Altra parte") + [procura(),
               documento("clausola", "Clausola o compromesso", "contratto con clausola arbitrale", ["arbitr", "clausola"], obbligatorio=False),
               avvocato("atto", "Atto", "Clausola, domanda di arbitrato con nomina dell’arbitro, nomina, comparsa o memoria?", norma=[(CPC, "810", "invito a nominare entro venti giorni")])],
           [("Atto", "contenuto secondo l’atto")], ["diritti non disponibili", "clausola non scritta"]),

    scheda("ADR_014", "Accordo transattivo finale", ["ADR_014"],
           [(CC, "1965", "transazione"), (CC, "1967", "forma scritta")],
           _lettera("Parte", "Altra parte") + [avvocato("contenuto", "Contenuto", "Concessioni, pagamenti, rinunce, spese e abbandono dei giudizi")],
           [("Accordo", "premesse, concessioni, rinunce")], ["diritti indisponibili"]),

    # ---------------- Studio
    scheda("STD_001", "Incarico, preventivo, procura e informative al cliente",
           ["STD_001", "STD_002", "STD_003", "STD_004", "STD_011", "STD_012"],
           [(LF, "13", "compenso pattuito di regola per iscritto; comunicazione scritta della prevedibile misura del costo (c. 5)"), ("55/2014", "4", "parametri"), (CDF, "27", "doveri di informazione"),
            (CPC, "83", "procura alle liti"), ("reg_ue_2016_679", "13", "informativa privacy")],
           _studio() + [
               avvocato("oggetto", "Oggetto dell’incarico", "Prestazione, fasi, complessità e valore"),
               avvocato("compenso", "Compenso e spese", "Forfait, a tempo o a parametri; fondo spese; rischi e durata prevedibile",
                        norma=[(LF, "13", "preventivo scritto obbligatorio"), ("55/2014", "4", "parametri")]),
               lex("mediazione", "Informativa ADR", "inserire l’informativa scritta sulla mediazione sottoscritta dall’assistito: senza, il contratto con l’avvocato è annullabile", norma=[(MED, "4", "obbligo di informazione dell’avvocato")])],
           [("Atto", "incarico, compenso, informative, firma")], ["oggetto dell’incarico non definito"]),

    scheda("STD_005", "Documenti interni di pratica e comunicazioni al cliente",
           ["STD_005", "STD_006", "STD_007", "STD_008", "STD_013", "STD_014", "STD_015"],
           [(CDF, "27", "dovere di informazione"), (CDF, "26", "adempimento del mandato")],
           _studio() + [fatti_documentati("Stato della pratica, documenti ricevuti e mancanti, scadenze"),
               avvocato("comunicazione", "Contenuto", "Che documento serve: scheda documenti, checklist, aggiornamento, sollecito, piano, verbale, chiusura?")],
           [("Documento", "contenuto secondo il tipo")], ["tipo di documento non indicato"]),

    scheda("STD_009", "Rinuncia all’incarico o revoca del mandato", ["STD_009", "STD_010"],
           [(CDF, "32", "rinuncia al mandato con congruo preavviso"), (CPC, "85", "revoca e rinuncia alla procura")],
           _studio() + [avvocato("motivo", "Atto e preavviso", "Rinuncia o revoca? Termini in corso da segnalare al cliente?", norma=[(CDF, "32", "informazione su termini")])],
           [("Lettera", "dichiarazione, termini pendenti, restituzione dei documenti")], ["termine processuale imminente senza preavviso congruo: segnalare"]),

    scheda("STD_016", "Compensi: sollecito, mora, accordo, proforma, fondo spese",
           ["STD_016", "STD_017", "STD_018", "STD_019", "STD_020"],
           [(LF, "13", "compensi"), ("55/2014", "2", "compensi e spese"), (CDF, "29", "richiesta di pagamento"), (CC, "2956", "prescrizione presuntiva triennale"), (CC, "2946", "prescrizione estintiva decennale")],
           _studio() + [
               documento("incarico", "Incarico o preventivo", "incarico firmato", ["incarico", "preventivo"], obbligatorio=False),
               avvocato("importi", "Importi", "Compenso, spese generali 15%, CPA, IVA, acconti ricevuti", norma=[("55/2014", "2", "spese forfettarie")])],
           [("Documento", "importi, termini, conseguenze")], ["compenso non concordato né determinabile"]),

    # ---------------- Consumo
    scheda("CON_001", "Diffide e reclami del consumatore (utenze, e-commerce, garanzia)",
           ["CON_001", "CON_002", "CON_003", "CON_007", "CON_008", "CON_009", "CON_010"],
           [(CONS, "61", "consegna entro trenta giorni"), (CONS, "52", "recesso"), (CONS, "128", "garanzia legale"), (CONS, "135bis", "rimedi del consumatore"),
            (CONS, "133", "difetti manifestati entro due anni dalla consegna"), (CONS, "141", "definizioni ADR"), (CC, "1219", "mora")],
           _lettera("Consumatore", "Professionista") + [
               documento("contratto", "Contratto, ordine, fatture, reclami", "contratto e corrispondenza", ["contratto", "ordine", "fattura", "reclamo"]),
               avvocato("problema", "Problema e richiesta", "Mancata consegna, difetto, fatturazione errata, interruzione del servizio? Cosa si chiede?"),
               lex("conciliazione", "Conciliazione", "segnalare il tentativo obbligatorio presso il Corecom o le procedure ARERA per telefonia ed energia, da verificare")],
           [("Diffida", "fatti, diritti del consumatore, richiesta, termine")], ["acquirente non consumatore"]),

    scheda("CON_004", "Reclamo per trasporto aereo, ferroviario o pacchetto turistico", ["CON_004", "CON_005", "CON_006"],
           [("reg_ue_2004_261", "7", "compensazione pecuniaria"), ("reg_ue_2004_261", "5", "cancellazione"), ("reg_ue_2004_261", "8", "rimborso")],
           _lettera("Passeggero o viaggiatore", "Vettore o organizzatore") + [
               documento("biglietto", "Biglietto o contratto di viaggio", "prenotazione", ["biglietto", "prenotazione", "pacchetto"]),
               avvocato("disservizio", "Disservizio", "Ritardo all’arrivo, cancellazione, negato imbarco, bagaglio o inadempimento del pacchetto"),
               lex("altre", "Fonti non in archivio", "segnalare che il regolamento sui diritti dei passeggeri ferroviari e il codice del turismo vanno verificati")],
           [("Reclamo", "volo o viaggio, disservizio, compensazione o rimborso")], ["circostanze eccezionali documentate dal vettore"]),

    scheda("CON_011", "Ricorso al giudice di pace del consumatore e azione su clausole vessatorie", ["CON_011", "CON_012"],
           [(CONS, "33", "clausole vessatorie"), (CONS, "36", "nullità di protezione"), (CONS, "66bis", "foro del consumatore"), (CPC, "316", "domanda davanti al giudice di pace")],
           _lettera("Consumatore", "Professionista") + [procura(),
               documento("contratto", "Contratto", "contratto", ["contratto"], se_manca="astensione: serve il contratto"),
               avvocato("clausole", "Clausole e domanda", "Quali clausole sono vessatorie e quale domanda si propone?")],
           [("Atto", "fatti, clausole, nullità, conclusioni")], ["contratto non presente"]),
]
