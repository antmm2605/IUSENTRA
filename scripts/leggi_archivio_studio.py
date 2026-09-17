#!/usr/bin/env python3
"""Lettura incrementale governata di un fascicolo SQL o inventario dello studio.

Il chiamante esegue un processo per fascicolo, con timeout e ripresa sui soli
oggetti mancanti. Nessuna lettura viene attribuita all'avvocato.
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--fascicolo")
    parser.add_argument("--limite", type=int, default=20)
    args = parser.parse_args()
    from web.app import create_app
    from pct.tenant import GestioneTenant, StatoTenant
    from web.services.fascicoli_presidi_runtime import _attach_tenant_context
    from web.services.registro_letture_runtime import registro_corrente, tenant_corrente
    from web.helpers import get_fascicoli
    from web.services.archivio_letture_runtime import leggi_fascicolo
    app = create_app()
    manager = GestioneTenant(registry_path=app.config["TENANTS_REGISTRY"])
    studio = manager.get(args.tenant)
    if studio is None or studio.stato == StatoTenant.SOSPESO:
        raise RuntimeError("Studio inesistente o sospeso")
    with app.test_request_context("/__job/lettura-archivio"):
        _attach_tenant_context(manager, studio)
        registro, tenant = registro_corrente(), tenant_corrente()
        backend = str(registro.backend_kind).lower()
        if backend not in {"sqlite", "postgresql"}:
            raise RuntimeError("La lettura richiede il registro SQL dello studio")
        fascicoli = get_fascicoli()
        if not args.fascicolo:
            elenco = sorted(fascicoli.tutti(archiviati=True), key=lambda f: (str(getattr(f.stato, "value", f.stato)) == "ARCHIVIATO", str(f.id)))
            result = {"source_of_truth": backend, "tenant": tenant, "fascicoli": [str(f.id) for f in elenco]}
        else:
            fascicolo = fascicoli.get(args.fascicolo)
            if fascicolo is None:
                raise RuntimeError("Fascicolo non trovato nello studio richiesto")
            esito = leggi_fascicolo(fascicolo, limite=max(1, min(args.limite, 50)), registro=registro)
            stato = registro.stato_fascicolo(tenant, fascicolo.id, lettori=("motore_documenti", "motore_pec"))
            result = {"source_of_truth": backend, "tenant": tenant, "fascicolo": fascicolo.id,
                      "oggetti": stato.oggetti, "letti": sum(x.letti for x in stato.lettori),
                      "da_leggere": sum(x.da_leggere for x in stato.lettori), "errori": sum(x.errori for x in stato.lettori),
                      "documenti_letti": int(esito.get("documenti", {}).get("letti", 0)),
                      "pec_lette": int(esito.get("pec", {}).get("letti", 0)),
                      "completa": stato.tutto_letto}
        print("RISULTATO_SQL " + json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
