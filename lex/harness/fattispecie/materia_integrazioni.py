"""Strumenti emersi dalla valutazione indipendente: rinuncia all'eredità, negoziazione assistita nei sinistri stradali,
decreto ingiuntivo per retribuzioni, definizione agevolata dei carichi, rimessione in termini, divorzio immediato.

Base normativa (testo vigente): artt. 467, 476, 480, 519, 521, 525 c.c.; art. 3 d.l. 132/2014; artt. 145, 148
d.lgs. 209/2005; artt. 413, 633, 634, 641, 642 c.p.c.; art. 1, commi 82-98, l. 199/2025; art. 153 c.p.c.; art. 3
l. 898/1970.
"""
from __future__ import annotations

from ..comprensione import Comprensione
from ..fatti import Fatti
from ..modello import Analisi
from .schede import R, Scheda, p

RINUNCIA_EREDITA = Scheda(
    regola="suc_rinuncia_eredita", materia="successioni", nome="rinuncia all'eredità",
    segnali=(r"rinun[cz]\w*[^.]{0,40}eredit|eredit\w*[^.]{0,40}rinun[cz]|non (?:voglio|vogliamo|vuole) (?:accettare )?l eredita|"
             r"rifiutare l eredita|non accettare l eredita",),
    esclusi=(r"vive nella casa|abita nella casa|continua ad abitar|conviveva|ne detiene le chiavi|nel possesso|ha (?:gia )?usato|ha preso|"
             r"ha venduto|ha incassato|paga le utenze",), punteggio=6,
    capito="Chiamato all'eredità che non vuole ereditare (di solito per i debiti del defunto).",
    rimedio="dichiarazione di rinuncia davanti al notaio o al cancelliere del tribunale del luogo di apertura della successione",
    conclusione=[
        p("La rinuncia si fa con dichiarazione ricevuta da un notaio o dal cancelliere del tribunale del circondario in cui si è "
          "aperta la successione, inserita nel registro delle successioni.",
          R("cc:519", "ricevuta da un notaio o dal cancelliere del tribunale del circondario")),
        p("Chi rinuncia è considerato come se non fosse mai stato chiamato; al suo posto subentrano per rappresentazione i "
          "discendenti (i figli del rinunciante), che a loro volta devono decidere se accettare o rinunciare.",
          R("cc:521", "e' considerato come se non vi fosse mai stato chiamato"),
          R("cc:467", "fa subentrare i discendenti")),
        p("Non si può più rinunciare se si è già accettato anche tacitamente, cioè compiendo atti che solo un erede potrebbe "
          "fare (vendere beni, incassare crediti del defunto).",
          R("cc:476", "un atto che presuppone necessariamente la sua volonta' di accettare")),
        p("La rinuncia si può revocare accettando, finché il diritto non è prescritto e l'eredità non è stata acquistata da "
          "altri chiamati.", R("cc:525", "possono sempre accettarla")),
    ],
    termini=[p("Il diritto di accettare si prescrive in dieci anni dall'apertura della successione; chi è nel possesso di beni "
               "ereditari ha invece tre mesi per l'inventario, altrimenti è erede puro e semplice.",
               R("cc:480", "si prescrive in dieci anni"), R("cc:485", "entro tre mesi dal giorno dell'apertura della successione"))],
    avvertenze=["Consiglio operativo: se nessuno degli eredi vuole i debiti, conviene che rinuncino anche i figli del rinunciante, o che i minori "
                "accettino con beneficio d'inventario."],
    dati=["data del decesso", "atti compiuti sui beni del defunto", "possesso di beni ereditari", "figli del chiamato"],
)

NEGOZIAZIONE_SINISTRI = Scheda(
    regola="rc_negoziazione_sinistri", materia="responsabilità civile", nome="negoziazione assistita obbligatoria nei sinistri stradali",
    segnali=(r"negoziazion|prima della causa|procedibil|direttamente dal giudice|andare dal giudice|fare causa subito|invit\w* (?:a stipulare|alla compagnia|l assicurazione)|prima di (?:fare|andare in) causa",
             r"sinistr|incident|tamponat|investit|circolazion|assicura|compagnia|rca|scontro"),
    # Se si chiede anche il giudice competente risponde la regola del sinistro, che dà competenza e procedibilità insieme.
    esclusi=(r"lavoro\b|medic|ospedal|locazion|conduttor|inquilin|moros|canon|quale giudice|competen",), punteggio=4,
    capito="Danno da circolazione stradale: passi obbligatori prima di agire in giudizio.",
    rimedio="richiesta di risarcimento all'assicurazione, attesa dei termini, poi invito alla negoziazione assistita tramite avvocato",
    conclusione=[
        p("Per qualsiasi azione di risarcimento del danno da circolazione di veicoli e natanti, di qualunque valore, l'avvocato "
          "deve prima invitare l'altra parte a stipulare una convenzione di negoziazione assistita: è condizione di "
          "procedibilità della domanda.",
          R("dl132:3", "risarcimento del danno da circolazione di veicoli e natanti"),
          R("dl132:3", "condizione di procedibilita' della domanda giudiziale")),
        p("Contro l'assicurazione l'azione è proponibile solo dopo la richiesta di risarcimento e dopo che sono decorsi i "
          "termini della procedura (sessanta giorni per i soli danni a cose, novanta per le lesioni).",
          R("dlgs209:145", "proponibilita'"), R("dlgs209:148", "sessanta giorni"), R("dlgs209:148", "novanta giorni")),
        p("La mancata risposta all'invito entro trenta giorni o il rifiuto possono essere valutati dal giudice sulle spese.",
          R("dl132:4", "entro trenta giorni dalla ricezione")),
    ],
    termini=[p("Il diritto al risarcimento dei danni da circolazione si prescrive in due anni.",
               R("cc:2947", "il diritto si prescrive in due anni"))],
    dati=["data del sinistro e della richiesta all'assicurazione", "tipo di danno (cose o lesioni)", "risposta della compagnia"],
)

DI_RETRIBUZIONI = Scheda(
    regola="lav_decreto_ingiuntivo", materia="lavoro", nome="decreto ingiuntivo per retribuzioni non pagate",
    segnali=(r"ingiuntiv|ingiunzion|monitori|ingiunger", r"stipend|retribu|buste? paga|busta paga|mensilit|tredicesim|"
             r"quattordicesim|\btfr\b|ferie|lavorator|dipendent|datore"),
    esclusi=(r"pignor|oppo|tardiv|ordinanza.ingiunzione|minister|pubblic\w* amministrazion|scuola",), punteggio=7,
    capito="Lavoratore con retribuzioni documentate e non pagate che vuole un titolo esecutivo rapido.",
    rimedio="ricorso per decreto ingiuntivo al tribunale in funzione di giudice del lavoro, con le buste paga",
    conclusione=[
        p("Chi è creditore di una somma liquida ottiene l'ingiunzione se del diritto dà prova scritta: per le retribuzioni lo "
          "sono, in pratica, le buste paga consegnate dal datore e gli altri documenti del rapporto.",
          R("cpc:633", "se del diritto fatto valere si da' prova scritta"), R("cpc:634", "promesse unilaterali")),
        p("Il ricorso va al tribunale in funzione di giudice del lavoro del luogo del rapporto o dell'azienda.",
          R("cpc:413", "e sorto il rapporto ovvero si trova l'azienda")),
        p("Il decreto si notifica e il datore ha quaranta giorni per opporsi; può essere chiesta l'esecuzione provvisoria se "
          "c'è pericolo nel ritardo o documentazione sottoscritta dal debitore.",
          R("cpc:641", "quaranta giorni"), R("cpc:642", "documentazione sottoscritta dal debitore")),
    ],
    termini=[p("Le retribuzioni si prescrivono in cinque anni.", R("cc:2948", "si prescrivono in cinque anni")),
             p("La sospensione feriale non si applica alle controversie di lavoro.",
               R("l742:3", "controversie previste dagli articoli 429"))],
    dati=["buste paga o altri documenti firmati dal datore", "mensilità e importi netti/lordi", "sede dell'azienda o luogo di lavoro"],
)


def _extra_definizione(a: Analisi, c: Comprensione, f: Fatti) -> None:
    from datetime import date

    if f.oggi > date(2026, 4, 30):
        a.termini.append(p("Il termine per la dichiarazione di adesione era il 30/04/2026 ed è scaduto: per i carichi non "
                           "dichiarati entro quella data la definizione non è più disponibile, salvo una nuova legge.",
                           R("l199:1", "entro il 30 aprile 2026")))


DEFINIZIONE_AGEVOLATA = Scheda(
    regola="trib_definizione_agevolata", materia="tributario", nome="definizione agevolata dei carichi (rottamazione)",
    segnali=(r"rottamazion|definizione agevolata|definire (?:le )?cartell|pace fiscale|stralcio (?:delle )?cartell",), punteggio=7,
    capito="Contribuente con cartelle che chiede se può pagarle senza sanzioni e interessi.",
    rimedio="dichiarazione di adesione all'agente della riscossione e pagamento in unica soluzione o a rate",
    conclusione=[
        p("I carichi affidati all'agente della riscossione dal 2000 al 2023 per imposte dichiarate e non versate (anche da "
          "controlli automatici) e per contributi INPS non versati, esclusi quelli da accertamento, si estinguono pagando il "
          "capitale e le spese, senza sanzioni, interessi di mora e aggio.",
          R("l199:1", "dal 1° gennaio 2000 al 31 dicembre 2023"), R("l199:1", "con esclusione di quelli richiesti a seguito di accertamento")),
        p("Il pagamento è in unica soluzione entro il 31 luglio 2026 o fino a cinquantaquattro rate bimestrali, con interessi "
          "del 3 per cento annuo; la dichiarazione si presenta all'agente della riscossione in via telematica entro il "
          "30 aprile 2026.", R("l199:1", "cinquantaquattro rate bimestrali"), R("l199:1", "entro il 30 aprile 2026")),
        p("Se non si paga l'unica rata o due rate, anche non consecutive, la definizione non produce effetti e i versamenti "
          "valgono come acconto.", R("l199:1", "di due rate, anche non consecutive")),
        p("Per le multe stradali la definizione riguarda solo gli interessi.",
          R("l199:1", "limitatamente agli interessi")),
    ],
    dati=["elenco dei carichi e anni di affidamento", "origine del debito (dichiarazione o accertamento)", "giudizi pendenti sui carichi"],
    extra=_extra_definizione,
)

RIMESSIONE_TERMINI = Scheda(
    regola="civ_rimessione_termini", materia="civile ordinario", nome="rimessione in termini",
    segnali=(r"rimession\w* in termin|rimess\w* in termin|scadut\w* (?:il )?termin|termin\w* (?:e )?scadut|decadut|decadenza",),
    alcuni=(r"causa non imputabile|non per colpa|malat|ricover|forza maggiore|errore della cancelleria|pec non (?:arrivat|ricevut)|"
            r"impedit|non (?:ho|abbiamo) potuto|rimession|rimess|non (?:e )?(?:mai )?arrivat|guasto|sistema",),
    esclusi=(r"penal|imputat|reato|querel|tributar|opposizione tardiva|decreto ingiuntiv|eredit",), punteggio=6,
    capito="Parte decaduta da un termine processuale per una causa che non dipende da lei.",
    rimedio="istanza di rimessione in termini al giudice, con la prova della causa non imputabile, appena cessato l'impedimento",
    conclusione=[
        p("I termini perentori non si prorogano, ma la parte che dimostra di essere incorsa in decadenze per causa non imputabile "
          "può chiedere al giudice di essere rimessa in termini.",
          R("cpc:153", "i termini perentori non possono essere abbreviati o prorogati"),
          R("cpc:153", "per causa ad essa non imputabile")),
    ],
    avvertenze=["Consiglio operativo: l'istanza va proposta tempestivamente, appena cessato l'impedimento, e con la prova documentale della causa."],
    dati=["termine scaduto e atto mancato", "causa dell'impedimento e prove", "data in cui l'impedimento è cessato"],
)

DIVORZIO_IMMEDIATO = Scheda(
    regola="fam_divorzio_immediato", materia="famiglia e minori", nome="divorzio senza separazione per condanne penali e altri casi dell'art. 3 l. 898/1970",
    segnali=(r"divorzi|sciogliment\w* del matrimonio", r"condann|ergastol|carcer|galera|reato|omicid|maltratt|violenz|in prigione"),
    punteggio=7,
    capito="Coniuge che chiede il divorzio senza passare dalla separazione perché l'altro è stato condannato.",
    rimedio="ricorso per divorzio fondato sull'art. 3, n. 1, l. 898/1970 (senza separazione)",
    conclusione=[
        p("Il divorzio si può chiedere subito se l'altro coniuge è stato condannato con sentenza definitiva, anche per fatti "
          "precedenti al matrimonio, all'ergastolo o a più di quindici anni per delitti non colposi.",
          R("l898:3", "all'ergastolo ovvero ad una pena superiore ad anni quindici")),
        p("Bastano invece condanne a qualsiasi pena per l'omicidio volontario di un figlio o il tentato omicidio del coniuge o "
          "di un figlio, e i reati di violenza o maltrattamenti in famiglia indicati dalla legge con due o più condanne.",
          R("l898:3", "omicidio volontario di un figlio"), R("l898:3", "con due o piu' condanne")),
    ],
    dati=["sentenze di condanna e passaggio in giudicato", "reati e pene", "figli minori", "residenza dei coniugi"],
)

SCHEDE = (RINUNCIA_EREDITA, NEGOZIAZIONE_SINISTRI, DI_RETRIBUZIONI, DEFINIZIONE_AGEVOLATA, RIMESSIONE_TERMINI, DIVORZIO_IMMEDIATO)
