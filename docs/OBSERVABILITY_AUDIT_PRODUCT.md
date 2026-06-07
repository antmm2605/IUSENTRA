# Observability e Audit come Capability di Prodotto

## Punto di arrivo

Osservabilita' non significa solo metriche runtime. Nel prodotto devono esistere anche:

- visibilita' sullo stato storage e sulla parity di migrazione
- controllo delle superfici autorizzative
- audit degli accessi e delle azioni sensibili
- capability operative telematiche e AI leggibili dal pannello admin

## Capability attive

| Capability | Superficie | Output |
| --- | --- | --- |
| Metriche runtime HTTP e Lex | `admin/osservabilita` | latenze, p95, bucket endpoint, first token |
| Storage parity e migrazione | Piattaforma superadmin: `admin/governance` | matrice R/W, fallback, wave di cutover |
| Storage operativo per studio | `admin/server-manutenzione` | categorie consumo, cartelle pesanti, file principali, scansione rapida con dettaglio parziale dichiarato, azioni analisi/compattazione |
| Audit accessi e ruoli | Piattaforma superadmin: `admin/governance` | eventi audit, superfici presidiate, ruoli ammessi |
| Audit probatorio WORM | Fascicolo: tab `Audit`, endpoint `/audit/*`, bundle fascicolo | envelope firmati in WORM, catena hash, snapshot Merkle, proof offline |
| Capability telematiche | Centro Servizi Telematici / Motori Legali | stato canali, fonti, warning, catalogo capability |
| Archivio legale verificato | `admin/pianificazioni`, `admin/aggiornamenti-legali` | documenti letti, analisi, schede pubblicate, evidenze web, allegati ufficiali, esecuzioni da completare |
| Salute sistema | Piattaforma superadmin: `admin/salute-sistema`, `admin/system-health` | backup, OCR, provider locali, readiness deploy |
| Crash test operativo | `admin/crash-test-operativo` | checklist finale `si/no`, ticket di riparazione, backup blindato, esito per fase |
| Assistenza remota pronta | `admin/supporto-remoto` | link cliente firmato, stanza operatore, schermo/audio con consenso, chat e audit |

## Aggiornamento operativo 2026-06-07

La salute sistema e l'osservabilità non devono più mostrare stime vuote o pannelli senza decisione operativa. Il superadmin deve poter vedere disco reale, studi attivi, aree globali, backup/mirror, log e dati Normattiva duplicati, quindi applicare manutenzione governata senza intervenire a mano sul server.

La Scorecard Lex non è considerata misura se mostra solo il catalogo dei casi. Deve indicare quante prove reali sono state eseguite, quante sono passate/fallite, percentuale di risposte con fonti utili, tempo medio risposta e percorso del file risultati. In assenza di risultati reali, il pannello deve dire `non misurata` e non dichiarare copertura.

## Regole

- ogni superficie sensibile deve avere una lettura prodotto, non solo log tecnici
- i dati di audit devono essere esportabili in modo governato
- il pannello admin deve mostrare sia `runtime` sia `product capability`
- la vista `admin/governance` deve distinguere in modo esplicito tra `capability della piattaforma` e `backend strutturato effettivo dello studio`
- il deploy non e' chiuso se metriche, audit e storage manifest raccontano storie diverse

## Failure handling richiesto

La vista `admin/osservabilita` non deve limitarsi a mostrare numeri:

- deve evidenziare gli endpoint con errori `5xx`
- deve segnalare backlog o errori OCR
- deve distinguere backlog OCR da worker OCR fermo
- deve dichiarare quando il runtime AI locale non e' operativo
- deve dichiarare quando la sincronizzazione PEC/IMAP entra in circuito aperto dopo errori ripetuti
- deve dichiarare quando ricerca o anteprima dei portali telematici entrano in circuito aperto dopo errori ripetuti
- deve dichiarare quando gli aggiornamenti legali leggono riferimenti ma non producono evidenze web, allegati o schede pubblicate
- deve permettere l'annullamento governato dei controlli fonte legale rimasti in corso oltre il tempo operativo, lasciando traccia nel registro scheduler
- deve avvisare se il runtime predefinito e' ancora `JSON`
- deve esporre un `messaggio operatore` leggibile, non solo un dettaglio tecnico
- deve offrire anche un endpoint JSON operativo (`/admin/system-health`) con stato sintetico di scheduler, OCR, AI e backend database
- deve suggerire un'azione concreta di presidio, non solo il sintomo
- deve mostrare `codice`, `famiglia`, `componente`, `soglia operativa` e `passi di remediation`
- il `crash test operativo` deve riusare questi segnali e tradurli in ticket di riparazione senza richiedere lettura dei log applicativi
- i log applicativi devono essere strutturati e mascherare automaticamente CF, email, IBAN, telefoni e altri identificativi sensibili
- `server-manutenzione` deve spiegare lo spazio per studio senza sommare due volte tenant e aree globali
- `server-manutenzione` deve proteggere il caricamento con limiti di file/tempo configurabili e segnalare quando il dettaglio iniziale e' parziale; l'analisi completa resta una scelta esplicita sul singolo studio o sull'area da manutenere
- `supporto-remoto` deve partire senza configurazioni preliminari; relay reti difficili e controllo avanzato esterno sono ottimizzazioni, non blocchi della sessione base

## Tassonomia minima attesa

| Famiglia | Esempi |
| --- | --- |
| `HTTP` | `HTTP_5XX_BUCKET` |
| `OCR` | `OCR_TIMEOUT`, `OCR_QUEUE_OVERFLOW` |
| `WORKER` | `OCR_WORKER_STALLED` |
| `AI` | `AI_MODEL_UNAVAILABLE` |
| `COMUNICAZIONI` | `IMAP_CIRCUIT_OPEN` |
| `TELEMATICO` | `PORTAL_CIRCUIT_OPEN` |
| `STORAGE` | `TENANT_DB_ERROR` |
| `MIGRATION` | `MIGRATION_FAILED` |

## Output operatore atteso

Ogni alert deve tradurre la diagnostica in decisione operativa. Esempi:

- `HTTP_5XX_BUCKET`
  "Errore applicativo reale: apri subito i log del bucket indicato e ripeti lo smoke test della superficie coinvolta."
- `OCR_QUEUE_OVERFLOW`
  "OCR rallentato: controlla worker, CPU e throughput prima che la coda continui a crescere."
- `OCR_WORKER_STALLED`
  "Worker OCR fermo: riporta il worker online prima di accumulare nuova arretratezza."
- `AI_MODEL_UNAVAILABLE`
  "AI locale non disponibile: il prodotto resta operativo, ma Lex e i motori assistiti vanno usati solo dopo il ripristino del runtime."
- `IMAP_CIRCUIT_OPEN`
  "PEC temporaneamente sospesa: verifica server, rete o credenziali prima di rilanciare aggiorna o auto-esiti."
- `PORTAL_CIRCUIT_OPEN`
  "Portale telematico sospeso: controlla certificati, rete o canale ufficiale prima di rilanciare ricerca o anteprima."
- `TENANT_DB_ERROR`
  "Storage non ancora chiuso sul database: completa il cutover tenant-aware prima di considerare il backend stabile."

## Criterio di chiusura operativa

Una tranche osservabilita' e' chiusa solo quando:

- il payload runtime continua a rispondere anche in presenza di errori parziali
- la UI admin rende visibili degradi, severita' e rimedi
- esiste almeno un test che simula un degrado reale e ne verifica la resa
- il linguaggio resta italiano e non lascia dump incomprensibili come unica esperienza utente
- il crash test operativo riesce a trasformare il degrado in report persistito, ticket di riparazione e backup blindato prima del nuovo tentativo
