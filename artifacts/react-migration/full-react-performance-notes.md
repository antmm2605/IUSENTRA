# Full React performance notes

Generato: 2026-05-08T09:10:14.073Z

## Interventi e stato

- Workspace esistenti caricati con `React.lazy` nella shell corrente.
- Nuovo `frontend/src/app/routes.ts` centralizza le macro-route senza introdurre bundle pesanti.
- Client API unico supporta `AbortSignal` e mantiene credenziali same-origin/CSRF per scritture.
- Nessuna nuova dipendenza grafica introdotta.
- I nuovi componenti UI sono primitive leggere e CSS-token based.
- 2026-05-10: build Vite 2.214.0 completata in 7.04s. Bundle principale `index-P8CJ9O56.js` 428.12 kB (127.71 kB gzip); CSS principale `index-CGSsz9Se.css` 121.41 kB (22.28 kB gzip). Docker locale 2.214.0 healthy e `/api/pronto` 200.
- 2026-05-10: smoke browser desktop/mobile sulle pagine richieste non ha rilevato overflow orizzontale o redirect anomali; i dettagli email React caricano nella shell senza fallback tecnico visibile.
- 2026-05-10: ottimizzati i bootstrap di `/tariffario` e `/preventivi/wizard`. Misura locale con client Flask autenticato: `/api/v1/ui/tariffario` 416585 byte, media 66.4 ms su 3 run; `/api/v1/ui/preventivi/wizard` 704916 byte, media 46.8 ms su 3 run; `/preventivi/` 9124 byte, media 5.4 ms.
- 2026-05-10: browser smoke su Tariffario 2.214.1 conferma il riepilogo sticky desktop dopo scroll e nessun errore console; tablet/mobile restano senza overflow nel flusso normale.

## Rischi residui

- `frontend/src/App.tsx` resta un file monolitico legacy React da spezzare in tranche successive.
- Diverse feature usano ancora fetch locali storici; il re-export preserva compatibilita ma non completa la convergenza totale al nuovo client.
- Misura bundle prima/dopo da confermare con `npm run build`.
