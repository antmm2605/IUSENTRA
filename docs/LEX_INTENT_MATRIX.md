# LEX — Intent Matrix (v2.200.0)

Matrice di 13 macro-intent con priorità ordinata. Classificazione automatica via `lex.research.legal_studio_intent_matrix`.

## Priorità di routing

| Priorità | Intent | Workflow | Pattern chiave |
|----------|--------|----------|----------------|
| 1 | `lex_feedback_diagnostico` | `lex_feedback_diagnostico` | "non hai capito", "riprova", "correggiti" |
| 2 | `redazione_legale` | `drafting_legal_letter` | "scrivi una diffida", "bozza lettera", "messa in mora" |
| 3 | `agenda_scadenze_termini` | `termini_processuali` | "termine per", "giorni dalla notifica", "perentorio" |
| 4 | `telematico_deposito` | `deposito_telematico` | "deposito telematico", "checklist deposito", "errore PST" |
| 5 | `pec_comunicazioni` | `pec_comunicazioni` | "scrivi una PEC", "comunicazione formale" |
| 6 | `fascicolo_operativo` | `fascicolo` | "fascicolo", "udienza", "controparte" |
| 7 | `analisi_documentale` | `document_analysis` | "analizza documento", "estratto da", "clausola" |
| 8 | `giurisprudenza` | `giurisprudenza` | "sentenza", "cassazione", "orientamento" |
| 9 | `normativa` | `normativa` | "art.", "legge n.", "decreto legislativo" |
| 10 | `economico_forense` | `tariffario` | "onorario", "tariffa", "DM 55", "preventivo" |
| 11 | `fatturazione_incassi` | `fatturazione` | "fattura", "pagamento", "nota spese" |
| 12 | `cabina_studio` | `cabina` | "prossime scadenze", "cosa fare oggi" |
| 13 | `strategia_legale` | `research` | "strategia difensiva", "come impostare" |

## API

```python
from lex.research.legal_studio_intent_matrix import (
    classify_from_matrix,
    workflow_for_intent,
    response_schema_for_intent,
    all_intents,
)

intent = classify_from_matrix("scrivi una diffida per mancato pagamento")
# → "redazione_legale"

workflow = workflow_for_intent(intent)
# → "drafting_legal_letter"

schema = response_schema_for_intent(intent)
# → {"sections": ["intestazione", "fatto", "diritto", ...], ...}
```

## MacroIntent — struttura dataclass

```python
@dataclass(frozen=True)
class MacroIntent:
    name: str                    # identificatore
    priority: int                # 1 = massima precedenza
    workflows: tuple[str, ...]   # workflow candidati
    patterns: tuple[str, ...]    # regex o keyword
    response_schema: dict        # sezioni output attese
    provider_hint: str           # "deterministic" | "llm" | "auto"
```

## Regole di classificazione

1. Il classificatore scorre gli intent in ordine di priorità crescente
2. Per ogni intent testa i `patterns` sulla domanda normalizzata (lowercase, strip)
3. Al primo match ritorna l'`intent.name`
4. Se nessun pattern matcha → fallback a `"chat"` (question_answering)

## Contratti per workflow

Ogni workflow ha un `AnswerContract` in `lex/contracts.py` che definisce:
- `sections`: sezioni attese nella risposta
- `provider_hint`: provider preferito
- `metadata`: flags di qualità (`italian_only`, `disclaimer_suppressed`, ecc.)
- `allow_abstention`: se il provider può rispondere "non so"
