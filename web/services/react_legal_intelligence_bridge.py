"""Bridge read-only per le superfici React Legal Intelligence."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Mapping


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _short(value: Any, limit: int = 220) -> str:
    text = _text(value)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _safe_href(value: Any, fallback: str = "") -> str:
    href = _text(value)
    if href.startswith("/") and href != "#":
        return href
    if href.startswith("https://") or href.startswith("http://"):
        return href
    return fallback


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


def _tone(value: Any) -> str:
    text = _text(value).lower().replace("_", " ")
    if not text:
        return "neutral"
    if text in {"published", "pubblicata", "approved", "approvata", "sincronizzata", "aggiornata", "ok"}:
        return "success"
    if text in {"pending", "pending review", "in revisione", "verifica richiesta", "da verificare"}:
        return "warning"
    if text in {"error", "errore", "fallita", "non aggiornata"}:
        return "danger"
    return "info"


def _safe_call(loader: Callable[[], Any], warnings: list[dict[str, str]], code: str, label: str) -> list[Any]:
    try:
        value = loader()
        return list(value or [])
    except Exception as exc:
        warnings.append(_warning(code, f"{label} non disponibili: {type(exc).__name__}."))
        return []


def _dashboard_snapshot(
    manager: Any,
    warnings: list[dict[str, str]],
    *,
    get_fascicoli: Callable[[], Any],
    get_clienti: Callable[[], Any],
    get_agenda: Callable[[], Any],
    get_scadenziario: Callable[[], Any],
) -> dict[str, Any]:
    try:
        return manager.build_dashboard_snapshot(
            fascicoli=_safe_call(lambda: get_fascicoli().tutti(archiviati=True), warnings, "fascicoli_non_disponibili", "Fascicoli"),
            clienti=_safe_call(lambda: get_clienti().tutti(), warnings, "clienti_non_disponibili", "Clienti"),
            appuntamenti=_safe_call(lambda: get_agenda().tutti(), warnings, "agenda_non_disponibile", "Agenda"),
            scadenze=_safe_call(lambda: get_scadenziario().tutte(), warnings, "scadenze_non_disponibili", "Scadenze"),
            portali=[],
        )
    except Exception as exc:
        warnings.append(_warning("snapshot_non_disponibile", f"Snapshot Legal Intelligence non disponibile: {type(exc).__name__}."))
        return {}


def _pipeline_snapshot(pipeline: Any, warnings: list[dict[str, str]]) -> dict[str, Any]:
    try:
        return _dict(pipeline.dashboard_snapshot())
    except Exception as exc:
        warnings.append(_warning("pipeline_non_disponibile", f"Repository aggiornamenti non disponibile: {type(exc).__name__}."))
        return {}


def _news_rows(pipeline: Any, warnings: list[dict[str, str]], query: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    query = query or {}
    try:
        return list(
            pipeline.repository.list_news(
                matter_slug=_text(query.get("materia")),
                news_type=_text(query.get("tipo")),
                limit=80,
            )
        )
    except Exception as exc:
        warnings.append(_warning("news_non_disponibili", f"News giuridiche non disponibili: {type(exc).__name__}."))
        return []


def _matters(pipeline: Any, warnings: list[dict[str, str]]) -> list[dict[str, Any]]:
    try:
        return list(pipeline.repository.list_matters())
    except Exception as exc:
        warnings.append(_warning("materie_non_disponibili", f"Materie non disponibili: {type(exc).__name__}."))
        return []


def _mediazione_snapshot(manager: Any, warnings: list[dict[str, str]], query: Mapping[str, Any] | None) -> dict[str, Any]:
    query = query or {}
    try:
        return _dict(
            manager.mediazione_registry_snapshot(
                q=_text(query.get("q")),
                city=_text(query.get("city")),
                registry_number=_text(query.get("registry_number")),
                organismo_type=_text(query.get("organismo_type")),
            )
        )
    except Exception as exc:
        warnings.append(_warning("mediazione_non_disponibile", f"Registro mediazione non disponibile: {type(exc).__name__}."))
        return {}


def _safe_news_record(row: Mapping[str, Any], index: int) -> dict[str, Any]:
    news_id = _text(row.get("id") or row.get("slug")) or f"news_{index}"
    slug = _text(row.get("slug"))
    status = _text(row.get("publication_status") or row.get("review_status") or row.get("status"))
    source_label = _text(row.get("source_name") or row.get("source_code") or row.get("authority") or "Fonte interna")
    return {
        "id": news_id,
        "kind": "news",
        "title": _text(row.get("title") or row.get("headline")) or "News",
        "subtitle": _short(row.get("short_summary") or row.get("lead") or row.get("description"), 220),
        "sourceLabel": source_label,
        "sourceKind": "fonte ufficiale" if row.get("is_official") else "contenuto interno",
        "sourceHref": _safe_href(row.get("source_url") or row.get("official_url")),
        "date": _text(row.get("published_at") or row.get("created_at") or row.get("updated_at")),
        "area": _text(row.get("matter_name") or row.get("matter_slug")),
        "branch": _text(row.get("submatter_name") or row.get("submatter_slug")),
        "approvalLabel": status or "pubblicata",
        "approvalTone": _tone(status or "published"),
        "legacyHref": f"/legal-intelligence/news/{slug}?_legacy=1" if slug else "/legal-intelligence/news?_legacy=1",
        "evidenceType": "fonte",
    }


def _safe_mediazione_record(row: Mapping[str, Any], index: int) -> dict[str, Any]:
    registration = _text(row.get("registration_number") or row.get("numero_iscrizione") or index)
    city = _text(row.get("city") or row.get("comune"))
    province = _text(row.get("province") or row.get("provincia"))
    return {
        "id": registration or f"organismo_{index}",
        "kind": "mediazione",
        "title": _text(row.get("name") or row.get("denominazione")) or "Organismo di mediazione",
        "subtitle": _short(row.get("type") or row.get("tipologia") or row.get("address"), 180),
        "sourceLabel": "Registro mediazione",
        "sourceKind": "fonte ufficiale" if row.get("official") or row.get("source") == "ministero" else "contenuto interno",
        "date": _text(row.get("registration_date") or row.get("updated_at")),
        "area": city,
        "branch": province,
        "territory": " - ".join(part for part in (city, province) if part),
        "stateLabel": _text(row.get("status") or row.get("state") or "presente"),
        "stateTone": _tone(row.get("status") or row.get("state") or "ok"),
        "registryNumber": registration,
        "legacyHref": "/legal-intelligence/mediazione?_legacy=1",
        "evidenceType": "fonte",
    }


def _source_items(snapshot: Mapping[str, Any], update_snapshot: Mapping[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for index, row in enumerate(_list(snapshot.get("source_rows")), start=1):
        if not isinstance(row, dict):
            continue
        label = _text(row.get("title") or row.get("name") or row.get("source_id") or row.get("id"))
        state = _text(row.get("freshness") or row.get("sync_status") or row.get("status"))
        items.append(_item(f"fonte_{index}", label or "Fonte", state or "censita", _text(row.get("last_checked_at") or row.get("last_synced_at")), _tone(state)))
    for index, row in enumerate(_list(update_snapshot.get("sources")), start=1):
        if not isinstance(row, dict):
            continue
        label = _text(row.get("name") or row.get("code"))
        state = "ufficiale" if row.get("is_official") else _text(row.get("trust_class") or "interna")
        items.append(_item(f"update_source_{index}", label or "Fonte aggiornamenti", state, _text(row.get("category")), "success" if row.get("is_official") else "neutral"))
    return items


def _mediazione_section(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    registry = _dict(snapshot.get("mediazione_registry"))
    table = _dict(registry.get("table"))
    return _section(
        "mediazione",
        "Registro mediazione",
        "source-cards",
        [
            _item("totale", "Organismi", registry.get("total_rows", 0), _text(registry.get("data_origin_label") or "repository interno"), "primary"),
            _item("filtrati", "Risultati filtrati", registry.get("filtered_rows", 0), _text(table.get("sync_status") or registry.get("data_origin")), _tone(table.get("sync_status"))),
            _item("aggiornamento", "Ultimo aggiornamento", _text(table.get("last_synced_at") or registry.get("last_successful_sync_at") or "n/d"), _text(registry.get("technical_notice")), "neutral"),
        ],
        "Registro mediazione non disponibile.",
    )


def _empty_payload(source: str, message: str, legacy_contract: str) -> dict[str, Any]:
    return {
        "source": source,
        "generated_at": _iso_now(),
        "contracts": {
            "mock_fallback": False,
            "writes": "legacy_routes",
            "route_owner": "react_shell",
            "external_fetch": False,
            "ai_generation": False,
            "canonical_source": "backend_legacy",
            "legacy_contract": legacy_contract,
        },
        "metrics": [],
        "sections": [],
        "records": [],
        "actions": [
            _action("dashboard", "Legal Intelligence", "/legal-intelligence", "primary"),
            _action("news", "News legali", "/legal-intelligence/news", "neutral"),
            _action("mediazione", "Registro mediazione", "/legal-intelligence/mediazione", "neutral"),
        ],
        "forms": [],
        "warnings": [_warning("legal_intelligence_non_disponibile", message)],
    }


def build_react_legal_intelligence_payload(
    *,
    get_legal_intelligence: Callable[[], Any],
    get_legal_update_pipeline: Callable[[], Any],
    get_fascicoli: Callable[[], Any],
    get_clienti: Callable[[], Any],
    get_agenda: Callable[[], Any],
    get_scadenziario: Callable[[], Any],
    page: str = "dashboard",
    query: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    warnings: list[dict[str, str]] = [
        _warning("workflow_legacy", "Sincronizzazione fonti, approvazione contenuti, indice assistito e import restano nelle route legacy."),
        _warning("metadati_sicuri", "La shell React espone solo fonte, stato, date, aree e metadati gia presenti nel backend."),
    ]
    manager = get_legal_intelligence()
    pipeline = get_legal_update_pipeline()
    snapshot = _dashboard_snapshot(
        manager,
        warnings,
        get_fascicoli=get_fascicoli,
        get_clienti=get_clienti,
        get_agenda=get_agenda,
        get_scadenziario=get_scadenziario,
    )
    update_snapshot = _pipeline_snapshot(pipeline, warnings)
    headline = _dict(snapshot.get("headline"))
    update_headline = _dict(update_snapshot.get("headline"))
    mediazione = _mediazione_snapshot(manager, warnings, query)
    news_rows = _news_rows(pipeline, warnings, query)
    news_records = [_safe_news_record(row, index) for index, row in enumerate(news_rows, start=1) if isinstance(row, dict)]
    mediazione_records = [
        _safe_mediazione_record(row, index)
        for index, row in enumerate(_list(mediazione.get("rows")), start=1)
        if isinstance(row, dict)
    ]
    matters = _matters(pipeline, warnings)
    source_items = _source_items(snapshot, update_snapshot)

    if page == "news":
        records = news_records
        legacy_contract = "artifacts/react-migration/legacy-contracts/legal-intelligence__news.json"
    elif page == "mediazione":
        records = mediazione_records
        legacy_contract = "artifacts/react-migration/legacy-contracts/legal-intelligence__mediazione.json"
    elif page == "ricerca-legale":
        records = news_records + mediazione_records
        legacy_contract = "artifacts/react-migration/legacy-contracts/ricerca-legale.json"
    else:
        records = news_records[:8] + mediazione_records[:8]
        legacy_contract = "artifacts/react-migration/legacy-contracts/legal-intelligence.json"

    return {
        "source": "repository_reali",
        "generated_at": _iso_now(),
        "contracts": {
            "mock_fallback": False,
            "writes": "legacy_routes",
            "route_owner": "react_shell",
            "external_fetch": False,
            "ai_generation": False,
            "canonical_source": "backend_legacy",
            "legacy_contract": legacy_contract,
        },
        "metrics": [
            _metric("fonti_monitorate", "Fonti monitorate", int(headline.get("fonti_monitorate") or update_headline.get("sources") or 0), "Repository e monitor legacy", "primary"),
            _metric("news_pubblicate", "News pubblicate", int(update_headline.get("published_news") or len(news_records)), "Gia presenti nel backend", "info"),
            _metric("review", "In revisione", int(update_headline.get("review_pending") or headline.get("tabelle_da_validare") or 0), "Workflow legacy", "warning"),
            _metric("mediazione", "Organismi mediazione", int(mediazione.get("total_rows") or 0), "Registro consultabile", "success" if mediazione.get("total_rows") else "neutral"),
            _metric("fascicoli", "Fascicoli nel monitor", int(headline.get("fascicoli") or 0), "Metadati studio", "neutral"),
        ],
        "sections": [
            _section("fonti", "Stato fonti", "source-cards", source_items, "Nessuna fonte disponibile."),
            _section(
                "news",
                "News legali",
                "metadata",
                [
                    _item(record["id"], record["title"], record["date"], record["sourceLabel"], record["approvalTone"])
                    for record in news_records[:8]
                ],
                "Nessuna news pubblicata nel backend.",
            ),
            _mediazione_section({"mediazione_registry": mediazione}),
            _section(
                "materie",
                "Materie",
                "metadata",
                [
                    _item(_text(row.get("slug") or row.get("name")), _text(row.get("name")), _text(row.get("level") or ""), _text(row.get("parent_slug")), "neutral")
                    for row in matters
                    if isinstance(row, dict)
                ],
                "Nessuna materia disponibile.",
            ),
            _section(
                "distinzione",
                "Fonte, metadato e inferenza",
                "evidence",
                [
                    _item("fonte", "Fonte", "ufficiale o interna", "Etichetta visibile su ogni riga", "success"),
                    _item("metadato", "Metadato", "data, area, stato", "Letto dal backend legacy", "info"),
                    _item("inferenza", "Inferenza", "solo se gia esposta", "Nessuna generazione in React", "warning"),
                ],
                "Nessuna distinzione disponibile.",
            ),
        ],
        "records": records,
        "actions": [
            _action("dashboard", "Legal Intelligence", "/legal-intelligence", "primary"),
            _action("news", "News legali", "/legal-intelligence/news", "primary"),
            _action("mediazione", "Registro mediazione", "/legal-intelligence/mediazione", "neutral"),
            _action("giurisprudenza", "Archivio giurisprudenza", "/giurisprudenza", "neutral"),
        ],
        "forms": [],
        "warnings": warnings,
        "filters": dict(query or {}),
    }


def build_react_legal_intelligence_error_payload(
    message: str = "Legal Intelligence non disponibile.",
    *,
    legacy_contract: str = "artifacts/react-migration/legacy-contracts/legal-intelligence.json",
) -> dict[str, Any]:
    return _empty_payload("errore_controllato", message, legacy_contract)
