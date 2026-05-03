# Perimetro MetaHarness - IUSENTRA

## Principio

MetaHarness puo' aiutare a migliorare Codex, ma non deve diventare un agente libero sul codice prodotto.

Ogni proposta MetaHarness e' non attendibile finche':
- il diff non e' stato revisionato;
- i test pertinenti non passano;
- non indebolisce AGENTS.md;
- non modifica dipendenze runtime;
- non riduce CI, coverage o security workflow;
- non modifica storage o migrazioni senza piano esplicito;
- non modifica UI prodotto senza verifica grafica e funzionale.

## Moduli protetti

MetaHarness non deve modificare direttamente senza autorizzazione esplicita:

- `pct/`
- `web/`
- `lex/`
- `migrations/`
- `requirements/`
- `requirements.txt`
- `requirements-dev.txt`
- `pyproject.toml`
- `setup.py`
- `pct/__init__.py`
- `Dockerfile`
- `railway.toml`
- `.github/workflows/`

## Moduli su cui puo' proporre miglioramenti

- `AGENTS.md`
- `docs/`
- `tools/metaharness/`
- `tools/autoresearch-lite/`
- `tools/open-design-support/`
- `tools/codex_harness/`
- script di validazione dedicati;
- checklist operative;
- criteri di valutazione harness;
- documentazione per Codex;
- design system e skill UI/UX di supporto.

## Workflow core da proteggere

- cliente -> preventivo -> conferimento -> fascicolo -> attivita' -> parcella -> incasso
- fascicoli
- clienti
- soggetti
- agenda
- scadenziario
- deposito telematico
- SIGP / Giudice di Pace
- PST / PDP / PAT / PTT
- fatturazione
- pagamenti
- storage JSON / SQLite / PostgreSQL
- Lex AI
- multi-tenant
- assistenza remota
- sito studio
- portale cliente

## Regola keep/discard

Una proposta va classificata:

- `keep`: migliora il risultato, rispetta scope e test;
- `discard`: non migliora o introduce complessita' inutile;
- `crash`: non funziona o rompe validazioni;
- `scope-violation`: tocca file o aree vietate;
- `needs-review`: potenzialmente utile ma richiede revisione umana.
