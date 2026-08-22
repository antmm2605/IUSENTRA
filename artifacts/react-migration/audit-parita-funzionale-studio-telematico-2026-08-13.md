# Audit funzionale comparativo del 13/08/2026

## Perimetro e fonte

- Applicazione di confronto installata: versione `26.021`.
- Sorgenti decompilati consultati: `D:\tmp\qo-decomp-codex-20260812`.
- Inventario: 4.465 file sorgente C#.
- La ricerca per nomi `Form`, `frm`, `Scheda` e `Wizard` ha individuato 90 candidati. Il numero comprende anche tipi generati e non equivale a 90 schermate operative distinte.
- Nessun riferimento al prodotto di confronto o dettaglio tecnico interno deve essere mostrato all'avvocato nell'interfaccia IUSENTRA.

## Copertura documentata

- Classificazione pratiche: 773 codici storici ancora attivi coincidono con il catalogo corrente; IUSENTRA comprende inoltre 245 codici ufficiali presenti negli XSD correnti. Sei codici storici non più attivi restano esclusi dalla selezione.
- Catalogo deposito: 270 tipi su 270 risultano censiti e sottoposti ai controlli di generazione e ruolo ministeriale già documentati negli artefatti del deposito.
- Schemi deposito: 20 famiglie `DatiAtto` su 20 e 50 namespace su 50 dispongono del profilo corrente e dei relativi XSD versionati.
- Strumenti operativi: 36 strumenti su 36 sono compilabili nella superficie React; la ricerca uffici per Comune è collegata al servizio reale.
- Ricerca codice oggetto: filtri per area, gruppo e registro; ricerca per codice o parole; caricamento progressivo; comando per mostrare tutti i risultati; vista a schermo intero.

## Prove materiali di questa campagna

- Copia reale locale: `http://127.0.0.1:8080`, container `iusentra-app` healthy.
- Pagina `Nuovo fascicolo`: 238 risultati di `Volontaria giurisdizione`, nessuna sovrapposizione nella vista ordinaria e 238 righe caricate nella vista a schermo intero.
- Pagina `Strumenti Forensi`: ricerca degli uffici di Palmi, 10 risultati leggibili e assenza di campi tecnici nel risultato.
- Il form del fascicolo è stato ripristinato e nessun fascicolo è stato creato.
- Nessun deposito, notifica o messaggio PEC è stato preparato o inviato durante questa campagna.

## Estensione registro fascicoli del 15/08/2026

- La tabella operativa espone 37 campi selezionabili, organizzati in Pratica, Procedimento, Persone e Controlli; Riferimento e Titolo / oggetto restano sempre presenti.
- Sono disponibili le composizioni Essenziali, Procedimento, Persone e Tutte, oltre alla selezione puntuale e alle densità Compatta e Adattiva.
- Colonne e densità sono salvate nelle preferenze dello studio insieme ai filtri; i valori non riconosciuti vengono esclusi dal servizio prima della persistenza.
- La tabella economica resta separata: mantiene le sei colonne economiche e non mostra il selettore delle colonne operative.
- Prova reale su `http://127.0.0.1:8080`, viewport 1146 x 912: il criterio `Anno e numero RG` è interamente leggibile, la barra non presenta overflow e le azioni Filtri, Salva vista e Aggiorna fascicoli restano accessibili.
- Nel selettore sono state contate 37 caselle; la composizione Procedimento con Annotazioni ha prodotto 11 colonne reali e la densità Adattiva è stata applicata alla tabella.
- Dopo il salvataggio e il ritorno a `/fascicoli`, la vista Operativa ha ripristinato `Anno e numero RG`, otto colonne essenziali e righe compatte.

## Limite dichiarativo

Le verifiche sopra certificano soltanto le aree e le matrici nominate. Non costituiscono una dichiarazione generica di identità dell'intero prodotto: ogni ulteriore flusso viene considerato equivalente solo dopo confronto documentale, guardrail automatici e prova materiale sulla copia reale dell'utente.
## Aggiornamento del 17/08/2026

### Inventario e contratti

- L'inventario decompilato resta la fonte comparativa: 1.428 percorsi funzionali, 1.015 azioni uniche e 413 ricorrenze conservate come prova.
- Tutti i 1.428 percorsi dispongono ora di un contratto esplicito verso route, componente, API o comportamento locale IUSENTRA; le voci senza contratto sono zero.
- La matrice non promuove automaticamente la mappatura a equivalenza: 30 percorsi hanno prova materiale registrata, 1.032 sono presenti da provare e 366 restano parziali.
- I gruppi parziali principali sono i comandi avanzati dell'editor e del menu generale; restano inoltre espliciti ricampionamento immagini e scheda immigrazione. Non sono dichiarati conformi.

### Strumenti documentali aggiunti

- Nuova superficie React `/strumenti-documentali` per unire PDF, creare archivi ZIP e produrre PDF multipagina con ordinamento e rotazione.
- Gli originali non vengono modificati. L'elaborazione avviene in memoria; il salvataggio nel fascicolo richiede un comando esplicito ed è tenant-aware.
- L'acquisizione scanner parte esclusivamente dal PC Windows in uso tramite Local Signer, endpoint loopback `/scanner/acquire`; nessun contenuto dello scanner viene acquisito dal server.
- Il Local Signer è stato aggiornato alla versione `1.6.114`; il PIN e i dati dei dispositivi di firma restano fuori da questo flusso.

### Verifiche automatiche

- `python -m pytest tests/test_document_tools.py tests/test_local_signer.py tests/test_functional_parity_audit.py tests/test_notiziario_react.py -q`
- `npm run typecheck`
- Rigenerazione di `audit-parita-funzionale-comandi.json` e `audit-parita-funzionale-comandi.md`.
- Controlli coperti: ordine e pagine PDF, rotazione, nomi ZIP, limiti upload, route API, distribuzione Local Signer, acquisizione WIA simulata e guardrail zero voci non mappate.

### Prova reale

La prova automatica non sostituisce il collaudo materiale. La nuova superficie, i download, il salvataggio nel fascicolo e l'apertura del selettore WIA devono essere cliccati sulla copia reale `http://127.0.0.1:8080`. L'acquisizione completa richiede uno scanner Windows realmente collegato. Fino a tale prova queste funzioni restano presenti da provare e non vengono dichiarate verificate.
