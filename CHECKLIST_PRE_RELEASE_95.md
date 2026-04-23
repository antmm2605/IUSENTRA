# Checklist pre-release 95/100

## Repo
- [ ] `python tools/check_repo_governance.py`
- [ ] `python tools/sync_packaging_files.py --check`
- [ ] `python tools/check_python_baseline.py`

## Local Signer
- [ ] `python tools/check_local_signer_boundaries.py`
- [ ] test cache AI verdi

## Lex
- [ ] `python tools/check_lex_quality_gates.py`
- [ ] orchestrator presente
- [ ] fallback esplicito
- [ ] timeout espliciti
- [ ] retrieval separato
- [ ] telemetry presente o pianificata

## Performance
- [ ] `python tools/check_performance_budget.py`
- [ ] benchmark smoke presente
- [ ] nessuna regressione evidente

## Test
- [ ] `python -m pytest -q`
- [ ] coverage ancora sopra soglia CI

## Release
- [ ] changelog sintetico
- [ ] smoke deploy locale o container
- [ ] verifica login / healthcheck / route critiche
