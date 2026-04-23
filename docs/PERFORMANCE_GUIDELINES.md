# Performance Guidelines

## Obiettivo
Bloccare regressioni evidenti prima che arrivino in produzione.

## Minimo richiesto
- smoke benchmark esistente
- controllo import / bootstrap / lex path
- soglie esplicite quando avrai numeri stabili

## Evoluzione
Fase attuale:
- presenza e coerenza di performance_smoke.py

Fase successiva:
- output JSON benchmarkato
- comparazione run corrente vs baseline
- fail CI su regressioni superiori a soglia
