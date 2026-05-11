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
- 2026-05-11: build Vite 2.215.7 completata in 6.15s. Bundle principale `index-SZkr27sC.js` 430.21 kB (128.12 kB gzip); CSS principale `index-CG6vHJFj.css` 121.43 kB (22.29 kB gzip); chunk `StudioModulePage-DZTXfIER.js` 11.66 kB (4.16 kB gzip) e CSS `StudioModulePage-D2p9hbMw.css` 10.31 kB (2.30 kB gzip).
- 2026-05-11: `/documenti` verificata in Docker locale 2.215.7 dopo warm-up tenant: desktop 352.9 ms, tablet 210.8 ms, mobile 167.9 ms a contenuto React visibile; `DOMContentLoaded` rispettivamente 261.7 ms, 194.0 ms, 139.0 ms; nessun overflow orizzontale, nessun errore console, nessuna richiesta oltre 1s e nessun termine tecnico visibile.
- 2026-05-11: osservato un primo accesso tenant autenticato post-riavvio che puo' arrivare a circa 60s prima della shell. Il caso e' registrato in `pytest-open-issues.md` come warm-up tenant preesistente; non riguarda il payload `/api/v1/ui/studio-modules/documenti`, che risponde 200 e resta privo di record `demo`/`sample`.
- 2026-05-11: build Vite finale 2.216.0 completata in 6.02s dopo Fascicolo Veloce. Bundle principale `index-Da78y99a.js` 430.21 kB (128.12 kB gzip); CSS principale `index-CG6vHJFj.css` 121.43 kB (22.29 kB gzip); chunk `FascicoliPage-CxUx2oAi.js` 130.73 kB (34.08 kB gzip) e CSS `FascicoliPage-CbTgM5LC.css` 54.06 kB (8.56 kB gzip). La modifica aggiunge solo pannelli leggeri e input file condizionati, senza nuove dipendenze.
- 2026-05-11: `/fascicoli/nuovo` verificata in Docker locale 2.216.0 su desktop/tablet/mobile. Primo accesso desktop post-restart: 146088.2 ms a contenuto visibile con bootstrap tenant gia' documentato e richieste lente su time tracking/notifiche/API fascicolo; passaggi caldi desktop 761.3 ms, 647.2 ms, 538.7 ms; tablet 692.5 ms; mobile 646.7 ms. Nessun overflow orizzontale, nessun errore console, nessuna richiesta oltre 1s sui passaggi caldi.
- 2026-05-11: build Vite 2.216.1 completata in 5.84s dopo hotfix sessione PST Local Signer. Bundle principale `index-y9B4mVr4.js` 430.21 kB (128.12 kB gzip); CSS principale invariato `index-CG6vHJFj.css` 121.43 kB (22.29 kB gzip); chunk `TelematicoSurfacePage-3VycwlEO.js` 58.61 kB (17.51 kB gzip) e CSS `TelematicoSurfacePage-hCFGWhgQ.css` 21.95 kB (3.91 kB gzip). Nessuna nuova dipendenza introdotta.

## Rischi residui

- `frontend/src/App.tsx` resta un file monolitico legacy React da spezzare in tranche successive.
- Diverse feature usano ancora fetch locali storici; il re-export preserva compatibilita ma non completa la convergenza totale al nuovo client.
- Primo accesso tenant autenticato dopo restart Docker/produzione da profilare separatamente sui bootstrap tenant, senza ripetere diagnosi generica su `/api/pronto`.
