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
| Storage parity e migrazione | `admin/governance` | matrice R/W, fallback, wave di cutover |
| Audit accessi e ruoli | `admin/governance` | eventi audit, superfici presidiate, ruoli ammessi |
| Capability telematiche | Centro Servizi Telematici / Motori Legali | stato canali, fonti, warning, catalogo capability |
| Salute sistema | `admin/salute-sistema` | backup, OCR, provider locali, readiness deploy |

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
- deve avvisare se il runtime predefinito e' ancora `JSON`
- deve esporre un `messaggio operatore` leggibile, non solo un dettaglio tecnico
- deve suggerire un'azione concreta di presidio, non solo il sintomo
- deve mostrare `codice`, `famiglia`, `componente`, `soglia operativa` e `passi di remediation`

## Tassonomia minima attesa

| Famiglia | Esempi |
| --- | --- |
| `HTTP` | `HTTP_5XX_BUCKET` |
| `OCR` | `OCR_FAILED_JOBS`, `OCR_QUEUE_BACKLOG` |
| `WORKER` | `OCR_WORKER_STALLED` |
| `AI` | `LOCAL_AI_RUNTIME_DOWN` |
| `STORAGE` | `STORAGE_DEFAULT_JSON` |
| `PRODUCT` | `PRODUCT_CAPABILITY_GAP` |

## Output operatore atteso

Ogni alert deve tradurre la diagnostica in decisione operativa. Esempi:

- `HTTP_5XX_BUCKET`
  "Errore applicativo reale: apri subito i log del bucket indicato e ripeti lo smoke test della superficie coinvolta."
- `OCR_QUEUE_BACKLOG`
  "OCR rallentato: controlla worker, CPU e throughput prima che la coda continui a crescere."
- `OCR_WORKER_STALLED`
  "Worker OCR fermo: riporta il worker online prima di accumulare nuova arretratezza."
- `LOCAL_AI_RUNTIME_DOWN`
  "AI locale non disponibile: il prodotto resta operativo, ma Lex e i motori assistiti vanno usati solo dopo il ripristino del runtime."
- `STORAGE_DEFAULT_JSON`
  "Storage non ancora chiuso sul database: completa il cutover tenant-aware prima di considerare il backend stabile."

## Criterio di chiusura operativa

Una tranche osservabilita' e' chiusa solo quando:

- il payload runtime continua a rispondere anche in presenza di errori parziali
- la UI admin rende visibili degradi, severita' e rimedi
- esiste almeno un test che simula un degrado reale e ne verifica la resa
- il linguaggio resta italiano e non lascia dump incomprensibili come unica esperienza utente
