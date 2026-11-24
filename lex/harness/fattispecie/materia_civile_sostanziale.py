"""Contratti, responsabilità civile, successioni, diritti reali e condominio.

Base normativa (testo vigente): artt. 1218, 1223, 1226, 1227, 1418, 1421, 1422, 1427, 1441, 1442, 1447, 1448, 1449,
1453, 1455, 1458, 2043, 2051, 2059, 2947 c.c.; artt. 7, 8, 12 l. 24/2017; art. 696-bis c.p.c.; artt. 533, 534, 553,
554, 557, 564, 713, 718 c.c.; art. 784 c.p.c.; artt. 949, 950, 951, 1079, 1129, 1158, 1159 c.c.; art. 64 disp. att.
c.c.; art. 5 d.lgs. 28/2010.
"""
from __future__ import annotations

from .schede import R, Scheda, p

_MEDIAZIONE = p("La materia rientra fra quelle per cui la mediazione è condizione di procedibilità della domanda giudiziale.",
                R("dlgs28:5", "condizione di procedibilita"))
_NON_CONTRATTO = r"caparra|preliminare|locazion|conduttor|sfratt|lavor|appalt|condomin|consumator|banca|polizza"

RISOLUZIONE = Scheda(
    regola="con_risoluzione", materia="contratti", nome="risoluzione del contratto per inadempimento",
    segnali=(r"risoluzion|risolvere il contratto|sciogliere il contratto|liberarsi dal contratto|sciolto il contratto",),
    alcuni=(r"inadempi|non (?:consegna|adempie|paga|esegue)|non ha (?:mai )?(?:consegnato|pagato|eseguito)|ritard|restitu|acconti",),
    esclusi=(_NON_CONTRATTO, r"diffida ad adempiere|1454"), punteggio=5,
    capito="Contraente che vuole sciogliere un contratto a prestazioni corrispettive per l'inadempimento dell'altro.",
    rimedio="domanda giudiziale di risoluzione per inadempimento con risarcimento del danno (o diffida ad adempiere prima)",
    conclusione=[
        p("Nei contratti a prestazioni corrispettive, se una parte non adempie, l'altra può chiedere l'adempimento o la "
          "risoluzione, salvo in ogni caso il risarcimento del danno; chiesta la risoluzione non si può più chiedere l'adempimento.",
          R("cc:1453", "puo' a sua scelta chiedere l'adempimento o la risoluzione del contratto"),
          R("cc:1453", "non puo' piu' chiedersi l'adempimento quando e' stata domandata la risoluzione")),
        p("Il contratto non si risolve se l'inadempimento ha scarsa importanza rispetto all'interesse dell'altra parte.",
          R("cc:1455", "ha scarsa importanza")),
        p("La risoluzione ha effetto retroattivo (salvo i contratti a esecuzione continuata o periodica per le prestazioni "
          "già eseguite) e non pregiudica i diritti acquistati dai terzi.", R("cc:1458", "ha effetto retroattivo tra le parti")),
    ],
    termini=[p("Prescrizione ordinaria decennale.", R("cc:2946", "si estinguono per prescrizione con il decorso di dieci anni"))],
    dati=["contratto e prestazioni", "inadempimento e sua importanza", "diffide inviate", "danni"],
)

RESCISSIONE = Scheda(
    regola="con_rescissione", materia="contratti", nome="rescissione del contratto",
    segnali=(r"rescission|rescinder|ultra dimidium|stato di bisogno|stato di pericolo|meta del (?:prezzo|valore)|a meta prezzo",),
    punteggio=6,
    capito="Contratto concluso in stato di pericolo o con lesione oltre la metà approfittando dello stato di bisogno.",
    rimedio="domanda di rescissione entro un anno dalla conclusione del contratto",
    conclusione=[
        p("Il contratto concluso a condizioni inique per la necessità, nota all'altra parte, di salvarsi da un pericolo attuale "
          "di danno grave alla persona può essere rescisso.", R("cc:1447", "puo' essere rescisso")),
        p("Per lesione la rescissione richiede sproporzione dipesa dallo stato di bisogno di cui l'altro ha approfittato, e la "
          "lesione deve eccedere la metà del valore della prestazione.",
          R("cc:1448", "dipesa dallo stato di bisogno"), R("cc:1448", "non eccede la meta' del valore")),
    ],
    termini=[p("L'azione si prescrive in un anno dalla conclusione del contratto.",
               R("cc:1449", "si prescrive in un anno dalla conclusione del contratto"))],
    dati=["data del contratto", "valore della prestazione e corrispettivo", "stato di bisogno o di pericolo"],
)

ANNULLAMENTO = Scheda(
    regola="con_annullamento", materia="contratti", nome="annullamento del contratto",
    segnali=(r"annullament|annullabil|annullar\w* (?:il|la) (?:contratto|vendita|donazione|firma)|annullarl",),
    alcuni=(r"contratt|vendita|firmat|errore|dolo|raggir|violenz|incapac|minacc",),
    esclusi=(r"delibera|provvedimento|\btar\b|sentenza|decreto|atto amministrativ|annullamento d ufficio|autotutela", _NON_CONTRATTO,
             r"transazion|transatt"), punteggio=5,
    capito="Contratto viziato da errore, violenza, dolo o incapacità.",
    rimedio="domanda di annullamento del contratto",
    conclusione=[
        p("Il contraente il cui consenso fu dato per errore, estorto con violenza o carpito con dolo può chiedere l'annullamento; "
          "l'azione spetta solo alla parte nel cui interesse è stabilita.",
          R("cc:1427", "carpito con dolo"), R("cc:1441", "solo dalla parte nel cui interesse e' stabilito dalla legge")),
    ],
    termini=[p("L'azione si prescrive in cinque anni, che per i vizi del consenso decorrono dalla cessazione della violenza o dalla "
               "scoperta dell'errore o del dolo.", R("cc:1442", "si prescrive in cinque anni"),
               R("cc:1442", "e' stato scoperto l'errore o il dolo"))],
    dati=["contratto e data", "vizio del consenso o incapacità", "data della scoperta"],
)

NULLITA = Scheda(
    regola="con_nullita", materia="contratti", nome="nullità del contratto",
    segnali=(r"nullit|e null[oa]\b|contratto nullo|clausola nulla",), alcuni=(r"contratt|clausola|accordo|scrittura",),
    esclusi=(r"delibera|notifica|sentenza|precett|verbale|bancari|usur|consumator|vessatori", _NON_CONTRATTO), punteggio=5,
    capito="Contratto o clausola contraria a norme imperative o priva dei requisiti essenziali.",
    rimedio="azione di accertamento della nullità e di restituzione delle prestazioni",
    conclusione=[
        p("Il contratto è nullo se contrario a norme imperative, se manca un requisito essenziale, se causa o motivo comune "
          "sono illeciti o se l'oggetto non ha i requisiti di legge, e negli altri casi previsti dalla legge.",
          R("cc:1418", "e' nullo quando e' contrario a norme imperative")),
        p("La nullità può essere fatta valere da chiunque vi ha interesse ed è rilevabile d'ufficio; l'azione non si prescrive, "
          "salvi usucapione e prescrizione delle azioni di ripetizione.",
          R("cc:1421", "puo' essere rilevata d'ufficio dal giudice"), R("cc:1422", "non e' soggetta a prescrizione")),
    ],
    dati=["contratto", "causa di nullità", "prestazioni eseguite da restituire"],
)

RISARCIMENTO_CONTRATTUALE = Scheda(
    regola="con_risarcimento_inadempimento", materia="contratti", nome="risarcimento del danno da inadempimento",
    segnali=(r"danni|danno|risarc|lucro cessante|mancato guadagno", r"inadempi|ritardo nella consegna|non ha (?:consegnato|eseguito)|"
             r"consegna\w* in ritardo|contratt|corriere|fornitor|diligenza|concorso di colpa"),
    esclusi=(_NON_CONTRATTO, r"sinistro|incidente|medic|ospedal|buca|diffamaz|custodia"), punteggio=4,
    capito="Danni subiti per l'inadempimento o il ritardo nell'esecuzione di un contratto.",
    rimedio="domanda di risarcimento del danno contrattuale",
    conclusione=[
        p("Il debitore che non esegue esattamente la prestazione risarcisce il danno se non prova l'impossibilità per causa a "
          "lui non imputabile; il risarcimento comprende perdita subita e mancato guadagno, se conseguenza immediata e diretta.",
          R("cc:1218", "e' tenuto al risarcimento del danno"), R("cc:1223", "il mancato guadagno")),
        p("Se il danno non è provabile nel preciso ammontare è liquidato in via equitativa; si riduce per il concorso di colpa "
          "del creditore e non comprende i danni evitabili con l'ordinaria diligenza.",
          R("cc:1226", "valutazione equitativa"), R("cc:1227", "usando l'ordinaria diligenza")),
    ],
    termini=[p("Prescrizione ordinaria decennale.", R("cc:2946", "si estinguono per prescrizione con il decorso di dieci anni"))],
    dati=["contratto e obbligo violato", "danno emergente e lucro cessante con prove", "condotta del creditore"],
)

RESPONSABILITA_SANITARIA = Scheda(
    regola="rc_responsabilita_sanitaria", materia="responsabilità civile", nome="responsabilità sanitaria (l. 24/2017)",
    segnali=(r"medic|ospedal|chirurg|sanitari|clinica|malasanita|infezione ospedaliera|errore (?:diagnostic|medico)|struttura sanitaria",),
    alcuni=(r"danni|danno|risarc|causa|errore|mort|responsabil|assicurazion|citare|rispond",),
    esclusi=(r"invalidita civile|inps|accompagnamento|(?:\blegge|\bl\.)\s*(?:n\.?\s*)?104\b|dati (?:sanitari|personali)|privacy|garante",), punteggio=7,
    capito="Danno da prestazione sanitaria: responsabilità della struttura e del medico.",
    rimedio="ricorso per consulenza tecnica preventiva ex art. 696-bis c.p.c. (o mediazione), poi giudizio di merito",
    conclusione=[
        p("La struttura sanitaria risponde contrattualmente delle condotte dei sanitari di cui si avvale; il medico risponde "
          "ai sensi dell'art. 2043 c.c., salvo obbligazione contrattuale assunta con il paziente.",
          R("l24:7", "risponde, ai sensi degli articoli 1218 e 1228 del codice civile"),
          R("l24:7", "risponde del proprio operato ai sensi dell'articolo 2043 del codice civile")),
        p("Prima della causa è condizione di procedibilità il ricorso per consulenza tecnica preventiva ex art. 696-bis "
          "c.p.c., in alternativa la mediazione; non si applica la negoziazione assistita.",
          R("l24:8", "costituisce condizione di procedibilita' della domanda di risarcimento"),
          R("l24:8", "in alternativa il procedimento di mediazione")),
        p("Il danneggiato può agire direttamente contro l'assicurazione della struttura o del sanitario, nei limiti del massimale.",
          R("l24:12", "ha diritto di agire direttamente")),
    ],
    termini=[p("Prescrizione: dieci anni verso la struttura (responsabilità contrattuale); cinque anni verso il medico che "
               "risponde da fatto illecito.", R("cc:2946", "si estinguono per prescrizione con il decorso di dieci anni"),
               R("cc:2947", "si prescrive in cinque anni"))],
    dati=["struttura e sanitari coinvolti", "cartella clinica", "danno e consulenza medico-legale", "assicurazione della struttura"],
)

COSE_IN_CUSTODIA = Scheda(
    regola="rc_cose_in_custodia", materia="responsabilità civile", nome="danno da cose in custodia e insidia",
    segnali=(r"custod|buca|marciapiede|scivolat|caduta|cadut\w* (?:per|a causa|in)|pavimento bagnato|ramo|tombino|insidia|dissesto",),
    alcuni=(r"danni|danno|risarc|responsabil|paga|ferit|lesion|rott|frattur|fatto male",),
    esclusi=(r"condomin\w*[^.]{0,40}(?:lastrico|infiltrazion)|sinistro stradale|tamponat|medic|ospedal", r"pignor|sequestr"), punteggio=5,
    capito="Danno causato da una cosa in custodia altrui (strada, locale, albero, impianto).",
    rimedio="richiesta di risarcimento al custode (ente proprietario della strada, esercente, condominio) e azione ex art. 2051 c.c.",
    conclusione=[
        p("Ciascuno risponde del danno cagionato dalle cose che ha in custodia, salvo che provi il caso fortuito: il "
          "danneggiato prova la cosa, il danno e il nesso causale; il custode prova il fortuito, anche nella condotta del danneggiato.",
          R("cc:2051", "salvo che provi il caso fortuito")),
        p("Il concorso di colpa del danneggiato riduce il risarcimento.", R("cc:1227", "il risarcimento e' diminuito")),
    ],
    termini=[p("Prescrizione in cinque anni dal fatto.", R("cc:2947", "si prescrive in cinque anni"))],
    dati=["luogo, data e dinamica", "custode della cosa", "testimoni e fotografie", "lesioni e spese"],
)

DIFFAMAZIONE_CIVILE = Scheda(
    regola="rc_diffamazione", materia="responsabilità civile", nome="diffamazione: risarcimento civile",
    segnali=(r"diffam|recension\w* (?:fals|offensiv)|post offensiv|scritt\w*[^.]{0,60}(?:truffator|ladro|incapace|delinquent)",),
    alcuni=(r"danni|danno|risarc|civil|causa|citazione",), esclusi=(r"querel\w*[^.]{0,30}(?:entro|termin)",), punteggio=6,
    capito="Lesione della reputazione con chiedere il risarcimento in sede civile.",
    rimedio="citazione per risarcimento del danno (mediazione obbligatoria se a mezzo stampa o altro mezzo di pubblicità)",
    conclusione=[
        p("Il fatto doloso o colposo che cagiona un danno ingiusto obbliga al risarcimento; il danno non patrimoniale si "
          "risarcisce nei casi di legge, fra cui la lesione di diritti inviolabili come la reputazione e i fatti di reato.",
          R("cc:2043", "obbliga colui che ha commesso il fatto a risarcire il danno"),
          R("cc:2059", "solo nei casi determinati dalla legge")),
        p("La diffamazione è reato procedibile a querela: l'azione civile si può proporre anche nel processo penale.",
          R("cp:595", "comunicando con piu' persone, offende l'altrui reputazione")),
    ],
    procedibilita=[_MEDIAZIONE],
    termini=[p("Prescrizione in cinque anni dal fatto (o il termine più lungo del reato).", R("cc:2947", "si prescrive in cinque anni"))],
    dati=["contenuto e mezzo di diffusione", "data della pubblicazione e della conoscenza", "diffusione e danno"],
)

PETIZIONE = Scheda(
    regola="suc_petizione_eredita", materia="successioni", nome="petizione di eredità",
    segnali=(r"petizione di eredita|qualita (?:di erede|ereditaria)|erede apparente|"
             r"(?:presi|preso|tenut\w*|possied\w*|occupa)[^.]{0,40}(?:beni|casa|eredita)[^.]{0,40}(?:defunt|padre|madre|eredit)",),
    alcuni=(r"eredit|erede|defunt|success",), punteggio=6,
    capito="Erede che chiede il riconoscimento della qualità ereditaria e la restituzione dei beni posseduti da altri.",
    rimedio="citazione per petizione di eredità al tribunale del luogo di apertura della successione",
    conclusione=[
        p("L'erede può chiedere il riconoscimento della qualità ereditaria contro chi possiede beni ereditari a titolo di "
          "erede o senza titolo, per ottenerne la restituzione; l'azione è imprescrittibile, salvi gli effetti dell'usucapione.",
          R("cc:533", "l'azione e' imprescrittibile")),
        p("Si agisce anche contro gli aventi causa, salvi i diritti acquistati a titolo oneroso in buona fede dall'erede "
          "apparente, nei limiti della trascrizione per immobili e mobili registrati.",
          R("cc:534", "per effetto di convenzioni a titolo oneroso con l'erede apparente")),
    ],
    procedibilita=[_MEDIAZIONE],
    dati=["qualità di erede (testamento o legge)", "beni posseduti dal convenuto", "eventuali alienazioni a terzi"],
)

DIVISIONE = Scheda(
    regola="suc_divisione", materia="successioni", nome="divisione ereditaria e scioglimento della comunione",
    segnali=(r"divisione|\bdivid|scioglimento della comunione|uscire dalla comproprieta|comproprieta",),
    alcuni=(r"eredit|coered|fratell|comproprie|comunione|success|cugin|in natura|vendere la casa",),
    esclusi=(r"condomin|separazion|divorzi|societ",), punteggio=5,
    capito="Coeredi o comproprietari che non si accordano sulla divisione dei beni.",
    rimedio="mediazione obbligatoria e poi citazione per divisione giudiziale nei confronti di tutti i condividenti",
    conclusione=[
        p("I coeredi possono sempre domandare la divisione (salvi i limiti temporali disposti dal testatore) e ciascuno può "
          "chiedere la sua parte in natura dei beni.",
          R("cc:713", "i coeredi possono sempre domandare la divisione"), R("cc:718", "la sua parte in natura")),
        p("La domanda di divisione si propone nei confronti di tutti gli eredi o comunisti e dei creditori opponenti.",
          R("cpc:784", "debbono proporsi in confronto di tutti gli eredi o condomini")),
    ],
    procedibilita=[_MEDIAZIONE],
    dati=["coeredi e quote", "beni e stime", "donazioni da collazionare", "comoda divisibilità degli immobili"],
)

RIDUZIONE = Scheda(
    regola="suc_riduzione", materia="successioni", nome="azione di riduzione (lesione di legittima)",
    segnali=(r"legittim|riduzion\w* (?:delle )?(?:donazion|disposizion)|azione di riduzione|lesion\w* (?:di|della) legittima|"
             r"lasciato tutto|diseredat",),
    alcuni=(r"eredit|testament|donazion|figli|coniuge|success|defunt|beneficio d inventario|riduzion",), esclusi=(r"legittim\w* (?:impedimento|sospetto)",),
    punteggio=6,
    capito="Legittimario leso da testamento o donazioni.",
    rimedio="mediazione obbligatoria e citazione per riduzione delle disposizioni testamentarie e delle donazioni",
    conclusione=[
        p("Le disposizioni testamentarie eccedenti la quota disponibile sono soggette a riduzione; la riduzione può essere "
          "chiesta solo dai legittimari, dai loro eredi o aventi causa, che non possono rinunciarvi finché vive il donante.",
          R("cc:554", "sono soggette a riduzione"), R("cc:557", "non puo' essere domandata che dai legittimari")),
        p("Il legittimario che non ha accettato con beneficio d'inventario non può chiedere la riduzione di donazioni e legati "
          "fatti a non coeredi.", R("cc:564", "non ha accettato l'eredita' col beneficio d'inventario")),
    ],
    procedibilita=[_MEDIAZIONE],
    avvertenze=[
        "Giurisprudenza letta — Cass., sez. II, n. 8517/2025 (dep. 01/04/2025): l'azione di riduzione si prescrive in dieci "
        "anni; se la qualità di legittimario nasce da una sentenza che dichiara la filiazione dopo la morte, il termine "
        "decorre dal passaggio in giudicato di quella sentenza. https://www.italgiure.giustizia.it/sncass/isapi/hc.dll/sn.solr/sn-collection/select?q=id%3Asnciv2025208517S&rows=1&wt=json"],
    dubbi=["Da verificare: la decorrenza ordinaria della prescrizione (Cass. SU n. 20644/2004, citata da Cass. n. 17749/2023) "
           "non ha un testo ufficiale leggibile. Fonti tentate il 24/11/2026: archivio SentenzeWeb (copre dal 2021); "
           "Italgiure/SentenzeWeb (non raggiungibile: certificato non verificabile); sito della Corte di cassazione (nessun "
           "archivio delle Sezioni Unite anteriori); Portale del Massimario (43 rassegne civili 2010-2025: la sentenza non è "
           "citata); Gazzetta Ufficiale (non pubblica le sentenze della Cassazione; ricerca respinta). Leggerne il testo "
           "prima di indicare la decorrenza al cliente."],
    dati=["testamento e donazioni", "asse ereditario e valori", "legittimari", "accettazione con beneficio d'inventario"],
)

REVOCA_AMMINISTRATORE = Scheda(
    regola="dr_revoca_amministratore", materia="diritti reali e condominio", nome="revoca giudiziale dell'amministratore di condominio",
    segnali=(r"amministrator", r"revoc|cacci|mandare via|gravi irregolarita|rendiconto|conto corrente condominiale"),
    alcuni=(r"condomin|rendiconto|revoca giudiziale|non fa il suo lavoro|grave irregolarita",),
    esclusi=(r"societa|\bsrl\b|\bspa\b|di sostegno|amministratore unico",), punteggio=6,
    capito="Condòmino che chiede la revoca dell'amministratore per gravi irregolarità o mancato rendiconto.",
    rimedio="ricorso per revoca giudiziale dell'amministratore (procedimento in camera di consiglio)",
    conclusione=[
        p("La revoca può essere disposta dall'autorità giudiziaria su ricorso di ciascun condòmino se l'amministratore non "
          "rende il conto della gestione o in caso di gravi irregolarità.",
          R("cc:1129", "su ricorso di ciascun condomino"), R("cc:1129", "in caso di gravi irregolarita'")),
        p("Il giudice provvede in camera di consiglio con decreto motivato, sentito l'amministratore; contro il provvedimento "
          "è ammesso reclamo entro dieci giorni dalla notificazione o comunicazione.",
          R("dispattcc:64", "provvede in camera di consiglio, con decreto motivato"),
          R("dispattcc:64", "entro dieci giorni dalla notificazione o dalla comunicazione")),
    ],
    competenza=[p("La competenza passa dal tribunale al giudice di pace con la riforma della magistratura onoraria, le cui "
                  "modifiche alle disposizioni di attuazione del codice civile entrano in vigore il 31 ottobre 2027: fino al "
                  "30 ottobre 2027 il ricorso si propone al tribunale.",
                  R("dlgs116:27", "all'articolo 64, sono apportate le seguenti modificazioni"),
                  R("dlgs116:32", "le disposizioni dell'articolo 27 entrano in vigore il"))],
    dati=["irregolarità contestate", "rendiconti mancanti", "delibere assembleari sulla revoca"],
)

NEGATORIA = Scheda(
    regola="dr_negatoria", materia="diritti reali e condominio", nome="azione negatoria",
    esclusi=(r"precett|esecuzion|pignor",),
    segnali=(r"negatori|inesistenza (?:della|di una|del) (?:servitu|diritto)|pretende (?:una|di avere) (?:servitu|diritto)|"
             r"servitu che non esiste|come se avesse (?:diritto|una servitu)",), punteggio=6,
    capito="Proprietario che contesta un diritto affermato da altri sulla sua cosa.",
    rimedio="citazione per accertamento dell'inesistenza del diritto e cessazione delle molestie",
    conclusione=[p("Il proprietario può agire per far dichiarare l'inesistenza dei diritti affermati da altri sulla cosa, se ha "
                   "motivo di temerne pregiudizio, e chiedere la cessazione di turbative e molestie e il risarcimento.",
                   R("cc:949", "far dichiarare l'inesistenza di diritti affermati da altri sulla cosa"))],
    procedibilita=[_MEDIAZIONE],
    dati=["titolo di proprietà", "diritto vantato dal terzo", "molestie"],
)

CONFESSORIA = Scheda(
    regola="dr_confessoria", materia="diritti reali e condominio", nome="azione confessoria della servitù",
    segnali=(r"confessori|riconoscere la servitu|accertamento della servitu|(?:impedisce|impedito|blocca)[^.]{0,60}(?:passaggio|servitu)|"
             r"servitu di passaggio[^.]{0,60}(?:cancello|impedi|blocc)|servitu[^.]{0,40}contestat|fondo servente|destinazione del padre di famiglia",),
    esclusi=(r"inesistenza|negatori",), punteggio=6,
    capito="Titolare di una servitù contestata o impedita dal proprietario del fondo servente.",
    rimedio="citazione per l'accertamento della servitù, la cessazione degli impedimenti e la rimessione in pristino",
    conclusione=[p("Il titolare della servitù può farne riconoscere l'esistenza contro chi ne contesta l'esercizio, far cessare "
                   "impedimenti e turbative e chiedere la rimessione in pristino e i danni.",
                   R("cc:1079", "puo' farne riconoscere in giudizio l'esistenza"))],
    procedibilita=[_MEDIAZIONE],
    avvertenze=["Se l'impedimento è recente, valutare prima l'azione possessoria entro l'anno (artt. 1168-1170 c.c.)."],
    dati=["titolo o modo di acquisto della servitù", "impedimenti e date"],
)

USUCAPIONE = Scheda(
    regola="dr_usucapione", materia="diritti reali e condominio", nome="usucapione",
    segnali=(r"usucap|diventarne proprietari|(?:possied|coltiv|usa|utilizz)\w*[^.]{0,60}da (?:oltre )?\d+ anni|possiede da (?:oltre )?(?:venti|20|vent)|da (?:oltre )?(?:venti|20|25|trent) anni[^.]{0,60}(?:possied|coltiv|uso|usa)",),
    punteggio=7,
    capito="Acquisto della proprietà o di un diritto reale per possesso prolungato.",
    rimedio="mediazione obbligatoria e citazione per accertamento dell'usucapione (trascrizione della sentenza o del verbale)",
    conclusione=[
        p("La proprietà degli immobili e gli altri diritti reali di godimento si acquistano con il possesso continuato per vent'anni.",
          R("cc:1158", "possesso continuato per venti anni")),
        p("Chi acquista in buona fede da un non proprietario con titolo idoneo trascritto usucapisce in dieci anni dalla trascrizione.",
          R("cc:1159", "col decorso di dieci anni dalla data della trascrizione")),
    ],
    procedibilita=[_MEDIAZIONE],
    dati=["inizio e atti di possesso", "testimoni", "dati catastali", "titolo trascritto (usucapione abbreviata)"],
)

CONFINI = Scheda(
    regola="dr_regolamento_confini", materia="diritti reali e condominio", nome="regolamento di confini e apposizione di termini",
    segnali=(r"confin\w* (?:incert|tra i|fra i)|regolamento di confini|apposizione di termini|spostat\w*[^.]{0,30}(?:paletti|termini|confin)",),
    punteggio=6,
    capito="Confine incerto fra fondi o termini mancanti.",
    rimedio="citazione per regolamento di confini (o per apposizione di termini)",
    conclusione=[
        p("Quando il confine è incerto ciascun proprietario può chiedere che sia stabilito giudizialmente; ogni mezzo di prova è "
          "ammesso e, in mancanza, il giudice segue le mappe catastali.",
          R("cc:950", "ogni mezzo di prova e' ammesso"), R("cc:950", "mappe catastali")),
        p("Se i termini mancano o sono irriconoscibili ciascun proprietario può chiederne l'apposizione a spese comuni.",
          R("cc:951", "a spese comuni")),
    ],
    procedibilita=[_MEDIAZIONE],
    dati=["titoli e mappe catastali", "stato dei luoghi", "eventuale CTU topografica"],
)

SCHEDE = (RESCISSIONE, ANNULLAMENTO, NULLITA, RISOLUZIONE, RISARCIMENTO_CONTRATTUALE, RESPONSABILITA_SANITARIA,
          COSE_IN_CUSTODIA, DIFFAMAZIONE_CIVILE, PETIZIONE, RIDUZIONE, DIVISIONE, REVOCA_AMMINISTRATORE, NEGATORIA,
          CONFESSORIA, USUCAPIONE, CONFINI)
