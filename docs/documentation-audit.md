# Audit documentazione fase 12

Aggiornato: 2026-05-14, fase 12 `fasereact`.

Obiettivo: rendere coerenti documenti, codice, test e CI reali senza dichiarare strumenti o rollout non presenti.

| Documento | Esiste | Aggiornato | Contraddizioni | Azione | Stato |
| --- | --- | --- | --- | --- | --- |
| `README.md` | si | si | Era molto ampio ma mancava un percorso rapido handover/App V2/CI. | Aggiunta sezione rapido sviluppo e link a `docs/index.md`. | coerente |
| `SECURITY.md` | si | si | Troppo generico per RBAC, tenant isolation, file security e CI gates. | Riscritto come security handover operativo senza segreti o indirizzi finti. | coerente |
| `CONTRIBUTING.md` | si | si | Indicava branch descrittivi, in conflitto con la policy operativa locale dei due branch ammessi. | Riallineato a branch ammessi, checklist PR App V2 e quality gates. | coerente |
| `docs/index.md` | no | si | Mancava indice ufficiale. | Creato indice con link ai documenti reali e validazioni. | creato |
| `docs/architecture.md` | no | si | Esisteva solo `docs/ARCHITETTURA.md` storico. | Creato handover architetturale corrente e link allo storico. | creato |
| `docs/app-v2.md` | no | si | Stato App V2 disperso tra registry, test plan e master plan. | Creato documento operativo con checklist pagina/rotta/componente. | creato |
| `docs/feature-flags.md` | si | si | Stato 2026-05-13 e nessun riepilogo handover fase 12. | Aggiornato a 2026-05-14, aggiunta checklist e fonte verificabile. | coerente |
| `docs/legacy-to-app-v2-routing-map.md` | si | si | Generato e coerente; non va modificato manualmente se il generatore passa. | Verifica demandata a `generate_app_v2_page_registry.py --check`. | generato |
| `docs/security-rbac-tenant-isolation.md` | si | si | Mancava sezione handover fase 12. | Aggiunta sezione con policy PII/file/report e test richiesti. | coerente |
| `docs/api-contracts.md` | si | si | Testo iniziale diceva che OpenAPI sarebbe stata estesa in futuro. | Aggiornato a fase 12: OpenAPI e provider verification sono gia' attivi. | coerente |
| `docs/api-endpoint-contract-map.md` | si | si | Generato; nessuna modifica manuale richiesta. | Verifica con generatori/API gates. | generato |
| `docs/backend-endpoint-security-map.md` | si | si | Generato; nessuna modifica manuale richiesta. | Verifica con `generate_backend_security_map.py --check` quando toccato. | generato |
| `docs/test-plan-app-v2.md` | si | si | Coerente con fase 11; mancava solo collegamento a indice fase 12. | Indicizzato e validato. | coerente |
| `docs/ci-cd-gates.md` | si | si | Coerente con workflow reali; rollout automatico non dichiarato. | Indicizzato e mantenuto come registro CI. | coerente |
| `docs/ui-regression-and-storybook.md` | si | si | Dichiara correttamente Storybook/VRT non presenti. | Nessuna promozione fittizia. | coerente |
| `docs/release-rollout.md` | si | si | Mancava runbook completo fase 12 per Hetzner e rollback entro 2 ore. | Esteso con pre-release, smoke, rollback e escalation. | coerente |
| `docs/troubleshooting.md` | no | si | Mancava troubleshooting unico. | Creato con sintomi, diagnosi e fix. | creato |
| `docs/risk-register.md` | no | si | Rischi residui dispersi in open issues. | Creato registro con mitigazioni e owner. | creato |
| `docs/handover-next-prs.md` | no | si | Mancava handover sintetico e prossime PR. | Creato con priorita e criteri accettazione. | creato |
| `docs/observability-and-logs.md` | no | si | Osservabilita App V2 dispersa. | Creato runbook log/audit/metriche. | creato |
| `docs/database-and-migrations.md` | no | si | Stato DB/migrazioni non raccolto in documento fase 12. | Creato con SQLite/PostgreSQL, tenant e rollback. | creato |
| `docs/release-notes-app-v2.md` | no | si | Mancava release notes tecnica App V2. | Creato documento tecnico non marketing. | creato |
| `scripts/validate_docs_links.py` | no | si | Nessun check leggero link handover. | Creato script locale senza dipendenze esterne. | creato |
| `scripts/validate_docs_commands.py` | no | si | Nessun check leggero su comandi documentati. | Creato script locale su script/workflow/npm scripts reali. | creato |

## Contraddizioni risolte

1. Branch policy: `CONTRIBUTING.md` ora non suggerisce branch temporanei generici nel contesto operativo corrente.
2. API contracts: `docs/api-contracts.md` non parla piu' di OpenAPI come lavoro futuro.
3. Storybook/VRT: restano esplicitamente gap, non gate pronti.
4. Smoke autenticati: documentati come bloccati da env/secrets dedicate, non verdi.
5. Deploy: documentato come operativo/manuale; non esiste CD automatico di produzione da PR.

## Contraddizioni note non risolte per scelta

| Area | Motivo | Mitigazione |
| --- | --- | --- |
| Documenti storici con nomi maiuscoli/minuscoli duplicati | Sono documenti di epoche diverse e non vanno cancellati in fase 12. | `docs/index.md` indica il documento corrente da usare. |
| Route `partial` o `blocked` ancora presenti | Rappresentano stato reale del prodotto, non errore documentale. | `docs/handover-next-prs.md` propone PR piccole e verificabili. |
| Smoke autenticati non eseguiti senza credenziali | Il repository non deve contenere segreti. | Usare environment GitHub protetto o variabili locali dedicate. |
