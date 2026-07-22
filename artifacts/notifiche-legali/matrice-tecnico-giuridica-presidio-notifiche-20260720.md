# Matrice tecnico-giuridica presidio notifiche, PEC, udienze e scadenze

Data: 20/07/2026  
Tenant di riferimento: `studio-legale-giuseppe-montagnese`  
Stato: dossier aggiornato dopo implementazione server-first e audit reale del 21/07/2026.

## Obiettivo

Il presidio deve permettere all'avvocato di fidarsi del software. Per questo IUSENTRA non deve limitarsi a cercare la parola `notifica`, `sentenza` o `udienza`, ma deve capire la funzione processuale dell'atto e produrre l'azione corretta:

- notifica da eseguire;
- prova di notifica da completare o depositare;
- termine processuale da mettere nello Scadenziario;
- udienza o trattazione da mettere in Agenda;
- avviso operativo in topbar e Web Push;
- solo monitoraggio, quando non esiste un adempimento immediato;
- storico già gestito, solo quando la prova o la regola di migrazione lo consentono.

## Regola madre

La data del documento non basta. La decisione deve usare insieme:

1. natura dell'atto;
2. fonte dell'atto: PEC di cancelleria, PST/PolisWeb, documento d'ufficio, documento importato, PEC inviata dallo studio, ricevuta RAC/RdAC, deposito prova;
3. testo dell'atto e ordini del giudice;
4. dati del fascicolo: RG, ufficio, parte, rito, stato, documenti collegati;
5. prove già presenti: relata, PEC inviata, RAC, RdAC, attestazione, deposito prova;
6. data di ricezione/elaborazione, distinta dalla data del provvedimento;
7. cutoff storico 19/07/2026 solo come regola di migrazione, non come criterio giuridico.

## Caso-spia Alfano / RG 1100/2026

Documento allegato dall'utente: `C:\Users\antmm\Downloads\19040620s.pdf`.

Estrazione testo eseguita:

- Tribunale ordinario di Padova, Sezione I civile - lavoro;
- RG `1100/2026`;
- parte ricorrente `Giuseppe Alfano`;
- controparte `Ministero dell'Istruzione e del Merito`;
- decisione del 16/07/2026;
- sentenza resa ex art. 429 c.p.c.;
- accertato diritto alla Carta docente per gli anni scolastici 2021/2022, 2022/2023, 2023/2024;
- condanna del Ministero a costituire/accreditare la Carta elettronica con euro 500 per ciascun anno;
- spese liquidate in euro 1.030,00 oltre 15% spese generali, IVA e CPA, con distrazione in favore del procuratore antistatario.

Decisione tecnico-giuridica applicata nel codice:

- non è una semplice udienza da archiviare;
- non è una comunicazione che fa decorrere automaticamente il termine breve;
- è una sentenza favorevole con spese distratte e titolo operativo da valutare;
- se lo studio decide di notificare la sentenza per far decorrere il termine breve o per presidiare l'adempimento/esecuzione, il software deve proporre una attività chiara `Valutare/preparare notifica sentenza`, collegata al fascicolo, alla sentenza e ai destinatari corretti;
- non deve essere cancellata dal cutoff storico solo perché la data del provvedimento è 16/07/2026, se la ricezione/elaborazione è nuova o se l'avvocato la indica come attività da notificare.

Esito implementato e verificato sul tenant produzione il 21/07/2026:

- il caso Alfano/RG `1100/2026` è stato classificato come `sentenza_a_verbale`/`judgment_to_notify_review`, non come opposizione 127-ter;
- la PEC sorgente `pec_8d456e0fe2f268159b5510b5`, ricevuta il `16/07/2026 13:01` ora italiana, ha generato presidio operativo `NEEDS_REVIEW`;
- il fascicolo non contiene, dopo la ricezione della sentenza, una prova completa composta da relata, PEC L. 53, RAC, RdAC completa e deposito prova;
- quindi il software deve mostrare all'avvocato `Sentenza da valutare per la notifica` e non `notifica già eseguita`;
- il termine breve non viene creato automaticamente dalla comunicazione di cancelleria.

## Fonti già consultate

- Codice di procedura civile, art. 429, Gazzetta Ufficiale: la sentenza nel rito lavoro viene pronunciata in udienza con lettura del dispositivo e delle ragioni; in caso di complessità il giudice fissa termine per deposito.
- Codice di procedura civile, art. 431: le sentenze di condanna a favore del lavoratore per crediti di lavoro sono provvisoriamente esecutive; occorre comunque distinguere il caso Carta docente e le attività concrete da eseguire.
- Codice di procedura civile, artt. 325 e 326: il termine breve di impugnazione decorre dalla notificazione della sentenza; la comunicazione di cancelleria non basta.
- Codice di procedura civile, art. 327: in assenza di notificazione opera il termine lungo dalla pubblicazione della sentenza.
- Codice di procedura civile, art. 133 come modificato dal D.Lgs. 164/2024: la comunicazione del deposito della sentenza non è idonea a far decorrere i termini di impugnazione di cui all'art. 325.
- Codice di procedura civile, artt. 127-bis e 127-ter: udienza da remoto e deposito note scritte in sostituzione dell'udienza; opposizione/richiesta entro 5 giorni dalla comunicazione; deposito note con termine perentorio; il giorno di scadenza delle note è data di udienza a tutti gli effetti.
- Codice di procedura civile, art. 171-ter: memorie integrative 40/20/10 giorni prima dell'udienza di cui all'art. 183.
- Codice di procedura civile, art. 479: l'esecuzione forzata deve essere preceduta dalla notificazione del titolo esecutivo e del precetto, salvo diversa disposizione.
- Portale Servizi Telematici del Ministero della Giustizia, scheda notifiche L. 53/1994 via PEC: oggetto PEC, allegati, relata separata firmata digitalmente, richiesta ricevuta completa, RAC/RdAC e deposito ricevute.

## Ricerca web normativa estesa del 20/07/2026

Questa sezione è stata aggiunta dopo la richiesta dell'utente di non procedere a intuito e di conoscere gli articoli spesso menzionati negli atti. Le fonti usate sono principalmente Gazzetta Ufficiale, Portale Servizi Telematici del Ministero della Giustizia e, solo come ausilio di lettura quando la pagina ufficiale non era comoda, repertori giuridici aggiornati che rinviano al testo normativo.

### Sentenza, definitività, giudicato e termini di impugnazione

- Art. 324 c.p.c. - cosa giudicata formale: una sentenza è passata in giudicato quando non è più soggetta a regolamento di competenza, appello, ricorso per cassazione o revocazione ordinaria nei casi indicati. Regola software: non usare la formula testuale `definitivamente decidendo` come sinonimo automatico di `passata in giudicato`; quella formula di solito indica che il giudice definisce quel grado o quella fase.
- Art. 285 c.p.c. - notificazione della sentenza: la notifica della sentenza finalizzata al termine di impugnazione avviene su istanza di parte e secondo l'art. 170. Regola software: per far partire il termine breve serve una vera notificazione di parte, non basta la comunicazione della cancelleria.
- Art. 325 c.p.c. - termini brevi: trenta giorni per appello/revocazione/opposizione di terzo revocatoria; sessanta giorni per ricorso per cassazione. Regola software: creare scadenza breve solo se esiste notifica sentenza valida, con destinatario e prova.
- Art. 326 c.p.c. - decorrenza termini brevi: i termini dell'art. 325 decorrono dalla notificazione della sentenza, dal perfezionamento verso il destinatario. Regola software: RAC/RdAC, destinatario e oggetto notificato sono dati necessari per trattare il termine come operativo.
- Art. 327 c.p.c. - termine lungo: indipendentemente dalla notificazione, appello/ricorso per cassazione/revocazione ordinaria non possono proporsi dopo sei mesi dalla pubblicazione della sentenza, salvo eccezioni per il contumace ignaro. Regola software: se non esiste notifica sentenza, presidiare termine lungo da pubblicazione/deposito, non termine breve.
- Art. 133 c.p.c. - pubblicazione/comunicazione sentenza: la comunicazione del deposito alle parti costituite non è idonea a far decorrere i termini ex art. 325. Regola software: `Comunicazione.xml` con sentenza allegata produce `esame sentenza` e, se opportuno, `valutare notifica`, ma non `termine breve già decorrente`.

### Rito lavoro e sentenza ex art. 429 c.p.c.

- Art. 429 c.p.c. - pronuncia della sentenza nel rito lavoro: il giudice, esaurita la discussione, pronuncia sentenza e definisce il giudizio; può fissare un termine massimo di sessanta giorni per il deposito in caso di complessità; può concedere note difensive fino a dieci giorni se necessario. Regola software: se il testo contiene `decide la causa con sentenza`, `P.Q.M.`, `definitivamente decidendo`, `sentenza resa ex art. 429`, l'evento prevalente è sentenza, non udienza.
- Art. 430 c.p.c. - deposito della sentenza: nel rito lavoro la sentenza deve essere depositata in cancelleria e comunicata alle parti. Regola software: il deposito/comunicazione alimenta `esame sentenza`, non prova di notifica eseguita.
- Art. 431 c.p.c. - esecutorietà della sentenza di lavoro: le sentenze di condanna in materia lavoro sono provvisoriamente esecutive nei casi previsti. Regola software: distinguere `titolo/adempimento/esecuzione da valutare` da `giudicato`; l'esecutività provvisoria non equivale a definitività.
- Art. 433 c.p.c. - appello lavoro: l'appello contro sentenze delle controversie ex art. 409 si propone con ricorso davanti alla Corte d'appello in funzione di giudice del lavoro. Regola software: nel rito lavoro l'esito sentenza deve alimentare anche il profilo di possibile appello/termine, con revisione umana.

### Udienza, rinvio, trattazione scritta e note

- Art. 127 c.p.c. coordinato con 127-bis e 127-ter: il giudice può disporre udienza con collegamenti audiovisivi o sostituzione con note scritte. Regola software: queste sono modalità dell'udienza, non notifiche.
- Art. 127-bis c.p.c. - udienza mediante collegamenti audiovisivi: il provvedimento è comunicato almeno quindici giorni prima; ciascuna parte può chiedere udienza in presenza entro cinque giorni dalla comunicazione; il giudice decide nei cinque giorni successivi. Regola software: Agenda con link/aula; Scadenziario per richiesta presenza entro cinque giorni se pertinente; topbar/Web Push se link mancante o evento imminente.
- Art. 127-ter c.p.c. - note scritte in sostituzione dell'udienza: il giudice assegna termine perentorio non inferiore a quindici giorni per le note; ciascuna parte può opporsi entro cinque giorni dalla comunicazione; il giorno di scadenza delle note è data di udienza a tutti gli effetti; se nessuno deposita, può seguire nuovo termine o udienza, fino a cancellazione/estinzione. Regola software: `note_127_ter_da_depositare`, `opposizione_127_ter_da_valutare`, `udienza_cartolare`, non `notifica da eseguire` salvo ordine separato.
- Art. 171-bis e 171-ter c.p.c. - verifiche preliminari e memorie integrative: il giudice verifica il contraddittorio, può fissare nuova udienza, confermare/differire l'udienza e indicare questioni; le parti depositano memorie integrative con scansioni 40/20/10 giorni prima dell'udienza. Regola software: classificare come scadenze processuali e produzione/memorie, non come notifiche.
- Art. 183 c.p.c. - trattazione e calendario: il giudice provvede sulle richieste istruttorie, predispone calendario delle udienze e, se dispone mezzi di prova d'ufficio, assegna termini per deduzioni e repliche. Regola software: `rinvio/fissazione/calendario` genera Agenda e termini istruttori.
- Art. 420 c.p.c. - udienza di discussione nel rito lavoro: il giudice interroga le parti, tenta la conciliazione, può assumere mezzi istruttori e gestire il processo in udienza. Regola software: se il provvedimento fissa o rinvia udienza lavoro, creare Agenda; se assegna attività istruttorie o note, creare scadenze.
- Art. 421 c.p.c. - poteri istruttori del giudice del lavoro: il giudice indica irregolarità sanabili di atti/documenti assegnando termine e può disporre mezzi di prova. Regola software: se l'atto chiede integrazioni, produzioni o regolarizzazioni documentali, creare `documenti_da_depositare/regolarizzare`, non `notifica`.
- Art. 210 c.p.c. - ordine di esibizione: il giudice può ordinare alla parte o al terzo l'esibizione di documenti o cose necessari. Regola software: scadenza documentale/probatoria con soggetto obbligato e prova del deposito/esibizione; nessuna notifica salvo espressa disposizione.

### Opposizioni, decreti ingiuntivi, cautelari ed esecuzione

- Art. 641 c.p.c. - decreto ingiuntivo: il decreto ingiunge pagamento/consegna nel termine ordinario di quaranta giorni, con avviso che nello stesso termine può essere fatta opposizione; termini diversi sono possibili nei casi previsti. Regola software: per il creditore assistito il presidio è `notifica decreto ingiuntivo` e monitoraggio opposizione; per il debitore assistito è `opposizione a decreto ingiuntivo`.
- Art. 643 c.p.c. - notificazione del decreto ingiuntivo: ricorso e decreto sono notificati e la notificazione determina pendenza della lite. Regola software: distinguere bozza/ottenimento decreto da notifica effettiva.
- Art. 644 c.p.c. - mancata notificazione del decreto: il decreto diventa inefficace se non notificato entro sessanta giorni dalla pronuncia nel territorio della Repubblica, novanta negli altri casi. Regola software: scadenza critica `notifica DI entro 60/90 giorni`.
- Art. 645 c.p.c. - opposizione a decreto ingiuntivo: l'opposizione si propone davanti all'ufficio del giudice che ha emesso il decreto. Regola software: quando arriva un'opposizione, l'evento cambia stato del fascicolo e non è più una notifica da fare; quando arriva il decreto, invece, presidiare la notifica.
- Art. 669-terdecies c.p.c. - reclamo cautelare: contro ordinanza che concede o nega provvedimento cautelare è ammesso reclamo nel termine perentorio di quindici giorni dalla pronuncia in udienza, oppure dalla comunicazione o notificazione se anteriore. Regola software: termine cautelare P0/P1 solo se l'atto è cautelare.
- Art. 479 c.p.c. - titolo esecutivo e precetto: l'esecuzione forzata deve essere preceduta dalla notificazione del titolo e del precetto, salvo diversa disposizione. Regola software: dopo sentenza/titolo favorevole, eventuale fase esecutiva richiede presidio distinto `titolo/precetto`.
- Art. 615 c.p.c. - opposizione all'esecuzione: riguarda la contestazione del diritto a procedere a esecuzione forzata. Regola software: se l'atto parla di opposizione ex 615, classificarlo come opposizione sostanziale all'esecuzione.
- Art. 617 c.p.c. - opposizione agli atti esecutivi: riguarda regolarità formale di titolo, precetto o atti esecutivi, con termine perentorio di venti giorni nei casi previsti. Regola software: se l'atto parla di 617, classificare termine/formalità dell'esecuzione, non opposizione monitoria o 127-ter.

### Notifiche L. 53/1994 via PEC e prova

- Portale Servizi Telematici del Ministero della Giustizia, scheda notificazioni telematiche L. 53/1994: indirizzo PEC mittente e destinatario devono risultare da pubblici elenchi; l'oggetto PEC deve riportare la dizione di notificazione ai sensi della legge n. 53 del 1994; vanno allegati atto, eventuale procura e relata separata firmata digitalmente; va richiesta RdAC completa; la notifica si perfeziona per il notificante con RAC e per il destinatario con RdAC; per il deposito in cancelleria vanno inseriti atto notificato, RAC e RdAC. Regola software: senza RAC/RdAC complete e coerenti non mostrare `notificata`; mostrare `inviata in attesa ricevute`, `RAC raccolta`, `RdAC raccolta`, `prova da depositare` o `mancata consegna`.

## Distinzione operativa obbligatoria: esito dell'atto prima della notifica

Il primo classificatore non deve chiedersi subito "va notificato?", ma:

1. l'atto definisce il giudizio o una fase?  
   Esempi: sentenza, ordinanza decisoria, ordinanza di accoglimento/rigetto che definisce, decreto che chiude. Output: `esame_provvedimento`, `termine_impugnazione`, eventuale `notifica_da_valutare`, eventuale `titolo/adempimento/esecuzione`.
2. l'atto rinvia o fissa un'udienza?  
   Esempi: `rinvia`, `fissa udienza`, `differisce`, `comparizione`, `discussione`, `trattazione scritta`, `collegamento audiovisivo`. Output: Agenda, modalità udienza, link/aula, eventuali termini 127-bis/127-ter.
3. l'atto assegna un termine per note, memorie o documenti?  
   Esempi: `assegna termine`, `deposito note`, `produzioni documentali`, `ordine di esibizione`, `integrazione documenti`, `regolarizzazione`. Output: Scadenziario documentale/probatorio, task avvocato, alert se vicino.
4. l'atto ordina o richiede una notifica?  
   Esempi: `notificare ricorso e decreto`, `notificare il provvedimento`, `termine per la notifica`, decreto ingiuntivo da notificare. Output: Notifiche legali operative, con destinatari e prove richieste.
5. l'atto è prova di una notifica già eseguita?  
   Esempi: PEC L. 53 inviata, RAC, RdAC, ricevuta completa, deposito prova, accettazione deposito. Output: completamento catena prova, non nuova notifica.
6. l'atto è solo comunicazione di cancelleria?  
   Output: collegamento al fascicolo e classificazione dell'evento contenuto, ma non prova di notifica di parte.

## Regola corretta per Alfano / RG 1100/2026

La PEC server `pec_8d456e0fe2f268159b5510b5` contiene `Comunicazione.xml` con oggetto `SENTENZA A VERBALE (art. 127 ter cpc)` e l'allegato `19040620s.pdf`. Il testo del PDF dice che l'udienza era stata sostituita da note ex art. 127-ter, ma poi il giudice `decide la causa con sentenza a norma degli artt. 429 e 127ter cpc`.

Conclusione tecnico-giuridica:

- la citazione dell'art. 127-ter spiega la modalità cartolare dell'udienza;
- la citazione dell'art. 429 e il dispositivo con `definitivamente decidendo` indicano una sentenza che definisce il primo grado/fase;
- non è ancora `sentenza passata in giudicato` solo perché contiene `definitivamente decidendo`;
- la comunicazione di cancelleria non fa partire automaticamente il termine breve di impugnazione;
- il software deve creare almeno `Esame sentenza`, `Valutare/preparare notifica sentenza`, `Spese distratte da presidiare`, `Adempimento MIM/Carta docente da monitorare`;
- non deve lasciare il caso come sola `udienza_online` o `opposizione 127-ter`;
- non deve marcarlo `storico_gestito` solo perché la data provvedimento è 16/07/2026, dato che la PEC è stata ricevuta il 16/07/2026 ed è parte del perimetro che l'utente indica come ancora da presidiare.

## Matrice eventi da implementare/verificare

| Classe evento | Segnali affidabili | Azione software | Anti falso positivo |
|---|---|---|---|
| Comunicazione di cancelleria generica | `comunicazione di cancelleria`, `biglietto di cancelleria`, `Comunicazione.xml` | conservare, collegare al fascicolo, eventuale lettura evento | non creare prova di notifica L. 53; non far decorrere termine breve sentenza |
| Deposito/pubblicazione sentenza | `deposito sentenza`, `pubblicazione sentenza`, sentenza allegata o scaricata | attività `Esame sentenza`; estrazione dispositivo, spese, distrazione; valutazione notifica | non creare automaticamente termine breve art. 325 dalla sola comunicazione |
| Sentenza da notificare | sentenza completa + scelta/ordine/strategia di notifica, oppure workflow avvocato, oppure titolo/adempimento da presidiare | `Valutare/preparare notifica sentenza`, topbar/Web Push se operativa, scadenziario solo se c'è termine o attività programmata | non cancellare per cutoff se ricezione/elaborazione è nuova; non dire `notificata` senza RAC/RdAC o prova |
| Sentenza già notificata | atto notificato, relata, PEC inviata, RAC, RdAC, deposito prova | stato `prova raccolta` o `prova depositata`, nessuna nuova notifica | presenza di una sola RAC senza RdAC non basta per prova completa |
| Sentenza ex art. 429 c.p.c. | testo `resa ex art. 429`, rito lavoro, decisione in udienza | agenda: udienza/decisione completata; task: esame sentenza; eventuale notifica/adempimento | non trattare come mero rinvio udienza dopo la decisione |
| Spese distratte/antistatario | `distrazione`, `antistatario`, `in favore del procuratore` | economia fascicolo/incasso avvocato, collegato alla sentenza | spese senza distrazione = credito della parte, non incasso automatico avvocato |
| Trattazione scritta 127-ter | `127-ter`, `trattazione scritta`, `deposito note scritte`, `sostituisce l'udienza` | Agenda come udienza cartolare; Scadenziario per deposito note; topbar/Web Push se prossimo o mancante | non chiamarla `notifica` salvo ordine separato di notificare ricorso/decreto |
| Opposizione 127-ter | `opposizione entro cinque giorni dalla comunicazione` | Scadenziario termine 5 giorni; alert P0/P1 se vicino | serve data comunicazione; se manca, revisione umana |
| Note scritte | termine assegnato per note, istanze/conclusioni | attività di deposito note con termine perentorio; agenda il giorno scadenza come udienza | non confondere note già depositate con note da depositare |
| Udienza da remoto 127-bis | collegamento audiovisivo, Teams/Zoom/Meet, `127-bis` | Agenda con link verificato; Scadenziario/alert se link mancante o richiesta presenza | link solo da domini affidabili o da fonte verificata |
| Rinvio/fissazione udienza | `rinvia`, `fissa udienza`, data/ora/aula/modalità | Agenda + eventuali scadenze derivate | non duplicare se stessa data/ora/rg già presente |
| Decreto ingiuntivo da notificare | `decreto ingiuntivo`, `notificare il decreto`, art. 644 | Scadenziario notifica decreto entro 60/90 giorni; notifica operativa | non usare art. 641 come termine dello studio ricorrente; art. 641 governa opposizione dell'ingiunto |
| Opposizione a decreto ingiuntivo | decreto notificato alla parte assistita, termine opposizione | Scadenziario opposizione 40 giorni salvo termini diversi | serve data notificazione al destinatario |
| Provvedimento cautelare reclamabile | ordinanza cautelare accolta/rigettata, art. 669-terdecies | Scadenziario reclamo 15 giorni da pronuncia/comunicazione/notifica se anteriore | non applicare a provvedimenti non cautelari |
| Titolo esecutivo/precetto | sentenza/titolo + intenzione esecutiva, precetto | attività notificazione titolo/precetto e monitoraggio esecuzione | non presentare come già eseguito senza prova notifica titolo/precetto |
| PEC L. 53 inviata | oggetto `notificazione ai sensi della legge n. 53 del 1994` | aprire presidio prova; attendere RAC/RdAC | non basta la bozza PEC |
| RAC | ricevuta di accettazione | prova lato mittente; task `attendere/collegare RdAC` | non prova consegna al destinatario |
| RdAC | ricevuta avvenuta consegna completa | prova consegna; completa catena con RAC | verificare destinatario, message-id, allegati |
| Mancata consegna | avviso mancata consegna/delivery failure | alert urgente; valutare indirizzo e percorso art. 3-ter/PST se applicabile | non trattare come notifica perfezionata |

## Stato dati server Montagnese rilevato finora

- DB reale server: `/data/tenants/studio-legale-giuseppe-montagnese/studio.db`, dimensione circa 30 GB.
- Fascicolo `C3565650`: `Alfano Giuseppe c. MIM`, Tribunale di Padova, RG `1100/2026`, stato `IN_CORSO`, 28 documenti, 14 attività.
- Nel fascicolo sono presenti documenti storici/importati, ricorso e deposito telematico del ricorso notificato.
- In `scadenze` risultano eventi:
  - `Fissazione termine per note in sostituzione udienza - 16/07/2026 - RG 1100/2026`;
  - `Fissazione udienza di discussione - 16/07/2026 - RG 1100/2026`;
  - `Fissazione udienza - 13/07/2026 - RG 1100/2026`;
  - `Opposizione alla trattazione scritta ex art. 127-ter c.p.c. (5 giorni dalla comunicazione)` con scadenza `2026-07-21`.
- In `appuntamenti` risultano almeno:
  - udienza/discussione del 16/07/2026 in modalità trattazione scritta;
  - udienza del 13/07/2026 completata.
- Nelle tabelle `pec_messages` e `search_documenti` non è ancora emerso, con query stretta, il PDF `19040620s.pdf` o la sentenza Alfano del 16/07/2026 come documento indicizzato.

## Ipotesi tecnica da verificare prima del codice

Il caso Alfano potrebbe essere errato in uno di questi modi:

1. la sentenza del 16/07/2026 non è stata acquisita/indicizzata nel fascicolo, quindi il software continua a vedere solo l'udienza/trattazione scritta;
2. la sentenza è stata acquisita ma classificata come evento di udienza o documento generico, non come `sentenza da esaminare/notificare`;
3. il cutoff storico `19/07/2026` la neutralizza perché guarda la data del provvedimento e non la data di ricezione/elaborazione/azione richiesta;
4. Agenda mostra correttamente il vecchio evento 127-ter ma manca la nuova attività post-sentenza;
5. la PEC è in un repository diverso dal `studio.db` o in un mirror tenant-aware non ancora interrogato.

## Decisioni per il codice, ancora da confermare

- Creare/estendere una state machine unica `legal_event_presidio` o equivalente, usata fuori dal caricamento pagina.
- Non appesantire la UI: la pagina deve leggere eventi materializzati o payload già calcolati, non scansionare 301 fascicoli/documenti a ogni apertura.
- Separare stati:
  - `da_esaminare_sentenza`;
  - `da_valutare_notifica_sentenza`;
  - `da_preparare_notifica`;
  - `ricevute_da_completare`;
  - `prova_raccolta`;
  - `prova_depositata`;
  - `note_127_ter_da_depositare`;
  - `opposizione_127_ter_da_valutare`;
  - `udienza_da_presidiare`;
  - `monitoraggio`.
- Il cutoff storico deve restare solo overlay di migrazione: `storico_gestito` vale per segnali storici importati/provati, non per documenti nuovi o attività indicate come ancora da eseguire.

## Decisione tecnico-giuridica consolidata prima del codice

La regola non deve essere “se contiene la parola sentenza allora notifica”, perché produrrebbe falsi positivi; e non deve essere “se è prima del 20/07/2026 allora chiuso”, perché cancellerebbe atti nuovi appena arrivati o appena elaborati.

La regola corretta è questa:

1. una comunicazione di cancelleria, anche se contiene la parola `notificazione` perché il sistema ministeriale notifica alla PEC del difensore, è fonte dell’evento ma non è prova di notifica eseguita dall’avvocato alla controparte;
2. una sentenza o un provvedimento decisorio ricevuto via PEC/cancelleria apre sempre almeno `esame sentenza/provvedimento`;
3. se la sentenza è utile o necessaria per una notifica professionale, per far decorrere il termine breve, per presidiare adempimento, esecuzione o recupero somme, e non sono presenti relata, PEC inviata, RAC, RdAC e prova depositata, il sistema deve aprire `Valutare/preparare notifica sentenza`;
4. se sono presenti RAC e RdAC per tutti i destinatari e l’eventuale deposito della prova, il sistema deve chiudere o mostrare `prova raccolta/depositata`, mai `da notificare`;
5. il cutoff storico del 19/07/2026 vale solo per dati migrati o pratiche che l’utente ha dichiarato già gestite; non vale contro una PEC nuova, un allegato nuovo, una elaborazione nuova o una richiesta esplicita dell’avvocato di notificare un atto;
6. il termine breve di impugnazione non decorre dalla sola comunicazione della cancelleria: decorre dalla notificazione della sentenza, quando perfezionata;
7. Agenda, Scadenziario, topbar e Web Push devono leggere un presidio materializzato, non rieseguire scansioni pesanti su PEC, ZIP, OCR o 301 fascicoli durante il caricamento pagina.

## Output obbligatorio per canale

| Evento rilevato | Agenda | Scadenziario | Topbar/Web Push | Presidio fascicolo | Stato economico |
|---|---|---|---|---|---|
| Sentenza ex art. 429 già pronunciata | udienza/trattazione del giorno marcata come conclusa o decisione resa | nessun termine breve automatico; task di esame se non completato | avviso operativo “Sentenza da esaminare/valutare per notifica” | documento decisione collegato, stato `da_valutare_notifica_sentenza` se manca prova | estrarre spese, distrazione, importi e adempimenti |
| Comunicazione deposito sentenza | nessun nuovo evento udienza se non c’è udienza futura | `Esame sentenza`, non termine art. 325 automatico | avviso se P1/P0 per decisione recente | `comunicazione_ufficio`, non prova notifica | eventuale pagamento da verificare |
| PEC L. 53 inviata | nessuna udienza | monitoraggio RAC/RdAC | avviso se manca ricevuta o destinatario | `notifica_inviata_in_attesa_prova` | non applicabile |
| RAC senza RdAC | nessuna udienza | task attendere/riconciliare RdAC | avviso operativo P1/P0 se vicino o mancante | `ricevute_da_completare` | non applicabile |
| RdAC completa con RAC | nessuna udienza | nessuna nuova notifica, salvo deposito prova | notifica chiusa/archiviata | `prova_raccolta` | non applicabile |
| Deposito prova notifica | nessuna udienza | chiusura residui collegati | nessun avviso operativo pendente | `prova_depositata` | non applicabile |
| Trattazione scritta 127-ter futura | agenda come udienza cartolare | termine note/opposizione solo se l’atto lo prevede ed è ancora utile | alert se termine vicino o note mancanti | `note_127_ter_da_depositare` o `opposizione_127_ter_da_valutare` | non applicabile |
| Sentenza a verbale dopo 127-ter | chiudere la trattazione come decisione resa | rimuovere/sostituire eventuale opposizione 127-ter non più pertinente | avviso post-sentenza, non “opposizione trattazione” | `da_valutare_notifica_sentenza` se manca prova | spese/adempimenti da presidiare |

## Caso Alfano, regola specifica da codificare

Per il fascicolo `C3565650` / RG `1100/2026`:

- la PEC `pec_8d456e0fe2f268159b5510b5` è arrivata il 16/07/2026 alle 13:01 ora di Roma;
- l’oggetto ministeriale è comunicazione/notificazione di cancelleria ai sensi del D.L. 179/2012;
- l’allegato `19040620s.pdf` è una sentenza/verbale del Tribunale di Padova, resa ex art. 429 c.p.c.;
- il dispositivo contiene condanna del Ministero a costituire/accreditare Carta docente per tre annualità e spese liquidate in `€ 1.030,00` oltre 15%, IVA e CPA, con distrazione in favore del procuratore antistatario;
- nel repository PEC non risultano presidi di notifica già aperti per questa sentenza e nel fascicolo non risultano, allo stato della verifica, relata/RAC/RdAC/deposito prova della notifica della sentenza del 16/07/2026.

Conclusione: l’agenda attuale non è sufficiente se mostra solo opposizione/trattazione 127-ter. Il software deve sostituire o affiancare l’evento con:

- `Sentenza resa ex art. 429 c.p.c. da esaminare`;
- `Valutare/preparare notifica sentenza`, finché mancano prove complete;
- presidio economico per spese distratte e adempimento Carta docente;
- nessun termine breve automatico da comunicazione di cancelleria;
- nessuna chiusura per cutoff storico, perché il documento è stato ricevuto/elaborato come evento operativo nuovo e l’utente ha confermato che va notificato.

## Errori concreti riscontrati nel DB produzione sul caso Alfano

Verifica server in sola lettura del 20/07/2026 sul tenant `studio-legale-giuseppe-montagnese`:

- fascicolo corretto: `C3565650`, `Alfano Giuseppe c. MIM`, Tribunale di Padova, RG `1100/2026`;
- PEC corretta: `pec_8d456e0fe2f268159b5510b5`, ricevuta il 16/07/2026 alle 13:01 ora italiana, collegata al fascicolo con score `0,83`;
- allegato decisivo: `19040620s.pdf.zip`, contenente la sentenza/verbale ex art. 429 c.p.c.;
- allegato ministeriale: `Comunicazione.xml`, oggetto `SENTENZA A VERBALE (art. 127 ter cpc)`, con formula di notifica di cancelleria ai sensi del D.L. 179/2012.

Errori da correggere:

1. `Comunicazione.xml` è stata trattata come base di scadenza/notifica processuale dello studio, ma è solo comunicazione dell'ufficio al difensore.
2. La presenza testuale di `127-ter` ha fatto scattare `CIV_OPPOSIZIONE_127_TER`, generando nello scadenziario una voce aperta `Opposizione alla trattazione scritta ex art. 127-ter c.p.c. (5 giorni dalla comunicazione)` al `21/07/2026`.
3. Il V2 PEC ha materializzato `primary_event=udienza_online` invece di `sentenza_a_verbale` o `decisione_post_trattazione_scritta`.
4. Il sistema ha ricavato un finto orario udienza `13:01`, che in realtà è l'orario della PEC/daticert, non un'udienza da celebrare.
5. Il sistema ha ricavato un finto codice di accesso `_fiscale_destinatario`, che è un placeholder/schema, non istruzioni operative per udienza.
6. `pec_legal_notification_presidia` è vuota per la PEC/sentenza Alfano: manca il presidio `Valutare/preparare notifica sentenza`.
7. L'estrazione economica deve leggere le spese liquidate `€ 1.030,00` oltre accessori con distrazione al procuratore antistatario, senza confondere l'importo Carta docente `€ 500,00` per annualità con compensi o spese.

Regola tecnica derivata:

- prima si riconosce il contesto decisorio (`sentenza`, `SENTENZA A VERBALE`, `definitivamente decidendo`, `P.Q.M.`, `condanna`, `art. 429 c.p.c.`, `EVENTI FASE DECISORIA`);
- solo se il contesto non è decisorio si applicano le regole 127-ter per opposizione/deposito note;
- se il contesto è decisorio, le scadenze 127-ter residue devono essere completate/sostituite come falsi positivi, non lasciate aperte;
- il presidio corretto è post-sentenza: esame, eventuale notifica sentenza, ricevute/prova, economia fascicolo e adempimento.

## Ampliamento della visione professionale: ragionare per fascicolo, non per parole chiave

Aggiornamento: 20/07/2026, dopo richiesta espressa dell'utente di impostare la logica come farebbe un avvocato.

Il motore non deve limitarsi a classificare il documento. Per ogni PEC, atto o provvedimento deve ricostruire, con evidenza consultabile, queste domande operative:

1. **Chi assistiamo e in quale posizione?** Ricorrente, resistente, creditore, debitore, appellante, appellato, imputato, parte civile, amministrazione o terzo. La stessa sentenza può richiedere notifica, impugnazione, adempimento o sola vigilanza a seconda della posizione.
2. **In quale rito e fase ci troviamo?** Civile ordinario, lavoro, scuola/pubblico impiego, esecuzione, cautelare, monitorio, amministrativo/PAT, penale/PDP, tributario/PTT o altra procedura speciale. Non sono trasferibili automaticamente termini e meccanismi tra riti diversi.
3. **Che cosa è arrivato davvero?** Avviso di cancelleria, sentenza, verbale, decreto, ordinanza, atto avversario, PEC L. 53/1994 inviata dallo studio, RAC, RdAC, avviso di mancata consegna, ricevuta PCT, prova già depositata, documento proveniente da portale.
4. **Quale effetto ha già prodotto?** Decisione, fissazione/rinvio, ordine di deposito o esibizione, apertura di un termine, esecutività, obbligo di adempimento, prova di notifica, semplice conoscenza legale o nessun effetto ancora verificabile.
5. **Che cosa manca per agire in sicurezza?** Destinatario corretto, domicilio digitale tratto da elenco, procura, relata, firma, atto conforme, ricevuta completa, prova del deposito, data certa di comunicazione/notifica, autorizzazione o scelta professionale dell'avvocato.
6. **Quali sono le quattro date da distinguere?** Data del provvedimento; deposito/pubblicazione; comunicazione di cancelleria; perfezionamento della notifica di parte. L'Agenda mostra tutte quelle utili, mentre lo Scadenziario calcola soltanto la data prevista dalla regola applicabile e con la prova richiesta.

Questa struttura impedisce gli errori più gravi: sentenza scambiata per udienza, comunicazione di cancelleria scambiata per notifica L. 53, termine breve creato senza prova, ricezione PEC trattata come orario di udienza, oppure atto già notificato riaperto senza motivo.

## Gerarchia delle fonti e criterio per il cervello giuridico

Ogni regola del motore deve avere un record di conoscenza con: `fonte`, `articolo`, `versione/data di consultazione`, `rito`, `fatto generatore`, `dies a quo`, `durata`, `natura del termine`, `prova necessaria`, `eccezioni`, `azione software`, `confidenza` e `revisione umana richiesta`.

Ordine inderogabile delle fonti:

1. testo vigente di legge/codice e norme transitorie da Gazzetta Ufficiale o Normattiva;
2. atti e specifiche ufficiali del Ministero, PST, DGSIA, Giustizia Amministrativa, PDP/PTT o altro portale competente;
3. giurisprudenza ufficiale di Cassazione, Corte costituzionale, CGUE/Curia e, quando rilevante, provvedimento dell'ufficio;
4. Guide Pratiche IUSENTRA, studi legali e repertori professionali, solo come radar per scoprire fattispecie, checklist, documenti e rischi;
5. se una fonte non consente una conclusione certa, suggerimento professionale `da verificare`, mai automatismo perentorio.

Esempio applicato ad Alfano: gli artt. 133, 285, 325, 326 e 327 c.p.c. distinguono comunicazione, notificazione e termini di impugnazione; gli artt. 429-433 c.p.c. qualificano il rito lavoro e la sentenza; l'art. 1, comma 121, L. 107/2015 e il D.P.C.M. 28 novembre 2016 spiegano l'adempimento Carta docente; la scheda PST L. 53/1994 definisce relata, RAC e RdAC. Perciò il software può proporre una notifica della sentenza da valutare, ma non dichiararla eseguita né far decorrere il termine breve dalla sola comunicazione dell'ufficio.

## Guide Pratiche: utilizzo corretto come radar interno dei casi

Le Guide Pratiche già presenti in IUSENTRA vengono usate per ampliare la copertura dei possibili scenari, ma non sostituiscono una norma né autorizzano automatismi arbitrari.

- La base interna contiene guide curate per il catalogo PST/XSD, migliaia di termini e template calcolabili; il servizio è caricato una volta per processo e resta in sola lettura, quindi non aggiunge scansioni al caricamento della pagina.
- La consultazione ha individuato percorsi per opposizione a precetto (art. 615 c.p.c.), opposizione a decreto ingiuntivo (art. 645 c.p.c.), opposizione agli atti esecutivi (art. 617 c.p.c.), reclamo cautelare, appello civile, sospensione dell'esecutività, revocazione/correzione della sentenza, lavoro e previdenza, notificazioni civili/PEC, procedimenti amministrativi e costituzione di parte civile penale.
- Le guide aiutano a collegare decreto ingiuntivo e notifica; titolo e precetto; opposizione sostanziale o formale; rinvio, udienza, note e produzioni; sentenza, impugnazione, esecuzione e adempimento.
- Ogni termine o regola tratto dalla Guida entra nel motore automatico soltanto dopo verifica della fonte primaria e della disciplina transitoria. Finché tale verifica non è presente, resta un suggerimento `da verificare`, mai una scadenza perentoria calcolata in modo autonomo.
- Il codice oggetto della Guida resta distinto dal codice ministeriale del fascicolo: la Guida arricchisce il ragionamento e non cambia rito, registro o canale di deposito.

Fonti interne consultate: `docs/GUIDA_PRATICA_PIANO_OPERATIVO.md`, `pct/guida_pratica/service.py`, `artifacts/guida-pratica/IMPLEMENTATION_AUDIT.md` e moduli KB collegati. La Guida Pratica è un inventario professionale di situazioni e controlli; Gazzetta Ufficiale, Ministero, PST, Curia, Cassazione o fonte processuale ufficiale restano la base per le regole esecutive.

## Matrice ampliata per canale e fase

| Canale/fase | Cosa il software deve riconoscere | Presidio corretto | Regola prudenziale |
|---|---|---|---|
| Civile ordinario | citazione/ricorso, memorie, ordinanze, rinvii, sentenze, impugnazioni | Agenda per udienze, Scadenziario per termini assegnati, esame del provvedimento | la sola PEC di cancelleria non prova una notifica di parte |
| Lavoro e scuola | rito lavoro, art. 429, condanne provvisorie, Carta docente, spese distratte, appello lavoro | esame sentenza, adempimento del datore/Ministero, notifica da valutare, monitoraggio economico | esecutorietà provvisoria e giudicato sono stati diversi |
| Decreto ingiuntivo | ricorso/decreto, provvisoria esecuzione, notifica, opposizione, inefficacia | notifica del decreto per il creditore; opposizione per il debitore; prova notifica | nessuna chiusura senza identificare il lato assistito e la prova dell'invio/consegna |
| Cautelare | ricorso urgente, ordinanza concessiva/negativa, reclamo, attuazione | priorità alta, termine solo dalla fonte corretta, controllo esecuzione | il reclamo non va confuso con appello o con termine civile ordinario |
| Esecuzione | titolo, notifica titolo, precetto, pignoramento, opposizioni, rinvii GE | checklist titolo/precetto/prove, termini esecutivi, Agenda GE | non dichiarare eseguibile il flusso se titolo o precetto non risultano notificati quando richiesto |
| Amministrativo/PAT | ricorso, notifica, deposito, memorie, udienza pubblica/camerale, rito accelerato | canale `amministrativo_pat`, Agenda/Scadenziario dedicati e controllo deposito | non applicare le regole L. 53/c.p.c. senza ruleset PAT verificato |
| Penale/PDP | avvisi, deposito sentenza, impugnazione, notificazioni, parte civile | canale `penale_pdp`, revisione con regole c.p.p. e prova di deposito | il motore civile non deve generare termini penali né viceversa |
| Tributario/PTT | atti impositivi, ricorsi, reclami/mediazione, udienze, sentenze | canale `tributario_ptt`, revisione e regole speciali | nessuna assimilazione automatica a civile o PAT |

## Catena di prova della notifica: stati da rendere leggibili all'avvocato

`documento/decisione da esaminare` → `scelta o ordine di notificare` → `atto e destinatari verificati` → `relata pronta e firmata` → `PEC inviata` → `RAC acquisita` → `RdAC completa acquisita` → `prova collegata/depositata`.

- L'avviso ministeriale di comunicazione e il suo XML sono prova della comunicazione dell'ufficio, non un anello di questa catena per la notifica dell'avvocato.
- Una RAC da sola mantiene il presidio aperto: attesta il perfezionamento per il notificante, ma non dimostra ancora la consegna al destinatario.
- RdAC completa, riferita al medesimo messaggio/atto/destinatario, consente lo stato `prova raccolta`; il deposito della prova nel fascicolo/atto successivo produce `prova depositata` quando richiesto dal flusso.
- Mancata consegna, rifiuto o anomalia non producono una falsa chiusura: aprono un presidio urgente per determinare se occorra nuovo canale o altra attività conforme.

La fonte tecnica ufficiale per la notifica PEC in proprio è la scheda del Portale dei Servizi Telematici del Ministero della Giustizia sulla L. 53/1994: oggetto legale, relata separata firmata, allegati, ricevuta completa, RAC e RdAC. Il materiale professionale esterno, incluso AvvocatoAndreani, è usato solo per individuare casi e checklist da verificare; non è mai la sola base di una regola automatica.

## Fonti ufficiali e fonti-radar da mantenere nella memoria del progetto

- Codice di procedura civile: artt. 133, 285, 324-327, 127-bis, 127-ter, 171-bis, 171-ter, 210, 421, 429-433, 479-481, 615, 617, 641-645 e 669-terdecies; testi vigenti e relative disposizioni transitorie da Gazzetta Ufficiale/Normattiva.
- Processo amministrativo: D.Lgs. 104/2010, con routing separato per termini e depositi PAT; testo ufficiale da Gazzetta Ufficiale e portale Giustizia Amministrativa.
- Processo penale: c.p.p. artt. 148, 548 e 585 e regole PDP; il canale resta separato e non può ereditare gli automatismi civili.
- Scuola/Carta docente: art. 1, comma 121, L. 107/2015; D.P.C.M. 28 novembre 2016; ordinanza CGUE 18/05/2022, C-450/21; Cass. lav. n. 29961/2023 e successivi orientamenti ufficiali. Nel caso Alfano questi riferimenti spiegano il contenuto della condanna, non sostituiscono la verifica dell'adempimento concreto del MIM.
- Radar professionale: Guide Pratiche IUSENTRA, AvvocatoAndreani e altri materiali di studio servono a scoprire varianti operative, documenti, prove e rischi. Ogni norma o termine che passa da radar a regola deve registrare fonte, data di consultazione, ambito, versione e comportamento prudente.

## Requisiti anti-prestazione negativa

- La UI React `/notifiche-legali`, la topbar e i fascicoli devono leggere tabelle/proiezioni già materializzate.
- Il ricalcolo su PEC, ZIP, OCR, PDF e 301 fascicoli deve avvenire in job o script incrementale, con batch e marker di ripresa.
- L’audit completo Montagnese può essere eseguito come procedura server, ma non deve diventare parte del caricamento pagina.
- Ogni query di lista deve essere paginata e indicizzata per `tenant_id`, `status`, `fascicolo_id`, `source_message_id`, `updated_at`.
- La verifica finale deve riportare tempi medi/massimi di audit e confermare che la pagina non scansiona fascicoli o PEC all’apertura.

## Consolidamento 21/07/2026 - logica tecnica prima del codice

La logica operativa del presidio non è più una somma di pattern testuali. Il software deve ragionare come una state machine probatoria:

1. **fonte dell'evento**: PEC di cancelleria, `Comunicazione.xml`, allegato PDF/ZIP, PST/PolisWeb o documento già nel fascicolo;
2. **qualificazione giuridica**: comunicazione, udienza/trattazione, termine, sentenza/provvedimento decisorio, ordine di notifica, notifica L. 53 inviata, ricevuta, mancata consegna o deposito prova;
3. **effetto operativo**: Agenda, Scadenziario, Presidio notifiche, topbar/Web Push, economia fascicolo, adempimento o sola archiviazione;
4. **prova necessaria**: documento, relata, destinatario, PEC inviata dal PC locale, RAC, RdAC completa per ogni destinatario e prova collegata/depositata;
5. **stato conclusivo**: il presidio si chiude solo se la prova richiesta per quello scenario è completa o se l'avvocato dichiara motivatamente che l'atto non va notificato.

Regola anti-falso-verde:

- una PEC dell'ufficio giudiziario è conoscenza/comunicazione dell'evento, non notifica professionale dell'avvocato;
- `Comunicazione.xml` non è relata;
- RAC senza RdAC non prova la consegna al destinatario;
- RdAC non coerente per messaggio, destinatario o allegati non chiude la catena;
- lo stato `NOTIFICATION_CONFIRMED` significa solo che la necessità di notifica è stata confermata dall'operatore, non che la notifica sia materialmente eseguita;
- il testo visibile deve quindi dire `Notifica necessaria confermata` e proporre `Verifica destinatari e prepara relata`, non formule come `notifica eseguita` o `notificato` se mancano ricevute/prova.

Fonti ufficiali controllate in questa ripresa:

- Gazzetta Ufficiale, Codice di procedura civile, art. 133: la comunicazione del deposito della sentenza non fa decorrere i termini brevi ex art. 325;
- Gazzetta Ufficiale, Codice di procedura civile, art. 285: la notificazione della sentenza per il termine d'impugnazione è atto di parte;
- Gazzetta Ufficiale, Codice di procedura civile, artt. 325 e 326: termini brevi e decorrenza dalla notificazione/perfezionamento;
- Gazzetta Ufficiale, Codice di procedura civile, art. 429: nel rito lavoro la decisione resa in udienza è sentenza e prevale sulla precedente modalità cartolare;
- Portale Servizi Telematici del Ministero della Giustizia, scheda notificazioni L. 53/1994: oggetto PEC, relata separata firmata, allegati, ricevuta completa, RAC/RdAC e deposito delle ricevute;
- Specifiche tecniche DGSIA/PST: comunicazioni/notificazioni telematiche dell'ufficio e distinzione tra ricevuta breve per comunicazioni e ricevuta completa per notificazioni.

Regola specifica server Montagnese:

- i residui storici ante cutoff possono essere riconciliati solo se appartengono a segnali già gestiti o provati;
- il cutoff del 19/07/2026 non chiude automaticamente eventi vivi ricevuti/elaborati come sentenze da esaminare;
- il caso Alfano, PEC `pec_8d456e0fe2f268159b5510b5`, resta `judgment_to_notify_review` perché la sentenza ex art. 429 è fonte di valutazione/notifica e nel fascicolo non risulta prova completa post-sorgente;
- i 5 presìdi attivi Montagnese devono restare l'unica coda operativa pubblicata in Presidio notifiche, Scadenziario, topbar e Web Push finché non emergono nuove PEC/prove.

## Ripristino fonte SQL e regola anti-archivio pesante - 21/07/2026

Il presidio può essere considerato giuridicamente affidabile solo se la fonte tecnica è coerente. Il 21/07/2026 sul server Montagnese il file `studio.db` è risultato materialmente non SQLite: conteneva JSON dello Scadenziario e aveva un WAL storico di circa `15,2 GB`. In tale stato qualunque presidio sarebbe stato un falso verde tecnico, perché la fonte di verità dichiarata non era leggibile come database.

Decisione tecnica:

- `studio.db` deve contenere il dominio core strutturato: fascicoli, clienti, soggetti, parti, agenda, scadenze, utenti, audit, messaggi, preventivi, fatturazione, impostazioni e mirror JSON core;
- OCR, PDF, ZIP, `documenti_ai/**/extracted_text.json`, indici di ricerca e repository dedicati non devono essere copiati dentro `studio.db`; restano archivi verticali o rigenerabili, con job indicizzati;
- una cache JSON non può mai leggere o scrivere su `.db`, `.sqlite` o `.sqlite3`; se accade, il sistema deve bloccare con errore esplicito invece di creare un database finto;
- il caricamento UI deve interrogare tabelle/proiezioni leggere e già materializzate, mai lanciare scansioni sui 301/302 fascicoli o sugli allegati.

Ripristino eseguito:

- stage core esplicito da JSON tenant-aware Montagnese, `54 MB`, `PRAGMA quick_check=ok`;
- installazione come nuovo `studio.db` dopo stop breve di app e scheduler;
- vecchi `studio.db`, `studio.db-wal`, `studio.db-shm` preservati in backup forense;
- WAL del nuovo database troncato a freddo e poi stabile a dimensione ordinaria;
- guardrail codice in `pct/cache.py` e test in `tests/test_cache_security.py`.

Effetto sulla logica notifiche: il presidio notifica deve essere ricalcolato e verificato dal nuovo SQLite valido prima di ogni dichiarazione finale. I conteggi pre-ripristino restano utili come indizio storico, ma non sono prova conclusiva finché non vengono confermati sulla fonte SQL riparata.
