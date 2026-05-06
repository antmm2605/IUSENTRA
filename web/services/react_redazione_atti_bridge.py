"""Bridge read-only per la superficie React Redazione Atti."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from web.services.react_template_atti_bridge import (
    _action,
    _item,
    _metric,
    _section,
    _short,
    _text,
    _warning,
    build_react_template_atti_payload,
)


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_count(label: str, loader: Callable[[], Any], warnings: list[dict[str, str]]) -> int:
    try:
        result = loader()
        if isinstance(result, list):
            return len(result)
        return len(list(result))
    except Exception as exc:
        warnings.append(_warning(f"{label}_non_disponibile", f"Sorgente {label} non disponibile: {type(exc).__name__}."))
        return 0


def _template_refs(template_payload: dict[str, Any]) -> list[dict[str, Any]]:
    records = template_payload.get("records") if isinstance(template_payload, dict) else []
    refs: list[dict[str, Any]] = []
    for record in records if isinstance(records, list) else []:
        if not isinstance(record, dict):
            continue
        refs.append(
            {
                "id": _text(record.get("id")) or f"template_{len(refs) + 1}",
                "title": _text(record.get("title")) or "Template",
                "subtitle": _text(record.get("subtitle") or record.get("category")),
                "meta": _text(record.get("matter") or record.get("channel")),
                "stateLabel": _text(record.get("stateLabel")) or "Metadati",
                "stateTone": _text(record.get("stateTone")) or "neutral",
                "href": _text(record.get("href")) or "/template-atti/catalogo",
            }
        )
    return refs


def build_react_redazione_atti_payload(
    *,
    get_template_manager: Callable[[], Any],
    get_fascicoli: Callable[[], Any] | None = None,
    get_preventivi: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    warnings: list[dict[str, str]] = [
        _warning("workflow_legacy", "Redazione guidata, assistenza redazionale e produzione file restano nei percorsi Flask legacy."),
        _warning("solo_metadati", "Questa pagina mostra solo quadro operativo, template di riferimento e link controllati."),
    ]
    template_payload = build_react_template_atti_payload(
        get_template_manager=get_template_manager,
        page="redazione",
    )
    warnings.extend(template_payload.get("warnings") or [])
    template_refs = _template_refs(template_payload)
    fascicoli_count = 0
    if get_fascicoli:
        fascicoli_count = _safe_count(
            "fascicoli",
            lambda: get_fascicoli().tutti(archiviati=False),
            warnings,
        )
    preventivi_count = 0
    if get_preventivi:
        preventivi_count = _safe_count(
            "preventivi",
            lambda: get_preventivi().tutti(),
            warnings,
        )

    workflow_items = [
        _item("scegli_template", "Scegli template", "React", "Catalogo e metadati senza contenuti integrali", "primary"),
        _item("redazione_guidata", "Redazione guidata", "legacy", "Compilazione e revisione restano su Flask", "warning"),
        _item("checklist", "Checklist", "legacy", "Controlli deposito e fascicolo restano operativi nel legacy", "warning"),
        _item("lex", "Lex", "legacy", "Assistenza contenuti solo nei workflow gia' governati", "neutral"),
    ]

    records = [
        {
            "id": "workflow_template",
            "title": "Catalogo template",
            "subtitle": "Punto di ingresso React",
            "meta": f"{len(template_refs)} template consultabili come metadati",
            "stateLabel": "React",
            "stateTone": "primary",
            "href": "/template-atti/catalogo",
        },
        {
            "id": "workflow_legacy",
            "title": "Redazione guidata legacy",
            "subtitle": "Compilazione controllata",
            "meta": "Editor, controlli e file restano sul percorso storico",
            "stateLabel": "Legacy",
            "stateTone": "warning",
            "href": "/template-atti?_legacy=1",
        },
    ]
    records.extend(template_refs)

    return {
        "source": "repository_reali",
        "generated_at": _iso_now(),
        "contracts": {
            "mock_fallback": False,
            "writes": "legacy_routes",
            "route_owner": "react_shell",
            "legacy_contract": "artifacts/react-migration/legacy-contracts/redazione-atti.json",
        },
        "metrics": [
            _metric("template", "Template", len(template_refs), "Riferimenti sicuri", "primary"),
            _metric("fascicoli", "Fascicoli attivi", fascicoli_count, "Conteggio repository", "info" if fascicoli_count else "neutral"),
            _metric("preventivi", "Preventivi", preventivi_count, "Collegamenti mandato", "neutral"),
            _metric("workflow", "Workflow", len(workflow_items), "Ingresso operativo", "warning"),
        ],
        "sections": [
            _section("workflow", "Workflow disponibili", "operational", workflow_items, "Nessun workflow disponibile."),
            _section(
                "fonti",
                "Fonti collegate",
                "metadata",
                [
                    _item("template", "Template atti", len(template_refs), "Solo metadati e variabili nominate", "primary"),
                    _item("fascicoli", "Fascicoli", fascicoli_count, "Solo conteggio sicuro in questa tranche", "neutral"),
                    _item("preventivi", "Preventivi", preventivi_count, "Collegamento al mandato economico", "neutral"),
                ],
                "Nessuna fonte collegata.",
            ),
            _section(
                "presidi",
                "Presidi conservati",
                "legacy-routes",
                [
                    _item("template_editor", "Editor template", "legacy", "Creazione e modifica non sono React", "warning"),
                    _item("deposito", "Checklist deposito", "legacy", "Flusso telematico non sbloccato", "warning"),
                    _item("intelligence", "Giurisprudenza e intelligence", "legacy", "Ricerca e monitoraggio restano su Flask", "warning"),
                ],
                "Nessun presidio rilevato.",
            ),
        ],
        "records": records,
        "actions": [
            _action("catalogo", "Catalogo template", "/template-atti/catalogo", "primary"),
            _action("nuovo_template", "Nuovo template legacy", "/template-atti/nuovo?_legacy=1", "neutral"),
            _action("checklist", "Checklist legacy", "/checklist?_legacy=1", "neutral"),
            _action("deposito", "Checklist deposito legacy", "/deposito/checklist?_legacy=1", "warning"),
            _action("fascicoli", "Fascicoli", "/fascicoli", "primary"),
            _action("preventivi", "Preventivi", "/preventivi", "neutral"),
            _action("intelligence", "Legal intelligence legacy", "/legal-intelligence?_legacy=1", "neutral"),
        ],
        "forms": [],
        "warnings": warnings,
        "summary": _short("Quadro operativo per scegliere template, fascicolo e controlli prima di rientrare nei workflow legacy completi.", 240),
    }


def build_react_redazione_atti_error_payload(message: str = "Redazione atti non disponibile.") -> dict[str, Any]:
    return {
        "source": "errore_controllato",
        "generated_at": _iso_now(),
        "contracts": {
            "mock_fallback": False,
            "writes": "legacy_routes",
            "route_owner": "react_shell",
            "legacy_contract": "artifacts/react-migration/legacy-contracts/redazione-atti.json",
        },
        "metrics": [],
        "sections": [],
        "records": [],
        "actions": [
            _action("catalogo", "Catalogo template", "/template-atti/catalogo", "primary"),
            _action("checklist", "Checklist legacy", "/checklist?_legacy=1", "neutral"),
        ],
        "forms": [],
        "warnings": [_warning("redazione_atti_errore_controllato", message)],
        "summary": "",
    }
