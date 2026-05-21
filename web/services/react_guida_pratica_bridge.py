"""Bridge React/API per Guida Pratica fascicolo.

Il bridge resta sottile: risolve il fascicolo dai repository esistenti, legge il codice oggetto PST già esposto
nel payload fascicoli e delega la conoscenza a `pct.guida_pratica.GuidaPraticaService`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Callable

from pct.guida_pratica import GuidaPraticaError, GuidaPraticaService, normalize_codice_materia


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _text(value: Any, default: str = "") -> str:
    text = str(value if value is not None else default).strip()
    return text if text else default


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "").strip()


def _safe(label: str, func: Callable[[], Any], fallback: Any) -> Any:
    try:
        return func()
    except Exception:
        return fallback


def _fascicolo_lookup_keys(fascicolo: Any) -> set[str]:
    fields = (
        "id",
        "id_pratica",
        "numero",
        "numero_interno",
        "numero_rg",
        "riferimento",
        "reference",
        "codice",
        "codice_fascicolo",
        "source_external_id",
        "import_log_id",
    )
    keys = {_text(getattr(fascicolo, field, "")) for field in fields}
    keys.update({_text(getattr(fascicolo, "id", "")).upper(), _text(getattr(fascicolo, "id", "")).lower()})
    return {key for key in keys if key}


def resolve_fascicolo_for_guida(get_fascicoli: Callable[[], Any], requested_id: str) -> Any | None:
    repo = get_fascicoli()
    direct = _safe("fascicolo_direct", lambda: repo.get(requested_id), None)
    if direct:
        return direct
    wanted = _text(requested_id).casefold()
    if not wanted:
        return None
    for fascicolo in _safe("fascicoli_all", lambda: repo.tutti(), []):
        if wanted in {key.casefold() for key in _fascicolo_lookup_keys(fascicolo)}:
            return fascicolo
    return None


def fascicolo_guida_context(fascicolo: Any) -> dict[str, Any]:
    return {
        "id": _text(getattr(fascicolo, "id", "")),
        "titolo": _text(getattr(fascicolo, "titolo", "") or getattr(fascicolo, "oggetto", "")),
        "title": _text(getattr(fascicolo, "titolo", "") or getattr(fascicolo, "oggetto", "")),
        "tipo": _enum_value(getattr(fascicolo, "tipo", "")),
        "stato": _enum_value(getattr(fascicolo, "stato", "")),
        "cliente": _text(getattr(fascicolo, "nome_cliente", "")),
        "controparte": _text(getattr(fascicolo, "controparte", "")),
        "tribunale": _text(getattr(fascicolo, "tribunale", "")),
        "numero_rg": _text(getattr(fascicolo, "numero_rg", "")),
        "anno_rg": _text(getattr(fascicolo, "anno_rg", "")),
        "codice_oggetto_pst": normalize_codice_materia(getattr(fascicolo, "codice_oggetto_pst", "")),
        "codiceOggettoPst": normalize_codice_materia(getattr(fascicolo, "codice_oggetto_pst", "")),
        "fonte_codice_oggetto": _text(getattr(fascicolo, "fonte_codice_oggetto", "")),
        "fonteCodiceOggetto": _text(getattr(fascicolo, "fonte_codice_oggetto", "")),
        "file_fonte_codice_oggetto": _text(getattr(fascicolo, "file_fonte_codice_oggetto", "")),
        "fileFonteCodiceOggetto": _text(getattr(fascicolo, "file_fonte_codice_oggetto", "")),
        "valore_causa": _text(getattr(fascicolo, "valore_causa", "")),
    }


def build_react_guida_pratica_payload(*, codice: str, fascicolo: dict[str, Any] | None = None, service: GuidaPraticaService | None = None) -> dict[str, Any]:
    service = service or GuidaPraticaService()
    guida = service.get_guidance(codice, fascicolo=fascicolo or {})
    checklist = service.get_checklist(codice, {"fascicolo": fascicolo or {}})
    return {
        "ok": True,
        "source": "legal_knowledge_base_json_catalogo_xsd",
        "generatedAt": _now(),
        "guida": guida,
        "checklist": checklist,
        "catalogoSize": service.catalog_size(),
    }


def build_react_guida_pratica_catalog_payload(*, query: str = "", coverage: str = "", limit: int = 500, service: GuidaPraticaService | None = None) -> dict[str, Any]:
    service = service or GuidaPraticaService()
    rows = service.list_guidance(query=query, coverage=coverage, limit=limit)
    counts: dict[str, int] = {}
    for row in rows:
        level = _text((row.get("coverage") or {}).get("level"), "sconosciuta") if isinstance(row.get("coverage"), dict) else "sconosciuta"
        counts[level] = counts.get(level, 0) + 1
    return {
        "ok": True,
        "source": "catalogo_xsd_e_kb",
        "generatedAt": _now(),
        "items": rows,
        "summary": {
            "total": len(rows),
            "catalogoSize": service.catalog_size(),
            "coverage": counts,
        },
    }


def build_react_fascicolo_guida_pratica_payload(*, get_fascicoli: Callable[[], Any], id_fasc: str, service: GuidaPraticaService | None = None) -> dict[str, Any]:
    fascicolo = resolve_fascicolo_for_guida(get_fascicoli, id_fasc)
    if not fascicolo:
        return {"ok": False, "generatedAt": _now(), "notFound": True, "message": "Fascicolo non trovato."}
    context = fascicolo_guida_context(fascicolo)
    codice = normalize_codice_materia(context.get("codice_oggetto_pst"))
    if not codice:
        return {
            "ok": False,
            "generatedAt": _now(),
            "fascicolo": context,
            "message": "Il fascicolo non ha un codice oggetto PST/materia valorizzato. Impostalo nella scheda fascicolo per attivare la Guida Pratica.",
            "code": "codice_oggetto_missing",
        }
    payload = build_react_guida_pratica_payload(codice=codice, fascicolo=context, service=service)
    payload["fascicolo"] = context
    return payload


def build_react_guida_pratica_checklist_payload(*, codice: str, dati: dict[str, Any], service: GuidaPraticaService | None = None) -> dict[str, Any]:
    service = service or GuidaPraticaService()
    checklist = service.get_checklist(codice, dati)
    return {"ok": True, "generatedAt": _now(), "checklist": checklist}


def guida_pratica_error_payload(error: Exception) -> dict[str, Any]:
    if isinstance(error, GuidaPraticaError):
        return {"ok": False, "code": "guida_pratica_error", "message": str(error), "generatedAt": _now()}
    return {"ok": False, "code": "guida_pratica_unavailable", "message": "Guida Pratica non disponibile.", "generatedAt": _now()}
