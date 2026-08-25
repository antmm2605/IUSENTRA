# Incremento presidio: azione e fonte leggibili — 25/08/2026

## Obiettivo

Eliminare dalle card di priorità del fascicolo gli estratti OCR non contestualizzati, senza togliere la fonte o il dettaglio probatorio verificabile.

## Modifiche

- La priorità **Presìdi del fascicolo** usa il titolo dell'azione operativa e, quando presente, la fonte leggibile del documento. Non usa più il testo libero `reason` come microcopy della card.
- La card **Contributo unificato** mostra la fonte e invita ad aprire il presidio economico per verificare importo, ricevuta o esenzione. L'estratto OCR resta disponibile soltanto nel dettaglio operativo, dove può essere valutato nel proprio contesto.
- Il collegamento diretto `#presidio-fascicolo` passa lo stato di apertura al componente React: il pannello non viene più richiuso da un successivo rendering dopo il caricamento lazy.

## Dati e sicurezza

Nessun dato è stato modificato. Non sono stati introdotti fallback JSON, nuove API o cambiamenti nei criteri economici: importo, stato, documento-fonte e controlli restano quelli provenienti dal modello SQL/API già in uso.

## Verifiche eseguite

- `pnpm --dir frontend run build` — superato.
- `python -m pytest tests/test_regia_ui_react.py -q --tb=short` — superato (`26 passed`).
- `python -m pytest tests/test_fascicolo_detail_ux.py -q -x --tb=short -k 'dettaglio_fascicolo_espone_ux_documenti_e_cabina_collassabile or presidio_economico_unifica_contributo_e_provvedimenti_nella_stessa_superficie'` — superato (`2 passed`).
- `pnpm --dir frontend run build` include `tsc --noEmit` — superato.
- Copia locale Docker: `iusentra-app` healthy e `http://127.0.0.1:8080/api/pronto` ha risposto `ok: true` alle 16:31 Europe/Rome.
- Prima dell'ultimo raffinamento della card economica, la pagina reale `DC5BF1DB#presidio-fascicolo` ha mostrato il pannello aperto e la priorità: `Registrare contributo unificato (€ 98,00) · Fonte: Ricevuta pagoPA`.

## Verifica visiva da ripetere

Il controllo browser integrato non ha consentito un secondo caricamento della pagina locale dopo l'ultimo affinamento, pur con contenitore locale healthy. La verifica materiale aggiornata della sola card economica resta quindi da ripetere sulla scheda reale `127.0.0.1:8080` prima di attestare l'accettazione visiva dell'incremento.
