# Codex Harness per IUSENTRA

Questa cartella contiene controlli leggeri per aiutare Codex a lavorare meglio su IUSENTRA.

## Scopo

I controlli verificano che un task:
- non modifichi file vietati;
- non aggiunga dipendenze runtime;
- non indebolisca AGENTS.md;
- resti coerente con il perimetro dichiarato;
- mantenga MetaHarness, autoresearch-lite e Open Design support come strumenti esterni;
- produca un risultato classificabile come keep/discard.

## Comandi

```powershell
python tools/codex_harness/check_codex_scope.py --mode dev-tooling
python tools/codex_harness/check_runtime_dependencies.py
python tools/codex_harness/check_agents_guardrails.py
python tools/codex_harness/check_open_design_support.py
python tools/codex_harness/run_codex_quality_gate.py --mode dev-tooling
```

## Modalita'

### dev-tooling

Per task come MetaHarness, autoresearch-lite, Open Design support, documentazione Codex e script di validazione.

In questa modalita' sono vietate modifiche a:

- runtime applicativo;
- dipendenze;
- Docker/Railway;
- versione applicativa;
- storage/migrazioni;
- Lex AI;
- portali telematici.

### docs

Per task solo documentali.

### ui-support

Per task di design system, skill UI e prompt grafici sotto `tools/open-design-support/`.

### code

Per task codice applicativo.
Richiede review piu' forte e test pertinenti.
