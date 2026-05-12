# Responsive Report React

Generato: 2026-05-08

## Route controllate

Route full/partial principali: amministrazione, studio, backup, sito studio, fatturazione, incassi, preventivi, compensi, tariffario, template atti, redazione atti, giurisprudenza, Legal Intelligence, news, mediazione, ricerca legale.

## Miglioramenti applicati

- Aggiunte classi responsive per stati, skeleton, wizard stepper, compliance panel, channel card, message list e LexPanel in `iusentra-design-system.css`.
- Le nuove route promosse evitano hero/action bar con CTA legacy primaria e mantengono filtri/card/lista in layout flessibile.
- LexPanel e liste comunicazioni hanno breakpoint mobile con colonna singola e azioni raggiungibili.
- 2026-05-09: smoke browser Chrome su `/deposito/checklist`, `/strumenti-legali` e `/strumenti-operativi` in viewport desktop 1440x900, tablet 834x1112 e mobile 390x844. Nessun overflow orizzontale; shell React, titoli, card e azioni risultano visibili.
- 2026-05-10: smoke browser Chrome su Docker locale 2.214.0 in desktop 1440x950 e mobile 390x844 per `/redazione-atti`, `/template-atti`, `/statistiche`, `/ricerca-legale`, `/legal-intelligence/news`, `/giurisprudenza`, `/strumenti-legali`, `/strumenti-operativi`, `/deposito/checklist`, `/sito-studio/contatti`, dettagli PEC/email ordinaria e `/admin/database`. Nessun overflow orizzontale e nessun testo tecnico vietato visibile.
- 2026-05-10: smoke browser Tariffario 2.214.1 in desktop 1366x768, tablet 900x720 e mobile 390x844. Desktop: il riepilogo in tempo reale resta visibile durante lo scroll dei parametri; tablet/mobile: layout a colonna singola senza sovrapposizioni. Verificato anche `/preventivi/` con tre link `Preventivo guidato` verso `/preventivi/wizard` e wizard caricato senza errori console.
- 2026-05-11: smoke browser Docker locale 2.216.0 su `/fascicoli/nuovo` in desktop 1440x950, tablet 834x1112 e mobile 390x844. Pannelli collassabili, `Fascicolo Veloce`, upload documenti/email EML e colonna laterale visibili; `scrollWidth` uguale al viewport in tutti i formati.
- 2026-05-11: smoke browser Docker locale 2.216.5 su `/fascicoli/nuovo` dopo selettori guidati. Desktop: sezioni `Dati generali`, `Parti` e `Identificazione giudiziale` visibili con cliente, soggetto controparte e autorita' giudiziaria. Tablet 834x1112: layout a colonna singola senza overflow orizzontale. Mobile 390x844: card compatte, campi controparte/CF e campo autorita' giudiziaria leggibili; nessun errore console.
- 2026-05-12: smoke Chrome headless Docker locale 2.218.0 su `/template-atti/catalogo` in desktop 1440x950, tablet 834x1112 e mobile 390x844. Cartabia, timbro studio e prefill sono visibili; `scrollWidth` uguale al viewport in tutti i formati, nessun errore console e nessun testo tecnico vietato. Verificato anche `/template-atti/compila/CIV_CIT_001` desktop con timbro e `Completa dati mancanti`.

## Rischi residui

- Verifica browser visuale completata per le tre route promosse in 2.210.0; restano da coprire solo route future o legacy quando verranno promosse.
- Tabelle legacy e sotto-route telematiche rimangono da verificare quando avranno wrapper React completi.

## Esito

Responsive minimo aggiornato per i componenti condivisi nuovi; nessuna route e' stata promossa solo per estetica.
