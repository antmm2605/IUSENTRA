# Matrice Storage e Read/Write Parity

## Obiettivo

Questa matrice formalizza lo stato reale dei backend per dominio applicativo.

Legenda:

- `R/W`: lettura e scrittura attive nel dominio
- `R`: sola lettura
- `-`: backend non attivo per quel dominio

## Matrice tecnica

| Dominio | Modulo | JSON | SQLite | PostgreSQL | Parita' PostgreSQL | Wave | Fallback |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Identita' | Autenticazione e audit | R/W | R/W | - | non attiva | Wave 1 - identita' e audit | JSON tenant-aware se `studio.db` e' vuoto o indisponibile |
| Core operativo | Clienti e condivisioni | R/W | R/W | - | non attiva | Wave 2 - core operativo | fallback automatico a JSON se SQLite non e' seedato |
| Core operativo | Fascicoli e documenti | R/W | R/W | - | non attiva | Wave 2 - core operativo | metadati su JSON/SQLite, documenti sempre su filesystem tenant |
| Programmazione | Agenda e sincronizzazione calendario | R/W | R/W | - | non attiva | Wave 2 - core operativo | JSON operativo se il runtime SQL locale non e' disponibile |
| Programmazione | Scadenziario | R/W | R/W | - | non attiva | Wave 2 - core operativo | fallback a JSON con guardia su riferimenti collegati |
| Produzione atti | Template atti e preferenze editor | R/W | R/W | - | non attiva | Wave 3 - workspace professionali | JSON per continuita' dei layout editor |
| Commerciale | Preventivi e workflow commerciale | R/W | - | - | non attiva | Wave 4 - economico | JSON tenant-aware come backend canonico corrente |
| Economico | Fatturazione e pagamenti | R/W | - | - | non attiva | Wave 4 - economico | JSON tenant-aware con report di consistenza pre-cutover |
| Motori legali | Legal intelligence, monitoraggio e audit fonti | R/W | - | - | non attiva | Wave 5 - intelligence | JSON tenant-aware con snapshot e audit trace locali |
| Motori legali | Giurisprudenza e corpus interno | R/W | - | - | non attiva | Wave 5 - intelligence | JSON tenant-aware come corpus canonico corrente |
| Telematico | PST, PDP, PAT e PTT/SIGIT | R/W | R/W | - | non attiva | Wave 3 - workspace professionali | metadati su JSON/SQLite, file e buste sempre su filesystem tenant |
| Cabina intelligente | Workspace intelligence e cockpit | R/W | - | - | non attiva | Wave 5 - intelligence | snapshot derivato su JSON fino a consolidamento dei domini sorgente |
| AI locale | Runtime locale, modelli e RAG | - | R/W | - | non attiva | Fuori scope come backend primario | SQLite locale e filesystem sullo stesso host del runtime |

## Read/Write parity reale oggi

- `JSON` e' il backend canonico per tutti i domini che non hanno ancora repository SQLite dedicato.
- `SQLite` e' chiuso in read/write parity per i domini core gia' agganciati a `StudioDB`.
- `PostgreSQL` e' oggi un backend **configurabile** a livello tenant, ma non ancora la sorgente attiva dei repository dominio per dominio.

In altre parole:

- `selected_mode = POSTGRESQL` indica intenzione infrastrutturale
- `effective_runtime_kind` resta oggi `json` o `sqlite` finche' il dominio non ha il repository PostgreSQL chiuso

## Regola di verita' operativa

Ogni claim commerciale o tecnico sul backend deve restare coerente con:

- `selected_mode`
- `runtime_kind`
- `effective_runtime_kind`
- stato della parity per singolo dominio

## Check consistenza minimi per wave

- Wave 1: utenti attivi, ruoli e audit log coerenti tra sorgente e destinazione
- Wave 2: conteggi clienti, fascicoli, appuntamenti, scadenze e riferimenti forti invariati
- Wave 3: id deposito, gruppi documentali e repository capability telematiche coerenti
- Wave 4: totale preventivato, fatturato, incassato e residui invariati
- Wave 5: motori, fonti, alert, snapshot e audit trace invariati
