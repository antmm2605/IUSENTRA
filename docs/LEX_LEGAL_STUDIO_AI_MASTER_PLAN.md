# LEX Legal Studio AI — Master Plan (v2.200.0)

Piano di trasformazione Lex in AI professionale per studi legali italiani. 20 fasi completate.

## Obiettivo

Trasformare Lex da chatbot generico a **AI legale professionale** per studi legali italiani che:
- Risponde sempre in italiano, con linguaggio professionale forense
- Non usa mai disclaimer "consulta un avvocato"
- Produce bozze legali strutturate senza chiedere chiarimenti preventivi
- Calcola termini processuali con base normativa
- Guida il deposito telematico con checklist operative
- Rispetta DM 55/2014 per calcolo onorari

## Architettura risultante

```
Domanda avvocato
    │
    ▼
LexRouter (12 livelli di priorità)
    │
    ├── Intent Matrix (13 macro-intent)
    │
    ├── Request Profile (classificatore)
    │
    ▼
Workflow selezionato
    │
    ├── AnswerContract (quality constraints)
    │
    ├── EvidenceRelevanceGuard
    │
    ├── Provider (Deterministic | LLM | Research)
    │
    ├── LegalAnswerQualityGuard
    │
    ▼
Risposta professionale italiana
```

## Le 20 Fasi

### Fase 1 — Audit codebase Lex
Analisi completa di router, contracts, orchestrator, providers, guards, workflows, prompts, tools.

### Fase 2 — Intent Matrix
`lex/research/legal_studio_intent_matrix.py` — 13 MacroIntent con priorità ordinata.

### Fase 3 — Answer Contracts
`lex/contracts.py` — contratti per workflow con `italian_only`, `disclaimer_suppressed`, `no_english_output`.

### Fase 4 — LexRouter a 12 livelli
`lex/router.py` — routing deterministico a priorità esplicita, override per feedback/telematico/giurisprudenza specifica.

### Fase 5 — Tool Registry
`lex/tools/legal_studio_tools.py` — 25+ tool: tariffario DM 55, termini processuali, checklist deposito, diagnosi errori PST/PDP/PAT.

### Fase 6 — 8 Template di redazione
`lex/providers/deterministic_provider.py` — diffida, sollecito pagamento, PEC formale, lettera al cliente, contestazione fattura, richiesta documenti, invito a stipula, riscontro comunicazione.

### Fase 7 — EvidenceRelevanceGuard esteso
`lex/guards/evidence_relevance_guard.py` — logica per drafting, termini processuali, deposito telematico.

### Fase 8 — LegalAnswerQualityGuard
`lex/guards/legal_answer_quality_guard.py` — pipeline 6 stadi: disclaimer, chatbot, JSON, inglese, generici, fonti.

### Fase 9 — FeedbackWorkflow
`lex/workflows/feedback_workflow.py` — gestione correzioni avvocato senza comportamento difensivo.

### Fase 10 — GiurisprudenzaSpecificaWorkflow
`lex/workflows/giurisprudenza_specifica_workflow.py` — mai inventare numeri sentenza, suggerisce DeJure/Italgiure.

### Fase 11 — TerminiProcessualiWorkflow
`lex/workflows/termini_processuali_workflow.py` — 16 tipi termine con norma, calcolo deterministico, sospensione feriale agosto.

### Fase 12 — DepositoTelematicoWorkflow
`lex/workflows/deposito_telematico_workflow.py` — checklist PST/PDP/PAT/PTT, diagnosi errori comuni.

### Fase 13 — Workflow Registry aggiornato
`lex/workflows/__init__.py` — 20 workflow registrati.

### Fase 14 — Request Profile aggiornato
`lex/research/request_profile.py` — 4 nuovi intent in testa al catalogo.

### Fase 15 — Provider dispatch per template
`DeterministicProvider.generate()` — dispatch per keyword in query (sollecito, PEC, contestazione, ecc.).

### Fase 16 — Routing conflicts risolti
Priorità esplicita: feedback > redazione > termini > telematico > PEC > giurisprudenza specifica > normativa > economico > fascicolo > documenti > cabina > chat.

### Fase 17 — Test suite completa
`tests/test_lex_legal_studio_full.py` — 95 test in 20 classi (TC-01…TC-20): routing, contracts, guards, tools, templates, snapshot, pipeline.

### Fase 18 — Debug payload v2.0
`lex/formatting/debug_payload_builder.py` — 46 campi: intent, routing_priority, guard_verdicts, answer_contract, latency_ms, token usage, session/request ID.

### Fase 19 — Documentazione
`docs/LEX_INTENT_MATRIX.md`, `docs/LEX_TOOL_REGISTRY.md`, `docs/LEX_RESPONSE_QUALITY_GUARD.md`, `docs/LEX_LEGAL_STUDIO_AI_MASTER_PLAN.md`.

### Fase 20 — Versione 2.200.0
Bump in `pct/__init__.py`, `Dockerfile`, `railway.toml`. Commit e push su entrambi i branch.

## Regole non negoziabili (invarianti di produzione)

| Regola | Applicazione |
|--------|-------------|
| Sempre in italiano | `LegalAnswerQualityGuard` stadio 4, tutti i system prompt |
| Mai "consulta un avvocato" | `LegalAnswerQualityGuard` stadio 1 |
| Mai formule chatbot | `LegalAnswerQualityGuard` stadio 2 |
| Mai JSON non richiesto | `LegalAnswerQualityGuard` stadio 3 |
| Mai inventare sentenze | `GiurisprudenzaSpecificaWorkflow`, `AnswerContract.no_invented_references` |
| Mai chiedere chiarimenti prima di una bozza | `DeterministicProvider` — produce subito il template |
| Feedback senza comportamento difensivo | `FeedbackWorkflow` — riconosce la correzione e propone riformulazione |

## Metriche di qualità

| Metrica | Target | Misurazione |
|---------|--------|-------------|
| Risposte in italiano | 100% | `LegalAnswerQualityGuard` |
| Disclaimer vietati | 0% | `DISCLAIMER_MARKERS` |
| Template corretto per intent | ≥95% | TC-13 snapshot test |
| Routing corretto | ≥95% | TC-01…TC-05 routing tests |
| Termini calcolati con norma | 100% | `TerminiProcessualiWorkflow` |
