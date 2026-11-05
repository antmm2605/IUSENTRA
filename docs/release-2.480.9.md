# Release 2.480.9 — log dello scheduler senza DEBUG

Correzione nata dal controllo sul server del 05/11/2026.

1. **Scheduler a livello DEBUG** — la prova di resilienza («crash drill») crea nello stesso processo dello
   scheduler un'app isolata con `TESTING=True`; la configurazione dei log portava allora a DEBUG l'intero processo.
   Lo scheduler di produzione scriveva circa 147.000 righe di `pdfminer` ogni 2 minuti, con CPU e memoria in
   crescita (fino a 6 GB, swap pieno e server bloccato alcuni minuti). Ora l'app isolata eredita il livello del
   servizio (`PCT_LOG_LEVEL`, predefinito INFO) (`pct/operational_resilience.py`).
2. **Librerie PDF mai sotto WARNING** — `pdfminer`, `pdfplumber`, `PIL` e `fontTools` non scrivono log di dettaglio
   qualunque sia il livello del servizio (`web/services/structured_logging.py`).

Test: `tests/test_structured_logging.py` (2 nuovi), `tests/test_operational_resilience.py`.
