"""Famiglia (affidamento dei figli fuori dal matrimonio), locazioni (recesso del conduttore, aggiornamento ISTAT),
consumatori (recesso, pratiche scorrette, ADR), tributario (autotutela, adesione, rateizzazione), immigrazione
(protezione internazionale), stragiudiziale (transazione, parere).

Base normativa (testo vigente): artt. 337-ter, 337-quater c.c.; art. 473-bis.11 c.p.c.; artt. 27, 32 l. 392/1978;
art. 3 l. 431/1998; artt. 20, 21, 27, 52, 53, 54, 141 d.lgs. 206/2005; artt. 10-quater, 10-quinquies l. 212/2000;
artt. 5, 6, 15 d.lgs. 218/1997; art. 19 d.P.R. 602/1973; artt. 35, 35-bis d.lgs. 25/2008; artt. 1965, 1966, 1975 c.c.;
art. 2 l. 247/2012.
"""
from __future__ import annotations

from .schede import R, Scheda, p

AFFIDAMENTO = Scheda(
    regola="fam_affidamento_figli", materia="famiglia e minori", nome="affidamento e collocamento dei figli (anche nati fuori dal matrimonio)",
    segnali=(r"affid|collocament|vedere (?:il|la|i) figli|impedisce[^.]{0,40}(?:vedere|figli)",),
    alcuni=(r"figli|bambin|minore|padre|madre|genitor|affidamento (?:super )?esclusivo",),
    esclusi=(r"separazion|divorzi|modific\w* (?:delle )?condizion|modificar\w* (?:il )?collocamento|affidamento in prova|servizi sociali[^.]{0,20}condann|"
             r"negoziazione assistita|maggiorenn", r"incarico|appalto|banca"), punteggio=6,
    capito="Genitori (sposati o no) in disaccordo sull'affidamento, il collocamento e le visite dei figli minori.",
    rimedio="ricorso al tribunale del luogo di residenza abituale del minore (rito unificato delle persone, dei minorenni e delle famiglie)",
    conclusione=[
        p("Il figlio minore ha diritto a un rapporto equilibrato e continuativo con entrambi i genitori; il giudice valuta "
          "prioritariamente l'affidamento a entrambi e fissa tempi di presenza e contributo al mantenimento.",
          R("cc:337ter", "rapporto equilibrato e continuativo con ciascuno dei genitori"),
          R("cc:337ter", "valuta prioritariamente la possibilita' che i figli minori restino affidati a entrambi i genitori")),
        p("L'affidamento a un solo genitore è disposto con provvedimento motivato quando l'affidamento all'altro è contrario "
          "all'interesse del minore; ciascun genitore può chiederlo in qualsiasi momento.",
          R("cc:337quater", "contrario all'interesse del minore")),
        p("È competente il tribunale del luogo di residenza abituale del minore (dell'ultima residenza, se il trasferimento "
          "non autorizzato risale a meno di un anno).",
          R("cpc:473bis11", "e' competente il tribunale del luogo in cui il minore ha la residenza abituale")),
    ],
    dati=["residenza abituale del minore", "età e situazione del minore", "proposta di calendario", "redditi dei genitori"],
)

RECESSO_CONDUTTORE = Scheda(
    regola="loc_recesso_conduttore", materia="locazioni", nome="recesso del conduttore",
    segnali=(r"recess|recedere|lasciare (?:la casa|l immobile|il locale)|andar(?:e|sene) via prima|se ne va|senza preavviso|disdett\w* (?:del|dell) inquilin",),
    alcuni=(r"conduttor|inquilin|locazion|affitto|locatore|contratto 4\+4|4 ?\+ ?4|gravi motivi|contratto commerciale|deposito",),
    esclusi=(r"socio|societa|consumator|caparra|sfratt|morosit|in nero|non registrat|indebit|extra canone",), punteggio=6,
    capito="Conduttore che vuole lasciare l'immobile prima della scadenza.",
    rimedio="comunicazione di recesso con preavviso di sei mesi (per gravi motivi o se previsto dal contratto)",
    conclusione=[
        p("Indipendentemente dal contratto, il conduttore può recedere in qualsiasi momento per gravi motivi con preavviso di "
          "almeno sei mesi; il contratto può prevedere il recesso libero con lo stesso preavviso.",
          R("l392:27", "qualora ricorrano gravi motivi, puo' recedere in qualsiasi momento"),
          R("l392:27", "almeno sei mesi prima")),
        p("Nelle locazioni abitative il conduttore può recedere per gravi motivi con preavviso di sei mesi.",
          R("l431:3", "dando comunicazione al locatore con preavviso di sei mesi")),
    ],
    dati=["tipo di contratto (abitativo, commerciale)", "clausola di recesso", "gravi motivi", "data della comunicazione"],
)

AGGIORNAMENTO_CANONE = Scheda(
    regola="loc_aggiornamento_istat", materia="locazioni", nome="aggiornamento ISTAT del canone",
    segnali=(r"\bistat\b|aggiornamento del canone|rivalutazione del canone|adeguamento del canone",), punteggio=6,
    capito="Aggiornamento annuale del canone di locazione all'indice ISTAT.",
    rimedio="richiesta scritta del locatore; contestazione delle somme non dovute",
    conclusione=[p("Le parti possono convenire l'aggiornamento annuale del canone su richiesta del locatore; per i contratti "
                   "di durata non superiore a quella legale l'aumento non può superare il 75 per cento della variazione ISTAT.",
                   R("l392:32", "aggiornato annualmente su richiesta del locatore"), R("l392:32", "75 per cento"))],
    dubbi=["Nei contratti abitativi in cedolare secca l'aggiornamento è sospeso per la durata dell'opzione: la norma "
           "fiscale non è nella biblioteca, verificarla."],
    dati=["clausola di aggiornamento", "data della richiesta scritta", "tipo di contratto e regime fiscale"],
)

RECESSO_CONSUMATORE = Scheda(
    regola="cons_recesso", materia="consumatori", nome="diritto di recesso del consumatore",
    segnali=(r"recess|recedere|restituire il prodotto|ripensa",),
    alcuni=(r"online|a distanza|porta a porta|fuori dai locali|a domicilio|e-commerce|sito|consumator|ordin|comprat|acquist|abbonament|diritto di recesso|venditor",),
    esclusi=(r"socio|societa|conduttor|inquilin|locazion|caparra", r"lavor"), punteggio=6,
    capito="Consumatore che vuole recedere da un contratto a distanza o concluso fuori dei locali commerciali.",
    rimedio="dichiarazione esplicita di recesso (anche con il modulo tipo) entro il termine",
    conclusione=[
        p("Il consumatore ha quattordici giorni per recedere da un contratto a distanza o negoziato fuori dei locali "
          "commerciali, senza motivazione e senza costi diversi da quelli di legge; trenta giorni per le visite non richieste a domicilio.",
          R("dlgs206:52", "un periodo di quattordici giorni per recedere"), R("dlgs206:52", "prolungato a trenta giorni")),
        p("Se il professionista non informa del diritto di recesso, il periodo termina dodici mesi dopo la fine di quello iniziale.",
          R("dlgs206:53", "termina dodici mesi dopo la fine del periodo di recesso iniziale")),
        p("Il recesso si esercita con il modulo tipo o con qualsiasi dichiarazione esplicita prima della scadenza.",
          R("dlgs206:54", "qualsiasi altra dichiarazione esplicita")),
    ],
    dati=["data di conclusione e di consegna", "canale di vendita", "informativa ricevuta"],
)

PRATICHE_SCORRETTE = Scheda(
    regola="cons_pratiche_scorrette", materia="consumatori", nome="pratiche commerciali scorrette",
    segnali=(r"pratic\w* commercial\w* (?:scorrett|aggressiv|ingannevol)|pubblicita ingannevol|servizi non richiest|pratica aggressiv|pressione aggressiv|ingannat\w*[^.]{0,30}pubblicita|pubblicita[^.]{0,30}ingann|antitrust|\bagcm\b|ingannevol",),
    punteggio=6,
    capito="Pratica commerciale ingannevole o aggressiva verso i consumatori.",
    rimedio="segnalazione all'Autorità garante della concorrenza e del mercato; azione civile per i danni",
    conclusione=[
        p("Le pratiche commerciali scorrette sono vietate: è scorretta la pratica contraria alla diligenza professionale e "
          "idonea a falsare in misura apprezzabile il comportamento economico del consumatore medio.",
          R("dlgs206:20", "le pratiche commerciali scorrette sono vietate"),
          R("dlgs206:20", "contraria alla diligenza professionale")),
        p("È ingannevole la pratica che contiene informazioni non vere o induce in errore il consumatore medio facendogli "
          "prendere una decisione che non avrebbe preso.", R("dlgs206:21", "informazioni non rispondenti al vero")),
        p("L'Autorità garante della concorrenza e del mercato interviene sulle pratiche scorrette, anche nei settori regolati.",
          R("dlgs206:27", "l'autorita' garante della concorrenza e del mercato")),
    ],
    dati=["pratica e prove (pubblicità, contratti, registrazioni)", "danno subito"],
)

ADR_CONSUMO = Scheda(
    regola="cons_adr", materia="consumatori", nome="risoluzione alternativa delle controversie di consumo (ADR, Corecom, ARERA)",
    segnali=(r"\badr\b|corecom|arera|conciliazione paritetica|risoluzione alternativa|conciliazion\w*[^.]{0,40}(?:bollett|telefon|gas|luce|energia)|"
             r"(?:bollett|telefon|gas|luce|energia)[^.]{0,60}conciliazion",),
    punteggio=6,
    capito="Controversia di consumo da portare a una procedura di risoluzione extragiudiziale.",
    rimedio="domanda all'organismo ADR del settore (Corecom/ConciliaWeb per le comunicazioni, Servizio conciliazione ARERA per energia)",
    conclusione=[
        p("Restano obbligatorie le procedure extragiudiziali previste per settore: mediazione nelle materie di legge, "
          "tentativo di conciliazione nelle comunicazioni elettroniche e nei servizi di pubblica utilità regolati.",
          R("dlgs206:141", "tentativo obbligatorio di conciliazione nel settore delle comunicazioni elettroniche")),
    ],
    dati=["settore e operatore", "reclamo già presentato e risposta", "importo contestato"],
)

AUTOTUTELA = Scheda(
    regola="trib_autotutela", materia="tributario", nome="autotutela tributaria",
    segnali=(r"autotutela",), alcuni=(r"tribut|agenzia|entrate|imposta|imposizion|cartella|avviso|accertament|fisco|imu|tari|ufficio|annullar|istanza|rifiuto|ricorso",), punteggio=7,
    capito="Richiesta all'amministrazione finanziaria di annullare in autotutela un atto illegittimo.",
    rimedio="istanza di autotutela (obbligatoria nei casi di manifesta illegittimità), senza sospensione del termine per il ricorso",
    conclusione=[
        p("L'amministrazione finanziaria annulla l'atto, anche in pendenza di giudizio o se definitivo, nei casi di manifesta "
          "illegittimità: errore di persona, di calcolo, sul tributo, sul presupposto, pagamenti non considerati, documenti sanati.",
          R("l212:10quater", "procede in tutto o in parte all'annullamento"), R("l212:10quater", "errore di persona")),
        p("Fuori da quei casi l'autotutela è facoltativa, per illegittimità o infondatezza dell'atto.",
          R("l212:10quinquies", "illegittimita' o dell'infondatezza dell'atto")),
    ],
    avvertenze=["L'istanza di autotutela non sospende il termine per il ricorso: se il termine scade, depositare comunque il ricorso."],
    dati=["atto e data di notifica", "vizio (rientra nei casi di autotutela obbligatoria?)"],
)

ADESIONE = Scheda(
    regola="trib_adesione", materia="tributario", nome="accertamento con adesione",
    segnali=(r"adesione|definire (?:l accertamento|con l ufficio)|trattare con l agenzia|ridurre l accertamento",),
    alcuni=(r"accertament|agenzia|entrate|imposta|tribut|avviso|ricorso|contraddittorio",),
    esclusi=(r"definizione agevolata|rottamazion|(?:prepar|redig|scriv)\w* (?:il |un |l )?ricorso",), punteggio=6,
    capito="Contribuente che vuole definire l'accertamento con l'ufficio.",
    rimedio="istanza di accertamento con adesione prima dell'impugnazione",
    conclusione=[
        p("Il contribuente cui è notificato un avviso di accertamento non preceduto dal contraddittorio preventivo può "
          "presentare istanza di accertamento con adesione prima di impugnarlo.",
          R("dlgs218:6", "istanza di accertamento con adesione")),
        p("Con l'istanza il termine per impugnare e quello per il pagamento sono sospesi per novanta giorni.",
          R("dlgs218:6", "sospesi per un periodo di novanta giorni dalla data di presentazione dell'istanza")),
    ],
    dati=["avviso e data di notifica", "contraddittorio preventivo svolto o no", "importi contestati"],
)

RATEIZZAZIONE = Scheda(
    regola="trib_rateizzazione", materia="tributario", nome="rateizzazione delle somme iscritte a ruolo",
    segnali=(r"rateizz|dilazion|a rate|rateazion|\brate\b",), alcuni=(r"cartell|ruol|riscossione|agenzia delle entrate|tribut|fisc|salto|ipotech|fermi|decad",),
    esclusi=(r"pignor\w*[^.]{0,40}convers|conversione del pignoramento",), punteggio=6,
    capito="Dilazione del pagamento delle cartelle con l'Agenzia delle entrate-Riscossione.",
    rimedio="richiesta di dilazione all'Agenzia delle entrate-Riscossione",
    conclusione=[
        p("Su semplice richiesta, per temporanea difficoltà, le somme fino a 120.000 euro si dilazionano fino a 84 rate per "
          "le richieste del 2025-2026, 96 nel 2027-2028 e 108 dal 2029; oltre 120.000 euro, documentando la difficoltà, fino a 120 rate.",
          R("dpr602:19", "ottantaquattro rate mensili"), R("dpr602:19", "centoventi rate mensili")),
        p("Il mancato pagamento di otto rate, anche non consecutive, fa decadere dalla rateazione e rende l'intero importo "
          "riscuotibile; il carico non può essere nuovamente rateizzato.",
          R("dpr602:19", "otto rate, anche non consecutive")),
    ],
    dati=["importo complessivo a ruolo", "anno della richiesta", "situazione economica documentabile"],
)

PROTEZIONE_INTERNAZIONALE = Scheda(
    regola="imm_protezione_internazionale", materia="immigrazione", nome="ricorso contro le decisioni della Commissione territoriale",
    segnali=(r"commissione territoriale|asilo|protezione (?:internazionale|sussidiaria|speciale)|rifugiat|sezione immigrazione|decisione della commissione|manifestamente infondata",), punteggio=7,
    capito="Richiedente protezione internazionale che impugna il diniego della Commissione territoriale.",
    rimedio="ricorso alla sezione specializzata immigrazione del tribunale ordinario",
    conclusione=[
        p("Contro i provvedimenti della Commissione territoriale e della Commissione nazionale è ammesso ricorso al giudice "
          "ordinario, anche quando è riconosciuta solo la protezione sussidiaria o speciale.",
          R("dlgs25:35", "e' ammesso ricorso all'autorita' giudiziaria ordinaria")),
        p("Il ricorso è proposto, a pena di inammissibilità, entro trenta giorni dalla notificazione (sessanta se il "
          "ricorrente è in un Paese terzo).", R("dlgs25:35bis", "entro trenta giorni dalla notificazione del provvedimento")),
    ],
    dubbi=["Termini ridotti ed effetto sospensivo nelle procedure accelerate e di frontiera (artt. 35-bis e 35-ter): "
           "verificare il tipo di procedura indicato nel provvedimento."],
    dati=["provvedimento e data di notifica", "tipo di procedura (ordinaria, accelerata, di frontiera)", "paese di origine"],
)

TRANSAZIONE = Scheda(
    regola="str_transazione", materia="stragiudiziale", nome="transazione",
    segnali=(r"transazion|accordo transattivo|chiudere (?:la lite|la causa) con un accordo|reciproche concessioni",),
    esclusi=(r"lavorator|dipendent|datore di lavoro|vertenza", r"\(creditore|precett"), punteggio=5,
    capito="Accordo per chiudere o prevenire una lite con reciproche concessioni.",
    rimedio="contratto di transazione per iscritto",
    conclusione=[
        p("La transazione è il contratto con cui le parti, con reciproche concessioni, pongono fine a una lite o la prevengono, "
          "anche creando o estinguendo rapporti diversi.", R("cc:1965", "facendosi reciproche concessioni")),
        p("Le parti devono poter disporre dei diritti; la transazione su diritti indisponibili è nulla.",
          R("cc:1966", "la transazione e' nulla")),
        p("La transazione generale non si impugna per la scoperta successiva di documenti ignoti, salvo che fossero occultati dall'altra parte.",
          R("cc:1975", "salvo che questi siano stati occultati dall'altra parte")),
    ],
    dati=["rapporto controverso", "concessioni reciproche", "modalità di pagamento e clausole di risoluzione"],
)

PARERE = Scheda(
    regola="str_parere", materia="stragiudiziale", nome="parere legale scritto",
    segnali=(r"parere (?:pro veritate|scritto|legale|motivato)|redigere un parere|scrivere un parere",), tipi=frozenset({"parere", "redazione", "termine", "calcolo", "altro"}),
    punteggio=3,
    capito="Richiesta di un parere legale scritto per il cliente.",
    rimedio="parere scritto: quesito, fatti, norme e giurisprudenza, soluzione, rischi e alternative",
    conclusione=[p("La consulenza legale e l'assistenza stragiudiziale connesse all'attività giurisdizionale, svolte in modo "
                   "continuativo e organizzato, sono di competenza degli avvocati.",
                   R("l247:2", "l'attivita' professionale di consulenza legale e di assistenza legale stragiudiziale"))],
    cosa_fare=["Formulare il quesito e i fatti rilevanti con i documenti.", "Indicare norme vigenti e orientamenti verificati.",
               "Concludere con la soluzione, i rischi e le alternative, e i termini da rispettare."],
    dati=["quesito", "fatti e documenti", "destinatario del parere"],
)

SCHEDE = (AFFIDAMENTO, RECESSO_CONDUTTORE, AGGIORNAMENTO_CANONE, RECESSO_CONSUMATORE, PRATICHE_SCORRETTE, ADR_CONSUMO,
          AUTOTUTELA, ADESIONE, RATEIZZAZIONE, PROTEZIONE_INTERNAZIONALE, TRANSAZIONE, PARERE)
