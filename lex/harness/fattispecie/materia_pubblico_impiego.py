"""Pubblico impiego contrattualizzato: differenze retributive, carta del docente, abuso dei contratti a termine,
ricostruzione di carriera, foro del dipendente pubblico, esecuzione contro la PA e ottemperanza.

Base normativa (testo vigente letto dalla biblioteca, istantanea ``dati/norme_vigenti_materie.json``):
art. 63 d.lgs. 165/2001 (giurisdizione del giudice ordinario del lavoro), art. 413, quinto comma, c.p.c. (foro
dell'ufficio di assegnazione), art. 417-bis c.p.c., art. 45 e art. 36, comma 5, d.lgs. 165/2001, art. 1, comma 121,
l. 107/2015, art. 485 d.lgs. 297/1994, art. 22, comma 36, l. 724/1994 e art. 16, comma 6, l. 412/1991 (interessi o
rivalutazione), art. 14 d.l. 669/1996 (120 giorni), artt. 112-114 c.p.a. (ottemperanza), art. 9, comma 1-bis,
d.P.R. 115/2002 (contributo unificato).
"""
from __future__ import annotations

from ..comprensione import Comprensione
from ..fatti import Fatti
from ..modello import Analisi
from .. import procedura as P
from .schede import Bozza, R, Scadenza, Scheda, p

PA = (r"minister|\bmiur\b|\bmim\b|istruzione e del merito|scuol|scolastic|istituto comprensivo|docent|supplen|"
      r"personale ata|\bata\b|collaborator\w* scolastic|pubblic\w* amministrazion|amministrazion\w* (?:pubblic|statal|dello stato)|"
      r"dipendent\w* pubblic|pubblico impiego|ente pubblico|azienda sanitaria|\basl\b|\basp\b|dipendente (?:del|di un) comune|"
      r"universita|agenzia delle entrate|\binps\b come datore")
_RETRIB = (r"retribu|differenz\w* (?:retributiv|stipendial)|stipend|indennit|scatt|compens|\brpd\b|\bcia\b|ferie non godut|"
           r"tredicesim|emolument|trattamento economico|busta paga|buste paga|progression|arretrat")
_CARTA = r"carta (?:elettronica )?(?:per l aggiornamento )?(?:del |dei )?docent|bonus (?:formazione|aggiornamento|500)|500 euro[^.]{0,60}formazion"
_TERMINE = (r"abus\w*|reiterazion|successione di contratti|contratti a termine|tempo determinato|36 mesi|trentasei mesi|"
            r"stabilizz|danno comunitario|precari\w*[^.]{0,40}(?:dieci|anni|risarc)")
_CARRIERA = r"ricostruzione (?:di |della )?carriera|pre-?ruolo|servizio non di ruolo|anzianita di servizio|\b485\b|servizio prestato prima del ruolo"
_ESECUZIONE = r"precett|pignor|ottemper|esecuzion|tesoreria|centoventi giorni|120 giorni|giudicato|commissario ad acta"
PA_ESEC = PA + r"|amministrazion|\bcomune\b|regione|\bente\b"
_TITOLO = r"sentenz|titolo|decreto ingiuntivo|giudicato|condann|ordinanza"


def _luogo(f: Fatti) -> str:
    return f.luogo_lavoro or ""


def _comuni(a: Analisi, c: Comprensione, f: Fatti) -> None:
    luogo = _luogo(f)
    a.giudice = (P.ufficio("Tribunale", luogo) + " in funzione di giudice del lavoro") if luogo else (
        "Tribunale in funzione di giudice del lavoro del luogo dell'ufficio al quale il dipendente è addetto")
    a.competenza = [
        p("Giurisdizione: le controversie sul rapporto di lavoro alle dipendenze delle pubbliche amministrazioni sono "
          "devolute al giudice ordinario in funzione di giudice del lavoro, anche quando vengono in questione atti "
          "amministrativi presupposti, che il giudice disapplica se illegittimi: non si ricorre al TAR.",
          R("dlgs165:63", "sono devolute al giudice ordinario, in funzione di giudice del lavoro"),
          R("dlgs165:63", "il giudice li disapplica, se illegittimi")),
        p("Foro (art. 413, quinto comma, c.p.c.): è competente il giudice nella cui circoscrizione ha sede l'ufficio al "
          "quale il dipendente è addetto o era addetto al momento della cessazione del rapporto"
          + (f" (qui: {luogo})" if luogo else " [ufficio di assegnazione da completare]")
          + "; le clausole che derogano a questa competenza sono nulle.",
          R("cpc:413", "era addetto al momento della cessazione del rapporto"),
          R("cpc:413", "sono nulle le clausole derogative della competenza per territorio")),
    ]
    a.procedibilita = [p("Il tentativo di conciliazione è facoltativo: chi agisce «può promuovere» il tentativo "
                         "dell'art. 410 c.p.c.; mediazione e negoziazione assistita non sono condizioni di procedibilità.",
                         R("cpc:410", "puo promuovere"))]
    a.rito = [
        p("Rito del lavoro: ricorso depositato nella cancelleria del giudice competente.", R("cpc:414", "si propone con ricorso")),
        p("In primo grado l'amministrazione può stare in giudizio avvalendosi direttamente di propri dipendenti; per le "
          "amministrazioni statali l'Avvocatura dello Stato può assumere la trattazione nelle questioni di massima o di "
          "notevole rilievo economico.", R("cpc:417bis", "avvalendosi direttamente di propri dipendenti"),
          R("cpc:417bis", "questioni di massima o aventi notevoli riflessi economici")),
        p("Contributo unificato: nelle controversie di pubblico impiego è dovuto (in misura ridotta) solo se il ricorrente "
          "ha un reddito imponibile superiore a tre volte il limite del patrocinio a spese dello Stato; altrimenti è esente.",
          R("dpr115:9", "concernenti rapporti di pubblico impiego"), R("dpr115:9", "superiore a tre volte")),
    ]
    a.dubbi.append("Notifica all'amministrazione statale: va eseguita presso l'Avvocatura dello Stato del distretto "
                   "(r.d. 1611/1933); la norma non è ancora leggibile nella biblioteca di IUSENTRA: verificarla prima del deposito.")


def _interessi(a: Analisi) -> None:
    a.inquadramento.append(p(
        "Accessori: per i crediti retributivi dei dipendenti pubblici non si cumulano interessi e rivalutazione; si "
        "riconosce la maggior somma fra i due, perché l'importo degli interessi è portato in detrazione dal maggior danno "
        "da svalutazione (regola estesa agli emolumenti dei dipendenti pubblici).",
        R("l724:22", "si applica anche agli emolumenti di natura retributiva"),
        R("l724:22", "spettanti ai dipendenti pubblici e privati"),
        R("l412:16", "portato in detrazione dalle somme eventualmente spettanti a ristoro del maggior danno")))


def _prescrizione(a: Analisi) -> None:
    a.termini.append(p("Prescrizione: i crediti retributivi, come tutto ciò che si paga periodicamente ad anno o in termini "
                       "più brevi, si prescrivono in cinque anni da ciascuna scadenza; nessuna decadenza per il ricorso.",
                       R("cc:2948", "si prescrivono in cinque anni"), R("cc:2948", "deve pagarsi periodicamente ad anno")))
    a.termini.append(p("La sospensione feriale non si applica alle controversie di lavoro.",
                       R("l742:3", "controversie previste dagli articoli 429")))


def _extra_retribuzioni(a: Analisi, c: Comprensione, f: Fatti) -> None:
    _comuni(a, c, f)
    _interessi(a)
    _prescrizione(a)


DIFFERENZE = Scheda(
    regola="pi_differenze_retributive", materia="pubblico impiego",
    nome="differenze retributive del dipendente pubblico",
    segnali=(PA, _RETRIB), esclusi=(_CARTA, _CARRIERA, r"licenzia", r"precett|pignor|ottemper"),
    punteggio=6, modello="LAV_005",
    capito="Dipendente di una pubblica amministrazione che chiede trattamento economico non corrisposto o differenze retributive.",
    rimedio="ricorso ex art. 414 c.p.c. al giudice del lavoro per la condanna dell'amministrazione al pagamento delle differenze",
    conclusione=[p("Il trattamento economico fondamentale e accessorio è definito dai contratti collettivi e le "
                   "amministrazioni devono garantire parità di trattamento contrattuale e trattamenti non inferiori a "
                   "quelli dei contratti collettivi: le differenze non pagate si chiedono con ricorso al giudice del lavoro.",
                   R("dlgs165:45", "e definito dai contratti collettivi"),
                   R("dlgs165:45", "trattamenti non inferiori a quelli previsti dai rispettivi contratti collettivi"),
                   R("dlgs165:63", "sono devolute al giudice ordinario, in funzione di giudice del lavoro"))],
    cosa_fare=["Raccogliere contratti individuali, cedolini, CCNL di comparto e conteggi analitici per mese.",
               "Individuare l'ufficio di assegnazione (foro dell'art. 413, quinto comma, c.p.c.).",
               "Interrompere la prescrizione con diffida scritta all'amministrazione se le prime mensilità sono vicine ai cinque anni.",
               "Verificare il reddito del ricorrente per il contributo unificato."],
    dati=["amministrazione datrice e ufficio di assegnazione", "tipo di contratto (ruolo, tempo determinato, supplenza)",
          "voci retributive richieste e periodo", "CCNL di comparto applicato", "reddito imponibile del ricorrente (contributo unificato)"],
    avvertenze=["Per i dipendenti pubblici non si usa il foro dell'azienda (art. 413, secondo comma): vale l'ufficio di assegnazione."],
    bozza=Bozza("Ricorso ex art. 414 c.p.c.", "condanna dell'amministrazione al pagamento delle differenze retributive",
                ["Rapporto di lavoro alle dipendenze dell'amministrazione resistente, qualifica e ufficio: [da completare].",
                 "Trattamento economico dovuto secondo il contratto collettivo di comparto (art. 45 d.lgs. 165/2001) e "
                 "somme non corrisposte: [da completare] (conteggi allegati).",
                 "Giurisdizione del giudice ordinario del lavoro (art. 63 d.lgs. 165/2001) e competenza del giudice "
                 "dell'ufficio di assegnazione (art. 413, quinto comma, c.p.c.)."],
                "condannare l'amministrazione resistente al pagamento in favore del ricorrente della somma di [da completare], "
                "oltre interessi legali o rivalutazione monetaria nella misura maggiore; con vittoria di spese.",
                "contratti, cedolini, conteggi, CCNL di comparto.", "artt. 413 e 414 c.p.c.; art. 63 d.lgs. 165/2001"),
    extra=_extra_retribuzioni,
)


def _extra_carta(a: Analisi, c: Comprensione, f: Fatti) -> None:
    _comuni(a, c, f)
    _prescrizione(a)


CARTA_DOCENTE = Scheda(
    regola="pi_carta_docente", materia="pubblico impiego", nome="carta del docente",
    segnali=(_CARTA,), punteggio=7, modello="LAV_005",
    capito="Docente (di ruolo o supplente) che chiede la carta elettronica per l'aggiornamento e la formazione non attribuita.",
    rimedio="ricorso ex art. 414 c.p.c. al giudice del lavoro per l'accertamento del diritto alla carta per gli anni "
            "scolastici indicati e la condanna del Ministero all'attribuzione o al risarcimento per equivalente",
    conclusione=[
        p("La carta elettronica per l'aggiornamento e la formazione spetta, nel testo vigente, al docente di ruolo, al "
          "docente con supplenza annuale su posto vacante e disponibile e al docente con supplenza fino al termine delle "
          "attività didattiche, oltre al personale educativo; l'importo è fino a 500 euro annui per anno scolastico.",
          R("l107:1", "del docente con contratto di supplenza annuale su posto vacante e disponibile"),
          R("l107:1", "supplenza fino al termine delle attivita' didattiche"),
          R("l107:1", "dell'importo fino a euro 500 annui")),
        p("Per gli anni anteriori all'estensione del testo, il diritto dei supplenti si fonda sul divieto di "
          "discriminazione dei lavoratori a termine e va chiesto al giudice del lavoro, che ha giurisdizione sul rapporto.",
          R("dlgs165:63", "sono devolute al giudice ordinario, in funzione di giudice del lavoro")),
    ],
    cosa_fare=["Elencare per ogni anno scolastico il contratto (ruolo, supplenza al 31/08, al 30/06, breve) e la scuola.",
               "Verificare se il docente è ancora in servizio: se non lo è, la domanda è di risarcimento per equivalente.",
               "Interrompere la prescrizione con diffida al Ministero per gli anni più vecchi."],
    dati=["anni scolastici e tipo di contratto per ciascuno", "scuola e ufficio di assegnazione", "servizio attuale (in ruolo, supplente, cessato)",
          "eventuali carte già ricevute"],
    dubbi=["Prescrizione e ammontare per gli anni passati: verificare l'orientamento della Cassazione nell'archivio "
           "SentenzeWeb prima di indicarli al cliente."],
    bozza=Bozza("Ricorso ex art. 414 c.p.c.", "accertamento del diritto alla carta elettronica del docente",
                ["Servizi prestati dal ricorrente negli anni scolastici [da completare] con contratti [da completare].",
                 "Diritto alla carta elettronica per l'aggiornamento e la formazione (art. 1, comma 121, l. 107/2015) e "
                 "divieto di discriminazione dei lavoratori a tempo determinato.",
                 "Giurisdizione del giudice ordinario del lavoro (art. 63 d.lgs. 165/2001)."],
                "accertare il diritto del ricorrente alla carta elettronica per gli anni scolastici [da completare] e "
                "condannare il Ministero all'attribuzione o, in subordine, al risarcimento per equivalente; con vittoria di spese.",
                "contratti di supplenza, certificato di servizio.", "artt. 413 e 414 c.p.c.; art. 1, comma 121, l. 107/2015"),
    extra=_extra_carta,
)


def _extra_termine(a: Analisi, c: Comprensione, f: Fatti) -> None:
    _comuni(a, c, f)
    a.termini.append(p("La sospensione feriale non si applica alle controversie di lavoro.",
                       R("l742:3", "controversie previste dagli articoli 429")))


ABUSO_TERMINE = Scheda(
    regola="pi_abuso_termine", materia="pubblico impiego", nome="abuso dei contratti a termine nella PA",
    segnali=(PA, _TERMINE), esclusi=(_CARTA,), punteggio=7, modello="LAV_005",
    capito="Lavoratore con una successione di contratti a termine con una pubblica amministrazione.",
    rimedio="ricorso ex art. 414 c.p.c. al giudice del lavoro per il risarcimento del danno da abuso (non per la conversione)",
    conclusione=[
        p("Con la pubblica amministrazione la violazione delle norme imperative sull'assunzione non può comportare la "
          "costituzione di un rapporto a tempo indeterminato: il lavoratore ha diritto al risarcimento del danno.",
          R("dlgs165:36", "non puo' comportare la costituzione di rapporti di lavoro a tempo indeterminato"),
          R("dlgs165:36", "ha diritto al risarcimento del danno")),
        p("Per l'abuso nella successione di contratti a termine il giudice liquida un'indennità fra quattro e ventiquattro "
          "mensilità dell'ultima retribuzione utile per il TFR, secondo la gravità della violazione, il numero dei "
          "contratti e la durata complessiva, salva la prova del maggior danno.",
          R("dlgs165:36", "un minimo di quattro e un massimo di ventiquattro mensilita'"),
          R("dlgs165:36", "fatta salva la facolta' per il lavoratore di provare il maggior danno")),
    ],
    cosa_fare=["Ricostruire tutti i contratti (date, posto vacante o no, ragioni) e la durata complessiva.",
               "Verificare se è intervenuta l'immissione in ruolo o la stabilizzazione: incide sul danno risarcibile.",
               "Calcolare l'ultima retribuzione di riferimento per il TFR."],
    dati=["elenco dei contratti con date e sede", "posto vacante e disponibile o supplenza temporanea",
          "eventuale immissione in ruolo e data", "ultima retribuzione di riferimento per il TFR"],
    dubbi=["La forbice da 4 a 24 mensilità è quella del testo vigente dell'art. 36, comma 5: per i giudizi già pendenti e "
           "per i contratti anteriori verificare la disciplina transitoria e l'orientamento delle Sezioni Unite "
           "nell'archivio SentenzeWeb."],
    avvertenze=["Nel pubblico impiego non si chiede la conversione del rapporto: la domanda è risarcitoria."],
    extra=_extra_termine,
)


def _extra_carriera(a: Analisi, c: Comprensione, f: Fatti) -> None:
    _comuni(a, c, f)
    _interessi(a)
    _prescrizione(a)


RICOSTRUZIONE = Scheda(
    regola="pi_ricostruzione_carriera", materia="pubblico impiego", nome="ricostruzione di carriera del docente",
    segnali=(_CARRIERA,), esclusi=(_CARTA,), punteggio=7, modello="LAV_005",
    capito="Docente immesso in ruolo che chiede il riconoscimento del servizio pre-ruolo ai fini giuridici ed economici.",
    rimedio="ricorso ex art. 414 c.p.c. per l'accertamento del diritto al riconoscimento del servizio non di ruolo e le differenze",
    conclusione=[
        p("Al docente delle scuole secondarie immesso in ruolo dall'anno scolastico 2023/2024 e confermato, il servizio "
          "non di ruolo prestato nelle scuole statali e pareggiate è riconosciuto come servizio di ruolo, ai fini "
          "giuridici ed economici, per intero, purché prestato senza demerito e con il titolo richiesto.",
          R("dlgs297:485", "riconosciuto come servizio di ruolo, ai fini giuridici ed economici, per intero"),
          R("dlgs297:485", "prestati senza demerito")),
        p("Per i docenti immessi in ruolo prima di quell'anno la richiesta di riconoscimento integrale si fonda sul "
          "divieto di discriminazione dei lavoratori a termine e si propone al giudice del lavoro.",
          R("dlgs165:63", "sono devolute al giudice ordinario, in funzione di giudice del lavoro")),
    ],
    cosa_fare=["Acquisire il decreto di ricostruzione di carriera e il certificato dei servizi pre-ruolo.",
               "Confrontare l'anzianità riconosciuta con il servizio effettivo e calcolare le differenze stipendiali.",
               "Verificare la data di immissione in ruolo (prima o dopo l'a.s. 2023/2024)."],
    dati=["data di immissione e conferma in ruolo", "ordine di scuola", "servizi pre-ruolo con date",
          "decreto di ricostruzione già emesso"],
    dubbi=["Regime dei docenti immessi in ruolo prima dell'a.s. 2023/2024 e decorrenza della prescrizione: verificare "
           "l'orientamento della Cassazione nell'archivio prima di indicarli al cliente."],
    extra=_extra_carriera,
)


def _extra_esecuzione(a: Analisi, c: Comprensione, f: Fatti) -> None:
    a.giudice = ("giudice dell'esecuzione (pignoramento presso terzi: foro dell'Avvocatura dello Stato del distretto del "
                 "creditore) oppure TAR per l'ottemperanza del giudicato")


ESECUZIONE_PA = Scheda(
    regola="pi_esecuzione_pa", materia="pubblico impiego", nome="esecuzione contro la PA e ottemperanza",
    segnali=(PA_ESEC, _ESECUZIONE, _TITOLO), esclusi=(_CARTA, r"sentenza del (?:tar|consiglio di stato)|tar passata|del tar\b"),
    punteggio=7,
    capito="Creditore di una pubblica amministrazione con un titolo (sentenza o decreto) non pagato.",
    rimedio="notificare il titolo, attendere 120 giorni, poi precetto e pignoramento presso terzi; in alternativa, "
            "passata in giudicato la sentenza, ricorso per ottemperanza al TAR",
    conclusione=[
        p("Le amministrazioni dello Stato e gli enti pubblici non economici completano il pagamento entro centoventi "
          "giorni dalla notificazione del titolo esecutivo: prima di quel termine il creditore non può procedere a "
          "esecuzione forzata né notificare il precetto.",
          R("dl669:14", "entro il termine di centoventi giorni dalla notificazione del titolo esecutivo"),
          R("dl669:14", "il creditore non puo' procedere ad esecuzione forzata ne' alla notifica di atto di precetto")),
        p("In alternativa all'esecuzione civile, per le sentenze del giudice ordinario passate in giudicato si propone "
          "l'azione di ottemperanza, anche senza previa diffida, al TAR nella cui circoscrizione ha sede il giudice che "
          "ha emesso la sentenza.",
          R("cpa:112", "delle sentenze passate in giudicato e degli altri provvedimenti ad esse equiparati del giudice ordinario"),
          R("cpa:113", "nella cui circoscrizione ha sede il giudice che ha emesso"),
          R("cpa:114", "anche senza previa diffida")),
    ],
    competenza=[p("Pignoramento di crediti contro una pubblica amministrazione: è competente il giudice del luogo dove ha "
                  "sede l'ufficio dell'Avvocatura dello Stato nel cui distretto il creditore ha la residenza o la sede.",
                  R("cpc:26bis", "nel cui distretto il creditore ha la residenza"))],
    termini=[p("L'azione di ottemperanza si prescrive in dieci anni dal passaggio in giudicato della sentenza.",
               R("cpa:114", "si prescrive con il decorso di dieci anni dal passaggio in giudicato"))],
    scadenze=[Scadenza("precetto non prima di", 120, "giorni", r"(?:titolo|sentenza|decreto)[^0-9]{0,40}notificat\w*(?: il)?",
                       (R("dl669:14", "entro il termine di centoventi giorni dalla notificazione del titolo esecutivo"),),
                       sospensione_feriale=False, sostanziale=True)],
    cosa_fare=["Notificare il titolo esecutivo all'amministrazione (con la formula esecutiva) e annotare la data.",
               "Decorsi 120 giorni senza pagamento: precetto e pignoramento presso la tesoreria, oppure ottemperanza se c'è giudicato.",
               "Con l'ottemperanza chiedere anche la nomina del commissario ad acta e la penalità di mora."],
    dati=["titolo (sentenza, decreto ingiuntivo) e data di notificazione all'amministrazione", "passaggio in giudicato",
          "importo dovuto e pagamenti parziali", "residenza del creditore (foro dell'Avvocatura)"],
    avvertenze=["Il precetto notificato prima dei 120 giorni è inefficace come atto di esecuzione: si espone a opposizione."],
    extra=_extra_esecuzione,
)


def _extra_competenza(a: Analisi, c: Comprensione, f: Fatti) -> None:
    _comuni(a, c, f)
    a.conclusione = [a.competenza[1], a.competenza[0]]


COMPETENZA_PI = Scheda(
    regola="pi_competenza", materia="pubblico impiego", nome="giudice e foro del dipendente pubblico",
    segnali=(PA, r"foro|competen|quale (?:giudice|tribunale)|giurisdizion|\btar\b|giudice del lavoro"),
    alcuni=(r"dipendent|lavorator|docent|supplen|personale|impiego|rapport\w* di lavoro|scatti|carriera",),
    esclusi=(r"precett|pignor|ottemper|permesso di costruire|aggiudicazion|gara",), punteggio=5,
    capito="Domanda su giudice e foro competente per una controversia di un dipendente pubblico.",
    extra=_extra_competenza,
)

# Differenze retributive, foro ed esecuzione contro la PA hanno anche le regole ricorso_dipendente_pubblico ed
# esecuzione_contro_pa (fattispecie/pubblico.py), che sono prima nell'elenco e vincono a parità di punteggio: queste
# schede rispondono solo alle formulazioni che quelle non riconoscono (es. «differenze stipendiali del docente supplente
# contro il Ministero»).
SCHEDE = (CARTA_DOCENTE, ABUSO_TERMINE, RICOSTRUZIONE, ESECUZIONE_PA, DIFFERENZE, COMPETENZA_PI)
