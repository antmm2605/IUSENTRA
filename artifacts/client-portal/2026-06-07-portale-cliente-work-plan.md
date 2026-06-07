# Portale Cliente - piano operativo Codex

Data: 7 giugno 2026.
Repository: `D:\legale\IUSENTRA`.
Branch operativo: `Codex/legal-electronic-filing-kIxcV`, da sincronizzare solo a fine lavoro con `claude/legal-electronic-filing-kIxcV`.

## Regola di rientro dopo compattazione

Prima di riprendere il lavoro dopo ogni compattazione o pausa, leggere questo file per intero e poi eseguire:

```powershell
git status --short
```

Non procedere se il piano non è coerente con la richiesta corrente, con `AGENTS.md` o con la worktree reale.

## Vincoli non negoziabili

- Nessun commit e nessun push finché il Portale Cliente non è completo, funzionante e verificato sul perimetro dichiarato.
- Nessun backup operativo e nessun commit intermedio: backup, commit e push si valutano solo nel rilascio finale, quando il prodotto è completo e funzionante.
- Non perdere o sovrascrivere modifiche già presenti nella worktree: classificarle, preservarle se intenzionali e ripulire solo artefatti runtime/generati non collegati.
- Nessun dato demo spacciato per reale, nessuna route finta, nessun pulsante non collegato, nessun TODO bloccante.
- Il client non può mai inviare o scegliere `tenant_id`, `studio_id`, ruoli, permessi, percorsi filesystem, token interni o segreti.
- Tutto il testo visibile deve essere italiano corretto UTF-8, con accenti reali e senza termini tecnici interni.
- Orari visibili in `Europe/Rome`.
- Ogni persistenza nuova deve avere parità SQLite e PostgreSQL, più storage tenant-aware per file/documenti.
- Tutto deve arrivare all'UI React App V2 con API JSON reali sotto `/api/v1/ui/*`.
- Le capability sensibili devono partire dietro feature flag e default-off finché non sono verificate.

## Documenti già consultati

- `README.md`
- `docs/index.md`
- `docs/architecture.md`
- `docs/app-v2.md`
- `docs/feature-flags.md`
- `docs/security-rbac-tenant-isolation.md`
- `SECURITY.md`
- `docs/api-contracts.md`
- `docs/test-plan-app-v2.md`
- `docs/ci-cd-gates.md`
- `docs/smoke-tests.md`
- `docs/release-rollout.md`
- `docs/troubleshooting.md`
- `docs/UI_DESIGN_SYSTEM.md`
- `tools/open-design-support/IUSENTRA_UI_RULES.md`
- `docs/REACT_MIGRATION_MASTER_PLAN.md`
- `artifacts/react-migration/pytest-confirmed-ok.md`
- `artifacts/react-migration/pytest-open-issues.md`
- `docs/database-and-migrations.md`
- `docs/STORAGE_MATRIX.md`

## Stato iniziale worktree

All'avvio del lavoro la worktree non è pulita. File modificati già presenti:

- `core/security/headers.py`
- `data/auth/audit.json`
- `data/auth/utenti.json`
- `data/intelligence/motori.json`
- `data/intelligence/tabelle_normative.json`
- `data/tenant_user_directory.json`
- `data/tenants/tenant-8bf98719c459/auth/audit.json`
- `deploy/hetzner/Caddyfile`
- `frontend/src/components/ScadenziarioPage.tsx`
- `frontend/src/components/SupportOperatorRoom.tsx`
- `frontend/src/index.css`
- `pct/pec_pipeline.py`
- `pct/support_remote.py`
- `tests/test_pec_audit_pipeline.py`
- `tests/test_security_headers.py`
- `tests/test_support_remote.py`
- `web/services/react_scadenziario_bridge.py`
- `web/services/scadenziario_views.py`
- `web/static/js/support_customer_room.js`
- `web/static/js/support_operator_room.js`
- `web/templates/support/customer_room.html`
- `web/templates/support/operator_room.html`
- `.codex-remote-attachments/`

Prima di modificare questi file o file collegati, capire se sono sorgente intenzionale, runtime locale o artefatti da escludere dal commit.

Classificazione iniziale dopo lettura diff:

- Sorgente/test da preservare e non sovrascrivere: modifiche su assistenza remota, header `Permissions-Policy`, Caddy, Scadenziario, PEC udienze da remoto e relativi test. Sembrano correzioni funzionali intenzionali preesistenti.
- Runtime/dati locali da non committare nel Portale Cliente salvo richiesta esplicita: `data/auth/audit.json`, `data/auth/utenti.json`, `data/intelligence/motori.json`, `data/intelligence/tabelle_normative.json`, `data/tenant_user_directory.json`, `data/tenants/tenant-8bf98719c459/auth/audit.json`.
- Artefatti allegati/analisi da non confondere con sorgente prodotto: `.codex-remote-attachments/`.
- Artefatto intenzionale di questa analisi: `artifacts/client-portal/2026-06-07-portale-cliente-work-plan.md`.

## Architettura da seguire

1. Backend Python/Flask, blueprint modulari in `web/blueprints`.
2. Servizi applicativi in `web/services` o package coerenti sotto `pct`.
3. API JSON sotto `/api/v1/ui/client-portal/*`.
4. Feature flag in `web/services/feature_flags.py` e `frontend/src/lib/featureFlags.ts`.
5. React 19/Vite sotto `frontend/src`, usando componenti IUSENTRA/shadcn e icone `lucide-react`.
6. Route studio: `/app/portale-clienti`.
7. Route cliente: `/portale-cliente`, `/portale-cliente/invito/:token` e sottopagine operative.
8. Persistenza tenant-aware:
   - JSON solo come bootstrap/export controllato se coerente con il repository.
   - SQLite locale con schema dedicato.
   - PostgreSQL con schema equivalente.
   - File caricati su filesystem tenant-safe, mai esponendo path.
9. OpenAPI e provider verification aggiornati secondo le convenzioni repo.
10. Registry App V2 e manifest route aggiornati.

## Sequenza di lavoro

## Perimetro da valutare prima del codice

Non iniziare l'implementazione finché ogni riga sotto non è stata valutata contro codice esistente, documenti, test e impatti collaterali.

| Area | Cosa valutare | Esito richiesto prima di iniziare |
| --- | --- | --- |
| Worktree iniziale | File sorgente già modificati, dati runtime, asset generati e allegati remoti | Classificazione scritta e nessuna modifica utente persa |
| Branch e igiene repo | Branch corrente, branch locali ammessi, worktree unica, script `scripts/repo_hygiene.ps1` | Nessun branch o worktree parallelo introdotto |
| Architettura Flask | Blueprint esistenti, factory, registrazione API, `api_v1_react.py`, `react_shell.py` | Scelta del punto di integrazione senza stack parallelo |
| Feature flag | Backend `feature_flags.py`, frontend `featureFlags.ts`, default, alias e rollback | Flag Portale Cliente definiti e default sicuri |
| RBAC | Ruoli reali in `pct/auth.py`, profili studio, permessi mutazione e sola lettura | Permessi nuovi o mapping esistente documentati e testabili |
| Tenant isolation | Risoluzione tenant da sessione/API key, divieto di parametri server-controlled, path tenant-safe | Nessun endpoint o repository accetta tenant dal client |
| Audit | Audit log esistenti, denial log, audit operazioni sensibili, minimizzazione PII | Ogni mutazione sensibile ha evento audit previsto |
| SQLite | Pattern `pct/database.py`, script `pct/sql/*.sql`, repository verticali | Schema locale definito e testato |
| PostgreSQL | Pattern `pct/storage_postgres.py`, script `_postgres.sql`, migrazione/mirror | Schema equivalente definito e testato |
| JSON tenant-aware | Eventuale uso solo come bootstrap/export, mirror `moduli_json_records` se applicabile | Nessun fallback invisibile o sorgente parallela |
| File/documenti | Upload, download, anteprima, hash, storage tenant-safe, antivirus/scansione se presente | Nessun path esposto e regole file testate |
| Notifiche | Centro notifiche, Web Push, flag mobile, provider e fallback in-app | In-app sempre reale, Web Push default-off se non configurato |
| Privacy | Registro consensi, versioni informative, blocchi funzioni sensibili | Privacy obbligatoria governata prima delle funzioni cliente |
| Firme | Firma semplice, evidenza, provider futuro, limiti giuridici | Nessuna promessa di firma qualificata senza provider reale |
| Booking/videocall | Agenda, disponibilità, fusi orari, provider videocall astratto | Slot e link governati senza segreti hardcoded |
| Chat | Messaggi, allegati, lettura/non lettura, blocco pratica chiusa | REST/polling sicuro se non esiste realtime dedicato |
| UI React | Route, shell, menu, preset IUSENTRA, componenti shadcn, Lucide, responsive | Tutte le pagine previste hanno stati e API reali |
| Approvazione grafica | Mockup studio e cliente, densità, gerarchia, responsive, stati e coerenza con `docs/UI_DESIGN_SYSTEM.md` | Mostrare il mockup all'utente e attendere ok prima di implementare la UI di prodotto |
| API JSON | Namespace `/api/v1/ui/client-portal/*`, schema errori, 401/403/422/successo | Contratti OpenAPI e provider verification pianificati |
| OpenAPI/registry | `docs/openapi.yaml`, mappe endpoint, route manifest, registry App V2 | Nessun endpoint o route fuori registro |
| Test backend | Servizi, repository, API, RBAC, tenant, token, upload, firme, privacy, chat, booking, notifiche | File test dedicati prima della consegna |
| Test frontend | Contratti, typecheck, build, flag on/off, stati UI, testi visibili | Gate frontend reali verdi, nessun runner inventato |
| UTF-8 e testo visibile | Accenti, date italiane, orari Roma, divieto termini tecnici in UI | `utf8-integrity` o test dedicati verdi |
| Performance | Caricamento, cambio pagina, asset, richieste lente | Baseline o verifica mirata sulle route toccate |
| Docker reale | Copia locale utente su `127.0.0.1:8080` | Prova finale solo sulla porta reale 8080 |
| GitHub/CI | Gate required dello SHA corrente, CodeQL, supply chain, shard, frontend | Nessun rosso o skipped dichiarato verde |
| Deploy Hetzner | Profilo `deploy/hetzner`, commit server, container, `/api/pronto`, prune cache | Eseguito solo dopo push e CI verdi |
| Documentazione finale | `docs/client-portal.md`, docs App V2/security/test/smoke, changelog e report | Stato reale tracciato, limiti non nascosti |

## Copertura funzionale da valutare

| Requisito | Valutazione obbligatoria |
| --- | --- |
| A. Link sicuro cliente | Token forte, hash, scadenza, revoca, riemissione, uso invito, errore sicuro, audit, anti-enumerazione, tenant A/B |
| B. Timeline pratica | Step ordinati, progresso, visibilità cliente, azioni richieste, documenti mancanti, scadenza, messaggi, appuntamento, aggiornamento studio |
| C. Anagrafica cliente | Campi personali/societari, salvataggio parziale, validazioni, PII minimizzata, audit, accesso solo proprio |
| D. Upload documenti | Tipi consentiti, dimensione, nome normalizzato, path traversal, SHA-256, versioni, stato verifica, notifiche, audit |
| E. Documenti da firmare | Richiesta studio, vista cliente propria, firma semplice, rifiuto, scadenza, evidenza, hash coerente, notifica, audit |
| F. Privacy e consensi | Versione informativa, accettazione obbligatoria, consensi opzionali, storico, blocco funzioni sensibili, audit |
| G. Chat interna | Conversazione per pratica, studio/cliente, allegati governati, letto/non letto, notifiche, blocco se pratica chiusa |
| H. Appuntamenti e videocall | Disponibilità studio, slot, conflitti, annullo/modifica, timezone, provider test, provider non configurato senza link falso |
| I. Notifiche mobile/offline | Centro notifiche, letto/non letto, deep link sicuro, preferenze, Web Push dietro flag, fallback in-app, payload senza PII eccessiva |
| J. Dashboard studio | Inviti, anagrafica, documenti, firme, messaggi, appuntamenti, configurazioni, template, azioni rapide e permessi |
| K1. Checklist onboarding | Percentuale, prossima azione, blocchi privacy/anagrafica/documento |
| K2. Evidence pack finale | Riepilogo pratica consultabile/scaricabile con PII minimizzata e permessi |
| K3. Preferenze comunicazioni | Canali cliente, canali ammessi studio, consenso notifiche |
| K4. Documento identità in scadenza | Data scadenza, avviso cliente/studio, notifica |
| K5. Questionari guidati | Domande per tipologia pratica, risposte cliente, collegamento pratica, audit |
| K6. Survey fine pratica | Soddisfazione opzionale, non bloccante, visibile allo studio |
| K7. Esportazione conversazione | Export con permesso adeguato e audit |
| K8. Centro attività cliente | Pagina "Cosa devo fare adesso" con documenti, firme, appuntamenti e messaggi |

### Fase 0 - Analisi e classificazione

1. Rileggere il brief utente allegato.
2. Verificare branch corrente e worktree.
3. Classificare i file sporchi: sorgente intenzionale, dati runtime, asset generati, file da preservare.
4. Leggere pattern esistenti per:
   - blueprint API React;
   - bridge React;
   - feature flag;
   - route shell;
   - storage SQLite/PostgreSQL;
   - notifiche;
   - upload documenti;
   - audit/RBAC;
   - registry App V2.
5. Aggiornare questo piano se l'analisi mostra un ordine migliore.

### Fase 1 - Disegno tecnico versionato

1. Creare o aggiornare `docs/client-portal.md` con flusso studio, flusso cliente, permessi, flag, notifiche, firme, booking/videocall, provider e limiti.
2. Definire feature flag:
   - `routes.appV2.clientPortal.enabled`
   - `routes.appV2.clientPortal.notifications`
   - `routes.appV2.clientPortal.webPush`
   - `routes.appV2.clientPortal.videoCalls`
   - `routes.appV2.clientPortal.signatures`
3. Definire permessi RBAC coerenti:
   - amministrazione portale;
   - operatività studio;
   - sola lettura;
   - accesso cliente;
   - accesso cliente pendente.
4. Definire schema dati e mapping SQLite/PostgreSQL prima del codice.

### Fase 2 - Repository e database

Implementare repository tenant-aware con schema SQLite e PostgreSQL per:

1. inviti cliente con token solo hashato;
2. profilo cliente portale;
3. step pratica;
4. slot documentali;
5. documenti cliente;
6. richieste firma;
7. evidenze firma;
8. privacy e consensi;
9. messaggi chat;
10. impostazioni booking studio;
11. appuntamenti e videocall;
12. notifiche portale;
13. subscription push;
14. questionari, survey, preferenze comunicazioni ed evidence pack se inclusi nella consegna.

Regole:

- Schema SQLite in `pct/sql/YYYYMMDD_client_portal.sql`.
- Schema PostgreSQL in `pct/sql/YYYYMMDD_client_portal_postgres.sql`.
- Test che confrontano presenza tabelle/indici in entrambi.
- Nessun fallback invisibile quando PostgreSQL è attivo.
- File upload in cartelle tenant-aware.

### Fase 3 - Sicurezza, servizi e API

1. Servizio inviti: generazione token forte, salvataggio hash, scadenza, revoca, riemissione, uso sicuro, limite richieste o hook se presente.
2. Servizio sessione cliente limitata da invito.
3. Servizio timeline pratica e step.
4. Servizio anagrafica e privacy.
5. Servizio upload documenti con validazione tipo/dimensione/nome/hash/versione.
6. Servizio firma semplice con evidenza auditabile e astrazione provider.
7. Servizio chat REST/polling.
8. Servizio booking e provider videocall astratto.
9. Servizio notifiche in-app, preferenze, Web Push default-off e provider/fallback.
10. Blueprint API `/api/v1/ui/client-portal/*` con auth, RBAC, tenant context server-side, validazione, audit, error schema.
11. Test 401, 403, 400/422, successo e isolamento tenant per ogni endpoint.

### Fase 4 - UI React App V2

0. Prima di scrivere la UI di prodotto, preparare un mockup statico/artifact che mostri:
   - dashboard studio `/app/portale-clienti`;
   - dashboard cliente `/portale-cliente`;
   - dettaglio pratica/timeline;
   - pannelli documenti, firme, privacy, chat, appuntamenti e notifiche;
   - layout desktop, tablet e mobile;
   - stati vuoto, caricamento, errore, funzione non attiva e sola lettura.
1. Mostrare il mockup all'utente e attendere ok esplicito sulla direzione grafica.
2. Dashboard studio `/app/portale-clienti`.
3. Impostazioni studio `/app/portale-clienti/impostazioni`.
4. Landing invito `/portale-cliente/invito/:token`.
5. Dashboard cliente `/portale-cliente`.
6. Dettaglio pratica/timeline.
7. Anagrafica.
8. Documenti.
9. Firme.
10. Privacy.
11. Chat.
12. Appuntamenti.
13. Notifiche.

Ogni schermata deve includere caricamento, stato vuoto, errore, permesso negato, funzione non attiva, sola lettura e conferma dove applicabile. Nessun `alert()` grezzo. Nessun testo tecnico visibile.

### Fase 5 - Documentazione, OpenAPI, registry

1. Aggiornare `docs/openapi.yaml` tramite generatori o convenzioni repo.
2. Aggiornare `docs/api-contracts.md` se serve.
3. Aggiornare `docs/app-v2.md`, `docs/feature-flags.md`, `docs/security-rbac-tenant-isolation.md`, `docs/test-plan-app-v2.md`, `docs/smoke-tests.md`.
4. Aggiornare `tools/react-migration/route-manifest.json` e registry generati.
5. Aggiornare `docs/REACT_MIGRATION_MASTER_PLAN.md`, report React pertinenti, `artifacts/react-migration/pytest-confirmed-ok.md`, `artifacts/react-migration/pytest-open-issues.md` e `CHANGELOG.md`.
6. Bump versione in `pct/__init__.py`, `setup.py`, `Dockerfile`, `railway.toml` solo quando il codice è pronto per gate finali.

### Fase 6 - Verifiche locali

Gate mirati obbligatori prima di commit:

```powershell
python -m pytest tests/test_client_portal*.py -q --tb=short
python -m pytest tests/test_backend_security_phase5.py tests/test_tenant_isolation_runtime.py tests/test_feature_flags.py tests/test_app_v2_feature_flags.py -q --tb=short
python scripts/react-migration/generate_api_contracts.py --check
python scripts/validate_openapi.py docs/openapi.yaml
python scripts/verify_openapi_provider.py
pnpm --filter @iusentra/studio test
pnpm --filter @iusentra/studio typecheck
pnpm --filter @iusentra/studio build
python scripts/react-migration/generate_app_v2_page_registry.py --check
python scripts/react-migration/generate_app_v2_area_requirements.py --check
python scripts/react-migration/generate_app_v2_test_docs.py --check
python scripts/validate_docs_links.py
python scripts/validate_docs_commands.py
python tools/sync_packaging_files.py --check
python scripts/audit_tenant_data_structure.py --repair
python -m pytest tests/test_utf8_integrity.py -q --tb=short
git diff --check
git status --short
```

Usare shard aggiuntivi se i file toccati lo richiedono. Non usare `python -m pytest -q` monolitico come unico verdetto.

### Fase 7 - Docker locale e browser reale

1. Ricostruire o ricreare la copia reale Docker su `http://127.0.0.1:8080`.
2. Verificare `/api/pronto` sul commit locale.
3. Eseguire browser verification desktop/tablet/mobile sulle route:
   - `/app/portale-clienti`
   - `/app/portale-clienti/impostazioni`
   - `/portale-cliente/invito/<token-test>`
   - `/portale-cliente`
   - dettaglio pratica
   - documenti
   - firme
   - privacy
   - chat
   - appuntamenti
   - notifiche
4. Controllare console error, network, tempi caricamento, assenza overflow, assenza testi tecnici, UTF-8 e orari italiani.

### Fase 8 - Commit, push e deploy solo a prodotto funzionante

1. `git status --short`.
2. Ripulire runtime/generati non intenzionali.
3. Commit solo dopo verifiche verdi.
4. Sync branch gemello `claude/legal-electronic-filing-kIxcV`.
5. Push.
6. Attendere check GitHub dello SHA corrente, inclusi CodeQL, code scanning, lint, governance, frontend, shard pytest, coverage, signer e supply chain.
7. Solo dopo check verdi, deploy Hetzner `deploy/hetzner`.
8. Verificare commit server, container healthy, `https://app.iusentra.it/api/pronto`.
9. Eseguire prune Docker build cache e rimuovere eventuale `/opt/iusentra/tmp-backup-snapshot`.
10. Report finale con esiti reali, limiti reali e istruzioni operative.

## Criteri di stop

Fermarsi e correggere prima di proseguire se:

- una feature core A-J manca di backend reale, UI reale o test;
- un endpoint accetta tenant/studio/path/token dal client;
- SQLite e PostgreSQL non sono entrambi aggiornati;
- un upload espone path, accetta filename malevoli o non calcola SHA-256;
- una firma viene descritta come qualificata/PAdES/FEQ senza provider reale;
- Web Push parte senza consenso o con flag spento;
- la UI mostra termini tecnici vietati o dati demo;
- un test o smoke è `BLOCKED`, `SKIP` o non eseguito ma viene trattato come verde;
- la copia finale non è quella reale su `127.0.0.1:8080`;
- la worktree contiene dati runtime o file appesi non classificati.

## Output finale richiesto

La relazione finale deve contenere:

1. riepilogo implementazione;
2. test eseguiti con esito;
3. copertura requisiti core e migliorie;
4. sicurezza: tenant, RBAC, token, upload, audit, dati non esposti;
5. limiti noti reali;
6. istruzioni operative: variabili ambiente, flag, provider notifiche, provider videocall, rollback.

Se anche una sola feature core non è implementata e testata, dichiarare `parzialmente completato`, non `completo`.
