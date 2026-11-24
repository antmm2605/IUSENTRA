"""Esecuzione forzata e monitorio: pignoramento mobiliare, immobiliare e presso terzi, opposizione all'esecuzione già
iniziata, opposizione di terzo, conversione del pignoramento, ricerca telematica dei beni, obblighi di fare e non fare,
opposizione tardiva e provvisoria esecuzione del decreto ingiuntivo.

Base normativa (testo vigente): artt. 26-bis, 481, 492-bis, 495, 497, 513, 514, 518, 543, 545, 547, 548, 555, 557,
567, 612, 614-bis, 615, 616, 619, 620, 624, 642, 648, 649, 650 c.p.c.; art. 2931 c.c.
"""
from __future__ import annotations

from ..comprensione import Comprensione
from ..fatti import Fatti
from ..modello import Analisi
from .schede import R, Scadenza, Scheda, p

_EFFICACIA_PRECETTO = p("Il precetto perde efficacia se entro novanta giorni dalla notificazione non è iniziata l'esecuzione.",
                        R("cpc:481", "novanta giorni"))
_EFFICACIA_PIGNORAMENTO = p("Il pignoramento perde efficacia se entro quarantacinque giorni dal compimento non è chiesta "
                            "l'assegnazione o la vendita.",
                            R("cpc:497", "senza che sia stata richiesta l'assegnazione o la vendita"))
_NON_ESEC = (r"\bministero|pubblica amministrazione|\bcomune di|azienda sanitaria",)  # contro la PA: regola pi_esecuzione_pa


def _giudice_esecuzione(a: Analisi, c: Comprensione, f: Fatti) -> None:
    luogo = f.residenza_convenuto or ""
    a.giudice = "Tribunale" + (f" di {luogo}" if luogo else "") + " — giudice dell'esecuzione"


PIGNORAMENTO_MOBILIARE = Scheda(
    regola="es_pignoramento_mobiliare", materia="esecuzione", nome="pignoramento mobiliare presso il debitore",
    segnali=(r"pignoramento mobiliare|pignor\w*[^.]{0,50}(?:beni mobili|\bmobili\b|in casa|cose del debitore|arredi|merce)|"
             r"impignorabil[^.]{0,40}(?:mobil|cose|beni)|ufficiale giudiziario[^.]{0,60}(?:casa|mobili)",),
    esclusi=(r"presso terzi|stipendi|\bpension|conto corrente|immobil|opposizion|proprieta (?:di|del) terz|di mia proprieta", *_NON_ESEC),
    punteggio=6,
    capito="Creditore con titolo e precetto che vuole pignorare beni mobili del debitore.",
    rimedio="richiesta all'ufficiale giudiziario di pignoramento mobiliare, poi iscrizione a ruolo e istanza di vendita",
    conclusione=[
        p("L'ufficiale giudiziario, munito del titolo esecutivo e del precetto, ricerca le cose da pignorare nella casa del "
          "debitore e negli altri luoghi a lui appartenenti, anche con l'assistenza della forza pubblica.",
          R("cpc:513", "munito del titolo esecutivo e del precetto"),
          R("cpc:513", "nella casa del debitore e negli altri luoghi a lui appartenenti")),
        p("Ricevuto il verbale, il creditore iscrive a ruolo il processo entro quindici giorni dalla consegna, a pena di "
          "inefficacia del pignoramento.",
          R("cpc:518", "entro quindici giorni dalla consegna, a pena di inefficacia del pignoramento")),
    ],
    inquadramento=[p("Non si possono pignorare i beni indicati dalla legge (fra gli altri: anello nuziale, vestiti, letti, "
                     "tavoli e sedie per i pasti, frigorifero, lavatrice, utensili di casa).",
                     R("cpc:514", "non si possono pignorare"), R("cpc:514", "il frigorifero"))],
    termini=[_EFFICACIA_PRECETTO, _EFFICACIA_PIGNORAMENTO],
    cosa_fare=["Verificare che il precetto sia notificato e ancora efficace (novanta giorni).",
               "Chiedere il pignoramento all'UNEP del luogo dei beni; valutare l'esperto stimatore.",
               "Iscrivere a ruolo entro quindici giorni dalla consegna del verbale e chiedere la vendita entro quarantacinque giorni."],
    dati=["titolo esecutivo e data di notifica del precetto", "luogo dei beni", "beni presumibilmente presenti"],
    extra=_giudice_esecuzione,
)

PIGNORAMENTO_IMMOBILIARE = Scheda(
    regola="es_pignoramento_immobiliare", materia="esecuzione", nome="pignoramento immobiliare",
    segnali=(r"pignoramento immobiliare|pignor\w*[^.?]{0,50}(?:\bcasa\b|immobil|appartamento|terreno|villa|fabbricat)|"
             r"(?:\bcasa\b|immobil|appartamento|terreno|villa)[^.?]{0,60}pignor|"
             r"documentazione ipocatastale|certificato notarile|ventennale|nota di trascrizione",),
    esclusi=(r"opposizion|conversion|a rate|\bmobili\b|merce|impignorabil|presso terzi|stipendi|\bpension|usucap", *_NON_ESEC), punteggio=7,
    capito="Creditore che vuole pignorare un immobile del debitore.",
    rimedio="atto di pignoramento immobiliare notificato e trascritto, iscrizione a ruolo, istanza di vendita con la documentazione",
    conclusione=[
        p("Il pignoramento immobiliare si esegue con la notificazione al debitore e la successiva trascrizione di un atto "
          "che indica esattamente i beni e i diritti immobiliari.",
          R("cpc:555", "mediante notificazione al debitore e successiva trascrizione")),
        p("Il creditore iscrive a ruolo il processo depositando titolo, precetto, atto di pignoramento e nota di "
          "trascrizione entro quindici giorni dalla consegna dell'atto, a pena di inefficacia.",
          R("cpc:557", "entro quindici giorni dalla consegna dell'atto di pignoramento, a pena di inefficacia")),
        p("Con l'istanza di vendita il creditore deposita, entro il termine di efficacia del pignoramento, l'estratto del "
          "catasto e i certificati delle iscrizioni e trascrizioni dei venti anni anteriori, o il certificato notarile.",
          R("cpc:567", "nei venti anni anteriori alla trascrizione del pignoramento"),
          R("cpc:567", "certificato notarile")),
    ],
    termini=[_EFFICACIA_PRECETTO, _EFFICACIA_PIGNORAMENTO],
    cosa_fare=["Visure catastali e ipotecarie per individuare esattamente l'immobile e le iscrizioni.",
               "Notifica dell'atto di pignoramento e trascrizione; iscrizione a ruolo entro quindici giorni dalla consegna.",
               "Istanza di vendita con documentazione ventennale o certificato notarile entro quarantacinque giorni."],
    dati=["titolo esecutivo e precetto", "dati catastali dell'immobile", "quota di proprietà del debitore", "ipoteche iscritte"],
    extra=_giudice_esecuzione,
)


def _extra_terzi(a: Analisi, c: Comprensione, f: Fatti) -> None:
    luogo = f.residenza_convenuto or ""
    a.giudice = "Tribunale del luogo di residenza, domicilio, dimora o sede del debitore" + (f" ({luogo})" if luogo else "")


PIGNORAMENTO_TERZI = Scheda(
    regola="es_pignoramento_terzi", materia="esecuzione", nome="pignoramento presso terzi",
    segnali=(r"presso terzi|terzo pignorat|dichiarazione del terzo|pignor\w*[^.]{0,50}(?:stipendi|salari|\bpension|conto|banca|"
             r"crediti|quinto|fitti|canoni)|(?:stipendi|\bpension|conto)[^.]{0,50}pignor",),
    esclusi=(r"opposizion", *_NON_ESEC), punteggio=6,
    capito="Creditore che vuole pignorare crediti del debitore verso terzi (stipendio, pensione, conto corrente).",
    rimedio="atto di pignoramento presso terzi notificato al terzo e al debitore, con citazione davanti al giudice dell'esecuzione",
    conclusione=[
        p("Il pignoramento di crediti del debitore verso terzi si esegue con atto notificato al terzo e al debitore, "
          "con l'invito al terzo a comunicare la dichiarazione entro dieci giorni.",
          R("cpc:543", "mediante atto notificato al terzo e al debitore"),
          R("cpc:543", "entro dieci giorni")),
        p("Il creditore iscrive a ruolo il processo entro trenta giorni dalla consegna dell'atto notificato, a pena di "
          "inefficacia del pignoramento.", R("cpc:543", "entro trenta giorni dalla consegna, a pena di inefficacia del pignoramento")),
        p("Stipendi e salari si pignorano nella misura di un quinto; la pensione non è pignorabile per il doppio della "
          "misura massima mensile dell'assegno sociale, con un minimo di 1.000 euro.",
          R("cpc:545", "nella misura di un quinto"),
          R("cpc:545", "doppio della misura massima mensile dell'assegno sociale, con un minimo di 1.000 euro")),
    ],
    competenza=[p("Per l'espropriazione di crediti è competente il giudice del luogo in cui il debitore ha la residenza, il "
                  "domicilio, la dimora o la sede (contro le pubbliche amministrazioni vale il foro dell'Avvocatura dello Stato).",
                  R("cpc:26bis", "competente il giudice del luogo in cui il debitore ha la residenza"))],
    inquadramento=[p("Se il terzo non rende la dichiarazione e non compare all'udienza successiva, il credito indicato dal "
                     "creditore si considera non contestato.", R("cpc:548", "si considera non contestato"))],
    termini=[_EFFICACIA_PRECETTO],
    cosa_fare=["Individuare il terzo (datore di lavoro, ente pensionistico, banca): se ignoto, valutare la ricerca telematica dei beni.",
               "Notificare l'atto al terzo e al debitore; iscrivere a ruolo entro trenta giorni dalla consegna.",
               "Notificare al terzo l'avviso di iscrizione a ruolo prima dell'udienza."],
    dati=["titolo e precetto", "terzo debitore e tipo di credito", "residenza del debitore", "importo del credito"],
    extra=_extra_terzi,
)

OPPOSIZIONE_ESECUZIONE = Scheda(
    regola="es_opposizione_esecuzione", materia="esecuzione", nome="opposizione all'esecuzione già iniziata (art. 615, secondo comma)",
    segnali=(r"oppo|contest|sospension\w* dell esecuzione|sospendere l esecuzione",
             r"pignorament\w*[^.]{0,30}(?:gia|e stato|avvenut|eseguit|notificat)|esecuzione (?:gia )?iniziat|dopo il pignoramento|"
             r"beni pignorati|ci hanno pignorato|hanno pignorato|pignorat\w* (?:il|la|lo|i|le) |impignorabil|"
             r"sospension\w* dell esecuzione|titolo prescritto|procede con un titolo|diritto (?:del creditore )?a procedere"),
    esclusi=(r"\b617\b|precett|vizi\w* (?:di forma|formal)|nullit|irregolar|atti esecutivi|di mia proprieta|non (?:e|sono) del debitore|"
             r"proprieta (?:di|del) terz|intestat\w* a|terzo proprietario|619|decreto ingiuntiv|ingiunzion|\b650\b|"
             r"vero proprietario", *_NON_ESEC),
    punteggio=7,
    capito="Debitore che contesta il diritto del creditore a procedere, o la pignorabilità dei beni, a esecuzione già iniziata.",
    rimedio="ricorso al giudice dell'esecuzione (art. 615, secondo comma, c.p.c.) con istanza di sospensione",
    conclusione=[
        p("Quando l'esecuzione è iniziata, l'opposizione sul diritto a procedere e quella sulla pignorabilità dei beni si "
          "propongono con ricorso al giudice dell'esecuzione, che fissa l'udienza e il termine per la notifica.",
          R("cpc:615", "si propongono con ricorso al giudice dell'esecuzione stessa")),
        p("Nell'espropriazione l'opposizione è inammissibile se proposta dopo che è stata disposta la vendita o "
          "l'assegnazione, salvo fatti sopravvenuti o impossibilità non imputabile.",
          R("cpc:615", "dopo che e stata disposta la vendita o l'assegnazione")),
        p("Il giudice dell'esecuzione, concorrendo gravi motivi, sospende il processo con cauzione o senza; poi fissa un "
          "termine perentorio per introdurre il giudizio di merito.",
          R("cpc:624", "concorrendo gravi motivi, sospende, su istanza di parte, il processo con cauzione o senza"),
          R("cpc:616", "fissa un termine perentorio per l'introduzione del giudizio di merito")),
    ],
    avvertenze=["Se si contesta la regolarità formale di un atto (titolo, precetto, pignoramento) il rimedio è l'opposizione "
                "agli atti esecutivi entro venti giorni (art. 617 c.p.c.), non questa."],
    cosa_fare=["Verificare se è già stata disposta la vendita o l'assegnazione (inammissibilità).",
               "Ricorso al giudice dell'esecuzione con istanza di sospensione motivata (gravi motivi).",
               "Annotare il termine perentorio che il giudice fisserà per il merito."],
    dati=["atto di pignoramento e data", "motivo di opposizione (pagamento, titolo caducato, impignorabilità)", "stato della procedura"],
    extra=_giudice_esecuzione,
)

OPPOSIZIONE_TERZO = Scheda(
    regola="es_opposizione_terzo", materia="esecuzione", nome="opposizione di terzo all'esecuzione (art. 619)",
    segnali=(r"pignor|\b619\b|opposizione di terzo all esecuzione", r"di mia proprieta|esecuzione mobiliare|non (?:e|sono) del debitore|proprieta (?:di|del|della) (?:terz|madre|padre|moglie|marito|societa)|"
             r"intestat\w* a|terzo proprietario|opposizione di terzo|\b619\b|terzo che (?:e|e il) proprietario|appartengono a|"
             r"vero proprietario|il proprietario (?:dei|del|delle) ben"),
    esclusi=(r"intestat\w* a lui|intestat\w* al debitore|\(creditore", *_NON_ESEC), punteggio=8,
    capito="Terzo, estraneo al debito, i cui beni sono stati pignorati.",
    rimedio="ricorso di opposizione di terzo al giudice dell'esecuzione prima della vendita o dell'assegnazione",
    conclusione=[
        p("Il terzo che pretende la proprietà o altro diritto reale sui beni pignorati propone opposizione con ricorso al "
          "giudice dell'esecuzione, prima che sia disposta la vendita o l'assegnazione.",
          R("cpc:619", "il terzo che pretende avere la proprieta' o altro diritto reale sui beni pignorati"),
          R("cpc:619", "prima che sia disposta la vendita o l'assegnazione dei beni")),
        p("Se la vendita dei mobili non è sospesa o l'opposizione è proposta dopo la vendita, i diritti del terzo si fanno "
          "valere sulla somma ricavata.", R("cpc:620", "i diritti del terzo si fanno valere sulla somma ricavata")),
        p("Con l'opposizione si può chiedere la sospensione del processo esecutivo per gravi motivi.",
          R("cpc:624", "concorrendo gravi motivi, sospende, su istanza di parte, il processo con cauzione o senza")),
    ],
    cosa_fare=["Raccogliere la prova della proprietà con data certa anteriore al pignoramento (fatture, atti, libretto).",
               "Depositare subito il ricorso: dopo la vendita resta solo il diritto sul ricavato."],
    dati=["beni pignorati e verbale", "titolo di proprietà del terzo e sua data", "data fissata per la vendita"],
    extra=_giudice_esecuzione,
)

CONVERSIONE = Scheda(
    regola="es_conversione_pignoramento", materia="esecuzione", nome="conversione del pignoramento (art. 495)",
    segnali=(r"conversione del pignoramento|\b495\b|sostituire (?:i beni|le cose|il bene)[^.]{0,30}pignorat|"
             r"(?:pignor|vendita)[^.]{0,80}(?:a rate|rateizz|pagando a rate)|(?:a rate|rateizz)[^.]{0,80}(?:pignor|vendita)",),
    esclusi=_NON_ESEC, punteggio=6,
    capito="Debitore esecutato che vuole evitare la vendita sostituendo ai beni pignorati una somma di denaro, anche a rate.",
    rimedio="istanza di conversione del pignoramento al giudice dell'esecuzione con il deposito di almeno un sesto",
    conclusione=[
        p("Prima che sia disposta la vendita o l'assegnazione il debitore può chiedere di sostituire ai beni pignorati una "
          "somma pari al credito del pignorante e degli intervenuti, con capitale, interessi e spese, oltre alle spese di esecuzione.",
          R("cpc:495", "prima che sia disposta la vendita o l'assegnazione"),
          R("cpc:495", "sostituire alle cose o ai crediti pignorati una somma di denaro")),
        p("Con l'istanza va depositata, a pena di inammissibilità, una somma non inferiore a un sesto; per immobili e mobili il "
          "giudice può concedere rate mensili fino a quarantotto mesi.",
          R("cpc:495", "non inferiore a un sesto"), R("cpc:495", "quarantotto")),
    ],
    cosa_fare=["Verificare che la vendita non sia già stata disposta.",
               "Calcolare il credito del pignorante e degli intervenuti e versare almeno un sesto con l'istanza.",
               "Chiedere la rateizzazione motivando i giustificati motivi."],
    dati=["stato della procedura (vendita disposta o no)", "importo dei crediti e degli interventi", "capacità di pagamento"],
    extra=_giudice_esecuzione,
)

RICERCA_BENI = Scheda(
    regola="es_ricerca_beni", materia="esecuzione", nome="ricerca telematica dei beni da pignorare (art. 492-bis)",
    segnali=(r"492-?bis|ricerca telematica|ricerca (?:dei|con modalita telematiche dei) beni|anagrafe (?:dei rapporti|tributaria)|"
             r"(?:trovare|scoprire|sapere|individuare)[^.]{0,30}(?:i conti|i beni|dove lavora|che beni|quali beni)|"
             r"(?:che|quali) beni ha il debitore|non sappiamo (?:che|quali) beni",),
    esclusi=_NON_ESEC, punteggio=6,
    capito="Creditore che non conosce i beni del debitore e chiede la ricerca telematica nelle banche dati.",
    rimedio="istanza di ricerca telematica dei beni all'ufficiale giudiziario (o al presidente del tribunale se c'è pericolo nel ritardo)",
    conclusione=[
        p("Su istanza del creditore munito di titolo e precetto, l'ufficiale giudiziario del tribunale del luogo di "
          "residenza o sede del debitore procede alla ricerca con modalità telematiche dei beni da pignorare; l'istanza non "
          "si propone prima che sia decorso il termine del precetto.",
          R("cpc:492bis", "procede alla ricerca con modalita' telematiche dei beni da pignorare"),
          R("cpc:492bis", "prima che sia decorso il termine di cui all'articolo 482")),
        p("Se vi è pericolo nel ritardo, prima della notifica del precetto o del decorso del termine, la ricerca è autorizzata "
          "dal presidente del tribunale; dalla proposizione dell'istanza il termine di efficacia del precetto è sospeso.",
          R("cpc:492bis", "se vi e' pericolo nel ritardo, il presidente del tribunale"),
          R("cpc:492bis", "e' sospeso")),
    ],
    cosa_fare=["Notificare il precetto e attendere il termine ad adempiere (salvo urgenza).",
               "Depositare l'istanza con PEO del difensore e PEC per la dichiarazione del terzo.",
               "Con l'esito, scegliere il pignoramento (presso terzi, mobiliare, immobiliare)."],
    dati=["titolo e precetto notificato", "residenza o sede del debitore", "urgenza (pericolo nel ritardo)"],
    extra=_giudice_esecuzione,
)

OBBLIGHI_FARE = Scheda(
    regola="es_obblighi_fare", materia="esecuzione", nome="esecuzione degli obblighi di fare e non fare; misure coercitive",
    segnali=(r"obblig\w* di (?:fare|non fare)|\b612\b|614-?bis|demolir|rimozion|rimuover|ripristin|consegnare i documenti|"
             r"penale per ogni giorno|somma per ogni giorno|misur\w* coercitiv|astreinte",
             r"sentenz|condann|titolo|ordinanza|giudice|esecuzion|adempiment|ritardo|ricorso|\b612\b"),
    esclusi=(r"ordinanza di demolizione|permesso di costruire|\btar\b|comune ha", *_NON_ESEC), punteggio=6,
    capito="Titolo che condanna a fare o non fare qualcosa (demolire, rimuovere, consegnare) rimasto ineseguito.",
    rimedio="precetto e ricorso al giudice dell'esecuzione per le modalità dell'esecuzione; misura coercitiva per ogni giorno di ritardo",
    conclusione=[
        p("Se non è adempiuto un obbligo di fare, l'avente diritto può ottenere che sia eseguito a spese dell'obbligato.",
          R("cc:2931", "puo' ottenere che esso sia eseguito a spese dell'obbligato")),
        p("Dopo la notificazione del precetto si chiede con ricorso al giudice dell'esecuzione di determinare le modalità "
          "dell'esecuzione; il giudice designa l'ufficiale giudiziario e chi compie l'opera o la distrugge.",
          R("cpc:612", "dopo la notificazione del precetto"),
          R("cpc:612", "che siano determinate le modalita' dell'esecuzione")),
        p("Per gli obblighi diversi dal pagamento si può chiedere la somma dovuta per ogni violazione o ritardo: nel giudizio "
          "di cognizione o, se non chiesta, al giudice dell'esecuzione dopo il precetto.",
          R("cpc:614bis", "la somma di denaro dovuta dall'obbligato per ogni violazione o inosservanza"),
          R("cpc:614bis", "e' determinata dal giudice dell'esecuzione, su ricorso dell'avente diritto")),
    ],
    cosa_fare=["Notificare titolo e precetto con l'indicazione dell'obbligo.",
               "Ricorso ex art. 612 c.p.c. con la proposta delle modalità esecutive e, se utile, della misura coercitiva."],
    dati=["titolo e dispositivo", "obbligo da eseguire", "data di notifica del precetto", "luogo dell'esecuzione"],
    extra=_giudice_esecuzione,
)

OPPOSIZIONE_TARDIVA = Scheda(
    regola="mon_opposizione_tardiva", materia="monitorio", nome="opposizione tardiva a decreto ingiuntivo (art. 650)",
    segnali=(r"decreto ingiuntiv|ingiunzion|\bdi\b notificat|opposizione tardiva|\b650\b",
             r"tardiv|\b650\b|(?:termine|giorni)[^.]{0,50}(?:scadut|decors)|oltre il termine|scopert\w* solo|vecchio indirizzo|altro indirizzo|ricoverat|"
             r"mai ricevut|mai notificat|notifica\w* (?:era |e )?(?:nulla|irregolar|inesistent)|(?:40|quaranta) giorni (?:sono )?(?:scadut|passat|decors)|non (?:ne )?(?:ho|abbiamo|ha) avuto conoscenza"),
    esclusi=(r"ordinanza.ingiunzione|\(creditore",), punteggio=6,
    capito="Ingiunto che ha saputo del decreto dopo la scadenza del termine per l'opposizione.",
    rimedio="opposizione tardiva con atto di citazione davanti all'ufficio che ha emesso il decreto, provando l'incolpevole ignoranza",
    conclusione=[
        p("L'intimato può opporsi anche dopo il termine se prova di non aver avuto tempestiva conoscenza del decreto per "
          "irregolarità della notificazione o per caso fortuito o forza maggiore; l'esecutorietà può essere sospesa.",
          R("cpc:650", "se prova di non averne avuta tempestiva conoscenza per irregolarita' della notificazione")),
        p("L'opposizione tardiva non è più ammessa decorsi dieci giorni dal primo atto di esecuzione.",
          R("cpc:650", "non e' piu' ammessa decorsi dieci giorni dal primo atto di esecuzione")),
    ],
    scadenze=[Scadenza("opposizione tardiva al più tardi entro", 10, "giorni",
                       r"(?:primo atto di esecuzione|pignoramento|precetto)[^0-9]{0,30}(?:notificat\w*|eseguit\w*)?(?: il)?",
                       (R("cpc:650", "non e' piu' ammessa decorsi dieci giorni dal primo atto di esecuzione"),))],
    inquadramento=[p("Il termine di dieci giorni dal primo atto di esecuzione è un limite finale: iniziata l'esecuzione, "
                     "l'opposizione tardiva va proposta subito.",
                     R("cpc:650", "non e' piu' ammessa decorsi dieci giorni dal primo atto di esecuzione"))],
    cosa_fare=["Ricostruire come e dove è stato notificato il decreto (relata) e quando se ne è avuta conoscenza.",
               "Raccogliere la prova dell'impedimento (certificati di ricovero, residenza diversa, vizio della notifica).",
               "Citazione in opposizione con istanza di sospensione dell'esecutorietà."],
    dati=["decreto e relata di notifica", "data della conoscenza effettiva", "primo atto di esecuzione e data", "causa dell'impedimento"],
)

PROVVISORIA_ESECUZIONE = Scheda(
    regola="mon_provvisoria_esecuzione", materia="monitorio", nome="provvisoria esecuzione del decreto ingiuntivo (artt. 642 e 648)",
    segnali=(r"provvisori\w* esecuzion|esecuzione provvisoria|provvisoriamente esecutiv|esecutorieta|subito esecutiv|\b642\b|\b648\b|\b649\b",
             r"decret|ingiun|\b642\b|\b648\b|opposizion"),
    esclusi=(r"precett|\(creditore",), punteggio=6,
    capito="Esecutorietà del decreto ingiuntivo: concessione con il decreto o nel giudizio di opposizione, sospensione.",
    conclusione=[
        p("Con il decreto il giudice autorizza l'esecuzione provvisoria se il credito è fondato su cambiale, assegno o atto "
          "notarile, se vi è pericolo di grave pregiudizio nel ritardo o se il ricorrente produce documentazione sottoscritta "
          "dal debitore comprovante il diritto.",
          R("cpc:642", "cambiale, assegno bancario, assegno circolare"),
          R("cpc:642", "pericolo di grave pregiudizio nel ritardo"),
          R("cpc:642", "documentazione sottoscritta dal debitore")),
        p("Nel giudizio di opposizione il giudice può concederla in prima udienza se l'opposizione non è fondata su prova "
          "scritta o di pronta soluzione e deve concederla per le somme non contestate.",
          R("cpc:648", "provvedendo in prima udienza"),
          R("cpc:648", "limitatamente alle somme non contestate")),
        p("Su istanza dell'opponente, per gravi motivi, il giudice può sospendere l'esecuzione provvisoria concessa con il decreto.",
          R("cpc:649", "sospendere l'esecuzione provvisoria del decreto")),
    ],
    cosa_fare=["Nel ricorso: chiedere la provvisoria esecuzione indicando il fondamento (titolo cambiario, documento sottoscritto, pericolo).",
               "In opposizione: depositare l'istanza ex art. 648 per la prima udienza, anche anticipata se urgente."],
    dati=["documenti a fondamento del credito", "pericolo nel ritardo", "somme contestate e non contestate"],
)

# Pignoramento presso terzi e ricerca dei beni hanno anche pignoramento_terzi e ricerca_beni (esecuzione.py), che vincono a
# parità; immobiliare e opposizione all'esecuzione iniziata hanno punteggio 7 perché pignoramento_terzi scatta anche su
# «banca» (ipoteca) e su «sospensione» (contiene «pension»).
SCHEDE = (OPPOSIZIONE_TERZO, OPPOSIZIONE_ESECUZIONE, CONVERSIONE, RICERCA_BENI, OBBLIGHI_FARE, PIGNORAMENTO_TERZI,
          PIGNORAMENTO_IMMOBILIARE, PIGNORAMENTO_MOBILIARE, OPPOSIZIONE_TARDIVA, PROVVISORIA_ESECUZIONE)
