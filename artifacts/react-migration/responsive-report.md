# Responsive Report React

Generato: 2026-05-08

## Route controllate

Route full/partial principali: amministrazione, studio, backup, sito studio, fatturazione, incassi, preventivi, compensi, tariffario, template atti, redazione atti, giurisprudenza, Legal Intelligence, news, mediazione, ricerca legale.

## Miglioramenti applicati

- Aggiunte classi responsive per stati, skeleton, wizard stepper, compliance panel, channel card, message list e LexPanel in `iusentra-design-system.css`.
- Le nuove route promosse evitano hero/action bar con CTA legacy primaria e mantengono filtri/card/lista in layout flessibile.
- LexPanel e liste comunicazioni hanno breakpoint mobile con colonna singola e azioni raggiungibili.

## Rischi residui

- Verifica browser visuale non ancora completata in questa sessione per tutte le route perche il lavoro e' stato concentrato su gate, dati e compliance.
- Tabelle legacy e sotto-route telematiche rimangono da verificare quando avranno wrapper React completi.

## Esito

Responsive minimo aggiornato per i componenti condivisi nuovi; nessuna route e' stata promossa solo per estetica.
