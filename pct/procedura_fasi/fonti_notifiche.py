"""Fonti degli obblighi di notifica che nascono dalle comunicazioni ricevute (pct/notifiche_obblighi).

Ogni estratto riassume fedelmente il testo vigente letto il 05/11/2026 dall'archivio Normattiva del software
(``normative_articles`` di ``codici_leggi.sqlite``, la stessa via di ``lex/testi_ufficiali.py``): c.p.c., disp. att.
c.p.p., c.p.p., D.Lgs. 274/2000, c.p.a., Testo unico della giustizia tributaria (D.Lgs. 175/2024), Codice della crisi
(D.Lgs. 14/2019), L. 53/1994. Le voci già presenti nel registro (``cpc_415``, ``cpc_435``, ``cpc_644``,
``cpc_281undecies``, ``cpc_473bis14``, ``cpc_615``, ``cpc_617``, ``rd1611_art11``, ``l53_art3bis``…) non si ripetono.
"""

from __future__ import annotations

from typing import Any

VERIFICA_NOTIFICHE = "testo vigente letto dall'archivio Normattiva del software il 05/11/2026"
_VERIFICA_06_11 = "testo vigente letto dall'archivio Normattiva del software il 06/11/2026"

_NORMATTIVA = "https://www.normattiva.it/uri-res/N2Ls?"
_CPC = "urn:nir:stato:regio.decreto:1940-10-28;1443"
_CPP = "urn:nir:stato:decreto.del.presidente.della.repubblica:1988-09-22;447"
_CPP_ATT = "urn:nir:stato:decreto.legislativo:1989-07-28;271"
_GDP_PEN = "urn:nir:stato:decreto.legislativo:2000-08-28;274"
_CPA = "urn:nir:stato:decreto.legislativo:2010-07-02;104"
_TU_TRIB = "urn:nir:stato:decreto.legislativo:2024-11-14;175"
_CCII = "urn:nir:stato:decreto.legislativo:2019-01-12;14"
_L53 = "urn:nir:stato:legge:1994-01-21;53"
_DPR115 = "urn:nir:stato:decreto.del.presidente.della.repubblica:2002-05-30;115"


def _voce(norma: str, titolo: str, atto: str, art: str, estratto: str, verifica: str = VERIFICA_NOTIFICHE) -> dict[str, Any]:
    return {"norma": norma, "titolo": titolo, "url": f"{_NORMATTIVA}{atto}~art{art}", "verifica": verifica, "estratto": estratto}


FONTI_NOTIFICHE: dict[str, dict[str, Any]] = {
    # ── Processo civile ──────────────────────────────────────────────────
    "cpc_102": _voce("art. 102 c.p.c.", "Litisconsorzio necessario", _CPC, "102",
        "Se la decisione non può pronunciarsi che in confronto di più parti e il processo è promosso da alcune o contro alcune "
        "soltanto di esse, il giudice ordina l'integrazione del contraddittorio in un termine perentorio da lui stabilito."),
    "cpc_137": _voce("art. 137 c.p.c.", "Notificazioni", _CPC, "137",
        "Le notificazioni, quando non è disposto altrimenti, sono eseguite dall'ufficiale giudiziario, su istanza di parte; "
        "l'ufficiale giudiziario o l'avvocato esegue la notificazione mediante consegna al destinatario di copia conforme "
        "all'originale; se il destinatario non possiede un indirizzo PEC l'ufficiale giudiziario consegna una copia su carta "
        "dichiarata conforme all'originale."),
    "cpc_144": _voce("art. 144 c.p.c.", "Notificazione alle amministrazioni dello Stato", _CPC, "144",
        "Per le amministrazioni dello Stato si osservano le disposizioni delle leggi speciali che prescrivono la notificazione "
        "presso gli uffici dell'Avvocatura dello Stato; negli altri casi la notificazione si fa direttamente presso l'amministrazione."),
    "cpc_155": _voce("art. 155 c.p.c.", "Computo dei termini", _CPC, "155",
        "Nel computo dei termini a giorni o ad ore si escludono il giorno o l'ora iniziali; i giorni festivi si computano nel termine; "
        "se il giorno di scadenza è festivo o sabato la scadenza è prorogata di diritto al primo giorno seguente non festivo."),
    "cpc_164": _voce("art. 164 c.p.c.", "Nullità della citazione", _CPC, "164",
        "Se il convenuto non si costituisce, il giudice, rilevata la nullità della citazione, ne dispone d'ufficio la rinnovazione "
        "entro un termine perentorio; se la rinnovazione non viene eseguita, il giudice ordina la cancellazione della causa dal "
        "ruolo e il processo si estingue a norma dell'articolo 307, comma terzo."),
    "cpc_170": _voce("art. 170 c.p.c.", "Notificazioni e comunicazioni nel corso del procedimento", _CPC, "170",
        "Dopo la costituzione in giudizio tutte le notificazioni e le comunicazioni si fanno al procuratore costituito, salvo che "
        "la legge disponga altrimenti."),
    "cpc_269": _voce("art. 269 c.p.c.", "Chiamata di un terzo in causa", _CPC, "269",
        "La citazione è notificata al terzo a cura del convenuto, o dell'attore autorizzato dal giudice, entro il termine "
        "perentorio stabilito dal giudice e nel rispetto dei termini dell'articolo 163-bis; la parte che chiama in causa il terzo "
        "deposita la citazione notificata entro il termine dell'articolo 165."),
    "cpc_285": _voce("art. 285 c.p.c.", "Modo di notificazione della sentenza", _CPC, "285",
        "La notificazione della sentenza, al fine della decorrenza del termine per l'impugnazione, si fa, su istanza di parte, a "
        "norma dell'articolo 170."),
    "cpc_291": _voce("art. 291 c.p.c.", "Contumacia del convenuto", _CPC, "291",
        "Se il convenuto non si costituisce e il giudice rileva un vizio che importi nullità nella notificazione della citazione, "
        "fissa all'attore un termine perentorio per rinnovarla; se l'ordine di rinnovazione non è eseguito il giudice ordina la "
        "cancellazione della causa dal ruolo e il processo si estingue."),
    "cpc_330": _voce("art. 330 c.p.c.", "Notificazione dell'impugnazione", _CPC, "330",
        "Se nell'atto di notificazione della sentenza la parte ha dichiarato la residenza, eletto domicilio o indicato un indirizzo "
        "PEC da pubblici elenchi, l'impugnazione si notifica lì; altrimenti, ai sensi dell'articolo 170, presso il procuratore "
        "costituito o all'indirizzo PEC risultante da pubblici elenchi o al domicilio digitale speciale indicato per il giudizio."),
    "cpc_618": _voce("art. 618 c.p.c.", "Provvedimenti del giudice dell'esecuzione", _CPC, "618",
        "Il giudice dell'esecuzione fissa con decreto l'udienza di comparizione delle parti davanti a sé e il termine perentorio "
        "per la notificazione del ricorso e del decreto."),
    "cpc_619": _voce("art. 619 c.p.c.", "Opposizione di terzo all'esecuzione", _CPC, "619",
        "Il terzo che pretende la proprietà o altro diritto reale sui beni pignorati propone opposizione con ricorso al giudice "
        "dell'esecuzione, che fissa con decreto l'udienza e il termine perentorio per la notificazione del ricorso e del decreto."),
    "cpc_643": _voce("art. 643 c.p.c.", "Notificazione del decreto d'ingiunzione", _CPC, "643",
        "Il ricorso e il decreto sono notificati per copia autentica a norma degli articoli 137 e seguenti; la notificazione "
        "determina la pendenza della lite."),
    "cpc_660": _voce("art. 660 c.p.c.", "Forma dell'intimazione di licenza o di sfratto", _CPC, "660",
        "Le intimazioni di licenza o di sfratto sono notificate a norma degli articoli 137 e seguenti, esclusa la notificazione al "
        "domicilio eletto; tra il giorno della notificazione dell'intimazione e quello dell'udienza debbono intercorrere termini "
        "liberi non minori di venti giorni."),
    "cpc_669sexies": _voce("art. 669-sexies c.p.c.", "Procedimento cautelare", _CPC, "669sexies",
        "Quando la convocazione della controparte potrebbe pregiudicare l'attuazione del provvedimento, il giudice provvede con "
        "decreto motivato, fissa l'udienza di comparizione entro un termine non superiore a quindici giorni e assegna all'istante "
        "un termine perentorio non superiore a otto giorni per la notificazione del ricorso e del decreto; i termini sono "
        "triplicati se la notificazione deve effettuarsi all'estero."),
    "cpc_669octies": _voce("art. 669-octies c.p.c.", "Provvedimento cautelare di accoglimento", _CPC, "669octies",
        "L'ordinanza di accoglimento resa prima della causa di merito fissa un termine perentorio non superiore a sessanta giorni "
        "per l'inizio del giudizio di merito; in mancanza il termine è di sessanta giorni e decorre dalla pronuncia in udienza o "
        "dalla comunicazione."),
    "cpc_840ter": _voce("art. 840-ter c.p.c.", "Azione di classe: forma della domanda", _CPC, "840ter",
        "Il ricorso, unitamente al decreto di fissazione dell'udienza, è pubblicato a cura della cancelleria entro dieci giorni "
        "dal deposito del decreto nell'area pubblica del portale dei servizi telematici."),
    # ── Processo penale ──────────────────────────────────────────────────
    "cpp_78": _voce("art. 78 c.p.p.", "Formalità della costituzione di parte civile", _CPP, "78",
        "Se è presentata fuori udienza, la dichiarazione di costituzione di parte civile deve essere notificata, a cura della parte "
        "civile, alle altre parti e produce effetto per ciascuna di esse dal giorno nel quale è eseguita la notificazione."),
    "cpp_152": _voce("art. 152 c.p.p.", "Notificazioni richieste dalle parti private", _CPP, "152",
        "Salvo che la legge disponga altrimenti, le notificazioni richieste dalle parti private possono essere sostituite dalla "
        "notificazione con modalità telematiche eseguita dal difensore a mezzo di posta elettronica certificata o altro servizio "
        "elettronico di recapito certificato qualificato, ovvero dall'invio di copia dell'atto con raccomandata con avviso di ricevimento."),
    "cpp_395": _voce("art. 395 c.p.p.", "Presentazione e notificazione della richiesta di incidente probatorio", _CPP, "395",
        "La richiesta di incidente probatorio è depositata nella cancelleria del giudice per le indagini preliminari ed è notificata a "
        "cura di chi l'ha proposta al pubblico ministero e alle persone indicate nell'articolo 393; la prova della notificazione è "
        "depositata in cancelleria."),
    "cpp_79": _voce("art. 79 c.p.p.", "Termine per la costituzione di parte civile", _CPP, "79",
        "La costituzione di parte civile può avvenire per l'udienza preliminare, prima che siano ultimati gli accertamenti relativi "
        "alla costituzione delle parti, o, quando manca l'udienza preliminare, fino a che non siano compiuti gli adempimenti "
        "previsti dall'articolo 484 o dall'articolo 554-bis, comma 2; i termini sono stabiliti a pena di decadenza.", _VERIFICA_06_11),
    "cpp_396": _voce("art. 396 c.p.p.", "Deduzioni sulla richiesta di incidente probatorio", _CPP, "396",
        "Entro due giorni dalla notificazione della richiesta, il pubblico ministero ovvero la persona sottoposta alle indagini può "
        "presentare deduzioni sull'ammissibilità e sulla fondatezza della richiesta.", _VERIFICA_06_11),
    "cpp_398": _voce("art. 398 c.p.p.", "Provvedimenti sulla richiesta di incidente probatorio", _CPP, "398",
        "Entro due giorni dal deposito della prova della notifica, e comunque dopo la scadenza del termine dell'articolo 396, il "
        "giudice decide sulla richiesta; con l'ordinanza che l'accoglie stabilisce la data dell'udienza e fa notificare alla persona "
        "sottoposta alle indagini, alla persona offesa e ai difensori avviso del giorno, dell'ora e del luogo almeno due giorni prima.", _VERIFICA_06_11),
    "dispattcpp_142": _voce("art. 142 disp. att. c.p.p.", "Citazione di testimoni, periti e consulenti tecnici", _CPP_ATT, "142",
        "Quando per le notificazioni dei testimoni, dei periti, degli interpreti e dei consulenti tecnici è richiesto l'ufficiale "
        "giudiziario, le parti devono consegnargli gli atti di citazione in tempo utile e nel numero di copie necessario."),
    "dlgs274_art27": _voce("D.Lgs. 274/2000, art. 27", "Giudice di pace penale: decreto di convocazione sul ricorso immediato", _GDP_PEN, "27",
        "Il decreto, unitamente al ricorso, è notificato a cura del ricorrente al pubblico ministero, alla persona citata in giudizio "
        "e al suo difensore almeno venti giorni prima dell'udienza; entro lo stesso termine il ricorrente notifica il decreto alle "
        "altre persone offese di cui conosca l'identità."),
    # ── Processo amministrativo ──────────────────────────────────────────
    "cpa_41": _voce("art. 41 c.p.a.", "Notificazione del ricorso e suoi destinatari", _CPA, "41",
        "Il ricorso di annullamento è notificato, a pena di decadenza, alla pubblica amministrazione che ha emesso l'atto e ad almeno "
        "uno dei controinteressati; la notificazione nei confronti delle amministrazioni dello Stato segue le norme vigenti per la "
        "difesa in giudizio delle stesse."),
    "cpa_43": _voce("art. 43 c.p.a.", "Motivi aggiunti", _CPA, "43",
        "I motivi aggiunti si propongono mediante atto notificato alle parti; le notifiche alle controparti costituite avvengono ai "
        "sensi dell'articolo 170 del codice di procedura civile."),
    "cpa_44": _voce("art. 44 c.p.a.", "Vizi del ricorso e della notificazione", _CPA, "44",
        "Se è nulla la notificazione e il destinatario non si costituisce, il giudice, se l'esito negativo dipende da causa non "
        "imputabile al notificante, fissa al ricorrente un termine perentorio per rinnovarla; la rinnovazione impedisce ogni decadenza."),
    "cpa_49": _voce("art. 49 c.p.a.", "Integrazione del contraddittorio", _CPA, "49",
        "Nell'ordinare l'integrazione del contraddittorio il giudice fissa il termine e indica le parti cui il ricorso deve essere "
        "notificato; se l'atto non è tempestivamente notificato e depositato il giudice provvede ai sensi dell'articolo 35."),
    # ── Processo tributario (Testo unico D.Lgs. 175/2024) ────────────────
    "tu175_art58": _voce("D.Lgs. 175/2024, art. 58", "Litisconsorzio e intervento (ex art. 14 D.Lgs. 546/1992)", _TU_TRIB, "58",
        "Se il ricorso non è stato proposto da o nei confronti di tutti i soggetti interessati inscindibilmente è ordinata "
        "l'integrazione del contraddittorio mediante la loro chiamata in causa entro un termine stabilito a pena di decadenza."),
    "tu175_art60": _voce("D.Lgs. 175/2024, art. 60", "Comunicazioni e notificazioni (ex art. 16 D.Lgs. 546/1992)", _TU_TRIB, "60",
        "Le notificazioni sono fatte secondo gli articoli 137 e seguenti del codice di procedura civile, esclusivamente con modalità "
        "telematiche salvo i casi dell'articolo 61, comma 3."),
    "tu175_art87": _voce("D.Lgs. 175/2024, art. 87", "Richiesta di copie e notificazione della sentenza (ex art. 38 D.Lgs. 546/1992)", _TU_TRIB, "87",
        "Le parti hanno l'onere di provvedere direttamente alla notificazione della sentenza alle altre parti, depositando nei "
        "successivi trenta giorni l'originale o la copia autentica dell'originale notificato nella segreteria; se nessuna parte "
        "notifica si applica l'articolo 327, primo comma, del codice di procedura civile."),
    "tu175_art105": _voce("D.Lgs. 175/2024, art. 105", "Termini d'impugnazione (ex art. 51 D.Lgs. 546/1992)", _TU_TRIB, "105",
        "Se la legge non dispone diversamente il termine per impugnare la sentenza della corte di giustizia tributaria di primo e "
        "secondo grado è di sessanta giorni, decorrente dalla sua notificazione ad istanza di parte."),
    # ── Crisi d'impresa ──────────────────────────────────────────────────
    "ccii_art40": _voce("D.Lgs. 14/2019, art. 40", "Procedimento unitario: notificazione del ricorso e del decreto", _CCII, "40",
        "Sulla domanda del creditore, degli organi di controllo o del pubblico ministero, il ricorso e il decreto di convocazione sono "
        "notificati a cura dell'ufficio all'indirizzo PEC del debitore; se la notificazione non riesce per causa non imputabile al "
        "destinatario, la notifica è eseguita a cura del ricorrente di persona a norma dell'art. 107 D.P.R. 1229/1959."),
    # ── 06/11/2026: sentenza e sua esecuzione, spese di giustizia nel lavoro ──
    "cpc_292": _voce("art. 292 c.p.c.", "Notificazione e comunicazione di atti al contumace", _CPC, "292",
        "Le sentenze sono notificate alla parte contumace personalmente.", _VERIFICA_06_11),
    "cpc_431": _voce("art. 431 c.p.c.", "Esecutorietà della sentenza", _CPC, "431",
        "Le sentenze che pronunciano condanna a favore del lavoratore per crediti derivanti dai rapporti di cui all'articolo "
        "409 sono provvisoriamente esecutive.", _VERIFICA_06_11),
    "dl669_art14": _voce("D.L. 669/1996, art. 14", "Esecuzione forzata nei confronti delle pubbliche amministrazioni",
        "urn:nir:stato:decreto.legge:1996-12-31;669", "14",
        "Le amministrazioni dello Stato e gli enti pubblici non economici completano le procedure per l'esecuzione dei "
        "provvedimenti giurisdizionali aventi efficacia esecutiva e comportanti l'obbligo di pagamento di somme di denaro entro "
        "centoventi giorni dalla notificazione del titolo esecutivo; prima di tale termine il creditore non può procedere ad "
        "esecuzione forzata né alla notifica di atto di precetto.",
        "testo vigente (in vigore dal 12/08/2018) letto su Normattiva il 06/11/2026"),
    "cpa_112": _voce("art. 112 c.p.a.", "Disposizioni generali sul giudizio di ottemperanza", _CPA, "112",
        "L'azione di ottemperanza può essere proposta per conseguire l'attuazione delle sentenze passate in giudicato e degli "
        "altri provvedimenti ad esse equiparati del giudice ordinario, al fine di ottenere l'adempimento dell'obbligo della "
        "pubblica amministrazione di conformarsi, per quanto riguarda il caso deciso, al giudicato.", _VERIFICA_06_11),
    "dpr115_art9": _voce("D.P.R. 115/2002, art. 9", "Contributo unificato", _DPR115, "9",
        "Nelle controversie individuali di lavoro o concernenti rapporti di pubblico impiego le parti sono soggette al "
        "contributo unificato solo se titolari di un reddito imponibile, risultante dall'ultima dichiarazione, superiore a tre "
        "volte l'importo previsto dall'articolo 76 (comma 1-bis).", _VERIFICA_06_11),
    "dpr115_art30": _voce("D.P.R. 115/2002, art. 30", "Anticipazioni forfettarie all'erario nel processo civile", _DPR115, "30",
        "La parte che per prima si costituisce o deposita il ricorso introduttivo anticipa in modo forfettizzato euro 27, "
        "eccetto che nei processi previsti dall'articolo unico della legge 2 aprile 1958, n. 319, e in quelli in cui si applica "
        "lo stesso articolo.", _VERIFICA_06_11),
    # ── Notificazioni in proprio ─────────────────────────────────────────
    "l53_art11": _voce("L. 53/1994, art. 11", "Nullità delle notificazioni in proprio", _L53, "11",
        "Le notificazioni sono nulle, e la nullità è rilevabile d'ufficio, se mancano i requisiti soggettivi e oggettivi previsti, se "
        "non sono osservate le disposizioni della legge e se vi è incertezza sulla persona cui è consegnata la copia o sulla data."),
}
