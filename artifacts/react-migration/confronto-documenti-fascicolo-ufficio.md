# Confronto documenti del fascicolo d'ufficio

Aggiornato il 18/07/2026. Questo documento conserva l'analisi del flusso osservato nel materiale decompilato e la sua traduzione operativa per IUSENTRA. È una memoria di progetto: non deve essere trasformata in riferimenti tecnici visibili nella UI.

## Obiettivo

Dal fascicolo IUSENTRA l'avvocato deve poter:

1. aprire la consultazione ufficiale già contestualizzata sulla pratica;
2. vedere i documenti del fascicolo d'ufficio senza ripetere la ricerca;
3. distinguere documento principale e allegati;
4. scegliere quali file acquisire e in quale forma;
5. importare solo ciò che manca, senza duplicare file già presenti;
6. ritrovare subito i file acquisiti nei Documenti e atti del fascicolo.

## Materiale analizzato

Percorso decompilato analizzato:

`C:\Users\antmm\AppData\Local\Temp\quickorganizer_decompiled_full\QuickOrganizer`

File e responsabilità osservate:

- `FormMain.cs`: recupero dei dati della pratica, validazioni, costruzione del collegamento al fascicolo ufficiale e avvio del browser incorporato;
- `BrowserForm.cs`: apertura della pagina ufficiale, selezione automatica della sezione documenti, intercettazione download e associazione alla pratica;
- `Common.cs`: struttura tabellare del catalogo e relazione documento principale/allegati;
- `PCT.cs`: ricerca documenti, lettura del dettaglio, download copia/originale e normalizzazione dei metadati;
- `WizardImportaPraticheDaPolisWeb.cs`: elenco gerarchico, classificazione, scelta di download e riconoscimento degli elementi già acquisiti.

## Percorso 1: consultazione diretta dalla pratica

### Prerequisiti letti dalla pratica

Il comando parte dal fascicolo corrente e verifica prima dell'apertura:

| Dato | Uso |
| --- | --- |
| Autorità giudiziaria | risoluzione dell'ufficio ministeriale |
| Codice ufficio | selezione del servizio del distretto |
| Registro | scelta del canale civile, lavoro, esecuzioni, procedure concorsuali, minori o Giudice di Pace |
| Numero RG | individuazione del fascicolo |
| Anno RG | individuazione del fascicolo |
| Sotto-procedimento | selezione del ramo corretto quando presente |
| Ruolo utente | accesso come avvocato, curatore o altro ruolo ammesso |
| Codice fiscale dell'utente | contestualizzazione dell'accesso autenticato |

Se uno dei dati essenziali è assente o non valido, il flusso non inventa un valore: riporta l'avvocato alla pratica da correggere.

### Apertura e sezione documenti

Il browser incorporato apre la pagina ufficiale del fascicolo usando i dati già noti. Quando riconosce la pagina informativa del fascicolo:

1. legge i collegamenti disponibili nella pagina;
2. individua quello relativo ai documenti del fascicolo;
3. vi naviga automaticamente;
4. mantiene il contenuto ufficiale nel browser incorporato.

La caratteristica importante non è il collegamento hardcoded, ma il comportamento: l'avvocato parte dalla pratica e arriva direttamente ai documenti senza ricompilare ufficio, registro, RG e anno.

## Percorso 2: catalogo strutturato per acquisizione

### Ricerca dei depositi

Il servizio del registro restituisce una riga per ciascun deposito o documento con questi campi:

| Campo osservato | Significato operativo IUSENTRA |
| --- | --- |
| `dataDeposito` | data ufficiale del deposito |
| `autore` | soggetto che ha depositato |
| `tipo` | tipo di atto o documento |
| `idUfficio` | ufficio proprietario del fascicolo |
| `IdDocumento` | identificativo ufficiale del documento/deposito |
| `IdDocMittente` | riferimento del documento del mittente |
| `stato` | stato ufficiale |
| `annoDocumento` / `numeroDocumento` | estremi del documento |
| `annoFascicolo` / `numeroFascicolo` | estremi del fascicolo |
| `subprocedimento` | ramo del procedimento |

### Dettaglio principale e allegati

Per ogni identificativo viene richiesto il dettaglio. Il risultato è organizzato in due insiemi collegati:

- documento principale: data, depositante, nome originale, identificativo ufficiale, tipologia e scelta di acquisizione;
- allegati: nome originale, identificativo ufficiale e scelta di acquisizione, collegati al padre mediante lo stesso identificativo del deposito.

L'elenco presenta quindi una struttura padre/figli, non una lista piatta. Questo evita di perdere il contesto del deposito a cui appartiene ciascun allegato.

Alcuni file puramente tecnici di servizio non vengono mostrati come documenti professionali nell'elenco principale. In IUSENTRA devono comunque restare conservabili nel pacchetto tecnico e nell'audit, senza confonderli con gli atti che l'avvocato deve leggere o selezionare.

### Scelta per ogni file

La modalità non seleziona automaticamente tutto. Per ciascun documento l'avvocato può scegliere:

- originale informatico o duplicato;
- copia di consultazione/copia informatica;
- non acquisire.

La scelta deve essere indipendente per documento principale e allegati. Il default IUSENTRA resta prudente e non deve trasformarsi in una preselezione massiva nascosta.

## Riconoscimento dei documenti già acquisiti

Il confronto usa l'identificativo ufficiale del documento. Se lo stesso identificativo è già presente nella pratica:

- la riga viene marcata come acquisita;
- non viene riscaricata;
- conserva la classificazione già assegnata;
- gli allegati figli già presenti ricevono lo stesso presidio;
- l'avvocato può distinguere subito nuovi documenti e documenti già conservati.

Per IUSENTRA la chiave primaria di riconciliazione deve seguire questo ordine:

1. identificativo ufficiale del documento o del catalogo;
2. impronta SHA-256 del contenuto;
3. riferimento del deposito e nome originale normalizzato;
4. solo in assenza dei precedenti, combinazione prudente di fascicolo, data, tipo e nome.

Il nome del file da solo non è sufficiente per decidere che due documenti sono uguali.

## Download e associazione alla pratica

Quando il download parte dal fascicolo corrente, la pratica di destinazione è già nota. La selezione manuale di un'altra pratica compare soltanto se la consultazione è stata aperta senza contesto.

Al completamento vengono conservati:

- identificativo della pratica;
- nome originale del file;
- percorso fisico governato;
- identificativo ufficiale del documento;
- origine telematica;
- breve descrizione del contenuto;
- indicazione di firma digitale o natura della copia;
- data e ora dell'acquisizione;
- impronta del contenuto;
- operatore e tenant proprietario.

L'elenco documenti della pratica viene aggiornato immediatamente dopo il salvataggio.

## Copertura già presente in IUSENTRA

Il codice attuale possiede già gran parte del motore necessario:

- sessione PST locale riusabile con durata governata;
- autenticazione tramite certificato sul PC dell'avvocato;
- ricerca fascicoli e documenti per registri supportati;
- parser per documento principale e allegati;
- download singolo e batch;
- scelta fra copia e originale;
- supporto degli identificativi `id_documento`, `id_cat`, repertorio e messaggio;
- deduplicazione per identificativo e metadati forti;
- salvataggio tenant-aware nel fascicolo;
- catalogo locale dei metadati portale e distinzione acquisito/da acquisire.

File IUSENTRA da riusare:

- `tools/local_signer.py` per sessione, ricerca, dettaglio e download;
- `web/services/telematico_runtime.py` per normalizzazione del catalogo e importazione;
- `web/services/fascicoli_runtime.py` e `pct/fascicoli.py` per riconciliazione e persistenza;
- `web/services/react_fascicoli_bridge.py` per il payload del fascicolo React;
- `frontend/src/components/FascicoliPage.tsx` per Documenti e atti;
- `frontend/src/fascicoliData.ts` per il contratto tipizzato.

## Lacuna da chiudere

La superficie React del fascicolo non espone ancora il ciclo completo nello stesso pannello. Il comando richiesto deve:

1. usare i dati del fascicolo corrente;
2. verificare il servizio locale e riusare la sessione valida;
3. cercare il fascicolo ufficiale senza chiedere di reinserire i dati già presenti;
4. caricare il catalogo gerarchico dei documenti;
5. mostrare nuovi e già acquisiti;
6. consentire la scelta per ogni file;
7. scaricare soltanto i selezionati;
8. salvare e aggiornare l'elenco senza ricaricare l'intero fascicolo;
9. conservare log e prova dell'acquisizione;
10. non esporre PIN, cookie, certificati o dettagli tecnici al server o nella UI.

## Stati UI richiesti

| Stato | Testo operativo |
| --- | --- |
| servizio locale non raggiungibile | `Collegamento al PC non disponibile` con azione di riprova |
| dati fascicolo incompleti | indicazione esatta del dato da completare e azione rapida |
| ricerca in corso | `Ricerca nel fascicolo d'ufficio...` senza bloccare la pagina |
| nessun risultato | `Nessun documento disponibile per questo fascicolo` |
| catalogo caricato | numero di documenti principali, allegati e già acquisiti |
| download in corso | avanzamento per file e totale |
| acquisito | `Acquisito nel fascicolo` e azione di visualizzazione |
| errore singolo | il lotto continua; il file fallito resta selezionabile per nuovo tentativo |

Nessun testo UI deve citare il prodotto usato per il confronto, nomi di metodi, endpoint o identificativi tecnici.

## Prestazioni

- riusare una sola sessione locale per consultazione e download;
- una ricerca di catalogo per fascicolo, non una ricerca per ogni documento;
- dettaglio e download batch quando il servizio lo consente;
- non rileggere file già acquisiti e invariati;
- aggiornare in React solo la sezione Documenti e atti;
- non inviare al server i contenuti dei documenti per la sola visualizzazione del catalogo;
- usare caricamento progressivo degli allegati se il catalogo è molto grande.

## Sicurezza e titolarità del dato

- PIN e chiavi private restano sul PC;
- cookie e sessioni ufficiali restano nel servizio locale;
- il server riceve soltanto metadati e file esplicitamente acquisiti;
- ogni salvataggio usa tenant e fascicolo della richiesta autenticata;
- il backend deve rileggere il fascicolo e rifiutare identificativi appartenenti a un altro tenant;
- la prova di acquisizione conserva origine, identificativo, hash, data/ora italiana e operatore.

## Matrice minima di collaudo

La funzione non può essere dichiarata chiusa senza prova reale su almeno:

- civile SICID;
- lavoro SICID;
- Giudice di Pace/SIGP;
- esecuzioni o procedure concorsuali SIECIC;
- documento principale senza allegati;
- documento principale con più allegati;
- file già acquisito;
- nuovo file nello stesso deposito;
- scelta copia;
- scelta originale;
- esclusione manuale;
- errore di un file in un lotto;
- aggiornamento di fascicolo già esistente senza duplicazione;
- responsive desktop, notebook 14 pollici e mobile;
- hover, focus, loading, errore e successo;
- apertura del file acquisito nel visualizzatore IUSENTRA.

## Verifica 18/07/2026 - apertura online PST

Richiesta utente: il flusso dei documenti del fascicolo d'ufficio deve aprire direttamente il Portale Servizi online, entrare nel fascicolo e portare l'avvocato al tab Documenti, dove sceglie cosa scaricare.

Esito implementato e provato su `https://app.iusentra.it/fascicoli/78D6022C#documenti`:

- nel pannello `Documenti e atti` è presente il blocco `Fascicolo d'ufficio`;
- il comando primario `Apri Portale Servizi` genera l'URL ufficiale PST con ufficio, registro, numero e anno del fascicolo;
- il click reale apre una sola scheda del Portale Servizi online;
- la scheda aperta è `https://servizipst.giustizia.it/PST/it/sicid_infofascicolo.wp?...documentiFascicolo.action...ufficioRicerca=0800570094&numero=1428&anno=2026`;
- non viene più avviata automaticamente una seconda scheda generica del servizio locale;
- l'azione interna `Leggi elenco` resta separata per il catalogo acquisibile, così il percorso online non viene bloccato se il servizio locale non è disponibile.

Guardrail prestazionale: la build Vite in produzione non segnala chunk JavaScript superiori a 500 kB; `OfficeDocumentsPanel` risulta circa 17 kB minificato.

## Stato

- Analisi del decompilato: completata.
- Confronto con i componenti IUSENTRA esistenti: completato.
- Implementazione della superficie React nel fascicolo: in corso, apertura online PST completata.
- Prova reale server: eseguita per apertura online PST su fascicolo `78D6022C`.
- Prova reale locale su `127.0.0.1:8080`: non eseguita per la nuova superficie.
- Commit, push e deploy finale: aperti nell'ambito della tranche composta corrente.

## Correzione 18/07/2026 - ciclo corretto per scelta e download documenti

La verifica successiva ha corretto la strategia precedente: l'apertura diretta della pagina interna `documentiFascicolo.action` non è affidabile, perché quella pagina presuppone una sessione PST già aperta dal portale ufficiale.

Il ciclo operativo aggiornato è:

1. dal fascicolo IUSENTRA l'avvocato apre `Documenti e atti`;
2. il comando `Apri Portale Servizi` avvia tramite Local Signer una sessione assistita locale sulla pagina ufficiale di accesso PST;
3. l'avvocato si autentica nel portale, entra in InfoFascicolo e poi nel tab Documenti;
4. l'avvocato sceglie e scarica solo i documenti necessari;
5. il comando `Raccogli download` importa nel fascicolo IUSENTRA corrente i file scaricati, senza creare un nuovo fascicolo e senza duplicare documenti già presenti;
6. `Leggi elenco` resta il canale automatico per il catalogo acquisibile, separato dalla scelta manuale sul portale.

Decisioni operative confermate:

- il pulsante primario non deve usare un link profondo alla pagina interna del PST;
- PST è ammesso nel circuito di sessione assistita solo per apertura portale, raccolta download e import file;
- il canale diretto Local Signer/PST per consultazione automatica resta separato e invariato;
- la UI non deve citare il prodotto usato per il confronto né endpoint tecnici;
- ZIP, PDF, P7M, XML, EML, MSG, TXT e HTML scaricati vengono filtrati per estensione sicura, hash e fascicolo di destinazione.

Stato della correzione:

- React `OfficeDocumentsPanel`: aggiornato.
- Runtime portali: PST abilitato per sessione assistita di acquisizione.
- Local Signer sorgente e distribuzione: apertura PST dalla pagina ufficiale e rientro governato verso InfoFascicolo Documenti.
- Produzione `https://app.iusentra.it`: deploy eseguito sul server Hetzner e container `iusentra-app` healthy.
- Local Signer sul PC: aggiornato e verificato alla versione `1.6.97`.
- Prova reale server/browser del 18/07/2026: dalla scheda IUSENTRA del fascicolo `78D6022C` il comando `Apri Portale Servizi` risulta disponibile nel blocco `Fascicolo d'ufficio`; la sessione assistita locale ha aperto il portale ufficiale e lo stato del servizio locale ha registrato `InfoFascicolo documenti aperto nella sessione ufficiale` per `TRIBUNALE DI PALMI`, `R.G. 1428/2026`, registro `RGN`, ufficio `0800570094`.
- Evidenza browser del 18/07/2026: scheda PST aperta su `sicid_infofascicolo.wp` con `documentiFascicolo.action`, `ufficioRicerca=0800570094`, `numero=1428`, `anno=2026`.
- Test mirati eseguiti: `python -m py_compile tools/local_signer.py tools/dist/local_signer.py`, `pnpm --dir frontend typecheck`, `pytest` mirati su Local Signer, payload PST e React shell.
- Correzione immagine Docker: prima di copiare il bundle React appena compilato viene rimossa la vecchia cartella `web/static/react`, così gli asset storici non entrano nel container. Controllo post-deploy: chunk JavaScript più grande nel container `369239` byte, quindi sotto 500 kB.
- Prova reale locale su `127.0.0.1:8080`: da eseguire dopo riallineamento della copia locale.

## Verifica 18/07/2026 - automazione post accesso PST

Nuovo controllo richiesto: dopo l'accesso al Portale Servizi la sessione assistita non deve restare su una pagina generica e non deve tentare un link profondo non autenticato. Il comportamento da mantenere e' il ciclo osservato nel materiale di confronto:

1. apertura della pagina ufficiale di accesso PST;
2. riconoscimento della sessione autenticata dopo il login;
3. apertura della pagina di ricerca documenti del registro corretto;
4. compilazione di ufficio, registro, ruolo, numero e anno gia' presenti nel fascicolo IUSENTRA;
5. avvio della ricerca;
6. selezione del collegamento InfoFascicolo corrispondente a numero e anno;
7. selezione automatica del tab Documenti;
8. scelta manuale dei documenti da parte dell'avvocato e raccolta governata dei download nel fascicolo.

Implementazione IUSENTRA:

- `tools/local_signer.py` ora distingue tra pagina di ricerca PST, pagina InfoFascicolo e tab Documenti;
- una pagina `pst_2_1_*_4.wp` non viene piu' considerata arrivo finale;
- se la sessione arriva su `homepage.wp?redirectflag=1`, il Local Signer calcola la pagina documenti corretta per il registro e vi naviga;
- sulla pagina di ricerca compila i campi disponibili e avvia la ricerca senza chiedere all'avvocato di reinserire i dati del fascicolo;
- sulla pagina InfoFascicolo clicca il tab Documenti quando presente;
- se il tab e' gia' su `documentiFascicolo.action`, lo stato diventa finale;
- la versione Local Signer collegata alla correzione e' `1.6.99`.
- il profilo browser assistito PST e' stabile per portale, non piu' creato dentro la
  singola sessione casuale, cosi' la sessione autenticata non viene persa a ogni
  apertura e si riduce la richiesta ripetuta di PIN.

Test mirati aggiunti:

- `test_portal_assistant_pst_documenti_guida_ricerca_post_accesso`;
- `test_portal_assistant_pst_documenti_non_considera_arrivo_la_pagina_ricerca`;
- `test_portal_assistant_pst_infofascicolo_clicca_tab_documenti`;
- `test_portal_assistant_pst_profile_controllato_stabile`.

Stato prova:

- test automatici mirati: superati;
- applicazione al Local Signer installato sul PC e prova reale browser: da completare prima della chiusura della tranche.

## Hotfix 18/07/2026 - aggiornamento Local Signer senza login IUSENTRA

Perche' la sessione assistita PST usi davvero la logica nuova sul PC dell'avvocato,
il servizio locale deve poter scaricare sorgente, moduli, cataloghi e installer dal
server anche quando non possiede la sessione web IUSENTRA. La rotta
`/polisWeb/local-signer/` resta quindi pubblica solo per i pacchetti Local Signer e
non cambia le regole di accesso dell'applicazione.

Guardrail aggiunti:

- alias pubblico `/polisWeb/local-signer/download/local-signer.py` per evitare che
  un controllo manuale cada nella pagina di login;
- esenzione di tutto il prefisso `/polisWeb/local-signer/` dal gate di login;
- test anonimi sul download Python, alias, cataloghi, moduli, requisiti e installer.

## Aggiornamento 18/07/2026 - selezione documenti prima di Notifica e Deposito

Il criterio operativo confermato è lo stesso del ciclo documentale osservato: l'avvocato sceglie i documenti nel contesto del fascicolo e il flusso successivo riceve soltanto quella selezione. Questo evita di ricaricare l'intero fascicolo nella pagina Notifica o Deposito e riduce il rischio di allegare documenti non voluti.

Implementazione:

- nel dettaglio fascicolo i pulsanti `Notifica` e `Deposito telematico` aprono una finestra sopra la pagina;
- la finestra mostra documenti ricercabili e selezionabili, con comando rapido per i documenti proposti;
- la destinazione riceve la query `documenti` con gli identificativi scelti;
- l'API documenti Notifica accetta la selezione esplicita e restituisce anche documenti oltre il vecchio primo blocco di quaranta elementi;
- il deposito legge la stessa query come perimetro iniziale dei documenti da inviare;
- se non viene indicata alcuna selezione esplicita, resta valida la logica precedente.

Verifiche automatiche eseguite:

- `tests/test_notifiche_legali.py::test_payload_documenti_pratica_rispetta_selezione_esplicita_oltre_primo_blocco`;
- `tests/test_regia_ui_react.py::test_ui_fascicolo_notifica_e_deposito_partono_da_documenti_scelti`;
- `tests/test_regia_ui_react.py::test_ui_notifiche_mantiene_indirizzi_generali_e_preselezione_documenti`;
- `tests/test_regia_ui_react.py::test_ui_deposito_accetta_documenti_preselezionati_da_query_fascicolo`;
- typecheck React e build Vite con budget asset sotto `500.000` byte.

Stato: codice pronto per prova reale server. Nessun riferimento tecnico al materiale di confronto viene esposto nella UI.
