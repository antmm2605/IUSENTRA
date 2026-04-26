"""Servizi catalogo template atti per UI, filtri e controlli deposito."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import datetime
from typing import Any

from pct.template_atti_master_catalog import catalogo_master_stats, load_catalogo_master, load_split_catalogs
from pct.template_deposit_rules import compliance_template_summary, normalizza_canale, portale_deposito_label


SUITE_GROUP_LABELS: dict[str, str] = {
    "core": "Core processuale e civile",
    "advanced": "Studio generalista evoluto",
    "specialist": "Riti e portali specialistici",
    "studio_interno": "Atti interni di studio",
}


QUICK_FILTERS = [
    ("Civile", "materia", "Diritto civile"),
    ("Giudice di Pace", "canale_deposito", "PST_GDP"),
    ("Decreto ingiuntivo", "procedimento", "Procedimento monitorio"),
    ("Famiglia", "materia", "Diritto di famiglia"),
    ("Volontaria giurisdizione", "rito", "Volontaria giurisdizione"),
    ("Locazioni", "procedimento", "Locazioni, condominio e immobili"),
    ("Penale", "canale_deposito", "PDP"),
    ("Tributario", "canale_deposito", "PTT"),
    ("Amministrativo", "canale_deposito", "PAT"),
    ("Stragiudiziale", "natura_atto", "stragiudiziale"),
    ("Atti interni", "canale_deposito", "NESSUNO"),
    ("Preventivi", "query", "preventivo"),
    ("Incarichi", "query", "incarico"),
    ("Deposito telematico", "depositabile", "true"),
    ("Firma obbligatoria", "richiede_firma_digitale", "true"),
    ("PDF/A obbligatorio", "richiede_pdfa", "true"),
]


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _template_prefix(template_id: str, module_codes: list[str]) -> str:
    ordered = sorted(module_codes, key=len, reverse=True)
    for code in ordered:
        if template_id == code or template_id.startswith(f"{code}_"):
            return code
    return template_id.split("_", 1)[0]


def _build_split_index() -> dict[str, dict[str, str]]:
    index: dict[str, dict[str, str]] = {}
    for group_key, payload in load_split_catalogs().items():
        for item in payload.get("template") or []:
            template_id = _clean(item.get("id"))
            if template_id:
                index[template_id] = {
                    "categoria_suite": group_key,
                    "categoria_suite_label": SUITE_GROUP_LABELS.get(group_key, group_key.replace("_", " ").title()),
                }
    return index


def _module_index(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {_clean(item.get("codice")): dict(item) for item in payload.get("moduli") or [] if _clean(item.get("codice"))}


def _derive_natura_atto(item: dict[str, Any]) -> str:
    area = _clean(item.get("area")).lower()
    fase = _clean(item.get("fase")).lower()
    titolo = _clean(item.get("titolo")).lower()
    canale = normalizza_canale(item.get("canale_telematico"))
    if canale == "NESSUNO" or "interno" in area:
        return "interno"
    if "stragiud" in area or canale == "PEC":
        return "stragiudiziale"
    if any(token in titolo for token in ("appello", "cassazione", "reclamo", "opposizione")):
        return "impugnazione"
    if any(token in titolo for token in ("precetto", "pignoramento", "esecuzione", "assegnazione", "vendita")):
        return "esecuzione"
    if any(token in titolo for token in ("istanza", "memoria", "note", "deposito", "osservazioni")):
        return "istanza"
    if "deposito" in fase:
        return "deposito"
    return "giudiziale"


def _derive_tipo_atto(item: dict[str, Any]) -> str:
    titolo = _clean(item.get("titolo"))
    if not titolo:
        return _clean(item.get("procedimento")) or "Template atto"
    return titolo.split(" per ", 1)[0].split(" ex ", 1)[0][:80]


def _requires_pdfa(canale: str, depositabile: bool) -> bool:
    return bool(depositabile and canale in {"PST", "PST_GDP", "PST_CONCORSUALE", "PAT", "PTT", "PDP"})


def _requires_signature(canale: str, depositabile: bool) -> bool:
    return bool(depositabile and canale in {"PST", "PST_GDP", "PST_CONCORSUALE", "PAT", "PTT", "PDP"})


def _requires_dati_atto(canale: str, depositabile: bool) -> bool:
    return bool(depositabile and canale in {"PST", "PST_GDP", "PST_CONCORSUALE"})


def _requires_contributo(item: dict[str, Any], canale: str, depositabile: bool) -> bool:
    if not depositabile or canale not in {"PST", "PST_GDP", "PAT", "PTT"}:
        return False
    title = _clean(item.get("titolo")).lower()
    return any(token in title for token in ("ricorso", "citazione", "appello", "opposizione", "sfratto"))


def _output_previsti(item: dict[str, Any], canale: str, depositabile: bool) -> list[str]:
    outputs = ["docx", "pdf"]
    if _requires_pdfa(canale, depositabile):
        outputs.append("pdfa")
    if _requires_dati_atto(canale, depositabile):
        outputs.append("xml")
    if depositabile and canale != "NESSUNO":
        outputs.append("zip deposito")
    return outputs


def build_template_catalog_items() -> list[dict[str, Any]]:
    payload = load_catalogo_master()
    split_index = _build_split_index()
    modules = _module_index(payload)
    module_codes = list(modules)
    items: list[dict[str, Any]] = []

    for raw in payload.get("template") or []:
        item = deepcopy(raw)
        template_id = _clean(item.get("id"))
        canale = normalizza_canale(item.get("canale_telematico"))
        depositabile = bool(item.get("depositabile"))
        module_code = _template_prefix(template_id, module_codes)
        module = modules.get(module_code, {})
        split_meta = split_index.get(template_id, {})
        compliance = compliance_template_summary(canale, list(item.get("checklist_conformita") or []))
        campi_precompila = [_clean(value) for value in item.get("campi_precompila") or [] if _clean(value)]
        blocchi_guidati = [_clean(value) for value in item.get("blocchi_guidati") or [] if _clean(value)]
        allegati_obbligatori = [_clean(value) for value in item.get("allegati_essenziali") or [] if _clean(value)]
        tags = [_clean(value) for value in item.get("tags") or [] if _clean(value)]
        natura = _derive_natura_atto(item)
        richiede_pdfa = _requires_pdfa(canale, depositabile)
        richiede_firma = _requires_signature(canale, depositabile)
        richiede_dati_atto = _requires_dati_atto(canale, depositabile)
        richiede_contributo = _requires_contributo(item, canale, depositabile)
        search_parts = [
            template_id,
            item.get("slug"),
            item.get("titolo"),
            item.get("famiglia"),
            item.get("area"),
            item.get("macro_area"),
            item.get("sottobranca"),
            item.get("procedimento"),
            item.get("rito"),
            item.get("fase"),
            canale,
            portale_deposito_label(canale),
            natura,
            module.get("nome"),
            split_meta.get("categoria_suite_label"),
            *tags,
            *allegati_obbligatori,
            *campi_precompila,
        ]
        items.append(
            {
                **item,
                "codice": template_id,
                "descrizione": (
                    f"{_clean(item.get('titolo'))}: template master {item.get('versione')} "
                    f"per {_clean(item.get('famiglia'))}, rito {_clean(item.get('rito'))}."
                ),
                "categoria_suite": split_meta.get("categoria_suite", ""),
                "categoria_suite_label": split_meta.get("categoria_suite_label", "Suite professionale"),
                "modulo_professionale": _clean(module.get("nome")) or _clean(item.get("famiglia")),
                "modulo_codice": module_code,
                "materia": _clean(item.get("macro_area")),
                "tipo_atto": _derive_tipo_atto(item),
                "natura_atto": natura,
                "canale_deposito": canale,
                "portale_deposito": portale_deposito_label(canale),
                "normativa_riferimento": [
                    {
                        "fonte": rule["fonte_normativa"],
                        "versione": rule["versione_regola"],
                        "data_ultimo_aggiornamento": rule["data_ultimo_aggiornamento"],
                    }
                    for rule in compliance["regole"][:3]
                ],
                "controlli_conformita_dettaglio": compliance["regole"],
                "controlli_deposito_disponibili": compliance["totale"],
                "controlli_completi": compliance["completo"],
                "allegati_obbligatori": allegati_obbligatori,
                "allegati_facoltativi": [],
                "dati_obbligatori": campi_precompila,
                "blocchi_guidati": blocchi_guidati,
                "richiede_pdfa": richiede_pdfa,
                "richiede_firma_digitale": richiede_firma,
                "richiede_dati_atto_xml": richiede_dati_atto,
                "richiede_contributo_unificato": richiede_contributo,
                "richiede_marca_bollo": False,
                "output_previsti": _output_previsti(item, canale, depositabile),
                "stato": _clean(item.get("stato")) or "pronto",
                "priorita": int(item.get("ordinamento") or 9999),
                "tags": tags,
                "created_at": "",
                "updated_at": "",
                "search_text": " ".join(_clean(value).lower() for value in search_parts if _clean(value)),
                "compliance_summary": compliance,
            }
        )
    return sorted(items, key=lambda row: (row["priorita"], row["codice"]))


def _filter_values(items: list[dict[str, Any]], key: str) -> list[str]:
    return sorted({_clean(item.get(key)) for item in items if _clean(item.get(key))}, key=str.casefold)


def build_template_catalog_filters(items: list[dict[str, Any]]) -> dict[str, list[str]]:
    return {
        "materia": _filter_values(items, "materia"),
        "area": _filter_values(items, "area"),
        "macro_area": _filter_values(items, "macro_area"),
        "sottobranca": _filter_values(items, "sottobranca"),
        "procedimento": _filter_values(items, "procedimento"),
        "rito": _filter_values(items, "rito"),
        "fase": _filter_values(items, "fase"),
        "tipo_atto": _filter_values(items, "tipo_atto"),
        "categoria_suite": _filter_values(items, "categoria_suite_label"),
        "canale_deposito": _filter_values(items, "canale_deposito"),
        "portale_deposito": _filter_values(items, "portale_deposito"),
        "stato": _filter_values(items, "stato"),
        "natura_atto": _filter_values(items, "natura_atto"),
    }


def build_suite_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    stats = catalogo_master_stats()
    canali = Counter(item["canale_deposito"] for item in items)
    groups = Counter(item["categoria_suite_label"] for item in items)
    return {
        "titolo": "Suite professionale completa",
        "versione": f"v{stats.get('versione')}",
        "totale_template": len(items),
        "moduli_professionali": int(stats.get("moduli") or 0),
        "canali_governati": len(canali),
        "canali": dict(sorted(canali.items())),
        "categorie": dict(sorted(groups.items())),
        "badges": [
            "Compilatore atti",
            "Controlli deposito",
            "Normativa vigente",
            "Pre-verifica conformita",
        ],
    }


def build_suite_groups(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    order = ["Core processuale e civile", "Studio generalista evoluto", "Riti e portali specialistici", "Atti interni di studio"]
    groups: list[dict[str, Any]] = []
    for label in order:
        templates = [item for item in items if item.get("categoria_suite_label") == label]
        if not templates:
            continue
        groups.append({"label": label, "count": len(templates), "examples": templates[:3]})
    return groups


def build_template_catalog_page_context() -> dict[str, Any]:
    items = build_template_catalog_items()
    return {
        "suite_summary": build_suite_summary(items),
        "suite_groups": build_suite_groups(items),
        "template_suite": items,
        "template_filters": build_template_catalog_filters(items),
        "quick_filters": [{"label": label, "field": field, "value": value} for label, field, value in QUICK_FILTERS],
        "generated_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
    }


def get_template_catalog_item(codice: str) -> dict[str, Any] | None:
    requested = _clean(codice).upper()
    for item in build_template_catalog_items():
        if item["codice"].upper() == requested:
            return item
    return None


def verifica_deposito_template(codice: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    item = get_template_catalog_item(codice)
    if not item:
        return {"ok": False, "errore": "Template non trovato.", "codice": codice}
    payload = payload or {}
    missing_data = [
        field
        for field in item.get("dati_obbligatori", [])
        if field and not _clean(payload.get("dati", {}).get(field) if isinstance(payload.get("dati"), dict) else "")
    ]
    missing_attachments = [
        attachment
        for attachment in item.get("allegati_obbligatori", [])
        if attachment and not _clean(payload.get("allegati", {}).get(attachment) if isinstance(payload.get("allegati"), dict) else "")
    ]
    blocking_rules = [rule for rule in item["controlli_conformita_dettaglio"] if rule.get("blocca_deposito")]
    return {
        "ok": not missing_data and not missing_attachments,
        "codice": item["codice"],
        "titolo": item["titolo"],
        "canale_deposito": item["canale_deposito"],
        "portale_deposito": item["portale_deposito"],
        "ruleset_version": item["compliance_summary"]["ruleset_version"],
        "controlli": item["controlli_conformita_dettaglio"],
        "bloccanti_configurati": len(blocking_rules),
        "dati_mancanti": missing_data,
        "allegati_mancanti": missing_attachments,
        "messaggio": "Verifica superata." if not missing_data and not missing_attachments else "Completare dati e allegati prima del deposito.",
    }


__all__ = [
    "QUICK_FILTERS",
    "SUITE_GROUP_LABELS",
    "build_suite_summary",
    "build_template_catalog_filters",
    "build_template_catalog_items",
    "build_template_catalog_page_context",
    "get_template_catalog_item",
    "verifica_deposito_template",
]
