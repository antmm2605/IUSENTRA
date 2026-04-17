# Piano di Migrazione Storage

## Obiettivo

Rendere esplicito il percorso `JSON / SQLite -> PostgreSQL` senza perdere fallback, audit e verifiche di consistenza.

## Fasi

### 1. Inventario e precheck

- censimento storage manifest per tenant
- verifica integrita' JSON
- freeze dei conteggi per dominio e dei timestamp di riferimento

Blocco:

- nessun cutover se `studio.db` e' vuoto ma i JSON legacy contengono dati
- nessun cutover se restano errori critici di integrita'

### 2. Mirror repository e read parity

- attivazione repository SQL per singolo dominio
- parita' in lettura su liste, dettaglio e statistiche
- nessuna scrittura canonica sul backend nuovo finche' la lettura non coincide

### 3. Shadow write e report di consistenza

- scritture parallele su backend corrente e backend nuovo
- conteggi per operazione
- checksum o signature dei payload serializzati

Rollback:

- al primo mismatch bloccante la scrittura resta canonica sul backend corrente

### 4. Cutover tenant per tenant

- passaggio del tenant solo dopo finestra stabile di osservazione
- smoke test applicativo completo subito dopo il cutover
- confronto headline governance prima/dopo

Rollback:

- ritorno immediato alla sorgente precedente se falliscono healthcheck o controlli di consistenza

## Check di consistenza minimi

- utenti attivi e per ruolo
- clienti e codici fiscali univoci
- fascicoli, `id_cliente` e documenti allegati
- appuntamenti, scadenze e riferimenti forti
- id deposito, gruppi per `id_deposito` e warning telematici
- preventivato, fatturato, incassato e residui
- motori legali, fonti, alert e audit trace

## Fallback ufficiali

- JSON tenant-aware resta fallback dei domini non ancora portati su repository SQL
- SQLite resta fallback locale dei domini core gia' chiusi su `StudioDB`
- filesystem tenant resta sorgente primaria per documenti, buste, upload e modelli locali AI
