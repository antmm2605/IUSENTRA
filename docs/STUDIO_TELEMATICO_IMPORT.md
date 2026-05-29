# Import pratiche da Studio Telematico

## Obiettivo

La funzione **Importa pratiche da Studio Telematico** consente allo studio di acquisire in IUSENTRA le pratiche provenienti dal vecchio gestionale installato nella postazione del cliente.

Il percorso è disponibile da:

`Amministrazione` -> `Importa pratiche da Studio Telematico`

L'operatore carica un pacchetto unico, controlla l'anteprima e avvia l'import solo dopo il riepilogo di completezza.

## Struttura sorgente attesa

La postazione del vecchio gestionale usa sempre questa struttura:

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
- un file `.mdb` caricato da solo permette il controllo dei dati, ma senza `ATTI` ed `EMAILS` l'acquisizione completa non è possibile.

## Pacchetto consigliato

Dalla pagina React è disponibile il comando **Prepara pacchetto**, che scarica lo script:

`web/static/tools/prepara_import_studio_telematico.ps1`

Sulla postazione del cliente lo script:

1. legge le tabelle operative da `QuickOrganizer.mdb`;
2. esporta i dati in `quickorganizer-export.json`;
3. copia integralmente `ATTI`;
4. copia integralmente `EMAILS`;
5. crea sul Desktop un file `IUSENTRA-StudioTelematico-<data>.zip`.

Lo script non legge la tabella `Accounts` e non trasferisce credenziali del vecchio gestionale.

## Cosa viene importato

| Origine | Destinazione IUSENTRA |
| --- | --- |
| `PRATICHE` | Fascicoli |
| `NOMI` | Anagrafiche soggetti |
| `TitolareID` della pratica | Cliente principale |
| `TAVOLA` | Parti del fascicolo |
| `TESTI` + file in `ATTI` | Documenti del fascicolo |
| `EMAILS` + file in `EMAILS` | Email collegate al fascicolo |
| `AGENDA` | Attività e appuntamenti del fascicolo |

Ogni pratica conserva `source_external_id = quickorganizer:<numero pratica>`, così un secondo import aggiorna la pratica già presente invece di duplicarla.

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

## Sicurezza e isolamento

- Gli endpoint sono sotto `/api/v1/ui/import/quickorganizer*`.
- L'accesso richiede profilo di amministrazione oppure permessi di scrittura su fascicoli e clienti.
- Ogni anteprima e ogni import scrivono un evento nel registro attività.
- Il pacchetto caricato viene messo in area temporanea tenant-aware sotto la cartella dati dello studio.
- Le scritture usano i repository esistenti di fascicoli, clienti e soggetti, rispettando deduplica e storage documentale già governati da IUSENTRA.

## Route e componenti

- UI React: `frontend/src/components/QuickOrganizerImportPage.tsx`
- Normalizzazione dati frontend: `frontend/src/quickOrganizerImportData.ts`
- Servizio import: `web/services/quickorganizer_import.py`
- Endpoint React: `web/blueprints/api_v1_react.py`
- Helper cliente: `web/static/tools/prepara_import_studio_telematico.ps1`
- Route governata: `/importa-pratiche-studio-telematico`
