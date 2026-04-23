# Applica questo secondo blocco dopo il primo zip

## Contenuto

Questo pacchetto aggiunge:

- base condivisa per CLI coverage
- rimozione della password hardcoded di default `postgres`
- gestione errori CLI coerente
- validazione input `limit` e `draft-id`
- CI più severa e allineata ai constraints
- `types-requests` nei dev requirements

## File da sostituire o aggiungere

- `tools/coverage_cli_base.py` (nuovo)
- `tools/legal_coverage_cli_common.py`
- `tools/auto_fill_generator.py`
- `tools/coverage_auditor.py`
- `tools/draft_reviewer.py`
- `tools/gap_builder.py`
- `requirements-dev.txt`
- `.github/workflows/ci.yml`

## Nota importante

Dato che `requirements-dev.txt` è generato, devi replicare gli stessi vincoli anche nella sorgente `requirements/dev.txt` o nel manifest da cui lo rigeneri.

## Comandi finali

```bash
python tools/sync_packaging_files.py --check
python tools/check_repo_governance.py
python tools/check_python_baseline.py
python -m ruff check .
python -m mypy .
python -m pytest -q
```
