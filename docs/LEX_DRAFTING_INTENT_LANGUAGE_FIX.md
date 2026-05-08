# Lex — Fix Drafting Intent & Language Bug

**Versione:** 2.80.0  
**Data:** 2026-05-08  
**Gravità:** Critica (output in inglese per richieste di redazione italiana)

---

## Il Bug

**Input utente:** `"scrivi un diffida professionale se serve utilizza la ricerca web"`

**Comportamento errato (versione 2.79.x):**
```
Okay, here's a draft of a professional-sounding email for a formal demand letter.

Dear Recipient,

I am writing to formally notify you that...
```

**Comportamento corretto (versione 2.80.0):**
```
BOZZA — DIFFIDA E MESSA IN MORA

Con la presente si invita e diffida formalmente la S.V. ad adempiere entro...
```

---

## Analisi Causa Radice

Il bug aveva **4 cause sovrapposte**, ciascuna indipendente ma tutte necessarie per la correzione completa.

### Causa 1 — Routing gap in `lex/router.py`

`resolve_workflow()` aveva routing per tutti gli intenti noti (`bozza_atto`, `fascicolo`, ecc.) ma **non per `bozza_lettera`**. La richiesta di diffida cadeva nel fallback `"question_answering"`.

```python
# PRIMA (v2.79.x) — nessun routing per bozza_lettera
if intent == "draft_act_support":
    return "atto"
# ...
return "question_answering"  # ← la diffida finiva qui

# DOPO (v2.80.0) — routing dedicato
if intent == "bozza_lettera":
    return "drafting_legal_letter"
```

In aggiunta, il testo "diffida" non era nei `_LETTERA_HINTS` del router, quindi anche il routing testuale falliva.

### Causa 2 — Nessun workflow dedicato per lettere legali

`WORKFLOW_REGISTRY` non aveva nessun entry per `"drafting_legal_letter"`. Il `ChatWorkflow` generico non aveva vincoli linguistici → Ollama produceva inglese.

**Fix:** `lex/workflows/lettera_workflow.py` con system prompt italiano esplicito che:
- Vieta letteralmente `"Dear"`, `"Subject:"`, `"Please"`, `"I am writing"`, `"Okay, here's"`
- Impone struttura italiana: intestazione, oggetto DIFFIDA E MESSA IN MORA, corpo, riserva

### Causa 3 — `ItalianResponseGuard` non cablata nel pipeline

`ItalianLanguageGuard` (basata su `italian_response_guard.py`) **esisteva** ma non era nell'elenco `post_guards` dell'orchestratore:

```python
# PRIMA (v2.79.x) — guard linguistica assente
self.post_guards = [
    CitationGuard(),
    LegalReferenceGuard(),
    # ItalianResponseGuard MANCANTE
    ...
]

# DOPO (v2.80.0) — prima in pipeline, con priorità massima
self.post_guards = [
    ItalianLanguageGuard(),   # ← Prima di tutto
    EvidenceRelevanceGuard(), # ← Nuova
    CitationGuard(),
    ...
]
```

### Causa 4 — Pattern insufficienti nella guardia linguistica

`FORBIDDEN_ENGLISH_FRAGMENTS` aveva solo 10 pattern. Mancavano:
- `"dear recipient"`, `"dear sir"`, `"dear madam"` — saluti email inglesi
- `"subject:"`, `"i am writing"`, `"please be advised"` — formule commerciali inglesi  
- `"important disclaimer"`, `"sincerely yours"`, `"please consult"` — chiusure inglesi
- `"here's a draft"`, `"as requested,"`, `"feel free to"` — formule generiche AI inglesi

In aggiunta, nessun rilevamento di **risposte prevalentemente inglesi** senza formule note.

---

## Modifiche Implementate

### File creati

| File | Scopo |
|------|-------|
| `lex/workflows/lettera_workflow.py` | Workflow `drafting_legal_letter` con system prompt italiano obbligatorio |
| `lex/guards/italian_language_guard.py` | Classe guard che implementa `check(**kwargs)` → `GuardVerdict` con supporto `rewritten_draft` |
| `lex/guards/language_guard.py` | Funzione standalone `validate_italian_output()` con retry e fallback deterministico |
| `lex/guards/evidence_relevance_guard.py` | Filtra evidenze irrilevanti (sentenze, GU) per workflow di redazione |
| `tests/test_lex_drafting_intent.py` | 27 test cases (snapshot, routing, guard pipeline, profiling, template) |

### File modificati

| File | Modifica |
|------|---------|
| `lex/router.py` | Aggiunto routing `bozza_lettera → drafting_legal_letter`; aggiunto `_LETTERA_HINTS` per routing testuale; aggiunto `risposta_in_italiano → question_answering` |
| `lex/workflows/__init__.py` | Registrato `LetteraWorkflow` con 3 alias: `drafting_legal_letter`, `lettera`, `bozza_lettera` |
| `lex/guards/orchestrator.py` | Aggiunto `ItalianLanguageGuard` e `EvidenceRelevanceGuard` in `post_guards` |
| `lex/guards/italian_response_guard.py` | +35 pattern inglesi; aggiunto `_is_predominantly_english()` per rilevare testi anglofonii senza formule note |
| `lex/research/request_profile.py` | `bozza_lettera`: +14 pattern (scrivi/redigi diffida, costituzione in mora, ecc.); spostato prima di `fatturazione_economica` nel catalogo; aggiunto intent `risposta_in_italiano` |
| `lex/http_bounded_bridge.py` | Per `bozza_lettera`/`bozza_atto`: i token "web"/"cerca" NON attivano external search; solo token normativi specifici la giustificano; aggiunto `bozza_lettera` a `_REQUEST_PROFILE_INTENTS` |
| `lex/providers/deterministic_provider.py` | Aggiunto `build_diffida_messa_in_mora_template()` — fallback deterministico italiano completo; agganciato in `DeterministicProvider.generate()` per workflow lettera |
| `lex/contracts.py` | Aggiunto campo opzionale `rewritten_draft: str | None` a `GuardVerdict` |
| `lex/orchestrator_workflow.py` | Gestione `post.rewritten_draft` — se una guard riscrive, il draft riformulato rimpiazza l'output AI |

---

## Architettura Post-Fix

```
Input: "scrivi un diffida professionale se serve utilizza la ricerca web"
  │
  ▼
LexRequestProfile.classify_request()
  → intent = "bozza_lettera"  (r"\bdiffida\b" matched)
  │
  ▼
LexRouter.resolve_workflow()
  → "drafting_legal_letter"   (intent == "bozza_lettera")
  │
  ▼
WORKFLOW_REGISTRY["drafting_legal_letter"] = LetteraWorkflow
  → system_prompt: "Rispondi SEMPRE e SOLO in italiano. Mai una parola in inglese."
  │
  ▼
Ollama/Provider genera bozza
  │
  ▼ POST-GUARDS (in ordine)
  │
  ├─ ItalianLanguageGuard.check()
  │   ├─ detect_non_italian_response(draft) → False (sistema corretto)
  │   │   → GuardVerdict(allowed=True)
  │   │
  │   └─ Se output in inglese (es. modello non seguito istruzioni):
  │       ├─ Tenta rewrite con _REPLACEMENTS
  │       ├─ Se rewrite OK → GuardVerdict(allowed=True, rewritten_draft=testo_italiano)
  │       └─ Se tutto inglese → usa build_diffida_messa_in_mora_template() come fallback
  │
  ├─ EvidenceRelevanceGuard.check()
  │   → Segnala se sentenze/GU non pertinenti alla bozza
  │
  └─ [altri guards: citazioni, allucinazioni, qualità, ecc.]
  │
  ▼
Output: Bozza italiana professionale
```

---

## Invarianti da Rispettare

1. **Mai rimuovere `ItalianLanguageGuard` da `post_guards`** — è il guardrail finale contro output inglesi
2. **`bozza_lettera` deve precedere `fatturazione_economica`** nel catalogo intenti — "messa in mora" è un istituto legale, non economico
3. **`build_diffida_messa_in_mora_template()`** non deve mai contenere testo in inglese — è il fallback di sicurezza
4. **Il campo `rewritten_draft`** in `GuardVerdict` non va rimosso — il flusso in `orchestrator_workflow.py` lo usa per rimpiazzare draft inglesi

---

## Acceptance Criterion — Verifica

L'input originale del bug **deve** produrre:
- Workflow: `drafting_legal_letter` (verificabile con `LexRouter().resolve_workflow(request)`)
- Intent: `bozza_lettera` (verificabile con `classify_request(query).intent`)
- Output: contiene `"si invita e diffida formalmente"` e `"in difetto"` e `"riserva di agire"`
- Output: NON contiene `"Okay, here's"`, `"Dear"`, `"I am writing"`

**Test di regressione:**
```bash
python -m pytest tests/test_lex_drafting_intent.py::TestSnapshotOriginalBug -v
```

**Suite completa:**
```bash
python -m pytest tests/test_lex_drafting_intent.py -v
# Risultato atteso: 27 passed
```
