# UI regression, Storybook e gate visuali App V2

Aggiornato: 2026-05-13, fase 9 `fasereact`.

## Stato sintetico

- Storybook: non introdotto. Il frontend non aveva `.storybook`, storie, test runner o dipendenze dedicate; introdurlo ora avrebbe aggiunto peso infrastrutturale non ancora governato.
- Test UI: attivi tramite alternativa leggera `scripts/validate_ui_coverage.py`, `frontend/scripts/check-app-v2-frontend.mjs`, typecheck e build Vite.
- VRT: non attivo. Nessuna baseline visuale viene dichiarata pronta senza un comando reale di screenshot/regressione.
- Fixture sicure: `frontend/src/test/fixtures/app-v2-ui-fixtures.json`, isolate dal runtime e prive di PII reale, segreti, token, PEC vere o tenant reali.
- Pagine P0/P1 React full: marcate `ui_tested` solo nei registri generati quando esistono componente React, stati UI, RBAC/flag governati e gate fase 9.

## Comandi

```powershell
python scripts\validate_ui_coverage.py
npm --prefix frontend run test
npm --prefix frontend run typecheck
npm --prefix frontend run build
python -m pytest -q tests/test_ui_coverage_phase9.py --tb=short
```

Storybook non ha comandi disponibili in questa fase: `npm run storybook`,
`npm run build-storybook` e `npm run test-storybook` non vengono dichiarati
finche' la relativa configurazione non esiste.

## Copertura

| Area | Componente/Pagina | Priorita | Storybook | Component Test | VRT | A11y | Stato |
|------|-------------------|----------|-----------|----------------|-----|------|-------|
| Comunicazioni | PEC, email ordinaria, messaggi, notifiche legali | P0/P1 | no, alternativa leggera | si, coverage statico + gate App V2 | no, gap documentato | heading, nomi pulsanti, errori sicuri | ui_tested |
| Impostazioni | Studio, PEC/SMTP, pagamenti, notifiche, backup, calendari | P1 | no, alternativa leggera | si, coverage statico + gate App V2 | no, gap documentato | label form, segreti mascherati, readonly | ui_tested |
| Agenda | Nuovo appuntamento | P1 | no, alternativa leggera | si, coverage statico + gate App V2 | no, gap documentato | heading, label input, errori form | ui_tested |
| Clienti e soggetti | Nuovo cliente, nuovo soggetto | P1 | no, alternativa leggera | si, coverage statico + gate App V2 | no, gap documentato | label form, PII minima, errori sicuri | ui_tested |
| Documenti e ricerca | Redazione, template, giurisprudenza, ricerca legale | P1 | no, alternativa leggera | si, coverage statico + gate App V2 | no, gap documentato | azioni nominate, empty/error sicuri | ui_tested |
| Mandato/economico | Preventivi, compensi, fatturazione, incassi, tariffario | P1 | no, alternativa leggera | si, coverage statico + gate App V2 | no, gap documentato | form/azioni nominate, readonly | ui_tested |
| Telematico | Controlli atti | P0 | no, alternativa leggera | si, coverage statico + gate App V2 | no, gap documentato | stato forbidden/flag-off in italiano | ui_tested |
| Amministrazione | Registro GDPR nuovo | P1 | no, alternativa leggera | si, coverage statico + gate App V2 | no, gap documentato | permessi e azioni amministrative | ui_tested |
| Aree partial o legacy | Servizi non parificati | P0/P1 | no | no, da aggiungere prima della promozione | no | pending | partial/blocked/pending |

La tabella pagina per pagina e' generata in `docs/frontend-app-v2-pages.md` e
`docs/app-v2-page-registry.md` nella sezione `Copertura UI fase 9`.

## Stati UI coperti

Il gate fase 9 richiede per P0/P1 React full:

- default/success;
- loading;
- empty;
- error;
- forbidden;
- flag-off senza chiamata API dati;
- readonly/RBAC limited;
- desktop, tablet e mobile documentati.

Le pagine partial, legacy o bloccate non possono essere marcate `ui_tested`.

## RBAC

Le fixture includono utenti admin, avvocato, collaboratore e readonly. Le righe
P0/P1 full devono dichiarare permessi attesi e comportamento senza permesso:
azioni di scrittura nascoste, stato forbidden sicuro, nessun dato cross-tenant.
Il gate controlla che la pagina non sia promossa a `ui_tested` se non e' gia'
`react_operational_full`.

## Feature Flag

Le fixture includono stati flag on/off per fascicoli, documenti, comunicazioni
e impostazioni. Il comportamento flag-off resta quello della fase 7: la shell
mostra "Funzione non attiva per questo studio." e non carica l'API dati della
pagina. `frontend/scripts/check-app-v2-frontend.mjs` continua a presidiare il
no-fetch flag-off e la 404 sicura App V2.

## Accessibilita

La copertura minima fase 9 e' statica ma vincolante:

- heading pagina presente o componente header equivalente;
- bottoni con nome accessibile;
- input con label o testo associato;
- errori in italiano, senza stack trace o chiavi tecniche;
- icone informative accompagnate da testo o `aria-label`;
- azioni nascoste quando il ruolo non ha permesso.

I test automatici axe non sono attivi in questa fase perche' il repo non ha un
runner component/browser dedicato. La loro introduzione resta un passo futuro,
insieme a Storybook o Playwright component testing.

## Responsive

Per P0/P1 React full il registro richiede desktop, tablet e mobile documentati.
La fase 9 non aggiunge nuove baseline screenshot: preserva i browser smoke gia'
documentati e registra il gap VRT. Quando verra' introdotto VRT, le baseline
dovranno usare viewport desktop, tablet e mobile con dati fixture stabilizzati.

## Mock sicuri

Regole applicate a `frontend/src/test/fixtures/app-v2-ui-fixtures.json`:

- email solo su `example.invalid` o `pec.example.invalid`;
- nessuna password, token, chiave provider o segreto in chiaro;
- nessun codice fiscale reale;
- nessun tenant reale;
- nessun path interno reale;
- valori segreti solo mascherati.

## Design System Consistency

- Componenti usati: shell IUSENTRA esistente, card operative, badge, pulsanti e icone `lucide-react` gia' presenti.
- Componenti duplicati trovati: nessun nuovo duplicato introdotto in fase 9.
- Fix fatti: nessun refactor visivo runtime; la fase aggiunge governance e test, non cambia layout produzione.
- Refactor futuri consigliati: separare progressivamente `frontend/src/App.tsx`, introdurre un runner component leggero e valutare Storybook solo dopo avere un piano dipendenze/CI dedicato.

## CI gate

La CI App V2 deve eseguire:

- `python scripts/react-migration/generate_app_v2_area_requirements.py --check`;
- `python scripts/smoke_app_v2_workflows.py --list`;
- `python scripts/validate_ui_coverage.py`;
- `python -m pytest -q tests/test_ui_coverage_phase9.py --tb=short`;
- `npm --prefix frontend run test`;
- `npm --prefix frontend run typecheck`;
- `npm --prefix frontend run build`.

## Gap residui

- Storybook non e' presente e non viene dichiarato pronto.
- VRT/screenshot regression non e' presente e non viene dichiarato pronto.
- Smoke UI autenticato tenant A/B richiede credenziali ambiente dedicate.
- Test axe automatici richiedono un runner component/browser futuro.
- Le aree partial o blocked restano escluse da `ui_tested` finche' non diventano React full con gate dedicati.

## Rollback

- Per rimuovere la fase 9 revertire il commit che introduce fixture, `scripts/validate_ui_coverage.py`, test pytest e sezioni documentali fase 9.
- Se il gate UI coverage blocca erroneamente, correggere prima la riga del registro o la fixture; disattivarlo in CI solo con commit esplicito e issue collegata.
- Se una regressione UI appare dopo rollout, spegnere il feature flag App V2 interessato e tornare al fallback governato, poi rilanciare test e browser smoke.
