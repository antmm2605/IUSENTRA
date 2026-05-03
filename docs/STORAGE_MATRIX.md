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
| Operativita' | Timesheet e valorizzazione attivita' | R/W | R/W | R/W | parita' completa | Wave 4 - economico | JSON solo come bootstrap o import storico |
| Commerciale | Preventivi e workflow commerciale | R/W | R/W | R/W | parita' completa | Wave 4 - economico | SQLite/PostgreSQL tenant-aware; JSON solo come ponte di migrazione |
| Economico | Fatturazione, pagamenti e saldo cliente | R/W | R/W | R/W | parita' completa | Wave 4 - economico | cutover ufficiale con report di consistenza e nessun fallback invisibile |
| Motori legali | Legal intelligence, monitoraggio e audit fonti | R/W | R/W | R/W | parita' completa | Wave 5 - intelligence | JSON tenant-aware come export/recovery, senza fallback invisibili |
| Motori legali | Giurisprudenza e corpus interno | R/W | R/W | R/W | parita' completa | Wave 5 - intelligence | JSON tenant-aware come export/import storico controllato |
| Motori legali | Update Intelligence, news e archivio normativo assistito | R/W | R/W | R/W | parita' completa | Wave 5 - intelligence | repository SQL/PostgreSQL dedicato, JSON solo come export amministrativo |
| Motori legali | Coverage AI, gap queue, draft v2 e publish SQL | - | R/W | R/W | parita' completa | Wave 5 - intelligence | pipeline SQL reale su `studio.db` o PostgreSQL tenant-aware, senza fallback fittizi |
| Telematico | PST, PDP, PAT e PTT/SIGIT | R/W | R/W | R/W | parita' completa | Wave 3 - workspace professionali | metadati e repository su SQL/PostgreSQL, file e buste sempre su filesystem tenant |
| Telematico | Uffici giudiziari e PEC | R/W | R | R | schema governato, runtime cache JSON-first | Wave 3 - workspace professionali | cache JSON esplicita per continuita'; SQL/PostgreSQL predisposti in `pct/sql/20260430_uffici_giudiziari_pec*.sql`, senza fallback invisibile quando verra' attivato il repository tenant-aware |
| Telematico | SIGP - Giudice di Pace | - | R/W | R/W | snapshot fascicolo e validazione XSD governati | Wave 3 - workspace professionali | sync autorizzata fascicolo/parti/eventi/udienze/documenti/comunicazioni su SQL; file XSD e future buste su filesystem tenant |
| Cabina intelligente | Workspace intelligence e cockpit | R/W | R/W | R/W | parita' completa | Wave 5 - intelligence | snapshot SQL/PostgreSQL con JSON come export derivato |
| Piattaforma | Assistenza remota cliente e audit sessioni | - | R/W | R/W | parita' completa | Wave piattaforma | repository SQL/PostgreSQL dedicato, nessun fallback invisibile |
| Web pubblico studio | Sito Studio, pagine, articoli, sedi, contatti e prenotazioni | - | R/W | R/W | parita' completa | Wave web studio | repository SQL/PostgreSQL dedicato; asset su filesystem tenant; sezioni pubbliche opzionali governate da flag |
| AI locale | Runtime locale, modelli e RAG | - | R/W | - | non attiva | Fuori scope come backend primario | SQLite locale e filesystem sullo stesso host del runtime |

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
- i moduli economici condividono lo stesso percorso ufficiale di migrazione `JSON -> SQLite -> PostgreSQL` con report di consistenza; il compenso a tempo ex art. 22-bis D.M. 55/2014 e' persistito su preventivi, conferimenti, log economico e fatturazione con migrazioni SQLite/PostgreSQL dedicate.
- anche `Update Intelligence` e `Coverage AI` rientrano nello stesso programma ufficiale di migrazione, con repository SQL locale e replica PostgreSQL tenant-aware.
- Lex AI consuma `Update Intelligence` dal repository SQL/PostgreSQL `legal_updates.db`; `legal_updates_repository.json` e `giurisprudenza.json` non sono sorgenti runtime e restano solo export/mirror espliciti.
- l'`Assistenza remota cliente` e' un dominio di piattaforma: sessioni, eventi, consensi ed escalation vivono nel repository SQL dedicato e non degradano su JSON.
- `Sito Studio` usa un repository SQL dedicato per tenant, mentre immagini e asset restano su filesystem tenant-aware; `strumenti legali`, `applicazioni` e `news giuridiche strutturate` vengono pubblicati solo quando il flag amministrativo del sito e' attivo.
- `Uffici giudiziari e PEC` resta runtime JSON-first per la cache storica degli uffici, ma ora ha schema SQLite/PostgreSQL esplicito e report di verifica con fonti PST/IPA distinte; il cutover R/W SQL richiede repository tenant-aware e job schedulato dedicato.
- `admin/database` esegue la verifica referenziale con riparazione automatica dei problemi risolvibili: prima della scrittura crea backup JSON, non crea record fittizi e, quando non trova un collegamento reale univoco, scollega il riferimento orfano conservando l'ID originale in note/metadati.
- I moduli JSON monitorati da `admin/database` che non hanno ancora una tabella verticale dedicata sono comunque migrabili con struttura esplicita SQLite/PostgreSQL: `moduli_dati` registra percorso, backend e metadati; `moduli_json_records` conserva i record normalizzati per modulo. Le tabelle dedicate restano il target preferito per i domini core, ma Calendar Sync, Email, Soggetti, Portale, Template, Wizard, Intelligence e moduli analoghi non devono risultare "non migrabili" solo perche' sono JSON runtime.
- Lo snapshot SQLite mostrato da `admin/database` resta presente anche se una tabella tecnica derivata, come l'indice FTS `search_documenti`, non e' conteggiabile nel runtime corrente: la pagina mostra un avviso e conserva le statistiche delle altre tabelle invece di dichiarare assente l'intero database.

## Check di consistenza minimi

- utenti attivi, ruoli e audit log coerenti
- clienti, codici fiscali ed email univoci invariati
- fascicoli, riferimenti cliente e metadati documentali coerenti
- appuntamenti, scadenze e riferimenti forti invariati
- template termini processuali, versioni regole/calendario e audit hashati invariati
- timesheet, preventivi, conferimenti, parcelle e link pagamento coerenti tra cliente e fascicolo
- fonti, staging, review queue, news, normative, giurisprudenza e prassi di `Update Intelligence` coerenti tra SQL locale e PostgreSQL
- snapshot, gap queue, draft e publish history di `Coverage AI` coerenti tra `studio.db` e PostgreSQL tenant-aware
- report di migrazione persistito sotto `backup/` del tenant
