# UI regression, Storybook e gate visuali App V2

Aggiornato: 22/08/2026, release 2.278.64.

## Stato sintetico

- Storybook: presente e bloccante per tutte le 73 superfici React `*Page.tsx`, divise in 11 domini funzionali. Le pagine usano il componente sorgente, provider applicativi, bootstrap RBAC/feature flag e fixture API controllate: non sono schermate decorative.
- La suite esegue 90 storie in Chromium con l'integrazione Vitest ufficiale di Storybook. `@storybook/addon-a11y` usa axe e ogni violazione impostata come errore blocca il job.
- Il controllo `frontend/scripts/check-storybook-page-coverage.mjs` impone la parità 73/73: verifica sorgente, assenza di duplicati, harness con provider e fixture runtime, e almeno otto domini di copertura.
- La CI esegue ora un job dedicato che installa Chromium, lancia `test:storybook` e costruisce Storybook statico. Il job aggregato frontend fallisce se anche questo presidio non riesce.
- VRT: non attivo. Il confronto con Chromatic richiede una baseline pubblicata e un token/progetto approvato. Non viene quindi dichiarata una copertura di screenshot che non esiste.
- Le fixture sono isolate dal runtime e non contengono PII reale, segreti, token, PEC reali o dati di tenant produttivi.

## Comandi

```powershell
pnpm install --frozen-lockfile
pnpm --filter @iusentra/studio test
pnpm --filter @iusentra/studio typecheck
pnpm --filter @iusentra/studio test:storybook
pnpm --filter @iusentra/studio build:vite
pnpm --filter @iusentra/studio build-storybook
python scripts\validate_ui_coverage.py
python -m pytest -q tests/test_ui_coverage_phase9.py --tb=short
```

`test` include il controllo di parità Storybook 73/73. `test:storybook` esegue le storie in Chromium con i controlli axe bloccanti; `build-storybook` assicura che la documentazione navigabile sia producibile. Questi controlli non sostituiscono l'accettazione materiale nella copia Docker reale su `http://127.0.0.1:8080`.

## Copertura

| Area | Superfici | Storybook | A11y automatica | VRT | Stato |
|------|-----------|-----------|-----------------|-----|-------|
| Fondazioni e shell | componenti, card, feedback, layout, navigazione e stati operativi | presente | axe bloccante | non attivo | coperta |
| Agenda e scadenze | agenda, nuovo appuntamento, nuova scadenza, scadenziario e strumenti dei termini | presente | axe bloccante | non attivo | coperta |
| Fascicoli | elenco, dettaglio, deposito, documenti AI e cartelle condivise | presente | axe bloccante | non attivo | coperta |
| Anagrafiche | clienti, soggetti, import ed elenchi operativi | presente | axe bloccante | non attivo | coperta |
| Comunicazioni | PEC, email, messaggi, notifiche legali e presìdi | presente | axe bloccante | non attivo | coperta |
| Documenti e ricerca | documenti, redazione, template, editor e ricerca legale | presente | axe bloccante | non attivo | coperta |
| Telematico | servizi e superfici operative connesse | presente | axe bloccante | non attivo | coperta |
| Studio ed economico | parcelle, preventivi, compensi, prima nota, portale clienti e sito studio | presente | axe bloccante | non attivo | coperta |
| Amministrazione | impostazioni, privacy, backup, pagamenti e configurazioni studio | presente | axe bloccante | non attivo | coperta |
| Legal Skills e strumenti | Legal Skills, regia agentica, archivio e strumenti forensi | presente | axe bloccante | non attivo | coperta |

La matrice sorgente è verificata automaticamente; la tabella di dettaglio resta in `docs/frontend-app-v2-pages.md` e `docs/app-v2-page-registry.md`.

## Stati UI e accessibilità

Le storie esercitano i percorsi con dati controllati e i principali stati operativi. Il gate richiede, dove applicabile:

- intestazioni gerarchiche e landmark non duplicati;
- pulsanti, icone e righe interattive con nome accessibile e focus visibile;
- label o descrizione associata agli input e ai filtri;
- messaggi italiani per errori, loading, stati vuoti e permessi;
- contrasto leggibile per testo secondario, badge e azioni primarie;
- stati hover, focus, selezionato, disabilitato e caricamento coerenti.

I miglioramenti trasversali della release applicano questi criteri alle sezioni del design system, a moduli e filtri, alla riga PEC selezionabile, alle intestazioni, ai pannelli e alle superfici più dense del prodotto. L'accettazione reale deve comunque confermare in browser i flussi autenticati, i salvataggi e gli stati legati al tenant.
## RBAC e Feature Flag

Le fixture condivise sono in `frontend/src/test/fixtures/app-v2-ui-fixtures.json`: includono i ruoli admin, avvocato, collaboratore e readonly, tenant A/B controllati e stati flag on/off. Le storie non promuovono una superficie se permessi, confini tenant o comportamento flag-off non restano governati. Nei flussi con azioni sensibili, i pulsanti non autorizzati restano nascosti o restituiscono un riscontro italiano e sicuro.

## Accessibilita e inclusione

Oltre ai controlli axe, la review Accessibilita richiede contrasto, focus tastiera, ordine delle intestazioni, label, landmark, target touch e messaggi che non dipendano soltanto dal colore. Le eccezioni scoperte dalla suite vanno risolte nel componente o nel design system e non silenziate nella configurazione della storia.

## Design System Consistency

Il canvas `frontend/src/stories/storybook.css` è registrato nella governance del design system ed è limitato a token già approvati. Il gate controlla le allowlist CSS, gli inline style autorizzati e i pattern grafici vietati, affinché la documentazione Storybook non introduca una seconda interfaccia o stili non governati.

## Responsive e prova reale

Storybook e axe non sono prova di funzionamento per l'utente. Prima di una consegna UI occorre ricostruire la copia Docker senza cache e verificare in browser reale su `127.0.0.1:8080`:

- desktop, tablet e mobile;
- scroll completo di pagina o pannello;
- click reali, salvataggi e feedback osservabili;
- hover e focus da tastiera dei controlli principali;
- italiano, date/orari `Europe/Rome`, importi italiani, overflow e contrasto.

Le route protette richiedono una sessione autentica o dati controllati nella copia locale dell'utente. Browser isolati, screenshot statici e mock non sostituiscono questa prova.

## CI gate

`frontend-ci.yml` comprende:

- matrice contratti, typecheck e build Vite;
- job Storybook: installazione Chromium, `test:storybook` e `build-storybook`;
- job aggregato che richiede l'esito positivo di entrambi.

Restano attivi anche i gate App V2: generazione requisiti area, smoke workflow, copertura UI, test Python mirati e contratti frontend. Il nuovo job non riduce né sostituisce i controlli preesistenti.

## VRT e limiti residui

- Il VRT esterno richiede una baseline Chromatic approvata, un progetto e un token dedicato; finché non sono disponibili resta esplicitamente non attivo.
- Le storie utilizzano dati controllati e non possono coprire integrazioni con credenziali reali, Local Signer, PEC, microfono o browser permission.
- Per i flussi autenticati e sensibili la prova reale su `127.0.0.1:8080` e la documentazione operativa pertinente restano obbligatorie.

## Rollback

Se una storia o il gate rileva un errore, va corretta la superficie React o la fixture che lo espone e poi ripetuti typecheck, build, suite Storybook e prova reale. Non si disattivano addon, test o job CI per aggirare una regressione.