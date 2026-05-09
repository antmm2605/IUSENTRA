"""Bridge read-only per la superficie React Redazione Atti."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from web.services.react_template_atti_bridge import _action, _item, _metric, _section, _short, _text, _warning


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


def _template_refs(records: list[Any], *, limit: int = 18) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for record in records[:limit]:
        if isinstance(record, dict):
            title = _text(record.get("titolo") or record.get("title") or record.get("name"))
            subtitle = _text(record.get("tipo_atto") or record.get("procedimento") or record.get("subtitle"))
            meta = _text(record.get("materia") or record.get("area") or record.get("category"))
            record_id = _text(record.get("codice") or record.get("id")) or f"template_{len(refs) + 1}"
        else:
            title = _text(getattr(record, "titolo", ""))
            subtitle = _text(getattr(record, "fase", "") or getattr(record, "rito", ""))
            meta = _text(getattr(record, "area", "") or getattr(record, "categoria", ""))
            record_id = _text(getattr(record, "id", "")) or f"template_{len(refs) + 1}"
        refs.append(
            {
                "id": record_id,
                "title": title or "Template",
                "subtitle": subtitle,
                "meta": meta,
                "stateLabel": "Metadati",
                "stateTone": "neutral",
                "href": "/template-atti/catalogo",
            }
        )
    return refs


def _studio_templates(get_template_manager: Callable[[], Any], warnings: list[dict[str, str]]) -> list[Any]:
    try:
        manager = get_template_manager()
        reader = getattr(manager, "tutti", None)
        return list(reader()) if callable(reader) else []
    except Exception as exc:
        warnings.append(_warning("template_studio_non_disponibili", f"Template studio non disponibili: {type(exc).__name__}."))
        return []


def build_react_redazione_atti_payload(
    *,
    get_template_manager: Callable[[], Any],
    get_fascicoli: Callable[[], Any] | None = None,
    get_preventivi: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    warnings: list[dict[str, str]] = [
        _warning("workflow_dedicato", "Redazione guidata, assistenza redazionale e produzione file restano nei percorsi dedicati e auditati."),
        _warning("solo_metadati", "Questa pagina mostra solo quadro operativo, template di riferimento e link controllati."),
    ]
    studio_templates = _studio_templates(get_template_manager, warnings)
    template_refs = _template_refs(studio_templates)
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
            lambda: get_preventivi().tutti_preventivi(),
            warnings,
        )

    workflow_items = [
        _item("scegli_template", "Scegli template", "interfaccia", "Catalogo e metadati senza contenuti integrali", "primary"),
        _item("redazione_guidata", "Redazione guidata", "percorso dedicato", "Compilazione e revisione restano auditati", "warning"),
        _item("checklist", "Checklist", "percorso dedicato", "Controlli deposito e fascicolo restano nei workflow governati", "warning"),
        _item("lex", "Lex", "workspace", "Assistenza contenuti solo nei workflow gia' governati", "neutral"),
    ]

    records = [
        {
            "id": "workflow_template",
            "title": "Catalogo template",
            "subtitle": "Punto di ingresso operativo",
            "meta": f"{len(template_refs)} template consultabili come metadati",
            "stateLabel": "React",
            "stateTone": "primary",
            "href": "/template-atti/catalogo",
        },
        {
            "id": "workflow_guidato",
            "title": "Redazione guidata controllata",
            "subtitle": "Compilazione controllata",
            "meta": "Editor, controlli e file restano sul percorso governato",
            "stateLabel": "Governato",
            "stateTone": "warning",
            "href": "/redazione-atti",
        },
    ]
    records.extend(template_refs)

    return {
        "source": "repository_reali",
        "generated_at": _iso_now(),
        "contracts": {
            "mock_fallback": False,
            "writes": "none",
            "route_owner": "react_shell",
            "legacy_contract": "artifacts/react-migration/legacy-contracts/redazione-atti.json",
        },
        "metrics": [
            _metric("template", "Template", len(studio_templates), "Riferimenti sicuri", "primary"),
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
                "dedicated-routes",
                [
                    _item("template_editor", "Editor template", "percorso dedicato", "Creazione e modifica restano nei percorsi auditati", "warning"),
                    _item("deposito", "Checklist deposito", "percorso dedicato", "Flusso telematico non sbloccato", "warning"),
                    _item("intelligence", "Giurisprudenza e intelligence", "consultazione", "Ricerca e monitoraggio consultabili senza richiami esterni", "info"),
                ],
                "Nessun presidio rilevato.",
            ),
        ],
        "records": records,
        "actions": [
            _action("catalogo", "Catalogo template", "/template-atti/catalogo", "primary"),
            _action("fascicoli", "Fascicoli", "/fascicoli", "primary"),
            _action("preventivi", "Preventivi", "/preventivi", "neutral"),
            _action("intelligence", "Legal intelligence", "/legal-intelligence", "neutral"),
        ],
        "forms": [],
        "warnings": warnings,
        "summary": _short("Quadro operativo per scegliere template, fascicolo e controlli prima dei workflow documentali completi.", 240),
    }


def build_react_redazione_atti_error_payload(message: str = "Redazione atti non disponibile.") -> dict[str, Any]:
    return {
        "source": "errore_controllato",
        "generated_at": _iso_now(),
        "contracts": {
            "mock_fallback": False,
            "writes": "none",
            "route_owner": "react_shell",
            "legacy_contract": "artifacts/react-migration/legacy-contracts/redazione-atti.json",
        },
        "metrics": [],
        "sections": [],
        "records": [],
        "actions": [
            _action("catalogo", "Catalogo template", "/template-atti/catalogo", "primary"),
            _action("fascicoli", "Fascicoli", "/fascicoli", "neutral"),
        ],
        "forms": [],
        "warnings": [_warning("redazione_atti_errore_controllato", message)],
        "summary": "",
    }
