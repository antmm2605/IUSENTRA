"""Bridge read-only per la superficie React Giurisprudenza."""

from __future__ import annotations

from collections import Counter
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


def _tone_from_status(value: Any) -> str:
    status = _text(value).lower().replace("_", " ")
    if not status:
        return "neutral"
    if status in {"verificata", "verificato", "citabile", "sincronizzata", "pubblicata"}:
        return "success"
    if status in {"da verificare", "parziale", "parzialmente verificata", "in revisione"}:
        return "warning"
    if status in {"non citabile", "errore", "scaduta", "bloccata"}:
        return "danger"
    return "info"


def _source_state(row: Mapping[str, Any], last_status: str) -> tuple[str, str, str]:
    source_id = _text(row.get("id") or row.get("source_system") or row.get("nome"))
    raw = _text(last_status).lower()
    fallback_label = _text(row.get("fallback_label"))
    fallback_note = _text(row.get("fallback_note"))
    if raw == "ok":
        return "Aggiornata", "success", fallback_note
    if raw in {"vuoto", "mai_eseguito"}:
        return "Da verificare", "warning", fallback_note or "Fonte censita: il prossimo recupero controllera' nuovi provvedimenti."
    if raw == "errore" and fallback_label:
        return "Da verificare", "warning", f"Soluzione alternativa: {fallback_label}. {fallback_note}".strip()
    if raw == "errore":
        return "Da verificare", "warning", "L'agente deve rieseguire il controllo e cercare un canale ufficiale alternativo."
    if raw == "handoff_richiesto":
        return "Recupero assistito", "warning", "Serve accesso guidato al portale ufficiale o import di materiale legittimamente ottenuto."
    if raw == "da_verificare":
        return "Da verificare", "warning", fallback_note
    if source_id == "manuale_interno":
        return "Inserimento interno", "info", ""
    if _text(row.get("access_mode")) in {"materiale_cliente", "manuale"}:
        return "Import assistito", "warning", "Usare solo materiale fornito o autorizzato dallo studio."
    return last_status or "Fonte censita", _tone_from_status(last_status), fallback_note


def _count_section(sid: str, title: str, kind: str, values: list[str], empty: str) -> dict[str, Any]:
    counter = Counter(value for value in values if value)
    items = [
        _item(_text(key).lower().replace(" ", "_") or f"{sid}_{index}", key, count)
        for index, (key, count) in enumerate(counter.most_common(), start=1)
    ]
    return _section(sid, title, kind, items, empty)


def _safe_source(row: Mapping[str, Any]) -> dict[str, Any]:
    source_id = _text(row.get("id") or row.get("source_system") or row.get("nome"))
    last_run = row.get("last_run") if isinstance(row.get("last_run"), dict) else {}
    last_status = _text(last_run.get("status") or row.get("sync_status"))
    state_label, state_tone, resolution_note = _source_state(row, last_status)
    return {
        "id": source_id,
        "label": _text(row.get("nome") or row.get("name") or source_id) or "Fonte",
        "kind": _text(row.get("giurisdizione") or row.get("badge") or row.get("access_mode")),
        "coverage": _text(row.get("coverage")),
        "accessMode": _text(row.get("access_mode") or row.get("sync_mode")),
        "sourceHref": _safe_href(row.get("official_url") or row.get("search_url")),
        "legacyHref": "",
        "lastRunAt": _text(last_run.get("ended_at") or last_run.get("checked_at") or last_run.get("started_at")),
        "stateLabel": state_label,
        "stateTone": state_tone,
        "resolutionNote": resolution_note,
        "count": int(row.get("judgment_count") or 0),
        "evidenceType": "fonte",
    }


def _safe_links(links: Any) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for index, link in enumerate(_list(links), start=1):
        if not isinstance(link, dict):
            continue
        fascicolo_id = _text(link.get("fascicolo_id") or link.get("practice_id") or link.get("id"))
        label = _text(link.get("fascicolo_titolo") or link.get("titolo") or link.get("nome") or fascicolo_id)
        href = _safe_href(link.get("href") or (f"/fascicoli/{fascicolo_id}" if fascicolo_id else ""))
        if not label and not href:
            continue
        out.append({"id": fascicolo_id or f"collegamento_{index}", "label": label or "Fascicolo collegato", "href": href})
    return out


def _safe_record(row: Mapping[str, Any], sources: Mapping[str, dict[str, Any]], index: int) -> dict[str, Any]:
    record_id = _text(row.get("id")) or f"provvedimento_{index}"
    source_id = _text(row.get("source_system") or row.get("fonte") or "manuale_interno")
    source = sources.get(source_id, {})
    date_value = _text(row.get("data_deposito") or row.get("data_decisione") or row.get("published_at") or row.get("updated_at"))
    verification = _text(row.get("stato_verifica") or row.get("stato_citabilita") or row.get("verifica") or row.get("citabilita"))
    orientation = _text(row.get("orientamento"))
    title = _text(row.get("titolo")) or _text(row.get("tipo_provvedimento")) or "Provvedimento"
    return {
        "id": record_id,
        "title": title,
        "subtitle": _short(row.get("microtema") or row.get("materia") or row.get("rito") or row.get("esito"), 180),
        "sourceId": source_id,
        "sourceLabel": _text(source.get("label") or row.get("source_label") or source_id),
        "sourceKind": _text(source.get("kind") or row.get("giurisdizione")),
        "authority": _text(row.get("organo_giudicante") or row.get("ufficio")),
        "office": _text(row.get("ufficio") or row.get("sezione")),
        "date": date_value,
        "area": _text(row.get("area")),
        "branch": _text(row.get("branca")),
        "subbranch": _text(row.get("sottobranca")),
        "grade": _text(row.get("grado")),
        "jurisdiction": _text(row.get("giurisdizione")),
        "caseNumber": _text(row.get("numero_provvedimento") or row.get("numero_rg") or row.get("riferimento_causa")),
        "ecli": _text(row.get("ecli")),
        "orientation": orientation,
        "orientationKind": "inferenza" if orientation else "",
        "verificationLabel": verification,
        "verificationTone": _tone_from_status(verification),
        "citationLabel": _text(row.get("stato_citabilita") or row.get("citabilita")),
        "tags": [_text(item) for item in _list(row.get("parole_chiave") or row.get("tags")) if _text(item)][:12],
        "legacyHref": f"/giurisprudenza?scheda={record_id}",
        "practiceLinks": _safe_links(row.get("practice_links") or row.get("fascicoli_collegati")),
        "evidenceType": "informazione",
    }


def _empty_payload(source: str, message: str) -> dict[str, Any]:
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
            "legacy_contract": "artifacts/react-migration/legacy-contracts/giurisprudenza.json",
        },
        "metrics": [],
        "sections": [],
        "records": [],
        "actions": [
            _action("legal_intelligence", "Ricerca legale", "/ricerca-legale", "primary"),
        ],
        "forms": [],
        "warnings": [_warning("giurisprudenza_non_disponibile", message)],
    }


def build_react_giurisprudenza_payload(
    *,
    get_giurisprudenza: Callable[[], Any],
    query: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Costruisce i dati pagina usando solo informazioni gia presenti."""

    query = query or {}
    warnings: list[dict[str, str]] = []
    manager = get_giurisprudenza()
    sources = [_safe_source(row) for row in _list(manager.catalogo_fonti()) if isinstance(row, dict)]
    source_lookup = {source["id"]: source for source in sources if source.get("id")}
    filters = {
        "q": _text(query.get("q")),
        "source_system": _text(query.get("source_system")),
        "area": _text(query.get("area")),
        "branca": _text(query.get("branca")),
        "sottobranca": _text(query.get("sottobranca")),
        "grado": _text(query.get("grado")),
        "giurisdizione": _text(query.get("giurisdizione")),
        "orientamento": _text(query.get("orientamento")),
        "uso_nel_software": _text(query.get("uso_nel_software")),
    }
    raw_records = manager.cerca(**filters)
    records = [
        _safe_record(row, source_lookup, index)
        for index, row in enumerate(_list(raw_records), start=1)
        if isinstance(row, dict)
    ]
    stats = manager.statistiche()
    storage_stats = manager.storage_stats()
    catalog_filters = manager.filtri()
    run_log = [
        _item(
            f"run_{index}",
            _text(row.get("source_id") or row.get("source_system") or "Fonte"),
            _text(row.get("status") or row.get("ended_at") or row.get("checked_at")),
            _text(row.get("message") or row.get("warning")),
            _tone_from_status(row.get("status")),
        )
        for index, row in enumerate(_list(manager.recent_sync_runs()), start=1)
        if isinstance(row, dict)
    ]

    return {
        "source": "repository_reali",
        "generated_at": _iso_now(),
        "contracts": {
            "mock_fallback": False,
            "writes": "none",
            "route_owner": "react_shell",
            "external_fetch": False,
            "ai_generation": False,
            "canonical_source": "backend_storico",
            "legacy_contract": "artifacts/react-migration/legacy-contracts/giurisprudenza.json",
        },
        "metrics": [
            _metric("provvedimenti", "Provvedimenti", int(stats.get("totale_sentenze") or len(records)), "Archivio interno", "primary"),
            _metric("fonti", "Fonti censite", int(stats.get("fonti_attive") or len(sources)), "Archivio giurisprudenza", "info"),
            _metric("aree", "Aree coperte", int(stats.get("aree_coperte") or 0), "Classificazione disponibile", "neutral"),
            _metric("da_verificare", "Da verificare", int(stats.get("bozze_da_classificare") or 0), "Gestione governata", "warning"),
            _metric("collegamenti", "Fascicoli collegati", int(stats.get("fascicoli_collegati") or 0), "Informazioni collegate", "success" if stats.get("fascicoli_collegati") else "neutral"),
        ],
        "sections": [
            _section(
                "fonti",
                "Fonti disponibili",
                "source-cards",
                [
                    _item(source["id"], source["label"], source["count"], source.get("coverage") or source.get("stateLabel", ""), source.get("stateTone", "neutral"))
                    for source in sources
                ],
                "Nessuna fonte censita nell'archivio.",
            ),
            _count_section("aree", "Aree", "distribution", [record["area"] for record in records], "Nessuna area disponibile."),
            _count_section("gradi", "Gradi", "distribution", [record["grade"] for record in records], "Nessun grado disponibile."),
            _count_section("orientamenti", "Orientamenti", "analisi", [record["orientation"] for record in records], "Nessun orientamento presente nelle informazioni disponibili."),
            _section("sync_recenti", "Aggiornamenti registrati", "metadata", run_log, "Nessun aggiornamento registrato."),
            _section(
                "filtri",
                "Filtri disponibili",
                "metadata",
                [
                    _item("fonti", "Fonti", len(_list(catalog_filters.get("fonti"))), "Catalogo"),
                    _item("aree", "Aree", len(_list(catalog_filters.get("aree"))), "Tassonomia"),
                    _item("storage", "Versione archivio", storage_stats.get("storage_version", ""), "Matrice archivi"),
                ],
                "Nessun filtro disponibile.",
            ),
        ],
        "records": records,
        "actions": [
            _action("legal_intelligence", "Ricerca legale", "/ricerca-legale", "primary"),
            _action("ricerca_legale", "Ricerca legale", "/ricerca-legale", "neutral"),
        ],
        "forms": [],
        "warnings": warnings,
        "sources": sources,
        "filters": filters,
    }


def build_react_giurisprudenza_error_payload(message: str = "Archivio giurisprudenza non disponibile.") -> dict[str, Any]:
    return _empty_payload("errore_controllato", message)
