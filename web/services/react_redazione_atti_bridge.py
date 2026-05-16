"""Dati consultabili per la pagina Redazione Atti."""

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
        warnings.append(_warning(f"{label}_non_disponibile", f"Dati {label} non disponibili."))
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
                "stateLabel": "Informazioni",
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


def _compiler_models(config: dict[str, Any] | None = None, *, limit: int = 10) -> list[dict[str, Any]]:
    try:
        from pct.compilatore_atti import MODELS, campi_modello, prefill_payload
    except Exception:
        return []
    models: list[dict[str, Any]] = []
    for model in list(MODELS)[:limit]:
        code = _text(model.get("code"))
        if not code:
            continue
        initial = prefill_payload(code, config=config or {})
        fields = []
        for field in campi_modello(code)[:18]:
            name = _text(field.get("name"))
            if not name:
                continue
            options = [
                {"value": _text(value), "label": _text(label)}
                for value, label in list(field.get("options") or [])[:80]
            ]
            fields.append(
                {
                    "name": name,
                    "label": _text(field.get("label")) or name.replace("_", " ").title(),
                    "type": _text(field.get("type")) or "text",
                    "required": True,
                    "value": _text(initial.get(name)),
                    "options": options,
                }
            )
        models.append(
            {
                "code": code,
                "title": _text(model.get("name")) or code,
                "area": _text(model.get("area_label") or model.get("area")),
                "summary": _short(model.get("summary") or model.get("description") or model.get("name"), 180),
                "fields": fields,
            }
        )
    return models


def build_react_redazione_atti_payload(
    *,
    get_template_manager: Callable[[], Any],
    get_fascicoli: Callable[[], Any] | None = None,
    get_preventivi: Callable[[], Any] | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    warnings: list[dict[str, str]] = []
    studio_templates = _studio_templates(get_template_manager, warnings)
    template_refs = _template_refs(studio_templates)
    production_models = _compiler_models(config)
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
        _item("scegli_template", "Scegli template", "in pagina", "Catalogo e modelli disponibili nella stessa pagina", "primary"),
        _item("produci_anteprima", "Produci atto", "in pagina", "Compilazione con anteprima immediata", "success"),
        _item("verifica", "Verifica campi", "controllo", "Validazioni del compilatore prima dell'uso", "warning"),
        _item("lex", "Lex", "workspace", "Assistenza contestuale su modello e fascicolo", "neutral"),
    ]

    records = [
        {
            "id": "workflow_template",
            "title": "Catalogo template",
            "subtitle": "Punto di ingresso operativo",
            "meta": f"{len(template_refs)} template e {len(production_models)} modelli produttivi",
            "stateLabel": "In pagina",
            "stateTone": "primary",
            "href": "/template-atti/catalogo",
        },
        {
            "id": "workflow_guidato",
            "title": "Produzione atti",
            "subtitle": "Compilazione e anteprima immediata",
            "meta": "Modelli reali del compilatore integrati nella pagina",
            "stateLabel": "In pagina",
            "stateTone": "success",
            "href": "/redazione-atti",
        },
    ]
    records.extend(template_refs)

    return {
        "source": "repository_reali",
        "generated_at": _iso_now(),
        "contracts": {
            "mock_fallback": False,
            "writes": "azioni_protette",
            "route_owner": "react_shell",
            "legacy_contract": "artifacts/react-migration/legacy-contracts/redazione-atti.json",
        },
        "metrics": [
            _metric("template", "Template", len(studio_templates), "Riferimenti sicuri", "primary"),
            _metric("produzione", "Modelli produzione", len(production_models), "Compilatore atti", "success" if production_models else "neutral"),
            _metric("fascicoli", "Fascicoli attivi", fascicoli_count, "Conteggio archivio", "info" if fascicoli_count else "neutral"),
            _metric("preventivi", "Preventivi", preventivi_count, "Collegamenti mandato", "neutral"),
        ],
        "sections": [
            _section("percorsi", "Percorsi disponibili", "operativa", workflow_items, "Nessun percorso disponibile."),
            _section(
                "fonti",
                "Fonti collegate",
                "informazioni",
                [
                    _item("template", "Template atti", len(template_refs), "Campi e variabili disponibili", "primary"),
                    _item("fascicoli", "Fascicoli", fascicoli_count, "Conteggio disponibile", "neutral"),
                    _item("preventivi", "Preventivi", preventivi_count, "Collegamento al mandato economico", "neutral"),
                ],
                "Nessuna fonte collegata.",
            ),
            _section(
                "produzione",
                "Produzione atti",
                "operativa",
                [
                    _item("modelli", "Modelli compilatore", len(production_models), "Selezione e campi guidati in pagina", "success" if production_models else "neutral"),
                    _item("validazioni", "Validazioni", "attive", "Campi obbligatori controllati prima dell'anteprima", "success"),
                    _item("telematico", "Servizi telematici", "fase dedicata", "Deposito e portali saranno completati nel percorso previsto", "warning"),
                ],
                "Nessun presidio rilevato.",
            ),
        ],
        "records": records,
        "actions": [
            _action("catalogo", "Catalogo template", "/template-atti/catalogo", "primary"),
            _action("fascicoli", "Fascicoli", "/fascicoli", "primary"),
            _action("preventivi", "Preventivi", "/preventivi", "neutral"),
            _action("intelligence", "Ricerca legale", "/ricerca-legale", "neutral"),
        ],
        "forms": [],
        "warnings": warnings,
        "production": {
            "defaultModelCode": production_models[0]["code"] if production_models else "",
            "models": production_models,
            "endpoint": "/api/v1/ui/redazione-atti/produci",
        },
        "summary": _short("Quadro operativo per scegliere template, fascicolo e controlli prima dei percorsi documentali completi.", 240),
    }


def produce_react_redazione_atti(payload: dict[str, Any], *, config: dict[str, Any] | None = None) -> tuple[dict[str, Any], int]:
    try:
        from pct.compilatore_atti import prefill_payload, render_compiled_act, validate_payload
    except Exception:
        return {"ok": False, "errors": {}, "warnings": ["Compilatore atti non disponibile."]}, 200
    model_code = _text(payload.get("modelCode") or payload.get("model_code"))
    values = payload.get("values") if isinstance(payload.get("values"), dict) else {}
    if not model_code:
        return {"ok": False, "errors": {"modelCode": "Seleziona un modello."}, "warnings": []}, 200
    initial = prefill_payload(model_code, config=config or {})
    compiled_payload = {**initial, **{str(k): v for k, v in values.items()}}
    errors = validate_payload(model_code, compiled_payload)
    if errors:
        return {"ok": False, "title": initial.get("title", "Atto"), "preview": "", "errors": errors, "warnings": []}, 200
    text = render_compiled_act(model_code, compiled_payload)
    return {
        "ok": True,
        "title": _text(compiled_payload.get("title")) or "Atto",
        "preview": text,
        "errors": {},
        "warnings": [],
    }, 200


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
