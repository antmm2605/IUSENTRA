from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from pct.pec_pipeline import _is_remote_hearing_url
from pct.scadenziario import GestioneScadenziario
from pct.tenant import GestioneTenant

TECHNICAL_ACTORS = {"codex-test", "pytest", "pec-api", "pec-worker", "pec-demo", "pec-maintenance"}


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


def _url_fingerprint(url: str) -> dict[str, str]:
    parsed = urlsplit(str(url or ""))
    return {
        "host": parsed.netloc.lower(),
        "path_prefix": parsed.path[:80],
        "sha256": hashlib.sha256(str(url or "").encode("utf-8", errors="ignore")).hexdigest(),
    }


def _deadline_sample(scadenza: Any) -> dict[str, Any]:
    url = str(getattr(scadenza, "remote_hearing_url", "") or "")
    return {
        "id": str(getattr(scadenza, "id", "") or ""),
        "data": str(getattr(scadenza, "data_scadenza", "") or ""),
        "tipo": str(getattr(getattr(scadenza, "tipo", ""), "value", getattr(scadenza, "tipo", "")) or ""),
        "titolo": str(getattr(scadenza, "titolo", "") or "")[:180],
        "link": _url_fingerprint(url) if url else {},
        "pdf_da_acquisire": bool(getattr(scadenza, "remote_hearing_pdf_required", False)),
    }


def audit_tenant(scadenziario_db: Path) -> dict[str, Any]:
    manager = GestioneScadenziario(str(scadenziario_db))
    totals: dict[str, Any] = {
        "pec_deadlines": 0,
        "remote_hearing_valid_links": 0,
        "remote_hearing_invalid_links": 0,
        "remote_hearing_pdf_pending": 0,
        "generic_notice_deadlines": 0,
        "artificial_future_notice_deadlines": 0,
        "technical_actor_deadlines": 0,
        "hearing_deadlines": 0,
        "samples_valid_links": [],
        "samples_invalid_links": [],
        "samples_generic_notice": [],
        "samples_pdf_pending": [],
    }
    for scadenza in manager.tutte(solo_aperte=False):
        note = str(getattr(scadenza, "note", "") or "")
        title = str(getattr(scadenza, "titolo", "") or "")
        if "PEC_AUDIT:" not in note:
            continue
        totals["pec_deadlines"] += 1
        tipo = str(getattr(getattr(scadenza, "tipo", ""), "value", getattr(scadenza, "tipo", "")) or "")
        if tipo.upper() == "UDIENZA" or title.startswith("Udienza da PEC"):
            totals["hearing_deadlines"] += 1
        actor = str(getattr(scadenza, "id_utente_responsabile", "") or "").strip().lower()
        if actor in TECHNICAL_ACTORS or actor.startswith("codex"):
            totals["technical_actor_deadlines"] += 1
        if title.startswith("Valuta termini da notifica PEC"):
            totals["generic_notice_deadlines"] += 1
            if len(totals["samples_generic_notice"]) < 5:
                totals["samples_generic_notice"].append(_deadline_sample(scadenza))
        data_scadenza = str(getattr(scadenza, "data_scadenza", "") or "")
        if title.startswith("Valuta termini da notifica PEC") and data_scadenza >= "2030-01-01":
            totals["artificial_future_notice_deadlines"] += 1
        if bool(getattr(scadenza, "remote_hearing_pdf_required", False)):
            totals["remote_hearing_pdf_pending"] += 1
            if len(totals["samples_pdf_pending"]) < 5:
                totals["samples_pdf_pending"].append(_deadline_sample(scadenza))
        url = str(getattr(scadenza, "remote_hearing_url", "") or "")
        if url:
            if _is_remote_hearing_url(url, ""):
                totals["remote_hearing_valid_links"] += 1
                if len(totals["samples_valid_links"]) < 5:
                    totals["samples_valid_links"].append(_deadline_sample(scadenza))
            else:
                totals["remote_hearing_invalid_links"] += 1
                if len(totals["samples_invalid_links"]) < 10:
                    totals["samples_invalid_links"].append(_deadline_sample(scadenza))
    return totals


def run_audit(*, registry: Path, tenant: str = "") -> dict[str, Any]:
    manager = GestioneTenant(str(registry))
    studios = [studio for studio in manager.lista() if _matches(studio.slug, tenant)]
    payload: dict[str, Any] = {"ok": True, "registry": str(registry), "studios": {}}
    for studio in studios:
        paths = manager.percorsi_dati(studio.slug, reconcile_aliases=False)
        payload["studios"][studio.slug] = audit_tenant(Path(paths["SCADENZIARIO_DB"]))
    if tenant and not studios:
        payload["ok"] = False
        payload["errors"] = [f"Studio non trovato: {tenant}"]
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit read-only delle scadenze PEC con udienze da remoto e falsi positivi.")
    parser.add_argument("--registry", default="", help="Percorso registry tenant; default da ambiente o data/tenants.json.")
    parser.add_argument("--tenant", default="", help="Slug studio da controllare; vuoto = tutti gli studi nel registry.")
    args = parser.parse_args()
    result = run_audit(registry=_registry_path(args.registry), tenant=args.tenant)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
