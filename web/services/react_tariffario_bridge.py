"""Bridge read-only per la superficie React del tariffario."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from pct.tariffario import ComplessitaStimata, Grado, Materia
from pct.tariffario_catalogo import (
    grade_catalog_by_materia,
    phase_catalog_by_materia,
    rule_catalog_by_materia,
    tariffario_complessita_rows,
)


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _text(value: Any) -> str:
    return str(value or "").strip()


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
    if options:
        return options
    return [_option(grado.value, grado.value) for grado in Grado]


def _complexity_options() -> list[dict[str, Any]]:
    rows = tariffario_complessita_rows()
    if not rows:
        return [_option(item.value, item.value.capitalize()) for item in ComplessitaStimata]
    return [_option(row.get("value", ""), _text(row.get("label")) or _text(row.get("value")), _text(row.get("description"))) for row in rows]


def _rule_options(rule_catalog: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    options = [_option("", "Regola automatica")]
    for rows in rule_catalog.values():
        for row in rows[:18]:
            label = _text(row.get("label")) or _text(row.get("table_label")) or _text(row.get("rule_code"))
            value = _text(row.get("rule_code"))
            if value:
                options.append(_option(value, label or value, _text(row.get("matter"))))
    return options[:120]


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


def build_react_tariffario_payload(
    *,
    get_normative_tables: Callable[[], Any],
    query: dict[str, Any] | None = None,
) -> dict[str, Any]:
    del query
    warnings: list[dict[str, str]] = [
        _warning("scritture_legacy", "Il submit resta sulla route Flask esistente."),
        _warning("motore_backend", "Tariffario canonico, risultati e stampe restano nel backend."),
    ]
    profili = _table_rows(get_normative_tables, "tariffario_profili", warnings, "profili")
    regole = _table_rows(get_normative_tables, "tariffario_regole", warnings, "regole")
    riferimenti = _table_rows(get_normative_tables, "tariffario_riferimenti", warnings, "riferimenti")
    audit = _table_rows(get_normative_tables, "tariffario_audit", warnings, "audit")
    phase_catalog = phase_catalog_by_materia()
    grade_catalog = grade_catalog_by_materia()
    rule_catalog = rule_catalog_by_materia()

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
        "metrics": [
            _metric("profili", "Profili", len(profili), "Tabelle normative", "primary"),
            _metric("regole", "Regole", len(regole), "Catalogo backend", "info"),
            _metric("riferimenti", "Riferimenti", len(riferimenti), "Fonti collegate", "neutral"),
            _metric("audit", "Audit", len(audit), "Controlli registrati", "warning" if audit else "neutral"),
        ],
        "sections": [
            _section("aree", "Aree tariffarie", "distribution", area_items, "Nessuna area tariffaria disponibile."),
            _section(
                "presidi",
                "Presidi conservati",
                "legacy-routes",
                [
                    _item("motore", "Motore backend", "legacy", "Nessuna formula viene spostata in React", "warning"),
                    _item("wizard", "Wizard preventivi", "legacy", "Flusso preventivi avanzato ancora sui template", "warning"),
                    _item("stampe", "Stampe e documenti", "legacy", "Produzione gestita dalle route storiche", "warning"),
                ],
                "Nessun presidio rilevato.",
            ),
        ],
        "records": records,
        "actions": [
            _action("compensi", "Compensi forensi", "/compensi-forensi", "primary"),
            _action("wizard", "Wizard preventivi", "/preventivi/wizard?_legacy=1", "neutral"),
            _action("legacy", "Vista Flask", "/tariffario?_legacy=1", "warning"),
        ],
        "forms": [_tariffario_form(grade_catalog=grade_catalog, rule_catalog=rule_catalog)],
        "warnings": warnings,
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
        "metrics": [],
        "sections": [],
        "records": [],
        "actions": [_action("legacy", "Vista Flask", "/tariffario?_legacy=1", "warning")],
        "forms": [],
        "warnings": [_warning("tariffario_errore_controllato", message)],
    }
