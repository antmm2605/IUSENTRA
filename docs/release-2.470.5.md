# 2.470.5 — Le riletture notturne riprendono anche i fascicoli rimasti in errore

- Il giro ogni 10 minuti lavora sulla coda degli eventi; i fascicoli da aggiornare li accoda la rilettura notturna
  (tra mezzanotte e le 6). Questa accodava solo 2 fascicoli per giro e mai quelli rimasti in errore: i 99 fascicoli
  finiti in errore nella notte del 01/11/2026 non sarebbero più stati letti. Ora riprende, i più vecchi per primi,
  i fascicoli letti da un motore superato e quelli in errore o a metà, 4 per giro (circa 144 per notte).
