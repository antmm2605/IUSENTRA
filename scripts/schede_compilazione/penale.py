"""Schede del processo penale (PEN).

Base normativa: codice di procedura penale (testo dopo D.Lgs. 150/2022 e L. 114/2024); artt. 120-126 e 152 c.p.
(querela e remissione); L. 354/1975 (ordinamento penitenziario). Sospensione feriale: si applica ai termini
processuali penali, salvo i procedimenti con imputati detenuti o in misura cautelare e quelli in cui l’imputato
rinuncia (art. 2 L. 742/1969; art. 91 ord. giud.); per questi i termini si calcolano senza sospensione.
"""
from scripts.schede_compilazione.comuni import (FERIALE, PENALE, T, avvocato, calcolo, data_luogo, database, documento, letto, lex)
from scripts.schede_compilazione.costruisci import scheda

CPP = "codice_procedura_penale"
CP = "codice_penale"
DETENUTI = ("legge_742_1969", "2", "sospensione esclusa con imputati detenuti")


def _difensore():
    return database("difensore", "Difensore, foro e PEC", ["studio.avvocato_titolare", "studio_timbro.codice_fiscale", "studio_timbro.pec"],
                    norma=[(CPP, "96", "difensore di fiducia")], compilatore=["lawyer", "_lawyer_pec", "_lawyer_tax_id"])


def _assistito(et="Assistito (indagato, imputato o persona offesa)"):
    return database("assistito", et, ["parti.assistito_principale", "cliente"], compilatore=["client_or_sender"])


def _nomina():
    return documento("nomina", "Nomina del difensore depositata", "atto di nomina", ["nomina"],
                     norma=[(CPP, "96", "nomina")], se_manca="chiedere la nomina: senza non si deposita per l’assistito")


def _procedimento():
    return letto("procedimento", "Autorità procedente e numero del procedimento (R.G.N.R. o R.G.)", "ufficio_e_rg", "avvisi e notifiche",
                 [{"categoria": "ruolo"}], se_manca="chiedere autorità e numero del procedimento")


def _detenuto():
    return avvocato("detenuto", "Assistito detenuto o in misura cautelare", "L’assistito è detenuto o sottoposto a misura cautelare? (esclude la sospensione feriale)",
                    norma=[DETENUTI])


def _base(et=None):
    return [_difensore(), data_luogo(), _assistito(et) if et else _assistito(), _nomina(), _procedimento()]


SCHEDE = [
    scheda("PEN_001", "Nomina, revoca o rinuncia del difensore", ["PEN_001", "PEN_002"],
           [(CPP, "96", "difensore di fiducia: massimo due"), (CPP, "107", "rinuncia e revoca"), (CPP, "100", "difensore della parte civile e della persona offesa")],
           [_difensore(), data_luogo(), _assistito(), _procedimento(),
            avvocato("atto", "Atto", "Nomina, revoca o rinuncia? Con elezione di domicilio presso il difensore?", norma=[(CPP, "161", "elezione di domicilio")]),
            lex("rinuncia", "Effetti della rinuncia", "ricordare che la rinuncia non ha effetto finché la parte non ha un nuovo difensore e non è decorso il termine a difesa",
                norma=[(CPP, "107", "efficacia")])],
           [("Atto", "dichiarazione sottoscritta e autenticata")], ["autorità o numero del procedimento non noti"]),

    scheda("PEN_003", "Memorie, istanze e richieste al giudice o al pubblico ministero",
           ["PEN_003", "PEN_004", "PEN_005", "PEN_015", "PEN_016", "PEN_024"],
           [(CPP, "121", "memorie e richieste delle parti"), (CPP, "420ter", "legittimo impedimento"), (CPP, "116", "copie di atti"),
            (CPP, "415bis", "avviso di conclusione delle indagini e accesso"), (CPP, "421", "discussione in udienza preliminare")],
           _base() + [
               avvocato("istanza", "Atto richiesto", "Memoria, rinvio, legittimo impedimento (con prova), copie, accesso al fascicolo o memoria per l’udienza preliminare?"),
               letto("udienza", "Udienza", "udienza", "decreti e avvisi", [{"categoria": "data", "campo": "udienza"}], obbligatorio=False),
               documento("impedimento", "Prova dell’impedimento", "certificato medico o prova dell’impegno concomitante", ["certificato", "impedimento"], obbligatorio=False,
                         norma=[(CPP, "420ter", "assoluta impossibilità e comunicazione tempestiva")]),
               avvocato("termine_415bis", "Termine dell’avviso di conclusione", "Se c’è l’avviso dell’art. 415-bis: entro 20 giorni memorie, documenti, richiesta di interrogatorio",
                        obbligatorio=False, norma=[(CPP, "415bis", "venti giorni")])],
           [("Atto", "richiesta motivata")], ["procedimento non individuato"]),

    scheda("PEN_006", "Lista testimoni", ["PEN_006"],
           [(CPP, "468", "citazione di testimoni, periti e consulenti"), FERIALE],
           _base() + [
               letto("udienza", "Udienza dibattimentale", "udienza", "decreto che dispone il giudizio", [{"categoria": "data", "campo": "udienza"}],
                     se_manca="chiedere la data del dibattimento"),
               calcolo("termine", "Ultimo giorno per depositare la lista", termine=T("udienza", 8, ritroso=True, sabato=False),
                       regola="almeno 7 giorni prima del dibattimento, contati come liberi secondo la giurisprudenza prevalente, a pena di inammissibilità", norma=[(CPP, "468", "sette giorni liberi")]),
               avvocato("testi", "Testimoni e circostanze", "Nomi, recapiti e circostanze su cui ciascuno deve deporre", norma=[(CPP, "468", "indicazione delle circostanze")])],
           [("Lista", "testimoni e circostanze")], ["data del dibattimento non nota"]),

    scheda("PEN_007", "Opposizione a decreto penale di condanna", ["PEN_007"],
           [(CPP, "461", "opposizione"), (CPP, "459", "decreto penale"), (CPP, "464", "giudizio conseguente")],
           _base("Imputato") + [
               documento("decreto", "Decreto penale notificato", "decreto penale di condanna", ["decreto"], se_manca="astensione: serve il decreto"),
               letto("notifica", "Data di notifica del decreto", "notifica", "relata", [{"categoria": "data", "campo": "notifica"}]),
               calcolo("termine", "Ultimo giorno per l’opposizione", termine=T("notifica", 15, sabato=False), regola="15 giorni dalla notifica del decreto, con sospensione feriale" + PENALE,
                       norma=[(CPP, "461", "quindici giorni"), FERIALE]),
               avvocato("rito", "Rito richiesto", "Giudizio immediato, abbreviato, patteggiamento, oblazione o messa alla prova?", norma=[(CPP, "461", "richieste con l’opposizione")]),
               lex("pagamento", "Riduzione", "ricordare la riduzione di un quinto della pena pecuniaria se si paga entro 15 giorni rinunciando all’opposizione",
                   norma=[(CPP, "460", "riduzione")])],
           [("Opposizione", "dichiarazione e richiesta di rito")], ["decreto non presente", "quindici giorni scaduti"]),

    scheda("PEN_008", "Opposizione alla richiesta di archiviazione", ["PEN_008"],
           [(CPP, "408", "avviso alla persona offesa e termine"), (CPP, "410", "opposizione con indagini suppletive"), FERIALE],
           _base("Persona offesa") + [
               letto("notifica", "Notifica dell’avviso di archiviazione", "notifica", "avviso", [{"categoria": "data", "campo": "notifica"}]),
               calcolo("termine", "Ultimo giorno per l’opposizione", termine=T("notifica", 20, sabato=False),
                       regola="20 giorni dalla notifica dell’avviso (30 per i delitti con violenza alla persona e furto in abitazione)" + PENALE,
                       norma=[(CPP, "408", "venti o trenta giorni")]),
               avvocato("indagini", "Indagini suppletive e prove", "Quali indagini integrative chiedi e quali elementi di prova le giustificano?",
                        norma=[(CPP, "410", "a pena di inammissibilità")])],
           [("Opposizione", "indagini suppletive ed elementi di prova")], ["avviso non presente", "nessuna indagine suppletiva indicata"]),

    scheda("PEN_009", "Querela, denuncia-querela e remissione", ["PEN_009", "PEN_010", "PEN_011"],
           [(CP, "120", "diritto di querela"), (CP, "124", "termine di tre mesi"), (CP, "152", "remissione"), (CPP, "336", "querela"), (CPP, "337", "forme"),
            (CPP, "340", "remissione")],
           [_difensore(), data_luogo(), _assistito("Persona offesa"),
            avvocato("fatto", "Fatto", "Cosa è accaduto, quando, dove, chi è il responsabile se noto, con testimoni e documenti"),
            letto("conoscenza", "Data di conoscenza del fatto", "evento", "documenti", [{"categoria": "data", "campo": "evento"}], obbligatorio=False),
            calcolo("termine", "Ultimo giorno per la querela", termine=T("evento", mesi=3, feriale=False, sabato=False),
                    regola="3 mesi dalla notizia del fatto; per i delitti sessuali 12 mesi (art. 609-septies c.p.): in quel caso la data calcolata non vale; termine sostanziale, senza sospensione feriale",
                    norma=[(CP, "124", "tre mesi")]),
            avvocato("procedibilita", "Reato procedibile a querela", "Il reato è procedibile a querela? Per la remissione: è stata accettata o non ricusata?",
                     norma=[(CP, "152", "remissione"), (CPP, "340", "accettazione")])],
           [("Atto", "esposizione del fatto, istanza di punizione, richiesta di essere avvisati dell’archiviazione")], ["reato procedibile d’ufficio: basta la denuncia"]),

    scheda("PEN_012", "Costituzione di parte civile", ["PEN_012"],
           [(CPP, "74", "legittimazione"), (CPP, "76", "procura speciale"), (CPP, "78", "forma"), (CPP, "79", "termine"), (CPP, "100", "difensore")],
           _base("Danneggiato") + [
               documento("procura_speciale", "Procura speciale", "procura speciale per la costituzione", ["procura"], norma=[(CPP, "76", "procura speciale")],
                         se_manca="astensione: serve la procura speciale"),
               avvocato("danno", "Danno e ragioni della domanda", "Quali danni patrimoniali e non patrimoniali, e il nesso con il reato?", norma=[(CPP, "78", "ragioni della domanda")]),
               lex("termine", "Termine", "ricordare che la costituzione va fatta prima che siano compiuti gli accertamenti sulla costituzione delle parti nell’udienza preliminare o nel dibattimento",
                   norma=[(CPP, "79", "termine")])],
           [("Atto", "generalità, imputato, ragioni della domanda, procura")], ["procura speciale mancante"]),

    scheda("PEN_013", "Istanza di dissequestro o restituzione di beni sequestrati", ["PEN_013", "PEN_014"],
           [(CPP, "262", "restituzione delle cose sequestrate"), (CPP, "263", "procedimento"), (CPP, "324", "riesame del sequestro preventivo")],
           _base() + [
               documento("verbale", "Verbale o decreto di sequestro", "decreto di sequestro", ["sequestro"], se_manca="chiedere il decreto o il verbale"),
               avvocato("titolarita", "Titolarità dei beni e cessazione delle esigenze", "Chi è proprietario e perché il vincolo non è più necessario?",
                        norma=[(CPP, "262", "esigenze probatorie cessate")]),
               lex("riesame", "Riesame", "ricordare che il riesame del sequestro va chiesto entro 10 giorni dall’esecuzione o dalla conoscenza", norma=[(CPP, "324", "dieci giorni")])],
           [("Istanza", "beni, titolarità, ragioni della restituzione")], ["decreto di sequestro non presente"]),

    scheda("PEN_017", "Richiesta di incidente probatorio", ["PEN_017"],
           [(CPP, "392", "casi"), (CPP, "393", "richiesta"), (CPP, "395", "deposito e notifica")],
           _base() + [avvocato("prova", "Prova e caso", "Quale prova, quale caso dell’art. 392, perché non rinviabile al dibattimento?", norma=[(CPP, "393", "contenuto a pena di inammissibilità")])],
           [("Richiesta", "prova, fatti, persone, ragioni dell’urgenza")], ["caso non previsto dall’art. 392"]),

    scheda("PEN_018", "Appello penale e ricorso per cassazione", ["PEN_018", "PEN_019"],
           [(CPP, "581", "forma dell’impugnazione"), (CPP, "585", "termini"), (CPP, "593", "casi di appello"), (CPP, "606", "motivi di ricorso per cassazione"),
            (CPP, "613", "ricorso sottoscritto da difensore cassazionista"), FERIALE, DETENUTI],
           _base("Imputato o parte") + [_detenuto(),
               documento("sentenza", "Sentenza impugnata", "sentenza", ["sentenza"], se_manca="astensione: serve la sentenza"),
               avvocato("motivazione", "Tempi della motivazione", "Motivazione contestuale, entro 15 giorni o entro il termine fissato fino a 90 giorni? Imputato giudicato in assenza?",
                        norma=[(CPP, "585", "15, 30 o 45 giorni dalla decorrenza; +15 per l’assente")]),
               letto("decorrenza", "Data da cui decorre il termine (lettura, scadenza per il deposito, avviso di deposito)", "provvedimento", "sentenza e avvisi",
                     [{"categoria": "data", "campo": "provvedimento"}]),
               avvocato("motivi", "Motivi e richieste", "Capi e punti impugnati, prove, richieste, ragioni di diritto", norma=[(CPP, "581", "specificità a pena di inammissibilità")]),
               lex("elezione", "Requisiti del difensore", "per l’imputato giudicato in assenza e difeso d’ufficio serve lo specifico mandato a impugnare rilasciato dopo la sentenza, con dichiarazione o elezione di domicilio (comma 1-ter abrogato dalla L. 114/2024)",
                   norma=[(CPP, "581", "mandato specifico per l’assente difeso d’ufficio")])],
           [("Impugnazione", "capi, punti, motivi, richieste")], ["sentenza non presente", "termini scaduti"]),

    scheda("PEN_020", "Esecuzione penale: misure alternative e sospensione dell’ordine di esecuzione", ["PEN_020", "PEN_021"],
           [(CPP, "656", "sospensione dell’ordine di esecuzione e istanza entro trenta giorni"), ("legge_354_1975", "47", "affidamento in prova"),
            ("legge_354_1975", "47ter", "detenzione domiciliare"), ("legge_354_1975", "50", "semilibertà")],
           _base("Condannato") + [
               documento("ordine", "Ordine di esecuzione e decreto di sospensione", "ordine di esecuzione", ["esecuzione"], se_manca="chiedere l’ordine di esecuzione"),
               letto("notifica", "Notifica dell’ordine e del decreto di sospensione", "notifica", "relata", [{"categoria": "data", "campo": "notifica"}]),
               calcolo("termine", "Ultimo giorno per l’istanza di misura alternativa", termine=T("notifica", 30, feriale=False, sabato=False),
                       regola="30 giorni dalla notifica dell’ordine sospeso, calcolati senza sospensione feriale: è la data che non espone a decadenza" + PENALE, norma=[(CPP, "656", "trenta giorni")]),
               avvocato("misura", "Misura richiesta e requisiti", "Pena residua, misura richiesta, lavoro, domicilio, percorso"),
],
           [("Istanza", "misura, requisiti, documenti")], ["ordine di esecuzione non presente"]),

    scheda("PEN_022", "Istanza di revoca o sostituzione di misura cautelare", ["PEN_022", "PEN_023"],
           [(CPP, "299", "revoca e sostituzione"), (CPP, "274", "esigenze cautelari"), (CPP, "275", "proporzionalità e adeguatezza"), DETENUTI],
           _base("Indagato o imputato") + [
               documento("ordinanza", "Ordinanza applicativa", "ordinanza cautelare", ["ordinanza"], se_manca="chiedere l’ordinanza"),
               avvocato("fatti_nuovi", "Fatti nuovi o attenuazione delle esigenze", "Cosa è cambiato (tempo trascorso, condotta, lavoro, domicilio)?", norma=[(CPP, "299", "presupposti")]),
               lex("notifica_po", "Notifica alla persona offesa", "ricordare che nei delitti con violenza alla persona l’istanza va notificata alla persona offesa a pena di inammissibilità",
                   norma=[(CPP, "299", "notifica alla persona offesa")])],
           [("Istanza", "fatti nuovi, esigenze, misura meno afflittiva")], ["ordinanza non presente"]),

    scheda("PEN_025", "Questioni preliminari al dibattimento", ["PEN_025"],
           [(CPP, "491", "questioni preliminari"), (CPP, "178", "nullità di ordine generale"), (CPP, "181", "nullità relative")],
           _base("Imputato") + [
               letto("udienza", "Udienza dibattimentale", "udienza", "decreto di citazione", [{"categoria": "data", "campo": "udienza"}]),
               avvocato("questioni", "Questioni", "Competenza, nullità, costituzione di parte civile, riunione o separazione: da proporre subito dopo l’accertamento della costituzione",
                        norma=[(CPP, "491", "a pena di decadenza")])],
           [("Eccezioni", "questioni con norme")], ["udienza non nota"]),
]
