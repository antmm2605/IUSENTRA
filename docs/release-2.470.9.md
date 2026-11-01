# 2.470.9 — Registro delle letture senza blocchi

- Il registro delle letture (`pct/registro_letture/repository.py`) passa alla modalità WAL, come gli altri archivi
  SQLite (scheduler, OCR, telematico): chi legge non attende più chi scrive. Verifica in produzione del 01/11/2026:
  durante il recupero delle letture la Panoramica, il riepilogo delle discordanze del Controllo Studio e le stesse
  letture fallivano con «database is locked» (anche la causa dei 99 fascicoli «in errore» del mattino).
- Lo schema si prepara una volta per processo, non a ogni apertura del registro; la migrazione del vecchio vincolo
  delle ricevute chiede il blocco in scrittura solo se c'è davvero qualcosa da migrare.
- Nuovo test `tests/test_registro_letture_wal.py`: apertura e lettura del registro mentre un altro processo scrive.
- Workflow «Stato delle pianificazioni»: errori recenti dell'app e dello scheduler (solo punti del codice e tipo
  d'errore, nessun dato del cliente).
- Base normativa: art. 3 D.M. 44/2011 e art. 20 CAD (integrità e tracciabilità delle letture dei documenti).
