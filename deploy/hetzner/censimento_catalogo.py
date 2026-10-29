"""Censimento delle etichette certe del catalogo documentale (eseguito DENTRO il container scheduler-worker).

Sola lettura: legge catalogo SQL, metadati del portale e audit delle decisioni; non apre documenti e non scrive.
Stampa un JSON di soli conteggi e voci del catalogo, senza nomi di file, testi o dati del cliente.

Uso sul server:
    cd /opt/iusentra/repo
    docker compose --env-file /opt/iusentra/.env.hetzner -f deploy/hetzner/docker-compose.hetzner.yml \
        exec -T scheduler-worker python - < deploy/hetzner/censimento_catalogo.py
"""

from __future__ import annotations

import json
import sys


def main() -> int:
    sys.path.insert(0, "/app")
    from pct.scheduler_worker import create_scheduler_app
    from web.services.verita_catalogo_runtime import censimento_studi

    app = create_scheduler_app()
    esito = censimento_studi(app)
    print(json.dumps(esito, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
