# Import pratiche da Studio Telematico

## Obiettivo

La funzione **Importa pratiche da Studio Telematico** consente allo studio di acquisire in IUSENTRA le pratiche provenienti dal vecchio gestionale installato nella postazione del cliente.

Il percorso è disponibile da:

`Amministrazione` -> `Importa pratiche da Studio Telematico`

L'operatore carica un pacchetto unico, controlla l'anteprima e avvia l'import solo dopo il riepilogo di completezza.

## Struttura sorgente attesa

La postazione del vecchio gestionale usa questa struttura:

```text
C:\QuickOrganizer\QuickOrganizer.mdb
C:\QuickOrganizer\ATTI
C:\QuickOrganizer\EMAILS
```

Le regole di lettura sono vincolanti:

- le pratiche e le anagrafiche vengono lette da `QuickOrganizer.mdb`;
- tutti i documenti del fascicolo vengono cercati nella cartella `ATTI`;
- le email collegate vengono cercate nella cartella `EMAILS`;
- la cartella `EMAILS` non deve essere rinominata e non sostituisce `ATTI`;
- un file `.mdb` caricato da solo permette il controllo dei dati, ma senza `ATTI` ed `EMAILS` l'acquisizione completa non è possibile;
- se lo ZIP contiene `QuickOrganizer.mdb`, IUSENTRA prova a leggere direttamente l'MDB su Windows tramite Jet/OleDB; se l'ambiente non lo consente, l'errore deve restare operativo e indicare l'uso del preparatore `.exe`.

## Pacchetto consigliato

Dalla pagina React è disponibile il comando **Prepara pacchetto**, che scarica il programma:

`web/static/tools/PreparaPacchettoStudioTelematico.exe`

Sulla postazione del cliente il programma:

1. legge le tabelle operative da `QuickOrganizer.mdb`;
2. esporta i dati in `quickorganizer-export.json`;
3. copia integralmente `ATTI`;
4. copia integralmente `EMAILS`;
5. crea sul Desktop un file `IUSENTRA-StudioTelematico-<data>.zip`.

Il programma non legge la tabella `Accounts` e non trasferisce credenziali del vecchio gestionale.

Il programma non deve produrre un JSON parziale: se non riesce a leggere `PRATICHE`, `NOMI`, `TAVOLA`, `TESTI`, `EMAILS` o `AGENDA`, oppure se mancano i campi minimi per ricostruire i collegamenti (`PRATICHE.NUMEROPRATICA`, `NOMI.NUM_NOM`, `NOMI.CONTROLLO`, `TAVOLA.NUMEROPRATICA`, `TAVOLA.NUM_NOM`), il pacchetto viene bloccato prima della creazione dello ZIP. Nel file `quickorganizer-export.json` viene salvata anche la sezione `validation`, con conteggi tabella e conteggi relazione, così l'audit può verificare che i collegamenti cliente/pratica non siano stati persi durante l'export.

## Preparazione assistita con caricamento automatico

Dal comando **Prepara pacchetto** la pagina crea una sessione sicura dello studio, scarica l'avviatore `AvviaImportStudioTelematico.cmd` e mostra una barra di avanzamento per:

1. ricerca della cartella `C:\QuickOrganizer`;
2. lettura di `QuickOrganizer.mdb`;
3. creazione dello ZIP con `quickorganizer-export.json`, `ATTI` ed `EMAILS`;
4. caricamento automatico a blocchi su IUSENTRA;
5. controllo automatico del pacchetto caricato;
6. import definitivo automatico solo se il controllo risulta completo.

Se Windows o il browser non eseguono automaticamente l'avviatore scaricato, l'operatore deve aprire `AvviaImportStudioTelematico.cmd` dalla cartella download. Da quel momento la pagina continua a ricevere gli aggiornamenti dalla postazione Studio Telematico e completa il controllo senza richiedere il caricamento manuale dello ZIP.

La sessione usa un token operativo generato dal server, inviato dal preparatore negli header delle chiamate locali e memorizzato lato server solo come digest. Il token non contiene tenant, studio o percorsi filesystem e scade automaticamente.

## Pacchetti grandi sul PC

Per archivi molto grandi l'operatore può indicare il percorso locale del file ZIP invece di caricarlo dal browser. Il percorso locale funziona solo quando il server IUSENTRA gira sullo stesso PC o vede lo stesso disco. In produzione remota, invece, va usato il caricamento del file oppure una procedura assistita di trasferimento sul server.

## Cosa viene importato

| Origine | Destinazione IUSENTRA |
| --- | --- |
| `PRATICHE` | Fascicoli |
| `NOMI` | Anagrafiche soggetti |
| `TitolareID` della pratica, oppure primo nominativo `CLI` collegato in `TAVOLA` quando `TitolareID` manca | Cliente principale |
| `TAVOLA` | Parti del fascicolo |
| `TESTI` + file in `ATTI` | Documenti del fascicolo |
| `EMAILS` + file in `EMAILS` | Email collegate al fascicolo |
| `AGENDA` | Attività e appuntamenti del fascicolo |

Il nome visibile dei documenti non viene ricavato dal nome del PDF o dal file fisico: per `TESTI` viene preso dal titolo presente nella tabella dati (`NOME_DOCUMENTO`, `NOME_ATTO`, `TITOLO` o campi descrittivi equivalenti), mentre per `EMAILS` viene preso dall'oggetto della riga email quando disponibile. Il nome file originale resta salvato in `nome_originale` e viene usato solo per reperire e conservare il file sorgente.

Ogni pratica conserva `source_external_id = quickorganizer:<numero pratica>`, così un secondo import aggiorna la pratica già presente invece di duplicarla.

Per i pacchetti preparati in `quickorganizer-export.json`, la pratica può non esporre `TitolareID`. In quel caso IUSENTRA risolve il cliente principale dalla tabella ponte `TAVOLA`, scegliendo il nominativo collegato con `NOMI.CONTROLLO = CLI` o `OWN`; tutti i nominativi `CLI` vengono importati anche nella rubrica clienti e restano parti `ASSISTITO` del fascicolo. Gli altri ruoli vengono mantenuti come parti processuali. Se una pratica non ha alcun collegamento `CLI`, viene creata una scheda cliente di recupero dalla pratica e l'audit finale la evidenzia, senza bloccare la conservazione del fascicolo.

## Persistenza SQL quando configurata

Se lo studio è configurato in SQLite o PostgreSQL, l'import non deve scrivere i dati core nei JSON. Prima dell'esecuzione viene verificato il runtime dei domini `clienti`, `fascicoli` e `soggetti`: se il profilo è SQL ma il backend strutturato non è disponibile, l'import viene bloccato con errore operativo e non viene avviato alcun fallback invisibile a JSON.

In modalità SQL i dati importati finiscono nelle tabelle strutturate:

- `clienti`;
- `fascicoli`;
- `soggetti`;
- `soggetti_parti`.

Il test di regressione `test_import_studio_telematico_sqlite_scrive_tabelle_core_senza_json` verifica che l'import Studio Telematico popoli realmente queste tabelle e non crei `clienti/anagrafica.json`, `fascicoli/fascicoli.json`, `soggetti/anagrafica.json` o `soggetti/parti.json`.

## Controlli prima della scrittura

L'anteprima mostra:

- numero pratiche;
- pratiche attive e archiviate;
- anagrafiche e collegamenti parte;
- documenti trovati in `ATTI`;
- email trovate in `EMAILS`;
- appuntamenti;
- primi file mancanti da recuperare.

Se mancano file indicati dal database, l'import completo viene bloccato. L'operatore può scegliere l'acquisizione parziale solo con conferma esplicita.

## Verifica reale del 30 maggio 2026

Sul pacchetto reale `C:\Users\antmm\Downloads\ATTI\QuickOrganizer.zip`, pari a circa 5,3 GB, IUSENTRA ha letto direttamente `QuickOrganizer.mdb` e ha prodotto questa anteprima:

- `324` pratiche, di cui `279` attive e `45` archiviate;
- `307` anagrafiche;
- `796` collegamenti parte;
- `8967` documenti trovati nella cartella `ATTI`;
- `29` appuntamenti;
- `4239` email indicate dal database ma non presenti come file nella cartella `EMAILS` del pacchetto.

L'import reale ha creato le pratiche e copiato `8950` documenti importabili. La differenza rispetto al conteggio anteprima è dovuta a righe `TESTI` del database non collegabili a una pratica o prive di nome file: quelle righe non possono diventare documenti di fascicolo senza inventare un collegamento.

## Sicurezza e isolamento

- Gli endpoint sono sotto `/api/v1/ui/import/quickorganizer*`.
- L'accesso richiede profilo di amministrazione oppure permessi di scrittura su fascicoli e clienti.
- Ogni anteprima e ogni import scrivono un evento nel registro attività.
- Il pacchetto caricato viene messo in area temporanea tenant-aware sotto la cartella dati dello studio.
- Nei caricamenti a blocchi la sessione viene rimossa solo dopo staging riuscito; se lo staging fallisce, il pacchetto ricomposto resta nell'area `_chunk_uploads` dello studio per audit e recupero operativo.
- Le scritture usano i repository esistenti di fascicoli, clienti e soggetti, rispettando deduplica e storage documentale già governati da IUSENTRA.

## Route e componenti

- UI React: `frontend/src/components/QuickOrganizerImportPage.tsx`
- Normalizzazione dati frontend: `frontend/src/quickOrganizerImportData.ts`
- Servizio import: `web/services/quickorganizer_import.py`
- Endpoint React: `web/blueprints/api_v1_react.py`
- Helper cliente: `web/static/tools/prepara_import_studio_telematico.ps1`
- Programma pubblico Windows: `web/static/tools/PreparaPacchettoStudioTelematico.exe`
- Route governata: `/importa-pratiche-studio-telematico`
