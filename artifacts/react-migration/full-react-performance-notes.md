# Full React performance notes

Generato: 2026-05-08T09:10:14.073Z

## Interventi e stato

- Workspace esistenti caricati con `React.lazy` nella shell corrente.
- Nuovo `frontend/src/app/routes.ts` centralizza le macro-route senza introdurre bundle pesanti.
- Client API unico supporta `AbortSignal` e mantiene credenziali same-origin/CSRF per scritture.
- Nessuna nuova dipendenza grafica introdotta.
- I nuovi componenti UI sono primitive leggere e CSS-token based.

## Rischi residui

- `frontend/src/App.tsx` resta un file monolitico legacy React da spezzare in tranche successive.
- Diverse feature usano ancora fetch locali storici; il re-export preserva compatibilita ma non completa la convergenza totale al nuovo client.
- Misura bundle prima/dopo da confermare con `npm run build`.
