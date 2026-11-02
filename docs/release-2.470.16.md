# 2.470.16 — Letture dei fascicoli non più ferme per un solo documento; scadute coerenti nella pagina Fascicoli

- Controllo dei lavori notturni del 02/11/2026: 241 fascicoli su 336 risultavano con la lettura in errore. Il registro
  non dava più «database is locked» (correzione della 2.470.13), ma il riscontro del giudice sul testo nativo
  sollevava «Fonte cambiata» quando l'impronta del file non coincideva e fermava la lettura dell'intero fascicolo.
  Ora quel solo documento resta senza riscontro nativo (nessun dato promosso, si rilegge con la nuova impronta) e
  il resto del fascicolo si legge; l'impronta d'archivio è riconosciuta. Test in
  `tests/test_giudice_archivio_recovery.py` (fallisce senza la correzione).
- Pagina Fascicoli, «Scadenze urgenti»: la 2.470.15 aveva corretto solo la via di calcolo di riserva; la pagina usa il
  catalogo SQL (`pct.fascicoli_list_query.deadline_overview`), che contava ancora le udienze passate tra le
  scadute (9 invece di 3). Ora esclude le udienze passate (V28; artt. 126 e 127-ter c.p.c.) e usa il giorno di
  Roma. Il catalogo conserva il riepilogo completo delle udienze passate. Test in
  `tests/test_fascicoli_list_query.py` (fallisce senza la correzione).
