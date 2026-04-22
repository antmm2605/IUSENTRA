# Contributing

## Branch e igiene repository

- branch di sviluppo operativo: `Codex/legal-electronic-filing-kIxcV`
- branch gemello da riallineare sempre: `claude/legal-electronic-filing-kIxcV`
- non creare branch temporanei aggiuntivi
- mantenere un solo worktree attivo: `D:\\legale\\hacs`

## Regole di contribuzione

- testo UI sempre in italiano;
- date e ore visibili sempre in formato italiano;
- niente fallback nascosti o comportamento non spiegabile;
- ogni nuova feature deve chiudere dominio, storage, route, UI, permessi, test e documentazione.

## Packaging governato

Le dipendenze non si aggiornano piu' a mano in piu' punti:

- sorgente runtime: `requirements/base.txt`
- sorgente dev: `requirements/dev.txt`
- extra package: `requirements/pdf.txt`, `requirements/pades.txt`, `requirements/pkcs11.txt`
- file flat generati: `requirements.txt`, `requirements-dev.txt`

Per sincronizzare:

```bash
python tools/sync_packaging_files.py
```

Per verificare senza scrivere:

```bash
python tools/sync_packaging_files.py --check
```

## Test minimi prima del push

```bash
python tools/check_repo_governance.py
python -m pytest -q tests/test_packaging_consistency.py
docker compose build --no-cache
docker compose up -d --force-recreate
docker compose ps
```

## Release

- la versione sorgente vive in `pct/__init__.py`;
- `setup.py`, `Dockerfile` e `railway.toml` devono restare allineati;
- ogni release va pushata sia sul branch `Codex/...` sia su `claude/...`.
