"""Bridge read-only per le superfici React Template Atti."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Callable


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _short(value: Any, limit: int = 180) -> str:
    text = _text(value)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


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


def _tone_from_state(value: Any) -> str:
    state = _text(value).lower()
    if state in {"attivo", "completo", "pronto", "validato"}:
        return "success"
    if state in {"bozza", "in revisione", "parziale"}:
        return "warning"
    if state in {"errore", "bloccato"}:
        return "danger"
    if state:
        return "info"
    return "neutral"


def _variable_names(values: Any) -> list[dict[str, str]]:
    names: list[dict[str, str]] = []
    seen: set[str] = set()
    for entry in _list(values):
        if isinstance(entry, dict):
            name = _text(entry.get("name") or entry.get("nome") or entry.get("id") or entry.get("label"))
            label = _text(entry.get("label") or entry.get("nome") or name)
            kind = _text(entry.get("type") or entry.get("tipo") or "metadato")
        else:
            name = _text(entry)
            label = name
            kind = "metadato"
        if not name or name in seen:
            continue
        seen.add(name)
        names.append({"name": name, "label": label or name, "kind": kind, "source": "metadata"})
    return names


def _catalog_record(row: dict[str, Any], index: int) -> dict[str, Any]:
    code = _text(row.get("codice")) or f"catalogo_{index}"
    channel = _text(row.get("canale_deposito") or row.get("portale_deposito"))
    state = _text(row.get("stato")) or ("depositabile" if row.get("depositabile") else "catalogo")
    compiler_code = _text(row.get("link_compilatore_code") or row.get("codice"))
    return {
        "id": code,
        "kind": "catalogo",
        "title": _text(row.get("titolo")) or _text(row.get("name")) or "Template",
        "subtitle": _text(row.get("tipo_atto") or row.get("procedimento") or row.get("fase")),
        "description": _short(row.get("descrizione"), 220),
        "category": _text(row.get("categoria_suite_label") or row.get("famiglia") or row.get("macro_area")),
        "matter": _text(row.get("materia") or row.get("area")),
        "area": _text(row.get("area") or row.get("macro_area")),
        "branch": _text(row.get("branca") or row.get("sottobranca")),
        "channel": channel or "Canale non indicato",
        "portal": _text(row.get("portale_deposito")),
        "stateLabel": state.capitalize(),
        "stateTone": _tone_from_state(state),
        "complianceLabel": "Controlli completi" if row.get("controlli_completi") else ("Da verificare" if row.get("controlli_deposito_disponibili") else ""),
        "updatedAt": _text(row.get("updated_at") or row.get("created_at")),
        "tags": [_text(item) for item in _list(row.get("tags")) if _text(item)],
        "requiredVariables": _variable_names(row.get("dati_obbligatori")),
        "href": f"/template-atti/catalogo?template={compiler_code}" if compiler_code else "/template-atti/catalogo",
        "detailHref": f"/template-atti/catalogo?scheda={code}",
    }


def _studio_record(template: Any, index: int) -> dict[str, Any]:
    template_id = _text(getattr(template, "id", "")) or f"studio_{index}"
    state = "built-in" if bool(getattr(template, "builtin", False)) else "studio"
    channel = _text(getattr(template, "canale_telematico", ""))
    return {
        "id": template_id,
        "kind": "studio",
        "title": _text(getattr(template, "titolo", "")) or "Template studio",
        "subtitle": _text(getattr(template, "fase", "") or getattr(template, "rito", "")),
        "description": _short(getattr(template, "descrizione", ""), 220),
        "category": _text(getattr(template, "categoria", "")),
        "matter": _text(getattr(template, "branca", "") or getattr(template, "sottobranca", "")),
        "area": _text(getattr(template, "area", "")),
        "branch": _text(getattr(template, "sottobranca", "")),
        "channel": channel or "Canale non indicato",
        "portal": _text(getattr(template, "profilo_deposito", "")),
        "stateLabel": "Sistema" if state == "built-in" else "Studio",
        "stateTone": "info" if state == "built-in" else "primary",
        "complianceLabel": "Metadati deposito" if getattr(template, "controlli_conformita", None) else "",
        "updatedAt": _text(getattr(template, "modificato_il", "") or getattr(template, "creato_il", "")),
        "tags": [_text(item) for item in _list(getattr(template, "parole_chiave", [])) if _text(item)],
        "requiredVariables": _variable_names(getattr(template, "campi_guidati", [])),
        "href": f"/template-atti/catalogo?template={template_id}",
        "detailHref": f"/template-atti/catalogo?scheda={template_id}",
    }


def _counter_section(
    sid: str,
    title: str,
    kind: str,
    values: list[str],
    empty: str,
) -> dict[str, Any]:
    counter = Counter(value for value in values if value)
    items = [
        _item(key.lower().replace(" ", "_") or f"{sid}_{index}", key, count, "", "neutral")
        for index, (key, count) in enumerate(counter.most_common(), start=1)
    ]
    return _section(sid, title, kind, items, empty)


def _safe_catalog_rows(warnings: list[dict[str, str]]) -> list[dict[str, Any]]:
    try:
        from pct.template_catalog_service import build_template_catalog_page_context

        context = build_template_catalog_page_context()
        rows = context.get("template_suite") if isinstance(context, dict) else []
        return [row for row in _list(rows) if isinstance(row, dict)]
    except Exception as exc:
        warnings.append(_warning("catalogo_non_disponibile", f"Catalogo template non disponibile: {type(exc).__name__}."))
        return []


def _safe_studio_templates(
    get_template_manager: Callable[[], Any],
    warnings: list[dict[str, str]],
) -> list[Any]:
    try:
        manager = get_template_manager()
        reader = getattr(manager, "tutti", None)
        return list(reader()) if callable(reader) else []
    except Exception as exc:
        warnings.append(_warning("template_studio_non_disponibili", f"Template studio non disponibili: {type(exc).__name__}."))
        return []


def build_react_template_atti_payload(
    *,
    get_template_manager: Callable[[], Any],
    page: str = "dashboard",
) -> dict[str, Any]:
    warnings: list[dict[str, str]] = [
        _warning("editor_dedicato", "Editor, compilazione assistita, esportazioni e stampe restano nei percorsi Flask dedicati e auditati."),
        _warning("metadati_sicuri", "React riceve solo metadati, variabili come nomi e link operativi sicuri."),
    ]
    catalog_rows = _safe_catalog_rows(warnings)
    studio_templates = _safe_studio_templates(get_template_manager, warnings)
    catalog_records = [_catalog_record(row, index) for index, row in enumerate(catalog_rows, start=1)]
    studio_records = [_studio_record(template, index) for index, template in enumerate(studio_templates, start=1)]
    records = catalog_records + studio_records

    categories = [record["category"] for record in records]
    matters = [record["matter"] or record["area"] for record in records]
    channels = [record["channel"] for record in records]
    with_variables = sum(1 for record in records if record.get("requiredVariables"))
    catalog_total = len(catalog_records)
    studio_total = len(studio_records)

    legacy_contract = (
        "artifacts/react-migration/legacy-contracts/template-atti__catalogo.json"
        if page == "catalogo"
        else "artifacts/react-migration/legacy-contracts/template-atti.json"
    )
    return {
        "source": "repository_reali",
        "generated_at": _iso_now(),
        "contracts": {
            "mock_fallback": False,
            "writes": "none",
            "route_owner": "react_shell",
            "legacy_contract": legacy_contract,
        },
        "metrics": [
            _metric("template_totali", "Template", len(records), "Catalogo e modelli studio", "primary"),
            _metric("catalogo", "Catalogo", catalog_total, "Template classificati", "info"),
            _metric("studio", "Studio", studio_total, "Modelli locali", "neutral"),
            _metric("variabili", "Variabili", with_variables, "Solo nomi e metadati", "warning" if with_variables else "neutral"),
        ],
        "sections": [
            _counter_section("categorie", "Categorie", "distribution", categories, "Nessuna categoria disponibile."),
            _counter_section("materie", "Materie", "distribution", matters, "Nessuna materia disponibile."),
            _counter_section("canali", "Canali", "distribution", channels, "Nessun canale indicato."),
            _section(
                "presidi",
                "Presidi documentali conservati",
                "dedicated-routes",
                [
                    _item("nuovo", "Nuovo template", "percorso dedicato", "Creazione e modifica restano su Flask auditato", "warning"),
                    _item("redazione", "Redazione guidata", "percorso dedicato", "Workflow completo non spostato in React", "warning"),
                    _item("file", "Stampe e file", "percorso dedicato", "Produzione e download restano sui percorsi governati", "warning"),
                ],
                "Nessun presidio rilevato.",
            ),
        ],
        "records": records,
        "actions": [
            _action("catalogo", "Catalogo template", "/template-atti/catalogo", "primary"),
            _action("redazione", "Redazione atti", "/redazione-atti", "primary"),
            _action("documenti", "Console documenti", "/documenti", "neutral"),
        ],
        "forms": [],
        "warnings": warnings,
    }


def build_react_template_atti_error_payload(message: str = "Template atti non disponibili.") -> dict[str, Any]:
    return {
        "source": "errore_controllato",
        "generated_at": _iso_now(),
        "contracts": {
            "mock_fallback": False,
            "writes": "none",
            "route_owner": "react_shell",
            "legacy_contract": "artifacts/react-migration/legacy-contracts/template-atti.json",
        },
        "metrics": [],
        "sections": [],
        "records": [],
        "actions": [
            _action("catalogo", "Catalogo template", "/template-atti/catalogo", "primary"),
            _action("redazione", "Redazione atti", "/redazione-atti", "neutral"),
        ],
        "forms": [],
        "warnings": [_warning("template_atti_errore_controllato", message)],
    }
