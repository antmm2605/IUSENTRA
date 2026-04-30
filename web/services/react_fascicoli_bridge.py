"""Bridge dati per le superfici React Fascicoli.

Il modulo normalizza repository, azioni e metadati del dominio Fascicoli:
lettura tramite API React, scritture demandate ai servizi Flask già auditati.
"""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Iterable

from pct.fascicoli import EsitoAttivita, StatoFascicolo, TipoAttivita, TipoDocumento, TipoFascicolo

MONTHS_SHORT = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"]


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe(label: str, func: Callable[[], Any], fallback: Any) -> Any:
    try:
        return func()
    except Exception:
        return fallback


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "")


def _text(value: Any, default: str = "") -> str:
    text = str(value if value is not None else default).strip()
    return text if text else default


def _short(value: Any, limit: int = 120) -> str:
    text = " ".join(_text(value).split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "..."


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    else:
        raw = _text(value)
        if not raw:
            return None
        parsed = None
        for sample in (raw.replace("Z", "+00:00"), raw[:19], raw[:10]):
            try:
                parsed = datetime.fromisoformat(sample)
                break
            except ValueError:
                continue
        if parsed is None:
            return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone().replace(tzinfo=None)
    return parsed


def _parse_date(value: Any) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    parsed = _parse_datetime(value)
    if parsed:
        return parsed.date()
    try:
        return date.fromisoformat(_text(value)[:10])
    except ValueError:
        return None


def _date_label(value: Any) -> str:
    parsed = _parse_date(value)
    if not parsed:
        return _text(value, "n.d.")
    today = date.today()
    if parsed == today:
        return "oggi"
    if parsed == today + timedelta(days=1):
        return "domani"
    if parsed == today - timedelta(days=1):
        return "ieri"
    if parsed.year == today.year:
        return f"{parsed.day} {MONTHS_SHORT[parsed.month - 1]}"
    return parsed.strftime("%d/%m/%Y")


def _time_label(value: Any) -> str:
    parsed = _parse_datetime(value)
    if not parsed:
        return ""
    return parsed.strftime("%H:%M")


def _euro(value: Any) -> str:
    try:
        number = float(value or 0.0)
    except (TypeError, ValueError):
        number = 0.0
    text = f"{number:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"EUR {text}"


def _bytes_label(value: Any) -> str:
    try:
        size = int(value or 0)
    except (TypeError, ValueError):
        size = 0
    if size <= 0:
        return ""
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{round(size / 1024)} KB"
    return f"{size / (1024 * 1024):.1f} MB".replace(".", ",")


def _status_tone(status: str) -> str:
    status = status.upper()
    if status == StatoFascicolo.IN_CORSO.value:
        return "success"
    if status == StatoFascicolo.DEFINITO.value:
        return "info"
    if status == StatoFascicolo.ARCHIVIATO.value:
        return "neutral"
    if status == StatoFascicolo.SOSPESO.value:
        return "orange"
    return "primary"


def _activity_tone(result: str) -> str:
    result = result.upper()
    if result == EsitoAttivita.FAVOREVOLE.value:
        return "success"
    if result == EsitoAttivita.PARZIALE.value:
        return "warning"
    if result == EsitoAttivita.SFAVOREVOLE.value:
        return "danger"
    if result == EsitoAttivita.RINVIATO.value:
        return "info"
    if result == EsitoAttivita.ANNULLATO.value:
        return "neutral"
    return "primary"


def _deadline_tone(scadenza: Any) -> str:
    priority = _enum_value(getattr(scadenza, "priorita", "")).upper()
    raw_date = _parse_date(getattr(scadenza, "data_scadenza", "") or getattr(scadenza, "data", ""))
    if raw_date and raw_date <= date.today():
        return "danger"
    if "CRITICA" in priority:
        return "danger"
    if "ALTA" in priority:
        return "warning"
    if "BASSA" in priority:
        return "success"
    return "primary"


def _status_for_filters(fascicolo: Any) -> str:
    stato = _enum_value(getattr(fascicolo, "stato", "")).upper()
    if stato == StatoFascicolo.DEFINITO.value and bool(getattr(fascicolo, "archivio_pronto", False)):
        return "da_archiviare"
    return stato.lower()


def _type_for_filters(fascicolo: Any) -> str:
    return _enum_value(getattr(fascicolo, "tipo", "ALTRO")).lower()


def _option(value: Any) -> dict[str, str]:
    raw = _enum_value(value)
    return {"value": raw, "label": raw.replace("_", " ").title()}


def _options() -> dict[str, list[dict[str, str]]]:
    return {
        "states": [_option(item) for item in StatoFascicolo],
        "documentTypes": [_option(item) for item in TipoDocumento],
        "activityTypes": [_option(item) for item in TipoAttivita],
        "activityResults": [_option(item) for item in EsitoAttivita],
    }


def _select_options(values: Iterable[Any]) -> list[dict[str, str]]:
    return [_option(value) for value in values]


def _rg(fascicolo: Any) -> str:
    return _text(getattr(fascicolo, "rg_completo", "")) or _text(getattr(fascicolo, "numero_rg", "")) or "n.d."


def _next_deadline(fascicolo: Any, scadenze_by_fasc: dict[str, list[Any]] | None = None) -> Any | None:
    prop = getattr(fascicolo, "prossima_scadenza", None)
    if prop:
        return prop
    if scadenze_by_fasc is None:
        return None
    deadlines = scadenze_by_fasc.get(_text(getattr(fascicolo, "id", "")), [])
    dated = [item for item in deadlines if _parse_date(getattr(item, "data_scadenza", "") or getattr(item, "data", ""))]
    dated.sort(key=lambda item: _parse_date(getattr(item, "data_scadenza", "") or getattr(item, "data", "")) or date.max)
    return dated[0] if dated else None


def _item(fascicolo: Any, *, scadenze_by_fasc: dict[str, list[Any]] | None = None, archived: bool | None = None) -> dict[str, Any]:
    fid = _text(getattr(fascicolo, "id", ""))
    stato = _enum_value(getattr(fascicolo, "stato", StatoFascicolo.APERTO.value))
    n_scadenza = _next_deadline(fascicolo, scadenze_by_fasc)
    n_date = _text(getattr(n_scadenza, "data_scadenza", "") or getattr(n_scadenza, "data", "")) if n_scadenza else ""
    docs = len(getattr(fascicolo, "documenti", []) or [])
    deposits = getattr(fascicolo, "depositi_pct", []) or []
    unread = sum(1 for dep in deposits if _enum_value(getattr(dep, "stato", "")).upper() in {"WARN_CONTROLLI", "ERRORE_CONTROLLI", "RIFIUTATO_CANCELLERIA", "ERRORE"})
    alerts = unread
    if getattr(fascicolo, "has_conflicts", False):
        alerts += 1
    if n_scadenza and _deadline_tone(n_scadenza) in {"danger", "warning"}:
        alerts += 1
    archive = getattr(fascicolo, "archivio", None)
    return {
        "id": fid,
        "ref": _rg(fascicolo) if _rg(fascicolo) != "n.d." else _text(getattr(fascicolo, "numero", ""), fid),
        "internalRef": _text(getattr(fascicolo, "numero", "")),
        "title": _short(getattr(fascicolo, "titolo", "") or getattr(fascicolo, "oggetto", "") or "Fascicolo", 120),
        "subtitle": _short(getattr(fascicolo, "oggetto", ""), 160),
        "type": _type_for_filters(fascicolo),
        "client": _text(getattr(fascicolo, "nome_cliente", ""), "Cliente non collegato"),
        "court": _text(getattr(fascicolo, "tribunale", ""), "Ufficio non impostato"),
        "rg": _rg(fascicolo),
        "nextDeadline": _date_label(n_date) if n_date else "n.d.",
        "nextDeadlineIso": n_date,
        "status": "archiviato" if archived is True else _status_for_filters(fascicolo),
        "documents": docs,
        "unreadCommunications": unread,
        "alerts": alerts,
        "openedAt": _text(getattr(fascicolo, "data_apertura", "")),
        "closedAt": _text(getattr(fascicolo, "data_chiusura", "")),
        "updatedAt": _text(getattr(fascicolo, "modificato_il", "")),
        "href": f"/fascicoli/{fid}",
        "operationalHref": f"/fascicoli/{fid}",
        "editHref": f"/fascicoli/{fid}/modifica",
        "operationalEditHref": f"/fascicoli/{fid}/modifica",
        "exportPdfHref": f"/fascicoli/{fid}/pdf",
        "archiveZipHref": f"/fascicoli/{fid}/archivio/scarica",
        "restoreAction": f"/fascicoli/{fid}/ripristina",
        "tone": _status_tone(stato),
        "archive": {
            "outcome": _text(getattr(archive, "esito_finale", "")),
            "archivedAt": _text(getattr(archive, "data_archiviazione", "")),
            "reason": _text(getattr(archive, "motivo", "")),
            "notes": _text(getattr(archive, "note_archivio", "")),
            "zipAvailable": bool(_text(getattr(archive, "percorso_zip", ""))),
            "zipSize": _bytes_label(getattr(archive, "dimensione_zip", 0)),
            "hash": _text(getattr(archive, "hash_zip", "")),
        } if archive else None,
    }


def _all_scadenze_by_fasc(get_scadenziario: Callable[[], Any]) -> dict[str, list[Any]]:
    rows = _safe("scadenziario", lambda: get_scadenziario().tutte(solo_aperte=True), [])
    grouped: dict[str, list[Any]] = {}
    for item in rows:
        fid = _text(getattr(item, "id_fascicolo", ""))
        if fid:
            grouped.setdefault(fid, []).append(item)
    return grouped


def _summary(items: list[dict[str, Any]], archived_count: int = 0, deadlines30: int = 0) -> dict[str, int]:
    return {
        "total": len(items) + archived_count,
        "active": sum(1 for item in items if item["status"] != "archiviato"),
        "inProgress": sum(1 for item in items if item["status"] == "in_corso"),
        "toArchive": sum(1 for item in items if item["status"] in {"definito", "da_archiviare"}),
        "archived": archived_count + sum(1 for item in items if item["status"] == "archiviato"),
        "suspended": sum(1 for item in items if item["status"] == "sospeso"),
        "deadlines7": sum(1 for item in items if item.get("nextDeadlineIso") and (_parse_date(item["nextDeadlineIso"]) or date.max) <= date.today() + timedelta(days=7)),
        "deadlines30": deadlines30,
        "documents": sum(int(item.get("documents") or 0) for item in items),
        "documentsToClassify": sum(int(item.get("alerts") or 0) for item in items),
        "unreadCommunications": sum(int(item.get("unreadCommunications") or 0) for item in items),
    }


def _facets(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    types = Counter(item["type"] for item in items)
    statuses = Counter(item["status"] for item in items)
    type_labels = {
        "civile": "Civile",
        "penale": "Penale",
        "amministrativo": "Amministrativo",
        "tributario": "Tributario",
        "stragiudiziale": "Stragiudiziale",
        "consulenza": "Consulenza",
        "lavoro": "Lavoro",
        "famiglia": "Famiglia",
        "successioni": "Successioni",
        "altro": "Altro",
    }
    status_labels = {
        "aperto": "Aperto",
        "in_corso": "In corso",
        "definito": "Definito",
        "da_archiviare": "Da archiviare",
        "archiviato": "Archiviato",
        "sospeso": "Sospeso",
    }
    return {
        "types": [{"value": "tutti", "label": "Tutti i tipi", "count": len(items)}]
        + [{"value": value, "label": label, "count": types.get(value, 0)} for value, label in type_labels.items()],
        "statuses": [{"value": "tutti", "label": "Tutti gli stati", "count": len(items)}]
        + [{"value": value, "label": label, "count": statuses.get(value, 0)} for value, label in status_labels.items()],
    }


def _deadline_rows(get_scadenziario: Callable[[], Any], items_by_id: dict[str, dict[str, Any]], days: int = 7) -> list[dict[str, Any]]:
    horizon = date.today() + timedelta(days=days)
    scadenze = _safe("scadenziario", lambda: get_scadenziario().tutte(solo_aperte=True), [])
    out: list[dict[str, Any]] = []
    for scadenza in scadenze:
        due = _parse_date(getattr(scadenza, "data_scadenza", "") or getattr(scadenza, "data", ""))
        if not due or due > horizon:
            continue
        fid = _text(getattr(scadenza, "id_fascicolo", ""))
        matter = items_by_id.get(fid, {})
        out.append(
            {
                "id": _text(getattr(scadenza, "id", ""), f"deadline-{len(out)}"),
                "matterId": fid,
                "matterRef": matter.get("ref") or fid,
                "title": _short(getattr(scadenza, "titolo", "") or "Scadenza", 100),
                "date": _date_label(due),
                "dateIso": due.isoformat(),
                "href": f"/scadenziario?id_fascicolo={fid}" if fid else "/scadenziario",
                "tone": _deadline_tone(scadenza),
            }
        )
    return sorted(out, key=lambda item: item["dateIso"])


def _contracts() -> dict[str, Any]:
    return {"mock_fallback": False, "read_only": True, "writes": "operational_routes"}


def build_react_fascicoli_payload(*, get_fascicoli: Callable[[], Any], get_scadenziario: Callable[[], Any]) -> dict[str, Any]:
    gf = get_fascicoli()
    scadenze_by_fasc = _all_scadenze_by_fasc(get_scadenziario)
    fascicoli = _safe("fascicoli", lambda: gf.tutti(archiviati=False), [])
    archived = _safe("fascicoli_archivio", lambda: gf.tutti(stato=StatoFascicolo.ARCHIVIATO, archiviati=True), [])
    items = [_item(fascicolo, scadenze_by_fasc=scadenze_by_fasc) for fascicolo in fascicoli]
    items_by_id = {item["id"]: item for item in items}
    deadlines30 = len(_deadline_rows(get_scadenziario, items_by_id, days=30))
    return {
        "source": "repository_reali",
        "generatedAt": _now(),
        "contracts": _contracts(),
        "summary": _summary(items, archived_count=len(archived), deadlines30=deadlines30),
        "items": items,
        "facets": _facets(items),
        "deadlines": _deadline_rows(get_scadenziario, items_by_id, days=7),
    }


def build_react_archivio_payload(*, get_fascicoli: Callable[[], Any], get_scadenziario: Callable[[], Any], query: str = "") -> dict[str, Any]:
    gf = get_fascicoli()
    scadenze_by_fasc = _all_scadenze_by_fasc(get_scadenziario)
    if query:
        fascicoli = _safe("archivio", lambda: gf.cerca(testo=query, stato=StatoFascicolo.ARCHIVIATO, archiviati=True), [])
    else:
        fascicoli = _safe("archivio", lambda: gf.tutti(stato=StatoFascicolo.ARCHIVIATO, archiviati=True), [])
    items = [_item(fascicolo, scadenze_by_fasc=scadenze_by_fasc, archived=True) for fascicolo in fascicoli]
    return {
        "source": "repository_reali",
        "generatedAt": _now(),
        "contracts": _contracts(),
        "summary": _summary(items, archived_count=0, deadlines30=0),
        "items": items,
        "facets": _facets(items),
        "deadlines": [],
    }


def _client_label(cliente: Any) -> str:
    return _text(getattr(cliente, "nome_completo", "")) or _text(getattr(cliente, "ragione_sociale", "")) or _text(getattr(cliente, "cognome", "")) or "Cliente"


def _client_options(get_clienti: Callable[[], Any]) -> list[dict[str, str]]:
    clienti = _safe("clienti", lambda: get_clienti().tutti(stato=None), [])
    out = []
    for cliente in clienti:
        out.append(
            {
                "id": _text(getattr(cliente, "id", "")),
                "label": _client_label(cliente),
                "taxCode": _text(getattr(cliente, "codice_fiscale", "")),
            }
        )
    return out


def _form_fascicolo_payload(fascicolo: Any | None) -> dict[str, Any] | None:
    if not fascicolo:
        return None
    base = _item(fascicolo)
    base.update(
        {
            "object": _text(getattr(fascicolo, "oggetto", "")),
            "counterparty": _text(getattr(fascicolo, "controparte", "")),
            "counterpartyTaxCode": _text(getattr(fascicolo, "cf_controparte", "")),
            "judge": _text(getattr(fascicolo, "giudice", "")),
            "section": _text(getattr(fascicolo, "sezione", "")),
            "leadLawyer": _text(getattr(fascicolo, "avvocato_referente", "")),
            "dominus": _text(getattr(fascicolo, "avvocato_dominus", "")),
            "value": str(getattr(fascicolo, "valore_causa", "") or ""),
            "quotedValue": str(getattr(fascicolo, "valore_preventivato", "") or ""),
            "agreedFee": str(getattr(fascicolo, "compenso_pattuito", "") or ""),
            "procedureType": _text(getattr(fascicolo, "tipo_procedimento", "")),
            "practiceId": _text(getattr(fascicolo, "id_pratica", "")),
            "practiceArea": _text(getattr(fascicolo, "area_pratica", "")),
            "firstHearing": _text(getattr(fascicolo, "data_prima_udienza", "")),
            "citationNotification": _text(getattr(fascicolo, "data_notifica_citazione", "")),
            "nextHearing": _text(getattr(fascicolo, "data_prossima_udienza", "")),
            "notes": _text(getattr(fascicolo, "note", "")),
            "reservedNotes": _text(getattr(fascicolo, "note_riservate", "")),
            "source": _text(getattr(fascicolo, "source", "")),
            "sourceExternalId": _text(getattr(fascicolo, "source_external_id", "")),
            "lastSyncAt": _text(getattr(fascicolo, "last_sync_at", "")),
            "syncStatus": _text(getattr(fascicolo, "sync_status", "")),
            "importLogId": _text(getattr(fascicolo, "import_log_id", "")),
            "hasConflicts": bool(getattr(fascicolo, "has_conflicts", False)),
            "documentSyncEnabled": bool(getattr(fascicolo, "document_sync_enabled", False)),
            "eventsSyncEnabled": bool(getattr(fascicolo, "events_sync_enabled", False)),
            "complianceControlsEnabled": bool(getattr(fascicolo, "compliance_controls_enabled", True)),
            "archiveReady": bool(getattr(fascicolo, "archivio_pronto", False)),
            "typeRaw": _enum_value(getattr(fascicolo, "tipo", "")),
            "statusRaw": _enum_value(getattr(fascicolo, "stato", "")),
            "clientId": _text(getattr(fascicolo, "id_cliente", "")),
            "id_cliente": _text(getattr(fascicolo, "id_cliente", "")),
            "tribunale": _text(getattr(fascicolo, "tribunale", "")),
            "numeroRg": _text(getattr(fascicolo, "numero_rg", "")),
            "numero_rg": _text(getattr(fascicolo, "numero_rg", "")),
            "annoRg": str(getattr(fascicolo, "anno_rg", "") or ""),
            "anno_rg": str(getattr(fascicolo, "anno_rg", "") or ""),
            "valueRaw": str(getattr(fascicolo, "valore_causa", "") or ""),
            "quotedValueRaw": str(getattr(fascicolo, "valore_preventivato", "") or ""),
            "agreedFeeRaw": str(getattr(fascicolo, "compenso_pattuito", "") or ""),
            "firstHearingIso": _text(getattr(fascicolo, "data_prima_udienza", "")),
            "citationNotificationIso": _text(getattr(fascicolo, "data_notifica_citazione", "")),
            "nextHearingIso": _text(getattr(fascicolo, "data_prossima_udienza", "")),
        }
    )
    return base


def build_react_fascicolo_form_payload(
    *,
    get_fascicoli: Callable[[], Any],
    get_clienti: Callable[[], Any],
    id_fasc: str | None = None,
    query: dict[str, Any] | None = None,
    correction_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    query = {str(k): _text(v) for k, v in (query or {}).items()}
    fascicolo = _safe("fascicolo", lambda: get_fascicoli().get(id_fasc), None) if id_fasc else None
    mode = "edit" if id_fasc else "new"
    action = f"/fascicoli/{id_fasc}/modifica" if id_fasc else "/fascicoli/nuovo"
    detail = f"/fascicoli/{id_fasc}" if id_fasc else "/fascicoli"
    workflow = None
    if query.get("source_preventivo") or query.get("source_conferimento"):
        workflow = {
            "title": "Apertura pratica guidata",
            "badges": [value for value in [query.get("source_preventivo"), query.get("source_conferimento"), query.get("from_page")] if value],
            "summary": "Il fascicolo conservera' il collegamento con preventivo e conferimento tramite i campi nascosti storici.",
            "checklist": [
                "Verifica dati cliente, controparte e ufficio giudiziario.",
                "Controlla valore causa, compenso pattuito e tipo procedimento.",
                "Dopo la creazione carica documenti, scadenze e attività iniziali.",
            ],
            "values": [
                {"label": "Preventivo origine", "value": query.get("source_preventivo", "n.d."), "mono": True},
                {"label": "Conferimento origine", "value": query.get("source_conferimento", "n.d."), "mono": True},
            ],
        }
    return {
        "source": "repository_reali",
        "generatedAt": _now(),
        "mode": mode,
        "action": action,
        "backHref": f"/fascicoli/{id_fasc}" if id_fasc else "/fascicoli",
        "detailHref": detail,
        "query": query,
        "clients": _client_options(get_clienti),
        "types": _select_options(TipoFascicolo),
        "states": _select_options(StatoFascicolo),
        "fascicolo": _form_fascicolo_payload(fascicolo),
        "workflow": workflow,
        "correction": correction_context or {"active": False, "title": "", "help": "", "highlight": ""},
    }


def _client_payload(cliente: Any) -> dict[str, Any] | None:
    if not cliente:
        return None
    recapiti = getattr(cliente, "recapiti", None)
    indirizzo = getattr(cliente, "indirizzo", None)
    address = " ".join(
        part
        for part in [
            _text(getattr(indirizzo, "via", "")),
            _text(getattr(indirizzo, "cap", "")),
            _text(getattr(indirizzo, "comune", "")),
            _text(getattr(indirizzo, "provincia", "")),
        ]
        if part
    )
    return {
        "id": _text(getattr(cliente, "id", "")),
        "name": _client_label(cliente),
        "taxCode": _text(getattr(cliente, "codice_fiscale", "")),
        "vat": _text(getattr(cliente, "partita_iva", "")),
        "email": _text(getattr(recapiti, "email", "") or getattr(cliente, "email", "")),
        "pec": _text(getattr(recapiti, "pec", "") or getattr(cliente, "pec", "")),
        "phone": _text(getattr(recapiti, "telefono", "") or getattr(recapiti, "cellulare", "") or getattr(cliente, "telefono", "")),
        "address": address,
        "href": f"/clienti/{_text(getattr(cliente, 'id', ''))}",
    }


def _profile(fascicolo: Any) -> list[dict[str, Any]]:
    rows = [
        ("Cliente", getattr(fascicolo, "nome_cliente", ""), False, f"/clienti/{_text(getattr(fascicolo, 'id_cliente', ''))}" if _text(getattr(fascicolo, "id_cliente", "")) else ""),
        ("Controparte", getattr(fascicolo, "controparte", ""), False, ""),
        ("Tribunale", getattr(fascicolo, "tribunale", ""), False, ""),
        ("N. registro", _rg(fascicolo), True, ""),
        ("Rif. interno", getattr(fascicolo, "numero", ""), True, ""),
        ("Sezione", getattr(fascicolo, "sezione", ""), False, ""),
        ("Giudice", getattr(fascicolo, "giudice", ""), False, ""),
        ("Avv. referente", getattr(fascicolo, "avvocato_referente", ""), False, ""),
        ("Avv. dominus", getattr(fascicolo, "avvocato_dominus", ""), False, ""),
        ("Valore causa", _euro(getattr(fascicolo, "valore_causa", 0)), False, ""),
        ("Compenso pattuito", _euro(getattr(fascicolo, "compenso_pattuito", 0)), False, ""),
        ("Apertura", _date_label(getattr(fascicolo, "data_apertura", "")), False, ""),
        ("Prima udienza", _date_label(getattr(fascicolo, "data_prima_udienza", "")), False, ""),
        ("Prossima udienza", _date_label(getattr(fascicolo, "data_prossima_udienza", "")), False, ""),
        ("Chiusura", _date_label(getattr(fascicolo, "data_chiusura", "")), False, ""),
        ("Fonte portale", getattr(fascicolo, "source", ""), False, ""),
        ("Ultimo sync", _date_label(getattr(fascicolo, "last_sync_at", "")), False, ""),
    ]
    return [
        {"label": label, "value": _text(value, "n.d."), "mono": mono, "href": href}
        for label, value, mono, href in rows
        if _text(value) and _text(value) != "EUR 0,00"
    ]


def _documents(fascicolo: Any) -> list[dict[str, Any]]:
    fid = _text(getattr(fascicolo, "id", ""))
    out = []
    for doc in getattr(fascicolo, "documenti", []) or []:
        did = _text(getattr(doc, "id", ""))
        name = _text(getattr(doc, "nome", ""), "Documento")
        signed = bool(getattr(doc, "firmato", False) or getattr(doc, "firmato_digitalmente", False) or name.lower().endswith(".p7m"))
        out.append(
            {
                "id": did,
                "name": name,
                "type": _enum_value(getattr(doc, "tipo", "ALTRO")).replace("_", " "),
                "size": _bytes_label(getattr(doc, "dimensione_bytes", 0)),
                "uploadedAt": _date_label(getattr(doc, "data_caricamento", "")),
                "documentDate": _date_label(getattr(doc, "data_documento", "")),
                "notes": _short(getattr(doc, "note", ""), 180),
                "tags": list(getattr(doc, "tags", []) or []),
                "signed": signed,
                "source": _text(getattr(doc, "fonte_documento", ""), "CARICAMENTO_STUDIO"),
                "portalName": _text(getattr(doc, "nome_portale", "")),
                "portalClass": _text(getattr(doc, "classificazione_portale", "")),
                "portalSender": _text(getattr(doc, "mittente_portale", "")),
                "portalDate": _date_label(getattr(doc, "data_deposito_portale", "")),
                "hash": _text(getattr(doc, "hash_sha256", "")),
                "actions": {
                    "preview": f"/fascicoli/{fid}/documenti/{did}/visualizza",
                    "download": f"/fascicoli/{fid}/documenti/{did}/scarica",
                    "edit": f"/fascicoli/{fid}/documenti/{did}/editor",
                    "sign": f"/fascicoli/{fid}/documenti/{did}/firma",
                    "pdfa": f"/fascicoli/{fid}/documenti/{did}/converti-pdfa",
                    "attest": f"/fascicoli/{fid}/documenti/{did}/attestazione",
                    "metadata": f"/fascicoli/{fid}/documenti/{did}/metadati",
                    "delete": f"/fascicoli/{fid}/documenti/{did}/elimina",
                },
            }
        )
    return out


def _activities(fascicolo: Any) -> list[dict[str, Any]]:
    fid = _text(getattr(fascicolo, "id", ""))
    out = []
    for att in getattr(fascicolo, "attivita", []) or []:
        aid = _text(getattr(att, "id", ""))
        result = _enum_value(getattr(att, "esito", "IN_ATTESA"))
        out.append(
            {
                "id": aid,
                "type": _enum_value(getattr(att, "tipo", "ALTRO")).replace("_", " "),
                "title": _short(getattr(att, "titolo", ""), 120) or "Attivita",
                "date": _date_label(getattr(att, "data", "")),
                "description": _short(getattr(att, "descrizione", ""), 220),
                "result": result.replace("_", " "),
                "place": _text(getattr(att, "luogo", "")),
                "notes": _short(getattr(att, "note", ""), 180),
                "lawyer": _text(getattr(att, "avvocato", "")),
                "documentId": _text(getattr(att, "id_documento", "")),
                "depositId": _text(getattr(att, "id_deposito_pct", "")),
                "updateAction": f"/fascicoli/{fid}/attivita/{aid}/esito",
                "deleteAction": f"/fascicoli/{fid}/attivita/{aid}/elimina",
                "tone": _activity_tone(result),
            }
        )
    return sorted(out, key=lambda item: item["date"], reverse=True)


def _deadlines(scadenze: Iterable[Any]) -> list[dict[str, Any]]:
    out = []
    for item in scadenze:
        sid = _text(getattr(item, "id", ""), f"deadline-{len(out)}")
        raw_date = _text(getattr(item, "data_scadenza", "") or getattr(item, "data", ""))
        out.append(
            {
                "id": sid,
                "title": _short(getattr(item, "titolo", ""), 120) or "Scadenza",
                "date": _date_label(raw_date),
                "dateIso": raw_date,
                "type": _enum_value(getattr(item, "tipo", "")).replace("_", " "),
                "priority": _enum_value(getattr(item, "priorita", "")).replace("_", " "),
                "status": _enum_value(getattr(item, "stato", "")).replace("_", " "),
                "peremptory": bool(getattr(item, "perentorio", False)),
                "notes": _short(getattr(item, "note", ""), 160),
                "href": f"/scadenziario?focus={sid}",
                "tone": _deadline_tone(item),
            }
        )
    return sorted(out, key=lambda item: item["dateIso"] or "9999")


def _appointments(apps: Iterable[Any]) -> list[dict[str, Any]]:
    out = []
    for app in apps:
        aid = _text(getattr(app, "id", ""), f"app-{len(out)}")
        raw = getattr(app, "data_ora", "") or getattr(app, "data_ora_dt", "")
        out.append(
            {
                "id": aid,
                "title": _short(getattr(app, "titolo", ""), 120) or "Appuntamento",
                "date": _date_label(raw),
                "time": _time_label(raw),
                "place": _text(getattr(app, "luogo", "")),
                "court": _text(getattr(app, "tribunale", "")),
                "type": _enum_value(getattr(app, "tipo", "")),
                "href": f"/agenda?id={aid}",
                "tone": "warning" if _parse_date(raw) and (_parse_date(raw) or date.max) <= date.today() + timedelta(days=1) else "primary",
            }
        )
    return out


def _deposits(fascicolo: Any) -> list[dict[str, Any]]:
    out = []
    for dep in getattr(fascicolo, "depositi_pct", []) or []:
        did = _text(getattr(dep, "id", ""), f"deposito-{len(out)}")
        status = _enum_value(getattr(dep, "stato", ""))
        portal_docs = []
        for doc in getattr(dep, "documenti_portale", []) or []:
            if not isinstance(doc, dict):
                continue
            portal_docs.append(
                {
                    "name": _text(doc.get("nome"), "Documento ufficiale"),
                    "type": _text(doc.get("tipo"), "Documento"),
                    "date": _date_label(doc.get("data_deposito") or doc.get("data_documento")),
                    "sender": _text(doc.get("mittente")),
                    "imported": bool(doc.get("gia_importato") or doc.get("local_doc_id")),
                    "available": bool(doc.get("disponibile", True)),
                }
            )
        tone = "success" if status in {"ACCETTATO_CANCELLERIA", "CONSEGNATO", "ACCETTATO_PEC"} else "danger" if "ERRORE" in status or "RIFIUTATO" in status else "warning" if "WARN" in status else "primary"
        out.append(
            {
                "id": did,
                "timestamp": _date_label(getattr(dep, "timestamp", "")),
                "status": status.replace("_", " "),
                "actType": _enum_value(getattr(dep, "tipo_atto", "")).replace("_", " "),
                "pec": _text(getattr(dep, "pec_destinatario", "")),
                "message": _short(getattr(dep, "messaggio", ""), 200),
                "checks": _enum_value(getattr(dep, "esito_controlli", "")),
                "source": _text(getattr(dep, "fonte_portale", "")) or _text(getattr(dep, "servizio_portale", "")),
                "externalId": _text(getattr(dep, "id_deposito_esterno", "")),
                "mainFile": _text(getattr(dep, "nome_atto_principale", "")),
                "documentsCount": len(getattr(dep, "documenti_ids", []) or []) + len(portal_docs),
                "portalDocuments": portal_docs,
                "tone": tone,
            }
        )
    return out


def _parties(parti: Iterable[Any]) -> list[dict[str, str]]:
    out = []
    for item in parti:
        sid = _text(getattr(item, "id", ""), f"soggetto-{len(out)}")
        recapiti = getattr(item, "recapiti", None)
        out.append(
            {
                "id": sid,
                "name": _text(getattr(item, "nome_completo", ""), "Soggetto"),
                "role": _enum_value(getattr(item, "ruolo", "")),
                "taxCode": _text(getattr(item, "codice_fiscale", "") or getattr(item, "identificativo", "")),
                "email": _text(getattr(recapiti, "email", "") or getattr(item, "email", "")),
                "pec": _text(getattr(recapiti, "pec", "") or getattr(item, "pec", "")),
                "phone": _text(getattr(recapiti, "telefono", "") or getattr(item, "telefono", "")),
                "href": f"/soggetti/{sid}",
            }
        )
    return out


def _history(fascicolo: Any) -> list[dict[str, str]]:
    out = []
    for item in getattr(fascicolo, "avanzamento", []) or []:
        out.append(
            {
                "date": _date_label(getattr(item, "data", "")),
                "description": _short(getattr(item, "descrizione", ""), 160),
                "from": _text(getattr(item, "stato_precedente", "")),
                "to": _text(getattr(item, "stato_nuovo", "")),
                "notes": _short(getattr(item, "note", ""), 180),
                "lawyer": _text(getattr(item, "avvocato", "")),
            }
        )
    return out


def _economics(preventivi: list[Any], conferimenti: list[Any], parcelle: list[Any], timesheet_entries: list[Any], fascicolo: Any) -> list[dict[str, Any]]:
    minutes = sum(int(getattr(item, "minuti", 0) or 0) for item in timesheet_entries)
    parcelle_total = sum(float(getattr(item, "totale", 0.0) or getattr(item, "netto_a_pagare", 0.0) or 0.0) for item in parcelle)
    return [
        {"id": "valore", "label": "Valore causa", "value": _euro(getattr(fascicolo, "valore_causa", 0)), "note": "dato fascicolo", "href": "#profilo", "tone": "primary"},
        {"id": "compenso", "label": "Compenso pattuito", "value": _euro(getattr(fascicolo, "compenso_pattuito", 0)), "note": f"{len(conferimenti)} conferimenti", "href": "/preventivi", "tone": "purple"},
        {"id": "parcelle", "label": "Parcelle", "value": _euro(parcelle_total), "note": f"{len(parcelle)} documenti economici", "href": "/fatturazione/", "tone": "success"},
        {"id": "tempo", "label": "Tempo", "value": f"{round(minutes/60, 1)} h".replace(".", ","), "note": f"{len(timesheet_entries)} voci timesheet", "href": "/timesheet", "tone": "info"},
        {"id": "preventivi", "label": "Preventivi", "value": str(len(preventivi)), "note": "collegati al fascicolo", "href": "/preventivi/", "tone": "orange"},
    ]


def _workflow(preventivi: list[Any], conferimenti: list[Any], parcelle: list[Any], timesheet_entries: list[Any], cliente: Any) -> list[dict[str, Any]]:
    return [
        {"label": "Cliente", "value": "OK" if cliente else "Da collegare", "note": "anagrafica fascicolo", "tone": "success" if cliente else "warning", "href": "/clienti"},
        {"label": "Preventivo", "value": str(len(preventivi)), "note": "offerte collegate", "tone": "success" if preventivi else "neutral", "href": "/preventivi/"},
        {"label": "Conferimento", "value": str(len(conferimenti)), "note": "incarichi collegati", "tone": "success" if conferimenti else "warning", "href": "/preventivi/"},
        {"label": "Attivita", "value": str(len(timesheet_entries)), "note": "voci valorizzabili", "tone": "primary" if timesheet_entries else "neutral", "href": "/timesheet"},
        {"label": "Parcelle", "value": str(len(parcelle)), "note": "fino all'incasso", "tone": "success" if parcelle else "neutral", "href": "/fatturazione/"},
    ]


def _telematic(fascicolo: Any) -> list[dict[str, Any]]:
    fid = _text(getattr(fascicolo, "id", ""))
    tipo = _enum_value(getattr(fascicolo, "tipo", ""))
    return [
        {"label": "PolisWeb / PST", "value": "Apri", "note": "consultazione e acquisizione guidata", "href": f"/polisWeb?id_fasc={fid}", "tone": "primary"},
        {"label": "PDP Penale", "value": "Attivo" if tipo == "PENALE" else "Disponibile", "note": "workflow penale se applicabile", "href": f"/pdp/fascicoli/{fid}", "tone": "danger" if tipo == "PENALE" else "neutral"},
        {"label": "PAT", "value": "Collega", "note": "amministrativo", "href": "/pat", "tone": "info"},
        {"label": "PTT / SIGIT", "value": "Collega", "note": "tributario", "href": "/sigit/ricerca", "tone": "warning"},
        {"label": "Checklist deposito", "value": "Verifica", "note": "busta, firme, PDF/A", "href": "/deposito/checklist", "tone": "success"},
    ]


def _quality(fascicolo: Any, cliente: Any, scadenze: list[Any], parti: list[Any]) -> list[dict[str, Any]]:
    return [
        {"label": "Dati principali", "value": "titolo, tipo, ufficio", "ok": bool(getattr(fascicolo, "titolo", "") and getattr(fascicolo, "tipo", "")), "tone": "success"},
        {"label": "Cliente", "value": _text(getattr(fascicolo, "nome_cliente", ""), "non collegato"), "ok": bool(cliente), "tone": "success" if cliente else "warning"},
        {"label": "Parti", "value": f"{len(parti)} soggetti", "ok": bool(parti or getattr(fascicolo, "controparte", "")), "tone": "success" if parti else "warning"},
        {"label": "Documenti", "value": f"{len(getattr(fascicolo, 'documenti', []) or [])} file", "ok": bool(getattr(fascicolo, "documenti", [])), "tone": "primary"},
        {"label": "Scadenze", "value": f"{len(scadenze)} termini", "ok": bool(scadenze), "tone": "warning" if scadenze else "neutral"},
        {"label": "Controlli conformita", "value": "attivi" if getattr(fascicolo, "compliance_controls_enabled", True) else "disattivati", "ok": bool(getattr(fascicolo, "compliance_controls_enabled", True)), "tone": "success" if getattr(fascicolo, "compliance_controls_enabled", True) else "orange"},
        {"label": "Sync portale", "value": _text(getattr(fascicolo, "sync_status", ""), "locale"), "ok": not bool(getattr(fascicolo, "has_conflicts", False)), "tone": "danger" if getattr(fascicolo, "has_conflicts", False) else "success"},
    ]


def _full_fascicolo(fascicolo: Any) -> dict[str, Any]:
    base = _item(fascicolo)
    base.update(
        {
            "object": _text(getattr(fascicolo, "oggetto", "")),
            "counterparty": _text(getattr(fascicolo, "controparte", "")),
            "counterpartyTaxCode": _text(getattr(fascicolo, "cf_controparte", "")),
            "judge": _text(getattr(fascicolo, "giudice", "")),
            "section": _text(getattr(fascicolo, "sezione", "")),
            "leadLawyer": _text(getattr(fascicolo, "avvocato_referente", "")),
            "dominus": _text(getattr(fascicolo, "avvocato_dominus", "")),
            "value": _euro(getattr(fascicolo, "valore_causa", 0)),
            "quotedValue": _euro(getattr(fascicolo, "valore_preventivato", 0)),
            "agreedFee": _euro(getattr(fascicolo, "compenso_pattuito", 0)),
            "procedureType": _text(getattr(fascicolo, "tipo_procedimento", "")),
            "practiceId": _text(getattr(fascicolo, "id_pratica", "")),
            "practiceArea": _text(getattr(fascicolo, "area_pratica", "")),
            "firstHearing": _date_label(getattr(fascicolo, "data_prima_udienza", "")),
            "citationNotification": _date_label(getattr(fascicolo, "data_notifica_citazione", "")),
            "nextHearing": _date_label(getattr(fascicolo, "data_prossima_udienza", "")),
            "notes": _text(getattr(fascicolo, "note", "")),
            "reservedNotes": _text(getattr(fascicolo, "note_riservate", "")),
            "source": _text(getattr(fascicolo, "source", "")),
            "sourceExternalId": _text(getattr(fascicolo, "source_external_id", "")),
            "lastSyncAt": _date_label(getattr(fascicolo, "last_sync_at", "")),
            "syncStatus": _text(getattr(fascicolo, "sync_status", "")),
            "importLogId": _text(getattr(fascicolo, "import_log_id", "")),
            "hasConflicts": bool(getattr(fascicolo, "has_conflicts", False)),
            "documentSyncEnabled": bool(getattr(fascicolo, "document_sync_enabled", False)),
            "eventsSyncEnabled": bool(getattr(fascicolo, "events_sync_enabled", False)),
            "complianceControlsEnabled": bool(getattr(fascicolo, "compliance_controls_enabled", True)),
            "archiveReady": bool(getattr(fascicolo, "archivio_pronto", False)),
            "typeRaw": _enum_value(getattr(fascicolo, "tipo", "")),
            "statusRaw": _enum_value(getattr(fascicolo, "stato", "")),
            "clientId": _text(getattr(fascicolo, "id_cliente", "")),
            "numeroRg": _text(getattr(fascicolo, "numero_rg", "")),
            "annoRg": str(getattr(fascicolo, "anno_rg", "") or ""),
            "valueRaw": str(getattr(fascicolo, "valore_causa", "") or ""),
            "quotedValueRaw": str(getattr(fascicolo, "valore_preventivato", "") or ""),
            "agreedFeeRaw": str(getattr(fascicolo, "compenso_pattuito", "") or ""),
            "firstHearingIso": _text(getattr(fascicolo, "data_prima_udienza", "")),
            "citationNotificationIso": _text(getattr(fascicolo, "data_notifica_citazione", "")),
            "nextHearingIso": _text(getattr(fascicolo, "data_prossima_udienza", "")),
        }
    )
    return base


def build_react_fascicolo_detail_payload(
    *,
    get_fascicoli: Callable[[], Any],
    get_clienti: Callable[[], Any],
    get_agenda: Callable[[], Any],
    get_scadenziario: Callable[[], Any],
    get_soggetti: Callable[[], Any],
    get_preventivi: Callable[[], Any],
    get_fatturazione: Callable[[], Any],
    get_timesheet: Callable[[], Any],
    id_fasc: str,
) -> dict[str, Any]:
    fascicolo = _safe("fascicolo", lambda: get_fascicoli().get(id_fasc), None)
    if not fascicolo:
        return {"source": "repository_reali", "generatedAt": _now(), "contracts": _contracts(), "notFound": True, "fascicolo": {"id": id_fasc}}
    cliente = _safe("cliente", lambda: get_clienti().get(getattr(fascicolo, "id_cliente", "")), None) if getattr(fascicolo, "id_cliente", "") else None
    apps = _safe("agenda", lambda: get_agenda().cerca(testo=getattr(fascicolo, "numero_rg", "")) if getattr(fascicolo, "numero_rg", "") else [], [])
    scadenze = _safe("scadenziario", lambda: get_scadenziario().tutte(id_fascicolo=id_fasc, solo_aperte=False), [])
    parti = _safe("soggetti", lambda: get_soggetti().parti_fascicolo(id_fasc), [])
    preventivi_repo = _safe("preventivi_repo", lambda: get_preventivi(), None)
    preventivi = _safe("preventivi", lambda: preventivi_repo.preventivi_per_fascicolo(id_fasc), []) if preventivi_repo else []
    conferimenti = _safe("conferimenti", lambda: preventivi_repo.conferimenti_per_fascicolo(id_fasc), []) if preventivi_repo else []
    parcelle = _safe("parcelle", lambda: get_fatturazione().per_fascicolo(id_fasc), [])
    timesheet_entries = _safe("timesheet", lambda: get_timesheet().per_fascicolo(id_fasc), [])
    activities = _activities(fascicolo)
    requests = [item for item in activities if "ISTAN" in item["type"].upper() or "ISTAN" in item["title"].upper()]
    quick_counts = {
        "profilo": len(_profile(fascicolo)),
        "documenti": len(getattr(fascicolo, "documenti", []) or []),
        "attivita": len(activities),
        "udienze_scadenze": len(scadenze) + len(apps),
        "comunicazioni": len(getattr(fascicolo, "depositi_pct", []) or []),
        "istanze": len(requests),
    }
    fid = _text(getattr(fascicolo, "id", id_fasc))
    return {
        "source": "repository_reali",
        "generatedAt": _now(),
        "contracts": _contracts(),
        "fascicolo": _full_fascicolo(fascicolo),
        "quickCounts": quick_counts,
        "profile": _profile(fascicolo),
        "documents": _documents(fascicolo),
        "activities": activities,
        "deadlines": _deadlines(scadenze),
        "appointments": _appointments(apps),
        "deposits": _deposits(fascicolo),
        "requests": requests,
        "parties": _parties(parti),
        "history": _history(fascicolo),
        "client": _client_payload(cliente),
        "economics": _economics(preventivi, conferimenti, parcelle, timesheet_entries, fascicolo),
        "workflow": _workflow(preventivi, conferimenti, parcelle, timesheet_entries, cliente),
        "telematic": _telematic(fascicolo),
        "quality": _quality(fascicolo, cliente, scadenze, parti),
        "actions": {
            "changeState": f"/fascicoli/{fid}/stato",
            "define": f"/fascicoli/{fid}/definisci",
            "archive": f"/fascicoli/{fid}/archivia",
            "restore": f"/fascicoli/{fid}/ripristina",
            "delete": f"/fascicoli/{fid}/elimina",
            "uploadDocument": f"/fascicoli/{fid}/documenti/carica",
            "importPortal": f"/fascicoli/{fid}/documenti/importa-portale",
            "addActivity": f"/fascicoli/{fid}/attivita/aggiungi",
            "complianceOn": f"/fascicoli/{fid}/conformita/controlli?enabled=1",
            "complianceOff": f"/fascicoli/{fid}/conformita/controlli?enabled=0",
            "exportPdf": f"/fascicoli/{fid}/pdf",
            "archiveZip": f"/fascicoli/{fid}/archivio/scarica",
        },
        "options": _options(),
    }


def build_react_fascicoli_export_payload(*, get_fascicoli: Callable[[], Any], get_scadenziario: Callable[[], Any]) -> dict[str, Any]:
    page = build_react_fascicoli_payload(get_fascicoli=get_fascicoli, get_scadenziario=get_scadenziario)
    recent = page["items"][:12]
    return {
        "source": "repository_reali",
        "generatedAt": _now(),
        "summary": page["summary"],
        "formats": [
            {"id": "pdf", "label": "PDF lista", "description": "Elenco fascicoli filtrato", "href": "/fascicoli/export.pdf", "tone": "danger"},
            {"id": "csv", "label": "CSV", "description": "Dati strutturati per analisi", "href": "/fascicoli/export.csv", "tone": "success"},
            {"id": "single_pdf", "label": "PDF singolo", "description": "Scheda completa del fascicolo", "href": "/fascicoli/<id>/pdf", "tone": "primary"},
            {"id": "zip", "label": "ZIP archivio", "description": "Archivio documentale dei fascicoli chiusi", "href": "/fascicoli/<id>/archivio/scarica", "tone": "neutral"},
        ],
        "fields": [
            {"key": "numero", "label": "Numero interno", "checked": True},
            {"key": "rg", "label": "N. causa / RG", "checked": True},
            {"key": "titolo", "label": "Titolo e oggetto", "checked": True},
            {"key": "tipo", "label": "Tipo fascicolo", "checked": True},
            {"key": "stato", "label": "Stato", "checked": True},
            {"key": "cliente", "label": "Cliente", "checked": True},
            {"key": "controparte", "label": "Controparte", "checked": True},
            {"key": "tribunale", "label": "Ufficio giudiziario", "checked": True},
            {"key": "date", "label": "Date apertura/chiusura", "checked": True},
            {"key": "avvocato", "label": "Avvocato referente", "checked": True},
            {"key": "economico", "label": "Valori economici", "checked": False},
            {"key": "sync", "label": "Sync e fonte portale", "checked": False},
        ],
        "presets": [
            {"label": "Attivi", "description": "Tutti i fascicoli non archiviati", "href": "/fascicoli/export.pdf", "tone": "primary"},
            {"label": "Da archiviare", "description": "Fascicoli definiti pronti per conservazione", "href": "/fascicoli/export.pdf?stato=DEFINITO", "tone": "warning"},
            {"label": "CSV completo", "description": "Base dati per controllo di studio", "href": "/fascicoli/export.csv", "tone": "success"},
            {"label": "Archivio", "description": "Controllo fascicoli chiusi", "href": "/fascicoli/archivio", "tone": "neutral"},
        ],
        "recent": recent,
        "facets": page["facets"],
    }
