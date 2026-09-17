"""Fonti normative e ministeriali della conoscenza procedurale.

Ogni fase, termine o adempimento descritto in questo pacchetto rimanda a una
voce di questo registro. Ogni voce riporta la norma, il titolo, l'URL ufficiale,
la data e l'esito della consultazione e un estratto letterale del testo
vigente: la conoscenza è citabile e verificabile, non ricordata.

Le fonti sono state consultate il 14/09/2026 su Normattiva (testo vigente),
sul Portale dei Servizi Telematici del Ministero della Giustizia e sulle
Specifiche tecniche DGSIA del 7 agosto 2024 (PDF ufficiale conservato in
docs/specs/ministero). Dove una fonte non era raggiungibile, la voce lo dice.
"""

from __future__ import annotations

from typing import Any

_NORMATTIVA = "https://www.normattiva.it/uri-res/N2Ls?"
_CPC = "urn:nir:stato:regio.decreto:1940-10-28;1443"
_DISP_ATT = "urn:nir:stato:regio.decreto:1941-12-18;1368"
_CPP = "urn:nir:stato:decreto.del.presidente.della.repubblica:1988-09-22;447"
_CPA = "urn:nir:stato:decreto.legislativo:2010-07-02;104"
_TU_TRIB = "urn:nir:stato:decreto.legislativo:2024-11-14;175"
_DM44 = "urn:nir:ministero.giustizia:decreto:2011-02-21;44"
_L53 = "urn:nir:stato:legge:1994-01-21;53"
_DL179 = "urn:nir:stato:decreto.legge:2012-10-18;179"
_L890 = "urn:nir:stato:legge:1982-11-20;890"
_DLGS28 = "urn:nir:stato:decreto.legislativo:2010-03-04;28"
_L247 = "urn:nir:stato:legge:2012-12-31;247"

VERIFICA_NORMATTIVA = "testo vigente consultato su Normattiva il 14/09/2026"
VERIFICA_DGSIA = (
    "Specifiche tecniche DGSIA 7 agosto 2024 (art. 34 D.M. 44/2011), PDF ufficiale scaricato dal PST e "
    "conservato in docs/specs/ministero/Specifiche_Tecniche_DGSIA_DM44_2011_2024_08_07.pdf; consultato il 14/09/2026"
)
_PST_DOWNLOAD = "https://pst.giustizia.it/PST/it/download.page"


def _norma(norma: str, titolo: str, atto: str, art: str, estratto: str, *, verifica: str = VERIFICA_NORMATTIVA) -> dict[str, Any]:
    return {
        "norma": norma,
        "titolo": titolo,
        "url": f"{_NORMATTIVA}{atto}~art{art}",
        "verifica": verifica,
        "estratto": estratto,
    }


def _dgsia(articolo: int, titolo: str, estratto: str) -> dict[str, Any]:
    return {
        "norma": f"Specifiche tecniche DGSIA 7/8/2024, art. {articolo}",
        "titolo": titolo,
        "url": _PST_DOWNLOAD,
        "verifica": VERIFICA_DGSIA,
        "estratto": estratto,
    }


FONTI: dict[str, dict[str, Any]] = {
    # ── Codice di procedura civile ──────────────────────────────────────────
    "cpc_136": _norma("art. 136 c.p.c.", "Comunicazioni", _CPC, "136",
        "Il cancelliere fa le comunicazioni prescritte dalla legge o dal giudice; la comunicazione è effettuata a mezzo posta elettronica certificata all'indirizzo risultante dai pubblici elenchi o al domicilio digitale speciale eletto."),
    "cpc_147": _norma("art. 147 c.p.c.", "Tempo delle notificazioni", _CPC, "147",
        "Le notificazioni a mezzo PEC possono essere eseguite senza limiti orari; si perfezionano per il notificante quando è generata la ricevuta di accettazione e per il destinatario quando è generata la ricevuta di avvenuta consegna; se questa è generata tra le 21 e le 7, la notificazione si intende perfezionata per il destinatario alle ore 7."),
    "cpc_163bis": _norma("art. 163-bis c.p.c.", "Termini per comparire", _CPC, "163bis",
        "Tra il giorno della notificazione della citazione e quello dell'udienza di comparizione debbono intercorrere termini liberi non minori di centoventi giorni se il luogo della notificazione si trova in Italia e di centocinquanta giorni se si trova all'estero."),
    "cpc_165": _norma("art. 165 c.p.c.", "Costituzione dell'attore", _CPC, "165",
        "L'attore, entro dieci giorni dalla notificazione della citazione al convenuto, deve costituirsi in giudizio iscrivendo la causa a ruolo e depositando l'originale della citazione, la procura e i documenti offerti in comunicazione."),
    "cpc_166": _norma("art. 166 c.p.c.", "Costituzione del convenuto", _CPC, "166",
        "Il convenuto deve costituirsi almeno settanta giorni prima dell'udienza di comparizione fissata nell'atto di citazione depositando la comparsa di cui all'articolo 167 con la copia della citazione notificata, la procura e i documenti."),
    "cpc_171bis": _norma("art. 171-bis c.p.c.", "Verifiche preliminari", _CPC, "171bis",
        "Scaduto il termine di cui all'articolo 166, entro i successivi quindici giorni il giudice istruttore verifica d'ufficio la regolarità del contraddittorio e, quando occorre, pronuncia i provvedimenti previsti e fissa nuova udienza."),
    "cpc_171ter": _norma("art. 171-ter c.p.c.", "Memorie integrative", _CPC, "171ter",
        "Le parti, a pena di decadenza, con memorie integrative possono: 1) almeno quaranta giorni prima dell'udienza di cui all'articolo 183, proporre le domande e le eccezioni conseguenti, precisare o modificare domande, eccezioni e conclusioni; seguono la seconda e la terza memoria nei termini di legge."),
    "cpc_183": _norma("art. 183 c.p.c.", "Prima comparizione delle parti e trattazione della causa", _CPC, "183",
        "All'udienza fissata per la prima comparizione e la trattazione le parti devono comparire personalmente; la mancata comparizione senza giustificato motivo costituisce comportamento valutabile ai sensi dell'articolo 116, secondo comma."),
    "cpc_189": _norma("art. 189 c.p.c.", "Rimessione al collegio", _CPC, "189",
        "Il giudice istruttore fissa l'udienza per la rimessione della causa al collegio e assegna alle parti termini perentori: un termine non superiore a sessanta giorni prima dell'udienza per le note di precisazione delle conclusioni, poi i termini per comparse conclusionali e memorie di replica."),
    "cpc_281undecies": _norma("art. 281-undecies c.p.c.", "Rito semplificato: forma della domanda e costituzione delle parti", _CPC, "281undecies",
        "La domanda si propone con ricorso, che contiene le indicazioni dell'articolo 163 e l'avvertimento sulle decadenze; il giudice, entro cinque giorni dalla designazione, fissa con decreto l'udienza di comparizione assegnando il termine per la costituzione del convenuto, che deve avvenire non oltre dieci giorni prima dell'udienza; ricorso e decreto sono notificati al convenuto."),
    "cpc_325": _norma("art. 325 c.p.c.", "Termini per le impugnazioni", _CPC, "325",
        "Il termine per proporre l'appello, la revocazione e l'opposizione di terzo è di trenta giorni; il termine per proporre il ricorso per cassazione è di sessanta giorni."),
    "cpc_327": _norma("art. 327 c.p.c.", "Decadenza dall'impugnazione", _CPC, "327",
        "Indipendentemente dalla notificazione, l'appello, il ricorso per cassazione e la revocazione non possono proporsi dopo decorsi sei mesi dalla pubblicazione della sentenza."),
    "cpc_414": _norma("art. 414 c.p.c.", "Rito del lavoro: forma della domanda", _CPC, "414",
        "La domanda si propone con ricorso, che deve contenere l'indicazione del giudice, delle parti, dell'oggetto, dei fatti e degli elementi di diritto, delle conclusioni e dei mezzi di prova."),
    "cpc_415": _norma("art. 415 c.p.c.", "Rito del lavoro: deposito del ricorso e decreto di fissazione dell'udienza", _CPC, "415",
        "Il giudice, entro cinque giorni dal deposito del ricorso, fissa con decreto l'udienza di discussione; tra il deposito e l'udienza non devono decorrere più di sessanta giorni; il ricorso con il decreto deve essere notificato al convenuto."),
    "cpc_416": _norma("art. 416 c.p.c.", "Rito del lavoro: costituzione del convenuto", _CPC, "416",
        "Il convenuto deve costituirsi almeno dieci giorni prima dell'udienza depositando una memoria difensiva nella quale devono essere proposte, a pena di decadenza, le domande riconvenzionali e le eccezioni non rilevabili d'ufficio."),
    "cpc_435": _norma("art. 435 c.p.c.", "Appello nel rito del lavoro: decreto del presidente", _CPC, "435",
        "Il presidente entro cinque giorni dal deposito del ricorso fissa, non oltre sessanta giorni, l'udienza di discussione; l'appellante, nei dieci giorni successivi al deposito del decreto, notifica ricorso e decreto all'appellato."),
    "cpc_480": _norma("art. 480 c.p.c.", "Forma del precetto", _CPC, "480",
        "Il precetto consiste nell'intimazione di adempiere l'obbligo risultante dal titolo esecutivo entro un termine non minore di dieci giorni, con l'avvertimento che, in mancanza, si procederà a esecuzione forzata."),
    "cpc_481": _norma("art. 481 c.p.c.", "Cessazione dell'efficacia del precetto", _CPC, "481",
        "Il precetto diventa inefficace se nel termine di novanta giorni dalla sua notificazione non è iniziata l'esecuzione; se contro il precetto è proposta opposizione, il termine rimane sospeso."),
    "cpc_497": _norma("art. 497 c.p.c.", "Cessazione dell'efficacia del pignoramento", _CPC, "497",
        "Il pignoramento perde efficacia quando dal suo compimento sono trascorsi quarantacinque giorni senza che sia stata richiesta l'assegnazione o la vendita."),
    "cpc_518": _norma("art. 518 c.p.c.", "Pignoramento mobiliare: forma e iscrizione a ruolo", _CPC, "518",
        "L'ufficiale giudiziario redige processo verbale delle operazioni; il creditore iscrive a ruolo il processo esecutivo nel termine di legge dalla consegna del verbale."),
    "cpc_543": _norma("art. 543 c.p.c.", "Pignoramento presso terzi: forma", _CPC, "543",
        "Il pignoramento di crediti del debitore verso terzi si esegue mediante atto notificato al terzo e al debitore; il creditore iscrive a ruolo il processo nel termine di legge dalla notificazione."),
    "cpc_557": _norma("art. 557 c.p.c.", "Pignoramento immobiliare: deposito dell'atto", _CPC, "557",
        "Il creditore iscrive a ruolo il processo depositando copie conformi del titolo esecutivo, del precetto, dell'atto di pignoramento e della nota di trascrizione entro quindici giorni dalla consegna dell'atto di pignoramento."),
    "cpc_615": _norma("art. 615 c.p.c.", "Opposizione all'esecuzione", _CPC, "615",
        "Quando si contesta il diritto della parte istante a procedere ad esecuzione forzata e questa non è ancora iniziata, si può proporre opposizione al precetto con citazione davanti al giudice competente."),
    "cpc_617": _norma("art. 617 c.p.c.", "Opposizione agli atti esecutivi", _CPC, "617",
        "Le opposizioni relative alla regolarità formale del titolo esecutivo e del precetto si propongono, prima che sia iniziata l'esecuzione, con atto di citazione da notificarsi nel termine perentorio di venti giorni dalla notificazione del titolo esecutivo o del precetto."),
    "cpc_641": _norma("art. 641 c.p.c.", "Decreto ingiuntivo: accoglimento della domanda", _CPC, "641",
        "Il giudice, con decreto motivato da emettere entro trenta giorni dal deposito del ricorso, ingiunge di pagare nel termine di quaranta giorni, con l'avvertimento che nello stesso termine può essere fatta opposizione."),
    "cpc_644": _norma("art. 644 c.p.c.", "Decreto ingiuntivo: mancata notificazione", _CPC, "644",
        "Il decreto d'ingiunzione diventa inefficace qualora la notificazione non sia eseguita nel termine di sessanta giorni dalla pronuncia (novanta se all'estero); la domanda può essere riproposta."),
    "cpc_647": _norma("art. 647 c.p.c.", "Decreto ingiuntivo: esecutorietà per mancata opposizione", _CPC, "647",
        "Se non è stata fatta opposizione nel termine stabilito, oppure l'opponente non si è costituito, il giudice, su istanza anche verbale del ricorrente, dichiara esecutivo il decreto."),
    "cpc_669terdecies": _norma("art. 669-terdecies c.p.c.", "Reclamo contro i provvedimenti cautelari", _CPC, "669terdecies",
        "Contro l'ordinanza con la quale è stato concesso o negato il provvedimento cautelare è ammesso reclamo nel termine perentorio di quindici giorni dalla pronuncia in udienza ovvero dalla comunicazione o dalla notificazione se anteriore."),
    # ── Disposizioni di attuazione c.p.c. (deposito telematico, dopo la riforma Cartabia) ──
    "dispatt_196quater": _norma("art. 196-quater disp. att. c.p.c.", "Obbligatorietà del deposito telematico", _DISP_ATT, "196quater",
        "Il deposito degli atti processuali e dei documenti da parte del pubblico ministero, dei difensori e dei soggetti nominati o delegati dall'autorità giudiziaria ha luogo esclusivamente con modalità telematiche."),
    "dispatt_196sexies": _norma("art. 196-sexies disp. att. c.p.c.", "Perfezionamento del deposito con modalità telematiche", _DISP_ATT, "196sexies",
        "Il deposito con modalità telematiche si ha per avvenuto nel momento in cui è generata la conferma del completamento della trasmissione ed è tempestivamente eseguito quando la conferma è generata entro la fine del giorno di scadenza."),
    "dispatt_196undecies": _norma("art. 196-undecies disp. att. c.p.c.", "Modalità dell'attestazione di conformità", _DISP_ATT, "196undecies",
        "L'attestazione di conformità della copia analogica è apposta in calce o a margine della copia o su foglio separato; quella di una copia informatica è apposta nel medesimo documento informatico o su documento separato secondo le specifiche tecniche."),
    # ── D.M. 44/2011 e Specifiche tecniche DGSIA ───────────────────────────
    "dm44_art13": _norma("D.M. 44/2011, art. 13", "Trasmissione dei documenti da parte dei soggetti abilitati esterni nel procedimento civile", _DM44, "13",
        "I documenti informatici si intendono ricevuti dal dominio giustizia nel momento in cui viene generata la conferma della trasmissione secondo le specifiche tecniche; la conferma attesta l'avvenuto deposito dell'atto presso l'ufficio giudiziario competente."),
    "dm44_art16": _norma("D.M. 44/2011, art. 16", "Comunicazioni o notificazioni per via telematica dall'ufficio giudiziario", _DM44, "16",
        "La comunicazione o la notificazione per via telematica da un soggetto abilitato interno a un soggetto abilitato esterno avviene mediante invio di un messaggio dalla PEC dell'ufficio giudiziario alla PEC del destinatario risultante dal ReGIndE o dagli altri pubblici elenchi."),
    "dgsia_art17": _dgsia(17, "Trasmissione di atti da parte dei soggetti abilitati esterni nel procedimento civile",
        "Il gestore dei servizi telematici effettua i controlli automatici sulla busta: WARN (anomalia non bloccante), ERROR (bloccante, serve l'intervento della cancelleria), FATAL (bloccante, busta non elaborabile). In caso di FATAL invia una PEC di rifiuto; in caso di accettazione, anche dopo l'intervento della cancelleria, invia una PEC di avvenuto deposito."),
    "dgsia_art19": _dgsia(19, "Trasmissione di atti da parte dei soggetti abilitati esterni nel procedimento penale (PDP)",
        "Il PDP genera la ricevuta di accettazione del deposito con identificativo unico nazionale anno/numero e data e ora dell'invio. Stati del deposito: INVIATO, IN TRANSITO, ACCETTATO (automaticamente o dopo verifiche), IN VERIFICA (anomalia bloccante, dati non coincidenti), RIFIUTATO (motivazione sul PDP), ERRORE TECNICO (ripetere il deposito)."),
    "dgsia_art21": _dgsia(21, "Comunicazioni e notificazioni per via telematica",
        "Il gestore dei servizi telematici invia le comunicazioni e notificazioni dell'ufficio alla PEC del destinatario recuperata dai pubblici elenchi; la comunicazione è nel corpo del messaggio e nel file Comunicazione.xml; le ricevute e gli avvisi di mancata consegna sono conservati nel fascicolo informatico."),
    "dgsia_art26": _dgsia(26, "Notificazioni per via telematica eseguite dagli avvocati",
        "L'atto originale informatico da notificare è in PDF o PDF/A ottenuto da documento testuale, senza scansione di immagini; le ricevute previste dall'art. 3-bis, comma 3, L. 53/1994 e la copia dell'atto notificato sono trasmesse all'ufficio inserendole nella busta telematica, con i dati delle ricevute nel DatiAtto.xml."),
    # ── Notificazioni ─────────────────────────────────────────────────────
    "l53_art3bis": _norma("L. 53/1994, art. 3-bis", "Notificazione con modalità telematica", _L53, "3bis",
        "La notificazione con modalità telematica si esegue a mezzo di posta elettronica certificata all'indirizzo risultante da pubblici elenchi, nel rispetto della normativa concernente la sottoscrizione, la trasmissione e la ricezione dei documenti informatici."),
    "l53_art9": _norma("L. 53/1994, art. 9", "Deposito dell'atto notificato", _L53, "9",
        "Nei casi in cui il cancelliere deve prendere nota dell'avvenuta notificazione di un atto di opposizione o di impugnazione, il notificante provvede, contestualmente alla notifica, a depositare copia dell'atto notificato."),
    "dl179_art16ter": _norma("D.L. 179/2012, art. 16-ter", "Pubblici elenchi per notificazioni e comunicazioni", _DL179, "16ter",
        "Ai fini della notificazione e comunicazione degli atti in materia civile, penale, amministrativa, contabile e stragiudiziale si intendono per pubblici elenchi quelli previsti dagli articoli 6-bis, 6-quater e 62 del CAD, dall'art. 16, comma 12, del decreto (ReGIndE) e dall'INI-PEC."),
    "l890_art8": _norma("L. 890/1982, art. 8", "Notificazioni a mezzo posta: mancato recapito e giacenza", _L890, "8",
        "Se il piego non può essere recapitato, è depositato entro due giorni lavorativi presso il punto di deposito più vicino al destinatario; del tentativo di notifica e del deposito è data notizia al destinatario con avviso raccomandato; la notificazione si ha comunque per eseguita trascorsi dieci giorni dalla data di spedizione della lettera raccomandata (compiuta giacenza), o dalla data del ritiro del piego se anteriore."),
    # ── Procedura penale ───────────────────────────────────────────────────
    "cpp_111bis": _norma("art. 111-bis c.p.p.", "Deposito telematico", _CPP, "111bis",
        "In ogni stato e grado del procedimento, il deposito di atti, documenti, richieste, memorie ha luogo esclusivamente con modalità telematiche, nel rispetto della normativa concernente la sottoscrizione, la trasmissione e la ricezione degli atti informatici."),
    "cpp_415bis": _norma("art. 415-bis c.p.p.", "Avviso all'indagato della conclusione delle indagini preliminari", _CPP, "415bis",
        "Prima della scadenza del termine delle indagini, il pubblico ministero, se non deve chiedere l'archiviazione, fa notificare alla persona sottoposta alle indagini e al difensore l'avviso della conclusione delle indagini preliminari, con l'avvertimento che l'indagato ha facoltà, entro il termine di venti giorni, di presentare memorie, produrre documenti, depositare documentazione di investigazioni difensive e chiedere di essere interrogato."),
    "cpp_429": _norma("art. 429 c.p.p.", "Decreto che dispone il giudizio", _CPP, "429",
        "Il decreto che dispone il giudizio contiene le generalità dell'imputato, l'indicazione della persona offesa, l'enunciazione del fatto in forma chiara e precisa, l'indicazione del giudice e della data dell'udienza; tra la data del decreto e la data fissata per il giudizio deve intercorrere un termine non inferiore a venti giorni."),
    "cpp_552": _norma("art. 552 c.p.p.", "Decreto di citazione a giudizio", _CPP, "552",
        "Il decreto di citazione a giudizio contiene le generalità dell'imputato, l'indicazione della persona offesa, l'enunciazione del fatto in forma chiara e precisa, l'indicazione del giudice e del luogo, giorno e ora della comparizione."),
    "cpp_585": _norma("art. 585 c.p.p.", "Termini per l'impugnazione", _CPP, "585",
        "Il termine per proporre impugnazione è di quindici giorni per i provvedimenti emessi in camera di consiglio, di trenta giorni nel caso dell'art. 544, comma 2, di quarantacinque giorni nel caso dell'art. 544, comma 3; i termini sono aumentati di quindici giorni per il difensore dell'imputato giudicato in assenza."),
    # ── Processo amministrativo ───────────────────────────────────────────
    "cpa_29": _norma("art. 29 c.p.a.", "Azione di annullamento", _CPA, "29",
        "L'azione di annullamento per violazione di legge, incompetenza ed eccesso di potere si propone nel termine di decadenza di sessanta giorni."),
    "cpa_45": _norma("art. 45 c.p.a.", "Deposito del ricorso e degli altri atti processuali", _CPA, "45",
        "Il ricorso e gli altri atti soggetti a preventiva notificazione sono depositati nella segreteria del giudice nel termine perentorio di trenta giorni, decorrente dal momento in cui l'ultima notificazione dell'atto si è perfezionata anche per il destinatario."),
    "cpa_46": _norma("art. 46 c.p.a.", "Costituzione delle parti intimate", _CPA, "46",
        "Nel termine di sessanta giorni dal perfezionamento nei propri confronti della notificazione del ricorso, le parti intimate possono costituirsi, presentare memorie, fare istanze, indicare i mezzi di prova e produrre documenti."),
    "cpa_92": _norma("art. 92 c.p.a.", "Termini per le impugnazioni", _CPA, "92",
        "Le impugnazioni si propongono con ricorso e devono essere notificate entro il termine perentorio di sessanta giorni decorrenti dalla notificazione della sentenza."),
    "cpa_dpcm_40_2016": {
        "norma": "D.P.C.M. 16 febbraio 2016, n. 40; d.P.C.S. 28 luglio 2021, mod. d.P.C.S. 9 maggio 2025",
        "titolo": "Regole tecnico-operative del processo amministrativo telematico (PAT): deposito con Formweb e moduli PEC",
        "url": "https://www.giustizia-amministrativa.it/documents/20142/74204502/Pubblicazione%2BRegole%2Btecnico-operative%2BPAT.pdf/db2b8d35-4e88-c32a-a7c6-15715348d34b?t=1748969121419",
        "verifica": (
            "documento ufficiale della Giustizia amministrativa «Nuove regole tecnico-operative del PAT» (d.P.C.S. 9 maggio 2025), "
            "PDF scaricato il 24/08/2026 e conservato in docs/specs/ministero/fonti_ufficiali/2026-08-24/pat-regole-tecnico-operative-2025.pdf "
            "(SHA-256 ceba3e41…d075); consultato il 15/09/2026"
        ),
        "estratto": (
            "accanto al consueto uso dei moduli di deposito trasmessi tramite posta elettronica certificata – i quali, nella fase a regime, "
            "come individuata dal d.P.C.S. 9 maggio 2025, rivestiranno una valenza residuale – per l'incardinamento dei ricorsi e per la "
            "produzione di atti aggiuntivi è prevista l'esecuzione dei depositi online attraverso una procedura che guida l'avvocato nella "
            "compilazione di un Formweb. […] Resta ferma la necessità della sottoscrizione digitale prima dell'invio per il deposito da parte del soggetto legittimato."
        ),
    },
    # ── Processo tributario: Testo unico D.Lgs. 175/2024 (gli artt. 18-23 D.Lgs. 546/1992 sono abrogati) ──
    "tu175_art61": _norma("D.Lgs. 175/2024, art. 61", "Comunicazioni, notificazioni e depositi telematici (ex art. 16-bis D.Lgs. 546/1992)", _TU_TRIB, "61",
        "Le comunicazioni sono effettuate mediante posta elettronica certificata ai sensi del D.Lgs. 82/2005; le notificazioni e i depositi seguono le modalità telematiche del processo tributario."),
    "tu175_art64": _norma("D.Lgs. 175/2024, art. 64", "Il ricorso (ex art. 18 D.Lgs. 546/1992)", _TU_TRIB, "64",
        "Il processo è introdotto con ricorso alla corte di giustizia tributaria di primo grado; il ricorso deve contenere l'indicazione della corte, del ricorrente, dell'ente impositore, dell'atto impugnato, dell'oggetto e dei motivi."),
    "tu175_art67": _norma("D.Lgs. 175/2024, art. 67", "Termine per la proposizione del ricorso (ex art. 21 D.Lgs. 546/1992)", _TU_TRIB, "67",
        "Il ricorso deve essere proposto a pena di inammissibilità entro sessanta giorni dalla data di notificazione dell'atto impugnato; la notificazione della cartella di pagamento vale anche come notificazione del ruolo."),
    "tu175_art68": _norma("D.Lgs. 175/2024, art. 68", "Costituzione in giudizio del ricorrente (ex art. 22 D.Lgs. 546/1992)", _TU_TRIB, "68",
        "Il ricorrente, entro trenta giorni dalla proposizione del ricorso, a pena d'inammissibilità lo deposita telematicamente nella segreteria della corte di giustizia tributaria adita."),
    "tu175_art69": _norma("D.Lgs. 175/2024, art. 69", "Costituzione in giudizio della parte resistente (ex art. 23 D.Lgs. 546/1992)", _TU_TRIB, "69",
        "L'ente impositore, l'agente della riscossione e i soggetti iscritti all'albo si costituiscono in giudizio entro sessanta giorni dal giorno in cui il ricorso è stato notificato, consegnato o ricevuto."),
    # ── Mediazione e incarico professionale ───────────────────────────────
    "dlgs28_art5": _norma("D.Lgs. 28/2010, art. 5", "Mediazione: condizione di procedibilità", _DLGS28, "5",
        "Chi intende esercitare in giudizio un'azione in materia di condominio, diritti reali, divisione, successioni, patti di famiglia, locazione, comodato, affitto di aziende, responsabilità medica e sanitaria, diffamazione a mezzo stampa, contratti assicurativi, bancari e finanziari, associazione in partecipazione, consorzio, franchising e altre materie indicate è tenuto preliminarmente a esperire il procedimento di mediazione."),
    "dlgs28_art6": _norma("D.Lgs. 28/2010, art. 6", "Mediazione: durata", _DLGS28, "6",
        "Il procedimento di mediazione ha una durata di sei mesi, prorogabile dopo la sua instaurazione e prima della sua scadenza per periodi di volta in volta non superiori a tre mesi."),
    "dlgs28_art8": _norma("D.Lgs. 28/2010, art. 8", "Mediazione: procedimento", _DLGS28, "8",
        "Il responsabile dell'organismo designa un mediatore e fissa il primo incontro tra le parti, che deve tenersi non prima di venti e non oltre quaranta giorni dal deposito della domanda, salvo diversa concorde indicazione delle parti."),
    "l247_art13": _norma("L. 247/2012, art. 13", "Conferimento dell'incarico e compenso", _L247, "13",
        "Il compenso è pattuito di regola per iscritto all'atto del conferimento dell'incarico; il professionista è tenuto a comunicare in forma scritta a chi conferisce l'incarico la prevedibile misura del costo della prestazione."),
}


# Snapshot istituzionali consultabili nel lettore interno; URL e impronte sono
# conservati nel manifesto di acquisizione, separati dalla sintesi operativa.
FONTI.update({
    "cpc_127ter": _norma("art. 127-ter c.p.c.", "Deposito di note scritte in sostituzione dell’udienza", _CPC, "127ter",
        "Il giudice dispone la sostituzione dell’udienza e assegna il termine per le note. L’opposizione decorre dalla comunicazione del provvedimento, non dalla ricevuta di un deposito. Il termine delle note è considerato data di udienza.",
        verifica="Testo integrale consultato su Normattiva, note all’art. 3 D.Lgs. 164/2024, il 16/09/2026."),
    "cpc_309": _norma("art. 309 c.p.c.", "Mancata comparizione all’udienza", _CPC, "309",
        "Se nel corso del processo nessuna delle parti si presenta all’udienza, il giudice provvede a norma del primo comma dell’articolo 181.",
        verifica="Testo acquisito dalla banca dati normativa istituzionale MEF il 16/09/2026."),
    "dgsia_2024": {"norma": "Specifiche tecniche DGSIA 7/8/2024", "titolo": "Testo integrale delle specifiche tecniche", "estratto": "Documento ufficiale, da leggere con le rettifiche del 16/09/2024 e del 30/10/2024.", "verifica": "PDF ufficiale PST acquisito e confrontato il 16/09/2026.", "url": _PST_DOWNLOAD},
    "dgsia_modifica_art27": {"norma": "Rettifica DGSIA 16/09/2024", "titolo": "Rettifica degli artt. 17, comma 4, e 27, comma 1", "estratto": "Corregge il riferimento all’art. 196-undecies disp. att. c.p.c. e sostituisce «la busta telematica» con «l’atto.enc» nell’art. 17, comma 4.", "verifica": "PDF ufficiale PST acquisito e confrontato il 16/09/2026.", "url": _PST_DOWNLOAD},
    "dgsia_rettifica": {"norma": "Rettifica DGSIA 30/10/2024", "titolo": "Rettifica dell’art. 19, comma 12, lettera c)", "estratto": "Per denuncia, querela e istanza di procedimento l’accoglimento equivale al ricevimento nel ReGeWEB; è eliminato il riferimento all’iscrizione.", "verifica": "PDF ufficiale PST acquisito e confrontato il 16/09/2026.", "url": _PST_DOWNLOAD},
})
for _id in ("cpc_127ter", "cpc_309", "dgsia_2024", "dgsia_modifica_art27", "dgsia_rettifica"):
    FONTI[_id]["reader_url"] = f"/api/v1/ui/fonti-procedurali/{_id}/visualizza"
for _id, _voce in FONTI.items():
    if _id.startswith("dgsia_") and not _voce.get("reader_url"):
        _voce["reader_url"] = "/api/v1/ui/fonti-procedurali/dgsia_2024/visualizza"
        _voce["verifica"] = "PDF ufficiale PST, con rettifiche del 16/09/2024 e 30/10/2024; consultato il 16/09/2026."


def fonte(identificativo: str) -> dict[str, Any]:
    """La voce del registro, o un dizionario vuoto se l'identificativo non esiste."""
    voce = FONTI.get(str(identificativo or "").strip())
    return dict(voce) if voce else {}


def fonti(identificativi: list[str] | tuple[str, ...]) -> list[dict[str, Any]]:
    righe: list[dict[str, Any]] = []
    visti: set[str] = set()
    for identificativo in identificativi:
        chiave = str(identificativo or "").strip()
        if not chiave or chiave in visti or chiave not in FONTI:
            continue
        visti.add(chiave)
        righe.append({"id": chiave, **FONTI[chiave]})
    return righe


def norme(identificativi: list[str] | tuple[str, ...]) -> str:
    """Le norme in una riga, per i testi della lettura («art. 165 c.p.c.; L. 53/1994, art. 3-bis»)."""
    return "; ".join(voce["norma"] for voce in fonti(identificativi))


__all__ = ["FONTI", "VERIFICA_DGSIA", "VERIFICA_NORMATTIVA", "fonte", "fonti", "norme"]
