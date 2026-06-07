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
    if not wanted:
        return True
    return slug == wanted or slug.lower() == wanted.lower()


def run_backfill(*, registry: Path, tenant: str = "", limit: int = 0, actor: str = "pec-maintenance") -> dict[str, Any]:
    manager = GestioneTenant(str(registry))
    studios = [studio for studio in manager.lista() if _matches(studio.slug, tenant)]
    payload: dict[str, Any] = {"ok": True, "registry": str(registry), "studios": {}, "total": {"checked": 0, "updated": 0, "skipped": 0}}
    for studio in studios:
        paths = manager.percorsi_dati(studio.slug, reconcile_aliases=False)
        email_db = Path(paths["EMAIL_CASELLA_DB"])
        pec_db = email_db.parent / "pec_audit.sqlite"
        if not pec_db.exists():
            result = {"ok": True, "checked": 0, "updated": 0, "skipped": 0, "message": "Archivio PEC audit non presente."}
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
            result = repo.enrich_deadlines_with_remote_hearing_links(actor=actor, limit=limit)
        payload["studios"][studio.slug] = result
        payload["ok"] = bool(payload["ok"] and result.get("ok", False))
        for key in ("checked", "updated", "skipped"):
            payload["total"][key] += int(result.get(key) or 0)
    if tenant and not studios:
        payload["ok"] = False
        payload["errors"] = [f"Studio non trovato: {tenant}"]
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Bonifica link udienze audiovisive da PEC già presidiate.")
    parser.add_argument("--registry", default="", help="Percorso registry tenant; default da ambiente o data/tenants.json.")
    parser.add_argument("--tenant", default="", help="Slug studio da bonificare; vuoto = tutti gli studi nel registry.")
    parser.add_argument("--limit", type=int, default=0, help="Numero massimo di scadenze PEC da controllare per studio.")
    parser.add_argument("--actor", default="pec-maintenance", help="Attore audit da registrare in agenda/PEC.")
    args = parser.parse_args()
    result = run_backfill(registry=_registry_path(args.registry), tenant=args.tenant, limit=args.limit, actor=args.actor)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
