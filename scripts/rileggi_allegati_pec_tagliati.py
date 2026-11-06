"""Rilegge gli allegati PEC il cui testo fu tagliato al vecchio limite di 20.000 caratteri (06/11/2026).

Il dispositivo, le spese liquidate e la data in calce delle sentenze lunghe stavano oltre il taglio. Si rileggono solo
quegli allegati; poi va eseguito il ripasso delle PEC (``scripts/backfill_pec_change_receipts.py``).

Uso: python -m scripts.rileggi_allegati_pec_tagliati --tenant <slug> [--prova] [--limite N]
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from pct.pec_pipeline import PecAuditRepository
from pct.tenant import GestioneTenant


def main() -> int:
    parser = argparse.ArgumentParser(description="Rilettura degli allegati PEC con testo tagliato a 20.000 caratteri.")
    parser.add_argument("--registry", default="", help="Registro degli studi; default da ambiente.")
    parser.add_argument("--tenant", required=True, help="Slug dello studio.")
    parser.add_argument("--limite", type=int, default=0, help="Numero massimo di PEC da rileggere.")
    parser.add_argument("--prova", action="store_true", help="Conta soltanto, senza rileggere.")
    args = parser.parse_args()
    registry = Path(args.registry or os.environ.get("PCT_TENANTS_REGISTRY") or "data/tenants.json")
    manager = GestioneTenant(str(registry))
    paths = manager.percorsi_dati(args.tenant, reconcile_aliases=False)
    pec_db = Path(paths["EMAIL_CASELLA_DB"]).parent / "pec_audit.sqlite"
    repo = PecAuditRepository(pec_db, tenant_id=args.tenant)
    esito = repo.rileggi_allegati_tagliati(limit=args.limite, prova=args.prova)
    print(json.dumps(esito, ensure_ascii=False, indent=2))
    return 0 if not esito["errori"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
