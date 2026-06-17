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
| Programmazione | Calcolatore termini processuali e audit | R/W | R/W | R/W | parita' completa | Wave 2 - core operativo | template, audit SHA-256, calendario e promemoria PEC hanno schema JSON/SQLite/PostgreSQL; JSON solo bootstrap controllato |
| Produzione atti | Template atti e preferenze editor | R/W | R/W | R/W | parita' completa | Wave 3 - workspace professionali | JSON come export/bootstrap controllato dei layout editor |
| Produzione atti | Editor AI e generazione atti Lex | R/W | R/W | R/W | schema governato | Wave 3 - workspace professionali | JSON tenant-aware in `editor_ai/editor_ai.json` come fallback esplicito; metadati, versioni, fonti, proposte e audit su SQLite/PostgreSQL con `pct/sql/20260505_editor_ai*.sql`; documento finale sempre nel repository fascicolo |
| Operativita' | Timesheet e valorizzazione attivita' | R/W | R/W | R/W | parita' completa | Wave 4 - economico | JSON solo come bootstrap o import storico |
| Operativita' | Timer attivita top bar | R/W | R/W | R/W | schema governato | Wave 4 - economico | JSON tenant-aware in `timesheet/time_tracking.json`; SQLite/PostgreSQL predisposti in `pct/sql/20260505_topbar_time_tracking*.sql`; allo stop crea voce timesheet reale |
| Operativita' | Centro notifiche e Web Push | - | R/W | R/W | schema governato | Wave 4 - operativo | repository tenant-aware in `NOTIFICATIONS_DB`, default `notifications/notifications.db`; SQLite/PostgreSQL predisposti in `pct/sql/20260512_notifications*.sql`; payload push sempre privacy-safe e senza dati sensibili |
| Commerciale | Preventivi e workflow commerciale | R/W | R/W | R/W | parita' completa | Wave 4 - economico | SQLite/PostgreSQL tenant-aware; JSON solo come ponte di migrazione |
| Economico | Fatturazione, pagamenti e saldo cliente | R/W | R/W | R/W | parita' completa | Wave 4 - economico | cutover ufficiale con report di consistenza e nessun fallback invisibile |
| Operativita' fascicolo | Regia Operativa / Practice Engine | R/W | R/W | R/W | schema governato | Wave 3 - workspace professionali | JSON tenant-aware in `fascicoli/practice_engine/practice_engine.json`; SQLite/PostgreSQL predisposti in `pct/sql/20260504_practice_engine*.sql`; ricevute ed evidence pack su filesystem tenant |
| Operativita' fascicolo | Documenti AI Fascicolo | R/W | R/W | R/W | schema governato | Wave 3 - workspace professionali | JSON tenant-aware in `fascicoli/documenti_ai/documenti_ai.json` come fallback esplicito; repository persistente SQLite/PostgreSQL attivo con `pct/sql/20260505_documenti_ai*.sql`; file originali e testi estratti su filesystem tenant |
| Motori legali | Legal intelligence, monitoraggio e audit fonti | R/W | R/W | R/W | parita' completa | Wave 5 - intelligence | JSON tenant-aware come export/recovery, senza fallback invisibili |
| Motori legali | Giurisprudenza e corpus interno | R/W | R/W | R/W | parita' completa | Wave 5 - intelligence | JSON tenant-aware come export/import storico controllato |
| Motori legali | Update Intelligence, news e archivio normativo assistito | R/W | R/W | R/W | parita' completa | Wave 5 - intelligence | repository SQL applicativo condiviso da tutti gli studi, JSON solo come export amministrativo |
| Motori legali | Coverage AI, gap queue, draft v2 e publish SQL | - | R/W | R/W | parita' completa | Wave 5 - intelligence | pipeline SQL reale su archivio condiviso di piattaforma (`LEGAL_COVERAGE_SQLITE_DB` o PostgreSQL esplicito), senza fallback fittizi per-studio |
| Telematico | PST, PDP, PAT e PTT/SIGIT | R/W | R/W | R/W | parita' completa | Wave 3 - workspace professionali | metadati e repository su SQL/PostgreSQL, file e buste sempre su filesystem tenant |
| Telematico | Uffici giudiziari e PEC | R/W | R | R | schema governato, runtime cache JSON-first | Wave 3 - workspace professionali | cache JSON esplicita per continuita'; SQL/PostgreSQL predisposti in `pct/sql/20260430_uffici_giudiziari_pec*.sql`, senza fallback invisibile quando verra' attivato il repository tenant-aware |
| Comunicazioni | PEC audit-grade | - | R/W | R/W | schema governato | Wave 3 - workspace professionali | `pec_audit.sqlite` nella cartella email tenant; MIME originale BLOB, parsed JSON versionato, allegati/OCR/firme, validation report, link fascicolo, digest e audit append-only; PostgreSQL predisposto in `pct/sql/20260521_pec_audit_pipeline_postgres.sql` |
| Comunicazioni | PEC Control Tower e Lex AI | - | R/W | R/W | schema governato | Wave 3 - workspace professionali | `pec_control_tower.sqlite` nella cartella email tenant; ogni PEC diventa evento giuridico tracciato con ricevute, fascicolo, scadenze in bozza, agenda, task, notifiche, prove e audit HMAC; PostgreSQL predisposto in `pct/sql/20260606_pec_control_tower_postgres.sql` |
| Telematico | SIGP - Giudice di Pace | - | R/W | R/W | snapshot fascicolo e validazione XSD governati | Wave 3 - workspace professionali | sync autorizzata fascicolo/parti/eventi/udienze/documenti/comunicazioni su SQL; file XSD e future buste su filesystem tenant |
| Cabina intelligente | Workspace intelligence e cockpit | R/W | R/W | R/W | parita' completa | Wave 5 - intelligence | snapshot SQL/PostgreSQL con JSON come export derivato |
| Piattaforma | Assistenza remota cliente e audit sessioni | - | R/W | R/W | parita' completa | Wave piattaforma | repository SQL/PostgreSQL dedicato, nessun fallback invisibile |
| Web pubblico studio | Sito Studio, pagine, articoli, sedi, contatti e prenotazioni | - | R/W | R/W | parita' completa | Wave web studio | repository SQL/PostgreSQL dedicato; asset su filesystem tenant; sezioni pubbliche opzionali governate da flag |
| AI locale | Runtime locale, modelli e RAG | - | R/W | - | non attiva | Fuori scope come backend primario | SQLite locale e filesystem sullo stesso host del runtime |
| AI locale | Local Deep Research sidecar e SearXNG | - | R/W sidecar | - | fuori parity IUSENTRA | Fuori scope come backend primario | dati runtime sotto `${IUSENTRA_DATA_DIR:-./data}/local-deep-research` e `${IUSENTRA_DATA_DIR:-./data}/searxng`; credenziali solo in env locale; nessun fallback su dati fascicolo |

## Verita' operativa oggi

- La pagina `admin/governance` separa sempre due livelli:
  - `capability tecnica della piattaforma`, cioe' quali domini hanno parity R/W disponibile su SQLite o PostgreSQL;
  - `backend strutturato effettivo dello studio`, cioe' quale database governa davvero tutti i dati strutturati tenant-aware del tenant selezionato.
- `selected_mode = POSTGRESQL` senza attivazione non basta: il backend effettivo resta quello dichiarato nel manifest tenant.
- `effective_runtime_kind = postgresql` significa che i domini migrati stanno usando davvero PostgreSQL in produzione per quel tenant.
- `effective_runtime_kind = sqlite` significa che i dati strutturati tenant-aware dello studio stanno lavorando davvero su SQL locale tenant-aware.
- non esiste fallback silenzioso da PostgreSQL attivo a JSON: il runtime blocca l'operazione e lascia traccia nel log applicativo.
- documenti, buste telematiche e modelli locali AI restano filesystem-first anche dopo il cutover SQL.
- L'adapter Docling di Lex e' un parser opzionale in-memory attivato da `LEX_DOCLING_ENABLED=1`: produce metadati citabili per evidence pack e, quando si persiste RAG, deve confluire nelle tabelle `rag_documents`/`rag_chunks` del dominio `AI locale` senza creare fallback invisibili o sorgenti parallele.
- Local Deep Research e' un sidecar opzionale per ricerche pubbliche. I suoi dati applicativi restano nel data root scrivibile e non diventano fonte primaria IUSENTRA: Lex continua a usare retrieval tenant-aware per fascicoli, clienti, atti e documenti interni.
- i moduli economici condividono lo stesso percorso ufficiale di migrazione `JSON -> SQLite -> PostgreSQL` con report di consistenza; il compenso a tempo ex art. 22-bis D.M. 55/2014 e' persistito su preventivi, conferimenti, log economico e fatturazione con migrazioni SQLite/PostgreSQL dedicate.
- `Update Intelligence` e `Coverage AI` usano repository condivisi di piattaforma, per evitare scansioni, gap queue, review e publish duplicati tra studi.
- Lex AI consuma `Update Intelligence` dal repository SQL `legal_updates.db` condiviso; `legal_updates_repository.json` e `giurisprudenza.json` non sono sorgenti runtime e restano solo export/mirror espliciti.
- l'`Assistenza remota cliente` e' un dominio di piattaforma: sessioni, eventi, consensi ed escalation vivono nel repository SQL dedicato e non degradano su JSON.
- `Sito Studio` usa un repository SQL dedicato per tenant, mentre immagini e asset restano su filesystem tenant-aware; `strumenti legali`, `applicazioni` e `news giuridiche strutturate` vengono pubblicati solo quando il flag amministrativo del sito e' attivo.
- `Uffici giudiziari e PEC` resta runtime JSON-first per la cache storica degli uffici, ma ora ha schema SQLite/PostgreSQL esplicito e report di verifica con fonti PST/IPA distinte; il cutover R/W SQL richiede repository tenant-aware e job schedulato dedicato.
- `admin/database` esegue la verifica referenziale con riparazione automatica dei problemi risolvibili: prima della scrittura crea backup JSON, non crea record fittizi e, quando non trova un collegamento reale univoco, scollega il riferimento orfano conservando l'ID originale in note/metadati.
- `admin/database` non sovrascrive più un `studio.db` operativo con sorgenti JSON vuote o incomplete: la migrazione usa staging, precheck anti-perdita e validazione campo-per-campo prima di installare il database finale.
- Il cutover SQLite completo riesegue il mirror core dopo la sincronizzazione dei repository secondari, così i JSON generati da Legal Intelligence, Giurisprudenza, Workspace Intelligence, template e moduli analoghi finiscono anche in `moduli_json_records`.
- `timesheet/time_tracking.json` è un percorso tenant-aware ufficiale: il timer della top bar viene copiato dal bootstrap legacy, migrato in `time_tracking_timers`, contato nei report e portato nel cutover PostgreSQL.
- I moduli JSON monitorati da `admin/database` che non hanno ancora una tabella verticale dedicata sono comunque migrabili con struttura esplicita SQLite/PostgreSQL: `moduli_dati` registra percorso, backend e metadati; `moduli_json_records` conserva i record normalizzati per modulo. Le tabelle dedicate restano il target preferito per i domini core, ma Calendar Sync, Email, Soggetti, Portale, Template, Wizard, Intelligence e moduli analoghi non devono risultare "non migrabili" solo perche' sono JSON runtime.
- Lo snapshot SQLite mostrato da `admin/database` resta presente anche se una tabella tecnica derivata, come l'indice FTS `search_documenti`, non e' conteggiabile nel runtime corrente: la pagina mostra un avviso e conserva le statistiche delle altre tabelle invece di dichiarare assente l'intero database.
- Negli studi in modalita SQL la fonte di verita e' `studio.db` o PostgreSQL; i JSON tenant-aware sono solo mirror, bootstrap controllato, cache, archivio o import/export storico. Nessun conteggio operativo, audit conclusivo o riparazione massiva deve usare un JSON al posto del database quando SQL esiste.
- `scripts/audit_tenant_data_structure.py` censisce anche JSON operativi nascosti e famiglie dinamiche. I path `fascicoli/documenti_ai/**/*.json`, `fascicoli/importazioni/**/*.json` e `intelligence/lex_dataset/**/*.json` vengono trasformati in moduli SQL stabili dentro `moduli_dati` e `moduli_json_records`.
- Stato locale del 2026-06-16 sul tenant `tenant-8bf98719c459`: `source_of_truth=sqlite`, `json_authoritative=false`, 436 moduli `moduli_dati`, 7772 record `moduli_json_records`, 242 JSON classificati come cache/archivio e 0 JSON operativi non censiti.

## Baseline tenant obbligatoria

Ogni nuovo studio e ogni studio riparato dal superadmin esegue la baseline dati tenant: seed JSON con forma corretta, `studio.db`, `notifications.db`, tabelle core, agenda, scadenziario e mirror `moduli_dati`/`moduli_json_records` per tutti i JSON monitorati.

Il gate `python scripts/audit_tenant_data_structure.py --repair` deve uscire con codice `0`. Senza `--repair` deve fallire se manca un JSON, una tabella SQLite, una tabella notifiche, un record `moduli_dati`, un mirror `moduli_json_records` o lo schema PostgreSQL corrispondente. Questo controllo non crea backup o snapshot: corregge solo la struttura minima tenant-aware e verifica che ogni JSON previsto abbia il corrispondente presidio SQL.

## Check di consistenza minimi

- utenti attivi, ruoli e audit log coerenti
- clienti, codici fiscali ed email univoci invariati
- fascicoli, riferimenti cliente e metadati documentali coerenti
- appuntamenti, scadenze e riferimenti forti invariati
- template termini processuali, versioni regole/calendario e audit hashati invariati
- timesheet, preventivi, conferimenti, parcelle e link pagamento coerenti tra cliente e fascicolo
- fonti, staging, review queue, news, normative, giurisprudenza e prassi di `Update Intelligence` coerenti nell'archivio SQL condiviso di piattaforma
- snapshot, gap queue, draft e publish history di `Coverage AI` coerenti tra SQLite condiviso e PostgreSQL esplicito di piattaforma
- report di migrazione persistito sotto `backup/` del tenant
- audit severo con `scripts/audit_sqlite_migration_integrity.py` prima di dichiarare riuscito un recupero dati o un cutover su tenant reale
- audit struttura tenant con `scripts/audit_tenant_data_structure.py` prima di dichiarare chiusa una modifica che tocca JSON, SQLite, PostgreSQL, agenda, scadenziario, notifiche, PEC o creazione studi
