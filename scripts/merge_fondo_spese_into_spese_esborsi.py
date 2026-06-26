"""Migra la voce economica legacy fondo_spese nella voce unica Spese/esborsi."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.backfill_sentenza_lex_economics import (
    TenantBackfillTarget,
    _build_repositories,
    _load_tenants,
    _now_rome,
    _text,
)


def _as_number(value: Any) -> float | None:
    if value is None:
        return None
    raw = _text(value).replace("EUR", "").replace("eur", "").replace("€", "").replace(" ", "")
    if not raw:
        return None
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    try:
        return round(float(raw), 2)
    except (TypeError, ValueError):
        return None


def _is_blank(value: Any) -> bool:
    return value in (None, "", [], {})


def _merge_payment(spese: dict[str, Any], fondo: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    merged = dict(spese)
    changed = False
    if not merged:
        merged = dict(fondo)
        changed = True
    for key in (
        "status",
        "stato",
        "pagato",
        "previsto",
        "importo",
        "amount",
        "data_pagamento",
        "dataPagamento",
        "date",
        "metodo",
        "method",
        "note",
        "proforma_id",
        "proformaId",
        "documento_fonte",
        "documentSource",
        "origine",
        "origin",
        "updated_at",
        "updatedAt",
        "updated_by",
        "updatedBy",
    ):
        if _is_blank(merged.get(key)) and not _is_blank(fondo.get(key)):
            merged[key] = fondo.get(key)
            changed = True
    spese_amount = _as_number(spese.get("importo") if "importo" in spese else spese.get("amount"))
    fondo_amount = _as_number(fondo.get("importo") if "importo" in fondo else fondo.get("amount"))
    if spese_amount is None and fondo_amount is not None:
        merged["importo"] = fondo_amount
        changed = True
    merged["kind"] = "spese_esborsi"
    merged["label"] = "Spese/esborsi"
    merged["natura"] = "spese_esborsi"
    history = []
    for raw in (spese.get("history") or spese.get("storico") or [], fondo.get("history") or fondo.get("storico") or []):
        if isinstance(raw, list):
            history.extend(raw)
    if history:
        merged["history"] = history[-25:]
    return merged, changed


def merge_tenant(tenant: TenantBackfillTarget, *, apply: bool) -> dict[str, Any]:
    fascicoli, _fatturazione = _build_repositories(tenant)
    rows = list(fascicoli.tutti())
    report: dict[str, Any] = {
        "tenant": tenant.storage_key,
        "root": str(tenant.root),
        "source_of_truth": "sqlite/postgresql runtime repositories",
        "fascicoli_seen": len(rows),
        "fascicoli_changed": 0,
        "legacy_entries_removed": 0,
        "duplicates_avoided": 0,
        "items": [],
    }
    for fascicolo in rows:
        payments = dict(getattr(fascicolo, "pagamenti", {}) or {})
        fondo = payments.get("fondo_spese")
        if not isinstance(fondo, dict):
            continue
        spese = payments.get("spese_esborsi") if isinstance(payments.get("spese_esborsi"), dict) else {}
        merged, changed = _merge_payment(spese, fondo)
        payments["spese_esborsi"] = merged
        del payments["fondo_spese"]
        report["fascicoli_changed"] += 1
        report["legacy_entries_removed"] += 1
        if spese:
            report["duplicates_avoided"] += 1
        item = {
            "id": _text(getattr(fascicolo, "id", "")),
            "titolo": _text(getattr(fascicolo, "titolo", "")),
            "spese_importo": merged.get("importo"),
            "fondo_importo_precedente": fondo.get("importo"),
            "duplicate_avoided": bool(spese),
            "changed": True,
        }
        report["items"].append(item)
        if apply:
            fascicoli.aggiorna(item["id"], pagamenti=payments)
    return report


def run_merge(*, data_root: Path, registry: Path, tenants: set[str] | None = None, apply: bool = False) -> dict[str, Any]:
    selected = tenants or set()
    report: dict[str, Any] = {
        "ok": True,
        "mode": "apply" if apply else "dry_run",
        "started_at": _now_rome(),
        "source_of_truth": "sqlite/postgresql runtime repositories",
        "data_root": str(data_root),
        "registry": str(registry),
        "totals": {
            "tenants": 0,
            "fascicoli_seen": 0,
            "fascicoli_changed": 0,
            "legacy_entries_removed": 0,
            "duplicates_avoided": 0,
        },
        "tenants": [],
    }
    for tenant in _load_tenants(registry, data_root, selected):
        tenant_report = merge_tenant(tenant, apply=apply)
        report["tenants"].append(tenant_report)
        report["totals"]["tenants"] += 1
        for key in ("fascicoli_seen", "fascicoli_changed", "legacy_entries_removed", "duplicates_avoided"):
            report["totals"][key] += int(tenant_report.get(key) or 0)
    report["finished_at"] = _now_rome()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", default="data")
    parser.add_argument("--registry", default="data/tenants.json")
    parser.add_argument("--tenant", action="append", default=[])
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--report", default="")
    args = parser.parse_args()
    report = run_merge(
        data_root=Path(args.data_root),
        registry=Path(args.registry),
        tenants=set(args.tenant or []),
        apply=bool(args.apply),
    )
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report:
        path = Path(args.report)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload, encoding="utf-8")
    print(payload)
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
