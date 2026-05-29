# Audit finale PST / SQLite / PEC

Generato: 2026-05-29 13:08:23
Branch: `Codex/legal-electronic-filing-kIxcV`
Commit di partenza: `cd5aeb959c3528d43cd1dacb41865a7834d84672`
Esito complessivo: SUPERATO

## Nota copertura

Il report non dichiara copertura globale 100% del progetto storico. La soglia 100% viene applicata al nuovo classificatore PEC legale, mentre Step 7, SQLite, UI React e attestazione sono presidiati da fixture mirate e gate di regressione.

## Comandi

| Area | Verifica | Esito | Secondi |
| --- | --- | --- | --- |
| Sintassi | Compilazione moduli critici | OK | 0.36 |
| Frontend | Typecheck React | OK | 22.73 |
| Frontend | Build Vite | OK | 33.59 |
| Step 7 PST/Local Signer | Import documenti reali, catalogo e contenuto mancante | OK | 44.62 |
| SQLite | Pre-verifica, riconciliazione e blocco anti-perdita | OK | 77.99 |
| PEC legale | Classificazione PEC, registri, eventi e pipeline | OK | 10.36 |
| Attestazione conformità | Modello autocompilante e DOCX generato | OK | 3.1 |
| React shell | Contratti UI amministrazione database e PST | OK | 7.63 |
| UTF-8 | Presidio testi italiani | OK | 1.74 |
| Git | Whitespace e patch check | OK | 0.22 |
| Copertura | Copertura 100% classificatore PEC legale | OK |  |

## File modificati

```text
CHANGELOG.md
Dockerfile
artifacts/audit/finale-pst-sqlite-pec-20260529-130823.md
artifacts/react-migration/pytest-confirmed-ok.md
artifacts/react-migration/pytest-open-issues.md
docs/LEGAL_NOTIFICATIONS_AND_TELEMATIC_REGISTRY.md
docs/REACT_MIGRATION_MASTER_PLAN.md
docs/database-and-migrations.md
docs/openapi.yaml
docs/templates/attestazione_conformita_autocompilante.docx
docs/templates/attestazione_conformita_autocompilante.md
frontend/src/adminDatabaseData.ts
frontend/src/components/AdminDatabasePage.css
frontend/src/components/AdminDatabasePage.tsx
frontend/src/components/TelematicoSurfacePage.css
frontend/src/components/TelematicoSurfacePage.tsx
pct/__init__.py
pct/database.py
pct/notifiche_legali.py
pct/pec_legal_workflow.py
pct/pec_pipeline.py
railway.toml
scripts/audit_finale_pst_sqlite_pec.py
tests/test_database.py
tests/test_notifiche_legali.py
tests/test_pec_legal_workflow.py
tests/test_polisweb.py
tests/test_react_shell.py
web/bootstrap/admin_database_routes.py
web/bootstrap/portali_acquisizione_routes.py
web/services/fascicoli_runtime.py
web/services/react_admin_database_bridge.py
web/services/telematico_runtime.py
```

## Esito operativo

- Step 7 PST/Local Signer: fixture di importazione reale, catalogo e contenuto mancante eseguite.
- SQLite: pre-verifica, riconciliazione e blocco anti-perdita eseguiti.
- PEC: registri, famiglie, eventi e correlazione eseguiti.
- UI React: typecheck, build e contratti mirati eseguiti.
- Attestazione: payload e DOCX autocompilante verificati.
