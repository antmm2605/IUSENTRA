# IUSENTRA — Quarto blocco: verso 95/100

Questo pacchetto completa il salto da repo buona a prodotto quasi maturo.

## Cosa aggiunge
- quality gates per Lex
- controllo budget performance
- workflow CI separato per qualità
- roadmap finale 95/100
- checklist hardening finale pre-release

## Perché è coerente con la tua repo reale
Hai già:
- strumenti coverage/gap/draft review CLI
- performance smoke dedicato
- local AI host bridge
- local signer avanzato

Quindi il blocco giusto adesso non è aggiungere altre feature:
è misurare, bloccare regressioni e imporre standard.

## Ordine di applicazione
1. copia i file di questo zip
2. integra il workflow CI opzionale
3. esegui:
   ```bash
   python tools/check_lex_quality_gates.py
   python tools/check_performance_budget.py
   python -m pytest -q tests/test_lex_quality_gates.py tests/test_performance_budget.py
   ```
4. se tutto va bene, aggiungi i check al workflow principale

## Obiettivo reale
Con i 4 blocchi applicati hai:
- repo coerente
- baseline Python allineata
- docs e governance più professionali
- refactor iniziale Local Signer
- quality gates veri su AI/performance

Questo è il livello corretto per dirti onestamente: sei in zona 95/100 strutturale.
