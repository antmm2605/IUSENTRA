"""Penale: remissione della querela, opposizione all'archiviazione, patteggiamento, giudizio abbreviato, messa alla prova,
riesame e appello cautelare, costituzione di parte civile, giustizia riparativa, esecuzione penale.

Base normativa (testo vigente): artt. 152, 168-bis c.p.; artt. 74, 78, 79, 129-bis, 309, 310, 324, 340, 408, 410, 438,
442, 444, 446, 458, 464-bis, 656, 665, 666 c.p.p.; artt. 42, 44 d.lgs. 150/2022.
"""
from __future__ import annotations

from .schede import R, Scadenza, Scheda, p

_PENALE = r"querel|reato|imputat|indagat|penal|\bpm\b|pubblico ministero|procura|gip|gup|denuncia|processo|condann|arrest|carcer"

REMISSIONE = Scheda(
    regola="pen_remissione_querela", materia="penale", nome="remissione della querela",
    segnali=(r"remission\w* (?:della |di )?querela|rimetter\w* (?:la )?querela|ritirar\w* (?:la )?querela|ritirare la denuncia|"
             r"querela[^.]{0,60}(?:rimess|ritir)|fatto pace con il querelat",),
    punteggio=7,
    capito="Querelante che vuole rimettere la querela o effetti della mancata comparizione del querelante.",
    rimedio="dichiarazione di remissione all'autorità procedente (o a un ufficiale di polizia giudiziaria) e accettazione del querelato",
    conclusione=[
        p("Nei reati punibili a querela la remissione estingue il reato; può essere processuale o extraprocessuale, espressa o "
          "tacita.", R("cp:152", "la remissione estingue il reato")),
        p("È remissione tacita anche la mancata comparizione senza giustificato motivo del querelante citato come testimone e "
          "la partecipazione a un programma di giustizia riparativa concluso con esito riparativo.",
          R("cp:152", "non compare all'udienza alla quale e' stato citato in qualita' di testimone"),
          R("cp:152", "programma di giustizia riparativa concluso con un esito riparativo")),
        p("La remissione e l'accettazione si fanno personalmente o con procuratore speciale, con dichiarazione all'autorità "
          "procedente o a un ufficiale di polizia giudiziaria; le spese del procedimento sono del querelato, salvo diverso accordo.",
          R("cpp:340", "e' fatta e accettata personalmente o a mezzo di procuratore speciale"),
          R("cpp:340", "le spese del procedimento sono a carico del querelato")),
    ],
    dati=["reato e procedibilità a querela", "fase del procedimento", "accordi su spese e risarcimento"],
    inquadramento=[p("La remissione estingue solo i reati punibili a querela: per i reati procedibili d'ufficio non ha effetto.",
                     R("cp:152", "punibili a querela della persona offesa, la remissione estingue il reato"))],
)

OPPOSIZIONE_ARCHIVIAZIONE = Scheda(
    regola="pen_opposizione_archiviazione", materia="penale", nome="opposizione alla richiesta di archiviazione",
    segnali=(r"archiviazion|archiviat|archiviar",), alcuni=(r"oppo|richiesta|avviso|\bpm\b|pubblico ministero|gip|persona offesa|denuncia|querela",),
    esclusi=(r"fascicol\w* (?:dello studio|archiviat)|pratica archiviata",), punteggio=6,
    capito="Persona offesa che riceve l'avviso della richiesta di archiviazione del pubblico ministero.",
    rimedio="opposizione motivata al GIP con indicazione delle investigazioni suppletive e dei relativi elementi di prova",
    conclusione=[
        p("Nell'avviso è precisato che nel termine di venti giorni la persona offesa può prendere visione degli atti e "
          "presentare opposizione con richiesta motivata di prosecuzione delle indagini; per i delitti con violenza alla "
          "persona e per il furto in abitazione il termine è di trenta giorni.",
          R("cpp:408", "nel termine di venti giorni"), R("cpp:408", "elevato a trenta giorni")),
        p("L'opposizione indica, a pena di inammissibilità, l'oggetto dell'investigazione suppletiva e i relativi elementi di prova.",
          R("cpp:410", "a pena di inammissibilita', l'oggetto della investigazione suppletiva")),
    ],
    scadenze=[Scadenza("opposizione entro", 20, "giorni", r"(?:avviso|richiesta di archiviazione)[^0-9]{0,40}notificat\w*(?: il)?",
                       (R("cpp:408", "nel termine di venti giorni"),), modello="PEN_OPPOSIZIONE_ARCHIVIAZIONE_408")],
    dati=["avviso della richiesta e data di notifica", "reato (violenza alla persona: trenta giorni)", "indagini da chiedere"],
)

PATTEGGIAMENTO = Scheda(
    regola="pen_patteggiamento", materia="penale", nome="applicazione della pena su richiesta (patteggiamento)",
    segnali=(r"patteggi|applicazione della pena su richiesta|\b444\b",), punteggio=6,
    capito="Definizione del processo con applicazione concordata della pena.",
    rimedio="richiesta di applicazione della pena con il consenso del pubblico ministero",
    conclusione=[
        p("Imputato e pubblico ministero possono chiedere l'applicazione di una pena sostitutiva o pecuniaria diminuita fino a "
          "un terzo, o di una pena detentiva che, diminuita fino a un terzo, non superi cinque anni; possono chiedere di non "
          "applicare le pene accessorie e la confisca facoltativa.",
          R("cpp:444", "diminuita fino a un terzo"), R("cpp:444", "non supera cinque anni")),
        p("La richiesta si formula fino alle conclusioni dell'udienza preliminare o, nel direttissimo, fino all'apertura del "
          "dibattimento; dopo il decreto di giudizio immediato, nei termini dell'art. 458; la volontà dell'imputato è espressa "
          "personalmente o con procuratore speciale.",
          R("cpp:446", "fino alla presentazione delle conclusioni"),
          R("cpp:446", "personalmente o a mezzo di procuratore speciale")),
    ],
    dati=["reato e pena edittale", "esclusioni oggettive (art. 444, comma 1-bis)", "precedenti", "accordo con il PM"],
)

ABBREVIATO = Scheda(
    regola="pen_abbreviato", materia="penale", nome="giudizio abbreviato",
    segnali=(r"abbreviato",), punteggio=6,
    capito="Definizione del processo allo stato degli atti con la riduzione della pena.",
    rimedio="richiesta di giudizio abbreviato (semplice o condizionato)",
    conclusione=[
        p("L'imputato può chiedere che il processo sia definito all'udienza preliminare allo stato degli atti, fino alle "
          "conclusioni; non è ammesso per i delitti puniti con l'ergastolo.",
          R("cpp:438", "allo stato degli atti"), R("cpp:438", "non e' ammesso il giudizio abbreviato per i delitti puniti con la pena dell'ergastolo")),
        p("In caso di condanna la pena è diminuita della metà per le contravvenzioni e di un terzo per i delitti; se non si "
          "propone impugnazione, è ridotta di un ulteriore sesto in esecuzione.",
          R("cpp:442", "diminuita della meta' se si procede per una contravvenzione e di un terzo se si procede per un delitto"),
          R("cpp:442", "ulteriormente ridotta di un sesto")),
        p("Dopo il decreto di giudizio immediato la richiesta si deposita, a pena di decadenza, entro quindici giorni dalla notificazione.",
          R("cpp:458", "entro quindici giorni dalla notificazione del decreto di giudizio immediato")),
    ],
    scadenze=[Scadenza("richiesta di abbreviato entro", 15, "giorni", r"(?:giudizio immediato)[^0-9]{0,40}notificat\w*(?: il)?",
                       (R("cpp:458", "entro quindici giorni dalla notificazione del decreto di giudizio immediato"),))],
    dati=["reato", "fase del procedimento", "eventuale decreto di giudizio immediato e data di notifica"],
)

MESSA_ALLA_PROVA = Scheda(
    regola="pen_messa_alla_prova", materia="penale", nome="sospensione del procedimento con messa alla prova",
    segnali=(r"messa alla prova|168-?bis|464-?bis|\bmap\b",), punteggio=7,
    capito="Sospensione del procedimento con messa alla prova dell'imputato.",
    rimedio="richiesta di sospensione con messa alla prova e programma predisposto con l'UEPE",
    conclusione=[
        p("È ammessa per i reati puniti con la sola pena pecuniaria o con pena detentiva non superiore nel massimo a quattro "
          "anni e per alcuni delitti a citazione diretta; comporta condotte riparatorie, il risarcimento ove possibile, "
          "l'affidamento al servizio sociale e il lavoro di pubblica utilità.",
          R("cp:168bis", "non superiore nel massimo a quattro anni"), R("cp:168bis", "il risarcimento del danno")),
        p("La richiesta si propone fino alle conclusioni dell'udienza preliminare, o fino all'apertura del dibattimento nel "
          "direttissimo, o fino alla conclusione dell'udienza predibattimentale nella citazione diretta.",
          R("cpp:464bis", "fino a che non siano formulate le conclusioni"),
          R("cpp:464bis", "fino alla conclusione dell'udienza predibattimentale")),
    ],
    dati=["reato e pena edittale massima", "precedenti messe alla prova", "fase del procedimento", "disponibilità al lavoro di pubblica utilità"],
)

RIESAME = Scheda(
    regola="pen_riesame", materia="penale", nome="riesame e appello cautelare",
    segnali=(r"riesame|appello cautelare|custodia cautelare|arresti domiciliari|misura cautelare|sequestro (?:preventivo|probatorio)",),
    alcuni=(r"riesame|impugn|appell|revoca|contest|entro|termin|ricors",), punteggio=6,
    capito="Impugnazione di una misura cautelare personale o reale.",
    rimedio="richiesta di riesame al tribunale distrettuale (o appello cautelare ex art. 310 c.p.p.)",
    conclusione=[
        p("Contro l'ordinanza che dispone una misura coercitiva si propone richiesta di riesame, anche nel merito, entro dieci "
          "giorni dall'esecuzione o notificazione.",
          R("cpp:309", "entro dieci giorni dalla esecuzione o notificazione del provvedimento")),
        p("Fuori di questi casi le ordinanze sulle misure cautelari personali si impugnano con appello, enunciando "
          "contestualmente i motivi.", R("cpp:310", "possono proporre appello contro le ordinanze in materia di misure cautelari personali")),
        p("Per i sequestri la richiesta di riesame si presenta entro dieci giorni dall'esecuzione o dalla conoscenza del sequestro.",
          R("cpp:324", "entro dieci giorni dalla data di esecuzione del provvedimento che ha disposto il sequestro")),
    ],
    scadenze=[Scadenza("riesame entro", 10, "giorni", r"(?:eseguit\w*|notificat\w*|arrestat\w*|sequestrat\w*)(?: il)?",
                       (R("cpp:309", "entro dieci giorni dalla esecuzione o notificazione del provvedimento"),),
                       sospensione_feriale=False)],
    termini=[p("Nei procedimenti relativi a imputati in custodia cautelare la sospensione feriale dei termini non opera se "
               "l'imputato o il difensore vi rinunciano.",
               R("l742:2", "non opera nei procedimenti relativi ad imputati in stato di custodia cautelare"),
               R("l742:2", "rinunzino alla sospensione dei termini"))],
    dubbi=["Consiglio operativo: il termine del riesame è calcolato senza sospensione feriale, in via prudenziale: proporre la "
           "richiesta entro quella data."],
    dati=["ordinanza e data di esecuzione o notifica", "tipo di misura (personale o reale)", "motivi"],
)

PARTE_CIVILE = Scheda(
    regola="pen_parte_civile", materia="penale", nome="costituzione di parte civile",
    segnali=(r"parte civile|risarcimento[^.]{0,40}(?:nel )?processo penale|responsabile civile",), punteggio=6,
    capito="Persona danneggiata dal reato che chiede restituzioni e risarcimento nel processo penale.",
    rimedio="dichiarazione di costituzione di parte civile depositata o presentata in udienza, con procura speciale",
    conclusione=[
        p("L'azione civile per restituzioni e risarcimento del danno da reato può essere esercitata nel processo penale dal "
          "danneggiato o dai successori universali, contro l'imputato e il responsabile civile.",
          R("cpp:74", "nei confronti dell'imputato e del responsabile civile")),
        p("La dichiarazione contiene, a pena di inammissibilità, le generalità delle parti, il difensore e la procura e le "
          "ragioni della domanda.", R("cpp:78", "a pena di inammissibilita'")),
        p("La costituzione è possibile per l'udienza preliminare, prima che siano ultimati gli accertamenti sulla costituzione "
          "delle parti, o fino agli adempimenti dell'art. 484 o dell'udienza predibattimentale, a pena di decadenza.",
          R("cpp:79", "prima che siano ultimati gli accertamenti relativi alla costituzione delle parti"),
          R("cpp:79", "a pena di decadenza")),
    ],
    dati=["reato e imputato", "danno subito e quantificazione", "fase e data dell'udienza", "procura speciale"],
)

GIUSTIZIA_RIPARATIVA = Scheda(
    regola="pen_giustizia_riparativa", materia="penale", nome="giustizia riparativa",
    segnali=(r"giustizia riparativa|programma riparativo|mediatore penale|129-?bis|incontrare la vittima",), punteggio=7,
    capito="Accesso a un programma di giustizia riparativa fra autore dell'offesa e vittima.",
    rimedio="richiesta all'autorità giudiziaria di invio al Centro per la giustizia riparativa",
    conclusione=[
        p("In ogni stato e grado del procedimento l'autorità giudiziaria può disporre, anche d'ufficio, l'invio dell'imputato e "
          "della vittima al Centro per la giustizia riparativa; la richiesta è proposta personalmente o con procuratore speciale.",
          R("cpp:129bis", "in ogni stato e grado del procedimento"),
          R("cpp:129bis", "personalmente o per mezzo di procuratore speciale")),
        p("I programmi sono accessibili senza preclusioni per tipo o gravità del reato, anche nella fase esecutiva.",
          R("dlgs150g:44", "senza preclusioni in relazione alla fattispecie di reato o alla sua gravita"),
          R("dlgs150g:44", "nella fase esecutiva della pena")),
        p("L'esito riparativo nei reati a querela vale come remissione tacita.",
          R("cp:152", "programma di giustizia riparativa concluso con un esito riparativo")),
    ],
    dati=["reato e fase", "consenso della vittima", "Centro per la giustizia riparativa di riferimento"],
)

ESECUZIONE_PENALE = Scheda(
    regola="pen_esecuzione", materia="penale", nome="esecuzione penale e incidente di esecuzione",
    segnali=(r"ordine di (?:esecuzione|carcerazione)|incidente di esecuzione|giudice dell esecuzione[^.]{0,40}(?:penal|condann|sentenz)|"
             r"misur\w* alternativ|affidamento in prova|continuazione tra|pene concorrenti|abolitio criminis|cumulo delle pene",),
    esclusi=(r"pignor|precett|civile",), punteggio=6,
    capito="Questioni sull'esecuzione di una sentenza penale di condanna.",
    rimedio="istanza al giudice dell'esecuzione (art. 666 c.p.p.) o al tribunale di sorveglianza per le misure alternative",
    conclusione=[
        p("Per pene detentive (anche residue) non superiori a tre anni, o quattro nei casi dell'art. 47-ter ord. pen., il "
          "pubblico ministero sospende l'esecuzione e notifica ordine e decreto di sospensione per consentire l'istanza di misure alternative.",
          R("cpp:656", "non e' superiore a tre anni"), R("cpp:656", "ne sospende l'esecuzione")),
        p("È competente per l'esecuzione il giudice che ha deliberato il provvedimento (salve le regole per i giudizi di "
          "impugnazione); procede a richiesta del pubblico ministero, dell'interessato o del difensore.",
          R("cpp:665", "e' il giudice che lo ha deliberato"),
          R("cpp:666", "procede a richiesta del pubblico ministero, dell'interessato o del difensore")),
    ],
    dati=["sentenze e data di irrevocabilità", "ordine di esecuzione e data di notifica", "pena residua"],
)

SCHEDE = (REMISSIONE, GIUSTIZIA_RIPARATIVA, MESSA_ALLA_PROVA, PATTEGGIAMENTO, ABBREVIATO, OPPOSIZIONE_ARCHIVIAZIONE, RIESAME,
          PARTE_CIVILE, ESECUZIONE_PENALE)
