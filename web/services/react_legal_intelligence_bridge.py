"""Dati consultabili per le pagine di ricerca legale."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.parse import urlparse

try:
    from lex.research.privacy_safe_query_rewriter import rewrite_query_for_legal_research as _rewrite_query_for_legal_research
    from lex.research.public_legal_research_gateway import run_public_legal_research as _run_public_legal_research
except Exception:  # pragma: no cover - la UI deve degradare senza bloccare la shell
    _rewrite_query_for_legal_research = None
    _run_public_legal_research = None


_PST_MEDIAZIONE_RECOVERY_URL = (
    "https://pst.giustizia.it/PST/page/it/"
    "ripristinati_registro_organismi_di_mediazione_elenco_enti_per_la_mediazione_"
    "e_elenco_formatori_per_la_mediazione?contentId=NWS4865&modelId=4"
)
_PST_MEDIAZIONE_RECOVERY_TITLE = (
    "Ripristinati Registro Organismi di Mediazione, Elenco Enti per la Mediazione "
    "e Elenco Formatori per la Mediazione"
)
_MEDIAZIONE_OFFICIAL_REGISTRY_RECORDS: tuple[dict[str, str], ...] = (
    {
        "id": "mediazione-registro-organismi",
        "title": "Registro Organismi di Mediazione",
        "subtitle": "Consultazione ministeriale degli organismi abilitati alla mediazione civile e commerciale.",
        "sourceHref": "https://mediazione.giustizia.it/ROM/ALBOORGANISMIMEDIAZIONE.ASPX",
        "branch": "Organismi di mediazione",
    },
    {
        "id": "mediazione-elenco-enti",
        "title": "Elenco Enti per la Mediazione",
        "subtitle": "Consultazione ministeriale degli enti accreditati per la formazione in materia di mediazione.",
        "sourceHref": "https://mediazione.giustizia.it/ROM/AlboEntiFormazione.aspx",
        "branch": "Enti per la mediazione",
    },
    {
        "id": "mediazione-elenco-formatori",
        "title": "Elenco Formatori per la Mediazione",
        "subtitle": "Consultazione ministeriale dei formatori collegati agli enti accreditati per la mediazione.",
        "sourceHref": "https://mediazione.giustizia.it/ROM/AlboFormatori.aspx",
        "branch": "Formatori per la mediazione",
    },
)


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _short(value: Any, limit: int = 220) -> str:
    text = _text(value)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def _value(value: Any, key: str, fallback: Any = "") -> Any:
    if isinstance(value, Mapping):
        return value.get(key, fallback)
    return getattr(value, key, fallback)


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


def _source_label_from_url(url: str) -> str:
    host = urlparse(url or "").netloc.lower()
    if "pst.giustizia.it" in host:
        return "Portale Servizi Telematici"
    if "giustizia.it" in host:
        return "Ministero della Giustizia"
    if "normattiva.it" in host:
        return "Normattiva"
    if "gazzettaufficiale.it" in host:
        return "Gazzetta Ufficiale"
    if "cortedicassazione.it" in host:
        return "Corte di Cassazione"
    if "cortecostituzionale.it" in host:
        return "Corte costituzionale"
    if "agenziaentrate.gov.it" in host:
        return "Agenzia delle Entrate"
    return host or "Fonte"


def _is_official_href(url: str) -> bool:
    host = urlparse(url or "").netloc.lower()
    return any(
        domain in host
        for domain in (
            "giustizia.it",
            "normattiva.it",
            "gazzettaufficiale.it",
            "cortedicassazione.it",
            "cortecostituzionale.it",
            "giustizia-amministrativa.it",
            "agenziaentrate.gov.it",
            "eur-lex.europa.eu",
        )
    )


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


def _search_query(query: Mapping[str, Any] | None) -> str:
    query = query or {}
    for key in ("q", "query", "search", "cerca", "testo"):
        value = query.get(key)
        if isinstance(value, (list, tuple)):
            value = value[0] if value else ""
        text = _text(value)
        if text:
            return _short(text, 240)
    return ""


def _matches_query(record: Mapping[str, Any], search_query: str) -> bool:
    query_text = _text(search_query).lower()
    if not query_text:
        return True
    haystack = " ".join(
        _text(record.get(key)).lower()
        for key in (
            "title",
            "subtitle",
            "sourceLabel",
            "sourceKind",
            "area",
            "branch",
            "territory",
            "registryNumber",
            "date",
        )
    )
    tokens = [token for token in query_text.replace("/", " ").replace("-", " ").split() if len(token) >= 3]
    if not tokens:
        return query_text in haystack
    return all(token in haystack for token in tokens[:8]) or any(token in haystack for token in tokens[:3])


def _dedupe_records(records: list[dict[str, Any]], *, limit: int | None = None) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for record in records:
        key = _text(record.get("sourceHref")) or f"{_text(record.get('kind'))}:{_text(record.get('id'))}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(record)
        if limit is not None and len(deduped) >= limit:
            break
    return deduped


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
        warnings.append(_warning("snapshot_non_disponibile", "Riepilogo ricerca legale non disponibile."))
        return {}


def _pipeline_snapshot(pipeline: Any, warnings: list[dict[str, str]]) -> dict[str, Any]:
    try:
        return _dict(pipeline.dashboard_snapshot())
    except Exception as exc:
        warnings.append(_warning("pipeline_non_disponibile", "Archivio aggiornamenti non disponibile."))
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
        "legacyHref": f"/ricerca-legale/news?scheda={slug}" if slug else "/ricerca-legale/news",
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
        "legacyHref": f"/ricerca-legale/mediazione?organismo={registration}" if registration else "/ricerca-legale/mediazione",
        "evidenceType": "fonte",
    }


def _pst_mediazione_recovery_news_record() -> dict[str, Any]:
    return {
        "id": "pst-nws4865-ripristino-mediazione",
        "kind": "news",
        "title": _PST_MEDIAZIONE_RECOVERY_TITLE,
        "subtitle": (
            "Il Portale dei Servizi Telematici comunica che dal 22/04/2026 "
            "sono stati ripristinati Registro Organismi di Mediazione, Elenco "
            "Enti per la Mediazione ed Elenco Formatori per la Mediazione."
        ),
        "sourceLabel": "Portale Servizi Telematici",
        "sourceKind": "fonte ufficiale",
        "sourceHref": _PST_MEDIAZIONE_RECOVERY_URL,
        "date": "2026-05-11",
        "area": "Mediazione",
        "branch": "Ministero della Giustizia",
        "approvalLabel": "pubblicata",
        "approvalTone": "success",
        "registryNumber": "NWS4865",
        "legacyHref": "/ricerca-legale/news?scheda=pst-nws4865-ripristino-mediazione",
        "evidenceType": "fonte ufficiale",
    }


def _mediazione_official_registry_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for item in _MEDIAZIONE_OFFICIAL_REGISTRY_RECORDS:
        records.append(
            {
                "id": item["id"],
                "kind": "mediazione",
                "title": item["title"],
                "subtitle": item["subtitle"],
                "sourceLabel": "Ministero della Giustizia",
                "sourceKind": "fonte ufficiale",
                "sourceHref": item["sourceHref"],
                "date": "22/04/2026",
                "area": "Mediazione civile e commerciale",
                "branch": item["branch"],
                "approvalLabel": "ripristinato",
                "approvalTone": "success",
                "stateLabel": "consultabile",
                "stateTone": "success",
                "territory": "Italia",
                "registryNumber": "",
                "legacyHref": f"/ricerca-legale/mediazione?scheda={item['id']}",
                "evidenceType": "accesso ufficiale",
            }
        )
    return records


def _with_pst_recovery_news(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pst_record = _pst_mediazione_recovery_news_record()
    for record in records:
        if _text(record.get("sourceHref")) == _PST_MEDIAZIONE_RECOVERY_URL:
            return records
        if _text(record.get("id")) == pst_record["id"]:
            return records
    return [pst_record, *records]


def _search_type_label(value: Any) -> str:
    text = _text(value).lower().replace("_", " ")
    if text in {"normativa", "normative"}:
        return "normativa"
    if text in {"giurisprudenza", "jurisprudence"}:
        return "giurisprudenza"
    if text in {"prassi", "practice"}:
        return "prassi"
    if text in {"news", "notizia", "aggiornamento"}:
        return "news"
    if text in {"web ufficiale", "web_ufficiale", "official web"}:
        return "fonte ufficiale"
    return text or "fonte"


def _record_follow_up_query(record: Mapping[str, Any]) -> str:
    parts = [
        _text(record.get("title")),
        _text(record.get("area")),
        _text(record.get("branch")),
        _text(record.get("sourceLabel")),
    ]
    return _short(" ".join(part for part in parts if part), 180)


def _record_practical_use(record: Mapping[str, Any]) -> str:
    kind = _text(record.get("kind")).lower()
    title = _text(record.get("title")).lower()
    area = _text(record.get("area") or record.get("branch"))
    if "mediazione" in kind or "mediazione" in title:
        return "Usa questa scheda per verificare soggetti e requisiti collegati alla mediazione prima di scegliere organismo, ente o formatore."
    if "news" in kind:
        return "Usa l'aggiornamento per capire se il fascicolo richiede una verifica normativa, giurisprudenziale o organizzativa."
    if "giurisprudenza" in kind:
        return "Usa l'estratto per individuare autorità, data e materia prima del confronto con l'archivio giurisprudenza."
    if "normativa" in kind:
        return "Usa la fonte per controllare testo vigente, data di pubblicazione e collegamenti normativi prima dell'atto o del parere."
    if "prassi" in kind:
        return "Usa il riferimento per valutare l'indirizzo amministrativo e confrontarlo con il caso concreto."
    if area:
        return f"Usa la scheda per valutare pertinenza, fonte e data rispetto all'area {area}."
    return "Usa la scheda per valutare pertinenza, fonte e data prima di inserirla nel lavoro di studio."


def _record_reliability_note(record: Mapping[str, Any]) -> str:
    source_kind = _text(record.get("sourceKind")).lower()
    source_href = _text(record.get("sourceHref"))
    if "ufficiale" in source_kind or _is_official_href(source_href):
        return "Fonte ufficiale o istituzionale: il testo originale resta disponibile per il controllo finale prima di atti, pareri o depositi."
    if "verificare" in source_kind:
        return "Fonte da controllare: usa il contesto come orientamento e verifica il testo originale prima dell'uso professionale."
    if source_kind:
        return "Fonte censita nello studio: conserva il contesto utile e richiede controllo professionale prima dell'uso."
    return "Informazione disponibile nello studio: verifica la fonte prima di usarla in un atto o in un parere."


def _record_context_items(record: Mapping[str, Any], excerpt: str) -> list[str]:
    items: list[str] = []
    if excerpt:
        items.append(f"Contenuto: {excerpt}")
    scope = " / ".join(
        part
        for part in (
            _text(record.get("area")),
            _text(record.get("branch")),
            _text(record.get("territory")),
        )
        if part
    )
    if scope:
        items.append(f"Ambito: {scope}")
    if _text(record.get("date")):
        items.append(f"Aggiornamento: {_text(record.get('date'))}")
    if _text(record.get("registryNumber")):
        items.append(f"Registro: {_text(record.get('registryNumber'))}")
    if _text(record.get("sourceLabel")):
        items.append(f"Provenienza: {_text(record.get('sourceLabel'))}")
    return items[:5]


def _enrich_record_context(record: Mapping[str, Any]) -> dict[str, Any]:
    enriched = dict(record)
    excerpt = _short(
        enriched.get("sourceExcerpt")
        or enriched.get("subtitle")
        or enriched.get("summary")
        or enriched.get("title"),
        560,
    )
    enriched["sourceExcerpt"] = excerpt
    enriched["sourceContext"] = _record_context_items(enriched, excerpt)
    enriched["practicalUse"] = _record_practical_use(enriched)
    enriched["reliabilityNote"] = _record_reliability_note(enriched)
    enriched["followUpQuery"] = _record_follow_up_query(enriched)
    return enriched


def _safe_search_record(row: Mapping[str, Any], index: int) -> dict[str, Any]:
    source_href = _safe_href(row.get("official_url") or row.get("source_url") or row.get("url"))
    source_label = _text(row.get("authority") or row.get("source_name") or row.get("source_code")) or _source_label_from_url(source_href)
    verified = bool(row.get("verified_reference") or row.get("is_official") or _is_official_href(source_href))
    kind = _search_type_label(row.get("type") or row.get("entity_type") or row.get("category"))
    title = _text(row.get("title") or row.get("headline") or row.get("name")) or "Fonte ricerca legale"
    excerpt = _short(row.get("excerpt") or row.get("content") or row.get("summary") or row.get("short_summary"), 560)
    matter = _text(row.get("matter_name") or row.get("matter_slug") or row.get("category"))
    return {
        "id": _text(row.get("id")) or f"ricerca_{index}",
        "kind": kind,
        "title": title,
        "subtitle": excerpt,
        "sourceExcerpt": excerpt,
        "sourceLabel": source_label,
        "sourceKind": "fonte ufficiale" if verified else "fonte da verificare",
        "sourceHref": source_href,
        "date": _text(row.get("published_at") or row.get("publication_date") or row.get("date") or row.get("created_at")),
        "area": matter,
        "branch": kind,
        "approvalLabel": "verificata" if verified else "da verificare",
        "approvalTone": "success" if verified else "warning",
        "legacyHref": "/ricerca-legale",
        "evidenceType": "estratto fonte" if excerpt else "riferimento fonte",
    }


def _safe_public_source_record(source: Any, index: int) -> dict[str, Any]:
    source_href = _safe_href(_value(source, "url"))
    source_name = _text(_value(source, "source_name")) or _source_label_from_url(source_href)
    official = bool(_value(source, "official") or _is_official_href(source_href))
    excerpt = _short(_value(source, "excerpt"), 560)
    kind = _search_type_label(_value(source, "source_type"))
    return {
        "id": _text(_value(source, "id")) or f"fonte_ufficiale_{index}",
        "kind": kind,
        "title": _text(_value(source, "title")) or "Fonte ufficiale",
        "subtitle": excerpt,
        "sourceExcerpt": excerpt,
        "sourceLabel": source_name,
        "sourceKind": "fonte ufficiale" if official else "fonte pubblica",
        "sourceHref": source_href,
        "date": _text(_value(source, "date")),
        "area": "Ricerca legale",
        "branch": source_name,
        "approvalLabel": "verificata" if official else "da verificare",
        "approvalTone": "success" if official else "warning",
        "legacyHref": "/ricerca-legale",
        "evidenceType": "estratto fonte" if excerpt else "riferimento fonte",
    }


def _search_repository_records(pipeline: Any, warnings: list[dict[str, str]], search_query: str) -> list[dict[str, Any]]:
    if not search_query:
        return []
    try:
        rows = list(pipeline.repository.search_lex_sources(search_query, limit=12))
    except Exception:
        warnings.append(_warning("ricerca_archivio_non_disponibile", "Archivio giuridico non disponibile per questa ricerca."))
        return []
    return [_safe_search_record(row, index) for index, row in enumerate(rows, start=1) if isinstance(row, Mapping)]


def _needs_public_fallback(records: list[dict[str, Any]], search_query: str) -> bool:
    if not search_query:
        return False
    official_context = [
        record
        for record in records
        if "ufficiale" in _text(record.get("sourceKind")).lower()
        and len(_text(record.get("subtitle"))) >= 80
    ]
    return len(official_context) < 2


def _public_search_records(search_query: str, warnings: list[dict[str, str]]) -> tuple[list[dict[str, Any]], bool]:
    if not search_query or _rewrite_query_for_legal_research is None or _run_public_legal_research is None:
        if search_query:
            warnings.append(_warning("ricerca_ufficiale_non_disponibile", "Ricerca su fonti ufficiali non disponibile in questo momento."))
        return [], False
    try:
        rewritten = _rewrite_query_for_legal_research(search_query)
        rewritten.can_use_ldr = False
        rewritten.local_deep_research_query = ""
        result = _run_public_legal_research(rewritten, source_mode="balanced", max_results=8)
    except Exception:
        warnings.append(_warning("ricerca_ufficiale_non_completata", "Ricerca su fonti ufficiali non completata. Riprova tra poco o apri la fonte indicata."))
        return [], True

    for message in list(getattr(result, "warnings", []) or [])[:2]:
        cleaned = _short(str(message).split(":")[0], 160)
        if cleaned:
            warnings.append(_warning("ricerca_ufficiale_avviso", cleaned))

    records = [
        _safe_public_source_record(source, index)
        for index, source in enumerate(list(getattr(result, "sources", []) or []), start=1)
    ]
    return records, True


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
        "fonti",
        [
            _item("totale", "Organismi", registry.get("total_rows", 0), _text(registry.get("data_origin_label") or "archivio interno"), "primary"),
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
            "writes": "none",
            "route_owner": "react_shell",
            "external_fetch": False,
            "ai_generation": False,
            "canonical_source": "backend_storico",
            "legacy_contract": legacy_contract,
        },
        "metrics": [],
        "sections": [],
        "records": [],
        "actions": [
            _action("dashboard", "Ricerca legale", "/ricerca-legale", "primary"),
            _action("news", "News legali", "/ricerca-legale/news", "neutral"),
            _action("mediazione", "Registro mediazione", "/ricerca-legale/mediazione", "neutral"),
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
    warnings: list[dict[str, str]] = []
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
    news_records = _with_pst_recovery_news(
        [_safe_news_record(row, index) for index, row in enumerate(news_rows, start=1) if isinstance(row, dict)]
    )
    mediazione_records = [
        _safe_mediazione_record(row, index)
        for index, row in enumerate(_list(mediazione.get("rows")), start=1)
        if isinstance(row, dict)
    ]
    mediazione_official_records = _mediazione_official_registry_records()
    matters = _matters(pipeline, warnings)
    source_items = _source_items(snapshot, update_snapshot)
    search_query = _search_query(query)
    search_records: list[dict[str, Any]] = []
    official_search_attempted = False

    if page == "news":
        records = news_records
        legacy_contract = "artifacts/react-migration/legacy-contracts/legal-intelligence__news.json"
    elif page == "mediazione":
        records = _dedupe_records(mediazione_official_records + mediazione_records)
        legacy_contract = "artifacts/react-migration/legacy-contracts/legal-intelligence__mediazione.json"
    elif page == "ricerca-legale":
        local_matches = [
            record
            for record in news_records + mediazione_official_records + mediazione_records
            if _matches_query(record, search_query)
        ]
        search_records = _search_repository_records(pipeline, warnings, search_query)
        combined_search = _dedupe_records(search_records + local_matches)
        if _needs_public_fallback(combined_search, search_query):
            public_records, official_search_attempted = _public_search_records(search_query, warnings)
            combined_search = _dedupe_records(combined_search + public_records, limit=24)
        records = combined_search if search_query else _dedupe_records(news_records + mediazione_official_records + mediazione_records)
        if search_query and not records:
            warnings.append(
                _warning(
                    "nessun_risultato_ricerca",
                    "Nessuna fonte trovata con questa ricerca. Prova con parole piu' specifiche o apri gli archivi collegati.",
                )
            )
        legacy_contract = "artifacts/react-migration/legacy-contracts/ricerca-legale.json"
    else:
        records = news_records[:8] + mediazione_official_records[:3] + mediazione_records[:5]
        legacy_contract = "artifacts/react-migration/legacy-contracts/legal-intelligence.json"

    records = [_enrich_record_context(record) for record in records]

    search_section = _section(
        "ricerca",
        "Ricerca fonti",
        "informazioni",
        [
            _item("query", "Termini cercati", search_query or "nessun termine", "Archivio e fonti collegate", "primary" if search_query else "neutral"),
            _item("risultati", "Risultati", len(records), "Schede disponibili", "success" if records else "neutral"),
            _item("archivio", "Archivio studio", len(search_records), "Aggiornamenti giuridici indicizzati", "info" if search_records else "neutral"),
            _item("fonti_ufficiali", "Fonti ufficiali", len([record for record in records if "ufficiale" in _text(record.get("sourceKind")).lower()]), "Con estratto o riferimento consultabile", "success"),
        ],
        "Inserisci una ricerca per consultare archivio e fonti ufficiali.",
    )

    return {
        "source": "repository_reali",
        "generated_at": _iso_now(),
        "contracts": {
            "mock_fallback": False,
            "writes": "none",
            "route_owner": "react_shell",
            "external_fetch": official_search_attempted,
            "ai_generation": False,
            "canonical_source": "backend_storico",
            "legacy_contract": legacy_contract,
        },
        "metrics": [
            _metric("fonti_monitorate", "Fonti monitorate", int(headline.get("fonti_monitorate") or update_headline.get("sources") or 0), "Archivio e monitor governato", "primary"),
            _metric("news_pubblicate", "News pubblicate", int(update_headline.get("published_news") or len(news_records)), "Disponibili nello studio", "info"),
            _metric("review", "In revisione", int(update_headline.get("review_pending") or headline.get("tabelle_da_validare") or 0), "Percorso governato", "warning"),
            _metric("mediazione", "Organismi mediazione", int(mediazione.get("total_rows") or 0), "Registro consultabile", "success" if mediazione.get("total_rows") else "neutral"),
            _metric("fascicoli", "Fascicoli nel monitor", int(headline.get("fascicoli") or 0), "Informazioni studio", "neutral"),
        ],
        "sections": [
            *([search_section] if page == "ricerca-legale" else []),
            _section("fonti", "Stato fonti", "fonti", source_items, "Nessuna fonte disponibile."),
            _section(
                "news",
                "News legali",
                "informazioni",
                [
                    _item(record["id"], record["title"], record["date"], record["sourceLabel"], record["approvalTone"])
                    for record in news_records[:8]
                ],
                "Nessuna news pubblicata.",
            ),
            _mediazione_section({"mediazione_registry": mediazione}),
            _section(
                "materie",
                "Materie",
                "informazioni",
                [
                    _item(_text(row.get("slug") or row.get("name")), _text(row.get("name")), _text(row.get("level") or ""), _text(row.get("parent_slug")), "neutral")
                    for row in matters
                    if isinstance(row, dict)
                ],
                "Nessuna materia disponibile.",
            ),
            _section(
                "distinzione",
                "Fonte, scheda e valutazione",
                "controllo",
                [
                    _item("fonte", "Fonte", "ufficiale o interna", "Etichetta visibile su ogni riga", "success"),
                    _item("scheda", "Scheda", "data, area, stato", "Informazioni disponibili", "info"),
                    _item("revisione", "Revisione", "se presente", "Controllo umano consigliato", "warning"),
                ],
                "Nessuna distinzione disponibile.",
            ),
        ],
        "records": records,
        "actions": [
            _action("dashboard", "Ricerca legale", "/ricerca-legale", "primary"),
            _action("news", "News legali", "/ricerca-legale/news", "primary"),
            _action("mediazione", "Registro mediazione", "/ricerca-legale/mediazione", "neutral"),
            _action("giurisprudenza", "Archivio giurisprudenza", "/giurisprudenza", "neutral"),
        ],
        "forms": [],
        "warnings": warnings,
        "filters": dict(query or {}),
    }


def build_react_legal_intelligence_error_payload(
    message: str = "Ricerca legale non disponibile.",
    *,
    legacy_contract: str = "artifacts/react-migration/legacy-contracts/legal-intelligence.json",
) -> dict[str, Any]:
    return _empty_payload("errore_controllato", message, legacy_contract)
