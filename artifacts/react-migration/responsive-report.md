# Responsive Report React

Generato: 2026-05-08

## Route controllate

Route full/partial principali: amministrazione, studio, backup, sito studio, fatturazione, incassi, preventivi, compensi, tariffario, template atti, redazione atti, giurisprudenza, Legal Intelligence, news, mediazione, ricerca legale.

## Miglioramenti applicati

- Aggiunte classi responsive per stati, skeleton, wizard stepper, compliance panel, channel card, message list e LexPanel in `iusentra-design-system.css`.
- Le nuove route promosse evitano hero/action bar con CTA legacy primaria e mantengono filtri/card/lista in layout flessibile.
- LexPanel e liste comunicazioni hanno breakpoint mobile con colonna singola e azioni raggiungibili.
- 2026-05-09: smoke browser Chrome su `/deposito/checklist`, `/strumenti-legali` e `/strumenti-operativi` in viewport desktop 1440x900, tablet 834x1112 e mobile 390x844. Nessun overflow orizzontale; shell React, titoli, card e azioni risultano visibili.

## Rischi residui

- Verifica browser visuale completata per le tre route promosse in 2.210.0; restano da coprire solo route future o legacy quando verranno promosse.
- Tabelle legacy e sotto-route telematiche rimangono da verificare quando avranno wrapper React completi.

## Esito

Responsive minimo aggiornato per i componenti condivisi nuovi; nessuna route e' stata promossa solo per estetica.
