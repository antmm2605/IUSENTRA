"""Pacchetto per addestrare il modello di catalogazione sul PC dell'avvocato (eseguito DENTRO scheduler-worker).

Autorizzazione dell'avvocato del 30/10/2026: testi dei documenti pseudonimizzati, più esempi inventati. Scrive
nella cartella dello studio sul server `intelligence/addestramento_catalogo/pacchetto/` (file leggibili solo da
root) e, fuori dal pacchetto, la corrispondenza codice → documento, che non va copiata. Non modifica il catalogo.
Stampa solo conteggi e il percorso del pacchetto.

Uso sul server:
    cd /opt/iusentra/repo
    docker compose --env-file /opt/iusentra/.env.hetzner -f deploy/hetzner/docker-compose.hetzner.yml \
        exec -T scheduler-worker python - < deploy/hetzner/esportazione_addestramento.py
"""

from __future__ import annotations

import json
import sys

MARCATORE = "ESPORTAZIONE_JSON:"


def main() -> int:
    sys.path.insert(0, "/app")
    from pct.scheduler_worker import create_scheduler_app
    from web.services.classificatore_catalogo_runtime import esportazione_studi

    app = create_scheduler_app()
    esito = esportazione_studi(app)
    # L'avvio dell'app scrive log anche sullo standard output: il risultato è l'unica riga con questo marcatore.
    print(MARCATORE + json.dumps(esito, ensure_ascii=False, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
