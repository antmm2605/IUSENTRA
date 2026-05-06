"""Bridge pagina per la console React del tariffario."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from pct.motore_preventivo import catalogo_wizard
from pct.tariffario import ComplessitaStimata, Grado, Materia
from pct.tariffario_catalogo import (
    grade_catalog_by_materia,
    phase_catalog_by_materia,
    rule_catalog_by_materia,
    tariffario_complessita_rows,
)
from web.services.mediazione_dm150_runtime import MEDIAZIONE_ODM_TABLE_ID
from web.services.react_tariffario_compute import build_react_tariffario_run_payload


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _text(value: Any, fallback: str = "") -> str:
    rendered = str(value or "").strip()
    return rendered or fallback


def _metric(mid: str, label: str, value: Any, note: str, tone: str = "neutral") -> dict[str, Any]:
    return {"id": mid, "label": label, "value": value, "note": note, "tone": tone}


def _item(iid: str, label: str, value: Any, note: str = "", tone: str = "neutral") -> dict[str, Any]:
    return {"id": iid, "label": label, "value": value, "note": note, "tone": tone}


def _section(sid: str, title: str, kind: str, items: list[dict[str, Any]], empty: str) -> dict[str, Any]:
    return {"id": sid, "title": title, "kind": kind, "items": items, "emptyMessage": empty}


def _action(aid: str, label: str, href: str, tone: str = "neutral") -> dict[str, Any]:
    return {"id": aid, "label": label, "href": href, "method": "GET", "tone": tone}


def _warning(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _option(value: Any, label: str, description: str = "") -> dict[str, Any]:
    return {"value": _text(value), "label": label, "description": description, "enabled": True}


def _field(
    name: str,
    label: str,
    field_type: str,
    *,
    required: bool = False,
    value: str = "",
    options: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"name": name, "label": label, "type": field_type, "required": required, "value": value}
    if options is not None:
        payload["options"] = options
    return payload


def _table_rows(
    get_normative_tables: Callable[[], Any],
    method: str,
    warnings: list[dict[str, str]],
    label: str,
) -> list[dict[str, Any]]:
    try:
        manager = get_normative_tables()
        reader = getattr(manager, method, None)
        if callable(reader):
            return [row for row in reader() if isinstance(row, dict)]
    except Exception as exc:
        warnings.append(_warning(f"{label}_non_disponibile", f"Sorgente {label} non disponibile: {type(exc).__name__}."))
    return []


def _all_tables(get_normative_tables: Callable[[], Any], warnings: list[dict[str, str]]) -> list[dict[str, Any]]:
    try:
        rows = get_normative_tables().catalogo_tabelle()
        return [
            row for row in rows
            if isinstance(row, dict)
            and (_text(row.get("id")).startswith("tariffario_forense_") or _text(row.get("id")) == MEDIAZIONE_ODM_TABLE_ID)
        ]
    except Exception as exc:
        warnings.append(_warning("tabelle_non_disponibili", f"Catalogo tabelle non disponibile: {type(exc).__name__}."))
    return []


def _materia_options() -> list[dict[str, Any]]:
    return [_option(materia.value, materia.value) for materia in Materia]


def _grado_options(grade_catalog: dict[str, list[str]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    options: list[dict[str, Any]] = []
    for values in grade_catalog.values():
        for value in values:
            label = _text(value)
            if label and label not in seen:
                seen.add(label)
                options.append(_option(label, label))
    return options or [_option(grado.value, grado.value) for grado in Grado]


def _complexity_options() -> list[dict[str, Any]]:
    rows = tariffario_complessita_rows()
    if not rows:
        return [_option(item.value, item.value.capitalize()) for item in ComplessitaStimata]
    return [_option(row.get("value", ""), _text(row.get("label")) or _text(row.get("value")), _text(row.get("description"))) for row in rows]


def _rule_options(rule_catalog: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    options = [_option("", "Regola standard del tariffario")]
    seen: set[str] = set()
    for rows in rule_catalog.values():
        for row in rows:
            value = _text(row.get("rule_code"))
            if not value or value in seen:
                continue
            seen.add(value)
            label = _text(row.get("label")) or _text(row.get("table_label")) or value
            options.append(_option(value, label, _text(row.get("matter"))))
    return options


def _tariffario_form(
    *,
    grade_catalog: dict[str, list[str]],
    rule_catalog: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    return {
        "id": "tariffario_calcolo_legacy",
        "title": "Parametri per submit Flask",
        "description": "Il form invia alla route esistente; il risultato viene prodotto dal backend.",
        "action": "/tariffario",
        "method": "POST",
        "submitLabel": "Invia al motore backend",
        "enabled": True,
        "fields": [
            _field("materia", "Materia", "select", required=True, options=_materia_options()),
            _field("regola_tariffaria", "Regola tariffaria", "select", options=_rule_options(rule_catalog)),
            _field("grado", "Grado / sede", "select", required=True, options=_grado_options(grade_catalog)),
            _field("valore", "Valore pratica", "text", value="0"),
            _field("complessita", "Complessita stimata", "select", options=_complexity_options()),
            _field("spese_generali", "Spese generali", "checkbox", value="1"),
            _field("perc_spese_generali", "Percentuale spese generali", "text", value="15"),
            _field("bonus_telematico", "Bonus telematico", "checkbox", value=""),
        ],
    }


def _wizard_catalog() -> tuple[dict[str, list[dict[str, Any]]], dict[str, dict[str, Any]]]:
    catalog = catalogo_wizard()
    by_id = {
        _text(item.get("id")): item
        for items in catalog.values()
        for item in items
        if isinstance(item, dict) and _text(item.get("id"))
    }
    return catalog, by_id


def _enrich_audit(rows: list[dict[str, Any]], practices: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            **row,
            "practice_label": practices.get(_text(row.get("suggested_practice_id")), {}).get("label")
            or _text(row.get("suggested_practice_id")),
        }
        for row in rows
    ]


def _audit_summary(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "totale": len(rows),
        "verificata_snapshot": sum(1 for row in rows if row.get("compliance_status") == "verificata_snapshot"),
        "verificata_seed": sum(1 for row in rows if row.get("compliance_status") == "verificata_seed"),
        "ricostruttiva": sum(1 for row in rows if row.get("compliance_status") == "ricostruttiva"),
        "da_verificare": sum(1 for row in rows if row.get("compliance_status") == "da_verificare"),
    }


def _profile_record(row: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        "id": _text(row.get("profile_code")) or f"profilo_{index}",
        "title": _text(row.get("table_label")) or _text(row.get("materia_label")) or "Profilo tariffario",
        "subtitle": _text(row.get("grado_input_value")) or _text(row.get("fase_label")),
        "meta": _text(row.get("materia_label")) or "Tariffario backend",
        "stateLabel": "Profilo",
        "stateTone": "neutral",
        "href": "/tariffario",
    }


def _rule_record(row: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        "id": _text(row.get("rule_code")) or f"regola_{index}",
        "title": _text(row.get("label")) or _text(row.get("table_label")) or "Regola tariffaria",
        "subtitle": _text(row.get("matter")) or _text(row.get("jurisdiction")) or _text(row.get("description")),
        "meta": _text(row.get("materia_label")) or "Regola backend",
        "stateLabel": "Regola",
        "stateTone": "info",
        "href": "/tariffario",
    }


def _support_payload(
    *,
    audit: list[dict[str, Any]],
    tables: list[dict[str, Any]],
    options: list[dict[str, Any]],
    references: list[dict[str, Any]],
    channels: list[dict[str, Any]],
    summary: dict[str, int],
) -> dict[str, Any]:
    warnings = [row for row in audit if row.get("compliance_status") != "verificata_snapshot"]
    return {
        "auditSummary": summary,
        "auditRows": warnings,
        "auditCards": [
            {
                "value": summary.get("verificata_snapshot", 0),
                "label": "Regole allineate allo snapshot ufficiale DM 147/2022.",
            },
            {
                "value": summary.get("verificata_seed", 0),
                "label": "Regole coperte da integrazioni seed controllate.",
            },
        ],
        "tables": tables,
        "options": options,
        "references": references,
        "channels": channels,
    }


def _stats_payload(
    *,
    profiles: list[dict[str, Any]],
    rules: list[dict[str, Any]],
    tables: list[dict[str, Any]],
    options: list[dict[str, Any]],
    audit_summary: dict[str, int],
) -> dict[str, Any]:
    open_count = audit_summary.get("ricostruttiva", 0) + audit_summary.get("da_verificare", 0)
    aligned = audit_summary.get("verificata_snapshot", 0) + audit_summary.get("verificata_seed", 0)
    return {
        "profiles": len(profiles),
        "rules": len(rules),
        "tables": len(tables),
        "options": len(options),
        "auditOpen": open_count,
        "auditAligned": aligned,
        "auditTotal": audit_summary.get("totale", len(rules)),
    }


def _catalog_payload(
    *,
    grade_catalog: dict[str, list[str]],
    phase_catalog: dict[str, list[dict[str, Any]]],
    rule_catalog: dict[str, list[dict[str, Any]]],
    practices: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return {
        "materiaOptions": _materia_options(),
        "gradeCatalog": grade_catalog,
        "phaseCatalog": phase_catalog,
        "ruleCatalog": rule_catalog,
        "complexityOptions": _complexity_options(),
        "ruleOptions": _rule_options(rule_catalog),
        "gradeOptions": _grado_options(grade_catalog),
        "practices": practices,
    }


def build_react_tariffario_payload(
    *,
    get_normative_tables: Callable[[], Any],
    query: dict[str, Any] | None = None,
) -> dict[str, Any]:
    warnings: list[dict[str, str]] = [
        _warning("scritture_legacy", "Creazione preventivo, parcella e flussi fiscali restano sulle route Flask esistenti."),
        _warning("motore_backend", "Il motore tariffario canonico resta nel backend Python."),
    ]
    profili = _table_rows(get_normative_tables, "tariffario_profili", warnings, "profili")
    regole = _table_rows(get_normative_tables, "tariffario_regole", warnings, "regole")
    riferimenti = _table_rows(get_normative_tables, "tariffario_riferimenti", warnings, "riferimenti")
    audit = _table_rows(get_normative_tables, "tariffario_audit", warnings, "audit")
    opzioni = _table_rows(get_normative_tables, "tariffario_opzioni", warnings, "opzioni")
    canali = _table_rows(get_normative_tables, "tariffario_fatturazione", warnings, "canali")
    tables = _all_tables(get_normative_tables, warnings)
    phase_catalog = phase_catalog_by_materia()
    grade_catalog = grade_catalog_by_materia()
    rule_catalog = rule_catalog_by_materia()
    _, practices = _wizard_catalog()
    audit_enriched = _enrich_audit(audit, practices)
    summary = _audit_summary(audit_enriched)
    stats = _stats_payload(profiles=profili, rules=regole, tables=tables, options=opzioni, audit_summary=summary)
    initial = build_react_tariffario_run_payload(dict(query or {}), get_normative_tables=get_normative_tables)
    area_items = [
        _item(
            _text(materia).lower().replace(" ", "_") or "materia",
            _text(materia) or "Materia",
            len(phase_catalog.get(materia, [])),
            f"{len(grade_catalog.get(materia, []))} gradi disponibili",
            "primary",
        )
        for materia in sorted(set(phase_catalog) | set(grade_catalog))
    ]
    records = [_profile_record(row, index) for index, row in enumerate(profili[:40], start=1)]
    records.extend(_rule_record(row, index) for index, row in enumerate(regole[:40], start=1))
    return {
        "source": "repository_reali",
        "generated_at": _iso_now(),
        "contracts": {
            "mock_fallback": False,
            "writes": "legacy_routes",
            "route_owner": "react_shell",
            "legacy_contract": "artifacts/react-migration/legacy-contracts/tariffario.json",
        },
        "stats": stats,
        "catalog": _catalog_payload(
            grade_catalog=grade_catalog,
            phase_catalog=phase_catalog,
            rule_catalog=rule_catalog,
            practices=practices,
        ),
        "state": initial.get("state", {}),
        "profile": initial.get("profile", {}),
        "dynamic": initial.get("dynamic", {}),
        "result": initial.get("result"),
        "support": _support_payload(
            audit=audit_enriched,
            tables=tables,
            options=opzioni,
            references=riferimenti,
            channels=canali,
            summary=summary,
        ),
        "metrics": [
            _metric("profili", "Profili tariffari", stats["profiles"], "Materia, grado, fasi e profilo operativo.", "primary"),
            _metric("opzioni", "Opzioni di calcolo", stats["options"], "Spese generali, bonus, accessori e logiche fiscali.", "info"),
            _metric("tabelle", "Tabelle sincronizzate", stats["tables"], "Catalogo normativo condiviso con il motore preventivi.", "neutral"),
            _metric("audit", "Audit da aprire", stats["auditOpen"], "Voci ricostruttive o da verificare disponibili nel pannello tecnico.", "warning" if stats["auditOpen"] else "success"),
        ],
        "sections": [
            _section("aree", "Aree tariffarie", "distribution", area_items, "Nessuna area tariffaria disponibile."),
            _section(
                "presidi",
                "Presidi conservati",
                "legacy-routes",
                [
                    _item("motore", "Motore backend", "attivo", "Nessuna formula viene spostata in React", "success"),
                    _item("preventivo", "Preventivo guidato", "collegato", "CTA precompilata su route esistente", "primary"),
                    _item("parcella", "Parcella precompilata", "collegata", "Voci operative passate alla fatturazione", "primary"),
                ],
                "Nessun presidio rilevato.",
            ),
        ],
        "records": records,
        "actions": [
            _action("compensi", "Compensi forensi", "/compensi-forensi", "primary"),
            _action("wizard", "Wizard preventivi", "/preventivi/wizard", "neutral"),
            _action("legacy", "Vista Flask", "/tariffario?_legacy=1", "warning"),
        ],
        "forms": [_tariffario_form(grade_catalog=grade_catalog, rule_catalog=rule_catalog)],
        "warnings": warnings + list(initial.get("warnings") or []),
    }


def build_react_tariffario_error_payload(message: str = "Tariffario non disponibile.") -> dict[str, Any]:
    return {
        "source": "errore_controllato",
        "generated_at": _iso_now(),
        "contracts": {
            "mock_fallback": False,
            "writes": "legacy_routes",
            "route_owner": "react_shell",
            "legacy_contract": "artifacts/react-migration/legacy-contracts/tariffario.json",
        },
        "stats": {},
        "catalog": {},
        "state": {},
        "profile": {},
        "dynamic": {},
        "result": None,
        "support": {},
        "metrics": [],
        "sections": [],
        "records": [],
        "actions": [_action("legacy", "Vista Flask", "/tariffario?_legacy=1", "warning")],
        "forms": [],
        "warnings": [_warning("tariffario_errore_controllato", message)],
    }
