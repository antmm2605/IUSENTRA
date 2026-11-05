# Release 2.480.8 — nessun documento resta senza lettura

Dalla verifica online del 05/11/2026 (2.480.7): 8.466 documenti mai indicizzati, 2.443 mai catalogati, 443 senza
OCR; la sentenza del fascicolo 9DC39668 (08/10/2026) non indicizzata, quindi nessuna definizione proposta.

1. **Letture mancanti in coda** — a ogni giro della lettura automatica (ogni 10 minuti) entrano in coda fino a 4
   fascicoli con letture di base mancanti (OCR, indice documentale, catalogo, motore documenti), i meno recenti
   per primi; lo stesso fascicolo non torna in coda prima di 6 ore. Un fascicolo senza letture mancanti non entra:
   nessuna rilettura dell'invariato (`web/services/archivio_letture_runtime.py`, `accoda_letture_pendenti`).
2. **Backup degli indici interrotto** — la cartella senza manifest si elimina e il backup si rifà, invece di
   accumulare copie incomplete (`scripts/query_index_backup.py`).

Base: art. 3 D.M. 44/2011 e art. 20 CAD (registro delle letture).
