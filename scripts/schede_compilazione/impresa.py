"""Schede di diritto societario, crisi d’impresa e bancario (SOC, CONC, BAN).

Base normativa: artt. 2247-2510 c.c. (società), artt. 2598-2601 c.c. (concorrenza sleale); codice della crisi
D.Lgs. 14/2019 (insinuazione, stato passivo, sovraindebitamento, esdebitazione); TUB D.Lgs. 385/1993 artt. 117-120
e L. 108/1996 sull’usura; art. 1283 e 1815 c.c. Sospensione feriale: esclusa per i procedimenti del codice della crisi
(art. 9 CCII); si applica alle cause societarie e bancarie ordinarie.
"""
from scripts.schede_compilazione.comuni import (CC, CPC, FERIALE, SENZA_FERIALE, T, IN_AVANTI, A_RITROSO, assistito, avvocato, calcolo,
                                                controparte, data_luogo, difensore, documento, fatti_documentati, letto, lex,
                                                procura, ufficio_da_adire)
from scripts.schede_compilazione.costruisci import scheda

CCII = "codice_crisi"
TUB = "385/1993"
CRISI_FERIALE = (CCII, "9", "sospensione feriale esclusa nei procedimenti del codice della crisi")
SEZ_IMPRESA = [(CPC, "50bis", "tribunale collegiale; sezione specializzata in materia di impresa (D.Lgs. 168/2003, da verificare)")]


def _parti(ric="Assistito", res="Controparte"):
    return [difensore(), procura(), data_luogo(), assistito(ric), controparte(res)]


def _lettera(ric="Assistito", res="Destinatario"):
    return [difensore(), data_luogo(), assistito(ric), controparte(res)]


def _visura():
    return documento("visura", "Visura camerale, statuto e atti sociali", "visura e statuto", ["visura", "statuto", "atto costitutivo"],
                     se_manca="chiedere visura e statuto")


def _procedura():
    return letto("procedura", "Tribunale, numero della procedura e curatore o liquidatore", "ufficio_e_rg", "sentenza e avviso del curatore",
                 [{"categoria": "ruolo"}], se_manca="chiedere i dati della procedura")


def _contratti_bancari():
    return documento("contratti", "Contratti ed estratti conto integrali", "contratti di conto, affidamento, mutuo ed estratti conto", ["contratto", "estratto", "conto"],
                     norma=[(TUB, "117", "forma scritta"), (TUB, "119", "estratti conto")],
                     se_manca="chiedere i documenti alla banca con l’art. 119 TUB prima di agire")


SCHEDE = [
    # ---------------- Società
    scheda("SOC_001", "Diffide, convocazioni e verbali societari", ["SOC_001", "SOC_002", "SOC_003", "SOC_004"],
           [(CC, "2366", "convocazione dell’assemblea di s.p.a."), (CC, "2479bis", "assemblea di s.r.l."), (CC, "2375", "verbale"), (CC, "2392", "doveri degli amministratori")],
           _lettera("Società, socio o amministratore", "Destinatario") + [_visura(),
               avvocato("atto", "Atto", "Diffida al socio o all’amministratore, convocazione o verbale? Ordine del giorno, data, maggioranze",
                        norma=[(CC, "2366", "termini di convocazione"), (CC, "2479bis", "otto giorni prima nelle s.r.l. salvo statuto")])],
           [("Atto", "contenuto secondo il tipo")], ["statuto non disponibile per i quorum"]),

    scheda("SOC_005", "Impugnazione di delibere assembleari e del bilancio", ["SOC_005", "SOC_006", "SOC_011"],
           [(CC, "2377", "annullabilità: novanta giorni"), (CC, "2379", "nullità: tre anni"), (CC, "2479ter", "delibere di s.r.l."), (CC, "2434bis", "impugnazione del bilancio"),
            (CC, "2378", "procedimento e sospensione"), *SEZ_IMPRESA, FERIALE],
           _parti("Socio o organo", "Società") + [_visura(),
               documento("delibera", "Verbale della delibera", "verbale assembleare", ["verbale", "delibera"], se_manca="astensione: serve la delibera"),
               letto("iscrizione", "Data della delibera o della sua iscrizione o deposito nel registro delle imprese", "evento", "verbale e visura",
                     [{"categoria": "data", "campo": "evento"}]),
               calcolo("termine", "Ultimo giorno per l’annullabilità", termine=T("evento", 90, feriale=False),
                       regola="calcolo prudenziale senza sospensione feriale (la Cassazione la applica alle azioni di impugnazione); 90 giorni dalla delibera o dall’iscrizione o deposito nel registro delle imprese (s.r.l.: dalla trascrizione nel libro); termine sostanziale di decadenza",
                       norma=[(CC, "2377", "novanta giorni"), (CC, "2479ter", "s.r.l.")]),
               avvocato("legittimazione", "Legittimazione e vizi", "Il socio era assente, dissenziente o astenuto? Possiede la quota minima? Quali vizi?",
                        norma=[(CC, "2377", "legittimazione e soglie")]),
               ufficio_da_adire(SEZ_IMPRESA)],
           [("Fatto", "delibera e vizi"), ("Conclusioni", "annullamento o nullità, sospensione")], ["delibera non presente", "termine di 90 giorni scaduto per vizi di annullabilità"]),

    scheda("SOC_007", "Azione di responsabilità contro gli amministratori", ["SOC_007"],
           [(CC, "2392", "responsabilità verso la società"), (CC, "2393", "azione sociale"), (CC, "2393bis", "azione dei soci di minoranza"), (CC, "2394", "creditori sociali"),
            (CC, "2476", "s.r.l."), (CC, "2949", "prescrizione quinquennale"), *SEZ_IMPRESA],
           _parti("Società, soci o creditori", "Amministratori") + [_visura(), fatti_documentati("Atti di mala gestio, danno e nesso"),
               avvocato("legittimazione", "Chi agisce", "Società con delibera, soci (quota), creditori o curatore?", norma=[(CC, "2393", "delibera"), (CC, "2476", "socio di s.r.l.")]),
               ufficio_da_adire(SEZ_IMPRESA)],
           [("Fatto", "condotte e danno"), ("Conclusioni", "condanna al risarcimento")], ["danno non quantificato né quantificabile"]),

    scheda("SOC_008", "Esibizione dei libri, esclusione e recesso del socio", ["SOC_008", "SOC_009", "SOC_010"],
           [(CC, "2476", "diritto di controllo del socio di s.r.l."), (CC, "2473", "recesso nella s.r.l."), (CC, "2437", "recesso nella s.p.a."),
            (CC, "2473bis", "esclusione nella s.r.l."), (CC, "2286", "esclusione nelle società di persone"), (CC, "2287", "opposizione entro trenta giorni")],
           _lettera("Socio o società", "Controparte") + [_visura(),
               avvocato("atto", "Atto e cause", "Esibizione dei libri, esclusione (giusta causa prevista) o recesso (causa legale o statutaria)? Termini statutari?",
                        norma=[(CC, "2437bis", "recesso entro quindici giorni dall’iscrizione della delibera")])],
           [("Atto", "presupposti e richiesta")], ["causa di recesso o esclusione non prevista dalla legge o dallo statuto"]),

    scheda("SOC_012", "Concorrenza sleale, patto di non concorrenza e segni distintivi", ["SOC_012", "SOC_013", "SOC_014"],
           [(CC, "2598", "atti di concorrenza sleale"), (CC, "2599", "inibitoria"), (CC, "2600", "risarcimento"), (CC, "2596", "patto di non concorrenza"),
            (CC, "2125", "non concorrenza del lavoratore"), (CC, "2564", "ditta"), ("30/2005", "20", "diritti del titolare del marchio")],
           _lettera("Impresa", "Concorrente") + [fatti_documentati("Condotte con prove (pagine, fatture, testimoni)"),
               avvocato("richiesta", "Richiesta", "Cessazione, ritiro dei prodotti, pubblicazione, risarcimento")],
           [("Diffida", "condotte, norme, richieste, termine")], ["nessun rapporto di concorrenza"]),

    scheda("SOC_015", "Ricorso cautelare societario e inibitoria commerciale urgente", ["SOC_015", "SOC_016"],
           [(CPC, "700", "provvedimenti d’urgenza"), (CPC, "669bis", "forma della domanda"), (CC, "2378", "sospensione della delibera"), (CC, "2599", "inibitoria"),
            *SENZA_FERIALE, *SEZ_IMPRESA],
           _parti("Ricorrente", "Resistente") + [_visura(), fatti_documentati("Fatti e prove"),
               avvocato("periculum", "Pregiudizio imminente e irreparabile", "Perché non si può attendere il giudizio ordinario?", norma=[(CPC, "700", "pregiudizio")]),
               ufficio_da_adire(SEZ_IMPRESA)],
           [("Ricorso", "fumus, periculum, misure")], ["urgenza non dimostrata"]),

    # ---------------- Crisi d’impresa
    scheda("CONC_001", "Domanda di ammissione al passivo, privilegio, rivendica e restituzione",
           ["CONC_001", "CONC_004", "CONC_005", "CONC_006"],
           [(CCII, "201", "domanda almeno trenta giorni prima dell’udienza, via PEC al curatore"), (CCII, "210", "rivendica e restituzione"), CRISI_FERIALE,
            (CC, "2745", "privilegi: indicare la norma specifica")],
           [difensore(), data_luogo(), assistito("Creditore o titolare del bene"), _procedura(),
            letto("udienza", "Udienza di verifica dello stato passivo", "udienza", "avviso del curatore", [{"categoria": "data", "campo": "udienza"}],
                  se_manca="chiedere la data dell’udienza dall’avviso del curatore"),
            calcolo("termine", "Ultimo giorno per trasmettere la domanda", termine=T("udienza", 30, ritroso=True, feriale=False),
                    regola="almeno 30 giorni prima dell’udienza di verifica, senza sospensione feriale" + A_RITROSO, norma=[(CCII, "201", "trenta giorni")]),
            documento("titolo", "Documenti del credito o del diritto sul bene", "fatture, contratti, titoli", ["fattura", "contratto", "decreto", "sentenza"]),
            avvocato("credito", "Credito, privilegio e PEC", "Importo, causa, privilegio o prelazione con la norma, PEC per le comunicazioni",
                     norma=[(CCII, "201", "contenuto a pena di inammissibilità")])],
           [("Domanda", "creditore, credito, prelazione, documenti, PEC")], ["udienza di verifica non nota"]),

    scheda("CONC_002", "Domanda tardiva di ammissione al passivo", ["CONC_002"],
           [(CCII, "208", "domande tardive entro sei mesi dall’esecutività dello stato passivo"), CRISI_FERIALE],
           [difensore(), data_luogo(), assistito("Creditore"), _procedura(),
            letto("esecutivita", "Deposito del decreto di esecutività dello stato passivo", "provvedimento", "comunicazione del curatore",
                  [{"categoria": "data", "campo": "provvedimento"}]),
            calcolo("termine", "Ultimo giorno per la tardiva", termine=T("provvedimento", mesi=6, feriale=False),
                    regola="6 mesi dal deposito del decreto di esecutività; se la sentenza di apertura lo ha prorogato fino a 12 mesi la data calcolata non vale; oltre, solo se il ritardo non è imputabile" + IN_AVANTI,
                    norma=[(CCII, "208", "sei mesi")]),
            avvocato("ritardo", "Ragioni del ritardo", "Se oltre il termine: perché il ritardo non è imputabile?", obbligatorio=False, norma=[(CCII, "208", "ultratardive")])],
           [("Domanda", "credito, documenti, ragioni del ritardo")], ["termine scaduto senza causa non imputabile"]),

    scheda("CONC_003", "Opposizione allo stato passivo", ["CONC_003"],
           [(CCII, "206", "impugnazioni"), (CCII, "207", "procedimento: trenta giorni dalla comunicazione"), CRISI_FERIALE],
           [difensore(), procura(), data_luogo(), assistito("Creditore"), _procedura(),
            letto("comunicazione", "Comunicazione dell’esito della domanda", "comunicazione", "PEC del curatore", [{"categoria": "data", "campo": "comunicazione"}]),
            calcolo("termine", "Ultimo giorno per l’opposizione", termine=T("comunicazione", 30, feriale=False),
                    regola="30 giorni dalla comunicazione del curatore, senza sospensione feriale" + IN_AVANTI, norma=[(CCII, "207", "trenta giorni")]),
            avvocato("motivi", "Motivi e prove", "Perché la domanda va accolta; documenti nuovi solo se indicati a pena di decadenza", norma=[(CCII, "207", "contenuto")])],
           [("Ricorso", "motivi, prove, conclusioni")], ["comunicazione non presente"]),

    scheda("CONC_007", "Sovraindebitamento: liquidazione controllata, concordato minore, ristrutturazione del consumatore",
           ["CONC_007", "CONC_011", "CONC_012"],
           [(CCII, "268", "liquidazione controllata"), (CCII, "74", "concordato minore"), (CCII, "67", "ristrutturazione dei debiti del consumatore"),
            (CCII, "2", "definizioni di sovraindebitamento e consumatore"), CRISI_FERIALE],
           [difensore(), procura(), data_luogo(), assistito("Debitore"),
            documento("relazione", "Relazione dell’OCC", "relazione dell’organismo di composizione della crisi", ["occ", "relazione"],
                      se_manca="chiedere la relazione dell’OCC: senza la domanda non si deposita"),
            documento("elenco", "Elenco creditori, beni, redditi, dichiarazioni dei redditi", "elenco creditori e documenti", ["creditori", "redditi"]),
            avvocato("procedura", "Procedura scelta", "Debitore consumatore o impresa minore? Proposta ai creditori o liquidazione?", norma=[(CCII, "2", "definizioni")]),
            avvocato("meritevolezza", "Meritevolezza", "Cause dell’indebitamento e diligenza", norma=[(CCII, "69", "ostative per il consumatore"), (CCII, "77", "inammissibilità del concordato minore"), (CCII, "283", "incapiente")])],
           [("Domanda", "situazione, piano o proposta, documenti")], ["relazione OCC mancante"]),

    scheda("CONC_008", "Istanze, osservazioni e memorie dei creditori e del liquidatore",
           ["CONC_008", "CONC_013", "CONC_014", "CONC_015"],
           [(CCII, "70", "osservazioni nella ristrutturazione del consumatore: venti giorni"), (CCII, "78", "osservazioni nel concordato minore"), (CCII, "275", "attività del liquidatore"), (CCII, "128", "funzioni del curatore"), CRISI_FERIALE],
           [difensore(), data_luogo(), assistito("Creditore, curatore o liquidatore"), _procedura(),
            avvocato("atto", "Atto", "Istanza al curatore, osservazioni al piano (termine assegnato), memoria o autorizzazione ad atti del liquidatore?")],
           [("Atto", "richiesta motivata")], ["procedura non individuata"]),

    scheda("CONC_009", "Reclamo contro i provvedimenti del giudice delegato", ["CONC_009"],
           [(CCII, "124", "reclamo entro dieci giorni"), CRISI_FERIALE],
           [difensore(), procura(), data_luogo(), assistito("Reclamante"), _procedura(),
            letto("comunicazione", "Comunicazione del provvedimento", "comunicazione", "PEC", [{"categoria": "data", "campo": "comunicazione"}]),
            calcolo("termine", "Ultimo giorno per il reclamo", termine=T("comunicazione", 10, feriale=False),
                    regola="10 giorni dalla comunicazione o notificazione, senza sospensione feriale" + IN_AVANTI, norma=[(CCII, "124", "dieci giorni")]),
            avvocato("motivi", "Motivi", "Perché il provvedimento è illegittimo o inopportuno?")],
           [("Reclamo", "motivi e conclusioni")], ["provvedimento non presente"]),

    scheda("CONC_010", "Domanda di esdebitazione", ["CONC_010"],
           [(CCII, "278", "esdebitazione"), (CCII, "280", "condizioni"), (CCII, "282", "esdebitazione di diritto nel sovraindebitamento"),
            (CCII, "283", "debitore incapiente"), CRISI_FERIALE],
           [difensore(), procura(), data_luogo(), assistito("Debitore"), _procedura(),
            avvocato("condizioni", "Condizioni", "Condanne ostative, collaborazione, assenza di esdebitazione nei cinque anni precedenti", norma=[(CCII, "280", "condizioni")])],
           [("Domanda", "condizioni e richiesta")], ["cause ostative"]),

    # ---------------- Bancario
    scheda("BAN_001", "Richiesta di documentazione e diffide all’intermediario", ["BAN_001", "BAN_002", "BAN_011", "BAN_012"],
           [(TUB, "119", "copia della documentazione degli ultimi dieci anni entro novanta giorni"), (TUB, "128bis", "Arbitro Bancario Finanziario"),
            ("58/1998", "32ter", "Arbitro per le Controversie Finanziarie")],
           _lettera("Cliente", "Banca o intermediario") + [
               avvocato("rapporti", "Rapporti", "Conti, mutui, affidamenti, investimenti: numeri e periodi"),
               calcolo("termine", "Termine per la consegna", "entro 90 giorni dalla richiesta, per i documenti degli ultimi dieci anni", norma=[(TUB, "119", "novanta giorni")]),
               lex("abf", "ABF", "ricordare che il ricorso all’ABF richiede il reclamo preventivo all’intermediario")],
           [("Lettera", "rapporti, documenti richiesti, termine")], ["rapporti non indicati"]),

    scheda("BAN_003", "Azioni su anatocismo, usura, indebito, fideiussioni omnibus", ["BAN_003", "BAN_004", "BAN_005", "BAN_006", "BAN_008", "BAN_009"],
           [(TUB, "120", "capitalizzazione degli interessi"), (TUB, "117", "forma e tassi"), (CC, "1283", "anatocismo"), (CC, "1815", "interessi usurari"),
            ("108/1996", "2", "tassi soglia"), (CC, "2033", "indebito"), (CC, "2946", "prescrizione decennale"), (CC, "1418", "nullità"),
            ("legge_287_1990", "2", "intese restrittive (schema ABI sulle fideiussioni)"), ("28/2010", "5", "mediazione obbligatoria nei contratti bancari"), FERIALE],
           _parti("Cliente o garante", "Banca") + [_contratti_bancari(),
               documento("perizia", "Perizia econometrica", "perizia di parte", ["perizia", "consulenza"], obbligatorio=False,
                         se_manca="segnalare che senza ricalcolo la domanda resta generica"),
               avvocato("rimesse", "Conto aperto o chiuso, rimesse", "Il conto è chiuso? Le rimesse sono solutorie o ripristinatorie (incide sulla prescrizione)?",
                        norma=[(CC, "2946", "decorrenza dalla chiusura per le rimesse ripristinatorie")]),
               avvocato("mediazione", "Mediazione", "È stata esperita la mediazione?", norma=[("28/2010", "5", "condizione di procedibilità")])],
           [("Fatto", "rapporti e addebiti"), ("Diritto", "nullità e ricalcolo"), ("Conclusioni", "ripetizione o rideterminazione del saldo")],
           ["estratti conto incompleti", "mediazione non esperita"]),

    scheda("BAN_007", "Opposizione a decreto ingiuntivo su saldo di conto", ["BAN_007"],
           [(CPC, "645", "opposizione"), (CPC, "641", "quaranta giorni"), (TUB, "50", "estratto certificato"), FERIALE],
           _parti("Correntista o garante", "Banca") + [
               documento("decreto", "Decreto ingiuntivo notificato", "decreto ingiuntivo", ["decreto"], se_manca="astensione: serve il decreto"),
               letto("notifica", "Notifica del decreto", "notifica", "relata", [{"categoria": "data", "campo": "notifica"}]),
               calcolo("termine", "Ultimo giorno per l’opposizione", termine=T("notifica", 40), regola="40 giorni dalla notifica, con sospensione feriale" + IN_AVANTI,
                       norma=[(CPC, "641", "quaranta giorni")]),
               _contratti_bancari()],
           [("Opposizione", "contestazione del saldo, nullità, ricalcolo")], ["decreto non presente"]),

    scheda("BAN_010", "Contestazione dell’iscrizione in centrale rischi", ["BAN_010"],
           [(TUB, "125", "preavviso di segnalazione"), (CPC, "700", "tutela d’urgenza")],
           _lettera("Cliente", "Intermediario") + [
               avvocato("segnalazione", "Segnalazione", "Quale centrale, quando, se c’è stato preavviso e perché è illegittima")],
           [("Atto", "contestazione e richiesta di cancellazione")], ["segnalazione non documentata"]),
]
