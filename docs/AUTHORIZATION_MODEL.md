# Modello Autorizzativo

## Principi

- Separazione netta tra piattaforma multi-tenant e singolo studio
- Nessun accesso implicito alle superfici sensibili solo per vicinanza tecnica
- Telematico, AI, admin e audit sono superfici distinte
- Le policy devono essere verificabili da catalogo permessi, non da convenzioni implicite

## Ruoli

| Ruolo | Ambito | Note |
| --- | --- | --- |
| `SUPERADMIN` | piattaforma | vede tenant, puo configurare, impersonare e governare l'intera piattaforma |
| `AMMINISTRATORE` | tenant | governa lo studio, utenti, policy, storage e superfici admin del tenant |
| `AVVOCATO` | operativo alto privilegio | lavora su fascicoli, telematico, assistenti AI e processi operativi |
| `COLLABORATORE` | operativo | scrive sui domini operativi ma senza superfici amministrative |
| `PRATICANTE` | operativo controllato | lettura ampia, agenda e AI operativa, senza depositi |
| `SEGRETERIA` | front-office | anagrafiche, agenda, messaggi, lettura telematica |
| `CONTABILE` | economico | lettura fascicoli e funzioni economiche di controllo |

## Superfici sensibili

| Superficie | Permessi chiave | Rischio | Ruoli ammessi |
| --- | --- | --- | --- |
| Tenant e piattaforma | `tenant.leggi`, `tenant.configura`, `tenant.impersona` | critico | `SUPERADMIN` |
| Superfici admin | `admin.leggi`, `admin.configura`, `autorizzazioni.leggi`, `autorizzazioni.scrivi` | alto | `SUPERADMIN`, `AMMINISTRATORE` |
| Flussi telematici | `telematico.leggi`, `telematico.importa`, `telematico.valida`, `telematico.deposita` | critico | `SUPERADMIN`, `AMMINISTRATORE`, `AVVOCATO` |
| Assistenti AI | `ai.usa`, `ai.configura`, `ai.audit` | alto | `SUPERADMIN`, `AMMINISTRATORE` per configurazione; ruoli operativi per l'uso |
| Audit e compliance | `audit.leggi`, `audit.esporta` | alto | `SUPERADMIN`, `AMMINISTRATORE` |

## Regole

- `SUPERADMIN` non e' un ruolo di tenant: e' un ruolo di piattaforma
- la piattaforma governa un solo `SUPERADMIN` attivo come account radice operativo
- il `SUPERADMIN` usa una superficie dedicata `admin/utenti-piattaforma`, separata dagli utenti dei tenant
- nessuno studio puo' creare, importare o promuovere utenti `SUPERADMIN`
- in modalita' multi-tenant il `SUPERADMIN` legge e scrive sempre sulla persistenza auth di piattaforma, mai sul `studio.db` del tenant
- Le superfici admin di tenant non devono implicare impersonazione o visibilita' cross-tenant
- I depositi telematici devono restare separati dalla sola consultazione
- L'uso di Lex e degli assistenti non implica configurazione del runtime AI
- L'export dei log va trattato come superficie distinta dalla sola lettura audit
