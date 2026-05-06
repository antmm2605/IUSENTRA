"""Bridge read-only per la superficie React preventivi e incarichi."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _enum(value: Any) -> str:
    return _text(getattr(value, "value", value))


def _money(value: Any) -> str:
    try:
        amount = float(value or 0)
    except (TypeError, ValueError):
        amount = 0.0
    return f"EUR {amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _date_label(value: Any) -> str:
    raw = _text(value)
    if not raw:
        return ""
    try:
        parsed = date.fromisoformat(raw[:10])
        return parsed.strftime("%d/%m/%Y")
    except ValueError:
        return raw[:10]


def _status_tone(status: str) -> str:
    return {
        "BOZZA": "warning",
        "IN_CALCOLO": "info",
        "GENERATO": "primary",
        "VERIFICATO": "info",
        "INVIATO": "primary",
        "APERTO": "warning",
        "ACCETTATO": "success",
        "RIFIUTATO": "danger",
        "SCADUTO": "danger",
        "REVISIONATO": "neutral",
        "CONVERTITO": "success",
        "ATTIVO": "success",
        "DEFINITO": "neutral",
        "REVOCATO": "danger",
    }.get(status.upper(), "neutral")


def _status_label(status: str) -> str:
    return {
        "BOZZA": "Bozza",
        "IN_CALCOLO": "In preparazione",
        "GENERATO": "Generato",
        "VERIFICATO": "Verificato",
        "INVIATO": "Inviato",
        "APERTO": "Aperto",
        "ACCETTATO": "Accettato",
        "RIFIUTATO": "Rifiutato",
        "SCADUTO": "Scaduto",
        "REVISIONATO": "Revisionato",
        "CONVERTITO": "Convertito",
        "ATTIVO": "Attivo",
        "DEFINITO": "Definito",
        "REVOCATO": "Revocato",
    }.get(status.upper(), status or "Non indicato")


def _metric(mid: str, label: str, value: Any, note: str, tone: str) -> dict[str, Any]:
    return {"id": mid, "label": label, "value": value, "note": note, "tone": tone}


def _item(iid: str, label: str, value: Any, note: str = "", tone: str = "neutral") -> dict[str, Any]:
    return {"id": iid, "label": label, "value": value, "note": note, "tone": tone}


def _section(sid: str, title: str, kind: str, items: list[dict[str, Any]], empty: str) -> dict[str, Any]:
    return {"id": sid, "title": title, "kind": kind, "items": items, "emptyMessage": empty}


def _action(aid: str, label: str, href: str, tone: str = "neutral") -> dict[str, Any]:
    return {"id": aid, "label": label, "href": href, "method": "GET", "tone": tone}


def _option(value: Any, label: str, description: str = "") -> dict[str, Any]:
    return {
        "value": _text(value),
        "label": label,
        "description": description,
        "enabled": True,
    }


def _safe_all(loader: Callable[[], Any], method: str, warnings: list[dict[str, str]], label: str) -> list[Any]:
    try:
        manager = loader()
        func = getattr(manager, method, None)
        if callable(func):
            return list(func())
    except Exception as exc:
        warnings.append({
            "code": f"{label}_non_disponibile",
            "message": f"Sorgente {label} non disponibile: {type(exc).__name__}.",
        })
    return []


def _client_label(cliente: Any) -> str:
    return (
        _text(getattr(cliente, "nome_completo", ""))
        or _text(getattr(cliente, "denominazione", ""))
        or _text(getattr(cliente, "nome", ""))
        or "Cliente non indicato"
    )


def _case_label(fascicolo: Any) -> str:
    title = _text(getattr(fascicolo, "titolo", "")) or _text(getattr(fascicolo, "oggetto", ""))
    rg = _text(getattr(fascicolo, "numero_rg", ""))
    if title and rg:
        return f"{title} - RG {rg}"
    return title or rg or "Fascicolo senza titolo"


def _case_customer_id(fascicolo: Any) -> str:
    return _text(getattr(fascicolo, "id_cliente", ""))


def _record_amount(preventivo: Any) -> str:
    return _money(getattr(preventivo, "totale", 0))


def _preventivo_record(preventivo: Any, clienti: dict[str, Any], fascicoli: dict[str, Any]) -> dict[str, Any]:
    pid = _text(getattr(preventivo, "id", ""))
    status = _enum(getattr(preventivo, "stato", ""))
    id_cliente = _text(getattr(preventivo, "id_cliente", ""))
    id_fascicolo = _text(getattr(preventivo, "id_fascicolo", ""))
    return {
        "id": pid,
        "kind": "preventivo",
        "number": _text(getattr(preventivo, "numero", "")) or pid,
        "subject": _text(getattr(preventivo, "oggetto", "")) or "Oggetto non indicato",
        "customerName": _client_label(clienti.get(id_cliente)),
        "caseTitle": _case_label(fascicoli.get(id_fascicolo)) if id_fascicolo else "",
        "amountDisplay": _record_amount(preventivo),
        "issuedAt": _date_label(getattr(preventivo, "data_emissione", "")),
        "dueAt": _date_label(getattr(preventivo, "data_scadenza", "")),
        "engagementAt": "",
        "state": status,
        "stateLabel": _status_label(status),
        "stateTone": _status_tone(status),
        "detailHref": f"/preventivi/p/{pid}?_legacy=1" if pid else "",
        "wizardHref": "/preventivi/wizard?_legacy=1",
        "legacyHref": "/preventivi?_legacy=1",
    }


def _conferimento_record(conferimento: Any, clienti: dict[str, Any], fascicoli: dict[str, Any]) -> dict[str, Any]:
    cid = _text(getattr(conferimento, "id", ""))
    status = _enum(getattr(conferimento, "stato", ""))
    id_cliente = _text(getattr(conferimento, "id_cliente", ""))
    id_fascicolo = _text(getattr(conferimento, "id_fascicolo", ""))
    return {
        "id": cid,
        "kind": "conferimento",
        "number": _text(getattr(conferimento, "numero", "")) or cid,
        "subject": _text(getattr(conferimento, "oggetto", "")) or "Oggetto non indicato",
        "customerName": _client_label(clienti.get(id_cliente)),
        "caseTitle": _case_label(fascicoli.get(id_fascicolo)) if id_fascicolo else "",
        "amountDisplay": _money(getattr(conferimento, "compenso_pattuito", 0)),
        "issuedAt": "",
        "dueAt": "",
        "engagementAt": _date_label(getattr(conferimento, "data_incarico", "")),
        "state": status,
        "stateLabel": _status_label(status),
        "stateTone": _status_tone(status),
        "detailHref": f"/preventivi/conferimento/{cid}?_legacy=1" if cid else "",
        "wizardHref": "",
        "legacyHref": "/preventivi?_legacy=1",
    }


def _selected(args: dict[str, Any], *names: str) -> str:
    for name in names:
        value = _text(args.get(name))
        if value:
            return value
    return ""


def _customer_options(clienti: list[Any]) -> list[dict[str, Any]]:
    options = [_option("", "Seleziona cliente")]
    options.extend(_option(getattr(cliente, "id", ""), _client_label(cliente)) for cliente in clienti)
    return options


def _case_options(fascicoli: list[Any], clienti: dict[str, Any]) -> list[dict[str, Any]]:
    options = [_option("", "Nessun fascicolo collegato")]
    for fascicolo in fascicoli:
        customer = clienti.get(_case_customer_id(fascicolo))
        options.append(_option(getattr(fascicolo, "id", ""), _case_label(fascicolo), _client_label(customer) if customer else ""))
    return options


def _preventivo_options(preventivi: list[Any], clienti: dict[str, Any]) -> list[dict[str, Any]]:
    options = [_option("", "Nessun preventivo collegato")]
    for preventivo in preventivi:
        customer = clienti.get(_text(getattr(preventivo, "id_cliente", "")))
        number = _text(getattr(preventivo, "numero", "")) or _text(getattr(preventivo, "id", ""))
        subject = _text(getattr(preventivo, "oggetto", ""))
        label = f"{number} - {subject}" if subject else number
        options.append(_option(getattr(preventivo, "id", ""), label, _client_label(customer) if customer else ""))
    return options


def _form_preventivo(
    clienti_list: list[Any],
    fascicoli_list: list[Any],
    clienti: dict[str, Any],
    query: dict[str, Any] | None,
) -> dict[str, Any]:
    args = query or {}
    today = date.today()
    due = today + timedelta(days=30)
    fields = [
        {
            "name": "id_cliente",
            "label": "Cliente",
            "type": "select",
            "required": True,
            "value": _selected(args, "id_cliente", "from_cliente"),
            "options": _customer_options(clienti_list),
        },
        {
            "name": "id_fascicolo",
            "label": "Fascicolo",
            "type": "select",
            "required": False,
            "value": _selected(args, "id_fascicolo"),
            "options": _case_options(fascicoli_list, clienti),
        },
        {"name": "from_cliente", "label": "from_cliente", "type": "hidden", "value": _selected(args, "from_cliente")},
        {"name": "id_pratica", "label": "id_pratica", "type": "hidden", "value": _selected(args, "id_pratica")},
        {"name": "area_pratica", "label": "area_pratica", "type": "hidden", "value": _selected(args, "area_pratica")},
    ]
    return {
        "id": "nuovo_preventivo",
        "title": "Nuovo preventivo",
        "description": "Il form invia alla route Flask esistente; motore economico e documenti restano nei percorsi auditati.",
        "action": "/preventivi/nuovo",
        "method": "POST",
        "submitLabel": "Crea preventivo",
        "enabled": True,
        "fields": fields,
        "defaults": {
            "subject": _text(args.get("oggetto")),
            "issuedAt": _text(args.get("data_emissione")) or today.isoformat(),
            "dueAt": _text(args.get("data_scadenza")) or due.isoformat(),
            "note": _text(args.get("note")),
            "lineDescription": _text(args.get("descrizione")),
            "lineAmount": _text(args.get("importo")),
            "lineType": _text(args.get("voce_tipo")) or "ONORARIO",
            "withFund": _text(args.get("applica_cassa") or "1") != "0",
            "withVat": _text(args.get("applica_iva") or "1") != "0",
            "practiceKind": _text(args.get("tipo_procedimento")),
            "feeKind": _text(args.get("tipo_compenso")),
            "value": _text(args.get("valore_controversia")),
            "complexity": _text(args.get("complessita")),
        },
    }


def _form_conferimento(
    clienti_list: list[Any],
    fascicoli_list: list[Any],
    preventivi: list[Any],
    clienti: dict[str, Any],
    query: dict[str, Any] | None,
) -> dict[str, Any]:
    args = query or {}
    today = date.today()
    fields = [
        {
            "name": "id_cliente",
            "label": "Cliente",
            "type": "select",
            "required": True,
            "value": _selected(args, "id_cliente", "from_cliente"),
            "options": _customer_options(clienti_list),
        },
        {
            "name": "id_fascicolo",
            "label": "Fascicolo",
            "type": "select",
            "required": False,
            "value": _selected(args, "id_fascicolo"),
            "options": _case_options(fascicoli_list, clienti),
        },
        {
            "name": "id_preventivo",
            "label": "Preventivo collegato",
            "type": "select",
            "required": False,
            "value": _selected(args, "id_preventivo"),
            "options": _preventivo_options(preventivi, clienti),
        },
        {"name": "from_cliente", "label": "from_cliente", "type": "hidden", "value": _selected(args, "from_cliente")},
        {"name": "id_pratica", "label": "id_pratica", "type": "hidden", "value": _selected(args, "id_pratica")},
        {"name": "area_pratica", "label": "area_pratica", "type": "hidden", "value": _selected(args, "area_pratica")},
    ]
    return {
        "id": "nuovo_conferimento",
        "title": "Nuovo conferimento incarico",
        "description": "Il form invia alla route Flask esistente; firme, stati e apertura fascicolo restano nel workflow legacy.",
        "action": "/preventivi/conferimento/nuovo",
        "method": "POST",
        "submitLabel": "Crea conferimento",
        "enabled": True,
        "fields": fields,
        "defaults": {
            "subject": _text(args.get("oggetto")),
            "engagementAt": _text(args.get("data_incarico")) or today.isoformat(),
            "lawyer": _text(args.get("avvocato_referente")),
            "amount": _text(args.get("compenso_pattuito")),
            "hourly": _text(args.get("tariffa_oraria")),
            "note": _text(args.get("note")),
            "barNumber": _text(args.get("numero_iscrizione_albo")),
            "barCouncil": _text(args.get("ordine_avvocati")),
            "feeKind": _text(args.get("tipo_compenso")),
            "practiceKind": _text(args.get("tipo_procedimento")),
            "openCaseGuided": _text(args.get("apri_fascicolo_guidato")) == "1",
            "art13Notice": _text(args.get("informativa_art13_resa") or "1") != "0",
            "adrClause": _text(args.get("clausola_adr_resa") or "1") != "0",
        },
    }


def build_react_preventivi_payload(
    *,
    get_preventivi: Callable[[], Any],
    get_clienti: Callable[[], Any],
    get_fascicoli: Callable[[], Any],
    query: dict[str, Any] | None = None,
    route: str = "/preventivi",
) -> dict[str, Any]:
    warnings: list[dict[str, str]] = [
        {
            "code": "scritture_legacy",
            "message": "I form React usano invio HTML standard verso le route Flask esistenti.",
        },
        {
            "code": "motore_legacy",
            "message": "Wizard, motore economico, stati avanzati e produzione documenti restano nei percorsi auditati.",
        },
    ]
    preventivi: list[Any] = []
    conferimenti: list[Any] = []
    try:
        manager = get_preventivi()
        preventivi = list(getattr(manager, "tutti_preventivi", lambda: [])())
        conferimenti = list(getattr(manager, "tutti_conferimenti", lambda: [])())
    except Exception as exc:
        warnings.append({
            "code": "preventivi_non_disponibili",
            "message": f"Archivio preventivi non disponibile: {type(exc).__name__}.",
        })

    clienti_list = _safe_all(get_clienti, "tutti", warnings, "clienti")
    fascicoli_list = _safe_all(get_fascicoli, "tutti", warnings, "fascicoli")
    clienti = {_text(getattr(cliente, "id", "")): cliente for cliente in clienti_list}
    fascicoli = {_text(getattr(fascicolo, "id", "")): fascicolo for fascicolo in fascicoli_list}

    preventivo_records = [_preventivo_record(item, clienti, fascicoli) for item in preventivi[:120]]
    conferimento_records = [_conferimento_record(item, clienti, fascicoli) for item in conferimenti[:120]]
    records = preventivo_records + conferimento_records

    open_preventivi = [item for item in preventivo_records if item["state"] in {"BOZZA", "IN_CALCOLO", "GENERATO", "VERIFICATO", "INVIATO", "APERTO"}]
    accepted_preventivi = [item for item in preventivo_records if item["state"] in {"ACCETTATO", "CONVERTITO"}]
    active_engagements = [item for item in conferimento_records if item["state"] == "ATTIVO"]
    state_codes = [
        "BOZZA",
        "GENERATO",
        "INVIATO",
        "ACCETTATO",
        "SCADUTO",
        "CONVERTITO",
    ]
    engagement_codes = ["ATTIVO", "DEFINITO", "REVOCATO"]

    payload = {
        "source": "repository_reali",
        "generated_at": _iso_now(),
        "contracts": {
            "mock_fallback": False,
            "writes": "legacy_routes",
            "route_owner": "react_shell",
            "legacy_contract": "artifacts/react-migration/legacy-contracts/preventivi.json",
        },
        "metrics": [
            _metric("preventivi_totali", "Preventivi", len(preventivo_records), "Archivio corrente", "primary"),
            _metric("preventivi_attivi", "Preventivi aperti", len(open_preventivi), "Bozze e invii non chiusi", "warning" if open_preventivi else "neutral"),
            _metric("preventivi_accettati", "Accettati o convertiti", len(accepted_preventivi), "Stati dal repository", "success" if accepted_preventivi else "neutral"),
            _metric("conferimenti_attivi", "Incarichi attivi", len(active_engagements), "Conferimenti in corso", "success" if active_engagements else "neutral"),
        ],
        "sections": [
            _section(
                "stati_preventivo",
                "Stati preventivo",
                "distribution",
                [
                    _item(code.lower(), _status_label(code), len([row for row in preventivo_records if row["state"] == code]), "Conteggio archivio corrente", _status_tone(code))
                    for code in state_codes
                ],
                "Nessun preventivo nell'archivio.",
            ),
            _section(
                "stati_conferimento",
                "Stati conferimento",
                "distribution",
                [
                    _item(code.lower(), _status_label(code), len([row for row in conferimento_records if row["state"] == code]), "Conteggio archivio corrente", _status_tone(code))
                    for code in engagement_codes
                ],
                "Nessun conferimento nell'archivio.",
            ),
            _section(
                "funzioni_legacy",
                "Funzioni conservate",
                "legacy-routes",
                [
                    _item("dettaglio", "Dettagli e workflow", "legacy", "Stati, firme e azioni sensibili restano Flask", "warning"),
                    _item("wizard", "Wizard compensi", "legacy", "Parametri forensi e log economico restano nel motore esistente", "warning"),
                    _item("tariffario", "Tariffario e compensi", "legacy", "La consultazione economica avanzata non viene sbloccata", "warning"),
                ],
                "Nessuna funzione legacy rilevata.",
            ),
        ],
        "records": records,
        "actions": [
            _action("nuovo_preventivo", "Nuovo preventivo", "/preventivi/nuovo", "primary"),
            _action("nuovo_conferimento", "Nuovo conferimento", "/preventivi/conferimento/nuovo", "primary"),
            _action("wizard", "Wizard legacy", "/preventivi/wizard?_legacy=1", "neutral"),
            _action("compensi", "Compensi forensi legacy", "/compensi-forensi?_legacy=1", "neutral"),
            _action("tariffario", "Tariffario legacy", "/tariffario?_legacy=1", "neutral"),
            _action("legacy", "Archivio legacy", "/preventivi?_legacy=1", "warning"),
        ],
        "forms": [
            _form_preventivo(clienti_list, fascicoli_list, clienti, query),
            _form_conferimento(clienti_list, fascicoli_list, preventivi, clienti, query),
        ],
        "warnings": warnings,
    }
    if route == "/preventivi/nuovo":
        payload["contracts"]["legacy_contract"] = "artifacts/react-migration/legacy-contracts/preventivi__nuovo.json"
    if route == "/preventivi/conferimento/nuovo":
        payload["contracts"]["legacy_contract"] = "artifacts/react-migration/legacy-contracts/preventivi__conferimento__nuovo.json"
    return payload


def build_react_preventivi_error_payload(message: str = "Preventivi non disponibili.") -> dict[str, Any]:
    return {
        "source": "errore_controllato",
        "generated_at": _iso_now(),
        "contracts": {
            "mock_fallback": False,
            "writes": "legacy_routes",
            "route_owner": "react_shell",
            "legacy_contract": "artifacts/react-migration/legacy-contracts/preventivi.json",
        },
        "metrics": [],
        "sections": [],
        "records": [],
        "actions": [_action("legacy", "Archivio legacy", "/preventivi?_legacy=1", "warning")],
        "forms": [],
        "warnings": [{"code": "preventivi_errore_controllato", "message": message}],
    }
