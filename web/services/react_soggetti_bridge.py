"""Bridge dati per la pagina React Soggetti e Parti.

La superficie React resta progressiva e read-only: usa i repository reali per
lista, conteggi e collegamenti, mentre le scritture restano nelle route Flask.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Callable

from pct.soggetti import TipoSoggetto


def _text(value: Any, fallback: str = "") -> str:
    return " ".join(str(value or fallback).split())


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "")


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe(func: Callable[[], Any], fallback: Any) -> Any:
    try:
        return func()
    except Exception:
        return fallback


def _tipo_label(value: str) -> str:
    return value.replace("_", " ").title()


def _is_legal_type(value: Any) -> bool:
    tipo = _enum_value(value)
    return tipo in {"PERSONA_GIURIDICA", "PUBBLICA_AMMINISTRAZIONE", "ENTE", "CONDOMINIO", "ASSOCIAZIONE"}


def _tone(value: str) -> str:
    return {
        "PERSONA_FISICA": "primary",
        "PERSONA_GIURIDICA": "purple",
        "PUBBLICA_AMMINISTRAZIONE": "info",
        "ENTE": "neutral",
        "CONDOMINIO": "orange",
        "ASSOCIAZIONE": "success",
        "PROFESSIONISTA": "primary",
    }.get(value, "neutral")


def _client_index(clienti: list[Any]) -> dict[str, str]:
    return {
        _text(getattr(cliente, "id", "")): _text(getattr(cliente, "nome_completo", "")) or "Cliente senza nome"
        for cliente in clienti
        if _text(getattr(cliente, "id", ""))
    }


def _subject_items(soggetti_repo: Any, soggetti: list[Any], clienti: list[Any]) -> list[dict[str, Any]]:
    clienti_by_id = _client_index(clienti)
    rows: list[dict[str, Any]] = []
    for index, soggetto in enumerate(soggetti):
        item_id = _text(getattr(soggetto, "id", "")) or f"soggetto-{index}"
        tipo = _enum_value(getattr(soggetto, "tipo", TipoSoggetto.PERSONA_FISICA))
        recapiti = getattr(soggetto, "recapiti", None)
        indirizzo = getattr(soggetto, "indirizzo", None)
        fascicoli = _safe(lambda: soggetti_repo.fascicoli_con_soggetto(item_id), [])
        id_cliente = _text(getattr(soggetto, "id_cliente", ""))
        rows.append({
            "id": item_id,
            "name": _text(getattr(soggetto, "nome_completo", "")) or "Soggetto senza nome",
            "type": tipo,
            "typeLabel": _tipo_label(tipo),
            "role": _text(getattr(soggetto, "qualifica", "")) or "ALTRO",
            "identifier": _text(getattr(soggetto, "identificativo", "") or getattr(soggetto, "codice_fiscale", "") or getattr(soggetto, "partita_iva", "")) or "-",
            "email": _text(getattr(recapiti, "email", "")),
            "phone": _text(getattr(recapiti, "cellulare", "") or getattr(recapiti, "telefono", "")),
            "pec": _text(getattr(recapiti, "pec", "")),
            "city": _text(getattr(indirizzo, "comune", "")),
            "province": _text(getattr(indirizzo, "provincia", "")),
            "clientId": id_cliente,
            "clientName": clienti_by_id.get(id_cliente, ""),
            "matters": len(fascicoli) if isinstance(fascicoli, list) else 0,
            "isLegal": _is_legal_type(getattr(soggetto, "tipo", "")),
            "missingFields": [
                label for label, missing in (
                    ("nome o ragione sociale", not _text(getattr(soggetto, "nome_completo", "")).replace("-", "")),
                    ("identificativo fiscale", not _text(getattr(soggetto, "identificativo", "") or getattr(soggetto, "codice_fiscale", "") or getattr(soggetto, "partita_iva", ""))),
                    ("recapito", not (_text(getattr(recapiti, "email", "")) or _text(getattr(recapiti, "cellulare", "")) or _text(getattr(recapiti, "telefono", "")) or _text(getattr(recapiti, "pec", "")))),
                ) if missing
            ],
            "href": f"/soggetti/{item_id}",
            "editHref": f"/soggetti/{item_id}/modifica",
            "tone": _tone(tipo),
        })
    return rows


def _summary(items: list[dict[str, Any]]) -> dict[str, int]:
    types = Counter(item.get("type") for item in items)
    return {
        "total": len(items),
        "physical": int(types.get("PERSONA_FISICA", 0)),
        "legal": sum(1 for item in items if item.get("isLegal")),
        "professionals": int(types.get("PROFESSIONISTA", 0)),
        "linkedClients": sum(1 for item in items if item.get("clientId")),
        "withMatters": sum(1 for item in items if int(item.get("matters") or 0) > 0),
        "incomplete": sum(1 for item in items if item.get("missingFields")),
        "withoutContacts": sum(1 for item in items if not (item.get("email") or item.get("phone") or item.get("pec"))),
    }


def _facets(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    type_counts = Counter(item.get("type") for item in items)
    role_counts = Counter(item.get("role") or "ALTRO" for item in items)
    return {
        "types": [{"value": "tutti", "label": "Tutti i tipi", "count": len(items)}] + [
            {"value": item.value, "label": _tipo_label(item.value), "count": int(type_counts.get(item.value, 0))}
            for item in TipoSoggetto
        ],
        "roles": [{"value": "tutti", "label": "Tutti i ruoli", "count": len(items)}] + [
            {"value": role, "label": role.replace("_", " ").title(), "count": count}
            for role, count in sorted(role_counts.items())
        ],
    }


def build_react_soggetti_payload(
    *,
    get_soggetti: Callable[[], Any],
    get_clienti: Callable[[], Any],
) -> dict[str, Any]:
    soggetti_repo = get_soggetti()
    soggetti = _safe(lambda: soggetti_repo.tutti(), [])
    clienti = _safe(lambda: get_clienti().tutti(), [])
    items = _subject_items(soggetti_repo, soggetti, clienti)
    return {
        "source": "repository_reali",
        "generated_at": _iso_now(),
        "contracts": {"mock_fallback": False, "read_only": True},
        "summary": _summary(items),
        "items": items,
        "facets": _facets(items),
    }
