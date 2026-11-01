# 2.470.12 — Consegne delle ricevute rimesse in coda durante il deploy

- Il deploy della 2.470.11 si è fermato nella preparazione degli indici delle ricevute («Consegne delle ricevute in
  attesa di recupero: catalogo non confermato»): con il registro bloccato, la versione in servizio aveva segnato come
  fallite (5 tentativi) alcune consegne verso il catalogo delle ricevute; la preparazione le contava come pendenti ma
  non le ritentava, e nessun deploy poteva più concludersi. Ora, dopo il backup verificato, la preparazione rimette in
  coda le consegne fallite o rimandate e le consegna subito; la proiezione ricalcola il fascicolo ed è ripetibile.
  Test nuovo in `tests/test_receipt_archive_query.py` (fallisce senza la correzione).
- Spazio sul server: svuotata la cache di costruzione Docker inutilizzata (48 GB, da 14 a 56 GB liberi); il backup
  preventivo della 2.470.11 non trovava spazio.
- Contiene la 2.470.9, la 2.470.10 e la 2.470.11, mai arrivate in produzione.
