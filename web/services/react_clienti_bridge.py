"""Bridge dati per la pagina Anagrafica Clienti della shell React.

Normalizza i repository esistenti senza introdurre una seconda source of truth
frontend. La lista e i form React usano i servizi Flask operativi per le
scritture, cosi audit, tenant e validazioni restano governati da un'unica
source of truth.
"""

from __future__ import annotations


from pct.formatting import format_euro_it
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from typing import Any, Callable, Mapping

from pct.clienti import StatoCliente, TipoCliente, TipoDocumento
from pct.fascicoli import StatoFascicolo
from pct.scadenziario import StatoTermine
from pct.soggetti import RuoloSoggetto, TipoSoggetto, soggetto_coincide_con_cliente


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "")


def _text(value: Any, fallback: str = "") -> str:
    return " ".join(str(value or fallback).split())


def _safe_internal_path(value: Any) -> str:
    raw = _text(value)
    if raw.startswith("/") and not raw.startswith("//"):
        return raw
    return ""


def _short(value: Any, limit: int = 120) -> str:
    text = _text(value)
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "..."


def _safe(label: str, func: Callable[[], Any], fallback: Any) -> Any:
    try:
        return func()
    except Exception:
        return fallback


def _parse_date(value: Any) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    raw = str(value or "").strip()
    if not raw:
        return None
    for sample in (raw.replace("Z", "+00:00"), raw[:19], raw[:10]):
        try:
            return datetime.fromisoformat(sample).date()
        except ValueError:
            continue
    return None


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _date_label(value: Any) -> str:
    parsed = _parse_date(value)
    if not parsed:
        return ""
    return parsed.strftime("%d/%m/%Y")


def _enum_label(value: Any) -> str:
    return _enum_value(value).replace("_", " ").title()


def _amount(value: Any) -> str:
    return format_euro_it(value)


def _status(cliente: Any) -> str:
    raw = _enum_value(getattr(cliente, "stato", "")).lower()
    if "archiv" in raw:
        return "archiviato"
    if "potenzial" in raw:
        return "potenziale"
    if "inatt" in raw:
        return "inattivo"
    return "attivo"


def _type(cliente: Any) -> str:
    raw = _enum_value(getattr(cliente, "tipo", "")).lower()
    if "giurid" in raw or "societ" in raw or raw == "pg":
        return "pg"
    return "pf"


def _tone(status: str) -> str:
    return {"attivo": "success", "potenziale": "warning", "archiviato": "neutral", "inattivo": "orange"}.get(status, "neutral")


def _recapiti(cliente: Any) -> tuple[str, str, str]:
    recapiti = getattr(cliente, "recapiti", None)
    phone = _text(getattr(recapiti, "cellulare", "") or getattr(recapiti, "telefono", ""))
    email = _text(getattr(recapiti, "email", ""))
    pec = _text(getattr(recapiti, "pec", ""))
    return phone, email, pec


def _fiscal_id(cliente: Any) -> str:
    return _text(getattr(cliente, "identificativo_fiscale", "") or getattr(cliente, "codice_fiscale", "") or getattr(cliente, "partita_iva", ""))


def _document_expired(cliente: Any) -> bool:
    documento = getattr(cliente, "documento", None)
    try:
        explicit = getattr(documento, "scaduto", None)
        if isinstance(explicit, bool):
            return explicit
    except Exception:
        explicit = None
    due = _parse_date(getattr(documento, "data_scadenza", ""))
    return bool(due and due < date.today())


def _cliente_key(value: Any) -> str:
    return _text(value).lower()


def _matter_groups(fascicoli_repo: Any) -> tuple[dict[str, list[Any]], dict[str, list[Any]]]:
    by_client_id: dict[str, list[Any]] = defaultdict(list)
    by_client_name: dict[str, list[Any]] = defaultdict(list)
    seen: set[str] = set()
    candidates: list[Any] = []
    for getter in (lambda: fascicoli_repo.tutti(archiviati=False), lambda: fascicoli_repo.tutti(archiviati=True), lambda: fascicoli_repo.tutti()):
        value = _safe("fascicoli", getter, [])
        if isinstance(value, list):
            candidates.extend(value)
    for item in candidates:
        item_id = _text(getattr(item, "id", "")) or _text(getattr(item, "numero", ""))
        if item_id in seen:
            continue
        seen.add(item_id)
        id_cliente = _text(getattr(item, "id_cliente", "") or getattr(item, "cliente_id", ""))
        nome_cliente = _cliente_key(getattr(item, "nome_cliente", "") or getattr(item, "cliente", ""))
        if id_cliente:
            by_client_id[id_cliente].append(item)
        if nome_cliente:
            by_client_name[nome_cliente].append(item)
    return by_client_id, by_client_name


def _matters_for(cliente: Any, by_client_id: dict[str, list[Any]], by_client_name: dict[str, list[Any]]) -> list[Any]:
    cliente_id = _text(getattr(cliente, "id", ""))
    nome = _cliente_key(getattr(cliente, "nome_completo", ""))
    items = list(by_client_id.get(cliente_id, []))
    known = {_text(getattr(item, "id", "")) for item in items}
    for item in by_client_name.get(nome, []):
        item_id = _text(getattr(item, "id", ""))
        if item_id not in known:
            items.append(item)
            known.add(item_id)
    return items


def _active_matter_count(items: list[Any]) -> int:
    total = 0
    for item in items:
        raw = _enum_value(getattr(item, "stato", "")).lower()
        archived = bool(getattr(item, "archiviato", False) or getattr(item, "is_archived", False) or "archiv" in raw)
        if not archived:
            total += 1
    return total


def _missing_fields(cliente: Any) -> list[str]:
    explicit = getattr(cliente, "campi_mancanti_per_conferimento", []) or []
    if isinstance(explicit, list):
        return [_text(item) for item in explicit if _text(item)]
    return []


def _subtitle(cliente: Any) -> str:
    parts = [_text(getattr(cliente, "provenienza", "")), _text(getattr(cliente, "forma_giuridica", "")), _short(getattr(cliente, "note", ""), 70)]
    return " - ".join(part for part in parts if part)


def _facet_rows(items: list[dict[str, Any]], key: str, labels: dict[str, str], all_label: str) -> list[dict[str, Any]]:
    rows = [{"value": "tutti", "label": all_label, "count": len(items)}]
    for value, label in labels.items():
        rows.append({"value": value, "label": label, "count": sum(1 for item in items if item.get(key) == value)})
    return rows


def _summary(items: list[dict[str, Any]]) -> dict[str, int]:
    statuses = Counter(item.get("status") for item in items)
    return {
        "total": len(items),
        "active": int(statuses.get("attivo", 0)),
        "potential": int(statuses.get("potenziale", 0)),
        "archived": int(statuses.get("archiviato", 0)),
        "withMatters": sum(1 for item in items if int(item.get("matters") or 0) > 0),
        "incomplete": sum(1 for item in items if item.get("missingFields")),
        "withoutContacts": sum(1 for item in items if not (item.get("email") or item.get("phone") or item.get("pec"))),
        "privacyMissing": sum(1 for item in items if not item.get("privacyOk")),
        "documentsExpired": sum(1 for item in items if item.get("documentExpired")),
    }


def build_react_clienti_payload(*, get_clienti: Callable[[], Any], get_fascicoli: Callable[[], Any]) -> dict[str, Any]:
    clienti_repo = get_clienti()
    fascicoli_repo = get_fascicoli()
    by_client_id, by_client_name = _matter_groups(fascicoli_repo)
    clienti = _safe("clienti", lambda: clienti_repo.tutti(), [])
    items: list[dict[str, Any]] = []

    for index, cliente in enumerate(clienti):
        item_id = _text(getattr(cliente, "id", "")) or f"cliente-{index}"
        status = _status(cliente)
        tipo = _type(cliente)
        phone, email, pec = _recapiti(cliente)
        linked_matters = _matters_for(cliente, by_client_id, by_client_name)
        procedimenti = getattr(cliente, "procedimenti", []) or []
        matters_count = max(len(linked_matters), len(procedimenti) if isinstance(procedimenti, list) else 0)
        active_count = max(_active_matter_count(linked_matters), len(getattr(cliente, "procedimenti_attivi", []) or []))
        tags = getattr(cliente, "tag", []) or []
        if not isinstance(tags, list):
            tags = []
        items.append({
            "id": item_id,
            "name": _text(getattr(cliente, "nome_completo", "")) or "Cliente senza nome",
            "subtitle": _subtitle(cliente),
            "type": tipo,
            "fiscalId": _fiscal_id(cliente) or "-",
            "email": email,
            "phone": phone,
            "pec": pec,
            "attorney": _text(getattr(cliente, "avvocato_referente", "")) or "-",
            "matters": matters_count,
            "activeMatters": active_count,
            "status": status,
            "missingFields": _missing_fields(cliente),
            "privacyOk": bool(getattr(cliente, "consenso_trattamento", False)),
            "documentExpired": _document_expired(cliente),
            "tags": [_text(tag) for tag in tags if _text(tag)],
            "lastUpdated": _text(getattr(cliente, "modificato_il", "") or getattr(cliente, "creato_il", "")),
            "href": f"/clienti/{item_id}",
            "editHref": f"/clienti/{item_id}/modifica",
            "folderHref": f"/clienti/{item_id}/cartella",
            "deleteHref": f"/clienti/{item_id}/elimina",
            "tone": _tone(status),
        })

    type_labels = {"pf": "Persone fisiche", "pg": "Persone giuridiche"}
    status_labels = {"attivo": "Attivi", "potenziale": "Potenziali", "archiviato": "Archiviati", "inattivo": "Inattivi"}
    return {
        "source": "repository_reali",
        "generated_at": _iso_now(),
        "contracts": {
            "mock_fallback": False,
            "read_only": False,
            "writes": "operational_routes",
            "route_owner": "react_shell",
        },
        "summary": _summary(items),
        "items": items,
        "facets": {"types": _facet_rows(items, "type", type_labels, "Tutti i tipi"), "statuses": _facet_rows(items, "status", status_labels, "Tutti gli stati")},
    }


def _fascicolo_archiviato(fascicolo: Any) -> bool:
    stato = getattr(fascicolo, "stato", None)
    raw = _enum_value(stato).lower()
    return bool(
        stato in {StatoFascicolo.ARCHIVIATO, StatoFascicolo.DEFINITO}
        or getattr(fascicolo, "archiviato", False)
        or "archiv" in raw
        or "definit" in raw
    )


def _matter_card(fascicolo: Any) -> dict[str, Any]:
    item_id = _text(getattr(fascicolo, "id", ""))
    tipo = _enum_label(getattr(fascicolo, "tipo", ""))
    stato = _enum_label(getattr(fascicolo, "stato", ""))
    numero_rg = _text(getattr(fascicolo, "numero_rg", ""))
    anno_rg = _text(getattr(fascicolo, "anno_rg", ""))
    rg = f"RG {numero_rg}/{anno_rg}" if numero_rg or anno_rg else ""
    tribunale = _text(getattr(fascicolo, "tribunale", ""))
    subtitle = " - ".join(part for part in [rg, tribunale, tipo] if part)
    return {
        "id": item_id,
        "title": _text(getattr(fascicolo, "titolo", "")) or _text(getattr(fascicolo, "numero", "")) or "Fascicolo",
        "subtitle": subtitle,
        "status": stato or "Aperto",
        "type": tipo,
        "counterparty": _text(getattr(fascicolo, "controparte", "")),
        "documents": int(getattr(fascicolo, "documenti_count", 0) or len(getattr(fascicolo, "documenti", []) or [])),
        "activities": int(getattr(fascicolo, "attivita_count", 0) or len(getattr(fascicolo, "attivita", []) or [])),
        "href": f"/fascicoli/{item_id}",
        "editHref": f"/fascicoli/{item_id}/modifica",
        "tone": "neutral" if _fascicolo_archiviato(fascicolo) else "primary",
    }


def _deadline_card(scadenza: Any, fascicolo: Any | None = None) -> dict[str, Any]:
    item_id = _text(getattr(scadenza, "id", ""))
    data = _text(getattr(scadenza, "data_scadenza", "") or getattr(scadenza, "data", ""))
    parsed = _parse_date(data)
    days = (parsed - date.today()).days if parsed else None
    raw_priority = _enum_value(getattr(scadenza, "priorita", "")).lower()
    tone = "danger" if days is not None and days < 0 else "warning" if raw_priority in {"alta", "critica"} else "primary"
    return {
        "id": item_id,
        "title": _text(getattr(scadenza, "titolo", "")) or "Scadenza",
        "subtitle": _text(getattr(scadenza, "descrizione", "")) or (_text(getattr(fascicolo, "titolo", "")) if fascicolo else ""),
        "date": _date_label(data),
        "days": days,
        "priority": _enum_label(getattr(scadenza, "priorita", "")),
        "status": _enum_label(getattr(scadenza, "stato", "")),
        "href": f"/scadenziario/{item_id}",
        "editHref": f"/scadenziario/{item_id}/modifica",
        "completeHref": f"/scadenziario/{item_id}/completa",
        "tone": tone,
    }


def _appointment_card(item: Any) -> dict[str, Any]:
    item_id = _text(getattr(item, "id", ""))
    when = _text(getattr(item, "data_ora", "") or getattr(item, "data", ""))
    return {
        "id": item_id,
        "title": _text(getattr(item, "titolo", "")) or "Appuntamento",
        "subtitle": " - ".join(part for part in [_text(getattr(item, "luogo", "")), _text(getattr(item, "tribunale", ""))] if part),
        "date": _date_label(when),
        "time": when[11:16] if len(when) >= 16 else "",
        "href": f"/agenda/{item_id}" if item_id else "/agenda",
        "tone": "primary",
    }


def _message_card(item: Any) -> dict[str, Any]:
    item_id = _text(getattr(item, "id", ""))
    canale = _enum_label(getattr(item, "canale", ""))
    stato = _enum_label(getattr(item, "stato", ""))
    return {
        "id": item_id,
        "title": _text(getattr(item, "oggetto", "")) or canale or "Comunicazione",
        "subtitle": _short(getattr(item, "corpo", ""), 140) or _text(getattr(item, "destinatario", "")),
        "date": _date_label(getattr(item, "creato_il", "")),
        "status": stato,
        "channel": canale,
        "href": f"/messaggi/{item_id}" if item_id else "/messaggi",
        "tone": "warning" if "Coda" in stato else "danger" if "Fallito" in stato else "neutral",
    }


def _quote_card(item: Any) -> dict[str, Any]:
    item_id = _text(getattr(item, "id", ""))
    total = getattr(item, "totale_documento", None)
    if total is None:
        total = getattr(item, "totale", 0.0)
    return {
        "id": item_id,
        "title": _text(getattr(item, "oggetto", "")) or _text(getattr(item, "numero", "")) or "Preventivo",
        "subtitle": _text(getattr(item, "numero", "")),
        "date": _date_label(getattr(item, "data_emissione", "")),
        "amount": _amount(total),
        "status": _enum_label(getattr(item, "stato", "")),
        "href": f"/preventivi/{item_id}",
        "tone": "success" if "Accett" in _enum_label(getattr(item, "stato", "")) else "primary",
    }


def _engagement_card(item: Any) -> dict[str, Any]:
    item_id = _text(getattr(item, "id", ""))
    return {
        "id": item_id,
        "title": _text(getattr(item, "oggetto", "")) or _text(getattr(item, "numero", "")) or "Conferimento incarico",
        "subtitle": _text(getattr(item, "numero", "")),
        "date": _date_label(getattr(item, "data_incarico", "")),
        "status": _enum_label(getattr(item, "stato", "")),
        "href": f"/preventivi/conferimenti/{item_id}",
        "tone": "success",
    }


def _invoice_card(item: Any) -> dict[str, Any]:
    item_id = _text(getattr(item, "id", ""))
    total = getattr(item, "netto_a_pagare", None)
    if total is None:
        total = getattr(item, "totale", 0.0)
    return {
        "id": item_id,
        "title": _text(getattr(item, "numero", "")) or "Parcella",
        "subtitle": _date_label(getattr(item, "data_emissione", "")),
        "amount": _amount(total),
        "status": _enum_label(getattr(item, "stato", "")),
        "href": f"/fatturazione/parcelle/{item_id}",
        "tone": "success" if "Pagata" in _enum_label(getattr(item, "stato", "")) else "warning",
    }


def _timeline_from_fascicoli(fascicoli: list[Any], limit: int = 12) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for fascicolo in fascicoli:
        fascicolo_id = _text(getattr(fascicolo, "id", ""))
        for attivita in getattr(fascicolo, "attivita", []) or []:
            rows.append({
                "id": f"{fascicolo_id}-{_text(getattr(attivita, 'id', 'attivita'))}",
                "title": _text(getattr(attivita, "titolo", "")) or _text(getattr(attivita, "descrizione", "")) or "Attivita",
                "subtitle": _text(getattr(fascicolo, "titolo", "")),
                "date": _date_label(getattr(attivita, "data", "")),
                "href": f"/fascicoli/{fascicolo_id}",
                "tone": "neutral",
            })
    return sorted(rows, key=lambda row: row.get("date") or "", reverse=True)[:limit]


def build_react_cliente_cartella_payload(
    *,
    get_clienti: Callable[[], Any],
    get_fascicoli: Callable[[], Any],
    get_agenda: Callable[[], Any],
    get_messaggi: Callable[[], Any],
    get_scadenziario: Callable[[], Any],
    get_preventivi: Callable[[], Any],
    get_fatturazione: Callable[[], Any],
    id_cliente: str,
) -> dict[str, Any]:
    cliente = get_clienti().get(id_cliente)
    if not cliente:
        raise KeyError(id_cliente)

    fascicoli = _safe("fascicoli cliente", lambda: get_fascicoli().cerca(id_cliente=id_cliente, archiviati=True), [])
    fascicoli_attivi = [item for item in fascicoli if not _fascicolo_archiviato(item)]
    fascicoli_archiviati = [item for item in fascicoli if _fascicolo_archiviato(item)]
    fascicoli_by_id = {_text(getattr(item, "id", "")): item for item in fascicoli}
    fascicolo_ids = {item_id for item_id in fascicoli_by_id if item_id}

    scadenze = _safe(
        "scadenze cliente",
        lambda: [item for item in get_scadenziario().tutte(solo_aperte=False) if _text(getattr(item, "id_fascicolo", "")) in fascicolo_ids],
        [],
    )
    scadenze_aperte = [item for item in scadenze if getattr(item, "stato", None) == StatoTermine.APERTO]
    scadenze_scadute = [item for item in scadenze_aperte if (_parse_date(getattr(item, "data_scadenza", "")) or date.max) < date.today()]
    appuntamenti = _safe(
        "appuntamenti cliente",
        lambda: get_agenda().per_cliente(id_cliente) or get_agenda().cerca(cliente=getattr(cliente, "nome_completo", "")),
        [],
    )
    messaggi = _safe("messaggi cliente", lambda: get_messaggi().per_cliente(id_cliente), [])
    preventivi = _safe("preventivi cliente", lambda: get_preventivi().preventivi_per_cliente(id_cliente), [])
    conferimenti = _safe("conferimenti cliente", lambda: get_preventivi().conferimenti_per_cliente(id_cliente), [])
    parcelle = _safe("parcelle cliente", lambda: get_fatturazione().per_cliente(id_cliente), [])
    phone, email, pec = _recapiti(cliente)

    return {
        "source": "repository_reali",
        "generated_at": _iso_now(),
        "contracts": {
            "mock_fallback": False,
            "read_only": False,
            "writes": "operational_routes",
            "route_owner": "react_shell",
        },
        "cliente": {
            "id": id_cliente,
            "name": _text(getattr(cliente, "nome_completo", "")) or "Cliente senza nome",
            "subtitle": _subtitle(cliente),
            "type": _type(cliente),
            "status": _status(cliente),
            "fiscalId": _fiscal_id(cliente),
            "phone": phone,
            "email": email,
            "pec": pec,
            "attorney": _text(getattr(cliente, "avvocato_referente", "")) or "-",
            "privacyOk": bool(getattr(cliente, "consenso_trattamento", False)),
            "missingFields": _missing_fields(cliente),
            "documentExpired": _document_expired(cliente),
            "href": f"/clienti/{id_cliente}",
            "editHref": f"/clienti/{id_cliente}/modifica",
            "folderHref": f"/clienti/{id_cliente}/cartella",
        },
        "summary": {
            "activeMatters": len(fascicoli_attivi),
            "archivedMatters": len(fascicoli_archiviati),
            "documents": sum(int(getattr(item, "documenti_count", 0) or len(getattr(item, "documenti", []) or [])) for item in fascicoli),
            "deadlines": len(scadenze_aperte),
            "overdueDeadlines": len(scadenze_scadute),
            "appointments": len(appuntamenti),
            "messages": len(messaggi),
            "quotes": len(preventivi),
            "engagements": len(conferimenti),
            "invoices": len(parcelle),
        },
        "matters": {
            "active": [_matter_card(item) for item in fascicoli_attivi],
            "archived": [_matter_card(item) for item in fascicoli_archiviati[:12]],
        },
        "deadlines": [_deadline_card(item, fascicoli_by_id.get(_text(getattr(item, "id_fascicolo", "")))) for item in scadenze_aperte[:12]],
        "appointments": [_appointment_card(item) for item in appuntamenti[:8]],
        "messages": [_message_card(item) for item in messaggi[:8]],
        "quotes": [_quote_card(item) for item in preventivi[:8]],
        "engagements": [_engagement_card(item) for item in conferimenti[:8]],
        "invoices": [_invoice_card(item) for item in parcelle[:8]],
        "timeline": _timeline_from_fascicoli(fascicoli),
        "actions": {
            "editClient": f"/clienti/{id_cliente}/modifica",
            "newMatter": f"/fascicoli/nuovo?id_cliente={id_cliente}",
            "newDeadline": f"/scadenziario/nuova?id_cliente={id_cliente}&from_cliente=cartella",
            "newAppointment": f"/agenda/nuovo?id_cliente={id_cliente}",
            "newMessage": f"/messaggi/nuovo?id_cliente={id_cliente}",
            "newQuote": f"/preventivi/nuovo?id_cliente={id_cliente}",
            "folder": f"/clienti/{id_cliente}/cartella",
            "dossier": f"/clienti/{id_cliente}/faldone",
            "exportFolder": f"/clienti/{id_cliente}/esporta",
        },
    }


def _option(value: Any, *, label: str = "", subtitle: str = "", tone: str = "neutral", count: int | None = None) -> dict[str, Any]:
    raw = _enum_value(value)
    payload: dict[str, Any] = {
        "value": raw,
        "label": label or raw.replace("_", " ").title(),
        "tone": tone,
    }
    if subtitle:
        payload["subtitle"] = subtitle
    if count is not None:
        payload["count"] = count
    return payload


def _subject_type_tone(value: TipoSoggetto) -> str:
    return {
        TipoSoggetto.PERSONA_FISICA: "primary",
        TipoSoggetto.PERSONA_GIURIDICA: "purple",
        TipoSoggetto.PUBBLICA_AMMINISTRAZIONE: "info",
        TipoSoggetto.ENTE: "neutral",
        TipoSoggetto.CONDOMINIO: "orange",
        TipoSoggetto.ASSOCIAZIONE: "success",
        TipoSoggetto.PROFESSIONISTA: "primary",
    }.get(value, "neutral")


def _role_tone(value: RuoloSoggetto) -> str:
    return {
        RuoloSoggetto.ASSISTITO: "success",
        RuoloSoggetto.CONTROPARTE: "danger",
        RuoloSoggetto.DIFENSORE_CONTROPARTE: "danger",
        RuoloSoggetto.TESTIMONE: "warning",
        RuoloSoggetto.PERITO_CTP: "info",
        RuoloSoggetto.PERITO_CTU: "info",
        RuoloSoggetto.CORRISPONDENTE: "primary",
        RuoloSoggetto.NOTAIO: "purple",
        RuoloSoggetto.MEDIATORE: "success",
        RuoloSoggetto.GARANTE: "warning",
        RuoloSoggetto.INTERVENIENTE: "info",
        RuoloSoggetto.CREDITORE: "primary",
        RuoloSoggetto.DEBITORE: "danger",
    }.get(value, "neutral")


def _client_options(clienti: list[Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for cliente in clienti:
        recapiti = getattr(cliente, "recapiti", None)
        item_id = _text(getattr(cliente, "id", ""))
        if not item_id:
            continue
        rows.append({
            "id": item_id,
            "label": _text(getattr(cliente, "nome_completo", "")) or "Cliente senza nome",
            "taxCode": _fiscal_id(cliente),
            "email": _text(getattr(recapiti, "email", "")),
            "type": _enum_value(getattr(cliente, "tipo", "")),
        })
    return rows


def _clienti_nuovo_stats(clienti: list[Any], soggetti: list[Any]) -> dict[str, int]:
    soggetti_operativi = [item for item in soggetti if not soggetto_coincide_con_cliente(item, clienti)]
    return {
        "totalClients": len(clienti),
        "physicalClients": sum(1 for item in clienti if getattr(item, "tipo", None) == TipoCliente.PERSONA_FISICA),
        "legalClients": sum(1 for item in clienti if getattr(item, "tipo", None) == TipoCliente.PERSONA_GIURIDICA),
        "activeClients": sum(1 for item in clienti if getattr(item, "stato", None) == StatoCliente.ATTIVO),
        "potentialClients": sum(1 for item in clienti if getattr(item, "stato", None) == StatoCliente.POTENZIALE),
        "missingRegistry": sum(1 for item in clienti if _missing_fields(item)),
        "expiredDocuments": sum(1 for item in clienti if _document_expired(item)),
        "totalSubjects": len(soggetti_operativi),
        "subjectsWithoutClient": sum(1 for item in soggetti_operativi if not _text(getattr(item, "id_cliente", ""))),
    }


def _indirizzo_values(cliente: Any, attr: str, prefix: str = "") -> dict[str, str]:
    indirizzi = getattr(cliente, "indirizzi", {}) or {}
    address = indirizzi.get(attr) if isinstance(indirizzi, dict) else getattr(indirizzi, attr, None)
    if address is None:
        address = getattr(cliente, attr, None)
    if address is None:
        address = getattr(cliente, f"indirizzo_{attr}", None)
    return {
        f"{prefix}via": _text(getattr(address, "via", "")),
        f"{prefix}civico": _text(getattr(address, "civico", "")),
        f"{prefix}cap": _text(getattr(address, "cap", "")),
        f"{prefix}comune": _text(getattr(address, "comune", "")),
        f"{prefix}provincia": _text(getattr(address, "provincia", "")),
        f"{prefix}nazione": _text(getattr(address, "nazione", "")) or "Italia",
    }


def _cliente_form_values(cliente: Any) -> dict[str, Any]:
    recapiti = getattr(cliente, "recapiti", None)
    documento = getattr(cliente, "documento", None)
    values: dict[str, Any] = {
        "tipo": _enum_value(getattr(cliente, "tipo", "")) or TipoCliente.PERSONA_FISICA.value,
        "nome": _text(getattr(cliente, "nome", "")),
        "cognome": _text(getattr(cliente, "cognome", "")),
        "ragione_sociale": _text(getattr(cliente, "ragione_sociale", "")),
        "codice_fiscale": _text(getattr(cliente, "codice_fiscale", "")),
        "partita_iva": _text(getattr(cliente, "partita_iva", "")),
        "forma_giuridica": _text(getattr(cliente, "forma_giuridica", "")),
        "data_nascita": _text(getattr(cliente, "data_nascita", "")),
        "luogo_nascita": _text(getattr(cliente, "luogo_nascita", "")),
        "provincia_nascita": _text(getattr(cliente, "provincia_nascita", "")),
        "sesso": _text(getattr(cliente, "sesso", "")),
        "nazionalita": _text(getattr(cliente, "nazionalita", "")) or "Italiana",
        "rappresentante_legale": _text(getattr(cliente, "rappresentante_legale", "")),
        "cf_rappresentante": _text(getattr(cliente, "cf_rappresentante", "")),
        "telefono": _text(getattr(recapiti, "telefono", "")),
        "cellulare": _text(getattr(recapiti, "cellulare", "")),
        "email": _text(getattr(recapiti, "email", "")),
        "pec": _text(getattr(recapiti, "pec", "")),
        "fax": _text(getattr(recapiti, "fax", "")),
        "sito_web": _text(getattr(recapiti, "sito_web", "")),
        "doc_tipo": _enum_value(getattr(documento, "tipo", "")) or TipoDocumento.CARTA_IDENTITA.value,
        "doc_numero": _text(getattr(documento, "numero", "")),
        "doc_rilasciato_da": _text(getattr(documento, "rilasciato_da", "")),
        "doc_data_rilascio": _text(getattr(documento, "data_rilascio", "")),
        "doc_data_scadenza": _text(getattr(documento, "data_scadenza", "")),
        "avvocato_referente": _text(getattr(cliente, "avvocato_referente", "")),
        "provenienza": _text(getattr(cliente, "provenienza", "")),
        "note": _text(getattr(cliente, "note", "")),
        "stato": _enum_value(getattr(cliente, "stato", "")) or StatoCliente.ATTIVO.value,
        "crea_preventivo_iniziale": False,
    }
    values.update(_indirizzo_values(cliente, "residenza"))
    values.update(_indirizzo_values(cliente, "domicilio", "dom_"))
    values.update(_indirizzo_values(cliente, "sede_legale", "sl_"))
    return values


def _soggetto_form_values(soggetto: Any) -> dict[str, str]:
    indirizzo = getattr(soggetto, "indirizzo", None)
    recapiti = getattr(soggetto, "recapiti", None)
    return {
        "tipo": _enum_value(getattr(soggetto, "tipo", "PERSONA_FISICA")) or "PERSONA_FISICA",
        "nome": _text(getattr(soggetto, "nome", "")),
        "cognome": _text(getattr(soggetto, "cognome", "")),
        "ragione_sociale": _text(getattr(soggetto, "ragione_sociale", "")),
        "codice_fiscale": _text(getattr(soggetto, "codice_fiscale", "")),
        "partita_iva": _text(getattr(soggetto, "partita_iva", "")),
        "forma_giuridica": _text(getattr(soggetto, "forma_giuridica", "")),
        "data_nascita": _text(getattr(soggetto, "data_nascita", "")),
        "luogo_nascita": _text(getattr(soggetto, "luogo_nascita", "")),
        "provincia_nascita": _text(getattr(soggetto, "provincia_nascita", "")),
        "sesso": _text(getattr(soggetto, "sesso", "")),
        "rappresentante_legale": _text(getattr(soggetto, "rappresentante_legale", "")),
        "qualifica": _text(getattr(soggetto, "qualifica", "CONTROPARTE")) or "CONTROPARTE",
        "ordine": _text(getattr(soggetto, "ordine", "")),
        "numero_iscrizione": _text(getattr(soggetto, "numero_iscrizione", "")),
        "id_cliente": _text(getattr(soggetto, "id_cliente", "")),
        "telefono": _text(getattr(recapiti, "telefono", "")),
        "cellulare": _text(getattr(recapiti, "cellulare", "")),
        "email": _text(getattr(recapiti, "email", "")),
        "pec": _text(getattr(recapiti, "pec", "")),
        "fax": _text(getattr(recapiti, "fax", "")),
        "sito_web": _text(getattr(recapiti, "sito_web", "")),
        "via": _text(getattr(indirizzo, "via", "")),
        "civico": _text(getattr(indirizzo, "civico", "")),
        "cap": _text(getattr(indirizzo, "cap", "")),
        "comune": _text(getattr(indirizzo, "comune", "")),
        "provincia": _text(getattr(indirizzo, "provincia", "")),
        "nazione": _text(getattr(indirizzo, "nazione", "Italia")) or "Italia",
        "note": _text(getattr(soggetto, "note", "")),
        "tag": ", ".join(str(item) for item in (getattr(soggetto, "tag", None) or []) if str(item).strip()),
    }


def _subject_role_from_query(query: Mapping[str, Any]) -> str:
    raw = _text(query.get("ruolo") or query.get("qualifica") or query.get("ruolo_soggetto"))
    normalized = raw.replace("-", "_").replace(" ", "_").upper()
    if not normalized:
        return ""
    try:
        return RuoloSoggetto(normalized).value
    except ValueError:
        return ""


def build_react_clienti_nuovo_payload(
    *,
    get_clienti: Callable[[], Any],
    get_soggetti: Callable[[], Any],
    query: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    clienti = _safe("clienti", lambda: get_clienti().tutti(), [])
    soggetti = _safe("soggetti", lambda: get_soggetti().tutti(), [])
    query = query or {}
    id_fascicolo = _text(query.get("id_fascicolo") or query.get("fascicolo") or query.get("case_id"))
    ruolo_soggetto = _subject_role_from_query(query) or ("CONTROPARTE" if id_fascicolo else "")
    next_url = _safe_internal_path(query.get("next_url") or query.get("next"))
    if id_fascicolo and not next_url:
        next_url = f"/fascicoli/{id_fascicolo}/modifica"
    tab = _text(query.get("tab") or query.get("tipo"))
    if id_fascicolo and not tab:
        tab = "soggetto"
    payload = {
        "source": "repository_reali",
        "generated_at": _iso_now(),
        "contracts": {
            "mock_fallback": False,
            "read_only": False,
            "writes": "operational_routes",
            "route_owner": "react_shell",
        },
        "stats": _clienti_nuovo_stats(clienti, soggetti),
        "options": {
            "clientTypes": [
                _option(TipoCliente.PERSONA_FISICA, label="Persona fisica", subtitle="Privato, professionista o assistito", tone="primary"),
                _option(TipoCliente.PERSONA_GIURIDICA, label="Persona giuridica", subtitle="Società, ente o organizzazione", tone="purple"),
            ],
            "clientStatuses": [_option(item, tone={"ATTIVO": "success", "POTENZIALE": "warning", "INATTIVO": "orange"}.get(item.value, "neutral")) for item in StatoCliente],
            "documentTypes": [_option(item) for item in TipoDocumento],
            "cieGenerations": [
                {"value": "elettronica", "label": "Elettronica dal 2016 con MRZ", "tone": "primary"},
                {"value": "plastificata", "label": "Plastificata 2000-2016", "tone": "neutral"},
                {"value": "cartacea", "label": "Cartacea pre-2000", "tone": "neutral"},
            ],
            "subjectTypes": [_option(item, tone=_subject_type_tone(item)) for item in TipoSoggetto],
            "subjectRoles": [_option(item, label=item.label, tone=_role_tone(item)) for item in RuoloSoggetto],
            "legalForms": [
                {"value": "", "label": "-"},
                *[{"value": item, "label": item} for item in ["Srl", "SpA", "Sas", "Snc", "Ss", "Impresa individuale", "Cooperativa", "Associazione", "Fondazione", "Ente pubblico", "Altro"]],
            ],
            "qualificationHints": [{"value": item, "label": item} for item in ["Avvocato", "Procuratore", "Notaio", "Geometra", "Ingegnere", "Architetto", "Medico", "Perito industriale", "Commercialista", "Consulente del lavoro", "Mediatore", "Curatore fallimentare", "Liquidatore", "Magistrato", "Pubblico Ministero"]],
        },
        "clientOptions": _client_options(clienti),
        "actions": {
            "newClient": "/clienti/nuovo",
            "newSubject": "/soggetti/nuovo",
            "clientsList": "/clienti",
            "subjectsList": "/soggetti",
            "operationalClientForm": "/clienti/nuovo",
            "operationalSubjectForm": "/soggetti/nuovo",
            "documentReader": "/api/v1/ui/clienti/nuovo/documento/leggi",
        },
        "query": {
            "tab": tab,
            "nextUrl": next_url,
            "idCliente": _text(query.get("id_cliente")),
            "idFascicolo": id_fascicolo,
            "ruoloSoggetto": ruolo_soggetto,
        },
        "initialSubject": {"qualifica": ruolo_soggetto} if ruolo_soggetto else {},
        "insights": [
            "Prima del salvataggio controlla CF/P.IVA per prevenire duplicati.",
            "Per il conferimento incarico servono dati fiscali, recapiti e indirizzo.",
            "Il soggetto processuale resta separato dai clienti: assistiti e clienti si gestiscono in Clienti e anagrafiche.",
        ],
    }
    return payload


def build_react_cliente_modifica_payload(
    *,
    get_clienti: Callable[[], Any],
    get_soggetti: Callable[[], Any],
    id_cliente: str,
    query: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = build_react_clienti_nuovo_payload(get_clienti=get_clienti, get_soggetti=get_soggetti, query=query)
    cliente = get_clienti().get(id_cliente)
    if not cliente:
        raise KeyError(id_cliente)
    payload["mode"] = "edit"
    payload["initialClient"] = _cliente_form_values(cliente)
    payload["actions"]["operationalClientForm"] = f"/clienti/{id_cliente}/modifica"
    payload["actions"]["clientsList"] = f"/clienti/{id_cliente}/cartella"
    payload["query"]["idCliente"] = id_cliente
    payload["insights"] = [
        "Stai modificando l'anagrafica reale: i collegamenti a fascicoli, preventivi e conferimenti restano sullo stesso id cliente.",
        "Completa recapiti, documento e indirizzo prima di generare o firmare il conferimento incarico.",
        "Salvataggio, fascicoli collegati e ricerca restano agganciati agli archivi operativi dello studio.",
    ]
    return payload


def build_react_soggetto_modifica_payload(
    *,
    get_clienti: Callable[[], Any],
    get_soggetti: Callable[[], Any],
    id_soggetto: str,
    query: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = build_react_clienti_nuovo_payload(get_clienti=get_clienti, get_soggetti=get_soggetti, query=query)
    soggetto = get_soggetti().get(id_soggetto)
    if not soggetto:
        raise KeyError(id_soggetto)
    payload["mode"] = "edit_subject"
    payload["initialSubject"] = _soggetto_form_values(soggetto)
    payload["actions"]["operationalSubjectForm"] = f"/soggetti/{id_soggetto}/modifica"
    payload["actions"]["subjectsList"] = f"/soggetti/{id_soggetto}"
    payload["query"]["tab"] = "soggetto"
    payload["query"]["idSoggetto"] = id_soggetto
    payload["insights"] = [
        "Stai modificando un soggetto o una parte processuale reale: i collegamenti ai fascicoli restano sullo stesso id.",
        "Ruolo, recapiti, identificativo fiscale e collegamento cliente alimentano Ricerca Studio e schede fascicolo.",
        "Salvataggio, collegamenti e ricerca restano agganciati agli archivi operativi dello studio.",
    ]
    return payload
