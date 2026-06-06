"""Audit copertura fonti ufficiali dei Template Atti.

Il controllo è intenzionalmente severo: le fonti di base comune non chiudono
la copertura. Ogni modello deve avere almeno una fonte professionale valida e
almeno una fonte collegata, tecnica, attuativa, deontologica o di autorità
competente, con URL ufficiale e data di verifica coerente con il registro.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pct.compilatore_atti import elenco_modelli
from pct.template_atti_legal_sources import (
    LAST_VERIFIED_AT,
    REGISTRY_VERSION,
    TEMPLATE_ATTI_LEGAL_SOURCES,
    template_atti_sources_for_model,
    template_atti_source_registry_summary,
)
from pct.template_atti_unified_catalog import iter_all_templates


VALID_COVERAGE_ROLES = {
    "specifica",
    "telematica",
    "secondaria_collegata",
    "autorita",
    "deontologia",
    "ordinamento_professionale",
}

CONNECTED_COVERAGE_ROLES = {
    "telematica",
    "secondaria_collegata",
    "autorita",
    "deontologia",
    "ordinamento_professionale",
}


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _catalog_area(row: dict[str, Any]) -> str:
    return " ".join(
        _clean(row.get(key))
        for key in (
            "titolo",
            "area",
            "materia",
            "macro_area",
            "canale_deposito",
            "processo_area",
            "cartabia_profile",
        )
        if _clean(row.get(key))
    )


def _compiler_area(row: dict[str, Any]) -> str:
    return " ".join(_clean(row.get(key)) for key in ("name", "area", "matter") if _clean(row.get(key)))


def _is_valid_coverage(source: dict[str, Any]) -> bool:
    return (
        _clean(source.get("coverage_role")) in VALID_COVERAGE_ROLES
        and not bool(source.get("deprecated"))
    )


def _is_connected_coverage(source: dict[str, Any]) -> bool:
    return (
        _clean(source.get("coverage_role")) in CONNECTED_COVERAGE_ROLES
        and not bool(source.get("deprecated"))
    )


def _source_issue(source: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if not _clean(source.get("official_url")).startswith("https://"):
        issues.append("url_ufficiale_mancante")
    if _clean(source.get("last_verified_at")) != LAST_VERIFIED_AT:
        issues.append("verifica_non_aggiornata")
    return issues


def _model_audit_row(*, source: str, code: str, title: str, area: str) -> dict[str, Any]:
    rows = template_atti_sources_for_model(model_code=code, model_name=title, area=area)
    issues: list[str] = []
    if not rows:
        issues.append("nessuna_fonte")
    if rows and not any(_is_valid_coverage(item) for item in rows):
        issues.append("solo_base_comune_o_transitoria")
    if rows and not any(_is_connected_coverage(item) for item in rows):
        issues.append("manca_fonte_secondaria_tecnica_deontologica_o_autorita")
    if rows and all(bool(item.get("deprecated")) for item in rows):
        issues.append("solo_fonti_transitorie")
    per_source_issues = {
        _clean(item.get("id")): _source_issue(item)
        for item in rows
        if _source_issue(item)
    }
    if per_source_issues:
        issues.append("fonte_non_verificabile")
    return {
        "source": source,
        "code": code,
        "title": title,
        "area": area,
        "ok": not issues,
        "issues": issues,
        "source_count": len(rows),
        "valid_coverage_count": sum(1 for item in rows if _is_valid_coverage(item)),
        "connected_coverage_count": sum(1 for item in rows if _is_connected_coverage(item)),
        "base_common_count": sum(1 for item in rows if _clean(item.get("coverage_role")) == "base_comune"),
        "deprecated_count": sum(1 for item in rows if bool(item.get("deprecated"))),
        "roles": sorted({_clean(item.get("coverage_role")) for item in rows if _clean(item.get("coverage_role"))}),
        "source_ids": [_clean(item.get("id")) for item in rows],
        "source_issues": per_source_issues,
        "sources": rows,
    }


def build_audit() -> dict[str, Any]:
    catalog_rows = [
        _model_audit_row(
            source="catalogo_unificato",
            code=_clean(row.get("codice")),
            title=_clean(row.get("titolo") or row.get("name")),
            area=_catalog_area(row),
        )
        for row in iter_all_templates(refresh=True)
    ]
    compiler_rows = [
        _model_audit_row(
            source="compilatore_atti",
            code=_clean(row.get("code")),
            title=_clean(row.get("name")),
            area=_compiler_area(row),
        )
        for row in elenco_modelli()
    ]
    source_registry_issues = {
        _clean(item.get("id")): _source_issue(item)
        for item in TEMPLATE_ATTI_LEGAL_SOURCES
        if _source_issue(item)
    }
    all_rows = catalog_rows + compiler_rows
    issues = [row for row in all_rows if not row["ok"]]
    return {
        "schema_version": "2026-06-06.template_atti_sources_audit.v1",
        "registry_version": REGISTRY_VERSION,
        "last_verified_at": LAST_VERIFIED_AT,
        "summary": {
            "catalog_models": len(catalog_rows),
            "compiler_models": len(compiler_rows),
            "total_model_rows": len(all_rows),
            "ok_model_rows": sum(1 for row in all_rows if row["ok"]),
            "issue_model_rows": len(issues),
            "registry_source_count": len(TEMPLATE_ATTI_LEGAL_SOURCES),
            "registry_source_issues": len(source_registry_issues),
            "registry": template_atti_source_registry_summary(),
        },
        "registry_source_issues": source_registry_issues,
        "issues": issues,
        "models": all_rows,
    }


def _write_markdown(audit: dict[str, Any], path: Path) -> None:
    summary = audit["summary"]
    def _md(value: Any) -> str:
        return _clean(value).replace("|", "\\|") or "-"

    def _csv(values: Any, limit: int = 16) -> str:
        items = [_clean(item) for item in (values or ()) if _clean(item)]
        if len(items) > limit:
            return ", ".join(items[:limit]) + f", +{len(items) - limit}"
        return ", ".join(items) or "-"

    lines = [
        "# Audit fonti ufficiali Template Atti",
        "",
        f"- Data verifica: {audit['last_verified_at']}",
        f"- Versione registro: {audit['registry_version']}",
        f"- Modelli catalogo unificato: {summary['catalog_models']}",
        f"- Modelli compilatore: {summary['compiler_models']}",
        f"- Righe modello totali: {summary['total_model_rows']}",
        f"- Righe modello OK: {summary['ok_model_rows']}",
        f"- Righe modello con problemi: {summary['issue_model_rows']}",
        f"- Fonti nel registro: {summary['registry_source_count']}",
        f"- Fonti registro con problemi: {summary['registry_source_issues']}",
        "",
        "## Regola di audit",
        "",
        "La fonte `base_comune` non chiude la copertura. Un modello è OK solo se",
        "ha almeno una fonte professionale valida e almeno una fonte collegata",
        "tra `telematica`, `secondaria_collegata`, `deontologia`,",
        "`ordinamento_professionale` o `autorita`, non transitoria, con URL ufficiale",
        "e data di verifica aggiornata. Questo impedisce di spacciare una fonte",
        "generale per presidio specifico del modello.",
        "",
        "## Fonti registro con problemi",
        "",
    ]
    registry_issues = audit.get("registry_source_issues") or {}
    if registry_issues:
        for source_id, issues in registry_issues.items():
            lines.append(f"- `{source_id}`: {', '.join(issues)}")
    else:
        lines.append("- Nessuna.")
    lines.extend(
        [
            "",
            "## Fonti censite e ricerche web riportate in Ricerca Legale",
            "",
            "| ID | Fonte | Ruolo | Tipo | Ambito | URL ufficiale | Modelli collegati | Termini |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for source in TEMPLATE_ATTI_LEGAL_SOURCES:
        url = _clean(source.get("official_url"))
        linked = f"[apri]({url})" if url.startswith("https://") else "-"
        lines.append(
            f"| `{_md(source.get('id'))}` | {_md(source.get('title') or source.get('source_title'))} | "
            f"{_md(source.get('coverage_role'))} | {_md(source.get('source_type'))} | "
            f"{_md(source.get('scope'))} | {linked} | "
            f"{_csv(source.get('applies_to_prefixes'))} | {_csv(source.get('match_terms'), limit=10)} |"
        )
    lines.extend(
        [
            "",
            "## Matrice completa modelli",
            "",
            "| Origine | Codice | Modello | Stato | Ruoli fonte | Fonti valide | Problemi |",
            "| --- | --- | --- | --- | --- | ---: | --- |",
        ]
    )
    for row in audit["models"]:
        status = "OK" if row["ok"] else "DA COMPLETARE"
        roles = ", ".join(row["roles"]) or "-"
        issues = ", ".join(row["issues"]) or "-"
        title = str(row["title"]).replace("|", "\\|")
        lines.append(
            f"| {row['source']} | `{row['code']}` | {title} | {status} | "
            f"{roles} | {row['valid_coverage_count']} / collegate {row['connected_coverage_count']} | {issues} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--json-out",
        default="artifacts/template-atti/template-atti-official-sources-audit-2026-06-06.json",
    )
    parser.add_argument(
        "--md-out",
        default="artifacts/template-atti/template-atti-official-sources-audit-2026-06-06.md",
    )
    parser.add_argument("--fail-on-issues", action="store_true")
    args = parser.parse_args()

    audit = build_audit()
    json_path = Path(args.json_out)
    md_path = Path(args.md_out)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_markdown(audit, md_path)
    print(
        "Audit Template Atti:",
        f"{audit['summary']['ok_model_rows']}/{audit['summary']['total_model_rows']} righe modello OK,",
        f"{audit['summary']['issue_model_rows']} problemi modello,",
        f"{audit['summary']['registry_source_issues']} problemi fonte.",
    )
    if args.fail_on_issues and (
        audit["summary"]["issue_model_rows"] or audit["summary"]["registry_source_issues"]
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
