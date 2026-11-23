"""Bancario e finanziario, società, crisi d'impresa e sovraindebitamento.

Base normativa (testo vigente): art. 644 c.p.; art. 2 l. 108/1996; artt. 1815, 1832, 2033 c.c.; artt. 119, 120, 125,
128-bis d.lgs. 385/1993 (TUB); art. 32-ter d.lgs. 58/1998 (TUF); art. 5 d.lgs. 28/2010; artt. 2377, 2378, 2379,
2393, 2394, 2437, 2437-bis, 2473, 2476, 2479-ter c.c.; artt. 12, 17, 18, 44, 67, 69, 84, 268, 278, 282, 283
d.lgs. 14/2019 (CCII).
"""
from __future__ import annotations

from .schede import R, Scheda, p

_BANCA = r"banca|bancari|istituto di credito|finanziari|mutuo|fido|conto corrente|leasing|finanziamento|prestito|intermediario"
_MEDIAZIONE_BANCARIA = p("Nelle controversie su contratti bancari e finanziari la mediazione è condizione di procedibilità.",
                         R("dlgs28:5", "bancari e finanziari"))

USURA = Scheda(
    regola="ban_usura", materia="bancario e finanziario", nome="usura bancaria",
    segnali=(r"usur|tasso soglia|antiusura|\bteg\b|tegm",), alcuni=(_BANCA, r"interess"), punteggio=6,
    capito="Contratto di credito con interessi che superano la soglia antiusura.",
    rimedio="azione di accertamento della nullità della clausola degli interessi e di ripetizione (mediazione preventiva obbligatoria)",
    conclusione=[
        p("Sono usurari gli interessi oltre il limite di legge e, anche se inferiori, quelli sproporzionati rispetto alla "
          "prestazione in relazione al tasso medio per operazioni simili.",
          R("cp:644", "la legge stabilisce il limite oltre il quale gli interessi sono sempre usurari")),
        p("Il limite è il tasso effettivo globale medio della categoria di operazioni rilevato trimestralmente, aumentato di "
          "un quarto e di un margine di ulteriori quattro punti.",
          R("l108:2", "rileva trimestralmente il tasso effettivo globale medio"), R("l108:2", "aumentato di un quarto")),
        p("Se sono convenuti interessi usurari la clausola è nulla e non sono dovuti interessi.",
          R("cc:1815", "se sono convenuti interessi usurari, la clausola e' nulla e non sono dovuti interessi")),
    ],
    procedibilita=[_MEDIAZIONE_BANCARIA],
    dati=["contratto e data di stipula", "TEG pattuito e TEGM del trimestre di riferimento", "piano di ammortamento", "perizia econometrica"],
    dubbi=["Usura sopravvenuta e rilevanza degli interessi di mora: verificare l'orientamento della Cassazione nell'archivio."],
)

ANATOCISMO = Scheda(
    regola="ban_anatocismo", materia="bancario e finanziario", nome="anatocismo e ripetizione dell'indebito bancario",
    segnali=(r"anatocism|capitalizz|interessi (?:sugli|su) interessi|ripetizione d\w* ?indebit|rimesse solutori|ricalcolo del conto",),
    alcuni=(_BANCA, r"interess"), punteggio=6,
    capito="Correntista che contesta la capitalizzazione degli interessi e chiede la restituzione di quanto addebitato.",
    rimedio="mediazione e poi citazione per accertamento del saldo e ripetizione dell'indebito",
    conclusione=[
        p("Nei conti correnti la periodicità di conteggio degli interessi debitori e creditori è la stessa e comunque non "
          "inferiore a un anno; gli interessi debitori non producono ulteriori interessi, salvo quelli di mora, e si "
          "calcolano solo sulla sorte capitale.",
          R("tub:120", "comunque non inferiore ad un anno"), R("tub:120", "non possono produrre interessi ulteriori, salvo quelli di mora")),
        p("Chi ha eseguito un pagamento non dovuto ha diritto di ripetere ciò che ha pagato.",
          R("cc:2033", "chi ha eseguito un pagamento non dovuto ha diritto di ripetere")),
    ],
    procedibilita=[_MEDIAZIONE_BANCARIA],
    termini=[p("Prescrizione decennale, che per le rimesse solutorie decorre da ciascun pagamento e per le altre dalla chiusura del conto.",
               R("cc:2946", "si estinguono per prescrizione con il decorso di dieci anni"))],
    dati=["estratti conto completi dall'apertura", "contratto e affidamenti", "data di chiusura del conto", "perizia contabile"],
)

ESTRATTI = Scheda(
    regola="ban_documenti_estratti", materia="bancario e finanziario", nome="estratti conto e documentazione bancaria (art. 119 TUB)",
    segnali=(r"estratt\w* conto|documentazione bancaria|copia del contratto|\b119\b|contestar\w*[^.]{0,30}estratto",),
    alcuni=(_BANCA,), punteggio=6,
    capito="Richiesta di documentazione alla banca o contestazione degli estratti conto.",
    rimedio="richiesta scritta ex art. 119, comma 4, TUB; contestazione scritta degli estratti conto",
    conclusione=[
        p("Il cliente ha diritto di ottenere, a proprie spese e comunque non oltre novanta giorni, copia della documentazione "
          "sulle operazioni degli ultimi dieci anni; gli si possono addebitare solo i costi di produzione.",
          R("tub:119", "non oltre novanta giorni"), R("tub:119", "negli ultimi dieci anni")),
        p("In mancanza di opposizione scritta gli estratti conto si intendono approvati trascorsi sessanta giorni dal "
          "ricevimento; l'approvazione non preclude l'impugnazione per errori di scritturazione o di calcolo, omissioni o "
          "duplicazioni, entro sei mesi.",
          R("tub:119", "trascorsi sessanta giorni dal ricevimento"),
          R("cc:1832", "per errori di scritturazione o di calcolo"), R("cc:1832", "entro sei mesi")),
    ],
    dati=["rapporti e periodo", "data della richiesta e risposta della banca"],
)

ABF = Scheda(
    regola="ban_abf", materia="bancario e finanziario", nome="Arbitro Bancario Finanziario",
    segnali=(r"\babf\b|arbitro bancario",), punteggio=7,
    capito="Risoluzione stragiudiziale di una controversia con la banca davanti all'ABF.",
    rimedio="reclamo alla banca e, senza risposta soddisfacente, ricorso all'Arbitro Bancario Finanziario",
    conclusione=[
        p("Banche e intermediari aderiscono a sistemi di risoluzione stragiudiziale delle controversie con la clientela; il "
          "ricorso non pregiudica gli altri mezzi di tutela e vale come condizione di procedibilità alternativa alla mediazione.",
          R("tub:128bis", "aderiscono a sistemi di risoluzione stragiudiziale delle controversie con la clientela"),
          R("tub:128bis", "articolo 5, comma 1, del decreto legislativo 4 marzo 2010, n. 28")),
    ],
    dubbi=["Limiti di valore, termini dal reclamo ed effetti della decisione sono fissati dalle disposizioni della Banca "
           "d'Italia e del CICR, non presenti nella biblioteca: verificarli sul sito dell'ABF prima di indicarli."],
    dati=["reclamo alla banca e data", "risposta della banca", "importo e oggetto della controversia"],
)

ACF = Scheda(
    regola="ban_acf", materia="bancario e finanziario", nome="Arbitro per le Controversie Finanziarie",
    segnali=(r"\bacf\b|arbitro per le controversie finanziarie|arbitro consob",), punteggio=7,
    capito="Controversia con un intermediario finanziario sugli obblighi di diligenza, correttezza e informazione.",
    rimedio="reclamo all'intermediario e ricorso all'ACF presso la Consob",
    conclusione=[p("I soggetti vigilati dalla Consob e i consulenti finanziari aderiscono a sistemi di risoluzione stragiudiziale "
                   "delle controversie con gli investitori non professionali.",
                   R("tuf:32ter", "aderiscono a sistemi di risoluzione stragiudiziale delle controversie con gli investitori"))],
    dubbi=["Limite di valore e termini sono nel regolamento Consob dell'ACF, non presente nella biblioteca: verificarli."],
    dati=["investimento e profilatura", "reclamo e data", "danno"],
)

CENTRALE_RISCHI = Scheda(
    regola="ban_segnalazione_centrale_rischi", materia="bancario e finanziario", nome="segnalazione illegittima in Centrale rischi o nei sistemi di informazione creditizia",
    segnali=(r"centrale (?:dei )?rischi|\bcrif\b|segnalazion\w*[^.]{0,40}(?:sofferenz|banca dati|cattivo pagatore)|cattivo pagatore",),
    punteggio=7,
    capito="Cliente segnalato come cattivo pagatore senza preavviso o per un credito contestato.",
    rimedio="diffida alla banca per la cancellazione; ricorso d'urgenza o azione risarcitoria; reclamo al Garante privacy per i sistemi privati",
    conclusione=[
        p("I finanziatori informano preventivamente il consumatore la prima volta che segnalano informazioni negative a una "
          "banca dati e lo informano della registrazione entro trenta giorni.",
          R("tub:125", "informano preventivamente il consumatore la prima volta che segnalano"),
          R("tub:125", "entro trenta giorni dalla medesima registrazione")),
    ],
    dati=["data e contenuto della segnalazione", "preavviso ricevuto o no", "stato del credito (contestato, pagato)", "danno"],
)

_SOCIETA = r"azione sociale|mala gestio|societa|\bsrl\b|s\.r\.l|\bspa\b|s\.p\.a|socio|soci\b|assemblea dei soci|amministrator\w* (?:unico|della societa)"

DELIBERE_SOCIETARIE = Scheda(
    regola="soc_impugnazione_delibere", materia="società e impresa", nome="impugnazione delle delibere societarie",
    segnali=(r"delibera|deliberazion|decisione dei soci", r"\bsrl\b|s\.r\.l|\bspa\b|s\.p\.a|socio|soci\b|societa|bilancio|aumento di capitale"),
    esclusi=(r"condomin",), punteggio=6,
    capito="Socio che contesta una delibera assembleare o una decisione dei soci.",
    rimedio="atto di citazione davanti al tribunale delle imprese del luogo della sede, con eventuale istanza di sospensione",
    conclusione=[
        p("Nella s.p.a. le delibere non conformi a legge o statuto sono impugnate da soci assenti, dissenzienti o astenuti "
          "titolari della quota minima, entro novanta giorni dalla data, dall'iscrizione o dal deposito nel registro delle imprese.",
          R("cc:2377", "possono essere impugnate dai soci assenti, dissenzienti od astenuti"),
          R("cc:2377", "nel termine di novanta giorni dalla data della deliberazione")),
        p("Nei casi di mancata convocazione, mancanza del verbale, oggetto impossibile o illecito la delibera può essere "
          "impugnata da chiunque vi abbia interesse entro tre anni.",
          R("cc:2379", "entro tre anni dalla sua iscrizione o deposito nel registro delle imprese")),
        p("Nella s.r.l. le decisioni dei soci si impugnano entro novanta giorni dalla trascrizione nel libro delle decisioni.",
          R("cc:2479ter", "entro novanta giorni dalla loro trascrizione nel libro delle decisioni dei soci")),
        p("L'impugnazione si propone con citazione davanti al tribunale del luogo della sede della società.",
          R("cc:2378", "con atto di citazione davanti al tribunale del luogo dove la societa' ha sede")),
    ],
    dati=["tipo di società", "delibera e data di iscrizione o trascrizione", "partecipazione del socio e voto espresso", "vizio"],
)

RESPONSABILITA_AMMINISTRATORI = Scheda(
    regola="soc_responsabilita_amministratori", materia="società e impresa", nome="azione di responsabilità contro gli amministratori",
    segnali=(r"amministrator", r"responsabilit|distratt|distrazion|mala gestio|danni alla societa|azione sociale|creditori sociali"),
    alcuni=(_SOCIETA,), esclusi=(r"condomin|amministratore di sostegno",), punteggio=6,
    capito="Azione della società, dei soci o dei creditori contro gli amministratori per i danni da mala gestione.",
    rimedio="azione sociale di responsabilità (delibera assembleare o, nella s.r.l., anche del singolo socio); azione dei creditori sociali",
    conclusione=[
        p("Nella s.p.a. l'azione sociale è promossa in seguito a deliberazione dell'assemblea ed è esercitabile entro cinque "
          "anni dalla cessazione dell'amministratore dalla carica.",
          R("cc:2393", "e' promossa in seguito a deliberazione dell'assemblea"),
          R("cc:2393", "entro cinque anni dalla cessazione dell'amministratore dalla carica")),
        p("Gli amministratori rispondono verso i creditori sociali per l'inosservanza degli obblighi di conservazione "
          "dell'integrità del patrimonio; i creditori agiscono quando il patrimonio è insufficiente.",
          R("cc:2394", "conservazione dell'integrita' del patrimonio sociale"),
          R("cc:2394", "quando il patrimonio sociale risulta insufficiente")),
        p("Nella s.r.l. gli amministratori sono solidalmente responsabili verso la società e l'azione può essere promossa "
          "anche da ciascun socio.", R("cc:2476", "sono solidalmente responsabili verso la societa'")),
    ],
    dati=["tipo di società", "condotte e danno", "data di cessazione dalla carica", "delibera assembleare o legittimazione del socio"],
)

RECESSO_SOCIO = Scheda(
    regola="soc_recesso_socio", materia="società e impresa", nome="recesso del socio",
    segnali=(r"recess|reced|uscire dalla societa|uscir\w*|liquidazione della quota|liquida la quota", r"soci|societa|\bsrl\b|\bspa\b|quota|azioni"),
    esclusi=(r"conduttor|locazion|contratto di (?:lavoro|fornitura)|consumator",), punteggio=7,
    capito="Socio che vuole recedere dalla società e ottenere la liquidazione della partecipazione.",
    rimedio="dichiarazione di recesso nelle forme e nei termini di legge o di statuto",
    conclusione=[
        p("Nella s.p.a. recedono i soci che non hanno concorso alle delibere su modifica dell'oggetto sociale, "
          "trasformazione, revoca della liquidazione, criteri di valutazione delle azioni e diritti di voto.",
          R("cc:2437", "i soci che non hanno concorso alle deliberazioni riguardanti")),
        p("Il recesso si esercita con raccomandata spedita entro quindici giorni dall'iscrizione della delibera nel registro "
          "delle imprese, o entro trenta giorni dalla conoscenza del fatto diverso da una delibera.",
          R("cc:2437bis", "entro quindici giorni dall'iscrizione nel registro delle imprese della delibera"),
          R("cc:2437bis", "entro trenta giorni dalla sua conoscenza")),
        p("Nella s.r.l. l'atto costitutivo determina quando il socio può recedere; il recesso spetta comunque a chi non ha "
          "consentito al cambiamento dell'oggetto o del tipo, a fusione o scissione e alle altre modifiche di legge.",
          R("cc:2473", "l'atto costitutivo determina quando il socio puo' recedere")),
    ],
    dati=["tipo di società e statuto", "fatto o delibera che legittima il recesso e data di iscrizione", "partecipazione"],
)

_CRISI = r"crisi d impresa|crisi della societa|insolvenz|sovraindebitat|sovraindebitament|\bocc\b|debiti che non riesc|non riesce piu a pagare"

COMPOSIZIONE_NEGOZIATA = Scheda(
    regola="crisi_composizione_negoziata", materia="crisi d'impresa e sovraindebitamento", nome="composizione negoziata della crisi",
    segnali=(r"composizione negoziata|esperto (?:indipendente|della composizione)|misure protettive",), punteggio=7,
    capito="Imprenditore in squilibrio che chiede la nomina dell'esperto per negoziare il risanamento.",
    rimedio="istanza di nomina dell'esperto sulla piattaforma telematica della camera di commercio, con eventuali misure protettive",
    conclusione=[
        p("L'imprenditore commerciale o agricolo in squilibrio che rende probabile la crisi o l'insolvenza, se il risanamento "
          "è ragionevolmente perseguibile, chiede la nomina di un esperto al segretario generale della camera di commercio.",
          R("ccii:12", "puo' chiedere la nomina di un esperto"), R("ccii:12", "risulta ragionevolmente perseguibile il risanamento dell'impresa")),
        p("L'istanza si presenta sulla piattaforma telematica con bilanci e documenti; con essa o dopo si possono chiedere "
          "misure protettive del patrimonio, escluse per i crediti dei lavoratori.",
          R("ccii:17", "e' presentata tramite la piattaforma telematica"),
          R("ccii:18", "sono esclusi dalle misure protettive i diritti di credito dei lavoratori")),
    ],
    dati=["situazione economico-finanziaria e bilanci", "debiti e creditori principali", "piano di risanamento", "esecuzioni in corso"],
)

CONCORDATO = Scheda(
    regola="crisi_concordato_preventivo", materia="crisi d'impresa e sovraindebitamento", nome="concordato preventivo",
    segnali=(r"concordato (?:preventivo|in continuita|liquidatorio|con riserva|in bianco)|\bconcordato\b",),
    esclusi=(r"concordato minore",), punteggio=6,
    capito="Imprenditore in crisi o insolvente che propone ai creditori un concordato preventivo.",
    rimedio="ricorso per concordato preventivo (anche con riserva) al tribunale del centro degli interessi principali",
    conclusione=[
        p("L'imprenditore in crisi o insolvente può proporre un concordato che soddisfi i creditori in misura non inferiore "
          "alla liquidazione giudiziale, con continuità aziendale, liquidazione, assuntore o altra forma.",
          R("ccii:84", "in misura non inferiore a quella realizzabile in caso di liquidazione giudiziale")),
        p("Con la domanda con riserva il tribunale fissa un termine fra trenta e sessanta giorni, prorogabile fino a ulteriori "
          "sessanta, per depositare proposta, piano e attestazione.",
          R("ccii:44", "compreso tra trenta e sessanta giorni")),
    ],
    dati=["stato di crisi o insolvenza", "piano e attestatore", "classi di creditori", "continuità o liquidazione"],
)

LIQUIDAZIONE_CONTROLLATA = Scheda(
    regola="crisi_liquidazione_controllata", materia="crisi d'impresa e sovraindebitamento", nome="liquidazione controllata",
    segnali=(r"liquidazione controllata|liquidazione del patrimonio",), punteggio=7,
    capito="Debitore sovraindebitato che chiede la liquidazione dei beni per liberarsi dei debiti.",
    rimedio="ricorso al tribunale per l'apertura della liquidazione controllata, con la relazione dell'OCC",
    conclusione=[
        p("Il debitore in sovraindebitamento può domandare con ricorso l'apertura della liquidazione controllata dei suoi "
          "beni; se è insolvente la domanda può proporla anche un creditore, ma non per debiti scaduti inferiori a cinquantamila euro.",
          R("ccii:268", "l'apertura di una procedura di liquidazione controllata dei suoi beni"),
          R("ccii:268", "inferiore a euro cinquantamila")),
        p("L'esdebitazione opera alla chiusura o comunque decorsi tre anni dall'apertura, con decreto del tribunale.",
          R("ccii:282", "decorsi tre anni dalla sua apertura")),
    ],
    dati=["debiti e creditori", "beni e redditi", "relazione dell'OCC", "nucleo familiare"],
)

RISTRUTTURAZIONE_CONSUMATORE = Scheda(
    regola="crisi_ristrutturazione_consumatore", materia="crisi d'impresa e sovraindebitamento", nome="ristrutturazione dei debiti del consumatore",
    segnali=(r"ristrutturazione dei debiti|piano del consumatore|piano di ristrutturazione",), alcuni=(r"consumator|sovraindebit|\bocc\b|debit",),
    punteggio=7,
    capito="Consumatore sovraindebitato che propone un piano di ristrutturazione dei debiti con l'OCC.",
    rimedio="domanda di ristrutturazione dei debiti tramite l'OCC al tribunale",
    conclusione=[
        p("Il consumatore sovraindebitato, con l'ausilio dell'OCC, può proporre un piano di ristrutturazione a contenuto libero, "
          "anche con soddisfacimento parziale e differenziato dei crediti.",
          R("ccii:67", "con l'ausilio dell'OCC, puo' proporre ai creditori un piano di ristrutturazione dei debiti")),
        p("Non può accedervi chi è stato esdebitato nei cinque anni precedenti, ne ha già beneficiato due volte o ha "
          "determinato il sovraindebitamento con colpa grave, malafede o frode.",
          R("ccii:69", "con colpa grave, malafede o frode")),
    ],
    dati=["creditori e somme dovute", "patrimonio e redditi degli ultimi tre anni", "atti straordinari degli ultimi cinque anni", "cause del sovraindebitamento"],
)

ESDEBITAZIONE = Scheda(
    regola="crisi_esdebitazione", materia="crisi d'impresa e sovraindebitamento", nome="esdebitazione (anche dell'incapiente)",
    segnali=(r"esdebit|incapient",), punteggio=7,
    capito="Liberazione dai debiti residui dopo la liquidazione o per il debitore incapiente.",
    rimedio="istanza di esdebitazione al tribunale (per l'incapiente tramite l'OCC)",
    conclusione=[
        p("L'esdebitazione libera dai debiti e rende inesigibili i crediti rimasti insoddisfatti nella liquidazione giudiziale o controllata.",
          R("ccii:278", "comporta la inesigibilita' dal debitore dei crediti rimasti insoddisfatti")),
        p("Il debitore persona fisica meritevole che non può offrire alcuna utilità ai creditori accede all'esdebitazione una "
          "sola volta; il debito torna esigibile se entro tre anni sopravvengono utilità che consentono un soddisfacimento utile.",
          R("ccii:283", "puo' accedere all'esdebitazione solo per una volta"), R("ccii:283", "entro tre anni dal decreto del giudice")),
    ],
    dati=["procedura chiusa o in corso", "redditi e patrimonio", "meritevolezza", "precedenti esdebitazioni"],
)

SCHEDE = (USURA, ANATOCISMO, ESTRATTI, ABF, ACF, CENTRALE_RISCHI, DELIBERE_SOCIETARIE, RESPONSABILITA_AMMINISTRATORI,
          RECESSO_SOCIO, COMPOSIZIONE_NEGOZIATA, CONCORDATO, LIQUIDAZIONE_CONTROLLATA, RISTRUTTURAZIONE_CONSUMATORE, ESDEBITAZIONE)
