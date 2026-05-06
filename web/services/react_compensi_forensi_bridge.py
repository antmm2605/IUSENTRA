"""Bridge read-only per la superficie React dei compensi forensi."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from pct.motore_preventivo import catalogo_wizard


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


def _preventivi_totals(get_preventivi: Callable[[], Any] | None, warnings: list[dict[str, str]]) -> tuple[int, int]:
    if not callable(get_preventivi):
        return 0, 0
    try:
        manager = get_preventivi()
        preventivi = getattr(manager, "tutti_preventivi", lambda: [])()
        conferimenti = getattr(manager, "tutti_conferimenti", lambda: [])()
        return len(list(preventivi)), len(list(conferimenti))
    except Exception as exc:
        warnings.append(_warning("mandato_non_disponibile", f"Archivio mandato non disponibile: {type(exc).__name__}."))
        return 0, 0


def _wizard_sections(warnings: list[dict[str, str]]) -> list[dict[str, Any]]:
    try:
        catalog = catalogo_wizard()
    except Exception as exc:
        warnings.append(_warning("catalogo_wizard_non_disponibile", f"Catalogo wizard non disponibile: {type(exc).__name__}."))
        return []
    sections: list[dict[str, Any]] = []
    for area, rows in catalog.items():
        items = rows if isinstance(rows, list) else []
        sections.append(
            _item(
                _text(area).lower().replace(" ", "_") or "area",
                _text(area) or "Area operativa",
                len(items),
                "Percorsi esistenti nel catalogo backend",
                "primary" if items else "neutral",
            )
        )
    return sections


def _safe_record(row: dict[str, Any], index: int) -> dict[str, Any]:
    title = _text(row.get("table_label")) or _text(row.get("materia_label")) or _text(row.get("label"))
    subtitle = _text(row.get("grado_input_value")) or _text(row.get("article")) or _text(row.get("description"))
    return {
        "id": _text(row.get("profile_code")) or _text(row.get("rule_code")) or _text(row.get("reference_code")) or f"record_{index}",
        "title": title or "Voce tariffaria",
        "subtitle": subtitle,
        "meta": _text(row.get("materia_label")) or _text(row.get("domains")) or "Dato backend",
        "stateLabel": "Backend",
        "stateTone": "neutral",
        "href": "/tariffario",
    }


def build_react_compensi_forensi_payload(
    *,
    get_normative_tables: Callable[[], Any],
    get_preventivi: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    warnings: list[dict[str, str]] = [
        _warning("scritture_legacy", "I submit restano sulle route Flask esistenti."),
        _warning("motore_backend", "Il motore forense, i log economici e la produzione di stampe restano nel backend."),
    ]
    profili = _table_rows(get_normative_tables, "tariffario_profili", warnings, "profili")
    regole = _table_rows(get_normative_tables, "tariffario_regole", warnings, "regole")
    audit = _table_rows(get_normative_tables, "tariffario_audit", warnings, "audit")
    preventivi_count, conferimenti_count = _preventivi_totals(get_preventivi, warnings)
    wizard_items = _wizard_sections(warnings)

    records = [_safe_record(row, index) for index, row in enumerate((profili[:16] + regole[:16]), start=1)]

    return {
        "source": "repository_reali",
        "generated_at": _iso_now(),
        "contracts": {
            "mock_fallback": False,
            "writes": "legacy_routes",
            "route_owner": "react_shell",
            "legacy_contract": "artifacts/react-migration/legacy-contracts/compensi-forensi.json",
        },
        "metrics": [
            _metric("profili", "Profili tariffari", len(profili), "Letti dalle tabelle normative", "primary"),
            _metric("regole", "Regole disponibili", len(regole), "Catalogo backend", "info"),
            _metric("preventivi", "Preventivi collegati", preventivi_count, "Archivio mandato", "neutral"),
            _metric("conferimenti", "Conferimenti", conferimenti_count, "Archivio incarichi", "neutral"),
        ],
        "sections": [
            _section("percorsi", "Aree di calcolo disponibili", "workflow", wizard_items, "Nessun percorso disponibile."),
            _section(
                "presidi",
                "Presidi conservati",
                "legacy-routes",
                [
                    _item("tariffario", "Tariffario canonico", "legacy", "Consultazione e submit sono governati da Flask", "warning"),
                    _item("wizard", "Wizard preventivi", "legacy", "Generazione e audit restano nel workflow storico", "warning"),
                    _item("audit", "Audit tariffario", len(audit), "Righe audit lette dal backend", "info" if audit else "neutral"),
                ],
                "Nessun presidio rilevato.",
            ),
        ],
        "records": records,
        "actions": [
            _action("tariffario", "Apri tariffario", "/tariffario", "primary"),
            _action("wizard", "Wizard preventivi", "/preventivi/wizard?_legacy=1", "neutral"),
            _action("preventivi", "Archivio preventivi", "/preventivi", "neutral"),
            _action("legacy", "Vista Flask", "/compensi-forensi?_legacy=1", "warning"),
        ],
        "forms": [],
        "warnings": warnings,
    }


def build_react_compensi_forensi_error_payload(message: str = "Compensi forensi non disponibili.") -> dict[str, Any]:
    return {
        "source": "errore_controllato",
        "generated_at": _iso_now(),
        "contracts": {
            "mock_fallback": False,
            "writes": "legacy_routes",
            "route_owner": "react_shell",
            "legacy_contract": "artifacts/react-migration/legacy-contracts/compensi-forensi.json",
        },
        "metrics": [],
        "sections": [],
        "records": [],
        "actions": [_action("legacy", "Vista Flask", "/compensi-forensi?_legacy=1", "warning")],
        "forms": [],
        "warnings": [_warning("compensi_errore_controllato", message)],
    }
