# Confronto documenti del fascicolo d'ufficio

## Aggiornamento 24/08/2026 — catalogazione per fonti autoritative

È aperta la progettazione Fase 4 per una catalogazione documentale completa,
non basata sul solo nome del file. Il dossier
`artifacts/react-migration/catalogazione-documentale-fascicoli-analisi-2026-08-24.md`
definisce famiglie, riti, fasi, tipi, formati, gerarchia delle fonti e criteri
di prova.

Le classificazioni provenienti da PST/PolisWeb/PAT/PTT/PDP sono metadati di
fonte e prevalgono sulle inferenze locali deboli. Ogni nuova regola deve
indicare una fonte ufficiale, versione, ambito, evidenze e stato di revisione;
un conflitto non è risolto automaticamente ma portato in revisione. ZIP, EML
e P7M mantengono sempre relazione padre/figlio e l'originale resta disponibile
nel lettore interno.

### Aggiornamento 24/08/2026 — fonti non acquisibili dal job

La validità della fonte non coincide con un codice HTTP positivo. Durante
l'audit, gli endpoint PTT che restituivano PDF di errore, URL EUR-Lex
reindirizzati alla Gazzetta del giorno e una vecchia pagina ACF di manutenzione
sono stati esclusi dalla selezione. Le sostituzioni utilizzabili sono annotate
in `audit-copertura-famiglie-e-sottofamiglie-2026-08-24.md` e nel manifest delle
fonti ufficiali con impronta.

Il portale normativo ACF richiede invece browser reale: è stato verificato
materialmente nella pagina Consob che espone normativa UE, nazionale, delibera
22721/2023 e regolamento consolidato. La sua prova è conservata come
`browser:acf-normativa-2026`; il job non deve interrogarlo né mascherare un
fallimento. Se la verifica browser non conferma più quel contenuto, i documenti
ACF del fascicolo passano a revisione umana e nessun tipo viene attribuito in
modo silenzioso.

### Aggiornamento 24/08/2026 — profili di canale e stati non confondibili

Le specifiche DGSIA 2024, PAT 2025/2026 e Tribunale Online per la volontaria
giurisdizione sono state acquisite con URL e impronta nel manifest
`docs/specs/ministero/fonti_ufficiali/2026-08-24/README.md`. La conseguenza
operativa per il confronto d'ufficio è precisa:

1. atto principale, allegato, XML tecnico, busta, ricevuta e stato di deposito
   restano record correlati ma distinti;
2. i limiti dimensionali e i formati ammessi dipendono dal canale di origine:
   per esempio Formweb PAT ha il proprio profilo, che non modifica i limiti
   dell'import ordinario dello studio;
3. lo stato di portale — compresi `In attivazione`, `Attivo`, `Chiuso`,
   `Annullato` della volontaria giurisdizione e gli stati PDP — è una prova di
   trasmissione o lavorazione, non la classificazione giuridica del documento;
4. `atto.enc`, ricevute e file tecnici restano disponibili nel pacchetto e
   nell'audit, ma non devono essere presentati come atto professionale o
   provvedimento al posto del contenuto a cui si riferiscono;
5. qualunque incongruenza fra tipo ufficiale, contenuto estratto e metadati
   locali crea una revisione esplicita, mai una riclassificazione silenziosa.

## Aggiornamento 2026-07-26 - Ingresso rapido Apri Portale Servizi dal menu contestuale

Nel dettaglio fascicolo React il tasto destro apre un pannello di azioni rapide. La voce `Apri Portale Servizi` non crea un percorso alternativo: porta alla sezione `Documenti e atti`, carica `OfficeDocumentsPanel` se necessario e richiama lo stesso comando `openAssistedPortal()` già usato dal pannello del fascicolo d'ufficio.

Il comportamento da preservare resta quello definito in questo dossier: sessione assistita, Local Signer sul PC dell'avvocato, dati fascicolo tenant-aware, nessun deep link esterno come soluzione primaria e nessuna scansione runtime ricorsiva. Se il portale non è apribile per mancanza di certificato, canale locale o dati ufficio, deve rispondere il pannello esistente con un messaggio esplicito e non il menu contestuale con un silenzio operativo.

Aggiornato il 22/07/2026. Questo documento conserva l'analisi del flusso osservato nel materiale decompilato e la sua traduzione operativa per IUSENTRA. È una memoria di progetto: non deve essere trasformata in riferimenti tecnici visibili nella UI.

## Aggiornamento 2026-07-22 - Acquisizione mirata da presidio notifiche

Il passaggio da presidio notifica a fascicolo d'ufficio deve essere trattato come un unico flusso tenant-aware, non come apertura generica del portale:

1. il presidio parte dalla PEC che ha generato l'evento e conserva `pec_id`, documento PEC, fascicolo, R.G., ufficio, registro e parte assistita;
2. `Acquisisci originale` porta al wizard PST già compilato con quei dati, compresa la modalità `single_document=1` e `non_duplicare_documenti=1`;
3. il controllo certificato PST del Local Signer vale come prova che il servizio locale è vivo per quella sessione; dopo tale controllo la UI non deve riavviare il Local Signer prima della ricerca;
4. il documento ufficiale scaricato da PST deve essere salvato nei Documenti e atti del fascicolo con origine `PolisWeb / PST`, tipo atto ufficiale e identificativo portale;
5. lo stesso record documentale deve diventare la fonte unica collegabile a relata, Agenda, Scadenziario, topbar e Web Push, così quando l'avvocato riapre l'evento vede la PEC o il provvedimento che ha generato proprio quel presidio;
6. se il documento è già presente, il flusso deve mostrare il documento esistente e non crearne duplicati.

Caso reale di riferimento: `Romeo Maria`, R.G. `1428/2026`, `Tribunale di Palmi`, PEC `pec_d23c133a4ef8ada88ecb8c08`, ZIP PEC `9732730s.pdf.zip`, presidio `f5480e4d-5fc1-498f-8259-078dcc17fe84`. La prova reale ha evidenziato un falso errore di canale locale dovuto al riavvio del Local Signer dopo certificato già confermato; la regola aggiornata impedisce quel riavvio nel percorso presidio → PST.

## Aggiornamento 2026-07-22 - Documento PST già acquisito da riconciliare al presidio

Nel caso Romeo Maria, R.G. `1428/2026`, il documento `SentenzaDefinitiva_35882174.pdf` è già presente nel fascicolo `78D6022C` come documento `DE29EE7F`, importato da PolisWeb/PST il 22/07/2026. La PEC del presidio conserva lo ZIP `9732730s.pdf.zip` come copia informativa di cancelleria; la fonte autorevole per la relata e per la decisione di notifica deve però essere il documento PST nel fascicolo quando esiste.

La riconciliazione è stata trasformata in regola generale:

1. non si cerca in tutti gli studi e non si usa un database diverso: si legge soltanto il fascicolo collegato al presidio nel tenant corrente;
2. non si scansionano in runtime alberi pesanti, ZIP, OCR o caselle PEC: il controllo resta leggero per non rallentare il caricamento;
3. sono candidati solo documenti con metadati PST/PolisWeb o identificativo portale;
4. sono collegabili automaticamente solo provvedimenti decisori, cioè sentenze, ordinanze, decreti, verbali o provvedimenti;
5. sono esclusi ricorsi, memorie, istanze, comparse, note, ricevute, esiti controlli e accettazioni di deposito;
6. se il collegamento è univoco, il documento diventa `Documento PST acquisito nel fascicolo` e viene aperto dal lettore interno IUSENTRA;
7. se il documento manca davvero, il flusso resta `Scarica dal portale`, già compilato con ufficio, R.G., registro, PEC sorgente e modalità anti-duplicato.

Questa regola evita che l'avvocato debba ricontrollare manualmente tutti i documenti del fascicolo e impedisce che una copia PEC venga scambiata per originale notificabile.

### Blindatura 22/07/2026 - QuickOrganizer/testi non è PST

La prova sul tenant reale ha evidenziato che un vecchio `id_documento_portale` interno nel formato `quickorganizer:testi:*` non può essere trattato come identificativo ministeriale. La nuova regola distingue quindi tre famiglie:

1. documenti PST/PolisWeb veri: origine o servizio `pst`, `polisweb`, `portale servizi`, `portale telematico`, oppure identificativo portale numerico coerente;
2. copie PEC d’ufficio: fonte dell’evento, evidenza e documento informativo, ma non originale autorevole per la relata;
3. import interni/storici: QuickOrganizer, documenti AI, upload manuali o altri mirror, da non usare per riconciliazione automatica PST.

Effetto operativo: nel fascicolo Romeo Maria, R.G. `1428/2026`, le due vecchie sentenze QuickOrganizer non rendono più ambigua la riconciliazione; il candidato PST collegabile resta il documento `DE29EE7F`, `SentenzaDefinitiva_35882174.pdf`, origine `pst:JPW_SIL_DISTR:35882174`.

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

### Aggiornamento 19/07/2026 - ordine documenti nella scelta Notifica e Deposito

Richiesta utente: nella finestra `Documenti del fascicolo`, aperta dal fascicolo prima di Notifica o Deposito, i documenti devono essere ordinati per data dal più recente al meno recente. L'avvocato deve trovare subito gli ultimi documenti caricati, senza scorrere l'elenco in ordine storico o casuale.

Correzione applicata:

- la modale condivisa ordina i documenti usando prima la data documento visibile, poi la data caricamento e infine la data portale solo come fallback;
- sono supportati formati italiani e ISO, mantenendo ordinamento stabile per nome a parità di data;
- ricerca, `Seleziona proposti`, riepilogo documenti scelti e pulsanti `Continua alla notifica` / `Continua al deposito` usano tutti lo stesso ordine;
- il comportamento resta identico se l'avvocato filtra o seleziona manualmente i documenti.

Guardrail eseguiti:

- `python -m pytest -q tests/test_regia_ui_react.py::test_ui_fascicolo_notifica_e_deposito_partono_da_documenti_scelti`;
- `pnpm --filter @iusentra/studio typecheck`;
- `git diff --check`;
- `pnpm --filter @iusentra/studio build`, senza asset JavaScript sopra `500 kB`.

Stato: pronto per deploy e verifica reale in produzione sulla modale aperta da `Notifica` e `Deposito telematico`.

### Aggiornamento 22/07/2026 - apertura del documento PST riconciliato dal presidio

Il confronto operativo ora include anche il comportamento di apertura dal presidio:

- se il documento PST è già nel fascicolo e viene riconciliato automaticamente, il pulsante `Visualizza` deve aprire quel documento nel lettore interno IUSENTRA;
- le copie PEC dell'ufficio restano evidenze consultabili, ma non sostituiscono l'originale ministeriale quando l'originale PST è presente;
- il lettore interno del fascicolo deve essere incorporabile anche nella modale `Fonte dell'informazione`, senza pagina bianca e senza uscire dal software.

Correzione collegata: il sandbox della modale fonte ora consente `allow-same-origin` anche per URL interne `/documenti/.../visualizza`, così il preview PDF del documento PST può caricare le proprie risorse same-origin.

### Aggiornamento 22/07/2026 - scaricamento dal viewer interno

Per i documenti PST già acquisiti e collegati al presidio, lo scaricamento operativo non deve spostare l'avvocato fuori dal drawer e non deve dipendere dalla sola rotta `/scarica` se il browser la blocca. Il viewer interno `/documenti/.../visualizza` ora accetta `download=1` e viene usato dal dettaglio Presidi come canale primario di scaricamento quando il viewer è disponibile.

### Aggiornamento 23/07/2026 - prova notifica depositata prevale sulla preparazione relata

Il confronto con il fascicolo d’ufficio è stato esteso al caso in cui il documento PST originale è già acquisito ma il fascicolo contiene anche la prova della notifica già depositata. In questo scenario il documento PST non basta a determinare “relata da preparare”: la fonte decisiva per la fase successiva diventa la catena documentale del fascicolo.

Regola aggiornata:

- se il fascicolo espone `Prova notifica depositata`, il presidio avanzato deve registrare `PROOF_DEPOSITED`;
- la copia PEC e l’originale PST restano documenti collegati e visualizzabili, ma non generano una nuova notifica;
- la riconciliazione deve essere tenant-aware e limitata al fascicolo del presidio, senza scansioni ricorsive runtime;
- il click errato su `Conferma notifica` deve prima rieseguire questa verifica, evitando duplicazioni operative.

Caso guida: Calabrò Daniela, fascicolo `FB586324`, R.G. `3571/2025`, originale PST `SentenzaDefinitiva_35815989.pdf`, copia PEC `21295227s.pdf.zip`.

### Aggiornamento 24/08/2026 — catalogazione strutturata ancorata al fascicolo

La nuova catalogazione non introduce un archivio concorrente: ogni assegnazione,
candidato, evidenza, revisione e job porta `tenant_id` e `fascicolo_id` e resta
consultabile dal pannello Documenti del fascicolo. Il documento originale resta
nel lettore interno; il catalogo conserva soltanto decisione, provenienza,
motivazione, fonti, hash e stato di revisione.

L'aggiornamento è esplicito e a richiesta dell'avvocato. L'apertura del
fascicolo legge solo il catalogo SQL già disponibile e non avvia scansioni
ricorsive, OCR o chiamate verso fonti esterne. Se il profilo processuale non è
completo o la prova è insufficiente, il documento è marcato `Da rivedere` e non
viene trattato come classificazione certa. La conferma dell'avvocato è
registrata nello storico, senza eliminare le decisioni anteriori.

La prova materiale locale della UI e del flusso di revisione resta da registrare
in questo dossier dopo l'esecuzione sulla copia Docker reale `127.0.0.1:8080`.

### Chiusura prova locale 24/08/2026 — catalogo SQL e lettore interno

La prova è stata eseguita sulla copia Docker reale già autenticata
`http://127.0.0.1:8080`, nel fascicolo di prova `DD242366`. L'inventario di 14
documenti è rimasto interamente ancorato al fascicolo: tutte le assegnazioni,
evidenze e revisioni sono SQL tenant-aware; non è stato letto un JSON come fonte
di verità né avviata una scansione ricorsiva runtime.

Risultato osservato: in assenza di area, branca e sottofamiglia verificabili,
tutti i documenti sono esposti con revisione richiesta. È il comportamento
corretto, non un errore: una conferma automatica avrebbe trasformato una
proposta tecnica in certezza giuridica fittizia. Il caso
`Attestazione_di_conformita_1025_2026.pdf` è stato riclassificato usando il
nome verificabile e viene mostrato come `Attestazione di conformità` con
profilo da definire, anziché come sentenza per effetto di OCR ambiguo.

Con click reale sono stati provati aggiornamento, apertura e chiusura del
`Decreto_28162803.pdf.p7m` nel lettore interno. Nel reader sono comparsi
download e controlli di adattamento/zoom; hover e focus da tastiera del
controllo di apertura hanno conservato etichetta, contrasto e outline. Lo
scroll ha raggiunto sia il fondo sia l'inizio del pannello e, alla larghezza
reale disponibile di 891 px, non è risultato overflow orizzontale.

La replica PostgreSQL del contratto SQL è stata verificata contro PostgreSQL 16
effimero con migrazioni, scritture batch e snapshot fonti; l'ambiente di prova è
stato rimosso. I test mirati coprono idempotenza per hash/versione, storico
revisioni, assenza di estrazioni ripetute e mancata ri-esecuzione del processo
Lex per un aggiornamento invariato. La pagina resta quindi orientata al
fascicolo, senza duplicare il documento originale o uscire dal lettore interno.

Dopo la ricostruzione finale del container locale `iusentra-app`, healthy su
porta 8080, la medesima prova con click reale è stata ripetuta: aggiornamento
abilitato a fine richiesta, tipo dell'attestazione invariato e lettore P7M
aperto/richiuso senza uscire da IUSENTRA.

## Aggiornamento 24/08/2026 — controllo contributo, catalogo SQL e cronologia

L'accorpamento della presentazione non rimuove i resolver. In particolare il
**contributo unificato** resta una voce autonoma del riepilogo economico del
fascicolo: stato, importo, nota e documento fonte provengono dal resolver
economico; il Presidio del fascicolo ne mostra una sola card con il collegamento ai
documenti/evidenze da verificare. Non esiste una sostituzione con una variabile
grafica né un'affermazione generica di pagamento o esenzione.

La correzione del catalogo documentale è ora una procedura completa e
tenant-aware:

- il pannello React invia una richiesta autenticata alla rotta
  `POST /api/v1/ui/fascicoli/{id}/documenti-ai/{documento}/catalogazione-documentale/sovrascrivi`;
- il servizio verifica il fascicolo del tenant, aggiorna la stessa assegnazione
  SQL e registra l'evento `document_catalog.overridden` senza riversare la nota
  libera nell'audit tecnico;
- lo stato `manual_override` identifica la decisione professionale distinta da
  evidenza automatica o da semplice metadato del portale;
- la migrazione SQLite ricrea esclusivamente il vincolo `source_state` delle
  installazioni precedenti, copiando tutte le colonne e mantenendo candidati,
  evidenze e revisioni; la migrazione PostgreSQL aggiorna il vincolo omologo;
- la visualizzazione React espone quattro stati non ambigui: catalogato dal
  contenuto, confermato manualmente, metadati del portale senza contenuto,
  oppure documento da indicizzare. Il nome file non diventa una classificazione
  dal contenuto.

Anche la cronologia è stata corretta: acquisizioni PST/PolisWeb e download
Local Signer vanno in `Eventi tecnici e acquisizioni`; non sono più presentati
come attività processuali in attesa. Le udienze e le iscrizioni a ruolo importate
rimangono invece nella cronologia processuale come eventi registrati, non
modificabili come se fossero bozze dell'avvocato.

Guardrail automatici già eseguiti in questa tranche:

- repository: correzione SQL, conservazione di candidati/evidenze e conferma
  manuale;
- migrazione SQLite di un catalogo già esistente;
- API autenticata con payload completo della correzione;
- payload React: documento locale non indicizzato e documento PST privo di
  contenuto non vengono classificati dal nome;
- separazione di attività processuali, udienze importate ed eventi tecnici.

La prova di accettazione finale resta **aperta**: richiede ricostruzione della
copia Docker locale, click materiali sulle card e sulle azioni di catalogo,
scroll completo, hover/focus, desktop/tablet/mobile e verifica del comportamento
con dati controllati in `http://127.0.0.1:8080` prima di commit, push e deploy.

La superficie è denominata **Presidio del fascicolo**. L'ancora precedente
`#cabina-regia` resta disponibile soltanto per compatibilità con link e percorsi
esistenti: risolve e apre il medesimo Presidio, senza creare un secondo pannello.

## Aggiornamento 24/08/2026 — anteprima prima della scelta per deposito e notifica

Perimetro: finestra React di selezione dei documenti del fascicolo, condivisa
da **Prepara deposito telematico** e **Prepara notifica**. Non sono state
modificate la selezione dei candidati, la firma, l’indice, la busta, il
destinatario, il trasporto PEC o la logica di invio.

- Ogni documento disponibile localmente espone il comando esplicito
  **Visualizza** accanto alla casella di selezione; il comando apre il lettore
  interno IUSENTRA e conserva aperta la finestra di scelta.
- Il lettore viene portato sopra il selettore con uno stacking context
  dedicato; chiudendolo si ritorna allo stesso elenco e alle stesse selezioni.
  Un documento non disponibile localmente espone invece il motivo, senza
  simulare un’anteprima.
- Prova materiale eseguita sulla copia Docker reale
  `http://127.0.0.1:8080`, fascicolo `DC5BF1DB`: nel deposito è stato aperto
  `decretoLiquidazioneCTU.pdf`, verificato nel lettore interno e quindi
  selezionato; la UI ha mostrato `1 documenti selezionati` e il riepilogo del
  file. Nella notifica è stato ripetuto il flusso su
  `depositoMinutaSentenzaSemplificata.pdf`, con lettura interna, chiusura e
  selezione mantenuta.
- I test React mirati, il typecheck TypeScript e `git diff --check` sono
  passati prima della ricostruzione. Il container locale `iusentra-app` è
  stato ricreato ed è healthy su porta 8080.
## Aggiornamento 24/08/2026 — richiesta scadenze nel profilo PST

Il payload QBuilder per ProfiloFascicolo mantiene il parametro scadTermini con valore 1. È la richiesta primaria che include nel profilo i termini e le scadenze restituiti dal PST: non è corretto disattivarla e poi dedurre che il fascicolo non abbia scadenze. Durante il collaudo della Fase 4 è stata trovata una sola asserzione di test ancora ferma al valore storico 0; è stata aggiornata al contratto effettivo senza modificare connettore, dati, richieste PST o risultati operativi.

La UI continua a presentare esclusivamente termini leggibili e verificabili; un mancato riscontro del PST o del contenuto indicizzato resta un esito da presidiare, non un termine inventato.

## Aggiornamento 24/08/2026 — lettore interno dalla scelta deposito/notifica

Il lettore unico è stato provato nuovamente nella copia Docker reale
`http://127.0.0.1:8080`, fascicolo `DC5BF1DB`, partendo dal selettore
**Prepara deposito telematico**. Il click materiale su `Visualizza` del
`decretoLiquidazioneCTU.pdf` ha aperto il PDF reale nel lettore IUSENTRA sopra
il selettore, mantenendo il contesto del fascicolo. Il successivo click su
`Scarica` ha mostrato l'esito osservabile `Download avviato` con il nome del
file, senza `Failed to fetch`.

Lo stesso selettore è stato aperto per **Prepara notifica** e presenta i
documenti reali con il medesimo comando di anteprima; nessuna notifica,
deposito, firma o trasmissione PEC è stata avviata durante la prova. La prova
copre il lettore interno e l'azione di download locale; non sostituisce i
collaudi successivi della firma, della busta o dell'invio dal PC dell'avvocato.

## Aggiornamento 24/08/2026 — cronologia derivata dal contenuto

Le attività che derivano dal contenuto indicizzato di un documento non sono
azioni pendenti dello studio. Nella superficie React la riga è pertanto
esplicitamente in sola lettura: mostra tipo, titolo `… rilevata dal documento`,
fonte apribile e passaggio letto, senza selettore di esito, `Salva` o
`Elimina`. Il modulo separato di inserimento manuale conserva invece gli stati
gestibili perché rappresenta attività create dall'avvocato.

La modifica non altera deposito, firma, notifica, catalogazione, dati SQL o
connettori PST/PolisWeb. È stata provata nella copia Docker reale
`http://127.0.0.1:8080`, fascicolo `DC5BF1DB`, con consultazione visiva della
cronologia e senza alcuna mutazione di eventi o documenti.

## Aggiornamento 24/08/2026 — udienze e scadenze derivate dal contenuto

Nel **Presidio documenti fascicolo** della sezione **Udienze e scadenze** ogni
proposta con una data leggibile espone ora la fonte reale nel lettore interno e
un collegamento che apre il modulo React di nuova scadenza già compilato. Il
collegamento non registra alcuna scadenza: l'avvocato verifica il documento e
conferma solo dal salvataggio esplicito del modulo. Per proposte dipendenti
dalla data di comunicazione resta invece visibile il vincolo, senza calcolo
fittizio.

La prova materiale sulla copia Docker `http://127.0.0.1:8080`, fascicolo
`DC5BF1DB`, ha aperto la fonte PDF interna e poi il modulo Scadenziario con
data, tipo, fascicolo, descrizione e nota della fonte precompilati. Nessun
evento o scadenza è stato creato durante il collaudo.
