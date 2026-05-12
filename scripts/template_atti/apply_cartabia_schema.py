from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pct.template_cartabia_rules import STATUS_READY, STATUS_REVIEW, ensure_cartabia_metadata
from pct.template_atti_compiler_bindings import compiler_binding_map_by_title
from pct.template_atti_master_catalog import REQUIRED_TEMPLATE_FIELDS, SPLIT_CATALOG_FILES


DATA_DIR = ROOT / "pct" / "template_atti_catalogo_data"
MASTER = DATA_DIR / "catalogo_master.json"
REPORT_DIR = ROOT / "artifacts" / "template-atti"
TARGET_VERSION = "1.2.0"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _enrich_payload(payload: dict) -> dict:
    enriched = dict(payload)
    enriched["versione"] = TARGET_VERSION
    schema = list(dict.fromkeys(list(enriched.get("schema_obbligatorio") or []) + list(REQUIRED_TEMPLATE_FIELDS)))
    enriched["schema_obbligatorio"] = schema
    bindings = compiler_binding_map_by_title()
    templates = []
    for item in enriched.get("template") or []:
        current = ensure_cartabia_metadata(item)
        title = str(current.get("titolo") or "")
        binding = bindings.get(title) or {}
        current["link_compilatore_code"] = current.get("link_compilatore_code") or binding.get("compiler_code") or _fallback_compiler_code(current)
        templates.append(current)
    enriched["template"] = templates
    enriched["totale_template"] = len(templates)
    return enriched


def _fallback_compiler_code(item: dict) -> str:
    area = str(item.get("processo_area") or "").strip()
    return {
        "penale": "PEN_IST_001",
        "tributario": "TRIB_RIC_001",
        "amministrativo": "AMM_RIC_001",
        "studio_interno": "STR_COM_001",
        "famiglia_minori": "FAM_MEMO_001",
        "adr": "STR_COM_001",
        "monitorio": "CIV_RDI_001",
        "esecuzione": "CIV_IST_001",
        "cautelare": "CIV_RCAUT_001",
    }.get(area, "CIV_CIT_001")


def _sync_splits(master_payload: dict) -> dict[str, dict]:
    by_id = {item["id"]: item for item in master_payload["template"]}
    synced: dict[str, dict] = {}
    for key, path in SPLIT_CATALOG_FILES.items():
        current = _read(path)
        template_ids = [item["id"] for item in current.get("template") or []]
        current["versione"] = master_payload["versione"]
        current["schema_obbligatorio"] = list(master_payload.get("schema_obbligatorio") or [])
        current["template"] = [by_id[template_id] for template_id in template_ids]
        current["totale_template"] = len(current["template"])
        _write(path, current)
        synced[key] = current
    return synced


def _coverage(master_payload: dict, splits: dict[str, dict]) -> dict:
    templates = master_payload["template"]
    return {
        "versione": master_payload["versione"],
        "template_totali": len(templates),
        "template_con_cartabia_profile": sum(1 for item in templates if item.get("cartabia_profile")),
        "template_con_prefill_bindings": sum(1 for item in templates if item.get("prefill_bindings")),
        "template_con_timbro_automatico": len(templates),
        "template_cartabia_ready": sum(1 for item in templates if item.get("stato_conformita") == STATUS_READY),
        "template_cartabia_review_required": sum(1 for item in templates if item.get("stato_conformita") == STATUS_REVIEW),
        "split": {key: payload.get("totale_template") for key, payload in splits.items()},
    }


def _write_report(coverage: dict) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "cartabia-catalog-coverage.json").write_text(
        json.dumps(coverage, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Copertura catalogo Template Atti Cartabia",
        "",
        f"- Versione catalogo: {coverage['versione']}",
        f"- Template totali: {coverage['template_totali']}",
        f"- Template con cartabia_profile: {coverage['template_con_cartabia_profile']}",
        f"- Template con prefill_bindings: {coverage['template_con_prefill_bindings']}",
        f"- Template con timbro automatico: {coverage['template_con_timbro_automatico']}",
        f"- Template cartabia_ready: {coverage['template_cartabia_ready']}",
        f"- Template cartabia_review_required: {coverage['template_cartabia_review_required']}",
        "",
        "## Split",
    ]
    for key, value in sorted(coverage["split"].items()):
        lines.append(f"- {key}: {value}")
    (REPORT_DIR / "cartabia-catalog-coverage.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    master = _enrich_payload(_read(MASTER))
    _write(MASTER, master)
    splits = _sync_splits(master)
    coverage = _coverage(master, splits)
    _write_report(coverage)
    print(json.dumps(coverage, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
