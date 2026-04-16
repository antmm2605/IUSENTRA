# Matrice Storage

## Obiettivo

Questa matrice distingue, per ogni area applicativa, tra:

- backend effettivo oggi utilizzabile in produzione
- compatibilità già presente ma non ancora completata
- stato target per rollout cloud o multi-tenant avanzato

## Legenda

- `Pronto`: backend già usabile nel flusso reale del modulo
- `Compatibile`: wiring e strategia presenti, ma migrazione non ancora completa
- `Target`: direzione dichiarata, non ancora da presentare come backend operativo completo

## Matrice

| Modulo | JSON | SQLite | PostgreSQL | Note |
| --- | --- | --- | --- | --- |
| Autenticazione e audit | Pronto | Compatibile | Target | Runtime attuale centrato su file tenant-aware; evoluzione verso backend transazionale esterno prevista. |
| Clienti e condivisioni | Pronto | Compatibile | Target | Flussi consolidati su file JSON; SQLite già supportato come strategia di studio. |
| Fascicoli e documenti | Pronto | Compatibile | Target | Core operativo reale su storage locale; passaggio a backend esterno da completare per il dominio documentale. |
| Agenda e calendar sync | Pronto | Compatibile | Target | Scheduling e sincronizzazione usano percorsi tenant-aware già coerenti con strategia studio. |
| Scadenziario | Pronto | Compatibile | Target | Stato vicino al core operativo, ma ancora prevalentemente JSON/SQLite-first. |
| Template atti | Pronto | Compatibile | Target | Repository e preferenze già separati; PostgreSQL non va ancora presentato come backend pienamente migrato. |
| Preventivi e workflow commerciale | Pronto | Compatibile | Target | Runtime stabile su file; strategia esterna prevista insieme al resto del dominio economico. |
| Fatturazione e pagamenti | Pronto | Compatibile | Target | Dominio produttivo ma ancora orientato a storage locale governabile. |
| Legal intelligence | Pronto | Compatibile | Target | Snapshot, monitoraggio, audit e tabelle normative sono effettivi su JSON; migrazione esterna progressiva. |
| Giurisprudenza | Pronto | Compatibile | Target | Archivio e corpus sono già governati per tenant; rollout transazionale ancora incrementale. |
| Telematico / PST / PDP / PAT | Pronto | Compatibile | Target | Repository e workflow vivono su storage locale coerente col tenant; backend esterno ancora non dichiarabile come completo. |
| Workspace intelligence | Pronto | Compatibile | Target | Snapshot e indicatori già reali su file tenant-aware. |
| Local AI e RAG locale | Pronto | Compatibile | Non previsto come primario | Il runtime locale resta vicino ai dati del cliente; PostgreSQL non è il backend primario per embeddings e modelli locali. |

## Regola commerciale e tecnica

Quando si descrive lo stato del prodotto all’esterno:

- `JSON` e `SQLite` possono essere dichiarati backend effettivi
- `PostgreSQL` va presentato come strategia configurabile e direzione di rollout, non come copertura totale già chiusa su tutti i moduli
- ogni claim deve restare coerente con `selected_mode` e `effective_runtime_kind` del tenant
