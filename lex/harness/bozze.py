"""Bozze d'atto dell'harness: struttura del modello del catalogo e contenuto obbligatorio della norma vigente.

La bozza della citazione segue l'art. 163, comma 3, c.p.c. (nn. 1-7) e la scheda CIV_ORD_001 del catalogo dei modelli
(«Atto di citazione ordinario»). I dati che l'avvocato non ha scritto restano «[da completare]». È una bozza da rivedere:
non viene salvata, firmata, notificata né depositata.
"""
from __future__ import annotations

import re

from .fatti import Fatti, euro
from .modello import Analisi

DA = "[da completare]"


def _fatto(testo: str) -> str:
    """«Il 12/02/2026 Ferrandina ha versato…» → «In data 12/02/2026 Ferrandina ha versato…»; il resto come scritto."""
    testo = re.sub(r"^(?:Il|il|In data)\s+(\d{1,2}/\d{1,2}/\d{4})\s*,?\s*", r"In data \1 ", testo.strip())
    return testo.rstrip(".") + "."


def _fatti_numerati(f: Fatti) -> list[str]:
    return [f"{n}. {_fatto(e.testo)}" for n, e in enumerate(f.eventi, 1)]


def citazione_caparra(f: Fatti, a: Analisi, caparra: float, doppio: float) -> str:
    attore = f.assistita.nome or DA
    convenuto = f.controparte.nome or DA
    citta = f.residenza_convenuto or DA
    ufficio = a.giudice or f"Tribunale di {citta}"
    righe = [
        f"{ufficio.upper()}",
        "ATTO DI CITAZIONE",
        "(artt. 163 ss. c.p.c.)",
        "",
        f"Per: {attore}, nato a {DA} il {DA}, codice fiscale {DA}, residente in {DA}, rappresentato e difeso, giusta procura "
        f"in calce/allegata, dall'avv. {DA} (codice fiscale {DA}, PEC {DA}), presso il cui studio in {DA} elegge domicilio "
        "– attore –",
        "",
        f"Contro: {convenuto}, nato a {DA} il {DA}, codice fiscale {DA}, residente in {citta}, {DA} – convenuto –",
        "",
        "OGGETTO DELLA DOMANDA (art. 163, comma 3, n. 3, c.p.c.)",
        f"Accertamento del legittimo recesso dell'attore dal contratto preliminare di compravendita per inadempimento del "
        f"convenuto e condanna del convenuto al pagamento del doppio della caparra confirmatoria, pari a {euro(doppio)}, "
        "oltre interessi legali.",
        "",
        "CONDIZIONE DI PROCEDIBILITÀ (art. 163, comma 3, n. 3-bis, c.p.c.)",
        f"In data {DA} l'attore ha invitato il convenuto a stipulare una convenzione di negoziazione assistita ai sensi "
        f"dell'art. 3 d.l. 132/2014 (invito ricevuto il {DA}); l'invito non è stato seguito da adesione entro trenta giorni "
        "[oppure: è stato rifiutato / la negoziazione si è conclusa senza accordo il " + DA + "].",
        "",
        "FATTO (art. 163, comma 3, n. 4, c.p.c.)",
        *_fatti_numerati(f),
        f"{len(f.eventi) + 1}. Con il contratto preliminare le parti hanno qualificato espressamente la somma di "
        f"{euro(caparra)} come caparra confirmatoria ai sensi dell'art. 1385 c.c. (clausola 6).",
        f"{len(f.eventi) + 2}. Il convenuto non ha stipulato il contratto definitivo, non si è presentato davanti al notaio "
        "nella data fissata, non ha adempiuto nel termine assegnato con la diffida e ha offerto l'immobile in vendita a terzi.",
        "",
        "DIRITTO",
        "1. Inadempimento grave e imputabile del promittente venditore. La mancata comparizione per la stipula, "
        "documentata dal verbale notarile, il silenzio sulla diffida ad adempiere e l'offerta dell'immobile a terzi "
        "integrano un inadempimento di non scarsa importanza (art. 1455 c.c.), che rende definitivamente impossibile "
        "l'attuazione del preliminare.",
        "2. Recesso e doppio della caparra. Ai sensi dell'art. 1385, comma 2, c.c., se inadempiente è la parte che ha "
        "ricevuto la caparra, l'altra può recedere dal contratto ed esigere il doppio della caparra. L'attore esercita il "
        "recesso [con la dichiarazione del " + DA + " e comunque] con il presente atto e chiede il pagamento di "
        f"{euro(doppio)}. La domanda non richiede la prova del danno, che la caparra liquida in via anticipata; non si "
        "chiede la risoluzione con il risarcimento secondo le norme generali (art. 1385, comma 3, c.c.).",
        "3. In subordine. Ove il contratto si ritenga già risolto di diritto per l'inutile decorso del termine della "
        "diffida (art. 1454 c.c.), resta fermo il diritto dell'attore a conseguire il doppio della caparra come "
        "liquidazione convenzionale del danno conseguente all'inadempimento del convenuto [verificare la giurisprudenza "
        "di legittimità prima del deposito].",
        f"4. Competenza. Il valore della causa è di {euro(doppio)} (artt. 10 e 14 c.p.c.) ed eccede il limite del giudice di "
        f"pace (art. 7 c.p.c.): è competente il tribunale (art. 9 c.p.c.). Il convenuto risiede in {citta}: foro generale "
        "dell'art. 18 c.p.c.; concorre il foro dell'obbligazione dell'art. 20 c.p.c.",
        "5. Interessi. Sono dovuti gli interessi legali dalla domanda (o dalla dichiarazione di recesso) al saldo "
        "(art. 1224 c.c.).",
        "",
        "CONCLUSIONI",
        f"Voglia l'Ill.mo Tribunale adito, contrariis reiectis: 1) in via principale, accertare e dichiarare il legittimo "
        f"recesso dell'attore dal contratto preliminare per grave inadempimento del convenuto e, per l'effetto, condannare "
        f"{convenuto} al pagamento in favore di {attore} della somma di {euro(doppio)}, pari al doppio della caparra "
        "confirmatoria versata, oltre interessi legali dalla domanda al saldo; 2) in subordine, accertata la risoluzione di "
        "diritto del contratto per inadempimento del convenuto ai sensi dell'art. 1454 c.c., condannare il convenuto al "
        f"pagamento della medesima somma di {euro(doppio)} a titolo di liquidazione convenzionale del danno, oltre interessi; "
        "3) con vittoria di spese e compensi del giudizio, oltre rimborso forfettario, IVA e CPA come per legge.",
        "",
        "MEZZI DI PROVA E DOCUMENTI (art. 163, comma 3, n. 5, c.p.c.)",
        "Si producono: 1) contratto preliminare di compravendita; 2) contabile del bonifico della caparra; 3) convocazione "
        "dal notaio (PEC o raccomandata) con ricevuta; 4) verbale notarile di mancata comparizione; 5) diffida ad adempiere "
        "con ricevuta; 6) annuncio di vendita a terzi; 7) invito alla negoziazione assistita e relativo esito. "
        "Ci si riserva ogni ulteriore deduzione e produzione nei termini dell'art. 171-ter c.p.c.",
        "",
        "INVITO E AVVERTIMENTI (art. 163, comma 3, n. 7, c.p.c.)",
        f"Si cita {convenuto} a comparire all'udienza del {DA} [almeno 120 giorni liberi dopo la notificazione, art. 163-bis "
        f"c.p.c.], ore di rito, davanti al {ufficio}, giudice designato ai sensi dell'art. 168-bis c.p.c., con invito a "
        "costituirsi nel termine di settanta giorni prima dell'udienza indicata, nelle forme dell'art. 166 c.p.c., e a "
        "comparire all'udienza indicata, con l'avvertimento che la costituzione oltre i suddetti termini implica le "
        "decadenze di cui agli artt. 38 e 167 c.p.c.; che la difesa tecnica mediante avvocato è obbligatoria in tutti i "
        "giudizi davanti al tribunale, fuori dei casi previsti dall'art. 86 c.p.c. o da leggi speciali; che la parte, "
        "sussistendone i presupposti di legge, può presentare istanza per l'ammissione al patrocinio a spese dello Stato.",
        "",
        f"Ai fini del contributo unificato si dichiara che il valore della causa è di {euro(doppio)}.",
        "",
        f"{DA}, {DA}",
        f"Avv. {DA}",
        "",
        "PROCURA ALLE LITI (art. 83 c.p.c.)",
        f"Io sottoscritto {attore} delego a rappresentarmi e difendermi nel presente giudizio, in ogni sua fase e grado, "
        f"l'avv. {DA}, conferendo ogni facoltà di legge; eleggo domicilio presso il suo studio. Dichiaro di aver ricevuto "
        "l'informativa sul trattamento dei dati personali e sulla possibilità della mediazione e della negoziazione assistita.",
        f"Firma {DA}   Per autentica: Avv. {DA}",
        "",
        "— Bozza preparata da Lex sul modello del catalogo CIV_ORD_001: da rivedere, non salvata, non firmata, non notificata. —",
    ]
    return "\n".join(righe)


def comparsa_generica(f: Fatti) -> str:
    return "\n".join([
        "TRIBUNALE DI " + DA,
        "R.G. n. " + DA + " – Giudice " + DA + " – Udienza del " + DA,
        "COMPARSA DI COSTITUZIONE E RISPOSTA (artt. 166 e 167 c.p.c.)",
        "",
        f"Per: {f.assistita.nome or DA}, codice fiscale {DA}, rappresentato e difeso dall'avv. {DA} – convenuto –",
        f"Contro: {f.controparte.nome or DA} – attore –",
        "",
        "PREMESSO IN FATTO: " + DA,
        "ECCEZIONI PROCESSUALI E DI MERITO (da proporre a pena di decadenza, art. 167 c.p.c.): " + DA,
        "EVENTUALE DOMANDA RICONVENZIONALE E CHIAMATA DEL TERZO: " + DA,
        "CONCLUSIONI: voglia il Tribunale rigettare le domande avversarie perché infondate in fatto e in diritto; con "
        "vittoria di spese e compensi.",
        "MEZZI DI PROVA E DOCUMENTI: " + DA,
        "",
        "— Bozza preparata da Lex: da rivedere, non salvata, non depositata. —",
    ])


def ricorso_generico(titolo: str, ufficio: str, f: Fatti, oggetto: str, diritto: list[str], conclusioni: str,
                     documenti: str, norme_struttura: str) -> str:
    righe = [
        (ufficio or "UFFICIO GIUDIZIARIO " + DA).upper(),
        titolo.upper(),
        f"({norme_struttura})",
        "",
        f"Per: {f.assistita.nome or DA}, codice fiscale {DA}, residente/con sede in {DA}, rappresentato e difeso dall'avv. {DA} "
        f"(PEC {DA}) giusta procura allegata – ricorrente –",
        f"Contro: {f.controparte.nome or DA}, codice fiscale/partita IVA {DA}, residente/con sede in {f.residenza_convenuto or DA} – resistente –",
        "",
        "OGGETTO: " + oggetto,
        "",
        "FATTO",
        *(_fatti_numerati(f) or ["1. " + DA]),
        "",
        "DIRITTO",
        *[f"{n}. {d}" for n, d in enumerate(diritto, 1)],
        "",
        "CONCLUSIONI",
        conclusioni,
        "",
        "DOCUMENTI: " + documenti,
        "",
        f"{DA}, {DA} – Avv. {DA}",
        "",
        "— Bozza preparata da Lex: da rivedere, non salvata, non firmata, non depositata. —",
    ]
    return "\n".join(righe)
