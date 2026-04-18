# Matrice Storage e Read/Write Parity

## Obiettivo

Questa matrice descrive il backend reale per ciascun dominio e chiarisce dove la parita' R/W e' chiusa davvero.

Legenda:

- `R/W`: lettura e scrittura attive
- `R`: sola lettura
- `-`: backend non attivo

## Matrice tecnica

| Dominio | Modulo | JSON | SQLite | PostgreSQL | Parita' PostgreSQL | Wave | Fallback |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Identita' | Autenticazione e audit | R/W | R/W | R/W | parita' completa | Wave 1 - identita' e audit | nessun fallback invisibile quando PostgreSQL e' attivo |
| Core operativo | Clienti e condivisioni | R/W | R/W | R/W | parita' completa | Wave 2 - core operativo | SQLite o JSON solo come bootstrap controllato |
| Core operativo | Fascicoli e documenti | R/W | R/W | R/W | parita' completa | Wave 2 - core operativo | documenti sempre su filesystem tenant |
| Programmazione | Agenda e sincronizzazione calendario | R/W | R/W | R/W | parita' completa | Wave 2 - core operativo | SQLite resta fallback dichiarato solo prima del cutover |
| Programmazione | Scadenziario | R/W | R/W | R/W | parita' completa | Wave 2 - core operativo | JSON solo in bootstrap o fallback locale dichiarato |
| Produzione atti | Template atti e preferenze editor | R/W | R/W | R/W | parita' completa | Wave 3 - workspace professionali | JSON come export/bootstrap controllato dei layout editor |
| Operativita' | Timesheet e valorizzazione attivita' | R/W | R/W | R/W | parita' completa | Wave 4 - economico | JSON solo come bootstrap o import storico |
| Commerciale | Preventivi e workflow commerciale | R/W | R/W | R/W | parita' completa | Wave 4 - economico | SQLite/PostgreSQL tenant-aware; JSON solo come ponte di migrazione |
| Economico | Fatturazione, pagamenti e saldo cliente | R/W | R/W | R/W | parita' completa | Wave 4 - economico | cutover ufficiale con report di consistenza e nessun fallback invisibile |
| Motori legali | Legal intelligence, monitoraggio e audit fonti | R/W | R/W | R/W | parita' completa | Wave 5 - intelligence | JSON tenant-aware come export/recovery, senza fallback invisibili |
| Motori legali | Giurisprudenza e corpus interno | R/W | R/W | R/W | parita' completa | Wave 5 - intelligence | JSON tenant-aware come export/import storico controllato |
| Telematico | PST, PDP, PAT e PTT/SIGIT | R/W | R/W | R/W | parita' completa | Wave 3 - workspace professionali | metadati e repository su SQL/PostgreSQL, file e buste sempre su filesystem tenant |
| Cabina intelligente | Workspace intelligence e cockpit | R/W | R/W | R/W | parita' completa | Wave 5 - intelligence | snapshot SQL/PostgreSQL con JSON come export derivato |
| AI locale | Runtime locale, modelli e RAG | - | R/W | - | non attiva | Fuori scope come backend primario | SQLite locale e filesystem sullo stesso host del runtime |

## Verita' operativa oggi

- `selected_mode = POSTGRESQL` senza attivazione non basta: il backend effettivo resta quello dichiarato nel manifest tenant.
- `effective_runtime_kind = postgresql` significa che i domini migrati stanno usando davvero PostgreSQL in produzione per quel tenant.
- non esiste fallback silenzioso da PostgreSQL attivo a JSON: il runtime blocca l'operazione e lascia traccia nel log applicativo.
- documenti, buste telematiche e modelli locali AI restano filesystem-first anche dopo il cutover SQL.
- i moduli economici condividono lo stesso percorso ufficiale di migrazione `JSON -> SQLite -> PostgreSQL` con report di consistenza.

## Check di consistenza minimi

- utenti attivi, ruoli e audit log coerenti
- clienti, codici fiscali ed email univoci invariati
- fascicoli, riferimenti cliente e metadati documentali coerenti
- appuntamenti, scadenze e riferimenti forti invariati
- timesheet, preventivi, conferimenti, parcelle e link pagamento coerenti tra cliente e fascicolo
- report di migrazione persistito sotto `backup/` del tenant
