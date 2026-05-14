# Risk register App V2

Aggiornato: 2026-05-14, fase 12 `fasereact`.

| ID | Rischio | Area | Probabilita | Impatto | Mitigazione | Owner | Stato |
| --- | --- | --- | --- | --- | --- | --- | --- |
| R-001 | Smoke autenticati tenant A/B/readonly non eseguibili senza secrets dedicate. | smoke/deploy | media | alto | Usare `smoke-staging.yml` con environment protetto; non marcare verdi i profili mancanti. | Release manager | aperto |
| R-002 | Storybook/VRT non presenti: regressioni layout mobile possono sfuggire ai gate statici. | UI regression | media | medio | Introdurre Playwright screenshot o Storybook in PR dedicata; oggi usare browser smoke mirati. | Frontend lead | aperto |
| R-003 | Endpoint parametrizzati/upload hanno provider verification auth-error ma non sempre success-body full. | API contracts | media | alto | Aggiungere fixture dominio per endpoint P0/P1 quando una pagina viene promossa. | Backend lead | aperto |
| R-004 | Aree `partial` o `blocked` potrebbero essere comunicate come complete per errore. | App V2 governance | bassa | alto | Usare `docs/app-v2-area-requirements.md` come fonte; `validate_docs_commands.py` e registry `--check`. | Product/tech lead | monitorato |
| R-005 | Parametri client come `tenant_id` o `studio_id` possono riapparire in nuovi form/API. | tenant isolation | bassa | critico | `web/services/backend_security.py`, test fase 5 e checklist endpoint obbligatoria. | Security lead | monitorato |
| R-006 | Deploy manuale Hetzner puo' essere eseguito senza smoke post-deploy. | smoke/deploy | media | alto | `release-rollout.md` richiede `/api/pronto`, container healthy e smoke security/routing/workflow. | Release manager | aperto |
| R-007 | Documentazione generata modificata manualmente puo' andare in drift. | documentazione | media | medio | Usare generatori `--check`; non editare manualmente registri generati se non si aggiorna lo script. | Maintainer docs | monitorato |
| R-008 | Log applicativi possono includere PII non necessaria durante nuove integrazioni. | dati/PII | bassa | alto | Masking, denial log senza payload sensibile, review `SECURITY.md` e `observability-and-logs.md`. | Security lead | monitorato |
| R-009 | Rollback non isolabile se una modifica bypassa feature flag. | feature flag | bassa | alto | Ogni nuova pagina App V2 deve avere flag/fallback o rollback commit documentato. | Backend/frontend lead | monitorato |
| R-010 | Migrazioni dati non transazionali su JSON/SQLite possono lasciare stato parziale. | data/migration | bassa | alto | Backup prima di scrivere, script idempotenti, rollback documentato in `database-and-migrations.md`. | Data lead | aperto |
