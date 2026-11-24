"""Lavoro e previdenza: conciliazione e rinunce, mobbing e demansionamento, ricorso amministrativo e giudiziale contro
INPS/INAIL, accertamento tecnico preventivo obbligatorio.

Base normativa (testo vigente): artt. 410, 411, 412-ter, 413, 414 c.p.c.; artt. 2087, 2103, 2113, 2946 c.c.;
artt. 442, 443, 444, 445-bis c.p.c.; art. 46 l. 88/1989; art. 47 d.P.R. 639/1970; art. 3 l. 742/1969.
"""
from __future__ import annotations

from ..comprensione import Comprensione
from ..fatti import Fatti
from ..modello import Analisi
from .schede import Bozza, R, Scadenza, Scheda, p

LAV = r"rapporto (?:di lavoro|cessat)|lavor|dipendent|datore|azienda|impiegat|operai|\bcapo\b|superior|colleg|mansion|vertenza|sindacal|ispettorato"
ENTE = (r"\binps\b|\binail\b|\bpension|naspi|disoccupazion|assegno (?:sociale|unico|di invalidita|ordinario)|indennita di "
        r"(?:malattia|maternita|accompagnamento)|reversibilita|prestazion\w* (?:previdenz|assistenz)|invalidita civile|"
        r"inabilita|contribut\w* previdenz|\b104\b|handicap|indebito (?:pensionistico|previdenziale)|accompagnamento")
_INVALIDITA = r"invalidita|inabilita|accompagnament|handicap|\b104\b|cecita|sordita|disabilita|445-?bis|assegno ordinario"

_TERMINI_LAVORO = p("La sospensione feriale non si applica alle controversie di lavoro e di previdenza.",
                    R("l742:3", "controversie previste dagli articoli 429"))


def _giudice_lavoro(a: Analisi, f: Fatti) -> None:
    luogo = f.luogo_lavoro or ""
    a.giudice = "Tribunale in funzione di giudice del lavoro" + (f" di {luogo}" if luogo else "")
    a.competenza = [p("Foro del lavoro: il giudice nella cui circoscrizione è sorto il rapporto ovvero si trova l'azienda o la "
                      "dipendenza alla quale è addetto il lavoratore (per i dipendenti pubblici: l'ufficio di assegnazione).",
                      R("cpc:413", "e sorto il rapporto ovvero si trova l'azienda"),
                      R("cpc:413", "era addetto al momento della cessazione del rapporto"))]
    a.rito = [p("Rito del lavoro: ricorso al giudice competente.", R("cpc:414", "si propone con ricorso"))]
    a.termini.append(_TERMINI_LAVORO)


def _extra_lavoro(a: Analisi, c: Comprensione, f: Fatti) -> None:
    _giudice_lavoro(a, f)


CONCILIAZIONE = Scheda(
    regola="lav_conciliazione_rinunce", materia="lavoro", nome="conciliazione, rinunce e transazioni del lavoratore",
    segnali=(r"conciliazion|rinunc|transazion|transatt|chiudere (?:la vertenza|la lite)|accordo con il datore", LAV),
    esclusi=(r"licenzia|precett|pignor|sfratt", r"\binps\b|\bpension"), punteggio=6,
    capito="Conciliazione della vertenza di lavoro o validità di rinunce e transazioni firmate dal lavoratore.",
    rimedio="conciliazione in sede protetta (commissione presso l'Ispettorato, sede sindacale o prevista dai contratti "
            "collettivi); impugnazione scritta delle rinunce invalide entro sei mesi",
    conclusione=[
        p("Rinunce e transazioni del lavoratore su diritti derivanti da norme inderogabili di legge o dei contratti "
          "collettivi non sono valide e si impugnano, a pena di decadenza, entro sei mesi dalla cessazione del rapporto o "
          "dalla rinuncia o transazione se successiva, con qualsiasi atto scritto anche stragiudiziale.",
          R("cc:2113", "non sono valide"), R("cc:2113", "entro sei mesi dalla data di cessazione del rapporto"),
          R("cc:2113", "con qualsiasi atto scritto, anche stragiudiziale")),
        p("Le conciliazioni concluse davanti alla commissione di conciliazione, in sede sindacale o nelle sedi previste "
          "dai contratti collettivi sono stabili: la regola dell'impugnazione non si applica.",
          R("cc:2113", "non si applicano alla conciliazione intervenuta"),
          R("cpc:412ter", "presso le sedi e con le modalita' previste dai contratti collettivi")),
        p("Se la conciliazione riesce si redige il verbale, che il giudice dichiara esecutivo con decreto su istanza "
          "della parte; se non riesce, la commissione formula una proposta di cui il giudice terrà conto.",
          R("cpc:411", "lo dichiara esecutivo con decreto"), R("cpc:411", "deve formulare una proposta")),
    ],
    procedibilita=[p("Il tentativo di conciliazione è facoltativo.", R("cpc:410", "puo promuovere"))],
    cosa_fare=["Verificare dove e davanti a chi è stata firmata la rinuncia o la transazione (sede protetta o no).",
               "Se non in sede protetta: impugnazione scritta entro sei mesi dalla cessazione (o dalla firma, se successiva).",
               "Per chiudere la vertenza: verbale in sede sindacale o davanti alla commissione, con l'elenco dei diritti transatti."],
    dati=["data di cessazione del rapporto", "data e sede della rinuncia o transazione", "diritti e importi oggetto dell'accordo"],
    scadenze=[Scadenza("impugnazione della rinuncia entro", 6, "mesi", r"(?:cessat\w*|cessazione del rapporto|firmat\w*)(?: il)?",
                       (R("cc:2113", "entro sei mesi dalla data di cessazione del rapporto"),), sospensione_feriale=False,
                       sostanziale=True)],
    extra=_extra_lavoro,
)

MOBBING = Scheda(
    regola="lav_mobbing_demansionamento", materia="lavoro", nome="mobbing, straining e demansionamento",
    segnali=(r"mobbing|straining|vessa|demansion|mansioni (?:inferiori|dequalific)|dequalific|umilia|isolat\w*|"
             r"persecut|svuotat\w* (?:di|delle) mansioni", LAV),
    esclusi=(r"licenzia|precett|pignor|provvediment\w* (?:d )?urgent|\b700\b|ricorso d urgenza",), punteggio=6, modello="LAV_005",
    capito="Lavoratore che lamenta condotte vessatorie (mobbing, straining) o l'assegnazione a mansioni inferiori.",
    rimedio="ricorso ex art. 414 c.p.c. per la reintegra nelle mansioni e il risarcimento del danno alla salute e alla professionalità",
    conclusione=[
        p("Il datore deve adottare le misure necessarie a tutelare l'integrità fisica e la personalità morale del "
          "lavoratore: le condotte vessatorie o la loro tolleranza sono inadempimento contrattuale e obbligano al risarcimento.",
          R("cc:2087", "tutelare l'integrita' fisica e la personalita' morale dei prestatori di lavoro")),
        p("Il lavoratore va adibito alle mansioni per cui è stato assunto o riconducibili allo stesso livello e categoria; "
          "le mansioni del livello inferiore sono ammesse solo per modifica degli assetti organizzativi, nella stessa "
          "categoria legale, con comunicazione scritta a pena di nullità e conservazione del livello e del trattamento.",
          R("cc:2103", "riconducibili allo stesso livello e categoria legale di inquadramento"),
          R("cc:2103", "comunicato per iscritto, a pena di nullita'")),
    ],
    termini=[p("Prescrizione decennale per il risarcimento da inadempimento contrattuale del datore.",
               R("cc:2946", "si estinguono per prescrizione con il decorso di dieci anni"))],
    cosa_fare=["Ricostruire per date le condotte, i soggetti e i testimoni; raccogliere comunicazioni, ordini di servizio, certificati medici.",
               "Per il demansionamento: confrontare mansioni di assunzione, livello CCNL e mansioni attuali.",
               "Valutare la consulenza medico-legale sul danno biologico e la prova dell'intento persecutorio (mobbing)."],
    dati=["periodo e descrizione delle condotte", "testimoni", "certificazione medica", "livello di inquadramento e mansioni",
          "datore pubblico o privato (foro)"],
    bozza=Bozza("Ricorso ex art. 414 c.p.c.", "risarcimento del danno da demansionamento e condotte vessatorie",
                ["Rapporto di lavoro, livello e mansioni di assunzione: [da completare].",
                 "Condotte vessatorie e assegnazione a mansioni inferiori (art. 2103 c.c.): [da completare].",
                 "Violazione dell'obbligo di sicurezza del datore (art. 2087 c.c.) e danno alla salute e alla professionalità."],
                "accertare l'illegittimità del demansionamento e delle condotte, ordinare la riassegnazione alle mansioni e "
                "condannare il resistente al risarcimento dei danni nella misura di [da completare]; con vittoria di spese.",
                "contratto, ordini di servizio, corrispondenza, certificati medici.", "artt. 413 e 414 c.p.c."),
    extra=_extra_lavoro,
)


def _extra_prev(a: Analisi, c: Comprensione, f: Fatti) -> None:
    a.termini.append(_TERMINI_LAVORO)


PREV_AMMINISTRATIVO = Scheda(
    regola="prev_ricorso_amministrativo", materia="previdenza", nome="ricorso amministrativo INPS",
    segnali=(ENTE, r"ricorso amministrativ|comitato|respint|rigett|diniego|negat|revocat|revoca|indebit|sospes|non risponde"),
    esclusi=(r"giudice|tribunale|causa\b|fare causa|ricorso giudiziale|in giudizio|azione giudiziaria|\btar\b|precett|pignor|licenzia", _INVALIDITA), punteggio=6,
    capito="Provvedimento dell'INPS (diniego, revoca, indebito) da contestare prima del giudizio.",
    rimedio="ricorso amministrativo al comitato provinciale dell'INPS entro novanta giorni dalla comunicazione del provvedimento",
    giudice="comitato provinciale INPS (poi tribunale in funzione di giudice del lavoro del luogo di residenza)",
    conclusione=[
        p("Contro i provvedimenti dell'INPS sulle prestazioni si ricorre al comitato provinciale entro novanta giorni dalla "
          "comunicazione; trascorsi inutilmente novanta giorni dalla presentazione senza decisione, il ricorso si intende respinto.",
          R("l88:46", "termine per ricorrere al comitato provinciale e di novanta giorni"),
          R("l88:46", "trascorsi inutilmente novanta giorni")),
        p("La domanda giudiziale non è procedibile finché il procedimento amministrativo non è esaurito o non sono decorsi i "
          "termini, e comunque 180 giorni dal ricorso amministrativo.",
          R("cpc:443", "decorsi 180 giorni dalla data in cui e stato proposto il ricorso amministrativo")),
    ],
    scadenze=[Scadenza("ricorso al comitato provinciale entro", 90, "giorni",
                       r"(?:comunicat\w*|notificat\w*|ricevut\w*|provvedimento del)(?: il)?",
                       (R("l88:46", "termine per ricorrere al comitato provinciale e di novanta giorni"),),
                       sospensione_feriale=False, sostanziale=True)],
    cosa_fare=["Presentare il ricorso amministrativo online (sito INPS o patronato) allegando la documentazione.",
               "Annotare la data di presentazione: dopo 90 giorni senza risposta il ricorso si intende respinto.",
               "Calcolare la decadenza per l'azione giudiziaria (un anno o tre anni secondo la prestazione)."],
    dati=["provvedimento INPS e data di comunicazione", "prestazione richiesta", "data della domanda amministrativa"],
    extra=_extra_prev,
)

PREV_GIUDIZIALE = Scheda(
    regola="prev_ricorso_giudiziale", materia="previdenza", nome="causa previdenziale e assistenziale (artt. 442-444 c.p.c.)",
    segnali=(ENTE, r"giudice|tribunale|fare causa|causa\b|ricorso giudiziale|in giudizio|decadenza|competen"),
    esclusi=(_INVALIDITA, r"\btar\b|precett|pignor|licenzia|sfratt|comitato provinciale"), punteggio=7,
    capito="Azione giudiziaria contro un ente previdenziale (INPS, INAIL) per una prestazione.",
    rimedio="ricorso al tribunale in funzione di giudice del lavoro del luogo di residenza, dopo il ricorso amministrativo",
    conclusione=[
        p("Le controversie di previdenza e assistenza obbligatorie seguono il rito del lavoro e sono di competenza del "
          "tribunale, in funzione di giudice del lavoro, nella cui circoscrizione ha la residenza l'attore.",
          R("cpc:442", "ogni altra forma di previdenza e di assistenza obbligatorie"),
          R("cpc:444", "nella cui circoscrizione ha la residenza l'attore")),
        p("La domanda è procedibile solo dopo il procedimento amministrativo, o decorsi 180 giorni dal ricorso "
          "amministrativo; se manca, il giudice sospende e assegna sessanta giorni per presentarlo.",
          R("cpc:443", "decorsi 180 giorni dalla data in cui e stato proposto il ricorso amministrativo"),
          R("cpc:443", "termine perentorio di sessanta giorni")),
        p("Decadenza: per i trattamenti pensionistici l'azione si propone entro tre anni dalla comunicazione della decisione "
          "del ricorso o dalla scadenza dei termini del procedimento; per le prestazioni temporanee entro un anno.",
          R("dpr639:47", "entro il termine di tre anni dalla data di comunicazione della decisione del ricorso"),
          R("dpr639:47", "entro il termine di un anno dalle date di cui al precedente comma")),
    ],
    cosa_fare=["Verificare che il ricorso amministrativo sia stato presentato e la data (procedibilità).",
               "Calcolare la decadenza (un anno o tre anni) dalla decisione o dal silenzio.",
               "Raccogliere estratto contributivo, provvedimenti e documentazione della prestazione."],
    dati=["prestazione e provvedimento", "data del ricorso amministrativo e della decisione", "residenza del ricorrente"],
    extra=_extra_prev,
)

ATPO = Scheda(
    regola="prev_atp_obbligatorio", materia="previdenza", nome="accertamento tecnico preventivo obbligatorio (art. 445-bis c.p.c.)",
    segnali=(_INVALIDITA,), alcuni=(ENTE, r"commissione medica|verbale (?:sanitario|di visita)|ricors|causa|giudice"),
    esclusi=(r"precett|pignor|licenzia|sfratt|sinistro|incidente",), punteggio=8,
    capito="Prestazione legata a invalidità civile, handicap, inabilità o assegno di invalidità negata per motivi sanitari.",
    rimedio="ricorso per accertamento tecnico preventivo obbligatorio al tribunale (giudice del lavoro) del luogo di residenza",
    giudice="Tribunale in funzione di giudice del lavoro del circondario di residenza del ricorrente",
    conclusione=[
        p("Nelle controversie su invalidità civile, handicap, disabilità, pensione di inabilità e assegno di invalidità chi "
          "intende agire presenta prima, con ricorso, istanza di accertamento tecnico preventivo: è condizione di "
          "procedibilità della domanda e interrompe la prescrizione.",
          R("cpc:445bis", "invalidita' civile, cecita' civile, sordita' civile, handicap e disabilita'"),
          R("cpc:445bis", "costituisce condizione di procedibilita' della domanda"),
          R("cpc:445bis", "interrompe la prescrizione")),
        p("Depositata la consulenza, chi la contesta deposita la dichiarazione di dissenso entro trenta giorni dalla "
          "comunicazione e poi il ricorso introduttivo entro trenta giorni dalla dichiarazione.",
          R("cpc:445bis", "entro il termine perentorio di trenta giorni dalla comunicazione"),
          R("cpc:445bis", "entro il termine perentorio di trenta giorni dalla formulazione della dichiarazione di dissenso")),
    ],
    scadenze=[Scadenza("dichiarazione di dissenso entro", 30, "giorni", r"(?:deposito della (?:ctu|consulenza)|comunicat\w*)(?: il)?",
                       (R("cpc:445bis", "entro il termine perentorio di trenta giorni dalla comunicazione"),),
                       sospensione_feriale=False)],
    cosa_fare=["Raccogliere il verbale della commissione medica e la documentazione sanitaria aggiornata.",
               "Depositare il ricorso per ATP con i quesiti e la documentazione.",
               "Dopo la CTU: se sfavorevole, dissenso entro 30 giorni e ricorso di merito entro i 30 giorni successivi."],
    dati=["prestazione richiesta", "verbale sanitario e data", "residenza del ricorrente", "requisiti reddituali"],
    extra=_extra_prev,
)

# Ricorso amministrativo e causa previdenziale hanno anche ricorso_amministrativo_inps e ricorso_442 (pubblico.py), che
# vincono a parità; l'ATP obbligatorio ha punteggio più alto perché per invalidità civile, handicap e inabilità la via
# è l'accertamento tecnico preventivo (art. 445-bis c.p.c.).
SCHEDE = (CONCILIAZIONE, MOBBING, ATPO, PREV_AMMINISTRATIVO, PREV_GIUDIZIALE)
