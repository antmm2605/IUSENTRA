"""Addestramento e misura del classificatore piccolo del catalogo (eseguito DENTRO il container scheduler-worker).

Legge catalogo SQL, decisioni dell'avvocato e testi già estratti; non apre documenti e non modifica il catalogo.
Scrive soltanto, nella cartella dello studio sul server, l'elenco dei disaccordi con le regole
(`intelligence/classificatore_disaccordi.json`). Stampa un JSON di soli conteggi e voci pubblicabili.

Uso sul server:
    cd /opt/iusentra/repo
    docker compose --env-file /opt/iusentra/.env.hetzner -f deploy/hetzner/docker-compose.hetzner.yml \
        exec -T scheduler-worker python - < deploy/hetzner/classificatore_catalogo.py
"""

from __future__ import annotations

import json
import sys

MARCATORE = "CLASSIFICATORE_JSON:"


def main() -> int:
    sys.path.insert(0, "/app")
    from pct.scheduler_worker import create_scheduler_app
    from web.services.classificatore_catalogo_runtime import classificatore_studi

    app = create_scheduler_app()
    esito = classificatore_studi(app)
    # L'avvio dell'app scrive log anche sullo standard output: il risultato è l'unica riga con questo marcatore.
    print(MARCATORE + json.dumps(esito, ensure_ascii=False, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
