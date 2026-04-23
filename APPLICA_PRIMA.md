# IUSENTRA hardening pack — applicazione rapida

## Cosa contiene

Questo zip contiene file pronti da copiare nella tua repo per:

- allineare la baseline Python a 3.12;
- rafforzare governance e documentazione;
- introdurre constraints per le dipendenze;
- aggiornare `requirements-dev.txt`;
- migliorare la CI reale che hai caricato.

## Come applicarlo

1. estrai lo zip nella root della repo;
2. sovrascrivi i file esistenti quando richiesto;
3. esegui questi comandi:

```bash
python tools/sync_packaging_files.py --check
python tools/check_repo_governance.py
python tools/check_python_baseline.py
python -m ruff check .
python -m mypy packaging_manifest.py docker/entrypoint.py tools/sync_packaging_files.py
python -m pytest -q
```

## Commit consigliato

```bash
git checkout -b chore/repo-hardening
git add .
git commit -m "chore: harden repo governance, python baseline and ci"
```

## Nota importante

`requirements-dev.txt` è un file flat generato. Dopo l'applicazione conviene riallineare anche la sorgente vera (`requirements/dev.txt`) così il file non verrà rigenerato in modo diverso in futuro.
