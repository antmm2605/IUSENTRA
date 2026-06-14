# CodeQL e falso-verde gate 2.253.21 - 2026-06-14

## Stato

GitHub ha segnalato sullo SHA `d242ad5cdeee9c2a69b6213a46c8078375d98e48` il check `Code scanning results / CodeQL` in fallimento con 9 nuove annotazioni, incluse 2 high severity.

## Annotazioni trattate

- `web/services/server_maintenance_surface.py`: path controllato da dati tenant nella risoluzione delle cartelle sotto `data/tenants`.
- `web/blueprints/api_v1_react.py`: possibili traceback, eccezioni o percorsi server nei payload JSON delle route React Fascicolo/Regia e import scadenze PDF.
- `.github/required-checks.json`: `CodeQL` era richiesto solo su `pull_request`, quindi il gate di push poteva risultare verde mentre code scanning dello stesso SHA era rosso.

## Correzione prevista

- Validare la chiave storage tenant prima di confrontarla con le cartelle reali.
- Evitare join diretti tra path base e chiavi tenant non sanificate.
- Sanificare i payload pubblici React prima di `jsonify`.
- Richiedere `CodeQL` anche su `push`.
- Aggiungere test mirati su traversal, payload pubblici e gate CodeQL.

## Blocco operativo

Il lavoro resta aperto finché il nuovo SHA non ha `CodeQL`/code scanning verde. Solo dopo si può procedere con deploy Hetzner e prova dry-run server del deposito senza invio PEC reale.

## Verifiche locali eseguite

| Comando | Esito | Nota |
| --- | --- | --- |
| `python -m py_compile web\services\server_maintenance_surface.py web\blueprints\api_v1_react.py tools\check_github_required_gates.py tests\test_codeql_public_surface_regressions.py` | OK | Compilazione dei file toccati senza errori. |
| `python -m pytest -q tests\test_codeql_public_surface_regressions.py tests\test_ci_cd_gates_phase11.py --tb=short` | OK | 11/11 passati: tenant traversal bloccato, payload pubblici sanificati e CodeQL bloccante su push. |
| `python -m flake8 web\services\server_maintenance_surface.py web\blueprints\api_v1_react.py tools\check_github_required_gates.py tests\test_codeql_public_surface_regressions.py` | OK | Lint mirato sui file modificati. |
| `python tools\sync_packaging_files.py --check`; `python scripts\validate_openapi.py docs\openapi.yaml`; `python -m pytest -q tests\test_packaging_consistency.py tests\test_release_readiness.py tests\test_utf8_integrity.py --tb=short`; `git diff --check` | OK | Packaging, OpenAPI, readiness, UTF-8 e whitespace verdi sulla versione `2.253.21`. |
