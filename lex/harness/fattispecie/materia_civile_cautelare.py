"""Civile ordinario, cautelare e possessorio: citazione, memorie integrative, appello, cassazione, revocazione,
opposizione di terzo, regolamento di competenza; provvedimento d'urgenza, sequestro (domanda), ATP e consulenza tecnica
preventiva, istruzione preventiva, reclamo cautelare; reintegrazione, manutenzione, denuncia di nuova opera e di danno temuto.

Base normativa (testo vigente): artt. 21, 42, 47, 163, 163-bis, 165, 166, 171-bis, 171-ter, 325, 326, 327, 339, 341,
342, 360, 365, 366, 369, 395, 398, 404, 405, 669-ter, 669-octies, 669-terdecies, 671, 688, 692, 693, 696, 696-bis,
700, 703 c.p.c.; artt. 1168, 1170, 1171, 1172 c.c.; art. 1 l. 742/1969.
"""
from __future__ import annotations

from .schede import R, Scadenza, Scheda, p

_NON_CIVILE = r"lavorator|rapporto di lavoro|datore di lavoro|giudice del lavoro|rito del lavoro|causa di lavoro|licenzia|penal|imputat|reato|tributar|\btar\b|amministrativ|cartella|agenzia delle entrate|\binps\b"
_FERIALE = p("I termini sono sospesi dal 1° al 31 agosto.", R("l742:1", "giurisdizioni ordinarie ed a quelle amministrative"))
_NOTIFICA = r"(?:sentenza|decisione)[^0-9]{0,40}(?:notificat\w*|comunicat\w*)(?: il)?"
_PUBBLICAZIONE = r"(?:pubblicat\w*|depositat\w*)(?: il)?"

CITAZIONE = Scheda(
    regola="civ_citazione", materia="civile ordinario", nome="atto di citazione (rito ordinario di cognizione)",
    segnali=(r"atto di citazione|\bcitazione\b|citare in giudizio|atto introduttivo|termini? a comparire|fare causa|"
             r"prima udienza[^.]{0,40}notifica",),
    esclusi=(_NON_CIVILE, r"appell|opposizion|caparra|delibera|sfratt|decreto ingiuntiv|precett|separazion|divorzi|"
             r"revocazion|cassazion|semplificat|281-?decies|comparsa|memori"), punteggio=3,
    capito="Introduzione di una causa civile davanti al tribunale con atto di citazione.",
    rimedio="atto di citazione a udienza fissa notificato al convenuto, con iscrizione a ruolo",
    conclusione=[
        p("La domanda si propone con citazione a comparire a udienza fissa; l'atto deve contenere l'ufficio, le parti con "
          "codice fiscale e PEC del convenuto, l'oggetto, i fatti e gli elementi di diritto, le prove e gli avvertimenti di legge.",
          R("cpc:163", "mediante citazione a comparire a udienza fissa")),
        p("Fra notificazione e udienza devono intercorrere almeno centoventi giorni liberi (centocinquanta se si notifica "
          "all'estero); l'attore si costituisce entro dieci giorni dalla notificazione.",
          R("cpc:163bis", "non minori di centoventi giorni"), R("cpc:165", "entro dieci giorni dalla notificazione")),
        p("Dopo la costituzione del convenuto il giudice compie le verifiche preliminari; seguono le tre memorie integrative "
          "a quaranta, venti e dieci giorni prima dell'udienza.",
          R("cpc:171bis", "verifica d'ufficio la regolarita' del contraddittorio"),
          R("cpc:171ter", "almeno quaranta giorni prima dell'udienza")),
    ],
    procedibilita=[p("Verificare se la materia richiede la mediazione obbligatoria o la negoziazione assistita prima della causa.",
                     R("dlgs28:5", "condizione di procedibilita"), R("dl132:3", "condizione di procedibilita"))],
    cosa_fare=["Individuare giudice per valore e materia e foro competente.",
               "Verificare mediazione o negoziazione obbligatoria.",
               "Indicare nell'atto tutti i mezzi di prova e i documenti; calcolare i 120 giorni liberi."],
    dati=["parti, codici fiscali e PEC", "oggetto e valore", "fatti e documenti", "luogo di residenza o sede del convenuto"],
)

MEMORIE = Scheda(
    regola="civ_memorie_171ter", materia="civile ordinario", nome="memorie integrative (art. 171-ter c.p.c.)",
    segnali=(r"171-?ter|memorie integrative|prima memoria|seconda memoria|terza memoria|tre memorie",),
    esclusi=(_NON_CIVILE,), punteggio=6,
    capito="Termini e contenuto delle tre memorie integrative del rito ordinario.",
    rimedio="deposito delle memorie integrative a quaranta, venti e dieci giorni prima dell'udienza di prima comparizione",
    conclusione=[p("Le parti, a pena di decadenza, possono: almeno quaranta giorni prima dell'udienza precisare o modificare "
                   "domande ed eccezioni e proporre quelle conseguenti alle difese avversarie; almeno venti giorni prima "
                   "replicare e indicare i mezzi di prova e le produzioni; almeno dieci giorni prima replicare alle eccezioni "
                   "nuove e indicare la prova contraria.",
                   R("cpc:171ter", "a pena di decadenza"), R("cpc:171ter", "almeno quaranta giorni prima dell'udienza"),
                   R("cpc:171ter", "almeno venti giorni prima dell'udienza"), R("cpc:171ter", "almeno dieci giorni prima dell'udienza"))],
    termini=[_FERIALE],
    scadenze=[Scadenza("prima memoria entro", 40, "giorni", r"udienza(?: [a-z ]{0,30})?(?: fissata| e fissata)?(?: al| il| per il)?",
                       (R("cpc:171ter", "almeno quaranta giorni prima dell'udienza"),), modello="CIV_MEMORIA_171_TER_1"),
              Scadenza("seconda memoria entro", 20, "giorni", r"udienza(?: [a-z ]{0,30})?(?: fissata| e fissata)?(?: al| il| per il)?",
                       (R("cpc:171ter", "almeno venti giorni prima dell'udienza"),), modello="CIV_MEMORIA_171_TER_2"),
              Scadenza("terza memoria entro", 10, "giorni", r"udienza(?: [a-z ]{0,30})?(?: fissata| e fissata)?(?: al| il| per il)?",
                       (R("cpc:171ter", "almeno dieci giorni prima dell'udienza"),), modello="CIV_MEMORIA_171_TER_3")],
    avvertenze=["I termini si calcolano a ritroso dalla data dell'udienza eventualmente differita con il decreto dell'art. 171-bis."],
    dati=["data dell'udienza di prima comparizione (o differita con il decreto delle verifiche preliminari)"],
)

APPELLO = Scheda(
    regola="civ_appello", materia="civile ordinario", nome="appello civile",
    segnali=(r"appell", r"sentenz|tribunale|giudice di pace|corte|motivi|inammissibil|atto di appello"), esclusi=(_NON_CIVILE, r"cassazion|revocazion"),
    punteggio=4,
    capito="Impugnazione con appello di una sentenza civile di primo grado.",
    rimedio="atto di citazione in appello con motivi specifici per capo",
    conclusione=[
        p("L'appello contro le sentenze del giudice di pace e del tribunale si propone rispettivamente al tribunale e alla "
          "corte d'appello nella cui circoscrizione ha sede il giudice che ha pronunciato la sentenza.",
          R("cpc:341", "si propone rispettivamente al tribunale ed alla corte di appello")),
        p("L'appello si propone con citazione motivata in modo chiaro, sintetico e specifico: per ciascun motivo, a pena di "
          "inammissibilità, va individuato il capo impugnato con le censure in fatto e le violazioni di legge.",
          R("cpc:342", "deve essere motivato in modo chiaro, sintetico e specifico"),
          R("cpc:342", "a pena di inammissibilita'")),
    ],
    termini=[p("Termine breve: trenta giorni dalla notificazione della sentenza; senza notificazione, sei mesi dalla "
               "pubblicazione.", R("cpc:325", "e' di trenta giorni"), R("cpc:326", "decorrono dalla notificazione della sentenza"),
               R("cpc:327", "dalla pubblicazione della sentenza")), _FERIALE],
    scadenze=[Scadenza("appello entro", 30, "giorni", _NOTIFICA, (R("cpc:325", "e' di trenta giorni"),), modello="CIV_APPELLO_BREVE"),
              Scadenza("appello (termine lungo) entro", 6, "mesi", _PUBBLICAZIONE, (R("cpc:327", "dalla pubblicazione della sentenza"),),
                       modello="CIV_APPELLO_LUNGO")],
    avvertenze=["Nel rito del lavoro l'appello si propone con ricorso entro trenta giorni senza sospensione feriale (art. 434 c.p.c.)."],
    cosa_fare=["Verificare data di pubblicazione e di notificazione della sentenza.",
               "Individuare i capi da impugnare e per ciascuno le censure in fatto e in diritto.",
               "Termine a comparire in appello: novanta giorni liberi."],
    dati=["sentenza, data di pubblicazione e di notificazione", "capi impugnati", "rito (ordinario, lavoro, locazione)"],
)

CASSAZIONE = Scheda(
    regola="civ_cassazione", materia="civile ordinario", nome="ricorso per cassazione civile",
    segnali=(r"cassazion",), alcuni=(r"ricorr|ricorso|impugn|termin|motiv|sentenz",),
    esclusi=(_NON_CIVILE, r"regolamento di competenza|revocazion"), punteggio=4,
    capito="Ricorso per cassazione contro una sentenza civile d'appello o in unico grado.",
    rimedio="ricorso per cassazione sottoscritto da avvocato abilitato con procura speciale",
    conclusione=[
        p("Le sentenze d'appello o in unico grado si impugnano per motivi di giurisdizione, competenza, violazione o falsa "
          "applicazione di norme di diritto, nullità della sentenza o del procedimento, omesso esame di un fatto decisivo "
          "discusso fra le parti.", R("cpc:360", "per violazione o falsa applicazione di norme di diritto"),
          R("cpc:360", "per omesso esame circa un fatto decisivo")),
        p("Il ricorso è sottoscritto, a pena di inammissibilità, da un avvocato iscritto nell'albo speciale munito di procura "
          "speciale e deve contenere la chiara esposizione dei fatti e dei motivi con gli atti su cui ciascuno si fonda.",
          R("cpc:365", "da un avvocato iscritto nell'apposito albo, munito di procura speciale"),
          R("cpc:366", "a pena di inammissibilita'")),
        p("Il ricorso si deposita, a pena di improcedibilità, entro venti giorni dall'ultima notificazione.",
          R("cpc:369", "nel termine di giorni venti dall'ultima notificazione")),
    ],
    termini=[p("Termine breve: sessanta giorni dalla notificazione della sentenza; senza notificazione, sei mesi dalla pubblicazione.",
               R("cpc:325", "e' di giorni sessanta"), R("cpc:327", "dalla pubblicazione della sentenza")), _FERIALE],
    scadenze=[Scadenza("ricorso per cassazione entro", 60, "giorni", _NOTIFICA, (R("cpc:325", "e' di giorni sessanta"),),
                       modello="CIV_CASSAZIONE_BREVE")],
    dati=["sentenza impugnata e date", "motivi per numero dell'art. 360", "difensore cassazionista e procura speciale"],
)

REVOCAZIONE = Scheda(
    regola="civ_revocazione", materia="civile ordinario", nome="revocazione della sentenza",
    segnali=(r"revocazion|revocatori\w* (?:errore|motivo)|errore revocatorio|\b395\b|document\w* (?:falsi|decisiv\w*)[^.]{0,60}(?:sentenz|nascost)|"
             r"sentenz\w*[^.]{0,60}(?:documenti falsi|falsita|dolo della controparte)",),
    esclusi=(_NON_CIVILE, r"revocazione (?:dell|della) (?:ordinanza|decreto|patente|permesso)|azione revocatoria"), punteggio=6,
    capito="Revocazione di una sentenza d'appello o in unico grado per i casi tassativi dell'art. 395 c.p.c.",
    rimedio="citazione per revocazione davanti allo stesso giudice che ha pronunciato la sentenza",
    conclusione=[
        p("Le sentenze d'appello o in unico grado si impugnano per revocazione nei casi tassativi: dolo di una parte, prove "
          "false, documenti decisivi ritrovati, errore di fatto risultante dagli atti, contrasto con precedente giudicato, dolo del giudice.",
          R("cpc:395", "possono essere impugnate per revocazione"), R("cpc:395", "documenti decisivi")),
        p("Si propone con citazione davanti allo stesso giudice, indicando a pena d'inammissibilità il motivo, le prove e il "
          "giorno della scoperta; non sospende il termine per il ricorso per cassazione.",
          R("cpc:398", "davanti allo stesso giudice che ha pronunciato la sentenza impugnata"),
          R("cpc:398", "non sospende il termine per proporre il ricorso per cassazione")),
    ],
    termini=[p("Termine: trenta giorni dalla notificazione della sentenza; per dolo, falsità, documenti ritrovati e dolo del "
               "giudice decorre dalla scoperta; per errore di fatto e contrasto di giudicati vale anche il termine lungo di sei mesi.",
               R("cpc:325", "la revocazione"), R("cpc:326", "dal giorno in cui e' stato scoperto il dolo o la falsita'"),
               R("cpc:327", "la revocazione per i motivi indicati nei numeri 4 e 5")), _FERIALE],
    dati=["sentenza e date", "motivo di revocazione", "data della scoperta del dolo, della falsità o del documento"],
)

OPPOSIZIONE_TERZO_SENTENZA = Scheda(
    regola="civ_opposizione_terzo", materia="civile ordinario", nome="opposizione di terzo alla sentenza (art. 404)",
    segnali=(r"opposizione di terzo|\b404\b|sentenz\w*[^.]{0,80}(?:tra altr|fra altr|non era parte|pregiudic\w* (?:i )?(?:suoi|miei|diritti)|"
             r"collusion)|non era parte del giudizio",),
    esclusi=(_NON_CIVILE, r"pignor|esecuzion|\b619\b"), punteggio=6,
    capito="Terzo pregiudicato da una sentenza pronunciata fra altre persone.",
    rimedio="citazione in opposizione di terzo davanti allo stesso giudice che ha pronunciato la sentenza",
    conclusione=[
        p("Il terzo può opporsi alla sentenza passata in giudicato o esecutiva pronunciata fra altre persone quando pregiudica "
          "i suoi diritti; aventi causa e creditori di una parte possono opporsi alla sentenza effetto di dolo o collusione a loro danno.",
          R("cpc:404", "quando pregiudica i suoi diritti"), R("cpc:404", "effetto di dolo o collusione a loro danno")),
        p("L'opposizione si propone davanti allo stesso giudice, con l'indicazione della sentenza e, per l'opposizione "
          "revocatoria, del giorno della scoperta del dolo o della collusione e della prova.",
          R("cpc:405", "davanti allo stesso giudice che ha pronunciato la sentenza")),
    ],
    termini=[p("L'opposizione ordinaria non ha termine; quella revocatoria (dolo o collusione) va proposta entro trenta giorni dalla scoperta.",
               R("cpc:325", "l'opposizione di terzo di cui all'articolo 404, secondo comma"),
               R("cpc:326", "il dolo o la falsita' o la collusione"))],
    dati=["sentenza e parti del giudizio", "diritto del terzo pregiudicato", "data della scoperta del dolo o della collusione"],
)

REGOLAMENTO_COMPETENZA = Scheda(
    regola="civ_regolamento_competenza", materia="civile ordinario", nome="regolamento di competenza",
    segnali=(r"regolamento (?:necessario |facoltativo )?di competenza|dichiarat\w* incompetent|declin\w* la competenza|"
             r"sospensione (?:del processo )?per pregiudizialita|sospeso la causa",),
    esclusi=(_NON_CIVILE,), punteggio=6,
    capito="Impugnazione dell'ordinanza sulla competenza o del provvedimento di sospensione per pregiudizialità.",
    rimedio="ricorso alla Corte di cassazione per regolamento di competenza (in alternativa: riassunzione davanti al giudice indicato)",
    conclusione=[
        p("L'ordinanza che pronuncia sulla competenza senza decidere il merito e il provvedimento di sospensione per "
          "pregiudizialità si impugnano soltanto con regolamento di competenza.",
          R("cpc:42", "possono essere impugnati soltanto con istanza di regolamento di competenza")),
        p("Il ricorso alla Cassazione si notifica entro trenta giorni dalla comunicazione dell'ordinanza e si deposita entro "
          "venti giorni dall'ultima notificazione.",
          R("cpc:47", "entro il termine perentorio di trenta giorni dalla comunicazione della ordinanza"),
          R("cpc:47", "nel termine perentorio di venti giorni dall'ultima notificazione")),
    ],
    scadenze=[Scadenza("notifica del ricorso entro", 30, "giorni", r"(?:ordinanza|provvedimento)[^0-9]{0,40}comunicat\w*(?: il)?",
                       (R("cpc:47", "entro il termine perentorio di trenta giorni dalla comunicazione della ordinanza"),))],
    termini=[_FERIALE],
    dati=["provvedimento e data di comunicazione", "tipo (incompetenza o sospensione)"],
)

URGENZA_700 = Scheda(
    regola="cau_700", materia="cautelare e urgenza", nome="provvedimento d'urgenza (art. 700 c.p.c.)",
    segnali=(r"\b700\b|provvediment\w* d urgenza|ricorso d urgenza|pregiudizio imminente|irreparabil|tutela (?:cautelare )?urgente|"
             r"ordine del giudice (?:prima|subito)|subito un ordine",),
    esclusi=(_NON_CIVILE, r"sequestro|\btar\b|sospensiva"), punteggio=5,
    capito="Tutela urgente atipica in attesa del giudizio di merito.",
    rimedio="ricorso ex art. 700 c.p.c. al giudice competente per il merito",
    conclusione=[
        p("Chi teme che, nel tempo occorrente per far valere il diritto in via ordinaria, questo sia minacciato da un "
          "pregiudizio imminente e irreparabile può chiedere con ricorso i provvedimenti d'urgenza più idonei, fuori dei casi "
          "regolati dalle altre misure cautelari (residualità).",
          R("cpc:700", "pregiudizio imminente e irreparabile"), R("cpc:700", "fuori dei casi regolati nelle precedenti sezioni")),
        p("Prima della causa la domanda si propone al giudice competente per il merito.",
          R("cpc:669ter", "la domanda si propone al giudice competente a conoscere del merito")),
    ],
    termini=[p("Il provvedimento d'urgenza anticipatorio resta efficace anche senza causa di merito; per gli altri, il merito "
               "va iniziato nel termine fissato dal giudice o, in mancanza, entro sessanta giorni.",
               R("cpc:669octies", "termine perentorio di sessanta giorni")),
             p("Contro l'ordinanza è ammesso reclamo entro quindici giorni.",
               R("cpc:669terdecies", "nel termine perentorio di quindici giorni"))],
    dati=["diritto da tutelare e prove (fumus)", "pregiudizio imminente e irreparabile (periculum)", "giudice competente per il merito"],
)

SEQUESTRO_DOMANDA = Scheda(
    regola="cau_sequestro_domanda", materia="cautelare e urgenza", nome="domanda di sequestro conservativo o giudiziario",
    segnali=(r"sequestr",), alcuni=(r"chieder|ottener|ricorso|come si|possiamo|prepara|scriv|vend\w* (?:tutti )?i beni|distrarr|dilapid|conteso",),
    esclusi=(_NON_CIVILE, r"ottenuto il sequestro|autorizzat\w* il sequestro|sequestro (?:e stato )?(?:concesso|autorizzat)|eseguit\w* il sequestro|"
             r"preventiv|probatori|sequestro penale"), punteggio=5,
    capito="Creditore che teme di perdere la garanzia del credito o lite sulla proprietà o il possesso di un bene.",
    rimedio="ricorso per sequestro conservativo (o giudiziario) al giudice competente per il merito",
    conclusione=[
        p("Il giudice, su istanza del creditore che ha fondato timore di perdere la garanzia del credito, può autorizzare il "
          "sequestro conservativo dei beni del debitore nei limiti in cui la legge ne permette il pignoramento.",
          R("cpc:671", "fondato timore di perdere la garanzia del proprio credito")),
        p("Prima della causa la domanda si propone al giudice competente per il merito; accolta la domanda, il merito va "
          "iniziato nel termine fissato o entro sessanta giorni, a pena di inefficacia.",
          R("cpc:669ter", "la domanda si propone al giudice competente a conoscere del merito"),
          R("cpc:669octies", "termine perentorio di sessanta giorni"), R("cpc:669novies", "perde la sua efficacia")),
    ],
    dati=["credito e prova", "condotte del debitore che mettono a rischio la garanzia", "beni da sequestrare"],
)

ATP = Scheda(
    regola="cau_atp", materia="cautelare e urgenza", nome="accertamento tecnico preventivo e consulenza tecnica preventiva",
    segnali=(r"\batp\b|accertamento tecnico preventivo|696-?bis|consulenza tecnica preventiva|\b696\b|cristallizzar\w* lo stato|"
             r"stato dei luoghi[^.]{0,40}prima",),
    esclusi=(_NON_CIVILE, r"invalidita|445-?bis|obbligatorio|responsabilita (?:medica|sanitaria)|ospedal|medic"), punteggio=6,
    capito="Accertamento tecnico prima della causa: urgente (art. 696) o a fini conciliativi (art. 696-bis).",
    rimedio="ricorso per accertamento tecnico preventivo o per consulenza tecnica preventiva ai fini della composizione della lite",
    conclusione=[
        p("Chi ha urgenza di far verificare prima del giudizio lo stato di luoghi o la qualità o condizione di cose può "
          "chiedere un accertamento tecnico o un'ispezione giudiziale.",
          R("cpc:696", "chi ha urgenza di far verificare, prima del giudizio, lo stato di luoghi")),
        p("La consulenza tecnica preventiva si chiede anche senza urgenza per accertare e determinare i crediti da "
          "inadempimento contrattuale o da fatto illecito; il consulente tenta la conciliazione delle parti.",
          R("cpc:696bis", "anche al di fuori delle condizioni di cui al primo comma dell'articolo 696"),
          R("cpc:696bis", "tenta, ove possibile, la conciliazione delle parti")),
        p("Il ricorso si propone al giudice che sarebbe competente per il merito.",
          R("cpc:693", "al giudice che sarebbe competente per la causa di merito")),
    ],
    dati=["oggetto dell'accertamento e quesiti", "controparti", "urgenza (per l'art. 696)"],
)

ISTRUZIONE_PREVENTIVA = Scheda(
    regola="cau_istruzione_preventiva", materia="cautelare e urgenza", nome="istruzione preventiva: testimoni a futura memoria",
    segnali=(r"futura memoria|\b692\b|istruzione preventiva|(?:testimon|teste)[^.]{0,80}(?:malat|trasferir|estero|anzian|morire|prima della causa)",),
    esclusi=(_NON_CIVILE,), punteggio=6,
    capito="Assunzione preventiva di una testimonianza che rischia di andare perduta.",
    rimedio="ricorso per assunzione di testimoni a futura memoria",
    conclusione=[
        p("Chi teme che manchino uno o più testimoni necessari in una causa da proporre può chiederne l'audizione a futura memoria.",
          R("cpc:692", "audizione a futura memoria")),
        p("Il ricorso va al giudice competente per il merito (in caso di eccezionale urgenza, al tribunale del luogo della "
          "prova) e indica i motivi dell'urgenza, i fatti e le domande cui la prova è preordinata.",
          R("cpc:693", "al giudice che sarebbe competente per la causa di merito"), R("cpc:693", "motivi dell'urgenza")),
        p("La prova preventiva non pregiudica le questioni di ammissibilità e rilevanza nel merito.",
          R("cpc:698", "non pregiudica le questioni relative alla loro ammissibilita'")),
    ],
    dati=["generalità del teste e motivo del rischio", "capitoli di prova", "causa da proporre"],
)

RECLAMO_CAUTELARE = Scheda(
    regola="cau_reclamo", materia="cautelare e urgenza", nome="reclamo cautelare (art. 669-terdecies)",
    segnali=(r"reclam", r"cautelar|\b700\b|sequestr|ordinanza|urgenza|possessori|669"),
    esclusi=(_NON_CIVILE, r"garante|consumator|condomin|reclamo (?:al|alla) (?:banca|compagnia)"), punteggio=6,
    capito="Impugnazione dell'ordinanza che ha concesso o negato una misura cautelare.",
    rimedio="reclamo al collegio del tribunale (o ad altra sezione della corte d'appello)",
    conclusione=[
        p("Contro l'ordinanza che concede o nega il provvedimento cautelare è ammesso reclamo entro quindici giorni dalla "
          "pronuncia in udienza o dalla comunicazione o notificazione se anteriore; il reclamo contro il giudice singolo si "
          "propone al collegio.",
          R("cpc:669terdecies", "nel termine perentorio di quindici giorni"),
          R("cpc:669terdecies", "si propone al collegio")),
    ],
    scadenze=[Scadenza("reclamo entro", 15, "giorni", r"(?:ordinanza|provvedimento)[^0-9]{0,40}(?:comunicat\w*|notificat\w*|pronunciat\w*|del)(?: il)?",
                       (R("cpc:669terdecies", "nel termine perentorio di quindici giorni"),), modello="CIV_RECLAMO_CAUTELARE_669_TERDECIES")],
    avvertenze=["I procedimenti cautelari non godono della sospensione feriale."],
    dati=["ordinanza e data di pronuncia o comunicazione", "motivi", "circostanze sopravvenute"],
)

_POSSESSO = r"possess|spogli|spogliat|serratura|cancello|lucchett|tolto (?:l acqua|la luce)|staccato (?:l acqua|la luce)|molest|turbativ"

REINTEGRAZIONE = Scheda(
    regola="pos_reintegrazione", materia="possessorio", nome="azione di reintegrazione (spoglio)",
    segnali=(r"spogli|reintegr|cambiat\w* (?:la )?serratura|(?:chiuso|bloccato)[^.]{0,30}(?:cancello|accesso|passaggio)|"
             r"non (?:puo|possiamo|posso) piu (?:entrare|accedere)|staccat\w* (?:l acqua|la luce)|tolto il possesso",),
    esclusi=(_NON_CIVILE, r"sfratt|esecuzion|pignor"), punteggio=6,
    capito="Privazione violenta o clandestina del possesso o della detenzione.",
    rimedio="ricorso per reintegrazione nel possesso al tribunale del luogo",
    conclusione=[
        p("Chi è stato violentemente od occultamente spogliato del possesso può chiedere, entro l'anno dallo spoglio, la "
          "reintegrazione; l'azione spetta anche al detentore qualificato; se lo spoglio è clandestino l'anno decorre dalla scoperta.",
          R("cc:1168", "entro l'anno dal sofferto spoglio"), R("cc:1168", "a chi ha la detenzione della cosa"),
          R("cc:1168", "decorre dal giorno della scoperta dello spoglio")),
        p("La domanda si propone con ricorso al giudice del luogo; l'ordinanza è reclamabile e su richiesta prosegue il merito.",
          R("cpc:703", "si propongono con ricorso al giudice competente a norma dell'articolo 21"),
          R("cpc:703", "reclamabile ai sensi dell'articolo 669-terdecies")),
    ],
    scadenze=[Scadenza("reintegrazione entro", 1, "anni", r"(?:spoglio|cambiat\w* la serratura|chiuso)[^0-9]{0,30}(?:il|dal)?",
                       (R("cc:1168", "entro l'anno dal sofferto spoglio"),), sospensione_feriale=False, sostanziale=True)],
    dati=["data dello spoglio o della scoperta", "modalità (violenta o clandestina)", "titolo del possesso o della detenzione"],
)

MANUTENZIONE = Scheda(
    regola="pos_manutenzione", materia="possessorio", nome="azione di manutenzione",
    segnali=(r"manutenzione (?:nel|del) possesso|molest\w*[^.]{0,60}possess|turbativ|azione di manutenzione",),
    esclusi=(_NON_CIVILE, r"condomin\w* (?:delibera|assemblea)|spese di manutenzione|manutenzione straordinaria"), punteggio=6,
    capito="Molestia o turbativa nel possesso di un immobile o di un diritto reale.",
    rimedio="ricorso per manutenzione nel possesso al tribunale del luogo",
    conclusione=[
        p("Chi è molestato nel possesso di un immobile o di un diritto reale su un immobile può chiedere, entro l'anno dalla "
          "turbativa, la manutenzione; l'azione spetta se il possesso dura da oltre un anno, continuo e non interrotto.",
          R("cc:1170", "entro l'anno dalla turbativa"), R("cc:1170", "se il possesso dura da oltre un anno")),
        p("La domanda si propone con ricorso al giudice del luogo.",
          R("cpc:703", "si propongono con ricorso al giudice competente a norma dell'articolo 21")),
    ],
    dati=["data della turbativa", "durata del possesso", "oggetto del possesso"],
)

NUOVA_OPERA = Scheda(
    regola="pos_nuova_opera_danno_temuto", materia="possessorio", nome="denuncia di nuova opera e di danno temuto",
    segnali=(r"nuova opera|danno temuto|1171|1172|(?:sta costruendo|lavori iniziat\w*|costruzione in corso)[^.]{0,80}(?:bloccar|fermar|danno|luce)|"
             r"(?:pericolant|rischia di cadere|minaccia di crollare|sta per cadere)",),
    esclusi=(_NON_CIVILE, r"permesso di costruire|\btar\b|condomin"), punteggio=6,
    capito="Opera intrapresa da altri o cosa pericolante che minaccia danno al bene posseduto.",
    rimedio="ricorso per denuncia di nuova opera o di danno temuto al tribunale del luogo",
    conclusione=[
        p("Il proprietario, il titolare di un diritto reale di godimento o il possessore può denunciare la nuova opera da cui "
          "teme danno, purché non sia terminata e non sia trascorso un anno dal suo inizio; il giudice può vietarne la "
          "continuazione o permetterla con cautele.",
          R("cc:1171", "purche' questa non sia terminata e non sia trascorso un anno dal suo inizio"),
          R("cc:1171", "puo' vietare la continuazione dell'opera")),
        p("Contro il pericolo di danno grave e prossimo da edificio, albero o altra cosa si può chiedere che si provveda per "
          "ovviare al pericolo.", R("cc:1172", "pericolo di un danno grave e prossimo")),
        p("La denuncia si propone con ricorso al giudice del luogo.",
          R("cpc:688", "si propone con ricorso al giudice competente a norma dell'articolo 21")),
    ],
    dati=["data di inizio dei lavori e stato dell'opera", "danno temuto", "titolo del ricorrente"],
)

# La domanda di sequestro ante causam è coperta da sequestro_ante_causam (fattispecie/varie.py, branch lex-regole).
SCHEDE = (MEMORIE, REVOCAZIONE, OPPOSIZIONE_TERZO_SENTENZA, REGOLAMENTO_COMPETENZA, RECLAMO_CAUTELARE, ATP,
          ISTRUZIONE_PREVENTIVA, URGENZA_700, REINTEGRAZIONE, MANUTENZIONE, NUOVA_OPERA,
          CASSAZIONE, APPELLO, CITAZIONE)
