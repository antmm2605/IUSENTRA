"""Riporta in agenda le PEC di cancelleria già ricevute che hanno cambiato udienza o termine.

Per ogni PEC degli ultimi giorni indicati: impegno «PEC ricevuta: …» al giorno e all'ora di
consegna (ora italiana) e udienze superate dello stesso fascicolo segnate come rinviate.
Idempotente: si può rieseguire; gli impegni completati dall'avvocato non vengono riaperti.

Uso sul server (dalla cartella dell'applicazione):  python -m scripts.backfill_pec_change_receipts --days 180 [--tenant slug]
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from pct.pec_pipeline import PecAuditRepository
from pct.tenant import GestioneTenant


def _registry_path(value: str = "") -> Path:
    raw = (
        value
        or os.environ.get("TENANTS_REGISTRY")
        or os.environ.get("IUSENTRA_TENANTS_REGISTRY")
        or os.environ.get("PCT_TENANTS_REGISTRY")
        or "data/tenants.json"
    )
    return Path(raw)


def _matches(slug: str, wanted: str) -> bool:
    return not wanted or slug == wanted or slug.lower() == wanted.lower()


def run_backfill(*, registry: Path, tenant: str = "", days: int = 180, actor: str = "pec-maintenance") -> dict[str, Any]:
    manager = GestioneTenant(str(registry))
    studios = [studio for studio in manager.lista() if _matches(studio.slug, tenant)]
    payload: dict[str, Any] = {"ok": True, "registry": str(registry), "studios": {}, "total": {"checked": 0, "recorded": 0, "rescheduled": 0}}
    for studio in studios:
        paths = manager.percorsi_dati(studio.slug, reconcile_aliases=False)
        pec_db = Path(paths["EMAIL_CASELLA_DB"]).parent / "pec_audit.sqlite"
        if not pec_db.exists():
            result: dict[str, Any] = {"ok": True, "checked": 0, "recorded": 0, "rescheduled": 0, "message": "Archivio PEC audit non presente."}
        else:
            repo = PecAuditRepository(
                pec_db,
                tenant_id=studio.slug,
                clienti_db_path=paths["CLIENTI_DB"],
                fascicoli_db_path=paths["FASCICOLI_DB"],
                fascicoli_docs_path=paths["FASCICOLI_DOCS"],
                scadenziario_db_path=paths["SCADENZIARIO_DB"],
                agenda_db_path=paths["AGENDA_DB"],
            )
            result = repo.record_pec_schedule_change_receipts(days=days, actor=actor)
        payload["studios"][studio.slug] = result
        payload["ok"] = bool(payload["ok"] and result.get("ok", False))
        for key in ("checked", "recorded", "rescheduled"):
            payload["total"][key] += int(result.get(key) or 0)
    if tenant and not studios:
        payload["ok"] = False
        payload["errors"] = [f"Studio non trovato: {tenant}"]
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Ricezione in agenda delle PEC di cancelleria che cambiano udienza o termine.")
    parser.add_argument("--registry", default="", help="Percorso registry tenant; default da ambiente o data/tenants.json.")
    parser.add_argument("--tenant", default="", help="Slug studio; vuoto = tutti gli studi nel registry.")
    parser.add_argument("--days", type=int, default=180, help="PEC ricevute negli ultimi N giorni (default 180).")
    parser.add_argument("--actor", default="pec-maintenance", help="Attore audit da registrare.")
    args = parser.parse_args()
    result = run_backfill(registry=_registry_path(args.registry), tenant=args.tenant, days=args.days, actor=args.actor)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
