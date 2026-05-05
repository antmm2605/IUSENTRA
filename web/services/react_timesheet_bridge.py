"""Bridge JSON reale per la superficie React Timesheet."""

from __future__ import annotations

from datetime import date
from typing import Any, Callable

from pct.economic_pipeline import build_timesheet_billing_summary
from pct.timesheet import StatoTimesheet
from web.services.ui_localization import format_date, parse_temporal_value


STATUS_LABELS = {
    StatoTimesheet.APERTO.value: "Aperta",
    StatoTimesheet.VALIDATO.value: "Validata",
    StatoTimesheet.FATTURATO.value: "Fatturata",
    StatoTimesheet.ANNULLATO.value: "Annullata",
}

STATUS_TONES = {
    StatoTimesheet.APERTO.value: "warning",
    StatoTimesheet.VALIDATO.value: "success",
    StatoTimesheet.FATTURATO.value: "primary",
    StatoTimesheet.ANNULLATO.value: "neutral",
}


def _safe_text(value: Any, fallback: str = "") -> str:
    text = str(value or "").strip()
    return text or fallback


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "").strip()


def _money(value: Any) -> str:
    amount = float(value or 0.0)
    text = f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"EUR {text}"


def _hours_label(minutes: Any) -> str:
    total = int(minutes or 0)
    hours, mins = divmod(total, 60)
    if hours and mins:
        return f"{hours} h {mins} min"
    if hours:
        return f"{hours} h"
    return f"{mins} min"


def _date_in_range(value: Any, start: str, end: str) -> bool:
    parsed = parse_temporal_value(value)
    if not parsed:
        return not start and not end
    if start:
        start_parsed = parse_temporal_value(start)
        if start_parsed and parsed.date_value < start_parsed.date_value:
            return False
    if end:
        end_parsed = parse_temporal_value(end)
        if end_parsed and parsed.date_value > end_parsed.date_value:
            return False
    return True


def _cliente_label(cliente: Any | None, fallback: str = "") -> str:
    return _safe_text(getattr(cliente, "nome_completo", ""), fallback)


def _fascicolo_label(fascicolo: Any | None, fallback: str = "") -> str:
    if not fascicolo:
        return fallback
    numero = _safe_text(getattr(fascicolo, "numero", ""))
    titolo = _safe_text(getattr(fascicolo, "titolo", ""))
    return " - ".join(part for part in [numero, titolo] if part) or fallback


def _options_clienti(clienti_manager: Any) -> list[dict[str, str]]:
    try:
        clienti = clienti_manager.tutti(stato=None)
    except TypeError:
        clienti = clienti_manager.tutti()
    return [
        {
            "id": _safe_text(getattr(cliente, "id", "")),
            "label": _cliente_label(cliente, "Cliente senza nome"),
            "href": f"/clienti/{getattr(cliente, 'id', '')}",
        }
        for cliente in clienti
        if _safe_text(getattr(cliente, "id", ""))
    ]


def _options_fascicoli(fascicoli_manager: Any) -> list[dict[str, str]]:
    try:
        fascicoli = fascicoli_manager.tutti(stato=None)
    except TypeError:
        fascicoli = fascicoli_manager.tutti()
    return [
        {
            "id": _safe_text(getattr(fascicolo, "id", "")),
            "label": _fascicolo_label(fascicolo, "Fascicolo senza titolo"),
            "idCliente": _safe_text(getattr(fascicolo, "id_cliente", "")),
            "href": f"/fascicoli/{getattr(fascicolo, 'id', '')}",
        }
        for fascicolo in fascicoli
        if _safe_text(getattr(fascicolo, "id", ""))
    ]


def _entry_payload(entry: Any, clienti_by_id: dict[str, Any], fascicoli_by_id: dict[str, Any]) -> dict[str, Any]:
    entry_id = _safe_text(getattr(entry, "id", ""))
    id_cliente = _safe_text(getattr(entry, "id_cliente", ""))
    id_fascicolo = _safe_text(getattr(entry, "id_fascicolo", ""))
    cliente = clienti_by_id.get(id_cliente)
    fascicolo = fascicoli_by_id.get(id_fascicolo)
    status = _enum_value(getattr(entry, "stato", StatoTimesheet.APERTO.value)) or StatoTimesheet.APERTO.value
    data = _safe_text(getattr(entry, "data_attivita", ""))
    minuti = int(getattr(entry, "minuti", 0) or 0)
    valore_unitario = float(getattr(entry, "valore_unitario", 0.0) or 0.0)
    valore_totale = float(getattr(entry, "valore_totale", 0.0) or 0.0)
    dati_json = getattr(entry, "dati_json", {}) if isinstance(getattr(entry, "dati_json", {}), dict) else {}
    return {
        "id": entry_id,
        "date": data,
        "dateLabel": format_date(data),
        "description": _safe_text(getattr(entry, "descrizione", ""), "Attivita senza descrizione"),
        "idCliente": id_cliente,
        "clientName": _cliente_label(cliente, "Cliente non collegato" if not id_cliente else id_cliente),
        "clientHref": f"/clienti/{id_cliente}" if id_cliente else "",
        "idFascicolo": id_fascicolo,
        "fascicoloLabel": _fascicolo_label(fascicolo, "Fascicolo non collegato" if not id_fascicolo else id_fascicolo),
        "fascicoloHref": f"/fascicoli/{id_fascicolo}" if id_fascicolo else "",
        "user": _safe_text(getattr(entry, "username", "") or getattr(entry, "id_utente", ""), "Operatore"),
        "minutes": minuti,
        "hours": float(getattr(entry, "ore", 0.0) or round(minuti / 60.0, 2)),
        "hoursLabel": _hours_label(minuti),
        "hourlyRate": valore_unitario,
        "hourlyRateLabel": _money(valore_unitario),
        "totalValue": valore_totale,
        "totalValueLabel": _money(valore_totale),
        "billable": bool(getattr(entry, "fatturabile", False)),
        "billableLabel": "Fatturabile" if getattr(entry, "fatturabile", False) else "Interna",
        "status": status,
        "statusLabel": STATUS_LABELS.get(status, status),
        "statusTone": STATUS_TONES.get(status, "neutral"),
        "origin": _safe_text(getattr(entry, "origine", "")),
        "notes": _safe_text(getattr(entry, "note", "")),
        "context": _safe_text(dati_json.get("contesto", "")),
        "stateAction": f"/timesheet/{entry_id}/stato",
        "eligibleForInvoice": bool(getattr(entry, "fatturabile", False)) and status == StatoTimesheet.VALIDATO.value,
    }


def _filter_entries(entries: list[Any], filters: dict[str, str]) -> list[Any]:
    query = filters["q"].lower()
    filtered: list[Any] = []
    for entry in entries:
        if filters["id_cliente"] and _safe_text(getattr(entry, "id_cliente", "")) != filters["id_cliente"]:
            continue
        if filters["id_fascicolo"] and _safe_text(getattr(entry, "id_fascicolo", "")) != filters["id_fascicolo"]:
            continue
        if filters["stato"] and _enum_value(getattr(entry, "stato", "")) != filters["stato"]:
            continue
        if filters["utente"]:
            user = _safe_text(getattr(entry, "username", "") or getattr(entry, "id_utente", ""))
            if user != filters["utente"]:
                continue
        if not _date_in_range(getattr(entry, "data_attivita", ""), filters["data_da"], filters["data_a"]):
            continue
        if query:
            haystack = " ".join(
                [
                    _safe_text(getattr(entry, "descrizione", "")),
                    _safe_text(getattr(entry, "note", "")),
                    _safe_text(getattr(entry, "origine", "")),
                    _safe_text(getattr(entry, "username", "")),
                    _safe_text(getattr(entry, "id_cliente", "")),
                    _safe_text(getattr(entry, "id_fascicolo", "")),
                ]
            ).lower()
            if query not in haystack:
                continue
        filtered.append(entry)
    return filtered


def build_react_timesheet_payload(
    *,
    get_timesheet: Callable[[], Any],
    get_clienti: Callable[[], Any],
    get_fascicoli: Callable[[], Any],
    query: dict[str, Any] | None = None,
) -> dict[str, Any]:
    params = query or {}
    filters = {
        "id_cliente": _safe_text(params.get("id_cliente")),
        "id_fascicolo": _safe_text(params.get("id_fascicolo")),
        "stato": _safe_text(params.get("stato")),
        "utente": _safe_text(params.get("utente")),
        "q": _safe_text(params.get("q") or params.get("ricerca")),
        "data_da": _safe_text(params.get("data_da") or params.get("dal")),
        "data_a": _safe_text(params.get("data_a") or params.get("al")),
    }
    timesheet = get_timesheet()
    clienti_manager = get_clienti()
    fascicoli_manager = get_fascicoli()
    all_entries = list(timesheet.tutte())
    entries = _filter_entries(all_entries, filters)

    clienti_options = _options_clienti(clienti_manager)
    fascicoli_options = _options_fascicoli(fascicoli_manager)
    clienti_by_id = {item["id"]: clienti_manager.get(item["id"]) for item in clienti_options}
    fascicoli_by_id = {item["id"]: fascicoli_manager.get(item["id"]) for item in fascicoli_options}
    users = sorted(
        {
            _safe_text(getattr(entry, "username", "") or getattr(entry, "id_utente", ""))
            for entry in all_entries
            if _safe_text(getattr(entry, "username", "") or getattr(entry, "id_utente", ""))
        }
    )
    billing_summary = build_timesheet_billing_summary(entries)
    stats = timesheet.statistiche(entries)
    return {
        "source": "repository_reali",
        "generatedAt": date.today().isoformat(),
        "contracts": {
            "mock_fallback": False,
            "writes": "operational_routes",
            "route_owner": "react_shell",
        },
        "filters": filters,
        "summary": {
            "totalEntries": int(stats.get("totale_voci") or 0),
            "totalMinutes": int(stats.get("totale_minuti") or 0),
            "totalHours": float(stats.get("totale_ore") or 0.0),
            "totalHoursLabel": _hours_label(stats.get("totale_minuti") or 0),
            "totalValue": float(stats.get("valore_totale") or 0.0),
            "totalValueLabel": _money(stats.get("valore_totale") or 0.0),
            "open": int(stats.get("aperte") or 0),
            "validated": int(stats.get("validate") or 0),
            "invoiced": int(stats.get("fatturate") or 0),
            "billable": int(stats.get("fatturabili") or 0),
            "notBillable": int(stats.get("non_fatturabili") or 0),
        },
        "entries": [_entry_payload(entry, clienti_by_id, fascicoli_by_id) for entry in entries],
        "options": {
            "clients": clienti_options,
            "matters": fascicoli_options,
            "statuses": [
                {
                    "value": status.value,
                    "label": STATUS_LABELS.get(status.value, status.value),
                    "tone": STATUS_TONES.get(status.value, "neutral"),
                }
                for status in StatoTimesheet
            ],
            "users": [{"value": user, "label": user} for user in users],
        },
        "billing": {
            "ready": bool(billing_summary.get("ready")),
            "issues": list(billing_summary.get("issues") or []),
            "count": int(billing_summary.get("count") or 0),
            "hours": float(billing_summary.get("ore_totali") or 0.0),
            "hoursLabel": _hours_label(round(float(billing_summary.get("ore_totali") or 0.0) * 60)),
            "value": float(billing_summary.get("valore_totale") or 0.0),
            "valueLabel": _money(billing_summary.get("valore_totale") or 0.0),
            "entryIds": list(billing_summary.get("entry_ids") or []),
            "idCliente": _safe_text(billing_summary.get("id_cliente")),
            "idFascicolo": _safe_text(billing_summary.get("id_fascicolo")),
            "nextAction": _safe_text(billing_summary.get("next_action")),
            "action": "/timesheet/genera-parcella",
        },
        "actions": {
            "create": "/timesheet/nuovo",
            "billing": "/fatturazione/",
            "statistics": "/statistiche/?view=produttivita",
            "agenda": "/agenda",
            "clients": "/clienti",
            "matters": "/fascicoli",
            "lex": "/lex?context=timesheet",
        },
        "emptyStates": {
            "noEntries": not all_entries,
            "noFilteredEntries": bool(all_entries) and not entries,
            "noValidableEntries": not any(_enum_value(getattr(entry, "stato", "")) == StatoTimesheet.APERTO.value for entry in entries),
            "noBillableEntries": not billing_summary.get("ready"),
        },
    }
