# Roadmap enterprise verso 100/100

## Premessa onesta
Il 100/100 non arriva da un singolo refactor.
Arriva da:
- qualità continua
- regressioni basse
- telemetria
- disciplina release
- manutenzione costante

## Fase 1 — Repo governata
Completata con i blocchi 1-4:
- baseline Python coerente
- governance check
- security docs
- quality gates
- performance budget
- boundary checks

## Fase 2 — Osservabilità
Da introdurre:
- eventi strutturati per login, import, sync, signer, AI
- correlazione request_id / pratica_id / tenant_id
- log level chiaro
- retention log

## Fase 3 — Release train
Serve una policy:
- dev
- staging
- production
- hotfix

Ogni release deve avere:
- changelog sintetico
- smoke test
- rollback plan
- checklist pre-release

## Fase 4 — Multi-studio / SaaS
Se vuoi scalare davvero:
- tenant isolation rigorosa
- config per tenant
- storage strategy chiara
- metriche per tenant
- audit trail robusto

## Fase 5 — Maturità AI
Lex deve essere:
- misurabile
- limitato
- tracciabile
- non “magico”

Metriche chiave:
- citation rate
- fallback rate
- hallucination incidents
- empty response rate
- latency p50 / p95

## Giudizio finale
Con i blocchi 1-5 applicati bene:
- sei in area molto forte
- non sei “perfetto”, ma sei governato
- il prossimo salto dipende più dalla disciplina che dal codice
