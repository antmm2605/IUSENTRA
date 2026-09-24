"""Verifica non distruttiva della persistenza e dei blocchi del ciclo deposito."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pct.fascicoli import GestioneFascicoli
from pct.storage import StudioDB
from web.services.deposito_pec_runtime import (
    deposito_workflow_state,
    mark_deposito_workflow_stage,
    preserve_deposito_workflow,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant-root", required=True)
    parser.add_argument("--fascicolo", required=True)
    args = parser.parse_args()

    root = Path(args.tenant_root).resolve()
    manager = GestioneFascicoli(
        str(root / "fascicoli" / "fascicoli.json"),
        documents_dir=str(root / "fascicoli" / "documenti"),
        archive_dir=str(root / "fascicoli" / "archivio"),
        studio_db=StudioDB.get(str(root / "studio.db")),
        carica_tutto=False,
    )
    fascicolo = manager.get(args.fascicolo)
    if fascicolo is None:
        raise SystemExit(f"Fascicolo {args.fascicolo} non trovato")
    profile = dict(fascicolo.profilo_deposito or {})
    preparation = dict(profile.get("preparazione_busta") or {})
    persisted = deposito_workflow_state(preparation)
    if not all(persisted[stage]["ok"] for stage in ("proof", "simulation", "send")):
        raise SystemExit("Gli esiti positivi non risultano tutti persistiti")

    duplicate_blocked = False
    try:
        mark_deposito_workflow_stage(profile, "send", id_deposito="DUPLICATE")
    except ValueError as exc:
        duplicate_blocked = "secondo invio" in str(exc)
    if not duplicate_blocked:
        raise SystemExit("Il secondo invio non risulta bloccato")

    reset_preparation = preserve_deposito_workflow(preparation, preparation, reset=True)
    reset_state = deposito_workflow_state(reset_preparation)
    new_cycle_reset = not any(reset_state[stage]["ok"] for stage in ("proof", "simulation", "send"))
    if not new_cycle_reset:
        raise SystemExit("Il nuovo ciclo non riparte da zero")

    changed_preparation = dict(preparation)
    changed_preparation["corpo_pec"] = f"{preparation.get('corpo_pec', '')}\nmodifica"
    changed_preparation = preserve_deposito_workflow(changed_preparation, preparation)
    changed_state = deposito_workflow_state(changed_preparation)
    changed_input_reset = not any(
        changed_state[stage]["ok"] for stage in ("proof", "simulation", "send")
    )
    if not changed_input_reset:
        raise SystemExit("La modifica della preparazione non azzera il ciclo")

    print(
        json.dumps(
            {
                "ok": True,
                "source_of_truth": "sqlite",
                "fascicolo": args.fascicolo,
                "persisted_after_reload": True,
                "duplicate_send_blocked": duplicate_blocked,
                "new_cycle_reset": new_cycle_reset,
                "changed_input_reset": changed_input_reset,
                "fingerprint": persisted["fingerprint"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
