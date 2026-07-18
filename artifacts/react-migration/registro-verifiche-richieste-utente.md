# Registro permanente delle richieste e delle verifiche

Aggiornato il 18/07/2026. Questo file è il registro operativo vincolante delle revisioni richieste dall'utente e la memoria principale del lavoro ancora da completare.

## Regola di gestione

- Ogni nuova segnalazione viene aggiunta prima di modificare il codice.
- `[ ]` significa che la richiesta non è ancora stata verificata integralmente sul server reale.
- `[~]` significa che l'implementazione o la diagnosi è in corso.
- `[x]` si usa soltanto dopo prova materiale su `https://app.iusentra.it`, con click reale, scroll completo e risultato osservato.
- Test automatici, build e typecheck non autorizzano da soli il passaggio a `[x]`.
- Per ogni voce chiusa vanno annotati data, route, dato reale usato ed esito visibile.
- Ogni nuova richiesta, decisione di flusso, confronto con fonti, difetto osservato o prova reale aggiorna questo registro prima del report finale; le informazioni non devono restare soltanto nella conversazione.
- Le analisi estese possono vivere in dossier dedicati, ma devono essere collegate qui e mantenere separati: requisito, implementazione, test automatico, prova reale server, prova reale locale e stato di rilascio.

## Memorie collegate

- `artifacts/react-migration/confronto-documenti-fascicolo-ufficio.md`: consultazione e acquisizione dei documenti del fascicolo d'ufficio, gerarchia documento/allegati, copia/originale, deduplicazione e collaudo.
- `artifacts/react-migration/procedura-deposito-telematico.md`: deposito, firma, busta, PEC locale, ricevute, notifiche legali e verifiche operative sensibili.
- `artifacts/data-flow/incarico-operativo-permanente.md`: tenant, fonte dati SQL, API, React, persistenza e doppio controllo della struttura dati.

## Interventi attivi del 15/07/2026

- [~] `UI-001` Ripristinare il layout leggibile e responsive di `Strumenti Operativi`.
  Accettazione: griglia a larghezza piena, nessuna colonna compressa, nessuna sovrapposizione, click reali sui collegamenti, desktop 2196 px e notebook 1366 px.
- [~] `UI-002` Applicare la stessa correzione a `Strumenti Forensi` mantenendo la grafica coerente con IUSENTRA.
  Accettazione: stessi controlli di `UI-001` sulla route reale di Strumenti Forensi.
- [~] `AG-001` Correggere `Segna completato`: conferma JSON, aggiornamento reale, ricaricamento e sostituzione del comando con `Attività completata`.
  Accettazione: click reale su un'attività non completata, stato persistito, colore completato, pulsante non più presente dopo il salvataggio.
- [~] `AG-002` Compilare automaticamente cliente/parte dell'Agenda dal fascicolo quando ID o RG sono già noti.
  Accettazione: l'evento `RG 771/2025` mostra il cliente reale e non `Da collegare`.
- [~] `PEC-001` Allineare l'altezza del pannello di lettura PEC alla colonna messaggi mantenendo scroll indipendente.
  Accettazione: stessa estensione visiva delle due colonne su desktop e nessuna regressione nel lettore mobile.
- [~] `PEC-002` Leggere automaticamente il PDF contenuto negli allegati `.pdf.zip`, estrarre link e istruzioni audiovisive, verificarli e riportarli in PEC, Agenda e Scadenziario.
  Accettazione: il caso reale `21866865s.pdf.zip` mostra link cliccabile, fonte, orario e stato di verifica; nessun messaggio generico se il PDF è disponibile.
- [~] `PEC-003` Aprire automaticamente il documento leggibile contenuto negli ZIP PEC senza chiedere all'avvocato di estrarre manualmente l'archivio.
  Accettazione: il click sull'allegato `.pdf.zip` mostra direttamente il PDF interno nel visualizzatore IUSENTRA; il download conserva lo ZIP originale e gli archivi non sicuri vengono bloccati con un messaggio chiaro.
- [~] `DEPLOY-001` Distribuire gli interventi attivi sul server e provare ogni route con browser reale.

## Agenda e Scadenziario

- [~] `AG-003` Visualizzare la fonte PDF/PEC dentro IUSENTRA in una finestra sopra Agenda e Scadenziario, senza sostituire o incorporare il documento nel contenuto della pagina; usare il visualizzatore mobile con zoom.
  Accettazione: `Visualizza fonte` apre lo stesso pannello sovrapposto su entrambe le route, mantiene data, vista e filtri sottostanti e si chiude con pulsante, sfondo o tasto Esc.
- [x] `AG-004` Mostrare nel passaggio del mouse dati completi e immediatamente comprensibili: cliente, RG, ufficio, evento, data, ora, modalità e link udienza.
- [x] `AG-005` Rendere il link dell'udienza audiovisiva cliccabile e verificato nella scheda Agenda e nello Scadenziario.
- [ ] `AG-006` Assegnare colori distinti per udienza, scadenza/deposito, appuntamento, attività di studio e completata; il completamento deve essere riconoscibile subito.
- [ ] `AG-007` Inserire la legenda colori nel titolo della vista calendario senza sottrarre spazio utile.
- [~] `AG-008` Gestire eventi uguali o ravvicinati senza sovrapposizioni o colonne illeggibili, compresi i casi reali del 14 e 20 luglio.
  Accettazione: ogni fascia occupata mostra un solo riepilogo leggibile; il passaggio del mouse elenca separatamente orario, titolo e azioni di ciascun evento.
- [ ] `AG-009` Espandere il planner a tutto schermo e verificarlo anche su notebook da 14 pollici e mobile.
- [ ] `AG-010` Evitare `n.d.` quando documenti o PEC contengono una prossima udienza/scadenza; mantenere `n.d.` solo se l'evento non esiste realmente.
- [x] `AG-011` Ogni evento automatico deve avere un'azione `Visualizza fonte` che apra il documento o la PEC originaria.
- [~] `AG-012` Le attività `UDIENZA` devono restare nella timeline del fascicolo e alimentare Agenda, Scadenziario, notifiche operative e Web Push senza perdere note, modalità o link audiovisivo.
  Accettazione: un solo record per evento; il collegamento appare nell'app; il Web Push espone l'azione esterna solo dopo validazione; un allegato PDF/ZIP elaborato successivamente aggiorna la stessa notifica e invia un nuovo push soltanto quando aggiunge un'informazione audiovisiva utile.
- [~] `AG-013` Aprire il dettaglio operativo di eventi e scadenze in una finestra sopra Agenda e Scadenziario, senza incorporarlo nel flusso della pagina.
  Accettazione: il click su un evento Agenda o su una scadenza mantiene calendario, elenco, data e filtri sullo sfondo; il dettaglio conserva tutte le azioni e si chiude con pulsante, sfondo o tasto Esc. La route diretta con identificativo apre la stessa finestra.
- [~] `PEC-004` Risolvere la fonte collegata anche quando la PEC è conservata nel presidio documentale e non compare nella sola casella email.
  Accettazione: il caso reale `21866865s.pdf.zip` apre il PDF interno dalla fonte PEC registrata, senza il messaggio “PEC collegata non disponibile”, mantenendo lo ZIP originale per il download.

## PEC, documenti e intelligenza del fascicolo

- [ ] `DOC-001` Ogni PEC e documento deve avere hash persistente: un contenuto già letto non viene riletto, un contenuto nuovo viene sempre acquisito.
- [ ] `DOC-002` Avviare automaticamente classificazione ed estrazione quando arriva una PEC, viene caricato un documento o viene scaricato un fascicolo con nuovi documenti.
- [ ] `DOC-003` Leggere PDF testuali, scansioni, P7M, EML/MSG, ZIP e ZIP annidati senza tralasciare allegati sicuri.
- [ ] `DOC-004` Estrarre in autonomia decreti di fissazione/rinvio udienza, contributo unificato/esenzione, liquidazioni del giudice, modalità in presenza/da remoto, link, orari e istruzioni.
- [ ] `DOC-005` Salvare per ogni informazione estratta la prova documentale, il documento sorgente e il collegamento visualizzabile.
- [ ] `DOC-006` Valutare MinerU come secondo motore documentale/OCR, con confronto qualità, tempi, requisiti e integrazione governata; nessun motore esterno deve sostituire la fonte documentale.
- [ ] `DOC-007` Completare il presidio automatico su tutti i documenti dei fascicoli reali dello studio, senza riletture inutili.

## Ciclo operativo legale

- [ ] `FLOW-001` Modellare e aggiornare automaticamente il ciclo: ricorso, deposito, accettazione/consegna, assegnazione RG, nomina giudice, decreto, acquisizione PST, notifica, ricevute e attività successive.
- [ ] `FLOW-002` Ricostruire dalle relate e dalle PEC ciò che è già stato notificato, a chi e quando, con ricevute di accettazione e consegna.
- [ ] `FLOW-003` Mostrare per ogni fascicolo cosa resta da notificare, senza deduzioni non supportate da una fonte.
- [ ] `FLOW-004` Aggiungere alle attività quotidiane dell'avvocato il controllo degli atti da notificare.
- [ ] `FLOW-005` Proseguire il flusso fino a sentenza, liquidazione, controllo economico, proforma confermata dall'avvocato e successiva fattura.

## Deposito telematico

- [ ] `DEP-001` Confrontare campo per campo generatori, documenti richiesti, busta, indice, firma, PEC ufficio, codici ufficio, invio e ricevute con fonti ministeriali e logica verificata del software di riferimento.
- [ ] `DEP-002` Coprire ogni tipo di deposito previsto dalle tabelle ministeriali; l'audit deve fallire su mappature, regole o generatori mancanti.
- [ ] `DEP-003` Lasciare all'avvocato la scelta dei documenti da inviare e della classificazione; il software propone ma non seleziona tutto automaticamente.
- [ ] `DEP-004` Bloccare solo requisiti ministeriali essenziali e indicare con precisione il campo mancante con inserimento rapido nello stesso flusso.
- [ ] `DEP-005` Abilitare invio reale soltanto dopo simulazione positiva, firme, indice, busta, destinatario e testo verificati; ogni blocco residuo deve essere nominato.
- [ ] `DEP-006` Aggiornare un fascicolo già esistente durante ricerca/scarico PST senza creare duplicati.
- [ ] `DEP-007` Verificare tutte le tabelle e tutti i registri per ricerca e scarico fascicoli, oltre ai casi civile, lavoro e giudice di pace già provati.

## Acquisizione PST

- [~] `PST-001` Riutilizzare l'autenticazione del dispositivo nella stessa sessione: un solo inserimento PIN per consultare e un solo inserimento PIN per scaricare, senza richieste ripetute per anteprima o analisi.
  Accettazione: prova reale completa sullo stesso fascicolo o su un caso controllato; conteggio visibile di una richiesta PIN in consultazione e una nello scaricamento.
- [~] `PST-002` Al termine di tutti i download completare automaticamente registrazione e apertura del fascicolo, senza restare sullo Step 7 con comando disabilitato.
  Accettazione: a `N/N` il software crea o aggiorna la pratica, apre direttamente il fascicolo corretto e mostra documenti ed eventi acquisiti.
- [~] `PST-003` Ridurre i passaggi e i tempi dell'acquisizione confrontando il flusso operativo con il software di riferimento, senza duplicare ricerca, diagnostica o letture già concluse.
  Accettazione: log cronologico con durata dei passaggi, nessuna chiamata ridondante e confronto documentato; nessun riferimento tecnico al confronto nella UI.
- [~] `PST-004` Verificare l'acquisizione reale `RG 771/2025`, Tribunale di Palmi: una sola pratica, cliente `Mandaglio Daniela`, 46 documenti, 5 eventi e agenda riallineata.
  Accettazione: controllo reale su elenco, dettaglio fascicolo, documenti e evento agenda `642D3DB8`.
- [~] `PST-005` Riconoscere automaticamente il primo documento di cancelleria successivo al deposito, prima dalla PEC e poi dalla copia ufficiale scaricata dal portale, aggiornando il fascicolo senza duplicare dati o documenti.
  Accettazione: sul caso reale `Documento_30446614.pdf` il software acquisisce RG, ufficio, sezione, giudice, oggetto, ricorrente, difensore, controparti, esenzione dal contributo unificato e prima udienza; la copia PST viene ricongiunta alla precedente evidenza PEC tramite impronta e riferimenti del procedimento; una seconda elaborazione non rilegge il contenuto invariato.

## Notifiche legali

- [ ] `NOT-001` Rendere il percorso rapido e intuitivo, con firma relata tramite Local Signer e sola approvazione finale manuale dell'avvocato.
- [ ] `NOT-002` Verificare automaticamente avvocato, PEC notificante, PEC destinatario su pubblico elenco, allegati e relata; mostrare soltanto blocchi reali.
- [ ] `NOT-003` Generare una sola attestazione di conformità per tutti i documenti allegati, con formattazione identica al modello fornito e campi automatici.
- [ ] `NOT-004` Inserire automaticamente CAP, città e provincia dello studio nella relata e consentire valori configurabili, non fissati nel codice.
- [ ] `NOT-005` Ricerca pratiche completa e ricercabile nella pagina notifiche; pulsante `Notifica` nel fascicolo.
- [ ] `NOT-006` Verificare firma reale della relata con dispositivo locale senza invio PEC reale.

## Local Signer

- [ ] `SIGN-001` Portare in primo piano la richiesta PIN senza lasciarla incastrata nella barra di Windows.
- [ ] `SIGN-002` Aggiornamento automatico completo: download, installazione, avvio e verifica versione.
- [ ] `SIGN-003` Impedire servizi duplicati o processi Local Signer appesi.
- [ ] `SIGN-004` Verificare firma singola e multipla, salvataggio dei `.p7m` e prosecuzione del flusso senza invii reali.

## Fatturazione e proforma

- [ ] `FATT-001` Correggere salvataggio, modifica e visualizzazione proforma; `Genera proforma` deve creare e aprire il documento.
- [ ] `FATT-002` Usare esclusivamente i dati del tenant/studio corrente, mai quelli di un altro studio.
- [ ] `FATT-003` Impostazioni fiscali predefinite: regime, spese generali, Cassa Forense, IVA con aliquota, ritenuta, bollo, pagamento e scadenza.
- [ ] `FATT-004` CAP studio automatico dal comune e riuso ovunque, incluso timbro e documenti.
- [ ] `FATT-005` IBAN, banca, beneficiario e BIC/SWIFT nei Dati Studio e compilazione automatica nelle proforme.
- [ ] `FATT-006` Aggiornare le proforme in bozza con i nuovi default, senza modificare fatture emesse o trasmesse.

## Regole trasversali

- [ ] `QA-001` Audit reale con click su tutti i pulsanti delle superfici modificate; nessun pulsante fittizio.
- [ ] `QA-002` Verifica responsive desktop, notebook 14 pollici, tablet e mobile, inclusi hover, focus, loading, errore e successo.
- [ ] `QA-003` Coerenza grafica con IUSENTRA e nessun testo tecnico o riferimento al software di confronto nella UI.
- [ ] `QA-004` Italiano UTF-8, date e orari italiani, importi nel formato `€ 1.234,56`.
- [ ] `QA-005` Ogni chiusura deve riportare route, click, risultato osservato, test automatici e commit distribuito.

## Evidenze di chiusura

Nessuna delle voci attive del 15/07/2026 viene ancora dichiarata chiusa: sono in implementazione o attendono la prova materiale sul server dopo il deploy.

## Evidenze intermedie del 15/07/2026

- `UI-001` Strumenti Operativi, produzione `https://app.iusentra.it/strumenti-operativi`: eliminata la collisione tra il contenitore della pagina e le schede della pagina Studio. Verifica reale desktop 2196 x 1058: griglia a tre colonne larga 1.857 px, pannello principale largo 1.892 px, nessuna colonna compressa. Click reale su `Timesheet`, apertura osservata di `/timesheet` con titolo, filtri e dati del tenant. Resta da eseguire la prova materiale a 1366 px prima del passaggio a `[x]`.
- `UI-002` Strumenti Forensi, produzione `https://app.iusentra.it/strumenti-legali/`: stessa correzione applicata e verificata. Click reale su `Uffici competenti`, pannello operativo aperto a tutta larghezza; ricerca reale `Taurianova` completata con 9 schede operative e 18 risultati complessivi. Resta da eseguire la prova materiale a 1366 px prima del passaggio a `[x]`.
- `PST-005` Automazione post-deposito implementata e verificata sui dati reali di `Documento_30446614.pdf`: estratti RG `771/2025`, Tribunale di Palmi, sezione `01`, giudice Gabutti Carlo, oggetto, parti, avvocato, esenzione e prima udienza. Il job incrementale aggiorna una volta sola il fascicolo coerente e il test impedisce materialmente una seconda lettura del documento invariato. Restano da eseguire la prova visibile locale e la verifica sul server prima del passaggio a `[x]`.

## Evidenze intermedie del 16/07/2026 - notifica e firma

- `NOT-001`, `NOT-002` e `NOT-006` restano `[~]`: il flusso usa un unico campo PIN accanto a `Firma relata`; il PIN rimane sul PC, viene cancellato dallo stato React dopo l'operazione e viene riusato nella stessa azione per verifica dei pubblici elenchi e firma digitale. L'approvazione finale dell'avvocato resta separata e manuale.
- La verifica ReGIndE interroga il servizio ufficiale per indirizzo PEC, conserva le evidenze restituite e gestisce più indirizzi o ruoli. Il codice fiscale del notificante non viene mai corretto automaticamente; quello del destinatario può essere riallineato soltanto quando la risposta autorevole del registro corrisponde alla PEC cercata e la richiesta proviene dal controllo destinatario.
- Il Local Signer `1.6.92` è installato sul PC reale, risponde su `127.0.0.1:27272`, rileva il dispositivo CNS e dispone di certificati distinti per autenticazione e firma. È presente un solo processo in ascolto sulla porta del servizio.
- La copia Docker reale locale è stata ricostruita e ricreata; `http://127.0.0.1:8080/api/pronto` risponde `ok=true`, versione `2.256.1`, fuso `Europe/Rome`, container `iusentra-app` healthy.
- Produzione aggiornata senza invii: un solo container applicativo `iusentra-app`, healthy, e `https://app.iusentra.it/api/pronto` positivo. Non è stato eseguito alcun invio PEC reale.
- Guardrail superati: `314` test mirati su notifiche legali, Local Signer e conservazione asset React; typecheck e build Vite; budget massimo `500.000` byte rispettato. Il chunk JavaScript più grande è circa `369` kB e quello della pagina Notifiche legali circa `133` kB.
- La prova crittografica con click reale nella scheda autenticata, inserimento PIN, creazione della relata firmata, salvataggio nel fascicolo e visualizzazione del file firmato non viene marcata `[x]` in questo verbale finché non è osservata materialmente nel browser reale. I test automatici e il rilevamento del token non sostituiscono questa prova.

## Evidenze intermedie del 16/07/2026 - udienze audiovisive

- `AG-012` è implementato a livello codice: `UDIENZA` non è più esclusa dalla timeline del fascicolo; descrizione e note restano disponibili e gli URL riconosciuti sono cliccabili.
- Agenda e Scadenziario ricevono gli stessi campi strutturati `remote_hearing_*`; la notifica operativa porta al dettaglio corretto e propone il collegamento audiovisivo come azione secondaria.
- Il Web Push resta privo di dati della pratica. Se il link è verificato espone l'azione `Collegati`; se non è verificato apre soltanto IUSENTRA per il controllo.
- L'elaborazione incrementale non duplica il record: se un PDF o ZIP successivo aggiunge il collegamento o ne completa la verifica, la stessa notifica viene aggiornata, torna non letta e genera un solo nuovo push per l'arricchimento. Una ripetizione identica non produce altri push.
- Guardrail eseguiti: `20` test notifiche/push, `3` test integrazione PEC, `7` test comprensione udienze, `16` test Scadenziario React, `2` test timeline fascicolo, contratto React, route PWA/service worker e integrità UTF-8.
- Prova reale locale del 17/07/2026 su `127.0.0.1:8080`: evento controllato alle `16:45` collocato nella fascia corretta; passaggio del mouse con cliente, RG, ufficio, modalità, link Teams e fonte; click `Visualizza fonte` con PDF aperto nel modal interno; stessa informazione nello Scadenziario desktop e mobile, senza duplicati né overflow.
- Runtime Web Push verificato sul browser reale: configurazione e feature abilitate, service worker servito, azioni `Apri Agenda` e `Collegati` presenti e lettura del campo `remoteHearingUrl` confermata. La consegna della notifica al sistema operativo resta dipendente da un browser con permesso concesso e sottoscrizione attiva, quindi `AG-012` resta `[~]` fino a quella prova materiale.
- Evidenza completa: `artifacts/react-migration/pec-agenda-scadenziario-visual-audit.json`, con `failures=[]` e `consoleErrors=[]`.

## Evidenze tecniche del 17/07/2026 - catena completa udienza

- `AG-012` usa ora un unico contratto strutturato dalla PEC al fascicolo: modalità, data, ora, piattaforma, ID riunione, codice di accesso, istruzioni, fonte, stato di verifica e URL audiovisivo vengono conservati in Scadenziario e Agenda e riutilizzati dalle API React.
- Il filtro della timeline esclude soltanto le comunicazioni di cancelleria già rappresentate nella sezione dedicata. Le attività `UDIENZA` restano visibili; descrizione e note vengono mantenute e gli URL presenti sono resi cliccabili.
- Due udienze nella stessa data non vengono più accorpate soltanto per tipo e giorno: l'identità considera appuntamento, documento, deposito o titolo dell'evento.
- Centro notifiche e Web Push ricevono lo stesso payload. L'azione `Collegati` viene aggiunta esclusivamente per domini audiovisivi ammessi con corrispondenza esatta o sottodominio e con prova di verifica; domini somiglianti o URL non verificati non vengono esposti.
- Se il PDF o ZIP viene elaborato dopo la prima notifica e aggiunge un collegamento verificato, il record esistente viene aggiornato, torna non letto e produce un solo nuovo Web Push. Una seconda elaborazione invariata non produce duplicati.
- Verifiche automatiche rieseguite: `86` test mirati backend e bridge, build React, contratti React, copertura UI, integrità UTF-8 e conservazione asset. Il chunk JavaScript maggiore è `369,24 kB`, sotto il limite di `500 kB`.
- Resta necessaria la prova materiale finale su produzione, inclusa una sottoscrizione Web Push reale con permesso del browser, prima di trasformare `AG-012` da `[~]` a `[x]`.

## Verifica urgente notifica Tribunale di Locri - 17/07/2026

- Server di produzione aggiornato con Local Signer `1.6.94`; container applicativo unico `iusentra-app` osservato healthy e `https://app.iusentra.it/api/pronto` raggiungibile.
- Caso reale selezionato con click nella pagina autenticata: pratica `2026/339`, `RG 1854/2026`, Cuzzupoli Maria, `TRIBUNALE DI LOCRI`.
- Precompilazione osservata campo per campo: Avv. Giuseppe Montagnese, assistita e codice fiscale, Avvocatura Distrettuale dello Stato di Reggio Calabria, codice fiscale `92006980806`, PEC `ads.rc@mailcert.avvocaturastato.it`, registro `ReGIndE`, Ministero dell'Istruzione e del Merito come parte rappresentata.
- La verifica degli enti ReGIndE usa l'operazione ministeriale esatta `ricercaEnteEx`, con descrizione, codice fiscale e PEC. Il software non sostituisce il codice fiscale inserito e non accetta una risposta non visibile o non coincidente con tutti i dati mostrati.
- Click reale su `Controlla relata`: controllo eseguito alle `22:33`, nessun invio eseguito e messaggio operativo che richiede il PIN nel riquadro `Firma relata`. `Invia PEC` resta disabilitato finché mancano documento scelto, verifica ReGIndE, firma e approvazione finale.
- I documenti del fascicolo sono caricati e disponibili ma non preselezionati: la scelta degli atti da notificare resta dell'avvocato.
- Il servizio locale risponde su `127.0.0.1:27272`, versione `1.6.94`; al momento della verifica espone `0` dispositivi perché la chiavetta era stata rimossa. Verifica ReGIndE live e firma crittografica restano pertanto **non verificate su macchina reale** e devono essere completate dall'avvocato dopo l'inserimento del dispositivo.
- Nessuna PEC reale è stata inviata.

## Catalogo UNEP condiviso con Tribunali - 18/07/2026

- La pagina Notifiche legali non mantiene una seconda rubrica UNEP: usa lo stesso catalogo caricato dalla sezione `Tribunali e indirizzi PEC`.
- Il catalogo operativo espone `141` uffici UNEP distinti, ciascuno con denominazione, codice ministeriale, distretto e PEC. La PEC è classificata per richieste e ritorni UNEP e non viene confusa con una PEC di deposito PCT o con la PEC del destinatario della notifica.
- La ricerca nella pagina Notifiche legali accetta ufficio, città, distretto, codice e PEC; la selezione conserva insieme codice e indirizzo. Il backend rilegge il catalogo e rifiuta una combinazione codice/PEC non corrispondente.
- La pratica propone l'ufficio coerente con l'autorità giudiziaria, ma l'avvocato può sostituirlo dal catalogo. I casi di controllo includono Locri, Palmi e Vicenza.
- Sono governati separatamente i quattro mezzi di esecuzione (`a mani`, `posta`, `estero`, `telematica`) e i `18` tipi di richiesta UNEP ricostruiti dai relativi tracciati, comprese notifiche civili e penali, materia lavoro, pignoramenti, integrazioni di pagamento, ricerca beni e restituzione somme.
- Audit ripetibile: `python scripts/audit_legal_notification_coverage.py`. Fallisce per uffici mancanti, duplicati, PEC assente, uso errato dell'indirizzo, divergenza fra catalogo e UI o tipo di richiesta non mappato.
- Nessun riferimento al prodotto usato per il confronto viene esposto nella UI.
- La prova materiale su produzione e sulla copia reale locale resta obbligatoria prima di marcare questa tranche come chiusa; nessuna PEC o richiesta UNEP reale deve essere inviata durante il test.

## Accettazione locale reale del 17/07/2026 - `AG-012`

- Copia reale verificata: `http://127.0.0.1:8080`, container `iusentra-app` healthy, `/api/pronto` positivo, fuso `Europe/Rome`, versione `2.256.2`.
- Click reale Agenda: l'evento controllato alle `16:45` apre il dettaglio con cliente, RG, ufficio, modalità da remoto, piattaforma Microsoft Teams, identificativo riunione, codice di accesso, istruzioni e collegamento cliccabile.
- Click reale Scadenziario: la stessa udienza espone nota operativa, allegato fonte, stato di verifica, modalità, ora e collegamento audiovisivo.
- Click reale timeline fascicolo: l'attività di categoria `UDIENZA` non viene più esclusa e conserva descrizione, note, fonte e collegamento.
- Click reale topbar: la notifica operativa contiene data e ora italiane e l'azione secondaria `Collegati all'udienza`.
- Click reale Impostazioni > Notifiche: dispositivo attivato, endpoint registrato, notifica di prova inviata e mostrata sul dispositivo; stato finale `Attivo` e dispositivo push conteggiato.
- Corretto anche lo stato sospeso del browser: permesso e riallineamento sono limitati temporalmente e il pulsante torna sempre utilizzabile con esito chiaro.
- Guardrail rieseguiti: suite mirata PEC/udienze/Scadenziario/notifiche senza errori, build React, typecheck e `git diff --check`; chunk JavaScript massimo `369,24 kB`, inferiore al limite di `500 kB`.
- `AG-012` resta formalmente `[~]` fino alla ripetizione della prova sul server dopo il deploy dello stesso commit; la prova locale non viene usata per anticipare l'accettazione di produzione.

## Pubblici elenchi notifiche - ciclo completo del 18/07/2026

- [~] `NOT-002` è stato esteso a tutte le fonti governate: ReGIndE autenticato; Registro PP.AA./PST, INI-PEC professionisti, INI-PEC imprese, Registro Imprese e INAD con consultazione ufficiale assistita; ANPR escluso perché non certifica una PEC per la notifica.
- [x] `NOT-REG-001` IPA e Registro PP.AA. sono distinti: una risposta IPA non può essere registrata o mostrata come verifica del Registro PP.AA.
- [x] `NOT-REG-002` La conferma richiede fonte, soggetto, codice fiscale o partita IVA, PEC, operatore, data e ora della consultazione e URL ufficiale; il backend conserva una prova con impronta nel fascicolo e rifiuta prove alterate o scadute.
- [x] `NOT-REG-003` Il pannello React espone per ogni fonte l'azione corretta e non tenta di aggirare CAPTCHA o accessi riservati. Nessun riferimento tecnico al prodotto confrontato è mostrato nella UI.
- [x] `NOT-REG-004` Guardrail automatici superati: `89` test notifiche, `233` test Local Signer, audit `7` fonti / `141` uffici UNEP / `18` richieste UNEP, typecheck e build React; chunk massimo corrente `369,24 kB`.
- [ ] `NOT-REG-005` Eseguire il click reale su produzione e sulla copia locale `127.0.0.1:8080`: apertura della fonte ufficiale, conferma soggetto/PEC, ricaricamento, prova conservata nel fascicolo, responsive e stati hover/focus. Nessun invio PEC reale.

## Fascicolo, documenti e avvio rapido dei flussi - 18/07/2026

- [ ] `FAS-DOC-001` Correggere il rinomina documento: il nome salvato, mostrato dopo il ricaricamento e usato nei download deve coincidere; non basta modificare una sola etichetta descrittiva.
- [~] `FAS-DOC-002` Aggiungere nel fascicolo la ricerca dei documenti d'ufficio sul Portale dei Servizi Telematici tramite il servizio locale e il browser governato, riusando autenticazione e sessione già attive senza esporre credenziali al server.
  Analisi di confronto completata il 18/07/2026: il flusso di riferimento parte dalla pratica selezionata, valida ufficio, registro, RG, anno, ruolo e sotto-procedimento, apre il fascicolo ufficiale e porta direttamente alla sezione documenti. Il catalogo di acquisizione conserva la gerarchia documento principale/allegati, data, depositante, nome originale e identificativo ufficiale; i file già acquisiti sono riconosciuti dall'identificativo senza nuovo download. Ogni elemento consente la scelta fra originale informatico, copia di consultazione o esclusione. L'accettazione resta aperta fino all'implementazione React e alla prova reale server/locale.
  Memoria tecnica e funzionale permanente: `artifacts/react-migration/confronto-documenti-fascicolo-ufficio.md`.
- [ ] `FAS-DOC-003` Consentire all'avvocato di selezionare nel fascicolo i documenti da notificare e aprire Notifiche legali con soli riferimenti e impronte dei documenti scelti, senza nuovo caricamento dei file.
- [ ] `FAS-DOC-004` Applicare lo stesso contratto di selezione al deposito: scelta manuale nel fascicolo, passaggio di identificativi tenant-aware e caricamento del contenuto soltanto quando serve a firma o busta.
- [ ] `FAS-DOC-005` Conservare nella notifica e nel deposito la scelta dell'avvocato senza preselezionare automaticamente tutti i documenti e senza duplicare record o file.
- [ ] `NOT-REG-006` Rendere rapida l'aggiunta di destinatari ulteriori con ricerca nella fonte ufficiale selezionata; le proposte del fascicolo restano prioritarie ma non sostituiscono l'accesso agli altri soggetti verificabili.
- [~] `FAS-DOC-007` Ripristinare la visualizzazione interna dei file EML importati anche quando il titolo descrittivo non conserva l'estensione: il formato deve essere ricavato dal nome originale o dal file acquisito e il download deve mantenere `.eml`.
