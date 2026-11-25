"""Come l'avvocato chiede ciascuno dei calcolatori di Strumenti legali, con le sue parole.

Per ogni calcolatore: espressioni (sul testo senza accenti e in minuscolo) che descrivono la situazione per cui serve,
anche senza «calcola» né il nome dello strumento («sentenza notificata il …, entro quando appello?», «danno da
incidente con 8 punti di invalidità», «quanto paga di imposta di successione il figlio»). Il peso distingue l'uso
specifico (3) dal generico (1). ``CAMPI_DA_USO`` dà il valore di un campo di scelta quando l'uso lo rende certo
(es. impugnazione di una delibera condominiale → modello «CIV_IMPUGNAZIONE_DELIBERA_1137»).

Il test ``lex/tests/test_strumenti_usi.py`` controlla che ogni calcolatore della mappa abbia almeno un uso e che ogni
valore di ``CAMPI_DA_USO`` sia una scelta ammessa dal calcolatore.
"""
from __future__ import annotations

# (identificativo del calcolatore, peso, espressione regolare)
USI: tuple[tuple[str, int, str], ...] = (
    # ---------------------------------------------------------------- termini e notifiche
    ("impugnazioni", 3, r"(?:entro quando|quando scade|termine|scadenza|fino a quando|in tempo)\b.{0,60}\b(?:appell\w*|ricorso per cassazione|ricorrere in cassazione|impugn\w*)"),
    ("impugnazioni", 3, r"\b(?:appell\w*|impugn\w*|ricorso per cassazione)\b.{0,80}\b(?:sentenza|pronuncia)\b.{0,60}\b(?:notificat\w*|pubblicat\w*|depositat\w*)"),
    ("impugnazioni", 2, r"\b(?:sentenza|pronuncia)\b.{0,60}\b(?:notificat\w*|pubblicat\w*|depositat\w*)\b.{0,80}\b(?:appell\w*|cassazione|impugn\w*)"),
    ("impugnazioni", 2, r"termine (?:breve|lungo) (?:per )?(?:l'|d')?(?:appell|impugn)"),
    ("termini_processuali", 4, r"(?:impugn\w*|opporsi|opposizione).{0,30}delibera.{0,100}(?:condomin\w*|assemble\w*|1137)|(?:condomin\w*|assemble\w*|1137).{0,100}(?:impugn\w*|opporsi|opposizione).{0,30}delibera"),
    ("termini_processuali", 4, r"(?:impugn\w*|opporsi|opposizione).{0,30}delibera (?:condominiale|dell'assemblea|assembleare)|delibera (?:condominiale|assembleare).{0,60}(?:impugn|entro quando|termine)"),
    ("termini_processuali", 4, r"(?:opposizione|oppors\w*|opporre).{0,30}decreto ingiuntivo|decreto ingiuntivo.{0,60}(?:opposizione|oppors|entro quando|termine)"),
    ("termini_processuali", 3, r"memori\w* (?:integrativ\w*|171-?ter|ex art\. 171-?ter)|171-?ter"),
    ("termini_processuali", 3, r"\bprecetto\b.{0,60}(?:efficacia|scade|perde|entro|giorni|90|novanta|fino a quando|pignorare)|(?:efficacia|scadenza) del precetto"),
    ("termini_processuali", 2, r"(?:costitu\w+|comparsa di risposta).{0,40}(?:entro quando|termine|giorni prima)|(?:entro quando|termine).{0,40}costitu"),
    ("termini_processuali", 2, r"reclamo (?:cautelare|contro (?:l'|il )?(?:ordinanza|provvedimento) cautelare)|669-?terdecies"),
    ("termini_processuali", 2, r"riassun\w+.{0,40}(?:termine|entro|giorni|mesi)|(?:termine|entro).{0,40}riassun"),
    ("termini_processuali", 2, r"(?:ricorso|impugn\w*).{0,30}\btar\b.{0,60}(?:entro|termine|giorni|scade)|(?:entro|termine).{0,40}ricorso al tar"),
    ("termini_processuali", 2, r"ricorso (?:alla|in) (?:corte di giustizia tributaria|commissione tributaria)|(?:avviso di accertamento|cartella).{0,60}(?:entro quando|termine per ricorrere|ricorr)"),
    ("termini_processuali", 2, r"(?:multa|verbale|contravvenzione).{0,60}(?:ricorso al prefetto|giudice di pace|pagamento ridotto|entro quando)"),
    ("termini_processuali", 2, r"(?:entro quando|quando scade|termine per|scadenza del termine).{0,60}(?:notifica|depositare|deposito|costituirsi|memoria|note|comparsa|costituzione|replica|conclusionale)"),
    ("termini_processuali", 3, r"note scritte|trattazione scritta|127-?ter|note di trattazione|(?:udienza|rinvio).{0,60}(?:quando scade|entro quando|termine per)"),
    ("termini_processuali", 2, r"sospensione feriale"),
    ("termini_processuali", 4, r"opposizione agli atti esecutivi|\b617 c\.?p\.?c|opposizione all'esecuzione.{0,60}(?:entro|termine|giorni)"),
    ("termini_processuali", 2, r"calcol\w* (?:il |un |i )?termin\w*|termin\w*.{0,80}(?:a partire dal|decorr\w* dal|dal giorno)"),
    ("termini_penali", 4, r"(?:415-?bis|avviso (?:di )?conclusione (?:delle )?indagini).{0,80}(?:memori|entro|termine|giorni)|(?:memori|entro|termine).{0,60}415-?bis"),
    ("termini_penali", 4, r"(?:opposizione|oppors\w*).{0,20}decreto penale|decreto penale di condanna"),
    ("termini_penali", 3, r"\briesame\b|appello cautelare|(?:impugn\w*|appell\w*).{0,40}(?:sentenza|condanna) penal"),
    ("termini_penali", 4, r"oppo\w*.{0,40}archiviazion\w*|archiviazion\w*.{0,80}(?:oppo\w*|410)|\b410 c\.?p\.?p"),
    ("termini_penali", 2, r"(?:entro quando|termine).{0,60}(?:impugnare|appellare|appello).{0,60}(?:imputat|reato|penal|condann)"),
    ("indagini_preliminari", 3, r"durata (?:massima )?delle indagini|indagini preliminari.{0,60}(?:scad|durata|proroga|termine)|(?:scad|termine).{0,40}indagini"),
    # La detenzione raccontata a voce («in carcere da agosto», «detenuto da tre mesi») e la domanda di quanto può durare.
    ("custodia_durata", 4, r"(?:in carcere|detenut\w*|ai domiciliari|agli arresti|in custodia|in cella|dentro)\b.{0,100}"
                           r"(?:quanto (?:\w+ ){0,3}(?:restare|rimanere|durare|stare|tenerl\w*)|fino a quando|durata massima|per quanto tempo|al massimo)|"
                           r"(?:quanto (?:\w+ ){0,3}(?:restare|rimanere|stare)|fino a quando (?:\w+ ){0,2}(?:restare|rimanere|stare)).{0,40}(?:in carcere|detenut\w*|ai domiciliari|in custodia|dentro)"),
    # La persona appena arrestata o fermata: la misura cautelare, la convalida.
    ("custodia_cautelare", 4, r"(?:arrestat\w*|fermat[oa]\b|fermati\b|in stato di fermo|portat\w* in carcere).{0,100}(?:cosa succede|che succede|cosa accade|e adesso|"
                              r"convalida|cosa (?:devo|dobbiamo|possiamo) fare|interrogatorio di garanzia)"),
    ("conta_giorni", 4, r"quant[oi] (?:tempo |giorni )?(?:manca|mancano)\b|quanti giorni (?:mancano|ci sono|passano|intercorrono)|"
                        r"(?:giorni|tempo) (?:tra|fra) (?:il|due date|oggi)|quanti giorni da(?:l| oggi)"),
    ("onorari_forensi", 4, r"\bcompens\w* (?:dell'avvocato|professional\w*|forens\w*|secondo i parametri|da parametri|ai parametri)|"
                           r"parametri forensi|\bd\.?\s?m\.? 55/2014|parametri (?:del )?d\.?\s?m\.? 55"),
    ("custodia_cautelare", 3, r"custodia cautelare|arresti domiciliari|misura cautelare personale"),
    ("custodia_durata", 4, r"(?:in carcere|detenut\w*|agli arresti domiciliari|in custodia(?: cautelare)?) dal \d|arrestat\w* il \d|"
                           r"durata (?:massima )?della detenzione|quanto (?:puo|deve) (?:restare|stare|rimanere) in (?:carcere|custodia|detenzione)|"
                           r"(?:fino a quando|per quanto tempo) (?:puo )?(?:restare|stare|rimanere) (?:in carcere|detenut\w*|ai domiciliari)|"
                           r"(?:durare|dura|durata)\b.{0,30}(?:al massimo|massim\w*).{0,60}custodia|custodia.{0,60}(?:durare|durata) (?:al )?massim\w*|"
                           r"durata (?:massima )?della custodia|termini (?:di fase )?della custodia|scarcerazione per decorrenza"),
    ("improcedibilita_penale", 3, r"improcedibil\w*|344-?bis"),
    ("prescrizione_penale", 3, r"prescrizion\w* (?:del reato|penale)|(?:reato|delitto|contravvenzione|truffa|furto|lesioni|diffamazione|appropriazione).{0,80}prescri|prescri\w*.{0,40}(?:reato|delitto)"),
    ("prescrizione", 3, r"(?:credito|diritto|risarcimento|fattura|debito|canoni|stipendi|pagamento|danno).{0,80}(?:si prescrive|prescritt\w*|prescrizione)|(?:si prescrive|prescritt\w*|prescrizione).{0,60}(?:credito|diritto|risarcimento|fattura|debito)"),
    ("prescrizione", 3, r"(?:danno|credito|risarciment\w*|fattura|debito|diritto).{0,80}(?:e |sia |sono )?(?:prescritt\w*|in prescrizione|caduto in prescrizione)"),
    ("prescrizione", 3, r"calcol\w* (?:la |della )?prescrizione(?! (?:del reato|penale))"),
    # «si può ancora chiedere?»: un credito nel tempo è una domanda di prescrizione, non una scadenza dello studio.
    ("prescrizione", 4, r"(?:credit\w*|debit\w*|fattur\w*|risarciment\w*|diritt\w*|somm[ae]\b|import\w*|canon\w*|stipend\w*|danni\b).{0,100}"
                        r"(?:si (?:puo|possono) ancora (?:chiedere|pretendere|esigere|recuperare|agire|richiedere)|e ancora esigibil\w*|"
                        r"(?:posso|possiamo|puo|possono) ancora (?:chiedere|recuperare|agire|pretendere|esigere|richiedere|incassare))|"
                        r"(?:si puo|posso|possiamo|puo) ancora (?:chiedere|pretendere|esigere|recuperare|agire|richiedere).{0,100}"
                        r"(?:credit\w*|debit\w*|fattur\w*|risarciment\w*|somm[ae]\b|import\w*)"),
    ("prescrizione", 4, r"(?:risarciment\w*|credit\w*|\bdann[oi]\b|sinistro|incidente|tamponamento|fattur\w*|debit\w*|canon\w*).{0,100}"
                        r"(?:siamo|sono|e|sei|siete|si e) ancora in tempo|(?:siamo|sono) ancora in tempo.{0,80}(?:risarciment\w*|credit\w*|\bdann[oi]\b|fattur\w*)"),
    ("prescrizione", 1, r"\bprescrizione\b|\bprescritt\w*|si prescrive"),
    ("perfezionamento_notifica", 3, r"(?:notifica|notificazione)\b.{0,60}(?:si (?:e )?perfezion\w*|perfezionat\w*|perfezionamento)|perfezionamento della notifica|perfezion\w*.{0,30}notific"),
    ("perfezionamento_notifica", 2, r"(?:compiuta giacenza|art\.? ?140|art\.? ?143|irreperibil\w*).{0,60}notific|notific.{0,60}(?:compiuta giacenza|140|143)"),
    ("conta_giorni", 3, r"quanti giorni (?:ci sono|passano|intercorrono|mancano)|giorni (?:tra|fra) (?:il|due date)|differenza (?:in giorni )?tra (?:due )?date"),
    # ---------------------------------------------------------------- interessi, rivalutazione, crediti
    ("interessi", 3, r"interess\w* (?:legal\w*|moratori\w*|di mora|commerciali|convenzional\w*)|saggio (?:legale|degli interessi)|1284|231/2002"),
    ("interessi", 2, r"\binteress\w*\b.{0,60}(?:su|sul|sulla|per)\b.{0,30}\d"),
    ("interessi", 3, r"\binteress\w*\b.{0,80}\d[\d.,]*\s*(?:euro|€)"),
    ("interessi_acconti", 4, r"interess\w*.{0,120}(?:acconti|pagamenti parziali|versamenti parziali)|(?:acconti|pagamenti parziali).{0,60}interess"),
    ("rivalutazione_istat", 4, r"\blire\b.{0,60}(?:rivalut\w*|oggi|euro|attualizz)|(?:rivalut\w*|attualizz\w*).{0,60}\blire\b"),
    ("rivalutazione_istat", 3, r"rivalut\w*.{0,40}(?:istat|monetaria|foi)|(?:istat|indice foi).{0,40}rivalut|adeguamento istat (?:di|della) (?:somma|importo|credito)"),
    ("rivalutazione_media", 3, r"rivalut\w*.{0,30}media annua|media annua.{0,30}rivalut"),
    ("maggior_danno", 3, r"credit\w* di valore|maggior danno|rivalutazione e interessi (?:compensativi|sul danno)|interessi compensativi"),
    ("crediti_lavoro", 3, r"credit\w* di lavoro|differenze retributive.{0,40}(?:rivalut|interess)|(?:stipendi|retribuzioni) non pagat\w*.{0,60}(?:rivalut|interess)|429 (?:c\.?p\.?c|comma 3)"),
    ("usura", 3, r"usur\w*|tasso soglia|soglia (?:antiusura|d'usura|di usura)"),
    ("taeg", 3, r"\btaeg\b|tasso annuo effettivo globale|costo (?:totale )?del (?:credito|finanziamento)"),
    ("piano_ammortamento", 3, r"piano di ammortamento|rata (?:del mutuo|mensile del (?:mutuo|finanziamento))|ammortamento (?:francese|alla francese)"),
    ("surroga", 3, r"\bsurroga\b|portabilita del mutuo|surrogazione del mutuo"),
    ("rendimento_bot", 3, r"rendimento (?:dei |di un |del )?bot|\bbot\b.{0,30}rendiment"),
    ("pronti_contro_termine", 3, r"pronti contro termine"),
    ("percentuali", 2, r"(?:quanto e|calcola) il \d+ ?(?:%|per ?cento) di|percentuale di \d|che percentuale"),
    ("scorporo_iva", 3, r"scorpor\w*.{0,20}iva|\biva\b.{0,30}(?:inclusa|compresa|esclusa|da aggiungere)|(?:lordo|netto) (?:di|dell') ?iva"),
    ("tabella_istat", 2, r"tabella (?:degli )?indici istat|indice istat (?:di|del) (?:mese|anno)|indici foi"),
    ("tabella_tassi", 4, r"(?:qual e|quanto era|quanto vale) il (?:tasso|saggio) (?:legale|di interesse legale)|tass\w* (?:legal\w*|bce) (?:del|nel|degli|dal) \d{4}|tabella (?:dei )?tassi|saggio degli interessi legali (?:del|nel|per il)"),
    ("tabella_tassi", 2, r"tabella (?:dei )?tassi|tasso legale (?:del|nel|dell'anno|vigente)|tassi (?:legali|bce) (?:degli anni|storici)"),
    # ---------------------------------------------------------------- giustizia, compensi, spese
    ("contributo_unificato", 4, r"contributo unificato|iscri\w* (?:a|al) ruolo|iscrizione (?:a|al) ruolo|"
                                r"(?:marca da )?bollo.{0,30}contribut\w*|contribut\w*.{0,30}(?:marca da )?bollo|\bbollo e contributo\b"),
    # Il contributo del processo tributario (art. 13, c. 6-quater d.P.R. 115/2002), detto anche «contributo tributario».
    ("contributo_unificato", 4, r"contributo (?:unificato )?tributari\w*|contributo (?:per|del) (?:il )?(?:ricorso|processo|giudizio) tributari\w*|"
                                r"(?:ricorso|processo|giudizio|causa) tributari\w*.{0,80}\bcontribut\w*|\bcontribut\w*.{0,60}(?:impugnare|ricorrere contro) (?:una |la |l'|un )?"
                                r"(?:cartell\w*|avviso|accertament\w*|iscrizione ipotecaria|fermo)"),
    ("contributo_unificato", 3, r"contributo unificato|\bcu\b.{0,20}(?:causa|ricorso|decreto|appello)|marca da bollo (?:per l'iscrizione|da 27)|quanto costa iscrivere a ruolo|spese di iscrizione a ruolo"),
    ("onorari_forensi", 4, r"nota (?:spese|compensi|onorari).{0,40}(?:penal\w*|difesa|processo|procedimento|giudizio|causa)|"
                           r"(?:onorari\w*|compens\w*|parcella|parametri)\b.{0,60}(?:penal\w*|mediazione|negoziazione|stragiudizial\w*|tar|tributari\w*|esecuzion\w*)|"
                           r"(?:quanto|cosa) (?:posso|devo) (?:chiedere|mettere|fatturare)\b.{0,40}(?:parcella|compens|cliente|causa|giudizio)|in parcella per"),
    ("onorari_forensi", 3, r"(?:compens\w*|parcella|onorari\w*|parametri) (?:dell'avvocato|forens\w*|professional\w*|del legale|del difensore)|parametri forensi|d\.?m\.? ?55(?:/2014)?|tariffa forense|quanto (?:posso chiedere|chiedo|mi spetta) (?:di compenso|come avvocato|per la causa)"),
    ("compenso_a_tempo", 3, r"compenso a (?:tempo|ore)|tariffa oraria|(?:ore|ora) di (?:lavoro|attivita).{0,40}compens|a ore"),
    ("patrocinio_spese_stato", 3, r"patrocinio a spese dello stato|gratuito patrocinio|ammissione al patrocinio|liquidazione (?:del difensore )?(?:a carico dello stato|in patrocinio)"),
    ("lite_temeraria", 3, r"lite temeraria|responsabilita aggravata|art\.? ?96 c\.?p\.?c|abuso del processo"),
    ("ctu", 4, r"compens\w* (?:del|al|per il) (?:ctu|consulente tecnico|perito)|liquidazione (?:del|al) (?:ctu|consulente|perito)|\bvacazion\w*"),
    ("ctu", 3, r"\bctu\b|consulen\w* tecnic\w* d'ufficio|vacazion\w*|compens\w* (?:del|al) (?:consulente|perito|ausiliario)|ausiliari del giudice"),
    ("indennita_mediazione", 3, r"indennita di mediazione|spese (?:della|di) mediazione|costo della mediazione|quanto costa (?:la )?mediazione|organismo di mediazione.{0,40}(?:costo|spese|quanto)"),
    ("procedibilita_adr", 4, r"(?:devo|serve|occorre|bisogna|obbligatori\w*).{0,40}(?:mediazione|negoziazione assistita)(?! .{0,10}(?:costo|indennita))|(?:mediazione|negoziazione).{0,40}(?:prima di|condizione di procedibilita|obbligatori)"),
    ("procedibilita_adr", 3, r"(?:mediazione|negoziazione).{0,40}(?:obbligatori\w*|condizione di procedibilita|necessari\w*|serve|devo fare)|condizione di procedibilita|(?:devo|serve|e obbligatori\w*).{0,40}(?:mediazione|negoziazione)"),
    ("competenza_valore", 3, r"giudice di pace.{0,60}(?:valore|fino a|euro|\d)|(?:\d|euro).{0,80}(?:giudice di pace|tribunale)|(?:competent\w*|compete).{0,60}(?:giudice di pace|tribunale).{0,40}(?:valore|euro|\d)|competenza per valore|(?:va|vado|devo andare) (?:dal|davanti al) giudice di pace o (?:in |al )?tribunale"),
    ("valore_causa", 3, r"valore della (?:causa|controversia|lite)|(?:come si|come) determin\w* il valore|dichiarazione di valore"),
    ("uffici_competenti", 4, r"(?:qual e il|quale|che) (?:tribunale|giudice di pace|procura|unep|corte d'appello) (?:e )?competente (?:per|di) (?:il comune di )?[a-z']+|(?:comune|citta) di [a-z']+.{0,40}(?:tribunale|giudice di pace|procura|unep) competent"),
    ("uffici_competenti", 3, r"uffic\w* (?:giudiziari\w* )?(?:sono |e )?competent\w*.{0,30}(?:comune|per|di)|(?:tribunale|giudice di pace|procura|unep|corte d'appello) (?:competente )?(?:per|di) (?:il comune di )?[a-z']+.{0,20}\?|(?:quale|che) (?:tribunale|giudice di pace|procura|unep).{0,30}(?:competent|e competente)|competenza territoriale (?:per|di) [a-z']+"),
    ("nota_credito", 4, r"precisazione del credito|precisare il credito|nota (?:di )?precisazione"),
    ("nota_credito", 3, r"nota di precisazione del credito|precisazione del credito|nota spese.{0,30}(?:esecuzione|precetto|credito)"),
    ("pignoramento", 3, r"pignor\w*.{0,60}(?:stipendio|pensione|busta paga|quinto|retribuzione)|(?:stipendio|pensione|busta paga).{0,60}pignor|quota pignorabile|quinto (?:dello stipendio|della pensione)"),
    ("imposta_registro", 3, r"imposta di registro|registrazione (?:della|di una|del) (?:sentenza|decreto ingiuntivo|lodo|verbale)|tassa di registro"),
    # ---------------------------------------------------------------- danni
    ("danno_biologico", 3, r"danno biologico|punt\w* di invalidita|invalidita permanente|micropermanent\w*|(?:incidente|sinistro|caduta|infortunio).{0,80}(?:invalidita|punti|%)|tabelle (?:di milano|milanesi|ministeriali|unica nazionale)"),
    ("danno_parentale", 3, r"(?:perdita|morte|decesso) (?:del|della|di un|di una|dei) (?:padre|madre|figli\w*|coniuge|marito|moglie|fratell\w*|sorell\w*|nonn\w*|congiunt\w*|parent\w*)|danno (?:da perdita )?parentale|perdita del rapporto parentale"),
    ("danno_premorienza", 3, r"premorienz\w*|(?:morto|deceduto|morta|deceduta) (?:per )?(?:altra|altre) cause|deceduto prima della liquidazione"),
    ("danno_terminale", 3, r"danno (?:terminale|catastrofale|tanatologico)|(?:sopravvissut\w*|e morto dopo|deceduto dopo) \d+ giorni|lucida agonia"),
    ("consenso_informato", 3, r"consenso informato|mancata informazione (?:del paziente|medica)|lesione dell'autodeterminazione"),
    ("diffamazione", 4, r"diffamazion\w*.{0,80}(?:quanto|risarc\w*|danno|liquid\w*|importo)|(?:risarc\w*|danno|quanto).{0,60}diffamazion"),
    ("diffamazione", 3, r"diffamazion\w*.{0,60}(?:risarc|danno|quanto|liquid)|danno da diffamazion\w*|(?:articolo|post|giornale|stampa).{0,60}(?:diffamat\w*|lesivo della reputazione)"),
    ("capitalizzazione_rendita", 3, r"capitalizz\w*.{0,30}rendita|rendita vitalizia.{0,30}(?:capital|valore)|coefficient\w* di capitalizzazione|lucro cessante futuro"),
    # ---------------------------------------------------------------- lavoro e previdenza
    ("tfr", 4, r"\btfr\b|trattamento di fine rapporto|\bbuonuscita\b|(?:di|la|il|alla|a) fine (?:del )?rapporto|"
               r"(?:cosa|quanto) (?:gli|le|mi|ci) spetta.{0,40}(?:fine del rapporto|cessazione del rapporto|dimission|licenzia)|"
               r"liquidazione (?:del|di fine|maturata|che (?:gli|le) spetta)"),
    ("tfr", 3, r"\btfr\b|trattamento di fine rapporto|liquidazione (?:di fine rapporto|del lavoratore)|(?:dipendent\w*|lavorator\w*|assunt\w*|in servizio|in azienda).{0,80}\bliquidazione\b"),
    # Il TFR chiesto per conto del cliente con i verbi del ricevere («quanto prende, riceve, incassa, porta a casa di
    # liquidazione»), o la liquidazione legata alla fine del lavoro; non la liquidazione giudiziale, del danno o delle spese.
    ("tfr", 4, r"\bliquidazione\b(?! (?:giudizial|coatt|del danno|delle spese|dei compensi|dell'eredit|della societa|del patrimonio|dell'attivo))"
               r"(?=.{0,120}(?:lascia\w* il lavoro|lascia\w* l'azienda|dimess\w*|dimission\w*|licenziat\w*|pension\w*|anni di (?:lavoro|servizio)|"
               r"di lavoro|di servizio|fine (?:del )?lavoro|cessazion\w*|\d+ anni))|"
               r"(?:lascia\w* il lavoro|lascia\w* l'azienda|dimess\w*|dimission\w*|anni di (?:lavoro|servizio)|operai\w*|impiegat\w*|dipendent\w*|"
               r"lavorat(?:or|ric)\w*|magazzinier\w*|commess\w*|colf|badant\w*).{0,100}\bliquidazione\b(?! (?:giudizial|coatt|del danno|delle spese))|"
               r"quanto (?:\w+ )?(?:prend\w*|ricev\w*|incass\w*|porta a casa|gli dann\w*|le dann\w*|mi dann\w*|(?:gli |le |mi )?verr\w* (?:dat|liquidat|corrispost|pagat)\w*)"
               r" (?:di |come )?(?:liquidazione|tfr|trattamento di fine rapporto|buonuscita)"),
    ("indennita_licenziamento", 3, r"licenziat\w*.{0,80}(?:senza giusta causa|senza giustificato motivo|illegittim\w*|ingiustificat\w*|\bnullo\b|annullat\w*)|"
                                   r"(?:senza giusta causa|illegittim\w*|ingiustificat\w*).{0,40}licenzia\w*"),
    ("indennita_licenziamento", 3, r"(?:quanto|spett\w*|indennita|risarciment\w*).{0,60}licenziat\w*|indennita (?:di|per il|per) licenziament\w*|(?:licenziat\w*|licenziamento).{0,80}(?:quanto|spetta|mensilita|indennita|risarc)|tutele crescenti|indennita sostitutiva del preavviso|preavviso.{0,30}mensilit"),
    ("contributi_cassa_forense", 3, r"cassa forense|contribut\w* (?:previdenzial\w* )?(?:dell'avvocato|forens\w*|alla cassa)|contributo (?:soggettivo|integrativo)"),
    ("reversibilita", 4, r"reversibilita|pensione (?:ai superstiti|indiretta)|vedov\w*.{0,60}pension\w*|pension\w* del (?:marito|coniuge|moglie) (?:defunt\w*|decedut\w*|mort\w*)"),
    ("fattura_agente", 3, r"\benasarco\b|fattura (?:dell'|di un )?agente|provvigion\w*.{0,30}(?:fattura|enasarco)"),
    ("prestazione_occasionale", 3, r"prestazione occasionale|ricevuta (?:per )?(?:compenso )?occasionale|lavoro autonomo occasionale|ritenuta d'acconto.{0,30}occasional"),
    # ---------------------------------------------------------------- famiglia e successioni
    ("assegno_mantenimento", 4, r"(?:quanto|che importo|quale importo).{0,60}(?:mantenimento|assegno)|mantenimento.{0,60}(?:quanto|figli|coniuge|ex)|assegno (?:di mantenimento|divorzile|per i figli)"),
    ("assegno_mantenimento", 3, r"assegno.{0,60}(?:guadagn\w*|reddit\w*|stipend\w*)|(?:separat\w*|divorziat\w*|ex coniuge).{0,60}assegno|assegno (?:di mantenimento|divorzile|perequativo)|mantenimento (?:del|dei|della|per) (?:figli\w*|coniuge|moglie|marito|ex)|quanto (?:deve|devo) (?:versare|dare) (?:per|ai|al|alla) (?:figli|moglie|marito|ex)"),
    ("successione_legittima", 3, r"eredit\w*.{0,60}(?:figli|coniuge|moglie|marito|fratell|genitori)|asse ereditario.{0,80}(?:coniuge|moglie|marito|figli|fratell|genitori)|"
                                 r"(?:coniuge|moglie|marito|figli|fratell|genitori).{0,80}asse ereditario|"
                                 r"(?:moglie|marito|coniuge).{0,40}(?:figli|fratell|genitori).{0,80}(?:eredit|patrimonio|spett|quot|divid|va a chi|a chi va)|"
                                 r"(?:del defunto|del de cuius|alla morte).{0,80}(?:eredit|spett|quot|divid|a chi va)|"
                                 r"patrimonio.{0,120}(?:a chi va|chi eredita|come si divide)|"
                                 r"patrimonio.{0,80}(?:moglie|marito|coniuge|figli).{0,60}(?:eredit|spett|quot|divid)"),
    ("successione_legittima", 4, r"successione legittima|eredi legittimi|chi eredita|(?:muore|morto|morta|deceduto|deceduta) senza testamento|ab intestato"),
    ("successione_legittima", 3, r"successione legittima|quote (?:ereditarie|di eredita)|senza testamento.{0,120}(?:spetta|eredi|quota|si divide|divisione)|(?:come si divide|divisione).{0,40}eredit|(?:eredi|eredita).{0,60}(?:senza testamento|ab intestato)|chi eredita|quanto (?:eredita|spetta (?:al|alla|ai) (?:coniuge|figli|fratell))"),
    # La morte raccontata con gli eredi e i beni, senza una domanda espressa: chi eredita e quanto.
    ("successione_legittima", 4, r"^(?!.*(?:risarc|\bdanno|incident|sinistro|pension|reversibil|impost|tass[ae]\b))"
                                 r"(?=.*(?:\bmort[oa]\b|decedut\w*|defunt\w*|de cuius|scompars[oa]\b|venut[oa] a mancare))"
                                 r"(?=.*(?:figli|fratell\w*|sorell\w*|coniuge|moglie|marito|nipot\w*|genitor\w*|madre|padre|vedov\w*))"
                                 r"(?=.*(?:lascia\w*|patrimonio|eredit\w*|\beuro\b|immobil\w*|\bcasa\b|\bbeni\b|conto corrente))"),
    # L'eredità descritta con i beni e gli eredi, senza la parola «morto»: chi eredita e quanto.
    ("successione_legittima", 4, r"^(?!.*(?:risarc|\bdanno|incident|sinistro|pension|reversibil|impost|tass[ae]\b|testament))"
                                 r"(?=.*(?:\beredit\w*|asse ereditario|\beredi\b|patrimonio (?:del|della) (?:defunt|de cuius)))"
                                 r"(?=.*(?:figli\w*|fratell\w*|sorell\w*|coniuge|moglie|marito|nipot\w*|genitor\w*|madre|padre))"
                                 r"(?=.*(?:\beuro\b|\d{2,}|immobil\w*|appartament\w*|\bcasa\b|conto corrente))"),
    ("quote_riserva", 4, r"legittima les\w*|les\w* (?:della |la )?legittima|testament\w*.{0,60}(?:tutto|intero patrimonio).{0,60}(?:figli|coniuge|legittima)"),
    ("quote_riserva", 4, r"quot\w* di (?:riserva|legittima)|\blegittima\b.{0,40}(?:figli|coniuge|spett|quanto)|(?:quanto|che quota).{0,60}legittima|legittimari"),
    ("quote_riserva", 3, r"quot\w* (?:di )?riserva|legittima (?:del|dei|spettante)|legittimari\w*|lesione della legittima|disponibile.{0,30}testament|azione di riduzione"),
    ("imposte_successione", 3, r"(?:tass\w*|impost\w*).{0,60}eredit\w*|eredit\w*.{0,60}(?:tass\w*|impost\w*)|impost\w* di successione|tass\w* (?:di|sulla) successione|franchigia (?:di|da) (?:un milione|1\.000\.000|100\.000)|dichiarazione di successione.{0,60}(?:impost|quanto|pagare)|impost\w* (?:ipotecari\w*|catastal\w*).{0,40}successione"),
    ("usufrutto", 3, r"usufrutto|nuda proprieta|diritto di abitazione.{0,30}valore"),
    ("grado_parentela", 4, r"che parentela|parentela (?:c'e )?(?:tra|fra)|grado di parentela|che grado (?:di parentela )?(?:e|sono)|parent\w* di (?:primo|secondo|terzo|quarto|quinto|sesto) grado|\b(?:cugin\w*|zi[oa]|nipot\w*|cognat\w*)\b.{0,40}(?:\bgrado\b|parent)"),
    # ---------------------------------------------------------------- immobili e imposte
    ("canone_locazione", 3, r"(?:aggiornamento|adeguamento|rivalutazione) (?:istat )?del canone|canone.{0,40}(?:aggiorn\w*|adegu\w*|istat)"),
    ("cedolare_secca", 3, r"cedolare secca"),
    ("detrazione_canone", 3, r"detrazion\w*.{0,40}(?:canon\w*|affitt\w*|locazion\w*|inquilin\w*)|(?:inquilin\w*|conduttore).{0,40}detrazion"),
    ("imu", 3, r"\bimu\b|imposta municipale"),
    ("valore_catastale", 3, r"valore catastale|rendita catastale.{0,40}(?:valore|rivalut|moltiplic)|base imponibile catastale|prezzo valore"),
    ("categorie_catastali", 3, r"categori\w* catastal\w*|(?:cosa (?:e|significa)|che cos'e) (?:la )?(?:categoria )?a/?\d|categoria [a-f]/?\d"),
    # la tabella del catasto chiesta per gruppo è solo questo calcolatore
    ("categorie_catastali", 4, r"tabella (?:del |dal )?catast\w*|gruppo catastal\w*|(?:categori\w*|elenco) del catasto"),
    ("imposte_compravendita", 4, r"acquist\w* (?:della |di una |la )?(?:prima |seconda )?casa.{0,60}impost|prima casa.{0,60}impost|impost\w*.{0,40}(?:acquisto|compravendita|rogito)"),
    ("imposte_compravendita", 3, r"impost\w* (?:sulla|per la|di) (?:compravendita|acquisto (?:della|di una) casa|rogito)|(?:compro|acquisto|comprare) (?:casa|un immobile|un appartamento).{0,80}(?:impost|tasse|quanto pago)|agevolazion\w* prima casa"),
    ("riparto_spese", 3, r"ripart\w* (?:delle )?spese|ripartizione (?:delle )?(?:spese|utenze|bollette)|millesim\w*|spese condominiali.{0,40}(?:divid|ripart|quota)"),
    ("irpef", 3, r"\birpef\b|scaglioni (?:irpef|di reddito)|imposta (?:lorda|sul reddito delle persone)"),
    ("acconto_imposte", 3, r"acconto (?:irpef|imposte|cedolare|di novembre|di giugno)|secondo acconto|primo acconto"),
    ("rateazione_imposte", 3, r"rateizz\w*|rateazion\w*|rate (?:delle imposte|del saldo)|pagare a rate (?:le )?(?:imposte|tasse)"),
    ("ravvedimento_operoso", 4, r"(?:pagat\w*|versat\w*|saldat\w*) (?:\w+ )?tardi\b.{0,80}sanzion|(?:rata|rottamazione|definizione agevolata).{0,80}(?:tardi\b|in ritardo|di ritardo)|"
                                r"(?:ridurre|riduzione|ridott\w*) (?:la |della )?sanzion\w*.{0,60}(?:ritardo|tardi|tardiv)|(?:ritardo|tardi|tardiv).{0,80}(?:ridurre|riduzione|ridott\w*) (?:la |della )?sanzion"),
    ("ravvedimento_operoso", 4, r"(?:cartell\w*|\bf24\b|impost\w*|tribut\w*|\biva\b|\bimu\b|\btass[ae]\b|avviso bonario|\brata\b|rottamazione).{0,80}"
                                r"(?:in ritardo|di ritardo|tardiv\w*|regolarizz\w*|oltre la scadenza|dopo la scadenza)|"
                                r"(?:in ritardo|di ritardo|tardiv\w*|regolarizz\w*).{0,80}(?:cartell\w*|\bf24\b|impost\w*|tribut\w*|\biva\b|\bimu\b|\btass[ae]\b)"),
    ("ravvedimento_operoso", 4, r"ravvediment\w*|(?:quanto|che) sanzion\w*.{0,60}(?:ritardo|tardiv|non (?:ho )?pagat|omesso versamento)|(?:pagato|versato|pagamento) (?:in ritardo|di ritardo|tardiv\w*).{0,60}(?:f24|imposta|tributo|sanzion)|sanzion\w* ridott\w*.{0,30}(?:ritardo|tardiv)"),
    # Un tributo scaduto o una scadenza saltata, e la domanda di quanto costa rimediare ora: ravvedimento, in qualunque ordine.
    ("ravvedimento_operoso", 4, r"^(?=.*(?:cartell\w*|\bf24\b|impost\w*|tribut\w*|\biva\b|\bimu\b|\btari\b|\btass[ae]\b|bollo auto|\brata\b|"
                                r"acconto|versament\w*|dichiarazion\w*))"
                                r"(?=.*(?:scadut\w*|saltat\w*|non (?:ho |ha |abbiamo |hanno )?(?:pagat|versat)\w*|omess\w*|dimenticat\w*|mancat\w*|oltre il termine))"
                                r"(?=.*(?:in piu\b|in regola|regolarizz\w*|sanzion\w*|\badesso\b|\bora\b|\boggi\b|quanto|costa|rimediare|sistemare))"),
    ("regime_forfettario", 3, r"(?:regime )?forfettari\w*|flat tax (?:per gli )?autonomi|coefficiente di redditivita"),
    ("detrazioni_familiari", 3, r"detrazion\w* (?:per )?(?:familiari|figli|coniuge) a carico|familiari a carico"),
    ("detrazioni_reddito", 3, r"detrazion\w* (?:per |da )?(?:lavoro dipendente|pensione|redditi assimilati|tipo di reddito)"),
    ("codice_fiscale", 3, r"codice fiscale.{0,40}(?:calcol|verific|controll|genera|e giusto|corretto)|(?:calcol|verific|controll).{0,20}codice fiscale"),
    ("codice_fiscale", 4, r"\b[a-z]{6}\d{2}[a-z]\d{2}[a-z]\d{3}[a-z]\b|decodific\w*.{0,30}codice fiscale|codice fiscale.{0,40}(?:decodific|data di nascita|di chi|a chi|nato|luogo di nascita|leggere)"),
    # ---------------------------------------------------------------- penale
    ("pena_riti_alternativi", 3, r"(?:pena|condanna).{0,60}(?:abbreviat\w*|patteggi\w*|riti alternativi|attenuant\w*|riduzione)|patteggiamento.{0,40}(?:pena|quanto)|rito abbreviato.{0,60}(?:pena|sconto|ridu\w*)|sconto di pena|(?:attenuant\w*|abbreviat\w*|patteggi\w*).{0,60}(?:pena|ridu\w*)"),
)

# Campo di scelta il cui valore è certo dall'uso nominato nella domanda.
CAMPI_DA_USO: tuple[tuple[str, str, str, str], ...] = (
    # (calcolatore, campo, valore, espressione)
    ("termini_processuali", "term_modello", "CIV_IMPUGNAZIONE_DELIBERA_1137", r"delibera (?:condominiale|assembleare|dell'assemblea)"),
    ("termini_processuali", "term_modello", "CIV_OPPOSIZIONE_DI", r"opposizione.{0,30}decreto ingiuntivo|oppor\w*.{0,30}decreto ingiuntivo|decreto ingiuntivo.{0,80}(?:opposizion\w*|oppor\w*)"),
    ("termini_processuali", "term_modello", "CIV_MEMORIA_171_TER_1", r"prima memoria.{0,30}171|171-?ter.{0,30}(?:prima|n\.? ?1|comma 1)"),
    ("termini_processuali", "term_modello", "CIV_MEMORIA_171_TER_2", r"seconda memoria.{0,30}171|171-?ter.{0,30}(?:seconda|n\.? ?2)"),
    ("termini_processuali", "term_modello", "CIV_MEMORIA_171_TER_3", r"terza memoria.{0,30}171|171-?ter.{0,30}(?:terza|n\.? ?3)"),
    ("termini_processuali", "term_modello", "ESE_PRECETTO_EFFICACIA_90GG", r"efficacia del precetto|precetto.{0,40}(?:perde efficacia|90|novanta)"),
    ("termini_processuali", "term_modello", "ESE_PRECETTO_ADEMPIMENTO_10GG", r"precetto.{0,40}(?:10|dieci) giorni|termine (?:per )?adempiere (?:al )?precetto"),
    ("termini_processuali", "term_modello", "ESE_OPPOSIZIONE_ATTI_617", r"opposizione agli atti esecutivi|\b617\b"),
    ("termini_processuali", "term_modello", "CIV_RECLAMO_CAUTELARE_669_TERDECIES", r"reclamo cautelare|669-?terdecies"),
    ("termini_processuali", "term_modello", "AMM_RICORSO_29", r"ricorso (?:al )?tar(?!.{0,30}appalt)"),
    ("termini_processuali", "term_modello", "AMM_APPALTI_120", r"(?:appalt|gara).{0,40}(?:tar|ricorso)|(?:tar|ricorso).{0,40}(?:appalt|gara)"),
    ("termini_processuali", "term_modello", "TRIB_RICORSO_21", r"(?:ricorso|ricorrere).{0,40}(?:corte di giustizia tributaria|commissione tributaria|avviso di accertamento|cartella)"),
    ("termini_processuali", "term_modello", "CDS_RICORSO_PREFETTO_60GG", r"ricorso al prefetto"),
    ("termini_processuali", "term_modello", "CDS_RICORSO_GDP_30GG", r"(?:multa|verbale).{0,60}giudice di pace|ricorso al giudice di pace.{0,40}(?:multa|verbale)"),
    ("termini_processuali", "term_modello", "CIV_COSTITUZIONE_CONVENUTO_166", r"costitu\w+ (?:del )?convenut\w*|convenut\w*.{0,30}costitu"),
    ("termini_processuali", "term_modello", "CIV_RIASSUNZIONE_305", r"riassun\w*.{0,40}interruzione|interruzione.{0,40}riassun"),
    ("termini_penali", "tp_atto", "memorie_415bis", r"415-?bis|conclusione (?:delle )?indagini"),
    ("termini_penali", "tp_atto", "opposizione_decreto_penale", r"decreto penale"),
    ("termini_penali", "tp_atto", "riesame_personale", r"riesame(?!.{0,20}reale)"),
    ("termini_penali", "tp_atto", "opposizione_archiviazione", r"opposizione (?:alla richiesta di |all')archiviazione|archiviazion\w*.{0,80}oppo\w*|oppo\w*.{0,40}archiviazion"),
    ("termini_penali", "tp_atto", "impugnazione_sentenza", r"(?:impugn\w*|appell\w*).{0,40}sentenza"),
    ("impugnazioni", "imp_mezzo", "cassazione", r"cassazione"),
    ("impugnazioni", "imp_mezzo", "appello", r"\bappell\w*"),
    ("interessi", "int_tipo", "mora_commerciale", r"(?:mora|ritardat\w* pagament\w*).{0,40}(?:commercial|transazion|fornitur|imprese)|231/2002"),
    ("interessi", "int_tipo", "legali", r"interess\w* legal\w*"),
    ("perfezionamento_notifica", "not_canale", "pec", r"\bpec\b|posta elettronica certificata"),
    ("perfezionamento_notifica", "not_canale", "posta", r"(?:a mezzo|per|con) (?:il servizio )?post\w*|raccomandat\w*"),
    ("perfezionamento_notifica", "not_canale", "art140", r"\b140\b|irreperibil\w* relativ"),
    ("perfezionamento_notifica", "not_canale", "art143", r"\b143\b|irreperibil\w* assolut"),
    ("danno_biologico", "db_ambito", "circolazione", r"incidente stradale|sinistro stradale|tamponament|circolazione|rc auto|in auto|in moto"),
    ("danno_biologico", "db_ambito", "sanitaria", r"malpractice|responsabilita (?:medica|sanitaria)|errore medico|ospedal\w*|interven\w* chirurgic"),
    ("assegno_mantenimento", "man_percorso", "divorzio", r"divorzi\w*"),
    ("assegno_mantenimento", "man_percorso", "separazione", r"separazion\w*.{0,40}(?:coniuge|moglie|marito)|(?:coniuge|moglie|marito).{0,40}separazion"),
    ("assegno_mantenimento", "man_percorso", "figli", r"figli\w*"),
    ("contributo_unificato", "cu_grado", "appello", r"\bappell\w*"),
    ("contributo_unificato", "cu_grado", "cassazione", r"cassazione"),
    ("contributo_unificato", "cu_categoria", "decreto_ingiuntivo", r"decreto ingiuntivo|monitorio"),
    ("contributo_unificato", "cu_categoria", "lavoro", r"(?:causa|controversia|ricorso) di lavoro|giudice del lavoro"),
    ("contributo_unificato", "cu_categoria", "separazione_consensuale", r"separazione consensuale"),
    ("onorari_forensi", "onorari_materia", "PENALE", r"\bpenal\w*"),
    ("onorari_forensi", "onorari_materia", "MEDIAZIONE", r"mediazion\w*"),
    ("onorari_forensi", "onorari_materia", "NEGOZIAZIONE_ASSISTITA", r"negoziazion\w* assistit\w*"),
    ("onorari_forensi", "onorari_materia", "STRAGIUD", r"stragiudizial\w*"),
    ("onorari_forensi", "onorari_materia", "LAVORO", r"(?:causa|controversia) di lavoro|giudice del lavoro"),
    ("pignoramento", "pig_tipo_reddito", "pensione", r"pension\w*"),
    ("pignoramento", "pig_tipo_reddito", "stipendio", r"stipend\w*|busta paga|retribuzion\w*"),
    ("pignoramento", "pig_tipo_credito", "alimentare", r"aliment\w*|mantenimento"),
    ("pignoramento", "pig_tipo_credito", "esattoriale", r"esattorial\w*|agenzia (?:delle )?entrate riscossione|cartell\w*|fisco"),
    ("indennita_licenziamento", "lic_regime", "piccola_impresa", r"(?:meno di|sotto i|fino a) (?:15|quindici) dipendenti|piccola impresa"),
    ("indennita_licenziamento", "lic_regime", "preavviso", r"indennita (?:sostitutiva )?(?:del|di) preavviso"),
    ("imposta_registro", "reg_tipo_atto", "decreto_ingiuntivo", r"decreto ingiuntivo"),
    ("imposta_registro", "reg_tipo_atto", "verbale_conciliazione", r"verbale di conciliazione|conciliazione"),
    ("imposta_registro", "reg_tipo_atto", "sentenza_separazione", r"sentenza di separazione"),
    ("imposta_registro", "reg_tipo_atto", "lodo_arbitrale", r"\blodo\b"),
    ("competenza_valore", "comp_materia", "danno_circolazione", r"incidente|sinistro|circolazione|veicol\w*|auto\b"),
    ("competenza_valore", "comp_materia", "beni_mobili", r"beni mobili|merce|fornitur|vendita di|prestito|fattur\w*"),
)


__all__ = ["CAMPI_DA_USO", "USI"]
