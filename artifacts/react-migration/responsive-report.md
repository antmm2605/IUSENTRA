# Responsive Report React

Generato: 2026-05-08

## Route controllate

Route full/partial principali: amministrazione, studio, backup, sito studio, fatturazione, incassi, preventivi, compensi, tariffario, template atti, redazione atti, giurisprudenza, Legal Intelligence, news, mediazione, ricerca legale.

## Miglioramenti applicati

- Aggiunte classi responsive per stati, skeleton, wizard stepper, compliance panel, channel card, message list e LexPanel in `iusentra-design-system.css`.
- Le nuove route promosse evitano hero/action bar con CTA legacy primaria e mantengono filtri/card/lista in layout flessibile.
- LexPanel e liste comunicazioni hanno breakpoint mobile con colonna singola e azioni raggiungibili.
- 2026-05-22: preset grafico globale 2.248.12 verificato su `/fascicoli` desktop 1440x900, tablet 1024x900 e mobile 390x844. Desktop: MainSurface e SupportRail allineate a 670 px, footer/paginazione dentro DataSurface, selettore `Per pagina` nel toolbar alto e nessun overflow orizzontale. Tablet: rail sotto la DataSurface e nessun overflow. Mobile: contenuto principale e rail impilati, tabella contenuta e nessun overflow fuori schermo. `/sito-studio/builder` resta escluso dal preset.
- 2026-05-09: smoke browser Chrome su `/deposito/checklist`, `/strumenti-legali` e `/strumenti-operativi` in viewport desktop 1440x900, tablet 834x1112 e mobile 390x844. Nessun overflow orizzontale; shell React, titoli, card e azioni risultano visibili.
- 2026-05-10: smoke browser Chrome su Docker locale 2.214.0 in desktop 1440x950 e mobile 390x844 per `/redazione-atti`, `/template-atti`, `/statistiche`, `/ricerca-legale`, `/legal-intelligence/news`, `/giurisprudenza`, `/strumenti-legali`, `/strumenti-operativi`, `/deposito/checklist`, `/sito-studio/contatti`, dettagli PEC/email ordinaria e `/admin/database`. Nessun overflow orizzontale e nessun testo tecnico vietato visibile.
- 2026-05-10: smoke browser Tariffario 2.214.1 in desktop 1366x768, tablet 900x720 e mobile 390x844. Desktop: il riepilogo in tempo reale resta visibile durante lo scroll dei parametri; tablet/mobile: layout a colonna singola senza sovrapposizioni. Verificato anche `/preventivi/` con tre link `Preventivo guidato` verso `/preventivi/wizard` e wizard caricato senza errori console.
- 2026-05-11: smoke browser Docker locale 2.216.0 su `/fascicoli/nuovo` in desktop 1440x950, tablet 834x1112 e mobile 390x844. Pannelli collassabili, `Fascicolo Veloce`, upload documenti/email EML e colonna laterale visibili; `scrollWidth` uguale al viewport in tutti i formati.
- 2026-05-11: smoke browser Docker locale 2.216.5 su `/fascicoli/nuovo` dopo selettori guidati. Desktop: sezioni `Dati generali`, `Parti` e `Identificazione giudiziale` visibili con cliente, soggetto controparte e autorita' giudiziaria. Tablet 834x1112: layout a colonna singola senza overflow orizzontale. Mobile 390x844: card compatte, campi controparte/CF e campo autorita' giudiziaria leggibili; nessun errore console.
- 2026-05-12: smoke Chrome headless Docker locale 2.218.0 su `/template-atti/catalogo` in desktop 1440x950, tablet 834x1112 e mobile 390x844. Cartabia, timbro studio e prefill sono visibili; `scrollWidth` uguale al viewport in tutti i formati, nessun errore console e nessun testo tecnico vietato. Verificato anche `/template-atti/compila/CIV_CIT_001` desktop con timbro e `Completa dati mancanti`.
- 2026-05-14: smoke Playwright/CDP Docker locale 2.236.3 su `/agenda/nuovo` in desktop 1440x950, tablet 834x1112 e mobile 390x844. Avvocato responsabile precompilato, ricerca cliente senza error boundary e prefill cliente verificati; tablet/mobile senza overflow orizzontale. Su desktop verificate anche le scrollbar superiori sincronizzate di `/clienti`, `/soggetti` e `/fascicoli`.
- 2026-05-15: audit Chrome CDP 2.236.4 su 46 route x desktop/mobile, con sessione tenant reale. Nessun overflow orizzontale rilevato; tabelle IUSENTRA trasformate in card leggibili su mobile tramite `data-label`; action row, bottoni e topbar supportano wrapping a 125%, 150% e mobile landscape senza taglio del testo.
- 2026-05-15: rifinitura 2.236.5 verificata con Chrome CDP su 46 route desktop/mobile e retry mirato `/soggetti/nuovo` mobile. La barra Ricerca Studio usa font-size stabile, hint non tecnico e nasconde il suggerimento compatto su mobile; nessun overflow orizzontale o avviso residuo sulle rotte passate.
- 2026-05-15: `/sito-studio/builder` 2.239.1 verificato con Chrome CDP desktop 1600x1000, tablet e mobile. Desktop: pannello sinistro 380px, barra icone 92px, preview 1121px e resize a 480px senza overflow. Tablet/mobile: preview mantiene menu integrato e navigazione visibile, il pannello degrada senza maniglia e la pagina resta senza sovrapposizioni.
- 2026-05-16: `/legal-intelligence`, `/legal-intelligence/mediazione`, `/ricerca-legale` e `/ricerca-legale?q=mediazione` 2.239.3 verificati con Chrome CDP desktop/mobile. La scheda contesto laterale diventa blocco non sticky sotto 1180px, filtri e ricerche guidate collassano a colonna singola, nessun overflow orizzontale.
- 2026-05-16: `/ricerca-legale/mediazione` e `/legal-intelligence/mediazione` 2.243.4 verificati con Chrome CDP desktop 1440x980, tablet 834x1112 e mobile 390x844. La tabella registro resta contenuta nel wrapper, i 5 filtri degradano a colonna singola, 80 righe visibili e nessun overflow orizzontale.

## Rischi residui

- Verifica browser visuale completata per le tre route promosse in 2.210.0; restano da coprire solo route future o legacy quando verranno promosse.
- Tabelle legacy e sotto-route telematiche rimangono da verificare quando avranno wrapper React completi.

## Esito

Responsive minimo aggiornato per i componenti condivisi nuovi; nessuna route e' stata promossa solo per estetica.
