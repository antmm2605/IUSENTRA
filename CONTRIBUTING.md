# Contributing

## Obiettivo

Questo repository evolve come prodotto applicativo professionale. Ogni modifica deve privilegiare:

- prevedibilita';
- tracciabilita';
- sicurezza;
- coerenza tra dominio, storage, UI e documentazione.

## Regole di contribuzione

- testo UI sempre in italiano;
- date e ore visibili sempre in formato italiano;
- niente fallback nascosti o comportamento non spiegabile;
- ogni nuova feature deve chiudere dominio, storage, route, UI, permessi, test e documentazione;
- ogni bugfix deve includere almeno un controllo riproducibile o un test, quando sostenibile.

## Strategia branch

- usare branch descrittivi e orientati al cambiamento;
- evitare branch temporanei inutili;
- mantenere piccole PR coerenti per dominio;
- non mescolare refactor, fix e feature senza necessita' reale.

Esempi branch:

- `feat/lex-citations-hardening`
- `fix/pst-session-reuse`
- `chore/packaging-alignment`
- `docs/security-policy-refresh`

## Packaging governato

Le dipendenze non si aggiornano a mano in piu' punti.

Sorgenti principali:

- runtime: `requirements/base.txt`
- dev: `requirements/dev.txt`
- extra package: `requirements/pdf.txt`, `requirements/pades.txt`, `requirements/pkcs11.txt`

File derivati:

- `requirements.txt`
- `requirements-dev.txt`

Per sincronizzare:

```bash
python tools/sync_packaging_files.py
```

Per verificare senza scrivere:

```bash
python tools/sync_packaging_files.py --check
```

## Quality gate minimi prima del push

```bash
python tools/check_repo_governance.py
python -m pytest -q tests/test_packaging_consistency.py
python -m pytest -q
docker compose build --no-cache
docker compose up -d --force-recreate
docker compose ps
```

## Definition of done

Una modifica e' considerata chiusa solo se:

- il comportamento e' verificabile;
- i file di packaging restano coerenti;
- la documentazione minima e' aggiornata;
- la CI passa;
- non introduce segreti, debug residuo o config ambigue.

## Release

- la versione sorgente vive in `pct/__init__.py`;
- `setup.py`, `Dockerfile`, `railway.toml` e gli altri entrypoint di deploy devono restare allineati;
- ogni release deve avere changelog tecnico sintetico;
- prima del tag verificare bootstrap, storage persistente, login, healthcheck e smoke Flask.

## Cosa evitare

- percorsi locali hardcoded;
- branch policy dipendenti da una singola macchina;
- fix rapidi senza test minimo o scenario riproducibile;
- dipendenze aggiunte senza reale necessita';
- modifica manuale dei file generati se esiste gia' una sorgente governata.
