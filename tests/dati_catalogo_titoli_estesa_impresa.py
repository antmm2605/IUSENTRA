"""Documenti di prova delle regole di `pct.document_intelligence.titoli.estesa_impresa`.

Solo dati inventati. Per ogni regola: un campione (`CAMPIONI`) e dieci varianti (`VARIANTI`) che cambiano forma
del titolo, intestazione dell'ufficio o della parte, numero del procedimento, caso concreto e lunghezza.
"""

from __future__ import annotations

_UFFICI = {
    "crisi": (
        "TRIBUNALE DI BARI - SEZIONE FALLIMENTARE", "TRIBUNALE ORDINARIO DI MILANO\nSezione II civile - Procedure concorsuali",
        "TRIBUNALE DI NAPOLI NORD", "TRIBUNALE DI VERONA", "TRIBUNALE DI PALERMO - SEZIONE IV CIVILE E FALLIMENTARE",
        "TRIBUNALE DI ANCONA",
    ),
    "impresa": (
        "TRIBUNALE DI MILANO\nSezione specializzata in materia di impresa", "TRIBUNALE DI ROMA - SEZIONE XVI CIVILE",
        "TRIBUNALE DI TORINO\nSezione specializzata in materia di impresa", "TRIBUNALE DI BOLOGNA",
        "TRIBUNALE DI BARI - SEZIONE IMPRESE", "TRIBUNALE DI VENEZIA",
    ),
    "civile": (
        "TRIBUNALE DI BARI", "TRIBUNALE DI GENOVA - SEZIONE I CIVILE", "TRIBUNALE DI CATANIA", "TRIBUNALE DI PADOVA",
        "TRIBUNALE DI LECCE", "TRIBUNALE DI PERUGIA",
    ),
    "studio": (
        "STUDIO LEGALE BIANCHI\nVia Roma 1 - 70121 Bari", "Avv. Laura Verdi\nCorso Italia 12 - Milano",
        "STUDIO LEGALE ASSOCIATO NERI & GIALLI", "Mario Rossi\nVia Garibaldi 8 - Torino", "Beta S.r.l.\nVia Dante 3 - Firenze",
        "Avv. Paolo Esposito - Foro di Napoli",
    ),
    "parte": (
        "ALFA S.R.L.", "BETA S.P.A. - Codice fiscale 01234567890", "Gamma Costruzioni S.r.l.",
        "DELTA SOCIETÀ COOPERATIVA", "Epsilon S.p.A. - Sede legale in Verona", "Zeta S.r.l. unipersonale",
    ),
    "banca": (
        "BANCA ALFA S.P.A. - Filiale di Bari", "Notaio Paolo Neri in Milano - Rep. n. 12.345", "GAMMA FINANZIARIA S.P.A.",
        "Credito Delta S.p.A. - Sede di Roma", "BANCA EPSILON SOCIETÀ COOPERATIVA", "Zeta Leasing S.p.A.",
    ),
    "assicurazione": (
        "ALFA ASSICURAZIONI S.P.A.", "Beta Vita S.p.A. - Agenzia di Bari", "Mario Rossi\nVia Garibaldi 8 - Torino",
        "STUDIO LEGALE BIANCHI\nVia Roma 1 - 70121 Bari", "Gamma Assicurazioni S.p.A. - Direzione sinistri",
        "Avv. Laura Verdi\nCorso Italia 12 - Milano",
    ),
    "autorita": (
        "AUTORITÀ GARANTE DELLA CONCORRENZA E DEL MERCATO\nPiazza Verdi 6/a - Roma", "Mario Rossi\nVia Garibaldi 8 - Torino",
        "STUDIO LEGALE BIANCHI\nVia Roma 1 - 70121 Bari", "Associazione consumatori Alfa\nVia Po 3 - Milano",
        "Beta S.r.l.\nVia Dante 3 - Firenze", "Avv. Paolo Esposito - Foro di Napoli",
    ),
    "ufficio_pi": (
        "UFFICIO ITALIANO BREVETTI E MARCHI", "Mandatario abilitato Ing. Carlo Neri - Milano", "ALFA S.R.L.",
        "Studio brevetti Gialli & Partners", "Beta S.p.A. - Ufficio proprietà intellettuale", "Avv. Laura Verdi\nCorso Italia 12 - Milano",
    ),
    "procedura": (
        "Liquidazione giudiziale Alfa S.r.l. - Tribunale di Bari", "Concordato preventivo Beta S.p.A. - Tribunale di Milano",
        "Procedura n. 45/2026 - Tribunale di Verona", "Gamma S.r.l. in liquidazione giudiziale",
        "Procedura di sovraindebitamento Mario Rossi - Tribunale di Lecce", "Delta S.p.A. - Tribunale di Ancona",
    ),
}

_NUMERI = ("R.G. n. {n}/2026", "Proc. n. {n}/2026", "Rif. n. {n}/2026", "N. {n}/2025 R.G.", "Fascicolo {n}/2026")

_AGGIUNTE = (
    "Si allegano i documenti indicati nell'elenco in calce.",
    "Il presente atto si compone di quattro pagine e due allegati.",
    "Per ogni comunicazione si indica l'indirizzo di posta elettronica certificata studio.esempio@pec.it.",
)

# regola -> (etichetta, sezione, intestazioni, titoli, corpi). Il primo titolo e il primo corpo formano il campione.
_SPEC: dict[str, tuple[str, str, str, tuple[str, ...], tuple[str, ...]]] = {
    # ── Crisi d'impresa e insolvenza ──
    "imp_sentenza_apertura_liquidazione_giudiziale": (
        "Sentenza di apertura della liquidazione giudiziale", "provvedimenti", "crisi",
        ("Sentenza di apertura della liquidazione giudiziale", "Sentenza dichiarativa di apertura della liquidazione giudiziale",
         "Sentenza di liquidazione giudiziale", "Sentenza dichiarativa di fallimento"),
        ("Il Tribunale, accertato lo stato di insolvenza di Alfa S.r.l., dichiara aperta la liquidazione giudiziale, nomina giudice delegato la dott.ssa Anna Neri e curatore il dott. Carlo Gialli.",
         "Il Collegio, sentito il debitore, nomina curatore l'avv. Marta Blu e assegna ai creditori il termine per le domande di ammissione al passivo.",
         "Ai sensi dell'art. 49 CCII il Tribunale ordina al debitore il deposito dei bilanci e delle scritture contabili entro tre giorni."),
    ),
    "imp_reclamo_sentenza_concorsuale": (
        "Reclamo contro la sentenza di liquidazione giudiziale o di omologazione (art. 51 CCII)", "atti", "civile",
        ("Reclamo avverso la sentenza di apertura della liquidazione giudiziale", "Reclamo contro la sentenza di liquidazione giudiziale",
         "Reclamo ex art. 51 CCII", "Reclamo avverso la sentenza di omologazione"),
        ("Alla Corte d'Appello di Bari. Beta S.p.A. propone reclamo contro la sentenza n. 12/2026 che ha aperto la liquidazione giudiziale, contestando lo stato di insolvenza.",
         "Il creditore dissenziente Gamma S.r.l. impugna la sentenza di omologazione del concordato con reclamo ai sensi dell'art. 51 CCII.",
         "Il debitore chiede alla Corte d'appello di revocare la sentenza per difetto del requisito dimensionale e di sospenderne gli effetti."),
    ),
    "imp_relazione_curatore": (
        "Relazione del curatore (art. 130 CCII)", "allegati", "procedura",
        ("Relazione del curatore ex art. 130 CCII", "Relazione particolareggiata del curatore", "Relazione iniziale del curatore",
         "Rapporto riepilogativo semestrale"),
        ("Il curatore espone al giudice delegato le cause e circostanze dell'insolvenza di Alfa S.r.l. e la diligenza dell'amministratore nella gestione.",
         "Ai sensi dell'art. 130 CCII si riferisce sugli atti compiuti dagli amministratori nei tre anni anteriori e sulle possibili azioni di responsabilità.",
         "Il curatore riepiloga l'attività svolta nel semestre, gli incassi realizzati e le cause dell'insolvenza già descritte."),
    ),
    "imp_programma_liquidazione": (
        "Programma di liquidazione", "allegati", "procedura",
        ("Programma di liquidazione", "Programma di liquidazione ex art. 213 CCII", "Supplemento al programma di liquidazione" ,
         "Programma di liquidazione - aggiornamento"),
        ("Il curatore sottopone al comitato dei creditori le modalità e i tempi di realizzo dell'attivo, con la vendita dell'immobile di Bari mediante procedura competitiva.",
         "Ai sensi dell'art. 213 CCII si prevede la cessione in blocco del magazzino e l'esercizio delle azioni recuperatorie.",
         "Il programma indica i beni dell'attivo da liquidare entro cinque anni dall'apertura della liquidazione giudiziale."),
    ),
    "imp_inventario_concorsuale": (
        "Inventario dei beni della procedura concorsuale", "allegati", "procedura",
        ("Inventario dei beni acquisiti all'attivo", "Inventario fallimentare", "Inventario dei beni della procedura",
         "Inventario dei beni del debitore"),
        ("Il curatore, con l'assistenza del cancelliere, procede all'inventario dei beni rinvenuti presso la sede di Alfa S.r.l.: macchinari, automezzi e merci.",
         "Ai sensi dell'art. 195 CCII si descrivono i beni mobili e se ne indica il valore di stima.",
         "Presenti il curatore e il perito stimatore, si elencano gli arredi d'ufficio e due autocarri targati AB123CD e EF456GH."),
    ),
    "imp_avviso_curatore_creditori": (
        "Avviso del curatore ai creditori (art. 200 CCII)", "comunicazioni", "procedura",
        ("Avviso ai creditori", "Comunicazione del curatore ai creditori ex art. 200", "Avviso del curatore ai creditori",
         "Comunicazione ai creditori"),
        ("Il curatore comunica l'apertura della liquidazione giudiziale e il termine per presentare la domanda di ammissione al passivo all'indirizzo PEC della procedura.",
         "Ai sensi dell'art. 200 CCII si avvisa che l'udienza di esame dello stato passivo è fissata per il 10/09/2026.",
         "Il curatore invita i creditori a trasmettere le domande di ammissione almeno trenta giorni prima dell'udienza."),
    ),
    "imp_progetto_ripartizione_concorsuale": (
        "Progetto di ripartizione dell'attivo (art. 220 CCII)", "provvedimenti", "procedura",
        ("Progetto di ripartizione parziale", "Progetto di riparto finale", "Progetto di ripartizione dell'attivo",
         "Progetto di ripartizione"),
        ("Il curatore deposita il progetto di ripartizione delle somme disponibili fra i creditori ammessi in prededuzione, privilegio e chirografo.",
         "Ai sensi dell'art. 220 CCII il giudice delegato ordina il deposito del progetto e la comunicazione ai creditori.",
         "Il curatore propone di distribuire euro 120.000,00 secondo l'ordine delle cause di prelazione."),
    ),
    "imp_rendiconto_curatore": (
        "Rendiconto del curatore", "allegati", "procedura",
        ("Rendiconto del curatore", "Rendiconto finale della gestione del curatore", "Rendiconto della gestione ex art. 231",
         "Rendiconto finale del curatore"),
        ("Il curatore espone analiticamente le operazioni contabili e l'attività di gestione della procedura dal giorno dell'apertura.",
         "Ai sensi dell'art. 231 CCII si presenta il conto delle entrate e delle uscite per l'approvazione del giudice delegato.",
         "Il rendiconto riporta incassi per euro 250.000,00 e spese di gestione per euro 18.000,00."),
    ),
    "imp_decreto_apertura_concordato": (
        "Decreto di apertura del concordato preventivo", "provvedimenti", "crisi",
        ("Decreto di apertura del concordato preventivo", "Decreto di ammissione al concordato preventivo",
         "Decreto di apertura della procedura di concordato preventivo", "Decreto di ammissione del concordato preventivo"),
        ("Il Tribunale, verificata l'ammissibilità della proposta, dichiara aperta la procedura, nomina giudice delegato e commissario giudiziale il dott. Luca Verdi.",
         "Ai sensi dell'art. 47 CCII si fissa la data iniziale e finale per il voto dei creditori.",
         "Il Tribunale nomina il commissario giudiziale e ordina il deposito della somma per le spese della procedura."),
    ),
    "imp_domanda_accesso_con_riserva": (
        "Domanda di accesso con riserva (art. 44 CCII)", "atti", "crisi",
        ("Domanda di accesso con riserva", "Ricorso per l'accesso al concordato preventivo con riserva", "Ricorso ex art. 44 CCII",
         "Domanda prenotativa"),
        ("Alfa S.r.l. chiede la concessione del termine per il deposito della proposta di concordato, del piano e della documentazione.",
         "La società si riserva di depositare la proposta entro il termine di sessanta giorni ai sensi dell'art. 44 CCII.",
         "La ricorrente, in stato di crisi, chiede che sia assegnato il termine per presentare un accordo di ristrutturazione."),
    ),
    "imp_sentenza_omologazione_ccii": (
        "Sentenza di omologazione del concordato o degli accordi di ristrutturazione", "provvedimenti", "crisi",
        ("Sentenza di omologazione del concordato preventivo", "Sentenza di omologa del concordato minore",
         "Sentenza di omologazione degli accordi di ristrutturazione dei debiti", "Sentenza di omologazione del piano di ristrutturazione"),
        ("Il Tribunale, rilevato il raggiungimento delle maggioranze dei creditori, omologa il concordato proposto da Beta S.p.A.",
         "Ai sensi dell'art. 48 CCII il Collegio, esaminate le opposizioni, omologa gli accordi e ne dispone la pubblicazione.",
         "Il Tribunale omologa la proposta e nomina il liquidatore giudiziale per l'esecuzione del piano."),
    ),
    "imp_relazione_commissario_giudiziale": (
        "Relazione del commissario giudiziale", "allegati", "procedura",
        ("Relazione del commissario giudiziale", "Relazione ex art. 105 CCII", "Relazione particolareggiata del commissario giudiziale",
         "Relazione del commissario giudiziale ai creditori"),
        ("Il commissario giudiziale illustra ai creditori le cause del dissesto e la convenienza della proposta rispetto alla liquidazione giudiziale.",
         "Ai sensi dell'art. 105 CCII si deposita la relazione almeno quarantacinque giorni prima del voto.",
         "Il commissario esprime parere favorevole sulla fattibilità del piano e sulle garanzie offerte."),
    ),
    "imp_dichiarazione_voto_concordato": (
        "Dichiarazione di voto del creditore", "comunicazioni", "studio",
        ("Dichiarazione di voto", "Espressione del voto sulla proposta di concordato", "Dichiarazione di voto del creditore",
         "Manifestazione di voto nel concordato preventivo"),
        ("Il creditore Gamma S.r.l. esprime voto favorevole alla proposta di concordato preventivo di Alfa S.r.l. e lo trasmette al commissario giudiziale.",
         "Ai sensi dell'art. 107 CCII il sottoscritto creditore vota contro la proposta per il credito chirografario di euro 8.000,00.",
         "Il creditore privilegiato rinuncia parzialmente alla prelazione e vota a favore del concordato."),
    ),
    "imp_attestazione_professionista": (
        "Relazione di attestazione del professionista indipendente", "allegati", "parte",
        ("Relazione di attestazione del professionista indipendente", "Attestazione di veridicità dei dati e fattibilità del piano",
         "Attestazione ex art. 87 CCII", "Relazione del professionista attestatore"),
        ("Il sottoscritto professionista indipendente attesta la veridicità dei dati aziendali e la fattibilità del piano di concordato.",
         "Verificate le scritture contabili, si attesta che il piano è idoneo a garantire il soddisfacimento dei creditori.",
         "Il professionista attestatore conferma la fattibilità economica e giuridica degli accordi."),
    ),
    "imp_omologazione_accordi_ristrutturazione": (
        "Domanda di omologazione degli accordi di ristrutturazione dei debiti", "atti", "crisi",
        ("Domanda di omologazione degli accordi di ristrutturazione dei debiti", "Ricorso per l'omologazione degli accordi di ristrutturazione",
         "Ricorso per omologazione dell'accordo di ristrutturazione", "Domanda di omologa degli accordi di ristrutturazione agevolati"),
        ("Alfa S.r.l. chiede l'omologazione degli accordi conclusi con creditori che rappresentano il sessanta per cento dei crediti, corredati dall'attestazione.",
         "Ai sensi degli artt. 57 e 61 CCII la società deposita gli accordi a efficacia estesa sottoscritti dalle banche creditrici.",
         "La ricorrente allega la relazione di un professionista indipendente che attesta la veridicità dei dati."),
    ),
    "imp_piano_ristrutturazione_omologazione": (
        "Piano di ristrutturazione soggetto a omologazione", "atti", "crisi",
        ("Piano di ristrutturazione soggetto a omologazione", "Domanda di accesso al piano di ristrutturazione soggetto a omologazione",
         "Ricorso per l'omologazione del piano di ristrutturazione soggetto ad omologazione", "Piano di ristrutturazione soggetto ad omologa"),
        ("Beta S.p.A. propone un piano che suddivide i creditori in classi e prevede il voto unanime delle classi ai sensi dell'art. 64-bis CCII.",
         "Il piano ripartisce il valore generato fra le classi di creditori anche in deroga agli artt. 2740 e 2741 c.c.",
         "La debitrice chiede l'omologazione del piano approvato da tutte le classi."),
    ),
    "imp_piano_attestato_risanamento": (
        "Piano attestato di risanamento", "allegati", "parte",
        ("Piano attestato di risanamento", "Piano di risanamento", "Piano attestato di risanamento 2026-2028",
         "Piano di risanamento ex art. 56 CCII"),
        ("Il piano mira al risanamento dell'esposizione debitoria di Alfa S.r.l. ed è corredato dall'attestazione del professionista indipendente.",
         "Ai sensi dell'art. 56 CCII si indicano le azioni industriali e i tempi del riequilibrio finanziario.",
         "Il piano prevede la cessione di un ramo non strategico e la riduzione dell'indebitamento bancario, con attestazione allegata."),
    ),
    "imp_istanza_composizione_negoziata": (
        "Istanza di accesso alla composizione negoziata della crisi", "atti", "parte",
        ("Istanza di accesso alla composizione negoziata della crisi", "Istanza di nomina dell'esperto",
         "Istanza per la composizione negoziata", "Istanza di accesso alla composizione negoziata"),
        ("L'imprenditore Gamma S.r.l. chiede al segretario generale della camera di commercio la nomina dell'esperto tramite la piattaforma telematica nazionale.",
         "Ai sensi dell'art. 17 CCII si allegano il piano di risanamento e l'elenco dei creditori.",
         "La società si trova in squilibrio patrimoniale e chiede l'avvio della composizione negoziata con la nomina di un esperto indipendente."),
    ),
    "imp_ricorso_misure_protettive": (
        "Ricorso per la conferma delle misure protettive", "atti", "crisi",
        ("Ricorso per la conferma delle misure protettive", "Ricorso ex art. 19 CCII", "Istanza di applicazione di misure protettive",
         "Ricorso per la concessione delle misure protettive"),
        ("L'imprenditore, che ha chiesto la nomina dell'esperto, domanda la conferma delle misure protettive del patrimonio contro le azioni esecutive dei creditori.",
         "Ai sensi dell'art. 19 CCII la ricorrente chiede la conferma delle misure e l'adozione di provvedimenti cautelari.",
         "La società chiede che i creditori non possano acquisire diritti di prelazione durante le trattative condotte con l'esperto."),
    ),
    "imp_relazione_finale_esperto": (
        "Relazione finale dell'esperto (composizione negoziata)", "allegati", "parte",
        ("Relazione finale dell'esperto", "Relazione finale dell'esperto nella composizione negoziata",
         "Relazione finale dell'esperto indipendente", "Relazione finale dell'esperto - archiviazione"),
        ("L'esperto dà conto dell'esito delle trattative condotte nella composizione negoziata con i creditori bancari di Alfa S.r.l.",
         "Concluse le trattative senza accordo, l'esperto deposita la relazione finale sulla piattaforma ai sensi dell'art. 17 CCII.",
         "Le trattative si sono chiuse con un contratto con i creditori ai sensi dell'art. 23 CCII."),
    ),
    "imp_domanda_liquidazione_controllata": (
        "Domanda di liquidazione controllata", "atti", "crisi",
        ("Domanda di liquidazione controllata", "Ricorso per l'apertura della liquidazione controllata",
         "Ricorso per liquidazione controllata", "Istanza di liquidazione controllata del patrimonio"),
        ("Il debitore Mario Rossi, in stato di sovraindebitamento, chiede l'apertura della liquidazione controllata allegando la relazione dell'OCC.",
         "Ai sensi dell'art. 268 CCII la domanda è corredata dall'elenco dei creditori e dall'inventario dei beni.",
         "Il gestore della crisi ha verificato la completezza della documentazione depositata dal debitore."),
    ),
    "imp_sentenza_liquidazione_controllata": (
        "Sentenza di apertura della liquidazione controllata", "provvedimenti", "crisi",
        ("Sentenza di apertura della liquidazione controllata", "Sentenza dichiarativa della liquidazione controllata",
         "Sentenza di apertura liquidazione controllata", "Sentenza che dichiara aperta la liquidazione controllata"),
        ("Il Tribunale dichiara aperta la procedura di liquidazione controllata del patrimonio di Mario Rossi e nomina liquidatore il gestore della crisi.",
         "Ai sensi dell'art. 270 CCII si ordina la consegna dei beni al liquidatore e la trascrizione della sentenza.",
         "Il giudice nomina il liquidatore e assegna ai creditori il termine per le domande."),
    ),
    "imp_relazione_occ": (
        "Relazione particolareggiata dell'OCC", "allegati", "parte",
        ("Relazione particolareggiata dell'OCC", "Relazione dell'organismo di composizione della crisi",
         "Relazione particolareggiata del gestore della crisi", "Relazione OCC"),
        ("Il gestore della crisi riferisce sulle cause del sovraindebitamento di Mario Rossi e sulla diligenza impiegata nell'assumere le obbligazioni.",
         "Ai sensi dell'art. 68 CCII si valuta la completezza della documentazione e la convenienza del piano.",
         "L'organismo attesta che il debitore non ha determinato il sovraindebitamento con colpa grave, malafede o frode."),
    ),
    "imp_azione_revocatoria_concorsuale": (
        "Azione revocatoria concorsuale", "atti", "crisi",
        ("Atto di citazione per revocatoria fallimentare", "Azione revocatoria concorsuale", "Atto di citazione in revocatoria ex art. 166 CCII",
         "Azione revocatoria fallimentare"),
        ("Il curatore della liquidazione giudiziale di Alfa S.r.l. chiede la revoca dei pagamenti eseguiti a favore di Beta S.p.A. nei sei mesi anteriori.",
         "Ai sensi dell'art. 166 CCII il curatore chiede di dichiarare inefficace l'ipoteca iscritta dal convenuto, che conosceva lo stato di insolvenza.",
         "La procedura agisce per la revoca della vendita dell'immobile a prezzo vile concluso un anno prima dell'apertura della liquidazione giudiziale."),
    ),
    "imp_concordato_liquidazione_giudiziale": (
        "Proposta di concordato nella liquidazione giudiziale", "atti", "crisi",
        ("Proposta di concordato nella liquidazione giudiziale", "Proposta di concordato fallimentare",
         "Proposta di concordato nella liquidazione giudiziale di Alfa S.r.l.", "Proposta di concordato fallimentare con assuntore"),
        ("Il terzo proponente Gamma S.p.A. offre ai creditori chirografari il pagamento del trenta per cento entro sei mesi dall'omologazione.",
         "Ai sensi dell'art. 240 CCII la proposta suddivide i creditori in classi; il curatore esprimerà il proprio parere.",
         "L'assuntore si obbliga a pagare integralmente i creditori privilegiati e acquisisce l'attivo della procedura."),
    ),
    # ── Società e impresa ──
    "imp_atto_costitutivo": (
        "Atto costitutivo di società", "contratti", "banca",
        ("Atto costitutivo di società a responsabilità limitata", "Atto costitutivo", "Costituzione di società per azioni",
         "Atto costitutivo di s.r.l. semplificata"),
        ("I comparenti costituiscono Alfa S.r.l. con sede in Bari, capitale sociale di euro 10.000,00 e oggetto sociale la produzione di arredi.",
         "Ai sensi dell'art. 2463 c.c. si indica il capitale sociale sottoscritto e versato e la nomina dell'amministratore unico.",
         "La società ha per oggetto sociale il commercio di prodotti alimentari; il capitale sociale è di euro 50.000,00."),
    ),
    "imp_statuto_sociale": (
        "Statuto sociale", "contratti", "parte",
        ("Statuto sociale", "Statuto della società", "Statuto di Alfa S.r.l.", "Statuto"),
        ("Art. 1 - È costituita una società con la denominazione sociale Alfa S.r.l. Art. 2 - La società ha per oggetto sociale la consulenza informatica.",
         "Il capitale sociale è di euro 20.000,00 diviso in quote; le quote sono trasferibili con prelazione a favore dei soci.",
         "Titolo I - Denominazione sociale, sede, oggetto e durata. La società ha sede in Verona."),
    ),
    "imp_cessione_quote": (
        "Atto di cessione di quote sociali", "contratti", "banca",
        ("Atto di cessione di quote sociali", "Cessione di quote", "Atto di trasferimento di partecipazioni",
         "Compravendita di quote di s.r.l."),
        ("Il cedente Mario Rossi trasferisce al cessionario Luca Bianchi la quota pari al 30% del capitale di Alfa S.r.l. per il prezzo di euro 15.000,00.",
         "Ai sensi dell'art. 2470 c.c. l'atto sarà depositato per l'iscrizione nel registro delle imprese entro trenta giorni.",
         "Il cessionario subentra nei diritti sociali; il cedente garantisce la piena titolarità della quota."),
    ),
    "imp_bilancio_esercizio": (
        "Bilancio d'esercizio", "allegati", "parte",
        ("Bilancio d'esercizio al 31/12/2025", "Bilancio di esercizio", "Bilancio abbreviato", "Bilancio consolidato al 31/12/2025"),
        ("Stato patrimoniale: totale attivo euro 1.250.000,00; patrimonio netto euro 310.000,00. Conto economico: utile d'esercizio euro 42.000,00.",
         "Nota integrativa redatta ai sensi dell'art. 2423 c.c.; criteri di valutazione delle immobilizzazioni.",
         "Il conto economico chiude con una perdita di euro 85.000,00 coperta con riserve disponibili."),
    ),
    "imp_relazione_sindaci_revisore": (
        "Relazione del collegio sindacale o del revisore", "allegati", "parte",
        ("Relazione del collegio sindacale", "Relazione del revisore legale", "Relazione unitaria del collegio sindacale",
         "Relazione della società di revisione"),
        ("Il collegio sindacale riferisce all'assemblea sui risultati dell'esercizio e propone l'approvazione del bilancio al 31/12/2025.",
         "Ai sensi dell'art. 2429 c.c. il sindaco unico esprime parere favorevole sulla proposta di destinazione dell'utile.",
         "Il revisore ha svolto la revisione contabile del bilancio d'esercizio e rilascia un giudizio senza rilievi."),
    ),
    "imp_denuncia_gravi_irregolarita": (
        "Denuncia di gravi irregolarità (art. 2409 c.c.)", "atti", "impresa",
        ("Denuncia di gravi irregolarità", "Ricorso per gravi irregolarità nella gestione", "Ricorso ex art. 2409 c.c.",
         "Denunzia di gravi irregolarità"),
        ("Il socio Mario Rossi, titolare del 15% del capitale, denuncia che gli amministratori hanno distratto risorse sociali a favore di una società collegata.",
         "Ai sensi dell'art. 2409 c.c. il collegio sindacale chiede l'ispezione dell'amministrazione di Beta S.p.A.",
         "I ricorrenti espongono gravi irregolarità contabili e chiedono la revoca dell'amministratore unico e la nomina di un amministratore giudiziario."),
    ),
    "imp_nomina_liquidatore_societa": (
        "Ricorso per la nomina del liquidatore della società", "atti", "impresa",
        ("Ricorso per la nomina del liquidatore della società", "Ricorso per la nomina dei liquidatori",
         "Ricorso ex art. 2487 c.c.", "Ricorso per l'accertamento della causa di scioglimento"),
        ("Il socio di Alfa S.r.l. espone che l'assemblea non ha nominato i liquidatori nonostante la causa di scioglimento per impossibilità di funzionamento.",
         "Ai sensi dell'art. 2487 c.c. si chiede al Tribunale di nominare il liquidatore della società.",
         "Verificatasi la riduzione del capitale al di sotto del minimo, si chiede di accertare lo scioglimento ai sensi dell'art. 2485 c.c."),
    ),
    "imp_patto_parasociale": (
        "Patto parasociale", "contratti", "parte",
        ("Patto parasociale", "Patti parasociali", "Accordo parasociale", "Sindacato di voto"),
        ("I soci di Beta S.p.A. si impegnano a votare congiuntamente nelle assemblee per la nomina del consiglio di amministrazione.",
         "Ai sensi dell'art. 2341-bis c.c. il patto ha durata di cinque anni e vincola il trasferimento delle azioni.",
         "Le parti, titolari delle quote di Alfa S.r.l., concordano un diritto di prelazione e un obbligo di consultazione prima del voto."),
    ),
    "imp_fusione_scissione": (
        "Progetto di fusione o scissione", "contratti", "parte",
        ("Progetto di fusione per incorporazione", "Progetto comune di fusione", "Progetto di scissione parziale", "Atto di fusione"),
        ("La società incorporante Alfa S.p.A. incorpora Beta S.r.l.; il rapporto di concambio è fissato in una azione ogni due quote.",
         "Ai sensi dell'art. 2501-ter c.c. si indicano le società partecipanti e la data di efficacia della fusione.",
         "Alla società beneficiaria Gamma S.r.l. è assegnato il ramo immobiliare secondo l'art. 2506-bis c.c."),
    ),
    "imp_trasferimento_azienda": (
        "Atto di trasferimento d'azienda", "contratti", "banca",
        ("Atto di trasferimento d'azienda", "Contratto di affitto di ramo d'azienda", "Atto di cessione d'azienda",
         "Contratto di cessione dell'azienda"),
        ("Il cedente Alfa S.r.l. trasferisce al cessionario Beta S.r.l. l'azienda di ristorazione sita in Bari, comprensiva di avviamento e attrezzature.",
         "Ai sensi dell'art. 2556 c.c. l'atto è redatto in forma pubblica e sarà iscritto nel registro delle imprese.",
         "L'affittuario corrisponderà un canone mensile di euro 3.000,00 e conserverà l'efficienza del ramo d'azienda."),
    ),
    "imp_contratto_franchising": (
        "Contratto di affiliazione commerciale (franchising)", "contratti", "parte",
        ("Contratto di affiliazione commerciale", "Contratto di franchising", "Contratto di affiliazione commerciale (franchising)",
         "Contratto di franchising per punto vendita"),
        ("L'affiliante Alfa S.p.A. concede all'affiliato Beta S.r.l. l'uso del marchio e del know-how verso un diritto di ingresso e royalties mensili.",
         "Ai sensi della L. 129/2004 il franchisor consegna il contratto trenta giorni prima della firma.",
         "L'affiliato si impegna a rispettare il manuale operativo e a versare royalties pari al 5% del fatturato."),
    ),
    # ── Proprietà industriale e intellettuale ──
    "imp_domanda_registrazione_marchio": (
        "Domanda di registrazione di marchio", "allegati", "ufficio_pi",
        ("Domanda di registrazione di marchio", "Domanda di registrazione del marchio d'impresa", "Domanda di marchio",
         "Domanda di registrazione per marchio figurativo"),
        ("Richiedente Alfa S.r.l.; marchio figurativo con elemento verbale ALFASOLE; classi 25 e 35 della classificazione di Nizza.",
         "Il richiedente deposita la domanda presso l'UIBM e indica i prodotti contraddistinti dal marchio.",
         "Ai sensi dell'art. 156 c.p.i. si allegano l'esemplare del marchio e l'elenco dei prodotti e servizi."),
    ),
    "imp_domanda_brevetto": (
        "Domanda di brevetto", "allegati", "ufficio_pi",
        ("Domanda di brevetto per invenzione industriale", "Domanda di brevetto", "Domanda di brevetto per modello di utilità",
         "Domanda di registrazione di modello di utilità"),
        ("Inventore: ing. Carlo Neri. Titolo dell'invenzione: dispositivo di chiusura per contenitori; descrizione, rivendicazioni e disegni allegati.",
         "Ai sensi dell'art. 160 c.p.i. la domanda contiene la descrizione e le rivendicazioni.",
         "Si chiede la concessione del brevetto per l'invenzione relativa a un sistema di filtraggio; rivendicazioni da 1 a 12."),
    ),
    "imp_attestato_titolo_proprieta_industriale": (
        "Attestato di brevetto o di registrazione di marchio", "allegati", "ufficio_pi",
        ("Attestato di brevetto per invenzione industriale", "Attestato di registrazione di marchio", "Certificato di registrazione del marchio",
         "Attestato di concessione di brevetto"),
        ("Ufficio Italiano Brevetti e Marchi. Titolare: Alfa S.r.l. Data di deposito 10/03/2024. Numero di registrazione 302024000012345.",
         "L'UIBM attesta la concessione del titolo al titolare indicato, con effetto dalla data di deposito.",
         "Titolare del diritto: Beta S.p.A.; durata vent'anni dalla data di deposito della domanda."),
    ),
    "imp_opposizione_registrazione_marchio": (
        "Opposizione alla registrazione di marchio", "atti", "ufficio_pi",
        ("Opposizione alla registrazione di marchio", "Atto di opposizione alla domanda di registrazione del marchio",
         "Opposizione ex art. 176 c.p.i.", "Opposizione al marchio"),
        ("L'opponente Alfa S.r.l., titolare del marchio anteriore ALFASOLE, si oppone alla registrazione del segno ALFASOLI per prodotti identici.",
         "Ai sensi dell'art. 176 c.p.i. si chiede all'UIBM di respingere la domanda per rischio di confusione.",
         "L'opposizione è fondata sull'anteriorità di un marchio dell'Unione europea registrato presso l'EUIPO."),
    ),
    "imp_diffida_contraffazione": (
        "Diffida per contraffazione", "comunicazioni", "studio",
        ("Diffida per contraffazione", "Diffida per violazione del marchio", "Diffida alla cessazione della contraffazione",
         "Diffida per violazione dei diritti d'autore"),
        ("In nome di Alfa S.r.l., titolare del marchio registrato ALFASOLE, diffido Beta S.r.l. dal commercializzare prodotti contraffatti.",
         "La Vostra condotta costituisce contraffazione del brevetto n. 123456 della mia assistita; Vi invito a cessare entro dieci giorni.",
         "La pubblicazione delle fotografie viola il diritto d'autore del mio assistito tutelato dalla L. 633/1941."),
    ),
    "imp_ricorso_descrizione_sequestro": (
        "Ricorso per descrizione e sequestro (artt. 128-129 c.p.i.)", "atti", "impresa",
        ("Ricorso per descrizione e sequestro ex artt. 128-129 c.p.i.", "Ricorso per la descrizione", "Ricorso cautelare per sequestro di prodotti in contraffazione di marchio",
         "Ricorso per descrizione e sequestro (artt. 128-129 c.p.i.)"),
        ("Alfa S.r.l. chiede la descrizione e il sequestro dei prodotti che contraffanno il brevetto n. 123456 presso lo stabilimento di Beta S.r.l.",
         "Ai sensi degli artt. 128 e 129 c.p.i. si chiede di acquisire la prova della contraffazione del marchio.",
         "La ricorrente espone che i prodotti esposti in fiera riproducono il proprio modello registrato e ne chiede il sequestro."),
    ),
    "imp_ricorso_inibitoria_proprieta_industriale": (
        "Ricorso per inibitoria in materia di proprietà industriale (art. 131 c.p.i.)", "atti", "impresa",
        ("Ricorso per inibitoria ex art. 131 c.p.i.", "Ricorso cautelare per inibitoria in materia di marchi",
         "Ricorso ex art. 131 c.p.i.", "Ricorso per l'inibitoria della contraffazione di brevetto"),
        ("Alfa S.r.l. chiede l'inibitoria della fabbricazione e del commercio dei prodotti che contraffanno il proprio marchio, con penale per ogni violazione.",
         "Ai sensi dell'art. 131 c.p.i. la ricorrente chiede di inibire l'uso del segno sul sito internet della resistente.",
         "La ricorrente chiede di ordinare la cessazione della vendita dei dispositivi che riproducono il brevetto."),
    ),
    "imp_azione_contraffazione": (
        "Azione di contraffazione", "atti", "impresa",
        ("Atto di citazione per contraffazione di marchio", "Azione di contraffazione", "Atto di citazione in materia di contraffazione di brevetto",
         "Azione per contraffazione"),
        ("Alfa S.r.l. cita Beta S.r.l. davanti alla sezione specializzata in materia di impresa per sentir accertare la contraffazione del marchio ALFASOLE.",
         "Ai sensi degli artt. 124 e 125 c.p.i. si chiedono la distruzione dei prodotti e il risarcimento del danno.",
         "L'attrice chiede l'accertamento della contraffazione del brevetto e la retroversione degli utili."),
    ),
    "imp_azione_nullita_titolo": (
        "Azione di nullità o decadenza del marchio o brevetto", "atti", "impresa",
        ("Atto di citazione per nullità del marchio", "Azione di nullità o decadenza del marchio", "Azione di decadenza del marchio per non uso",
         "Atto di citazione per la nullità del brevetto"),
        ("Gamma S.r.l. chiede di dichiarare la nullità del marchio registrato da Beta S.r.l. per difetto di novità rispetto all'anteriorità ALFASOLE.",
         "Ai sensi dell'art. 122 c.p.i. si chiede l'annotazione della sentenza nel registro dell'UIBM.",
         "Il marchio non è stato usato per cinque anni dalla registrazione e ne va dichiarata la decadenza."),
    ),
    "imp_licenza_proprieta_industriale": (
        "Contratto di licenza di marchio o brevetto", "contratti", "parte",
        ("Contratto di licenza di marchio", "Contratto di licenza d'uso del brevetto", "Contratto di licenza di know-how",
         "Contratto di licenza su brevetti"),
        ("Il licenziante Alfa S.r.l. concede al licenziatario Beta S.r.l. la licenza non esclusiva del marchio ALFASOLE per l'Italia, verso royalties del 4%.",
         "Ai sensi dell'art. 23 c.p.i. la licenza non deve trarre in inganno il pubblico sulla qualità dei prodotti.",
         "Il licenziatario si obbliga a pagare royalties trimestrali e a rispettare gli standard qualitativi."),
    ),
    "imp_contratto_edizione": (
        "Contratto di edizione o di cessione dei diritti d'autore", "contratti", "parte",
        ("Contratto di edizione", "Contratto di cessione dei diritti d'autore", "Contratto di edizione per opera letteraria",
         "Contratto di cessione dei diritti di utilizzazione economica"),
        ("L'autore Mario Rossi concede all'editore Alfa Editrice S.r.l. il diritto di pubblicare per le stampe il romanzo inedito.",
         "Ai sensi dell'art. 118 L. 633/1941 la concessione ha durata di vent'anni.",
         "L'autore cede i diritti di utilizzazione economica della fotografia per la campagna pubblicitaria."),
    ),
    "imp_azione_diritto_autore": (
        "Azione per violazione del diritto d'autore", "atti", "impresa",
        ("Atto di citazione per violazione del diritto d'autore", "Azione per plagio", "Azione per violazione dei diritti d'autore",
         "Ricorso per violazione del diritto d'autore"),
        ("L'autore Mario Rossi lamenta il plagio della propria opera musicale e chiede l'inibitoria e il risarcimento ai sensi della L. 633/1941.",
         "Ai sensi dell'art. 156 L. 633/1941 l'attore chiede l'inibitoria della diffusione del software copiato.",
         "La convenuta ha riprodotto senza autorizzazione le fotografie dell'autore sul proprio catalogo."),
    ),
    # ── Banca e finanza ──
    "imp_contratto_conto_corrente": (
        "Contratto di conto corrente bancario", "contratti", "banca",
        ("Contratto di conto corrente bancario", "Contratto di conto corrente", "Contratto di apertura di conto corrente ordinario",
         "Contratto di conto corrente di corrispondenza"),
        ("La Banca e il correntista Mario Rossi convengono l'apertura del rapporto alle condizioni economiche del documento di sintesi.",
         "Ai sensi dell'art. 117 TUB il contratto è redatto per iscritto e una copia è consegnata al cliente.",
         "Il tasso debitore annuo nominale è pari al 9%; la banca addebita le competenze al correntista con periodicità annuale."),
    ),
    "imp_contratto_mutuo": (
        "Contratto di mutuo", "contratti", "banca",
        ("Contratto di mutuo fondiario", "Atto di mutuo", "Mutuo ipotecario", "Contratto di mutuo chirografario"),
        ("La Banca mutuante concede ai mutuatari Mario Rossi e Anna Neri la somma di euro 180.000,00 con piano di ammortamento in 300 rate mensili.",
         "Ai sensi dell'art. 1813 c.c. la parte mutuataria si obbliga a restituire la somma con gli interessi.",
         "A garanzia del mutuo i mutuatari concedono ipoteca sull'immobile in Torino; ammortamento alla francese."),
    ),
    "imp_contratto_fideiussione": (
        "Contratto di fideiussione", "contratti", "banca",
        ("Contratto di fideiussione", "Fideiussione omnibus", "Atto di fideiussione specifica", "Garanzia fideiussoria"),
        ("Il fideiussore Luca Bianchi garantisce alla Banca l'adempimento di ogni obbligazione del debitore principale Alfa S.r.l. fino a euro 200.000,00.",
         "Ai sensi dell'art. 1936 c.c. il fideiussore si obbliga personalmente verso il creditore.",
         "Il fideiussore rinuncia al beneficio della preventiva escussione del debitore principale previsto dall'art. 1944 c.c."),
    ),
    "imp_estratto_conto_certificato": (
        "Estratto conto certificato (art. 50 TUB)", "allegati", "banca",
        ("Estratto conto certificato ai sensi dell'art. 50 TUB", "Estratto di saldaconto ex art. 50 D.Lgs. 385/1993", "Estratto conto certificato",
         "Saldaconto certificato"),
        ("Il dirigente della Banca certifica che il saldo debitore del conto n. 000123 intestato ad Alfa S.r.l. è di euro 54.320,00.",
         "Si certifica, ai sensi dell'art. 50 del D.Lgs. 385/1993, la conformità del credito alle scritture contabili.",
         "Certificazione rilasciata dal funzionario delegato per il ricorso per decreto ingiuntivo."),
    ),
    "imp_ricorso_abf": (
        "Ricorso all'Arbitro Bancario Finanziario (ABF)", "atti", "studio",
        ("Ricorso all'Arbitro Bancario Finanziario", "Ricorso ABF", "Ricorso all'Arbitro Bancario Finanziario (ABF) - Collegio di Milano",
         "Ricorso al Collegio di Roma dell'Arbitro Bancario Finanziario"),
        ("Il ricorrente Mario Rossi chiede all'Arbitro Bancario Finanziario il rimborso delle commissioni non dovute addebitate dall'intermediario.",
         "Esperito il reclamo senza esito, il cliente propone ricorso all'ABF ai sensi dell'art. 128-bis TUB.",
         "Il ricorrente lamenta un'operazione di pagamento non autorizzata e chiede la restituzione da parte dell'intermediario."),
    ),
    "imp_decisione_abf": (
        "Decisione dell'Arbitro Bancario Finanziario", "provvedimenti", "studio",
        ("Decisione dell'Arbitro Bancario Finanziario", "Decisione del Collegio di Milano dell'Arbitro Bancario Finanziario",
         "Decisione ABF", "Decisione del collegio dell'ABF"),
        ("Il Collegio, esaminato il ricorso, dichiara l'intermediario tenuto a restituire al ricorrente la somma di euro 1.200,00.",
         "Il Collegio di Napoli respinge il ricorso ritenendo corretto l'addebito dell'intermediario.",
         "Il Collegio accoglie parzialmente il ricorso e dispone il rimborso del contributo al ricorrente."),
    ),
    "imp_reclamo_intermediario": (
        "Reclamo all'intermediario bancario o finanziario", "comunicazioni", "studio",
        ("Reclamo all'intermediario", "Reclamo alla banca", "Reclamo all'ufficio reclami", "Reclamo ex art. 128-bis TUB"),
        ("Il sottoscritto, cliente della Banca Alfa, contesta l'addebito di interessi di mora sul conto e chiede il rimborso entro sessanta giorni.",
         "Si presenta reclamo all'intermediario per la mancata estinzione anticipata del finanziamento.",
         "Contesto le modalità di collocamento delle obbligazioni proposte dalla banca e chiedo il ristoro della perdita."),
    ),
    "imp_ricorso_acf": (
        "Ricorso all'Arbitro per le Controversie Finanziarie (ACF)", "atti", "studio",
        ("Ricorso all'Arbitro per le Controversie Finanziarie", "Ricorso ACF", "Ricorso all'Arbitro per le Controversie Finanziarie (ACF)",
         "Ricorso presso l'Arbitro per le Controversie Finanziarie"),
        ("Il ricorrente lamenta la violazione degli obblighi di informazione dell'intermediario nella vendita di azioni non quotate e chiede il risarcimento.",
         "Il ricorso è presentato all'ACF istituito presso la Consob dopo il reclamo rimasto senza risposta.",
         "Il risparmiatore contesta l'inadeguatezza delle operazioni in strumenti derivati raccomandate dall'intermediario."),
    ),
    "imp_decisione_acf": (
        "Decisione dell'Arbitro per le Controversie Finanziarie", "provvedimenti", "studio",
        ("Decisione dell'Arbitro per le Controversie Finanziarie", "Decisione ACF", "Decisione del collegio dell'Arbitro per le Controversie Finanziarie",
         "Decisione dell'ACF n. 1234"),
        ("Il Collegio, accertata la violazione degli obblighi di condotta, condanna l'intermediario a risarcire al ricorrente euro 15.000,00.",
         "Il Collegio dichiara il ricorso irricevibile per decorso del termine annuale dal reclamo.",
         "Il Collegio respinge il ricorso: l'intermediario ha fornito al cliente le informazioni dovute."),
    ),
    "imp_contratto_servizi_investimento": (
        "Contratto quadro per servizi di investimento", "contratti", "banca",
        ("Contratto quadro per servizi di investimento", "Contratto quadro per la prestazione dei servizi di investimento",
         "Contratto di gestione di portafogli", "Contratto di consulenza in materia di investimenti"),
        ("La Banca e il cliente disciplinano la prestazione dei servizi di investimento e la negoziazione di strumenti finanziari secondo la disciplina MiFID.",
         "Ai sensi dell'art. 23 D.Lgs. 58/1998 il contratto è redatto per iscritto.",
         "Il gestore investe il patrimonio del cliente in strumenti finanziari secondo il profilo di rischio prudente."),
    ),
    "imp_contratto_credito_consumatori": (
        "Contratto di credito ai consumatori", "contratti", "banca",
        ("Contratto di credito ai consumatori", "Contratto di prestito personale", "Contratto di finanziamento finalizzato",
         "Contratto di credito al consumo"),
        ("Il finanziatore concede al consumatore Mario Rossi euro 12.000,00 rimborsabili in 48 rate; TAN 7,5%, TAEG 8,9%.",
         "Ai sensi dell'art. 125-bis TUB il contratto indica il TAEG e le condizioni di recesso.",
         "Il finanziamento è destinato all'acquisto di un'autovettura; il finanziatore versa l'importo al venditore."),
    ),
    "imp_modulo_secci": (
        "Modulo SECCI (informazioni europee di base sul credito ai consumatori)", "allegati", "banca",
        ("Modulo SECCI", "Informazioni europee di base sul credito ai consumatori", "SECCI - Informazioni europee di base sul credito ai consumatori",
         "Modulo SECCI prestito personale"),
        ("Finanziatore: Gamma Finanziaria S.p.A. Importo totale del credito euro 10.000,00. TAN fisso 6,9%. TAEG 8,1%.",
         "Ai sensi dell'art. 124 TUB il modulo è consegnato prima della conclusione del contratto.",
         "Durata del credito 60 mesi; TAEG comprensivo delle spese di istruttoria."),
    ),
    "imp_contratto_cessione_quinto": (
        "Contratto di cessione del quinto", "contratti", "banca",
        ("Contratto di cessione del quinto dello stipendio", "Contratto di prestito con cessione del quinto della pensione",
         "Contratto di cessione del quinto", "Delegazione di pagamento"),
        ("Il cedente, dipendente di Alfa S.p.A., cede la quota pari a un quinto dello stipendio mensile per 120 mesi a garanzia del prestito.",
         "Ai sensi del D.P.R. 180/1950 l'ente pensionistico tratterrà la rata sulla pensione.",
         "Il datore di lavoro verserà mensilmente al finanziatore la quota trattenuta sullo stipendio."),
    ),
    "imp_contratto_leasing": (
        "Contratto di leasing finanziario", "contratti", "banca",
        ("Contratto di leasing finanziario", "Contratto di locazione finanziaria", "Contratto di leasing immobiliare",
         "Contratto di leasing strumentale"),
        ("Il concedente acquista il macchinario indicato dall'utilizzatore Alfa S.r.l. e lo concede in godimento per 60 canoni mensili, con opzione di riscatto finale.",
         "Ai sensi della L. 124/2017 in caso di risoluzione il concedente restituisce all'utilizzatore quanto ricavato dalla vendita del bene.",
         "L'utilizzatore paga i canoni e alla scadenza può esercitare il riscatto dell'immobile."),
    ),
    # ── Assicurazioni ──
    "imp_polizza_assicurazione": (
        "Polizza di assicurazione", "contratti", "assicurazione",
        ("Polizza di assicurazione", "Polizza assicurativa responsabilità civile professionale", "Contratto di assicurazione sulla vita",
         "Condizioni generali di assicurazione"),
        ("Contraente: Alfa S.r.l. Assicurato: il contraente. Premio annuo lordo euro 1.250,00. Massimale per sinistro euro 1.000.000,00.",
         "Ai sensi dell'art. 1882 c.c. l'assicuratore si obbliga, verso pagamento del premio, a rivalere l'assicurato del danno.",
         "Il contraente versa il premio unico; la prestazione è dovuta ai beneficiari in caso di decesso."),
    ),
    "imp_denuncia_sinistro_assicuratore": (
        "Denuncia di sinistro all'assicuratore", "comunicazioni", "assicurazione",
        ("Denuncia di sinistro all'assicuratore", "Denuncia di sinistro", "Denuncia del sinistro alla compagnia", "Avviso di sinistro"),
        ("Il sottoscritto, assicurato con polizza n. 123456, denuncia il danno da infiltrazione d'acqua verificatosi il 03/03/2026.",
         "Ai sensi dell'art. 1913 c.c. si dà avviso del sinistro entro tre giorni dal fatto.",
         "Si comunica alla compagnia il furto dell'autovettura assicurata avvenuto a Bari il 10/02/2026."),
    ),
    "imp_reclamo_ivass": (
        "Reclamo all'IVASS", "comunicazioni", "assicurazione",
        ("Reclamo all'IVASS", "Reclamo IVASS", "Reclamo all'Istituto per la vigilanza sulle assicurazioni", "Reclamo all'IVASS - ritardo nella liquidazione"),
        ("Il sottoscritto si rivolge all'IVASS perché l'impresa di assicurazione non ha risposto al reclamo nel termine di quarantacinque giorni.",
         "Si lamenta il comportamento dell'intermediario assicurativo che ha collocato una polizza non adeguata.",
         "Si allega copia del reclamo presentato all'impresa di assicurazione e della polizza."),
    ),
    "imp_reclamo_impresa_assicurazione": (
        "Reclamo all'impresa di assicurazione", "comunicazioni", "studio",
        ("Reclamo all'impresa di assicurazione", "Reclamo alla compagnia di assicurazione", "Reclamo all'assicuratore",
         "Reclamo alla compagnia"),
        ("L'assicurato con polizza n. 987654 contesta il diniego di indennizzo del sinistro e chiede il riesame della pratica.",
         "Si chiede risposta entro 45 giorni sul ritardo nella liquidazione del danno all'abitazione assicurata.",
         "Il contraente contesta l'aumento del premio e chiede la correzione della polizza."),
    ),
    "imp_ricorso_arbitro_assicurativo": (
        "Ricorso all'Arbitro assicurativo", "atti", "studio",
        ("Ricorso all'Arbitro assicurativo", "Ricorso AAS", "Ricorso all'Arbitro assicurativo - polizza vita", "Ricorso Arbitro assicurativo"),
        ("Il ricorrente chiede all'Arbitro assicurativo istituito presso l'IVASS di accertare il diritto all'indennizzo negato dall'impresa di assicurazione.",
         "Ai sensi dell'art. 187.1 CAP il contraente contesta il mancato pagamento della prestazione prevista dalla polizza.",
         "L'assicurato lamenta che l'impresa di assicurazione non ha liquidato la rendita contrattuale."),
    ),
    # ── Consumatori e concorrenza ──
    "imp_recesso_consumatore": (
        "Comunicazione di recesso del consumatore", "comunicazioni", "studio",
        ("Comunicazione di recesso del consumatore", "Modulo di recesso", "Dichiarazione di esercizio del diritto di recesso",
         "Comunicazione di recesso dal contratto a distanza"),
        ("Il consumatore Mario Rossi comunica di recedere dal contratto di acquisto online del 02/03/2026 entro quattordici giorni ai sensi del Codice del consumo.",
         "Il contratto è stato concluso fuori dei locali commerciali; si esercita il recesso e si chiede il rimborso.",
         "Ai sensi del D.Lgs. 206/2005 il consumatore restituisce il bene e chiede il rimborso del prezzo pagato."),
    ),
    "imp_garanzia_legale_conformita": (
        "Richiesta di rimedi per difetto di conformità (garanzia legale)", "comunicazioni", "studio",
        ("Richiesta di intervento in garanzia", "Richiesta di riparazione o sostituzione", "Attivazione della garanzia legale di conformità",
         "Richiesta di rimedi per difetto di conformità"),
        ("Il frigorifero acquistato il 10/01/2026 presenta un difetto di conformità; si chiede al venditore la riparazione gratuita nella garanzia legale.",
         "Ai sensi dell'art. 135-bis del Codice del consumo si chiede la sostituzione del telefono difettoso.",
         "In mancanza di ripristino della conformità entro un termine congruo si chiederà la riduzione del prezzo."),
    ),
    "imp_adesione_azione_classe": (
        "Domanda di adesione all'azione di classe", "atti", "studio",
        ("Domanda di adesione all'azione di classe", "Atto di adesione all'azione di classe", "Adesione all'azione di classe",
         "Domanda di adesione azione di classe"),
        ("L'aderente Mario Rossi chiede di aderire all'azione di classe promossa contro Alfa S.p.A. tramite l'area del portale dei servizi telematici.",
         "Ai sensi dell'art. 840-septies c.p.c. l'aderente indica i fatti costitutivi del proprio diritto individuale omogeneo.",
         "L'aderente allega la documentazione dell'acquisto e nomina il rappresentante comune."),
    ),
    "imp_ricorso_azione_classe": (
        "Ricorso per azione di classe", "atti", "impresa",
        ("Ricorso per azione di classe", "Azione di classe", "Ricorso introduttivo dell'azione di classe", "Class action"),
        ("L'associazione Alfa agisce a tutela dei diritti individuali omogenei dei consumatori acquirenti di un'autovettura con emissioni falsate.",
         "Ai sensi dell'art. 840-bis c.p.c. il ricorrente chiede l'accertamento della responsabilità dell'impresa verso la classe.",
         "Il ricorrente chiede la dichiarazione di ammissibilità dell'azione e la fissazione del termine per le adesioni della classe."),
    ),
    "imp_azione_inibitoria_collettiva": (
        "Azione inibitoria collettiva", "atti", "impresa",
        ("Azione inibitoria collettiva", "Ricorso per azione inibitoria collettiva", "Ricorso per l'inibitoria collettiva",
         "Atto per azione inibitoria collettiva"),
        ("L'associazione dei consumatori chiede l'ordine di cessazione delle condotte omissive della compagnia telefonica a danno di una pluralità di utenti.",
         "Ai sensi dell'art. 840-sexiesdecies c.p.c. si chiede di inibire la reiterazione della condotta.",
         "La ricorrente chiede la pubblicazione del provvedimento inibitorio sul sito della resistente."),
    ),
    "imp_segnalazione_pratica_commerciale_scorretta": (
        "Segnalazione di pratica commerciale scorretta", "comunicazioni", "autorita",
        ("Segnalazione di pratica commerciale scorretta", "Segnalazione all'AGCM per pratica commerciale scorretta",
         "Denuncia di pratica commerciale scorretta", "Esposto per pratiche commerciali scorrette"),
        ("Si segnala che Alfa S.p.A. pubblicizza come gratuito un servizio poi addebitato, integrando una pratica ingannevole ai sensi del Codice del consumo.",
         "Ai sensi dell'art. 27 D.Lgs. 206/2005 si chiede all'Autorità di inibire la pratica aggressiva di telemarketing.",
         "La società omette informazioni rilevanti sul prezzo finale: la pratica è scorretta."),
    ),
    "imp_segnalazione_agcm": (
        "Segnalazione all'Autorità garante della concorrenza e del mercato", "comunicazioni", "autorita",
        ("Segnalazione all'Autorità garante della concorrenza e del mercato", "Denuncia all'AGCM", "Esposto all'Autorità garante della concorrenza e del mercato",
         "Denuncia di abuso di posizione dominante"),
        ("Si segnala un'intesa restrittiva della concorrenza fra tre distributori di carburante della provincia di Bari, che applicano prezzi identici.",
         "Beta S.p.A. pone in essere un abuso di posizione dominante rifiutando l'accesso alla propria rete, in violazione della L. 287/1990.",
         "Si chiede l'avvio dell'istruttoria per la ripartizione concordata delle gare pubbliche, lesiva della concorrenza."),
    ),
    "imp_provvedimento_agcm": (
        "Provvedimento dell'Autorità garante della concorrenza e del mercato", "provvedimenti", "parte",
        ("L'Autorità garante della concorrenza e del mercato", "Provvedimento dell'Autorità garante della concorrenza e del mercato",
         "Provvedimento n. 31234 AGCM", "Provvedimento AGCM"),
        ("Nella sua adunanza del 10 marzo 2026; vista la legge 10 ottobre 1990, n. 287; DELIBERA di irrogare ad Alfa S.p.A. una sanzione amministrativa pecuniaria.",
         "L'Autorità diffida la società dal reiterare la pratica commerciale accertata.",
         "Nella adunanza del 2 febbraio 2026 l'Autorità delibera l'avvio dell'istruttoria nei confronti di Beta S.r.l."),
    ),
    "imp_proposta_impegni_agcm": (
        "Proposta di impegni all'AGCM", "comunicazioni", "autorita",
        ("Proposta di impegni all'AGCM", "Formulario di presentazione degli impegni", "Proposta di impegni ex art. 14-ter L. 287/1990",
         "Presentazione di impegni"),
        ("Alfa S.p.A. presenta all'Autorità gli impegni volti a far venir meno i profili anticoncorrenziali oggetto dell'istruttoria.",
         "Ai sensi dell'art. 14-ter la società si impegna a modificare le clausole di esclusiva.",
         "La società propone impegni per chiudere il procedimento senza accertamento dell'infrazione da parte dell'AGCM."),
    ),
    "imp_risarcimento_danno_antitrust": (
        "Azione di risarcimento del danno antitrust", "atti", "impresa",
        ("Azione di risarcimento del danno antitrust", "Atto di citazione per il risarcimento del danno da intesa",
         "Atto di citazione per risarcimento del danno da cartello", "Azione per il risarcimento del danno da violazione del diritto della concorrenza"),
        ("Alfa S.r.l. chiede il risarcimento del sovrapprezzo pagato a causa del cartello accertato dall'AGCM fra i produttori di imballaggi, ai sensi del D.Lgs. 3/2017.",
         "L'attrice agisce per il danno antitrust derivante dall'abuso accertato con decisione definitiva.",
         "La convenuta ha partecipato a un'intesa restrittiva della concorrenza sui prezzi praticati agli acquirenti."),
    ),
    "imp_esibizione_prove_antitrust": (
        "Istanza di esibizione delle prove in materia antitrust", "atti", "impresa",
        ("Istanza di esibizione delle prove in materia antitrust", "Istanza di esibizione ex art. 3 D.Lgs. 3/2017",
         "Istanza di ordine di esibizione delle prove nel giudizio antitrust", "Istanza di esibizione delle prove nell'azione di risarcimento antitrust"),
        ("L'attrice chiede al giudice di ordinare alla convenuta l'esibizione dei documenti relativi agli scambi di informazioni sui prezzi, ai sensi del D.Lgs. 3/2017.",
         "Si chiede l'esibizione delle prove rilevanti in possesso della convenuta per quantificare il danno antitrust.",
         "La richiesta riguarda categorie di prove circoscritte e proporzionate, nel rispetto della concorrenza e della riservatezza."),
    ),
}


def _forma(titolo: str, i: int, sezione: str) -> str:
    forma = (titolo.upper(), titolo, titolo.upper(), titolo[:1].upper() + titolo[1:].lower(), titolo)[i % 5]
    if sezione == "comunicazioni" and i % 4 == 3:
        return f"Oggetto: {forma}"
    return forma


def _documento(regola: str, i: int) -> str:
    _, sezione, uffici, titoli, corpi = _SPEC[regola]
    righe = []
    elenco = _UFFICI[uffici]
    if i % 6 != 5:
        righe.append(elenco[(i + len(regola)) % len(elenco)])
    titolo = titoli[(i + i // len(titoli)) % len(titoli)] if i else titoli[0]
    righe.append(_forma(titolo, i, sezione) if i else titolo.upper())
    if i % 2 == 1:
        righe.append(_NUMERI[(i // 2) % len(_NUMERI)].format(n=100 + 37 * i + len(regola)))
    corpo = corpi[i % len(corpi)]
    if i % 3 == 2:
        corpo = f"{corpo} {_AGGIUNTE[(i // 3) % len(_AGGIUNTE)]}"
    righe.append(corpo)
    return "\n".join(righe)


# regola -> (testo, etichetta attesa, sezione attesa)
CAMPIONI: dict[str, tuple[str, str, str]] = {
    regola: (_documento(regola, 0), etichetta, sezione) for regola, (etichetta, sezione, *_resto) in _SPEC.items()
}

# regola -> dieci testi diversi, tutti con l'etichetta e la sezione del campione
VARIANTI: dict[str, tuple[str, ...]] = {regola: tuple(_documento(regola, i) for i in range(1, 11)) for regola in _SPEC}
