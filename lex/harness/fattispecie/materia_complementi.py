"""Schede complementari: strumenti che hanno già una regola nell'elenco principale (fattispecie/*.py) ma che quella regola
non riconosce in alcune formulazioni libere. Hanno punteggio 2 e vengono dopo nell'elenco: cedono sempre alla regola
principale e rispondono solo dove l'altra tace. Dove la regola principale dà una risposta sbagliata sullo strumento (clausole
vessatorie, sospensiva al TAR, esecuzione in forma specifica) il punteggio è più alto e lo si dichiara nella scheda.

Base normativa (testo vigente, istantanea dati/norme_vigenti_materie.json): vedi le norme citate in ciascuna scheda.
"""
from __future__ import annotations

from .schede import R, Scadenza, Scheda, p

_MEDIAZIONE = p("La materia rientra fra quelle per cui la mediazione è condizione di procedibilità.",
                R("dlgs28:5", "condizione di procedibilita"))
_FERIALE_NO = p("La sospensione feriale non si applica alle controversie di lavoro e di previdenza.",
                R("l742:3", "controversie previste dagli articoli 429"))

SEQUESTRO = Scheda(
    regola="cau_sequestro", materia="cautelare e urgenza", nome="sequestro conservativo e giudiziario",
    segnali=(r"sequestr",), esclusi=(r"preventiv|probatori|penal|imputat|reato",), punteggio=2,
    capito="Sequestro conservativo (garanzia del credito) o giudiziario (bene conteso), prima o durante la causa.",
    rimedio="ricorso per sequestro al giudice competente per il merito",
    conclusione=[
        p("Il sequestro conservativo si chiede quando il creditore ha fondato timore di perdere la garanzia del credito, sui "
          "beni del debitore nei limiti in cui sono pignorabili.", R("cpc:671", "fondato timore di perdere la garanzia del proprio credito")),
        p("Il sequestro giudiziario si chiede su beni di cui è controversa la proprietà o il possesso, quando è opportuno "
          "provvedere alla custodia o alla gestione temporanea.",
          R("cpc:670", "quando ne e' controversa la proprieta' o il possesso")),
        p("Prima della causa la domanda va al giudice competente per il merito; accolta, il merito va iniziato nel termine "
          "fissato o entro sessanta giorni, altrimenti il sequestro perde efficacia.",
          R("cpc:669ter", "la domanda si propone al giudice competente a conoscere del merito"),
          R("cpc:669octies", "termine perentorio di sessanta giorni"), R("cpc:669novies", "perde la sua efficacia")),
    ],
    dati=["credito o diritto conteso", "condotte che mettono a rischio la garanzia", "beni da sequestrare", "data dell'ordinanza"],
)

RICORSO_CREDITO = Scheda(
    regola="mon_ricorso_credito", materia="monitorio", nome="recupero rapido del credito con decreto ingiuntivo",
    segnali=(r"recuper\w* (?:il )?credit|prova scritta|ottenere l ingiunzione|decreto ingiuntivo|ingiunzion",),
    esclusi=(r"oppo|tardiv|ordinanza.ingiunzione|provvisori|notific\w* (?:il decreto|entro)|precett|contributo unificato", r"lavor|stipend"), punteggio=2,
    capito="Creditore con prova scritta che vuole un titolo esecutivo in tempi brevi.",
    rimedio="ricorso per decreto ingiuntivo al giudice competente per valore",
    conclusione=[
        p("Chi è creditore di una somma liquida ed esigibile, o di cose fungibili o mobili determinate, ottiene l'ingiunzione "
          "se fornisce prova scritta del diritto.", R("cpc:633", "se del diritto fatto valere si da' prova scritta")),
        p("Sono prove scritte anche le polizze e promesse unilaterali per scrittura privata e i telegrammi; per i crediti "
          "d'impresa gli estratti autentici delle scritture contabili.", R("cpc:634", "le polizze e promesse unilaterali")),
    ],
    dati=["credito, importo e scadenza", "prova scritta (contratto, fatture, riconoscimento di debito)", "sede del debitore"],
)

OPPOSIZIONE_DI = Scheda(
    regola="mon_opposizione_di", materia="monitorio", nome="opposizione a decreto ingiuntivo",
    segnali=(r"decreto ingiuntiv|ingiunzion|\bdecreto\b", r"oppo|contest|non (?:dovut|dovev)|mediazione|difend|prescritt|gia pagat"),
    esclusi=(r"tardiv|\b650\b|ordinanza.ingiunzione|\(creditore|provvisori|decreto (?:di|del) (?:espulsione|giudizio)|"
             r"decreto (?:del )?ministero|decreto cautelare"), punteggio=6,
    capito="Ingiunto che vuole contestare il decreto ingiuntivo notificato.",
    rimedio="atto di citazione in opposizione davanti all'ufficio che ha emesso il decreto, entro quaranta giorni dalla notifica",
    conclusione=[
        p("L'opposizione si propone davanti all'ufficio giudiziario al quale appartiene il giudice che ha emesso il decreto, con "
          "atto di citazione notificato al ricorrente nel termine indicato nel decreto.",
          R("cpc:645", "davanti all'ufficio giudiziario al quale appartiene il giudice che ha emesso il decreto")),
        p("Il termine ordinario è di quaranta giorni dalla notificazione.", R("cpc:641", "quaranta giorni")),
        p("Nelle materie di mediazione obbligatoria l'onere di avviare la mediazione nel giudizio di opposizione grava su chi "
          "ha chiesto il decreto ingiuntivo.", R("dlgs28:5bis", "grava sulla parte che ha proposto ricorso per decreto ingiuntivo")),
    ],
    scadenze=[Scadenza("opposizione entro", 40, "giorni", r"(?:decreto|ingiunzione)[^0-9]{0,60}notificat\w*(?: il)?",
                       (R("cpc:641", "quaranta giorni"),), modello="CIV_OPPOSIZIONE_DI")],
    dati=["decreto e relata di notifica", "motivi (pagamento, prescrizione, inesistenza del credito)", "materia (mediazione)"],
)

SEPARAZIONE = Scheda(
    regola="fam_separazione", materia="famiglia e minori", nome="separazione dei coniugi",
    segnali=(r"separar\w*|separazione", r"marit|moglie|coniug|sposat|matrimoni|figli|ricorso"),
    esclusi=(r"divorzi|negoziazione|modific|senza (?:andare in )?tribunale",), punteggio=2,
    capito="Coniuge che vuole separarsi, anche senza il consenso dell'altro.",
    rimedio="ricorso per separazione giudiziale (o congiunto per la consensuale) al tribunale",
    conclusione=[
        p("La separazione può essere chiesta quando si verificano, anche indipendentemente dalla volontà di uno o di entrambi "
          "i coniugi, fatti tali da rendere intollerabile la prosecuzione della convivenza.",
          R("cc:151", "intollerabile la prosecuzione della convivenza")),
        p("La domanda si propone con ricorso al tribunale secondo il rito unificato delle persone, dei minorenni e delle famiglie.",
          R("cpc:473bis12", "ricorso")),
    ],
    dati=["residenza dei coniugi e dei figli", "figli minori", "redditi e patrimonio", "fatti (anche violenze)"],
)

MODIFICA_CONDIZIONI = Scheda(
    regola="fam_modifica_condizioni", materia="famiglia e minori", nome="modifica dei provvedimenti su figli e contributi",
    segnali=(r"assegno|mantenimento|collocamento|contribut", r"ridurr|ridurlo|aumentar|abbassar|diminuir|piu alto|piu basso|modific|revision|"
             r"perso il lavoro|aumento di stipendio|trasferit"),
    esclusi=(r"negoziazione|non paga|pagamento diretto|maggiorenn|calcol", r"inps|pension|invalidit"), punteggio=2,
    capito="Richiesta di rivedere assegno, mantenimento o collocamento per fatti sopravvenuti.",
    rimedio="ricorso per la revisione dei provvedimenti al tribunale",
    conclusione=[p("Se sopravvengono giustificati motivi le parti possono chiedere in ogni tempo la revisione dei provvedimenti "
                   "a tutela dei minori e in materia di contributi economici.",
                   R("cpc:473bis29", "possono in ogni tempo chiedere"), R("cpc:473bis29", "in materia di contributi economici"))],
    dati=["provvedimento vigente", "fatti sopravvenuti e prove", "redditi attuali delle parti"],
)

MANTENIMENTO = Scheda(
    regola="fam_mantenimento", materia="famiglia e minori", nome="mantenimento dei figli e del coniuge",
    segnali=(r"mantenim|mantenut|assegno (?:per i figli|di mantenimento|periodico)|mantener\w*|pagamento diretto|assegno direttamente",),
    alcuni=(r"figli|coniug|moglie|marit|ex\b|separat|padre|madre",),
    esclusi=(r"negoziazione|modific|ridurr|aumentar|abbassar|diminuir|revision", r"invalidit|accompagnament"), punteggio=2,
    capito="Diritti e azioni sul mantenimento dei figli (anche maggiorenni) e del coniuge separato.",
    rimedio="domanda di determinazione del contributo; per l'inadempimento, ordine di pagamento diretto al terzo e titolo esecutivo",
    conclusione=[
        p("Ciascun genitore contribuisce al mantenimento in misura proporzionale al proprio reddito; il giudice fissa la misura "
          "e il modo del contributo.", R("cc:337ter", "la misura e il modo con cui ciascuno di essi deve contribuire al mantenimento")),
        p("Ai figli maggiorenni non indipendenti economicamente il giudice può riconoscere un assegno periodico, versato "
          "direttamente a loro salvo diversa decisione.", R("cc:337septies", "figli maggiorenni non indipendenti economicamente")),
        p("Al coniuge cui non è addebitabile la separazione e privo di adeguati redditi propri spetta quanto necessario al "
          "mantenimento, secondo le circostanze e i redditi dell'obbligato.",
          R("cc:156", "qualora egli non abbia adeguati redditi propri")),
        p("I provvedimenti sui contributi sono immediatamente esecutivi; se l'obbligato è inadempiente da almeno trenta giorni "
          "dopo la messa in mora, si può notificare il provvedimento al terzo (datore, ente) perché paghi direttamente.",
          R("cpc:473bis36", "sono immediatamente esecutivi"), R("cpc:473bis37", "inadempiente per un periodo di almeno trenta giorni")),
    ],
    dati=["provvedimento o accordo vigente", "redditi delle parti", "età e situazione dei figli", "mensilità non pagate"],
)

ORDINI_PROTEZIONE = Scheda(
    regola="fam_ordini_protezione", materia="famiglia e minori", nome="ordini di protezione contro gli abusi familiari",
    segnali=(r"violen|minacc|maltratt|picchia|abus", r"allontan|ordine (?:del giudice|di protezione)|fuori di casa|via di casa"),
    esclusi=(r"querel|denuncia penale|reato|imputat",), punteggio=2,
    capito="Condotte del coniuge o convivente (o di altro familiare convivente) che pregiudicano integrità o libertà.",
    rimedio="ricorso per ordine di protezione (allontanamento dalla casa familiare e divieto di avvicinamento)",
    conclusione=[
        p("Quando la condotta del coniuge o di altro convivente causa grave pregiudizio all'integrità fisica o morale o alla "
          "libertà dell'altro, il giudice su istanza di parte può adottare con decreto gli ordini di protezione.",
          R("cpc:473bis69", "grave pregiudizio all'integrita' fisica o morale ovvero alla liberta'")),
        p("Con il decreto il giudice ordina la cessazione della condotta, l'allontanamento dalla casa familiare e, se occorre, "
          "il divieto di avvicinarsi ai luoghi frequentati dalla vittima.",
          R("cpc:473bis70", "dispone l'allontanamento dalla casa familiare")),
    ],
    avvertenze=["Le vecchie norme del codice civile sugli ordini di protezione sono abrogate (d.lgs. 164/2024): la disciplina "
                "vigente è nel codice di procedura civile."],
    dati=["fatti e date", "convivenza", "figli", "procedimenti penali in corso"],
)

NEGOZIAZIONE_FAMILIARE = Scheda(
    regola="fam_negoziazione", materia="famiglia e minori", nome="negoziazione assistita familiare",
    segnali=(r"negoziazione|senza andare in tribunale|con gli avvocati",),
    alcuni=(r"separar|separazion|divorzi|coniug|assegno|figli|comune",), punteggio=4,
    capito="Separazione, divorzio o modifica delle condizioni con accordo negoziato dagli avvocati.",
    rimedio="convenzione di negoziazione assistita (almeno un avvocato per parte) e accordo trasmesso al procuratore della Repubblica",
    conclusione=[p("La negoziazione assistita da almeno un avvocato per parte può essere conclusa per separazione, divorzio, "
                   "modifica delle condizioni, affidamento e mantenimento dei figli nati fuori del matrimonio e alimenti.",
                   R("dl132:6", "da almeno un avvocato per parte"),
                   R("dl132:6", "modifica delle condizioni di separazione o di divorzio"))],
    dati=["figli minori o non autosufficienti", "condizioni concordate", "comune di trascrizione del matrimonio"],
)

DISCONOSCIMENTO = Scheda(
    regola="fam_disconoscimento", materia="famiglia e minori", nome="disconoscimento di paternità",
    segnali=(r"disconosc|test del dna|non (?:e|sia) (?:suo|il padre)", r"paternit|padre|figli"), punteggio=2,
    capito="Azione per far accertare che il marito non è padre del figlio nato in costanza di matrimonio.",
    rimedio="ricorso per disconoscimento di paternità",
    conclusione=[p("L'azione spetta al marito, alla madre e al figlio; per il figlio è imprescrittibile, per gli altri ci sono "
                   "termini di decadenza dalla nascita o dalla scoperta.",
                   R("cc:244", "imprescrittibile riguardo al figlio"))],
    dati=["data di nascita del figlio", "data della scoperta", "prova genetica"],
)

BENEFICIO_INVENTARIO = Scheda(
    regola="suc_beneficio_inventario", materia="successioni", nome="accettazione con beneficio d'inventario",
    segnali=(r"beneficio d inventario|beneficiat|eredit\w*[^.]{0,30}passiv|fare l inventario|\binventario\b",),
    punteggio=2,
    capito="Chiamato all'eredità che vuole tenere separati il proprio patrimonio e i debiti del defunto.",
    rimedio="dichiarazione di accettazione con beneficio d'inventario davanti al notaio o al cancelliere e redazione dell'inventario",
    conclusione=[
        p("L'accettazione con beneficio d'inventario si fa con dichiarazione ricevuta da un notaio o dal cancelliere del "
          "tribunale del luogo di apertura della successione.", R("cc:484", "ricevuta da un notaio o dal cancelliere del tribunale")),
        p("Il chiamato che possiede beni ereditari deve fare l'inventario entro tre mesi dall'apertura o dalla notizia; chi non "
          "li possiede può dichiarare finché il diritto non è prescritto e poi fare l'inventario entro tre mesi.",
          R("cc:485", "deve fare l'inventario entro tre mesi"), R("cc:487", "nel termine di tre mesi dalla dichiarazione")),
        p("Le eredità devolute a minori e interdetti si accettano solo con beneficio d'inventario.",
          R("cc:471", "se non col beneficio d'inventario")),
    ],
    dati=["data del decesso e della notizia", "possesso di beni ereditari", "minori fra i chiamati", "debiti noti"],
)

ESECUZIONE_2932 = Scheda(
    regola="con_esecuzione_2932", materia="contratti", nome="esecuzione in forma specifica dell'obbligo di concludere il contratto",
    segnali=(r"2932|forma specifica|sentenza che (?:trasferisca|produca gli effetti)|trasferimento (?:della casa|dell immobile)|"
             r"non (?:vuole piu fare|si presenta)[^.]{0,30}(?:rogito|dal notaio)|chiedere il trasferimento|trasferimento coattivo",),
    alcuni=(r"preliminar|rogito|notaio|promittent|venditor|compromesso|trasferiment",),
    esclusi=(r"caparra|obblig\w* di fare|612|demoli",), punteggio=6,
    capito="Promissario acquirente che vuole una sentenza che trasferisca il bene al posto del contratto definitivo.",
    rimedio="citazione ex art. 2932 c.c. con trascrizione della domanda (mediazione obbligatoria se diritti reali)",
    conclusione=[
        p("Se l'obbligato a concludere il contratto non adempie, l'altra parte può ottenere una sentenza che produca gli effetti "
          "del contratto non concluso; se si tratta di trasferire la proprietà, deve eseguire o offrire la propria prestazione.",
          R("cc:2932", "puo' ottenere una sentenza che produca gli effetti del contratto non concluso")),
        p("La domanda va trascritta: la trascrizione della sentenza di accoglimento prevale sulle trascrizioni e iscrizioni "
          "successive alla domanda.", R("cc:2652", "esecuzione in forma specifica dell'obbligo a contrarre")),
    ],
    procedibilita=[_MEDIAZIONE],
    termini=[p("Prescrizione decennale dalla data fissata per il definitivo.", R("cc:2946", "si estinguono per prescrizione con il decorso di dieci anni"))],
    dati=["preliminare e data fissata per il rogito", "prezzo pagato o offerto", "diffide", "dati catastali"],
)

RECESSO_CONTRATTO = Scheda(
    regola="con_recesso", materia="contratti", nome="recesso dal contratto",
    segnali=(r"recess|recedere",), alcuni=(r"contratt|preavviso|unilateral|fornitura|consulenza",),
    esclusi=(r"socio|societa|conduttor|inquilin|locazion|consumator|online|a distanza|caparra|lavor|licenzia|clausola vessatori",),
    punteggio=2,
    capito="Esercizio del recesso da un contratto.",
    rimedio="comunicazione scritta di recesso nei modi e termini del contratto",
    conclusione=[p("Se a una parte è attribuita la facoltà di recedere, la può esercitare finché il contratto non ha avuto "
                   "principio di esecuzione; nei contratti a esecuzione continuata o periodica anche dopo, senza effetto per le "
                   "prestazioni eseguite. Senza previsione di legge o di contratto il recesso unilaterale non è ammesso.",
                   R("cc:1373", "finche' il contratto non abbia avuto un principio di esecuzione"),
                   R("cc:1373", "nei contratti a esecuzione continuata o periodica"))],
    dati=["contratto e clausola di recesso", "esecuzione già iniziata", "preavviso e corrispettivo"],
)

SINISTRO = Scheda(
    regola="rc_sinistro", materia="responsabilità civile", nome="sinistro stradale",
    segnali=(r"incidente|sinistro|investit|tamponat|risarcimento diretto|scontro tra",),
    alcuni=(r"strad|auto|veicol|moto|strisce|pedon|assicura|risarc|lesion|danni|causa",),
    esclusi=(r"lavoro\b|infortunio sul lavoro|ospedal|medic",), punteggio=2,
    capito="Danni da circolazione stradale: richiesta all'assicurazione e azione giudiziale.",
    rimedio="richiesta di risarcimento all'assicurazione (diretto o del responsabile), poi negoziazione assistita e causa",
    conclusione=[
        p("Il conducente risponde dei danni da circolazione se non prova di aver fatto tutto il possibile per evitarli; nello "
          "scontro fra veicoli si presume il concorso uguale.", R("cc:2054", "se non prova di aver fatto tutto il possibile per evitare il danno")),
        p("L'azione verso l'assicurazione è proponibile solo dopo la richiesta di risarcimento e il decorso dei termini della "
          "procedura (sessanta giorni per i soli danni a cose, novanta per le lesioni).",
          R("dlgs209:145", "proponibilita'"), R("dlgs209:148", "sessanta giorni"), R("dlgs209:148", "novanta giorni")),
        p("Prima della causa per danni da circolazione serve l'invito alla negoziazione assistita.",
          R("dl132:3", "risarcimento del danno da circolazione di veicoli")),
    ],
    termini=[p("Prescrizione in due anni per i danni da circolazione (più lunga se il fatto è reato).",
               R("cc:2947", "il diritto si prescrive in due anni"))],
    dati=["data e luogo del sinistro", "veicoli e assicurazioni", "constatazione amichevole o verbale", "lesioni e certificati"],
)

CREDITI_LAVORO = Scheda(
    regola="lav_crediti", materia="lavoro", nome="crediti di lavoro e differenze retributive",
    segnali=(r"contratto collettivo|\bccnl\b|stipendi|differenze retributiv|livello inferiore|inquadrament|mi devono|"
             r"non (?:mi )?(?:ha|hanno) pagato|busta paga|buste paga|straordinar",),
    alcuni=(r"datore|lavor|dipendent|azienda|mansion|stipendi|buste paga|straordinar",),
    esclusi=(r"licenzia|minister|scuol|docent|pubblic\w* amministrazion|\binps\b|carta", r"pignor|precett"), punteggio=2,
    capito="Lavoratore subordinato privato che chiede retribuzioni o differenze non pagate.",
    rimedio="ricorso ex art. 414 c.p.c. al giudice del lavoro (o decreto ingiuntivo con le buste paga)",
    conclusione=[
        p("Il ricorso si propone al tribunale in funzione di giudice del lavoro del luogo in cui è sorto il rapporto o si "
          "trova l'azienda.", R("cpc:413", "e sorto il rapporto ovvero si trova l'azienda"), R("cpc:414", "si propone con ricorso")),
        p("Le retribuzioni si prescrivono in cinque anni.", R("cc:2948", "si prescrivono in cinque anni")),
    ],
    termini=[_FERIALE_NO],
    dati=["contratto e CCNL", "livello e mansioni", "buste paga e conteggi", "periodo"],
)

TFR = Scheda(
    regola="lav_tfr", materia="lavoro", nome="trattamento di fine rapporto",
    segnali=(r"\btfr\b|trattamento di fine rapporto",), esclusi=(r"licenzia\w*[^.]{0,30}impugn", r"pubblic\w* amministrazion|\btfs\b"),
    punteggio=2,
    capito="TFR non pagato alla cessazione del rapporto di lavoro.",
    rimedio="diffida, poi decreto ingiuntivo o ricorso al giudice del lavoro; con datore insolvente domanda al Fondo di garanzia INPS",
    conclusione=[
        p("In ogni caso di cessazione del rapporto di lavoro subordinato spetta il TFR: per ogni anno una quota pari alla "
          "retribuzione annua divisa per 13,5, rivalutata.", R("cc:2120", "divisa per 13,5")),
        p("Il diritto si prescrive in cinque anni dalla cessazione.", R("cc:2948", "le indennita' spettanti per la cessazione del rapporto di lavoro")),
    ],
    termini=[_FERIALE_NO],
    dati=["data di cessazione", "retribuzioni annue e anticipi", "eventuale procedura concorsuale del datore"],
)

RICORSO_414 = Scheda(
    regola="lav_ricorso_414", materia="lavoro", nome="ricorso nel rito del lavoro",
    segnali=(r"\b414\b|ricorso (?:di|nel rito del) lavoro|cause di lavoro|controversi\w* di lavoro|giudice del lavoro|"
             r"azienda ha sede|dove facciamo causa",),
    alcuni=(r"lavor|dipendent|azienda|datore|\b414\b",), esclusi=(r"minister|pubblic\w* amministrazion|\binps\b|appell|licenzia",), punteggio=3,
    capito="Introduzione della causa di lavoro: forma, contenuto e giudice competente.",
    rimedio="ricorso al tribunale in funzione di giudice del lavoro",
    conclusione=[
        p("Le controversie dei rapporti di lavoro subordinato privato seguono il rito del lavoro.",
          R("cpc:409", "rapporti di lavoro subordinato privato")),
        p("È competente il giudice del luogo in cui è sorto il rapporto o si trova l'azienda o la dipendenza cui è addetto il "
          "lavoratore.", R("cpc:413", "e sorto il rapporto ovvero si trova l'azienda")),
        p("Il ricorso deve contenere, fra l'altro, l'esposizione dei fatti e degli elementi di diritto e l'indicazione specifica "
          "dei mezzi di prova e dei documenti, a pena di decadenza.", R("cpc:414", "mezzi di prova")),
    ],
    termini=[_FERIALE_NO],
    dati=["luogo del rapporto e sede dell'azienda", "domande", "mezzi di prova e documenti"],
)

APPELLO_LAVORO = Scheda(
    regola="lav_appello", materia="lavoro", nome="appello nel rito del lavoro",
    segnali=(r"appell", r"\blavoro\b|lavorator|licenzia|retribu"), esclusi=(r"penal|imputat|tributar",), punteggio=4,
    tipi=frozenset({"parere", "redazione", "calcolo"}),
    capito="Appello contro la sentenza del giudice del lavoro.",
    rimedio="ricorso in appello alla corte d'appello in funzione di giudice del lavoro",
    conclusione=[
        p("L'appello contro le sentenze delle controversie di lavoro si propone con ricorso alla corte d'appello in funzione di "
          "giudice del lavoro.", R("cpc:433", "deve essere proposto con ricorso davanti alla corte di appello")),
        p("Il ricorso, motivato in modo chiaro, sintetico e specifico per capi, si deposita entro trenta giorni dalla "
          "notificazione della sentenza (quaranta se all'estero).", R("cpc:434", "entro trenta giorni dalla notificazione della sentenza")),
        p("Se la sentenza non è notificata vale il termine lungo: sei mesi dalla pubblicazione (deposito) della sentenza.",
          R("cpc:327", "dalla pubblicazione della sentenza")),
    ],
    termini=[_FERIALE_NO],
    dati=["sentenza e data di notifica o pubblicazione", "capi impugnati"],
)

DISDETTA = Scheda(
    regola="loc_disdetta", materia="locazioni", nome="disdetta e diniego di rinnovo alla scadenza",
    segnali=(r"disdett|diniego (?:del )?rinnovo|prima scadenza|finita locazione",),
    alcuni=(r"locazion|conduttor|inquilin|locator|4 ?\+ ?4|commercial|abitativ|contratto|negozio|appartamento",), esclusi=(r"moros|non paga",), punteggio=2,
    capito="Disdetta del contratto di locazione alla scadenza e diniego di rinnovo alla prima scadenza.",
    rimedio="comunicazione di disdetta (con motivo, alla prima scadenza) e, se il conduttore resta, intimazione di licenza o sfratto per finita locazione",
    conclusione=[
        p("Nelle locazioni abitative a 4+4 il locatore può negare il rinnovo alla prima scadenza solo per i motivi di legge, con "
          "preavviso di almeno sei mesi.", R("l431:3", "con preavviso di almeno sei mesi")),
        p("Nelle locazioni ad uso diverso il contratto si rinnova di sei anni in sei anni salvo disdetta da comunicare almeno "
          "dodici mesi prima della scadenza; alla prima scadenza il diniego è ammesso solo per i motivi di legge.",
          R("l392:28", "almeno 12 o 18 mesi prima della scadenza"), R("l392:29", "il diniego della rinnovazione del contratto alla prima scadenza")),
    ],
    dati=["tipo di contratto e decorrenza", "scadenza", "motivo del diniego", "data e modo della comunicazione"],
)

MOBILI_RILASCIO = Scheda(
    regola="loc_mobili_rilascio", materia="locazioni", nome="beni lasciati nell'immobile dopo il rilascio",
    segnali=(r"(?:lasciato|lascia|rimast\w*)[^.]{0,60}(?:mobili|beni|oggetti|macchinari|arredi)|mobili estranei|preavviso di rilascio",), punteggio=5,
    capito="Beni mobili rimasti nell'immobile al momento del rilascio.",
    rimedio="intimazione dell'ufficiale giudiziario all'asporto con termine; in mancanza, i beni sono trattati come abbandonati",
    conclusione=[p("Se nell'immobile si trovano beni che non vanno consegnati, l'ufficiale giudiziario intima alla parte tenuta "
                   "al rilascio, o al proprietario dei beni, di asportarli entro un termine.",
                   R("cpc:609", "di asportarli, assegnandogli il relativo termine"))],
    dati=["verbale di rilascio", "beni presenti e proprietario"],
)

CANONE_NERO = Scheda(
    regola="loc_canone_nero", materia="locazioni", nome="restituzione delle somme oltre il canone registrato",
    segnali=(r"in nero|non (?:era |e )?registrat|in contanti|canone piu basso|oltre (?:al )?canone",),
    alcuni=(r"locazion|canone|inquilin|conduttor|affitt|locator",), punteggio=2,
    capito="Conduttore che ha pagato somme oltre il canone del contratto registrato.",
    rimedio="azione di restituzione entro sei mesi dalla riconsegna dell'immobile",
    conclusione=[
        p("È nulla ogni pattuizione che fissi un canone superiore a quello del contratto scritto e registrato; il conduttore "
          "può chiedere la restituzione delle somme pagate in più entro sei mesi dalla riconsegna dell'immobile.",
          R("l431:13", "restituzione delle somme corrisposte in misura superiore al canone"),
          R("l431:13", "sei mesi dalla riconsegna")),
    ],
    procedibilita=[_MEDIAZIONE],
    dati=["contratto registrato e canone", "somme pagate in più e prove", "data di riconsegna"],
)

GARANZIA = Scheda(
    regola="cons_garanzia", materia="consumatori", nome="garanzia legale di conformità",
    segnali=(r"garanzia|difett\w* di conformita|difett|si (?:e )?rott|non funziona",),
    alcuni=(r"vendit|acquist|comprat|consumator|negozio|auto|prodotto",),
    esclusi=(r"appalt|impresa edile|falegnam|installator|banca|fideiussion|garanzia del credito|ipotec|garanzia personale"), punteggio=2,
    capito="Consumatore con un bene difettoso: rimedi verso il venditore.",
    rimedio="denuncia del difetto al venditore e richiesta di riparazione o sostituzione; poi riduzione del prezzo o risoluzione",
    conclusione=[
        p("Il venditore risponde verso il consumatore dei difetti di conformità esistenti alla consegna e manifestati entro "
          "due anni.", R("dlgs206:133", "si manifesta entro due anni")),
        p("Il consumatore ha diritto al ripristino della conformità (riparazione o sostituzione), o alla riduzione del prezzo o "
          "alla risoluzione alle condizioni di legge.", R("dlgs206:135bis", "riparazione e sostituzione")),
    ],
    dati=["data di consegna", "difetto e quando si è manifestato", "richieste già fatte al venditore"],
)

CLAUSOLE_VESSATORIE = Scheda(
    regola="cons_clausole_vessatorie", materia="consumatori", nome="clausole vessatorie",
    segnali=(r"vessatori|clausol\w*[^.]{0,30}abusiv|vieta[^.]{0,40}abusiv|abusiva\?|penale enorme|clausol\w*[^.]{0,80}(?:valid|efficac|nulla)|non (?:firmate|approvate) specificamente",),
    alcuni=(r"consumator|palestra|condizioni generali|penale|foro|abbonament|vessatori|abusiv|specificamente|venditor|cliente",),
    esclusi=(r"edilizi|demoli|occupa|recinzion|condomin|costruzion",), punteggio=6,
    capito="Clausole che creano a carico del consumatore un significativo squilibrio dei diritti e degli obblighi.",
    rimedio="eccezione o domanda di nullità della clausola (nullità di protezione), con il contratto che resta valido",
    conclusione=[
        p("Nel contratto fra consumatore e professionista sono vessatorie le clausole che, malgrado la buona fede, determinano "
          "un significativo squilibrio dei diritti e degli obblighi; alcune si presumono vessatorie.",
          R("dlgs206:33", "significativo squilibrio dei diritti e degli obblighi")),
        p("Le clausole vessatorie sono nulle mentre il contratto rimane valido per il resto.",
          R("dlgs206:36", "sono nulle mentre il contratto rimane valido per il resto")),
        p("Fra non consumatori, le condizioni generali che limitano la responsabilità, attribuiscono recesso o stabiliscono "
          "decadenze non hanno effetto se non approvate specificamente per iscritto.",
          R("cc:1341", "se non sono specificamente approvate per iscritto")),
    ],
    dati=["contratto e clausola", "qualità di consumatore", "trattativa individuale o modulo"],
)

FORO_CONSUMATORE = Scheda(
    regola="cons_foro", materia="consumatori", nome="foro del consumatore",
    segnali=(r"consumator", r"foro|competen|citat\w* fuori|comune di residenza|ci cita|cita a|dove (?:fare|facciamo) causa|che giudice|quale giudice|fare causa"),
    punteggio=2,
    capito="Giudice territorialmente competente nelle cause con il consumatore.",
    rimedio="eccezione di incompetenza per territorio se la causa è proposta fuori dal foro del consumatore",
    conclusione=[p("Si presume vessatoria la clausola che fissa un foro diverso dalla residenza o dal domicilio elettivo del "
                   "consumatore; per i contratti a distanza e fuori dei locali il foro è inderogabilmente quello del consumatore.",
                   R("dlgs206:33", "residenza o domicilio elettivo del consumatore"),
                   R("dlgs206:66bis", "residenza o di domicilio del consumatore"))],
    dati=["residenza del consumatore", "clausola sul foro", "tipo di contratto"],
)

SOSPENSIVA = Scheda(
    regola="amm_sospensiva", materia="amministrativo", nome="misure cautelari nel processo amministrativo",
    segnali=(r"sospensiv|sospender\w* (?:subito )?(?:l ordinanza|il provvedimento|l atto)|cautelar\w* (?:monocratic|collegial)|"
             r"decreto cautelare|istanza cautelare|urgentissim",),
    alcuni=(r"\btar\b|amministrativ|ordinanza|comune|provvedimento|demolizion|abbattiment|monocratic|atto impugnato",),
    esclusi=(r"tributar|cartella|penal|reato",), punteggio=6,
    capito="Sospensione o altra misura cautelare contro un provvedimento impugnato al TAR.",
    rimedio="domanda cautelare collegiale nel ricorso o con atto separato; in estrema urgenza istanza di decreto monocratico",
    conclusione=[
        p("Chi allega un pregiudizio grave e irreparabile nel tempo necessario alla decisione può chiedere misure cautelari; il "
          "collegio decide con ordinanza in camera di consiglio.",
          R("cpa:55", "pregiudizio grave e irreparabile"), R("cpa:55", "il collegio si pronuncia con ordinanza")),
        p("In caso di estrema gravità e urgenza che non consente di attendere la camera di consiglio si chiedono al presidente "
          "misure cautelari provvisorie con decreto.", R("cpa:56", "in caso di estrema gravita' ed urgenza")),
    ],
    dati=["provvedimento impugnato", "data dell'esecuzione temuta", "pregiudizio grave e irreparabile"],
)

QUERELA = Scheda(
    regola="pen_querela", materia="penale", nome="querela",
    segnali=(r"querel",), esclusi=(r"remission|ritirar|rimetter",), punteggio=2,
    capito="Persona offesa che vuole proporre querela.",
    rimedio="querela scritta o orale all'autorità giudiziaria o alla polizia giudiziaria entro tre mesi dalla notizia del fatto",
    conclusione=[
        p("La persona offesa da un reato procedibile a querela ha diritto di querela.", R("cp:120", "ha diritto di querela")),
        p("La querela si propone con dichiarazione, personalmente o con procuratore speciale, che manifesta la volontà che si "
          "proceda; il termine è di tre mesi dalla notizia del fatto.",
          R("cpp:336", "si manifesta la volonta' che si proceda"), R("cp:124", "decorsi tre mesi dal giorno della notizia del fatto")),
    ],
    dati=["fatto e data della notizia", "reato e procedibilità", "querelato"],
)

APPELLO_PENALE = Scheda(
    regola="pen_appello", materia="penale", nome="appello penale",
    segnali=(r"appell", r"penal|condann|imputat|reato"), esclusi=(r"lavor|tributar|\btar\b|cassazion",), punteggio=2,
    capito="Appello contro una sentenza penale.",
    rimedio="atto di appello con motivi specifici",
    conclusione=[
        p("L'imputato può appellare le sentenze di condanna.", R("cpp:593", "l'imputato puo' appellare contro le sentenze di condanna")),
        p("Il termine è di quindici giorni (motivazione contestuale o camera di consiglio), trenta o quarantacinque se la "
          "motivazione è depositata dopo; aumentato di quindici giorni per il difensore dell'imputato giudicato in assenza.",
          R("cpp:585", "di quindici giorni"), R("cpp:585", "di trenta giorni"), R("cpp:585", "di quarantacinque giorni")),
    ],
    dati=["sentenza e data di deposito o avviso", "tipo di motivazione", "processo in assenza"],
)

CASSAZIONE_PENALE = Scheda(
    regola="pen_cassazione", materia="penale", nome="ricorso per cassazione penale",
    segnali=(r"cassazion|saltum", r"penal|condann|imputat|reato|saltum|proscioglim"), esclusi=(r"lavor|tributar|\btar\b",), punteggio=2,
    capito="Ricorso per cassazione contro una sentenza penale.",
    rimedio="ricorso per cassazione sottoscritto da difensore iscritto nell'albo speciale",
    conclusione=[
        p("Il ricorso per cassazione si propone per i motivi tassativi di legge, fra cui la violazione della legge penale o "
          "processuale e i vizi di motivazione.", R("cpp:606", "inosservanza o erronea applicazione della legge penale")),
        p("L'imputato può ricorrere contro la sentenza di condanna o di proscioglimento; la parte che può appellare può "
          "ricorrere direttamente in cassazione (ricorso per saltum).",
          R("cpp:607", "l'imputato puo' ricorrere per cassazione contro la sentenza di condanna"),
          R("cpp:569", "puo' proporre direttamente ricorso per cassazione")),
        p("Il ricorso è sottoscritto, a pena di inammissibilità, da difensori iscritti nell'albo speciale della Corte di cassazione.",
          R("cpp:613", "da difensori iscritti nell'albo speciale della corte di cassazione")),
        p("Il termine segue l'art. 585 c.p.p.: quindici, trenta o quarantacinque giorni secondo il deposito della motivazione.",
          R("cpp:585", "di quindici giorni")),
    ],
    dati=["sentenza e data di deposito o avviso", "motivi di ricorso", "difensore cassazionista"],
)

PREFETTO = Scheda(
    regola="cds_prefetto", materia="violazioni amministrative", nome="ricorso al Prefetto contro il verbale",
    segnali=(r"prefett",), alcuni=(r"verbal|multa|sanzion|contravvenzion|ricors",), esclusi=(r"espulsion|ordinanza.ingiunzione",),
    punteggio=2,
    capito="Ricorso amministrativo al Prefetto contro un verbale del codice della strada.",
    rimedio="ricorso al Prefetto entro sessanta giorni (in alternativa al giudice di pace entro trenta)",
    conclusione=[
        p("Entro sessanta giorni dalla contestazione o notificazione, se non si è pagato in misura ridotta, si può ricorrere "
          "al Prefetto del luogo della violazione tramite l'ufficio accertatore.", R("dlgs285:203", "nel termine di giorni sessanta")),
        p("Se ritiene fondato l'accertamento, il Prefetto ingiunge il pagamento di una somma non inferiore al doppio del minimo "
          "edittale; altrimenti archivia.", R("dlgs285:204", "nel limite non inferiore al doppio del minimo edittale")),
    ],
    scadenze=[Scadenza("ricorso al Prefetto entro", 60, "giorni", r"(?:verbale|multa)[^0-9]{0,40}(?:notificat\w*|contestat\w*)(?: il)?",
                       (R("dlgs285:203", "nel termine di giorni sessanta"),), modello="CDS_RICORSO_PREFETTO_60GG")],
    dati=["verbale e data di notifica", "pagamento in misura ridotta già fatto o no"],
)

PERMESSO_ESPULSIONE = Scheda(
    regola="imm_permesso_espulsione", materia="immigrazione", nome="diniego del permesso di soggiorno ed espulsione",
    segnali=(r"permesso di soggiorno|espulsion|questura",), esclusi=(r"commissione territoriale|asilo|protezione internazionale",),
    punteggio=2,
    capito="Straniero cui è negato o revocato il permesso di soggiorno o notificata l'espulsione.",
    rimedio="ricorso al TAR contro il diniego del permesso (tribunale ordinario per i motivi familiari); ricorso al giudice di pace contro l'espulsione",
    conclusione=[
        p("Contro i provvedimenti su rilascio e rinnovo del permesso di soggiorno è ammesso ricorso al tribunale amministrativo "
          "regionale.", R("dlgs286:6", "e' ammesso ricorso al tribunale amministrativo regionale competente")),
        p("Contro il decreto di espulsione del prefetto si ricorre al giudice di pace del luogo dell'autorità che l'ha disposta, "
          "entro venti giorni dalla notificazione (quaranta se residente all'estero).",
          R("dlgs286:13", "avverso il decreto di espulsione puo' essere presentato ricorso all'autorita' giudiziaria ordinaria"),
          R("dlgs150:18", "e' competente il giudice di pace"), R("dlgs150:18", "entro venti giorni dalla notificazione")),
    ],
    avvertenze=["Per il diniego del permesso per motivi familiari è competente il giudice ordinario (art. 30, comma 6, TUI)."],
    dati=["provvedimento e data di notifica", "tipo di permesso", "legami familiari in Italia"],
)

MEDIAZIONE = Scheda(
    regola="str_mediazione", materia="stragiudiziale", nome="mediazione: durata, effetti e mancata partecipazione",
    segnali=(r"mediazion",), alcuni=(r"dura|prescrizion|non si presenta|non partecip|cosa rischia|primo incontro|domanda di mediazione",),
    esclusi=(r"tributar|famil|separazion",), punteggio=2,
    capito="Svolgimento della mediazione civile e commerciale.",
    rimedio="domanda di mediazione all'organismo competente",
    conclusione=[
        p("La mediazione dura sei mesi, prorogabili; il termine non è soggetto a sospensione feriale.",
          R("dlgs28:6", "ha una durata di sei mesi"), R("dlgs28:6", "non e' soggetto a sospensione feriale")),
        p("Dalla comunicazione alla controparte la domanda di mediazione produce sulla prescrizione gli effetti della domanda "
          "giudiziale e impedisce una volta la decadenza.", R("dlgs28:8", "produce sulla prescrizione gli effetti della domanda giudiziale")),
        p("Dalla mancata partecipazione senza giustificato motivo il giudice desume argomenti di prova e, se la mediazione è "
          "obbligatoria, condanna la parte al pagamento di una somma pari al doppio del contributo unificato.",
          R("dlgs28:12bis", "il giudice puo' desumere argomenti di prova"),
          R("dlgs28:12bis", "doppio del contributo unificato")),
    ],
    dati=["materia", "organismo competente", "data del deposito e del primo incontro"],
)

NEGOZIAZIONE = Scheda(
    regola="str_negoziazione", materia="stragiudiziale", nome="negoziazione assistita: invito, risposta e materie",
    segnali=(r"negoziazione",), alcuni=(r"invit|non risponde|rifiut|trenta giorni|30 giorni|lavoro|convenzione|aspett",),
    esclusi=(r"separar|divorzi|coniug|figli|sinistro|incidente",), punteggio=2,
    capito="Invito alla negoziazione assistita e conseguenze della mancata risposta.",
    rimedio="invito a stipulare la convenzione di negoziazione assistita firmato dall'avvocato",
    conclusione=[
        p("L'invito indica l'oggetto e avverte che la mancata risposta entro trenta giorni o il rifiuto possono essere valutati "
          "dal giudice ai fini delle spese e della provvisoria esecuzione.", R("dl132:4", "entro trenta giorni dalla ricezione")),
        p("Nelle controversie di lavoro la negoziazione assistita è possibile ma non è condizione di procedibilità.",
          R("dl132:2ter", "senza che cio' costituisca condizione di procedibilita'")),
    ],
    dati=["oggetto della controversia", "data dell'invito e della ricezione", "materia"],
)

SCHEDE = (SEQUESTRO, RICORSO_CREDITO, OPPOSIZIONE_DI, SEPARAZIONE, MODIFICA_CONDIZIONI, MANTENIMENTO, ORDINI_PROTEZIONE,
          NEGOZIAZIONE_FAMILIARE, DISCONOSCIMENTO, BENEFICIO_INVENTARIO, ESECUZIONE_2932, RECESSO_CONTRATTO, SINISTRO,
          CREDITI_LAVORO, TFR, RICORSO_414, APPELLO_LAVORO, DISDETTA, MOBILI_RILASCIO, CANONE_NERO, GARANZIA,
          CLAUSOLE_VESSATORIE, FORO_CONSUMATORE, SOSPENSIVA, QUERELA, APPELLO_PENALE, CASSAZIONE_PENALE, PREFETTO, PERMESSO_ESPULSIONE,
          MEDIAZIONE, NEGOZIAZIONE)
