from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pct.guida_pratica import GuidaPraticaService  # noqa: E402
from pct.pratiche_collegate_catalog import codice_oggetto_pst_entry, list_codici_oggetto_pst  # noqa: E402

DEFAULT_REPORT = ROOT / "artifacts" / "guida-pratica" / "guida-pratica-web-enrichment-audit.json"
DEFAULT_CSV = ROOT / "artifacts" / "guida-pratica" / "guida-pratica-web-enrichment-audit.csv"


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _is_internal(code: str, guidance: dict[str, Any]) -> bool:
    return code.startswith("GUIDA_") or bool(guidance.get("guida_interna_non_depositabile"))


def _all_codes(service: GuidaPraticaService) -> list[str]:
    official = [str(row["codice"]) for row in list_codici_oggetto_pst()]
    kb_codes = sorted(str(code) for code in getattr(service, "_kb_index", {}) if str(code))
    out: list[str] = []
    for code in [*official, *kb_codes]:
        if code not in out:
            out.append(code)
    return out


def _audit_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    service = GuidaPraticaService()
    rows: list[dict[str, Any]] = []
    for code in _all_codes(service):
        try:
            guidance = service.get_guidance(code)
        except Exception as exc:  # pragma: no cover - report operativo.
            rows.append(
                {
                    "codice": code,
                    "denominazione": "",
                    "official_catalog": bool(codice_oggetto_pst_entry(code)),
                    "internal_alias": code.startswith("GUIDA_"),
                    "depositabile": False,
                    "fonti_count": 0,
                    "presidi_present": False,
                    "non_bloccante": False,
                    "deposit_rule_present": False,
                    "deposit_contaminated": False,
                    "status": "service_error",
                    "error": str(exc),
                }
            )
            continue
        sources = _as_list(guidance.get("fonti_verifica_web"))
        presidi = _as_dict(guidance.get("presidi_operativi_integrativi"))
        enrichment = _as_dict(guidance.get("arricchimento_iusentra"))
        deposito = _as_dict(guidance.get("codice_deposito"))
        official = bool(codice_oggetto_pst_entry(code))
        internal = _is_internal(code, guidance) or not official
        depositable = bool(deposito.get("depositabile"))
        deposit_contaminated = bool(internal and depositable) or bool(not official and not internal and depositable)
        missing = []
        if not sources:
            missing.append("fonti_verifica_web")
        if not presidi:
            missing.append("presidi_operativi_integrativi")
        if not enrichment.get("non_bloccante"):
            missing.append("arricchimento_non_bloccante")
        if "codice deposito resta sempre" not in json.dumps(presidi, ensure_ascii=False).casefold():
            missing.append("regola_deposito_separato")
        if deposit_contaminated:
            missing.append("contaminazione_codice_deposito")
        rows.append(
            {
                "codice": code,
                "denominazione": _clean(guidance.get("denominazione")),
                "official_catalog": official,
                "internal_alias": internal,
                "depositabile": depositable,
                "fonti_count": len(sources),
                "presidi_present": bool(presidi),
                "non_bloccante": bool(enrichment.get("non_bloccante")),
                "deposit_rule_present": "regola_deposito_separato" not in missing,
                "deposit_contaminated": deposit_contaminated,
                "status": "ok" if not missing else "missing:" + ",".join(missing),
                "error": "",
            }
        )
    summary = {
        "generated_at": _utc_now(),
        "records_checked": len(rows),
        "official_records_checked": sum(1 for row in rows if row["official_catalog"]),
        "internal_aliases_checked": sum(1 for row in rows if row["internal_alias"]),
        "records_with_web_sources": sum(1 for row in rows if row["fonti_count"]),
        "records_with_presidi": sum(1 for row in rows if row["presidi_present"]),
        "non_blocking_records": sum(1 for row in rows if row["non_bloccante"]),
        "deposit_contaminations": sum(1 for row in rows if row["deposit_contaminated"]),
        "failures": sum(1 for row in rows if row["status"] != "ok"),
    }
    return rows, summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit dell'arricchimento web e dei presidi su tutta la Guida Pratica.")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--fail-on-missing", action="store_true")
    args = parser.parse_args()

    rows, summary = _audit_rows()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.csv.parent.mkdir(parents=True, exist_ok=True)
    with args.csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()) if rows else ["codice", "status"])
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.fail_on_missing and summary["failures"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
