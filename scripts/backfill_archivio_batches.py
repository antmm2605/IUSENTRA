#!/usr/bin/env python3
"""Backfill incrementale dell'archivio letture, sequenziale e riavviabile."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import sys
from typing import Any, Callable, Iterator
from urllib.request import Request, urlopen

BATCH_SIZE = 10
DEFAULT_CHECKPOINT = Path(os.getenv("PCT_DATA_ROOT", "./data")) / "intelligence" / "backfill_archivio_batches.json"
DEFAULT_READINESS = os.getenv("IUSENTRA_READINESS_URL", "https://app.iusentra.it/api/pronto")


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)
    path.chmod(0o600)


def _load_checkpoint(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("Checkpoint non valido.")
    return payload


def check_readiness(url: str, *, timeout: float = 10.0) -> None:
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "IUSENTRA-archive-backfill/1"})
    with urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
        if response.status != 200 or payload.get("ok") is not True:
            raise RuntimeError(f"Readiness degradata: HTTP {response.status}, ok={payload.get('ok')!r}")


def run_batches(
    cases: list[str],
    *,
    checkpoint_path: Path,
    process_case: Callable[[str], dict[str, Any]],
    readiness: Callable[[], None],
    batch_size: int = BATCH_SIZE,
) -> dict[str, Any]:
    """Lavora casi sequenziali, salvando ogni esito e riprendendo dal checkpoint."""
    checkpoint = _load_checkpoint(checkpoint_path)
    completed = set(str(value) for value in checkpoint.get("completed", []) if value)
    results = dict(checkpoint.get("results") or {})
    pending = [case for case in cases if case not in completed]
    state: dict[str, Any] = {
        "version": 1,
        "source_of_truth": "sqlite/postgresql tenant-aware",
        "mode": "incremental",
        "force": False,
        "batch_size": int(batch_size),
        "total": len(cases),
        "completed": sorted(completed),
        "results": results,
        "status": "running",
        "updated_at": _now(),
    }
    _write_json_atomic(checkpoint_path, state)
    try:
        for start in range(0, len(pending), max(1, int(batch_size))):
            readiness()
            batch = pending[start : start + max(1, int(batch_size))]
            state["current_batch"] = {"number": start // max(1, int(batch_size)) + 1, "cases": batch}
            _write_json_atomic(checkpoint_path, state)
            for case in batch:
                result = process_case(case)
                results[case] = result
                completed.add(case)
                state["completed"] = sorted(completed)
                state["results"] = results
                state["last_case"] = case
                state["updated_at"] = _now()
                _write_json_atomic(checkpoint_path, state)
                readiness()
        state["status"] = "complete"
        state.pop("current_batch", None)
        state["updated_at"] = _now()
        _write_json_atomic(checkpoint_path, state)
        return state
    except Exception as exc:
        state["status"] = "stopped"
        state["error"] = f"{type(exc).__name__}: {exc}"[:500]
        state["updated_at"] = _now()
        _write_json_atomic(checkpoint_path, state)
        raise


@contextmanager
def _tenant_context(app: Any, manager: Any, studio: Any, slug: str) -> Iterator[None]:
    from flask import g

    with app.test_request_context(f"/__backfill-archivio/{slug}"):
        if studio is not None:
            from web.services.fascicoli_presidi_runtime import _attach_tenant_context

            _attach_tenant_context(manager, studio)
        else:
            g.multi_tenant_enabled = False
            g.tenant_context_missing = False
            g.tenant_context_slug = ""
        yield


def _targets(app: Any, selected_tenant: str) -> tuple[Any, dict[str, Any]]:
    studios: dict[str, Any] = {}
    manager = None
    if app.config.get("MULTI_TENANT"):
        from pct.tenant import GestioneTenant, StatoTenant

        manager = GestioneTenant(registry_path=app.config["TENANTS_REGISTRY"])
        for studio in manager.lista():
            slug = str(studio.slug or "").strip().lower()
            if studio.stato == StatoTenant.SOSPESO or (selected_tenant and slug != selected_tenant):
                continue
            studios[slug] = studio
    else:
        if selected_tenant and selected_tenant not in {"default", "single-studio"}:
            raise RuntimeError(f"Tenant non disponibile in modalità singolo studio: {selected_tenant}")
        studios["default"] = None
    if not studios:
        raise RuntimeError("Nessuno studio attivo selezionato.")
    return manager, studios


def run_operational(app: Any, *, checkpoint_path: Path, readiness_url: str, selected_tenant: str = "") -> dict[str, Any]:
    from web.helpers import get_fascicoli
    from web.blueprints.api_v1_react import _fascicolo_singolo_loader
    from web.services.document_intelligence_runtime import fascicoli_db_path
    from web.services.storage_runtime import get_request_storage_runtime

    manager, studios = _targets(app, selected_tenant.strip().lower())
    cases: list[str] = []
    for slug, studio in studios.items():
        with _tenant_context(app, manager, studio, slug):
            profile = get_request_storage_runtime(fascicoli_db_path())
            if str(profile.effective_mode).strip().lower() not in {"sqlite", "postgresql"}:
                raise RuntimeError(f"Fonte SQL obbligatoria per {slug}: modalità {profile.effective_mode!r}.")
            fascicoli = sorted(get_fascicoli().tutti(archiviati=True), key=lambda item: str(getattr(item, "id", "")))
            cases.extend(f"{slug}:{getattr(fascicolo, 'id', '')}" for fascicolo in fascicoli if getattr(fascicolo, "id", ""))

    def process(case: str) -> dict[str, Any]:
        from web.services.archivio_letture_runtime import leggi_fascicolo

        slug, fascicolo_id = case.split(":", 1)
        with _tenant_context(app, manager, studios[slug], slug):
            fascicolo = _fascicolo_singolo_loader()().get(fascicolo_id)
            if fascicolo is None:
                raise RuntimeError(f"Fascicolo non trovato: {case}")
            totals = {"giri": 0, "documenti": 0, "pec": 0, "fatti": 0, "verificati": 0}
            while True:
                report = leggi_fascicolo(fascicolo, forza=False, limite=200)
                totals["giri"] += 1
                documenti, pec = dict(report.get("documenti") or {}), dict(report.get("pec") or {})
                totals["documenti"] += int(documenti.get("letti") or 0)
                totals["pec"] += int(pec.get("letti") or 0)
                totals["fatti"] += int(documenti.get("fatti") or 0) + int(pec.get("fatti") or 0)
                totals["verificati"] += int(documenti.get("verificati") or 0) + int(pec.get("verificati") or 0)
                consegne, catalogo = dict(report.get("consegne") or {}), dict(report.get("catalogo") or {})
                rag = dict(catalogo.get("rag") or {})
                if consegne.get("errore") or catalogo.get("error") or catalogo.get("status") == "error" or rag.get("error") or rag.get("status") == "error":
                    raise RuntimeError(f"Pipeline incompleta per {case}")
                catalogo_in_attesa = int(catalogo.get("waiting_for_text") or 0)
                rag_in_attesa = int(rag.get("waiting_for_text") or 0)
                if catalogo_in_attesa > 0 or rag_in_attesa > 0:
                    raise RuntimeError(
                        f"Testo SQL incompleto per {case}: "
                        f"catalogo={catalogo_in_attesa}, rag={rag_in_attesa}"
                    )
                restano = int(report.get("restano") or 0)
                if restano <= 0:
                    return {"ok": True, "tenant": slug, "fascicolo_id": fascicolo_id, **totals}
                progresso = int(documenti.get("letti") or 0) + int(documenti.get("senza_testo") or 0) + int(documenti.get("assenti") or 0) + int(pec.get("letti") or 0) + int(pec.get("assenti") or 0)
                if progresso <= 0:
                    raise RuntimeError(f"Nessun progresso per {case}; restano={restano}")

    return run_batches(
        cases,
        checkpoint_path=checkpoint_path,
        process_case=process,
        readiness=lambda: check_readiness(readiness_url),
        batch_size=BATCH_SIZE,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--readiness-url", default=DEFAULT_READINESS)
    parser.add_argument("--tenant", default="", help="Limita a uno studio; vuoto = tutti gli studi attivi.")
    args = parser.parse_args(argv)
    try:
        from pct.scheduler_worker import create_scheduler_app

        result = run_operational(
            create_scheduler_app(),
            checkpoint_path=args.checkpoint,
            readiness_url=args.readiness_url,
            selected_tenant=args.tenant,
        )
        print(json.dumps({"ok": True, "status": result["status"], "completed": len(result["completed"]), "total": result["total"], "checkpoint": str(args.checkpoint)}, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}", "checkpoint": str(args.checkpoint)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
