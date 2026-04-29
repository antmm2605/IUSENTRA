# Migrazione progressiva Flask + React

## Principio operativo

La migrazione a React non sostituisce la UI Jinja in blocco. Flask resta backend,
source of truth, motore di permessi, tenant, audit e repository. React entra come
shell separata su `/app-v2` e ogni pagina viene attivata solo dopo parità
funzionale verificata.

Regola di rilascio: una pagina React può sostituire la pagina storica solo se
supera API reali, test backend, test frontend, test responsive desktop/tablet/mobile,
accessibilità, tenant/RBAC e rollback immediato.

## Fase 0 - Baseline

- Inventariare route Jinja, blueprint, API, menu e flussi critici.
- Salvare screenshot baseline per desktop `1440px`, tablet `768px`, mobile `390px`.
- Eseguire smoke test autenticati su Panoramica, Regia Operativa, Ricerca Studio,
  Fascicoli, Scadenziario, Preventivi, Fatturazione, Servizi Telematici, Lex e
  Impostazioni.
- Bloccare l'uso di dati demo nella shell React.

## Fase 1 - Shell dormiente

- Integrare `frontend/` con Vite, React e TypeScript.
- Servire la build sotto `web/static/react`.
- Esporre `/app-v2` senza modificare le route esistenti.
- Esporre API ponte sotto `/api/v1/ui/*`, protette da sessione o API key.
- Mantenere tutti i flag di sostituzione route a `false`.

## Fase 2 - API contract

Ogni pagina React deve avere prima un contratto API stabile:

- `GET /api/v1/ui/bootstrap`
- `GET /api/v1/ui/dashboard`
- API dominio per fascicoli, clienti, scadenze, documenti, preventivi, parcelle,
  pagamenti, telematico, Lex e impostazioni.

React non legge file JSON e non accede direttamente allo storage. Tutto passa da
servizi Flask già tenant-aware.

## Fase 3 - Design system

- Usare i design token IUSENTRA già presenti in `tokens.json`.
- Mantenere testi visibili in italiano.
- Target touch minimo: `44px`.
- Verificare contrasto, focus visibile, heading order, navigazione tastiera e
  `prefers-reduced-motion`.
- Nessun caricamento esterno non necessario senza consenso.

### Stato Panoramica `/app-v2`

La prima pagina React usa la shell enterprise collegata a `/api/v1/ui/dashboard`:

- sidebar desktop con navigazione lunga scrollabile e drawer sotto `980px`;
- topbar con ricerca, azioni rapide e comandi principali;
- token CSS e TypeScript per colori, spacing, radius, shadow e typography;
- componenti riusabili `Panel`, `KpiCard`, `DossierCard`, `SourceCard`, `Badge`
  e `Button`;
- array dati separati in `frontend/src/data.ts` per KPI, agenda, operativita',
  fascicoli, fonti, scadenze, economia e suggerimenti Lex;
- niente mock operativo: le sezioni leggono i dati reali disponibili e usano
  stati vuoti espliciti quando il repository non contiene record.

## Fase 4 - Ordine di migrazione

1. Panoramica e shell globale.
2. Ricerca Studio.
3. Scadenziario.
4. Clienti e Anagrafiche.
5. Fascicoli read-only.
6. Documenti e upload.
7. Preventivi e Conferimenti.
8. Parcelle, Fatture, Incassi e Pagamenti.
9. Lex AI.
10. Sito Studio Builder.
11. Servizi Telematici, PDP/PST/PAT/PTT, Local Signer e PEC.
12. Admin e Impostazioni.

Le aree telematiche e di firma restano ultime perché hanno vincoli di compliance,
Local Signer, audit, canali separati e conferma consapevole dell'avvocato.

## Gate per ogni pagina

- API con dati reali, nessun mock operativo.
- UI read-only prima delle azioni di scrittura.
- Azioni di scrittura protette da CSRF/sessione, tenant e RBAC.
- Test unitari backend.
- Test frontend `npm run test`, `npm run typecheck`, `npm run build`.
- Test e2e/smoke desktop, tablet e mobile.
- Verifica accessibilità.
- Flag di rollback.
- Documentazione aggiornata.

## Rollback

Le route Jinja storiche restano sempre disponibili. Lo switch a React avviene solo
via feature flag e può essere disattivato senza migrazione dati.

## Comandi

```powershell
cd D:\legale\IUSENTRA\frontend
npm ci
npm run test
npm run typecheck
npm run build
```

```powershell
cd D:\legale\IUSENTRA
python -m pytest tests/test_react_shell.py -q
```
