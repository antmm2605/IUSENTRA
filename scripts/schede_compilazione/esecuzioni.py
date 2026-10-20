"""Schede dell'esecuzione forzata (ESE), oltre al precetto (ESE_001).

Base normativa: artt. 474-632 c.p.c. nel testo vigente al 19/10/2026; art. 92 R.D. 12/1941 e art. 3 L. 742/1969
per l'esclusione dei procedimenti di opposizione all'esecuzione dalla sospensione feriale; per l'art. 617 e l'art. 619
il termine si calcola per prudenza senza sospensione (la scadenza più vicina). I termini interni al processo
esecutivo (artt. 481, 482, 497, 543, 557) seguono la sospensione feriale ordinaria.
"""
from scripts.schede_compilazione.comuni import (CPC, FERIALE, IN_AVANTI, SENZA_FERIALE, T, assistito, avvocato, calcolo,
                                                causa_pendente, controparte, data_luogo, difensore, documento, lex, letto,
                                                procura)
from scripts.schede_compilazione.costruisci import scheda

ESTENSIONI = {"ESE_001": ["ESE_002"]}


def _base(cliente="Creditore procedente", altra="Debitore esecutato"):
    return [difensore(), data_luogo(), assistito(cliente), controparte(altra)]


def _titolo_e_precetto():
    return [documento("titolo", "Titolo esecutivo in copia conforme", "titolo esecutivo", ["sentenza", "decreto", "titolo", "cambiale", "assegno"],
                      norma=[(CPC, "474", "titolo esecutivo")], se_manca="astensione: senza titolo esecutivo non si procede"),
            letto("notifica_precetto", "Data di notifica del precetto", "notifica", "relata del precetto",
                  [{"categoria": "data", "campo": "notifica"}, {"categoria": "prova_notifica"}], norma=[(CPC, "480", "precetto")],
                  se_manca="astensione: l’esecuzione va preceduta dalla notifica del precetto"),
            calcolo("termine_dilatorio", "Primo giorno utile per l’esecuzione", termine=T("notifica", 10),
                    regola="decorsi 10 giorni dalla notifica del precetto, salvo autorizzazione per pericolo nel ritardo", norma=[(CPC, "482", "termine dilatorio")]),
            calcolo("termine_precetto", "Finestra per iniziare l’esecuzione", termine=T("notifica", 90),
                    regola="non prima di 10 giorni dalla notifica del precetto (salvo autorizzazione) ed entro 90 giorni, con sospensione feriale" + IN_AVANTI,
                    norma=[(CPC, "482", "termine dilatorio di dieci giorni"), (CPC, "481", "inefficacia dopo novanta giorni"), FERIALE])]


SCHEDE = [
    scheda("ESE_006", "Richiesta di pignoramento mobiliare", ["ESE_006"],
           [(CPC, "513", "ricerca delle cose da pignorare"), (CPC, "518", "forma del pignoramento e iscrizione a ruolo"),
            (CPC, "492", "ingiunzione al debitore"), (CPC, "497", "efficacia di quarantacinque giorni")],
           _base() + _titolo_e_precetto() + [
            avvocato("luogo", "Luogo dove cercare i beni", "Dove si trovano i beni mobili del debitore (abitazione, sede, altri luoghi)?",
                     norma=[(CPC, "513", "luoghi della ricerca")]),
            calcolo("iscrizione", "Iscrizione a ruolo e istanza di vendita", "deposito della nota di iscrizione entro 15 giorni dalla consegna del verbale; istanza di vendita entro 45 giorni dal pignoramento",
                    norma=[(CPC, "518", "quindici giorni"), (CPC, "497", "quarantacinque giorni")])],
           [("Istanza", "richiesta all’ufficiale giudiziario con titolo, precetto e luoghi")],
           ["titolo o notifica del precetto mancanti", "novanta giorni dal precetto già trascorsi: serve un nuovo precetto"]),

    scheda("ESE_007", "Atto di pignoramento presso terzi", ["ESE_007", "ESE_008", "ESE_009", "ESE_010", "ESE_011"],
           [(CPC, "543", "forma del pignoramento presso terzi"), (CPC, "545", "limiti di pignorabilità di stipendi, pensioni e conti"),
            (CPC, "547", "dichiarazione del terzo"), (CPC, "548", "mancata dichiarazione")],
           _base() + _titolo_e_precetto() + [
            avvocato("terzo", "Terzo debitore e credito da pignorare", "Chi è il terzo (banca, datore di lavoro, ente pensionistico, cliente) e quale credito vanta il debitore verso di lui?",
                     norma=[(CPC, "543", "indicazione del terzo e delle somme")]),
            avvocato("natura", "Natura del credito pignorato", "Si pignora uno stipendio, una pensione, un conto corrente o un credito commerciale?",
                     norma=[(CPC, "545", "stipendi: un quinto (metà con più crediti concorrenti); pensioni: impignorabile il doppio dell’assegno sociale con minimo di 1.000 euro; somme già accreditate su conto: pignorabili oltre il triplo dell’assegno sociale")]),
            avvocato("altri_vincoli", "Natura del credito e vincoli", "Il credito per cui si procede è alimentare o tributario? Ci sono cessioni del quinto o pignoramenti precedenti?",
                     obbligatorio=False, norma=[(CPC, "545", "crediti alimentari e concorso")]),
            calcolo("ufficio", "Giudice competente", "tribunale del luogo di residenza, domicilio, dimora o sede del debitore", norma=[(CPC, "26bis", "foro dell’esecuzione presso terzi")]),
            calcolo("iscrizione", "Iscrizione a ruolo e avviso al terzo", "nota di iscrizione entro 30 giorni dalla consegna dell’atto notificato, con sospensione feriale; avviso dell’iscrizione notificato al debitore e al terzo prima dell’udienza, a pena di inefficacia",
                    norma=[(CPC, "543", "trenta giorni e avviso di iscrizione")]),
            lex("importo", "Importo per cui si procede", "calcolare capitale, interessi e spese aumentati della metà come prevede l’art. 546",
                norma=[(CPC, "546", "obblighi del terzo nei limiti dell’importo aumentato della metà")])],
           [("Atto", "indicazione del credito, del titolo e del precetto, ingiunzione e citazione del debitore secondo l’art. 543")],
           ["titolo o notifica del precetto mancanti", "terzo o credito non indicati", "credito impignorabile secondo l’art. 545"]),

    scheda("ESE_012", "Atto di pignoramento immobiliare", ["ESE_012"],
           [(CPC, "555", "forma del pignoramento immobiliare e trascrizione"), (CPC, "557", "iscrizione a ruolo"),
            (CPC, "567", "istanza di vendita e documentazione ipocatastale"), (CPC, "497", "quarantacinque giorni")],
           _base() + _titolo_e_precetto() + [
            avvocato("immobili", "Immobili e dati catastali", "Quali immobili pignori? Indica comune, foglio, particella, subalterno e titolarità",
                     norma=[(CPC, "555", "esatta indicazione dei beni")]),
            calcolo("termini", "Termini successivi", "iscrizione a ruolo entro 15 giorni dalla consegna dell’atto e della nota di trascrizione; istanza di vendita e documentazione entro i termini degli artt. 497 e 567",
                    norma=[(CPC, "557", "quindici giorni"), (CPC, "567", "documentazione")])],
           [("Atto", "indicazione del credito e dei beni con i dati catastali, ingiunzione al debitore")],
           ["dati catastali non indicati", "titolo o notifica del precetto mancanti"]),

    scheda("ESE_013", "Istanza di ricerca telematica dei beni", ["ESE_013"],
           [(CPC, "492bis", "ricerca con modalità telematiche"), ("1368/1941", "155quinquies", "accesso alle banche dati tramite i gestori")],
           _base() + _titolo_e_precetto() + [
            avvocato("pec", "Indirizzi di posta del creditore", "Indica la PEC e la posta ordinaria a cui ricevere l’esito", norma=[(CPC, "492bis", "contenuto dell’istanza")])],
           [("Istanza", "richiesta all’ufficiale giudiziario del luogo di residenza del debitore")],
           ["titolo o precetto mancanti"]),

    scheda("ESE_014", "Istanza di assegnazione delle somme", ["ESE_014"],
           [(CPC, "553", "assegnazione e vendita di crediti"), (CPC, "552", "assegnazione e vendita di cose")],
           _base() + [causa_pendente("Procedura esecutiva e numero di ruolo"),
            documento("dichiarazione", "Dichiarazione positiva del terzo", "dichiarazione del terzo", ["dichiarazione"],
                      norma=[(CPC, "547", "dichiarazione")], se_manca="se il terzo non ha dichiarato, valutare l’art. 548 o l’accertamento dell’obbligo")],
           [("Istanza", "importo dovuto e richiesta di assegnazione")], ["dichiarazione del terzo non acquisita"]),

    scheda("ESE_015", "Istanza di vendita", ["ESE_015"],
           [(CPC, "497", "efficacia del pignoramento"), (CPC, "529", "istanza di vendita dei mobili"), (CPC, "567", "istanza di vendita degli immobili"),
            (CPC, "501", "termine dilatorio")],
           _base() + [causa_pendente("Procedura esecutiva e numero di ruolo"),
            avvocato("tipo", "Tipo di pignoramento", "Mobiliare o immobiliare? (nel presso terzi l’assegnazione si chiede all’udienza, non con questa istanza; nell’immobiliare va depositata la documentazione dell’art. 567)",
                     norma=[(CPC, "567", "documentazione")]),
            letto("data_pignoramento", "Data del pignoramento", "pignoramento", "verbale o atto di pignoramento", [{"categoria": "data"}]),
            calcolo("termine", "Finestra per l’istanza", "dopo 10 giorni e non oltre 45 giorni dal pignoramento, con sospensione feriale" + IN_AVANTI,
                    norma=[(CPC, "501", "dieci giorni"), (CPC, "497", "quarantacinque giorni"), FERIALE])],
           [("Istanza", "richiesta di vendita con la documentazione prevista")], ["45 giorni dal pignoramento già trascorsi: il pignoramento è inefficace"]),

    scheda("ESE_016", "Istanza di conversione del pignoramento", ["ESE_016"],
           [(CPC, "495", "conversione prima della vendita o assegnazione")],
           _base("Debitore esecutato", "Creditore procedente") + [causa_pendente("Procedura esecutiva e numero di ruolo"), procura(),
            avvocato("deposito", "Deposito e rateizzazione", "Il debitore può depositare la somma richiesta dall’art. 495 e chiede la rateizzazione?",
                     norma=[(CPC, "495", "deposito e rate")])],
           [("Istanza", "richiesta di conversione con il deposito")], ["vendita o assegnazione già disposte"]),

    scheda("ESE_017", "Istanza di riduzione del pignoramento", ["ESE_017"],
           [(CPC, "496", "riduzione del pignoramento")],
           _base("Debitore esecutato", "Creditore procedente") + [causa_pendente("Procedura esecutiva e numero di ruolo"),
            avvocato("eccedenza", "Valore dei beni e credito", "Perché il valore dei beni pignorati supera di molto il credito e le spese?",
                     norma=[(CPC, "496", "valore superiore")])],
           [("Istanza", "confronto tra valore dei beni e importo dovuto")], ["valori non indicati"]),

    scheda("ESE_018", "Atto di intervento del creditore", ["ESE_018"],
           [(CPC, "499", "creditori che possono intervenire"), (CPC, "525", "tempestività nei mobili"), (CPC, "563", "tempestività negli immobili"),
            (CPC, "551", "intervento nel pignoramento presso terzi")],
           [difensore(), procura(), data_luogo(), assistito("Creditore interveniente"), controparte("Debitore esecutato"),
            causa_pendente("Procedura esecutiva e numero di ruolo"),
            avvocato("titolo", "Titolo o causa di prelazione", "Il credito è fondato su un titolo esecutivo, su un sequestro, su una prelazione o su scritture contabili?",
                     norma=[(CPC, "499", "legittimazione")]),
            letto("udienza", "Udienza per l’autorizzazione della vendita o dell’assegnazione", "udienza", "fascicolo dell’esecuzione",
                  [{"categoria": "data", "campo": "udienza"}], norma=[(CPC, "563", "intervento tempestivo")])],
           [("Ricorso", "credito, titolo e importo")], ["credito senza titolo né causa di prelazione: l’intervento non è ammesso"]),

    scheda("ESE_019", "Opposizione all’esecuzione", ["ESE_019"],
           [(CPC, "615", "opposizione all’esecuzione"), (CPC, "616", "giudizio di merito"), *SENZA_FERIALE],
           [difensore(), procura(), data_luogo(), assistito("Opponente"), controparte("Creditore"),
            avvocato("fase", "Esecuzione iniziata o solo precetto", "L’esecuzione è già iniziata (si propone al giudice dell’esecuzione) o c’è solo il precetto (si propone con citazione al giudice competente)?",
                     norma=[(CPC, "615", "primo e secondo comma")]),
            avvocato("motivi", "Motivi", "Perché il creditore non ha diritto di procedere (titolo inesistente o caducato, pagamento, prescrizione, impignorabilità)?"),
            avvocato("sospensione", "Sospensione", "Chiedi la sospensione dell’efficacia del titolo o del processo? Per quali gravi motivi?", obbligatorio=False,
                     norma=[(CPC, "615", "sospensione"), (CPC, "624", "sospensione del processo")]),
            letto("termine_merito", "Termine assegnato dal giudice per il giudizio di merito", "termine_merito", "ordinanza del giudice dell’esecuzione",
                  [{"categoria": "data"}], obbligatorio=False, norma=[(CPC, "616", "termine perentorio per il merito"), (CPC, "624", "estinzione se il merito non è introdotto")])],
           [("Motivi", "ragioni dell’insussistenza del diritto di procedere"), ("Conclusioni", "accertamento e sospensione")],
           ["a vendita o assegnazione già disposta l’opposizione è inammissibile salvo fatti sopravvenuti o impedimento non imputabile",
            "termine assegnato per il giudizio di merito già scaduto"]),

    scheda("ESE_020", "Opposizione agli atti esecutivi", ["ESE_020"],
           [(CPC, "617", "opposizione agli atti esecutivi entro venti giorni"), (CPC, "618", "provvedimenti del giudice")],
           [difensore(), procura(), data_luogo(), assistito("Opponente"), controparte(),
            avvocato("fase", "Atto contestato e fase", "Contesti vizi formali del titolo o del precetto prima dell’esecuzione (citazione al giudice competente) o un atto dell’esecuzione già iniziata (ricorso al giudice dell’esecuzione)?",
                     norma=[(CPC, "617", "primo e secondo comma")]),
            documento("atto", "Atto o provvedimento contestato", "atto esecutivo o provvedimento del giudice dell’esecuzione",
                      ["ordinanza", "decreto", "verbale", "provvedimento", "precetto", "titolo"], se_manca="astensione: serve l’atto contestato"),
            letto("conoscenza", "Data di notifica del titolo o del precetto, del primo atto di esecuzione o del compimento dell’atto", "conoscenza", "notifiche e comunicazioni",
                  [{"categoria": "data", "campo": "comunicazione"}, {"categoria": "prova_notifica"}]),
            calcolo("termine", "Ultimo giorno", termine=T("comunicazione", 20, feriale=False),
                    regola="20 giorni dalla notifica o dal compimento dell’atto; per prudenza calcolato senza sospensione feriale (scadenza più vicina): l’applicabilità della sospensione al termine dell’art. 617 è discussa" + IN_AVANTI, norma=[(CPC, "617", "venti giorni")]),
            avvocato("vizio", "Vizio formale", "Quale vizio di forma o di regolarità dell’atto contesti?")],
           [("Motivi", "vizi formali dell’atto"), ("Conclusioni", "annullamento e provvedimenti indilazionabili")],
           ["venti giorni scaduti anche contando la sospensione feriale (se il periodo feriale è compreso, non astenersi: indicare entrambe le date e segnalare la questione)",
            "si contesta il diritto di procedere: è opposizione all’esecuzione, non agli atti"]),

    scheda("ESE_031", "Reclamo contro un provvedimento del giudice dell’esecuzione", ["ESE_031"],
           [(CPC, "624", "reclamo contro l’ordinanza sulla sospensione"), (CPC, "669terdecies", "forme e termine di quindici giorni"),
            (CPC, "630", "reclamo contro il provvedimento sull’estinzione"), (CPC, "178", "forme del reclamo al collegio")],
           [difensore(), procura(), data_luogo(), assistito("Reclamante"), controparte(), causa_pendente("Procedura esecutiva e numero di ruolo"),
            avvocato("provvedimento", "Provvedimento reclamato", "Reclami l’ordinanza sulla sospensione (15 giorni, art. 669-terdecies) o il provvedimento sull’estinzione (20 giorni, art. 630)? Per gli altri atti si usa l’opposizione agli atti",
                     norma=[(CPC, "624", "sospensione"), (CPC, "630", "estinzione")]),
            letto("comunicazione", "Data di pronuncia o comunicazione", "comunicazione", "PEC di cancelleria", [{"categoria": "data", "campo": "comunicazione"}]),
            calcolo("termine_sospensione", "Ultimo giorno (reclamo sulla sospensione)", termine=T("comunicazione", 15),
                    regola="15 giorni, con sospensione feriale" + IN_AVANTI, obbligatorio=False, norma=[(CPC, "669terdecies", "quindici giorni"), FERIALE]),
            calcolo("termine_estinzione", "Ultimo giorno (reclamo sull’estinzione)", termine=T("comunicazione", 20),
                    regola="20 giorni, con sospensione feriale" + IN_AVANTI, obbligatorio=False, norma=[(CPC, "630", "venti giorni"), FERIALE]),
            avvocato("motivi", "Motivi del reclamo", "Quali errori contesti al provvedimento?")],
           [("Motivi", "censure al provvedimento"), ("Conclusioni", "riforma")], ["termine scaduto", "provvedimento non reclamabile: valutare l’opposizione agli atti"]),

    scheda("ESE_021", "Opposizione di terzo all’esecuzione", ["ESE_021"],
           [(CPC, "619", "opposizione di terzo"), (CPC, "620", "opposizione dopo la vendita"), ("12/1941", "92", "esclusione dalla sospensione feriale: estensione all’opposizione di terzo per orientamento giurisprudenziale, da verificare")],
           [difensore(), procura(), data_luogo(), assistito("Terzo opponente"), controparte("Creditore procedente"),
            causa_pendente("Procedura esecutiva e numero di ruolo"),
            avvocato("diritto", "Diritto sui beni pignorati", "Quale proprietà o diritto reale hai sui beni pignorati e con quali documenti lo provi?",
                     norma=[(CPC, "619", "diritto del terzo")])],
           [("Motivi", "titolarità dei beni con prova"), ("Conclusioni", "liberazione dei beni e sospensione")],
           ["prova del diritto del terzo assente"]),

    scheda("ESE_022", "Istanza di sospensione dell’esecuzione", ["ESE_022"],
           [(CPC, "624", "sospensione per opposizione"), (CPC, "624bis", "sospensione su istanza delle parti"), *SENZA_FERIALE],
           _base("Parte istante", "Altra parte") + [causa_pendente("Procedura esecutiva e numero di ruolo"),
            avvocato("tipo", "Sospensione per opposizione o concordata", "Chiedi la sospensione per un’opposizione già proposta (gravi motivi) o su istanza concorde di tutti i creditori?",
                     norma=[(CPC, "624", "gravi motivi"), (CPC, "624bis", "istanza di tutti i creditori")])],
           [("Istanza", "gravi motivi o accordo dei creditori")], ["nessuna opposizione proposta né accordo dei creditori"]),

    scheda("ESE_023", "Dichiarazione del terzo pignorato", ["ESE_023"],
           [(CPC, "547", "contenuto della dichiarazione"), (CPC, "548", "mancata dichiarazione")],
           [difensore(), data_luogo(), assistito("Terzo pignorato"), controparte("Creditore procedente"),
            documento("atto", "Atto di pignoramento ricevuto", "atto di pignoramento presso terzi", ["pignoramento"], se_manca="astensione: serve l’atto"),
            avvocato("somme", "Somme o beni del debitore", "Di quali somme o beni del debitore sei debitore o detentore, con quali vincoli o sequestri anteriori?",
                     norma=[(CPC, "547", "specificazione")])],
           [("Dichiarazione", "somme o cose dovute, pagamenti, sequestri e cessioni anteriori")], ["atto di pignoramento non presente"]),

    scheda("ESE_024", "Contestazione della dichiarazione del terzo", ["ESE_024"],
           [(CPC, "549", "contestazioni sulla dichiarazione")],
           _base() + [causa_pendente("Procedura esecutiva e numero di ruolo"),
            documento("dichiarazione", "Dichiarazione contestata", "dichiarazione del terzo", ["dichiarazione"], se_manca="astensione: serve la dichiarazione"),
            avvocato("motivi", "Motivi della contestazione", "Perché la dichiarazione è incompleta o non veritiera? Con quali prove?")],
           [("Istanza", "contestazione con prove e richiesta di accertamento")], ["dichiarazione del terzo non presente"]),

    scheda("ESE_025", "Istanze sul custode e sulla liberazione dell’immobile pignorato", ["ESE_025", "ESE_032", "ESE_033"],
           [(CPC, "559", "nomina e sostituzione del custode"), (CPC, "560", "modo della custodia e ordine di liberazione"),
            (CPC, "617", "l’ordine di liberazione si impugna con l’opposizione agli atti")],
           _base() + [causa_pendente("Procedura esecutiva e numero di ruolo"),
            avvocato("richiesta", "Richiesta e motivi", "Chiedi la nomina o la sostituzione del custode, o l’ordine di liberazione? Per quali fatti (mancata collaborazione, danni, occupazione senza titolo)?",
                     norma=[(CPC, "560", "liberazione"), (CPC, "559", "nomina e sostituzione")])],
           [("Istanza", "fatti e provvedimento richiesto")], ["motivi non indicati"]),

    scheda("ESE_026", "Estinzione o rinuncia nella procedura esecutiva", ["ESE_026", "ESE_027"],
           [(CPC, "629", "rinuncia"), (CPC, "630", "inattività e reclamo"), (CPC, "631", "mancata comparizione")],
           _base("Parte istante", "Altra parte") + [causa_pendente("Procedura esecutiva e numero di ruolo"),
            avvocato("causa", "Causa di estinzione", "Rinunciano tutti i creditori titolati (prima dell’aggiudicazione) o c’è inattività delle parti?",
                     norma=[(CPC, "629", "rinuncia dei creditori"), (CPC, "630", "inattività")]),
            calcolo("reclamo", "Reclamo contro il provvedimento sull’estinzione", termine=T("comunicazione", 20),
                    regola="20 giorni dall’udienza o dalla comunicazione dell’ordinanza, con sospensione feriale" + IN_AVANTI,
                    obbligatorio=False, norma=[(CPC, "630", "reclamo"), FERIALE])],
           [("Istanza", "causa di estinzione e richiesta di dichiararla")], ["dopo la vendita mancano le rinunce di tutti i creditori concorrenti"]),

    scheda("ESE_028", "Precisazione e aggiornamento del credito", ["ESE_028", "ESE_029"],
           [(CPC, "596", "progetto di distribuzione"), (CPC, "499", "creditori intervenuti")],
           _base() + [causa_pendente("Procedura esecutiva e numero di ruolo"),
            lex("conteggio", "Conteggio del credito", "capitale, interessi fino alla data indicata dal giudice e spese, con i documenti", norma=[(CPC, "596", "distribuzione")]),
            avvocato("privilegi", "Cause di prelazione", "Il credito ha privilegi o ipoteche? Indica grado e documenti", obbligatorio=False)],
           [("Nota", "conteggio analitico del credito con le cause di prelazione")], ["data di riferimento del conteggio non indicata"]),

    scheda("ESE_030", "Osservazioni al progetto di distribuzione", ["ESE_030"],
           [(CPC, "598", "approvazione del progetto"), (CPC, "512", "controversie distributive")],
           _base() + [causa_pendente("Procedura esecutiva e numero di ruolo"),
            documento("progetto", "Progetto di distribuzione", "progetto depositato", ["progetto", "distribuzione", "riparto"], se_manca="astensione: serve il progetto"),
            letto("udienza", "Udienza di discussione del progetto", "udienza", "decreto di fissazione", [{"categoria": "data", "campo": "udienza"}]),
            avvocato("contestazioni", "Contestazioni", "Quali voci del progetto contesti (importo, grado, esistenza del credito altrui)?",
                     norma=[(CPC, "512", "controversie")])],
           [("Osservazioni", "contestazioni puntuali al progetto")], ["progetto di distribuzione non presente"]),
]
