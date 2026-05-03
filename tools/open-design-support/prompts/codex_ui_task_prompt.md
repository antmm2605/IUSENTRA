# Prompt Codex per task UI/UX IUSENTRA

Usa questo prompt quando devi modificare una UI di IUSENTRA.

## Istruzioni

Prima di modificare file, leggi:

1. `tools/open-design-support/IUSENTRA_DESIGN.md`
2. `tools/open-design-support/IUSENTRA_UI_RULES.md`
3. la skill pertinente in `tools/open-design-support/skills/`
4. `tools/autoresearch-lite/IUSENTRA_EXPERIMENT_TEMPLATE.md`

Poi dichiara:

- obiettivo UI;
- schermata interessata;
- file modificabili;
- file vietati;
- baseline;
- criterio keep/discard;
- test o smoke da eseguire.

Regole:
- testi visibili in italiano;
- date italiane;
- stati vuoti/loading/errore/conferma;
- responsive desktop/tablet/mobile;
- nessuna modifica backend non richiesta;
- nessuna dipendenza aggiunta;
- nessuna regressione navigazione;
- nessun effetto grafico incoerente.

Alla fine esegui i controlli pertinenti e classifica:
- `keep`
- `discard`
- `crash`
- `scope-violation`
- `needs-review`
