"""Perché il collaudo respinge i fatti letti (V13), eseguito DENTRO il container scheduler-worker.

Sola lettura: interroga la tabella SQL ``letture_fatti`` dell'archivio delle letture (art. 3 D.M. 44/2011 e
art. 20 CAD: i fatti nascono solo da documenti e PEC con impronta). Non apre documenti, non rilegge e non scrive.
Stampa un JSON di soli conteggi: esiti del collaudo, categorie e campi, codici delle prove respinte, motori e
quota di respinti per fascicolo, senza identificativi, valori letti, contesti o dati del cliente.

Uso sul server:
    cd /opt/iusentra/repo
    docker compose --env-file /opt/iusentra/.env.hetzner -f deploy/hetzner/docker-compose.hetzner.yml \
        exec -T scheduler-worker python - < deploy/hetzner/analisi_fatti_respinti.py
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from typing import Any

MARCATORE = "ANALISI_FATTI_JSON:"


def _prove(grezzo: Any) -> list[dict[str, Any]]:
    if isinstance(grezzo, list):
        return [p for p in grezzo if isinstance(p, dict)]
    try:
        valore = json.loads(grezzo or "[]")
    except (TypeError, ValueError):
        return []
    return [p for p in valore if isinstance(p, dict)] if isinstance(valore, list) else []


def riepilogo_studio_corrente() -> dict[str, Any]:
    """I conteggi dell'archivio dei fatti dello studio già presente nella richiesta."""
    from web.services.archivio_letture_runtime import registro_corrente, tenant_corrente

    registro = registro_corrente(sola_lettura=True)
    with registro.connection() as conn:
        righe = conn.execute(
            'SELECT "fascicolo_id", "verifica", "categoria", "campo", "motore", "tipo", "prove_json" '
            'FROM "letture_fatti" WHERE "tenant_id" = ?',
            (tenant_corrente(),),
        ).fetchall()
    esiti: Counter[str] = Counter()
    respinti_per_campo: Counter[str] = Counter()
    totali_per_campo: Counter[str] = Counter()
    respinti_per_motore: Counter[str] = Counter()
    prove_respinte: Counter[str] = Counter()
    prove_attenzione: Counter[str] = Counter()
    unica_prova_respinta: Counter[str] = Counter()
    per_fascicolo: dict[str, Counter[str]] = {}
    for riga in righe:
        fascicolo, verifica, categoria, campo, motore, tipo, prove = (riga[i] for i in range(7))
        verifica = str(verifica or "")
        voce = f"{categoria}/{campo}"
        esiti[verifica] += 1
        totali_per_campo[voce] += 1
        per_fascicolo.setdefault(str(fascicolo), Counter())[verifica] += 1
        respinte = [str(p.get("codice") or "") for p in _prove(prove) if p.get("esito") == "respinta"]
        for p in _prove(prove):
            if p.get("esito") == "attenzione":
                prove_attenzione[str(p.get("codice") or "")] += 1
        if verifica == "respinta":
            respinti_per_campo[voce] += 1
            respinti_per_motore[f"{motore}/{tipo}"] += 1
            prove_respinte.update(respinte)
            if len(set(respinte)) == 1:
                unica_prova_respinta[respinte[0]] += 1
    quote = []
    for conteggi in per_fascicolo.values():
        totale = sum(conteggi.values())
        if totale >= 20:
            quote.append(round(100 * conteggi.get("respinta", 0) / totale))
    fasce = Counter(f"{(q // 10) * 10}-{(q // 10) * 10 + 9}%" for q in quote)
    return {
        "fatti": sum(esiti.values()),
        "fascicoli": len(per_fascicolo),
        "esiti": dict(esiti.most_common()),
        "respinti_per_campo": {k: {"respinti": v, "totali": totali_per_campo[k]} for k, v in respinti_per_campo.most_common(25)},
        "respinti_per_motore": dict(respinti_per_motore.most_common()),
        "prove_respinte": dict(prove_respinte.most_common()),
        "respinti_con_una_sola_prova": dict(unica_prova_respinta.most_common()),
        "prove_attenzione": dict(prove_attenzione.most_common()),
        "fascicoli_con_almeno_20_fatti_per_quota_respinti": dict(sorted(fasce.items())),
    }


def main() -> int:
    sys.path.insert(0, "/app")
    from pct.scheduler_worker import create_scheduler_app
    from pct.tenant import GestioneTenant
    from web.services.fascicoli_presidi_runtime import _active_tenants, _attach_tenant_context

    app = create_scheduler_app()
    esito: dict[str, Any] = {"studi": {}}
    studi = _active_tenants(app)
    if studi:
        manager = GestioneTenant(registry_path=app.config["TENANTS_REGISTRY"])
        for numero, studio in enumerate(studi, start=1):
            slug = str(getattr(studio, "slug", "") or "").lower()
            with app.test_request_context(f"/__analisi/fatti/{slug}"):
                _attach_tenant_context(manager, studio)
                # Gli studi si identificano con un numero: il riepilogo non porta nomi.
                esito["studi"][f"studio_{numero}"] = riepilogo_studio_corrente()
    else:
        with app.test_request_context("/__analisi/fatti"):
            esito["studi"]["studio_1"] = riepilogo_studio_corrente()
    # L'avvio dell'app scrive log anche sullo standard output: il risultato è l'unica riga con questo marcatore.
    print(MARCATORE + json.dumps(esito, ensure_ascii=False, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
