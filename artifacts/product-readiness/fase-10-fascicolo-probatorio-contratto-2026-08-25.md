# Fase 10 — Fascicolo probatorio: riscontri operativi e fonti apribili

- Stato: analisi e contratto prima dell'implementazione.
- Data: 25/08/2026, Europa/Roma.
- Ambito: copia locale reale `http://127.0.0.1:8080`, Fascicoli React e dati
  tenant-aware dello studio.

## Problema osservato

Il lettore e il download dei documenti registrano già una traccia tecnica,
mentre il pannello **Audit del fascicolo** legge soltanto il registro
probatorio WORM e gli eventi della regia. Una consultazione reale può quindi
non comparire nel pannello e l'avvocato vede `Nessuna evidenza` pur avendo
aperto un documento: non è un risultato operativo accettabile.

## Decisione di implementazione

Ogni consultazione e download effettivi nel lettore interno devono scrivere un
evento nel registro operativo del fascicolo, fonte SQL già usata dalla Regia.
L'evento conserva solo dati minimizzati: azione, identificativo documento,
nome leggibile, attore e data/ora. Nel payload React l'evento espone un unico
comando **Apri documento** che riapre la fonte interna, senza URL esterni e
senza duplicare il contenuto del file.

Il registro operativo non viene presentato come firma, conservazione WORM,
marca temporale o prova di deposito. Quei requisiti restano nel presidio
probatorio separato e continuano ad essere dichiarati soltanto se realmente
configurati e verificabili.

## Modello e sicurezza

- Nessuna nuova tabella: `practice_audit_events` è la fonte SQL esistente,
  tenant-aware, con migrazioni SQLite e PostgreSQL già in parità; il JSON è
  solo mirror rigenerabile.
- Le route dei documenti ricevono il repository della Regia dal runtime core e
  registrano l'evento soltanto dopo aver risolto il documento autorizzato.
- Il fallimento della sola traccia non sostituisce né maschera un errore di
  lettura o download; viene registrato nel log server senza impedire la
  fruizione del file già autorizzata.
- Il nome e l'identificativo sono trattati come metadati già presenti nel
  fascicolo; nessun testo estratto, dato anagrafico o contenuto integrale è
  copiato nell'audit.

## Superficie React

Nel dettaglio **Audit** ogni riga operativa mostrerà la natura del riscontro,
la data italiana, l'autore e, quando esiste una fonte documentale, il comando
esplicito **Apri documento**. La lista non crea un nuovo pannello concorrente
al Presidio del fascicolo: ne alimenta il controllo `Audit del fascicolo`.

## Verifiche obbligatorie

1. test repository con SQLite e PostgreSQL per i payload operativi;
2. test route di visualizzazione e download, compresa autorizzazione e
   mancata duplicazione del contenuto;
3. typecheck e build React; test del bridge e dell'interfaccia audit;
4. browser reale: aprire e scaricare un documento controllato, ricaricare il
   dettaglio e verificare che il riscontro compaia con fonte apribile;
5. scroll, hover, focus e resa desktop/tablet/mobile; commit, push, deploy
   Hetzner, container unico healthy e readiness pubblica.

## Esito di implementazione prima del rilascio

- Le route `visualizza` e `scarica` registrano rispettivamente `DOC_VIEWED` e
  `DOC_DOWNLOADED` nella fonte SQL `practice_audit_events`. Il bridge React
  conserva messaggio, autore, data, identificativo e nome del documento.
- Ogni riga operativa con documento espone **Apri documento** e riapre il
  lettore interno della stessa fonte. I riscontri operativi non alimentano i
  contatori di firma, WORM, snapshot o marca temporale del presidio
  probatorio.
- Il download del lettore usa la route interna autorizzata del browser, senza
  passare da `fetch` e blob. Restano così validi il `Content-Disposition`, il
  nome restituito dal server e la registrazione del download nell'audit.
- L'orario dell'audit è presentato nel formato italiano, senza etichette
  tecniche di fuso nella UI.

## Verifiche eseguite prima del deploy

- SQLite: visualizzazione e download di `decreto-fonte.pdf` hanno prodotto i
  due riscontri e i relativi URL interni nel payload React.
- PostgreSQL isolato: `PracticeEngineRepository` ha scritto e riletto
  `DOC_VIEWED` con payload documentale; la struttura persistente resta in
  parità con SQLite.
- Test automatici mirati: 12 test in
  `tests/test_fascicolo_detail_ux.py`, inclusa la regressione sul download
  nativo, e 7 test in `tests/test_practice_engine_sql_source.py`.
- Compatibilità del lettore: 3 test mirati su PDF/P7M, PDF mobile e formati
  professionali supportati.
- Frontend: typecheck TypeScript e build Vite superati.
- Copia locale reale `127.0.0.1:8080`: apertura della fonte interna,
  visualizzazione del testo, download nativo osservato dal browser, riga
  `Documento scaricato: comunicazione.txt`, comando `Apri documento` e
  riapertura della fonte verificati con click effettivi. La data mostrata è
  `25/08/2026 12:33`, senza suffissi tecnici.

## Stato di rilascio

Rilasciata il 25/08/2026 con i commit `8ccd7479a` e `4f4780e42`, pubblicati
sia sul branch Codex sia sul branch gemello. Hetzner è stato aggiornato allo
stesso commit: un solo container applicativo `iusentra-app` risulta healthy e
la readiness pubblica `https://app.iusentra.it/api/pronto` risponde
correttamente. La cache di build del deploy e l'eventuale snapshot temporaneo
sono stati rimossi senza toccare i dati applicativi.
