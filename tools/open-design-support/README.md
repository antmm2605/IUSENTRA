# Open Design support per IUSENTRA

## Scopo

Questa cartella contiene risorse per aiutare Codex a produrre UI/UX piu' coerenti e professionali per IUSENTRA.

E' ispirata al metodo Open Design:
- design system in Markdown;
- skill UI/UX;
- prompt operativi;
- prototipo prima dell'integrazione;
- self-check grafico;
- artifact/review prima di modificare la UI prodotto.

Open Design non e' installato dentro IUSENTRA.
Open Design non e' una dipendenza runtime.
Questa cartella contiene solo supporto per Codex.

## Uso consigliato

Per task grafici o UI/UX, Codex deve leggere prima:

1. `tools/open-design-support/IUSENTRA_DESIGN.md`
2. `tools/open-design-support/IUSENTRA_UI_RULES.md`
3. la skill piu' adatta in `tools/open-design-support/skills/`
4. il prompt operativo in `tools/open-design-support/prompts/`

Poi deve:
- definire obiettivo;
- proporre una direzione grafica;
- indicare file modificabili;
- rispettare UI italiana;
- considerare desktop, tablet e mobile;
- gestire stati vuoti, loading, errore e conferma;
- eseguire test o smoke pertinenti;
- classificare risultato con autoresearch-lite.

## Regola fondamentale

Open Design support serve a migliorare la qualita' grafica di Codex.
Non autorizza modifiche libere a `web/`, `web/templates/`, `web/static/`, `web/blueprints/` o `/app-v2`.

Ogni modifica UI deve avere:
- scope;
- file ammessi;
- criterio visuale;
- verifica;
- review.
