# Log tecnico — Test Fascicolo d'ufficio

Data: 28/08/2026 13:30–13:48 (Europe/Rome)
Ambiente: copia locale reale `http://localhost:8080`
Pagina di prova: `http://localhost:8080/fascicoli/A1FB22FE#documenti`

## Dati del test

- Ufficio visualizzato: Tribunale di Vicenza.
- R.G.: 1084/2026.
- Codice ufficio IUSENTRA/PST: `0640011`.
- Codice ministeriale risolto dal registro locale: `0241160092`.
- Tabella/servizio risolto: `JPW_SICID`.
- Local Signer: `1.6.124`.
- Applicazione locale: `2.278.83`.

## Azione eseguita

1. Nel pannello **Fascicolo d'ufficio**, pulsante **Visualizza fascicolo**.
2. L'avvocato ha completato una sola richiesta PIN nativa di Windows.
3. Il pannello ha avviato il job locale `POST /pst/fascicolo-snapshot-job` e ha mostrato l'avanzamento della consultazione.

## Esito osservato

L'esito ricevuto nella UI non è accettabile per questo fascicolo:

> Nessun nuovo documento disponibile nel fascicolo d'ufficio.

Il fascicolo aveva già prodotto un catalogo di 30 documenti nel flusso Wizard. L'esito vuoto non deve quindi essere interpretato come assenza di documenti e non viene classificato come test positivo.

## Evidenza tecnica

Estratto del log del Local Signer:

```text
PST ricerca-snapshot: ufficio richiesto=0640011 codice_pst=0241160092
servizio=JPW_SICID tabella_hint=JPW_SICID rg=1084/2026
PST ricerca-snapshot: richiesta 7/JPW_SICID non bloccante:
Il PST ha restituito una SOAP Fault: IDATTO | SOAP-ENV:Client
_parse_fascicoli_xml: no element found: line 1, column 0
```

Il codice ufficio e il servizio sono coerenti con il registro ministeriale. Il difetto riguarda il catalogo: il batch SOAP iniziale può contenere soltanto gli atti principali mentre allegati e pagine successive sono esposti nella pagina ministeriale autenticata del fascicolo.

## Correzione applicata, non ancora accettata

Nel ramo `single_interactive_batch`, `tools/local_signer.py` completa il catalogo tramite `_pst_carica_infofascicolo_web` con il solo `cookie_file` della sessione già autenticata. Per questa lettura non sono passati thumbprint, certificato o retry mTLS: non deve quindi comparire un secondo PIN.

Se la pagina ministeriale non restituisce documenti, resta il recupero master-detail cookie-only. Il pannello conserva il catalogo ricevuto in `documenti`, `catalogo`, `documents` e `sezioni.documenti_fascicolo` prima di renderlo selezionabile.

## Controlli eseguiti

- Compilazione Python di `tools/local_signer.py` e della copia runtime installata: superata.
- Test Local Signer mirati (7): superati.
- Contratto React `office_documents_portale_pst_consulta_nell_app_con_catalogo_completo`: superato.
- `GET /api/pronto`: applicazione locale pronta.
- `GET /ping?light=1`: Local Signer pronto dopo riavvio silenzioso.

## Stato di accettazione

La correzione richiede ancora una prova materiale sulla stessa pagina con catalogo ministeriale completo visibile, selezione di tutti/non acquisiti/singoli, scelta copia/originale e controllo che non compaia un secondo PIN. Fino a quella prova, il test è **non verificato su macchina reale** e non va considerato risolto.

## Correzione lotto unico catalogo completo — 29/08/2026

### Causa confermata dal confronto con il backup IUSENTRA

Il backup con esito positivo conserva la stessa fonte del catalogo completo: la pagina ministeriale autenticata `documentiFascicolo`, che contiene allegati oltre ai cinque atti principali restituiti dal solo SOAP. Nel codice corrente il Wizard e il pannello erano stati portati sullo stesso job, ma il catalogo esteso veniva richiesto dopo il batch iniziale tramite più recuperi solo-cookie. Se il cookie non era sufficiente, il risultato rimaneva fermo ai cinque atti principali; inoltre il batch iniziale includeva cinque sezioni accessorie, facendo crescere il tempo della consultazione oltre il comportamento osservato di circa 45 secondi.

### Correzione applicata


## Rettifica codice ufficio e log prova — 29/08/2026 21:47

### Causa della prova non conforme

La richiesta appena registrata aveva il servizio `JPW_SICID`, ma il pannello aveva composto il campo `tribunale` dando precedenza a `ministerialCode`. Per il Tribunale di Vicenza quel campo vale `0241160092`, mentre il Wizard trasmette il codice operativo del registro `0640011`.

Nel Local Signer la trasformazione `0640011` → `0241160092` è invece prevista e identica alla copia positiva: il secondo valore è l’identificativo ministeriale richiesto nel protocollo PST. Non è una seconda selezione di ufficio né una regola nuova.

### Correzione applicata

- `OfficeDocumentsPanel.tsx` usa ora lo stesso ordine del Wizard: `depositOffice.code`, poi `depositOffice.ministerialCode`, poi il valore storico dello snapshot.
- Il messaggio di catalogo vuoto mostra la tabella effettivamente dedotta dall’hint server (`JPW_SICID` / `SICID_CONTENZIOSO_CIVILE` nel caso in prova), non il valore storico `SICID_LAVORO`.
- È stato aggiunto un test statico che blocca la regressione dell’ordine del codice ufficio.

### Valori attesi nel prossimo log Local Signer

```text
ufficio richiesto=0640011
codice_pst=0241160092
servizio=JPW_SICID
tabella_hint=JPW_SICID
```

Il primo valore conferma la parità del pannello con il Wizard; il secondo conferma la conversione ministeriale della baseline. Un servizio lavoro oppure un messaggio che cita `SICID_LAVORO` resta non conforme.

### Verifiche tecniche preliminari

- `registroRicerca` viene normalizzato ai codici brevi ministeriali per tutte le dieci tabelle (`CC`, `LAV`, `VG`, `MIN`, `ESM`, `ESIM`, `FALL`, `GDP`, `CASSCI`, `CASSPE`), senza riutilizzare il nome tecnico della tabella.
- Il percorso comune `POST /pst/ricerca-snapshot` ora compone un unico processo `curl` autenticato con tre trasferimenti SOAP (ricerca, profilo, sommario) e, quando il registro espone la pagina, due trasferimenti GET in sequenza (scheda e catalogo allegati). Lo stesso certificato e lo stesso cookie jar restano nel processo: non esiste un secondo processo solo-cookie nel ramo interattivo.
- Eventi, comunicazioni, udienze e scadenze non sono più aggiunti al lotto iniziale; non ritardano il catalogo selezionabile. Le tabelle senza pagina InfoFascicolo mantengono il loro catalogo SOAP senza essere bloccate.
- La UI Wizard e Fascicolo d’ufficio restano sul medesimo endpoint e sul medesimo contratto; il download selezionato resta un secondo lotto separato.

### Controlli tecnici eseguiti

- Compilazione Python della sorgente e del runtime installato: superata.
- Sei test mirati Local Signer: superati. Coprono lotto `curl` unico SOAP/HTML, catalogo, parità Wizard/pannello, normalizzazione delle dieci tabelle e compatibilità del job.
- `GET /api/pronto` su `127.0.0.1:8080`: applicazione pronta, versione `2.278.83`.
- `GET /ping?light=1` su `127.0.0.1:27272`: Local Signer `1.6.124` pronto dopo riavvio silenzioso.

### Stato di accettazione

Non è stata ancora eseguita la nuova prova materiale PST dopo questa correzione. La connessione automatica alla scheda browser integrata non è disponibile in questa sessione; pertanto servono ancora click reale su `Visualizza fascicolo`, una sola richiesta PIN inserita dall’avvocato e osservazione nella UI di 30 documenti, del tempo di consultazione e dell’assenza di un secondo prompt. Fino a tale prova, la correzione è **non verificata su macchina reale**.
## Rettifica baseline PST — 29/08/2026

La sezione precedente denominata `Correzione lotto unico catalogo completo — 29/08/2026` non descrive la baseline positiva: introduceva pagine web InfoFascicolo e recuperi master/detail nel ramo interattivo. Queste variazioni hanno prodotto cataloghi parziali e richieste non allineate.

### Baseline ripristinata

- La sorgente `tools/local_signer.py` e il runtime locale usano ora, byte per byte, il metodo `_pst_ricerca_snapshot` archiviato nella copia con esito positivo del 27/08/2026.
- Il lotto interattivo resta un solo processo cURL autenticato e include ricerca esatta, profilo, catalogo SOAP e sezioni PST previste dalla baseline.
- Nel ramo interattivo non sono presenti pagine InfoFascicolo aggiunte, recuperi master/detail aggiunti, flag di esclusione delle sezioni o guardrail browser del pannello.
- Wizard e Fascicolo d’ufficio chiamano entrambi `POST /pst/ricerca-snapshot` con `search_only=false`, `include_full_snapshot=true` e `single_interactive_batch=true`; il pannello non usa job alternativi.

### Verifiche tecniche eseguite

- Identità del metodo `_pst_ricerca_snapshot` fra sorgente corrente, runtime locale e baseline: verificata.
- Compilazione Python della sorgente e del runtime locale: superata.
- Test mirati di parità Wizard/Fascicolo d’ufficio e Local Signer: superati.
- Ping leggero Local Signer `1.6.124`: disponibile, senza sessioni PST o PIN aperte.

### Stato di accettazione

Non è stata avviata alcuna nuova richiesta PST dopo il ripristino. Serve ancora una prova materiale su `http://localhost:8080`: l’esito deve mostrare il catalogo completo del fascicolo nel pannello, non solo cinque documenti. Fino a quella prova, l’esito resta non verificato su macchina reale.